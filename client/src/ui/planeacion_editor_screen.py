"""Editar una planeación ya guardada — formato Diario Pedagógico.

La usan dos caminos: el docente sobre las suyas desde "Mis planeaciones",
y el directivo sobre las de cualquiera desde "Planeaciones de un docente".
El permiso lo resuelve el backend (ver Planeaciones.js#editar_planeacion).

El curso no se edita acá: cambiarlo movería la planeación de curso, con su
asistencia y todo, que es otra operación.
"""

from __future__ import annotations

from tkinter import messagebox
from typing import Callable

import customtkinter as ctk

import api_client
from ui.lista_dinamica import ListaDinamica
from ui.tareas import en_segundo_plano
from ui.widgets import CampoConContador, MIN_PALABRAS

MINUTOS_MINIMOS = 120

MOMENTOS = [
    ("inicial", "Momento inicial", 80, 60),
    ("desarrollo", "Momento de desarrollo", 100, 40),
    ("final", "Momento final", 70, 20),
]


class PlaneacionEditorScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, planeacion: dict, on_volver: Callable[[], None]):
        super().__init__(master, label_text="Editar planeación")
        self.sesion = sesion
        self.planeacion = planeacion
        self.on_volver = on_volver
        self.momentos: dict[str, dict] = {}

        ctk.CTkButton(self, text="← Volver", width=90, command=on_volver).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(
            self, text=f"Curso: {planeacion.get('grupo') or '—'}", text_color="gray", anchor="w"
        ).pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(self, text="Fecha (AAAA-MM-DD)", anchor="w").pack(fill="x")
        self.fecha_entry = ctk.CTkEntry(self)
        self.fecha_entry.insert(0, str(planeacion["fecha"])[:10])
        self.fecha_entry.pack(fill="x", pady=(2, 8))

        self.objetivo = CampoConContador(self, "Objetivo")
        self.objetivo.set(planeacion.get("objetivo", ""))
        self.objetivo.pack(fill="x", pady=(2, 8))

        ctk.CTkLabel(self, text="Temas vistos", anchor="w").pack(fill="x", pady=(8, 0))
        self.temas_lista = ListaDinamica(self, placeholder="Tema visto")
        temas = planeacion.get("temas_vistos") or []
        if temas:
            self.temas_lista.filas[0].insert(0, temas[0])
            for tema in temas[1:]:
                self.temas_lista.agregar_fila(tema)
        self.temas_lista.pack(fill="x", pady=(2, 8))

        encabezado = ctk.CTkFrame(self, fg_color="transparent")
        encabezado.pack(fill="x", pady=(10, 4))
        ctk.CTkLabel(
            encabezado, text="Momentos de la clase y tiempos", font=ctk.CTkFont(weight="bold")
        ).pack(side="left")
        self.minutos_label = ctk.CTkLabel(encabezado, text="", font=ctk.CTkFont(size=12))
        self.minutos_label.pack(side="right")

        guardados = planeacion.get("momentos") or {}
        for clave, etiqueta, minimo, sug in MOMENTOS:
            m = guardados.get(clave) or {}
            marco = ctk.CTkFrame(self, border_width=1, corner_radius=8)
            marco.pack(fill="x", pady=6)

            fila = ctk.CTkFrame(marco, fg_color="transparent")
            fila.pack(fill="x", padx=10, pady=(8, 0))
            ctk.CTkLabel(fila, text=etiqueta, font=ctk.CTkFont(weight="bold")).pack(side="left")
            ctk.CTkLabel(fila, text="Minutos:").pack(side="left", padx=(12, 4))
            minutos_entry = ctk.CTkEntry(fila, width=60)
            minutos_entry.insert(0, str(m.get("minutos") or sug))
            minutos_entry.pack(side="left")
            minutos_entry.bind("<KeyRelease>", lambda _e: self._actualizar_minutos())

            texto = CampoConContador(marco, "Qué pasó en este momento", alto=110, minimo=minimo)
            texto.set(m.get("texto", ""))
            texto.pack(fill="x", padx=10, pady=(4, 10))

            self.momentos[clave] = {"minutos": minutos_entry, "texto": texto}

        ctk.CTkLabel(self, text="Sobre toda la clase", font=ctk.CTkFont(weight="bold")).pack(
            fill="x", pady=(16, 0)
        )
        self.observaciones = CampoConContador(
            self, "Observaciones de clase (reflexión pedagógica)", alto=100
        )
        self.observaciones.set(planeacion.get("observaciones", ""))
        self.observaciones.pack(fill="x", pady=4)
        self.avances = CampoConContador(self, "Avances o retrocesos observados", alto=100)
        self.avances.set(planeacion.get("avances", ""))
        self.avances.pack(fill="x", pady=4)

        self.error_label = ctk.CTkLabel(self, text="", text_color="#c0392b", wraplength=450, justify="left")
        self.error_label.pack(fill="x", pady=(16, 4))
        self.guardar_boton = ctk.CTkButton(self, text="Guardar cambios", command=self._guardar)
        self.guardar_boton.pack(pady=10)

        self._actualizar_minutos()

    def _minutos_de(self, clave: str) -> int:
        try:
            return int(self.momentos[clave]["minutos"].get().strip() or 0)
        except ValueError:
            return 0

    def _actualizar_minutos(self):
        total = sum(self._minutos_de(c) for c in self.momentos)
        color = "#2fa84f" if total >= MINUTOS_MINIMOS else "#c0392b"
        self.minutos_label.configure(text=f"{total} de {MINUTOS_MINIMOS} min mínimos", text_color=color)

    def _validar(self) -> str | None:
        if not self.fecha_entry.get().strip():
            return "Falta la fecha"
        if not self.objetivo.es_valido():
            return f"El objetivo necesita mínimo {MIN_PALABRAS} palabras"
        if not self.temas_lista.valores():
            return "Agregá al menos un tema visto"
        for clave, etiqueta, minimo, _sug in MOMENTOS:
            if self._minutos_de(clave) <= 0:
                return f"{etiqueta}: falta cuántos minutos duró"
            if not self.momentos[clave]["texto"].es_valido():
                return f"{etiqueta}: necesita mínimo {minimo} palabras"
        total = sum(self._minutos_de(c) for c in self.momentos)
        if total < MINUTOS_MINIMOS:
            return f"Los momentos suman {total} min y la clase necesita al menos {MINUTOS_MINIMOS}"
        if not self.observaciones.es_valido():
            return f"Las observaciones necesitan mínimo {MIN_PALABRAS} palabras"
        if not self.avances.es_valido():
            return f"Los avances necesitan mínimo {MIN_PALABRAS} palabras"
        return None

    def _guardar(self):
        error = self._validar()
        if error:
            self.error_label.configure(text=error, text_color="#c0392b")
            return

        cambios = {
            "fecha": self.fecha_entry.get().strip(),
            "objetivo": self.objetivo.get(),
            "temas_vistos": self.temas_lista.valores(),
            "momentos": {
                clave: {"texto": self.momentos[clave]["texto"].get(), "minutos": self._minutos_de(clave)}
                for clave in self.momentos
            },
            "observaciones": self.observaciones.get(),
            "avances": self.avances.get(),
        }

        self.guardar_boton.configure(state="disabled", text="Guardando...")
        self.error_label.configure(text="Guardando...", text_color="gray")

        def listo(_resultado):
            self.guardar_boton.configure(state="normal", text="Guardar cambios")
            self.error_label.configure(text="Cambios guardados ✓", text_color="#2fa84f")
            messagebox.showinfo("Listo", "Los cambios de la planeación quedaron guardados.")
            self.on_volver()

        def fallo(exc):
            self.guardar_boton.configure(state="normal", text="Guardar cambios")
            self.error_label.configure(text=str(exc), text_color="#c0392b")

        en_segundo_plano(
            self,
            lambda: api_client.editar_planeacion(self.sesion["token"], self.planeacion["id"], cambios),
            listo,
            fallo,
            bloquea_cierre=True,
        )
