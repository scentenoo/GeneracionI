from __future__ import annotations

import customtkinter as ctk

from ui.login_screen import LoginScreen
from ui.home_screen import HomeScreen


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Generación-I — Planeaciones")
        self.geometry("480x520")

        self.sesion: dict | None = None
        self._mostrar_login()

    def _mostrar_login(self):
        self._limpiar()
        LoginScreen(self, on_login_exitoso=self._on_login_exitoso).pack(fill="both", expand=True)

    def _on_login_exitoso(self, sesion: dict):
        self.sesion = sesion
        self._limpiar()
        HomeScreen(self, sesion).pack(fill="both", expand=True)

    def _limpiar(self):
        for widget in self.winfo_children():
            widget.destroy()
