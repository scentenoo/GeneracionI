"""Menú post-login: botones según el rol de la sesión (spec sección 8)."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk


class HomeScreen(ctk.CTkFrame):
    def __init__(
        self,
        master,
        sesion: dict,
        on_nueva_planeacion: Callable[[], None],
        on_dashboard: Callable[[], None],
    ):
        super().__init__(master)

        ctk.CTkLabel(
            self,
            text=f"Hola, {sesion['nombre']}",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(pady=(40, 4))
        ctk.CTkLabel(self, text=f"Rol: {sesion['rol']}", text_color="gray").pack(pady=(0, 30))

        es_docente = sesion["rol"] in ("docente", "ambos")
        es_directivo = sesion["rol"] in ("directivo", "ambos")

        if es_docente:
            ctk.CTkButton(self, text="Nueva planeación de clase", width=260, command=on_nueva_planeacion).pack(
                pady=8
            )
        if es_directivo:
            ctk.CTkButton(self, text="Dashboard directivo", width=260, command=on_dashboard).pack(pady=8)

        # TODO (Generación-I): mis planeaciones, grupo de estudiantes,
        # generar informe mensual, cambiar contraseña...
