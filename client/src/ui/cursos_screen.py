"""Cursos de cada docente (rol directivo). Un docente puede tener varios:
en la nómina, Wendy Valle figura con "Matemáticas niños" y "Español
adolescentes" como dos filas separadas.

El núcleo y el rango de edades viven en el curso y no en la persona,
porque cambian de un curso a otro aunque sea el mismo docente, y ambos
salen en el informe mensual —que también va por curso.
"""

from __future__ import annotations

from tkinter import messagebox
from typing import Callable

import customtkinter as ctk

import api_client
from ui.tareas import cache


class CursosScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None]):
        super().__init__(master, label_text="Cursos")
        self.sesion = sesion
        self._docentes_por_nombre: dict[str, int] = {}
        self._nombre_por_docente_id: dict[int, str] = {}

        ctk.CTkButton(self, text="← Volver", width=90, command=on_volver).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(self, text="Nuevo curso", font=ctk.CTkFont(weight="bold")).pack(anchor="w")

        ctk.CTkLabel(self, text="Docente", anchor="w").pack(fill="x", pady=(8, 0))
        self.docente_menu = ctk.CTkOptionMenu(self, values=["(cargando...)"])
        self.docente_menu.pack(fill="x", pady=(2, 0))

        self.nombre_entry = self._campo("Nombre del curso", "Ej: Matemáticas niños")
        self.nucleo_entry = self._campo("Núcleo", "Ej: Matemáticas")

        fila_edades = ctk.CTkFrame(self, fg_color="transparent")
        fila_edades.pack(fill="x", pady=(8, 0))
        ctk.CTkLabel(fila_edades, text="Edades", width=70, anchor="w").pack(side="left")
        self.edad_desde_entry = ctk.CTkEntry(fila_edades, width=60, placeholder_text="desde")
        self.edad_desde_entry.pack(side="left")
        ctk.CTkLabel(fila_edades, text="a").pack(side="left", padx=6)
        self.edad_hasta_entry = ctk.CTkEntry(fila_edades, width=60, placeholder_text="hasta")
        self.edad_hasta_entry.pack(side="left")
        ctk.CTkLabel(fila_edades, text="años  (sale en la cuenta de cobro)", text_color="gray").pack(
            side="left", padx=6
        )

        self.error_label = ctk.CTkLabel(self, text="", text_color="#c0392b", wraplength=450, justify="left")
        self.error_label.pack(fill="x", pady=(12, 4))

        self.crear_boton = ctk.CTkButton(self, text="Crear curso", command=self._crear)
        self.crear_boton.pack(pady=(0, 16))

        ctk.CTkLabel(self, text="Cursos existentes", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(8, 4))
        self.lista_contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self.lista_contenedor.pack(fill="both", expand=True)

        self._cargar_docentes()

    def _campo(self, etiqueta: str, placeholder: str = "") -> ctk.CTkEntry:
        ctk.CTkLabel(self, text=etiqueta, anchor="w").pack(fill="x", pady=(8, 0))
        entry = ctk.CTkEntry(self, placeholder_text=placeholder)
        entry.pack(fill="x", pady=(2, 0))
        return entry

    def _trabajando(self, texto: str):
        self.error_label.configure(text=texto, text_color="gray")
        self.update_idletasks()

    def _cargar_docentes(self):
        self._trabajando("Cargando...")
        try:
            usuarios = cache.usuarios(self.sesion["token"])
        except api_client.ApiError as exc:
            self.error_label.configure(text=str(exc), text_color="#c0392b")
            return

        docentes = [u for u in usuarios if u["rol"] in ("docente", "ambos")]
        self._docentes_por_nombre = {d["nombre"]: d["id"] for d in docentes}
        self._nombre_por_docente_id = {d["id"]: d["nombre"] for d in docentes}

        nombres = list(self._docentes_por_nombre) or ["(sin docentes)"]
        self.docente_menu.configure(values=nombres)
        self.docente_menu.set(nombres[0])
        self.error_label.configure(text="")
        self._cargar_lista()

    def _cargar_lista(self):
        for w in self.lista_contenedor.winfo_children():
            w.destroy()

        try:
            cursos = cache.cursos(self.sesion["token"])
        except api_client.ApiError as exc:
            self.error_label.configure(text=str(exc), text_color="#c0392b")
            return

        activos = [c for c in cursos if c.get("activo")]
        if not activos:
            ctk.CTkLabel(self.lista_contenedor, text="Todavía no hay cursos.", text_color="gray").pack(anchor="w")
            return

        for curso in activos:
            fila = ctk.CTkFrame(self.lista_contenedor, border_width=1, corner_radius=8)
            fila.pack(fill="x", pady=3)

            info = ctk.CTkFrame(fila, fg_color="transparent")
            info.pack(side="left", fill="both", expand=True, padx=10, pady=8)
            ctk.CTkLabel(info, text=curso["nombre"], font=ctk.CTkFont(weight="bold"), anchor="w").pack(fill="x")

            docente = self._nombre_por_docente_id.get(curso["docente_id"], f"id {curso['docente_id']}")
            detalle = f"{docente}  ·  núcleo: {curso.get('nucleo') or '—'}"
            if curso.get("edad_desde") or curso.get("edad_hasta"):
                detalle += f"  ·  {curso.get('edad_desde')}–{curso.get('edad_hasta')} años"
            ctk.CTkLabel(info, text=detalle, text_color="gray", anchor="w").pack(fill="x")

            ctk.CTkButton(
                fila, text="Desactivar", width=100, fg_color="#c0392b", hover_color="#922b21",
                command=lambda c=curso: self._desactivar(c),
            ).pack(side="right", padx=10)

    def _crear(self):
        docente_id = self._docentes_por_nombre.get(self.docente_menu.get())
        nombre = self.nombre_entry.get().strip()
        if docente_id is None or not nombre:
            self.error_label.configure(text="Elegí un docente y escribí el nombre del curso.", text_color="#c0392b")
            return

        datos = {
            "docente_id": docente_id,
            "nombre": nombre,
            "nucleo": self.nucleo_entry.get().strip(),
            "edad_desde": self.edad_desde_entry.get().strip(),
            "edad_hasta": self.edad_hasta_entry.get().strip(),
        }

        self.crear_boton.configure(state="disabled")
        self._trabajando("Creando...")
        try:
            api_client.crear_curso(self.sesion["token"], datos)
        except api_client.ApiError as exc:
            self.error_label.configure(text=str(exc), text_color="#c0392b")
            return
        finally:
            self.crear_boton.configure(state="normal")

        cache.invalidar("cursos")

        for entry in (self.nombre_entry, self.nucleo_entry, self.edad_desde_entry, self.edad_hasta_entry):
            entry.delete(0, "end")

        self._cargar_lista()
        self.error_label.configure(text=f"Curso «{nombre}» creado ✓", text_color="#2fa84f")

    def _desactivar(self, curso: dict):
        if not messagebox.askyesno(
            "Desactivar curso",
            f"¿Desactivar «{curso['nombre']}»?\n\n"
            "No se borra: las planeaciones e informes de meses anteriores lo siguen usando. "
            "Solo deja de aparecer para cargar clases nuevas.",
        ):
            return

        self._trabajando("Desactivando...")
        try:
            api_client.desactivar_curso(self.sesion["token"], curso["id"])
            cache.invalidar("cursos")
        except api_client.ApiError as exc:
            self.error_label.configure(text=str(exc), text_color="#c0392b")
            return

        self._cargar_lista()
        self.error_label.configure(text="Curso desactivado.", text_color="#2fa84f")
