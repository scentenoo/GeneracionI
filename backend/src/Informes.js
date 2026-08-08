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
 */
function generar_informe_mensual(token, curso_id, mes, narrativa, gestionNarrativa, incluirGestion) {
  const sesion = requireSession_(token);

  const curso = findRowById_(SHEET_NAMES.CURSOS, curso_id);
  if (!curso) throw new Error('Curso no encontrado');

  const targetId = curso.docente_id;
  if (String(targetId) !== String(sesion.id) && !esDirectivo_(sesion)) {
    throw new Error('No tienes permiso para generar el informe de otro docente');
  }

  const usuario = findRowById_(SHEET_NAMES.USUARIOS, targetId);
  if (!usuario) throw new Error('Docente no encontrado');

  const planeacionesDelMes = readRowsWhere_(
    SHEET_NAMES.PLANEACIONES,
    (p) => String(p.curso_id) === String(curso_id) && mesDeFecha_(p.fecha) === mes
  ).map(parsePlaneacionRow_);

  const actividades = planeacionesDelMes.map((p) => {
    const asistentes = p.asistencia.filter((a) => a.presente).length;
    return {
      // No hay un campo "título corto" en la planeación — se usa el objetivo.
      actividad: p.objetivo,
      nro_semana: String(Math.ceil(diaDeFecha_(p.fecha) / 7)),
      horas_sede: String(p.horas || 0),
      horas_externas: '',
      cantidad_asistentes: String(asistentes),
      fecha: fechaCorta_(p.fecha),
      link_planeacion: '', // pendiente: no hay visor de planeaciones con URL propia todavía
    };
  });

  const totalHorasDocente = planeacionesDelMes.reduce((sum, p) => sum + (Number(p.horas) || 0), 0);
  const totalAsistentes = actividades.reduce((sum, a) => sum + Number(a.cantidad_asistentes), 0);

  const encuentros = planeacionesDelMes.map((p, i) => {
    const foto = archivoABase64_(p.foto_clase_drive_id);
    return { nro: String(i + 1), foto_base64: foto ? foto.base64 : null, foto_mime: foto ? foto.mimeType : null };
  });

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
  if (String(curso.docente_id) !== String(sesion.id) && !esDirectivo_(sesion)) {
    throw new Error('No tienes permiso para ver ese curso');
  }

  const planeaciones = readRowsWhere_(
    SHEET_NAMES.PLANEACIONES,
    (p) => String(p.curso_id) === String(curso_id) && mesDeFecha_(p.fecha) === mes
  ).map(parsePlaneacionRow_);

  const porSemana = {};
  planeaciones.forEach((p) => {
    const semana = Math.ceil(diaDeFecha_(p.fecha) / 7);
    if (!porSemana[semana]) porSemana[semana] = [];
    porSemana[semana] = porSemana[semana].concat(p.temas_vistos || []);
  });

  return Object.keys(porSemana)
    .map(Number)
    .sort((a, b) => a - b)
    .map((semana) => ({ semana: semana, temas: porSemana[semana] }));
}

function version_actual() {
  const configRows = readAllRows_(SHEET_NAMES.CONFIG);
  const fila = configRows.find((r) => r.key === 'version_actual');
  return fila ? fila.value : '0.0.0';
}
