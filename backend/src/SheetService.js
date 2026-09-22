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

// Contenido de cada pestaña ya leído en ESTA ejecución. Una acción típica
// (revisar una planeación, por ejemplo) leía Usuarios, Config, Cursos y
// Planeaciones varias veces cada una —esAdministrador_, puedeRevisarCurso_,
// leerConfig_, findRowById_ + updateRowById_...—, y cada lectura completa
// de una pestaña cuesta una ida y vuelta al motor de Sheets. Con esto se
// lee una vez por pestaña y las demás salen de memoria.
//
// Vive y muere con la ejecución (cada doPost arranca de cero), y cualquier
// escritura la invalida: nunca devuelve algo más viejo que lo último que
// esta misma ejecución escribió. Lo que otra ejecución escriba mientras
// tanto solo se ve al invalidar de nuevo — por eso cada `waitLock` llama a
// invalidarCacheHojas_() apenas obtiene el candado.
const _hojasCache_ = {};

/**
 * Sin argumentos: olvida todo lo leído (y los últimos ids entregados) —
 * para llamar justo después de tomar un LockService, cuando otra ejecución
 * pudo haber escrito mientras se esperaba. Con un nombre: solo esa pestaña,
 * después de escribirle.
 */
function invalidarCacheHojas_(sheetName) {
  if (sheetName) {
    delete _hojasCache_[sheetName];
    return;
  }
  Object.keys(_hojasCache_).forEach((k) => { delete _hojasCache_[k]; });
  Object.keys(_ultimoIdCache_).forEach((k) => { delete _ultimoIdCache_[k]; });
}

/** {headers, values} de la pestaña: encabezado y datos en UNA sola lectura. */
function leerHoja_(sheetName) {
  let hoja = _hojasCache_[sheetName];
  if (hoja) return hoja;

  const sheet = getSheet_(sheetName);
  const lastRow = sheet.getLastRow();
  const lastCol = sheet.getLastColumn();
  if (lastRow < 1 || lastCol === 0) {
    hoja = { headers: [], values: [] };
  } else {
    const todo = sheet.getRange(1, 1, lastRow, lastCol).getValues();
    hoja = { headers: todo[0], values: todo.slice(1) };
  }
  _hojasCache_[sheetName] = hoja;
  return hoja;
}

function filaComoObjeto_(headers, valores, filaReal) {
  const obj = { _row: filaReal }; // fila real en la hoja, útil para updates
  for (let c = 0; c < headers.length; c++) {
    obj[headers[c]] = valores[c];
  }
  return obj;
}

/** Lee toda la pestaña y la devuelve como array de objetos {columna: valor}. */
function readAllRows_(sheetName) {
  const { headers, values } = leerHoja_(sheetName);
  if (values.length === 0 || headers.length === 0) return [];
  return values.map((row, i) => filaComoObjeto_(headers, row, i + 2));
}

function readRowsWhere_(sheetName, predicate) {
  const { headers, values } = leerHoja_(sheetName);
  if (values.length === 0 || headers.length === 0) return [];
  const encontradas = [];
  values.forEach((row, i) => {
    const obj = filaComoObjeto_(headers, row, i + 2);
    if (predicate(obj)) encontradas.push(obj);
  });
  return encontradas;
}

function findRowById_(sheetName, id) {
  const { headers, values } = leerHoja_(sheetName);
  const idCol = headers.indexOf('id');
  if (idCol === -1) return null;
  const buscado = String(id);
  // Arma el objeto solo de la fila que coincide, no de toda la pestaña.
  for (let i = 0; i < values.length; i++) {
    if (String(values[i][idCol]) === buscado) return filaComoObjeto_(headers, values[i], i + 2);
  }
  return null;
}

/** Agrega una fila nueva; genera id incremental si no viene definido. */
function appendRow_(sheetName, obj) {
  const sheet = getSheet_(sheetName);
  const headers = leerHoja_(sheetName).headers;
  if (headers.length === 0) {
    throw new Error(`La pestaña "${sheetName}" no tiene encabezados`);
  }

  if (obj.id === undefined || obj.id === null || obj.id === '') {
    obj.id = nextId_(sheetName);
  }

  const row = headers.map((h) => (obj[h] !== undefined ? obj[h] : ''));
  sheet.appendRow(row);
  invalidarCacheHojas_(sheetName);
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
  invalidarCacheHojas_(sheetName);
  return filas.length;
}

/** Borra una fila que el caller ya tiene leída (con su `_row`). */
function eliminarFila_(sheetName, fila) {
  getSheet_(sheetName).deleteRow(fila._row);
  invalidarCacheHojas_(sheetName);
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
  const col = leerHoja_(sheetName).headers.indexOf(campo);
  if (col === -1) return false;
  sheet.getRange(fila._row, col + 1).setValue(valor);
  invalidarCacheHojas_(sheetName);
  return true;
}

/**
 * Actualiza campos específicos de la fila con ese id. Devuelve
 * {antes, despues} solo de los campos que realmente cambiaron, para que
 * el caller pueda decir cuántos se tocaron de verdad.
 */
function updateRowById_(sheetName, id, cambios) {
  const sheet = getSheet_(sheetName);
  const headers = leerHoja_(sheetName).headers;
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
    invalidarCacheHojas_(sheetName);
  }
  return cambiosReales;
}
