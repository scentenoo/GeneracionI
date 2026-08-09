"""Generar el informe mensual: junta las respuestas narrativas del mes,
le pide al backend los datos agregados (horas, asistentes, fotos) y arma
el .docx con docxtpl. Ver services/docx_generator.py."""

from __future__ import annotations

from tkinter import filedialog
from typing import Callable

import customtkinter as ctk

import api_client
from ui.tareas import cache
from services import date_utils, docx_generator, pdf_converter, vista_previa
from ui.avance_semana_editor import AvanceSemanaEditor
from ui.tareas import en_segundo_plano
from ui.widgets import MIN_PALABRAS, contar_palabras


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

        # El informe va por curso: quien tiene dos cursos entrega dos.
        ctk.CTkLabel(self, text="Curso").pack(anchor="w")
        self._cursos_por_etiqueta: dict[str, dict] = {}
        try:
            if self.es_directivo:
                cursos = cache.cursos(self.sesion["token"])
                usuarios = cache.nombres_de_usuarios(self.sesion["token"])
                self._cursos_por_etiqueta = {
                    f"{c['nombre']} — {usuarios.get(c['docente_id'], '')}": c
                    for c in cursos if c.get("activo")
                }
            else:
                self._cursos_por_etiqueta = {
                    c["nombre"]: c for c in api_client.listar_cursos(self.sesion["token"])
                }
        except api_client.ApiError:
            self._cursos_por_etiqueta = {}

        etiquetas = list(self._cursos_por_etiqueta) or ["(sin cursos)"]
        self.curso_menu = ctk.CTkOptionMenu(self, values=etiquetas)
        self.curso_menu.set(etiquetas[0])
        self.curso_menu.pack(fill="x", pady=(2, 10))

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
        ctk.CTkLabel(
            self,
            text="Las semanas y sus temas salen de tus planeaciones del mes.",
            text_color="gray",
            font=ctk.CTkFont(size=11),
        ).pack(anchor="w")

        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.pack(fill="x", pady=(4, 0))
        ctk.CTkButton(fila, text="Cargar semanas del mes", command=self._cargar_avance).pack(side="left")

        self.avances_contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self.avances_contenedor.pack(fill="x", pady=(6, 0))

    def _cargar_avance(self):
        """Trae del backend las semanas del mes con sus temas, para que el
        docente solo complete nivel y observaciones."""
        for w in self.avances_contenedor.winfo_children():
            w.destroy()
        self.avances = []

        curso = self._curso_seleccionado()
        if not curso:
            self.error_label.configure(text="Elegí un curso primero.", text_color="#c0392b")
            return

        self.error_label.configure(text="Cargando semanas...", text_color="gray")
        self.update_idletasks()
        try:
            semanas = api_client.obtener_avance_sugerido(
                self.sesion["token"], curso["id"], self.mes_entry.get().strip()
            )
        except api_client.ApiError as exc:
            self.error_label.configure(text=str(exc), text_color="#c0392b")
            return
        self.error_label.configure(text="")

        if not semanas:
            ctk.CTkLabel(
                self.avances_contenedor,
                text="No hay planeaciones de ese mes todavía.",
                text_color="gray",
            ).pack(anchor="w")
            return

        for s in semanas:
            editor = AvanceSemanaEditor(self.avances_contenedor, s["semana"], s.get("temas", []))
            editor.pack(fill="x", pady=3)
            self.avances.append(editor)

    def _construir_gestion(self):
        ctk.CTkLabel(self, text="Gestión institucional (tu parte como directivo)", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", pady=(16, 0)
        )
        # Si tenés varios cursos, las horas de gestión van en UNO solo de los
        # informes del mes; si no, se cobrarían dos veces.
        self.incluir_gestion_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            self,
            text="Incluir mis horas de gestión en este informe",
            variable=self.incluir_gestion_var,
        ).pack(anchor="w", pady=(6, 0))
        ctk.CTkLabel(
            self,
            text="Si tenés varios cursos, marcalo en uno solo del mes.",
            text_color="gray",
            font=ctk.CTkFont(size=11),
        ).pack(anchor="w")
        self.gestion_objetivos_box = self._campo("Objetivos y metas del mes")
        self.gestion_logros_box = self._campo("Principales logros, avances y entregables clave")
        self.gestion_novedades_box = self._campo("Novedades, obstáculos o riesgos identificados")
        self.gestion_estrategias_box = self._campo("Estrategias y acciones correctivas")
        self.gestion_pendientes_box = self._campo("Pendientes prioritarios para el próximo mes")

    def _construir_acciones(self):
        self.error_label = ctk.CTkLabel(self, text="", text_color="#c0392b", wraplength=450, justify="left")
        self.error_label.pack(fill="x", pady=(16, 4))

        # Igual que en la planeación: primero se revisa, después se guarda.
        self.previsualizar_boton = ctk.CTkButton(
            self, text="Ver vista previa", command=self._previsualizar
        )
        self.previsualizar_boton.pack(pady=(0, 6))

        self.guardar_boton = ctk.CTkButton(
            self, text="Guardar informe...", command=self._guardar, state="disabled"
        )
        self.guardar_boton.pack(pady=(0, 10))

        ctk.CTkLabel(
            self,
            text="Revisá la vista previa para poder guardar.",
            text_color="gray",
            font=ctk.CTkFont(size=11),
        ).pack()

    # --- armado ------------------------------------------------------------

    def _texto(self, box: ctk.CTkTextbox) -> str:
        return box.get("1.0", "end").strip()

    def _curso_seleccionado(self) -> dict | None:
        return self._cursos_por_etiqueta.get(self.curso_menu.get())

    def _validar(self) -> str | None:
        if not self._curso_seleccionado():
            return "Elegí un curso."
        if not self.mes_entry.get().strip():
            return "Falta el mes."

        campos = [
            (self.objetivo_box, "Objetivos del mes"),
            (self.logros_box, "Principales logros"),
            (self.dificultades_box, "Dificultades"),
            (self.estrategias_box, "Estrategias"),
            (self.situacion_box, "Situación positiva"),
            (self.ctei_box, "Componente CTeI"),
        ]
        if self.es_directivo:
            campos += [
                (self.gestion_objetivos_box, "Gestión: objetivos"),
                (self.gestion_logros_box, "Gestión: logros"),
                (self.gestion_novedades_box, "Gestión: novedades"),
                (self.gestion_estrategias_box, "Gestión: estrategias"),
                (self.gestion_pendientes_box, "Gestión: pendientes"),
            ]

        for box, nombre in campos:
            n = contar_palabras(self._texto(box))
            if n < MIN_PALABRAS:
                return f"«{nombre}» necesita mínimo {MIN_PALABRAS} palabras (tiene {n})."
        return None

    def _armar_contexto(self):
        """Pide al backend los datos agregados del mes ya mezclados con las
        respuestas narrativas."""
        curso = self._curso_seleccionado()
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

        return api_client.generar_informe_mensual(
            self.sesion["token"], curso["id"], self.mes_entry.get().strip(),
            narrativa, gestion_narrativa,
            incluir_gestion=bool(self.incluir_gestion_var.get()) if self.es_directivo else False,
        )

    # --- vista previa y guardado --------------------------------------------

    def _previsualizar(self):
        error = self._validar()
        if error:
            self.error_label.configure(text=error, text_color="#c0392b")
            return

        self.previsualizar_boton.configure(state="disabled", text="Generando...")
        self.error_label.configure(
            text="Armando el informe (puede tardar por las fotos)...", text_color="gray"
        )
        self.update_idletasks()

        def trabajo():
            contexto = self._armar_contexto()
            return contexto, vista_previa.previsualizar_informe(contexto)[1]

        def listo(resultado):
            contexto, es_pdf = resultado
            self._contexto_listo = contexto
            self.previsualizar_boton.configure(state="normal", text="Ver vista previa de nuevo")
            self.guardar_boton.configure(state="normal")
            formato = "PDF" if es_pdf else "documento de Word"
            self.error_label.configure(
                text=f"Abrí el {formato} para revisarlo. Si está bien, dale a guardar.",
                text_color="#2fa84f",
            )

        def fallo(exc):
            self.previsualizar_boton.configure(state="normal", text="Ver vista previa")
            self.error_label.configure(text=str(exc), text_color="#c0392b")

        en_segundo_plano(self, trabajo, listo, fallo)

    def _guardar(self):
        contexto = getattr(self, "_contexto_listo", None)
        if contexto is None:
            self.error_label.configure(text="Primero mirá la vista previa.", text_color="#c0392b")
            return

        ruta = filedialog.asksaveasfilename(
            title="Guardar informe mensual",
            defaultextension=".docx",
            filetypes=[("Word", "*.docx")],
            initialfile=f"informe_{self.mes_entry.get().strip()}.docx",
        )
        if not ruta:
            self.error_label.configure(text="No se guardó: cancelaste el diálogo.", text_color="gray")
            return

        # Reusa el contexto que ya vino del backend en la vista previa, así
        # que esto es rápido y no vuelve a pedir las fotos.
        docx_generator.generar_informe_mensual_docx(contexto, ruta)

        try:
            pdf_converter.docx_a_pdf(ruta)
            self.error_label.configure(text=f"Guardado: {ruta}  (también el PDF)", text_color="#2fa84f")
        except pdf_converter.ConversionNoDisponible:
            self.error_label.configure(
                text=f"Guardado: {ruta}  (sin PDF automático en este equipo, entregá el .docx)",
                text_color="#2fa84f",
            )
