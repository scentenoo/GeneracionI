"""Formulario de planeación de clase por bloques + checklist de asistencia
(spec sección 8). Punto de partida funcional para que Generación-I lo
termine de diseñar — hoy ya guarda de verdad contra el backend.
"""

from __future__ import annotations

from tkinter import filedialog
from typing import Callable

import customtkinter as ctk

import api_client
from services import date_utils, image_utils
from ui.bloque_editor import BloqueEditor
from ui.lista_dinamica import ListaDinamica
from ui.widgets import CampoConContador, MIN_PALABRAS, contar_palabras


class PlaneacionScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None]):
        super().__init__(master, label_text="Nueva planeación de clase")
        self.sesion = sesion
        self.on_volver = on_volver
        self.foto_path: str | None = None
        self.bloques: list[BloqueEditor] = []

        self._construir_encabezado()
        self._construir_temas_vistos()
        self._construir_bloques()
        self._construir_foto()
        self._construir_asistencia()
        self._construir_acciones()

    # --- secciones -----------------------------------------------------

    def _construir_encabezado(self):
        ctk.CTkButton(self, text="← Volver", width=90, command=self.on_volver).pack(anchor="w", pady=(0, 10))

        fila_fecha_grupo = ctk.CTkFrame(self, fg_color="transparent")
        fila_fecha_grupo.pack(fill="x", pady=4)

        ctk.CTkLabel(fila_fecha_grupo, text="Fecha (AAAA-MM-DD)").pack(anchor="w")
        self.fecha_entry = ctk.CTkEntry(fila_fecha_grupo)
        self.fecha_entry.insert(0, date_utils.hoy_iso())
        self.fecha_entry.pack(fill="x", pady=(2, 8))

        ctk.CTkLabel(fila_fecha_grupo, text="Grupo").pack(anchor="w")
        self.grupo_entry = ctk.CTkEntry(fila_fecha_grupo, placeholder_text="Ej: Desarrollo de aplicaciones")
        self.grupo_entry.pack(fill="x", pady=(2, 8))

        self.objetivo = CampoConContador(self, "Objetivo de la clase")
        self.objetivo.pack(fill="x", pady=4)

    def _construir_temas_vistos(self):
        ctk.CTkLabel(self, text="Temas vistos (uno por renglón)", anchor="w").pack(fill="x", pady=(10, 0))
        self.temas_contador = ctk.CTkLabel(self, text="", anchor="e", font=ctk.CTkFont(size=11))
        self.temas_lista = ListaDinamica(self, placeholder="Tema visto", on_change=self._actualizar_contador_temas)
        self.temas_lista.pack(fill="x", pady=(2, 0))
        self.temas_contador.pack(fill="x")
        self._actualizar_contador_temas()

    def _actualizar_contador_temas(self):
        if not hasattr(self, "temas_lista"):
            return  # se dispara una vez durante la construcción, antes de que exista el atributo
        n = contar_palabras(" ".join(self.temas_lista.valores()))
        color = "#2fa84f" if n >= MIN_PALABRAS else "#c0392b"
        self.temas_contador.configure(text=f"{n} palabras en total (mínimo {MIN_PALABRAS})", text_color=color)

    def _construir_bloques(self):
        ctk.CTkLabel(self, text="Momentos de la clase", anchor="w", font=ctk.CTkFont(weight="bold")).pack(
            fill="x", pady=(16, 4)
        )
        self.bloques_contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self.bloques_contenedor.pack(fill="x")
        ctk.CTkButton(self, text="+ Agregar bloque", command=self._agregar_bloque).pack(anchor="w", pady=(6, 0))
        self._agregar_bloque()

    def _agregar_bloque(self):
        bloque = BloqueEditor(self.bloques_contenedor, len(self.bloques) + 1, self._quitar_bloque)
        bloque.pack(fill="x", pady=6)
        self.bloques.append(bloque)

    def _quitar_bloque(self, bloque: BloqueEditor):
        if len(self.bloques) <= 1:
            return  # siempre tiene que quedar al menos un bloque
        self.bloques.remove(bloque)
        bloque.destroy()

    def _construir_foto(self):
        ctk.CTkLabel(self, text="Foto de la clase", anchor="w", font=ctk.CTkFont(weight="bold")).pack(
            fill="x", pady=(16, 4)
        )
        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.pack(fill="x")
        ctk.CTkButton(fila, text="Elegir foto...", command=self._elegir_foto).pack(side="left")
        self.foto_label = ctk.CTkLabel(fila, text="Ninguna foto seleccionada", text_color="gray")
        self.foto_label.pack(side="left", padx=10)

    def _elegir_foto(self):
        ruta = filedialog.askopenfilename(
            title="Elegí la foto de la clase",
            filetypes=[("Imágenes", "*.jpg *.jpeg *.png")],
        )
        if ruta:
            self.foto_path = ruta
            self.foto_label.configure(text=ruta.split("/")[-1].split("\\")[-1], text_color="white")

    def _construir_asistencia(self):
        ctk.CTkLabel(self, text="Asistencia", anchor="w", font=ctk.CTkFont(weight="bold")).pack(
            fill="x", pady=(16, 4)
        )
        self.asistencia_vars: dict[str, ctk.BooleanVar] = {}
        contenedor = ctk.CTkFrame(self, fg_color="transparent")
        contenedor.pack(fill="x")

        try:
            estudiantes = api_client.obtener_estudiantes(self.sesion["token"])
        except api_client.ApiError as exc:
            ctk.CTkLabel(contenedor, text=f"No se pudo cargar el grupo: {exc}", text_color="#c0392b").pack(
                anchor="w"
            )
            return

        if not estudiantes:
            ctk.CTkLabel(
                contenedor, text="Todavía no hay estudiantes en tu grupo (lo carga el directivo).", text_color="gray"
            ).pack(anchor="w")
            return

        for est in estudiantes:
            var = ctk.BooleanVar(value=True)
            ctk.CTkCheckBox(contenedor, text=est["nombre"], variable=var).pack(anchor="w", pady=2)
            self.asistencia_vars[est["nombre"]] = var

    def _construir_acciones(self):
        self.error_label = ctk.CTkLabel(self, text="", text_color="#c0392b", wraplength=400, justify="left")
        self.error_label.pack(fill="x", pady=(16, 4))
        ctk.CTkButton(self, text="Guardar planeación", command=self._guardar).pack(pady=10)

    # --- guardar ---------------------------------------------------------

    def _validar(self) -> str | None:
        if not self.fecha_entry.get().strip():
            return "Falta la fecha"
        if not self.grupo_entry.get().strip():
            return "Falta el grupo"
        if not self.objetivo.es_valido():
            return f"El objetivo necesita mínimo {MIN_PALABRAS} palabras"
        if contar_palabras(" ".join(self.temas_lista.valores())) < MIN_PALABRAS:
            return f"Los temas vistos necesitan mínimo {MIN_PALABRAS} palabras en total"
        for i, bloque in enumerate(self.bloques, start=1):
            if not bloque.es_valido():
                return f"Revisá el bloque {i}: falta el momento o no llega a {MIN_PALABRAS} palabras"
        if not self.foto_path:
            return "Falta la foto de la clase"
        return None

    def _guardar(self):
        error = self._validar()
        if error:
            self.error_label.configure(text=error)
            return

        self.error_label.configure(text="Guardando...", text_color="gray")

        datos = {
            "fecha": self.fecha_entry.get().strip(),
            "grupo": self.grupo_entry.get().strip(),
            "objetivo": self.objetivo.get(),
            "temas_vistos": self.temas_lista.valores(),
            "bloques": [b.a_dict() for b in self.bloques],
            "asistencia": [
                {"nombre": nombre, "presente": var.get()} for nombre, var in self.asistencia_vars.items()
            ],
        }
        fotos = {"foto_clase": image_utils.foto_a_payload(self.foto_path)}

        try:
            resultado = api_client.guardar_planeacion(self.sesion["token"], datos, fotos)
        except api_client.ApiError as exc:
            self.error_label.configure(text=str(exc), text_color="#c0392b")
            return

        self.error_label.configure(text=f"Planeación guardada (id {resultado['id']}) ✓", text_color="#2fa84f")
