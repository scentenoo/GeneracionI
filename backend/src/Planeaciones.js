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

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const fotoId = guardarArchivoBase64_(
      'Fotos de clase',
      fotos.foto_clase.base64,
      fotos.foto_clase.mimeType || 'image/jpeg',
      `clase_${sesion.id}_${datos.fecha}.jpg`
    );

    const fila = appendRow_(SHEET_NAMES.PLANEACIONES, {
      docente_id: sesion.id,
      curso_id: curso.id,
      fecha: datos.fecha,
      // Copia del nombre del curso tal como estaba ese día, para que la
      // Sheet se pueda leer sin cruzar referencias a mano.
      grupo: curso.nombre,
      objetivo: datos.objetivo,
      temas_vistos: JSON.stringify(datos.temas_vistos || []),
      bloques: JSON.stringify(datos.bloques),
      foto_clase_drive_id: fotoId,
      // Snapshot: la asistencia queda tal cual estaba ese día, no referencia
      // viva al grupo actual (evita que cambios posteriores alteren planeaciones ya guardadas).
      asistencia: JSON.stringify(datos.asistencia || []),
      horas: sumarMinutosBloques_(datos.bloques) / 60,
      creado_en: new Date().toISOString(),
    });

    return { ok: true, id: fila.id };
  } finally {
    lock.releaseLock();
  }
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

  if (String(targetId) !== String(sesion.id) && !esDirectivo_(sesion)) {
    throw new Error('No tienes permiso para ver planeaciones de otro docente');
  }

  const filas = readRowsWhere_(
    SHEET_NAMES.PLANEACIONES,
    (p) =>
      String(p.docente_id) === String(targetId) &&
      (!curso_id || String(p.curso_id) === String(curso_id))
  );

  if (resumen) {
    return filas.map((p) => ({
      id: p.id,
      docente_id: p.docente_id,
      curso_id: p.curso_id,
      fecha: p.fecha,
      grupo: p.grupo,
      objetivo: p.objetivo,
      horas: p.horas,
    }));
  }
  return filas.map(parsePlaneacionRow_);
}

/** Una sola planeación completa, para abrirla en el editor. */
function obtener_planeacion(token, id) {
  const sesion = requireSession_(token);

  const fila = findRowById_(SHEET_NAMES.PLANEACIONES, id);
  if (!fila) throw new Error(`No se encontró la planeación ${id}`);
  if (String(fila.docente_id) !== String(sesion.id) && !esDirectivo_(sesion)) {
    throw new Error('No tienes permiso para ver esa planeación');
  }
  return parsePlaneacionRow_(fila);
}

function parsePlaneacionRow_(p) {
  return Object.assign({}, p, {
    temas_vistos: JSON.parse(p.temas_vistos || '[]'),
    bloques: JSON.parse(p.bloques || '[]'),
    asistencia: JSON.parse(p.asistencia || '[]'),
  });
}

/**
 * Edita el docente dueño (CRUD sobre lo suyo) o un directivo sobre la de
 * cualquiera — pero el directivo nunca elimina, ver eliminar_planeacion.
 * Todo queda registrado en Historial.
 */
function editar_planeacion(token, id, cambios) {
  const sesion = requireSession_(token);

  const fila = findRowById_(SHEET_NAMES.PLANEACIONES, id);
  if (!fila) throw new Error(`No se encontró la planeación ${id}`);

  const esDueno = String(fila.docente_id) === String(sesion.id);
  if (!esDueno && !esDirectivo_(sesion)) {
    throw new Error('Solo podés editar tus propias planeaciones');
  }

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const cambiosSerializados = Object.assign({}, cambios);
    ['temas_vistos', 'bloques', 'asistencia'].forEach((campo) => {
      if (cambiosSerializados[campo] !== undefined) {
        cambiosSerializados[campo] = JSON.stringify(cambiosSerializados[campo]);
      }
    });

    const cambiosReales = updateRowById_(SHEET_NAMES.PLANEACIONES, id, cambiosSerializados);
    registrarHistorial_(sesion.usuario, 'planeacion', id, cambiosReales);
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

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    if (fila.foto_clase_drive_id) {
      try {
        DriveApp.getFileById(fila.foto_clase_drive_id).setTrashed(true);
      } catch (e) {
        // La foto ya no existe o no es accesible: no bloquea el borrado de la fila.
      }
    }
    getSheet_(SHEET_NAMES.PLANEACIONES).deleteRow(fila._row);
    registrarHistorial_(sesion.usuario, 'planeacion', id, [
      { campo: 'eliminada', antes: `${fila.fecha} - ${fila.grupo}`, despues: '' },
    ]);
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
  if (String(curso.docente_id) !== String(sesion.id) && !esDirectivo_(sesion)) {
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
