/** Reglas de validación de la sección 6 de la spec. */

const MIN_PALABRAS_DETALLE = 20;
const MIN_LARGO_PASSWORD = 6;
const CLASES_ESPERADAS_POR_MES = 4;

/** Cada clase tiene que sumar al menos 2 horas repartidas entre sus momentos. */
const MINUTOS_MINIMOS_CLASE = 120;

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
const NOMBRE_MOMENTO = { inicial: 'Momento inicial', desarrollo: 'Momento de desarrollo', final: 'Momento final' };

function sumarMinutosMomentos_(momentos) {
  return MOMENTOS_PLANEACION.reduce(
    (suma, clave) => suma + (Number((momentos || {})[clave] && momentos[clave].minutos) || 0), 0
  );
}

/**
 * Formato "Diario Pedagógico" del programa. La clase se describe en tres
 * momentos —inicial, desarrollo y final— cada uno con su texto y sus
 * minutos, y con un mínimo de palabras distinto (el desarrollo es el
 * grueso). Las dos columnas de al lado —la reflexión pedagógica
 * (observaciones) y los avances/retrocesos— son de TODA la clase, una sola
 * vez, no por momento.
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
  if (temas.length === 0) throw new Error('Agregá al menos un tema visto');

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

  requireMinPalabras_(datos.observaciones, 'Observaciones de clase (reflexión pedagógica)');
  requireMinPalabras_(datos.avances, 'Avances o retrocesos observados');

  const presentes = (datos.asistencia || []).filter((a) => a.presente).length;
  if (presentes === 0 && !esDirectivo) {
    throw new Error('No podés guardar una clase sin ningún estudiante presente');
  }

  if (!fotos || !fotos.foto_clase) {
    throw new Error('Falta la foto de la clase');
  }
}
