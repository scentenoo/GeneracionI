"""Widgets chicos reutilizables entre pantallas."""

from __future__ import annotations

import customtkinter as ctk

MIN_PALABRAS = 20  # ver spec sección 6


def contar_palabras(texto: str) -> int:
    return len([p for p in texto.split() if p])


class CampoConContador(ctk.CTkFrame):
    """Textbox multilínea + contador de palabras en vivo que se pone verde
    a partir de MIN_PALABRAS (spec sección 6: "contador en vivo mientras el
    docente escribe")."""

    def __init__(self, master, etiqueta: str, alto: int = 90, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        ctk.CTkLabel(self, text=etiqueta, anchor="w").pack(fill="x")
        self.textbox = ctk.CTkTextbox(self, height=alto)
        self.textbox.pack(fill="x", pady=(2, 0))
        self.textbox.bind("<KeyRelease>", lambda _e: self._actualizar_contador())

        self.contador_label = ctk.CTkLabel(self, text="", anchor="e", font=ctk.CTkFont(size=11))
        self.contador_label.pack(fill="x")

        self._actualizar_contador()

    def _actualizar_contador(self):
        n = contar_palabras(self.get())
        color = "#2fa84f" if n >= MIN_PALABRAS else "#c0392b"
        self.contador_label.configure(text=f"{n} palabras (mínimo {MIN_PALABRAS})", text_color=color)

    def get(self) -> str:
        return self.textbox.get("1.0", "end").strip()

    def set(self, texto: str):
        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", texto)
        self._actualizar_contador()

    def es_valido(self) -> bool:
        return contar_palabras(self.get()) >= MIN_PALABRAS
