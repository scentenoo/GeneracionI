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

/**
 * Normaliza un nombre de usuario para compararlo.
 *
 * Dos motivos. Uno: Sheets convierte a número los logins que parecen
 * número, así que un usuario "1" volvía como 1 y `1 === "1"` es false —
 * esa persona no podía entrar nunca, con ninguna contraseña. Dos: los
 * docentes escriben con mayúscula al empezar y con un espacio pegado al
 * copiar; nada de eso debería ser un usuario distinto.
 */
function usuarioNormalizado_(usuario) {
  return String(usuario === undefined || usuario === null ? '' : usuario).trim().toLowerCase();
}

function login(usuario, password) {
  const buscado = usuarioNormalizado_(usuario);
  const fila = readRowsWhere_(
    SHEET_NAMES.USUARIOS,
    (u) => usuarioNormalizado_(u.usuario) === buscado
  )[0];
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

  // Para que el equipo directivo vea quién viene usando la app: alguien
  // que nunca entró probablemente ni la tiene instalada.
  setCampoDeFila_(SHEET_NAMES.USUARIOS, fila, 'ultimo_acceso', ahoraISO_());

  return Object.assign({ token }, sesion);
}

function cambiarPassword(token, passwordActual, passwordNueva) {
  const sesion = requireSession_(token);
  const fila = findRowById_(SHEET_NAMES.USUARIOS, sesion.id);
  if (!verificarPassword_(passwordActual, fila.password_hash)) {
    throw new Error('La contraseña actual no es correcta');
  }
  requireLargoPassword_(passwordNueva);
  updateRowById_(SHEET_NAMES.USUARIOS, sesion.id, { password_hash: crearHashConSalt_(passwordNueva) });
  return { ok: true };
}

/** Lanza si el token no existe/expiró. Todas las funciones protegidas empiezan llamando esto. */
function requireSession_(token) {
  const raw = CacheService.getScriptCache().get(`session:${token}`);
  if (!raw) throw new Error('Sesión inválida o expirada, vuelve a iniciar sesión');
  return JSON.parse(raw);
}

/**
 * El administrador entra a todo lo que entra un directivo, aunque su rol
 * sea docente: es quien tiene que poder arreglar las cosas.
 *
 * Ojo con la diferencia: esto es sobre lo que se PUEDE HACER. Lo que la
 * persona ES sigue saliendo del rol, y eso es lo que decide la estructura
 * de su informe mensual y si el cierre de mes lo alcanza. Samir da clase y
 * además administra la app; administrar no es un cargo del programa, así
 * que no cobra horas de gestión y su informe es el de cualquier docente.
 */
function requireRole_(sesion, rolesPermitidos) {
  if (rolesPermitidos.includes(sesion.rol)) return;
  if (rolesPermitidos.includes(ROLES.DIRECTIVO) && esAdministrador_(sesion.id)) return;
  throw new Error(`Esta acción requiere rol ${rolesPermitidos.join(' o ')}`);
}

/** true si el usuario tiene componente docente (rol docente o ambos). */
function esDocente_(sesion) {
  return sesion.rol === ROLES.DOCENTE || sesion.rol === ROLES.AMBOS;
}

/** true si el usuario tiene componente directivo (rol directivo o ambos). */
function esDirectivo_(sesion) {
  return sesion.rol === ROLES.DIRECTIVO || sesion.rol === ROLES.AMBOS;
}

/**
 * Supervisar es ver o tocar lo de otra persona: las planeaciones de un
 * docente, sus estudiantes, su informe. Lo pueden el equipo directivo y
 * también el administrador.
 *
 * Responde una pregunta distinta de esDirectivo_, que es "¿ocupa un cargo
 * directivo EN EL PROGRAMA?". De eso dependen la foto opcional, saltarse
 * el cierre de mes y la sección de gestión del informe — cosas que el
 * administrador NO hereda, porque administrar la app no es un cargo del
 * programa y no se cobra.
 *
 * Estaban mezcladas en una sola función, y al pasar al administrador a
 * rol docente perdió el acceso a los datos de todos: podía abrir el
 * dashboard pero no revisar la planeación de nadie.
 *
 * Lee es_admin de la sesión en vez de releer la Sheet: esto corre en cada
 * lectura de planeaciones. Las acciones irreversibles siguen pasando por
 * requireAdministrador_, que sí revalida contra la Sheet.
 */
function puedeSupervisar_(sesion) {
  return esDirectivo_(sesion) || sesion.es_admin === true;
}
