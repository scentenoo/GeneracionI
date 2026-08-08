"""Conversión de .docx a .pdf. La spec pide LibreOffice headless, pero no
hay garantía de que los 18 computadores del municipio lo tengan instalado
(este mismo equipo de desarrollo no lo tiene, por ejemplo, pero sí Word).
Por eso probamos varias vías y devolvemos un error claro si ninguna sirve —
en ese caso el docente igual puede entregar el .docx.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


class ConversionNoDisponible(Exception):
    """Ninguna vía de conversión a PDF está disponible en este equipo."""


def _convertir_con_libreoffice(docx_path: Path, carpeta_salida: Path) -> Path | None:
    soffice = shutil.which("soffice") or shutil.which("soffice.exe")
    if not soffice:
        return None
    subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(carpeta_salida), str(docx_path)],
        check=True,
        timeout=60,
    )
    salida = carpeta_salida / (docx_path.stem + ".pdf")
    return salida if salida.exists() else None


def _convertir_con_word(docx_path: Path, carpeta_salida: Path) -> Path | None:
    if sys.platform != "win32":
        return None
    try:
        import win32com.client  # type: ignore
    except ImportError:
        return None

    salida = carpeta_salida / (docx_path.stem + ".pdf")
    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    try:
        doc = word.Documents.Open(str(docx_path))
        doc.SaveAs(str(salida), FileFormat=17)  # wdFormatPDF
        doc.Close()
    finally:
        word.Quit()
    return salida if salida.exists() else None


def docx_a_pdf(docx_path: str | Path, carpeta_salida: str | Path | None = None) -> Path:
    docx_path = Path(docx_path)
    carpeta_salida = Path(carpeta_salida) if carpeta_salida else docx_path.parent

    for convertir in (_convertir_con_libreoffice, _convertir_con_word):
        resultado = convertir(docx_path, carpeta_salida)
        if resultado:
            return resultado

    raise ConversionNoDisponible(
        "No se encontró LibreOffice ni Microsoft Word en este equipo para "
        "convertir a PDF. El .docx sí se generó correctamente."
    )
