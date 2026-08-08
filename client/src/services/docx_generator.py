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
from docx.shared import Mm

from config import TEMPLATES_DIR

PLANEACION_TEMPLATE = TEMPLATES_DIR / "planeacion_individual.docx"
INFORME_TEMPLATE = TEMPLATES_DIR / "informe_mensual.docx"

_IMG_WIDTH_GRANDE_MM = 90
_IMG_WIDTH_CHICA_MM = 55


def _imagen_desde_base64(tpl: DocxTemplate, base64_str: str | None, ancho_mm: int) -> InlineImage | None:
    if not base64_str:
        return None
    data = base64.b64decode(base64_str)
    return InlineImage(tpl, io.BytesIO(data), width=Mm(ancho_mm))


def generar_planeacion_docx(contexto: dict, foto_clase_path: str, ruta_salida: str | Path) -> Path:
    """contexto: fecha, grupo, objetivo, temas_vistos[], bloques[], asistencia[].
    foto_clase_path: ruta local a la foto ya comprimida (ver image_utils.py)."""
    tpl = DocxTemplate(str(PLANEACION_TEMPLATE))
    ctx = dict(contexto)
    ctx["foto_clase"] = InlineImage(tpl, foto_clase_path, width=Mm(_IMG_WIDTH_GRANDE_MM))
    tpl.render(ctx)

    ruta_salida = Path(ruta_salida)
    tpl.save(str(ruta_salida))
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
    return ruta_salida
