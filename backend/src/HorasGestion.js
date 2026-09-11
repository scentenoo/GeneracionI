/**
 * Horas de gestión (planeación administrativa) — equivalente a las
 * planeaciones docentes pero para el rol directivo. Formato mucho más
 * libre que la planeación: sin momentos y sin mínimo de palabras (ver
 * spec sección 6).
 *
 * Lo que sí lleva, desde el piloto, es EVIDENCIA: cada actividad va con su
 * foto y con el producto/entregable que dejó. Sin eso, la hoja de horas de
 * gestión era una lista de texto que nadie podía verificar, y esas horas se
 * pagan igual que las de clase. El link a la carpeta sigue siendo opcional
 * porque la foto ya hace de soporte cuando no hay nada que enlazar.
 *
 * A diferencia de las actividades docentes (ver Actividades.js), acá la
 * foto no exime a nadie: quien registra horas de gestión es directivo por
 * definición, así que la excepción "los directivos pueden sin foto" dejaría
 * la regla en nada.
 */

/**
 * Lo común a crear y editar. La foto es obligatoria solo al CREAR
 * (`esNueva`): exigírsela también al editar dejaría sin poder corregir ni
 * una fecha mal escrita a las actividades de antes del piloto, que se
 * cargaron sin foto porque todavía no se pedía.
 */
function validarHorasGestion_(datos, fotos, esNueva) {
  if (!datos.fecha) throw new Error('Falta la fecha');
  if (!datos.actividad) throw new Error('Falta describir la actividad/tarea');
  if (!datos.horas_sede) throw new Error('Falta el número de horas');
  if (!String(datos.entregable || '').trim()) {
    throw new Error('Falta el producto o entregable: es la prueba de la actividad');
  }
  if (esNueva && !(fotos && fotos.foto)) {
    throw new Error('Falta la foto de la actividad');
  }
}

function guardar_horas_gestion(token, datos, fotos) {
  const sesion = requireSession_(token);
  requireRole_(sesion, [ROLES.DIRECTIVO, ROLES.AMBOS]);
  validarHorasGestion_(datos, fotos, true);

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const fotoId = guardarArchivoBase64_(
      ['Fotos de horas de gestión'],
      fotos.foto.base64,
      fotos.foto.mimeType || 'image/jpeg',
      nombreDeFoto_('gestion', sesion.nombre, datos.fecha)
    );

    const fila = appendRow_(SHEET_NAMES.HORAS_GESTION, {
      directivo_id: sesion.id,
      fecha: datos.fecha,
      actividad: datos.actividad,
      horas_sede: datos.horas_sede,
      entregable: datos.entregable,
      link_soporte: datos.link_soporte || '',
      foto_drive_id: fotoId,
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
    throw new Error('No tiene permiso para ver las horas de gestión de otro usuario');
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
 * `fotos` es opcional: sin foto nueva se conserva la que ya tenía, no se
 * borra. Lo que no se puede es dejarla sin ninguna.
 *
 * No lleva chequeo de cierre de mes: el cierre exime a los directivos
 * (ver requireMesAbierto_ en Cierre.js) y las horas de gestión siempre son
 * de un directivo, así que el corte nunca los alcanza.
 */
function editar_horas_gestion(token, id, cambios, fotos) {
  const sesion = requireSession_(token);

  const fila = findRowById_(SHEET_NAMES.HORAS_GESTION, id);
  if (!fila) throw new Error('No se encontró esa hora de gestión');
  if (String(fila.directivo_id) !== String(sesion.id)) {
    throw new Error('Solo puede editar sus propias horas de gestión');
  }

  // Se valida la fila como va a quedar, no solo lo que llegó: editar manda
  // el formulario entero, pero si algún día mandara un cambio parcial, los
  // campos que no vienen tienen que seguir contando como llenos. La foto
  // nunca es obligatoria acá (ver validarHorasGestion_).
  validarHorasGestion_(Object.assign({}, fila, cambios), fotos, false);

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const cambiosFiltrados = {};
    Object.keys(cambios).forEach((campo) => {
      if (CAMPOS_EDITABLES_GESTION_.includes(campo)) cambiosFiltrados[campo] = cambios[campo];
    });

    if (fotos && fotos.foto) {
      cambiosFiltrados.foto_drive_id = reemplazarArchivo_(
        ['Fotos de horas de gestión'],
        fila.foto_drive_id,
        fotos.foto.base64,
        fotos.foto.mimeType || 'image/jpeg',
        nombreDeFoto_('gestion', sesion.nombre, cambiosFiltrados.fecha || fila.fecha)
      );
    }

    const cambiosReales = updateRowById_(SHEET_NAMES.HORAS_GESTION, id, cambiosFiltrados);
    return { ok: true, cambios: cambiosReales.length };
  } finally {
    lock.releaseLock();
  }
}

/** Elimina una hora de gestión. Solo el dueño. */
function eliminar_horas_gestion(token, id) {
  const sesion = requireSession_(token);

  const fila = findRowById_(SHEET_NAMES.HORAS_GESTION, id);
  if (!fila) throw new Error('No se encontró esa hora de gestión');
  if (String(fila.directivo_id) !== String(sesion.id)) {
    throw new Error('Solo puede eliminar sus propias horas de gestión');
  }

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    trasharSiExiste_(fila.foto_drive_id);
    getSheet_(SHEET_NAMES.HORAS_GESTION).deleteRow(fila._row);
    return { ok: true };
  } finally {
    lock.releaseLock();
  }
}
