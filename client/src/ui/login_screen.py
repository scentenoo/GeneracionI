"""Pantalla de login — punto de partida para que Generación-I la termine de
diseñar (logo, eslogan, frases motivadoras elegidas por votación, ver spec
sección 8). Funcionalmente ya llama al backend real; lo que falta es
estética y pulir la experiencia.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

import api_client


class LoginScreen(ctk.CTkFrame):
    def __init__(self, master, on_login_exitoso: Callable[[dict], None]):
        super().__init__(master)
        self.on_login_exitoso = on_login_exitoso

        ctk.CTkLabel(self, text="Generación-I", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(40, 10))
        ctk.CTkLabel(self, text="Planeaciones y asistencia").pack(pady=(0, 30))

        self.usuario_entry = ctk.CTkEntry(self, placeholder_text="Usuario", width=260)
        self.usuario_entry.pack(pady=8)

        self.password_entry = ctk.CTkEntry(self, placeholder_text="Contraseña", show="*", width=260)
        self.password_entry.pack(pady=8)
        self.password_entry.bind("<Return>", lambda _e: self._intentar_login())

        self.error_label = ctk.CTkLabel(self, text="", text_color="red")
        self.error_label.pack(pady=(4, 0))

        ctk.CTkButton(self, text="Ingresar", command=self._intentar_login, width=260).pack(pady=20)

    def _intentar_login(self):
        usuario = self.usuario_entry.get().strip()
        password = self.password_entry.get()
        if not usuario or not password:
            self.error_label.configure(text="Completá usuario y contraseña")
            return

        self.error_label.configure(text="Ingresando...")
        try:
            sesion = api_client.login(usuario, password)
        except api_client.ApiError as exc:
            self.error_label.configure(text=str(exc))
            return

        self.on_login_exitoso(sesion)
