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


class BarraSuperior(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, height=ALTO, corner_radius=0, fg_color=tema.VERDE_OSCURO)
        self.pack_propagate(False)

        self.titulo_label = ctk.CTkLabel(
            self, text="", font=tema.fuente(19, "bold"), text_color=tema.DORADO_ACENTO,
        )
        self.titulo_label.pack(side="left", padx=(28, 20))

        self._buscador_contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self._buscador_contenedor.pack(side="left", fill="y")
        self._buscador: CampoBusqueda | None = None

        self.periodo_label = ctk.CTkLabel(
            self, text="", font=tema.fuente(12), text_color=tema.TEXTO_CLARO_APAGADO,
        )
        self.periodo_label.pack(side="right", padx=28)

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
            self._buscador = CampoBusqueda(self._buscador_contenedor, placeholder, on_buscar)
            self._buscador.pack()
