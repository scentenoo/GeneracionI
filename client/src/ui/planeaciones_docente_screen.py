"""El directivo revisa y edita planeaciones de cualquier docente — nunca
las elimina (eso es solo del docente dueño, ver planeacion_list_screen.py).
Spec sección 3: "Puede editar (nunca eliminar) planeaciones de docentes,
con registro en el historial"."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

import api_client
from services import date_utils
from ui.bloque_editor import BloqueEditor
from ui.lista_dinamica import ListaDinamica


class PlaneacionesDocenteScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None]):
        super().__init__(master, label_text="Planeaciones de un docente")
        self.sesion = sesion
        self.on_volver = on_volver
        self._docentes_por_nombre: dict[str, int] = {}
        self._planeacion_en_edicion: dict | None = None
        self.bloques: list[BloqueEditor] = []

        ctk.CTkButton(self, text="← Volver", width=90, command=on_volver).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(self, text="Docente").pack(anchor="w")
        self.docente_menu = ctk.CTkOptionMenu(self, values=["(cargando...)"], command=lambda _v: self._mostrar_lista())
        self.docente_menu.pack(anchor="w", pady=(2, 10))

        self.error_label = ctk.CTkLabel(self, text="", text_color="#c0392b", wraplength=450, justify="left")
        self.error_label.pack(fill="x", pady=(0, 4))

        self.contenido = ctk.CTkFrame(self, fg_color="transparent")
        self.contenido.pack(fill="both", expand=True)

        self._cargar_docentes()

    def _limpiar_contenido(self):
        for w in self.contenido.winfo_children():
            w.destroy()

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
        self._mostrar_lista()

    def _docente_id_actual(self) -> int | None:
        return self._docentes_por_nombre.get(self.docente_menu.get())

    # --- lista -----------------------------------------------------------

    def _mostrar_lista(self):
        self._planeacion_en_edicion = None
        self._limpiar_contenido()
        self.error_label.configure(text="")

        docente_id = self._docente_id_actual()
        if docente_id is None:
            return

        try:
            planeaciones = api_client.obtener_planeaciones(self.sesion["token"], docente_id)
        except api_client.ApiError as exc:
            self.error_label.configure(text=str(exc))
            return

        if not planeaciones:
            ctk.CTkLabel(self.contenido, text="Este docente todavía no tiene planeaciones.", text_color="gray").pack(
                anchor="w", pady=10
            )
            return

        planeaciones.sort(key=lambda p: p["fecha"], reverse=True)
        for p in planeaciones:
            self._fila_planeacion(p)

    def _fila_planeacion(self, p: dict):
        try:
            fecha_legible = date_utils.a_fecha_larga(p["fecha"])
        except ValueError:
            fecha_legible = p["fecha"]

        fila = ctk.CTkFrame(self.contenido, border_width=1, corner_radius=8)
        fila.pack(fill="x", pady=4)

        info = ctk.CTkFrame(fila, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=10, pady=8)
        ctk.CTkLabel(info, text=f"{fecha_legible} — {p['grupo']}", font=ctk.CTkFont(weight="bold"), anchor="w").pack(
            fill="x"
        )

        ctk.CTkButton(fila, text="Editar", width=80, command=lambda: self._mostrar_edicion(p)).pack(
            side="right", padx=10
        )

    # --- edición -----------------------------------------------------------

    def _mostrar_edicion(self, p: dict):
        self._planeacion_en_edicion = p
        self._limpiar_contenido()
        self.bloques = []

        ctk.CTkButton(self.contenido, text="← Cancelar", width=100, command=self._mostrar_lista).pack(
            anchor="w", pady=(0, 10)
        )

        ctk.CTkLabel(self.contenido, text="Fecha (AAAA-MM-DD)").pack(anchor="w")
        self.fecha_entry = ctk.CTkEntry(self.contenido)
        self.fecha_entry.insert(0, p["fecha"][:10])
        self.fecha_entry.pack(fill="x", pady=(2, 8))

        ctk.CTkLabel(self.contenido, text="Grupo").pack(anchor="w")
        self.grupo_entry = ctk.CTkEntry(self.contenido)
        self.grupo_entry.insert(0, p["grupo"])
        self.grupo_entry.pack(fill="x", pady=(2, 8))

        ctk.CTkLabel(self.contenido, text="Objetivo").pack(anchor="w")
        self.objetivo_box = ctk.CTkTextbox(self.contenido, height=70)
        self.objetivo_box.insert("1.0", p["objetivo"])
        self.objetivo_box.pack(fill="x", pady=(2, 8))

        ctk.CTkLabel(self.contenido, text="Temas vistos").pack(anchor="w", pady=(8, 0))
        self.temas_lista = ListaDinamica(self.contenido, placeholder="Tema visto")
        if p["temas_vistos"]:
            self.temas_lista.filas[0].insert(0, p["temas_vistos"][0])  # ListaDinamica ya trae una fila vacía
            for tema in p["temas_vistos"][1:]:
                self.temas_lista.agregar_fila(tema)
        self.temas_lista.pack(fill="x", pady=(2, 8))

        ctk.CTkLabel(self.contenido, text="Bloques", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(10, 4))
        self.bloques_contenedor = ctk.CTkFrame(self.contenido, fg_color="transparent")
        self.bloques_contenedor.pack(fill="x")
        for bloque_data in p["bloques"]:
            self._agregar_bloque(bloque_data)
        ctk.CTkButton(self.contenido, text="+ Agregar bloque", command=lambda: self._agregar_bloque()).pack(
            anchor="w", pady=(6, 0)
        )

        ctk.CTkButton(self.contenido, text="Guardar cambios", command=self._guardar).pack(pady=16)

    def _agregar_bloque(self, datos: dict | None = None):
        bloque = BloqueEditor(self.bloques_contenedor, len(self.bloques) + 1, self._quitar_bloque)
        if datos:
            bloque.momento_entry.insert(0, datos.get("momento", ""))
            bloque.observacion.set(datos.get("observacion", ""))
            bloque.avance.set(datos.get("avance", ""))
        bloque.pack(fill="x", pady=6)
        self.bloques.append(bloque)

    def _quitar_bloque(self, bloque: BloqueEditor):
        if len(self.bloques) <= 1:
            return
        self.bloques.remove(bloque)
        bloque.destroy()

    def _guardar(self):
        cambios = {
            "fecha": self.fecha_entry.get().strip(),
            "grupo": self.grupo_entry.get().strip(),
            "objetivo": self.objetivo_box.get("1.0", "end").strip(),
            "temas_vistos": self.temas_lista.valores(),
            "bloques": [b.a_dict() for b in self.bloques],
        }

        try:
            api_client.editar_planeacion(self.sesion["token"], self._planeacion_en_edicion["id"], cambios)
        except api_client.ApiError as exc:
            self.error_label.configure(text=str(exc), text_color="#c0392b")
            return

        self._mostrar_lista()
        self.error_label.configure(text="Cambios guardados ✓", text_color="#2fa84f")
