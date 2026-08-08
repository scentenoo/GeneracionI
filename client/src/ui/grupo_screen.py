"""Gestión de los estudiantes de un curso (rol directivo, spec sección 3:
"Crea y gestiona el grupo de estudiantes de cada docente").

Los estudiantes cuelgan del curso, así que un docente con dos cursos
tiene dos listas separadas y acá se elige de cuál."""

from __future__ import annotations

from tkinter import filedialog
from typing import Callable

import customtkinter as ctk

import api_client
from ui.tareas import cache, en_segundo_plano


class GrupoScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None]):
        super().__init__(master, label_text="Estudiantes de un curso")
        self.sesion = sesion
        self.on_volver = on_volver
        self._cursos_por_etiqueta: dict[str, dict] = {}
        self._checkboxes: dict[int, tuple[ctk.CTkCheckBox, ctk.BooleanVar]] = {}

        ctk.CTkButton(self, text="← Volver", width=90, command=on_volver).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(self, text="Curso").pack(anchor="w")
        self.curso_menu = ctk.CTkOptionMenu(self, values=["(cargando...)"], command=lambda _v: self._cargar())
        self.curso_menu.pack(fill="x", pady=(2, 10))

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
        self.agregar_boton = ctk.CTkButton(fila_agregar, text="+ Agregar", width=90, command=self._agregar_uno)
        self.agregar_boton.pack(side="left", padx=6)

        self.error_label = ctk.CTkLabel(self, text="", text_color="#c0392b", wraplength=450, justify="left")
        self.error_label.pack(fill="x", pady=(10, 4))

        ctk.CTkLabel(self, text="Estudiantes actuales", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", pady=(16, 4)
        )
        self.lista_contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self.lista_contenedor.pack(fill="both", expand=True)

        self.quitar_boton = ctk.CTkButton(
            self, text="Quitar seleccionados", fg_color="#c0392b", hover_color="#922b21",
            command=self._quitar_seleccionados,
        )
        self.quitar_boton.pack(pady=10)

        self._cargar_cursos()

    # --- feedback ---------------------------------------------------------

    def _trabajando(self, texto: str):
        """Deja claro que la llamada está en curso, en vez de dejar fijo el
        mensaje de la operación anterior."""
        self.error_label.configure(text=texto, text_color="gray")
        self.update_idletasks()

    # --- carga ------------------------------------------------------------

    def _cargar_cursos(self):
        self._trabajando("Cargando cursos...")

        def traer():
            token = self.sesion["token"]
            return cache.cursos(token), cache.nombres_de_usuarios(token)

        def listo(datos):
            cursos, usuarios = datos
            activos = [c for c in cursos if c.get("activo")]
            self._cursos_por_etiqueta = {
                f"{c['nombre']} — {usuarios.get(c['docente_id'], 'docente ' + str(c['docente_id']))}": c
                for c in activos
            }
            etiquetas = list(self._cursos_por_etiqueta) or ["(sin cursos)"]
            self.curso_menu.configure(values=etiquetas)
            self.curso_menu.set(etiquetas[0])
            self.error_label.configure(text="")
            self._cargar()

        en_segundo_plano(self, traer, listo, self._mostrar_error)

    def _mostrar_error(self, exc):
        self.error_label.configure(text=str(exc), text_color="#c0392b")

    def _curso_actual(self) -> dict | None:
        return self._cursos_por_etiqueta.get(self.curso_menu.get())

    def _cargar(self):
        for w in self.lista_contenedor.winfo_children():
            w.destroy()
        self._checkboxes.clear()

        curso = self._curso_actual()
        if not curso:
            return

        self._trabajando("Cargando estudiantes...")

        def listo(estudiantes):
            self.error_label.configure(text="")
            if not estudiantes:
                ctk.CTkLabel(
                    self.lista_contenedor, text="Todavía no hay estudiantes.", text_color="gray"
                ).pack(anchor="w")
                return
            for est in estudiantes:
                var = ctk.BooleanVar(value=False)
                cb = ctk.CTkCheckBox(self.lista_contenedor, text=est["nombre"], variable=var)
                cb.pack(anchor="w", pady=2)
                self._checkboxes[est["id"]] = (cb, var)

        en_segundo_plano(
            self,
            lambda: api_client.obtener_estudiantes(self.sesion["token"], curso["id"]),
            listo,
            self._mostrar_error,
        )

    # --- acciones ---------------------------------------------------------

    def _importar_csv(self):
        curso = self._curso_actual()
        if not curso:
            self.error_label.configure(text="Elegí un curso primero.", text_color="#c0392b")
            return

        ruta = filedialog.askopenfilename(title="Elegí el CSV de estudiantes", filetypes=[("CSV", "*.csv")])
        if not ruta:
            return

        with open(ruta, encoding="utf-8") as f:
            contenido = f.read()

        self._trabajando("Importando...")

        def listo(resultado):
            self._cargar()
            self.error_label.configure(
                text=f"Se importaron {resultado['creados']} estudiantes.", text_color="#2fa84f"
            )

        en_segundo_plano(
            self,
            lambda: api_client.importar_estudiantes(self.sesion["token"], curso["id"], contenido),
            listo,
            self._mostrar_error,
        )

    def _agregar_uno(self):
        curso = self._curso_actual()
        nombre = self.nuevo_nombre_entry.get().strip()
        if not curso or not nombre:
            self.error_label.configure(text="Elegí un curso y escribí un nombre.", text_color="#c0392b")
            return

        self.agregar_boton.configure(state="disabled")
        self._trabajando(f"Agregando a {nombre}...")

        def listo(_resultado):
            self.agregar_boton.configure(state="normal")
            self.nuevo_nombre_entry.delete(0, "end")
            self._cargar()
            self.error_label.configure(text=f"{nombre} agregado ✓", text_color="#2fa84f")

        def fallo(exc):
            self.agregar_boton.configure(state="normal")
            self._mostrar_error(exc)

        en_segundo_plano(
            self,
            lambda: api_client.modificar_grupo(
                self.sesion["token"], curso["id"], {"agregar": [{"nombre": nombre}]}
            ),
            listo,
            fallo,
        )

    def _quitar_seleccionados(self):
        curso = self._curso_actual()
        ids_a_quitar = [est_id for est_id, (_, var) in self._checkboxes.items() if var.get()]
        if not curso or not ids_a_quitar:
            self.error_label.configure(text="Marcá al menos un estudiante para quitar.", text_color="#c0392b")
            return

        self.quitar_boton.configure(state="disabled")
        self._trabajando("Quitando...")

        def listo(_resultado):
            self.quitar_boton.configure(state="normal")
            self._cargar()
            self.error_label.configure(
                text=f"Se quitaron {len(ids_a_quitar)} estudiantes.", text_color="#2fa84f"
            )

        def fallo(exc):
            self.quitar_boton.configure(state="normal")
            self._mostrar_error(exc)

        en_segundo_plano(
            self,
            lambda: api_client.modificar_grupo(self.sesion["token"], curso["id"], {"quitar": ids_a_quitar}),
            listo,
            fallo,
        )
