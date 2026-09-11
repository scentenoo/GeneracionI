"""Revisar planeaciones e informes (rol directivo), en pestañas: cada una
es una manera distinta de mirar el estado del mes — planeaciones,
informes (con su descarga) y el dashboard general.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from ui import tema
from ui.dashboard_screen import DashboardScreen
from ui.revisar_informes_screen import RevisarInformesScreen
from ui.revisar_planeaciones_screen import RevisarPlaneacionesScreen


class RevisarHubScreen(ctk.CTkFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None]):
        super().__init__(master)
        self.sesion = sesion

        ctk.CTkButton(
            self, text="← Volver", width=90, fg_color="transparent", border_width=1,
            text_color=tema.TEXTO_OSCURO, hover_color=tema.FONDO_TARJETA, command=on_volver,
        ).pack(anchor="w", padx=12, pady=(12, 0))

        self.tabview = ctk.CTkTabview(
            self,
            segmented_button_selected_color=tema.VERDE_OSCURO,
            segmented_button_selected_hover_color=tema.VERDE_OSCURO_ACTIVO,
            segmented_button_unselected_color=tema.FONDO_TARJETA,
            text_color=tema.TEXTO_OSCURO,
        )
        self.tabview.pack(fill="both", expand=True, padx=8, pady=8)
        for nombre in ("Planeaciones", "Informes", "Dashboard mensual"):
            self.tabview.add(nombre)

        self.planeaciones = RevisarPlaneacionesScreen(self.tabview.tab("Planeaciones"), sesion)
        self.planeaciones.pack(fill="both", expand=True)

        self.informes = RevisarInformesScreen(self.tabview.tab("Informes"), sesion)
        self.informes.pack(fill="both", expand=True)

        self.dashboard = DashboardScreen(self.tabview.tab("Dashboard mensual"), sesion)
        self.dashboard.pack(fill="both", expand=True)
