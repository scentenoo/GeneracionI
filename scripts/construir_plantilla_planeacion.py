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
que pasó el equipo directivo.
"""

from __future__ import annotations

import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "templates" / "planeacion_individual.docx"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _membrete_municipio import armar_membrete_  # noqa: E402


def celda_titulo(celda, texto):
    p = celda.paragraphs[0]
    r = p.add_run(texto)
    r.bold = True


def main():
    doc = Document()
    armar_membrete_(doc, "DIARIO PEDAGÓGICO", codigo_tramite="PC-PA-003-F03", version_tramite="0")

    # Encabezado clave/valor
    enc = doc.add_table(rows=4, cols=2)
    enc.style = "Table Grid"
    filas = [
        ("FECHA", "{{ fecha }}"),
        ("GRUPO", "{{ grupo }}"),
        ("OBJETIVO", "{{ objetivo }}"),
        ("TEMAS VISTOS",
         "{% for t in temas_vistos %}{{ t }}{% if not loop.last %}, {% endif %}{% endfor %}"),
    ]
    for i, (k, v) in enumerate(filas):
        celda_titulo(enc.rows[i].cells[0], k)
        enc.rows[i].cells[1].paragraphs[0].add_run(v)

    doc.add_paragraph()

    # Tabla de 3 columnas: momentos | observaciones | avances
    tres = doc.add_table(rows=2, cols=3)
    tres.style = "Table Grid"
    cabeceras = [
        "MOMENTOS DE LA CLASE Y TIEMPOS",
        "OBSERVACIONES DE CLASE QUE CONTRIBUYAN A LA FUNDAMENTACIÓN DE GENERACIÓN-I "
        "(pequeña reflexión pedagógica, incluye también lo disciplinar)",
        "AVANCES O RETROCESOS OBSERVADOS EN CLASE "
        "(se puede nombrar al estudiante, tipo evaluación cualitativa)",
    ]
    for celda, texto in zip(tres.rows[0].cells, cabeceras):
        run = celda.paragraphs[0].add_run(texto)
        run.bold = True

    # Fila de datos
    col_momentos = tres.rows[1].cells[0]
    # el primer párrafo ya existe; lo usamos para el momento inicial
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

    tres.rows[1].cells[1].paragraphs[0].add_run("{{ observaciones }}")
    tres.rows[1].cells[2].paragraphs[0].add_run("{{ avances }}")

    # Asistencia
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.add_run("ASISTENCIA").bold = True
    asis = doc.add_table(rows=1, cols=2)
    asis.style = "Table Grid"
    asis.rows[0].cells[0].paragraphs[0].add_run("Estudiante").bold = True
    asis.rows[0].cells[1].paragraphs[0].add_run("Asistió").bold = True
    fila_for = asis.add_row().cells
    fila_for[0].paragraphs[0].add_run("{%tr for a in asistencia %}")
    fila_datos = asis.add_row().cells
    fila_datos[0].paragraphs[0].add_run("{{ a.nombre }}")
    fila_datos[1].paragraphs[0].add_run("{{ a.presente }}")
    fila_endfor = asis.add_row().cells
    fila_endfor[0].paragraphs[0].add_run("{%tr endfor %}")

    # Foto
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.add_run("Evidencia fotográfica de la clase").bold = True
    pf = doc.add_paragraph()
    pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf.add_run("{{ foto_clase }}")

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(SALIDA))
    print(f"Plantilla generada en {SALIDA}")


if __name__ == "__main__":
    main()
