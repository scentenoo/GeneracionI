/**
 * Google Sheets autoconvierte celdas con forma de fecha a su propio tipo
 * Date — así que un valor guardado como 'YYYY-MM-DD' vuelve de
 * readAllRows_ como objeto Date real, no como string. Estos helpers
 * normalizan cualquiera de los dos antes de compararlos/formatearlos, para
 * no repetir ese `instanceof Date` en cada lugar que toca una fecha.
 */

const ZONA_HORARIA_ = 'America/Bogota';

function fechaISO_(valor) {
  if (valor instanceof Date) {
    return Utilities.formatDate(valor, ZONA_HORARIA_, 'yyyy-MM-dd');
  }
  return String(valor).slice(0, 10);
}

function fechaCorta_(valor) {
  if (valor instanceof Date) {
    return Utilities.formatDate(valor, ZONA_HORARIA_, 'dd/MM/yyyy');
  }
  const [yyyy, mm, dd] = String(valor).slice(0, 10).split('-');
  return `${dd}/${mm}/${yyyy}`;
}

function mesDeFecha_(valor) {
  return fechaISO_(valor).slice(0, 7);
}

function diaDeFecha_(valor) {
  return Number(fechaISO_(valor).slice(8, 10));
}
