"""Deja al día, en el .docx ya archivado en Drive, la hoja de "Historial de
revisión" cuando alguien aprueba o devuelve una planeación o un informe.

La revisión en sí (el estado) queda guardada en la Sheet apenas contesta el
backend; esto es lo que hace que el DOCUMENTO también lo refleje enseguida,
sin esperar a que el docente lo edite o lo reenvíe. Corre en un hilo de
fondo, aparte de la revisión: quien revisa ve el estado nuevo al instante y
sigue con la siguiente, mientras el documento se actualiza atrás.

Lo que tarda (de más a menos, medido): abrir Word para recontar páginas
(~6 s, ahora casi siempre se evita — ver docx_generator.actualizar_historial_docx),
subir el archivo y bajarlo. Por eso se baja UNA vez, se cambia solo la última
hoja (no se rearma el documento ni se vuelven a bajar las fotos) y se sube
pisando el mismo archivo de Drive.
"""

from __future__ import annotations

import base64
import io
import tempfile
import threading
from pathlib import Path
from typing import Callable

import api_client
from services import docx_generator, pdf_converter

_MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# Las revisiones (cambio de estado) se mandan de a una: dos pedidos de
# escritura simultáneos a Apps Script son justo donde a veces contesta con
# la respuesta de OTRO (ver _una_llamada en api_client). Cada una tarda ~2 s,
# así que revisar varias seguidas no se siente lento.
candado_revision = threading.Lock()

# Un candado por documento: dos revisiones seguidas del MISMO documento
# actualizan su hoja una después de la otra, así la segunda parte del archivo
# que dejó la primera y no lo pisa con una versión vieja.
_candados_doc: dict[str, threading.Lock] = {}
_candados_doc_guarda = threading.Lock()


def _candado_de(clave: str) -> threading.Lock:
    with _candados_doc_guarda:
        return _candados_doc.setdefault(clave, threading.Lock())


def _sincronizar(
    clave: str,
    obtener: Callable[[], dict | None],
    historial: list | None,
    obtener_historial: Callable[[], list],
    guardar: Callable[[dict], dict],
) -> str | None:
    """Devuelve el id de Drive del documento (por si cambió), o None si no
    había nada que actualizar (todavía no tiene documento archivado).

    Las excepciones suben: quien llama decide cómo avisarle a la persona.
    Ya no se tragan en silencio — antes un fallo dejaba el documento sin
    actualizar y nadie se enteraba."""
    with _candado_de(clave):
        archivo = obtener()
        if not archivo or not archivo.get("base64"):
            return None
        # Casi siempre ya viene en la respuesta de la revisión; si no (un
        # backend anterior, o el documento se actualiza por otra vía), se pide.
        historial = historial or obtener_historial()
        if not historial:
            return None

        datos = base64.b64decode(archivo["base64"])
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "historial.docx"
            recontar = docx_generator.actualizar_historial_docx(io.BytesIO(datos), historial, ruta)
            if recontar:
                pdf_converter.recalcular_campos(ruta)
            nuevo_base64 = base64.b64encode(ruta.read_bytes()).decode("ascii")

        paquete = {
            "base64": nuevo_base64,
            "mimeType": archivo.get("mimeType") or _MIME_DOCX,
            "en_sitio": True,
        }
        try:
            resultado = guardar(paquete)
        except api_client.SinConexion:
            # Un bache de red: guardar el mismo documento dos veces es
            # inofensivo (queda igual), a diferencia de otras escrituras,
            # así que acá SÍ vale la pena un reintento.
            resultado = guardar(paquete)
        return resultado.get("id")


def sincronizar_planeacion(token: str, planeacion_id: int, historial: list | None = None) -> str | None:
    return _sincronizar(
        f"planeacion:{planeacion_id}",
        lambda: api_client.obtener_documento_planeacion(token, planeacion_id),
        historial,
        lambda: api_client.historial_revision(token, "planeacion", planeacion_id),
        lambda archivo: api_client.guardar_documento_planeacion(token, planeacion_id, archivo),
    )


def sincronizar_informe(token: str, curso_id: int, mes: str, historial: list | None = None) -> str | None:
    return _sincronizar(
        f"informe:{curso_id}|{mes}",
        lambda: api_client.obtener_documento_informe(token, curso_id, mes),
        historial,
        lambda: api_client.historial_revision(token, "informe", f"{curso_id}|{mes}"),
        lambda archivo: api_client.guardar_documento_informe(token, curso_id, mes, archivo),
    )
