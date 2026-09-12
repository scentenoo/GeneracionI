"""Un renglón de la tabla "3. EVALUACIÓN DE AVANCE POR TEMA".

La columna "unidad trabajada" se arma sola desde las planeaciones de esa
semana (semana + temas vistos), así que acá se muestra de solo lectura y
el docente aporta únicamente el nivel de avance y las observaciones.
"""

from __future__ import annotations

import customtkinter as ctk

from services import date_utils
from ui import tema

NIVELES = ["Bajo", "Medio", "Alto"]
_COLOR_NIVEL = {"Bajo": tema.ROJO, "Medio": tema.AMBAR, "Alto": tema.VERDE}
_COLOR_NIVEL_HOVER = {"Bajo": tema.ROJO_HOVER, "Medio": tema.AMBAR_HOVER, "Alto": tema.VERDE_HOVER}


class AvanceSemanaEditor(ctk.CTkFrame):
    def __init__(self, master, semana: int, temas: list[str], fecha: str = ""):
        super().__init__(master, border_width=1, corner_radius=8, fg_color="transparent")
        self.semana = semana

        # Cada fila es una clase concreta: sin la fecha, cuatro renglones
        # que dicen "Semana 1..4" no le dicen al docente cuál es cuál.
        titulo = f"Semana {semana}"
        if fecha:
            titulo += f"  ·  {date_utils.a_fecha_corta(fecha)}"
        ctk.CTkLabel(
            self, text=titulo, font=ctk.CTkFont(weight="bold"), anchor="w"
        ).pack(fill="x", padx=10, pady=(8, 0))

        resumen = " · ".join(temas) if temas else "(sin temas registrados)"
        ctk.CTkLabel(
            self, text=resumen, text_color="gray", anchor="w", justify="left", wraplength=420
        ).pack(fill="x", padx=10)

        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.pack(fill="x", padx=10, pady=(6, 10))

        self._nivel = NIVELES[0]
        self._nivel_botones: dict[str, ctk.CTkButton] = {}
        pastillas = ctk.CTkFrame(fila, fg_color="transparent")
        pastillas.pack(side="left")
        for nivel in NIVELES:
            boton = ctk.CTkButton(
                pastillas, text=nivel, width=64, height=26, corner_radius=13,
                font=tema.fuente(12), border_width=1, border_color=tema.BORDE_TARJETA,
                command=lambda n=nivel: self._elegir_nivel(n),
            )
            boton.pack(side="left", padx=(0, 4))
            self._nivel_botones[nivel] = boton
        self._actualizar_pastillas()

        self.observaciones_entry = ctk.CTkEntry(fila, placeholder_text="Observaciones de la semana")
        self.observaciones_entry.pack(side="left", fill="x", expand=True, padx=(8, 0))

    def _elegir_nivel(self, nivel: str):
        self._nivel = nivel
        self._actualizar_pastillas()

    def _actualizar_pastillas(self):
        for nivel, boton in self._nivel_botones.items():
            if nivel == self._nivel:
                boton.configure(
                    fg_color=_COLOR_NIVEL[nivel], hover_color=_COLOR_NIVEL_HOVER[nivel],
                    text_color=tema.TEXTO_CLARO,
                )
            else:
                boton.configure(
                    fg_color="transparent", hover_color=tema.FONDO_TARJETA,
                    text_color=tema.TEXTO_OSCURO,
                )

    def a_dict(self) -> dict:
        # `semana` va como número: el backend la usa para emparejar esta
        # respuesta con los temas que ya sacó de las planeaciones.
        return {
            "semana": self.semana,
            "nivel": self._nivel,
            "observaciones": self.observaciones_entry.get().strip(),
        }
