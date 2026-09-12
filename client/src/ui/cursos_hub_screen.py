"""Cursos (rol directivo): el alta/edición de cursos y sus estudiantes,
en pestañas — son las dos caras de armar un curso: primero el curso en sí
(núcleo, edades, color), después quién lo cursa.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from ui import tema
from ui.cursos_screen import CursosScreen
from ui.grupo_screen import GrupoScreen


class CursosHubScreen(ctk.CTkFrame):
    def __init__(
        self, master, sesion: dict, on_volver: Callable[[], None],
        on_buscador: Callable[[Callable[[str], None] | None, str], None] | None = None,
    ):
        super().__init__(master)
        self.sesion = sesion
        self.on_buscador = on_buscador

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
        for nombre in ("Cursos", "Estudiantes"):
            self.tabview.add(nombre)

        self.cursos = CursosScreen(self.tabview.tab("Cursos"), sesion)
        self.cursos.pack(fill="both", expand=True)

        self.estudiantes = GrupoScreen(self.tabview.tab("Estudiantes"), sesion)
        self.estudiantes.pack(fill="both", expand=True)

        self._al_cambiar_pestana()

    def _al_cambiar_pestana(self):
        if self.on_buscador is None:
            return
        pestana = self.tabview.get()
        if pestana == "Cursos":
            self.on_buscador(self.cursos.filtrar, "Buscar curso, docente o núcleo...")
        elif pestana == "Estudiantes":
            self.on_buscador(self.estudiantes.filtrar, "Buscar estudiante...")
        else:
            self.on_buscador(None)
