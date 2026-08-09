"""Mis planeaciones: verlas y eliminarlas (spec sección 3: "Docente: CRUD
de sus propias planeaciones"). Solo el dueño puede borrar la suya — ver
Planeaciones.js#eliminar_planeacion."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

import api_client
from services import date_utils


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

        self.error_label = ctk.CTkLabel(self, text="", text_color="#c0392b", wraplength=450, justify="left")
        self.error_label.pack(fill="x", pady=(0, 4))

        self.lista_contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self.lista_contenedor.pack(fill="both", expand=True)

        self._cargar()

    def _cargar(self):
        for w in self.lista_contenedor.winfo_children():
            w.destroy()
        self.error_label.configure(text="")

        try:
            planeaciones = api_client.obtener_planeaciones(self.sesion["token"])
        except api_client.ApiError as exc:
            self.error_label.configure(text=str(exc))
            return

        if not planeaciones:
            ctk.CTkLabel(self.lista_contenedor, text="Todavía no registraste ninguna planeación.", text_color="gray").pack(
                anchor="w", pady=10
            )
            return

        planeaciones.sort(key=lambda p: p["fecha"], reverse=True)
        for p in planeaciones:
            self._fila_planeacion(p)

    def _fila_planeacion(self, p: dict):
        fila = ctk.CTkFrame(self.lista_contenedor, border_width=1, corner_radius=8)
        fila.pack(fill="x", pady=4)

        info = ctk.CTkFrame(fila, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=10, pady=8)

        try:
            fecha_legible = date_utils.a_fecha_larga(p["fecha"])
        except ValueError:
            fecha_legible = p["fecha"]

        ctk.CTkLabel(info, text=f"{fecha_legible} — {p['grupo']}", font=ctk.CTkFont(weight="bold"), anchor="w").pack(
            fill="x"
        )
        objetivo_corto = p["objetivo"][:120] + ("..." if len(p["objetivo"]) > 120 else "")
        ctk.CTkLabel(info, text=objetivo_corto, text_color="gray", anchor="w", justify="left", wraplength=350).pack(
            fill="x"
        )

        acciones = ctk.CTkFrame(fila, fg_color="transparent")
        acciones.pack(side="right", padx=10)
        ctk.CTkButton(
            acciones, text="Eliminar", width=90, fg_color="#c0392b", hover_color="#922b21",
            command=lambda: self._eliminar(p["id"]),
        ).pack(pady=2)
        ctk.CTkButton(
            acciones, text="Editar", width=90, command=lambda: self.on_editar(p)
        ).pack(pady=2)

    def _eliminar(self, planeacion_id: int):
        try:
            api_client.eliminar_planeacion(self.sesion["token"], planeacion_id)
        except api_client.ApiError as exc:
            self.error_label.configure(text=str(exc), text_color="#c0392b")
            return
        self._cargar()
