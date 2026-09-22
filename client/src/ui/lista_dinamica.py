"""Lista de renglones de texto simples con botón "+ Agregar" — se usa para
Temas de la clase (una idea por línea)."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk


class ListaDinamica(ctk.CTkFrame):
    def __init__(self, master, placeholder: str = "", on_change: Callable[[], None] | None = None):
        super().__init__(master, fg_color="transparent")
        self.placeholder = placeholder
        self.on_change = on_change
        self.filas: list[ctk.CTkEntry] = []

        self.contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self.contenedor.pack(fill="x")

        ctk.CTkButton(self, text="+ Agregar", width=100, command=self.agregar_fila).pack(anchor="w", pady=(4, 0))

        self.agregar_fila()

    def agregar_fila(self, texto: str = ""):
        fila = ctk.CTkFrame(self.contenedor, fg_color="transparent")
        fila.pack(fill="x", pady=2)

        entry = ctk.CTkEntry(fila, placeholder_text=self.placeholder)
        entry.pack(side="left", fill="x", expand=True)
        if texto:
            entry.insert(0, texto)
        entry.bind("<KeyRelease>", lambda _e: self._avisar_cambio())

        def quitar():
            self.filas.remove(entry)
            fila.destroy()
            self._avisar_cambio()

        ctk.CTkButton(fila, text="x", width=28, fg_color="#c0392b", hover_color="#922b21", command=quitar).pack(
            side="left", padx=(4, 0)
        )

        self.filas.append(entry)
        self._avisar_cambio()

    def _avisar_cambio(self):
        if self.on_change:
            self.on_change()

    def limpiar(self):
        """Vacía la lista y deja una fila en blanco, sin tocar el orden de
        empaquetado del contenedor."""
        for w in self.contenedor.winfo_children():
            w.destroy()
        self.filas = []
        self.agregar_fila()

    def valores(self) -> list[str]:
        return [e.get().strip() for e in self.filas if e.get().strip()]
