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

    def __init__(self, master, etiqueta: str, alto: int = 90, minimo: int = MIN_PALABRAS, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.minimo = minimo

        ctk.CTkLabel(self, text=etiqueta, anchor="w").pack(fill="x")
        self.textbox = ctk.CTkTextbox(self, height=alto)
        self.textbox.pack(fill="x", pady=(2, 0))
        self.textbox.bind("<KeyRelease>", lambda _e: self._actualizar_contador())

        self.contador_label = ctk.CTkLabel(self, text="", anchor="e", font=ctk.CTkFont(size=11))
        self.contador_label.pack(fill="x")

        self._actualizar_contador()

    def _actualizar_contador(self):
        n = contar_palabras(self.get())
        color = "#2fa84f" if n >= self.minimo else "#c0392b"
        self.contador_label.configure(text=f"{n} palabras (mínimo {self.minimo})", text_color=color)

    def get(self) -> str:
        return self.textbox.get("1.0", "end").strip()

    def set(self, texto: str):
        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", texto)
        self._actualizar_contador()

    def es_valido(self) -> bool:
        return contar_palabras(self.get()) >= self.minimo


class CampoConInstruccion(ctk.CTkFrame):
    """Campo de texto con la pregunta arriba y la instrucción como marca de
    agua adentro: el texto gris de guía desaparece al escribir y vuelve si el
    campo queda vacío. Así el docente ve qué se espera sin que la instrucción
    se confunda con su respuesta.

    Con `minimo` muestra además el contador en vivo de CampoConContador,
    para las preguntas del informe mensual que también piden un mínimo de
    palabras."""

    def __init__(self, master, etiqueta: str, instruccion: str = "", alto: int = 70, minimo: int = 0):
        super().__init__(master, fg_color="transparent")
        self.minimo = minimo
        ctk.CTkLabel(self, text=etiqueta, anchor="w", justify="left", wraplength=560).pack(
            fill="x", pady=(10, 0)
        )
        self.instruccion = instruccion
        self.textbox = ctk.CTkTextbox(self, height=alto)
        self.textbox.pack(fill="x", pady=(2, 0))
        self._color_normal = self.textbox.cget("text_color")
        self._placeholder = False
        self.textbox.bind("<FocusIn>", self._al_entrar)
        self.textbox.bind("<FocusOut>", self._al_salir)
        self.textbox.bind("<KeyRelease>", lambda _e: self._actualizar_contador())

        if self.minimo:
            self.contador_label = ctk.CTkLabel(self, text="", anchor="e", font=ctk.CTkFont(size=11))
            self.contador_label.pack(fill="x")

        self._poner_placeholder()
        self._actualizar_contador()

    def _actualizar_contador(self):
        if not self.minimo:
            return
        n = contar_palabras(self.get())
        color = "#2fa84f" if n >= self.minimo else "#c0392b"
        self.contador_label.configure(text=f"{n} palabras (mínimo {self.minimo})", text_color=color)

    def _poner_placeholder(self):
        if self.instruccion:
            self.textbox.delete("1.0", "end")
            self.textbox.insert("1.0", self.instruccion)
            self.textbox.configure(text_color="gray")
            self._placeholder = True

    def _al_entrar(self, _e=None):
        if self._placeholder:
            self.textbox.delete("1.0", "end")
            self.textbox.configure(text_color=self._color_normal)
            self._placeholder = False

    def _al_salir(self, _e=None):
        if not self.textbox.get("1.0", "end").strip():
            self._poner_placeholder()
            self._actualizar_contador()

    def get(self) -> str:
        return "" if self._placeholder else self.textbox.get("1.0", "end").strip()

    def set(self, texto: str):
        if texto:
            self.textbox.delete("1.0", "end")
            self.textbox.configure(text_color=self._color_normal)
            self.textbox.insert("1.0", texto)
            self._placeholder = False
        else:
            self._poner_placeholder()
        self._actualizar_contador()
