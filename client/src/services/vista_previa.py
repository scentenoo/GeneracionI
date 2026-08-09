"""Genera el documento y lo abre para revisarlo antes de subirlo.

La planeación se arma con lo que hay en el formulario, sin pasar por el
backend: la idea es justamente ver qué va a quedar guardado *antes* de
guardarlo.

Los archivos van a una carpeta temporal del sistema. Son borradores para
mirar y descartar, no el entregable — ese sale del backend una vez
guardado.
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
    salida = _carpeta_temporal() / f"planeacion_{uuid.uuid4().hex[:8]}.docx"
    docx_generator.generar_planeacion_docx(contexto, foto_clase_path, salida)

    ruta, es_pdf = _a_pdf_si_se_puede(salida)
    abrir_con_el_sistema(ruta)
    return ruta, es_pdf


def previsualizar_informe(contexto: dict) -> tuple[Path, bool]:
    """Igual pero para el informe mensual, cuyo contexto ya viene armado
    desde el backend."""
    salida = _carpeta_temporal() / f"informe_{uuid.uuid4().hex[:8]}.docx"
    docx_generator.generar_informe_mensual_docx(contexto, salida)

    ruta, es_pdf = _a_pdf_si_se_puede(salida)
    abrir_con_el_sistema(ruta)
    return ruta, es_pdf
