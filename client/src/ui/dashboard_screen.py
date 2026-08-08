"""Dashboard directivo: qué docente lleva cuántas planeaciones del mes
(spec sección 3: "Ve un dashboard de estado: qué docente tiene qué
pendiente")."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

import api_client
from services import date_utils


class DashboardScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None]):
        super().__init__(master, label_text="Dashboard directivo")
        self.sesion = sesion
        self.on_volver = on_volver

        ctk.CTkButton(self, text="← Volver", width=90, command=self.on_volver).pack(anchor="w", pady=(0, 10))

        fila_mes = ctk.CTkFrame(self, fg_color="transparent")
        fila_mes.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(fila_mes, text="Mes (AAAA-MM):").pack(side="left")
        self.mes_entry = ctk.CTkEntry(fila_mes, width=100)
        self.mes_entry.insert(0, date_utils.hoy_iso()[:7])
        self.mes_entry.pack(side="left", padx=8)
        ctk.CTkButton(fila_mes, text="Actualizar", command=self._cargar).pack(side="left")

        self.tabla_contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self.tabla_contenedor.pack(fill="both", expand=True)

        self.error_label = ctk.CTkLabel(self, text="", text_color="#c0392b")
        self.error_label.pack(fill="x")

        self._cargar()

    def _cargar(self):
        for w in self.tabla_contenedor.winfo_children():
            w.destroy()
        self.error_label.configure(text="")

        self.error_label.configure(text="Cargando...", text_color="gray")
        self.update_idletasks()
        try:
            estados = api_client.obtener_dashboard_directivo(self.sesion["token"], self.mes_entry.get().strip())
        except api_client.ApiError as exc:
            self.error_label.configure(text=str(exc), text_color="#c0392b")
            return
        self.error_label.configure(text="")

        # Una fila por curso: quien tiene dos puede ir al día en uno y
        # atrasado en el otro.
        encabezado = ctk.CTkFrame(self.tabla_contenedor, fg_color="transparent")
        encabezado.pack(fill="x")
        for texto, ancho in [("Curso", 180), ("Docente", 160), ("Hechas", 70), ("Esperadas", 80), ("Faltan", 70)]:
            ctk.CTkLabel(encabezado, text=texto, width=ancho, anchor="w", font=ctk.CTkFont(weight="bold")).pack(
                side="left"
            )

        for estado in estados:
            fila = ctk.CTkFrame(self.tabla_contenedor, fg_color="transparent")
            fila.pack(fill="x", pady=2)
            color = "#2fa84f" if estado["faltantes"] == 0 else "#c0392b"
            ctk.CTkLabel(fila, text=estado.get("curso", ""), width=180, anchor="w").pack(side="left")
            ctk.CTkLabel(fila, text=estado.get("docente", ""), width=160, anchor="w").pack(side="left")
            ctk.CTkLabel(fila, text=str(estado["registradas"]), width=70, anchor="w").pack(side="left")
            ctk.CTkLabel(fila, text=str(estado["esperadas"]), width=80, anchor="w").pack(side="left")
            ctk.CTkLabel(fila, text=str(estado["faltantes"]), width=70, anchor="w", text_color=color).pack(side="left")

        if not estados:
            ctk.CTkLabel(self.tabla_contenedor, text="No hay cursos registrados todavía.", text_color="gray").pack(
                anchor="w", pady=10
            )
