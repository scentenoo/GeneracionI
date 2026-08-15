"""Revisar planeaciones e informes (Mariangel, Lorena, administrador).

Cada quien ve lo pendiente de los cursos de su color —Mariangel los verdes,
Lorena los morados—; el administrador ve todo. Sobre cada uno puede Abrir el
documento para leerlo, y después Aprobar o Devolver con un motivo. El motivo
le llega al docente cuando entra a la app, y queda en el historial que va al
final del documento.
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


def _url_drive(doc_id: str) -> str:
    return f"https://drive.google.com/file/d/{doc_id}/view"


class RevisarScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None]):
        super().__init__(master, label_text="Revisar")
        self.sesion = sesion

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
        cargando = Cargando(self.contenedor, texto="Cargando pendientes...")
        cargando.pack(pady=16)
        mes = self.mes_entry.get().strip()

        def listo(datos):
            for w in self.contenedor.winfo_children():
                w.destroy()
            planeaciones = datos.get("planeaciones", [])
            informes = datos.get("informes", [])
            total = len(planeaciones) + len(informes)
            self.resumen_label.configure(
                text=f"{total} pendiente(s) de revisar  ·  {mes}",
                text_color=self.color_normal if total else VERDE,
            )
            if total == 0:
                ctk.CTkLabel(
                    self.contenedor, text="No hay nada pendiente de revisar este mes.", text_color=GRIS
                ).pack(anchor="w", pady=10)
                return

            if planeaciones:
                ctk.CTkLabel(
                    self.contenedor, text="Planeaciones", font=ctk.CTkFont(weight="bold")
                ).pack(anchor="w", pady=(6, 2))
                for p in planeaciones:
                    self._fila_planeacion(p)
            if informes:
                ctk.CTkLabel(
                    self.contenedor, text="Informes del mes", font=ctk.CTkFont(weight="bold")
                ).pack(anchor="w", pady=(12, 2))
                for i in informes:
                    self._fila_informe(i)

        def fallo(exc):
            for w in self.contenedor.winfo_children():
                w.destroy()
            self.resumen_label.configure(text=str(exc), text_color=ROJO)

        en_segundo_plano(
            self,
            lambda: api_client.pendientes_de_revision(self.sesion["token"], mes),
            listo,
            fallo,
        )

    def _tarjeta(self, titulo: str, subtitulo: str):
        marco = ctk.CTkFrame(self.contenedor, corner_radius=8, border_width=1)
        marco.pack(fill="x", pady=3)
        cuerpo = ctk.CTkFrame(marco, fg_color="transparent")
        cuerpo.pack(side="left", fill="both", expand=True, padx=12, pady=8)
        ctk.CTkLabel(
            cuerpo, text=titulo, font=ctk.CTkFont(weight="bold"), anchor="w", justify="left", wraplength=380
        ).pack(fill="x")
        ctk.CTkLabel(cuerpo, text=subtitulo, text_color=GRIS, anchor="w").pack(fill="x")
        botones = ctk.CTkFrame(marco, fg_color="transparent")
        botones.pack(side="right", padx=10)
        return botones

    def _fila_planeacion(self, p: dict):
        botones = self._tarjeta(
            f"{p['curso']} — {p['fecha']}",
            f"{p['docente']}  ·  {str(p.get('objetivo', ''))[:60]}",
        )
        if p.get("doc_drive_id"):
            ctk.CTkButton(
                botones, text="Abrir", width=70, fg_color="transparent", border_width=1,
                command=lambda: webbrowser.open(_url_drive(p["doc_drive_id"])),
            ).pack(pady=2)
        ctk.CTkButton(
            botones, text="Aprobar", width=90, fg_color=VERDE, hover_color="#248a3d",
            command=lambda: self._revisar("planeacion", p, True),
        ).pack(pady=2)
        ctk.CTkButton(
            botones, text="Devolver", width=90, fg_color=AMBAR, hover_color="#6b4d10",
            command=lambda: self._revisar("planeacion", p, False),
        ).pack(pady=2)

    def _fila_informe(self, i: dict):
        botones = self._tarjeta(f"Informe — {i['curso']}", i.get("docente", ""))
        ctk.CTkButton(
            botones, text="Aprobar", width=90, fg_color=VERDE, hover_color="#248a3d",
            command=lambda: self._revisar("informe", i, True),
        ).pack(pady=2)
        ctk.CTkButton(
            botones, text="Devolver", width=90, fg_color=AMBAR, hover_color="#6b4d10",
            command=lambda: self._revisar("informe", i, False),
        ).pack(pady=2)

    def _revisar(self, tipo: str, item: dict, aprobar: bool):
        motivo = ""
        if not aprobar:
            dialogo = ctk.CTkInputDialog(
                title="Devolver",
                text="¿Por qué la devolvés? El docente va a ver este motivo:",
            )
            motivo = (dialogo.get_input() or "").strip()
            if not motivo:
                return  # sin motivo no se devuelve

        self.resumen_label.configure(text="Guardando la revisión...", text_color=GRIS)

        if tipo == "planeacion":
            trabajo = lambda: api_client.revisar_planeacion(self.sesion["token"], item["id"], aprobar, motivo)
        else:
            trabajo = lambda: api_client.revisar_informe(
                self.sesion["token"], item["curso_id"], item["mes"], aprobar, motivo
            )

        en_segundo_plano(
            self,
            trabajo,
            lambda _r: self._cargar(),
            lambda exc: self.resumen_label.configure(text=str(exc), text_color=ROJO),
        )
