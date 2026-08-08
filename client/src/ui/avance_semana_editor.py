"""Un renglón de la tabla "3. EVALUACIÓN DE AVANCE POR TEMA" del informe
mensual: semana, nivel de avance, observaciones."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

NIVELES = ["Bajo", "Medio", "Alto"]


class AvanceSemanaEditor(ctk.CTkFrame):
    def __init__(self, master, numero: int, on_eliminar: Callable[["AvanceSemanaEditor"], None]):
        super().__init__(master, border_width=1, corner_radius=8, fg_color="transparent")

        self.semana_entry = ctk.CTkEntry(self, width=90)
        self.semana_entry.insert(0, f"Semana {numero}")
        self.semana_entry.pack(side="left", padx=6, pady=6)

        self.nivel_menu = ctk.CTkOptionMenu(self, values=NIVELES, width=90)
        self.nivel_menu.pack(side="left", padx=6, pady=6)

        self.observaciones_entry = ctk.CTkEntry(self, placeholder_text="Observaciones")
        self.observaciones_entry.pack(side="left", fill="x", expand=True, padx=6, pady=6)

        ctk.CTkButton(
            self, text="x", width=28, fg_color="#c0392b", hover_color="#922b21",
            command=lambda: on_eliminar(self),
        ).pack(side="left", padx=6, pady=6)

    def a_dict(self) -> dict:
        return {
            "semana": self.semana_entry.get().strip(),
            "nivel": self.nivel_menu.get(),
            "observaciones": self.observaciones_entry.get().strip(),
        }
