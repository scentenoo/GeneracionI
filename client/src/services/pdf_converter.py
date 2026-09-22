"""Conversión de .docx a .pdf. La spec pide LibreOffice headless, pero no
hay garantía de que los 18 computadores del municipio lo tengan instalado
(este mismo equipo de desarrollo no lo tiene, por ejemplo, pero sí Word).
Por eso probamos varias vías y devolvemos un error claro si ninguna sirve —
en ese caso el docente igual puede entregar el .docx.
"""

from __future__ import annotations

import contextlib
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path


class ConversionNoDisponible(Exception):
    """Ninguna vía de conversión a PDF está disponible en este equipo."""


# Una sola instancia de Word a la vez. `Dispatch("Word.Application")` se
# engancha a la instancia que ya esté abierta y el `Quit()` de una tarea
# cerraría la de la otra a mitad de trabajo — pasa en cuanto dos revisiones
# seguidas actualizan su documento al mismo tiempo.
_CANDADO_WORD = threading.Lock()


@contextlib.contextmanager
def _com_en_este_hilo():
    """COM hay que inicializarlo en CADA hilo que lo use. pywin32 solo lo
    hace solo en el hilo que importa `win32com` por primera vez: las
    conversiones y recuentos de páginas corren en hilos de fondo (uno
    distinto por tarea), así que la primera funcionaba y todas las
    siguientes fallaban con "No se ha llamado a CoInitialize" — y como
    `recalcular_campos` se traga el error, el documento quedaba subido con
    el total de páginas equivocado ("2 de 1") sin que nadie se enterara."""
    import pythoncom  # type: ignore

    pythoncom.CoInitialize()
    try:
        yield
    finally:
        pythoncom.CoUninitialize()


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
    with _CANDADO_WORD, _com_en_este_hilo():
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


def _contar_paginas_word(docx_path: Path) -> int | None:
    """Vía Word: `ComputeStatistics` da el número real de páginas sin
    necesidad de guardar nada. Se probó primero pedirle a Word que
    recalculara los campos del documento (`Fields.Update()` sobre cada
    encabezado/pie) y volviera a guardar, pero el resultado nunca quedaba
    persistido en el .docx al cerrar — Word lo muestra en pantalla pero no
    lo escribe de vuelta en el archivo. Contar acá y escribir el número a
    mano (ver `_fijar_total_paginas_`) es más confiable."""
    if sys.platform != "win32":
        return None
    try:
        import win32com.client  # type: ignore
    except ImportError:
        return None

    with _CANDADO_WORD, _com_en_este_hilo():
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        try:
            # ReadOnly: solo se cuenta, no se guarda nada — abre sin crear
            # el archivo de bloqueo y sin preguntar por conversiones.
            doc = word.Documents.Open(str(docx_path), ReadOnly=True, AddToRecentFiles=False)
            try:
                return int(doc.ComputeStatistics(2))  # wdStatisticPages
            finally:
                doc.Close(False)  # sin guardar — solo hacía falta el conteo
        finally:
            word.Quit()


def _contar_paginas_pdf_(pdf_path: Path) -> int | None:
    """Cuenta las páginas de un PDF contando sus objetos `/Type /Page`
    (sin confundirlos con `/Type /Pages`, el nodo padre) — alcanza con
    esto y evita depender de una librería de PDF que no está instalada."""
    try:
        contenido = pdf_path.read_bytes()
    except OSError:
        return None
    paginas = len(re.findall(rb"/Type\s*/Page(?!s)\b", contenido))
    return paginas or None


def _contar_paginas_libreoffice(docx_path: Path) -> int | None:
    soffice = shutil.which("soffice") or shutil.which("soffice.exe")
    if not soffice:
        return None
    with tempfile.TemporaryDirectory() as carpeta:
        subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir", carpeta, str(docx_path)],
            check=True,
            timeout=60,
        )
        pdf_path = Path(carpeta) / (docx_path.stem + ".pdf")
        return _contar_paginas_pdf_(pdf_path) if pdf_path.exists() else None


def _fijar_total_paginas_(docx_path: Path, paginas: int) -> bool:
    """Reemplaza a mano el resultado en caché del campo NUMPAGES (el
    `<w:t>` que va entre su `fldChar` "separate" y "end") por el número de
    páginas real, en cualquier encabezado/pie del documento. El campo
    PAGE se deja como está: Google Drive sí lo recalcula solo al mostrar
    cada página, es NUMPAGES el que se queda con el valor de fábrica."""
    from docx import Document
    from docx.oxml.ns import qn

    doc = Document(str(docx_path))
    cambiado = False
    for contenedor in [doc] + [s.header for s in doc.sections] + [s.footer for s in doc.sections]:
        for p in contenedor.paragraphs:
            campo = None
            resultado_pendiente = False
            for r in p.runs:
                for hijo in r._r:
                    etiqueta = hijo.tag.split("}")[-1]
                    if etiqueta == "fldChar":
                        tipo = hijo.get(qn("w:fldCharType"))
                        if tipo == "begin":
                            campo, resultado_pendiente = None, False
                        elif tipo == "separate":
                            resultado_pendiente = bool(campo) and "NUMPAGES" in campo
                        elif tipo == "end":
                            campo, resultado_pendiente = None, False
                    elif etiqueta == "instrText":
                        campo = (campo or "") + (hijo.text or "")
                    elif etiqueta == "t" and resultado_pendiente:
                        hijo.text = str(paginas)
                        resultado_pendiente = False
                        cambiado = True
    if cambiado:
        doc.save(str(docx_path))
    return cambiado


def recalcular_campos(docx_path: str | Path) -> bool:
    """Cuenta cuántas páginas tiene el documento de verdad (con Word o,
    si no hay, con LibreOffice) y deja ese número escrito en el campo
    NUMPAGES del encabezado/pie.

    Los campos de "Página X de Y" nacen sin ningún resultado calculado —
    Word los resuelve solo al abrir, imprimir o convertir a PDF, pero el
    visor web de Google Drive (el que usa el botón "Abrir" de la app)
    nunca recalcula nada: se queda con lo que haya quedado guardado en el
    archivo. Sin este paso, Drive mostraba el número de página que sí
    sabe calcular por su cuenta pero el total de páginas siempre en 1
    ("2 de 1", "3 de 1"...), porque ese sí lo saca del valor guardado.

    Devuelve si se pudo recalcular; si no hay con qué contar las páginas,
    el documento queda como estaba — se sigue pudiendo subir y abrir,
    solo que el número de página en el visor de Drive no va a ser
    exacto."""
    docx_path = Path(docx_path)
    for contar in (_contar_paginas_word, _contar_paginas_libreoffice):
        try:
            paginas = contar(docx_path)
        except Exception:
            # Igual que en docx_a_pdf: que falle el conteo no debe romper
            # el guardado, el documento ya sirve tal cual está.
            continue
        if paginas:
            return _fijar_total_paginas_(docx_path, paginas)
    return False
