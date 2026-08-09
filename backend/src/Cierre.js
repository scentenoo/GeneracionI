/**
 * Cierre del mes.
 *
 * Pasada la fecha de corte, el docente ya no puede tocar lo del mes
 * anterior: ni cargar, ni editar, ni borrar planeaciones, ni volver a
 * entregar el informe. La razón es que con eso el equipo directivo ya
 * armó la cuenta de cobro, y que cambie después deja el pago y el
 * documento diciendo cosas distintas.
 *
 * El corte es un día del mes siguiente, que fijan los directivos: con
 * dia_de_corte = 5, todo lo de agosto se cierra el 5 de septiembre.
 *
 * No es una pared: un directivo puede volver a abrir un curso y un mes
 * puntuales cuando haga falta, y cerrarlos de nuevo. Los directivos nunca
 * quedan bloqueados — son quienes tienen que poder arreglar las cosas.
 */

const DIA_DE_CORTE_POR_DEFECTO_ = 5;

function diaDeCorte_() {
  const guardado = Number(leerConfig_('dia_de_corte'));
  if (!Number.isFinite(guardado) || guardado < 1 || guardado > 28) {
    return DIA_DE_CORTE_POR_DEFECTO_;
  }
  return Math.floor(guardado);
}

/** El día en que se cierra ese mes: 'YYYY-MM' -> 'YYYY-MM-DD'. */
function fechaDeCierre_(mes) {
  const partes = String(mes).split('-');
  const anio = Number(partes[0]);
  const numeroDeMes = Number(partes[1]); // 1..12
  // new Date(anio, numeroDeMes, dia) ya apunta al mes siguiente, porque el
  // constructor cuenta los meses desde 0.
  const cierre = new Date(anio, numeroDeMes, diaDeCorte_());
  return Utilities.formatDate(cierre, ZONA_HORARIA_, 'yyyy-MM-dd');
}

function reaperturaDe_(curso_id, mes) {
  return readAllRows_(SHEET_NAMES.REAPERTURAS).find(
    (r) => String(r.curso_id) === String(curso_id) && mesDeFecha_(r.mes) === mes
  ) || null;
}

function mesCerrado_(curso_id, mes) {
  const reapertura = reaperturaDe_(curso_id, mes);
  if (reapertura && reapertura.abierta === true) return false;
  return fechaISO_(new Date()) >= fechaDeCierre_(mes);
}

/**
 * Lanza si el mes está cerrado para quien pide. Lo llaman las funciones
 * que escriben sobre un mes: guardar/editar/eliminar planeación e
 * informe mensual.
 */
function requireMesAbierto_(sesion, curso_id, mes) {
  if (esDirectivo_(sesion)) return;
  if (!mesCerrado_(curso_id, mes)) return;
  throw new Error(
    `El mes ${mes} ya está cerrado (cerró el ${fechaCorta_(fechaDeCierre_(mes))}). ` +
    'Pedile al equipo directivo que lo vuelva a abrir si necesitás cambiar algo.'
  );
}

/**
 * Devuelve una función (curso_id, mes) -> bloqueado, que ya tiene leídas
 * las reaperturas. Para listas: llamar a mesCerrado_ por fila reeliría la
 * pestaña entera una vez por planeación.
 */
function calculadorDeCierre_(sesion) {
  if (esDirectivo_(sesion)) return function () { return false; };

  const abiertas = {};
  readAllRows_(SHEET_NAMES.REAPERTURAS).forEach((r) => {
    if (r.abierta === true) abiertas[`${r.curso_id}|${mesDeFecha_(r.mes)}`] = true;
  });
  const hoy = fechaISO_(new Date());

  return function (curso_id, mes) {
    if (abiertas[`${curso_id}|${mes}`]) return false;
    return hoy >= fechaDeCierre_(mes);
  };
}

/** Para que el cliente sepa si mostrar los botones de editar y borrar. */
function estado_cierre(token, curso_id, mes) {
  const sesion = requireSession_(token);
  const reapertura = reaperturaDe_(curso_id, mes);
  const cerrado = mesCerrado_(curso_id, mes);
  return {
    mes: mes,
    curso_id: curso_id,
    cerrado: cerrado,
    // Un directivo puede editar igual, así que para él nunca está trabado.
    bloqueado: cerrado && !esDirectivo_(sesion),
    reabierto: !!(reapertura && reapertura.abierta === true),
    dia_de_corte: diaDeCorte_(),
    fecha_cierre: fechaDeCierre_(mes),
  };
}

function fijar_dia_de_corte(token, dia) {
  const sesion = requireSession_(token);
  requireRole_(sesion, [ROLES.DIRECTIVO, ROLES.AMBOS]);

  const n = Number(dia);
  if (!Number.isFinite(n) || n < 1 || n > 28) {
    // Más allá del 28 no existe en febrero, y un corte que algunos meses
    // no llega nunca es peor que uno temprano.
    throw new Error('El día de corte tiene que estar entre 1 y 28');
  }

  escribirConfig_('dia_de_corte', String(Math.floor(n)));
  return { ok: true, dia_de_corte: Math.floor(n) };
}

/** Vuelve a abrir (o cierra de nuevo) un curso y un mes puntuales. */
function reabrir_mes(token, curso_id, mes, abierta) {
  const sesion = requireSession_(token);
  requireRole_(sesion, [ROLES.DIRECTIVO, ROLES.AMBOS]);

  if (!findRowById_(SHEET_NAMES.CURSOS, curso_id)) throw new Error('Curso no encontrado');
  if (!/^\d{4}-\d{2}$/.test(String(mes))) throw new Error('El mes va como AAAA-MM');

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const existente = reaperturaDe_(curso_id, mes);
    if (existente) {
      updateRowById_(SHEET_NAMES.REAPERTURAS, existente.id, {
        abierta: abierta === true,
        abierto_por: sesion.usuario,
        actualizado_en: ahoraISO_(),
      });
    } else {
      appendRow_(SHEET_NAMES.REAPERTURAS, {
        curso_id: curso_id,
        // Se guarda con día para que Sheets no lo reinterprete raro; igual
        // se lee siempre con mesDeFecha_.
        mes: mes,
        abierta: abierta === true,
        abierto_por: sesion.usuario,
        actualizado_en: ahoraISO_(),
      });
    }
    return { ok: true, abierta: abierta === true };
  } finally {
    lock.releaseLock();
  }
}
