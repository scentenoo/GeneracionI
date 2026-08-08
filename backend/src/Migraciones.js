/**
 * Migraciones que hay que correr a mano UNA VEZ desde el editor de Apps
 * Script, después de un `clasp push` que cambie el esquema.
 *
 * Todas son idempotentes: volver a correrlas no duplica ni rompe nada.
 * Corré siempre `setupSheets()` antes, para que existan las columnas nuevas.
 */

/** Borra columnas por nombre, de derecha a izquierda para que no se corran los índices. */
function eliminarColumnas_(sheetName, nombres) {
  const sheet = getSheet_(sheetName);
  if (sheet.getLastColumn() === 0) return [];

  const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  const indices = nombres
    .map((n) => headers.indexOf(n) + 1)
    .filter((i) => i > 0)
    .sort((a, b) => b - a);

  indices.forEach((i) => sheet.deleteColumn(i));
  return indices;
}

/**
 * Mueve curso/nucleo/edades de Usuarios a la pestaña Cursos, y repunta
 * Estudiantes y Planeaciones del docente al curso.
 *
 * Corré primero setupSheets() para que existan Cursos y las columnas
 * curso_id.
 */
function migrarACursos() {
  const lock = LockService.getScriptLock();
  lock.waitLock(60000);
  try {
    const usuarios = readAllRows_(SHEET_NAMES.USUARIOS);
    const cursosExistentes = readAllRows_(SHEET_NAMES.CURSOS);

    // 1. Un curso por cada usuario que traía el campo `curso` lleno y todavía no tiene ninguno.
    const cursoPorDocente = {};
    cursosExistentes.forEach((c) => {
      cursoPorDocente[String(c.docente_id)] = c.id;
    });

    usuarios.forEach((u) => {
      if (cursoPorDocente[String(u.id)]) return;
      if (!u.curso) return;

      const fila = appendRow_(SHEET_NAMES.CURSOS, {
        docente_id: u.id,
        nombre: u.curso,
        nucleo: u.nucleo || '',
        edad_desde: u.edad_desde || '',
        edad_hasta: u.edad_hasta || '',
        activo: true,
      });
      cursoPorDocente[String(u.id)] = fila.id;
      Logger.log('Curso creado para %s: %s (id %s)', u.nombre, u.curso, fila.id);
    });

    // 2. Estudiantes: del docente al curso.
    const estudiantes = readAllRows_(SHEET_NAMES.ESTUDIANTES);
    let estudiantesMigrados = 0;
    estudiantes.forEach((e) => {
      if (e.curso_id) return;
      const cursoId = cursoPorDocente[String(e.docente_id)];
      if (!cursoId) {
        Logger.log('OJO: el estudiante %s (id %s) quedó sin curso — su docente no tenía ninguno', e.nombre, e.id);
        return;
      }
      updateRowById_(SHEET_NAMES.ESTUDIANTES, e.id, { curso_id: cursoId });
      estudiantesMigrados++;
    });

    // 3. Planeaciones: idem, usando el curso del docente.
    const planeaciones = readAllRows_(SHEET_NAMES.PLANEACIONES);
    let planeacionesMigradas = 0;
    planeaciones.forEach((p) => {
      if (p.curso_id) return;
      const cursoId = cursoPorDocente[String(p.docente_id)];
      if (!cursoId) {
        Logger.log('OJO: la planeación %s quedó sin curso', p.id);
        return;
      }
      updateRowById_(SHEET_NAMES.PLANEACIONES, p.id, { curso_id: cursoId });
      planeacionesMigradas++;
    });

    Logger.log(
      'Migración lista. Cursos: %s · estudiantes repuntados: %s · planeaciones repuntadas: %s',
      Object.keys(cursoPorDocente).length, estudiantesMigrados, planeacionesMigradas
    );
    Logger.log('Si todo se ve bien en la Sheet, corré limpiarColumnasViejas() para borrar las columnas que quedaron sin uso.');
  } finally {
    lock.releaseLock();
  }
}

/**
 * Segundo paso, aparte a propósito: borra las columnas que migrarACursos()
 * dejó sin uso. Se corre solo cuando ya verificaste que los datos quedaron
 * bien, porque esto sí es destructivo.
 */
function limpiarColumnasViejas() {
  const borradasUsuarios = eliminarColumnas_(SHEET_NAMES.USUARIOS, [
    'curso', 'nucleo', 'edad_desde', 'edad_hasta',
  ]);
  const borradasEstudiantes = eliminarColumnas_(SHEET_NAMES.ESTUDIANTES, ['docente_id']);

  Logger.log(
    'Columnas borradas — Usuarios: %s · Estudiantes: %s',
    borradasUsuarios.length, borradasEstudiantes.length
  );
}
