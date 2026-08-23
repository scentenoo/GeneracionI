"""Revisar las planeaciones del mes (Mariangel, Lorena, administrador).

Muestra TODAS las planeaciones del mes de los cursos que le tocan, no solo
las pendientes: aprobar o devolver una no la hace desaparecer de la lista,
se actualiza ahí mismo con el estado nuevo. Antes, aprobar/devolver volvía
a pedir todo de nuevo y la tarjeta se esfumaba — para revisar varias
seguidas era lento y confuso, no quedaba claro qué se había hecho.
"""

from __future__ import annotations

import webbrowser
from typing import Callable

import customtkinter as ctk

import api_client
from services import date_utils
from ui.cargando import Cargando
from ui.tareas import en_segundo_plano

ROJO, VERDE, GRIS, AMBAR = "#c0392b", "#2fa84f", "gray", "#8A6114"

# Lo que falta por decidir va primero; lo devuelto (a mitad de corregirse)
# en el medio; lo ya aprobado, al final — es lo que menos hace falta mirar.
_PRIORIDAD_ESTADO = {"pendiente": 0, "devuelto": 1, "aprobado": 2}


def _url_drive(doc_id: str) -> str:
    return f"https://drive.google.com/file/d/{doc_id}/view"


class RevisarPlaneacionesScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None] | None = None):
        # Sin `on_volver` va montada como pestaña de RevisarHubScreen.
        super().__init__(master, label_text="" if on_volver is None else "Planeaciones")
        self.sesion = sesion
        self._planeaciones: list[dict] = []
        self._mes_cargado = ""

        if on_volver is not None:
            ctk.CTkButton(self, text="← Volver", width=90, command=on_volver).pack(anchor="w", pady=(0, 10))

        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.pack(fill="x")
        ctk.CTkLabel(fila, text="Mes").pack(side="left")
        self.mes_entry = ctk.CTkEntry(fila, width=90)
        self.mes_entry.insert(0, date_utils.hoy_iso()[:7])
        self.mes_entry.pack(side="left", padx=8)
        ctk.CTkButton(fila, text="Actualizar", width=100, command=self._cargar).pack(side="left")

        self.resumen_label = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=15, weight="bold"), anchor="w"
        )
        self.resumen_label.pack(fill="x", pady=(14, 2))
        self.color_normal = self.resumen_label.cget("text_color")

        self.contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self.contenedor.pack(fill="both", expand=True, pady=(6, 0))

        self._cargar()

    def _cargar(self):
        for w in self.contenedor.winfo_children():
            w.destroy()
        self.resumen_label.configure(text="", text_color=GRIS)
        cargando = Cargando(self.contenedor, texto="Cargando planeaciones...")
        cargando.pack(pady=16)
        mes = self.mes_entry.get().strip()

        def listo(datos):
            self._mes_cargado = mes
            self._planeaciones = datos.get("planeaciones", [])
            self._actualizar_resumen()
            self._redibujar()

        def fallo(exc):
            for w in self.contenedor.winfo_children():
                w.destroy()
            self.resumen_label.configure(text=str(exc), text_color=ROJO)

        en_segundo_plano(
            self,
            lambda: api_client.revision_del_mes(self.sesion["token"], mes),
            listo,
            fallo,
        )

    def _redibujar(self):
        """Reconstruye la lista con lo que ya está en memoria —no le pide
        nada de nuevo al backend—, ordenada: pendientes primero, devueltas
        en el medio, aprobadas al final."""
        for w in self.contenedor.winfo_children():
            w.destroy()

        if not self._planeaciones:
            ctk.CTkLabel(
                self.contenedor, text="No hay planeaciones cargadas este mes.", text_color=GRIS
            ).pack(anchor="w", pady=10)
            return

        # Dos pasadas porque el sort de Python es estable: ordenar primero
        # por fecha y después por estado deja, dentro de cada estado, la
        # fecha más nueva arriba — sin eso un sort solo perdería ese orden.
        self._planeaciones.sort(key=lambda p: p["fecha"], reverse=True)
        self._planeaciones.sort(key=lambda p: _PRIORIDAD_ESTADO.get(p.get("estado", "pendiente"), 0))
        for p in self._planeaciones:
            self._fila_planeacion(p)

    def _actualizar_resumen(self):
        total = len(self._planeaciones)
        pendientes = sum(1 for p in self._planeaciones if p.get("estado", "pendiente") == "pendiente")
        self.resumen_label.configure(
            text=f"{total} planeación(es) este mes  ·  {pendientes} pendiente(s)  ·  {self._mes_cargado}",
            text_color=self.color_normal if pendientes else VERDE,
        )

    def _fila_planeacion(self, p: dict):
        marco = ctk.CTkFrame(self.contenedor, corner_radius=8, border_width=1)
        marco.pack(fill="x", pady=3)
        cuerpo = ctk.CTkFrame(marco, fg_color="transparent")
        cuerpo.pack(side="left", fill="both", expand=True, padx=12, pady=8)
        ctk.CTkLabel(
            cuerpo, text=f"{p['curso']} — {p['fecha']}", font=ctk.CTkFont(weight="bold"),
            anchor="w", justify="left", wraplength=380,
        ).pack(fill="x")
        ctk.CTkLabel(
            cuerpo, text=f"{p['docente']}  ·  {str(p.get('objetivo', ''))[:60]}",
            text_color=GRIS, anchor="w",
        ).pack(fill="x")
        estado_label = ctk.CTkLabel(cuerpo, text="", anchor="w", font=ctk.CTkFont(size=12))
        estado_label.pack(fill="x", pady=(2, 0))
        self._pintar_estado(estado_label, p)

        botones = ctk.CTkFrame(marco, fg_color="transparent")
        botones.pack(side="right", padx=10)
        if p.get("doc_drive_id"):
            ctk.CTkButton(
                botones, text="Abrir", width=70, fg_color="transparent", border_width=1,
                command=lambda: webbrowser.open(_url_drive(p["doc_drive_id"])),
            ).pack(pady=2)
        aprobar_boton = ctk.CTkButton(botones, text="Aprobar", width=90, fg_color=VERDE, hover_color="#248a3d")
        aprobar_boton.pack(pady=2)
        devolver_boton = ctk.CTkButton(botones, text="Devolver", width=90, fg_color=AMBAR, hover_color="#6b4d10")
        devolver_boton.pack(pady=2)
        botones_revision = (aprobar_boton, devolver_boton)
        aprobar_boton.configure(command=lambda: self._revisar(p, True, estado_label, botones_revision))
        devolver_boton.configure(command=lambda: self._revisar(p, False, estado_label, botones_revision))

    def _pintar_estado(self, estado_label: ctk.CTkLabel, p: dict):
        estado = p.get("estado", "pendiente")
        motivo = p.get("motivo_devolucion", "")
        if estado == "aprobado":
            estado_label.configure(text="Aprobada ✓", text_color=VERDE)
        elif estado == "devuelto":
            estado_label.configure(text=f"Devuelta: {motivo}" if motivo else "Devuelta", text_color=AMBAR)
        else:
            estado_label.configure(text="Pendiente de revisar", text_color=GRIS)

    def _revisar(self, p: dict, aprobar: bool, estado_label: ctk.CTkLabel, botones: tuple):
        motivo = ""
        if not aprobar:
            dialogo = ctk.CTkInputDialog(
                title="Devolver",
                text="¿Por qué la devolvés? El docente va a ver este motivo:",
            )
            motivo = (dialogo.get_input() or "").strip()
            if not motivo:
                return  # sin motivo no se devuelve

        for b in botones:
            b.configure(state="disabled")
        estado_label.configure(text="Guardando...", text_color=GRIS)

        def listo(resultado):
            p["estado"] = resultado["estado"]
            p["motivo_devolucion"] = motivo if not aprobar else ""
            self._actualizar_resumen()
            self._redibujar()  # mueve la tarjeta a su lugar nuevo según el estado

        def fallo(exc):
            for b in botones:
                b.configure(state="normal")
            self._pintar_estado(estado_label, p)  # vuelve a lo último guardado, no a lo que se intentó
            self.resumen_label.configure(text=str(exc), text_color=ROJO)

        en_segundo_plano(
            self,
            lambda: api_client.revisar_planeacion(self.sesion["token"], p["id"], aprobar, motivo),
            listo,
            fallo,
        )
