/**
 * Informe consolidado de asistencia (spec: pedido de la Secretaría de
 * Educación vía Miguel) — un solo documento con TODOS los cursos del mes,
 * no uno por curso. Para el equipo directivo (directivo, ambos) y el
 * administrador — no para docentes: es información de supervisión de
 * todos los cursos, no solo del propio.
 *
 * La asistencia de cada clase vive en Planeaciones como snapshot
 * {nombre, presente} (ver Planeaciones.js#guardar_planeacion) — no está
 * ligada a estudiante_id, solo al nombre tal como se escribió ese día. Acá
 * se cruza contra el roster real (Inscripciones + Estudiantes) con
 * nombreNormalizado_ para no fallar por mayúsculas/tildes/espacios; lo que
 * ni así matchea no se descarta en silencio, queda listado en
 * `no_identificados` para que quien lo genere lo revise antes de mandar
 * el PDF.
 */

function generar_informe_asistencia(token, mes) {
  const sesion = requireSession_(token);
  requireSupervisor_(sesion);

  const cursos = readAllRows_(SHEET_NAMES.CURSOS);
  const cursoPorId = {};
  cursos.forEach((c) => { cursoPorId[String(c.id)] = c; });

  const usuarioPorId = {};
  readAllRows_(SHEET_NAMES.USUARIOS).forEach((u) => { usuarioPorId[String(u.id)] = u; });

  const fichaPorId = {};
  readAllRows_(SHEET_NAMES.ESTUDIANTES).forEach((e) => { fichaPorId[String(e.id)] = e; });

  const inscripciones = readAllRows_(SHEET_NAMES.INSCRIPCIONES);
  const estudiantesPorCurso = {};
  inscripciones.forEach((i) => {
    const clave = String(i.curso_id);
    const ficha = fichaPorId[String(i.estudiante_id)];
    if (!ficha) return; // ficha borrada, inscripción huérfana
    (estudiantesPorCurso[clave] = estudiantesPorCurso[clave] || []).push({
      id: ficha.id,
      nombre: String(ficha.nombre),
      normalizado: nombreNormalizado_(ficha.nombre),
    });
  });

  const planeacionesDelMes = readRowsWhere_(
    SHEET_NAMES.PLANEACIONES,
    (p) => mesDeFecha_(p.fecha) === mes
  ).map(parsePlaneacionRow_);

  const planeacionesPorCurso = {};
  planeacionesDelMes.forEach((p) => {
    const clave = String(p.curso_id);
    (planeacionesPorCurso[clave] = planeacionesPorCurso[clave] || []).push(p);
  });

  const noIdentificados = [];
  const cursosDelInforme = [];

  Object.keys(planeacionesPorCurso).forEach((cursoId) => {
    const curso = cursoPorId[cursoId];
    if (!curso) return; // curso borrado, planeación huérfana

    const clasesDelMes = planeacionesPorCurso[cursoId]
      .slice()
      .sort((a, b) => (fechaISO_(a.fecha) < fechaISO_(b.fecha) ? -1 : 1));

    const roster = estudiantesPorCurso[cursoId] || [];

    // Por clase: qué normalizados quedaron marcados presente, y cuáles no
    // matchearon a nadie del roster (van a no_identificados).
    const presentesPorClase = clasesDelMes.map((p, i) => {
      const presentesNorm = {};
      (p.asistencia || []).forEach((a) => {
        if (!a.presente) return;
        const norm = nombreNormalizado_(a.nombre);
        presentesNorm[norm] = true;
        if (!roster.some((e) => e.normalizado === norm)) {
          noIdentificados.push({
            curso: curso.nombre,
            nombre: a.nombre,
            fecha: fechaCorta_(p.fecha),
            clase: `Clase ${i + 1}`,
          });
        }
      });
      return presentesNorm;
    });

    const clases = clasesDelMes.map((p, i) => ({
      nro: `Clase ${i + 1}`,
      fecha: fechaCorta_(p.fecha),
    }));

    const estudiantes = roster
      .slice()
      .sort((a, b) => a.nombre.localeCompare(b.nombre, 'es'))
      .map((est) => {
        const marcas = presentesPorClase.map((presentes) => !!presentes[est.normalizado]);
        const totalAsistio = marcas.filter(Boolean).length;
        return {
          nombre: est.nombre,
          marcas: marcas.map((presente) => (presente ? 'Asistió' : 'Faltó')),
          total_asistio: totalAsistio,
          total_falto: clases.length - totalAsistio,
        };
      });

    const totalPosible = estudiantes.length * clases.length;
    const totalAsistidoCurso = estudiantes.reduce((sum, e) => sum + e.total_asistio, 0);
    const porcentaje = totalPosible > 0 ? Math.round((totalAsistidoCurso / totalPosible) * 100) : 0;

    const docente = usuarioPorId[String(curso.docente_id)] || {};
    // Misma asignación que "Revisores por color" (Revisiones.js): el color
    // del curso decide quién es su coordinadora de área. Un curso sin color
    // (o con un color sin nadie asignado todavía) queda sin coordinadora —
    // el documento lo avisa en vez de dejar el espacio de firma sin
    // explicación.
    const revisorId = revisorDeCurso_(curso);
    const coordinadora = revisorId ? (usuarioPorId[String(revisorId)] || {}).nombre || '' : '';
    cursosDelInforme.push({
      nombre: curso.nombre,
      docente: docente.nombre || '',
      coordinadora: coordinadora,
      nucleo: curso.nucleo || '',
      clases: clases,
      estudiantes: estudiantes,
      total_clases: clases.length,
      total_estudiantes: estudiantes.length,
      porcentaje_asistencia: porcentaje,
    });
  });

  cursosDelInforme.sort((a, b) => a.nombre.localeCompare(b.nombre, 'es'));

  // Cursos activos que no aparecieron arriba por no tener ni una clase
  // cargada ese mes — para que se note que falta algo, en vez de que el
  // curso simplemente no salga en el documento sin explicación.
  const cursosConDatos = {};
  Object.keys(planeacionesPorCurso).forEach((id) => { cursosConDatos[id] = true; });
  const cursosSinClases = cursos
    .filter((c) => c.activo === true && !cursosConDatos[String(c.id)])
    .map((c) => ({ nombre: c.nombre, docente: (usuarioPorId[String(c.docente_id)] || {}).nombre || '' }));

  return {
    mes: mes,
    mes_nombre: nombreMes_(mes),
    anio: mes.split('-')[0],
    fecha_emision: Utilities.formatDate(new Date(), 'America/Bogota', 'dd/MM/yyyy'),
    cursos: cursosDelInforme,
    cursos_sin_clases: cursosSinClases,
    no_identificados: noIdentificados,
  };
}

const UMBRAL_ALERTA_INASISTENCIAS = 3;

/**
 * Inasistencias acumuladas por estudiante en cada curso activo —
 * TODAS las clases que el curso haya dictado alguna vez, no de un mes
 * puntual. Mismo nivel de acceso que generar_informe_asistencia (equipo
 * directivo y administrador, no docentes) — es el mismo pedido de
 * Miguel/Secretaría, pero en Excel y acumulado en vez de PDF y mensual.
 *
 * Antes se acotaba desde Inscripciones.creado_en (la fecha en la que se
 * inscribió), pero ese campo resultó no ser confiable: hay clases
 * dictadas antes de que la inscripción quedara registrada en el sistema
 * (datos cargados después, migraciones, etc.), así que "desde que se
 * inscribió" dejaba afuera inasistencias reales y la alerta de más de 3
 * no marcaba a nadie. Ahora cuenta TODAS las clases del curso — más
 * simple y, con los datos que hay, más correcto.
 *
 * Se entrega junto con un segundo bloque, `estudiantes`: cuántos cursos
 * activos tiene cada estudiante del programa (para ver quién está en más
 * de uno) y el total de estudiantes — dato pedido aparte, nada que ver con
 * inasistencias, pero se junta acá para salir todo en el mismo Excel.
 */
function generar_reporte_inasistencias(token) {
  const sesion = requireSession_(token);
  requireSupervisor_(sesion);

  const cursosActivos = readRowsWhere_(SHEET_NAMES.CURSOS, (c) => c.activo === true);
  const cursoPorId = {};
  cursosActivos.forEach((c) => { cursoPorId[String(c.id)] = c; });

  const usuarioPorId = {};
  readAllRows_(SHEET_NAMES.USUARIOS).forEach((u) => { usuarioPorId[String(u.id)] = u; });

  const fichaPorId = {};
  readAllRows_(SHEET_NAMES.ESTUDIANTES).forEach((e) => { fichaPorId[String(e.id)] = e; });

  const inscripciones = readAllRows_(SHEET_NAMES.INSCRIPCIONES);

  const planeacionesPorCurso = {};
  readAllRows_(SHEET_NAMES.PLANEACIONES).map(parsePlaneacionRow_).forEach((p) => {
    const clave = String(p.curso_id);
    (planeacionesPorCurso[clave] = planeacionesPorCurso[clave] || []).push(p);
  });

  // --- bloque 1: inasistencias por curso activo -----------------------
  const cursosDelReporte = [];
  cursosActivos.forEach((curso) => {
    const inscripcionesDelCurso = inscripciones.filter((i) => String(i.curso_id) === String(curso.id));
    if (inscripcionesDelCurso.length === 0) return;

    const clasesDelCurso = (planeacionesPorCurso[String(curso.id)] || [])
      .slice()
      .sort((a, b) => (fechaISO_(a.fecha) < fechaISO_(b.fecha) ? -1 : 1));

    const estudiantes = inscripcionesDelCurso
      .map((insc) => {
        const ficha = fichaPorId[String(insc.estudiante_id)];
        if (!ficha) return null; // ficha borrada, inscripción huérfana

        const normalizado = nombreNormalizado_(ficha.nombre);
        const totalAsistio = clasesDelCurso.filter((p) =>
          (p.asistencia || []).some((a) => a.presente && nombreNormalizado_(a.nombre) === normalizado)
        ).length;
        const totalClases = clasesDelCurso.length;
        const totalFalto = totalClases - totalAsistio;

        return {
          nombre: String(ficha.nombre),
          total_clases: totalClases,
          total_asistio: totalAsistio,
          total_falto: totalFalto,
          alerta: totalFalto > UMBRAL_ALERTA_INASISTENCIAS,
        };
      })
      .filter(Boolean)
      // Primero quien más faltó -- es lo que Miguel necesita ver de
      // entrada, no una lista alfabética que hay que releer entera.
      .sort((a, b) => b.total_falto - a.total_falto || a.nombre.localeCompare(b.nombre, 'es'));

    const docente = usuarioPorId[String(curso.docente_id)] || {};
    cursosDelReporte.push({
      nombre: curso.nombre,
      docente: docente.nombre || '',
      nucleo: curso.nucleo || '',
      estudiantes: estudiantes,
    });
  });
  cursosDelReporte.sort((a, b) => a.nombre.localeCompare(b.nombre, 'es'));

  // --- bloque 2: en cuántos cursos activos está cada estudiante --------
  const cursosPorEstudiante = {};
  inscripciones.forEach((i) => {
    const curso = cursoPorId[String(i.curso_id)];
    if (!curso) return; // curso inactivo o borrado: no cuenta para este bloque
    const clave = String(i.estudiante_id);
    (cursosPorEstudiante[clave] = cursosPorEstudiante[clave] || []).push(curso.nombre);
  });

  const resumenEstudiantes = Object.keys(cursosPorEstudiante)
    .map((estudianteId) => {
      const ficha = fichaPorId[estudianteId];
      if (!ficha) return null;
      const cursosDe = cursosPorEstudiante[estudianteId];
      return {
        nombre: String(ficha.nombre),
        cantidad_cursos: cursosDe.length,
        cursos: cursosDe.slice().sort((a, b) => a.localeCompare(b, 'es')),
      };
    })
    .filter(Boolean)
    .sort((a, b) => b.cantidad_cursos - a.cantidad_cursos || a.nombre.localeCompare(b.nombre, 'es'));

  return {
    fecha_emision: Utilities.formatDate(new Date(), 'America/Bogota', 'dd/MM/yyyy'),
    umbral_alerta: UMBRAL_ALERTA_INASISTENCIAS,
    cursos: cursosDelReporte,
    estudiantes: resumenEstudiantes,
    total_estudiantes: resumenEstudiantes.length,
  };
}
