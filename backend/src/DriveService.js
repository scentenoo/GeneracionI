/**
 * Guardado de archivos en Drive. La compresión de fotos pasa en el cliente
 * (Pillow) antes de llamar al backend — acá solo se decodifica el base64 y
 * se guarda en la ruta de carpetas correspondiente dentro de la carpeta raíz
 * dedicada del programa.
 *
 * `rutaCarpetas` es una lista de nombres, de la raíz hacia adentro — por
 * ejemplo ['Planeaciones', 'Robótica', '2026-08 - Agosto', 'Fotos']. Cada
 * nivel se crea si no existe. Esto solo decide dónde cae un archivo NUEVO:
 * no mueve ni reorganiza nada de lo que ya está en Drive.
 */

function guardarArchivoBase64_(rutaCarpetas, base64Data, mimeType, nombreArchivo) {
  const folder = getOrCrearRutaCarpetas_(rutaCarpetas);
  return guardarArchivoEnCarpeta_(folder, base64Data, mimeType, nombreArchivo);
}

/**
 * Igual que guardarArchivoBase64_ pero con la carpeta ya resuelta —para
 * cuando se suben varios archivos seguidos al mismo lugar (hasta 3 fotos de
 * una clase) y no tiene sentido rehacer la búsqueda de carpetas por cada
 * uno.
 */
function guardarArchivoEnCarpeta_(folder, base64Data, mimeType, nombreArchivo) {
  const bytes = Utilities.base64Decode(base64Data);
  const blob = Utilities.newBlob(bytes, mimeType, nombreArchivo);
  const file = folder.createFile(blob);
  compartirConQuienTengaElLink_(file);
  return file.getId();
}

function reemplazarArchivo_(rutaCarpetas, fileIdExistente, base64Data, mimeType, nombreArchivo) {
  trasharSiExiste_(fileIdExistente);
  return guardarArchivoBase64_(rutaCarpetas, base64Data, mimeType, nombreArchivo);
}

/**
 * Manda un archivo a la papelera si existe el id. No revienta si ya no
 * está o no es accesible — eso no tiene por qué frenar el borrado o el
 * reemplazo que lo llamó. Compartido por los `eliminar_*` (planeación,
 * actividad, curso) y por `reemplazarArchivo_`, que antes repetían este
 * mismo try/catch cada uno por su lado.
 */
function trasharSiExiste_(fileId) {
  if (!fileId) return;
  try {
    DriveApp.getFileById(fileId).setTrashed(true);
  } catch (e) {
    // Ya no existe o no es accesible: no bloquea lo que se estaba haciendo.
  }
}

/**
 * Sin esto, un archivo nuevo queda visible solo para la cuenta que corre el
 * script: cualquier directivo que tocara "Abrir" en Revisar, o el link de
 * una planeación en el informe mensual, tenía que pedir acceso archivo por
 * archivo. Quien tenga el link (una cadena larga, no algo que se adivine)
 * ya entra directo — pedido explícito del piloto.
 *
 * Si el dominio de Workspace tiene bloqueado compartir hacia afuera,
 * setSharing tira error; se lo traga para que ESO no tumbe el guardado del
 * archivo — peor que pedir acceso sería que la planeación no se pudiera
 * guardar.
 */
function compartirConQuienTengaElLink_(file) {
  try {
    file.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
  } catch (e) {
    // Política del dominio no lo permite: el archivo se guarda igual,
    // solo que sigue pidiendo acceso como antes.
  }
}

/** Recorre `nombres` desde la raíz del programa, creando cada nivel que falte. */
function getOrCrearRutaCarpetas_(nombres) {
  let carpeta = getDriveRootFolder_();
  nombres.forEach((nombre) => {
    carpeta = getOrCreateSubcarpeta_(carpeta, nombre);
  });
  return carpeta;
}

function getOrCreateSubcarpeta_(carpetaPadre, nombre) {
  const existentes = carpetaPadre.getFoldersByName(nombre);
  if (existentes.hasNext()) return existentes.next();
  return carpetaPadre.createFolder(nombre);
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

function nombreDeInforme_(nombreCurso, mes) {
  return `Informe - ${nombreParaDrive_(nombreCurso)} - ${mes}.docx`;
}

function nombreParaDrive_(nombreCurso) {
  return String(nombreCurso || 'sin curso')
    .replace(/[\\/:*?"<>|]/g, ' ')
    .trim()
    .slice(0, 60);
}

/**
 * "2026-08 - Agosto": el número adelante para que las carpetas ordenen
 * cronológicamente en Drive (que ordena alfabético), y el nombre atrás para
 * que se lean sin tener que abrirlas.
 */
function nombreCarpetaMes_(fecha) {
  const mes = mesDeFecha_(fecha);
  return `${mes} - ${nombreMes_(mes)}`;
}
