"""Revisar horas externas del equipo directivo (solo administrador).

A diferencia de planeaciones e informes —que reparte el color del curso
entre dos revisores—, acá no hay curso de por medio: es horas de gestión
de un directivo, con foto+entregable como evidencia, y quien las revisa
es siempre el administrador (ver revisar_hora_gestion en el backend).

Maestro-detalle: a la izquierda una tarjeta por persona con su avance
contra la meta mensual (HORAS_OBJETIVO_MENSUAL); a la derecha, las
actividades de la persona elegida, para aprobar o devolver una por una.
"""

from __future__ import annotations

import webbrowser
from typing import Callable

import customtkinter as ctk

import api_client
from services import date_utils
from ui import tema
from ui.cargando import Cargando
from ui.tareas import en_segundo_plano
from ui.widgets import avatar_iniciales, chip

ROJO, VERDE, GRIS, AMBAR = tema.ROJO, tema.VERDE, tema.GRIS, tema.AMBAR

_PRIORIDAD_ESTADO = {"pendiente": 0, "devuelto": 1, "aprobado": 2}


def _url_drive(doc_id: str) -> str:
    return f"https://drive.google.com/file/d/{doc_id}/view"


class RevisarHorasScreen(ctk.CTkFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None] | None = None):
        super().__init__(master, fg_color="transparent")
        self.sesion = sesion
        self._resumen: list[dict] = []
        self._actividades: list[dict] = []
        self._directivo_seleccionado: int | None = None
        self._filtro_texto = ""

        if on_volver is not None:
            ctk.CTkButton(self, text="← Volver", width=90, command=on_volver).pack(anchor="w", padx=4, pady=(0, 8))

        encabezado = ctk.CTkFrame(self, fg_color="transparent")
        encabezado.pack(fill="x", padx=4)
        ctk.CTkLabel(encabezado, text="Mes").pack(side="left")
        self.mes_entry = ctk.CTkEntry(encabezado, width=90)
        self.mes_entry.insert(0, date_utils.hoy_iso()[:7])
        self.mes_entry.pack(side="left", padx=8)
        ctk.CTkButton(encabezado, text="Actualizar", width=100, command=self._cargar).pack(side="left")

        self.error_label = ctk.CTkLabel(self, text="", text_color=ROJO, anchor="w")
        self.error_label.pack(fill="x", padx=4, pady=(6, 0))

        cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True, pady=(8, 0))

        self.panel_personas = ctk.CTkScrollableFrame(cuerpo, width=260, label_text="Equipo directivo")
        self.panel_personas.pack(side="left", fill="y", padx=(0, 8))

        self.panel_detalle = ctk.CTkScrollableFrame(cuerpo, label_text="Actividades")
        self.panel_detalle.pack(side="left", fill="both", expand=True)

        self._cargar()

    # --- filtro (buscador del encabezado) ------------------------------

    def filtrar(self, texto: str):
        """Lo llama el buscador del encabezado superior (ver
        RevisarHubScreen) — filtra el equipo por nombre, sobre lo que ya
        está en memoria."""
        self._filtro_texto = texto.strip().lower()
        self._redibujar_personas()

    # --- carga ----------------------------------------------------------

    def _cargar(self):
        for w in self.panel_personas.winfo_children():
            w.destroy()
        for w in self.panel_detalle.winfo_children():
            w.destroy()
        Cargando(self.panel_personas, texto="Cargando...").pack(pady=16)
        self.error_label.configure(text="")

        mes = self.mes_entry.get().strip()

        def listo(datos):
            self._resumen = datos.get("resumen", [])
            self._actividades = datos.get("actividades", [])
            self._directivo_seleccionado = None
            self._redibujar_personas()
            self._redibujar_detalle()

        def fallo(exc):
            for w in self.panel_personas.winfo_children():
                w.destroy()
            self.error_label.configure(text=str(exc))

        en_segundo_plano(
            self,
            lambda: api_client.obtener_horas_del_equipo(self.sesion["token"], mes),
            listo,
            fallo,
        )

    # --- panel izquierdo: personas ---------------------------------------

    def _redibujar_personas(self):
        for w in self.panel_personas.winfo_children():
            w.destroy()

        personas = self._resumen
        if self._filtro_texto:
            personas = [p for p in personas if self._filtro_texto in str(p.get("nombre", "")).lower()]

        if not personas:
            texto = "Nadie coincide con la búsqueda." if self._filtro_texto else "Nadie registró horas este mes."
            ctk.CTkLabel(self.panel_personas, text=texto, text_color=GRIS, wraplength=220).pack(pady=10)
            return

        personas = sorted(personas, key=lambda p: str(p.get("nombre", "")).lower())
        for p in personas:
            self._tarjeta_persona(p)

    def _tarjeta_persona(self, p: dict):
        activo = p["directivo_id"] == self._directivo_seleccionado
        marco = ctk.CTkFrame(
            self.panel_personas, fg_color=tema.VERDE_OSCURO if activo else tema.FONDO_TARJETA,
            corner_radius=10, border_width=1, border_color=tema.BORDE_TARJETA, cursor="hand2",
        )
        marco.pack(fill="x", pady=4)

        color_texto = tema.TEXTO_CLARO if activo else tema.TEXTO_OSCURO
        color_muted = tema.TEXTO_CLARO_APAGADO if activo else tema.TEXTO_MUTED

        fila = ctk.CTkFrame(marco, fg_color="transparent")
        fila.pack(fill="x", padx=10, pady=(10, 4))
        avatar_iniciales(fila, str(p.get("nombre", "?"))).pack(side="left")
        textos = ctk.CTkFrame(fila, fg_color="transparent")
        textos.pack(side="left", padx=(8, 0), fill="x", expand=True)
        ctk.CTkLabel(
            textos, text=str(p.get("nombre", "")), font=tema.fuente(13, "bold"),
            text_color=color_texto, anchor="w", wraplength=160,
        ).pack(fill="x")
        ctk.CTkLabel(
            textos, text=str(p.get("rol", "")), text_color=color_muted, font=tema.fuente(11), anchor="w",
        ).pack(fill="x")

        barra = ctk.CTkProgressBar(marco)
        objetivo = p.get("objetivo") or 1
        barra.set(min(p.get("total_horas", 0) / objetivo, 1.0))
        barra.configure(progress_color=VERDE if p.get("cumple") else AMBAR)
        barra.pack(fill="x", padx=10, pady=(0, 4))

        ctk.CTkLabel(
            marco, text=f"{p.get('total_horas', 0)} de {p.get('objetivo', 0)} horas",
            text_color=color_muted, font=tema.fuente(11), anchor="w",
        ).pack(fill="x", padx=10, pady=(0, 10))

        for widget in (marco, fila, textos):
            widget.bind("<Button-1>", lambda _e, pid=p["directivo_id"]: self._elegir_persona(pid))

    def _elegir_persona(self, directivo_id: int):
        self._directivo_seleccionado = directivo_id
        self._redibujar_personas()
        self._redibujar_detalle()

    # --- panel derecho: actividades de la persona elegida ----------------

    def _redibujar_detalle(self):
        for w in self.panel_detalle.winfo_children():
            w.destroy()

        if self._directivo_seleccionado is None:
            ctk.CTkLabel(
                self.panel_detalle, text="Elija una persona a la izquierda para ver sus actividades.",
                text_color=GRIS,
            ).pack(pady=16)
            return

        actividades = [
            a for a in self._actividades if a["directivo_id"] == self._directivo_seleccionado
        ]
        actividades.sort(key=lambda a: a["fecha"], reverse=True)
        actividades.sort(key=lambda a: _PRIORIDAD_ESTADO.get(a.get("estado", "pendiente"), 0))

        if not actividades:
            ctk.CTkLabel(
                self.panel_detalle, text="Esta persona no registró horas este mes.", text_color=GRIS,
            ).pack(pady=16)
            return

        for a in actividades:
            self._fila_actividad(a)

    def _fila_actividad(self, a: dict):
        marco = ctk.CTkFrame(
            self.panel_detalle, fg_color=tema.FONDO_TARJETA, corner_radius=10,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        marco.pack(fill="x", pady=4)

        cuerpo = ctk.CTkFrame(marco, fg_color="transparent")
        cuerpo.pack(side="left", fill="both", expand=True, padx=12, pady=10)
        ctk.CTkLabel(
            cuerpo, text=f"{a.get('fecha', '')} — {a.get('actividad', '')} ({a.get('horas_sede', 0)}h)",
            font=tema.fuente(peso="bold"), anchor="w", justify="left", wraplength=420,
        ).pack(fill="x")
        if a.get("entregable"):
            ctk.CTkLabel(
                cuerpo, text=f"Entregable: {a['entregable']}", text_color=GRIS, anchor="w",
            ).pack(fill="x")

        enlaces = ctk.CTkFrame(cuerpo, fg_color="transparent")
        enlaces.pack(fill="x", pady=(4, 0))
        if a.get("foto_drive_id"):
            ctk.CTkButton(
                enlaces, text="Ver foto", width=90, fg_color="transparent", border_width=1,
                command=lambda: webbrowser.open(_url_drive(a["foto_drive_id"])),
            ).pack(side="left", padx=(0, 6))
        if a.get("link_soporte"):
            ctk.CTkButton(
                enlaces, text="Ver soporte", width=100, fg_color="transparent", border_width=1,
                command=lambda url=a["link_soporte"]: webbrowser.open(url),
            ).pack(side="left")

        estado_fila = ctk.CTkFrame(cuerpo, fg_color="transparent")
        estado_fila.pack(fill="x", pady=(6, 0))
        self._pintar_estado(estado_fila, a)

        botones = ctk.CTkFrame(marco, fg_color="transparent")
        botones.pack(side="right", padx=10)
        aprobar_boton = ctk.CTkButton(botones, text="Aprobar", width=90, fg_color=VERDE, hover_color=tema.VERDE_HOVER)
        aprobar_boton.pack(pady=2)
        devolver_boton = ctk.CTkButton(botones, text="Devolver", width=90, fg_color=AMBAR, hover_color=tema.AMBAR_HOVER)
        devolver_boton.pack(pady=2)
        botones_revision = (aprobar_boton, devolver_boton)
        aprobar_boton.configure(command=lambda: self._revisar(a, True, estado_fila, botones_revision))
        devolver_boton.configure(command=lambda: self._revisar(a, False, estado_fila, botones_revision))

    def _pintar_estado(self, estado_fila: ctk.CTkFrame, a: dict):
        for w in estado_fila.winfo_children():
            w.destroy()
        estado = a.get("estado", "pendiente")
        motivo = a.get("motivo_devolucion", "")
        if estado == "aprobado":
            chip(estado_fila, "Aprobada ✓", VERDE)
        elif estado == "devuelto":
            chip(estado_fila, "Devuelta", AMBAR)
            if motivo:
                ctk.CTkLabel(estado_fila, text=motivo, text_color=GRIS, anchor="w").pack(side="left")
        else:
            chip(estado_fila, "Pendiente de revisar", GRIS)

    def _revisar(self, a: dict, aprobar: bool, estado_fila: ctk.CTkFrame, botones: tuple):
        motivo = ""
        if not aprobar:
            dialogo = ctk.CTkInputDialog(
                title="Devolver",
                text="¿Por qué la devuelve? La persona va a ver este motivo:",
            )
            motivo = (dialogo.get_input() or "").strip()
            if not motivo:
                return  # sin motivo no se devuelve

        for b in botones:
            b.configure(state="disabled")
        for w in estado_fila.winfo_children():
            w.destroy()
        ctk.CTkLabel(estado_fila, text="Guardando...", text_color=GRIS, anchor="w").pack(side="left")

        def listo(resultado):
            a["estado"] = resultado["estado"]
            a["motivo_devolucion"] = motivo if not aprobar else ""
            self._redibujar_detalle()

        def fallo(exc):
            for b in botones:
                b.configure(state="normal")
            self._pintar_estado(estado_fila, a)
            self.error_label.configure(text=str(exc))

        en_segundo_plano(
            self,
            lambda: api_client.revisar_hora_gestion(self.sesion["token"], a["id"], aprobar, motivo),
            listo,
            fallo,
        )
