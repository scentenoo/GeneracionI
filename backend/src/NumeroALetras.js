/** Conversión de pesos colombianos a letras, para "VALOR EN LETRAS" de la cuenta de cobro. */

const UNIDADES_ = ['', 'un', 'dos', 'tres', 'cuatro', 'cinco', 'seis', 'siete', 'ocho', 'nueve'];
const DECENAS_ = ['diez', 'once', 'doce', 'trece', 'catorce', 'quince', 'dieciséis', 'diecisiete', 'dieciocho', 'diecinueve'];
const DECENAS_2_ = ['', '', 'veinte', 'treinta', 'cuarenta', 'cincuenta', 'sesenta', 'setenta', 'ochenta', 'noventa'];
const CENTENAS_ = ['', 'ciento', 'doscientos', 'trescientos', 'cuatrocientos', 'quinientos', 'seiscientos', 'setecientos', 'ochocientos', 'novecientos'];

function tresDigitosALetras_(n) {
  if (n === 0) return '';
  if (n === 100) return 'cien';

  const c = Math.floor(n / 100);
  const resto = n % 100;
  let texto = CENTENAS_[c];

  if (resto === 0) return texto;

  let restoTexto;
  if (resto < 10) {
    restoTexto = UNIDADES_[resto];
  } else if (resto < 20) {
    restoTexto = DECENAS_[resto - 10];
  } else {
    const d = Math.floor(resto / 10);
    const u = resto % 10;
    restoTexto = DECENAS_2_[d] + (u ? ` y ${UNIDADES_[u]}` : '');
  }
  return (texto ? texto + ' ' : '') + restoTexto;
}

function numeroALetras_(numero) {
  numero = Math.round(numero);
  if (numero === 0) return 'cero pesos';

  const millones = Math.floor(numero / 1000000);
  const miles = Math.floor((numero % 1000000) / 1000);
  const resto = numero % 1000;

  const partes = [];
  if (millones > 0) {
    partes.push(millones === 1 ? 'un millón' : `${tresDigitosALetras_(millones)} millones`);
  }
  if (miles > 0) {
    partes.push(miles === 1 ? 'mil' : `${tresDigitosALetras_(miles)} mil`);
  }
  if (resto > 0) {
    partes.push(tresDigitosALetras_(resto));
  }

  const texto = partes.join(' ').trim();
  return `${texto.charAt(0).toUpperCase()}${texto.slice(1)} pesos`;
}
