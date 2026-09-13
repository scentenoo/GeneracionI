"""Genera templates/planeacion_individual.docx con el formato Diario
Pedagógico del programa (PC-PA-003-F03).

La clase va en tres momentos —inicial, desarrollo y final— en una columna,
y las columnas de Observaciones y Avances son una sola por clase. Ver el
contrato de variables en client/src/ui/planeacion_screen._contexto_documento.

    python scripts/construir_plantilla_planeacion.py

Cuidado con los {%tr ...%} de la tabla de asistencia: el for y el endfor
van en filas SEPARADAS, o docxtpl tira "unknown tag 'endfor'".

El membrete (encabezado y pie de página) sale de _membrete_municipio.py,
compartido con construir_plantilla_gestion.py. Acá copia el formato oficial
real —CÓDIGO PC-PA-003-F03, VERSIÓN 0— comparado contra un documento real
que pasó el equipo directivo (10-08-26.docx): encabezado y momentos van en
UNA sola tabla continua (no dos tablas con un salto en el medio, que
quedaba desalineado) y la asistencia/fotos van en recuadros con borde,
igual que ese documento real. También esa comparación mostró que, sin
fijar la fuente a mano, el texto sale en la fuente "menor" del tema de
Word (Cambria, con serifa) en vez de la fuente sin serifa del resto de
documentos del programa — de ahí _fijar_fuente al final.
"""

from __future__ import annotations

import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "templates" / "planeacion_individual.docx"

FUENTE = "Calibri"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _membrete_municipio import armar_membrete_  # noqa: E402


def celda_titulo(celda, texto):
    p = celda.paragraphs[0]
    r = p.add_run(texto)
    r.bold = True


def _ancho_columnas(tabla, anchos):
    """python-docx necesita el ancho puesto en la columna Y en cada celda
    de cada fila — con solo `tabla.columns[i].width` Word igual autoajusta
    y las columnas quedan destimbaladas entre esta tabla y la de al lado."""
    tabla.autofit = False
    for col, ancho in zip(tabla.columns, anchos):
        col.width = ancho
    for fila in tabla.rows:
        for celda, ancho in zip(fila.cells, anchos):
            celda.width = ancho


_ANCHO_PAGINA = Cm(18)


def _recuadro(doc, texto=None):
    """Recuadro con borde propio (una tabla de 1x1) del ancho de toda la
    página — el mismo recurso visual que el documento real usa para
    "Lista de asistencia" y "Evidencia fotográfica", en vez de un párrafo
    suelto. Sin el ancho explícito la tabla nace angosta (autofit por
    contenido) y las fotos de la evidencia, en vez de entrar una al lado
    de la otra, se apilan y se salen de la página."""
    caja = doc.add_table(rows=1, cols=1)
    caja.style = "Table Grid"
    _ancho_columnas(caja, [_ANCHO_PAGINA])
    if texto is not None:
        p = caja.rows[0].cells[0].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(texto)
        r.bold = True
        r.italic = True
    return caja


def _fijar_fuente(doc, nombre=FUENTE):
    """Sin esto, cualquier texto que no pase por un run con fuente propia
    hereda la fuente "menor" del tema de Word (Cambria, con serifa) en vez
    de una fuente sin serifa — se nota fuerte comparado con el resto de
    documentos del programa. Recorre cuerpo, encabezado y pie, tablas
    incluidas (y tablas anidadas, por si alguna celda llega a tener una).
    No toca un run que ya tenga su propia fuente puesta a mano (el
    membrete institucional y el pie de página van siempre en Century
    Gothic — ver _FUENTE_INSTITUCION en _membrete_municipio.py)."""

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
    armar_membrete_(doc, "DIARIO PEDAGÓGICO", codigo_tramite="PC-PA-003-F03", version_tramite="0")

    # Encabezado clave/valor + momentos/observaciones/avances: UNA sola
    # tabla continua de 3 columnas iguales (como en el documento real), no
    # dos tablas separadas por un párrafo — así los bordes quedan
    # alineados entre las dos secciones en vez de desentonar.
    tabla = doc.add_table(rows=6, cols=3)
    tabla.style = "Table Grid"
    _ancho_columnas(tabla, [Cm(6), Cm(6), Cm(6)])

    filas_kv = [
        ("FECHA", "{{ fecha }}"),
        ("GRUPO", "{{ grupo }}"),
        ("OBJETIVO", "{{ objetivo }}"),
        ("TEMAS VISTOS",
         "{% for t in temas_vistos %}{{ t }}{% if not loop.last %}, {% endif %}{% endfor %}"),
    ]
    for i, (k, v) in enumerate(filas_kv):
        celda_titulo(tabla.rows[i].cells[0], k)
        valor = tabla.rows[i].cells[1].merge(tabla.rows[i].cells[2])
        valor.paragraphs[0].add_run(v)

    cabeceras = [
        "MOMENTOS DE LA CLASE Y TIEMPOS",
        "OBSERVACIONES DE CLASE QUE CONTRIBUYAN A LA FUNDAMENTACIÓN DE GENERACIÓN-I "
        "(pequeña reflexión pedagógica, incluye también lo disciplinar)",
        "AVANCES O RETROCESOS OBSERVADOS EN CLASE "
        "(se puede nombrar al estudiante, tipo evaluación cualitativa)",
    ]
    fila_cabecera = tabla.rows[4]
    for celda, texto in zip(fila_cabecera.cells, cabeceras):
        run = celda.paragraphs[0].add_run(texto)
        run.bold = True

    fila_datos = tabla.rows[5]
    col_momentos = fila_datos.cells[0]
    momentos = [
        ("Momento inicial", "{{ momento_inicial_min }}", "{{ momento_inicial_texto }}"),
        ("Momento de desarrollo", "{{ momento_desarrollo_min }}", "{{ momento_desarrollo_texto }}"),
        ("Momento final", "{{ momento_final_min }}", "{{ momento_final_texto }}"),
    ]
    primero = True
    for etiqueta, min_ph, texto_ph in momentos:
        p_tit = col_momentos.paragraphs[0] if primero else col_momentos.add_paragraph()
        primero = False
        run = p_tit.add_run(f"{etiqueta} ({min_ph} minutos)")
        run.bold = True
        col_momentos.add_paragraph(texto_ph)
        col_momentos.add_paragraph("")

    fila_datos.cells[1].paragraphs[0].add_run("{{ observaciones }}")
    fila_datos.cells[2].paragraphs[0].add_run("{{ avances }}")

    # Evidencias: un solo título y, debajo, un recuadro por cada evidencia
    # (asistencia, fotos) — igual que el documento real, en vez de títulos
    # sueltos sin borde.
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.add_run("EVIDENCIAS (ASISTENCIA Y FOTOS DE LA CLASE)").bold = True

    _recuadro(doc, "Lista de asistencia")
    asis = doc.add_table(rows=1, cols=2)
    asis.style = "Table Grid"
    _ancho_columnas(asis, [Cm(9), Cm(9)])
    asis.rows[0].cells[0].paragraphs[0].add_run("Estudiante").bold = True
    asis.rows[0].cells[1].paragraphs[0].add_run("Asistió").bold = True
    fila_for = asis.add_row().cells
    fila_for[0].paragraphs[0].add_run("{%tr for a in asistencia %}")
    fila_datos_asis = asis.add_row().cells
    fila_datos_asis[0].paragraphs[0].add_run("{{ a.nombre }}")
    fila_datos_asis[1].paragraphs[0].add_run("{{ a.presente }}")
    fila_endfor = asis.add_row().cells
    fila_endfor[0].paragraphs[0].add_run("{%tr endfor %}")

    # Fotos (1 a 3): un solo run con el for/endfor adentro, para que
    # docxtpl no lo vea partido entre runs distintos (eso rompería el tag,
    # igual que con la tabla de asistencia de más arriba).
    doc.add_paragraph()
    _recuadro(doc, "Evidencia fotográfica")
    caja_fotos = _recuadro(doc)
    pf = caja_fotos.rows[0].cells[0].paragraphs[0]
    pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf.add_run("{% for foto in fotos_clase %}{{ foto }} {% endfor %}")

    _fijar_fuente(doc)

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(SALIDA))
    print(f"Plantilla generada en {SALIDA}")


if __name__ == "__main__":
    main()
