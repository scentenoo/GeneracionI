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
  guardar_documento_planeacion,
  obtener_planeaciones,
  obtener_planeacion,
  editar_planeacion,
  eliminar_planeacion,
  obtener_estado_mes,
  estado_cierre,
  fijar_dia_de_corte,
  reabrir_mes,
  importar_estudiantes,
  obtener_estudiantes,
  modificar_grupo,
  guardar_horas_gestion,
  obtener_horas_gestion,
  guardar_actividad,
  editar_actividad,
  obtener_actividades,
  eliminar_actividad,
  crear_curso,
  listar_cursos,
  listar_todos_los_cursos,
  editar_curso,
  desactivar_curso,
  generar_informe_mensual,
  guardar_informe_mensual,
  obtener_informe_mensual,
  obtener_avance_sugerido,
  crear_usuario,
  editar_usuario,
  eliminar_usuario,
  convertirme_administrador,
  transferir_administrador,
  listar_usuarios,
  restablecer_password,
  subir_firma,
  obtener_dashboard_directivo,
  ejecutar_migracion,
  version_actual,
  fijar_version,
};

/**
 * Varias acciones en un solo viaje.
 *
 * Cada llamada a Apps Script cuesta entre 2 y 3 segundos de ida y vuelta,
 * casi todo overhead fijo y no datos. Una pantalla que necesita tres cosas
 * tardaba nueve segundos en abrir; agrupadas tarda tres.
 *
 * Cada llamada lleva su propio ok/error: que una falle no tumba al resto.
 */
function batch(llamadas) {
  return (llamadas || []).map((llamada) => {
    const fn = ACCIONES_PERMITIDAS_[llamada.action];
    // batch dentro de batch no aporta nada y solo abre la puerta a recursión.
    if (!fn || llamada.action === 'batch') {
      return { ok: false, error: `Acción desconocida: ${llamada.action}` };
    }
    try {
      return { ok: true, data: fn.apply(null, llamada.params || []) };
    } catch (err) {
      return { ok: false, error: String(err.message || err) };
    }
  });
}

function doPost(e) {
  let body;
  try {
    body = JSON.parse(e.postData.contents);
  } catch (err) {
    return jsonResponse_({ ok: false, error: 'Body inválido, se esperaba JSON' });
  }

  const { action, params } = body;

  if (action === 'batch') {
    try {
      return jsonResponse_({ ok: true, data: batch((params || [])[0]) });
    } catch (err) {
      return jsonResponse_({ ok: false, error: String(err.message || err) });
    }
  }

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
