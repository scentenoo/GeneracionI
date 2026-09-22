/**
 * Informe mensual de un directivo SIN curso (gestión pura).
 *
 * Wendy y Mariangel dan clase además de dirigir: su gestión va adjunta al
 * informe de uno de sus cursos (ver Informes.js, incluirGestion). Pero un
 * directivo como Sofía no tiene curso, y su informe es otro documento: sin
 * clases, sin asistencia, sin cuenta de cobro por hora docente — solo sus
 * horas de gestión del mes y lo que valen.
 *
 * Para no reescribir el modelo del informe docente, este se guarda en la
 * misma pestaña INFORMES pero con una clave de curso sintética
 * `gestion:<id>`, que nunca choca con un curso real (los ids de curso son
 * números). Así buscarInforme_/eliminar_informe_mensual siguen andando sin
 * cambios.
 */

function claveGestion_(directivo_id) {
  return `gestion:${directivo_id}`;
}

function esClaveGestion_(curso_id) {
  return String(curso_id).indexOf('gestion:') === 0;
}

function directivoDeClave_(curso_id) {
  return String(curso_id).split(':')[1];
}

/**
 * Guarda (o actualiza) el informe de gestión del mes. Solo el propio
 * directivo: es su planeación de horas. No pide curso.
 */
function guardar_informe_gestion(token, mes, gestionNarrativa) {
  const sesion = requireSession_(token);
  requireRole_(sesion, [ROLES.DIRECTIVO, ROLES.AMBOS]);
  if (!/^\d{4}-\d{2}$/.test(String(mes))) throw new Error('El mes va como AAAA-MM');

  CAMPOS_GESTION_.forEach((campo) => {
    requireMinPalabras_((gestionNarrativa || {})[campo], `gestión: ${campo}`);
  });

  const clave = claveGestion_(sesion.id);
  const fila = {
    curso_id: clave,
    docente_id: sesion.id,
    mes: mes,
    incluye_gestion: true,
    avance_semanal: '[]',
    actualizado_en: new Date().toISOString(),
  };
  CAMPOS_GESTION_.forEach((campo) => {
    fila['gestion_' + campo] = gestionNarrativa[campo];
  });

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  invalidarCacheHojas_();
  try {
    const existente = buscarInforme_(clave, mes);
    if (existente) {
      updateRowById_(SHEET_NAMES.INFORMES, existente.id, fila);
      registrarEntrega_('informe', `${clave}|${mes}`, SHEET_NAMES.INFORMES, existente.id, sesion.usuario);
      return { ok: true, id: existente.id, actualizado: true };
    }
    fila.creado_en = fila.actualizado_en;
    const creada = appendRow_(SHEET_NAMES.INFORMES, fila);
    registrarEntrega_('informe', `${clave}|${mes}`, SHEET_NAMES.INFORMES, creada.id, sesion.usuario);
    return { ok: true, id: creada.id, actualizado: false };
  } finally {
    lock.releaseLock();
  }
}

/** Las respuestas ya entregadas, o null. Dueño o quien supervisa. */
function obtener_informe_gestion(token, directivo_id, mes) {
  const sesion = requireSession_(token);
  const targetId = directivo_id || sesion.id;
  if (String(targetId) !== String(sesion.id) && !puedeSupervisar_(sesion)) {
    throw new Error('No tiene permiso para ver ese informe');
  }

  const fila = buscarInforme_(claveGestion_(targetId), mes);
  if (!fila) return null;
  const salida = {};
  CAMPOS_GESTION_.forEach((campo) => {
    salida['gestion_' + campo] = fila['gestion_' + campo];
  });
  return salida;
}

/**
 * Arma el contexto docxtpl del informe de gestión, listo para la plantilla
 * informe_gestion.docx (ver client). Sin narrativa, lo lee de lo entregado
 * — que es como lo descarga quien supervisa.
 */
function generar_informe_gestion(token, directivo_id, mes, gestionNarrativa) {
  const sesion = requireSession_(token);
  const targetId = directivo_id || sesion.id;
  if (String(targetId) !== String(sesion.id) && !puedeSupervisar_(sesion)) {
    throw new Error('No tiene permiso para generar ese informe');
  }

  const usuario = findRowById_(SHEET_NAMES.USUARIOS, targetId);
  if (!usuario) throw new Error('Directivo no encontrado');

  if (!gestionNarrativa) {
    const guardado = obtener_informe_gestion(token, targetId, mes);
    if (!guardado) throw new Error(`Todavía no se entregó el informe de gestión de ${mes}`);
    gestionNarrativa = {};
    CAMPOS_GESTION_.forEach((campo) => {
      gestionNarrativa[campo] = guardado['gestion_' + campo];
    });
  }

  const horasDelMes = readRowsWhere_(
    SHEET_NAMES.HORAS_GESTION,
    (h) => String(h.directivo_id) === String(targetId) && mesDeFecha_(h.fecha) === mes
  );
  const totalHoras = horasDelMes.reduce((sum, h) => sum + Number(h.horas_sede || 0), 0);
  const valorHora = Number(usuario.valor_hora_directivo) || 0;
  const valorTotal = totalHoras * valorHora;

  const firma = archivoABase64_(usuario.firma_drive_id);

  return {
    periodo_evaluado: `${nombreMes_(mes)} ${mes.split('-')[0]}`,
    nombre_directivo: usuario.nombre,
    cargo: 'Directivo',
    cedula: usuario.cedula || '',

    gestion_objetivos: gestionNarrativa.objetivos,
    gestion_logros: gestionNarrativa.logros,
    gestion_novedades: gestionNarrativa.novedades,
    gestion_estrategias: gestionNarrativa.estrategias,
    gestion_pendientes: gestionNarrativa.pendientes,

    horas_gestion: horasDelMes.map((h) => ({
      actividad: h.actividad,
      nro_semana: String(Math.ceil(diaDeFecha_(h.fecha) / 7)),
      horas_sede: String(h.horas_sede),
      entregable: h.entregable || '',
      // Sin link a mano, el soporte que se enlaza es la foto de la
      // actividad: siempre hay una, y así la columna nunca sale vacía.
      link_soporte: h.link_soporte || urlDeArchivo_(h.foto_drive_id),
    })),
    total_horas_gestion: String(totalHoras),

    // Cuenta de cobro, con la hora directiva (no la docente).
    fecha_emision: Utilities.formatDate(new Date(), 'America/Bogota', 'dd/MM/yyyy'),
    fecha_entrega: Utilities.formatDate(new Date(), 'America/Bogota', 'dd/MM/yyyy'),
    mes_a_cobrar: nombreMes_(mes),
    periodo_cobro: `(Del 01-${mes.split('-')[1]}-${mes.split('-')[0]} al ${ultimoDiaDelMes_(mes)}-${mes.split('-')[1]}-${mes.split('-')[0]})`,
    horas_totales: String(totalHoras),
    valor_en_numeros: `$ ${valorTotal.toLocaleString('es-CO')}`,
    valor_en_letras: numeroALetras_(valorTotal),
    numero_cuenta: usuario.numero_cuenta || '',
    tipo_cuenta: usuario.tipo_cuenta || '',
    entidad_bancaria: usuario.entidad_bancaria || '',

    firma_base64: firma ? firma.base64 : null,
    firma_mime: firma ? firma.mimeType : null,

    // Historial de revisión, para la hoja final si fue devuelto alguna vez.
    historial: historialDe_('informe', `${claveGestion_(targetId)}|${mes}`),
  };
}

/**
 * Los directivos con cargo de gestión que le tocan a quien supervisa, para
 * que «Informes del mes» los muestre igual que a los cursos: nombre, si
 * entregó y una clave para bajarlo. Un directivo con curso ya aparece por
 * su curso, así que acá van los que NO tienen ninguno — si no, saldrían
 * dos veces.
 */
function directivos_sin_curso_del_mes(token, mes) {
  const sesion = requireSession_(token);
  requireRole_(sesion, [ROLES.DIRECTIVO, ROLES.AMBOS]);

  const conCurso = {};
  readAllRows_(SHEET_NAMES.CURSOS).forEach((c) => {
    if (c.activo === true) conCurso[String(c.docente_id)] = true;
  });

  const informePorClave = {};
  readAllRows_(SHEET_NAMES.INFORMES).forEach((i) => {
    if (esClaveGestion_(i.curso_id) && mesDeFecha_(i.mes) === mes) {
      informePorClave[String(i.curso_id)] = true;
    }
  });

  return readAllRows_(SHEET_NAMES.USUARIOS)
    .filter((u) => (u.rol === ROLES.DIRECTIVO || u.rol === ROLES.AMBOS) && !conCurso[String(u.id)])
    .map((u) => ({
      directivo_id: u.id,
      nombre: u.nombre,
      mes: mes,
      informe_entregado: !!informePorClave[claveGestion_(u.id)],
    }));
}
