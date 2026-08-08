"""Configuración del cliente. No hay credenciales de Google acá — el único
secreto que maneja el cliente es la URL del backend, que ya vive detrás de
login() con su propio token (ver spec sección 2)."""

import sys
from pathlib import Path

BACKEND_URL = "https://script.google.com/macros/s/AKfycbys9dPldfgtNcO8J51jsroJkC2Ic-_qn7jkVyp_G9w0UgEjaqGH4VsN_K7bteJMEOE-/exec"

APP_VERSION = "1.0.0"


def _base_dir() -> Path:
    """Carpeta base de la app: la carpeta del ejecutable si está empaquetada
    con PyInstaller (sys._MEIPASS), o la raíz del repo en desarrollo."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[2]


TEMPLATES_DIR = _base_dir() / "templates"
