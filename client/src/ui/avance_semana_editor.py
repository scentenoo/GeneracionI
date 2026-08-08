"""Un renglón de la tabla "3. EVALUACIÓN DE AVANCE POR TEMA".

La columna "unidad trabajada" se arma sola desde las planeaciones de esa
semana (semana + temas vistos), así que acá se muestra de solo lectura y
el docente aporta únicamente el nivel de avance y las observaciones.
"""

from __future__ import annotations

import customtkinter as ctk

NIVELES = ["Bajo", "Medio", "Alto"]


class AvanceSemanaEditor(ctk.CTkFrame):
    def __init__(self, master, semana: int, temas: list[str]):
        super().__init__(master, border_width=1, corner_radius=8, fg_color="transparent")
        self.semana = semana

        ctk.CTkLabel(
            self, text=f"Semana {semana}", font=ctk.CTkFont(weight="bold"), anchor="w"
        ).pack(fill="x", padx=10, pady=(8, 0))

        resumen = " · ".join(temas) if temas else "(sin temas registrados)"
        ctk.CTkLabel(
            self, text=resumen, text_color="gray", anchor="w", justify="left", wraplength=420
        ).pack(fill="x", padx=10)

        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.pack(fill="x", padx=10, pady=(6, 10))

        self.nivel_menu = ctk.CTkOptionMenu(fila, values=NIVELES, width=90)
        self.nivel_menu.pack(side="left")

        self.observaciones_entry = ctk.CTkEntry(fila, placeholder_text="Observaciones de la semana")
        self.observaciones_entry.pack(side="left", fill="x", expand=True, padx=(8, 0))

    def a_dict(self) -> dict:
        # `semana` va como número: el backend la usa para emparejar esta
        # respuesta con los temas que ya sacó de las planeaciones.
        return {
            "semana": self.semana,
            "nivel": self.nivel_menu.get(),
            "observaciones": self.observaciones_entry.get().strip(),
        }
