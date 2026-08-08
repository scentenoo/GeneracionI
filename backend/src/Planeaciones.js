/**
 * Planeaciones de clase (rol docente). Cada clase son 2 horas fijas (ver
 * spec sección 4) — no se guarda un campo de duración.
 */

const HORAS_POR_CLASE = 2;

function guardar_planeacion(token, datos, fotos) {
  const sesion = requireSession_(token);
  requireRole_(sesion, [ROLES.DOCENTE, ROLES.AMBOS]);
  validarPlaneacion_(datos, fotos);

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
      fecha: datos.fecha,
      grupo: datos.grupo,
      objetivo: datos.objetivo,
      temas_vistos: JSON.stringify(datos.temas_vistos || []),
      bloques: JSON.stringify(datos.bloques),
      foto_clase_drive_id: fotoId,
      // Snapshot: la asistencia queda tal cual estaba ese día, no referencia
      // viva al grupo actual (evita que cambios posteriores alteren planeaciones ya guardadas).
      asistencia: JSON.stringify(datos.asistencia || []),
      horas: HORAS_POR_CLASE,
      creado_en: new Date().toISOString(),
    });

    return { ok: true, id: fila.id };
  } finally {
    lock.releaseLock();
  }
}

/** Docente ve solo las suyas; directivo puede pedir las de cualquiera. */
function obtener_planeaciones(token, docente_id) {
  const sesion = requireSession_(token);
  const targetId = docente_id || sesion.id;

  if (String(targetId) !== String(sesion.id) && !esDirectivo_(sesion)) {
    throw new Error('No tienes permiso para ver planeaciones de otro docente');
  }

  return readRowsWhere_(SHEET_NAMES.PLANEACIONES, (p) => String(p.docente_id) === String(targetId)).map(
    parsePlaneacionRow_
  );
}

function parsePlaneacionRow_(p) {
  return Object.assign({}, p, {
    temas_vistos: JSON.parse(p.temas_vistos || '[]'),
    bloques: JSON.parse(p.bloques || '[]'),
    asistencia: JSON.parse(p.asistencia || '[]'),
  });
}

/** Solo directivo edita, nunca elimina. Queda registrado en Historial. */
function editar_planeacion(token, id, cambios) {
  const sesion = requireSession_(token);
  requireRole_(sesion, [ROLES.DIRECTIVO, ROLES.AMBOS]);

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
 * Cuántas planeaciones lleva el docente en el mes vs las esperadas.
 * mes en formato 'YYYY-MM'.
 */
function obtener_estado_mes(token, docente_id, mes) {
  const sesion = requireSession_(token);
  const targetId = docente_id || sesion.id;
  if (String(targetId) !== String(sesion.id) && !esDirectivo_(sesion)) {
    throw new Error('No tienes permiso para ver el estado de otro docente');
  }

  const planeaciones = readRowsWhere_(
    SHEET_NAMES.PLANEACIONES,
    (p) => String(p.docente_id) === String(targetId) && mesDeFecha_(p.fecha) === mes
  );

  return {
    docente_id: targetId,
    mes: mes,
    registradas: planeaciones.length,
    esperadas: CLASES_ESPERADAS_POR_MES,
    faltantes: Math.max(0, CLASES_ESPERADAS_POR_MES - planeaciones.length),
  };
}
