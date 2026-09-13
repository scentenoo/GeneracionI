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
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor

from config import TEMPLATES_DIR

PLANEACION_TEMPLATE = TEMPLATES_DIR / "planeacion_individual.docx"
INFORME_TEMPLATE = TEMPLATES_DIR / "informe_mensual.docx"
INFORME_GESTION_TEMPLATE = TEMPLATES_DIR / "informe_gestion.docx"
CERTIFICADO_PAGO_TEMPLATE = TEMPLATES_DIR / "certificado_pago.docx"

_IMG_WIDTH_GRANDE_MM = 90
_IMG_WIDTH_CHICA_MM = 55

# Ancho de cada foto de clase según cuántas haya (1 a 3), para que entren
# en una sola fila del documento sin pasarse del margen de la página.
_ANCHO_FOTO_CLASE_MM = {1: _IMG_WIDTH_GRANDE_MM, 2: 75, 3: 55}

# Cómo se lee cada acción del historial en la hoja final del documento.
_ACCIONES = {
    "entregado": "Entregado",
    "actualizado": "Actualizado",
    "reenviado": "Reenviado corregido",
    "devuelto": "Devuelto para corregir",
    "aprobado": "Aprobado",
}


def _agregar_bordes_tabla(tabla) -> None:
    """Bordes finos en toda la tabla, puestos a mano en el XML en vez de con
    `tabla.style = "Table Grid"` — ese nombre de estilo solo existe si la
    plantilla .docx ya lo usó alguna vez (Word los agrega recién al primer
    uso); informe_mensual.docx no lo tenía y eso tiraba
    KeyError: no style with name 'Table Grid' justo al final, después de
    armar todo el resto del documento."""
    tblPr = tabla._tbl.tblPr
    bordes = OxmlElement("w:tblBorders")
    for lado in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{lado}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "999999")
        bordes.append(el)
    tblPr.append(bordes)


def _anexar_historial(ruta_salida: Path, historial: list | None) -> None:
    """Agrega al final del documento la hoja de auditoría —quién lo
    entregó, quién lo devolvió y por qué, quién lo aprobó y cuándo—, pedida
    por dirección para que quede en TODOS los documentos (no solo los que
    se devolvieron alguna vez): un registro completo de principio a fin,
    aunque se haya aprobado a la primera."""
    if not historial:
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
    _agregar_bordes_tabla(tabla)
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


def generar_planeacion_docx(
    contexto: dict, fotos_clase_paths: list[str], ruta_salida: str | Path
) -> Path:
    """contexto: fecha, grupo, objetivo, temas_vistos[], los tres momentos
    (momento_*_min/texto), observaciones, avances, asistencia[].
    fotos_clase_paths: 1 a 3 rutas locales a fotos ya comprimidas (ver
    image_utils.py)."""
    tpl = DocxTemplate(str(PLANEACION_TEMPLATE))
    ctx = dict(contexto)
    ancho = _ANCHO_FOTO_CLASE_MM.get(len(fotos_clase_paths), _IMG_WIDTH_CHICA_MM)
    ctx["fotos_clase"] = [InlineImage(tpl, p, width=Mm(ancho)) for p in fotos_clase_paths]
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


def generar_certificado_pago_docx(contexto: dict, ruta_salida: str | Path) -> Path:
    """Certificado mensual de horas de docencia para pago (ver
    Certificados.js#generar_certificado_pago) — solo administradores. Sin
    historial de revisión: no es un documento que se apruebe o devuelva."""
    tpl = DocxTemplate(str(CERTIFICADO_PAGO_TEMPLATE))
    tpl.render(dict(contexto))

    ruta_salida = Path(ruta_salida)
    tpl.save(str(ruta_salida))
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
