/**
 * Flujo de revisión de planeaciones e informes (pedido del piloto).
 *
 * Cada planeación e informe tiene un estado: pendiente, aprobado o
 * devuelto. Mariangel (cursos verdes) y Lorena (cursos morados) revisan lo
 * de SUS cursos —según el color del curso, ver Config revisor_verde /
 * revisor_morado— y pueden aprobar o devolver con un motivo. El
 * administrador puede revisar cualquiera.
 *
 * Cada acción queda en la hoja Revisiones (entregado, devuelto, reenviado,
 * aprobado, con quién y cuándo). Ese historial se imprime al final del
 * documento devuelto, como la hoja de auditoría del programa.
 *
 * Al guardar o corregir una planeación/informe, el estado vuelve a
 * "pendiente" y se registra la entrega (o el reenvío, si venía devuelto).
 */

const ESTADO_PENDIENTE = 'pendiente';
const ESTADO_APROBADO = 'aprobado';
const ESTADO_DEVUELTO = 'devuelto';

/**
 * Fija quién revisa cada color. Solo el administrador. Guarda los ids en
 * Config, así reasignar (si Mariangel o Lorena cambian) es cambiar esto y
 * no todos los cursos.
 */
function fijar_revisores(token, revisor_verde_id, revisor_morado_id) {
  const sesion = requireSession_(token);
  requireAdministrador_(sesion);
  if (revisor_verde_id) escribirConfig_('revisor_verde', String(revisor_verde_id));
  if (revisor_morado_id) escribirConfig_('revisor_morado', String(revisor_morado_id));
  return {
    ok: true,
    revisor_verde: leerConfig_('revisor_verde'),
    revisor_morado: leerConfig_('revisor_morado'),
  };
}

/** El id del directivo que revisa un curso, según su color. Null si no hay. */
function revisorDeCurso_(curso) {
  const color = String((curso && curso.color) || '').toLowerCase();
  if (!color) return null;
  const id = leerConfig_('revisor_' + color);
  return id ? Number(id) : null;
}

/** El administrador revisa cualquiera; si no, solo el revisor asignado por color. */
function puedeRevisarCurso_(sesion, curso) {
  if (esAdministrador_(sesion.id)) return true;
  const revisor = revisorDeCurso_(curso);
  return revisor !== null && String(revisor) === String(sesion.id);
}

function registrarRevision_(tipo, ref, accion, motivo, autor) {
  appendRow_(SHEET_NAMES.REVISIONES, {
    tipo: tipo,
    ref: String(ref),
    accion: accion,
    motivo: motivo || '',
    autor: autor || '',
    fecha: ahoraISO_(),
  });
}

/**
 * Marca un documento como entregado (estado pendiente) y registra la
 * acción. Si venía devuelto, la acción es "reenviado". Lo llaman guardar y
 * editar de planeación e informe.
 */
function registrarEntrega_(tipo, ref, sheetName, filaId, autor) {
  const previo = findRowById_(sheetName, filaId);
  const eraDevuelto = previo && previo.estado === ESTADO_DEVUELTO;
  updateRowById_(sheetName, filaId, {
    estado: ESTADO_PENDIENTE,
    revisado_por: '',
    revisado_en: '',
    motivo_devolucion: '',
  });
  registrarRevision_(tipo, ref, eraDevuelto ? 'reenviado' : 'entregado', '', autor);
}

/** El historial completo de un documento, ordenado del más viejo al más nuevo. */
function historialDe_(tipo, ref) {
  return readRowsWhere_(
    SHEET_NAMES.REVISIONES,
    (r) => r.tipo === tipo && String(r.ref) === String(ref)
  )
    .map((r) => ({
      accion: r.accion,
      motivo: r.motivo || '',
      autor: r.autor || '',
      fecha: fechaHoraISO_(r.fecha),
    }))
    .sort((a, b) => (a.fecha < b.fecha ? -1 : a.fecha > b.fecha ? 1 : 0));
}

/** Para el cliente: el historial de una planeación o informe (para el docx). */
function historial_revision(token, tipo, ref) {
  requireSession_(token);
  return historialDe_(tipo, ref);
}

// --- Aprobar / devolver -------------------------------------------------

function revisar_planeacion(token, id, aprobar, motivo) {
  const sesion = requireSession_(token);
  const fila = findRowById_(SHEET_NAMES.PLANEACIONES, id);
  if (!fila) throw new Error('No se encontró la planeación');
  const curso = findRowById_(SHEET_NAMES.CURSOS, fila.curso_id);
  if (!puedeRevisarCurso_(sesion, curso)) {
    throw new Error('No te toca revisar ese curso');
  }
  if (!aprobar && !String(motivo || '').trim()) {
    throw new Error('Escribí el motivo de la devolución para que el docente sepa qué corregir');
  }

  updateRowById_(SHEET_NAMES.PLANEACIONES, id, {
    estado: aprobar ? ESTADO_APROBADO : ESTADO_DEVUELTO,
    revisado_por: sesion.nombre,
    revisado_en: ahoraISO_(),
    motivo_devolucion: aprobar ? '' : String(motivo).trim(),
  });
  registrarRevision_('planeacion', id, aprobar ? 'aprobado' : 'devuelto',
    aprobar ? '' : String(motivo).trim(), sesion.nombre);
  return { ok: true, estado: aprobar ? ESTADO_APROBADO : ESTADO_DEVUELTO };
}

function revisar_informe(token, curso_id, mes, aprobar, motivo) {
  const sesion = requireSession_(token);
  const informe = buscarInforme_(curso_id, mes);
  if (!informe) throw new Error('No se encontró el informe');

  // Un informe de gestión (curso sintético) no tiene color: lo revisa el
  // administrador. Los demás, el revisor del curso.
  if (esClaveGestion_(curso_id)) {
    requireAdministrador_(sesion);
  } else {
    const curso = findRowById_(SHEET_NAMES.CURSOS, curso_id);
    if (!puedeRevisarCurso_(sesion, curso)) throw new Error('No te toca revisar ese curso');
  }
  if (!aprobar && !String(motivo || '').trim()) {
    throw new Error('Escribí el motivo de la devolución para que el docente sepa qué corregir');
  }

  updateRowById_(SHEET_NAMES.INFORMES, informe.id, {
    estado: aprobar ? ESTADO_APROBADO : ESTADO_DEVUELTO,
    revisado_por: sesion.nombre,
    revisado_en: ahoraISO_(),
    motivo_devolucion: aprobar ? '' : String(motivo).trim(),
  });
  registrarRevision_('informe', `${curso_id}|${mes}`, aprobar ? 'aprobado' : 'devuelto',
    aprobar ? '' : String(motivo).trim(), sesion.nombre);
  return { ok: true, estado: aprobar ? ESTADO_APROBADO : ESTADO_DEVUELTO };
}

// --- Listas -------------------------------------------------------------

/**
 * Lo que le toca revisar al directivo este mes: planeaciones e informes
 * pendientes de los cursos de su color (el administrador ve todos).
 */
function pendientes_de_revision(token, mes) {
  const sesion = requireSession_(token);
  requireRole_(sesion, [ROLES.DIRECTIVO, ROLES.AMBOS]);

  const nombrePorId = {};
  readAllRows_(SHEET_NAMES.USUARIOS).forEach((u) => { nombrePorId[String(u.id)] = u.nombre; });

  const misCursos = readRowsWhere_(SHEET_NAMES.CURSOS,
    (c) => c.activo === true && puedeRevisarCurso_(sesion, c));
  const idsCurso = {};
  misCursos.forEach((c) => { idsCurso[String(c.id)] = c; });

  const planeaciones = readRowsWhere_(
    SHEET_NAMES.PLANEACIONES,
    (p) => idsCurso[String(p.curso_id)] && mesDeFecha_(p.fecha) === mes && p.estado === ESTADO_PENDIENTE
  ).map((p) => ({
    id: p.id,
    curso: idsCurso[String(p.curso_id)].nombre,
    docente: nombrePorId[String(p.docente_id)] || '',
    fecha: fechaISO_(p.fecha),
    objetivo: p.objetivo,
    doc_drive_id: p.doc_drive_id || '',
  }));

  const informes = readRowsWhere_(
    SHEET_NAMES.INFORMES,
    (i) => idsCurso[String(i.curso_id)] && mesDeFecha_(i.mes) === mes && i.estado === ESTADO_PENDIENTE
  ).map((i) => ({
    curso_id: i.curso_id,
    mes: mes,
    curso: idsCurso[String(i.curso_id)].nombre,
    docente: nombrePorId[String(i.docente_id)] || '',
  }));

  return { planeaciones: planeaciones, informes: informes };
}

/**
 * Las devoluciones del propio docente, para avisarle al entrar a la app:
 * qué le devolvieron y con qué motivo.
 */
function mis_devoluciones(token) {
  const sesion = requireSession_(token);

  const planeaciones = readRowsWhere_(
    SHEET_NAMES.PLANEACIONES,
    (p) => String(p.docente_id) === String(sesion.id) && p.estado === ESTADO_DEVUELTO
  ).map((p) => ({
    tipo: 'planeacion',
    id: p.id,
    curso: p.grupo,
    fecha: fechaISO_(p.fecha),
    motivo: p.motivo_devolucion || '',
    por: p.revisado_por || '',
  }));

  const informes = readRowsWhere_(
    SHEET_NAMES.INFORMES,
    (i) => String(i.docente_id) === String(sesion.id) && i.estado === ESTADO_DEVUELTO
  ).map((i) => ({
    tipo: 'informe',
    curso_id: i.curso_id,
    mes: mesDeFecha_(i.mes),
    motivo: i.motivo_devolucion || '',
    por: i.revisado_por || '',
  }));

  return planeaciones.concat(informes);
}
