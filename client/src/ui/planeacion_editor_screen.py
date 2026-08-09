"""Editar una planeación ya guardada.

La usan dos caminos: el docente sobre las suyas desde "Mis planeaciones",
y el directivo sobre las de cualquiera desde "Planeaciones de un docente".
El permiso lo resuelve el backend (ver Planeaciones.js#editar_planeacion),
así que la pantalla es la misma para los dos.

El curso no se edita acá: cambiarlo movería la planeación de curso, con su
asistencia y todo, que es otra operación.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

import api_client
from ui.bloque_editor import BloqueEditor
from ui.lista_dinamica import ListaDinamica
from ui.tareas import en_segundo_plano
from ui.widgets import MIN_PALABRAS

MINUTOS_MINIMOS = 120


class PlaneacionEditorScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, planeacion: dict, on_volver: Callable[[], None]):
        super().__init__(master, label_text="Editar planeación")
        self.sesion = sesion
        self.planeacion = planeacion
        self.on_volver = on_volver
        self.bloques: list[BloqueEditor] = []

        ctk.CTkButton(self, text="← Volver", width=90, command=on_volver).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(
            self, text=f"Curso: {planeacion.get('grupo') or '—'}", text_color="gray", anchor="w"
        ).pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(self, text="Fecha (AAAA-MM-DD)", anchor="w").pack(fill="x")
        self.fecha_entry = ctk.CTkEntry(self)
        self.fecha_entry.insert(0, str(planeacion["fecha"])[:10])
        self.fecha_entry.pack(fill="x", pady=(2, 8))

        ctk.CTkLabel(self, text="Objetivo", anchor="w").pack(fill="x")
        self.objetivo_box = ctk.CTkTextbox(self, height=80)
        self.objetivo_box.insert("1.0", planeacion["objetivo"])
        self.objetivo_box.pack(fill="x", pady=(2, 8))

        ctk.CTkLabel(self, text="Temas vistos", anchor="w").pack(fill="x", pady=(8, 0))
        self.temas_lista = ListaDinamica(self, placeholder="Tema visto")
        temas = planeacion.get("temas_vistos") or []
        if temas:
            self.temas_lista.filas[0].insert(0, temas[0])  # ListaDinamica ya trae una fila vacía
            for tema in temas[1:]:
                self.temas_lista.agregar_fila(tema)
        self.temas_lista.pack(fill="x", pady=(2, 8))

        encabezado = ctk.CTkFrame(self, fg_color="transparent")
        encabezado.pack(fill="x", pady=(10, 4))
        ctk.CTkLabel(encabezado, text="Momentos de la clase", font=ctk.CTkFont(weight="bold")).pack(side="left")
        self.minutos_label = ctk.CTkLabel(encabezado, text="", font=ctk.CTkFont(size=12))
        self.minutos_label.pack(side="right")

        self.bloques_contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self.bloques_contenedor.pack(fill="x")
        for bloque_data in planeacion.get("bloques") or []:
            self._agregar_bloque(bloque_data)
        if not self.bloques:
            self._agregar_bloque()
        ctk.CTkButton(self, text="+ Agregar bloque", command=lambda: self._agregar_bloque()).pack(
            anchor="w", pady=(6, 0)
        )

        self.error_label = ctk.CTkLabel(self, text="", text_color="#c0392b", wraplength=450, justify="left")
        self.error_label.pack(fill="x", pady=(16, 4))
        self.guardar_boton = ctk.CTkButton(self, text="Guardar cambios", command=self._guardar)
        self.guardar_boton.pack(pady=10)

        self._actualizar_minutos()

    def _agregar_bloque(self, datos: dict | None = None):
        bloque = BloqueEditor(
            self.bloques_contenedor, len(self.bloques) + 1, self._quitar_bloque, self._actualizar_minutos
        )
        if datos:
            bloque.momento_entry.insert(0, datos.get("momento", ""))
            bloque.minutos_entry.insert(0, str(datos.get("minutos", "") or ""))
            bloque.observacion.set(datos.get("observacion", ""))
            bloque.avance.set(datos.get("avance", ""))
        bloque.pack(fill="x", pady=6)
        self.bloques.append(bloque)
        self._actualizar_minutos()

    def _quitar_bloque(self, bloque: BloqueEditor):
        if len(self.bloques) <= 1:
            return
        self.bloques.remove(bloque)
        bloque.destroy()
        self._actualizar_minutos()

    def _actualizar_minutos(self):
        total = sum(b.minutos() for b in self.bloques)
        color = "#2fa84f" if total >= MINUTOS_MINIMOS else "#c0392b"
        self.minutos_label.configure(text=f"{total} de {MINUTOS_MINIMOS} min mínimos", text_color=color)

    def _validar(self) -> str | None:
        if not self.fecha_entry.get().strip():
            return "Falta la fecha"
        if not self.temas_lista.valores():
            return "Agregá al menos un tema visto"
        for i, bloque in enumerate(self.bloques, start=1):
            if not bloque.momento_entry.get().strip():
                return f"Bloque {i}: falta el momento"
            if bloque.minutos() <= 0:
                return f"Bloque {i}: falta cuántos minutos duró"
            if not bloque.observacion.es_valido() or not bloque.avance.es_valido():
                return f"Bloque {i}: la observación y los avances necesitan {MIN_PALABRAS} palabras cada uno"
        total = sum(b.minutos() for b in self.bloques)
        if total < MINUTOS_MINIMOS:
            return f"Los bloques suman {total} min y la clase necesita al menos {MINUTOS_MINIMOS}"
        return None

    def _guardar(self):
        error = self._validar()
        if error:
            self.error_label.configure(text=error, text_color="#c0392b")
            return

        cambios = {
            "fecha": self.fecha_entry.get().strip(),
            "objetivo": self.objetivo_box.get("1.0", "end").strip(),
            "temas_vistos": self.temas_lista.valores(),
            "bloques": [b.a_dict() for b in self.bloques],
        }

        self.guardar_boton.configure(state="disabled", text="Guardando...")
        self.error_label.configure(text="Guardando...", text_color="gray")

        def listo(_resultado):
            self.guardar_boton.configure(state="normal", text="Guardar cambios")
            self.error_label.configure(text="Cambios guardados ✓", text_color="#2fa84f")

        def fallo(exc):
            self.guardar_boton.configure(state="normal", text="Guardar cambios")
            self.error_label.configure(text=str(exc), text_color="#c0392b")

        en_segundo_plano(
            self,
            lambda: api_client.editar_planeacion(self.sesion["token"], self.planeacion["id"], cambios),
            listo,
            fallo,
        )
