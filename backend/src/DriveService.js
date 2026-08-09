/**
 * Guardado de archivos en Drive. La compresión de fotos pasa en el cliente
 * (Pillow) antes de llamar al backend — acá solo se decodifica el base64 y
 * se guarda en la subcarpeta correspondiente dentro de la carpeta raíz
 * dedicada del programa.
 */

function guardarArchivoBase64_(subfolderName, base64Data, mimeType, nombreArchivo) {
  const folder = getOrCreateDriveSubfolder_(subfolderName);
  const bytes = Utilities.base64Decode(base64Data);
  const blob = Utilities.newBlob(bytes, mimeType, nombreArchivo);
  const file = folder.createFile(blob);
  return file.getId();
}

function reemplazarArchivo_(subfolderName, fileIdExistente, base64Data, mimeType, nombreArchivo) {
  if (fileIdExistente) {
    try {
      DriveApp.getFileById(fileIdExistente).setTrashed(true);
    } catch (e) {
      // El archivo ya no existe o no es accesible: seguimos igual, no es bloqueante.
    }
  }
  return guardarArchivoBase64_(subfolderName, base64Data, mimeType, nombreArchivo);
}

function obtenerUrlDescarga_(fileId) {
  return `https://drive.google.com/uc?id=${fileId}`;
}

/** El link que se pega en el informe mensual, para abrirlo en el navegador. */
function urlDeArchivo_(fileId) {
  return fileId ? `https://drive.google.com/file/d/${fileId}/view?usp=sharing` : '';
}

/**
 * Nombre con el que el archivo queda en Drive.
 *
 * Antes era `clase_<id del docente>_<fecha>`, así que todas las fotos de
 * una misma persona empezaban igual ("clase_1_...") y en Drive no había
 * forma de saber de qué curso era cada una sin abrirlas.
 */
function nombreDeFoto_(prefijo, nombreCurso, fecha) {
  return `${prefijo} - ${nombreParaDrive_(nombreCurso)} - ${fechaISO_(fecha)}.jpg`;
}

function nombreDeDocumento_(nombreCurso, fecha) {
  return `Planeacion - ${nombreParaDrive_(nombreCurso)} - ${fechaISO_(fecha)}.docx`;
}

function nombreParaDrive_(nombreCurso) {
  return String(nombreCurso || 'sin curso')
    .replace(/[\\/:*?"<>|]/g, ' ')
    .trim()
    .slice(0, 60);
}
