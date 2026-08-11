"""Horas de gestión (planeación administrativa, rol directivo) — log de
actividades administrativas del mes. Formato mucho más libre que la
planeación docente: sin bloques, sin mínimo de palabras (spec sección 6).

El mismo formulario sirve para cargar una nueva y para corregir una ya
registrada: al tocar «Editar» en una fila, sus datos suben al formulario
y «Guardar» pasa a actualizar esa en vez de crear otra.
"""

from __future__ import annotations

from tkinter import messagebox
from typing import Callable

import customtkinter as ctk

import api_client
from services import date_utils
from ui.tareas import en_segundo_plano

ROJO, VERDE, GRIS = "#c0392b", "#2fa84f", "gray"


class HorasGestionScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None]):
        super().__init__(master, label_text="Horas de gestión")
        self.sesion = sesion
        self._editando: dict | None = None  # la fila que se está corrigiendo, o None

        ctk.CTkButton(self, text="← Volver", width=90, command=on_volver).pack(anchor="w", pady=(0, 10))

        self.titulo_form = ctk.CTkLabel(self, text="Registrar actividad", font=ctk.CTkFont(weight="bold"))
        self.titulo_form.pack(anchor="w")

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

        self.error_label = ctk.CTkLabel(self, text="", text_color=ROJO, wraplength=450, justify="left")
        self.error_label.pack(fill="x", pady=(12, 4))

        botones = ctk.CTkFrame(self, fg_color="transparent")
        botones.pack(pady=(0, 20))
        self.guardar_boton = ctk.CTkButton(botones, text="Guardar", command=self._guardar)
        self.guardar_boton.pack(side="left", padx=4)
        self.cancelar_boton = ctk.CTkButton(
            botones, text="Cancelar edición", fg_color="transparent", border_width=1,
            command=self._cancelar_edicion,
        )  # se muestra solo mientras se edita

        ctk.CTkLabel(self, text="Actividades registradas", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", pady=(10, 4)
        )
        self.lista_contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self.lista_contenedor.pack(fill="both", expand=True)

        self._cargar_lista()

    def _limpiar_form(self):
        self.fecha_entry.delete(0, "end")
        self.fecha_entry.insert(0, date_utils.hoy_iso())
        for e in (self.actividad_entry, self.horas_entry, self.entregable_entry, self.link_entry):
            e.delete(0, "end")

    def _cancelar_edicion(self):
        self._editando = None
        self.titulo_form.configure(text="Registrar actividad")
        self.guardar_boton.configure(text="Guardar")
        self.cancelar_boton.pack_forget()
        self._limpiar_form()
        self.error_label.configure(text="")

    def _editar(self, a: dict):
        """Sube la fila al formulario para corregirla."""
        self._editando = a
        self.titulo_form.configure(text="Editar actividad")
        self.guardar_boton.configure(text="Guardar cambios")
        self.cancelar_boton.pack(side="left", padx=4)

        self._limpiar_form()
        self.fecha_entry.delete(0, "end")
        self.fecha_entry.insert(0, str(a.get("fecha", ""))[:10])
        self.actividad_entry.insert(0, str(a.get("actividad", "")))
        self.horas_entry.insert(0, str(a.get("horas_sede", "")))
        self.entregable_entry.insert(0, str(a.get("entregable", "")))
        self.link_entry.insert(0, str(a.get("link_soporte", "")))
        self.error_label.configure(text="")

    def _guardar(self):
        if not self.actividad_entry.get().strip() or not self.horas_entry.get().strip():
            self.error_label.configure(text="Actividad y horas son obligatorias.", text_color=ROJO)
            return

        datos = {
            "fecha": self.fecha_entry.get().strip(),
            "actividad": self.actividad_entry.get().strip(),
            "horas_sede": self.horas_entry.get().strip(),
            "entregable": self.entregable_entry.get().strip(),
            "link_soporte": self.link_entry.get().strip(),
        }

        self.guardar_boton.configure(state="disabled")
        self.error_label.configure(text="Guardando...", text_color=GRIS)
        editando = self._editando

        def listo(_r):
            self.guardar_boton.configure(state="normal")
            self._cancelar_edicion()
            self.error_label.configure(
                text="Cambios guardados ✓" if editando else "Actividad guardada ✓", text_color=VERDE
            )
            self._cargar_lista()

        def fallo(exc):
            self.guardar_boton.configure(state="normal")
            self.error_label.configure(text=str(exc), text_color=ROJO)

        if editando:
            trabajo = lambda: api_client.editar_horas_gestion(self.sesion["token"], editando["id"], datos)
        else:
            trabajo = lambda: api_client.guardar_horas_gestion(self.sesion["token"], datos)
        en_segundo_plano(self, trabajo, listo, fallo)

    def _eliminar(self, a: dict):
        if not messagebox.askyesno(
            "Eliminar actividad",
            f"¿Eliminar «{a.get('actividad', '')}» ({a.get('horas_sede', '')}h)?\n\n"
            "Esto no se puede deshacer.",
            icon="warning",
            default="no",
        ):
            return

        self.error_label.configure(text="Eliminando...", text_color=GRIS)
        en_segundo_plano(
            self,
            lambda: api_client.eliminar_horas_gestion(self.sesion["token"], a["id"]),
            lambda _r: self._cargar_lista(),
            lambda exc: self.error_label.configure(text=str(exc), text_color=ROJO),
        )

    def _cargar_lista(self):
        for w in self.lista_contenedor.winfo_children():
            w.destroy()
        cargando = ctk.CTkLabel(self.lista_contenedor, text="Cargando...", text_color=GRIS)
        cargando.pack(anchor="w")

        def listo(actividades):
            for w in self.lista_contenedor.winfo_children():
                w.destroy()
            if not actividades:
                ctk.CTkLabel(
                    self.lista_contenedor, text="Todavía no hay actividades registradas.", text_color=GRIS
                ).pack(anchor="w")
                return

            actividades.sort(key=lambda a: a["fecha"], reverse=True)
            for a in actividades:
                self._fila(a)

        en_segundo_plano(
            self,
            lambda: api_client.obtener_horas_gestion(self.sesion["token"]),
            listo,
            lambda exc: self.error_label.configure(text=str(exc), text_color=ROJO),
        )

    def _fila(self, a: dict):
        try:
            fecha_legible = date_utils.a_fecha_corta(a["fecha"])
        except ValueError:
            fecha_legible = a["fecha"]

        fila = ctk.CTkFrame(self.lista_contenedor, border_width=1, corner_radius=8)
        fila.pack(fill="x", pady=3)

        info = ctk.CTkFrame(fila, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=10, pady=6)
        ctk.CTkLabel(
            info, text=f"{fecha_legible} — {a['actividad']} ({a['horas_sede']}h)",
            anchor="w", justify="left", wraplength=360,
        ).pack(fill="x")
        if a.get("entregable"):
            ctk.CTkLabel(
                info, text=f"Entregable: {a['entregable']}", text_color=GRIS,
                anchor="w", font=ctk.CTkFont(size=11),
            ).pack(fill="x")

        acciones = ctk.CTkFrame(fila, fg_color="transparent")
        acciones.pack(side="right", padx=8)
        ctk.CTkButton(acciones, text="Editar", width=70, command=lambda: self._editar(a)).pack(pady=2)
        ctk.CTkButton(
            acciones, text="Eliminar", width=70, fg_color=ROJO, hover_color="#922b21",
            command=lambda: self._eliminar(a),
        ).pack(pady=2)
