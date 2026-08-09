/**
 * La pestaña Config, que es clave/valor: la versión vigente de la app y el
 * link para descargar el instalador.
 *
 * Publicar una actualización pasa a ser: subir el .exe a Drive, y fijar
 * acá la versión y el link. El docente que abre la app ve el aviso con el
 * link y lo descarga solo, sin que nadie tenga que ir a su computador.
 */

function leerConfig_(clave) {
  const fila = readAllRows_(SHEET_NAMES.CONFIG).find((r) => r.key === clave);
  return fila ? fila.value : '';
}

function escribirConfig_(clave, valor) {
  const sheet = getSheet_(SHEET_NAMES.CONFIG);
  const fila = readAllRows_(SHEET_NAMES.CONFIG).find((r) => r.key === clave);
  if (fila) {
    // La columna 2 es `value`, según el esquema de SetupSheets.
    sheet.getRange(fila._row, 2).setValue(valor);
  } else {
    sheet.appendRow([clave, valor]);
  }
}

/**
 * La consulta el cliente ANTES de loguearse, al abrir la app, así que no
 * pide sesión. Devuelve también el link para que la pantalla de bloqueo
 * pueda ofrecer la descarga.
 */
function version_actual() {
  return {
    version: String(leerConfig_('version_actual') || '0.0.0'),
    link_instalador: String(leerConfig_('link_instalador') || ''),
  };
}

/**
 * Publica una versión. Solo el administrador: dejar a los 18 afuera por
 * error no es algo que deba poder hacer cualquiera.
 */
function fijar_version(token, version, link_instalador) {
  const sesion = requireSession_(token);
  requireAdministrador_(sesion);

  if (!version || !String(version).trim()) throw new Error('Falta el número de versión');

  const anterior = version_actual();

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    escribirConfig_('version_actual', String(version).trim());
    if (link_instalador !== undefined && link_instalador !== null) {
      escribirConfig_('link_instalador', String(link_instalador).trim());
    }
  } finally {
    lock.releaseLock();
  }

  registrarHistorial_(sesion.usuario, 'config', 'version_actual', [
    { campo: 'version_actual', antes: anterior.version, despues: String(version).trim() },
  ]);

  return { ok: true, version: String(version).trim() };
}
