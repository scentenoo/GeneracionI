"""Gestión del grupo de estudiantes de un docente (rol directivo, spec
sección 3: "Crea y gestiona el grupo de estudiantes de cada docente")."""

from __future__ import annotations

from tkinter import filedialog
from typing import Callable

import customtkinter as ctk

import api_client


class GrupoScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None]):
        super().__init__(master, label_text="Grupo de estudiantes")
        self.sesion = sesion
        self.on_volver = on_volver
        self._docentes_por_nombre: dict[str, int] = {}
        self._checkboxes: dict[int, tuple[ctk.CTkCheckBox, ctk.BooleanVar]] = {}

        ctk.CTkButton(self, text="← Volver", width=90, command=on_volver).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(self, text="Docente").pack(anchor="w")
        self.docente_menu = ctk.CTkOptionMenu(self, values=["(cargando...)"], command=lambda _v: self._cargar())
        self.docente_menu.pack(anchor="w", pady=(2, 10))

        fila_import = ctk.CTkFrame(self, fg_color="transparent")
        fila_import.pack(fill="x", pady=(10, 4))
        ctk.CTkButton(fila_import, text="Importar CSV...", command=self._importar_csv).pack(side="left")
        ctk.CTkLabel(
            fila_import, text="  (columna 'nombre', una fila por estudiante)", text_color="gray"
        ).pack(side="left")

        fila_agregar = ctk.CTkFrame(self, fg_color="transparent")
        fila_agregar.pack(fill="x", pady=4)
        self.nuevo_nombre_entry = ctk.CTkEntry(fila_agregar, placeholder_text="Nombre del estudiante")
        self.nuevo_nombre_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(fila_agregar, text="+ Agregar", width=90, command=self._agregar_uno).pack(side="left", padx=6)

        self.error_label = ctk.CTkLabel(self, text="", text_color="#c0392b", wraplength=450, justify="left")
        self.error_label.pack(fill="x", pady=(10, 4))

        ctk.CTkLabel(self, text="Estudiantes actuales", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", pady=(16, 4)
        )
        self.lista_contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self.lista_contenedor.pack(fill="both", expand=True)

        ctk.CTkButton(
            self, text="Quitar seleccionados", fg_color="#c0392b", hover_color="#922b21",
            command=self._quitar_seleccionados,
        ).pack(pady=10)

        self._cargar_docentes()

    def _cargar_docentes(self):
        try:
            docentes = [
                u for u in api_client.listar_usuarios(self.sesion["token"]) if u["rol"] in ("docente", "ambos")
            ]
        except api_client.ApiError as exc:
            self.error_label.configure(text=str(exc))
            return

        self._docentes_por_nombre = {d["nombre"]: d["id"] for d in docentes}
        nombres = list(self._docentes_por_nombre) or ["(sin docentes)"]
        self.docente_menu.configure(values=nombres)
        self.docente_menu.set(nombres[0])
        self._cargar()

    def _docente_id_actual(self) -> int | None:
        return self._docentes_por_nombre.get(self.docente_menu.get())

    def _cargar(self):
        for w in self.lista_contenedor.winfo_children():
            w.destroy()
        self._checkboxes.clear()

        docente_id = self._docente_id_actual()
        if docente_id is None:
            return

        try:
            estudiantes = api_client.obtener_estudiantes(self.sesion["token"], docente_id)
        except api_client.ApiError as exc:
            self.error_label.configure(text=str(exc))
            return

        if not estudiantes:
            ctk.CTkLabel(self.lista_contenedor, text="Todavía no hay estudiantes.", text_color="gray").pack(
                anchor="w"
            )
            return

        for est in estudiantes:
            var = ctk.BooleanVar(value=False)
            cb = ctk.CTkCheckBox(self.lista_contenedor, text=est["nombre"], variable=var)
            cb.pack(anchor="w", pady=2)
            self._checkboxes[est["id"]] = (cb, var)

    def _importar_csv(self):
        docente_id = self._docente_id_actual()
        if docente_id is None:
            self.error_label.configure(text="Elegí un docente primero.")
            return

        ruta = filedialog.askopenfilename(title="Elegí el CSV de estudiantes", filetypes=[("CSV", "*.csv")])
        if not ruta:
            return

        with open(ruta, encoding="utf-8") as f:
            contenido = f.read()

        try:
            resultado = api_client.importar_estudiantes(self.sesion["token"], docente_id, contenido)
        except api_client.ApiError as exc:
            self.error_label.configure(text=str(exc), text_color="#c0392b")
            return

        self.error_label.configure(text=f"Se importaron {resultado['creados']} estudiantes.", text_color="#2fa84f")
        self._cargar()

    def _agregar_uno(self):
        docente_id = self._docente_id_actual()
        nombre = self.nuevo_nombre_entry.get().strip()
        if docente_id is None or not nombre:
            self.error_label.configure(text="Elegí un docente y escribí un nombre.")
            return

        try:
            api_client.modificar_grupo(self.sesion["token"], docente_id, {"agregar": [{"nombre": nombre}]})
        except api_client.ApiError as exc:
            self.error_label.configure(text=str(exc), text_color="#c0392b")
            return

        self.nuevo_nombre_entry.delete(0, "end")
        self.error_label.configure(text="Estudiante agregado.", text_color="#2fa84f")
        self._cargar()

    def _quitar_seleccionados(self):
        docente_id = self._docente_id_actual()
        ids_a_quitar = [est_id for est_id, (_, var) in self._checkboxes.items() if var.get()]
        if docente_id is None or not ids_a_quitar:
            self.error_label.configure(text="Marcá al menos un estudiante para quitar.")
            return

        try:
            api_client.modificar_grupo(self.sesion["token"], docente_id, {"quitar": ids_a_quitar})
        except api_client.ApiError as exc:
            self.error_label.configure(text=str(exc), text_color="#c0392b")
            return

        self.error_label.configure(text=f"Se quitaron {len(ids_a_quitar)} estudiantes.", text_color="#2fa84f")
        self._cargar()
