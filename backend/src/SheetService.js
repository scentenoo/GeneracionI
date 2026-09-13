/**
 * Helpers genéricos para leer/escribir pestañas de Sheets como si fueran
 * tablas de objetos. Todas las pestañas usan la primera fila como encabezado
 * y una columna "id" única por fila.
 */

function getSheet_(sheetName) {
  const sheet = getSpreadsheet_().getSheetByName(sheetName);
  if (!sheet) throw new Error(`No existe la pestaña "${sheetName}"`);
  return sheet;
}

function getHeaders_(sheet) {
  const lastCol = sheet.getLastColumn();
  if (lastCol === 0) return [];
  return sheet.getRange(1, 1, 1, lastCol).getValues()[0];
}

/** Lee toda la pestaña y la devuelve como array de objetos {columna: valor}. */
function readAllRows_(sheetName) {
  const sheet = getSheet_(sheetName);
  const lastRow = sheet.getLastRow();
  const headers = getHeaders_(sheet);
  if (lastRow < 2 || headers.length === 0) return [];

  const values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  return values.map((row, i) => {
    const obj = { _row: i + 2 }; // fila real en la hoja, útil para updates
    headers.forEach((h, colIdx) => {
      obj[h] = row[colIdx];
    });
    return obj;
  });
}

function readRowsWhere_(sheetName, predicate) {
  return readAllRows_(sheetName).filter(predicate);
}

function findRowById_(sheetName, id) {
  const rows = readAllRows_(sheetName);
  return rows.find((r) => String(r.id) === String(id)) || null;
}

/** Agrega una fila nueva; genera id incremental si no viene definido. */
function appendRow_(sheetName, obj) {
  const sheet = getSheet_(sheetName);
  const headers = getHeaders_(sheet);
  if (headers.length === 0) {
    throw new Error(`La pestaña "${sheetName}" no tiene encabezados`);
  }

  if (obj.id === undefined || obj.id === null || obj.id === '') {
    obj.id = nextId_(sheetName);
  }

  const row = headers.map((h) => (obj[h] !== undefined ? obj[h] : ''));
  sheet.appendRow(row);
  return obj;
}

// Último id entregado por pestaña, cacheado durante esta ejecución. Sin
// esto, importar un CSV de 30 estudiantes releía la pestaña Estudiantes
// entera (y la de Inscripciones) una vez por cada fila nueva — la carga de
// un curso completo se sentía lentísima aunque cada lectura individual
// fuera rápida. Vive y muere con la ejecución: no hay forma de que quede
// desactualizado entre pedidos.
const _ultimoIdCache_ = {};

function nextId_(sheetName) {
  if (!(sheetName in _ultimoIdCache_)) {
    const rows = readAllRows_(sheetName);
    _ultimoIdCache_[sheetName] = rows.reduce((max, r) => {
      const n = Number(r.id);
      return Number.isFinite(n) && n > max ? n : max;
    }, 0);
  }
  _ultimoIdCache_[sheetName] += 1;
  return _ultimoIdCache_[sheetName];
}

/**
 * Borra todas las filas que cumplan el predicado. Devuelve cuántas.
 *
 * Va de abajo hacia arriba a propósito: borrar la fila 5 corre la 6 al
 * lugar de la 5, así que recorriendo de arriba hacia abajo se saltearía
 * una fila por cada borrado.
 */
function eliminarFilasDonde_(sheetName, predicate) {
  const filas = readAllRows_(sheetName).filter(predicate);
  if (filas.length === 0) return 0;

  const sheet = getSheet_(sheetName);
  filas
    .map((f) => f._row)
    .sort((a, b) => b - a)
    .forEach((fila) => sheet.deleteRow(fila));
  return filas.length;
}

/**
 * Escribe un solo campo de una fila que el caller ya tiene leída.
 *
 * updateRowById_ vuelve a leer la pestaña entera para encontrar la fila;
 * cuando ya la tenemos en la mano eso es una lectura completa al pedo. Lo
 * usa el login, que corre cada vez que alguien abre la app.
 *
 * Devuelve false si la columna todavía no existe, para que el caller siga
 * andando mientras no se haya corrido setupSheets.
 */
function setCampoDeFila_(sheetName, fila, campo, valor) {
  const sheet = getSheet_(sheetName);
  const col = getHeaders_(sheet).indexOf(campo);
  if (col === -1) return false;
  sheet.getRange(fila._row, col + 1).setValue(valor);
  return true;
}

/**
 * Actualiza campos específicos de la fila con ese id. Devuelve
 * {antes, despues} solo de los campos que realmente cambiaron, para que
 * el caller pueda decir cuántos se tocaron de verdad.
 */
function updateRowById_(sheetName, id, cambios) {
  const sheet = getSheet_(sheetName);
  const headers = getHeaders_(sheet);
  const row = findRowById_(sheetName, id);
  if (!row) throw new Error(`No se encontró id=${id} en "${sheetName}"`);

  const cambiosReales = [];
  // Una sola escritura para toda la fila en vez de un setValue() por campo
  // cambiado: al motor de Sheets cada llamada le cuesta lo mismo tenga un
  // valor o diez, así que juntarlas en una sola gana justo cuando más de un
  // campo cambia a la vez (el caso normal de un "editar").
  const nuevaFila = headers.map((h) => row[h]);
  headers.forEach((h, colIdx) => {
    if (Object.prototype.hasOwnProperty.call(cambios, h) && cambios[h] !== row[h]) {
      cambiosReales.push({ campo: h, antes: row[h], despues: cambios[h] });
      nuevaFila[colIdx] = cambios[h];
    }
  });
  if (cambiosReales.length > 0) {
    sheet.getRange(row._row, 1, 1, headers.length).setValues([nuevaFila]);
  }
  return cambiosReales;
}
