"""Configuración del cliente. No hay credenciales de Google acá — el único
secreto que maneja el cliente es la URL del backend, que ya vive detrás de
login() con su propio token (ver spec sección 2)."""

import os
import sys
from pathlib import Path

_URL_PRODUCCION = "https://script.google.com/macros/s/AKfycbys9dPldfgtNcO8J51jsroJkC2Ic-_qn7jkVyp_G9w0UgEjaqGH4VsN_K7bteJMEOE-/exec"

# Para probar contra un deployment de Apps Script aparte (Sheet y carpeta de
# Drive de prueba, sin tocar los datos reales) sin editar este archivo:
#   set GENERACIONI_BACKEND_URL=https://script.google.com/macros/s/.../exec
BACKEND_URL = os.environ.get("GENERACIONI_BACKEND_URL") or _URL_PRODUCCION

# La versión de esta copia de la app. Al abrir se compara contra lo que
# diga la Sheet (ver main.py): por debajo de la mínima obligatoria queda
# bloqueada, entre la mínima y la vigente solo avisa.
#
# Este número sube RECIÉN cuando se va a repartir un instalador nuevo, no
# cada vez que se cambia código. El orden es: subir esto, compilar, subir
# el .exe a Drive, y recién ahí publicar desde «Versión de la app».
APP_VERSION = "1.1.6"


def comparar_versiones(a: str, b: str) -> int:
    """-1 si a < b, 0 si iguales, 1 si a > b. Compara por número, no por
    texto: como cadena '1.10.0' < '1.9.0', y eso bloquearía justo a quien
    sí actualizó."""
    def partes(v: str) -> list[int]:
        nums = []
        for p in str(v).split("."):
            try:
                nums.append(int(p))
            except ValueError:
                nums.append(0)
        return nums

    pa, pb = partes(a), partes(b)
    for i in range(max(len(pa), len(pb))):
        x = pa[i] if i < len(pa) else 0
        y = pb[i] if i < len(pb) else 0
        if x != y:
            return -1 if x < y else 1
    return 0


def _base_dir() -> Path:
    """Carpeta base de la app: la carpeta del ejecutable si está empaquetada
    con PyInstaller (sys._MEIPASS), o la raíz del repo en desarrollo."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[2]


TEMPLATES_DIR = _base_dir() / "templates"
DICCIONARIO_DIR = _base_dir() / "client" / "assets" / "diccionario"
