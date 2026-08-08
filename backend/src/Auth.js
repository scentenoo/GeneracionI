/**
 * Login propio de la app (usuario/contraseña de la pestaña Usuarios, no
 * cuentas de Google). Sesiones cortas en CacheService, no en Sheets: no hace
 * falta que sobrevivan un reinicio del servidor y evitamos escribir en cada
 * request.
 */

function hashPassword_(password, salt) {
  const digest = Utilities.computeDigest(
    Utilities.DigestAlgorithm.SHA_256,
    salt + password,
    Utilities.Charset.UTF_8
  );
  return digest.map((b) => (b < 0 ? b + 256 : b).toString(16).padStart(2, '0')).join('');
}

function crearHashConSalt_(password) {
  const salt = Utilities.getUuid();
  return `${salt}:${hashPassword_(password, salt)}`;
}

function verificarPassword_(password, hashGuardado) {
  const [salt, hash] = String(hashGuardado).split(':');
  if (!salt || !hash) return false;
  return hashPassword_(password, salt) === hash;
}

function login(usuario, password) {
  const fila = readRowsWhere_(SHEET_NAMES.USUARIOS, (u) => u.usuario === usuario)[0];
  if (!fila || !verificarPassword_(password, fila.password_hash)) {
    throw new Error('Usuario o contraseña incorrectos');
  }

  const token = Utilities.getUuid();
  const sesion = {
    id: fila.id,
    nombre: fila.nombre,
    usuario: fila.usuario,
    rol: fila.rol,
    // El backend siempre revalida es_admin contra la Sheet en las acciones
    // sensibles (ver requireAdministrador_) — esto es solo para que el
    // cliente sepa qué botones mostrar, no es la fuente de verdad.
    es_admin: fila.es_admin === true,
  };
  CacheService.getScriptCache().put(`session:${token}`, JSON.stringify(sesion), SESSION_TTL_SECONDS);

  return Object.assign({ token }, sesion);
}

function cambiarPassword(token, passwordActual, passwordNueva) {
  const sesion = requireSession_(token);
  const fila = findRowById_(SHEET_NAMES.USUARIOS, sesion.id);
  if (!verificarPassword_(passwordActual, fila.password_hash)) {
    throw new Error('La contraseña actual no es correcta');
  }
  updateRowById_(SHEET_NAMES.USUARIOS, sesion.id, { password_hash: crearHashConSalt_(passwordNueva) });
  return { ok: true };
}

/** Lanza si el token no existe/expiró. Todas las funciones protegidas empiezan llamando esto. */
function requireSession_(token) {
  const raw = CacheService.getScriptCache().get(`session:${token}`);
  if (!raw) throw new Error('Sesión inválida o expirada, vuelve a iniciar sesión');
  return JSON.parse(raw);
}

function requireRole_(sesion, rolesPermitidos) {
  if (!rolesPermitidos.includes(sesion.rol)) {
    throw new Error(`Esta acción requiere rol ${rolesPermitidos.join(' o ')}`);
  }
}

/** true si el usuario tiene componente docente (rol docente o ambos). */
function esDocente_(sesion) {
  return sesion.rol === ROLES.DOCENTE || sesion.rol === ROLES.AMBOS;
}

/** true si el usuario tiene componente directivo (rol directivo o ambos). */
function esDirectivo_(sesion) {
  return sesion.rol === ROLES.DIRECTIVO || sesion.rol === ROLES.AMBOS;
}
