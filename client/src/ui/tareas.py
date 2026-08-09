"""Llamadas al backend sin congelar la ventana.

Cada llamada a Apps Script tarda entre 1 y 3 segundos. Hechas en el hilo
de Tkinter, la ventana deja de responder todo ese rato — que es lo que se
siente como "la app está lenta".

Tkinter no es thread-safe: solo el hilo principal puede tocar widgets. El
patrón entonces es correr la llamada en un hilo aparte y devolver el
resultado al hilo de Tk con `widget.after()`, que sí es seguro.
"""

from __future__ import annotations

import threading
from typing import Callable

import api_client


def en_segundo_plano(
    widget,
    trabajo: Callable[[], object],
    al_terminar: Callable[[object], None],
    al_fallar: Callable[[Exception], None] | None = None,
):
    """Corre `trabajo()` fuera del hilo de la interfaz y entrega el
    resultado a `al_terminar` ya de vuelta en el hilo de Tk.

    Si el usuario navega a otra pantalla mientras la llamada está en
    curso, el widget deja de existir y el resultado se descarta en vez de
    reventar."""

    def entregar(callback, valor):
        try:
            if widget.winfo_exists():
                widget.after(0, lambda: callback(valor))
        except Exception:
            # La ventana ya se cerró: no hay a quién entregarle nada.
            pass

    def correr():
        try:
            resultado = trabajo()
        except Exception as exc:  # noqa: BLE001 — se lo pasamos tal cual al caller
            if al_fallar is not None:
                entregar(al_fallar, exc)
        else:
            entregar(al_terminar, resultado)

    threading.Thread(target=correr, daemon=True).start()


class Cache:
    """Guarda en memoria lo que no cambia dentro de una sesión — la lista
    de usuarios y la de cursos, que hoy se vuelven a pedir cada vez que se
    abre una pantalla.

    Cualquier pantalla que modifique usuarios o cursos tiene que llamar a
    `invalidar()` para que la próxima lectura vuelva a ir al backend.
    """

    def __init__(self):
        self._datos: dict[str, object] = {}

    def usuarios(self, token: str) -> list[dict]:
        if "usuarios" not in self._datos:
            self._datos["usuarios"] = api_client.listar_usuarios(token)
        return self._datos["usuarios"]  # type: ignore[return-value]

    def cursos(self, token: str) -> list[dict]:
        if "cursos" not in self._datos:
            self._datos["cursos"] = api_client.listar_todos_los_cursos(token)
        return self._datos["cursos"]  # type: ignore[return-value]

    def nombres_de_usuarios(self, token: str) -> dict[int, str]:
        return {u["id"]: u["nombre"] for u in self.usuarios(token)}

    def invalidar(self, *claves: str):
        """Sin argumentos borra todo; con claves borra solo esas."""
        if not claves:
            self._datos.clear()
            return
        for clave in claves:
            self._datos.pop(clave, None)

    def precargar(self, sesion: dict):
        """Trae de una sola vez lo que después piden casi todas las
        pantallas. Sin esto, abrir el informe cuesta tres o cuatro viajes
        seguidos de ~3 segundos cada uno; con esto, ninguno.

        Se corre apenas entra el usuario y en segundo plano, así que no
        retrasa que aparezca el menú.
        """
        token = sesion["token"]
        es_directivo = sesion["rol"] in ("directivo", "ambos")

        llamadas = [("listar_cursos", [token, None, False])]
        if es_directivo:
            llamadas += [("listar_todos_los_cursos", [token]), ("listar_usuarios", [token])]

        resultados = api_client.batch(llamadas)

        mis_cursos = resultados[0]
        if not isinstance(mis_cursos, Exception):
            self._datos["mis_cursos"] = mis_cursos

        if es_directivo:
            todos, usuarios = resultados[1], resultados[2]
            if not isinstance(todos, Exception):
                self._datos["cursos"] = todos
            if not isinstance(usuarios, Exception):
                self._datos["usuarios"] = usuarios

    def mis_cursos(self, token: str) -> list[dict]:
        if "mis_cursos" not in self._datos:
            self._datos["mis_cursos"] = api_client.listar_cursos(token)
        return self._datos["mis_cursos"]  # type: ignore[return-value]


# Una sola instancia para toda la app: se vacía sola al cerrarla.
cache = Cache()
