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
  if (String(targetId) !== String(sesion.id) && !esDirectivo_(sesion)) {
    throw new Error('No tienes permiso para ver las horas de gestión de otro usuario');
  }
  return readRowsWhere_(
    SHEET_NAMES.HORAS_GESTION,
    (h) => String(h.directivo_id) === String(targetId)
  );
}
