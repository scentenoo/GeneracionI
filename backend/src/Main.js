/**
 * Punto de entrada del Web App. El cliente Python manda POST con JSON:
 *   { action: 'guardar_planeacion', params: [token, datos, fotos] }
 * y recibe siempre { ok: true, data: ... } o { ok: false, error: '...' }.
 *
 * Un solo endpoint enrutando por "action" es más simple de mantener que un
 * deployment por función, y hace más fácil loguear todo en un solo lugar.
 */

const ACCIONES_PERMITIDAS_ = {
  login,
  cambiarPassword,
  guardar_planeacion,
  obtener_planeaciones,
  editar_planeacion,
  obtener_estado_mes,
  importar_estudiantes,
  obtener_estudiantes,
  modificar_grupo,
  guardar_horas_gestion,
  obtener_horas_gestion,
  generar_informe_mensual,
  crear_usuario,
  listar_usuarios,
  subir_firma,
  obtener_dashboard_directivo,
  version_actual,
};

function doPost(e) {
  let body;
  try {
    body = JSON.parse(e.postData.contents);
  } catch (err) {
    return jsonResponse_({ ok: false, error: 'Body inválido, se esperaba JSON' });
  }

  const { action, params } = body;
  const fn = ACCIONES_PERMITIDAS_[action];
  if (!fn) {
    return jsonResponse_({ ok: false, error: `Acción desconocida: ${action}` });
  }

  try {
    const data = fn.apply(null, params || []);
    return jsonResponse_({ ok: true, data: data });
  } catch (err) {
    return jsonResponse_({ ok: false, error: String(err.message || err) });
  }
}

/** version_actual() no necesita sesión — el cliente la consulta antes de loguear, al abrir la app. */
function doGet() {
  return jsonResponse_({ ok: true, data: version_actual() });
}

function jsonResponse_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
