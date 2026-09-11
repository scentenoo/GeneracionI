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
from ui import tema
from ui.cargando import Cargando
from ui.tareas import en_segundo_plano
from ui.widgets import chip

ROJO, VERDE, GRIS = tema.ROJO, tema.VERDE, tema.GRIS

# Ver la misma constante en revisar_planeaciones_screen.py: con listas
# largas, CTkScrollableFrame tiene un bug de fondo de Tk en Windows que
# corrompe el repintado al scrollear (sin arreglo posible desde acá —
# https://github.com/TomSchimansky/CustomTkinter/issues/215). "Mis
# planeaciones" no tiene límite de mes, así que con el tiempo crece sola.
_TANDA = 20


class PlaneacionListScreen(ctk.CTkScrollableFrame):
    def __init__(
        self,
        master,
        sesion: dict,
        on_editar: Callable[[dict], None],
        on_volver: Callable[[], None] | None = None,
    ):
        # Sin `on_volver` va montada como pestaña de PlaneacionesScreen.
        super().__init__(master, label_text="" if on_volver is None else "Mis planeaciones")
        self.sesion = sesion
        self.on_editar = on_editar

        if on_volver is not None:
            ctk.CTkButton(self, text="← Volver", width=90, command=on_volver).pack(anchor="w", pady=(0, 10))

        self.error_label = ctk.CTkLabel(self, text="", text_color=ROJO, wraplength=560, justify="left")
        self.error_label.pack(fill="x", pady=(0, 4))

        self.lista_contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self.lista_contenedor.pack(fill="both", expand=True)

        # «Mis planeaciones» se recarga cada vez que se entra a la pestaña
        # (ver PlaneacionesScreen._al_cambiar_pestana): si dos cargas quedan
        # en vuelo a la vez —por ejemplo, entrar y salir rápido dos veces—,
        # las dos terminan agregando filas sin saber una de la otra, y la
        # lista queda duplicada. Este número identifica cuál es la carga
        # vigente: si una respuesta llega y ya no es la última que se pidió,
        # se descarta en vez de agregarse encima.
        self._version_carga = 0
        self._planeaciones: list[dict] = []
        self._mostrar_hasta = _TANDA
        self._cargar()

    def _cargar(self):
        self._version_carga += 1
        version = self._version_carga

        for w in self.lista_contenedor.winfo_children():
            w.destroy()
        self.error_label.configure(text="")
        cargando = Cargando(self.lista_contenedor, texto="Cargando...")
        cargando.pack(pady=20)

        def listo(planeaciones):
            if version != self._version_carga:
                return  # una carga más nueva ya arrancó; esta quedó vieja
            cargando.detener()
            cargando.destroy()
            if not planeaciones:
                ctk.CTkLabel(
                    self.lista_contenedor,
                    text="Todavía no registraste ninguna planeación.",
                    text_color=GRIS,
                ).pack(anchor="w", pady=10)
                return

            planeaciones.sort(key=lambda p: p["fecha"], reverse=True)
            self._planeaciones = planeaciones
            self._mostrar_hasta = _TANDA
            self._redibujar()

        def fallo(exc):
            if version != self._version_carga:
                return
            cargando.detener()
            cargando.destroy()
            self.error_label.configure(text=str(exc), text_color=ROJO)

        en_segundo_plano(
            self,
            lambda: api_client.obtener_planeaciones(self.sesion["token"], resumen=True),
            listo,
            fallo,
        )

    def _redibujar(self):
        """Reconstruye la lista con lo que ya está en memoria, de a tandas
        (ver _TANDA) — no le pide nada de nuevo al backend."""
        for w in self.lista_contenedor.winfo_children():
            w.destroy()

        visibles = self._planeaciones[: self._mostrar_hasta]
        restantes = len(self._planeaciones) - len(visibles)
        for p in visibles:
            self._fila_planeacion(p)

        if restantes > 0:
            ctk.CTkButton(
                self.lista_contenedor,
                text=f"Cargar {min(restantes, _TANDA)} más ({restantes} sin mostrar)",
                fg_color="transparent", border_width=1, command=self._cargar_mas,
            ).pack(pady=10)

    def _cargar_mas(self):
        self._mostrar_hasta += _TANDA
        self._redibujar()

    def _fila_planeacion(self, p: dict):
        fila = ctk.CTkFrame(
            self.lista_contenedor, fg_color=tema.FONDO_TARJETA, corner_radius=10,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        fila.pack(fill="x", pady=4)

        info = ctk.CTkFrame(fila, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=10, pady=8)

        try:
            fecha_legible = date_utils.a_fecha_larga(p["fecha"])
        except ValueError:
            fecha_legible = p["fecha"]

        ctk.CTkLabel(
            info, text=f"{fecha_legible} — {p['grupo']}", font=tema.fuente(peso="bold"), anchor="w"
        ).pack(fill="x")
        objetivo = str(p.get("objetivo", ""))
        ctk.CTkLabel(
            info, text=objetivo[:120] + ("..." if len(objetivo) > 120 else ""),
            text_color=GRIS, anchor="w", justify="left", wraplength=350,
        ).pack(fill="x")

        if p.get("bloqueada"):
            fila_bloqueada = ctk.CTkFrame(info, fg_color="transparent")
            fila_bloqueada.pack(fill="x", pady=(6, 0))
            chip(fila_bloqueada, "mes cerrado", GRIS)
            ctk.CTkLabel(
                fila_bloqueada, text="pídale al equipo directivo que lo reabra",
                text_color=GRIS, anchor="w", font=tema.fuente(11),
            ).pack(side="left")
            return

        acciones = ctk.CTkFrame(fila, fg_color="transparent")
        acciones.pack(side="right", padx=10)
        ctk.CTkButton(
            acciones, text="Eliminar", width=90, fg_color=ROJO, hover_color=tema.ROJO_HOVER,
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
