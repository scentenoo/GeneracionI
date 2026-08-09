"""Genera el documento y lo abre para revisarlo antes de subirlo.

La planeación se arma con lo que hay en el formulario, sin pasar por el
backend: la idea es justamente ver qué va a quedar guardado *antes* de
guardarlo.

Los borradores van a una carpeta temporal del sistema y se limpian solos:
llevan nombres de estudiantes, la asistencia del día y la foto de la
clase, así que no tienen por qué quedar acumulándose en el disco después
de mirarlos. Cada vez que se genera uno nuevo se borran los anteriores.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from services import docx_generator, pdf_converter


def _carpeta_temporal() -> Path:
    carpeta = Path(tempfile.gettempdir()) / "generacion-i-vistas-previas"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def limpiar_borradores(excepto: Path | None = None):
    """Borra las vistas previas anteriores.

    Se llama antes de generar una nueva y al cerrar la app. Si un archivo
    sigue abierto en el visor, Windows no deja borrarlo — se ignora y se
    limpia en la próxima pasada.
    """
    for archivo in _carpeta_temporal().glob("*"):
        if excepto is not None and archivo == excepto:
            continue
        try:
            archivo.unlink()
        except OSError:
            pass


def abrir_con_el_sistema(ruta: Path):
    """Abre el archivo con el visor que tenga configurado el usuario."""
    if sys.platform == "win32":
        os.startfile(str(ruta))  # noqa: S606 — es un archivo que acabamos de generar
    elif sys.platform == "darwin":
        subprocess.run(["open", str(ruta)], check=False)
    else:
        subprocess.run(["xdg-open", str(ruta)], check=False)


def _a_pdf_si_se_puede(docx_path: Path) -> tuple[Path, bool]:
    """Devuelve (ruta a abrir, es_pdf). Si el equipo no tiene con qué
    convertir, se abre el .docx, que igual sirve para revisar."""
    try:
        return pdf_converter.docx_a_pdf(docx_path), True
    except pdf_converter.ConversionNoDisponible:
        return docx_path, False
    except Exception:
        # Word o LibreOffice pueden fallar por mil razones (una instancia
        # colgada, un permiso). No vale la pena romper la vista previa.
        return docx_path, False


def previsualizar_planeacion(contexto: dict, foto_clase_path: str) -> tuple[Path, bool]:
    """Arma la planeación desde el formulario y la abre. Devuelve
    (ruta abierta, es_pdf)."""
    limpiar_borradores()
    salida = _carpeta_temporal() / f"planeacion_{uuid.uuid4().hex[:8]}.docx"
    docx_generator.generar_planeacion_docx(contexto, foto_clase_path, salida)

    ruta, es_pdf = _a_pdf_si_se_puede(salida)
    if es_pdf:
        # El .docx intermedio ya no sirve una vez que hay PDF.
        try:
            salida.unlink()
        except OSError:
            pass
    abrir_con_el_sistema(ruta)
    return ruta, es_pdf


def previsualizar_informe(contexto: dict) -> tuple[Path, bool]:
    """Igual pero para el informe mensual, cuyo contexto ya viene armado
    desde el backend."""
    limpiar_borradores()
    salida = _carpeta_temporal() / f"informe_{uuid.uuid4().hex[:8]}.docx"
    docx_generator.generar_informe_mensual_docx(contexto, salida)

    ruta, es_pdf = _a_pdf_si_se_puede(salida)
    if es_pdf:
        try:
            salida.unlink()
        except OSError:
            pass
    abrir_con_el_sistema(ruta)
    return ruta, es_pdf
