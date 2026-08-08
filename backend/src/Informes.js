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

function generar_informe_mensual(token, docente_id, mes, narrativa, gestionNarrativa) {
  const sesion = requireSession_(token);
  const targetId = docente_id || sesion.id;
  if (String(targetId) !== String(sesion.id) && !esDirectivo_(sesion)) {
    throw new Error('No tienes permiso para generar el informe de otro docente');
  }

  const usuario = findRowById_(SHEET_NAMES.USUARIOS, targetId);
  if (!usuario) throw new Error('Docente no encontrado');

  const planeacionesDelMes = readRowsWhere_(
    SHEET_NAMES.PLANEACIONES,
    (p) => String(p.docente_id) === String(targetId) && mesDeFecha_(p.fecha) === mes
  ).map(parsePlaneacionRow_);

  const actividades = planeacionesDelMes.map((p) => {
    const asistentes = p.asistencia.filter((a) => a.presente).length;
    return {
      // No hay un campo "título corto" en la planeación — se usa el objetivo.
      actividad: p.objetivo,
      nro_semana: String(Math.ceil(diaDeFecha_(p.fecha) / 7)),
      horas_sede: String(HORAS_POR_CLASE),
      horas_externas: '',
      cantidad_asistentes: String(asistentes),
      fecha: fechaCorta_(p.fecha),
      link_planeacion: '', // pendiente: no hay visor de planeaciones con URL propia todavía
    };
  });

  const totalHorasDocente = planeacionesDelMes.length * HORAS_POR_CLASE;
  const totalAsistentes = actividades.reduce((sum, a) => sum + Number(a.cantidad_asistentes), 0);

  const encuentros = planeacionesDelMes.map((p, i) => {
    const foto = archivoABase64_(p.foto_clase_drive_id);
    return { nro: String(i + 1), foto_base64: foto ? foto.base64 : null, foto_mime: foto ? foto.mimeType : null };
  });

  const valorHoraDocente = Number(usuario.valor_hora_docente) || 0;
  let valorTotal = totalHorasDocente * valorHoraDocente;

  const context = {
    periodo_evaluado: `${nombreMes_(mes)} ${mes.split('-')[0]}`,
    nucleo: usuario.nucleo || '',
    nombre_docente: usuario.nombre,
    curso: usuario.curso || '',
    actividades: actividades,
    total_horas: String(totalHorasDocente),
    total_asistentes: String(totalAsistentes),

    objetivo_cumplimiento: narrativa.objetivo_cumplimiento,
    logros_avances: narrativa.logros_avances,
    dificultades: narrativa.dificultades,
    estrategias: narrativa.estrategias,
    situacion_positiva: narrativa.situacion_positiva,
    ctei_integracion: narrativa.ctei_integracion,
    avance_semanal: narrativa.avance_semanal || [],

    encuentros: encuentros,
    cedula_docente: usuario.cedula || '',
    fecha_entrega: Utilities.formatDate(new Date(), 'America/Bogota', 'dd/MM/yyyy'),

    fecha_emision: Utilities.formatDate(new Date(), 'America/Bogota', 'dd/MM/yyyy'),
    cuenta_cobro_no: String(planeacionesDelMes.length ? contarInformesPrevios_(targetId, mes) + 1 : 1),
    mes_a_cobrar: nombreMes_(mes),
    edad_desde: usuario.edad_desde || '',
    edad_hasta: usuario.edad_hasta || '',
    num_encuentros: String(planeacionesDelMes.length),
    horas_totales: String(totalHorasDocente),
    periodo_cobro: `(Del 01-${mes.split('-')[1]}-${mes.split('-')[0]} al ${ultimoDiaDelMes_(mes)}-${mes.split('-')[1]}-${mes.split('-')[0]})`,
    numero_cuenta: usuario.numero_cuenta || '',
    tipo_cuenta: usuario.tipo_cuenta || '',
    entidad_bancaria: usuario.entidad_bancaria || '',

    es_directivo: esDirectivo_({ rol: usuario.rol }),
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

/** Heurística simple: cuántos meses distintos con planeaciones tiene el docente antes de `mes`. */
function contarInformesPrevios_(docente_id, mes) {
  const meses = new Set(
    readRowsWhere_(SHEET_NAMES.PLANEACIONES, (p) => String(p.docente_id) === String(docente_id))
      .map((p) => mesDeFecha_(p.fecha))
      .filter((m) => m < mes)
  );
  return meses.size;
}

function version_actual() {
  const configRows = readAllRows_(SHEET_NAMES.CONFIG);
  const fila = configRows.find((r) => r.key === 'version_actual');
  return fila ? fila.value : '0.0.0';
}
