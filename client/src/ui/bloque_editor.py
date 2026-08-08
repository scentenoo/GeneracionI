"""Un bloque/momento de la planeación: momento+tiempo, observación
pedagógica y avances/retrocesos (los tres campos de la tabla "MOMENTOS DE
LA CLASE Y TIEMPOS" del template, ver templates/planeacion_individual.docx).
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from ui.widgets import CampoConContador


class BloqueEditor(ctk.CTkFrame):
    def __init__(self, master, numero: int, on_eliminar: Callable[["BloqueEditor"], None]):
        super().__init__(master, border_width=1, corner_radius=8)
        self.on_eliminar = on_eliminar

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 0))
        ctk.CTkLabel(header, text=f"Bloque {numero}", font=ctk.CTkFont(weight="bold")).pack(side="left")
        ctk.CTkButton(
            header, text="Quitar", width=70, fg_color="#c0392b", hover_color="#922b21",
            command=lambda: self.on_eliminar(self),
        ).pack(side="right")

        self.momento_entry = ctk.CTkEntry(self, placeholder_text="Momento y tiempo (ej: Repaso, 0-15 min)")
        self.momento_entry.pack(fill="x", padx=10, pady=(8, 4))

        self.observacion = CampoConContador(self, "Observación pedagógica")
        self.observacion.pack(fill="x", padx=10, pady=4)

        self.avance = CampoConContador(self, "Avances / retrocesos observados")
        self.avance.pack(fill="x", padx=10, pady=(4, 10))

    def es_valido(self) -> bool:
        return bool(self.momento_entry.get().strip()) and self.observacion.es_valido() and self.avance.es_valido()

    def a_dict(self) -> dict:
        return {
            "momento": self.momento_entry.get().strip(),
            "observacion": self.observacion.get(),
            "avance": self.avance.get(),
        }
