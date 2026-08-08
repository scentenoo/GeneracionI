/** Reglas de validación de la sección 6 de la spec. */

const MIN_PALABRAS_DETALLE = 20;
const CLASES_ESPERADAS_POR_MES = 4;

/** Cada clase tiene que sumar al menos 2 horas repartidas entre sus bloques. */
const MINUTOS_MINIMOS_CLASE = 120;

function contarPalabras_(texto) {
  return String(texto || '')
    .trim()
    .split(/\s+/)
    .filter(Boolean).length;
}

function requireMinPalabras_(texto, nombreCampo) {
  const n = contarPalabras_(texto);
  if (n < MIN_PALABRAS_DETALLE) {
    throw new Error(
      `"${nombreCampo}" necesita mínimo ${MIN_PALABRAS_DETALLE} palabras (tiene ${n})`
    );
  }
}

function sumarMinutosBloques_(bloques) {
  return (bloques || []).reduce((suma, b) => suma + (Number(b.minutos) || 0), 0);
}

/**
 * `esDirectivo` afecta una sola regla: solo un directivo puede guardar una
 * planeación sin ningún estudiante presente.
 *
 * Los temas vistos son una lista de viñetas, no un texto de detalle, así
 * que no llevan el mínimo de 20 palabras — basta con que haya uno.
 */
function validarPlaneacion_(datos, fotos, esDirectivo) {
  if (!datos.fecha) throw new Error('Falta la fecha');
  if (!datos.curso_id) throw new Error('Falta elegir el curso');

  requireMinPalabras_(datos.objetivo, 'Objetivo');

  const temas = (datos.temas_vistos || []).filter((t) => String(t).trim());
  if (temas.length === 0) throw new Error('Agregá al menos un tema visto');

  if (!Array.isArray(datos.bloques) || datos.bloques.length === 0) {
    throw new Error('La planeación necesita al menos un bloque/momento de clase');
  }
  datos.bloques.forEach((b, i) => {
    if (!b.momento) throw new Error(`Bloque ${i + 1}: falta el momento`);
    if (!Number(b.minutos)) throw new Error(`Bloque ${i + 1}: falta cuántos minutos duró`);
    requireMinPalabras_(b.observacion, `Bloque ${i + 1} - observación pedagógica`);
    requireMinPalabras_(b.avance, `Bloque ${i + 1} - avances/retrocesos`);
  });

  const minutos = sumarMinutosBloques_(datos.bloques);
  if (minutos < MINUTOS_MINIMOS_CLASE) {
    throw new Error(
      `Los bloques suman ${minutos} minutos y la clase necesita al menos ${MINUTOS_MINIMOS_CLASE} (2 horas)`
    );
  }

  const presentes = (datos.asistencia || []).filter((a) => a.presente).length;
  if (presentes === 0 && !esDirectivo) {
    throw new Error('No podés guardar una clase sin ningún estudiante presente');
  }

  if (!fotos || !fotos.foto_clase) {
    throw new Error('Falta la foto de la clase');
  }
}
