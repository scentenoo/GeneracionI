"""Horas de gestión (planeación administrativa, rol directivo) — log de
actividades administrativas del mes. Formato mucho más libre que la
planeación docente: sin bloques, sin mínimo de palabras (spec sección 6)."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

import api_client
from services import date_utils


class HorasGestionScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None]):
        super().__init__(master, label_text="Horas de gestión")
        self.sesion = sesion

        ctk.CTkButton(self, text="← Volver", width=90, command=on_volver).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(self, text="Registrar actividad", font=ctk.CTkFont(weight="bold")).pack(anchor="w")

        ctk.CTkLabel(self, text="Fecha (AAAA-MM-DD)").pack(anchor="w", pady=(8, 0))
        self.fecha_entry = ctk.CTkEntry(self)
        self.fecha_entry.insert(0, date_utils.hoy_iso())
        self.fecha_entry.pack(fill="x", pady=(2, 0))

        ctk.CTkLabel(self, text="Actividad / tarea").pack(anchor="w", pady=(8, 0))
        self.actividad_entry = ctk.CTkEntry(self)
        self.actividad_entry.pack(fill="x", pady=(2, 0))

        ctk.CTkLabel(self, text="Horas").pack(anchor="w", pady=(8, 0))
        self.horas_entry = ctk.CTkEntry(self, width=80)
        self.horas_entry.pack(anchor="w", pady=(2, 0))

        ctk.CTkLabel(self, text="Producto / entregable (opcional)").pack(anchor="w", pady=(8, 0))
        self.entregable_entry = ctk.CTkEntry(self)
        self.entregable_entry.pack(fill="x", pady=(2, 0))

        ctk.CTkLabel(self, text="Link a soporte / carpeta (opcional)").pack(anchor="w", pady=(8, 0))
        self.link_entry = ctk.CTkEntry(self)
        self.link_entry.pack(fill="x", pady=(2, 0))

        self.error_label = ctk.CTkLabel(self, text="", text_color="#c0392b", wraplength=450, justify="left")
        self.error_label.pack(fill="x", pady=(12, 4))
        ctk.CTkButton(self, text="Guardar", command=self._guardar).pack(pady=(0, 20))

        ctk.CTkLabel(self, text="Actividades registradas", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", pady=(10, 4)
        )
        self.lista_contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self.lista_contenedor.pack(fill="both", expand=True)

        self._cargar_lista()

    def _guardar(self):
        if not self.actividad_entry.get().strip() or not self.horas_entry.get().strip():
            self.error_label.configure(text="Actividad y horas son obligatorias.")
            return

        datos = {
            "fecha": self.fecha_entry.get().strip(),
            "actividad": self.actividad_entry.get().strip(),
            "horas_sede": self.horas_entry.get().strip(),
            "entregable": self.entregable_entry.get().strip(),
            "link_soporte": self.link_entry.get().strip(),
        }

        try:
            api_client.guardar_horas_gestion(self.sesion["token"], datos)
        except api_client.ApiError as exc:
            self.error_label.configure(text=str(exc), text_color="#c0392b")
            return

        self.error_label.configure(text="Actividad guardada ✓", text_color="#2fa84f")
        self.actividad_entry.delete(0, "end")
        self.horas_entry.delete(0, "end")
        self.entregable_entry.delete(0, "end")
        self.link_entry.delete(0, "end")
        self._cargar_lista()

    def _cargar_lista(self):
        for w in self.lista_contenedor.winfo_children():
            w.destroy()

        try:
            actividades = api_client.obtener_horas_gestion(self.sesion["token"])
        except api_client.ApiError as exc:
            self.error_label.configure(text=str(exc))
            return

        if not actividades:
            ctk.CTkLabel(self.lista_contenedor, text="Todavía no hay actividades registradas.", text_color="gray").pack(
                anchor="w"
            )
            return

        actividades.sort(key=lambda a: a["fecha"], reverse=True)
        for a in actividades:
            try:
                fecha_legible = date_utils.a_fecha_corta(a["fecha"])
            except ValueError:
                fecha_legible = a["fecha"]
            fila = ctk.CTkFrame(self.lista_contenedor, border_width=1, corner_radius=8, fg_color="transparent")
            fila.pack(fill="x", pady=3)
            ctk.CTkLabel(
                fila, text=f"{fecha_legible} — {a['actividad']} ({a['horas_sede']}h)", anchor="w", justify="left",
                wraplength=420,
            ).pack(fill="x", padx=8, pady=6)
