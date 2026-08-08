"""Compresión de fotos antes de subirlas (spec sección 6: cuida cuota y
velocidad de subida). Vive en services/ porque es lógica de backend/negocio,
no algo que las pantallas de los niños deban tocar directamente — ellas
solo llaman a `foto_a_payload`.
"""

from __future__ import annotations

import base64
import io

from PIL import Image

_MAX_DIMENSION_PX = 1600
_JPEG_QUALITY = 75


def comprimir_imagen(ruta_archivo: str) -> bytes:
    with Image.open(ruta_archivo) as img:
        img = img.convert("RGB")
        img.thumbnail((_MAX_DIMENSION_PX, _MAX_DIMENSION_PX))
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=_JPEG_QUALITY, optimize=True)
        return buffer.getvalue()


def foto_a_payload(ruta_archivo: str) -> dict:
    """Devuelve el dict {"base64": ..., "mimeType": "image/jpeg"} que espera
    el backend (guardar_planeacion, subir_firma)."""
    data = comprimir_imagen(ruta_archivo)
    return {"base64": base64.b64encode(data).decode("ascii"), "mimeType": "image/jpeg"}
