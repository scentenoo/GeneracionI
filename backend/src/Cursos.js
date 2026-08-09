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

function crear_curso(token, datos) {
  const sesion = requireSession_(token);
  requireRole_(sesion, [ROLES.DIRECTIVO, ROLES.AMBOS]);

  if (!datos.nombre || !datos.docente_id) {
    throw new Error('Faltan datos obligatorios (nombre, docente_id)');
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

  if (String(targetId) !== String(sesion.id) && !esDirectivo_(sesion)) {
    throw new Error('No tienes permiso para ver los cursos de otro docente');
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

const CAMPOS_EDITABLES_CURSO_ = ['nombre', 'nucleo', 'edad_desde', 'edad_hasta', 'docente_id', 'activo'];

function editar_curso(token, curso_id, cambios) {
  const sesion = requireSession_(token);
  requireRole_(sesion, [ROLES.DIRECTIVO, ROLES.AMBOS]);

  const cambiosFiltrados = {};
  Object.keys(cambios).forEach((campo) => {
    if (CAMPOS_EDITABLES_CURSO_.includes(campo)) cambiosFiltrados[campo] = cambios[campo];
  });

  const cambiosReales = updateRowById_(SHEET_NAMES.CURSOS, curso_id, cambiosFiltrados);
  return { ok: true, cambios: cambiosReales.length };
}

/**
 * No borra la fila: la marca inactiva. Las planeaciones ya guardadas
 * apuntan a este curso y tienen que seguir resolviendo su nombre para los
 * informes de meses anteriores.
 */
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
    throw new Error('Ese curso no es tuyo');
  }
  return curso;
}
