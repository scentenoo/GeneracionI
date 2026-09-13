"""Genera templates/certificado_pago.docx: el certificado mensual de horas
de docencia para pago del operador — solo lo generan administradores (ver
Certificados.js#generar_certificado_pago para el contrato de variables).

    python scripts/construir_plantilla_certificado.py

Copia el certificado real que pasó el equipo directivo tal cual: mismo
membrete (CÓDIGO PC-PA-003-F03, VERSIÓN 0 — el mismo código que el Diario
Pedagógico; no hay otro documentado para este trámite) pero con el correo
de Secretaría de Educación en vez del de Gobierno, fuente Arial en vez de
Calibri (así sale en el original, a diferencia de la planeación) y sin
`_fijar_fuente` de sobra: python-docx ya cae en Cambria si no se fija nada,
así que igual hay que fijarla acá.

El nombre de la Secretaria de Educación y el de la empresa contratista van
fijos (son institucionales, no cambian mes a mes) — si algún día cambian de
titular, se edita este script y se corre de nuevo.
"""

from __future__ import annotations

import sys
from pathlib import Path

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "templates" / "certificado_pago.docx"

FUENTE = "Arial"
GRIS_ENCABEZADO = "D9D9D9"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _membrete_municipio import _CORREO_EDUCACION, armar_membrete_  # noqa: E402


def _sombrear_celda(celda, color_hex=GRIS_ENCABEZADO):
    tcPr = celda._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color_hex)
    tcPr.append(shd)


def _ancho_columnas(tabla, anchos):
    tabla.autofit = False
    for col, ancho in zip(tabla.columns, anchos):
        col.width = ancho
    for fila in tabla.rows:
        for celda, ancho in zip(fila.cells, anchos):
            celda.width = ancho


def _fijar_fuente(doc, nombre=FUENTE):
    """Mismo problema que en construir_plantilla_planeacion.py: sin esto
    el texto sin run propio hereda Cambria (con serifa) del tema de Word,
    en vez de la fuente sin serifa del certificado real. No toca un run que
    ya tenga su propia fuente puesta a mano (el membrete institucional y el
    pie de página van siempre en Century Gothic, sin importar la fuente del
    cuerpo — ver _FUENTE_INSTITUCION en _membrete_municipio.py)."""

    def en_parrafos(parrafos):
        for p in parrafos:
            for r in p.runs:
                if r.font.name is None:
                    r.font.name = nombre

    def en_tablas(tablas):
        for tabla in tablas:
            for fila in tabla.rows:
                for celda in fila.cells:
                    en_parrafos(celda.paragraphs)
                    en_tablas(celda.tables)

    contenedores = [doc] + [s.header for s in doc.sections] + [s.footer for s in doc.sections]
    for contenedor in contenedores:
        en_parrafos(contenedor.paragraphs)
        en_tablas(contenedor.tables)

    doc.styles["Normal"].font.name = nombre


def main():
    doc = Document()
    # Márgenes de 2cm parejos (el certificado real los usa así, en carta
    # US no A4) — con los márgenes por defecto de python-docx (1 pulgada)
    # el ancho útil quedaba más angosto que el del original y todo se veía
    # más apretado de lo que debía.
    for seccion in doc.sections:
        seccion.left_margin = Cm(2)
        seccion.right_margin = Cm(2)
        seccion.top_margin = Cm(2)
        seccion.bottom_margin = Cm(2)

    armar_membrete_(
        doc, "CERTIFICADO", codigo_tramite="PC-PA-003-F03", version_tramite="0",
        correo=_CORREO_EDUCACION,
    )

    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run("LA SECRETARÍA DE EDUCACIÓN").bold = True
    doc.add_paragraph()
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run("CERTIFICA").bold = True
    doc.add_paragraph()

    # Justificado (no alineado a la izquierda): así sale en el original,
    # se nota en el margen derecho parejo de la primera línea.
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.add_run("Que, la empresa ")
    p.add_run("DIDÁCTICAS ELECTRÓNICAS").bold = True
    p.add_run(
        " realizó actividades de docencia en los siguientes grupos y con los docentes que "
        "paso a citar durante el mes de {{ mes_nombre }} del {{ anio }}."
    )

    p = doc.add_paragraph(
        "Realizaron un total de {{ total_horas }} horas de docencia efectivas para el "
        "municipio, con base en soportes que tuve a la vista así: "
    )
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    doc.add_paragraph()
    # Guión a mano en vez de un bullet real de Word: en el original el
    # marcador de la lista es un guión, no el círculo que trae por
    # defecto el estilo "List Bullet" — con esto se ve igual sin tener que
    # armar una numeración custom en el XML para un resultado idéntico.
    for item in (
        "Programas de curso y/o plan de trabajo",
        "Planeaciones académicas",
        "Informes con Registros fotográficos y enlaces",
    ):
        p_item = doc.add_paragraph()
        p_item.paragraph_format.left_indent = Cm(0.6)
        p_item.paragraph_format.space_after = Pt(0)
        p_item.add_run(f"- {item}")
    doc.add_paragraph()

    # Tabla de instructores: encabezado (gris) + fila-for + fila-datos +
    # fila-endfor + TOTAL. El for y el endfor van en filas separadas de la
    # tabla o docxtpl tira "unknown tag 'endfor'" (ver otros construir_*).
    tabla = doc.add_table(rows=4, cols=6)
    tabla.style = "Table Grid"
    _ancho_columnas(tabla, [Cm(4), Cm(2.6), Cm(2.6), Cm(3.6), Cm(3.2), Cm(2)])

    encabezados = ["INSTRUCTOR", "CÉDULA", "TELÉFONO", "FORMACIÓN", "CURSO", "Horas"]
    for celda, texto in zip(tabla.rows[0].cells, encabezados):
        run = celda.paragraphs[0].add_run(texto)
        run.bold = True
        celda.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        celda.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        _sombrear_celda(celda)

    fila_for = tabla.rows[1].cells
    fila_for[0].paragraphs[0].add_run("{%tr for f in filas %}")

    # Docente/cédula/teléfono/formación abajo, curso/horas al medio: así
    # sale en el original — si la formación de alguien ocupa varias líneas,
    # el resto de sus datos queda a la altura de la última en vez de
    # colgando arriba, y curso/horas quedan centrados en la fila entera.
    fila_datos = tabla.rows[2].cells
    fila_datos[0].paragraphs[0].add_run("{{ f.docente }}")
    fila_datos[1].paragraphs[0].add_run("{{ f.cedula }}")
    fila_datos[2].paragraphs[0].add_run("{{ f.telefono }}")
    fila_datos[3].paragraphs[0].add_run("{{ f.formacion }}")
    fila_datos[4].paragraphs[0].add_run("{{ f.curso }}")
    fila_datos[5].paragraphs[0].add_run("{{ f.horas }}")
    for celda in fila_datos[:4]:
        celda.vertical_alignment = WD_ALIGN_VERTICAL.BOTTOM
    for celda in fila_datos[4:]:
        celda.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

    fila_endfor = tabla.rows[3].cells
    fila_endfor[0].paragraphs[0].add_run("{%tr endfor %}")

    fila_total = tabla.add_row().cells
    celda_total = fila_total[0].merge(fila_total[1]).merge(fila_total[2]).merge(fila_total[3]).merge(fila_total[4])
    p_total = celda_total.paragraphs[0]
    p_total.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_total.add_run("TOTAL DE HORAS").bold = True
    _sombrear_celda(celda_total)
    p_valor_total = fila_total[5].paragraphs[0]
    p_valor_total.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_valor_total.add_run("{{ total_horas }}").bold = True
    _sombrear_celda(fila_total[5])

    # 10pt y no el tamaño normal del cuerpo (11pt): con 18 instructores
    # reales, muchos con nombre/formación largos, a 11pt se ve grande y
    # envuelve de más — 10pt es lo que de verdad entra prolijo en las
    # columnas sin que la tabla quede desproporcionada al resto del texto.
    for fila in tabla.rows:
        for celda in fila.cells:
            for p in celda.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(10)

    doc.add_paragraph()
    doc.add_paragraph("Cordialmente,")
    doc.add_paragraph()
    doc.add_paragraph()
    doc.add_paragraph()
    doc.add_paragraph("MARLENY DEL CARMEN LONDOÑO PEÑA").runs[0].bold = True
    doc.add_paragraph("SECRETARIA DE EDUCACIÓN")
    doc.add_paragraph()

    # Tabla de firmas: encabezado + fila fija (el certificado siempre lo
    # elabora y revisa la misma Secretaria) + fila de la nota legal, fundida
    # en las 4 columnas.
    firmas = doc.add_table(rows=3, cols=4)
    firmas.style = "Table Grid"
    _ancho_columnas(firmas, [Cm(3.5), Cm(6.5), Cm(4), Cm(3)])
    for celda, texto in zip(firmas.rows[0].cells, ("", "NOMBRE Y CARGO", "FIRMA", "FECHA")):
        run = celda.paragraphs[0].add_run(texto)
        run.bold = True
        celda.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

    firmas.rows[1].cells[0].paragraphs[0].add_run("Elaboró y revisó ")
    celda_nombre = firmas.rows[1].cells[1]
    celda_nombre.paragraphs[0].add_run("Esp. Marleny del Carmen Londoño Peña")
    celda_nombre.add_paragraph("Secretaria de Educación y Desarrollo Social")
    # Firma (celda 2) queda en blanco a propósito: es donde se firma a mano
    # sobre el impreso o sobre el .docx ya editado.
    firmas.rows[1].cells[3].paragraphs[0].add_run("{{ fecha_emision }}")

    celda_nota = firmas.rows[2].cells[0]
    for otra in firmas.rows[2].cells[1:]:
        celda_nota = celda_nota.merge(otra)
    celda_nota.paragraphs[0].add_run(
        "Los arriba firmantes declaramos que hemos revisado el documento y lo encontramos "
        "ajustado a las normas y disposiciones legales vigentes y, por lo tanto, bajo nuestra "
        "responsabilidad lo presentamos para la firma."
    )

    # Toda la tabla de firmas va en 8pt en el original, bastante más chica
    # que el resto del documento (11pt) — sin fijarla acá queda al tamaño
    # normal y se ve desproporcionadamente grande al lado de todo lo demás.
    for fila in firmas.rows:
        for celda in fila.cells:
            for p in celda.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(8)

    _fijar_fuente(doc)

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(SALIDA))
    print(f"Plantilla generada en {SALIDA}")


if __name__ == "__main__":
    main()
