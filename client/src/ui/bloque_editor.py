"""Un bloque/momento de la planeación: momento, cuántos minutos duró,
observación pedagógica y avances/retrocesos (los campos de la tabla
"MOMENTOS DE LA CLASE Y TIEMPOS", ver templates/planeacion_individual.docx).

Los minutos van en su propio campo y no dentro del texto del momento, para
poder sumarlos y validar el mínimo de 2 horas por clase.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from ui.widgets import CampoConContador


class BloqueEditor(ctk.CTkFrame):
    def __init__(
        self,
        master,
        numero: int,
        on_eliminar: Callable[["BloqueEditor"], None],
        on_minutos_cambio: Callable[[], None] | None = None,
    ):
        super().__init__(master, border_width=1, corner_radius=8)
        self.on_eliminar = on_eliminar
        self.on_minutos_cambio = on_minutos_cambio or (lambda: None)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 0))
        ctk.CTkLabel(header, text=f"Bloque {numero}", font=ctk.CTkFont(weight="bold")).pack(side="left")
        ctk.CTkButton(
            header, text="Quitar", width=70, fg_color="#c0392b", hover_color="#922b21",
            command=lambda: self.on_eliminar(self),
        ).pack(side="right")

        fila_momento = ctk.CTkFrame(self, fg_color="transparent")
        fila_momento.pack(fill="x", padx=10, pady=(8, 4))

        self.momento_entry = ctk.CTkEntry(fila_momento, placeholder_text="Momento (ej: Repaso del módulo)")
        self.momento_entry.pack(side="left", fill="x", expand=True)

        self.minutos_entry = ctk.CTkEntry(fila_momento, width=64)
        self.minutos_entry.pack(side="left", padx=(8, 4))
        self.minutos_entry.bind("<KeyRelease>", lambda _e: self.on_minutos_cambio())
        ctk.CTkLabel(fila_momento, text="min", text_color="gray").pack(side="left")

        self.observacion = CampoConContador(self, "Observación pedagógica")
        self.observacion.pack(fill="x", padx=10, pady=4)

        self.avance = CampoConContador(self, "Avances / retrocesos observados")
        self.avance.pack(fill="x", padx=10, pady=(4, 10))

    def minutos(self) -> int:
        try:
            return int(self.minutos_entry.get().strip() or 0)
        except ValueError:
            return 0

    def es_valido(self) -> bool:
        return (
            bool(self.momento_entry.get().strip())
            and self.minutos() > 0
            and self.observacion.es_valido()
            and self.avance.es_valido()
        )

    def a_dict(self) -> dict:
        return {
            "momento": self.momento_entry.get().strip(),
            "minutos": self.minutos(),
            "observacion": self.observacion.get(),
            "avance": self.avance.get(),
        }
