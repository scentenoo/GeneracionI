/**
 * Arma el JSON que el cliente Python usa con docxtpl para rellenar
 * templates/informe_mensual.docx (ver ese archivo para el contrato exacto
 * de variables). Este backend NO genera el .docx ni el PDF — Apps Script no
 * puede correr docxtpl/LibreOffice, así que solo agrega y devuelve datos.
 *
 * `narrativa` y `gestionNarrativa` son las respuestas de texto libre que el
 * docente/directivo escribe para el informe de ese mes (objetivos
 * cumplidos, logros, dificultades, etc.) — no son derivables de las
 * planeaciones guardadas, así que el cliente las recolecta en un formulario
 * y las manda tal cual al generar el informe.
 *
 * Pendiente de decidir con Samir (dejado con valores por defecto simples
 * por ahora, ver comentarios inline): numeración de la cuenta de cobro,
 * rango de edades por curso, y evidencias fotográficas de gestión (la
 * pestaña HorasGestion hoy no guarda fotos).
 */

const CAMPOS_NARRATIVA_ = [
  'objetivo_cumplimiento', 'logros_avances', 'dificultades',
  'estrategias', 'situacion_positiva', 'ctei_integracion',
];
const CAMPOS_GESTION_ = ['objetivos', 'logros', 'novedades', 'estrategias', 'pendientes'];

/**
 * Sheets convierte "2026-08" en una fecha al guardarlo, así que al releer
 * vuelve como Date y no como el string que mandamos. mesDeFecha_ normaliza
 * las dos formas — mismo problema que con `fecha` en Planeaciones.
 */
function buscarInforme_(curso_id, mes) {
  return readRowsWhere_(
    SHEET_NAMES.INFORMES,
    (i) => String(i.curso_id) === String(curso_id) && mesDeFecha_(i.mes) === mes
  )[0] || null;
}

/**
 * Guarda las respuestas narrativas del mes. Antes se escribían, se metían
 * en el .docx y se perdían; ahora quedan para poder reabrirlas, y para que
 * el dashboard sepa quién ya entregó.
 *
 * Solo se puede entregar con todas las clases del mes cargadas: el informe
 * las resume, así que a medias no sirve.
 */
function guardar_informe_mensual(token, curso_id, mes, narrativa, gestionNarrativa, incluirGestion) {
  const sesion = requireSession_(token);

  const curso = findRowById_(SHEET_NAMES.CURSOS, curso_id);
  if (!curso) throw new Error('Curso no encontrado');
  if (String(curso.docente_id) !== String(sesion.id) && !puedeSupervisar_(sesion)) {
    throw new Error('No tienes permiso para entregar el informe de ese curso');
  }

  requireMesAbierto_(sesion, curso_id, mes);

  const estado = obtener_estado_mes(token, curso_id, mes);
  if (estado.faltantes > 0) {
    throw new Error(
      `Faltan ${estado.faltantes} planeaciones de ${mes} para poder entregar el informe de este curso`
    );
  }

  CAMPOS_NARRATIVA_.forEach((campo) => {
    requireMinPalabras_(narrativa[campo], campo);
  });

  const fila = {
    curso_id: curso_id,
    docente_id: curso.docente_id,
    mes: mes,
    avance_semanal: JSON.stringify(narrativa.avance_semanal || []),
    incluye_gestion: incluirGestion === true,
    actualizado_en: new Date().toISOString(),
  };
  CAMPOS_NARRATIVA_.forEach((campo) => {
    fila[campo] = narrativa[campo];
  });
  if (incluirGestion === true) {
    CAMPOS_GESTION_.forEach((campo) => {
      requireMinPalabras_((gestionNarrativa || {})[campo], `gestión: ${campo}`);
      fila['gestion_' + campo] = gestionNarrativa[campo];
    });
  }

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const existente = buscarInforme_(curso_id, mes);
    if (existente) {
      updateRowById_(SHEET_NAMES.INFORMES, existente.id, fila);
      registrarEntrega_('informe', `${curso_id}|${mes}`, SHEET_NAMES.INFORMES, existente.id, sesion.usuario);
      return { ok: true, id: existente.id, actualizado: true };
    }
    fila.creado_en = fila.actualizado_en;
    const creada = appendRow_(SHEET_NAMES.INFORMES, fila);
    registrarEntrega_('informe', `${curso_id}|${mes}`, SHEET_NAMES.INFORMES, creada.id, sesion.usuario);
    return { ok: true, id: creada.id, actualizado: false };
  } finally {
    lock.releaseLock();
  }
}

/** Las respuestas ya guardadas, para reabrir el informe y seguir editándolo. */
/**
 * Borra un informe ya entregado, para que el mes vuelva a figurar como
 * pendiente. Solo el administrador.
 *
 * Reabrir el mes (ver Cierre.js) alcanza cuando hay que corregir algo:
 * el docente vuelve a entregar y se pisa lo anterior. Esto es para el
 * caso distinto de un informe que no debería existir — presentado sobre
 * el mes equivocado, o de prueba. Sin esto el dashboard queda diciendo
 * "entregado" para siempre sobre algo que nadie entregó.
 */
function eliminar_informe_mensual(token, curso_id, mes) {
  const sesion = requireSession_(token);
  requireAdministrador_(sesion);

  const borrados = eliminarFilasDonde_(
    SHEET_NAMES.INFORMES,
    (i) => String(i.curso_id) === String(curso_id) && mesDeFecha_(i.mes) === mes
  );
  if (borrados === 0) throw new Error('No hay un informe entregado para ese curso y mes');

  return { ok: true, borrados: borrados };
}

function obtener_informe_mensual(token, curso_id, mes) {
  const sesion = requireSession_(token);

  const curso = findRowById_(SHEET_NAMES.CURSOS, curso_id);
  if (!curso) throw new Error('Curso no encontrado');
  if (String(curso.docente_id) !== String(sesion.id) && !puedeSupervisar_(sesion)) {
    throw new Error('No tienes permiso para ver ese informe');
  }

  const fila = buscarInforme_(curso_id, mes);
  if (!fila) return null;
  return Object.assign({}, fila, { avance_semanal: JSON.parse(fila.avance_semanal || '[]') });
}

const MESES_ES_ = [
  'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
];

function nombreMes_(mes) {
  const [, mm] = mes.split('-').map(Number);
  return MESES_ES_[mm - 1];
}

function ultimoDiaDelMes_(mes) {
  const [yyyy, mm] = mes.split('-').map(Number);
  return new Date(yyyy, mm, 0).getDate();
}

function archivoABase64_(fileId) {
  if (!fileId) return null;
  const file = DriveApp.getFileById(fileId);
  return {
    base64: Utilities.base64Encode(file.getBlob().getBytes()),
    mimeType: file.getMimeType(),
  };
}

/**
 * El informe va por CURSO, no por persona: quien tiene dos cursos entrega
 * dos informes al mes, cada uno con sus clases y su cuenta de cobro, tal
 * como la nómina los paga por separado.
 *
 * `incluirGestion` decide si este informe se lleva la sección 5 y las
 * horas de gestión del mes. Solo aplica a quien tiene rol directivo, y hay
 * que marcarlo en UN solo informe del mes para no cobrar dos veces las
 * mismas horas de gestión.
 *
 * Si no le pasan `narrativa`, la lee de lo ya entregado — que es como lo
 * usa el directivo para descargar el informe de cualquier docente. Con
 * narrativa es la vista previa de un borrador todavía sin entregar.
 */
function generar_informe_mensual(token, curso_id, mes, narrativa, gestionNarrativa, incluirGestion) {
  const sesion = requireSession_(token);

  const curso = findRowById_(SHEET_NAMES.CURSOS, curso_id);
  if (!curso) throw new Error('Curso no encontrado');

  if (!narrativa) {
    const guardado = obtener_informe_mensual(token, curso_id, mes);
    if (!guardado) {
      throw new Error(`Todavía no se entregó el informe de ${mes} para este curso`);
    }
    narrativa = {};
    CAMPOS_NARRATIVA_.forEach((campo) => {
      narrativa[campo] = guardado[campo];
    });
    narrativa.avance_semanal = guardado.avance_semanal;

    gestionNarrativa = {};
    CAMPOS_GESTION_.forEach((campo) => {
      gestionNarrativa[campo] = guardado['gestion_' + campo];
    });
    incluirGestion = guardado.incluye_gestion === true;
  }

  const targetId = curso.docente_id;
  if (String(targetId) !== String(sesion.id) && !puedeSupervisar_(sesion)) {
    throw new Error('No tienes permiso para generar el informe de otro docente');
  }

  const usuario = findRowById_(SHEET_NAMES.USUARIOS, targetId);
  if (!usuario) throw new Error('Docente no encontrado');

  const planeacionesDelMes = readRowsWhere_(
    SHEET_NAMES.PLANEACIONES,
    (p) => String(p.curso_id) === String(curso_id) && mesDeFecha_(p.fecha) === mes
  ).map(parsePlaneacionRow_);

  // La tabla del informe lista las clases Y lo demás que se factura:
  // reuniones, claustros, informes. En julio esas otras fueron 8 de las 16
  // horas del mes, así que sin sumarlas la cuenta de cobro sale por mitad.
  const filasDeClases = planeacionesDelMes.map((p) => {
    const asistentes = p.asistencia.filter((a) => a.presente).length;
    return {
      _fecha: fechaISO_(p.fecha),
      // No hay un campo "título corto" en la planeación — se usa el objetivo.
      actividad: p.objetivo,
      nro_semana: String(Math.ceil(diaDeFecha_(p.fecha) / 7)),
      horas_sede: String(p.horas || 0),
      horas_externas: '',
      cantidad_asistentes: String(asistentes),
      fecha: fechaCorta_(p.fecha),
      link_planeacion: urlDeArchivo_(p.doc_drive_id),
    };
  });

  const otrasDelMes = readRowsWhere_(
    SHEET_NAMES.ACTIVIDADES,
    (a) => String(a.curso_id) === String(curso_id) && mesDeFecha_(a.fecha) === mes
  );

  const filasDeOtras = otrasDelMes.map((a) => ({
    _fecha: fechaISO_(a.fecha),
    actividad: a.descripcion,
    nro_semana: String(Math.ceil(diaDeFecha_(a.fecha) / 7)),
    horas_sede: Number(a.horas_sede) ? String(a.horas_sede) : '',
    horas_externas: Number(a.horas_externas) ? String(a.horas_externas) : '',
    // Una reunión no tiene asistencia de estudiantes ni planeación: su
    // soporte es la foto que se pidió al registrarla.
    cantidad_asistentes: '',
    fecha: fechaCorta_(a.fecha),
    link_planeacion: urlDeArchivo_(a.foto_drive_id),
  }));

  const actividades = filasDeClases
    .concat(filasDeOtras)
    .sort((a, b) => (a._fecha < b._fecha ? -1 : a._fecha > b._fecha ? 1 : 0));

  const horasDeClases = planeacionesDelMes.reduce((sum, p) => sum + (Number(p.horas) || 0), 0);
  const horasDeOtras = otrasDelMes.reduce(
    (sum, a) => sum + (Number(a.horas_sede) || 0) + (Number(a.horas_externas) || 0), 0
  );
  const totalHorasDocente = horasDeClases + horasDeOtras;
  const totalAsistentes = filasDeClases.reduce((sum, a) => sum + Number(a.cantidad_asistentes), 0);

  // Las evidencias fotográficas también llevan las actividades que no son
  // clase: en el informe real de Wendy, "Claustro docente con la directriz
  // de secretaría" aparece en esa tabla junto a las clases.
  const encuentrosDeClases = planeacionesDelMes.map((p, i) => {
    const foto = archivoABase64_(p.foto_clase_drive_id);
    return {
      _fecha: fechaISO_(p.fecha),
      nro: `Clase ${i + 1}`,
      foto_base64: foto ? foto.base64 : null,
      foto_mime: foto ? foto.mimeType : null,
    };
  });

  const encuentrosDeOtras = otrasDelMes
    .filter((a) => a.foto_drive_id)
    .map((a) => {
      const foto = archivoABase64_(a.foto_drive_id);
      return {
        _fecha: fechaISO_(a.fecha),
        nro: a.descripcion,
        foto_base64: foto ? foto.base64 : null,
        foto_mime: foto ? foto.mimeType : null,
      };
    });

  const encuentros = encuentrosDeClases
    .concat(encuentrosDeOtras)
    .sort((a, b) => (a._fecha < b._fecha ? -1 : a._fecha > b._fecha ? 1 : 0));

  const valorHoraDocente = Number(usuario.valor_hora_docente) || 0;
  let valorTotal = totalHorasDocente * valorHoraDocente;

  const context = {
    periodo_evaluado: `${nombreMes_(mes)} ${mes.split('-')[0]}`,
    nucleo: curso.nucleo || '',
    nombre_docente: usuario.nombre,
    curso: curso.nombre,
    actividades: actividades,
    total_horas: String(totalHorasDocente),
    total_asistentes: String(totalAsistentes),

    objetivo_cumplimiento: narrativa.objetivo_cumplimiento,
    logros_avances: narrativa.logros_avances,
    dificultades: narrativa.dificultades,
    estrategias: narrativa.estrategias,
    situacion_positiva: narrativa.situacion_positiva,
    ctei_integracion: narrativa.ctei_integracion,
    // La "unidad trabajada" se arma sola desde las planeaciones (semana +
    // temas vistos); el docente solo aporta nivel y observaciones.
    avance_semanal: armarAvanceSemanal_(planeacionesDelMes, narrativa.avance_semanal || []),

    encuentros: encuentros,
    cedula_docente: usuario.cedula || '',
    fecha_entrega: Utilities.formatDate(new Date(), 'America/Bogota', 'dd/MM/yyyy'),

    fecha_emision: Utilities.formatDate(new Date(), 'America/Bogota', 'dd/MM/yyyy'),
    cuenta_cobro_no: String(contarInformesPrevios_(curso_id, mes) + 1),
    mes_a_cobrar: nombreMes_(mes),
    edad_desde: curso.edad_desde || '',
    edad_hasta: curso.edad_hasta || '',
    num_encuentros: String(planeacionesDelMes.length),
    horas_totales: String(totalHorasDocente),
    periodo_cobro: `(Del 01-${mes.split('-')[1]}-${mes.split('-')[0]} al ${ultimoDiaDelMes_(mes)}-${mes.split('-')[1]}-${mes.split('-')[0]})`,
    numero_cuenta: usuario.numero_cuenta || '',
    tipo_cuenta: usuario.tipo_cuenta || '',
    entidad_bancaria: usuario.entidad_bancaria || '',

    // Controla la sección 5 de la plantilla. Un directivo con dos cursos
    // marca la gestión en uno solo, así que acá pesa también su elección.
    es_directivo: esDirectivo_({ rol: usuario.rol }) && incluirGestion !== false,
  };

  if (context.es_directivo) {
    const horasGestionDelMes = readRowsWhere_(
      SHEET_NAMES.HORAS_GESTION,
      (h) => String(h.directivo_id) === String(targetId) && mesDeFecha_(h.fecha) === mes
    );
    const totalHorasGestion = horasGestionDelMes.reduce((sum, h) => sum + Number(h.horas_sede || 0), 0);
    const valorHoraDirectivo = Number(usuario.valor_hora_directivo) || 0;
    valorTotal += totalHorasGestion * valorHoraDirectivo;

    context.horas_gestion = horasGestionDelMes.map((h) => ({
      actividad: h.actividad,
      nro_semana: String(Math.ceil(diaDeFecha_(h.fecha) / 7)),
      horas_sede: String(h.horas_sede),
      entregable: h.entregable,
      link_soporte: h.link_soporte,
    }));
    context.total_horas_gestion = String(totalHorasGestion);
    context.gestion_objetivos = gestionNarrativa.objetivos;
    context.gestion_logros = gestionNarrativa.logros;
    context.gestion_novedades = gestionNarrativa.novedades;
    context.gestion_estrategias = gestionNarrativa.estrategias;
    context.gestion_pendientes = gestionNarrativa.pendientes;
    // HorasGestion no guarda fotos todavía -> evidencias_gestion queda vacía
    // hasta que se agregue ese campo.
    context.evidencias_gestion = [];
  }

  context.valor_en_numeros = `$ ${valorTotal.toLocaleString('es-CO')}`;
  context.valor_en_letras = numeroALetras_(valorTotal);

  const firma = archivoABase64_(usuario.firma_drive_id);
  context.firma_base64 = firma ? firma.base64 : null;
  context.firma_mime = firma ? firma.mimeType : null;

  // El historial de revisión se imprime al final del documento si el
  // informe fue devuelto alguna vez (ver docx_generator._anexar_historial).
  context.historial = historialDe_('informe', `${curso_id}|${mes}`);

  return context;
}

/** Heurística simple: cuántos meses distintos con planeaciones tiene el curso antes de `mes`. */
function contarInformesPrevios_(curso_id, mes) {
  const meses = new Set(
    readRowsWhere_(SHEET_NAMES.PLANEACIONES, (p) => String(p.curso_id) === String(curso_id))
      .map((p) => mesDeFecha_(p.fecha))
      .filter((m) => m < mes)
  );
  return meses.size;
}

/**
 * Agrupa las planeaciones del mes por semana y arma la columna "unidad
 * trabajada" de la sección 3 juntando los temas vistos de esa semana.
 * `respuestas` trae el nivel y las observaciones que escribió el docente,
 * emparejadas por número de semana.
 */
function armarAvanceSemanal_(planeaciones, respuestas) {
  const porSemana = {};
  planeaciones.forEach((p) => {
    const semana = Math.ceil(diaDeFecha_(p.fecha) / 7);
    if (!porSemana[semana]) porSemana[semana] = [];
    porSemana[semana] = porSemana[semana].concat(p.temas_vistos || []);
  });

  const respuestaDeSemana = {};
  (respuestas || []).forEach((r) => {
    respuestaDeSemana[String(r.semana)] = r;
  });

  return Object.keys(porSemana)
    .map(Number)
    .sort((a, b) => a - b)
    .map((semana) => {
      const r = respuestaDeSemana[String(semana)] || {};
      return {
        semana: `Semana ${semana}\n${porSemana[semana].join('\n')}`,
        nivel: r.nivel || '',
        observaciones: r.observaciones || '',
      };
    });
}

/**
 * Las semanas del mes con sus temas, para que el cliente prellene el
 * formulario de la sección 3 y el docente solo complete nivel y
 * observaciones.
 */
function obtener_avance_sugerido(token, curso_id, mes) {
  const sesion = requireSession_(token);

  const curso = findRowById_(SHEET_NAMES.CURSOS, curso_id);
  if (!curso) throw new Error('Curso no encontrado');
  if (String(curso.docente_id) !== String(sesion.id) && !puedeSupervisar_(sesion)) {
    throw new Error('No tienes permiso para ver ese curso');
  }

  const planeaciones = readRowsWhere_(
    SHEET_NAMES.PLANEACIONES,
    (p) => String(p.curso_id) === String(curso_id) && mesDeFecha_(p.fecha) === mes
  ).map(parsePlaneacionRow_);

  // Una fila por clase, en orden de fecha, y la "semana" es el lugar que
  // ocupa esa clase en el mes: 4 clases son siempre las semanas 1 a 4.
  //
  // Antes agrupaba por Math.ceil(día / 7), y eso fusionaba dos clases de
  // la misma franja de días en una sola fila — el docente cargaba 4
  // planeaciones y el informe le mostraba 3 semanas. Además los días 29 a
  // 31 caían en una "semana 5" que el formato no tiene.
  return planeaciones
    .slice()
    .sort((a, b) => (fechaISO_(a.fecha) < fechaISO_(b.fecha) ? -1 : 1))
    .map((p, i) => ({
      semana: i + 1,
      fecha: fechaISO_(p.fecha),
      temas: p.temas_vistos || [],
    }));
}
