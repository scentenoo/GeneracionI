"""Revisar planeaciones e informes (rol directivo), en pestañas: cada una
es una manera distinta de mirar el estado del mes — planeaciones,
informes (con su descarga) y el dashboard general.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from ui import tema
from ui.dashboard_screen import DashboardScreen
from ui.revisar_horas_screen import RevisarHorasScreen
from ui.revisar_informes_screen import RevisarInformesScreen
from ui.revisar_planeaciones_screen import RevisarPlaneacionesScreen


class RevisarHubScreen(ctk.CTkFrame):
    def __init__(
        self, master, sesion: dict, on_volver: Callable[[], None],
        on_buscador: Callable[[Callable[[str], None] | None, str], None] | None = None,
    ):
        super().__init__(master)
        self.sesion = sesion
        self.on_buscador = on_buscador
        # Horas externas es supervisión pura del administrador (ver
        # revisar_hora_gestion/obtener_horas_del_equipo en el backend): a
        # Mariangel o Lorena, que revisan por color de curso pero no son
        # administradoras, esa pestaña les daría siempre "no tiene permiso".
        self._es_admin = bool(sesion.get("es_admin"))

        ctk.CTkButton(
            self, text="← Volver", width=90, fg_color="transparent", border_width=1,
            text_color=tema.TEXTO_OSCURO, hover_color=tema.FONDO_TARJETA, command=on_volver,
        ).pack(anchor="w", padx=12, pady=(12, 0))

        self.tabview = ctk.CTkTabview(
            self,
            segmented_button_selected_color=tema.DORADO_ACENTO,
            segmented_button_selected_hover_color=tema.DORADO_ACENTO_HOVER,
            segmented_button_unselected_color=tema.FONDO_TARJETA,
            text_color=tema.TEXTO_OSCURO,
            command=self._al_cambiar_pestana,
        )
        self.tabview.pack(fill="both", expand=True, padx=8, pady=8)
        nombres = ["Planeaciones", "Informes"]
        if self._es_admin:
            nombres.append("Horas externas")
        nombres.append("Dashboard mensual")
        for nombre in nombres:
            self.tabview.add(nombre)

        self.planeaciones = RevisarPlaneacionesScreen(self.tabview.tab("Planeaciones"), sesion)
        self.planeaciones.pack(fill="both", expand=True)

        self.informes = RevisarInformesScreen(self.tabview.tab("Informes"), sesion)
        self.informes.pack(fill="both", expand=True)

        self.horas: RevisarHorasScreen | None = None
        if self._es_admin:
            self.horas = RevisarHorasScreen(self.tabview.tab("Horas externas"), sesion)
            self.horas.pack(fill="both", expand=True)

        self.dashboard = DashboardScreen(self.tabview.tab("Dashboard mensual"), sesion)
        self.dashboard.pack(fill="both", expand=True)

        self._al_cambiar_pestana()

    def _al_cambiar_pestana(self):
        if self.on_buscador is None:
            return
        pestana = self.tabview.get()
        if pestana == "Planeaciones":
            self.on_buscador(self.planeaciones.filtrar, "Buscar curso o docente...")
        elif pestana == "Informes":
            self.on_buscador(self.informes.filtrar, "Buscar curso o docente...")
        elif pestana == "Horas externas" and self.horas is not None:
            self.on_buscador(self.horas.filtrar, "Buscar persona...")
        elif pestana == "Dashboard mensual":
            self.on_buscador(self.dashboard.filtrar, "Buscar curso o docente...")
        else:
            self.on_buscador(None)
