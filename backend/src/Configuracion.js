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
  invalidarCacheHojas_(SHEET_NAMES.CONFIG);
}

/**
 * La consulta el cliente ANTES de loguearse, al abrir la app, así que no
 * pide sesión.
 *
 * Devuelve dos números, no uno:
 *  - version: la última publicada. Quien tenga una anterior ve un aviso
 *    con el link, pero puede seguir trabajando.
 *  - version_minima: la mínima obligatoria. Quien esté por debajo queda
 *    bloqueado hasta que actualice.
 *
 * La distinción existe para no dejar a 17 personas afuera por una mejora
 * menor: solo un arreglo que de verdad no puede esperar sube la mínima.
 */
function version_actual() {
  const actual = String(leerConfig_('version_actual') || '0.0.0');
  // Si nunca se fijó una mínima, ninguna versión bloquea: se toma la más
  // baja posible, así todo lo instalado sigue entrando.
  return {
    version: actual,
    version_minima: String(leerConfig_('version_minima') || '0.0.0'),
    link_instalador: String(leerConfig_('link_instalador') || ''),
  };
}

/**
 * Compara dos versiones tipo "1.10.0". Devuelve -1, 0 o 1. Sin esto,
 * "1.9.0" > "1.10.0" al comparar como texto, y una obligatoria mal puesta
 * dejaría afuera justo a quien sí actualizó.
 */
function compararVersiones_(a, b) {
  const pa = String(a).split('.').map(Number);
  const pb = String(b).split('.').map(Number);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const x = pa[i] || 0;
    const y = pb[i] || 0;
    if (x !== y) return x < y ? -1 : 1;
  }
  return 0;
}

/**
 * Publica una versión. Solo el administrador: dejar a los 18 afuera por
 * error no es algo que deba poder hacer cualquiera.
 *
 * `obligatoria` marca si esta versión sube el piso: cuando es true, la
 * mínima pasa a ser esta versión y todo lo anterior queda bloqueado.
 * Cuando es false, la vigente avanza pero la mínima se queda donde estaba,
 * así que las versiones viejas solo ven un aviso.
 */
function fijar_version(token, version, link_instalador, obligatoria) {
  const sesion = requireSession_(token);
  requireAdministrador_(sesion);

  const nueva = String(version || '').trim();
  if (!nueva) throw new Error('Falta el número de versión');
  if (!/^\d+(\.\d+)*$/.test(nueva)) {
    throw new Error('La versión debe ser números separados por puntos, como 1.2.0');
  }

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  invalidarCacheHojas_();
  try {
    escribirConfig_('version_actual', nueva);
    if (link_instalador !== undefined && link_instalador !== null) {
      escribirConfig_('link_instalador', String(link_instalador).trim());
    }
    if (obligatoria === true) {
      escribirConfig_('version_minima', nueva);
    } else {
      // Una obligatoria no puede quedar por encima de la vigente: si la
      // mínima vieja fuera mayor que esta versión, nadie podría entrar ni
      // con la que acabás de publicar.
      const minimaVieja = String(leerConfig_('version_minima') || '0.0.0');
      if (compararVersiones_(minimaVieja, nueva) > 0) {
        escribirConfig_('version_minima', nueva);
      }
    }
  } finally {
    lock.releaseLock();
  }

  return { ok: true, version: nueva, obligatoria: obligatoria === true };
}
