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
