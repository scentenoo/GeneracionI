"""Cursos de cada docente (rol directivo). Un docente puede tener varios:
en la nómina, Wendy Valle figura con "Matemáticas niños" y "Español
adolescentes" como dos filas separadas.

El núcleo y el rango de edades viven en el curso y no en la persona,
porque cambian de un curso a otro aunque sea el mismo docente, y ambos
salen en el informe mensual —que también va por curso.

La carga de la nómina ya no crea cursos —no sabe de qué color va cada uno—
así que los cursos nuevos nacen todos desde acá. El color es obligatorio al
crear porque es lo que define quién lo revisa; el núcleo y las edades se
pueden completar después, editando. Por eso la edición no es un lujo, es
parte del alta.
"""

from __future__ import annotations

from tkinter import messagebox
from typing import Callable

import customtkinter as ctk

import api_client
from ui.cargando import Cargando
from ui.tareas import cache, en_segundo_plano

SIN_COLOR = "(sin asignar)"
AMBAR = "#8A6114"


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

        # El color va en el alta y no solo en «Editar»: un curso que nace sin
        # color no lo revisa nadie más que el administrador, y sin avisar.
        ctk.CTkLabel(self, text="Color (define quién lo revisa)", anchor="w").pack(fill="x", pady=(8, 0))
        self.color_menu = ctk.CTkOptionMenu(self, values=[SIN_COLOR, "verde", "morado"])
        self.color_menu.set(SIN_COLOR)
        self.color_menu.pack(fill="x", pady=(2, 0))

        self.error_label = ctk.CTkLabel(self, text="", text_color="#c0392b", wraplength=450, justify="left")
        self.error_label.pack(fill="x", pady=(12, 4))

        self.crear_boton = ctk.CTkButton(self, text="Crear curso", command=self._crear)
        self.crear_boton.pack(pady=(0, 16))

        ctk.CTkLabel(self, text="Cursos existentes", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(8, 4))
        self.lista_contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self.lista_contenedor.pack(fill="both", expand=True)
        self.cargando_label = ctk.CTkLabel(self.lista_contenedor, text="Cargando...", text_color="gray")
        self.cargando_label.pack(anchor="w")

        self._cargar_docentes()

    def _campo(self, etiqueta: str, placeholder: str = "") -> ctk.CTkEntry:
        ctk.CTkLabel(self, text=etiqueta, anchor="w").pack(fill="x", pady=(8, 0))
        entry = ctk.CTkEntry(self, placeholder_text=placeholder)
        entry.pack(fill="x", pady=(2, 0))
        return entry

    def _trabajando(self, texto: str):
        self.error_label.configure(text=texto, text_color="gray")

    # --- carga (en segundo plano: la lista de usuarios y cursos puede costar
    # un viaje al backend si el caché no está caliente, y hacerlo en el hilo
    # de Tk congelaba la ventana un par de segundos al abrir) ---------------

    def _cargar_docentes(self):
        def listo(usuarios):
            docentes = [u for u in usuarios if u["rol"] in ("docente", "ambos")]
            self._docentes_por_nombre = {d["nombre"]: d["id"] for d in docentes}
            self._nombre_por_docente_id = {d["id"]: d["nombre"] for d in docentes}

            nombres = list(self._docentes_por_nombre) or ["(sin docentes)"]
            self.docente_menu.configure(values=nombres)
            self.docente_menu.set(nombres[0])
            self._cargar_lista()

        en_segundo_plano(
            self,
            lambda: cache.usuarios(self.sesion["token"]),
            listo,
            lambda exc: self.error_label.configure(text=str(exc), text_color="#c0392b"),
        )

    def _cargar_lista(self):
        for w in self.lista_contenedor.winfo_children():
            w.destroy()
        Cargando(self.lista_contenedor, texto="Cargando...").pack(pady=16)

        def listo(cursos):
            for w in self.lista_contenedor.winfo_children():
                w.destroy()

            activos = [c for c in cursos if c.get("activo")]
            if not activos:
                ctk.CTkLabel(self.lista_contenedor, text="Todavía no hay cursos.", text_color="gray").pack(anchor="w")
                return

            # Los que les falta núcleo o edad van primero: son los que hay
            # que completar antes de que su cuenta de cobro salga bien.
            def incompleto(c):
                return not c.get("nucleo") or not (c.get("edad_desde") and c.get("edad_hasta"))

            # Un curso sin color tampoco está terminado —no tiene quien lo
            # revise— así que sube al mismo grupo de "hay que completar".
            def pendiente(c):
                return incompleto(c) or not str(c.get("color") or "").strip()

            for curso in sorted(activos, key=lambda c: (not pendiente(c), str(c["nombre"]).lower())):
                self._fila_curso(curso, incompleto(curso))

        def fallo(exc):
            for w in self.lista_contenedor.winfo_children():
                w.destroy()
            self.error_label.configure(text=str(exc), text_color="#c0392b")

        en_segundo_plano(
            self,
            lambda: cache.cursos(self.sesion["token"]),
            listo,
            fallo,
        )

    def _fila_curso(self, curso: dict, incompleto: bool):
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

        if incompleto:
            ctk.CTkLabel(
                info, text="Falta completar núcleo o edades", text_color=AMBAR, anchor="w",
                font=ctk.CTkFont(size=11),
            ).pack(fill="x")

        if not str(curso.get("color") or "").strip():
            ctk.CTkLabel(
                info, text="Sin color — no lo revisa nadie más que el administrador",
                text_color=AMBAR, anchor="w", font=ctk.CTkFont(size=11), wraplength=380, justify="left",
            ).pack(fill="x")

        botones = ctk.CTkFrame(fila, fg_color="transparent")
        botones.pack(side="right", padx=10)
        ctk.CTkButton(botones, text="Editar", width=80, command=lambda c=curso: self._editar(c)).pack(
            side="left", padx=(0, 6)
        )
        ctk.CTkButton(
            botones, text="Desactivar", width=100, fg_color="#c0392b", hover_color="#922b21",
            command=lambda c=curso: self._desactivar(c),
        ).pack(side="left")

    def _crear(self):
        docente_id = self._docentes_por_nombre.get(self.docente_menu.get())
        nombre = self.nombre_entry.get().strip()
        if docente_id is None or not nombre:
            self.error_label.configure(text="Elegí un docente y escribí el nombre del curso.", text_color="#c0392b")
            return
        if self.color_menu.get() == SIN_COLOR:
            self.error_label.configure(
                text="Elegí el color del curso: es lo que define quién lo revisa.", text_color="#c0392b"
            )
            return

        datos = {
            "docente_id": docente_id,
            "nombre": nombre,
            "nucleo": self.nucleo_entry.get().strip(),
            "edad_desde": self.edad_desde_entry.get().strip(),
            "edad_hasta": self.edad_hasta_entry.get().strip(),
            "color": "" if self.color_menu.get() == SIN_COLOR else self.color_menu.get(),
        }

        self.crear_boton.configure(state="disabled")
        self._trabajando("Creando...")

        def listo(_r):
            self.crear_boton.configure(state="normal")
            cache.invalidar("cursos")
            for entry in (self.nombre_entry, self.nucleo_entry, self.edad_desde_entry, self.edad_hasta_entry):
                entry.delete(0, "end")
            self.color_menu.set(SIN_COLOR)
            self._cargar_lista()
            self.error_label.configure(text=f"Curso «{nombre}» creado ✓", text_color="#2fa84f")

        def fallo(exc):
            self.crear_boton.configure(state="normal")
            self.error_label.configure(text=str(exc), text_color="#c0392b")

        en_segundo_plano(
            self,
            lambda: api_client.crear_curso(self.sesion["token"], datos),
            listo,
            fallo,
        )

    def _editar(self, curso: dict):
        DialogoEditarCurso(self, curso, self._guardar_edicion)

    def _guardar_edicion(self, curso_id: int, cambios: dict, dialogo):
        def listo(_r):
            cache.invalidar("cursos")
            dialogo.destroy()
            self._cargar_lista()
            self.error_label.configure(text="Curso actualizado ✓", text_color="#2fa84f")

        en_segundo_plano(
            self,
            lambda: api_client.editar_curso(self.sesion["token"], curso_id, cambios),
            listo,
            lambda exc: dialogo.mostrar_error(str(exc)),
        )

    def _desactivar(self, curso: dict):
        if not messagebox.askyesno(
            "Desactivar curso",
            f"¿Desactivar «{curso['nombre']}»?\n\n"
            "No se borra: las planeaciones e informes de meses anteriores lo siguen usando. "
            "Solo deja de aparecer para cargar clases nuevas.",
        ):
            return

        self._trabajando("Desactivando...")

        def listo(_r):
            cache.invalidar("cursos")
            self._cargar_lista()
            self.error_label.configure(text="Curso desactivado.", text_color="#2fa84f")

        en_segundo_plano(
            self,
            lambda: api_client.desactivar_curso(self.sesion["token"], curso["id"]),
            listo,
            lambda exc: self.error_label.configure(text=str(exc), text_color="#c0392b"),
        )


class DialogoEditarCurso(ctk.CTkToplevel):
    """Ventanita para completar/corregir un curso. El docente no se cambia
    acá: si un curso quedó con el docente equivocado, se desactiva y se
    crea de nuevo, para no mover planeaciones ya cargadas de dueño."""

    def __init__(self, master, curso: dict, on_guardar):
        super().__init__(master)
        self.curso = curso
        self.on_guardar = on_guardar

        self.title("Editar curso")
        self.geometry("380x430")
        self.transient(master.winfo_toplevel())
        # Esperar a que la ventana exista antes de robar el foco, si no
        # customtkinter tira error en algunos equipos.
        self.after(200, self.grab_set)

        ctk.CTkLabel(self, text=curso["nombre"], font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(16, 8))

        self.nombre_entry = self._campo("Nombre del curso", curso.get("nombre"))
        self.nucleo_entry = self._campo("Núcleo", curso.get("nucleo"))

        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.pack(pady=(8, 0))
        ctk.CTkLabel(fila, text="Edades", width=60, anchor="w").pack(side="left")
        self.desde_entry = ctk.CTkEntry(fila, width=60, placeholder_text="desde")
        self.desde_entry.pack(side="left")
        if curso.get("edad_desde"):
            self.desde_entry.insert(0, str(curso["edad_desde"]))
        ctk.CTkLabel(fila, text="a").pack(side="left", padx=6)
        self.hasta_entry = ctk.CTkEntry(fila, width=60, placeholder_text="hasta")
        self.hasta_entry.pack(side="left")
        if curso.get("edad_hasta"):
            self.hasta_entry.insert(0, str(curso["edad_hasta"]))

        # El color decide quién revisa el curso: verde lo revisa Mariangel,
        # morado Lorena (ver Config revisor_verde/revisor_morado).
        ctk.CTkLabel(self, text="Color (define quién lo revisa)", anchor="w").pack(
            fill="x", padx=20, pady=(10, 0)
        )
        self.color_menu = ctk.CTkOptionMenu(self, width=340, values=[SIN_COLOR, "verde", "morado"])
        self.color_menu.pack(padx=20)
        self.color_menu.set(str(curso.get("color") or SIN_COLOR))

        self.error_label = ctk.CTkLabel(self, text="", text_color="#c0392b", wraplength=340)
        self.error_label.pack(pady=(10, 0))

        botones = ctk.CTkFrame(self, fg_color="transparent")
        botones.pack(pady=16)
        ctk.CTkButton(botones, text="Cancelar", width=100, fg_color="transparent", border_width=1,
                      command=self.destroy).pack(side="left", padx=6)
        self.guardar_boton = ctk.CTkButton(botones, text="Guardar", width=100, command=self._guardar)
        self.guardar_boton.pack(side="left", padx=6)

    def _campo(self, etiqueta: str, valor) -> ctk.CTkEntry:
        ctk.CTkLabel(self, text=etiqueta, anchor="w").pack(fill="x", padx=20, pady=(8, 0))
        entry = ctk.CTkEntry(self, width=340)
        entry.pack(padx=20)
        if valor:
            entry.insert(0, str(valor))
        return entry

    def mostrar_error(self, texto: str):
        self.guardar_boton.configure(state="normal", text="Guardar")
        self.error_label.configure(text=texto)

    def _guardar(self):
        nombre = self.nombre_entry.get().strip()
        if not nombre:
            self.error_label.configure(text="El nombre no puede quedar vacío.")
            return

        color = self.color_menu.get()
        cambios = {
            "nombre": nombre,
            "nucleo": self.nucleo_entry.get().strip(),
            "edad_desde": self.desde_entry.get().strip(),
            "edad_hasta": self.hasta_entry.get().strip(),
            "color": "" if color == SIN_COLOR else color,
        }
        self.guardar_boton.configure(state="disabled", text="Guardando...")
        self.on_guardar(self.curso["id"], cambios, self)
