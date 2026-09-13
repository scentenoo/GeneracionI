/**
 * Certificado mensual de horas de docencia para pago del operador (spec:
 * "certificado para pago", solo para administradores). Una fila por
 * docente y curso, con el total de horas de ESE curso ese mes — la misma
 * suma que ya usa la cuenta de cobro del informe mensual
 * (Informes.js#generar_informe_mensual: totalHorasDocente): horas de las
 * clases (Planeaciones, siempre "de sede") más horas_sede + horas_externas
 * de Actividades. El certificado en sí solo lleva el total (sede y
 * externas se pagan igual, así que ahí se suman) — el desglose es para la
 * vista previa de la app, así el administrador ve de dónde sale el total
 * antes de descargar.
 *
 * Un curso sin ninguna hora ese mes no aparece en el certificado — no hay
 * nada que certificarle. Lo mismo un curso marcado `excluido_certificado`
 * (editable desde Cursos, solo administrador): sigue activo y anda normal
 * en el resto de la app, pero sus horas nunca entran a ESTE documento —
 * caso real: un docente cuyas horas no se pagan por esta vía. Los dos
 * casos van en `excluidos`, con el motivo, para que la vista previa avise
 * quién no va a salir en el documento antes de descargarlo.
 */
function generar_certificado_pago(token, mes) {
  const sesion = requireSession_(token);
  requireAdministrador_(sesion);

  const usuarioPorId = {};
  readAllRows_(SHEET_NAMES.USUARIOS).forEach((u) => {
    usuarioPorId[String(u.id)] = u;
  });

  // Horas de sede: las clases (Planeaciones, siempre de sede) más
  // horas_sede de Actividades (reuniones, claustros, etc. hechos en sede).
  const horasSedePorCurso = {};
  readAllRows_(SHEET_NAMES.PLANEACIONES).forEach((p) => {
    if (mesDeFecha_(p.fecha) !== mes) return;
    const clave = String(p.curso_id);
    horasSedePorCurso[clave] = (horasSedePorCurso[clave] || 0) + (Number(p.horas) || 0);
  });

  const horasExternasPorCurso = {};
  readAllRows_(SHEET_NAMES.ACTIVIDADES).forEach((a) => {
    if (mesDeFecha_(a.fecha) !== mes) return;
    const clave = String(a.curso_id);
    horasSedePorCurso[clave] = (horasSedePorCurso[clave] || 0) + (Number(a.horas_sede) || 0);
    horasExternasPorCurso[clave] = (horasExternasPorCurso[clave] || 0) + (Number(a.horas_externas) || 0);
  });

  const todas = readRowsWhere_(SHEET_NAMES.CURSOS, (c) => c.activo === true).map((curso) => {
    const clave = String(curso.id);
    const horasSede = horasSedePorCurso[clave] || 0;
    const horasExternas = horasExternasPorCurso[clave] || 0;
    const docente = usuarioPorId[String(curso.docente_id)] || {};
    return {
      docente: docente.nombre || `id ${curso.docente_id}`,
      cedula: docente.cedula || '',
      telefono: docente.telefono || '',
      formacion: docente.formacion || '',
      curso: curso.nombre,
      horas_sede: horasSede,
      horas_externas: horasExternas,
      horas: horasSede + horasExternas,
      excluido: curso.excluido_certificado === true,
    };
  });

  const filas = todas
    .filter((f) => !f.excluido && f.horas > 0)
    .map((f) => ({
      docente: f.docente, cedula: f.cedula, telefono: f.telefono, formacion: f.formacion,
      curso: f.curso, horas_sede: f.horas_sede, horas_externas: f.horas_externas, horas: f.horas,
    }))
    .sort((a, b) => a.docente.localeCompare(b.docente, 'es'));

  const excluidos = todas
    .filter((f) => f.excluido || f.horas === 0)
    .map((f) => ({
      docente: f.docente,
      curso: f.curso,
      motivo: f.excluido ? 'Excluido manualmente del certificado' : 'Sin horas cargadas este mes',
    }))
    .sort((a, b) => a.docente.localeCompare(b.docente, 'es'));

  const totalHoras = filas.reduce((sum, f) => sum + f.horas, 0);

  return {
    mes: mes,
    mes_nombre: nombreMes_(mes).toLowerCase(),
    anio: mes.split('-')[0],
    filas: filas,
    excluidos: excluidos,
    total_horas: totalHoras,
    fecha_emision: Utilities.formatDate(new Date(), 'America/Bogota', 'dd/MM/yyyy'),
  };
}
