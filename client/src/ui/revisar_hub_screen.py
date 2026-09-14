"""Revisar planeaciones e informes (rol directivo), en pestañas: cada una
es una manera distinta de mirar el estado del mes — planeaciones,
informes (con su descarga) y el dashboard general.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from ui import tema
from ui.certificado_pago_screen import CertificadoPagoScreen
from ui.dashboard_screen import DashboardScreen
from ui.revisar_horas_screen import RevisarHorasScreen
from ui.revisar_informes_screen import RevisarInformesScreen
from ui.revisar_planeaciones_screen import RevisarPlaneacionesScreen
from ui.widgets import PestanasPildora


class RevisarHubScreen(ctk.CTkFrame):
    def __init__(
        self, master, sesion: dict, on_volver: Callable[[], None],
        on_buscador: Callable[[Callable[[str], None] | None, str], None] | None = None,
    ):
        super().__init__(master)
        self.sesion = sesion
        self.on_buscador = on_buscador
        self._es_admin = bool(sesion.get("es_admin"))
        # Horas externas es supervisión del equipo directivo (ver
        # revisar_hora_gestion/obtener_horas_del_equipo en el backend):
        # rol directivo, ambos, o el administrador. A los docentes puros
        # (rol "docente", sin ser admin) esa pestaña les daría siempre
        # "no tiene permiso".
        self._puede_horas = self._es_admin or sesion.get("rol") in ("directivo", "ambos")

        ctk.CTkButton(
            self, text="← Volver", width=90, fg_color="transparent", border_width=1,
            text_color=tema.TEXTO_OSCURO, hover_color=tema.FONDO_TARJETA, command=on_volver,
        ).pack(anchor="w", padx=12, pady=(12, 0))

        self.tabview = PestanasPildora(self, command=self._al_cambiar_pestana)
        self.tabview.pack(fill="both", expand=True, padx=8, pady=8)
        nombres = ["Planeaciones", "Informes"]
        if self._puede_horas:
            nombres.append("Horas externas")
        nombres.append("Dashboard mensual")
        if self._es_admin:
            nombres.append("Certificado de pago")
        for nombre in nombres:
            self.tabview.add(nombre)

        self.planeaciones = RevisarPlaneacionesScreen(self.tabview.tab("Planeaciones"), sesion)
        self.planeaciones.pack(fill="both", expand=True)

        self.informes = RevisarInformesScreen(self.tabview.tab("Informes"), sesion)
        self.informes.pack(fill="both", expand=True)

        self.horas: RevisarHorasScreen | None = None
        if self._puede_horas:
            self.horas = RevisarHorasScreen(self.tabview.tab("Horas externas"), sesion)
            self.horas.pack(fill="both", expand=True)

        self.dashboard = DashboardScreen(self.tabview.tab("Dashboard mensual"), sesion)
        self.dashboard.pack(fill="both", expand=True)

        self.certificado: CertificadoPagoScreen | None = None
        if self._es_admin:
            self.certificado = CertificadoPagoScreen(self.tabview.tab("Certificado de pago"), sesion)
            self.certificado.pack(fill="both", expand=True)

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
            # "Certificado de pago" no filtra nada: es un solo documento por
            # mes, no una lista para buscar en ella.
            self.on_buscador(None)
