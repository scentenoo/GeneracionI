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
from ui.widgets import pildora

# Ver la misma constante en revisar_planeaciones_screen.py: con listas
# largas, CTkScrollableFrame tiene un bug de fondo de Tk en Windows que
# corrompe el repintado al scrollear (sin arreglo posible desde acá —
# https://github.com/TomSchimansky/CustomTkinter/issues/215). "Mis
# planeaciones" no tiene límite de mes, así que con el tiempo crece sola.
_TANDA = 20

# (ancho, peso): igual proporción que el grid del mockup — fecha y estado
# a ancho fijo, curso/objetivo se reparten lo que sobra.
_COLUMNAS = [("Fecha", 0, 100), ("Curso", 3, 0), ("Objetivo", 4, 0), ("Estado", 0, 130), ("Acciones", 0, 170)]


def _configurar_columnas(fila: ctk.CTkFrame):
    for i, (_titulo, peso, minsize) in enumerate(_COLUMNAS):
        fila.grid_columnconfigure(i, weight=peso, minsize=minsize, uniform="col" if peso == 0 else "")


class PlaneacionListScreen(ctk.CTkScrollableFrame):
    def __init__(
        self,
        master,
        sesion: dict,
        on_editar: Callable[[dict], None],
        on_volver: Callable[[], None] | None = None,
    ):
        # Sin `on_volver` va montada como pestaña de PlaneacionesScreen.
        super().__init__(master, label_text="" if on_volver is None else "Mis planeaciones", fg_color="transparent")
        self.sesion = sesion
        self.on_editar = on_editar

        if on_volver is not None:
            ctk.CTkButton(
                self, text="← Volver", width=90, fg_color="transparent", border_width=1,
                text_color=tema.TEXTO_OSCURO, hover_color=tema.FONDO_TARJETA, command=on_volver,
            ).pack(anchor="w", pady=(0, 12))

        cabecera = ctk.CTkFrame(self, fg_color="transparent")
        cabecera.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(
            cabecera, text="Mis planeaciones", font=tema.fuente(18, "bold"), anchor="w",
        ).pack(side="left")
        self.contador_label = ctk.CTkLabel(
            cabecera, text="", font=tema.fuente(12, "bold"), text_color=tema.TEXTO_MUTED,
            fg_color=tema.FONDO_CONTENIDO, corner_radius=999,
        )
        self.contador_label.pack(side="left", padx=(12, 0))

        # Chips de filtro por estado (client-side, sobre lo ya cargado —
        # el texto de búsqueda lo maneja el buscador del encabezado
        # superior de la app, ver `filtrar`).
        filtros = ctk.CTkFrame(cabecera, fg_color="transparent")
        filtros.pack(side="right")
        self._botones_filtro: dict[str, ctk.CTkButton] = {}
        for clave, etiqueta in (
            ("todas", "Todas"), ("aprobado", "Aprobadas"),
            ("pendiente", "Pendientes"), ("cerrado", "Mes cerrado"),
        ):
            boton = ctk.CTkButton(
                filtros, text=etiqueta, corner_radius=999, height=32,
                fg_color="transparent", border_width=1, border_color=tema.BORDE_TARJETA,
                text_color=tema.TEXTO_OSCURO, hover_color=tema.FONDO_TARJETA,
                command=lambda c=clave: self._elegir_filtro(c),
            )
            boton.pack(side="left", padx=(8, 0))
            self._botones_filtro[clave] = boton

        self.error_label = ctk.CTkLabel(self, text="", text_color=tema.ROJO, wraplength=760, justify="left")
        self.error_label.pack(fill="x", pady=(0, 8))

        self.tarjeta = ctk.CTkFrame(
            self, fg_color=tema.FONDO_TARJETA, corner_radius=16,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        self.tarjeta.pack(fill="both", expand=True)

        encabezado_tabla = ctk.CTkFrame(self.tarjeta, fg_color=tema.FONDO_CONTENIDO, corner_radius=0)
        encabezado_tabla.pack(fill="x")
        _configurar_columnas(encabezado_tabla)
        for i, (titulo, _peso, _minsize) in enumerate(_COLUMNAS):
            ctk.CTkLabel(
                encabezado_tabla, text=titulo.upper(), font=tema.fuente(10, "bold"),
                text_color=tema.TEXTO_MUTED, anchor="e" if titulo == "Acciones" else "w",
            ).grid(row=0, column=i, sticky="ew", padx=(20 if i == 0 else 10, 10), pady=12)

        self.lista_contenedor = ctk.CTkFrame(self.tarjeta, fg_color="transparent")
        self.lista_contenedor.pack(fill="both", expand=True)

        self.aviso_cerrado_label = ctk.CTkLabel(
            self.tarjeta, text="Las planeaciones de un mes cerrado no se pueden editar — "
                               "pídale al equipo directivo que lo reabra.",
            font=tema.fuente(11), text_color=tema.AMBAR, fg_color=tema.AMBAR_CHIP_BG,
            anchor="w", wraplength=760, justify="left",
        )

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
        self._filtro_texto = ""
        self._filtro_estado = "todas"
        self._marcar_filtro_activo()
        self._cargar()

    def filtrar(self, texto: str):
        """Lo llama el buscador del encabezado superior de la app (ver
        `PlaneacionesScreen._al_cambiar_pestana`) — filtra por curso u
        objetivo sobre lo que ya está en memoria, sin pedir nada al
        backend."""
        self._filtro_texto = texto.strip().lower()
        self._mostrar_hasta = _TANDA
        self._redibujar()

    def _elegir_filtro(self, clave: str):
        self._filtro_estado = clave
        self._mostrar_hasta = _TANDA
        self._marcar_filtro_activo()
        self._redibujar()

    def _marcar_filtro_activo(self):
        for clave, boton in self._botones_filtro.items():
            activo = clave == self._filtro_estado
            boton.configure(
                fg_color=tema.VERDE_OSCURO if activo else "transparent",
                text_color=tema.BLANCO if activo else tema.TEXTO_OSCURO,
                border_width=0 if activo else 1,
            )

    def _coincide_filtro(self, p: dict) -> bool:
        if self._filtro_texto:
            texto = f"{p.get('grupo', '')} {p.get('objetivo', '')}".lower()
            if self._filtro_texto not in texto:
                return False
        if self._filtro_estado == "todas":
            return True
        if self._filtro_estado == "cerrado":
            return bool(p.get("bloqueada"))
        if p.get("bloqueada"):
            return False
        if self._filtro_estado == "aprobado":
            return p.get("estado") == "aprobado"
        # "Pendientes" agrupa lo pendiente y lo devuelto: ambas necesitan
        # que el docente todavía haga algo, a diferencia de lo aprobado.
        return p.get("estado") != "aprobado"

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
            planeaciones.sort(key=lambda p: p["fecha"], reverse=True)
            self._planeaciones = planeaciones
            self._mostrar_hasta = _TANDA
            mes_actual = date_utils.hoy_iso()[:7]
            este_mes = sum(1 for p in planeaciones if str(p.get("fecha", ""))[:7] == mes_actual)
            self.contador_label.configure(text=f"  {este_mes} este mes  ")
            self._redibujar()

        def fallo(exc):
            if version != self._version_carga:
                return
            cargando.detener()
            cargando.destroy()
            self.error_label.configure(text=str(exc), text_color=tema.ROJO)

        en_segundo_plano(
            self,
            lambda: api_client.obtener_planeaciones(self.sesion["token"], resumen=True),
            listo,
            fallo,
        )

    def _redibujar(self):
        """Reconstruye la lista con lo que ya está en memoria, de a tandas
        (ver _TANDA) — no le pide nada de nuevo al backend. Aplica el
        filtro de texto (buscador del encabezado) y el chip de estado
        elegido antes de paginar."""
        for w in self.lista_contenedor.winfo_children():
            w.destroy()
        self.aviso_cerrado_label.pack_forget()

        if not self._planeaciones:
            ctk.CTkLabel(
                self.lista_contenedor, text="Todavía no registraste ninguna planeación.",
                text_color=tema.TEXTO_MUTED,
            ).pack(anchor="w", padx=20, pady=16)
            return

        filtradas = [p for p in self._planeaciones if self._coincide_filtro(p)]
        if not filtradas:
            ctk.CTkLabel(
                self.lista_contenedor, text="Ninguna planeación coincide con la búsqueda.",
                text_color=tema.TEXTO_MUTED,
            ).pack(anchor="w", padx=20, pady=16)
            return

        visibles = filtradas[: self._mostrar_hasta]
        restantes = len(filtradas) - len(visibles)
        for p in visibles:
            self._fila_planeacion(p)

        if any(p.get("bloqueada") for p in visibles):
            self.aviso_cerrado_label.pack(fill="x", padx=0, pady=0, ipady=12, ipadx=24)

        if restantes > 0:
            ctk.CTkButton(
                self.lista_contenedor,
                text=f"Cargar {min(restantes, _TANDA)} más ({restantes} sin mostrar)",
                fg_color="transparent", border_width=1, command=self._cargar_mas,
            ).pack(pady=12)

    def _cargar_mas(self):
        self._mostrar_hasta += _TANDA
        self._redibujar()

    def _fila_planeacion(self, p: dict):
        fila = ctk.CTkFrame(self.lista_contenedor, fg_color="transparent")
        fila.pack(fill="x")
        _configurar_columnas(fila)
        ctk.CTkFrame(self.lista_contenedor, fg_color=tema.DIVISOR, height=1).pack(fill="x")

        try:
            fecha_legible = date_utils.a_fecha_corta(p["fecha"])
        except ValueError:
            fecha_legible = p["fecha"]

        ctk.CTkLabel(
            fila, text=fecha_legible, font=tema.fuente(12), text_color=tema.TEXTO_MUTED, anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=(20, 10), pady=14)
        ctk.CTkLabel(
            fila, text=p["grupo"], font=tema.fuente(13, "bold"), anchor="w", justify="left", wraplength=220,
        ).grid(row=0, column=1, sticky="w", padx=10, pady=14)
        objetivo = str(p.get("objetivo", ""))
        ctk.CTkLabel(
            fila, text=objetivo[:140] + ("…" if len(objetivo) > 140 else ""),
            font=tema.fuente(12), text_color=tema.TEXTO_MUTED, anchor="w", justify="left", wraplength=320,
        ).grid(row=0, column=2, sticky="w", padx=10, pady=14)

        bloqueada = bool(p.get("bloqueada"))
        estado = p.get("estado", "pendiente")
        if bloqueada:
            estado_texto, estado_color, estado_fondo = "Mes cerrado", tema.TEXTO_MUTED, tema.FONDO_CONTENIDO
        elif estado == "aprobado":
            estado_texto, estado_color, estado_fondo = "Aprobada", tema.VERDE_CHIP_TEXTO, tema.VERDE_CHIP_BG
        elif estado == "devuelto":
            estado_texto, estado_color, estado_fondo = "Devuelta", tema.AMBAR, tema.AMBAR_CHIP_BG
        else:
            estado_texto, estado_color, estado_fondo = "Pendiente", tema.TEXTO_MUTED, tema.FONDO_CONTENIDO
        pildora(fila, estado_texto, estado_color, estado_fondo).grid(row=0, column=3, sticky="w", padx=10)

        acciones = ctk.CTkFrame(fila, fg_color="transparent")
        acciones.grid(row=0, column=4, sticky="e", padx=(10, 20))
        if bloqueada:
            ctk.CTkLabel(
                acciones, text="—", text_color=tema.TEXTO_MUTED, font=tema.fuente(12),
            ).pack()
            return

        ctk.CTkButton(
            acciones, text="Eliminar", width=80, fg_color=tema.ROJO, hover_color=tema.ROJO_HOVER,
            command=lambda: self._eliminar(p),
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            acciones, text="Editar", width=80, fg_color="transparent", border_width=1,
            border_color=tema.VERDE, text_color=tema.VERDE_CHIP_TEXTO, hover_color=tema.VERDE_CHIP_BG,
            command=lambda: self.on_editar(p),
        ).pack(side="left")

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

        self.error_label.configure(text="Eliminando...", text_color=tema.TEXTO_MUTED)

        en_segundo_plano(
            self,
            lambda: api_client.eliminar_planeacion(self.sesion["token"], p["id"]),
            lambda _r: self._cargar(),
            lambda exc: self.error_label.configure(text=str(exc), text_color=tema.ROJO),
        )
