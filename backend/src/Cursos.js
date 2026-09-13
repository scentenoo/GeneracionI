/**
 * Cursos de cada docente. Un docente puede tener varios — en la nómina,
 * Wendy Valle figura con "Matemáticas niños" y "Español adolescentes"
 * como dos filas separadas, cada una con su propio pago.
 *
 * El curso es la unidad del informe mensual: quien tiene dos cursos
 * entrega dos informes al mes, uno por cada uno. Por eso `nucleo` y el
 * rango de edades viven acá y no en Usuarios — cambian de un curso a otro
 * aunque sea la misma persona.
 *
 * Los estudiantes y las planeaciones cuelgan del curso, no del docente.
 */

/**
 * Normaliza el color de revisión. Vacío es válido —un curso puede nacer sin
 * revisor asignado— pero cualquier otra cosa que no sea verde o morado es
 * un error: `revisorDeCurso_` busca la clave `revisor_<color>` en Config y
 * un "Verde " con espacio, o un "azul", dejaría el curso sin quien lo mire.
 */
function colorDeCurso_(valor) {
  const color = String(valor === undefined || valor === null ? '' : valor).trim().toLowerCase();
  if (color === '') return '';
  if (color !== 'verde' && color !== 'morado') {
    throw new Error(`Color de curso inválido: "${valor}". Tiene que ser verde o morado.`);
  }
  return color;
}

function crear_curso(token, datos) {
  const sesion = requireSession_(token);
  requireRole_(sesion, [ROLES.DIRECTIVO, ROLES.AMBOS]);

  if (!datos.nombre || !datos.docente_id) {
    throw new Error('Faltan datos obligatorios (nombre, docente_id)');
  }

  // El color es obligatorio al crear —no al editar, porque los cursos que
  // vienen de antes pueden no tenerlo—. Un curso nace con quien lo revisa
  // ya definido, o no nace: sin color, sus planeaciones se apilan en
  // pendiente y nadie se entera.
  const color = colorDeCurso_(datos.color);
  if (!color) {
    throw new Error('Elija el color del curso: es lo que define quién lo revisa (verde o morado)');
  }

  const docente = findRowById_(SHEET_NAMES.USUARIOS, datos.docente_id);
  if (!docente) throw new Error('Docente no encontrado');
  if (![ROLES.DOCENTE, ROLES.AMBOS].includes(docente.rol)) {
    throw new Error('Solo se le pueden asignar cursos a un usuario con rol docente o ambos');
  }

  const fila = appendRow_(SHEET_NAMES.CURSOS, {
    docente_id: datos.docente_id,
    nombre: datos.nombre,
    nucleo: datos.nucleo || '',
    edad_desde: datos.edad_desde || '',
    edad_hasta: datos.edad_hasta || '',
    activo: true,
    // El color se elige desde el alta y no solo al editar: un curso sin
    // color no lo revisa nadie más que el administrador, y en silencio.
    color: color,
  });

  return { ok: true, id: fila.id };
}

/**
 * Sin `docente_id` devuelve los cursos del propio usuario — que es lo que
 * necesita el docente para el desplegable de la planeación. El directivo
 * puede pedir los de cualquiera.
 */
function listar_cursos(token, docente_id, incluir_inactivos) {
  const sesion = requireSession_(token);
  const targetId = docente_id || sesion.id;

  if (String(targetId) !== String(sesion.id) && !puedeSupervisar_(sesion)) {
    throw new Error('No tiene permiso para ver los cursos de otro docente');
  }

  return readRowsWhere_(
    SHEET_NAMES.CURSOS,
    (c) => String(c.docente_id) === String(targetId) && (incluir_inactivos || c.activo === true)
  );
}

/** Todos los cursos del programa, para las pantallas del directivo. */
function listar_todos_los_cursos(token) {
  const sesion = requireSession_(token);
  requireRole_(sesion, [ROLES.DIRECTIVO, ROLES.AMBOS]);
  return readAllRows_(SHEET_NAMES.CURSOS);
}

const CAMPOS_EDITABLES_CURSO_ = [
  'nombre', 'nucleo', 'edad_desde', 'edad_hasta', 'docente_id', 'activo', 'color',
  'excluido_certificado',
];

function editar_curso(token, curso_id, cambios) {
  const sesion = requireSession_(token);
  requireRole_(sesion, [ROLES.DIRECTIVO, ROLES.AMBOS]);

  const cambiosFiltrados = {};
  Object.keys(cambios).forEach((campo) => {
    if (CAMPOS_EDITABLES_CURSO_.includes(campo)) cambiosFiltrados[campo] = cambios[campo];
  });
  if (cambiosFiltrados.color !== undefined) {
    cambiosFiltrados.color = colorDeCurso_(cambiosFiltrados.color);
  }

  const cambiosReales = updateRowById_(SHEET_NAMES.CURSOS, curso_id, cambiosFiltrados);
  return { ok: true, cambios: cambiosReales.length };
}

/**
 * No borra la fila: la marca inactiva. Las planeaciones ya guardadas
 * apuntan a este curso y tienen que seguir resolviendo su nombre para los
 * informes de meses anteriores.
 */
/**
 * Borra un curso y TODO lo que le cuelga, sin vuelta atrás.
 *
 * No es lo que se usa normalmente: para un curso que terminó está
 * desactivar_curso, que lo esconde y conserva los informes ya
 * entregados. Esto es para el curso creado por error o de prueba, donde
 * dejar el rastro solo ensucia el dashboard.
 *
 * Borra en orden hijos → padre para que un fallo a mitad de camino no
 * deje planeaciones apuntando a un curso que ya no existe.
 *
 * Solo el administrador, y devuelve el detalle de lo borrado para poder
 * decir exactamente qué se fue.
 */
function eliminar_curso_definitivo(token, curso_id) {
  const sesion = requireSession_(token);
  requireAdministrador_(sesion);

  const curso = findRowById_(SHEET_NAMES.CURSOS, curso_id);
  if (!curso) throw new Error('Curso no encontrado');

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const borradas = {};

    // El historial de revisión cuelga por ref (id de planeación, o
    // curso|mes del informe), no por curso, así que hay que limpiarlo a
    // mano antes de borrar las filas — si no, queda suelto y como los ids
    // se reusan lo heredaría otro documento.
    //
    // Mismo motivo para las fotos y documentos: eliminarFilasDonde_ borra
    // filas de la Sheet, no sabe nada de Drive. Sin este paso, el borrado
    // en cascada de un curso deja huérfano en Drive todo lo que sus
    // planeaciones y actividades habían subido.
    readRowsWhere_(SHEET_NAMES.PLANEACIONES, function (p) {
      return String(p.curso_id) === String(curso_id);
    }).forEach(function (p) {
      borrarRevisiones_('planeacion', String(p.id));
      fotosClaseDriveIds_(p).forEach(trasharSiExiste_);
      trasharSiExiste_(p.doc_drive_id);
    });
    readRowsWhere_(SHEET_NAMES.ACTIVIDADES, function (a) {
      return String(a.curso_id) === String(curso_id);
    }).forEach(function (a) { trasharSiExiste_(a.foto_drive_id); });
    readRowsWhere_(SHEET_NAMES.INFORMES, function (i) {
      return String(i.curso_id) === String(curso_id);
    }).forEach(function (i) {
      borrarRevisiones_('informe', curso_id + '|' + mesDeFecha_(i.mes));
      trasharSiExiste_(i.doc_drive_id);
    });

    [
      [SHEET_NAMES.PLANEACIONES, 'curso_id'],
      [SHEET_NAMES.ACTIVIDADES, 'curso_id'],
      [SHEET_NAMES.INFORMES, 'curso_id'],
      [SHEET_NAMES.INSCRIPCIONES, 'curso_id'],
      [SHEET_NAMES.REAPERTURAS, 'curso_id'],
    ].forEach(function (par) {
      borradas[par[0]] = eliminarFilasDonde_(par[0], function (fila) {
        return String(fila[par[1]]) === String(curso_id);
      });
    });

    // Los estudiantes viven aparte de los cursos desde que uno puede
    // estar en varios: se borra la inscripción, no la persona. La ficha
    // queda huérfana solo si no le queda ninguna inscripción.
    borradas[SHEET_NAMES.ESTUDIANTES] = eliminarEstudiantesSinInscripcion_();

    getSheet_(SHEET_NAMES.CURSOS).deleteRow(curso._row);
    borradas[SHEET_NAMES.CURSOS] = 1;

    return { ok: true, curso: curso.nombre, borradas: borradas };
  } finally {
    lock.releaseLock();
  }
}

function desactivar_curso(token, curso_id) {
  const sesion = requireSession_(token);
  requireRole_(sesion, [ROLES.DIRECTIVO, ROLES.AMBOS]);

  const curso = findRowById_(SHEET_NAMES.CURSOS, curso_id);
  if (!curso) throw new Error('Curso no encontrado');

  updateRowById_(SHEET_NAMES.CURSOS, curso_id, { activo: false });
  return { ok: true };
}

/** Helper interno: lanza si el curso no existe o no es del docente indicado. */
function requireCursoDelDocente_(curso_id, docente_id) {
  const curso = findRowById_(SHEET_NAMES.CURSOS, curso_id);
  if (!curso) throw new Error(`No se encontró el curso ${curso_id}`);
  if (String(curso.docente_id) !== String(docente_id)) {
    throw new Error('Ese curso no es suyo');
  }
  return curso;
}

/**
 * Estado del núcleo del propio usuario: una fila por cada curso de ese
 * núcleo (el suyo y los de sus compañeros), con cuántas planeaciones lleva
 * cada uno y si ya entregó el informe del mes.
 *
 * Existe porque la revisión de dirección pasó a ser por núcleo completo
 * entregado, no por profe suelto: si a uno le falta, se atrasa la revisión
 * de todos. Esta vista deja que los mismos profes se empujen entre sí sin
 * que dirección tenga que estar recordándoles uno por uno.
 *
 * A diferencia de obtener_dashboard_directivo, la puede pedir cualquier
 * usuario con sesión (no hace falta ser directivo) — pero solo ve los
 * cursos de SU PROPIO núcleo, nunca de otro. Sin cursos propios (un
 * directivo sin componente docente) devuelve la lista vacía.
 */
function obtener_estado_nucleo(token, mes) {
  const sesion = requireSession_(token);

  const misCursos = readRowsWhere_(
    SHEET_NAMES.CURSOS,
    (c) => String(c.docente_id) === String(sesion.id) && c.activo === true
  );
  const nucleos = {};
  misCursos.forEach((c) => {
    const nombre = String(c.nucleo || '').trim();
    if (nombre) nucleos[nombre] = true;
  });
  const nombresNucleo = Object.keys(nucleos);
  if (nombresNucleo.length === 0) return { nucleo: '', mes: mes, cursos: [] };

  const nombrePorId = {};
  readAllRows_(SHEET_NAMES.USUARIOS).forEach((u) => { nombrePorId[String(u.id)] = u.nombre; });

  const clasesPorCurso = {};
  readAllRows_(SHEET_NAMES.PLANEACIONES).forEach((p) => {
    if (mesDeFecha_(p.fecha) !== mes) return;
    const clave = String(p.curso_id);
    clasesPorCurso[clave] = (clasesPorCurso[clave] || 0) + 1;
  });

  const informePorCurso = {};
  readAllRows_(SHEET_NAMES.INFORMES).forEach((i) => {
    if (mesDeFecha_(i.mes) !== mes) return;
    informePorCurso[String(i.curso_id)] = true;
  });

  const cursosDelNucleo = readRowsWhere_(
    SHEET_NAMES.CURSOS,
    (c) => c.activo === true && nucleos[String(c.nucleo || '').trim()]
  );

  const cursos = cursosDelNucleo.map((curso) => {
    const registradas = clasesPorCurso[String(curso.id)] || 0;
    return {
      curso_id: curso.id,
      curso: curso.nombre,
      docente_id: curso.docente_id,
      docente: nombrePorId[String(curso.docente_id)] || `id ${curso.docente_id}`,
      es_propio: String(curso.docente_id) === String(sesion.id),
      registradas: registradas,
      esperadas: CLASES_ESPERADAS_POR_MES,
      // "al día" con el mínimo que de verdad bloquea entregar el informe —
      // mismo criterio que obtener_estado_mes, no las 4 esperadas.
      planeaciones_al_dia: registradas >= CLASES_MINIMAS_POR_MES,
      informe_entregado: !!informePorCurso[String(curso.id)],
    };
  });

  return {
    nucleo: nombresNucleo.join(', '),
    mes: mes,
    cursos: cursos,
  };
}

/**
 * Resumen del mes para el propio usuario — los números del menú principal
 * (planeaciones registradas/pendientes, horas ejecutadas, cursos activos,
 * informes pendientes). Un solo viaje en vez de que el cliente arme la
 * cuenta pidiendo cursos, planeaciones e informes por separado.
 *
 * Mismo criterio que obtener_estado_mes para "pendientes": lo que bloquea
 * entregar el informe es el mínimo (3), no las 4 esperadas.
 */
function obtener_resumen_docente(token, mes) {
  const sesion = requireSession_(token);

  const misCursos = readRowsWhere_(
    SHEET_NAMES.CURSOS,
    (c) => String(c.docente_id) === String(sesion.id) && c.activo === true
  );
  const idsPropios = {};
  misCursos.forEach((c) => { idsPropios[String(c.id)] = true; });

  const planeacionesDelMes = readRowsWhere_(
    SHEET_NAMES.PLANEACIONES,
    (p) => idsPropios[String(p.curso_id)] && mesDeFecha_(p.fecha) === mes
  );
  const registradasPorCurso = {};
  planeacionesDelMes.forEach((p) => {
    const clave = String(p.curso_id);
    registradasPorCurso[clave] = (registradasPorCurso[clave] || 0) + 1;
  });

  let planeacionesPendientes = 0;
  misCursos.forEach((c) => {
    const registradas = registradasPorCurso[String(c.id)] || 0;
    planeacionesPendientes += Math.max(0, CLASES_MINIMAS_POR_MES - registradas);
  });

  const horasPlaneaciones = planeacionesDelMes.reduce((sum, p) => sum + (Number(p.horas) || 0), 0);
  const actividadesDelMes = readRowsWhere_(
    SHEET_NAMES.ACTIVIDADES,
    (a) => idsPropios[String(a.curso_id)] && mesDeFecha_(a.fecha) === mes
  );
  const horasActividades = actividadesDelMes.reduce(
    (sum, a) => sum + (Number(a.horas_sede) || 0) + (Number(a.horas_externas) || 0), 0
  );

  const informesDelMes = {};
  readAllRows_(SHEET_NAMES.INFORMES).forEach((i) => {
    if (mesDeFecha_(i.mes) !== mes) return;
    if (idsPropios[String(i.curso_id)]) informesDelMes[String(i.curso_id)] = true;
  });
  const informesPendientes = misCursos.filter((c) => !informesDelMes[String(c.id)]).length;

  return {
    mes: mes,
    planeaciones_registradas: planeacionesDelMes.length,
    planeaciones_pendientes: planeacionesPendientes,
    horas_ejecutadas: horasPlaneaciones + horasActividades,
    cursos_activos: misCursos.length,
    informes_pendientes: informesPendientes,
  };
}
