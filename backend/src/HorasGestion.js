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
      // Vacío = pendiente (mismo criterio que estaPendiente_ en
      // Revisiones.js): así una fila de antes del piloto, sin esta
      // columna, también cuenta como pendiente y no hace falta migrarla.
      estado: '',
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

/**
 * Vista de supervisión de TODAS las horas externas del equipo en un mes,
 * para Revisar → Horas externas — todo el equipo directivo (rol directivo,
 * ambos, o el administrador), es una vista de supervisión, no de
 * autoservicio.
 *
 * Junta DOS fuentes que antes vivían separadas — el banner de esta pantalla
 * ya decía "cada docente y directivo debe cumplir 8 horas externas al mes",
 * pero solo se leían las horas de gestión de los directivos, nunca las
 * horas_externas que cargan los docentes en sus actividades (reuniones,
 * claustros) de un curso:
 *   - Horas de gestión (directivos): un ítem revisable, con evidencia
 *     (foto+entregable) — se aprueba o devuelve una por una acá mismo.
 *   - horas_externas de Actividades (docentes): informativas nada más —
 *     ya se revisan como parte del informe mensual completo de ese curso,
 *     no una por una acá, así que no llevan aprobar/devolver.
 * horas_sede de Actividades queda afuera a propósito: esa no es "externa",
 * ya se cuenta en la cuenta de cobro / certificado de pago por su lado.
 *
 * Mismo patrón que Usuarios.js#obtener_dashboard_directivo: una lectura
 * de cada hoja, agrupado en memoria, en vez de una llamada por persona.
 */
function obtener_horas_del_equipo(token, mes) {
  const sesion = requireSession_(token);
  requireSupervisor_(sesion);

  const usuarioPorId = {};
  readAllRows_(SHEET_NAMES.USUARIOS).forEach((u) => {
    usuarioPorId[String(u.id)] = u;
  });

  const cursoPorId = {};
  readAllRows_(SHEET_NAMES.CURSOS).forEach((c) => {
    cursoPorId[String(c.id)] = c;
  });

  const totalPorPersona = {};
  const items = [];

  readAllRows_(SHEET_NAMES.HORAS_GESTION)
    .filter((h) => mesDeFecha_(h.fecha) === mes)
    .forEach((h) => {
      const clave = String(h.directivo_id);
      const horas = Number(h.horas_sede) || 0;
      totalPorPersona[clave] = (totalPorPersona[clave] || 0) + horas;
      const usuario = usuarioPorId[clave];
      items.push({
        tipo: 'gestion',
        id: h.id,
        persona_id: h.directivo_id,
        persona: usuario ? usuario.nombre : `id ${h.directivo_id}`,
        fecha: fechaISO_(h.fecha),
        actividad: h.actividad,
        curso: '',
        horas: horas,
        entregable: h.entregable,
        link_soporte: h.link_soporte || '',
        foto_drive_id: h.foto_drive_id || '',
        estado: h.estado || ESTADO_PENDIENTE,
        revisado_por: h.revisado_por || '',
        revisado_en: h.revisado_en || '',
        motivo_devolucion: h.motivo_devolucion || '',
      });
    });

  readAllRows_(SHEET_NAMES.ACTIVIDADES)
    .filter((a) => mesDeFecha_(a.fecha) === mes && Number(a.horas_externas) > 0)
    .forEach((a) => {
      const clave = String(a.usuario_id);
      const horas = Number(a.horas_externas) || 0;
      totalPorPersona[clave] = (totalPorPersona[clave] || 0) + horas;
      const usuario = usuarioPorId[clave];
      const curso = cursoPorId[String(a.curso_id)];
      items.push({
        tipo: 'actividad',
        id: a.id,
        persona_id: a.usuario_id,
        persona: usuario ? usuario.nombre : `id ${a.usuario_id}`,
        fecha: fechaISO_(a.fecha),
        actividad: a.descripcion,
        curso: curso ? curso.nombre : '',
        horas: horas,
        entregable: '',
        link_soporte: '',
        foto_drive_id: a.foto_drive_id || '',
        estado: '',
        revisado_por: '',
        revisado_en: '',
        motivo_devolucion: '',
      });
    });

  const resumen = Object.keys(totalPorPersona).map((personaId) => {
    const usuario = usuarioPorId[personaId];
    const total = totalPorPersona[personaId];
    return {
      persona_id: Number(personaId),
      nombre: usuario ? usuario.nombre : `id ${personaId}`,
      rol: usuario ? usuario.rol : '',
      total_horas: total,
      objetivo: HORAS_OBJETIVO_MENSUAL,
      cumple: total >= HORAS_OBJETIVO_MENSUAL,
    };
  });

  return { resumen: resumen, actividades: items };
}

/**
 * Una foto puntual de una hora externa (de gestión o de actividad de
 * docente), para verla adentro de la app en vez de abrir Drive — misma
 * vista de supervisión que obtener_horas_del_equipo, así que el mismo
 * permiso. `archivoABase64_` vive en Informes.js, es genérico para
 * cualquier archivo de Drive por id.
 */
function obtener_foto_horas_externas(token, foto_drive_id) {
  const sesion = requireSession_(token);
  requireSupervisor_(sesion);
  if (!foto_drive_id) throw new Error('Sin foto para mostrar');
  const foto = archivoABase64_(foto_drive_id);
  if (!foto) throw new Error('No se encontró la foto en Drive');
  return { base64: foto.base64, mimeType: foto.mimeType };
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
