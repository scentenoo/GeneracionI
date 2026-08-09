/**
 * Estudiantes de cada curso. Los gestiona el directivo; el docente solo
 * los consulta y marca asistencia sobre ellos.
 *
 * Cuelgan del curso, no del docente: un docente con dos cursos tiene dos
 * listas separadas de estudiantes.
 */

function importar_estudiantes(token, curso_id, csv) {
  const sesion = requireSession_(token);
  requireRole_(sesion, [ROLES.DIRECTIVO, ROLES.AMBOS]);

  if (!findRowById_(SHEET_NAMES.CURSOS, curso_id)) throw new Error('Curso no encontrado');

  const filas = Utilities.parseCsv(csv);
  const encabezado = filas[0].map((h) => h.trim().toLowerCase());
  const idxNombre = encabezado.indexOf('nombre');
  if (idxNombre === -1) throw new Error('El CSV necesita una columna "nombre"');

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const creados = filas.slice(1).filter((fila) => fila[idxNombre]).map((fila) =>
      appendRow_(SHEET_NAMES.ESTUDIANTES, {
        nombre: fila[idxNombre].trim(),
        curso_id: curso_id,
      })
    );


    return { ok: true, creados: creados.length };
  } finally {
    lock.releaseLock();
  }
}

/** El docente solo puede ver los estudiantes de sus propios cursos. */
function obtener_estudiantes(token, curso_id) {
  const sesion = requireSession_(token);
  if (!curso_id) throw new Error('Falta indicar el curso');

  const curso = findRowById_(SHEET_NAMES.CURSOS, curso_id);
  if (!curso) throw new Error('Curso no encontrado');

  if (String(curso.docente_id) !== String(sesion.id) && !esDirectivo_(sesion)) {
    throw new Error('No tienes permiso para ver los estudiantes de ese curso');
  }

  return readRowsWhere_(SHEET_NAMES.ESTUDIANTES, (e) => String(e.curso_id) === String(curso_id));
}

/**
 * cambios = { agregar: [{nombre}], quitar: [id, ...] }
 * Nunca modifica planeaciones ya guardadas (esas tienen su propio snapshot
 * de asistencia) — solo afecta la lista "actual" del curso.
 */
function modificar_grupo(token, curso_id, cambios) {
  const sesion = requireSession_(token);
  requireRole_(sesion, [ROLES.DIRECTIVO, ROLES.AMBOS]);

  if (!findRowById_(SHEET_NAMES.CURSOS, curso_id)) throw new Error('Curso no encontrado');

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const cambiosHechos = [];

    (cambios.agregar || []).forEach((est) => {
      const fila = appendRow_(SHEET_NAMES.ESTUDIANTES, { nombre: est.nombre, curso_id: curso_id });
      cambiosHechos.push({ campo: 'estudiante_agregado', antes: '', despues: `${fila.nombre} (id ${fila.id})` });
    });

    (cambios.quitar || []).forEach((estudianteId) => {
      const est = findRowById_(SHEET_NAMES.ESTUDIANTES, estudianteId);
      if (est) {
        getSheet_(SHEET_NAMES.ESTUDIANTES).deleteRow(est._row);
        cambiosHechos.push({ campo: 'estudiante_quitado', antes: `${est.nombre} (id ${est.id})`, despues: '' });
      }
    });

    return { ok: true, cambios: cambiosHechos.length };
  } finally {
    lock.releaseLock();
  }
}
