/** Registro de auditoría: quién cambió qué, cuándo y con qué valores. */

function registrarHistorial_(usuario, tipo, idAfectado, cambios) {
  cambios.forEach(({ campo, antes, despues }) => {
    appendRow_(SHEET_NAMES.HISTORIAL, {
      timestamp: new Date().toISOString(),
      usuario: usuario,
      tipo: tipo, // 'planeacion' | 'grupo_estudiantes' | 'horas_gestion'
      id_afectado: idAfectado,
      campo: campo,
      valor_anterior: antes,
      valor_nuevo: despues,
    });
  });
}
