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

from ui.planeacion_screen import PlaneacionScreen
from ui.planeacion_list_screen import PlaneacionListScreen
from ui.actividades_screen import ActividadesScreen


class PlaneacionesScreen(ctk.CTkFrame):
    def __init__(
        self,
        master,
        sesion: dict,
        on_volver: Callable[[], None],
        on_editar: Callable[[dict], None],
    ):
        super().__init__(master)
        self.sesion = sesion

        ctk.CTkButton(self, text="← Volver", width=90, command=on_volver).pack(
            anchor="w", padx=12, pady=(12, 0)
        )

        self.tabview = ctk.CTkTabview(self, command=self._al_cambiar_pestana)
        self.tabview.pack(fill="both", expand=True, padx=8, pady=8)
        for nombre in ("Nueva clase", "Mis planeaciones", "Otras actividades"):
            self.tabview.add(nombre)

        self.nueva = PlaneacionScreen(self.tabview.tab("Nueva clase"), sesion)
        self.nueva.pack(fill="both", expand=True)

        self.mias = PlaneacionListScreen(
            self.tabview.tab("Mis planeaciones"), sesion, on_editar=on_editar
        )
        self.mias.pack(fill="both", expand=True)

        self.actividades = ActividadesScreen(self.tabview.tab("Otras actividades"), sesion)
        self.actividades.pack(fill="both", expand=True)

        self.tabview.set("Nueva clase")

    def _al_cambiar_pestana(self):
        # Al volver a «Mis planeaciones» se recarga, para que aparezca lo
        # que se cargó recién en las otras pestañas.
        if self.tabview.get() == "Mis planeaciones":
            self.mias._cargar()
