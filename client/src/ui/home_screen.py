"""Menú post-login: botones agrupados por para-qué-sirven (spec sección 8).

Antes eran hasta doce botones en una sola columna, mezclando el trabajo de
aula, la supervisión del equipo y la cuenta propia. Ahora van en tres
secciones con un título cada una, para que quien entra encuentre lo suyo
sin recorrer todo.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk


class HomeScreen(ctk.CTkScrollableFrame):
    def __init__(
        self,
        master,
        sesion: dict,
        on_planeaciones: Callable[[], None],
        on_dashboard: Callable[[], None],
        on_informe: Callable[[], None],
        on_informes_mes: Callable[[], None],
        on_grupo: Callable[[], None],
        on_cursos: Callable[[], None],
        on_horas_gestion: Callable[[], None],
        on_planeaciones_docente: Callable[[], None],
        on_revisar: Callable[[], None],
        on_usuarios: Callable[[], None],
        on_cambiar_password: Callable[[], None],
        on_version: Callable[[], None],
    ):
        super().__init__(master)

        ctk.CTkLabel(
            self, text=f"Hola, {sesion['nombre']}", font=ctk.CTkFont(size=22, weight="bold")
        ).pack(pady=(24, 4))
        ctk.CTkLabel(self, text=f"Rol: {sesion['rol']}", text_color="gray").pack(pady=(0, 8))

        es_docente = sesion["rol"] in ("docente", "ambos")
        # El administrador entra a las pantallas de gestión aunque su rol
        # sea docente. Eso no lo vuelve directivo: su informe mensual sigue
        # siendo el de docente, porque administrar la app no es un cargo del
        # programa y no se cobran horas de gestión por eso.
        es_directivo = sesion["rol"] in ("directivo", "ambos") or bool(sesion.get("es_admin"))

        if es_docente:
            self._seccion("Como docente")
            self._boton("Planeaciones y actividades", on_planeaciones)
            self._boton("Generar informe mensual", on_informe)
        elif es_directivo:
            # Un directivo sin componente docente igual entrega su informe
            # de gestión, así que el botón no puede vivir solo en la sección
            # docente.
            self._seccion("Mi informe")
            self._boton("Generar informe mensual", on_informe)

        if es_directivo:
            self._seccion("Dirección")
            self._boton("Dashboard del mes", on_dashboard)
            self._boton("Informes del mes", on_informes_mes)
            self._boton("Revisar planeaciones e informes", on_revisar)
            self._boton("Cursos", on_cursos)
            self._boton("Estudiantes de un curso", on_grupo)
            self._boton("Planeaciones de un docente", on_planeaciones_docente)
            self._boton("Horas de gestión", on_horas_gestion)
            self._boton("Usuarios", on_usuarios)

        self._seccion("Mi cuenta")
        self._boton("Cambiar contraseña", on_cambiar_password)
        # Publicar una versión bloquea a quien no la tenga, así que va
        # detrás del administrador único y no del rol directivo.
        if sesion.get("es_admin"):
            self._boton("Versión de la app", on_version)

    def _seccion(self, titulo: str):
        ctk.CTkLabel(
            self, text=titulo.upper(), text_color="gray",
            font=ctk.CTkFont(size=12, weight="bold"), anchor="w",
        ).pack(fill="x", padx=40, pady=(16, 2))

    def _boton(self, texto: str, comando: Callable[[], None]):
        ctk.CTkButton(self, text=texto, width=260, command=comando).pack(pady=4)
