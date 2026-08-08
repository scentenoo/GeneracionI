"""Placeholder post-login. Acá arrancan las pantallas reales que construye
Generación-I: formulario de planeación por bloques, checklist de
asistencia, dashboard directivo (spec sección 8). Esto solo confirma que el
login funcionó y muestra qué rol quedó activo.
"""

from __future__ import annotations

import customtkinter as ctk


class HomeScreen(ctk.CTkFrame):
    def __init__(self, master, sesion: dict):
        super().__init__(master)

        ctk.CTkLabel(
            self,
            text=f"Hola, {sesion['nombre']}",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(pady=(40, 10))
        ctk.CTkLabel(self, text=f"Rol: {sesion['rol']}").pack(pady=(0, 30))

        # TODO (Generación-I): acá van los botones/pantallas reales según el rol:
        #   - docente / ambos: nueva planeación, mis planeaciones, asistencia
        #   - directivo / ambos: dashboard, grupos de estudiantes, informes
        ctk.CTkLabel(
            self,
            text="Pantallas pendientes: planeación, asistencia, dashboard...",
            text_color="gray",
        ).pack(pady=10)
