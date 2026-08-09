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

/**
 * Fecha + hora normalizada. Los timestamps también sufren la conversión de
 * Sheets, así que vuelven como Date igual que las fechas sueltas.
 *
 * Se guarda y se lee en hora de Bogotá, sin zona en el string: si
 * guardáramos UTC, el caso "Sheets no convirtió" mostraría cinco horas de
 * más y el caso "sí convirtió" no, para el mismo dato.
 */
function fechaHoraISO_(valor) {
  if (!valor) return '';
  if (valor instanceof Date) {
    return Utilities.formatDate(valor, ZONA_HORARIA_, "yyyy-MM-dd'T'HH:mm:ss");
  }
  return String(valor);
}

function ahoraISO_() {
  return Utilities.formatDate(new Date(), ZONA_HORARIA_, "yyyy-MM-dd'T'HH:mm:ss");
}

function mesDeFecha_(valor) {
  return fechaISO_(valor).slice(0, 7);
}

function diaDeFecha_(valor) {
  return Number(fechaISO_(valor).slice(8, 10));
}
