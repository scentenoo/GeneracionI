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


def previsualizar_planeacion(contexto: dict, fotos_clase_paths: list[str]) -> tuple[Path, bool]:
    """Arma la planeación desde el formulario y la abre. Devuelve
    (ruta abierta, es_pdf)."""
    limpiar_borradores()
    salida = _carpeta_temporal() / f"planeacion_{uuid.uuid4().hex[:8]}.docx"
    docx_generator.generar_planeacion_docx(contexto, fotos_clase_paths, salida)

    ruta, es_pdf = _a_pdf_si_se_puede(salida)
    if es_pdf:
        # El .docx intermedio ya no sirve una vez que hay PDF.
        try:
            salida.unlink()
        except OSError:
            pass
    abrir_con_el_sistema(ruta)
    return ruta, es_pdf


def planeacion_para_subir(contexto: dict, fotos_clase_paths: list[str]) -> dict:
    """Arma el .docx de la planeación y lo devuelve listo para mandarlo.

    Es el archivo que el informe mensual enlaza en «LINK A PLANEACION»:
    una planeación vive en una fila de Sheets y no tiene URL propia, así
    que el documento se genera acá —donde están las plantillas— y se
    archiva en Drive.
    """
    import base64

    salida = _carpeta_temporal() / f"subir_{uuid.uuid4().hex[:8]}.docx"
    try:
        docx_generator.generar_planeacion_docx(contexto, fotos_clase_paths, salida)
        pdf_converter.recalcular_campos(salida)
        datos = salida.read_bytes()
    finally:
        try:
            salida.unlink()
        except OSError:
            pass

    return {
        "base64": base64.b64encode(datos).decode("ascii"),
        "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }


def planeacion_para_subir_desde_base64(contexto: dict, fotos: list[dict]) -> dict:
    """Como planeacion_para_subir pero con las fotos en base64 (las que ya
    están en Drive), para regenerar el .docx al editar una planeación. Cada
    foto se escribe a un archivo temporal porque docxtpl necesita una ruta.

    fotos: [{"base64": ..., "mimeType": ...}, ...] (1 a 3)."""
    import base64

    tmps = []
    try:
        for foto in fotos:
            ext = ".png" if "png" in (foto.get("mimeType") or "") else ".jpg"
            tmp = _carpeta_temporal() / f"foto_{uuid.uuid4().hex[:8]}{ext}"
            tmp.write_bytes(base64.b64decode(foto["base64"]))
            tmps.append(tmp)
        return planeacion_para_subir(contexto, [str(t) for t in tmps])
    finally:
        for tmp in tmps:
            try:
                tmp.unlink()
            except OSError:
                pass


def informe_para_subir(contexto: dict) -> dict:
    """Arma el .docx del informe mensual y lo devuelve listo para archivarlo
    en Drive, igual que planeacion_para_subir."""
    import base64

    salida = _carpeta_temporal() / f"subir_informe_{uuid.uuid4().hex[:8]}.docx"
    try:
        docx_generator.generar_informe_mensual_docx(contexto, salida)
        pdf_converter.recalcular_campos(salida)
        datos = salida.read_bytes()
    finally:
        try:
            salida.unlink()
        except OSError:
            pass

    return {
        "base64": base64.b64encode(datos).decode("ascii"),
        "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }


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


def previsualizar_informe_gestion(contexto: dict) -> tuple[Path, bool]:
    """Vista previa del informe de gestión de un directivo sin curso."""
    limpiar_borradores()
    salida = _carpeta_temporal() / f"gestion_{uuid.uuid4().hex[:8]}.docx"
    docx_generator.generar_informe_gestion_docx(contexto, salida)

    ruta, es_pdf = _a_pdf_si_se_puede(salida)
    if es_pdf:
        try:
            salida.unlink()
        except OSError:
            pass
    abrir_con_el_sistema(ruta)
    return ruta, es_pdf
