/**
 * Estudiantes de cada curso. Los gestiona el directivo; el docente solo
 * los consulta y marca asistencia sobre ellos.
 *
 * Hay UNA ficha por persona (pestaña Estudiantes) y una inscripción por
 * cada curso en el que está (pestaña Inscripciones). Antes el estudiante
 * colgaba de un solo curso, así que a quien va a inglés y a robótica había
 * que escribirlo dos veces — y si la segunda vez se escribía distinto,
 * quedaba como dos personas y sus asistencias no se podían juntar.
 *
 * Al agregar por nombre se busca primero una ficha que ya exista: escribir
 * "Ana Pérez" en un curso donde ya está en otro la reusa, no la duplica.
 */

/** Para comparar nombres escritos por manos distintas y en días distintos. */
function nombreNormalizado_(nombre) {
  return String(nombre || '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * Devuelve la ficha del estudiante con ese nombre, creándola si no existe.
 * `fichas` es el listado ya leído, para no releer la pestaña por cada
 * nombre de un CSV.
 */
function fichaDeEstudiante_(nombre, fichas) {
  const buscado = nombreNormalizado_(nombre);
  const existente = fichas.find((e) => nombreNormalizado_(e.nombre) === buscado);
  if (existente) return existente;

  const fila = appendRow_(SHEET_NAMES.ESTUDIANTES, { nombre: String(nombre).trim() });
  fichas.push(fila);
  return fila;
}

/** Inscribe si no lo estaba ya. Devuelve true si hubo que crearla. */
function inscribir_(estudiante_id, curso_id, inscripciones) {
  const ya = inscripciones.some(
    (i) => String(i.estudiante_id) === String(estudiante_id) &&
           String(i.curso_id) === String(curso_id)
  );
  if (ya) return false;

  const fila = appendRow_(SHEET_NAMES.INSCRIPCIONES, {
    estudiante_id: estudiante_id,
    curso_id: curso_id,
    creado_en: new Date().toISOString(),
  });
  inscripciones.push(fila);
  return true;
}

/**
 * Excel en Windows con configuración regional en español exporta el CSV
 * separado por ; y no por , —la coma es el separador decimal en ese
 * idioma, así que el de columnas pasa a ser el punto y coma—. Sin esto,
 * un CSV real (con esa configuración, que es la de acá) no encontraba la
 * columna "nombre" aunque estuviera, porque toda la fila quedaba como un
 * solo campo sin partir.
 */
function filasCsvConNombre_(csv) {
  for (const separador of [',', ';']) {
    const filas = Utilities.parseCsv(csv, separador);
    const encabezado = (filas[0] || []).map((h) => h.trim().toLowerCase());
    const idxNombre = encabezado.indexOf('nombre');
    if (idxNombre !== -1) return { filas: filas, idxNombre: idxNombre };
  }
  throw new Error('El CSV necesita una columna "nombre"');
}

function importar_estudiantes(token, curso_id, csv) {
  const sesion = requireSession_(token);
  requireRole_(sesion, [ROLES.DIRECTIVO, ROLES.AMBOS]);

  if (!findRowById_(SHEET_NAMES.CURSOS, curso_id)) throw new Error('Curso no encontrado');

  const { filas, idxNombre } = filasCsvConNombre_(csv);

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  invalidarCacheHojas_();
  try {
    const fichas = readAllRows_(SHEET_NAMES.ESTUDIANTES);
    const inscripciones = readAllRows_(SHEET_NAMES.INSCRIPCIONES);

    let nuevos = 0;
    let reusados = 0;
    filas.slice(1).forEach((fila) => {
      if (!fila[idxNombre] || !fila[idxNombre].trim()) return;
      const antes = fichas.length;
      const ficha = fichaDeEstudiante_(fila[idxNombre], fichas);
      if (fichas.length > antes) nuevos++; else reusados++;
      inscribir_(ficha.id, curso_id, inscripciones);
    });

    return { ok: true, creados: nuevos, reusados: reusados };
  } finally {
    lock.releaseLock();
  }
}

/**
 * Los del curso indicado. Cada uno trae `otros_cursos` para que el equipo
 * directivo vea de un vistazo quién está en más de uno antes de sacarlo.
 */
function obtener_estudiantes(token, curso_id) {
  const sesion = requireSession_(token);
  if (!curso_id) throw new Error('Falta indicar el curso');

  const curso = findRowById_(SHEET_NAMES.CURSOS, curso_id);
  if (!curso) throw new Error('Curso no encontrado');

  if (String(curso.docente_id) !== String(sesion.id) && !puedeSupervisar_(sesion)) {
    throw new Error('No tiene permiso para ver los estudiantes de ese curso');
  }

  const inscripciones = readAllRows_(SHEET_NAMES.INSCRIPCIONES);
  const fichas = {};
  readAllRows_(SHEET_NAMES.ESTUDIANTES).forEach((e) => {
    fichas[String(e.id)] = e;
  });

  const cuantosCursos = {};
  inscripciones.forEach((i) => {
    const k = String(i.estudiante_id);
    cuantosCursos[k] = (cuantosCursos[k] || 0) + 1;
  });

  return inscripciones
    .filter((i) => String(i.curso_id) === String(curso_id))
    .map((i) => {
      const ficha = fichas[String(i.estudiante_id)];
      return {
        id: i.estudiante_id,
        nombre: ficha ? String(ficha.nombre) : `(ficha ${i.estudiante_id} borrada)`,
        inscripcion_id: i.id,
        otros_cursos: Math.max(0, (cuantosCursos[String(i.estudiante_id)] || 1) - 1),
      };
    });
}

/**
 * cambios = { agregar: [{nombre}], quitar: [estudiante_id, ...] }
 *
 * Quitar saca al estudiante de ESTE curso, no del programa: si está en
 * otro, su ficha y esa otra inscripción siguen intactas. Nunca toca
 * planeaciones ya guardadas, que llevan su propia copia de la asistencia
 * del día.
 */
function modificar_grupo(token, curso_id, cambios) {
  const sesion = requireSession_(token);
  requireRole_(sesion, [ROLES.DIRECTIVO, ROLES.AMBOS]);

  if (!findRowById_(SHEET_NAMES.CURSOS, curso_id)) throw new Error('Curso no encontrado');

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  invalidarCacheHojas_();
  try {
    let hechos = 0;

    const agregar = (cambios.agregar || []).filter((e) => e && String(e.nombre || '').trim());
    if (agregar.length > 0) {
      const fichas = readAllRows_(SHEET_NAMES.ESTUDIANTES);
      const inscripciones = readAllRows_(SHEET_NAMES.INSCRIPCIONES);
      agregar.forEach((est) => {
        const ficha = fichaDeEstudiante_(est.nombre, fichas);
        if (inscribir_(ficha.id, curso_id, inscripciones)) hechos++;
      });
    }

    (cambios.quitar || []).forEach((estudianteId) => {
      // De derecha a izquierda no hace falta: se borra de a una y se
      // vuelve a buscar, que con grupos de 20 no cuesta nada.
      const inscripcion = readAllRows_(SHEET_NAMES.INSCRIPCIONES).find(
        (i) => String(i.estudiante_id) === String(estudianteId) &&
               String(i.curso_id) === String(curso_id)
      );
      if (inscripcion) {
        eliminarFila_(SHEET_NAMES.INSCRIPCIONES, inscripcion);
        hechos++;
      }
    });

    // Quitar a alguien de un curso borra su inscripción, no su ficha:
    // el que además va a Robótica tiene que seguir existiendo. Pero si no
    // le quedó ninguna, la ficha ya no representa a nadie del programa y
    // sin esto la pestaña Estudiantes solo acumula nombres sueltos que
    // igual aparecen al buscar. Misma regla que al borrar un curso.
    if ((cambios.quitar || []).length > 0) eliminarEstudiantesSinInscripcion_();

    return { ok: true, cambios: hechos };
  } finally {
    lock.releaseLock();
  }
}

/**
 * Fichas que ya existen y coinciden con lo que se escribió, para poder
 * inscribir a alguien en un segundo curso sin volver a tipear su nombre
 * completo y arriesgarse a crear un duplicado.
 */
function buscar_estudiantes(token, texto) {
  const sesion = requireSession_(token);
  requireRole_(sesion, [ROLES.DIRECTIVO, ROLES.AMBOS]);

  const buscado = nombreNormalizado_(texto);
  if (buscado.length < 2) return [];

  const inscripciones = readAllRows_(SHEET_NAMES.INSCRIPCIONES);
  const cursos = {};
  readAllRows_(SHEET_NAMES.CURSOS).forEach((c) => {
    cursos[String(c.id)] = c.nombre;
  });

  return readAllRows_(SHEET_NAMES.ESTUDIANTES)
    .filter((e) => nombreNormalizado_(e.nombre).indexOf(buscado) !== -1)
    .slice(0, 15)
    .map((e) => ({
      id: e.id,
      nombre: String(e.nombre),
      cursos: inscripciones
        .filter((i) => String(i.estudiante_id) === String(e.id))
        .map((i) => cursos[String(i.curso_id)] || `curso ${i.curso_id}`),
    }));
}

/**
 * Borra las fichas de estudiante que ya no están inscritas en ningún
 * curso. Devuelve cuántas.
 *
 * Desde que un estudiante puede estar en varios cursos, borrar un curso
 * borra sus inscripciones pero no a la persona: alguien que además va a
 * Robótica tiene que seguir existiendo. Solo se va el que se queda sin
 * ninguna.
 */
function eliminarEstudiantesSinInscripcion_() {
  const inscritos = {};
  readAllRows_(SHEET_NAMES.INSCRIPCIONES).forEach((i) => {
    inscritos[String(i.estudiante_id)] = true;
  });

  return eliminarFilasDonde_(SHEET_NAMES.ESTUDIANTES, (e) => !inscritos[String(e.id)]);
}
