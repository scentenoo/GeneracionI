/**
 * Actividades del mes que NO son clases: reuniones, claustros, informes,
 * atención a padres.
 *
 * En el informe real de julio de Samir, cuatro clases sumaban 8 horas y
 * las otras tres filas —reunión docente, comité de padres, informe de
 * respuestas— sumaban las otras 8. Sin poder registrarlas, la cuenta de
 * cobro salía por la mitad.
 *
 * Las clases NO se guardan acá: viven en Planeaciones, que ya lleva sus
 * horas. El informe mensual junta las dos fuentes. Separarlas evita tener
 * el mismo dato en dos lados.
 *
 * `horas_sede` y `horas_externas` son las dos columnas del formato: dónde
 * se hizo, no de qué tipo es. Se pagan al mismo valor, así que para la
 * cuenta de cobro lo único que importa es la suma.
 */

/** Valida lo común a crear y editar, y devuelve el curso ya resuelto. */
function validarActividad_(sesion, datos) {
  if (!datos.fecha) throw new Error('Falta la fecha');
  if (!datos.descripcion) throw new Error('Falta describir la actividad');

  const horasSede = Number(datos.horas_sede) || 0;
  const horasExternas = Number(datos.horas_externas) || 0;
  if (horasSede + horasExternas <= 0) {
    throw new Error('La actividad tiene que tener al menos una hora');
  }

  // El informe va por curso, así que la actividad tiene que ir en el de
  // alguno: quien tiene varios elige en cuál la reporta, y así no se
  // cuenta dos veces.
  const curso = findRowById_(SHEET_NAMES.CURSOS, datos.curso_id);
  if (!curso) throw new Error('Elija en el informe de qué curso va esta actividad');
  if (String(curso.docente_id) !== String(sesion.id) && !puedeSupervisar_(sesion)) {
    throw new Error('Ese curso no es suyo');
  }

  return { curso: curso, horasSede: horasSede, horasExternas: horasExternas };
}

function guardar_actividad(token, datos, fotos) {
  const sesion = requireSession_(token);
  const { curso, horasSede, horasExternas } = validarActividad_(sesion, datos);
  // Cargar una actividad de un mes ya cerrado también le cambia la cuenta
  // de cobro al equipo directivo, igual que con una clase.
  requireMesAbierto_(sesion, curso.id, mesDeFecha_(datos.fecha));

  // La foto es la evidencia de que la actividad pasó, igual que en la
  // clase. Solo un directivo puede registrarla sin nada.
  if (!fotos || !fotos.foto) {
    if (!esDirectivo_(sesion)) throw new Error('Falta la foto de la actividad');
  }

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  invalidarCacheHojas_();
  try {
    let fotoId = '';
    if (fotos && fotos.foto) {
      fotoId = guardarArchivoBase64_(
        ['Actividades', curso.nombre, nombreCarpetaMes_(datos.fecha), 'Fotos'],
        fotos.foto.base64,
        fotos.foto.mimeType || 'image/jpeg',
        nombreDeFoto_('actividad', curso.nombre, datos.fecha)
      );
    }

    const fila = appendRow_(SHEET_NAMES.ACTIVIDADES, {
      usuario_id: curso.docente_id,
      curso_id: curso.id,
      fecha: datos.fecha,
      descripcion: datos.descripcion,
      horas_sede: horasSede,
      horas_externas: horasExternas,
      foto_drive_id: fotoId,
      creado_en: new Date().toISOString(),
    });
    return { ok: true, id: fila.id };
  } finally {
    lock.releaseLock();
  }
}

/**
 * Edita una actividad. `fotos` es opcional: sin foto nueva se conserva la
 * que ya tenía, no se borra.
 */
function editar_actividad(token, id, datos, fotos) {
  const sesion = requireSession_(token);

  const fila = findRowById_(SHEET_NAMES.ACTIVIDADES, id);
  if (!fila) throw new Error(`No se encontró la actividad ${id}`);
  if (String(fila.usuario_id) !== String(sesion.id) && !puedeSupervisar_(sesion)) {
    throw new Error('Solo puede editar sus propias actividades');
  }
  requireMesAbierto_(sesion, fila.curso_id, mesDeFecha_(fila.fecha));

  const { curso, horasSede, horasExternas } = validarActividad_(sesion, datos);

  if (!fila.foto_drive_id && !(fotos && fotos.foto) && !esDirectivo_(sesion)) {
    throw new Error('Falta la foto de la actividad');
  }

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  invalidarCacheHojas_();
  try {
    const cambios = {
      curso_id: curso.id,
      fecha: datos.fecha,
      descripcion: datos.descripcion,
      horas_sede: horasSede,
      horas_externas: horasExternas,
    };

    if (fotos && fotos.foto) {
      cambios.foto_drive_id = reemplazarArchivo_(
        ['Actividades', curso.nombre, nombreCarpetaMes_(datos.fecha), 'Fotos'],
        fila.foto_drive_id,
        fotos.foto.base64,
        fotos.foto.mimeType || 'image/jpeg',
        nombreDeFoto_('actividad', curso.nombre, datos.fecha)
      );
    }

    const cambiosReales = updateRowById_(SHEET_NAMES.ACTIVIDADES, id, cambios);
    return { ok: true, cambios: cambiosReales.length };
  } finally {
    lock.releaseLock();
  }
}

/** Las del curso indicado; con `mes` ('YYYY-MM') se acota al mes. */
function obtener_actividades(token, curso_id, mes) {
  const sesion = requireSession_(token);

  const curso = findRowById_(SHEET_NAMES.CURSOS, curso_id);
  if (!curso) throw new Error('Curso no encontrado');
  if (String(curso.docente_id) !== String(sesion.id) && !puedeSupervisar_(sesion)) {
    throw new Error('No tiene permiso para ver las actividades de ese curso');
  }

  const cerrado = calculadorDeCierre_(sesion);
  return readRowsWhere_(
    SHEET_NAMES.ACTIVIDADES,
    (a) => String(a.curso_id) === String(curso_id) && (!mes || mesDeFecha_(a.fecha) === mes)
  ).map((a) => Object.assign({}, a, { bloqueada: cerrado(a.curso_id, mesDeFecha_(a.fecha)) }));
}

/** Solo el dueño borra las suyas, igual que con las planeaciones. */
function eliminar_actividad(token, id) {
  const sesion = requireSession_(token);

  const fila = findRowById_(SHEET_NAMES.ACTIVIDADES, id);
  if (!fila) throw new Error(`No se encontró la actividad ${id}`);
  if (String(fila.usuario_id) !== String(sesion.id)) {
    throw new Error('Solo puede eliminar sus propias actividades');
  }
  requireMesAbierto_(sesion, fila.curso_id, mesDeFecha_(fila.fecha));

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  invalidarCacheHojas_();
  try {
    trasharSiExiste_(fila.foto_drive_id);
    eliminarFila_(SHEET_NAMES.ACTIVIDADES, fila);
    return { ok: true };
  } finally {
    lock.releaseLock();
  }
}
