"""Un renglón de la tabla "3. EVALUACIÓN DE AVANCE POR TEMA".

La columna "unidad trabajada" se arma sola desde las planeaciones de esa
semana (semana + temas vistos), así que acá se muestra de solo lectura y
el docente aporta únicamente el nivel de avance y las observaciones.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from services import date_utils
from ui import tema

NIVELES = ["Bajo", "Medio", "Alto"]
_COLOR_NIVEL = {"Bajo": tema.ROJO, "Medio": tema.AMBAR, "Alto": tema.VERDE}
_COLOR_NIVEL_HOVER = {"Bajo": tema.ROJO_HOVER, "Medio": tema.AMBAR_HOVER, "Alto": tema.VERDE_HOVER}


class AvanceSemanaEditor(ctk.CTkFrame):
    def __init__(
        self, master, semana: int, temas: list[str], fecha: str = "",
        on_cambiar: Callable[[], None] | None = None,
    ):
        super().__init__(
            master, border_width=1, corner_radius=12, fg_color="transparent", border_color=tema.DIVISOR,
        )
        self.semana = semana
        self._on_cambiar = on_cambiar

        contenido = ctk.CTkFrame(self, fg_color="transparent")
        contenido.pack(fill="x", padx=16, pady=14)

        fila = ctk.CTkFrame(contenido, fg_color="transparent")
        fila.pack(fill="x")
        fila.grid_columnconfigure(0, minsize=110)
        fila.grid_columnconfigure(1, weight=1)

        # Cada fila es una clase concreta: sin la fecha, cuatro renglones
        # que dicen "Semana 1..4" no le dicen al docente cuál es cuál.
        col_semana = ctk.CTkFrame(fila, fg_color="transparent")
        col_semana.grid(row=0, column=0, sticky="nw", padx=(0, 12))
        ctk.CTkLabel(
            col_semana, text=f"Semana {semana}", font=tema.fuente(13, "bold"),
            text_color=tema.VERDE_OSCURO, anchor="w",
        ).pack(fill="x")
        if fecha:
            ctk.CTkLabel(
                col_semana, text=date_utils.a_fecha_corta(fecha), font=tema.fuente(11),
                text_color=tema.TEXTO_MUTED, anchor="w",
            ).pack(fill="x")

        resumen = " · ".join(temas) if temas else "(sin temas registrados)"
        ctk.CTkLabel(
            fila, text=resumen, text_color=tema.TEXTO_OSCURO, font=tema.fuente(13),
            anchor="w", justify="left", wraplength=340,
        ).grid(row=0, column=1, sticky="nw")

        self._nivel = NIVELES[0]
        self._nivel_botones: dict[str, ctk.CTkButton] = {}
        pastillas = ctk.CTkFrame(fila, fg_color="transparent")
        pastillas.grid(row=0, column=2, sticky="ne", padx=(12, 0))
        for nivel in NIVELES:
            boton = ctk.CTkButton(
                pastillas, text=nivel, width=64, height=26, corner_radius=8,
                font=tema.fuente(11), border_width=1, border_color=tema.BORDE_TARJETA,
                command=lambda n=nivel: self._elegir_nivel(n),
            )
            boton.pack(side="left", padx=(0, 4))
            self._nivel_botones[nivel] = boton
        self._actualizar_pastillas()

        self.observaciones_entry = ctk.CTkEntry(contenido, placeholder_text="Observaciones de la semana")
        self.observaciones_entry.pack(fill="x", pady=(10, 0))
        self.observaciones_entry.bind("<KeyRelease>", lambda _e: self._avisar_cambio())

    def _elegir_nivel(self, nivel: str):
        self._nivel = nivel
        self._actualizar_pastillas()
        self._avisar_cambio()

    def _avisar_cambio(self):
        if self._on_cambiar is not None:
            self._on_cambiar()

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
