"""Encabezado superior persistente (rediseño completo): barra verde oscuro
entre la barra lateral y el contenido, con el título de la sección
activa, un buscador opcional (solo si la pantalla actual tiene algo que
filtrar) y el mes activo a la derecha.

Vive parado igual que `BarraLateral`: `App._armar_shell` lo arma una sola
vez, y cada `_mostrar_X` llama a `configurar(...)` con lo que corresponda
a esa sección — igual que ya hace con `self._sidebar.marcar_activo(...)`.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from services import date_utils
from ui import tema
from ui.widgets import CampoBusqueda

ALTO = 64
_ANCHO_BUSCADOR_MAX = 260
_ANCHO_BUSCADOR_MIN = 140


class BarraSuperior(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, height=ALTO, corner_radius=0, fg_color=tema.VERDE_OSCURO)
        # Con los tres widgets en pack() (títulos largos como "Revisar
        # planeaciones e informes" + buscador a ancho fijo + período) la
        # suma superaba el ancho disponible en ventanas angostas y el
        # período terminaba tapando/cortando el buscador. Con grid() cada
        # columna tiene su espacio reservado (el período nunca invade la
        # columna del buscador) y la columna del buscador puede angostarse
        # -- ver _ajustar_ancho_buscador -- en vez de superponerse.
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1, minsize=_ANCHO_BUSCADOR_MIN)
        self.grid_columnconfigure(2, weight=0)
        self.grid_rowconfigure(0, weight=1)

        self.titulo_label = ctk.CTkLabel(
            self, text="", font=tema.fuente(19, "bold"), text_color=tema.DORADO_ACENTO,
        )
        self.titulo_label.grid(row=0, column=0, sticky="w", padx=(28, 20))

        self._buscador_contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self._buscador_contenedor.grid(row=0, column=1, sticky="ew")
        self._buscador_contenedor.bind("<Configure>", self._ajustar_ancho_buscador)
        self._buscador: CampoBusqueda | None = None

        self.periodo_label = ctk.CTkLabel(
            self, text="", font=tema.fuente(12), text_color=tema.TEXTO_CLARO_APAGADO,
        )
        self.periodo_label.grid(row=0, column=2, sticky="e", padx=28)

    def configurar_titulo(self, titulo: str):
        """Cambia el título de la sección activa. `App` la llama una vez
        por cada `_mostrar_X`. No toca el buscador: las pantallas con
        pestañas (Planeaciones, Revisar, Cursos, Usuarios) tienen un
        buscador distinto por pestaña, así que ese lo maneja cada hub con
        `configurar_buscador` en su propio cambio de pestaña, no acá."""
        self.titulo_label.configure(text=titulo.upper())
        self.periodo_label.configure(text=f"Periodo activo · {date_utils.hoy_iso()[:7]}")

    def configurar_buscador(
        self, on_buscar: Callable[[str], None] | None, placeholder: str = "Buscar...",
    ):
        """Muestra un buscador que avisa `on_buscar(texto)` en cada cambio
        (con debounce) — la pantalla que lo pidió filtra sobre lo que ya
        tiene cargado en memoria, acá no se guarda ningún estado de
        filtro. `on_buscar=None` lo quita (pantallas sin nada que
        filtrar, o al cambiar a una pestaña sin buscador)."""
        if self._buscador is not None:
            self._buscador.destroy()
            self._buscador = None
        if on_buscar is not None:
            self._buscador = CampoBusqueda(
                self._buscador_contenedor, placeholder, on_buscar, ancho=_ANCHO_BUSCADOR_MAX,
            )
            self._buscador.pack(anchor="w")
            self._ajustar_ancho_buscador()

    def _ajustar_ancho_buscador(self, _evento=None):
        """Achica el buscador si la columna que le tocó (ver
        grid_columnconfigure en __init__) es más angosta que su ancho de
        sobra habitual, para que nunca invada la columna del período de al
        lado. Se dispara con cada resize del contenedor (incluido el
        primer layout, cuando todavía no tiene ancho real)."""
        if self._buscador is None:
            return
        disponible = self._buscador_contenedor.winfo_width()
        if disponible <= 1:
            return
        ancho = max(_ANCHO_BUSCADOR_MIN, min(_ANCHO_BUSCADOR_MAX, disponible))
        self._buscador.configure(width=ancho)
