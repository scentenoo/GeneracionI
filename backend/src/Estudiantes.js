/**
 * Grupo de estudiantes por docente. Lo gestiona el directivo (puede
 * modificarlo cuando quiera); el docente solo lo consulta y marca
 * asistencia sobre él.
 */

function importar_estudiantes(token, docente_id, csv) {
  const sesion = requireSession_(token);
  requireRole_(sesion, [ROLES.DIRECTIVO, ROLES.AMBOS]);

  const filas = Utilities.parseCsv(csv);
  const encabezado = filas[0].map((h) => h.trim().toLowerCase());
  const idxNombre = encabezado.indexOf('nombre');
  if (idxNombre === -1) throw new Error('El CSV necesita una columna "nombre"');

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const creados = filas.slice(1).filter((fila) => fila[idxNombre]).map((fila) =>
      appendRow_(SHEET_NAMES.ESTUDIANTES, {
        nombre: fila[idxNombre].trim(),
        docente_id: docente_id,
      })
    );

    registrarHistorial_(sesion.usuario, 'grupo_estudiantes', docente_id, [
      { campo: 'importacion_csv', antes: '', despues: `${creados.length} estudiantes` },
    ]);

    return { ok: true, creados: creados.length };
  } finally {
    lock.releaseLock();
  }
}

function obtener_estudiantes(token, docente_id) {
  const sesion = requireSession_(token);
  const targetId = docente_id || sesion.id;
  if (String(targetId) !== String(sesion.id) && !esDirectivo_(sesion)) {
    throw new Error('No tienes permiso para ver el grupo de otro docente');
  }
  return readRowsWhere_(SHEET_NAMES.ESTUDIANTES, (e) => String(e.docente_id) === String(targetId));
}

/**
 * cambios = { agregar: [{nombre}], quitar: [id, ...] }
 * Nunca modifica planeaciones ya guardadas (esas tienen su propio snapshot
 * de asistencia) — solo afecta el grupo "actual" del docente.
 */
function modificar_grupo(token, docente_id, cambios) {
  const sesion = requireSession_(token);
  requireRole_(sesion, [ROLES.DIRECTIVO, ROLES.AMBOS]);

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const cambiosHistorial = [];

    (cambios.agregar || []).forEach((est) => {
      const fila = appendRow_(SHEET_NAMES.ESTUDIANTES, { nombre: est.nombre, docente_id: docente_id });
      cambiosHistorial.push({ campo: 'estudiante_agregado', antes: '', despues: `${fila.nombre} (id ${fila.id})` });
    });

    (cambios.quitar || []).forEach((estudianteId) => {
      const est = findRowById_(SHEET_NAMES.ESTUDIANTES, estudianteId);
      if (est) {
        getSheet_(SHEET_NAMES.ESTUDIANTES).deleteRow(est._row);
        cambiosHistorial.push({ campo: 'estudiante_quitado', antes: `${est.nombre} (id ${est.id})`, despues: '' });
      }
    });

    registrarHistorial_(sesion.usuario, 'grupo_estudiantes', docente_id, cambiosHistorial);
    return { ok: true, cambios: cambiosHistorial.length };
  } finally {
    lock.releaseLock();
  }
}
