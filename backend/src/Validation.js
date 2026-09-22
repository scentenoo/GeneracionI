/** Reglas de validación de la sección 6 de la spec. */

const MIN_PALABRAS_DETALLE = 20;
// Las seis preguntas narrativas del informe mensual (2.1 a 2.6): piden más
// desarrollo que un campo de detalle común.
const MIN_PALABRAS_NARRATIVA_INFORME = 80;
const MIN_LARGO_PASSWORD = 6;
// Lo normal es dar 4 clases al mes (una por semana); ESPERADAS es ese
// número, el que se muestra ("3 de 4"). MINIMAS es lo que de verdad
// bloquea entregar el informe — con 3 ya alcanza, para no dejar a nadie
// sin poder entregar por una sola clase de menos (un feriado, un permiso),
// aunque igual conviene que la persona revise si le falta cargar una.
const CLASES_ESPERADAS_POR_MES = 4;
const CLASES_MINIMAS_POR_MES = 3;
const MIN_FOTOS_CLASE = 1;
const MAX_FOTOS_CLASE = 3;

/** Cada clase tiene que sumar al menos 2 horas repartidas entre sus momentos. */
const MINUTOS_MINIMOS_CLASE = 120;

/** Meta de horas de gestión externa (fuera de sede) que se espera por directivo al mes. */
const HORAS_OBJETIVO_MENSUAL = 8;

// Mínimo de palabras por momento del Diario Pedagógico (formato del
// programa): el inicio se describe corto, el desarrollo es el grueso de la
// clase, el cierre otra vez más breve.
const MIN_PALABRAS_MOMENTO = { inicial: 80, desarrollo: 100, final: 70 };

function contarPalabras_(texto) {
  return String(texto || '')
    .trim()
    .split(/\s+/)
    .filter(Boolean).length;
}

function requireMinPalabras_(texto, nombreCampo, minimo) {
  const min = minimo || MIN_PALABRAS_DETALLE;
  const n = contarPalabras_(texto);
  if (n < min) {
    throw new Error(`"${nombreCampo}" necesita mínimo ${min} palabras (tiene ${n})`);
  }
}

function requireLargoPassword_(password) {
  if (String(password || '').length < MIN_LARGO_PASSWORD) {
    throw new Error(`La contraseña necesita al menos ${MIN_LARGO_PASSWORD} caracteres`);
  }
}

function sumarMinutosBloques_(bloques) {
  return (bloques || []).reduce((suma, b) => suma + (Number(b.minutos) || 0), 0);
}

const MOMENTOS_PLANEACION = ['inicial', 'desarrollo', 'final'];
const NOMBRE_MOMENTO = { inicial: 'Momento inicial', desarrollo: 'Momento de desarrollo', final: 'Momento de cierre' };

function sumarMinutosMomentos_(momentos) {
  return MOMENTOS_PLANEACION.reduce(
    (suma, clave) => suma + (Number((momentos || {})[clave] && momentos[clave].minutos) || 0), 0
  );
}

/**
 * Formato "Diario Pedagógico" del programa (PC-PA-003-F03). La clase se
 * describe en tres momentos —inicial, desarrollo y final— cada uno con su
 * texto y sus minutos, y con un mínimo de palabras distinto (el desarrollo
 * es el grueso). La evaluación de la clase (observaciones) es de TODA la
 * clase, una sola vez, no por momento.
 *
 * `esDirectivo` afecta una sola regla: solo un directivo puede guardar una
 * planeación sin ningún estudiante presente. Los temas vistos son una lista
 * de viñetas, así que no llevan mínimo de palabras.
 */
function validarPlaneacion_(datos, fotos, esDirectivo) {
  if (!datos.fecha) throw new Error('Falta la fecha');
  if (!datos.curso_id) throw new Error('Falta elegir el curso');

  requireMinPalabras_(datos.objetivo, 'Objetivo');

  const temas = (datos.temas_vistos || []).filter((t) => String(t).trim());
  if (temas.length === 0) throw new Error('Agregue al menos un tema visto');

  const momentos = datos.momentos || {};
  MOMENTOS_PLANEACION.forEach((clave) => {
    const m = momentos[clave] || {};
    if (!Number(m.minutos)) throw new Error(`${NOMBRE_MOMENTO[clave]}: falta cuántos minutos duró`);
    requireMinPalabras_(m.texto, NOMBRE_MOMENTO[clave], MIN_PALABRAS_MOMENTO[clave]);
  });

  const minutos = sumarMinutosMomentos_(momentos);
  if (minutos < MINUTOS_MINIMOS_CLASE) {
    throw new Error(
      `Los momentos suman ${minutos} minutos y la clase necesita al menos ${MINUTOS_MINIMOS_CLASE} (2 horas)`
    );
  }

  requireMinPalabras_(datos.observaciones, 'Observaciones del desempeño de los estudiantes');

  const presentes = (datos.asistencia || []).filter((a) => a.presente).length;
  if (presentes === 0 && !esDirectivo) {
    throw new Error('No puede guardar una clase sin ningún estudiante presente');
  }

  const cantidadFotos = normalizarFotosClase_(fotos).length;
  if (cantidadFotos < MIN_FOTOS_CLASE) {
    throw new Error('Falta al menos una foto de la clase');
  }
  if (cantidadFotos > MAX_FOTOS_CLASE) {
    throw new Error(`Como máximo ${MAX_FOTOS_CLASE} fotos por clase`);
  }
}

/**
 * Las fotos de una clase viajan como `fotos.fotos_clase` (lista de 1 a 3,
 * clientes desde esta versión) o como `fotos.foto_clase` (una sola, formato
 * viejo — lo siguen mandando las copias de la app que todavía no se
 * actualizaron). Acá se normaliza a una lista siempre, para que el resto
 * del backend no tenga que conocer los dos formatos.
 */
function normalizarFotosClase_(fotos) {
  if (!fotos) return [];
  if (Array.isArray(fotos.fotos_clase)) return fotos.fotos_clase.filter(Boolean);
  if (fotos.foto_clase) return [fotos.foto_clase];
  return [];
}
