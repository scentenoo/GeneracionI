/**
 * Corre esto UNA VEZ desde el editor de Apps Script (seleccioná la función
 * setupSheets en el desplegable y dale Run) para crear las pestañas con sus
 * encabezados en la Sheet configurada como SHEET_ID. No borra pestañas
 * existentes, así que es seguro volver a correrlo si se agrega una columna.
 */

/**
 * Primer setup completo: crea la Sheet y la carpeta de Drive raíz si no
 * existen todavía, guarda sus IDs en Script Properties y arma las pestañas.
 * Idempotente — correrlo de nuevo no duplica nada, así que es seguro darle
 * Run más de una vez.
 */
function inicializarProyecto() {
  const props = PropertiesService.getScriptProperties();

  let sheetId = props.getProperty('SHEET_ID');
  if (!sheetId) {
    const ss = SpreadsheetApp.create('Generación-I - Base de datos');
    sheetId = ss.getId();
    props.setProperty('SHEET_ID', sheetId);
    Logger.log('Sheet creada: %s', ss.getUrl());
  }

  let folderId = props.getProperty('DRIVE_ROOT_FOLDER_ID');
  if (!folderId) {
    const folder = DriveApp.createFolder('Generación-I');
    folderId = folder.getId();
    props.setProperty('DRIVE_ROOT_FOLDER_ID', folderId);
    Logger.log('Carpeta de Drive creada: %s', folder.getUrl());
  }

  setupSheets();

  Logger.log('Listo. Sheet: https://docs.google.com/spreadsheets/d/%s/edit', sheetId);
  Logger.log('Carpeta Drive: https://drive.google.com/drive/folders/%s', folderId);
}

const ESQUEMA_SHEETS_ = {
  // curso/nucleo/edades ya no viven acá: se movieron a Cursos, porque una
  // misma persona puede tener varios cursos con distinto núcleo y edades.
  [SHEET_NAMES.USUARIOS]: [
    'id', 'nombre', 'usuario', 'password_hash', 'rol', 'es_admin',
    'valor_hora_docente', 'valor_hora_directivo', 'cedula',
    'numero_cuenta', 'tipo_cuenta', 'entidad_bancaria', 'firma_drive_id',
    'ultimo_acceso',
  ],
  [SHEET_NAMES.CURSOS]: [
    'id', 'docente_id', 'nombre', 'nucleo', 'edad_desde', 'edad_hasta', 'activo',
  ],
  [SHEET_NAMES.PLANEACIONES]: [
    'id', 'docente_id', 'curso_id', 'fecha', 'grupo', 'objetivo', 'temas_vistos',
    'bloques', 'foto_clase_drive_id', 'asistencia', 'horas', 'creado_en',
    'doc_drive_id',
    // Formato Diario Pedagógico: los tres momentos (JSON) y las dos
    // columnas de toda la clase. `bloques` queda por compatibilidad.
    'momentos', 'observaciones', 'avances',
  ],
  // Lo que se factura y no es una clase: reuniones, claustros, informes.
  // En el informe de julio de Samir eran 8 de las 16 horas del mes, así que
  // sin esto la cuenta de cobro salía por la mitad.
  [SHEET_NAMES.ACTIVIDADES]: [
    'id', 'usuario_id', 'curso_id', 'fecha', 'descripcion',
    'horas_sede', 'horas_externas', 'foto_drive_id', 'creado_en',
  ],
  // Las respuestas narrativas del mes, que antes se escribían una vez y se
  // perdían. Una fila por curso y mes.
  [SHEET_NAMES.INFORMES]: [
    'id', 'curso_id', 'docente_id', 'mes',
    'objetivo_cumplimiento', 'logros_avances', 'dificultades',
    'estrategias', 'situacion_positiva', 'ctei_integracion',
    'avance_semanal',
    'incluye_gestion', 'gestion_objetivos', 'gestion_logros',
    'gestion_novedades', 'gestion_estrategias', 'gestion_pendientes',
    'creado_en', 'actualizado_en',
  ],
  // Una ficha por persona. `curso_id` quedó de cuando el estudiante
  // colgaba de un solo curso; hoy manda Inscripciones (ver migrarAInscripciones).
  [SHEET_NAMES.ESTUDIANTES]: ['id', 'nombre', 'curso_id'],
  // Un estudiante puede estar en varios cursos: inglés y robótica, por
  // ejemplo. Antes había que escribirlo una vez por curso y, si se escribía
  // distinto, quedaba como dos personas.
  [SHEET_NAMES.INSCRIPCIONES]: ['id', 'estudiante_id', 'curso_id', 'creado_en'],
  [SHEET_NAMES.HORAS_GESTION]: [
    'id', 'directivo_id', 'fecha', 'actividad', 'horas_sede',
    'entregable', 'link_soporte', 'creado_en',
  ],
  // Un mes que el equipo directivo volvió a abrir para un curso puntual,
  // después de la fecha de corte.
  [SHEET_NAMES.REAPERTURAS]: [
    'id', 'curso_id', 'mes', 'abierta', 'abierto_por', 'actualizado_en',
  ],
  [SHEET_NAMES.CONFIG]: ['key', 'value'],
};

/**
 * Crea las pestañas que falten y agrega al final las columnas nuevas del
 * esquema. Nunca reordena ni pisa encabezados existentes: escribir la fila
 * 1 completa sobre una hoja con datos desalinearía los valores, que
 * quedarían bajo la columna equivocada. Quitar columnas es tarea de las
 * migraciones, no de esto.
 */
function setupSheets() {
  const ss = getSpreadsheet_();

  Object.entries(ESQUEMA_SHEETS_).forEach(([nombre, headers]) => {
    let sheet = ss.getSheetByName(nombre);
    if (!sheet) {
      sheet = ss.insertSheet(nombre);
      sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
      sheet.setFrozenRows(1);
      return;
    }

    const actuales = sheet.getLastColumn() > 0
      ? sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0].filter(String)
      : [];

    const faltantes = headers.filter((h) => actuales.indexOf(h) === -1);
    if (faltantes.length > 0) {
      sheet.getRange(1, actuales.length + 1, 1, faltantes.length).setValues([faltantes]);
      Logger.log('%s: columnas agregadas -> %s', nombre, faltantes.join(', '));
    }
    sheet.setFrozenRows(1);
  });

  const config = ss.getSheetByName(SHEET_NAMES.CONFIG);
  const yaTieneVersion =
    config.getLastRow() > 1 &&
    config
      .getRange(2, 1, config.getLastRow() - 1, 1)
      .getValues()
      .some((r) => r[0] === 'version_actual');
  if (!yaTieneVersion) {
    config.appendRow(['version_actual', '1.0.0']);
    config.appendRow(['link_instalador', '']);
  }

  Logger.log('Listo: pestañas creadas/actualizadas en %s', ss.getUrl());
}
