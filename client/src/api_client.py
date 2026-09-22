"""Cliente HTTP hacia el backend de Apps Script.

Esta es la única puerta hacia el backend: el resto de la app (pantallas,
lógica de documentos) nunca llama a `requests` directamente. Las pantallas
que arman los niños solo deberían importar las funciones de acá — no
necesitan saber que por debajo hay un POST a Apps Script.
"""

from __future__ import annotations

import json
import time
from typing import Callable

import requests

from config import BACKEND_URL


# Con hasta 3 fotos por clase, guardar_planeacion puede tardar bastante:
# medido contra el backend real, 1 foto ronda 13-14s y 3 fotos 25-30s (cada
# foto es una subida y un cambio de permisos aparte en Drive). 30s dejaba
# muy poco margen justo para el caso de 3 fotos con una conexión mediocre.
_TIMEOUT_SECONDS = 60

# Apps Script, bajo carga o justo después de un deploy, a veces contesta una
# vez con algo transitorio: un 500, un timeout, o —por sus redirects a
# googleusercontent— hasta la respuesta de OTRA petición. Con un usuario a la
# vez casi no pasa, pero cuando la sede sube todo junto a fin de mes sí. Un
# reintento con una pausa breve absorbe casi todos esos casos sin que el
# docente vea nada.
_REINTENTOS = 2
_PAUSA_REINTENTO_S = 2.5


class ApiError(Exception):
    """Error devuelto por el backend (usuario/contraseña, validación, permisos, etc.)."""


class SesionExpirada(ApiError):
    """El token de sesión venció o es inválido — hay que loguearse de nuevo."""


class LicenciaExpirada(ApiError):
    """El periodo de servicio pactado venció (ver Licencia.js en el backend,
    fuente de verdad de esto — no el reloj de esta computadora). Aparte de
    ApiError para que tareas.py la reconozca y tape toda la ventana con el
    aviso fijo, en vez de dejar que la pantalla que la disparó la muestre
    como un error cualquiera."""


class SinConexion(ApiError):
    """No se pudo llegar al servidor: sin internet, o Google no responde.

    Es distinto de que el backend conteste con un error: acá no llegamos ni
    a preguntarle. Se separa para que la app pueda ofrecer reintentar en vez
    de tratarlo como un fallo definitivo.
    """


# Acciones de solo lectura: no cambian nada en la Sheet, así que reintentarlas
# ante un fallo transitorio es seguro (a lo sumo se lee dos veces). Las de
# escritura NO están acá: reintentar una que quizás sí se guardó duplicaría el
# dato (dos planeaciones). El login entra igual: reintentarlo solo abre otra
# sesión, sin efecto.
_SOLO_LECTURA = frozenset({
    "login", "version_actual", "listar_cursos", "listar_todos_los_cursos",
    "listar_usuarios", "obtener_planeaciones", "obtener_planeacion",
    "obtener_foto_planeacion", "revision_del_mes", "mis_devoluciones",
    "historial_revision", "obtener_documento_planeacion", "obtener_documento_informe",
    "obtener_estado_mes", "obtener_estudiantes", "buscar_estudiantes",
    "obtener_horas_gestion", "obtener_actividades", "generar_informe_mensual",
    "obtener_informe_mensual", "obtener_avance_sugerido", "obtener_dashboard_directivo",
    "generar_informe_gestion", "obtener_informe_gestion", "directivos_sin_curso_del_mes",
    "estado_cierre", "fecha_de_cierre",
    # Se sumaron después y quedaron afuera de la lista por descuido — sin
    # esto, cualquiera de estas fallaba duro con el primer bache de Apps
    # Script en vez de reintentar sola como el resto de las de lectura.
    "obtener_estado_nucleo", "obtener_resumen_docente", "generar_certificado_pago",
    "generar_informe_asistencia", "generar_reporte_inasistencias",
    "obtener_horas_del_equipo", "obtener_foto_horas_externas", "obtener_mi_perfil",
    # `batch` junta solo lecturas en este código (cache.precargar, avisos al
    # entrar, Inicio) — reintentar todo el viaje ante un fallo transitorio
    # es tan seguro como reintentar cualquiera de esas lecturas sueltas.
    "batch",
})


# Acciones que aprueban o devuelven algo: siempre contestan {ok, estado, ...}.
_ACCIONES_DE_REVISION = frozenset({"revisar_planeacion", "revisar_informe", "revisar_hora_gestion"})


class _RespuestaTransitoria(Exception):
    """Fallo del que vale la pena reintentar (red caída, 500, respuesta que no
    se entiende). Interno: nunca sale de _call."""

    def __init__(self, publica):
        self.publica = publica  # la excepción que se mostraría si no reintentamos


_TAMANO_TROZO_PROGRESO = 16384


def _generador_con_progreso(datos: bytes, on_progress: Callable[[int, int], None]):
    """Parte `datos` en trozos y avisa cuánto lleva enviado después de cada
    uno — con esto `requests` sube el cuerpo de a poco en vez de todo junto,
    y quien llama puede pintar una barra de progreso real (bytes enviados,
    no una animación que solo simula que algo pasa)."""
    total = len(datos)
    enviado = 0
    if total == 0:
        on_progress(0, 0)
        return
    for inicio in range(0, total, _TAMANO_TROZO_PROGRESO):
        trozo = datos[inicio : inicio + _TAMANO_TROZO_PROGRESO]
        enviado += len(trozo)
        on_progress(enviado, total)
        yield trozo


def _una_llamada(action: str, params, on_progress: Callable[[int, int], None] | None = None):
    """Un intento. Levanta _RespuestaTransitoria para lo reintenable y las
    excepciones públicas (ApiError/SesionExpirada) para lo definitivo.

    `on_progress(enviado, total)` es opcional: cuando se pasa, el cuerpo se
    manda en trozos (en vez de todo de una) para poder avisar cuánto se
    lleva subido. Se usa en los guardados con fotos, donde el cuerpo puede
    pesar varios megabytes y una conexión lenta tarda de verdad."""
    cuerpo = json.dumps({"action": action, "params": list(params)}).encode("utf-8")
    try:
        if on_progress is not None:
            # OJO: sin Content-Length acá a propósito. Puesto a mano junto
            # con un cuerpo por trozos, Google lo rechaza con un 400 (la
            # combinación queda ambigua para su proxy) — comprobado a mano
            # contra el backend real. Sin ese header, requests manda el
            # cuerpo por trozos (chunked) solo, y funciona bien.
            resp = requests.post(
                BACKEND_URL,
                data=_generador_con_progreso(cuerpo, on_progress),
                headers={"Content-Type": "application/json"},
                timeout=_TIMEOUT_SECONDS,
            )
        else:
            resp = requests.post(
                BACKEND_URL,
                data=cuerpo,
                headers={"Content-Type": "application/json"},
                timeout=_TIMEOUT_SECONDS,
            )
    except requests.ConnectionError as exc:  # incluye fallos de DNS
        raise _RespuestaTransitoria(SinConexion(
            "No hay conexión a internet.\n\n"
            "Revise que esté conectado a la red y vuelva a intentar."
        )) from exc
    except requests.Timeout as exc:
        raise _RespuestaTransitoria(SinConexion(
            "El servidor está tardando demasiado en responder.\n\n"
            "Puede ser la conexión. Intente de nuevo en un momento."
        )) from exc
    except requests.RequestException as exc:
        raise _RespuestaTransitoria(SinConexion(
            "No se pudo conectar con el servidor.\n\nIntente de nuevo en un momento."
        )) from exc

    if resp.status_code in (401, 403):
        # Le pasa al deployment de Apps Script cuando pierde el acceso
        # "Cualquier usuario". El docente no puede hacer nada con esto, así
        # que lo importante es que sepa a quién avisarle. No es transitorio.
        raise ApiError(
            "El servidor rechazó la conexión.\n\n"
            "Es un problema de configuración, no suyo: avísele a Samir."
        )
    if resp.status_code >= 500:
        raise _RespuestaTransitoria(SinConexion(
            "El servidor tuvo un problema.\n\nIntente de nuevo en un momento."
        ))
    if resp.status_code != 200:
        # Comprobado a mano contra el backend real: pedido idéntico repetido
        # 3 veces, la 1 y la 3 dieron 200 y la del medio un 404 con una
        # página HTML de Google en vez de la respuesta — el mismo tipo de
        # bache pasajero que el 500 de arriba, no un problema de verdad.
        # Se reintenta igual (ver _SOLO_LECTURA en _call).
        raise _RespuestaTransitoria(
            SinConexion(f"El servidor respondió algo inesperado (código {resp.status_code}).\n\nIntente de nuevo en un momento.")
        )

    try:
        body = resp.json()
    except ValueError as exc:
        # Apps Script devolvió HTML (una página de error) en vez de JSON:
        # transitorio, típico justo después de un deploy.
        raise _RespuestaTransitoria(
            ApiError("El servidor respondió algo que no se entiende.")
        ) from exc

    if not isinstance(body, dict) or "ok" not in body:
        # Respuesta con forma inesperada: bajo carga, Apps Script a veces
        # devuelve el cuerpo de OTRA petición. Reintentable.
        raise _RespuestaTransitoria(ApiError("El servidor respondió algo que no se entiende."))

    if not body.get("ok"):
        error = body.get("error", "Error desconocido")
        if body.get("licencia_expirada"):
            raise LicenciaExpirada(error)
        if "sesión" in error.lower() or "sesion" in error.lower():
            raise SesionExpirada(error)
        raise ApiError(error)

    data = body.get("data")
    if action == "login" and not (isinstance(data, dict) and {"token", "rol", "nombre", "id"} <= data.keys()):
        # Mismo bache de Apps Script que el 404 de más arriba, pero con
        # forma válida: `ok: true` con el `data` de OTRA petición en vuelo
        # (pasa bajo carga, con dos pedidos casi simultáneos — acá con más
        # razón, porque login es justo lo primero que se reintenta solo).
        # Sin este chequeo, una sesión incompleta pasaba entera y explotaba
        # más adelante con un KeyError feo (`sesion["rol"]`) en vez de
        # avisar acá y reintentar.
        raise _RespuestaTransitoria(
            ApiError("El servidor respondió algo inesperado al iniciar sesión.\n\nIntente de nuevo.")
        )
    if action == "mis_devoluciones" and not (
        isinstance(data, list) and all(isinstance(d, dict) for d in data)
    ):
        # Mismo cruce de respuestas: era una lista de textos (el `data` de
        # otra petición) y el chequeo periódico de devoluciones reventaba
        # con "'str' object has no attribute 'get'". Es de solo lectura, así
        # que se reintenta sin riesgo.
        raise _RespuestaTransitoria(
            ApiError("El servidor respondió algo inesperado al traer las devoluciones.\n\nIntente de nuevo.")
        )
    if action in _ACCIONES_DE_REVISION and not (isinstance(data, dict) and "estado" in data):
        # Mismo cruce de respuestas: sin este chequeo, `resultado["estado"]`
        # explotaba con un KeyError feo. No se reintenta (es una escritura:
        # quizás sí se guardó), así que sube tal cual y la pantalla avisa
        # que actualice la lista para ver cómo quedó de verdad.
        raise _RespuestaTransitoria(ApiError(
            "El servidor respondió algo inesperado.\n\n"
            "Actualice la lista para ver cómo quedó la revisión."
        ))
    if action == "obtener_foto_horas_externas" and not (isinstance(data, dict) and "base64" in data):
        # Mismo cruce de respuestas que el de login: bajo carga, esto puede
        # traer el `data` de OTRA petición en vuelo. Sin este chequeo
        # explotaba más adelante con un KeyError feo al leer foto["base64"].
        raise _RespuestaTransitoria(
            ApiError("El servidor respondió algo inesperado al traer la foto.\n\nIntente de nuevo.")
        )
    return data


def _call(action: str, *params, on_progress: Callable[[int, int], None] | None = None):
    """Puerta única al backend. Un fallo transitorio (red, 500, respuesta
    ilegible) se reintenta con una pausa breve —pero solo en acciones de
    solo lectura, para no duplicar una escritura que quizás sí se guardó.
    Las excepciones que llegan a la interfaz nunca traen el detalle técnico
    ni la URL del backend.

    `on_progress`: ver _una_llamada. No tiene sentido combinarlo con
    reintento (una acción de escritura nunca se reintenta igual), así que
    solo importa para las llamadas de una sola pasada."""
    reintentable = action in _SOLO_LECTURA
    intentos = _REINTENTOS + 1 if reintentable else 1
    for i in range(intentos):
        try:
            return _una_llamada(action, params, on_progress)
        except _RespuestaTransitoria as t:
            if i + 1 >= intentos:
                raise t.publica from None
            time.sleep(_PAUSA_REINTENTO_S)


def version_actual() -> dict:
    """{version, version_minima, link_instalador}. Se consulta antes de
    loguearse, al abrir la app, así que no lleva token."""
    return _call("version_actual")


def fijar_version(
    token: str, version: str, link_instalador: str = "", obligatoria: bool = False
) -> dict:
    """Publica una versión. Con `obligatoria`, sube el piso: quien tenga
    una anterior queda bloqueado. Sin ella, solo se avisa. Solo el
    administrador."""
    return _call("fijar_version", token, version, link_instalador, obligatoria)


def batch(llamadas: list[tuple[str, list]]) -> list:
    """Varias acciones en un solo viaje al backend.

    Cada llamada cuesta ~3 segundos de ida y vuelta, casi todo overhead
    fijo. Agrupar tres en una request las baja de nueve segundos a tres.

    `llamadas` es [(accion, [params...]), ...]. Devuelve una lista del
    mismo largo: el valor si salió bien, o una ApiError (sin lanzarla) si
    esa llamada puntual falló — que una falle no invalida al resto.
    """
    payload = [{"action": accion, "params": list(params)} for accion, params in llamadas]
    resultados = _call("batch", payload)
    return [
        r["data"] if r.get("ok") else ApiError(r.get("error", "Error desconocido"))
        for r in resultados
    ]


# --- Sesión -----------------------------------------------------------------

def login(usuario: str, password: str) -> dict:
    """Devuelve {token, id, nombre, usuario, rol}."""
    return _call("login", usuario, password)


def cambiar_password(token: str, password_actual: str, password_nueva: str) -> dict:
    return _call("cambiarPassword", token, password_actual, password_nueva)


# --- Planeaciones -------------------------------------------------------------

def guardar_planeacion(
    token: str, datos: dict, fotos: dict, on_progress: Callable[[int, int], None] | None = None
) -> dict:
    """datos: fecha, grupo, objetivo, temas_vistos[], bloques[], asistencia[].
    fotos: {"fotos_clase": [{"base64": ..., "mimeType": "image/jpeg"}, ...]}
    (1 a 3 fotos). on_progress(enviado, total) opcional, para una barra de
    subida real — ver _una_llamada."""
    return _call("guardar_planeacion", token, datos, fotos, on_progress=on_progress)


def guardar_documento_planeacion(
    token: str, planeacion_id: int, archivo: dict, on_progress: Callable[[int, int], None] | None = None
) -> dict:
    """Sube a Drive el .docx de la planeación, que es lo que el informe
    mensual enlaza en la columna «LINK A PLANEACION».

    archivo: {"base64": ..., "mimeType": ...}. Con `"en_sitio": True` el
    backend pisa el contenido del mismo archivo en vez de recrearlo (más
    rápido, y el id de Drive no cambia); si no puede, cae a recrearlo."""
    return _call("guardar_documento_planeacion", token, planeacion_id, archivo, on_progress=on_progress)


def obtener_planeaciones(
    token: str,
    docente_id: int | None = None,
    curso_id: int | None = None,
    resumen: bool = False,
) -> list[dict]:
    """Con `resumen` no trae los bloques ni la asistencia — son el grueso
    del peso de cada fila y las listas no los muestran."""
    return _call("obtener_planeaciones", token, docente_id, curso_id, resumen)


def obtener_planeacion(token: str, id_: int) -> dict:
    """Una sola planeación completa, para abrirla en el editor."""
    return _call("obtener_planeacion", token, id_)


def obtener_foto_planeacion(token: str, id_: int) -> list[dict]:
    """Las fotos de clase de una planeación (1 a 3), en base64, para
    regenerar su .docx al editarla. Lista vacía si no tiene fotos."""
    return _call("obtener_foto_planeacion", token, id_)


def obtener_documento_planeacion(token: str, id_: int) -> dict | None:
    """El .docx ya archivado de la planeación, en base64 — para
    actualizarle solo la hoja de historial al aprobar/devolver sin
    regenerar todo el documento. None si todavía no tiene uno archivado."""
    return _call("obtener_documento_planeacion", token, id_)


def editar_planeacion(
    token: str, id_: int, cambios: dict, fotos: dict | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> dict:
    """fotos, si se manda, reemplaza el set completo de fotos (1 a 3):
    {"fotos_clase": [{"base64": ..., "mimeType": ...}, ...]}. Sin este
    argumento, las fotos que ya tenía la planeación quedan como están."""
    return _call("editar_planeacion", token, id_, cambios, fotos, on_progress=on_progress)


def eliminar_planeacion(token: str, id_: int) -> dict:
    """Solo el docente dueño puede eliminar su propia planeación."""
    return _call("eliminar_planeacion", token, id_)


def obtener_estado_mes(token: str, curso_id: int, mes: str) -> dict:
    """El estado va por curso, no por docente. mes en formato 'YYYY-MM'."""
    return _call("obtener_estado_mes", token, curso_id, mes)


# --- Cursos -------------------------------------------------------------------

def crear_curso(token: str, datos: dict) -> dict:
    """datos: docente_id, nombre, nucleo, edad_desde, edad_hasta, color.
    Solo directivo. `color` ("verde", "morado" o "") decide quién revisa el
    curso; vacío significa que solo el administrador puede revisarlo."""
    return _call("crear_curso", token, datos)


def listar_cursos(
    token: str, docente_id: int | None = None, incluir_inactivos: bool = False
) -> list[dict]:
    """Sin docente_id devuelve los cursos del propio usuario."""
    return _call("listar_cursos", token, docente_id, incluir_inactivos)


def listar_todos_los_cursos(token: str) -> list[dict]:
    """Todos los cursos del programa. Solo directivo."""
    return _call("listar_todos_los_cursos", token)


def editar_curso(token: str, curso_id: int, cambios: dict) -> dict:
    return _call("editar_curso", token, curso_id, cambios)


def desactivar_curso(token: str, curso_id: int) -> dict:
    """No borra el curso: lo marca inactivo, para no romper informes viejos."""
    return _call("desactivar_curso", token, curso_id)


def obtener_estado_nucleo(token: str, mes: str) -> dict:
    """Una fila por curso del propio núcleo (el suyo y los de sus
    compañeros): cuántas planeaciones lleva cada uno y si entregó el
    informe. Vacío si el usuario no tiene cursos propios."""
    return _call("obtener_estado_nucleo", token, mes)


def obtener_resumen_docente(token: str, mes: str) -> dict:
    """Los números del dashboard: planeaciones registradas/pendientes,
    horas ejecutadas, cursos activos e informes pendientes del mes,
    sobre los cursos propios."""
    return _call("obtener_resumen_docente", token, mes)


# --- Estudiantes / grupo ------------------------------------------------------

def importar_estudiantes(token: str, curso_id: int, csv_texto: str) -> dict:
    return _call("importar_estudiantes", token, curso_id, csv_texto)


def obtener_estudiantes(token: str, curso_id: int) -> list[dict]:
    """Los estudiantes cuelgan del curso, no del docente."""
    return _call("obtener_estudiantes", token, curso_id)


def modificar_grupo(token: str, curso_id: int, cambios: dict) -> dict:
    """cambios: {"agregar": [{"nombre": ...}], "quitar": [id, ...]}"""
    return _call("modificar_grupo", token, curso_id, cambios)


# --- Horas de gestión (rol directivo) -----------------------------------------

def guardar_horas_gestion(
    token: str, datos: dict, fotos: dict, on_progress: Callable[[int, int], None] | None = None
) -> dict:
    """datos: fecha, actividad, horas_sede, entregable, link_soporte.
    fotos: {"foto": {"base64": ..., "mimeType": "image/jpeg"}} — obligatoria,
    igual que el entregable: son la evidencia de la actividad."""
    return _call("guardar_horas_gestion", token, datos, fotos, on_progress=on_progress)


def editar_horas_gestion(
    token: str, id_: int, cambios: dict, fotos: dict | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> dict:
    """Solo el dueño puede corregir su propia hora de gestión.

    Sin foto nueva se conserva la que ya tenía; lo que no se puede es
    dejarla sin ninguna."""
    return _call("editar_horas_gestion", token, id_, cambios, fotos or {}, on_progress=on_progress)


def eliminar_horas_gestion(token: str, id_: int) -> dict:
    """Solo el dueño puede eliminar su propia hora de gestión."""
    return _call("eliminar_horas_gestion", token, id_)


def obtener_horas_gestion(token: str, directivo_id: int | None = None) -> list[dict]:
    return _call("obtener_horas_gestion", token, directivo_id)


def obtener_horas_del_equipo(token: str, mes: str) -> dict:
    """Solo administrador. {resumen: [{persona_id, nombre, rol, total_horas,
    objetivo, cumple}], actividades: [{tipo: 'gestion'|'actividad', ...,
    estado, revisado_por, motivo_devolucion}]} de TODO el equipo (docentes y
    directivos) en ese mes, para Revisar → Horas externas."""
    return _call("obtener_horas_del_equipo", token, mes)


def obtener_foto_horas_externas(token: str, foto_drive_id: str) -> dict:
    """Una foto puntual ({base64, mimeType}) de una hora externa, para
    mostrarla adentro de la app en vez de abrir Drive. Solo administrador."""
    return _call("obtener_foto_horas_externas", token, foto_drive_id)


def revisar_hora_gestion(token: str, id_: int, aprobar: bool, motivo: str = "") -> dict:
    """Solo administrador. Aprobar/devolver una hora de gestión externa;
    devolver necesita motivo."""
    return _call("revisar_hora_gestion", token, id_, aprobar, motivo)


# --- Actividades que no son clases ---------------------------------------------

def guardar_actividad(
    token: str, datos: dict, fotos: dict | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> dict:
    """Reuniones, claustros, informes: lo que se factura y no es una clase.
    datos: curso_id, fecha, descripcion, horas_sede, horas_externas.
    fotos: {"foto": {"base64": ..., "mimeType": ...}} — obligatoria salvo
    para directivos."""
    return _call("guardar_actividad", token, datos, fotos or {}, on_progress=on_progress)


def editar_actividad(
    token: str, id_: int, datos: dict, fotos: dict | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> dict:
    """Sin foto nueva se conserva la que ya tenía."""
    return _call("editar_actividad", token, id_, datos, fotos or {}, on_progress=on_progress)


def obtener_actividades(token: str, curso_id: int, mes: str | None = None) -> list[dict]:
    return _call("obtener_actividades", token, curso_id, mes)


def eliminar_actividad(token: str, id_: int) -> dict:
    return _call("eliminar_actividad", token, id_)


# --- Informes ------------------------------------------------------------------

def generar_informe_mensual(
    token: str,
    curso_id: int,
    mes: str,
    narrativa: dict | None = None,
    gestion_narrativa: dict | None = None,
    incluir_gestion: bool = True,
) -> dict:
    """Devuelve el contexto JSON listo para rellenar con docxtpl
    (ver client/src/services/docx_generator.py).

    El informe va por curso: quien tiene dos cursos entrega dos informes.
    Sin `narrativa` usa lo ya entregado — así descarga el directivo. Con
    narrativa es la vista previa de un borrador todavía sin entregar."""
    return _call(
        "generar_informe_mensual", token, curso_id, mes,
        narrativa, gestion_narrativa or {}, incluir_gestion,
    )


def guardar_documento_informe(
    token: str, curso_id: int, mes: str, archivo: dict,
    on_progress: Callable[[int, int], None] | None = None,
) -> dict:
    """Sube a Drive el .docx del informe ya entregado, para que quede
    archivado y el revisor lo pueda abrir directo.

    archivo: {"base64": ..., "mimeType": ...} — puede pesar bastante si el
    mes tuvo varias clases con fotos, de ahí on_progress. `"en_sitio": True`
    igual que en guardar_documento_planeacion."""
    return _call("guardar_documento_informe", token, curso_id, mes, archivo, on_progress=on_progress)


def obtener_documento_informe(token: str, curso_id: int, mes: str) -> dict | None:
    """El .docx ya archivado del informe, en base64 — para actualizarle
    solo la hoja de historial al aprobar/devolver. None si todavía no tiene
    uno archivado."""
    return _call("obtener_documento_informe", token, curso_id, mes)


def guardar_informe_mensual(
    token: str,
    curso_id: int,
    mes: str,
    narrativa: dict,
    gestion_narrativa: dict | None = None,
    incluir_gestion: bool = False,
) -> dict:
    """Entrega el informe del mes: guarda las respuestas para poder
    reabrirlas y para que el dashboard sepa quién ya entregó. Exige tener
    todas las planeaciones del mes cargadas."""
    return _call(
        "guardar_informe_mensual", token, curso_id, mes,
        narrativa, gestion_narrativa or {}, incluir_gestion,
    )


def obtener_informe_mensual(token: str, curso_id: int, mes: str) -> dict | None:
    """Las respuestas ya entregadas, o None si todavía no se entregó."""
    return _call("obtener_informe_mensual", token, curso_id, mes)


def obtener_avance_sugerido(token: str, curso_id: int, mes: str) -> list[dict]:
    """Las semanas del mes con sus temas, para prellenar la sección 3."""
    return _call("obtener_avance_sugerido", token, curso_id, mes)


# --- Informe de gestión (directivo sin curso) ----------------------------------

def guardar_informe_gestion(token: str, mes: str, gestion_narrativa: dict) -> dict:
    """Entrega el informe de gestión del mes de un directivo sin curso."""
    return _call("guardar_informe_gestion", token, mes, gestion_narrativa)


def obtener_informe_gestion(token: str, directivo_id: int | None, mes: str) -> dict | None:
    """Lo entregado, o None. Sin directivo_id, el del propio usuario."""
    return _call("obtener_informe_gestion", token, directivo_id, mes)


def generar_informe_gestion(
    token: str, directivo_id: int | None, mes: str, gestion_narrativa: dict | None = None
) -> dict:
    """Contexto docxtpl del informe de gestión. Sin narrativa, usa lo
    entregado (así lo descarga quien supervisa)."""
    return _call("generar_informe_gestion", token, directivo_id, mes, gestion_narrativa)


def directivos_sin_curso_del_mes(token: str, mes: str) -> list[dict]:
    """Directivos sin curso propio y si entregaron su informe de gestión,
    para «Informes del mes»."""
    return _call("directivos_sin_curso_del_mes", token, mes)


# --- Revisión (aprobar / devolver) ---------------------------------------------

def revisar_planeacion(token: str, id_: int, aprobar: bool, motivo: str = "") -> dict:
    """El revisor del curso aprueba o devuelve una planeación. Devolver
    necesita motivo. Responde {ok, estado, historial}: el historial ya
    incluye esta acción."""
    return _call("revisar_planeacion", token, id_, aprobar, motivo)


def revisar_informe(token: str, curso_id, mes: str, aprobar: bool, motivo: str = "") -> dict:
    """Igual que revisar_planeacion, para el informe de un curso y mes."""
    return _call("revisar_informe", token, curso_id, mes, aprobar, motivo)


def revision_del_mes(token: str, mes: str) -> dict:
    """Todas las planeaciones e informes del mes con su estado (no solo lo
    pendiente): {planeaciones[], informes[]}."""
    return _call("revision_del_mes", token, mes)


def mis_devoluciones(token: str) -> list[dict]:
    """Lo que le devolvieron al docente, con motivo — para el aviso al entrar."""
    return _call("mis_devoluciones", token)


def historial_revision(token: str, tipo: str, ref) -> list[dict]:
    """El historial de un documento (entregado/devuelto/reenviado/aprobado)."""
    return _call("historial_revision", token, tipo, ref)


def fijar_revisores(token: str, revisor_verde_id, revisor_morado_id) -> dict:
    """Solo administrador. Fija quién revisa los cursos verdes y los morados.

    Cadena vacía desasigna el color; None lo deja como estaba."""
    return _call("fijar_revisores", token, revisor_verde_id, revisor_morado_id)


def obtener_revisores(token: str) -> dict:
    """Solo administrador. Quién revisa cada color hoy, y cuántos cursos
    activos hay de cada uno (incluidos los que quedaron sin color)."""
    return _call("obtener_revisores", token)


# --- Administración de usuarios (rol directivo) --------------------------------

def crear_usuario(token: str, datos: dict) -> dict:
    return _call("crear_usuario", token, datos)


def editar_usuario(token: str, usuario_id: int, cambios: dict) -> dict:
    """Solo rol directivo. La contraseña no se toca acá (ver cambiar_password)."""
    return _call("editar_usuario", token, usuario_id, cambios)


def listar_usuarios(token: str) -> list[dict]:
    return _call("listar_usuarios", token)


def obtener_mi_perfil(token: str) -> dict:
    """El propio perfil (cédula, teléfono, formación, cuenta bancaria) —
    cualquier usuario logueado puede pedir el suyo, no hace falta ser
    directivo. Sirve para que un docente vea si ya le cargaron un dato."""
    return _call("obtener_mi_perfil", token)


def restablecer_password(token: str, usuario_id: int, password_nueva: str) -> dict:
    """Le pone una contraseña nueva a otro usuario, para cuando se le
    olvidó la suya.

    No hay forma de *ver* la contraseña de nadie: lo que guarda el backend
    es un hash con salt, ni él la conoce. Un directivo puede restablecer
    docentes; para tocar a otro directivo hace falta el administrador."""
    return _call("restablecer_password", token, usuario_id, password_nueva)


def eliminar_usuario(token: str, usuario_id: int) -> dict:
    """Directivo: solo usuarios con rol 'docente'. Administrador: cualquiera."""
    return _call("eliminar_usuario", token, usuario_id)


def convertirme_administrador(token: str) -> dict:
    """Bootstrap: solo funciona mientras no exista ya un administrador."""
    return _call("convertirme_administrador", token)


def transferir_administrador(token: str, nuevo_admin_id: int) -> dict:
    """Solo el administrador actual puede llamar esto."""
    return _call("transferir_administrador", token, nuevo_admin_id)


def subir_firma(token: str, usuario_id: int, imagen: dict) -> dict:
    return _call("subir_firma", token, usuario_id, imagen)


def estado_cierre(token: str, curso_id: int, mes: str) -> dict:
    """Si ese mes sigue abierto para quien pregunta. El docente lo usa para
    saber si todavía puede editar o borrar."""
    return _call("estado_cierre", token, curso_id, mes)


def fijar_dia_de_corte(token: str, dia: int) -> dict:
    """El día del mes siguiente en que se cierra el mes anterior. Directivo."""
    return _call("fijar_dia_de_corte", token, dia)


def fijar_fecha_de_cierre(token: str, mes: str, fecha: str) -> dict:
    """La fecha exacta (AAAA-MM-DD) en que se cierra un mes puntual, elegida
    en el calendario. Directivo."""
    return _call("fijar_fecha_de_cierre", token, mes, fecha)


def fecha_de_cierre(token: str, mes: str) -> dict:
    """La fecha en que se cierra un mes: {mes, fecha_cierre, fijada}."""
    return _call("fecha_de_cierre", token, mes)


def reabrir_mes(token: str, curso_id: int, mes: str, abierta: bool = True) -> dict:
    """Vuelve a abrir (o cierra de nuevo) un curso y un mes puntuales."""
    return _call("reabrir_mes", token, curso_id, mes, abierta)


def obtener_dashboard_directivo(token: str, mes: str) -> list[dict]:
    return _call("obtener_dashboard_directivo", token, mes)


def generar_certificado_pago(token: str, mes: str) -> dict:
    """Certificado mensual de horas de docencia para pago (solo
    administradores): una fila por docente y curso con el total de horas
    de ese curso ese mes (de sede + externas, ya sumadas)."""
    return _call("generar_certificado_pago", token, mes)


def generar_informe_asistencia(token: str, mes: str) -> dict:
    """Informe consolidado de asistencia de todos los cursos de un mes
    (solo administradores), para mandar a la Secretaría de Educación: por
    curso, qué estudiantes asistieron/faltaron en cada clase y el total del
    mes."""
    return _call("generar_informe_asistencia", token, mes)


def generar_reporte_inasistencias(token: str) -> dict:
    """Inasistencias acumuladas por curso activo (desde que cada estudiante
    se inscribió, no de un mes puntual) más cuántos cursos activos tiene
    cada estudiante del programa — solo administradores, para exportar a
    Excel."""
    return _call("generar_reporte_inasistencias", token)


def ejecutar_migracion(token: str, nombre: str) -> dict:
    """Tareas de mantenimiento del esquema, solo para el administrador.
    Evita tener que abrir el editor de Apps Script en cada cambio."""
    return _call("ejecutar_migracion", token, nombre)
