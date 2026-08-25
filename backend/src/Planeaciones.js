/**
 * Planeaciones de clase (rol docente). Las horas salen de sumar los
 * minutos de los bloques, con un mínimo de 2 horas por clase — antes eran
 * 2 fijas y el tiempo iba escrito dentro del texto del momento, así que no
 * se podía ni sumar ni validar.
 */

function guardar_planeacion(token, datos, fotos) {
  const sesion = requireSession_(token);
  requireRole_(sesion, [ROLES.DOCENTE, ROLES.AMBOS]);
  validarPlaneacion_(datos, fotos, esDirectivo_(sesion));

  const curso = requireCursoDelDocente_(datos.curso_id, sesion.id);
  // Cargar una clase de un mes ya cerrado también le cambia la cuenta al
  // equipo directivo, así que se bloquea igual que editar.
  requireMesAbierto_(sesion, curso.id, mesDeFecha_(datos.fecha));

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    // Una clase es única por curso y fecha: no hay dos clases del mismo
    // curso el mismo día (son 4 semanales al mes). Si ya existe una, se
    // ACTUALIZA en vez de agregar otra. Así, si el docente aprieta Guardar
    // varias veces porque la app se ve trabada —o si el cliente cortó por
    // timeout pero el servidor sí había guardado— nunca quedan duplicados.
    const dia = fechaISO_(datos.fecha);
    const existente = readRowsWhere_(
      SHEET_NAMES.PLANEACIONES,
      (p) => String(p.curso_id) === String(curso.id) && fechaISO_(p.fecha) === dia
    )[0];

    // La carpeta se resuelve una sola vez: antes de que hubiera hasta 3
    // fotos por clase, guardarArchivoBase64_ la buscaba/creaba (4 niveles)
    // por cada llamada; con varias fotos eso repetía la misma búsqueda
    // varias veces por nada.
    const fotosClase = normalizarFotosClase_(fotos);
    const carpetaFotos = getOrCrearRutaCarpetas_(
      ['Planeaciones', curso.nombre, nombreCarpetaMes_(datos.fecha), 'Fotos']
    );
    const fotoIds = fotosClase.map((foto, i) =>
      guardarArchivoEnCarpeta_(
        carpetaFotos,
        foto.base64,
        foto.mimeType || 'image/jpeg',
        nombreDeFoto_(`clase_${i + 1}`, curso.nombre, datos.fecha)
      )
    );

    const campos = {
      docente_id: sesion.id,
      curso_id: curso.id,
      fecha: datos.fecha,
      // Copia del nombre del curso tal como estaba ese día, para que la
      // Sheet se pueda leer sin cruzar referencias a mano.
      grupo: curso.nombre,
      objetivo: datos.objetivo,
      temas_vistos: JSON.stringify(datos.temas_vistos || []),
      // Formato Diario Pedagógico: los tres momentos y las dos columnas de
      // toda la clase. `bloques` queda vacío (era el formato viejo).
      bloques: '[]',
      momentos: JSON.stringify(datos.momentos || {}),
      observaciones: datos.observaciones || '',
      avances: datos.avances || '',
      // La primera queda también en foto_clase_drive_id -- de ahí la toma
      // el informe mensual (una sola foto por clase) y así una planeación
      // vieja, guardada antes de este campo, se sigue leyendo igual.
      foto_clase_drive_id: fotoIds[0],
      fotos_clase_drive_ids: JSON.stringify(fotoIds),
      // Snapshot: la asistencia queda tal cual estaba ese día, no referencia
      // viva al grupo actual (evita que cambios posteriores alteren planeaciones ya guardadas).
      asistencia: JSON.stringify(datos.asistencia || []),
      horas: sumarMinutosMomentos_(datos.momentos) / 60,
    };

    if (existente) {
      // Las fotos viejas quedan huérfanas en Drive: se mandan a la papelera.
      fotosClaseDriveIds_(existente).forEach(trasharSiExiste_);
      updateRowById_(SHEET_NAMES.PLANEACIONES, existente.id, campos);
      // Guardar de nuevo la deja pendiente de revisión otra vez.
      registrarEntrega_('planeacion', existente.id, SHEET_NAMES.PLANEACIONES, existente.id, sesion.usuario);
      return { ok: true, id: existente.id, actualizado: true };
    }

    campos.creado_en = new Date().toISOString();
    const fila = appendRow_(SHEET_NAMES.PLANEACIONES, campos);
    registrarEntrega_('planeacion', fila.id, SHEET_NAMES.PLANEACIONES, fila.id, sesion.usuario);
    return { ok: true, id: fila.id, actualizado: false };
  } finally {
    lock.releaseLock();
  }
}

/**
 * Guarda en Drive el documento de la planeación y se queda con su id.
 *
 * El informe mensual tiene una columna "LINK A PLANEACION" que en los
 * informes reales del programa apunta a un archivo de Drive; hasta ahora
 * iba vacía porque una planeación vive en una fila de Sheets y no tiene
 * URL propia. El .docx lo arma el cliente (Apps Script no puede rellenar
 * plantillas), así que lo sube apenas guarda y acá solo se archiva.
 *
 * Va aparte de guardar_planeacion para que la clase quede registrada
 * aunque el documento falle: el dato que importa es la planeación, el
 * archivo es la evidencia.
 */
function guardar_documento_planeacion(token, planeacion_id, archivo) {
  const sesion = requireSession_(token);

  const fila = findRowById_(SHEET_NAMES.PLANEACIONES, planeacion_id);
  if (!fila) throw new Error('Planeación no encontrada');
  if (String(fila.docente_id) !== String(sesion.id) && !puedeSupervisar_(sesion)) {
    throw new Error('No tienes permiso para modificar esa planeación');
  }
  if (!archivo || !archivo.base64) throw new Error('Falta el documento');

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const id = reemplazarArchivo_(
      ['Planeaciones', fila.grupo, nombreCarpetaMes_(fila.fecha), 'Documentos'],
      fila.doc_drive_id,
      archivo.base64,
      archivo.mimeType || 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      nombreDeDocumento_(fila.grupo, fila.fecha)
    );
    updateRowById_(SHEET_NAMES.PLANEACIONES, planeacion_id, { doc_drive_id: id });
    return { ok: true, link: urlDeArchivo_(id) };
  } finally {
    lock.releaseLock();
  }
}

/**
 * Los ids de Drive de las fotos de una planeación, en orden. Lee
 * `fotos_clase_drive_ids` (hasta 3, formato nuevo); si una fila vieja no lo
 * tiene, cae a la única foto de `foto_clase_drive_id`.
 */
function fotosClaseDriveIds_(fila) {
  if (fila.fotos_clase_drive_ids) {
    try {
      const ids = JSON.parse(fila.fotos_clase_drive_ids);
      if (Array.isArray(ids) && ids.length) return ids.filter(Boolean);
    } catch (e) {
      // Fila corrupta o vacía: cae al campo viejo de abajo.
    }
  }
  return fila.foto_clase_drive_id ? [fila.foto_clase_drive_id] : [];
}

/**
 * Las fotos de clase de una planeación (hasta 3), en base64, para
 * regenerar su .docx al editarla (el documento se arma en el cliente y
 * necesita las imágenes). Lista vacía si la planeación no tiene fotos.
 */
function obtener_foto_planeacion(token, id) {
  const sesion = requireSession_(token);
  const fila = findRowById_(SHEET_NAMES.PLANEACIONES, id);
  if (!fila) throw new Error(`No se encontró la planeación ${id}`);
  if (String(fila.docente_id) !== String(sesion.id) && !puedeSupervisar_(sesion)) {
    throw new Error('No tienes permiso para ver esa planeación');
  }
  return fotosClaseDriveIds_(fila)
    .map((driveId) => archivoABase64_(driveId))
    .filter(Boolean)
    .map((foto) => ({ base64: foto.base64, mimeType: foto.mimeType }));
}

/**
 * Docente ve solo las suyas; directivo puede pedir las de cualquiera.
 * Con `curso_id` se acota a un curso — que es lo que necesita el informe
 * mensual, ya que va por curso y no por persona.
 *
 * Con `resumen` deja afuera los campos pesados. Las pantallas de lista
 * solo muestran fecha, curso y objetivo, pero los bloques son el 90% del
 * peso de cada fila y eso crece con cada mes de uso. Para editar una hay
 * obtener_planeacion, que sí la trae completa.
 */
function obtener_planeaciones(token, docente_id, curso_id, resumen) {
  const sesion = requireSession_(token);
  const targetId = docente_id || sesion.id;

  if (String(targetId) !== String(sesion.id) && !puedeSupervisar_(sesion)) {
    throw new Error('No tienes permiso para ver planeaciones de otro docente');
  }

  const filas = readRowsWhere_(
    SHEET_NAMES.PLANEACIONES,
    (p) =>
      String(p.docente_id) === String(targetId) &&
      (!curso_id || String(p.curso_id) === String(curso_id))
  );

  // El cierre se resuelve acá para que la lista pueda esconder editar y
  // borrar sin pedir una consulta por fila. Se lee Reaperturas una sola
  // vez y no una por planeación.
  const cerrado = calculadorDeCierre_(sesion);

  if (resumen) {
    return filas.map((p) => ({
      id: p.id,
      docente_id: p.docente_id,
      curso_id: p.curso_id,
      fecha: p.fecha,
      grupo: p.grupo,
      objetivo: p.objetivo,
      horas: p.horas,
      // El cliente lo usa para avisar antes de pisar una planeación ya
      // guardada (mismo curso y fecha): si estaba aprobada, guardar de
      // nuevo la vuelve a pendiente, y eso vale la pena que se sepa antes.
      estado: p.estado || ESTADO_PENDIENTE,
      bloqueada: cerrado(p.curso_id, mesDeFecha_(p.fecha)),
    }));
  }
  return filas.map((p) =>
    Object.assign(parsePlaneacionRow_(p), {
      bloqueada: cerrado(p.curso_id, mesDeFecha_(p.fecha)),
    })
  );
}

/** Una sola planeación completa, para abrirla en el editor. */
function obtener_planeacion(token, id) {
  const sesion = requireSession_(token);

  const fila = findRowById_(SHEET_NAMES.PLANEACIONES, id);
  if (!fila) throw new Error(`No se encontró la planeación ${id}`);
  if (String(fila.docente_id) !== String(sesion.id) && !puedeSupervisar_(sesion)) {
    throw new Error('No tienes permiso para ver esa planeación');
  }
  const datos = parsePlaneacionRow_(fila);
  // El historial de revisión viaja con la planeación para imprimirse al
  // final del documento cuando fue devuelta alguna vez (ver docx_generator).
  datos.historial = historialDe_('planeacion', String(id));
  return datos;
}

function parsePlaneacionRow_(p) {
  return Object.assign({}, p, {
    temas_vistos: JSON.parse(p.temas_vistos || '[]'),
    bloques: JSON.parse(p.bloques || '[]'),
    momentos: JSON.parse(p.momentos || '{}'),
    observaciones: p.observaciones || '',
    avances: p.avances || '',
    asistencia: JSON.parse(p.asistencia || '[]'),
  });
}

/**
 * Edita el docente dueño (CRUD sobre lo suyo) o un directivo sobre la de
 * cualquiera — pero el directivo nunca elimina, ver eliminar_planeacion.
 */
function editar_planeacion(token, id, cambios) {
  const sesion = requireSession_(token);

  const fila = findRowById_(SHEET_NAMES.PLANEACIONES, id);
  if (!fila) throw new Error(`No se encontró la planeación ${id}`);

  const esDueno = String(fila.docente_id) === String(sesion.id);
  if (!esDueno && !puedeSupervisar_(sesion)) {
    throw new Error('Solo podés editar tus propias planeaciones');
  }
  requireMesAbierto_(sesion, fila.curso_id, mesDeFecha_(fila.fecha));

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    // A diferencia de guardar_planeacion, acá no hay "actualizar en vez de
    // duplicar": esto edita una fila puntual por id. Si el cambio de fecha
    // hace que coincida con OTRA planeación del mismo curso, no hay forma
    // de fusionarlas — se rechaza, para no terminar con dos filas de la
    // misma fecha (el bug que justo evita guardar_planeacion).
    if (cambios.fecha !== undefined) {
      const diaNuevo = fechaISO_(cambios.fecha);
      const colision = readRowsWhere_(
        SHEET_NAMES.PLANEACIONES,
        (p) => String(p.id) !== String(id) &&
          String(p.curso_id) === String(fila.curso_id) &&
          fechaISO_(p.fecha) === diaNuevo
      )[0];
      if (colision) {
        throw new Error(
          `Ya existe otra planeación de este curso para el ${fechaCorta_(diaNuevo)}. ` +
          'No se puede tener dos clases el mismo día — elegí otra fecha.'
        );
      }
    }

    const cambiosSerializados = Object.assign({}, cambios);
    ['temas_vistos', 'bloques', 'momentos', 'asistencia'].forEach((campo) => {
      if (cambiosSerializados[campo] !== undefined) {
        cambiosSerializados[campo] = JSON.stringify(cambiosSerializados[campo]);
      }
    });
    // Si cambiaron los momentos, recalcular las horas para que no queden
    // desfasadas de los minutos nuevos.
    if (cambios.momentos !== undefined) {
      cambiosSerializados.horas = sumarMinutosMomentos_(cambios.momentos) / 60;
    }

    const cambiosReales = updateRowById_(SHEET_NAMES.PLANEACIONES, id, cambiosSerializados);
    // Editarla la vuelve a dejar pendiente de revisión (si venía devuelta,
    // queda como reenviada).
    registrarEntrega_('planeacion', id, SHEET_NAMES.PLANEACIONES, id, sesion.usuario);
    return { ok: true, cambios: cambiosReales.length };
  } finally {
    lock.releaseLock();
  }
}

/**
 * Solo el docente dueño puede eliminar su propia planeación (spec sección
 * 3: "Docente: CRUD de sus propias planeaciones"). El directivo edita pero
 * nunca elimina — ver editar_planeacion.
 */
function eliminar_planeacion(token, id) {
  const sesion = requireSession_(token);
  const fila = findRowById_(SHEET_NAMES.PLANEACIONES, id);
  if (!fila) throw new Error(`No se encontró la planeación ${id}`);
  if (String(fila.docente_id) !== String(sesion.id)) {
    throw new Error('Solo podés eliminar tus propias planeaciones');
  }
  requireMesAbierto_(sesion, fila.curso_id, mesDeFecha_(fila.fecha));

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    fotosClaseDriveIds_(fila).forEach(trasharSiExiste_);
    trasharSiExiste_(fila.doc_drive_id);
    getSheet_(SHEET_NAMES.PLANEACIONES).deleteRow(fila._row);
    // Los ids se reusan, así que el historial de esta planeación no puede
    // quedar suelto para que lo herede la próxima con el mismo id.
    borrarRevisiones_('planeacion', String(id));
    return { ok: true };
  } finally {
    lock.releaseLock();
  }
}

/**
 * Cuántas planeaciones lleva un CURSO en el mes vs las esperadas.
 * Va por curso y no por docente porque el informe mensual también va por
 * curso: quien tiene dos cursos puede ir al día en uno y atrasado en otro.
 * mes en formato 'YYYY-MM'.
 */
function obtener_estado_mes(token, curso_id, mes) {
  const sesion = requireSession_(token);

  const curso = findRowById_(SHEET_NAMES.CURSOS, curso_id);
  if (!curso) throw new Error('Curso no encontrado');
  if (String(curso.docente_id) !== String(sesion.id) && !puedeSupervisar_(sesion)) {
    throw new Error('No tienes permiso para ver el estado de ese curso');
  }

  const planeaciones = readRowsWhere_(
    SHEET_NAMES.PLANEACIONES,
    (p) => String(p.curso_id) === String(curso_id) && mesDeFecha_(p.fecha) === mes
  );

  const informe = readRowsWhere_(
    SHEET_NAMES.INFORMES,
    (i) => String(i.curso_id) === String(curso_id) && mesDeFecha_(i.mes) === mes
  )[0];

  return {
    curso_id: curso.id,
    curso: curso.nombre,
    docente_id: curso.docente_id,
    mes: mes,
    registradas: planeaciones.length,
    esperadas: CLASES_ESPERADAS_POR_MES,
    faltantes: Math.max(0, CLASES_ESPERADAS_POR_MES - planeaciones.length),
    informe_entregado: !!informe,
    informe_actualizado_en: informe ? informe.actualizado_en : '',
  };
}
