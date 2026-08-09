"""Actividades del mes que no son clases: reuniones, claustros, informes,
atención a padres.

Son la mitad de lo que factura un docente —en el informe de julio, 8 de
16 horas— y hasta ahora no había dónde cargarlas, así que la cuenta de
cobro salía por la mitad.

Las clases no van acá: esas se cargan como planeación, que ya lleva sus
horas. El informe mensual junta las dos.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

import api_client
from services import date_utils
from ui.tareas import cache, en_segundo_plano


class ActividadesScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None]):
        super().__init__(master, label_text="Otras actividades del mes")
        self.sesion = sesion
        self._cursos_por_nombre: dict[str, dict] = {}

        ctk.CTkButton(self, text="← Volver", width=90, command=on_volver).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(
            self,
            text="Reuniones, claustros, informes: lo que se factura y no es una clase.",
            text_color="gray",
            wraplength=450,
            justify="left",
        ).pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(self, text="Va en el informe del curso", anchor="w").pack(fill="x")
        self.curso_menu = ctk.CTkOptionMenu(
            self, values=["(cargando...)"], command=lambda _v: self._cargar_lista()
        )
        self.curso_menu.pack(fill="x", pady=(2, 8))

        ctk.CTkLabel(self, text="Fecha (AAAA-MM-DD)", anchor="w").pack(fill="x")
        self.fecha_entry = ctk.CTkEntry(self)
        self.fecha_entry.insert(0, date_utils.hoy_iso())
        self.fecha_entry.pack(fill="x", pady=(2, 8))

        ctk.CTkLabel(self, text="Actividad", anchor="w").pack(fill="x")
        self.descripcion_entry = ctk.CTkEntry(self, placeholder_text="Ej: Reunión comité de padres")
        self.descripcion_entry.pack(fill="x", pady=(2, 8))

        fila_horas = ctk.CTkFrame(self, fg_color="transparent")
        fila_horas.pack(fill="x", pady=(4, 0))
        ctk.CTkLabel(fila_horas, text="Horas en sede", width=110, anchor="w").pack(side="left")
        self.horas_sede_entry = ctk.CTkEntry(fila_horas, width=60)
        self.horas_sede_entry.pack(side="left")
        ctk.CTkLabel(fila_horas, text="   externas", width=90, anchor="w").pack(side="left")
        self.horas_externas_entry = ctk.CTkEntry(fila_horas, width=60)
        self.horas_externas_entry.pack(side="left")

        self.error_label = ctk.CTkLabel(self, text="", text_color="#c0392b", wraplength=450, justify="left")
        self.error_label.pack(fill="x", pady=(12, 4))

        self.guardar_boton = ctk.CTkButton(self, text="Agregar actividad", command=self._guardar)
        self.guardar_boton.pack(pady=(0, 16))

        self.total_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(weight="bold"), anchor="w")
        self.total_label.pack(fill="x", pady=(8, 4))

        self.lista_contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self.lista_contenedor.pack(fill="both", expand=True)

        self._cargar_cursos()

    def _cargar_cursos(self):
        try:
            cursos = cache.mis_cursos(self.sesion["token"])
        except api_client.ApiError as exc:
            self.error_label.configure(text=str(exc), text_color="#c0392b")
            return

        self._cursos_por_nombre = {c["nombre"]: c for c in cursos}
        nombres = list(self._cursos_por_nombre)
        if not nombres:
            self.curso_menu.configure(values=["(no tenés cursos)"])
            self.curso_menu.set("(no tenés cursos)")
            return
        self.curso_menu.configure(values=nombres)
        self.curso_menu.set(nombres[0])
        self._cargar_lista()

    def _curso_actual(self) -> dict | None:
        return self._cursos_por_nombre.get(self.curso_menu.get())

    def _mes(self) -> str:
        return self.fecha_entry.get().strip()[:7] or date_utils.hoy_iso()[:7]

    def _cargar_lista(self):
        for w in self.lista_contenedor.winfo_children():
            w.destroy()

        curso = self._curso_actual()
        if not curso:
            return

        mes = self._mes()
        self.total_label.configure(text=f"Cargando las de {mes}...", text_color="gray")

        def listo(actividades):
            total = sum(
                (float(a.get("horas_sede") or 0) + float(a.get("horas_externas") or 0))
                for a in actividades
            )
            self.total_label.configure(
                text=f"{mes}: {len(actividades)} actividades, {total:g} horas", text_color="white"
            )

            if not actividades:
                ctk.CTkLabel(
                    self.lista_contenedor, text="Ninguna registrada este mes.", text_color="gray"
                ).pack(anchor="w")
                return

            actividades.sort(key=lambda a: str(a["fecha"]))
            for a in actividades:
                self._fila(a)

        en_segundo_plano(
            self,
            lambda: api_client.obtener_actividades(self.sesion["token"], curso["id"], mes),
            listo,
            lambda exc: self.total_label.configure(text=str(exc), text_color="#c0392b"),
        )

    def _fila(self, a: dict):
        fila = ctk.CTkFrame(self.lista_contenedor, border_width=1, corner_radius=8)
        fila.pack(fill="x", pady=3)

        info = ctk.CTkFrame(fila, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=10, pady=8)

        try:
            fecha = date_utils.a_fecha_corta(a["fecha"])
        except ValueError:
            fecha = str(a["fecha"])

        horas = []
        if float(a.get("horas_sede") or 0):
            horas.append(f"{float(a['horas_sede']):g} h en sede")
        if float(a.get("horas_externas") or 0):
            horas.append(f"{float(a['horas_externas']):g} h externas")

        ctk.CTkLabel(
            info, text=a["descripcion"], font=ctk.CTkFont(weight="bold"), anchor="w", wraplength=330,
            justify="left",
        ).pack(fill="x")
        ctk.CTkLabel(
            info, text=f"{fecha}  ·  {'  ·  '.join(horas)}", text_color="gray", anchor="w"
        ).pack(fill="x")

        ctk.CTkButton(
            fila, text="Quitar", width=80, fg_color="#c0392b", hover_color="#922b21",
            command=lambda: self._eliminar(a["id"]),
        ).pack(side="right", padx=10)

    def _guardar(self):
        curso = self._curso_actual()
        if not curso:
            self.error_label.configure(text="Elegí un curso.", text_color="#c0392b")
            return
        if not self.descripcion_entry.get().strip():
            self.error_label.configure(text="Escribí qué actividad fue.", text_color="#c0392b")
            return

        datos = {
            "curso_id": curso["id"],
            "fecha": self.fecha_entry.get().strip(),
            "descripcion": self.descripcion_entry.get().strip(),
            "horas_sede": self.horas_sede_entry.get().strip() or 0,
            "horas_externas": self.horas_externas_entry.get().strip() or 0,
        }

        self.guardar_boton.configure(state="disabled", text="Guardando...")
        self.error_label.configure(text="Guardando...", text_color="gray")

        def listo(_r):
            self.guardar_boton.configure(state="normal", text="Agregar actividad")
            for e in (self.descripcion_entry, self.horas_sede_entry, self.horas_externas_entry):
                e.delete(0, "end")
            self._cargar_lista()
            self.error_label.configure(text="Actividad agregada ✓", text_color="#2fa84f")

        def fallo(exc):
            self.guardar_boton.configure(state="normal", text="Agregar actividad")
            self.error_label.configure(text=str(exc), text_color="#c0392b")

        en_segundo_plano(
            self, lambda: api_client.guardar_actividad(self.sesion["token"], datos), listo, fallo
        )

    def _eliminar(self, actividad_id: int):
        en_segundo_plano(
            self,
            lambda: api_client.eliminar_actividad(self.sesion["token"], actividad_id),
            lambda _r: self._cargar_lista(),
            lambda exc: self.error_label.configure(text=str(exc), text_color="#c0392b"),
        )
