"""Generar el informe mensual: junta las respuestas narrativas del mes,
le pide al backend los datos agregados (horas, asistentes, fotos) y arma
el .docx con docxtpl. Ver services/docx_generator.py."""

from __future__ import annotations

from tkinter import messagebox
from typing import Callable

import customtkinter as ctk

import api_client
from ui.tareas import cache
from services import date_utils, vista_previa
from ui import tema
from ui.avance_semana_editor import AvanceSemanaEditor
from ui.tareas import en_segundo_plano, en_segundo_plano_con_progreso
from ui.widgets import (
    Acordeon,
    BarraDeSubida,
    CampoConInstruccion,
    MIN_PALABRAS,
    campo_label,
    contar_palabras,
)

# Las seis preguntas narrativas (2.1 a 2.6) piden más desarrollo que un
# campo de detalle común — mismo mínimo que exige el backend (Informes.js).
MIN_PALABRAS_NARRATIVA = 80
ANCHO_PANEL_DERECHO = 380

# (clave, título, instrucción)
PREGUNTAS = [
    (
        "objetivo", "2.1. ¿Cuáles eran los objetivos o metas planteadas para el mes y en qué medida se cumplieron?",
        "Texto amplio: describa con amplitud los objetivos del mes, no un texto por salir del paso.",
    ),
    (
        "logros", "2.2. Principales logros y avances observados en los estudiantes durante el mes.",
        "Háganlos a conciencia, revisando el nivel del grupo y los avances; sirve de insumo para "
        "mostrar que el programa avanza.",
    ),
    (
        "dificultades", "2.3. Dificultades, inconvenientes o novedades presentadas.",
        "En lista.",
    ),
    (
        "estrategias", "2.4. Estrategias, ajustes metodológicos implementados durante el mes.",
        "Describa con amplitud las estrategias desarrolladas en las clases; preste especial atención "
        "a si tuvo que hacer adecuaciones con estudiantes con discapacidad o trastornos del desarrollo.",
    ),
    (
        "situacion", "2.5. Describa alguna situación excepcionalmente positiva que haya notado en algún "
        "estudiante o grupo.",
        "Escriba las cosas positivas dignas de resaltar y mostrar; lo que escriba acá se publica en la "
        "bitácora al final del año.",
    ),
    (
        "ctei", "2.6. ¿Cómo integró el componente CTeI (ciencia, tecnología e innovación) en el mes?",
        "Todos los cursos deben integrar la misionalidad científica de Generación-I; describa AMPLIAMENTE "
        "cómo se desarrolló.",
    ),
]

CAMPOS_GESTION = [
    ("objetivos", "Objetivos y metas del mes"),
    ("logros", "Principales logros, avances y entregables clave"),
    ("novedades", "Novedades, obstáculos o riesgos identificados"),
    ("estrategias", "Estrategias y acciones correctivas"),
    ("pendientes", "Pendientes prioritarios para el próximo mes"),
]


class InformeScreen(ctk.CTkFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None]):
        super().__init__(master, fg_color="transparent")
        self.sesion = sesion
        self.on_volver = on_volver
        # Dos cosas distintas que antes iban juntas:
        #  - es_directivo: ocupa un cargo directivo del programa. De eso
        #    depende la sección de gestión institucional del informe.
        #  - puede_supervisar: puede ver y bajar el informe de OTROS
        #    docentes. Lo pueden el directivo y también el administrador,
        #    aunque su rol sea docente. Sin esto, Samir (docente + admin) no
        #    veía el selector de todos los cursos ni el botón de descarga.
        self.es_directivo = sesion["rol"] in ("directivo", "ambos")
        self.puede_supervisar = self.es_directivo or bool(sesion.get("es_admin"))
        self.avances: list[AvanceSemanaEditor] = []
        self._estado_mes: dict | None = None  # ver _cargar_entregado
        self._entregado = False
        self._tiene_firma: bool | None = None  # None = todavía no se sabe
        self._pregunta_boxes: dict[str, CampoConInstruccion] = {}
        self._pregunta_labels: dict[str, ctk.CTkLabel] = {}
        self._ultimos_chequeos: list[tuple[str, bool]] | None = None

        ctk.CTkButton(
            self, text="← Volver", width=90, fg_color="transparent", border_width=1,
            text_color=tema.TEXTO_OSCURO, hover_color=tema.FONDO_TARJETA, command=on_volver,
        ).pack(anchor="w", pady=(0, 12))

        cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True)

        self.columna_izquierda = ctk.CTkScrollableFrame(cuerpo, fg_color="transparent", label_text="")
        self.columna_izquierda.pack(side="left", fill="both", expand=True, padx=(0, 22))

        self.panel_derecho = ctk.CTkScrollableFrame(
            cuerpo, fg_color="transparent", label_text="", width=ANCHO_PANEL_DERECHO,
        )
        self.panel_derecho.pack(side="right", fill="y")

        self._construir_encabezado()
        self._construir_narrativa()
        self._construir_avance_semanal()
        if self.es_directivo:
            self._construir_gestion()
        self._construir_panel_derecho()

        self._cargar_firma()
        # Recién acá, con los botones ya creados, se puede saber si este
        # curso y mes están en condiciones de generar informe.
        self._cargar_entregado()

    # --- secciones -----------------------------------------------------

    def _construir_encabezado(self):
        tarjeta = ctk.CTkFrame(
            self.columna_izquierda, fg_color=tema.FONDO_TARJETA, corner_radius=16,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        tarjeta.pack(fill="x", pady=(0, 14))
        contenido = ctk.CTkFrame(tarjeta, fg_color="transparent")
        contenido.pack(fill="x", padx=26, pady=24)

        fila = ctk.CTkFrame(contenido, fg_color="transparent")
        fila.pack(fill="x")
        col_mes = ctk.CTkFrame(fila, fg_color="transparent", width=160)
        col_mes.pack(side="left", padx=(0, 18))
        col_curso = ctk.CTkFrame(fila, fg_color="transparent")
        col_curso.pack(side="left", fill="x", expand=True)

        campo_label(col_mes, "Mes a generar").pack(fill="x")
        self.mes_entry = ctk.CTkEntry(col_mes, width=140)
        self.mes_entry.insert(0, date_utils.hoy_iso()[:7])
        self.mes_entry.pack(fill="x", pady=(4, 0))
        # Cambiar el mes también cambia si el informe se puede armar, así
        # que se revisa al salir del campo y no solo al elegir curso.
        self.mes_entry.bind("<FocusOut>", lambda _e: self._cargar_entregado())
        self.mes_entry.bind("<Return>", lambda _e: self._cargar_entregado())

        # El informe va por curso: quien tiene dos cursos entrega dos.
        #
        # Acá se entrega SIEMPRE el propio, así que se muestran solo los
        # cursos propios —incluso a un directivo o al administrador—. Bajar
        # el informe de otro docente se hace desde «Informes del mes». Antes
        # esta pantalla listaba todos los cursos para quien supervisa, y eso
        # dejaba entregar (y pisar la narrativa de) el informe de otro.
        campo_label(col_curso, "Curso").pack(fill="x")
        self._cursos_por_etiqueta: dict[str, dict] = {}
        try:
            self._cursos_por_etiqueta = {
                c["nombre"]: c for c in cache.mis_cursos(self.sesion["token"])
            }
        except api_client.ApiError:
            self._cursos_por_etiqueta = {}

        etiquetas = list(self._cursos_por_etiqueta) or ["(sin cursos)"]
        # CTkOptionMenu no tiene border_width/border_color propios (a
        # diferencia de CTkEntry) — sin este marco quedaba sin ningún
        # borde, a diferencia de "Mes a generar" al lado, que sí lo tiene.
        marco_curso = ctk.CTkFrame(
            col_curso, corner_radius=10, border_width=1, border_color=tema.BORDE_TARJETA,
            fg_color=tema.FONDO_TARJETA,
        )
        marco_curso.pack(fill="x", pady=(4, 0))
        self.curso_menu = ctk.CTkOptionMenu(
            marco_curso, values=etiquetas, command=lambda _v: self._cargar_entregado(),
            fg_color=tema.FONDO_TARJETA, button_color=tema.FONDO_TARJETA,
            button_hover_color=tema.FONDO_CONTENIDO,
        )
        self.curso_menu.set(etiquetas[0])
        self.curso_menu.pack(fill="x", padx=2, pady=2)

        self.alerta_frame = ctk.CTkFrame(contenido, fg_color=tema.ROJO_CHIP_BG, corner_radius=12)
        self.alerta_label = ctk.CTkLabel(
            self.alerta_frame, text="", font=tema.fuente(12), text_color="#8E2F23",
            anchor="w", justify="left", wraplength=640,
        )
        self.alerta_label.pack(fill="x", padx=18, pady=14)
        # Se empaqueta/desempaqueta según haga falta (ver _cargar_entregado):
        # una caja vacía se vería como un espacio en blanco roto.

    def _campo(
        self, etiqueta: str, instruccion: str = "", minimo: int = MIN_PALABRAS, padre=None,
    ) -> CampoConInstruccion:
        campo = CampoConInstruccion(padre if padre is not None else self, etiqueta, instruccion, minimo=minimo)
        campo.pack(fill="x")
        return campo

    def _construir_narrativa(self):
        # Antes era un único Acordeon con las 6 preguntas apiladas adentro.
        # Como en el mockup, cada pregunta es ahora su propia tarjeta
        # numerada y colapsable: se ve de un vistazo cuáles ya tienen sus
        # palabras y cuáles faltan, sin abrir las seis a la vez.
        ctk.CTkLabel(
            self.columna_izquierda, text="2. Desarrollo del curso en el mes",
            font=tema.fuente(16, "bold"), anchor="w",
        ).pack(fill="x", pady=(8, 10))

        for indice, (clave, titulo, instruccion) in enumerate(PREGUNTAS, start=1):
            def _prefijo(padre, numero=indice):
                ctk.CTkFrame(
                    padre, width=34, height=30, corner_radius=9, fg_color=tema.FONDO_CONTENIDO,
                ).pack(side="left", padx=(16, 10), pady=10)

            def _extra(padre, clave=clave):
                etiqueta_conteo = ctk.CTkLabel(padre, text="", font=tema.fuente(12, "bold"))
                etiqueta_conteo.pack(side="right", padx=(0, 10))
                self._pregunta_labels[clave] = etiqueta_conteo

            acordeon = Acordeon(
                self.columna_izquierda, titulo, abierto=(indice == 1),
                prefijo=_prefijo, encabezado_extra=_extra, wraplength_titulo=600,
            )
            acordeon.pack(fill="x", pady=5)
            # El "34x30" del mockup es una insignia numerada — como los
            # campos de acá no son un for genérico (cada pregunta es un
            # método propio con su instrucción), el número se pinta encima
            # del cuadrito con .place() en vez de armar un prefijo genérico.
            insignia = acordeon.encabezado.winfo_children()[0]
            ctk.CTkLabel(
                insignia, text=str(indice), text_color=tema.VERDE_OSCURO, font=tema.fuente(12, "bold"),
            ).place(relx=0.5, rely=0.5, anchor="center")

            campo = CampoConInstruccion(acordeon.contenido, "", instruccion, alto=130, minimo=0)
            campo.pack(fill="x")
            campo.textbox.bind("<KeyRelease>", lambda _e, c=clave: self._actualizar_pregunta(c), add="+")
            self._pregunta_boxes[clave] = campo
            self._actualizar_pregunta(clave)

    def _actualizar_pregunta(self, clave: str):
        n = contar_palabras(self._pregunta_boxes[clave].get())
        ok = n >= MIN_PALABRAS_NARRATIVA
        etiqueta = self._pregunta_labels.get(clave)
        if etiqueta is not None:
            etiqueta.configure(
                text=f"{n} palabras" if ok else f"{n} de {MIN_PALABRAS_NARRATIVA} palabras",
                text_color=tema.VERDE_CHIP_TEXTO if ok else tema.ROJO,
            )
        self._actualizar_estado()

    def _construir_avance_semanal(self):
        tarjeta = ctk.CTkFrame(
            self.columna_izquierda, fg_color=tema.FONDO_TARJETA, corner_radius=16,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        tarjeta.pack(fill="x", pady=(10, 0))
        contenido = ctk.CTkFrame(tarjeta, fg_color="transparent")
        contenido.pack(fill="x", padx=26, pady=22)

        encabezado = ctk.CTkFrame(contenido, fg_color="transparent")
        encabezado.pack(fill="x")
        textos = ctk.CTkFrame(encabezado, fg_color="transparent")
        textos.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            textos, text="Evaluación de avance por tema", font=tema.fuente(16, "bold"), anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            textos, text="Las semanas y sus temas salen de sus planeaciones del mes.",
            font=tema.fuente(12), text_color=tema.TEXTO_MUTED, anchor="w",
        ).pack(fill="x", pady=(2, 0))
        ctk.CTkButton(
            encabezado, text="Cargar semanas del mes", fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER,
            command=self._cargar_avance,
        ).pack(side="right")

        self.avances_contenedor = ctk.CTkFrame(contenido, fg_color="transparent")
        self.avances_contenedor.pack(fill="x", pady=(16, 0))

    def _cargar_avance(self):
        """Trae del backend las semanas del mes con sus temas, para que el
        docente solo complete nivel y observaciones."""
        for w in self.avances_contenedor.winfo_children():
            w.destroy()
        self.avances = []

        curso = self._curso_seleccionado()
        if not curso:
            self.error_label.configure(text="Elija un curso primero.", text_color=tema.ROJO)
            return

        self.error_label.configure(text="Cargando semanas...", text_color=tema.TEXTO_MUTED)
        self.update_idletasks()
        try:
            semanas = api_client.obtener_avance_sugerido(
                self.sesion["token"], curso["id"], self.mes_entry.get().strip()
            )
        except api_client.ApiError as exc:
            self.error_label.configure(text=str(exc), text_color=tema.ROJO)
            return
        self.error_label.configure(text="")

        if not semanas:
            ctk.CTkLabel(
                self.avances_contenedor,
                text="No hay planeaciones de ese mes todavía.",
                text_color=tema.TEXTO_MUTED,
            ).pack(anchor="w")
            self._actualizar_estado()
            return

        for s in semanas:
            editor = AvanceSemanaEditor(
                self.avances_contenedor, s["semana"], s.get("temas", []), s.get("fecha", ""),
                on_cambiar=self._actualizar_estado,
            )
            editor.pack(fill="x", pady=4)
            self.avances.append(editor)
        self._actualizar_estado()

    def _construir_gestion(self):
        self.gestion_acordeon = Acordeon(
            self.columna_izquierda, "Gestión institucional", abierto=False,
            encabezado_extra=self._badge_gestion,
        )
        self.gestion_acordeon.pack(fill="x", pady=(10, 0))
        contenedor = self.gestion_acordeon.contenido

        ctk.CTkLabel(
            contenedor, text="(su parte como directivo) — si tiene varios cursos, márquelo en uno solo del mes.",
            font=tema.fuente(11), text_color=tema.TEXTO_MUTED, anchor="w", wraplength=560, justify="left",
        ).pack(fill="x", pady=(0, 12))

        # Si tenés varios cursos, las horas de gestión van en UNO solo de los
        # informes del mes; si no, se cobrarían dos veces.
        self.incluir_gestion_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            contenedor,
            text="Incluir mis horas de gestión en este informe",
            variable=self.incluir_gestion_var,
            command=self._actualizar_estado,
        ).pack(anchor="w", pady=(0, 16))

        grilla = ctk.CTkFrame(contenedor, fg_color="transparent")
        grilla.pack(fill="x")
        grilla.grid_columnconfigure((0, 1), weight=1, uniform="gestion")
        self._gestion_boxes: dict[str, CampoConInstruccion] = {}
        for i, (clave, etiqueta) in enumerate(CAMPOS_GESTION):
            celda = ctk.CTkFrame(grilla, fg_color="transparent")
            celda.grid(row=i // 2, column=i % 2, sticky="ew", padx=(0, 12 if i % 2 == 0 else 0), pady=(0, 14))
            campo = CampoConInstruccion(celda, "", minimo=MIN_PALABRAS)
            # Sin etiqueta propia de CampoConInstruccion: la mayúscula chica
            # del mockup (campo_label) es más angosta que el label normal.
            campo_label(celda, etiqueta).pack(fill="x")
            campo.pack(fill="x")
            campo.textbox.bind("<KeyRelease>", lambda _e: self._actualizar_estado(), add="+")
            self._gestion_boxes[clave] = campo

    def _badge_gestion(self, fila: ctk.CTkFrame):
        ctk.CTkLabel(
            fila, text=f"  {len(CAMPOS_GESTION)} campos  ", font=tema.fuente(12, "bold"),
            text_color=tema.TEXTO_MUTED, fg_color=tema.FONDO_CONTENIDO, corner_radius=999,
        ).pack(side="right", padx=(0, 8))

    # ------------------------------------------------------------------
    # Panel derecho: estado del informe
    # ------------------------------------------------------------------

    def _construir_panel_derecho(self):
        tarjeta = ctk.CTkFrame(
            self.panel_derecho, fg_color=tema.FONDO_TARJETA, corner_radius=16,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        tarjeta.pack(fill="both", expand=True)
        self._panel = ctk.CTkFrame(tarjeta, fg_color="transparent")
        self._panel.pack(fill="both", expand=True, padx=22, pady=22)

        ctk.CTkLabel(
            self._panel, text="Estado del informe", font=tema.fuente(15, "bold"), anchor="w",
        ).pack(fill="x")
        self.estado_pildora = ctk.CTkLabel(
            self._panel, text="Todavía no entregado", font=tema.fuente(12, "bold"),
            text_color=tema.TEXTO_MUTED, fg_color=tema.FONDO_CONTENIDO, corner_radius=999,
        )
        self.estado_pildora.pack(anchor="w", pady=(10, 0))

        # tema.BORDE_TARJETA y no tema.DIVISOR (#EDEFED): ese gris es tan
        # claro que se pierde contra el blanco de la tarjeta — ver la misma
        # nota en planeacion_screen.py (_separador).
        ctk.CTkFrame(self._panel, fg_color=tema.BORDE_TARJETA, height=1).pack(fill="x", pady=18)
        campo_label(self._panel, "Avance").pack(fill="x", pady=(0, 10))
        self._chequeos_contenedor = ctk.CTkFrame(self._panel, fg_color="transparent")
        self._chequeos_contenedor.pack(fill="x")

        self.segmentos_fila = ctk.CTkFrame(self._panel, fg_color="transparent")
        self.segmentos_fila.pack(fill="x", pady=(16, 0))
        self.porcentaje_label = ctk.CTkLabel(
            self._panel, text="", font=tema.fuente(11), text_color=tema.TEXTO_MUTED, anchor="w",
        )
        self.porcentaje_label.pack(fill="x", pady=(6, 0))

        self.error_label = ctk.CTkLabel(
            self._panel, text="", text_color=tema.ROJO, wraplength=ANCHO_PANEL_DERECHO - 32, justify="left",
        )
        self.error_label.pack(fill="x", pady=(14, 0))

        # Igual que en la planeación: primero se revisa, después se guarda.
        self.previsualizar_boton = ctk.CTkButton(
            self._panel, text="Ver vista previa", fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER,
            command=self._previsualizar,
        )
        self.previsualizar_boton.pack(fill="x", pady=(14, 6))
        self.guardar_boton = ctk.CTkButton(
            self._panel, text="Entregar informe del mes", state="disabled", command=self._guardar,
        )
        self.guardar_boton.pack(fill="x")
        ctk.CTkLabel(
            self._panel, text="Revise la vista previa para poder entregar.",
            text_color=tema.TEXTO_MUTED, font=tema.fuente(11), anchor="w",
        ).pack(fill="x", pady=(6, 0))

        self.barra_subida = BarraDeSubida(self._panel)
        self.barra_subida.pack(fill="x", pady=(4, 0))

        self.cierre_label = ctk.CTkLabel(
            self._panel, text="", font=tema.fuente(11), text_color=tema.AMBAR, fg_color=tema.AMBAR_CHIP_BG,
            corner_radius=9, anchor="w", justify="left", wraplength=ANCHO_PANEL_DERECHO - 56,
        )

        # Descargar el informe de OTROS docentes ya no vive acá: se mudó a
        # «Informes del mes», en Dirección, que además baja todos en un ZIP.
        # Esta pantalla vuelve a ser solo para armar y entregar el propio.
        if self.puede_supervisar:
            ctk.CTkLabel(
                self._panel,
                text="Para bajar informes ya entregados (los suyos o los de otros), "
                     "use «Informes del mes».",
                text_color=tema.TEXTO_MUTED, font=tema.fuente(11), justify="left", anchor="w",
                wraplength=ANCHO_PANEL_DERECHO - 32,
            ).pack(fill="x", pady=(14, 0))

        self._actualizar_estado()

    # --- estado / checklist -------------------------------------------------

    def _cargar_firma(self):
        def listo(usuarios):
            yo = next((u for u in usuarios if u["id"] == self.sesion["id"]), None)
            self._tiene_firma = bool(yo and yo.get("firma_drive_id"))
            self._actualizar_estado()

        en_segundo_plano(
            self,
            lambda: cache.usuarios(self.sesion["token"]),
            listo,
            lambda _exc: None,
            mostrar_overlay=False,
        )

    def _chequeos(self) -> list[tuple[str, bool]]:
        chequeos = []
        if self._estado_mes:
            registradas = self._estado_mes.get("registradas", 0)
            esperadas = self._estado_mes.get("esperadas", 0)
            chequeos.append((f"Planeaciones del mes: {registradas} de {esperadas}", registradas >= esperadas))

        faltan_narrativa = sum(
            1 for clave, _t, _i in PREGUNTAS
            if contar_palabras(self._pregunta_boxes[clave].get()) < MIN_PALABRAS_NARRATIVA
        )
        chequeos.append((
            "Las 6 respuestas completas" if faltan_narrativa == 0
            else f"{faltan_narrativa} respuesta(s) sin las {MIN_PALABRAS_NARRATIVA} palabras",
            faltan_narrativa == 0,
        ))

        if self.avances:
            faltan_avance = sum(1 for a in self.avances if not a.a_dict()["observaciones"])
            chequeos.append((
                "Evaluación de avance completa" if faltan_avance == 0
                else f"{faltan_avance} semana(s) sin observaciones",
                faltan_avance == 0,
            ))

        if self.es_directivo and self.incluir_gestion_var.get():
            faltan_gestion = sum(
                1 for box in self._gestion_boxes.values() if contar_palabras(box.get()) < MIN_PALABRAS
            )
            chequeos.append((
                "Gestión institucional completa" if faltan_gestion == 0
                else f"Gestión: {faltan_gestion} campo(s) sin completar",
                faltan_gestion == 0,
            ))

        if self._tiene_firma is not None:
            chequeos.append(("Firma cargada" if self._tiene_firma else "Todavía no tiene firma cargada", self._tiene_firma))

        return chequeos

    def _actualizar_estado(self):
        if not hasattr(self, "_chequeos_contenedor"):
            return  # todavía construyendo la pantalla

        self.estado_pildora.configure(
            text="Ya entregado" if self._entregado else "Todavía no entregado",
            text_color=tema.VERDE_CHIP_TEXTO if self._entregado else tema.TEXTO_MUTED,
            fg_color=tema.VERDE_CHIP_BG if self._entregado else tema.FONDO_CONTENIDO,
        )

        chequeos = self._chequeos()
        # Se llama en cada tecla de las seis preguntas, de gestión y de los
        # avances semanales — pero el conteo de palabras (y por lo tanto el
        # texto de cada chequeo) solo cambia al cruzar un espacio, no letra
        # por letra. Reconstruir igual todo el panel de abajo en cada tecla
        # se sentía como que "algo fallaba": destruía y volvía a armar cada
        # tarjetita y cada segmento aunque no hubiera nada distinto que
        # mostrar. Sin cambios reales en el checklist, no se toca nada de
        # esto (la píldora de arriba sí se actualiza siempre, por las dudas
        # que cambie sin que cambien los chequeos).
        if chequeos == self._ultimos_chequeos:
            return
        self._ultimos_chequeos = chequeos

        for w in self._chequeos_contenedor.winfo_children():
            w.destroy()
        for texto, ok in chequeos:
            fila = ctk.CTkFrame(self._chequeos_contenedor, fg_color="transparent")
            fila.pack(fill="x", pady=3)
            texto_color = tema.VERDE_CHIP_TEXTO if ok else tema.ROJO
            fondo_color = tema.VERDE_CHIP_BG if ok else tema.ROJO_CHIP_BG
            insignia = ctk.CTkFrame(fila, width=18, height=18, corner_radius=9, fg_color=fondo_color)
            insignia.pack(side="left", padx=(0, 11))
            insignia.pack_propagate(False)
            ctk.CTkLabel(
                insignia, text="✓" if ok else "!", text_color=texto_color, font=tema.fuente(11, "bold"),
            ).place(relx=0.5, rely=0.5, anchor="center")
            ctk.CTkLabel(
                fila, text=texto, font=tema.fuente(13), text_color=texto_color if not ok else tema.TEXTO_OSCURO,
                anchor="w", justify="left", wraplength=ANCHO_PANEL_DERECHO - 80,
            ).pack(side="left", fill="x", expand=True)

        for w in self.segmentos_fila.winfo_children():
            w.destroy()
        total = max(len(chequeos), 1)
        listos = sum(1 for _t, ok in chequeos if ok)
        for i in range(total):
            color = tema.VERDE if i < listos else tema.BORDE_TARJETA
            # width=1 a propósito: ver la nota en planeacion_screen.py
            # (_dibujar_segmentos_mes) — sin ancho explícito, CTkFrame pide
            # 200px por defecto y con 3+ hermanos a expand=True customtkinter
            # deja al tercero en adelante pegados en 1x1 en vez de repartir
            # el espacio.
            ctk.CTkFrame(self.segmentos_fila, width=1, height=8, corner_radius=4, fg_color=color).pack(
                side="left", fill="x", expand=True, padx=(0 if i == 0 else 5, 0),
            )
        porcentaje = round(100 * listos / total) if chequeos else 0
        self.porcentaje_label.configure(text=f"{porcentaje}% listo")

    # --- armado ------------------------------------------------------------

    def _texto(self, campo) -> str:
        # Los campos narrativos y de gestión son CampoConInstruccion: su
        # .get() ya devuelve "" cuando lo que se ve es la marca de agua.
        return campo.get()

    def _curso_seleccionado(self) -> dict | None:
        return self._cursos_por_etiqueta.get(self.curso_menu.get())

    def _validar(self) -> str | None:
        if not self._curso_seleccionado():
            return "Elija un curso."
        if not self.mes_entry.get().strip():
            return "Falta el mes."

        etiquetas_preguntas = {clave: titulo for clave, titulo, _i in PREGUNTAS}
        for clave, box in self._pregunta_boxes.items():
            n = contar_palabras(self._texto(box))
            if n < MIN_PALABRAS_NARRATIVA:
                return f"«{etiquetas_preguntas[clave]}» necesita mínimo {MIN_PALABRAS_NARRATIVA} palabras (tiene {n})."

        if self.es_directivo:
            etiquetas_gestion = dict(CAMPOS_GESTION)
            for clave, box in self._gestion_boxes.items():
                n = contar_palabras(self._texto(box))
                if n < MIN_PALABRAS:
                    return f"«{etiquetas_gestion[clave]}» necesita mínimo {MIN_PALABRAS} palabras (tiene {n})."

        if not self.avances:
            return 'Cargá la "Evaluación de avance por tema" (botón "Cargar semanas del mes") antes de entregar.'
        for a in self.avances:
            if not a.a_dict()["observaciones"]:
                return f"Falta la observación de la semana {a.semana} en la evaluación de avance por tema."
        return None

    def _respuestas(self):
        """Lo que escribió el usuario, en la forma que espera el backend."""
        narrativa = {
            "objetivo_cumplimiento": self._texto(self._pregunta_boxes["objetivo"]),
            "logros_avances": self._texto(self._pregunta_boxes["logros"]),
            "dificultades": self._texto(self._pregunta_boxes["dificultades"]),
            "estrategias": self._texto(self._pregunta_boxes["estrategias"]),
            "situacion_positiva": self._texto(self._pregunta_boxes["situacion"]),
            "ctei_integracion": self._texto(self._pregunta_boxes["ctei"]),
            "avance_semanal": [a.a_dict() for a in self.avances],
        }
        incluir = bool(self.incluir_gestion_var.get()) if self.es_directivo else False
        gestion = None
        if self.es_directivo:
            gestion = {clave: self._texto(box) for clave, box in self._gestion_boxes.items()}
        return narrativa, gestion, incluir

    def _armar_contexto(self):
        """Pide al backend los datos agregados del mes ya mezclados con las
        respuestas de pantalla — esto es el borrador, todavía sin entregar."""
        curso = self._curso_seleccionado()
        narrativa, gestion, incluir = self._respuestas()
        return api_client.generar_informe_mensual(
            self.sesion["token"], curso["id"], self.mes_entry.get().strip(),
            narrativa, gestion, incluir,
        )

    # --- vista previa y guardado --------------------------------------------

    def _previsualizar(self):
        error = self._validar()
        if error:
            self.error_label.configure(text=error, text_color=tema.ROJO)
            return

        self.previsualizar_boton.configure(state="disabled", text="Generando...")
        self.error_label.configure(
            text="Armando el informe (puede tardar por las fotos)...", text_color=tema.TEXTO_MUTED
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
                text=f"Abra el {formato} para revisarlo. Si está bien, dele a guardar.",
                text_color=tema.VERDE,
            )

        def fallo(exc):
            self.previsualizar_boton.configure(state="normal", text="Ver vista previa")
            self.error_label.configure(text=str(exc), text_color=tema.ROJO)

        en_segundo_plano(self, trabajo, listo, fallo)

    def _guardar(self):
        """Entrega el informe: guarda las respuestas en el backend para
        poder reabrirlas y para que el dashboard sepa que ya está."""
        curso = self._curso_seleccionado()
        if not curso:
            return

        if not self._confirmar_pocas_clases():
            return

        narrativa, gestion, incluir = self._respuestas()

        self.guardar_boton.configure(state="disabled", text="Entregando...")
        self.error_label.configure(text="Entregando el informe...", text_color=tema.TEXTO_MUTED)
        self.update_idletasks()

        mes = self.mes_entry.get().strip()

        def trabajo(reportar):
            resultado = api_client.guardar_informe_mensual(
                self.sesion["token"], curso["id"], mes, narrativa, gestion, incluir,
            )
            # Archiva el .docx en Drive con lo recién entregado. Si esto
            # falla, la entrega ya quedó guardada: el documento es
            # evidencia, no el dato (igual que al editar una planeación).
            try:
                contexto = api_client.generar_informe_mensual(self.sesion["token"], curso["id"], mes)
                archivo = vista_previa.informe_para_subir(contexto)
                api_client.guardar_documento_informe(
                    self.sesion["token"], curso["id"], mes, archivo,
                    on_progress=lambda enviado, total: reportar((enviado, total)),
                )
            except Exception:  # noqa: BLE001 — la entrega ya se guardó
                pass
            return resultado

        empezo_subida = {"si": False}

        def progreso(valor):
            enviado, total = valor
            if not empezo_subida["si"]:
                empezo_subida["si"] = True
                self.barra_subida.iniciar("Subiendo el documento")
            self.barra_subida.actualizar(enviado, total, "Subiendo el documento")

        def listo(resultado):
            self.barra_subida.detener()
            self.guardar_boton.configure(text="Entregar informe del mes")
            verbo = "actualizado" if resultado.get("actualizado") else "entregado"
            self.error_label.configure(text=f"Informe {verbo} ✓", text_color=tema.VERDE)
            self._cargar_entregado()

        def fallo(exc):
            self.barra_subida.detener()
            self.guardar_boton.configure(state="normal", text="Entregar informe del mes")
            self.error_label.configure(text=str(exc), text_color=tema.ROJO)

        en_segundo_plano_con_progreso(self, trabajo, progreso, listo, fallo, bloquea_cierre=True)

    def _confirmar_pocas_clases(self) -> bool:
        """Con el mínimo (3) ya se puede entregar, pero si no llegó a lo
        normal (4) se confirma antes — puede ser justo (un feriado, un
        permiso) o puede que falte cargar una clase sin querer."""
        estado = self._estado_mes
        if not estado:
            return True
        registradas, esperadas = estado.get("registradas", 0), estado.get("esperadas", 0)
        if registradas >= esperadas:
            return True
        return messagebox.askyesno(
            "Menos clases de lo normal",
            f"Este mes cargó {registradas} de las {esperadas} clases esperadas para este curso.\n\n"
            "¿Confirma que está bien entregar el informe así, o prefiere ir a cargar la que falta "
            "antes de entregar?",
            icon="warning",
            default="no",
        )

    def _permitir(self, permitido: bool):
        """El informe del mes se arma con las planeaciones del mes: si
        faltan clases por cargar, no hay nada que generar todavía. Se
        bloquea acá además de en el backend para que el docente no llene
        seis campos largos y recién ahí se entere."""
        estado = "normal" if permitido else "disabled"
        self.previsualizar_boton.configure(state=estado)
        self.guardar_boton.configure(state="disabled")  # se habilita tras la vista previa

    def _cargar_entregado(self):
        """Si el informe de ese curso y mes ya se entregó, trae las
        respuestas para poder revisarlas o corregirlas. De paso comprueba
        que estén todas las planeaciones del mes."""
        curso = self._curso_seleccionado()
        if not curso:
            return

        mes = self.mes_entry.get().strip()

        def estado_listo(estado):
            if isinstance(estado, Exception):
                return
            self._estado_mes = estado
            faltan = estado.get("faltantes", 0)
            registradas = estado.get("registradas", 0)
            esperadas = estado.get("esperadas", 0)
            if faltan > 0:
                self.alerta_label.configure(
                    text=f"Le faltan {faltan} de {esperadas} planeaciones de {mes} para este curso.\n"
                         "Cárguelas desde «Nueva planeación de clase» y vuelva acá: el informe del mes "
                         "se arma con ellas.",
                    text_color="#8E2F23",
                )
                self.alerta_frame.configure(fg_color=tema.ROJO_CHIP_BG)
                self.alerta_frame.pack(fill="x", pady=(18, 0))
            elif registradas < esperadas:
                # Ya alcanza el mínimo para entregar, pero es menos de lo
                # normal — se avisa acá y se vuelve a confirmar al entregar,
                # en vez de bloquear: puede ser justo (un feriado, un
                # permiso) o puede que se haya olvidado cargar una.
                self.alerta_label.configure(
                    text=f"Tiene {registradas} de {esperadas} planeaciones de {mes} — lo normal son "
                         f"{esperadas}. Puede entregar así, pero revise si le falta cargar alguna antes.",
                    text_color=tema.AMBAR,
                )
                self.alerta_frame.configure(fg_color=tema.AMBAR_CHIP_BG)
                self.alerta_frame.pack(fill="x", pady=(18, 0))
            else:
                self.alerta_frame.pack_forget()

            self._permitir(faltan == 0)
            self._actualizar_estado()

        en_segundo_plano(
            self,
            lambda: api_client.obtener_estado_mes(self.sesion["token"], curso["id"], mes),
            estado_listo,
            lambda _exc: None,
            mostrar_overlay=False,
        )

        def cierre_listo(cierre):
            if isinstance(cierre, Exception) or not cierre.get("fijada"):
                self.cierre_label.pack_forget()
                return
            self.cierre_label.configure(
                text=f"El mes se cierra el {cierre['fecha_cierre']}. Después de esa fecha no puede "
                     f"cargar ni editar nada de {mes}.",
            )
            self.cierre_label.pack(fill="x", pady=(14, 0))

        en_segundo_plano(
            self,
            lambda: api_client.fecha_de_cierre(self.sesion["token"], mes),
            cierre_listo,
            lambda _exc: None,
            mostrar_overlay=False,
        )

        def listo(guardado):
            self._entregado = bool(guardado)
            self._actualizar_estado()
            if not guardado:
                return

            for clave, campo_clave in [
                ("objetivo", "objetivo_cumplimiento"), ("logros", "logros_avances"),
                ("dificultades", "dificultades"), ("estrategias", "estrategias"),
                ("situacion", "situacion_positiva"), ("ctei", "ctei_integracion"),
            ]:
                self._pregunta_boxes[clave].set(guardado.get(campo_clave, "") or "")
                self._actualizar_pregunta(clave)

            if self.es_directivo:
                for clave, box in self._gestion_boxes.items():
                    box.set(guardado.get("gestion_" + clave, "") or "")
                self.incluir_gestion_var.set(bool(guardado.get("incluye_gestion")))
            self._actualizar_estado()

        en_segundo_plano(
            self,
            # `mes` capturado arriba, no self.mes_entry.get() de nuevo acá:
            # esto corre en un hilo de fondo y Tkinter no es thread-safe —
            # leer el widget desde ahí puede tirar "main thread is not in
            # main loop" (visto a ojo con el harness de captura de pantalla
            # de la sesión, justo al recrear esta pantalla).
            lambda: api_client.obtener_informe_mensual(self.sesion["token"], curso["id"], mes),
            listo,
            lambda exc: self.error_label.configure(text=str(exc), text_color=tema.ROJO),
            mostrar_overlay=False,
        )
