/**
 * Corre esto UNA VEZ desde el editor de Apps Script (seleccioná la función
 * setupSheets en el desplegable y dale Run) para crear las pestañas con sus
 * encabezados en la Sheet configurada como SHEET_ID. No borra pestañas
 * existentes, así que es seguro volver a correrlo si se agrega una columna.
 */

const ESQUEMA_SHEETS_ = {
  [SHEET_NAMES.USUARIOS]: [
    'id', 'nombre', 'usuario', 'password_hash', 'rol',
    'valor_hora_docente', 'valor_hora_directivo', 'cedula',
    'curso', 'nucleo', 'edad_desde', 'edad_hasta',
    'numero_cuenta', 'tipo_cuenta', 'entidad_bancaria', 'firma_drive_id',
  ],
  [SHEET_NAMES.PLANEACIONES]: [
    'id', 'docente_id', 'fecha', 'grupo', 'objetivo', 'temas_vistos',
    'bloques', 'foto_clase_drive_id', 'asistencia', 'horas', 'creado_en',
  ],
  [SHEET_NAMES.ESTUDIANTES]: ['id', 'nombre', 'docente_id'],
  [SHEET_NAMES.HORAS_GESTION]: [
    'id', 'directivo_id', 'fecha', 'actividad', 'horas_sede',
    'entregable', 'link_soporte', 'creado_en',
  ],
  [SHEET_NAMES.HISTORIAL]: [
    'timestamp', 'usuario', 'tipo', 'id_afectado', 'campo', 'valor_anterior', 'valor_nuevo',
  ],
  [SHEET_NAMES.CONFIG]: ['key', 'value'],
};

function setupSheets() {
  const ss = getSpreadsheet_();

  Object.entries(ESQUEMA_SHEETS_).forEach(([nombre, headers]) => {
    let sheet = ss.getSheetByName(nombre);
    if (!sheet) {
      sheet = ss.insertSheet(nombre);
    }
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
    sheet.setFrozenRows(1);
  });

  const config = ss.getSheetByName(SHEET_NAMES.CONFIG);
  const yaTieneVersion = config
    .getRange(2, 1, Math.max(config.getLastRow() - 1, 0), 1)
    .getValues()
    .some((r) => r[0] === 'version_actual');
  if (!yaTieneVersion) {
    config.appendRow(['version_actual', '1.0.0']);
  }

  Logger.log('Listo: pestañas creadas/actualizadas en %s', ss.getUrl());
}
