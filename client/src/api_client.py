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


def _call(action: str, *params):
    try:
        resp = requests.post(
            BACKEND_URL,
            json={"action": action, "params": list(params)},
            timeout=_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise ApiError(f"No se pudo conectar con el servidor: {exc}") from exc

    body = resp.json()
    if not body.get("ok"):
        error = body.get("error", "Error desconocido")
        if "sesión" in error.lower() or "sesion" in error.lower():
            raise SesionExpirada(error)
        raise ApiError(error)
    return body.get("data")


def version_actual() -> str:
    return _call("version_actual")


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


def obtener_planeaciones(token: str, docente_id: int | None = None) -> list[dict]:
    return _call("obtener_planeaciones", token, docente_id)


def editar_planeacion(token: str, id_: int, cambios: dict) -> dict:
    return _call("editar_planeacion", token, id_, cambios)


def eliminar_planeacion(token: str, id_: int) -> dict:
    """Solo el docente dueño puede eliminar su propia planeación."""
    return _call("eliminar_planeacion", token, id_)


def obtener_estado_mes(token: str, docente_id: int | None, mes: str) -> dict:
    """mes en formato 'YYYY-MM'."""
    return _call("obtener_estado_mes", token, docente_id, mes)


# --- Estudiantes / grupo ------------------------------------------------------

def importar_estudiantes(token: str, docente_id: int, csv_texto: str) -> dict:
    return _call("importar_estudiantes", token, docente_id, csv_texto)


def obtener_estudiantes(token: str, docente_id: int | None = None) -> list[dict]:
    return _call("obtener_estudiantes", token, docente_id)


def modificar_grupo(token: str, docente_id: int, cambios: dict) -> dict:
    """cambios: {"agregar": [{"nombre": ...}], "quitar": [id, ...]}"""
    return _call("modificar_grupo", token, docente_id, cambios)


# --- Horas de gestión (rol directivo) -----------------------------------------

def guardar_horas_gestion(token: str, datos: dict) -> dict:
    return _call("guardar_horas_gestion", token, datos)


def obtener_horas_gestion(token: str, directivo_id: int | None = None) -> list[dict]:
    return _call("obtener_horas_gestion", token, directivo_id)


# --- Informes ------------------------------------------------------------------

def generar_informe_mensual(
    token: str,
    docente_id: int | None,
    mes: str,
    narrativa: dict,
    gestion_narrativa: dict | None = None,
) -> dict:
    """Devuelve el contexto JSON listo para rellenar con docxtpl
    (ver client/src/services/docx_generator.py)."""
    return _call(
        "generar_informe_mensual", token, docente_id, mes, narrativa, gestion_narrativa or {}
    )


# --- Administración de usuarios (rol directivo) --------------------------------

def crear_usuario(token: str, datos: dict) -> dict:
    return _call("crear_usuario", token, datos)


def listar_usuarios(token: str) -> list[dict]:
    return _call("listar_usuarios", token)


def subir_firma(token: str, usuario_id: int, imagen: dict) -> dict:
    return _call("subir_firma", token, usuario_id, imagen)


def obtener_dashboard_directivo(token: str, mes: str) -> list[dict]:
    return _call("obtener_dashboard_directivo", token, mes)
