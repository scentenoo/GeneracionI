"""Generar el informe mensual: junta las respuestas narrativas del mes,
le pide al backend los datos agregados (horas, asistentes, fotos) y arma
el .docx con docxtpl. Ver services/docx_generator.py."""

from __future__ import annotations

from tkinter import filedialog
from typing import Callable

import customtkinter as ctk

import api_client
from services import date_utils, docx_generator, pdf_converter
from ui.avance_semana_editor import AvanceSemanaEditor


class InformeScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None]):
        super().__init__(master, label_text="Generar informe mensual")
        self.sesion = sesion
        self.on_volver = on_volver
        self.es_directivo = sesion["rol"] in ("directivo", "ambos")
        self.avances: list[AvanceSemanaEditor] = []

        ctk.CTkButton(self, text="← Volver", width=90, command=on_volver).pack(anchor="w", pady=(0, 10))

        self._construir_encabezado()
        self._construir_narrativa()
        self._construir_avance_semanal()
        if self.es_directivo:
            self._construir_gestion()
        self._construir_acciones()

    # --- secciones -----------------------------------------------------

    def _construir_encabezado(self):
        ctk.CTkLabel(self, text="Mes a generar (AAAA-MM)").pack(anchor="w")
        self.mes_entry = ctk.CTkEntry(self, width=100)
        self.mes_entry.insert(0, date_utils.hoy_iso()[:7])
        self.mes_entry.pack(anchor="w", pady=(2, 10))

        self.docente_id = self.sesion["id"]
        if self.sesion["rol"] == "directivo":
            # un directivo puro genera el informe de otro docente, no el suyo
            ctk.CTkLabel(self, text="Docente").pack(anchor="w")
            try:
                docentes = [
                    u for u in api_client.listar_usuarios(self.sesion["token"])
                    if u["rol"] in ("docente", "ambos")
                ]
            except api_client.ApiError:
                docentes = []
            self._docentes_por_nombre = {d["nombre"]: d["id"] for d in docentes}
            self.docente_menu = ctk.CTkOptionMenu(self, values=list(self._docentes_por_nombre) or ["(sin docentes)"])
            self.docente_menu.pack(anchor="w", pady=(2, 10))

    def _campo(self, etiqueta: str) -> ctk.CTkTextbox:
        ctk.CTkLabel(self, text=etiqueta, anchor="w").pack(fill="x", pady=(10, 0))
        box = ctk.CTkTextbox(self, height=70)
        box.pack(fill="x", pady=(2, 0))
        return box

    def _construir_narrativa(self):
        ctk.CTkLabel(self, text="Desarrollo del curso en el mes", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", pady=(16, 0)
        )
        self.objetivo_box = self._campo("¿Cuáles eran los objetivos del mes y en qué medida se cumplieron?")
        self.logros_box = self._campo("Principales logros y avances de los estudiantes")
        self.dificultades_box = self._campo("Dificultades, inconvenientes o novedades")
        self.estrategias_box = self._campo("Estrategias / ajustes metodológicos implementados")
        self.situacion_box = self._campo("Situación excepcionalmente positiva del mes")
        self.ctei_box = self._campo("¿Cómo integró el componente CTeI en el mes?")

    def _construir_avance_semanal(self):
        ctk.CTkLabel(self, text="Evaluación de avance por tema", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", pady=(16, 4)
        )
        self.avances_contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self.avances_contenedor.pack(fill="x")
        ctk.CTkButton(self, text="+ Agregar semana", command=self._agregar_avance).pack(anchor="w", pady=(6, 0))
        self._agregar_avance()

    def _agregar_avance(self):
        editor = AvanceSemanaEditor(self.avances_contenedor, len(self.avances) + 1, self._quitar_avance)
        editor.pack(fill="x", pady=3)
        self.avances.append(editor)

    def _quitar_avance(self, editor: AvanceSemanaEditor):
        if len(self.avances) <= 1:
            return
        self.avances.remove(editor)
        editor.destroy()

    def _construir_gestion(self):
        ctk.CTkLabel(self, text="Gestión institucional (tu parte como directivo)", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", pady=(16, 0)
        )
        self.gestion_objetivos_box = self._campo("Objetivos y metas del mes")
        self.gestion_logros_box = self._campo("Principales logros, avances y entregables clave")
        self.gestion_novedades_box = self._campo("Novedades, obstáculos o riesgos identificados")
        self.gestion_estrategias_box = self._campo("Estrategias y acciones correctivas")
        self.gestion_pendientes_box = self._campo("Pendientes prioritarios para el próximo mes")

    def _construir_acciones(self):
        self.error_label = ctk.CTkLabel(self, text="", text_color="#c0392b", wraplength=450, justify="left")
        self.error_label.pack(fill="x", pady=(16, 4))
        ctk.CTkButton(self, text="Generar informe (.docx)", command=self._generar).pack(pady=10)

    # --- generar -----------------------------------------------------------

    def _texto(self, box: ctk.CTkTextbox) -> str:
        return box.get("1.0", "end").strip()

    def _docente_id_seleccionado(self) -> int | None:
        if self.sesion["rol"] != "directivo":
            return self.docente_id
        nombre = self.docente_menu.get()
        return self._docentes_por_nombre.get(nombre)

    def _generar(self):
        docente_id = self._docente_id_seleccionado()
        if docente_id is None:
            self.error_label.configure(text="No hay docente seleccionado.")
            return

        narrativa = {
            "objetivo_cumplimiento": self._texto(self.objetivo_box),
            "logros_avances": self._texto(self.logros_box),
            "dificultades": self._texto(self.dificultades_box),
            "estrategias": self._texto(self.estrategias_box),
            "situacion_positiva": self._texto(self.situacion_box),
            "ctei_integracion": self._texto(self.ctei_box),
            "avance_semanal": [a.a_dict() for a in self.avances],
        }
        gestion_narrativa = None
        if self.es_directivo:
            gestion_narrativa = {
                "objetivos": self._texto(self.gestion_objetivos_box),
                "logros": self._texto(self.gestion_logros_box),
                "novedades": self._texto(self.gestion_novedades_box),
                "estrategias": self._texto(self.gestion_estrategias_box),
                "pendientes": self._texto(self.gestion_pendientes_box),
            }

        self.error_label.configure(text="Generando (puede tardar un poco por las fotos)...", text_color="gray")
        self.update()

        try:
            contexto = api_client.generar_informe_mensual(
                self.sesion["token"], docente_id, self.mes_entry.get().strip(), narrativa, gestion_narrativa
            )
        except api_client.ApiError as exc:
            self.error_label.configure(text=str(exc), text_color="#c0392b")
            return

        ruta = filedialog.asksaveasfilename(
            title="Guardar informe mensual",
            defaultextension=".docx",
            filetypes=[("Word", "*.docx")],
            initialfile=f"informe_{self.mes_entry.get().strip()}.docx",
        )
        if not ruta:
            self.error_label.configure(text="Generado pero no se guardó (cancelaste el diálogo).", text_color="gray")
            return

        docx_generator.generar_informe_mensual_docx(contexto, ruta)

        try:
            pdf_path = pdf_converter.docx_a_pdf(ruta)
            self.error_label.configure(text=f"Listo: {ruta}  (también generé el PDF)", text_color="#2fa84f")
        except pdf_converter.ConversionNoDisponible:
            self.error_label.configure(
                text=f"Listo: {ruta}  (no se pudo convertir a PDF automáticamente, entregá el .docx)",
                text_color="#2fa84f",
            )
