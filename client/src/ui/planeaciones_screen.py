"""Todo lo de planear en una sola pantalla, con pestañas.

Antes eran tres botones sueltos en el menú: «Nueva planeación», «Mis
planeaciones» y «Otras actividades». Son tres caras de lo mismo —lo que
el docente carga cada mes— así que ahora conviven acá, con un solo Volver
arriba.

«Mis planeaciones» se recarga al entrar a su pestaña: si el docente
acaba de cargar una en la primera pestaña, la ve sin tener que salir y
volver a entrar.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from ui import tema
from ui.planeacion_screen import PlaneacionScreen
from ui.planeacion_list_screen import PlaneacionListScreen
from ui.actividades_screen import ActividadesScreen
from ui.widgets import PestanasPildora


class PlaneacionesScreen(ctk.CTkFrame):
    def __init__(
        self,
        master,
        sesion: dict,
        on_volver: Callable[[], None],
        on_editar: Callable[[dict], None],
        on_buscador: Callable[[Callable[[str], None] | None, str], None] | None = None,
    ):
        super().__init__(master)
        self.sesion = sesion
        self.on_buscador = on_buscador

        ctk.CTkButton(
            self, text="← Volver", width=90, fg_color="transparent", border_width=1,
            text_color=tema.TEXTO_OSCURO, hover_color=tema.FONDO_TARJETA, command=on_volver,
        ).pack(anchor="w", padx=12, pady=(12, 0))

        self.tabview = PestanasPildora(self, command=self._al_cambiar_pestana)
        self.tabview.pack(fill="both", expand=True, padx=8, pady=8)
        # Los docentes piensan las clases como "horas en sede" y lo demás
        # como "horas externas": así lo pidieron en el piloto.
        for nombre in ("Horas en sede", "Mis planeaciones", "Horas externas"):
            self.tabview.add(nombre)

        self.nueva = PlaneacionScreen(self.tabview.tab("Horas en sede"), sesion)
        self.nueva.pack(fill="both", expand=True)

        self.mias = PlaneacionListScreen(
            self.tabview.tab("Mis planeaciones"), sesion, on_editar=on_editar
        )
        self.mias.pack(fill="both", expand=True)

        self.actividades = ActividadesScreen(self.tabview.tab("Horas externas"), sesion)
        self.actividades.pack(fill="both", expand=True)

        self.tabview.set("Horas en sede")
        self._al_cambiar_pestana()

    def _al_cambiar_pestana(self):
        # Al volver a «Mis planeaciones» se recarga, para que aparezca lo
        # que se cargó recién en las otras pestañas.
        pestana = self.tabview.get()
        if pestana == "Mis planeaciones":
            self.mias._cargar()
        # El buscador del encabezado superior es de la app, no de la
        # pestaña: se prende/apaga acá según cuál esté activa, en vez de
        # que cada pestaña lo maneje por su cuenta.
        if self.on_buscador is not None:
            if pestana == "Mis planeaciones":
                self.on_buscador(self.mias.filtrar, "Buscar curso u objetivo...")
            else:
                self.on_buscador(None)
