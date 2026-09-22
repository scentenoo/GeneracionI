/**
 * Vigencia contractual del servicio.
 *
 * La fecha vive en Script Properties, no en este archivo: mismo criterio que
 * SHEET_ID/DRIVE_ROOT_FOLDER_ID en Config.js, para no dejarla en el
 * historial de git y para poder renovarla sin volver a hacer `clasp push`
 * (ver renovar_licencia más abajo). Si la Script Property todavía no existe
 * —primer deploy— se usa la fecha pactada original como valor de arranque y
 * se guarda, para que quede la misma en cada lectura siguiente.
 *
 * OJO con el límite real de este esquema: Script Properties es visible
 * desde el editor de Apps Script para cualquiera con permiso de editor
 * sobre ESTE proyecto. Frena a un tercero cualquiera de internet; no frena
 * a quien administre este mismo proyecto (ver VENDOR_API_KEY más abajo).
 */
const FECHA_LIMITE_LICENCIA_POR_DEFECTO_ = '2026-10-05T23:59:59';
const PROP_FECHA_LIMITE_LICENCIA_ = 'FECHA_LIMITE_LICENCIA';
const PROP_VENDOR_API_KEY_ = 'VENDOR_API_KEY';

const MENSAJE_LICENCIA_EXPIRADA_ =
  'El periodo de servicio pactado ha finalizado. Por favor, contacte al ' +
  'proveedor del software para gestionar la renovación o el soporte técnico.';

function fechaLimiteLicencia_() {
  const props = PropertiesService.getScriptProperties();
  let fecha = props.getProperty(PROP_FECHA_LIMITE_LICENCIA_);
  if (!fecha) {
    fecha = FECHA_LIMITE_LICENCIA_POR_DEFECTO_;
    props.setProperty(PROP_FECHA_LIMITE_LICENCIA_, fecha);
  }
  return fecha;
}

/**
 * Compara como texto ISO en la zona horaria del proyecto (America/Bogota,
 * ver appsscript.json) en vez de construir un Date con año/mes/día: ese
 * constructor arma la fecha en la zona del entorno de ejecución de V8, que
 * no siempre coincide con la del proyecto, y una comparación de fechas mal
 * armada es justo el tipo de bug que conviene no tener acá.
 */
function licenciaVigente_() {
  const ahora = Utilities.formatDate(new Date(), 'America/Bogota', "yyyy-MM-dd'T'HH:mm:ss");
  return ahora <= fechaLimiteLicencia_();
}

/**
 * Renovación remota de la fecha límite: para cuando quien administra el
 * backend ya no tenga acceso de edición al proyecto de Apps Script del
 * cliente y no pueda usar `clasp push` ni el editor. Protegida por
 * VENDOR_API_KEY, que se configura A MANO en Project Settings > Script
 * properties —nunca como literal en este archivo— exactamente como ya se
 * hace con SHEET_ID y DRIVE_ROOT_FOLDER_ID.
 *
 * Falla cerrado si la Script Property de la llave no está configurada
 * todavía: sin llave puesta, nadie renueva nada, en vez de aceptar
 * cualquier valor.
 *
 * No exige sesión: es a propósito una puerta aparte del sistema de usuarios
 * de la app (login/token), pensada para un POST directo (Postman, curl) sin
 * pasar por ninguna cuenta de la Sheet.
 */
function renovar_licencia(nueva_fecha, vendor_key) {
  const props = PropertiesService.getScriptProperties();
  const claveEsperada = props.getProperty(PROP_VENDOR_API_KEY_);
  if (!claveEsperada || vendor_key !== claveEsperada) {
    throw new Error('No autorizado');
  }
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/.test(String(nueva_fecha))) {
    throw new Error('Formato de fecha inválido, se espera AAAA-MM-DDTHH:mm:ss');
  }
  props.setProperty(PROP_FECHA_LIMITE_LICENCIA_, nueva_fecha);
  return { ok: true, fecha_limite: nueva_fecha };
}
