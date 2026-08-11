"""Cambiar la propia contraseña (spec sección 3: Samir asigna la inicial,
cada usuario la cambia después)."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

import api_client
from ui.tareas import en_segundo_plano


class PasswordScreen(ctk.CTkFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None]):
        super().__init__(master)
        self.sesion = sesion

        ctk.CTkButton(self, text="← Volver", width=90, command=on_volver).pack(anchor="w", padx=20, pady=(20, 10))

        ctk.CTkLabel(self, text="Cambiar contraseña", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(10, 20))

        self.actual_entry = ctk.CTkEntry(self, placeholder_text="Contraseña actual", show="*", width=260)
        self.actual_entry.pack(pady=6)
        self.nueva_entry = ctk.CTkEntry(self, placeholder_text="Contraseña nueva", show="*", width=260)
        self.nueva_entry.pack(pady=6)
        self.confirmar_entry = ctk.CTkEntry(self, placeholder_text="Repetir contraseña nueva", show="*", width=260)
        self.confirmar_entry.pack(pady=6)

        self.error_label = ctk.CTkLabel(self, text="", text_color="#c0392b")
        self.error_label.pack(pady=(6, 0))

        self.boton = ctk.CTkButton(self, text="Cambiar", command=self._cambiar)
        self.boton.pack(pady=16)

    def _cambiar(self):
        if self.nueva_entry.get() != self.confirmar_entry.get():
            self.error_label.configure(text="Las contraseñas nuevas no coinciden", text_color="#c0392b")
            return
        if len(self.nueva_entry.get()) < 6:
            self.error_label.configure(text="La contraseña nueva necesita al menos 6 caracteres", text_color="#c0392b")
            return

        # En segundo plano: en los equipos lentos de la sede, hacerlo en el
        # hilo de la interfaz congelaba la ventana ~3s sin ningún aviso.
        self.boton.configure(state="disabled", text="Cambiando...")
        self.error_label.configure(text="", text_color="gray")

        actual, nueva = self.actual_entry.get(), self.nueva_entry.get()

        def listo(_r):
            self.boton.configure(state="normal", text="Cambiar")
            self.error_label.configure(text="Contraseña cambiada ✓", text_color="#2fa84f")
            self.actual_entry.delete(0, "end")
            self.nueva_entry.delete(0, "end")
            self.confirmar_entry.delete(0, "end")

        def fallo(exc):
            self.boton.configure(state="normal", text="Cambiar")
            self.error_label.configure(text=str(exc), text_color="#c0392b")

        en_segundo_plano(
            self,
            lambda: api_client.cambiar_password(self.sesion["token"], actual, nueva),
            listo,
            fallo,
        )
