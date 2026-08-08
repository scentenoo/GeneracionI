/** Reglas de validación de la sección 6 de la spec. */

const MIN_PALABRAS_DETALLE = 20;
const CLASES_ESPERADAS_POR_MES = 4; // 4 semanales -> 8 horas... ver nota en Informes.js

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

function validarPlaneacion_(datos, fotos) {
  if (!datos.fecha) throw new Error('Falta la fecha');
  if (!datos.grupo) throw new Error('Falta el grupo');

  requireMinPalabras_(datos.objetivo, 'Objetivo');
  requireMinPalabras_(
    (datos.temas_vistos || []).join(' '),
    'Temas vistos'
  );

  if (!Array.isArray(datos.bloques) || datos.bloques.length === 0) {
    throw new Error('La planeación necesita al menos un bloque/momento de clase');
  }
  datos.bloques.forEach((b, i) => {
    if (!b.momento) throw new Error(`Bloque ${i + 1}: falta el momento/tiempo`);
    requireMinPalabras_(b.observacion, `Bloque ${i + 1} - observación pedagógica`);
    requireMinPalabras_(b.avance, `Bloque ${i + 1} - avances/retrocesos`);
  });

  if (!fotos || !fotos.foto_clase) {
    throw new Error('Falta la foto de la clase');
  }
}
