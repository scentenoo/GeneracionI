"""Llamadas al backend sin congelar la ventana.

Cada llamada a Apps Script tarda entre 1 y 3 segundos. Hechas en el hilo
de Tkinter, la ventana deja de responder todo ese rato — que es lo que se
siente como "la app está lenta".

Tkinter no es thread-safe: solo el hilo principal puede tocar widgets. El
patrón entonces es correr la llamada en un hilo aparte y devolver el
resultado al hilo de Tk con `widget.after()`, que sí es seguro.
"""

from __future__ import annotations

import queue
import sys
import threading
import traceback
from typing import Callable

import api_client

# Los resultados de los hilos se dejan acá y los recoge el hilo principal.
#
# El hilo worker NO puede tocar Tkinter: ni siquiera `winfo_exists()` o
# `after()`, que fallan con "main thread is not in main loop". Por eso la
# entrega pasa por una cola, que sí es segura entre hilos, y un temporizador
# que corre en el hilo principal la vacía.
_cola: "queue.Queue[tuple]" = queue.Queue()
_entrega_iniciada = False

INTERVALO_MS = 50


def _bombear(root):
    """Corre en el hilo principal: saca resultados de la cola y los entrega.

    Si el usuario navegó a otra pantalla, el widget ya no existe y el
    resultado se descarta — es tarde para mostrarlo y ya no le importa.
    """
    try:
        while True:
            widget, callback, valor = _cola.get_nowait()
            try:
                if widget.winfo_exists():
                    callback(valor)
            except Exception:  # noqa: BLE001
                # Un callback que revienta no puede matar la entrega del resto.
                traceback.print_exc(file=sys.stderr)
    except queue.Empty:
        pass

    try:
        root.after(INTERVALO_MS, lambda: _bombear(root))
    except Exception:  # noqa: BLE001
        # La ventana se cerró: no hay nada más que entregar.
        pass


# Cuántas subidas hay corriendo ahora mismo. Cerrar la ventana en el medio
# de una mata el hilo antes de que Apps Script termine de escribir, y la
# planeación queda a medio guardar o la foto sin subir. El contador lo lee
# App._al_cerrar para avisar en vez de cerrar.
_lock_contador = threading.Lock()
_contador = 0


def hay_trabajo_pendiente() -> bool:
    with _lock_contador:
        return _contador > 0


def _sumar(delta: int):
    global _contador
    with _lock_contador:
        _contador += delta


def en_segundo_plano(
    widget,
    trabajo: Callable[[], object],
    al_terminar: Callable[[object], None],
    al_fallar: Callable[[Exception], None] | None = None,
    bloquea_cierre: bool = False,
):
    """Corre `trabajo()` fuera del hilo de la interfaz y entrega el
    resultado a `al_terminar` ya de vuelta en el hilo de Tk.

    Se llama siempre desde el hilo principal (sale de un callback de la
    interfaz), que es donde se arranca el temporizador de entrega.

    Con `bloquea_cierre` la tarea se cuenta como "subida en curso" y la app
    avisa antes de cerrarse. Va solo en lo que escribe en el backend: para
    una consulta de lectura, cerrar en el medio no rompe nada.
    """
    global _entrega_iniciada
    if not _entrega_iniciada:
        _entrega_iniciada = True
        _bombear(widget.winfo_toplevel())

    if bloquea_cierre:
        _sumar(1)

    def correr():
        try:
            resultado = trabajo()
        except Exception as exc:  # noqa: BLE001 — se lo pasamos tal cual al caller
            if al_fallar is not None:
                _cola.put((widget, al_fallar, exc))
            else:
                traceback.print_exc(file=sys.stderr)
        else:
            _cola.put((widget, al_terminar, resultado))
        finally:
            if bloquea_cierre:
                _sumar(-1)

    threading.Thread(target=correr, daemon=True).start()


def en_segundo_plano_con_progreso(
    widget,
    trabajo: Callable[[Callable[[object], None]], object],
    al_progreso: Callable[[object], None],
    al_terminar: Callable[[object], None],
    al_fallar: Callable[[Exception], None] | None = None,
):
    """Como en_segundo_plano, pero `trabajo` recibe un `reportar(valor)`
    para ir avisando cómo avanza. Cada `reportar` entrega el valor a
    `al_progreso` ya en el hilo de Tk, así una descarga larga puede pintar
    una barra sin congelar la ventana ni tocar widgets desde el worker.
    """
    global _entrega_iniciada
    if not _entrega_iniciada:
        _entrega_iniciada = True
        _bombear(widget.winfo_toplevel())

    def correr():
        def reportar(valor):
            _cola.put((widget, al_progreso, valor))

        try:
            resultado = trabajo(reportar)
        except Exception as exc:  # noqa: BLE001
            if al_fallar is not None:
                _cola.put((widget, al_fallar, exc))
            else:
                traceback.print_exc(file=sys.stderr)
        else:
            _cola.put((widget, al_terminar, resultado))

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
