"""Menú post-login: botones agrupados por para-qué-sirven (spec sección 8).

Antes eran hasta doce botones en una sola columna, mezclando el trabajo de
aula, la supervisión del equipo y la cuenta propia. Ahora van en tres
secciones con un título cada una, para que quien entra encuentre lo suyo
sin recorrer todo.
"""

from __future__ import annotations

from tkinter import messagebox
from typing import Callable

import customtkinter as ctk

import api_client
from services.avisos import texto_devoluciones
from ui.tareas import en_segundo_plano

AMBAR = "#8A6114"


class HomeScreen(ctk.CTkScrollableFrame):
    def __init__(
        self,
        master,
        sesion: dict,
        on_planeaciones: Callable[[], None],
        on_informe: Callable[[], None],
        on_cursos: Callable[[], None],
        on_horas_gestion: Callable[[], None],
        on_revisar: Callable[[], None],
        on_usuarios: Callable[[], None],
        on_cambiar_password: Callable[[], None],
        on_version: Callable[[], None],
        on_revisores: Callable[[], None],
    ):
        super().__init__(master)
        self.sesion = sesion
        self._devoluciones: list[dict] = []

        encabezado = ctk.CTkFrame(self, fg_color="transparent")
        encabezado.pack(fill="x", padx=16, pady=(16, 0))
        # Repite lo mismo que ya se avisa al entrar (ver App._avisos_al_entrar),
        # pero acá queda a mano todo el tiempo: si el docente cerró el aviso
        # sin leerlo bien, o vuelve horas después, no lo perdió.
        self.campana_boton = ctk.CTkButton(
            encabezado, text="🔔", width=36, height=32, fg_color="transparent",
            border_width=1, state="disabled", command=self._mostrar_devoluciones,
        )
        self.campana_boton.pack(side="right")
        self._cargar_devoluciones()

        ctk.CTkLabel(
            self, text=f"Hola, {sesion['nombre']}", font=ctk.CTkFont(size=22, weight="bold")
        ).pack(pady=(8, 4))
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
            self._boton("Revisar planeaciones e informes", on_revisar)
            self._boton("Cursos", on_cursos)
            self._boton("Horas de gestión", on_horas_gestion)
            self._boton("Usuarios", on_usuarios)

        self._seccion("Mi cuenta")
        self._boton("Cambiar contraseña", on_cambiar_password)
        # Publicar una versión bloquea a quien no la tenga, y reasignar
        # revisores cambia quién aprueba el trabajo de todos: las dos van
        # detrás del administrador único y no del rol directivo.
        if sesion.get("es_admin"):
            self._boton("Revisores por color", on_revisores)
            self._boton("Versión de la app", on_version)

    def _seccion(self, titulo: str):
        ctk.CTkLabel(
            self, text=titulo.upper(), text_color="gray",
            font=ctk.CTkFont(size=12, weight="bold"), anchor="w",
        ).pack(fill="x", padx=40, pady=(16, 2))

    def _boton(self, texto: str, comando: Callable[[], None]):
        ctk.CTkButton(self, text=texto, width=260, command=comando).pack(pady=4)

    # --- campanita de devoluciones ---------------------------------------

    def _cargar_devoluciones(self):
        en_segundo_plano(
            self,
            lambda: api_client.mis_devoluciones(self.sesion["token"]),
            self._al_cargar_devoluciones,
            lambda _exc: None,  # la campanita es un extra: si falla, no molesta
        )

    def _al_cargar_devoluciones(self, devoluciones: list[dict]):
        self._devoluciones = devoluciones or []
        if not self._devoluciones:
            return
        self.campana_boton.configure(
            text=f"🔔 {len(self._devoluciones)}", state="normal",
            fg_color=AMBAR, hover_color="#6b4d10", text_color="white",
        )

    def _mostrar_devoluciones(self):
        messagebox.showwarning("Te devolvieron esto", texto_devoluciones(self._devoluciones))
