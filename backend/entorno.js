#!/usr/bin/env node
/**
 * Puente entre clasp y los DOS proyectos de Apps Script (pruebas y real),
 * para que subir código sea explícito y no dependa de acordarse cuál de
 * los dos quedó pegado en `.clasp.json` — eso fue justo lo que pasó una
 * vez: se estaba editando "el de pruebas" y en realidad era el real.
 *
 * Nunca deja un `.clasp.json` ambiguo dando vueltas: lo arma al vuelo con
 * el scriptId del entorno pedido, corre el comando de clasp, y lo borra
 * apenas termina. Si en ese momento no hay ningún `.clasp.json`, cualquier
 * `clasp push` suelto (sin pasar por este script) falla en vez de ir a
 * parar a saber dónde.
 *
 * Uso: node entorno.js <test|prod> <push|pull|open>
 */

const fs = require('fs');
const path = require('path');
const readline = require('readline');
const { execSync } = require('child_process');

const RUTA_CLASP = path.join(__dirname, '.clasp.json');
const RUTA_ENTORNOS = path.join(__dirname, 'entornos.json');

function preguntar(mensaje) {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolve) => rl.question(mensaje, (resp) => { rl.close(); resolve(resp); }));
}

async function main() {
  const [destino, accion] = process.argv.slice(2);

  if (!['test', 'prod'].includes(destino) || !['push', 'pull', 'open'].includes(accion)) {
    console.error('Uso: node entorno.js <test|prod> <push|pull|open>');
    process.exit(1);
  }

  if (!fs.existsSync(RUTA_ENTORNOS)) {
    console.error(
      'Falta backend/entornos.json (no se versiona, tiene los scriptId reales).\n' +
      'Copiá entornos.json.example a entornos.json y completá los dos scriptId\n' +
      '(Project Settings > IDs del proyecto de secuencia de comandos, en cada editor de Apps Script).'
    );
    process.exit(1);
  }

  const entornos = JSON.parse(fs.readFileSync(RUTA_ENTORNOS, 'utf8'));
  const entorno = entornos[destino];
  if (!entorno || !entorno.scriptId || entorno.scriptId.startsWith('PEGAR_AQUÍ')) {
    console.error(`Falta configurar "${destino}" en backend/entornos.json (todavía tiene el placeholder).`);
    process.exit(1);
  }

  console.log('');
  console.log(destino === 'prod' ? '########## PRODUCCIÓN ##########' : '---------- pruebas ----------');
  console.log(`Entorno: ${entorno.nombre}`);
  console.log(`Acción:  ${accion}`);
  console.log(`scriptId: ${entorno.scriptId}`);
  console.log('');

  if (destino === 'prod') {
    const resp = await preguntar('Escribí exactamente SI PRODUCCION para continuar: ');
    if (resp.trim() !== 'SI PRODUCCION') {
      console.log('Cancelado — no se tocó nada.');
      process.exit(1);
    }
  }

  fs.writeFileSync(RUTA_CLASP, JSON.stringify({ scriptId: entorno.scriptId, rootDir: 'src' }, null, 2));
  try {
    const comando = { push: 'clasp push', pull: 'clasp pull', open: 'clasp open-script' }[accion];
    execSync(comando, { cwd: __dirname, stdio: 'inherit' });
    console.log(`\n✔ ${accion} contra ${entorno.nombre} — listo.`);
  } finally {
    // Nunca se deja .clasp.json apuntando a nada después de terminar: la
    // próxima vez que alguien corra `clasp` a mano acá, sin pasar por este
    // script, tiene que fallar en vez de pegarle sin querer al que quedó.
    fs.unlinkSync(RUTA_CLASP);
  }
}

main().catch((err) => {
  console.error(err.message || err);
  if (fs.existsSync(RUTA_CLASP)) fs.unlinkSync(RUTA_CLASP);
  process.exit(1);
});
