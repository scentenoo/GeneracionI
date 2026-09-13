/**
 * Configuración central del backend. Los IDs reales de Sheet/Drive se
 * guardan en Script Properties (Project Settings > Script properties en el
 * editor de Apps Script), nunca hardcodeados aquí, para no exponerlos en git.
 */

const SHEET_NAMES = {
  USUARIOS: 'Usuarios',
  CURSOS: 'Cursos',
  PLANEACIONES: 'Planeaciones',
  ACTIVIDADES: 'Actividades',
  INFORMES: 'InformesMensuales',
  ESTUDIANTES: 'Estudiantes',
  INSCRIPCIONES: 'Inscripciones',
  HORAS_GESTION: 'HorasGestion',
  REAPERTURAS: 'Reaperturas',
  REVISIONES: 'Revisiones',
  CONFIG: 'Config',
};

const ROLES = {
  DOCENTE: 'docente',
  DIRECTIVO: 'directivo',
  AMBOS: 'ambos',
};

/** Token de sesión propio de la app (no OAuth de Google). Vive en cache, no en Sheets. */
const SESSION_TTL_SECONDS = 60 * 60 * 8; // 8 horas, cubre una jornada

function getScriptProperty_(key) {
  const value = PropertiesService.getScriptProperties().getProperty(key);
  if (!value) {
    throw new Error(
      `Falta la Script Property "${key}". Configúrela en Project Settings > Script properties.`
    );
  }
  return value;
}

// Cachea el handle por ejecución: `batch` puede correr varias acciones en un
// mismo POST y cada una llama a getSheet_ varias veces — sin esto, cada
// llamada volvía a abrir el spreadsheet entero (openById tarda de verdad,
// no es gratis) aunque ya lo hubiéramos abierto un segundo antes.
let _spreadsheetCache_ = null;

function getSpreadsheet_() {
  if (!_spreadsheetCache_) {
    _spreadsheetCache_ = SpreadsheetApp.openById(getScriptProperty_('SHEET_ID'));
  }
  return _spreadsheetCache_;
}

function getDriveRootFolder_() {
  return DriveApp.getFolderById(getScriptProperty_('DRIVE_ROOT_FOLDER_ID'));
}
