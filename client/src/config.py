"""Configuración del cliente. No hay credenciales de Google acá — el único
secreto que maneja el cliente es la URL del backend, que ya vive detrás de
login() con su propio token (ver spec sección 2)."""

import sys
from pathlib import Path

BACKEND_URL = "https://script.google.com/macros/s/AKfycbys9dPldfgtNcO8J51jsroJkC2Ic-_qn7jkVyp_G9w0UgEjaqGH4VsN_K7bteJMEOE-/exec"

# Tiene que coincidir con lo que diga Config.version_actual en la Sheet, si
# no la app se bloquea al abrir (ver main.py).
#
# Este número sube RECIÉN cuando se va a repartir un instalador nuevo, no
# cada vez que se cambia código: subirlo antes bloquea la app —incluido el
# que corre desde el código— contra una versión que todavía no existe en
# ningún lado. El orden es: subir esto, compilar, subir el .exe a Drive, y
# recién ahí publicar desde «Versión de la app».
APP_VERSION = "1.0.0"


def _base_dir() -> Path:
    """Carpeta base de la app: la carpeta del ejecutable si está empaquetada
    con PyInstaller (sys._MEIPASS), o la raíz del repo en desarrollo."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[2]


TEMPLATES_DIR = _base_dir() / "templates"
