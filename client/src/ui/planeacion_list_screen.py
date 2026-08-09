"""Mis planeaciones: verlas, editarlas y eliminarlas (spec sección 3:
"Docente: CRUD de sus propias planeaciones"). Solo el dueño puede borrar
la suya — ver Planeaciones.js#eliminar_planeacion.

Pasada la fecha de corte del mes, editar y eliminar desaparecen: lo que
el equipo directivo ya usó para armar la cuenta de cobro no puede cambiar
por atrás. El backend lo vuelve a verificar igual.
"""

from __future__ import annotations

from tkinter import messagebox
from typing import Callable

import customtkinter as ctk

import api_client
from services import date_utils
from ui.tareas import en_segundo_plano

ROJO, VERDE, GRIS = "#c0392b", "#2fa84f", "gray"


class PlaneacionListScreen(ctk.CTkScrollableFrame):
    def __init__(
        self,
        master,
        sesion: dict,
        on_volver: Callable[[], None],
        on_editar: Callable[[dict], None],
    ):
        super().__init__(master, label_text="Mis planeaciones")
        self.sesion = sesion
        self.on_editar = on_editar

        ctk.CTkButton(self, text="← Volver", width=90, command=on_volver).pack(anchor="w", pady=(0, 10))

        self.error_label = ctk.CTkLabel(self, text="", text_color=ROJO, wraplength=560, justify="left")
        self.error_label.pack(fill="x", pady=(0, 4))

        self.lista_contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self.lista_contenedor.pack(fill="both", expand=True)

        self._cargar()

    def _cargar(self):
        for w in self.lista_contenedor.winfo_children():
            w.destroy()
        self.error_label.configure(text="Cargando...", text_color=GRIS)

        def listo(planeaciones):
            self.error_label.configure(text="")
            if not planeaciones:
                ctk.CTkLabel(
                    self.lista_contenedor,
                    text="Todavía no registraste ninguna planeación.",
                    text_color=GRIS,
                ).pack(anchor="w", pady=10)
                return

            planeaciones.sort(key=lambda p: p["fecha"], reverse=True)
            for p in planeaciones:
                self._fila_planeacion(p)

        en_segundo_plano(
            self,
            lambda: api_client.obtener_planeaciones(self.sesion["token"], resumen=True),
            listo,
            lambda exc: self.error_label.configure(text=str(exc), text_color=ROJO),
        )

    def _fila_planeacion(self, p: dict):
        fila = ctk.CTkFrame(self.lista_contenedor, border_width=1, corner_radius=8)
        fila.pack(fill="x", pady=4)

        info = ctk.CTkFrame(fila, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=10, pady=8)

        try:
            fecha_legible = date_utils.a_fecha_larga(p["fecha"])
        except ValueError:
            fecha_legible = p["fecha"]

        ctk.CTkLabel(
            info, text=f"{fecha_legible} — {p['grupo']}", font=ctk.CTkFont(weight="bold"), anchor="w"
        ).pack(fill="x")
        objetivo = str(p.get("objetivo", ""))
        ctk.CTkLabel(
            info, text=objetivo[:120] + ("..." if len(objetivo) > 120 else ""),
            text_color=GRIS, anchor="w", justify="left", wraplength=350,
        ).pack(fill="x")

        if p.get("bloqueada"):
            ctk.CTkLabel(
                info, text="Mes cerrado — pedile al equipo directivo que lo reabra",
                text_color=GRIS, anchor="w", font=ctk.CTkFont(size=11),
            ).pack(fill="x", pady=(4, 0))
            return

        acciones = ctk.CTkFrame(fila, fg_color="transparent")
        acciones.pack(side="right", padx=10)
        ctk.CTkButton(
            acciones, text="Eliminar", width=90, fg_color=ROJO, hover_color="#922b21",
            command=lambda: self._eliminar(p),
        ).pack(pady=2)
        ctk.CTkButton(
            acciones, text="Editar", width=90, command=lambda: self.on_editar(p)
        ).pack(pady=2)

    def _eliminar(self, p: dict):
        """Borrar una planeación se lleva puesta la foto de la clase y la
        asistencia de ese día, y no hay de dónde recuperarlas: por eso
        pregunta antes."""
        try:
            fecha = date_utils.a_fecha_larga(p["fecha"])
        except ValueError:
            fecha = p["fecha"]

        if not messagebox.askyesno(
            "Eliminar planeación",
            f"¿Eliminar la planeación del {fecha} de «{p['grupo']}»?\n\n"
            "Se borra también la foto de la clase y la asistencia de ese día.\n"
            "Esto no se puede deshacer.",
            icon="warning",
            default="no",
        ):
            return

        self.error_label.configure(text="Eliminando...", text_color=GRIS)

        en_segundo_plano(
            self,
            lambda: api_client.eliminar_planeacion(self.sesion["token"], p["id"]),
            lambda _r: self._cargar(),
            lambda exc: self.error_label.configure(text=str(exc), text_color=ROJO),
        )
