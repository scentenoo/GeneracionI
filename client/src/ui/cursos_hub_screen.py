"""Cursos (rol directivo): el alta/edición de cursos y sus estudiantes,
en pestañas — son las dos caras de armar un curso: primero el curso en sí
(núcleo, edades, color), después quién lo cursa.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from ui.cursos_screen import CursosScreen
from ui.grupo_screen import GrupoScreen


class CursosHubScreen(ctk.CTkFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None]):
        super().__init__(master)
        self.sesion = sesion

        ctk.CTkButton(self, text="← Volver", width=90, command=on_volver).pack(
            anchor="w", padx=12, pady=(12, 0)
        )

        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=8, pady=8)
        for nombre in ("Cursos", "Estudiantes"):
            self.tabview.add(nombre)

        self.cursos = CursosScreen(self.tabview.tab("Cursos"), sesion)
        self.cursos.pack(fill="both", expand=True)

        self.estudiantes = GrupoScreen(self.tabview.tab("Estudiantes"), sesion)
        self.estudiantes.pack(fill="both", expand=True)
