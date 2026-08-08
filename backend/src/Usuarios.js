/**
 * Gestión de usuarios y firma digital. Crear usuarios queda reservado al
 * directivo (Samir asigna la contraseña inicial, spec sección 3); cada
 * usuario la cambia después con cambiarPassword (ver Auth.js).
 */

function crear_usuario(token, datos) {
  // Bootstrap: si todavía no existe ningún usuario, no hay nadie con quien
  // loguearse para crear al primero — se permite sin sesión, pero solo
  // mientras la pestaña Usuarios esté vacía. Apenas exista uno, esta
  // ventana se cierra sola y vuelve a exigir sesión de directivo.
  const usuariosExistentes = readAllRows_(SHEET_NAMES.USUARIOS).length;
  if (usuariosExistentes > 0) {
    const sesion = requireSession_(token);
    requireRole_(sesion, [ROLES.DIRECTIVO, ROLES.AMBOS]);
  }

  if (!datos.nombre || !datos.usuario || !datos.password_inicial || !datos.rol) {
    throw new Error('Faltan datos obligatorios (nombre, usuario, password_inicial, rol)');
  }
  if (!Object.values(ROLES).includes(datos.rol)) {
    throw new Error(`Rol inválido: ${datos.rol}`);
  }

  const yaExiste = readRowsWhere_(SHEET_NAMES.USUARIOS, (u) => u.usuario === datos.usuario).length > 0;
  if (yaExiste) throw new Error(`Ya existe un usuario con el nombre de usuario "${datos.usuario}"`);

  const fila = appendRow_(SHEET_NAMES.USUARIOS, {
    nombre: datos.nombre,
    usuario: datos.usuario,
    password_hash: crearHashConSalt_(datos.password_inicial),
    rol: datos.rol,
    valor_hora_docente: datos.valor_hora_docente || '',
    valor_hora_directivo: datos.valor_hora_directivo || '',
    cedula: datos.cedula || '',
    curso: datos.curso || '',
    nucleo: datos.nucleo || '',
    edad_desde: datos.edad_desde || '',
    edad_hasta: datos.edad_hasta || '',
    numero_cuenta: datos.numero_cuenta || '',
    tipo_cuenta: datos.tipo_cuenta || '',
    entidad_bancaria: datos.entidad_bancaria || '',
    firma_drive_id: '',
  });

  return { ok: true, id: fila.id };
}

function listar_usuarios(token) {
  const sesion = requireSession_(token);
  requireRole_(sesion, [ROLES.DIRECTIVO, ROLES.AMBOS]);
  return readAllRows_(SHEET_NAMES.USUARIOS).map((u) => {
    const { password_hash, ...sinPassword } = u; // eslint-disable-line no-unused-vars
    return sinPassword;
  });
}

/** El directivo sube la firma una sola vez; se reutiliza en cada informe mensual (ver spec sección 7/11). */
function subir_firma(token, usuario_id, imagen) {
  const sesion = requireSession_(token);
  requireRole_(sesion, [ROLES.DIRECTIVO, ROLES.AMBOS]);

  const usuario = findRowById_(SHEET_NAMES.USUARIOS, usuario_id);
  if (!usuario) throw new Error('Usuario no encontrado');

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const nuevoId = reemplazarArchivo_(
      'Firmas',
      usuario.firma_drive_id,
      imagen.base64,
      imagen.mimeType || 'image/png',
      `firma_${usuario_id}.png`
    );
    updateRowById_(SHEET_NAMES.USUARIOS, usuario_id, { firma_drive_id: nuevoId });
    return { ok: true };
  } finally {
    lock.releaseLock();
  }
}

/** Dashboard directivo: qué docente lleva cuántas planeaciones este mes. */
function obtener_dashboard_directivo(token, mes) {
  const sesion = requireSession_(token);
  requireRole_(sesion, [ROLES.DIRECTIVO, ROLES.AMBOS]);

  const docentes = readAllRows_(SHEET_NAMES.USUARIOS).filter(
    (u) => u.rol === ROLES.DOCENTE || u.rol === ROLES.AMBOS
  );

  return docentes.map((d) => obtener_estado_mes(token, d.id, mes));
}
