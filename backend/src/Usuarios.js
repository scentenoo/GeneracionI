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
    es_admin: false,
    valor_hora_docente: datos.valor_hora_docente || '',
    valor_hora_directivo: datos.valor_hora_directivo || '',
    cedula: datos.cedula || '',
    // curso/nucleo/edades ya no viven acá: se cargan por separado con crear_curso.
    numero_cuenta: datos.numero_cuenta || '',
    tipo_cuenta: datos.tipo_cuenta || '',
    entidad_bancaria: datos.entidad_bancaria || '',
    firma_drive_id: '',
  });

  return { ok: true, id: fila.id };
}

const CAMPOS_EDITABLES_USUARIO_ = [
  'nombre', 'rol', 'valor_hora_docente', 'valor_hora_directivo', 'cedula',
  'numero_cuenta', 'tipo_cuenta', 'entidad_bancaria',
];

/**
 * Solo el directivo edita el perfil de un usuario (cédula, curso, tarifas,
 * cuenta bancaria, etc.) — un docente no toca sus propios datos, los pide
 * al equipo directivo. La contraseña tiene su propio flujo
 * (cambiarPassword) y no se toca acá.
 */
function editar_usuario(token, usuario_id, cambios) {
  const sesion = requireSession_(token);
  requireRole_(sesion, [ROLES.DIRECTIVO, ROLES.AMBOS]);

  const cambiosFiltrados = {};
  Object.keys(cambios).forEach((campo) => {
    if (CAMPOS_EDITABLES_USUARIO_.includes(campo)) {
      cambiosFiltrados[campo] = cambios[campo];
    }
  });

  if (cambiosFiltrados.rol && !Object.values(ROLES).includes(cambiosFiltrados.rol)) {
    throw new Error(`Rol inválido: ${cambiosFiltrados.rol}`);
  }

  const cambiosReales = updateRowById_(SHEET_NAMES.USUARIOS, usuario_id, cambiosFiltrados);
  return { ok: true, cambios: cambiosReales.length };
}

/**
 * Administrador único: no es un rol más (docente/directivo/ambos), es un
 * privilegio aparte sobre un usuario existente, reservado para acciones
 * irreversibles como eliminar usuarios. Se transfiere, nunca se duplica —
 * a lo sumo hay un usuario con es_admin=true a la vez.
 */

function hayAdministrador_() {
  return readAllRows_(SHEET_NAMES.USUARIOS).some((u) => u.es_admin === true);
}

function esAdministrador_(usuarioId) {
  const fila = findRowById_(SHEET_NAMES.USUARIOS, usuarioId);
  return !!fila && fila.es_admin === true;
}

function requireAdministrador_(sesion) {
  if (!esAdministrador_(sesion.id)) {
    throw new Error('Esta acción requiere ser el usuario administrador');
  }
}

/** Bootstrap: mientras no exista ningún administrador, cualquier directivo puede autoproclamarse. Se cierra solo apenas hay uno. */
function convertirme_administrador(token) {
  const sesion = requireSession_(token);
  requireRole_(sesion, [ROLES.DIRECTIVO, ROLES.AMBOS]);

  if (hayAdministrador_()) {
    throw new Error('Ya hay un administrador asignado — pedile que te transfiera el cargo');
  }

  updateRowById_(SHEET_NAMES.USUARIOS, sesion.id, { es_admin: true });
  return { ok: true };
}

/** El administrador actual le pasa el cargo a otro usuario (directivo o ambos). Nunca hay dos a la vez. */
function transferir_administrador(token, nuevo_admin_id) {
  const sesion = requireSession_(token);
  requireAdministrador_(sesion);

  const nuevoAdmin = findRowById_(SHEET_NAMES.USUARIOS, nuevo_admin_id);
  if (!nuevoAdmin) throw new Error('Usuario no encontrado');
  if (![ROLES.DIRECTIVO, ROLES.AMBOS].includes(nuevoAdmin.rol)) {
    throw new Error('El administrador tiene que ser directivo o ambos');
  }

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    updateRowById_(SHEET_NAMES.USUARIOS, sesion.id, { es_admin: false });
    updateRowById_(SHEET_NAMES.USUARIOS, nuevo_admin_id, { es_admin: true });
    return { ok: true };
  } finally {
    lock.releaseLock();
  }
}

/**
 * Elimina el LOGIN de un usuario. Un directivo puede eliminar docentes
 * (rol exactamente 'docente'); eliminar a otro directivo/ambos requiere
 * ser el administrador — así un directivo cualquiera no puede sacar a
 * otro directivo de encima. Las planeaciones y horas de gestión que haya
 * generado NO se borran — quedan como registro histórico con un
 * docente_id/directivo_id que ya no tiene login.
 */
function eliminar_usuario(token, usuario_id) {
  const sesion = requireSession_(token);

  if (String(usuario_id) === String(sesion.id)) {
    throw new Error('No podés eliminarte a vos mismo — transferí el cargo de administrador primero si hace falta');
  }

  const fila = findRowById_(SHEET_NAMES.USUARIOS, usuario_id);
  if (!fila) throw new Error('Usuario no encontrado');

  if (!esAdministrador_(sesion.id)) {
    requireRole_(sesion, [ROLES.DIRECTIVO, ROLES.AMBOS]);
    if (fila.rol !== ROLES.DOCENTE) {
      throw new Error('Un directivo solo puede eliminar usuarios con rol docente — para eliminar un directivo hace falta el administrador');
    }
  }

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    getSheet_(SHEET_NAMES.USUARIOS).deleteRow(fila._row);
    return { ok: true };
  } finally {
    lock.releaseLock();
  }
}

function listar_usuarios(token) {
  const sesion = requireSession_(token);
  requireRole_(sesion, [ROLES.DIRECTIVO, ROLES.AMBOS]);
  return readAllRows_(SHEET_NAMES.USUARIOS).map((u) => {
    const { password_hash, ...sinPassword } = u; // eslint-disable-line no-unused-vars
    sinPassword.ultimo_acceso = fechaHoraISO_(u.ultimo_acceso);
    // Sheets devuelve números donde esperamos texto: alguien que se llame
    // "2024" vuelve como int y revienta al cliente, que lo concatena.
    ['nombre', 'usuario', 'rol'].forEach((campo) => {
      sinPassword[campo] = String(sinPassword[campo] === undefined ? '' : sinPassword[campo]);
    });
    return sinPassword;
  });
}

/**
 * Le pone una contraseña nueva a otro usuario, para el caso de siempre:
 * a alguien se le olvidó la suya.
 *
 * No existe "ver la contraseña": lo guardado es un hash con salt (ver
 * Auth.js), o sea que ni el backend la conoce. Y está bien que sea así —
 * si el equipo directivo pudiera leer la de un docente, la firma de una
 * planeación dejaría de probar quién la subió.
 *
 * Permisos calcados de eliminar_usuario: un directivo restablece
 * docentes, y para tocar a otro directivo/ambos hace falta el
 * administrador. Si no, cualquier directivo se queda con la cuenta de
 * cualquier otro, incluida la del administrador.
 */
function restablecer_password(token, usuario_id, password_nueva) {
  const sesion = requireSession_(token);
  requireRole_(sesion, [ROLES.DIRECTIVO, ROLES.AMBOS]);

  const fila = findRowById_(SHEET_NAMES.USUARIOS, usuario_id);
  if (!fila) throw new Error('Usuario no encontrado');

  const esOtro = String(usuario_id) !== String(sesion.id);
  if (esOtro && fila.rol !== ROLES.DOCENTE) {
    requireAdministrador_(sesion);
  }

  requireLargoPassword_(password_nueva);

  updateRowById_(SHEET_NAMES.USUARIOS, usuario_id, {
    password_hash: crearHashConSalt_(password_nueva),
  });
  return { ok: true };
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

/**
 * Dashboard directivo: una fila por CURSO, no por docente, porque quien
 * tiene dos cursos puede ir al día en uno y atrasado en el otro.
 *
 * Lee cada tabla UNA vez y agrupa en memoria. Antes llamaba a
 * obtener_estado_mes por curso, y cada una de esas releía entera la tabla
 * de planeaciones: con 20 cursos eran 20 lecturas completas del mismo
 * dato, y eso crecía con cada mes de uso.
 */
function obtener_dashboard_directivo(token, mes) {
  const sesion = requireSession_(token);
  requireRole_(sesion, [ROLES.DIRECTIVO, ROLES.AMBOS]);

  const nombrePorId = {};
  readAllRows_(SHEET_NAMES.USUARIOS).forEach((u) => {
    nombrePorId[String(u.id)] = u.nombre;
  });

  const clasesPorCurso = {};
  readAllRows_(SHEET_NAMES.PLANEACIONES).forEach((p) => {
    if (mesDeFecha_(p.fecha) !== mes) return;
    const clave = String(p.curso_id);
    clasesPorCurso[clave] = (clasesPorCurso[clave] || 0) + 1;
  });

  const informePorCurso = {};
  readAllRows_(SHEET_NAMES.INFORMES).forEach((i) => {
    if (mesDeFecha_(i.mes) !== mes) return;
    informePorCurso[String(i.curso_id)] = i;
  });

  // Las reaperturas se leen una vez y no por curso: mesCerrado_ relee la
  // pestaña entera cada vez que se lo llama.
  const reabierto = {};
  readAllRows_(SHEET_NAMES.REAPERTURAS).forEach((r) => {
    if (mesDeFecha_(r.mes) === mes && r.abierta === true) reabierto[String(r.curso_id)] = true;
  });
  const fechaCierre = fechaDeCierre_(mes);
  const yaPasoElCorte = fechaISO_(new Date()) >= fechaCierre;

  return readRowsWhere_(SHEET_NAMES.CURSOS, (c) => c.activo === true).map((curso) => {
    const registradas = clasesPorCurso[String(curso.id)] || 0;
    const informe = informePorCurso[String(curso.id)];
    const abierto = !!reabierto[String(curso.id)];
    return {
      cerrado: yaPasoElCorte && !abierto,
      reabierto: abierto,
      dia_de_corte: diaDeCorte_(),
      fecha_cierre: fechaCierre,
      curso_id: curso.id,
      curso: curso.nombre,
      docente_id: curso.docente_id,
      docente: nombrePorId[String(curso.docente_id)] || `id ${curso.docente_id}`,
      mes: mes,
      registradas: registradas,
      esperadas: CLASES_ESPERADAS_POR_MES,
      faltantes: Math.max(0, CLASES_ESPERADAS_POR_MES - registradas),
      informe_entregado: !!informe,
      informe_actualizado_en: informe ? informe.actualizado_en : '',
    };
  });
}
