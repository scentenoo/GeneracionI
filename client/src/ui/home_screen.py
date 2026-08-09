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
        on_mis_planeaciones: Callable[[], None],
        on_actividades: Callable[[], None],
        on_dashboard: Callable[[], None],
        on_informe: Callable[[], None],
        on_grupo: Callable[[], None],
        on_cursos: Callable[[], None],
        on_horas_gestion: Callable[[], None],
        on_planeaciones_docente: Callable[[], None],
        on_usuarios: Callable[[], None],
        on_cambiar_password: Callable[[], None],
        on_version: Callable[[], None],
    ):
        super().__init__(master)

        ctk.CTkLabel(
            self,
            text=f"Hola, {sesion['nombre']}",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(pady=(30, 4))
        ctk.CTkLabel(self, text=f"Rol: {sesion['rol']}", text_color="gray").pack(pady=(0, 20))

        es_docente = sesion["rol"] in ("docente", "ambos")
        es_directivo = sesion["rol"] in ("directivo", "ambos")

        if es_docente:
            ctk.CTkButton(self, text="Nueva planeación de clase", width=260, command=on_nueva_planeacion).pack(
                pady=6
            )
            ctk.CTkButton(self, text="Mis planeaciones", width=260, command=on_mis_planeaciones).pack(pady=6)
            ctk.CTkButton(self, text="Otras actividades del mes", width=260, command=on_actividades).pack(pady=6)
        ctk.CTkButton(self, text="Generar informe mensual", width=260, command=on_informe).pack(pady=6)
        if es_directivo:
            ctk.CTkButton(self, text="Dashboard directivo", width=260, command=on_dashboard).pack(pady=6)
            ctk.CTkButton(self, text="Cursos", width=260, command=on_cursos).pack(pady=6)
            ctk.CTkButton(self, text="Estudiantes de un curso", width=260, command=on_grupo).pack(pady=6)
            ctk.CTkButton(self, text="Horas de gestión", width=260, command=on_horas_gestion).pack(pady=6)
            ctk.CTkButton(
                self, text="Planeaciones de un docente", width=260, command=on_planeaciones_docente
            ).pack(pady=6)
            ctk.CTkButton(self, text="Usuarios", width=260, command=on_usuarios).pack(pady=6)
        ctk.CTkButton(self, text="Cambiar contraseña", width=260, command=on_cambiar_password).pack(pady=6)

        # Publicar una versión bloquea a quien no la tenga, así que va
        # detrás del administrador único y no del rol directivo.
        if sesion.get("es_admin"):
            ctk.CTkButton(self, text="Versión de la app", width=260, command=on_version).pack(pady=6)
