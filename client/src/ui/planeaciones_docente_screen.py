"""El directivo revisa y edita planeaciones de cualquier docente — nunca
las elimina (eso es solo del docente dueño, ver planeacion_list_screen.py).
Spec sección 3: "Puede editar (nunca eliminar) planeaciones de docentes,
con registro en el historial".

Acá solo vive la lista: editar abre PlaneacionEditorScreen, la misma
pantalla que usa el docente sobre las suyas.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

import api_client
from services import date_utils
from ui.cargando import Cargando
from ui.tareas import cache, en_segundo_plano


class PlaneacionesDocenteScreen(ctk.CTkScrollableFrame):
    def __init__(
        self,
        master,
        sesion: dict,
        on_volver: Callable[[], None],
        on_editar: Callable[[dict], None],
    ):
        super().__init__(master, label_text="Planeaciones de un docente")
        self.sesion = sesion
        self.on_volver = on_volver
        self.on_editar = on_editar
        self._docentes_por_nombre: dict[str, int] = {}

        ctk.CTkButton(self, text="← Volver", width=90, command=on_volver).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(self, text="Docente").pack(anchor="w")
        self.docente_menu = ctk.CTkOptionMenu(
            self, values=["(cargando...)"], command=lambda _v: self._mostrar_lista()
        )
        self.docente_menu.pack(fill="x", pady=(2, 10))

        self.error_label = ctk.CTkLabel(self, text="", text_color="#c0392b", wraplength=450, justify="left")
        self.error_label.pack(fill="x", pady=(0, 4))

        self.contenido = ctk.CTkFrame(self, fg_color="transparent")
        self.contenido.pack(fill="both", expand=True)

        self._cargar_docentes()

    def _cargar_docentes(self):
        try:
            docentes = [
                u for u in cache.usuarios(self.sesion["token"]) if u["rol"] in ("docente", "ambos")
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

    def _mostrar_lista(self):
        for w in self.contenido.winfo_children():
            w.destroy()

        docente_id = self._docente_id_actual()
        if docente_id is None:
            return

        self.error_label.configure(text="")
        Cargando(self.contenido, texto="Cargando...").pack(pady=16)

        def listo(planeaciones):
            for w in self.contenido.winfo_children():
                w.destroy()
            if not planeaciones:
                ctk.CTkLabel(
                    self.contenido, text="Este docente todavía no tiene planeaciones.", text_color="gray"
                ).pack(anchor="w", pady=10)
                return

            planeaciones.sort(key=lambda p: p["fecha"], reverse=True)
            for p in planeaciones:
                self._fila_planeacion(p)

        def fallo(exc):
            for w in self.contenido.winfo_children():
                w.destroy()
            self.error_label.configure(text=str(exc), text_color="#c0392b")

        en_segundo_plano(
            self,
            # Resumen: la lista solo muestra fecha y curso, no hace falta
            # arrastrar los bloques de cada una.
            lambda: api_client.obtener_planeaciones(self.sesion["token"], docente_id, resumen=True),
            listo,
            fallo,
        )

    def _fila_planeacion(self, p: dict):
        try:
            fecha_legible = date_utils.a_fecha_larga(p["fecha"])
        except ValueError:
            fecha_legible = p["fecha"]

        fila = ctk.CTkFrame(self.contenido, border_width=1, corner_radius=8)
        fila.pack(fill="x", pady=4)

        info = ctk.CTkFrame(fila, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=10, pady=8)
        ctk.CTkLabel(
            info, text=f"{fecha_legible} — {p['grupo']}", font=ctk.CTkFont(weight="bold"), anchor="w"
        ).pack(fill="x")
        objetivo_corto = p["objetivo"][:110] + ("..." if len(p["objetivo"]) > 110 else "")
        ctk.CTkLabel(
            info, text=objetivo_corto, text_color="gray", anchor="w", justify="left", wraplength=340
        ).pack(fill="x")

        ctk.CTkButton(fila, text="Editar", width=80, command=lambda: self.on_editar(p)).pack(
            side="right", padx=10
        )
