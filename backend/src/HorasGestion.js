/**
 * Horas de gestión (planeación administrativa) — equivalente a las
 * planeaciones docentes pero para el rol directivo. Formato mucho más
 * libre: sin bloques, sin mínimo de palabras, sin foto obligatoria
 * (ver spec sección 6).
 */

function guardar_horas_gestion(token, datos) {
  const sesion = requireSession_(token);
  requireRole_(sesion, [ROLES.DIRECTIVO, ROLES.AMBOS]);

  if (!datos.fecha) throw new Error('Falta la fecha');
  if (!datos.actividad) throw new Error('Falta describir la actividad/tarea');
  if (!datos.horas_sede) throw new Error('Falta el número de horas');

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const fila = appendRow_(SHEET_NAMES.HORAS_GESTION, {
      directivo_id: sesion.id,
      fecha: datos.fecha,
      actividad: datos.actividad,
      horas_sede: datos.horas_sede,
      entregable: datos.entregable || '',
      link_soporte: datos.link_soporte || '',
      creado_en: new Date().toISOString(),
    });
    return { ok: true, id: fila.id };
  } finally {
    lock.releaseLock();
  }
}

function obtener_horas_gestion(token, directivo_id) {
  const sesion = requireSession_(token);
  const targetId = directivo_id || sesion.id;
  if (String(targetId) !== String(sesion.id) && !puedeSupervisar_(sesion)) {
    throw new Error('No tienes permiso para ver las horas de gestión de otro usuario');
  }
  return readRowsWhere_(
    SHEET_NAMES.HORAS_GESTION,
    (h) => String(h.directivo_id) === String(targetId)
  );
}

const CAMPOS_EDITABLES_GESTION_ = ['fecha', 'actividad', 'horas_sede', 'entregable', 'link_soporte'];

/**
 * Corrige una hora de gestión ya registrada. Solo el dueño: son sus horas
 * facturables, nadie más las toca.
 *
 * No lleva chequeo de cierre de mes: el cierre exime a los directivos
 * (ver requireMesAbierto_ en Cierre.js) y las horas de gestión siempre son
 * de un directivo, así que el corte nunca los alcanza.
 */
function editar_horas_gestion(token, id, cambios) {
  const sesion = requireSession_(token);

  const fila = findRowById_(SHEET_NAMES.HORAS_GESTION, id);
  if (!fila) throw new Error('No se encontró esa hora de gestión');
  if (String(fila.directivo_id) !== String(sesion.id)) {
    throw new Error('Solo podés editar tus propias horas de gestión');
  }

  const cambiosFiltrados = {};
  Object.keys(cambios).forEach((campo) => {
    if (CAMPOS_EDITABLES_GESTION_.includes(campo)) cambiosFiltrados[campo] = cambios[campo];
  });

  const cambiosReales = updateRowById_(SHEET_NAMES.HORAS_GESTION, id, cambiosFiltrados);
  return { ok: true, cambios: cambiosReales.length };
}

/** Elimina una hora de gestión. Solo el dueño. */
function eliminar_horas_gestion(token, id) {
  const sesion = requireSession_(token);

  const fila = findRowById_(SHEET_NAMES.HORAS_GESTION, id);
  if (!fila) throw new Error('No se encontró esa hora de gestión');
  if (String(fila.directivo_id) !== String(sesion.id)) {
    throw new Error('Solo podés eliminar tus propias horas de gestión');
  }

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    getSheet_(SHEET_NAMES.HORAS_GESTION).deleteRow(fila._row);
    return { ok: true };
  } finally {
    lock.releaseLock();
  }
}
