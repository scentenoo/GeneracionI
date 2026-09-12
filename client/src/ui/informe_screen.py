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
from ui.avance_semana_editor import AvanceSemanaEditor
from ui.tareas import en_segundo_plano, en_segundo_plano_con_progreso
from ui.widgets import Acordeon, BarraDeSubida, CampoConInstruccion, MIN_PALABRAS, contar_palabras

# Las seis preguntas narrativas (2.1 a 2.6) piden más desarrollo que un
# campo de detalle común — mismo mínimo que exige el backend (Informes.js).
MIN_PALABRAS_NARRATIVA = 80


class InformeScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None]):
        super().__init__(master, label_text="Generar informe mensual")
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

        ctk.CTkButton(self, text="← Volver", width=90, command=on_volver).pack(anchor="w", pady=(0, 10))

        self._construir_encabezado()
        self._construir_narrativa()
        self._construir_avance_semanal()
        if self.es_directivo:
            self._construir_gestion()
        self._construir_acciones()

        # Recién acá, con los botones ya creados, se puede saber si este
        # curso y mes están en condiciones de generar informe.
        self._cargar_entregado()

    # --- secciones -----------------------------------------------------

    def _construir_encabezado(self):
        ctk.CTkLabel(self, text="Mes a generar (AAAA-MM)").pack(anchor="w")
        self.mes_entry = ctk.CTkEntry(self, width=100)
        self.mes_entry.insert(0, date_utils.hoy_iso()[:7])
        self.mes_entry.pack(anchor="w", pady=(2, 10))

        # El informe va por curso: quien tiene dos cursos entrega dos.
        #
        # Acá se entrega SIEMPRE el propio, así que se muestran solo los
        # cursos propios —incluso a un directivo o al administrador—. Bajar
        # el informe de otro docente se hace desde «Informes del mes». Antes
        # esta pantalla listaba todos los cursos para quien supervisa, y eso
        # dejaba entregar (y pisar la narrativa de) el informe de otro.
        ctk.CTkLabel(self, text="Curso").pack(anchor="w")
        self._cursos_por_etiqueta: dict[str, dict] = {}
        try:
            self._cursos_por_etiqueta = {
                c["nombre"]: c for c in cache.mis_cursos(self.sesion["token"])
            }
        except api_client.ApiError:
            self._cursos_por_etiqueta = {}

        etiquetas = list(self._cursos_por_etiqueta) or ["(sin cursos)"]
        self.curso_menu = ctk.CTkOptionMenu(
            self, values=etiquetas, command=lambda _v: self._cargar_entregado()
        )
        self.curso_menu.set(etiquetas[0])
        self.curso_menu.pack(fill="x", pady=(2, 10))

        # Cambiar el mes también cambia si el informe se puede armar, así
        # que se revisa al salir del campo y no solo al elegir curso.
        self.mes_entry.bind("<FocusOut>", lambda _e: self._cargar_entregado())
        self.mes_entry.bind("<Return>", lambda _e: self._cargar_entregado())

        self.entregado_label = ctk.CTkLabel(self, text="", text_color="gray", anchor="w")
        self.entregado_label.pack(fill="x")

        self.faltantes_label = ctk.CTkLabel(
            self, text="", text_color="#c0392b", anchor="w", justify="left", wraplength=560
        )
        self.faltantes_label.pack(fill="x", pady=(4, 0))

        # Empacada acá mismo (no en _cargar_entregado) para que quede
        # siempre inmediatamente debajo del texto de faltantes: si se
        # empacara más tarde, quedaría al final de todo el formulario en
        # vez de debajo de su propio texto (pack ordena por momento de
        # llamada, no por creación).
        self.faltantes_barra = ctk.CTkProgressBar(self)
        self.faltantes_barra.set(0)
        self.faltantes_barra.pack(fill="x", pady=(6, 0))

    def _campo(
        self, etiqueta: str, instruccion: str = "", minimo: int = MIN_PALABRAS, padre=None,
    ) -> CampoConInstruccion:
        campo = CampoConInstruccion(padre if padre is not None else self, etiqueta, instruccion, minimo=minimo)
        campo.pack(fill="x")
        return campo

    def _construir_narrativa(self):
        # Acordeon en vez de las 6 cajas siempre visibles: son las preguntas
        # más largas del formulario, y colapsadas de a una vez completadas
        # dejan ver el resto de la pantalla sin scroll interminable.
        self.narrativa_acordeon = Acordeon(self, "2. Desarrollo del curso en el mes", abierto=True)
        self.narrativa_acordeon.pack(fill="x", pady=(16, 0))
        contenedor = self.narrativa_acordeon.contenido

        # Preguntas e instrucciones tal cual el formato oficial del programa
        # (formato informe mensual.docx). La instrucción va como marca de agua.
        self.objetivo_box = self._campo(
            "2.1. ¿Cuáles eran los objetivos o metas planteadas para el mes y en qué medida se cumplieron?",
            "Texto amplio: describa con amplitud los objetivos del mes, no un texto por salir del paso.",
            minimo=MIN_PALABRAS_NARRATIVA,
            padre=contenedor,
        )
        self.logros_box = self._campo(
            "2.2. Principales logros y avances observados en los estudiantes durante el mes.",
            "Háganlos a conciencia, revisando el nivel del grupo y los avances; sirve de insumo para "
            "mostrar que el programa avanza.",
            minimo=MIN_PALABRAS_NARRATIVA,
            padre=contenedor,
        )
        self.dificultades_box = self._campo(
            "2.3. Dificultades, inconvenientes o novedades presentadas.",
            "En lista.",
            minimo=MIN_PALABRAS_NARRATIVA,
            padre=contenedor,
        )
        self.estrategias_box = self._campo(
            "2.4. Estrategias, ajustes metodológicos implementados durante el mes.",
            "Describa con amplitud las estrategias desarrolladas en las clases; preste especial atención "
            "a si tuvo que hacer adecuaciones con estudiantes con discapacidad o trastornos del desarrollo.",
            minimo=MIN_PALABRAS_NARRATIVA,
            padre=contenedor,
        )
        self.situacion_box = self._campo(
            "2.5. Describa alguna situación excepcionalmente positiva que haya notado en algún estudiante o grupo.",
            "Escriba las cosas positivas dignas de resaltar y mostrar; lo que escriba acá se publica en la "
            "bitácora al final del año.",
            minimo=MIN_PALABRAS_NARRATIVA,
            padre=contenedor,
        )
        self.ctei_box = self._campo(
            "2.6. ¿Cómo integró el componente CTeI (ciencia, tecnología e innovación) en el mes?",
            "Todos los cursos deben integrar la misionalidad científica de Generación-I; describa AMPLIAMENTE "
            "cómo se desarrolló.",
            minimo=MIN_PALABRAS_NARRATIVA,
            padre=contenedor,
        )

    def _construir_avance_semanal(self):
        ctk.CTkLabel(self, text="Evaluación de avance por tema", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", pady=(16, 4)
        )
        ctk.CTkLabel(
            self,
            text="Las semanas y sus temas salen de sus planeaciones del mes.",
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
            self.error_label.configure(text="Elija un curso primero.", text_color="#c0392b")
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
            editor = AvanceSemanaEditor(
                self.avances_contenedor, s["semana"], s.get("temas", []), s.get("fecha", "")
            )
            editor.pack(fill="x", pady=3)
            self.avances.append(editor)

    def _construir_gestion(self):
        self.gestion_acordeon = Acordeon(self, "Gestión institucional (su parte como directivo)", abierto=False)
        self.gestion_acordeon.pack(fill="x", pady=(16, 0))
        contenedor = self.gestion_acordeon.contenido

        # Si tenés varios cursos, las horas de gestión van en UNO solo de los
        # informes del mes; si no, se cobrarían dos veces.
        self.incluir_gestion_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            contenedor,
            text="Incluir mis horas de gestión en este informe",
            variable=self.incluir_gestion_var,
        ).pack(anchor="w", pady=(6, 0))
        ctk.CTkLabel(
            contenedor,
            text="Si tiene varios cursos, márquelo en uno solo del mes.",
            text_color="gray",
            font=ctk.CTkFont(size=11),
        ).pack(anchor="w")
        self.gestion_objetivos_box = self._campo("Objetivos y metas del mes", padre=contenedor)
        self.gestion_logros_box = self._campo("Principales logros, avances y entregables clave", padre=contenedor)
        self.gestion_novedades_box = self._campo("Novedades, obstáculos o riesgos identificados", padre=contenedor)
        self.gestion_estrategias_box = self._campo("Estrategias y acciones correctivas", padre=contenedor)
        self.gestion_pendientes_box = self._campo("Pendientes prioritarios para el próximo mes", padre=contenedor)

    def _construir_acciones(self):
        self.error_label = ctk.CTkLabel(self, text="", text_color="#c0392b", wraplength=450, justify="left")
        self.error_label.pack(fill="x", pady=(16, 4))

        # Igual que en la planeación: primero se revisa, después se guarda.
        self.previsualizar_boton = ctk.CTkButton(
            self, text="Ver vista previa", command=self._previsualizar
        )
        self.previsualizar_boton.pack(pady=(0, 6))

        self.guardar_boton = ctk.CTkButton(
            self, text="Entregar informe del mes", command=self._guardar, state="disabled"
        )
        self.guardar_boton.pack(pady=(0, 10))

        ctk.CTkLabel(
            self,
            text="Revise la vista previa para poder entregar.",
            text_color="gray",
            font=ctk.CTkFont(size=11),
        ).pack()
        self.barra_subida = BarraDeSubida(self)
        self.barra_subida.pack(fill="x", pady=(4, 0))

        # Descargar el informe de OTROS docentes ya no vive acá: se mudó a
        # «Informes del mes», en Dirección, que además baja todos en un ZIP.
        # Esta pantalla vuelve a ser solo para armar y entregar el propio.
        if self.puede_supervisar:
            ctk.CTkLabel(
                self,
                text="Para bajar informes ya entregados (los suyos o los de otros),\n"
                     "use «Informes del mes» en el menú.",
                text_color="gray",
                font=ctk.CTkFont(size=11),
                justify="center",
            ).pack(pady=(16, 10))

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

        campos = [
            (self.objetivo_box, "Objetivos del mes", MIN_PALABRAS_NARRATIVA),
            (self.logros_box, "Principales logros", MIN_PALABRAS_NARRATIVA),
            (self.dificultades_box, "Dificultades", MIN_PALABRAS_NARRATIVA),
            (self.estrategias_box, "Estrategias", MIN_PALABRAS_NARRATIVA),
            (self.situacion_box, "Situación positiva", MIN_PALABRAS_NARRATIVA),
            (self.ctei_box, "Componente CTeI", MIN_PALABRAS_NARRATIVA),
        ]
        if self.es_directivo:
            campos += [
                (self.gestion_objetivos_box, "Gestión: objetivos", MIN_PALABRAS),
                (self.gestion_logros_box, "Gestión: logros", MIN_PALABRAS),
                (self.gestion_novedades_box, "Gestión: novedades", MIN_PALABRAS),
                (self.gestion_estrategias_box, "Gestión: estrategias", MIN_PALABRAS),
                (self.gestion_pendientes_box, "Gestión: pendientes", MIN_PALABRAS),
            ]

        for box, nombre, minimo in campos:
            n = contar_palabras(self._texto(box))
            if n < minimo:
                return f"«{nombre}» necesita mínimo {minimo} palabras (tiene {n})."

        if not self.avances:
            return 'Cargá la "Evaluación de avance por tema" (botón "Cargar semanas del mes") antes de entregar.'
        for a in self.avances:
            if not a.a_dict()["observaciones"]:
                return f"Falta la observación de la semana {a.semana} en la evaluación de avance por tema."
        return None

    def _respuestas(self):
        """Lo que escribió el usuario, en la forma que espera el backend."""
        narrativa = {
            "objetivo_cumplimiento": self._texto(self.objetivo_box),
            "logros_avances": self._texto(self.logros_box),
            "dificultades": self._texto(self.dificultades_box),
            "estrategias": self._texto(self.estrategias_box),
            "situacion_positiva": self._texto(self.situacion_box),
            "ctei_integracion": self._texto(self.ctei_box),
            "avance_semanal": [a.a_dict() for a in self.avances],
        }
        incluir = bool(self.incluir_gestion_var.get()) if self.es_directivo else False
        gestion = None
        if self.es_directivo:
            gestion = {
                "objetivos": self._texto(self.gestion_objetivos_box),
                "logros": self._texto(self.gestion_logros_box),
                "novedades": self._texto(self.gestion_novedades_box),
                "estrategias": self._texto(self.gestion_estrategias_box),
                "pendientes": self._texto(self.gestion_pendientes_box),
            }
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
                text=f"Abra el {formato} para revisarlo. Si está bien, dele a guardar.",
                text_color="#2fa84f",
            )

        def fallo(exc):
            self.previsualizar_boton.configure(state="normal", text="Ver vista previa")
            self.error_label.configure(text=str(exc), text_color="#c0392b")

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
        self.error_label.configure(text="Entregando el informe...", text_color="gray")
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
            self.error_label.configure(text=f"Informe {verbo} ✓", text_color="#2fa84f")
            self._cargar_entregado()

        def fallo(exc):
            self.barra_subida.detener()
            self.guardar_boton.configure(state="normal", text="Entregar informe del mes")
            self.error_label.configure(text=str(exc), text_color="#c0392b")

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
        if permitido:
            self.guardar_boton.configure(state="disabled")  # se habilita tras la vista previa
        else:
            self.guardar_boton.configure(state="disabled")

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
                self.faltantes_label.configure(
                    text=f"Le faltan {faltan} de {esperadas} planeaciones de {mes} "
                         f"para este curso.\nCárguelas desde «Nueva planeación de clase» y "
                         "vuelva acá: el informe del mes se arma con ellas.",
                    text_color="#c0392b",
                )
            elif registradas < esperadas:
                # Ya alcanza el mínimo para entregar, pero es menos de lo
                # normal — se avisa acá y se vuelve a confirmar al entregar,
                # en vez de bloquear: puede ser justo (un feriado, un
                # permiso) o puede que se haya olvidado cargar una.
                self.faltantes_label.configure(
                    text=f"Tiene {registradas} de {esperadas} planeaciones de {mes} — lo normal son "
                         f"{esperadas}. Puede entregar así, pero revise si le falta cargar alguna antes.",
                    text_color="#8A6114",
                )
            else:
                self.faltantes_label.configure(text="")

            if esperadas > 0:
                self.faltantes_barra.set(min(registradas / esperadas, 1.0))
                self.faltantes_barra.configure(
                    progress_color="#2fa84f" if registradas >= esperadas else "#c0392b"
                )
            else:
                self.faltantes_barra.set(0)

            self._permitir(faltan == 0)

        en_segundo_plano(
            self,
            lambda: api_client.obtener_estado_mes(self.sesion["token"], curso["id"], mes),
            estado_listo,
            lambda _exc: None,
        )

        def listo(guardado):
            if not guardado:
                self.entregado_label.configure(text="Todavía no entregado.", text_color="gray")
                return

            self.entregado_label.configure(
                text="Ya entregado — puede corregirlo y volver a entregar.", text_color="#2fa84f"
            )
            for campo, clave in [
                (self.objetivo_box, "objetivo_cumplimiento"),
                (self.logros_box, "logros_avances"),
                (self.dificultades_box, "dificultades"),
                (self.estrategias_box, "estrategias"),
                (self.situacion_box, "situacion_positiva"),
                (self.ctei_box, "ctei_integracion"),
            ]:
                campo.set(guardado.get(clave, "") or "")

            if self.es_directivo:
                for campo, clave in [
                    (self.gestion_objetivos_box, "gestion_objetivos"),
                    (self.gestion_logros_box, "gestion_logros"),
                    (self.gestion_novedades_box, "gestion_novedades"),
                    (self.gestion_estrategias_box, "gestion_estrategias"),
                    (self.gestion_pendientes_box, "gestion_pendientes"),
                ]:
                    campo.set(guardado.get(clave, "") or "")
                self.incluir_gestion_var.set(bool(guardado.get("incluye_gestion")))

        en_segundo_plano(
            self,
            lambda: api_client.obtener_informe_mensual(
                self.sesion["token"], curso["id"], self.mes_entry.get().strip()
            ),
            listo,
            lambda exc: self.entregado_label.configure(text=str(exc), text_color="#c0392b"),
        )

