"""Relleno de las plantillas docxtpl (templates/planeacion_individual.docx y
templates/informe_mensual.docx). Ver esos archivos para el contrato exacto
de variables — quedaron documentados ahí mismo al construirlos.

Esto es lógica de Samir + Claude Code (spec sección 8): las pantallas de
los niños solo deberían llamar a estas dos funciones con los datos ya
armados, nunca tocar docxtpl directamente.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

from docxtpl import DocxTemplate, InlineImage
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Mm, Pt, RGBColor

from config import TEMPLATES_DIR

PLANEACION_TEMPLATE = TEMPLATES_DIR / "planeacion_individual.docx"
INFORME_TEMPLATE = TEMPLATES_DIR / "informe_mensual.docx"
INFORME_GESTION_TEMPLATE = TEMPLATES_DIR / "informe_gestion.docx"

_IMG_WIDTH_GRANDE_MM = 90
_IMG_WIDTH_CHICA_MM = 55

# Cómo se lee cada acción del historial en la hoja final del documento.
_ACCIONES = {
    "entregado": "Entregado",
    "reenviado": "Reenviado corregido",
    "devuelto": "Devuelto para corregir",
    "aprobado": "Aprobado",
}


def _anexar_historial(ruta_salida: Path, historial: list | None) -> None:
    """Agrega al final del documento la hoja de revisión —quién lo entregó,
    quién lo devolvió y por qué, quién lo aprobó y cuándo—, como la hoja de
    auditoría del programa. Solo se agrega a un archivo que fue devuelto
    alguna vez; en uno aprobado de una no tiene nada que contar.
    """
    if not historial:
        return
    if not any(e.get("accion") == "devuelto" for e in historial):
        return

    doc = Document(str(ruta_salida))
    doc.add_page_break()

    titulo = doc.add_paragraph()
    run = titulo.add_run("Historial de revisión")
    run.bold = True
    run.font.size = Pt(14)

    sub = doc.add_paragraph()
    r = sub.add_run(
        "Registro de entregas, devoluciones y aprobación de este documento."
    )
    r.italic = True
    r.font.color.rgb = RGBColor(0x60, 0x60, 0x60)

    tabla = doc.add_table(rows=1, cols=4)
    tabla.style = "Table Grid"
    encabezados = ["Fecha", "Acción", "Responsable", "Motivo"]
    for celda, texto in zip(tabla.rows[0].cells, encabezados):
        p = celda.paragraphs[0]
        run = p.add_run(texto)
        run.bold = True

    for e in historial:
        fila = tabla.add_row().cells
        fecha = str(e.get("fecha", "")).replace("T", " ")[:16]
        fila[0].text = fecha
        fila[1].text = _ACCIONES.get(e.get("accion", ""), e.get("accion", ""))
        fila[2].text = str(e.get("autor", ""))
        fila[3].text = str(e.get("motivo", ""))

    doc.save(str(ruta_salida))


def _imagen_desde_base64(tpl: DocxTemplate, base64_str: str | None, ancho_mm: int) -> InlineImage | str:
    """Si no hay imagen (ej. todavía no se subió la firma), devuelve '' en
    vez de None — con None, docxtpl renderiza el texto literal "None"."""
    if not base64_str:
        return ""
    data = base64.b64decode(base64_str)
    return InlineImage(tpl, io.BytesIO(data), width=Mm(ancho_mm))


def generar_planeacion_docx(contexto: dict, foto_clase_path: str, ruta_salida: str | Path) -> Path:
    """contexto: fecha, grupo, objetivo, temas_vistos[], los tres momentos
    (momento_*_min/texto), observaciones, avances, asistencia[].
    foto_clase_path: ruta local a la foto ya comprimida (ver image_utils.py)."""
    tpl = DocxTemplate(str(PLANEACION_TEMPLATE))
    ctx = dict(contexto)
    ctx["foto_clase"] = InlineImage(tpl, foto_clase_path, width=Mm(_IMG_WIDTH_GRANDE_MM))
    tpl.render(ctx)

    ruta_salida = Path(ruta_salida)
    tpl.save(str(ruta_salida))
    _anexar_historial(ruta_salida, contexto.get("historial"))
    return ruta_salida


def generar_informe_mensual_docx(contexto: dict, ruta_salida: str | Path) -> Path:
    """contexto: el dict que devuelve api_client.generar_informe_mensual
    (incluye encuentros[].foto_base64 y firma_base64 como base64 crudo,
    que acá se convierten a InlineImage)."""
    tpl = DocxTemplate(str(INFORME_TEMPLATE))
    ctx = dict(contexto)

    ctx["encuentros"] = [
        {
            "nro": e["nro"],
            "asistencia": e.get("asistencia", ""),
            "foto": _imagen_desde_base64(tpl, e.get("foto_base64"), _IMG_WIDTH_CHICA_MM),
        }
        for e in contexto.get("encuentros", [])
    ]
    ctx["firma"] = _imagen_desde_base64(tpl, contexto.get("firma_base64"), 35)

    if ctx.get("es_directivo"):
        ctx["evidencias_gestion"] = [
            dict(ev, foto=_imagen_desde_base64(tpl, ev.get("foto_base64"), _IMG_WIDTH_CHICA_MM))
            for ev in contexto.get("evidencias_gestion", [])
        ]

    tpl.render(ctx)

    ruta_salida = Path(ruta_salida)
    tpl.save(str(ruta_salida))
    _anexar_historial(ruta_salida, contexto.get("historial"))
    return ruta_salida


def generar_informe_gestion_docx(contexto: dict, ruta_salida: str | Path) -> Path:
    """Informe mensual de un directivo sin curso (ver InformesGestion.js).
    Es un documento aparte del docente: solo gestión y cuenta de cobro con
    la hora directiva."""
    tpl = DocxTemplate(str(INFORME_GESTION_TEMPLATE))
    ctx = dict(contexto)
    ctx["firma"] = _imagen_desde_base64(tpl, contexto.get("firma_base64"), 35)
    tpl.render(ctx)

    ruta_salida = Path(ruta_salida)
    tpl.save(str(ruta_salida))
    _anexar_historial(ruta_salida, contexto.get("historial"))
    return ruta_salida
