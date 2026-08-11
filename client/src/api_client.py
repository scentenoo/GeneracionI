"""Cliente HTTP hacia el backend de Apps Script.

Esta es la única puerta hacia el backend: el resto de la app (pantallas,
lógica de documentos) nunca llama a `requests` directamente. Las pantallas
que arman los niños solo deberían importar las funciones de acá — no
necesitan saber que por debajo hay un POST a Apps Script.
"""

from __future__ import annotations

import requests

from config import BACKEND_URL

_TIMEOUT_SECONDS = 30


class ApiError(Exception):
    """Error devuelto por el backend (usuario/contraseña, validación, permisos, etc.)."""


class SesionExpirada(ApiError):
    """El token de sesión venció o es inválido — hay que loguearse de nuevo."""


class SinConexion(ApiError):
    """No se pudo llegar al servidor: sin internet, o Google no responde.

    Es distinto de que el backend conteste con un error: acá no llegamos ni
    a preguntarle. Se separa para que la app pueda ofrecer reintentar en vez
    de tratarlo como un fallo definitivo.
    """


def _call(action: str, *params):
    """Los errores de red se traducen a un mensaje que le sirva a un
    docente. El detalle técnico de requests no le dice nada a nadie y
    además incluye la URL del backend, que no tiene por qué andar a la
    vista en una pantalla de error."""
    try:
        resp = requests.post(
            BACKEND_URL,
            json={"action": action, "params": list(params)},
            timeout=_TIMEOUT_SECONDS,
        )
    except requests.ConnectionError as exc:  # incluye fallos de DNS
        raise SinConexion(
            "No hay conexión a internet.\n\n"
            "Revisá que estés conectado a la red y volvé a intentar."
        ) from exc
    except requests.Timeout as exc:
        raise SinConexion(
            "El servidor está tardando demasiado en responder.\n\n"
            "Puede ser la conexión. Intentá de nuevo en un momento."
        ) from exc
    except requests.RequestException as exc:
        raise SinConexion(
            "No se pudo conectar con el servidor.\n\nIntentá de nuevo en un momento."
        ) from exc

    if resp.status_code in (401, 403):
        # Le pasa al deployment de Apps Script cuando pierde el acceso
        # "Cualquier usuario". El docente no puede hacer nada con esto, así
        # que lo importante es que sepa a quién avisarle.
        raise ApiError(
            "El servidor rechazó la conexión.\n\n"
            "Es un problema de configuración, no tuyo: avisale a Samir."
        )
    if resp.status_code >= 500:
        raise SinConexion(
            "El servidor tuvo un problema.\n\nIntentá de nuevo en un momento."
        )
    if resp.status_code != 200:
        raise ApiError(f"El servidor respondió algo inesperado (código {resp.status_code}).")

    try:
        body = resp.json()
    except ValueError as exc:
        raise ApiError("El servidor respondió algo que no se entiende.") from exc

    if not body.get("ok"):
        error = body.get("error", "Error desconocido")
        if "sesión" in error.lower() or "sesion" in error.lower():
            raise SesionExpirada(error)
        raise ApiError(error)
    return body.get("data")


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

def guardar_planeacion(token: str, datos: dict, fotos: dict) -> dict:
    """datos: fecha, grupo, objetivo, temas_vistos[], bloques[], asistencia[].
    fotos: {"foto_clase": {"base64": ..., "mimeType": "image/jpeg"}}"""
    return _call("guardar_planeacion", token, datos, fotos)


def guardar_documento_planeacion(token: str, planeacion_id: int, archivo: dict) -> dict:
    """Sube a Drive el .docx de la planeación, que es lo que el informe
    mensual enlaza en la columna «LINK A PLANEACION».

    archivo: {"base64": ..., "mimeType": ...}"""
    return _call("guardar_documento_planeacion", token, planeacion_id, archivo)


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


def editar_planeacion(token: str, id_: int, cambios: dict) -> dict:
    return _call("editar_planeacion", token, id_, cambios)


def eliminar_planeacion(token: str, id_: int) -> dict:
    """Solo el docente dueño puede eliminar su propia planeación."""
    return _call("eliminar_planeacion", token, id_)


def obtener_estado_mes(token: str, curso_id: int, mes: str) -> dict:
    """El estado va por curso, no por docente. mes en formato 'YYYY-MM'."""
    return _call("obtener_estado_mes", token, curso_id, mes)


# --- Cursos -------------------------------------------------------------------

def crear_curso(token: str, datos: dict) -> dict:
    """datos: docente_id, nombre, nucleo, edad_desde, edad_hasta. Solo directivo."""
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

def guardar_horas_gestion(token: str, datos: dict) -> dict:
    return _call("guardar_horas_gestion", token, datos)


def editar_horas_gestion(token: str, id_: int, cambios: dict) -> dict:
    """Solo el dueño puede corregir su propia hora de gestión."""
    return _call("editar_horas_gestion", token, id_, cambios)


def eliminar_horas_gestion(token: str, id_: int) -> dict:
    """Solo el dueño puede eliminar su propia hora de gestión."""
    return _call("eliminar_horas_gestion", token, id_)


def obtener_horas_gestion(token: str, directivo_id: int | None = None) -> list[dict]:
    return _call("obtener_horas_gestion", token, directivo_id)


# --- Actividades que no son clases ---------------------------------------------

def guardar_actividad(token: str, datos: dict, fotos: dict | None = None) -> dict:
    """Reuniones, claustros, informes: lo que se factura y no es una clase.
    datos: curso_id, fecha, descripcion, horas_sede, horas_externas.
    fotos: {"foto": {"base64": ..., "mimeType": ...}} — obligatoria salvo
    para directivos."""
    return _call("guardar_actividad", token, datos, fotos or {})


def editar_actividad(
    token: str, id_: int, datos: dict, fotos: dict | None = None
) -> dict:
    """Sin foto nueva se conserva la que ya tenía."""
    return _call("editar_actividad", token, id_, datos, fotos or {})


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


# --- Administración de usuarios (rol directivo) --------------------------------

def crear_usuario(token: str, datos: dict) -> dict:
    return _call("crear_usuario", token, datos)


def editar_usuario(token: str, usuario_id: int, cambios: dict) -> dict:
    """Solo rol directivo. La contraseña no se toca acá (ver cambiar_password)."""
    return _call("editar_usuario", token, usuario_id, cambios)


def listar_usuarios(token: str) -> list[dict]:
    return _call("listar_usuarios", token)


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


def reabrir_mes(token: str, curso_id: int, mes: str, abierta: bool = True) -> dict:
    """Vuelve a abrir (o cierra de nuevo) un curso y un mes puntuales."""
    return _call("reabrir_mes", token, curso_id, mes, abierta)


def obtener_dashboard_directivo(token: str, mes: str) -> list[dict]:
    return _call("obtener_dashboard_directivo", token, mes)


def ejecutar_migracion(token: str, nombre: str) -> dict:
    """Tareas de mantenimiento del esquema, solo para el administrador.
    Evita tener que abrir el editor de Apps Script en cada cambio."""
    return _call("ejecutar_migracion", token, nombre)
