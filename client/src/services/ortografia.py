"""Corrector ortográfico en español (Colombia), sin conexión — corre
enteramente en el cliente con un diccionario Hunspell embebido (ver
client/assets/diccionario), usando `spylls` (Hunspell reimplementado en
Python puro, sin librería compilada — más simple de empaquetar con
PyInstaller que un binding a la C).

Cargar el diccionario tarda un momento (son ~60 mil palabras), así que
`cargar_en_segundo_plano()` lo dispara en un hilo aparte apenas arranca la
app (ver main.py), mientras se muestra el login — para cuando el docente
llega al primer campo largo, ya suele estar listo. Si por lo que sea no
carga (falta el archivo, versión vieja del instalador sin el diccionario
empaquetado), la app sigue funcionando igual, simplemente sin subrayar
nada — nunca es motivo para romper un formulario.
"""

from __future__ import annotations

import sys
import threading
import traceback

from config import DICCIONARIO_DIR

_diccionario = None
_listo = threading.Event()
_cargando_ahora = False

# Términos propios del programa que un diccionario general no conoce y que
# no tiene sentido marcar como error — son de la app, no del contenido que
# redacta cada docente (eso lo juzga el diccionario solo).
_PALABRAS_PROPIAS = {"CTeI", "Generación-I", "Generación-i"}


def cargar_en_segundo_plano():
    global _cargando_ahora
    if _listo.is_set() or _cargando_ahora:
        return
    _cargando_ahora = True
    threading.Thread(target=_cargar, daemon=True).start()


def _cargar():
    global _diccionario
    try:
        from spylls.hunspell import Dictionary

        _diccionario = Dictionary.from_files(str(DICCIONARIO_DIR / "es_CO"))
    except Exception:  # noqa: BLE001 — sin diccionario, la app anda igual
        traceback.print_exc(file=sys.stderr)
    finally:
        _listo.set()


def disponible() -> bool:
    return _listo.is_set() and _diccionario is not None


def es_correcta(palabra: str) -> bool:
    if not disponible():
        return True  # nada cargado todavía (o falló): no marcar nada como error
    if palabra in _PALABRAS_PROPIAS:
        return True
    return _diccionario.lookup(palabra)


def sugerencias(palabra: str, tope: int = 6) -> list[str]:
    if not disponible():
        return []
    resultado = []
    for s in _diccionario.suggest(palabra):
        resultado.append(s)
        if len(resultado) >= tope:
            break
    return resultado
