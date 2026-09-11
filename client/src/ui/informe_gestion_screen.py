"""Informe mensual de un directivo sin curso (gestión pura).

Un directivo que no da clase —como Sofía, «Gestión social»— no entrega un
informe por curso: entrega uno de gestión, armado con sus horas de gestión
del mes. Esta pantalla es la que le sale a él en «Generar informe
mensual», en lugar del informe docente (ver app._mostrar_informe, que
elige según si tiene cursos).

El directivo con curso (Wendy) NO usa esta pantalla: su gestión va adjunta
al informe de uno de sus cursos, como siempre.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

import api_client
from services import date_utils, vista_previa
from ui.tareas import en_segundo_plano
from ui.widgets import MIN_PALABRAS, contar_palabras

ROJO, VERDE, GRIS = "#c0392b", "#2fa84f", "gray"


class InformeGestionScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None]):
        super().__init__(master, label_text="Generar informe de gestión")
        self.sesion = sesion

        ctk.CTkButton(self, text="← Volver", width=90, command=on_volver).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(self, text="Mes a generar (AAAA-MM)").pack(anchor="w")
        self.mes_entry = ctk.CTkEntry(self, width=100)
        self.mes_entry.insert(0, date_utils.hoy_iso()[:7])
        self.mes_entry.pack(anchor="w", pady=(2, 6))
        self.mes_entry.bind("<FocusOut>", lambda _e: self._cargar_entregado())
        self.mes_entry.bind("<Return>", lambda _e: self._cargar_entregado())

        self.entregado_label = ctk.CTkLabel(self, text="", text_color=GRIS, anchor="w")
        self.entregado_label.pack(fill="x", pady=(0, 6))

        ctk.CTkLabel(
            self,
            text="El informe se arma con las horas de gestión que cargó este mes.\n"
                 "Cárguelas en «Horas de gestión» si todavía no lo hizo.",
            text_color=GRIS, font=ctk.CTkFont(size=11), justify="left", anchor="w",
        ).pack(fill="x", pady=(0, 8))

        self.boxes: dict[str, ctk.CTkTextbox] = {}
        for clave, etiqueta in [
            ("objetivos", "Objetivos y metas del mes"),
            ("logros", "Principales logros, avances y entregables clave"),
            ("novedades", "Novedades, obstáculos o riesgos identificados"),
            ("estrategias", "Estrategias y acciones correctivas"),
            ("pendientes", "Pendientes prioritarios para el próximo mes"),
        ]:
            self.boxes[clave] = self._campo(etiqueta)

        self.error_label = ctk.CTkLabel(self, text="", text_color=ROJO, wraplength=450, justify="left")
        self.error_label.pack(fill="x", pady=(12, 4))

        self.previsualizar_boton = ctk.CTkButton(self, text="Ver vista previa", command=self._previsualizar)
        self.previsualizar_boton.pack(pady=(0, 6))
        self.guardar_boton = ctk.CTkButton(
            self, text="Entregar informe de gestión", command=self._guardar, state="disabled"
        )
        self.guardar_boton.pack(pady=(0, 10))
        ctk.CTkLabel(
            self, text="Revise la vista previa para poder entregar.",
            text_color=GRIS, font=ctk.CTkFont(size=11),
        ).pack()

        self._cargar_entregado()

    def _campo(self, etiqueta: str) -> ctk.CTkTextbox:
        ctk.CTkLabel(self, text=etiqueta, anchor="w").pack(fill="x", pady=(10, 0))
        box = ctk.CTkTextbox(self, height=70)
        box.pack(fill="x", pady=(2, 0))
        return box

    def _texto(self, box: ctk.CTkTextbox) -> str:
        return box.get("1.0", "end").strip()

    def _narrativa(self) -> dict:
        return {clave: self._texto(box) for clave, box in self.boxes.items()}

    def _validar(self) -> str | None:
        if not self.mes_entry.get().strip():
            return "Falta el mes."
        etiquetas = {
            "objetivos": "Objetivos", "logros": "Logros", "novedades": "Novedades",
            "estrategias": "Estrategias", "pendientes": "Pendientes",
        }
        for clave, box in self.boxes.items():
            n = contar_palabras(self._texto(box))
            if n < MIN_PALABRAS:
                return f"«{etiquetas[clave]}» necesita mínimo {MIN_PALABRAS} palabras (tiene {n})."
        return None

    def _previsualizar(self):
        error = self._validar()
        if error:
            self.error_label.configure(text=error, text_color=ROJO)
            return

        self.previsualizar_boton.configure(state="disabled", text="Generando...")
        self.error_label.configure(text="Armando el informe...", text_color=GRIS)
        mes = self.mes_entry.get().strip()
        narrativa = self._narrativa()

        def trabajo():
            contexto = api_client.generar_informe_gestion(self.sesion["token"], None, mes, narrativa)
            return vista_previa.previsualizar_informe_gestion(contexto)[1]

        def listo(es_pdf):
            self.previsualizar_boton.configure(state="normal", text="Ver vista previa de nuevo")
            self.guardar_boton.configure(state="normal")
            formato = "PDF" if es_pdf else "documento de Word"
            self.error_label.configure(
                text=f"Abra el {formato} para revisarlo. Si está bien, dele a entregar.", text_color=VERDE
            )

        def fallo(exc):
            self.previsualizar_boton.configure(state="normal", text="Ver vista previa")
            self.error_label.configure(text=str(exc), text_color=ROJO)

        en_segundo_plano(self, trabajo, listo, fallo)

    def _guardar(self):
        mes = self.mes_entry.get().strip()
        narrativa = self._narrativa()

        self.guardar_boton.configure(state="disabled", text="Entregando...")
        self.error_label.configure(text="Entregando...", text_color=GRIS)

        def listo(resultado):
            self.guardar_boton.configure(text="Entregar informe de gestión")
            verbo = "actualizado" if resultado.get("actualizado") else "entregado"
            self.error_label.configure(text=f"Informe de gestión {verbo} ✓", text_color=VERDE)
            self._cargar_entregado()

        def fallo(exc):
            self.guardar_boton.configure(state="normal", text="Entregar informe de gestión")
            self.error_label.configure(text=str(exc), text_color=ROJO)

        en_segundo_plano(
            self,
            lambda: api_client.guardar_informe_gestion(self.sesion["token"], mes, narrativa),
            listo,
            fallo,
            bloquea_cierre=True,
        )

    def _cargar_entregado(self):
        mes = self.mes_entry.get().strip()

        def listo(guardado):
            if not guardado:
                self.entregado_label.configure(text="Todavía no entregado este mes.", text_color=GRIS)
                return
            self.entregado_label.configure(
                text="Ya entregado — puede corregirlo y volver a entregar.", text_color=VERDE
            )
            for clave, box in self.boxes.items():
                box.delete("1.0", "end")
                box.insert("1.0", guardado.get("gestion_" + clave, "") or "")

        en_segundo_plano(
            self,
            lambda: api_client.obtener_informe_gestion(self.sesion["token"], None, mes),
            listo,
            lambda exc: self.entregado_label.configure(text=str(exc), text_color=ROJO),
        )
