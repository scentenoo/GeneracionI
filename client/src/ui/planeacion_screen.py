"""Formulario de planeación de clase — formato Diario Pedagógico del
programa (spec sección 8 + ajuste del piloto).

La clase se describe en tres momentos —inicial, desarrollo y final—, cada
uno con su texto y sus minutos, y con un mínimo de palabras distinto
(inicial 80, desarrollo 100, final 70). Las dos columnas de al lado —la
reflexión pedagógica (observaciones) y los avances/retrocesos— son de toda
la clase, una sola vez.

El curso sale de un desplegable con los cursos de ese docente; al cambiar
de curso se recarga la asistencia, que es por curso.
"""

from __future__ import annotations

import sys
import traceback
from tkinter import filedialog, messagebox
from typing import Callable

import customtkinter as ctk

import api_client
from services import date_utils, image_utils, vista_previa
from ui import tema
from ui.lista_dinamica import ListaDinamica
from ui.tareas import cache, en_segundo_plano, en_segundo_plano_con_progreso
from ui.widgets import (
    Acordeon,
    BarraDeSubida,
    CampoConContador,
    MIN_PALABRAS,
    campo_label,
    contar_palabras,
    miniatura_ctk,
    pildora,
)

MINUTOS_MINIMOS = 120
MINUTOS_ESPERADOS = 120
MIN_FOTOS_CLASE = 1
MAX_FOTOS_CLASE = 3
ANCHO_PANEL_DERECHO = 300

# (clave, etiqueta, mínimo de palabras, minutos sugeridos)
MOMENTOS = [
    ("inicial", "Momento inicial", 80, 60),
    ("desarrollo", "Momento de desarrollo", 100, 40),
    ("final", "Momento final", 70, 20),
]


class PlaneacionScreen(ctk.CTkFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None] | None = None):
        # Sin `on_volver` va montada como pestaña de PlaneacionesScreen.
        super().__init__(master, fg_color="transparent")
        self.sesion = sesion
        self.on_volver = on_volver
        self.foto_paths: list[str] = []
        self._cursos_por_nombre: dict[str, dict] = {}
        # Por momento: {clave: {"minutos": Entry, "texto": CampoConContador}}
        self.momentos: dict[str, dict] = {}
        self.momentos_acordeones: dict[str, Acordeon] = {}

        # Dos columnas, como en el mockup: el formulario a la izquierda
        # (scrollable, puede ser largo) y a la derecha un panel fijo con el
        # checklist "Antes de guardar" y el progreso "Este mes" — antes todo
        # vivía apilado en una sola columna y el checklist ni existía.
        self.columna_izquierda = ctk.CTkScrollableFrame(self, fg_color="transparent", label_text="")
        self.columna_izquierda.pack(side="left", fill="both", expand=True, padx=(0, 22))

        # El formulario entero es UNA sola tarjeta blanca con borde (como en
        # el mockup) — las secciones de adentro (temas, momentos, fotos...)
        # no llevan cada una su propio borde (salvo los momentos, que sí son
        # tarjetas propias); se separan con líneas finas, ver `_separador`.
        self._tarjeta_formulario = ctk.CTkFrame(
            self.columna_izquierda, fg_color=tema.FONDO_TARJETA, corner_radius=16,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        self._tarjeta_formulario.pack(fill="both", expand=True)
        self._contenido_formulario = ctk.CTkFrame(self._tarjeta_formulario, fg_color="transparent")
        self._contenido_formulario.pack(fill="both", expand=True, padx=28, pady=26)

        self.panel_derecho = ctk.CTkFrame(self, fg_color="transparent", width=ANCHO_PANEL_DERECHO)
        self.panel_derecho.pack(side="right", fill="y")
        self.panel_derecho.pack_propagate(False)

        self._construir_titulo_formulario()
        self._separador()
        self._construir_encabezado()
        self._construir_temas_vistos()
        self._separador()
        self._construir_momentos()
        self._separador()
        self._construir_columnas_clase()
        self._separador()
        self._construir_foto()
        self._separador()
        self._construir_asistencia()
        self._construir_checklist()
        self._construir_este_mes()

        self._cargar_cursos()

    # --- secciones -----------------------------------------------------

    def _separador(self):
        """Línea fina entre secciones de la tarjeta del formulario, como en
        el mockup — reemplaza el espaciado a puro `pady` de antes, cuando
        cada sección todavía no vivía dentro de una sola tarjeta.

        Con `tema.DIVISOR` (#EDEFED, pensado para separar renglones sutiles
        adentro de una tarjeta chica) esta línea quedaba prácticamente
        invisible sobre el blanco de la tarjeta grande del formulario — acá
        se usa el mismo gris del borde de la tarjeta y de los campos
        (`BORDE_TARJETA`/#E4E6E4), que sí se nota, como en el mockup."""
        ctk.CTkFrame(self._contenido_formulario, fg_color=tema.BORDE_TARJETA, height=1, corner_radius=0).pack(
            fill="x", pady=(24, 18)
        )

    def _construir_titulo_formulario(self):
        # Apiladas, no en la misma fila como en el mockup: la ventana de
        # esta app se puede achicar bastante más que el ancho del diseño
        # (minsize 560px, ver app.py), y con las dos frases en una sola
        # línea se pisaban apenas el panel derecho crecía.
        ctk.CTkLabel(
            self._contenido_formulario, text="Nueva planeación de clase",
            font=tema.fuente(17, "bold"), anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            self._contenido_formulario,
            text=f"Se guarda en el informe del mes {date_utils.hoy_iso()[:7]}",
            font=tema.fuente(11), text_color=tema.TEXTO_MUTED, anchor="w",
        ).pack(fill="x", pady=(2, 0))

    def _construir_encabezado(self):
        if self.on_volver is not None:
            ctk.CTkButton(
                self._contenido_formulario, text="← Volver", width=90, command=self.on_volver
            ).pack(anchor="w", pady=(0, 10))

        # Fecha y curso lado a lado (como en el mockup: la fecha no
        # necesita todo el ancho del formulario) — antes iban apiladas.
        fila = ctk.CTkFrame(self._contenido_formulario, fg_color="transparent")
        fila.pack(fill="x")
        # Sin ancho fijo ni pack_propagate(False) en esta columna: CTkFrame
        # pide 200px de alto por defecto, y con el ancho fijado y el
        # propagate apagado ese alto de 200 queda pegado — como `fila`
        # empaqueta por la altura del más alto, "Curso" (sin ancho fijo,
        # alto real ~65px) terminaría centrado dentro de esos 200px en vez
        # de arriba, corrido hacia abajo respecto a "Fecha" (ver
        # horas_gestion_screen.py, mismo caso). El ancho angosto sale de
        # limitar el CTkEntry mismo, no el frame que lo contiene.
        columna_fecha = ctk.CTkFrame(fila, fg_color="transparent")
        columna_fecha.pack(side="left", padx=(0, 18))
        columna_curso = ctk.CTkFrame(fila, fg_color="transparent")
        columna_curso.pack(side="left", fill="x", expand=True)

        campo_label(columna_fecha, "Fecha").pack(fill="x")
        self.fecha_entry = ctk.CTkEntry(columna_fecha, width=180)
        self.fecha_entry.insert(0, date_utils.hoy_iso())
        self.fecha_entry.bind("<KeyRelease>", lambda _e: self._actualizar_checklist())
        self.fecha_entry.pack(fill="x", pady=(2, 0))

        campo_label(columna_curso, "Curso").pack(fill="x")
        # CTkOptionMenu no tiene border_width/border_color propios (a
        # diferencia de CTkEntry) — sin este marco quedaba sin ningún borde,
        # a diferencia de "Fecha" al lado, que sí lo tiene.
        marco_curso = ctk.CTkFrame(
            columna_curso, corner_radius=10, border_width=1, border_color=tema.BORDE_TARJETA,
            fg_color=tema.FONDO_TARJETA,
        )
        marco_curso.pack(fill="x", pady=(2, 0))
        self.curso_menu = ctk.CTkOptionMenu(
            marco_curso, values=["(cargando...)"], command=self._al_cambiar_curso,
            fg_color=tema.FONDO_TARJETA, button_color=tema.FONDO_TARJETA,
            button_hover_color=tema.FONDO_CONTENIDO,
        )
        self.curso_menu.pack(fill="x", padx=2, pady=2)

        self.objetivo = CampoConContador(self._contenido_formulario, "Objetivo de la clase")
        self.objetivo.pack(fill="x", pady=(16, 4))
        self.objetivo.textbox.bind("<KeyRelease>", lambda _e: self._actualizar_checklist(), add="+")

    def _cargar_cursos(self):
        self.curso_menu.configure(values=["Cargando..."])
        self.curso_menu.set("Cargando...")

        def listo(cursos):
            self._cursos_por_nombre = {c["nombre"]: c for c in cursos}
            nombres = list(self._cursos_por_nombre)
            if not nombres:
                self.curso_menu.configure(values=["(no tiene cursos asignados)"])
                self.curso_menu.set("(no tiene cursos asignados)")
                self.error_label.configure(
                    text="No tiene ningún curso asignado. Pídale al equipo directivo que le cree uno."
                )
                return
            self.curso_menu.configure(values=nombres)
            self.curso_menu.set(nombres[0])
            self._cargar_asistencia()
            self._cargar_estado_mes()
            self._actualizar_checklist()

        en_segundo_plano(
            self,
            lambda: cache.mis_cursos(self.sesion["token"]),
            listo,
            lambda exc: self.error_label.configure(text=str(exc), text_color=tema.ROJO),
        )

    def _al_cambiar_curso(self, _valor):
        self._cargar_asistencia()
        self._cargar_estado_mes()
        self._actualizar_checklist()

    def _curso_actual(self) -> dict | None:
        return self._cursos_por_nombre.get(self.curso_menu.get())

    def _construir_temas_vistos(self):
        campo_label(self._contenido_formulario, "Temas vistos (uno por renglón)").pack(fill="x", pady=(10, 0))
        self.temas_lista = ListaDinamica(self._contenido_formulario, placeholder="Tema visto")
        self.temas_lista.pack(fill="x", pady=(2, 0))

    def _construir_momentos(self):
        encabezado = ctk.CTkFrame(self._contenido_formulario, fg_color="transparent")
        encabezado.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(
            encabezado, text="Momentos de la clase", font=tema.fuente(16, "bold")
        ).pack(side="left")
        self.minutos_pildora = pildora(encabezado, "", tema.VERDE_CHIP_TEXTO, tema.VERDE_CHIP_BG)
        self.minutos_pildora.pack(side="right")

        # Por momento: labels del encabezado del acordeón que se actualizan
        # en vivo (minutos y contador de palabras), como en el mockup —
        # antes esto era un solo string armado a mano en el título.
        self.momentos_labels: dict[str, dict] = {}

        for indice, (clave, etiqueta, minimo, minutos_sug) in enumerate(MOMENTOS):
            def _prefijo(padre, numero=indice + 1):
                ctk.CTkLabel(
                    padre, text=str(numero), width=26, height=26, corner_radius=8,
                    fg_color=tema.VERDE_OSCURO, text_color=tema.BLANCO, font=tema.fuente(12, "bold"),
                ).pack(side="left", padx=(16, 10), pady=12)

            def _extra(padre, clave=clave):
                palabras_label = ctk.CTkLabel(padre, text="", font=tema.fuente(12))
                palabras_label.pack(side="right", padx=(0, 10))
                min_label = ctk.CTkLabel(padre, text="", font=tema.fuente(12), text_color=tema.TEXTO_MUTED)
                min_label.pack(side="right", padx=(0, 10))
                self.momentos_labels[clave] = {"min": min_label, "palabras": palabras_label}

            # Abierto solo el primero: igual que el mockup, deja ver de
            # entrada dónde hay que escribir sin mostrar los tres a la vez.
            acordeon = Acordeon(
                self._contenido_formulario, etiqueta, abierto=(indice == 0),
                prefijo=_prefijo, encabezado_extra=_extra,
            )
            acordeon.pack(fill="x", pady=6)

            fila = ctk.CTkFrame(acordeon.contenido, fg_color="transparent")
            fila.pack(fill="x")
            ctk.CTkLabel(fila, text="Minutos", font=tema.fuente(13), text_color=tema.TEXTO_MUTED).pack(side="left")
            minutos_entry = ctk.CTkEntry(fila, width=90)
            minutos_entry.insert(0, str(minutos_sug))
            minutos_entry.pack(side="left", padx=(10, 0))
            minutos_entry.bind("<KeyRelease>", lambda _e: self._actualizar_minutos())

            texto = CampoConContador(acordeon.contenido, "Qué pasó en este momento", alto=110, minimo=minimo)
            texto.pack(fill="x", pady=(8, 0))
            texto.textbox.bind("<KeyRelease>", lambda _e: self._actualizar_minutos(), add="+")

            self.momentos[clave] = {"minutos": minutos_entry, "texto": texto}
            self.momentos_acordeones[clave] = acordeon

        self._actualizar_minutos()

    def _minutos_de(self, clave: str) -> int:
        try:
            return int(self.momentos[clave]["minutos"].get().strip() or 0)
        except ValueError:
            return 0

    def _actualizar_minutos(self):
        total = sum(self._minutos_de(c) for c in self.momentos)
        ok = total >= MINUTOS_MINIMOS
        self.minutos_pildora.configure(
            text=f"  {total} de {MINUTOS_MINIMOS} min mínimos  ",
            text_color=tema.VERDE_CHIP_TEXTO if ok else tema.ROJO,
            fg_color=tema.VERDE_CHIP_BG if ok else tema.ROJO_CHIP_BG,
        )

        for clave, _etiqueta, minimo, _sug in MOMENTOS:
            labels = self.momentos_labels.get(clave)
            if labels is None:
                continue
            minutos = self._minutos_de(clave)
            palabras = contar_palabras(self.momentos[clave]["texto"].get())
            labels["min"].configure(text=f"{minutos} min")
            labels["palabras"].configure(
                text=f"{palabras} / {minimo} palabras",
                text_color=tema.VERDE if palabras >= minimo else tema.ROJO,
            )

        # Al construir los momentos todavía no existe el checklist (se arma
        # después) — `_actualizar_minutos` también se llama en cada tecla, de
        # ahí la guarda en vez de reordenar la construcción.
        if hasattr(self, "_chequeos_contenedor"):
            self._actualizar_checklist()

    def _construir_columnas_clase(self):
        ctk.CTkLabel(
            self._contenido_formulario, text="Sobre toda la clase", font=tema.fuente(16, "bold"), anchor="w",
        ).pack(fill="x", pady=(0, 14))
        self.observaciones = CampoConContador(
            self._contenido_formulario,
            "Observaciones de clase que contribuyan a la fundamentación de Generación-I "
            "(pequeña reflexión pedagógica, incluye también lo disciplinar)",
            alto=100, pregunta=True,
        )
        self.observaciones.pack(fill="x", pady=4)
        self.avances = CampoConContador(
            self._contenido_formulario,
            "Avances o retrocesos observados en clase "
            "(se puede nombrar al estudiante, tipo evaluación cualitativa)",
            alto=100, pregunta=True,
        )
        self.avances.pack(fill="x", pady=4)

    def _construir_foto(self):
        encabezado = ctk.CTkFrame(self._contenido_formulario, fg_color="transparent")
        encabezado.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(encabezado, text="Fotos de la clase", font=tema.fuente(16, "bold")).pack(side="left")
        pildora(
            encabezado, f"mínimo {MIN_FOTOS_CLASE} · máximo {MAX_FOTOS_CLASE}",
            tema.AMBAR, tema.AMBAR_CHIP_BG,
        ).pack(side="right")
        self.fotos_contenedor = ctk.CTkFrame(self._contenido_formulario, fg_color="transparent")
        self.fotos_contenedor.pack(fill="x")
        self.agregar_foto_boton = ctk.CTkButton(
            self._contenido_formulario, text="+ Agregar foto...", width=140, command=self._agregar_foto
        )
        self.agregar_foto_boton.pack(anchor="w", pady=(4, 0))
        self._refrescar_fotos_ui()

    def _agregar_foto(self):
        if len(self.foto_paths) >= MAX_FOTOS_CLASE:
            return
        ruta = filedialog.askopenfilename(
            title="Elija una foto de la clase",
            filetypes=[("Imágenes", "*.jpg *.jpeg *.png")],
        )
        if ruta:
            self.foto_paths.append(ruta)
            self._refrescar_fotos_ui()

    def _quitar_foto(self, indice: int):
        del self.foto_paths[indice]
        self._refrescar_fotos_ui()

    def _refrescar_fotos_ui(self):
        for w in self.fotos_contenedor.winfo_children():
            w.destroy()

        if not self.foto_paths:
            ctk.CTkLabel(
                self.fotos_contenedor, text="Ninguna foto seleccionada", text_color=tema.GRIS
            ).pack(anchor="w")

        # CTk no se queda con su propia referencia a la imagen: sin guardarla
        # acá, Python la recolecta apenas termina esta función y la miniatura
        # queda en blanco.
        self._miniaturas = []
        for indice, ruta in enumerate(self.foto_paths):
            fila = ctk.CTkFrame(self.fotos_contenedor, fg_color="transparent")
            fila.pack(fill="x", pady=2)
            miniatura = miniatura_ctk(ruta)
            self._miniaturas.append(miniatura)
            ctk.CTkLabel(fila, image=miniatura, text="").pack(side="left", padx=(0, 8))
            nombre = ruta.replace("\\", "/").split("/")[-1]
            ctk.CTkLabel(fila, text=nombre).pack(side="left")
            ctk.CTkButton(
                fila, text="x", width=28, fg_color=tema.ROJO, hover_color=tema.ROJO_HOVER,
                command=lambda i=indice: self._quitar_foto(i),
            ).pack(side="left", padx=(8, 0))

        self.agregar_foto_boton.configure(
            state="normal" if len(self.foto_paths) < MAX_FOTOS_CLASE else "disabled"
        )

    def _construir_asistencia(self):
        encabezado = ctk.CTkFrame(self._contenido_formulario, fg_color="transparent")
        encabezado.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(encabezado, text="Asistencia", font=tema.fuente(16, "bold")).pack(side="left")
        self.asistencia_pildora = pildora(encabezado, "", tema.VERDE_CHIP_TEXTO, tema.VERDE_CHIP_BG)
        self.asistencia_pildora.pack(side="right")

        self.asistencia_vars: dict[str, ctk.BooleanVar] = {}
        # Grilla de 2 columnas con cada estudiante en su propia celda con
        # borde, como en el mockup — antes era una sola columna de
        # checkboxes sueltos sin marco.
        self.asistencia_contenedor = ctk.CTkFrame(self._contenido_formulario, fg_color="transparent")
        self.asistencia_contenedor.pack(fill="x")
        self.asistencia_contenedor.grid_columnconfigure(0, weight=1)
        self.asistencia_contenedor.grid_columnconfigure(1, weight=1)
        self._actualizar_pildora_asistencia()

    def _actualizar_pildora_asistencia(self):
        total = len(self.asistencia_vars)
        if total == 0:
            self.asistencia_pildora.configure(text="  —  ")
            return
        presentes = sum(1 for v in self.asistencia_vars.values() if v.get())
        self.asistencia_pildora.configure(text=f"  {presentes} de {total} presentes  ")

    def _cargar_asistencia(self):
        for w in self.asistencia_contenedor.winfo_children():
            w.destroy()
        self.asistencia_vars = {}
        self._actualizar_pildora_asistencia()

        curso = self._curso_actual()
        if not curso:
            return

        def listo(estudiantes):
            for w in self.asistencia_contenedor.winfo_children():
                w.destroy()
            if not estudiantes:
                ctk.CTkLabel(
                    self.asistencia_contenedor,
                    text="Este curso todavía no tiene estudiantes (los carga el directivo).",
                    text_color=tema.GRIS,
                ).pack(anchor="w")
                self._actualizar_pildora_asistencia()
                return
            for indice, est in enumerate(estudiantes):
                var = ctk.BooleanVar(value=True)
                celda = ctk.CTkFrame(
                    self.asistencia_contenedor, fg_color="transparent", border_width=1,
                    border_color=tema.DIVISOR, corner_radius=10,
                )
                celda.grid(row=indice // 2, column=indice % 2, sticky="ew", padx=4, pady=4)
                ctk.CTkCheckBox(
                    celda, text=est["nombre"], variable=var, command=self._actualizar_pildora_asistencia,
                ).pack(anchor="w", padx=10, pady=8)
                self.asistencia_vars[est["nombre"]] = var
            self._actualizar_pildora_asistencia()

        def fallo(exc):
            for w in self.asistencia_contenedor.winfo_children():
                w.destroy()
            ctk.CTkLabel(
                self.asistencia_contenedor, text=f"No se pudo cargar el grupo: {exc}", text_color=tema.ROJO
            ).pack(anchor="w")
            self._actualizar_pildora_asistencia()

        en_segundo_plano(
            self,
            lambda: api_client.obtener_estudiantes(self.sesion["token"], curso["id"]),
            listo,
            fallo,
        )

    def _construir_checklist(self):
        """Tarjeta fija en el panel derecho, como en el mockup: en vez de
        enterarse recién al previsualizar qué le falta, el docente ve en
        vivo qué le falta mientras completa el formulario."""
        tarjeta = ctk.CTkFrame(
            self.panel_derecho, fg_color=tema.FONDO_TARJETA, corner_radius=16,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        tarjeta.pack(fill="x")
        ctk.CTkLabel(
            tarjeta, text="Antes de guardar", font=tema.fuente(15, "bold"), anchor="w",
        ).pack(fill="x", padx=16, pady=(16, 8))

        self._chequeos_contenedor = ctk.CTkFrame(tarjeta, fg_color="transparent")
        self._chequeos_contenedor.pack(fill="x", padx=16)

        self.error_label = ctk.CTkLabel(
            tarjeta, text="", text_color=tema.ROJO, wraplength=ANCHO_PANEL_DERECHO - 32,
            justify="left", anchor="w",
        )
        self.error_label.pack(fill="x", padx=16, pady=(8, 0))

        self.previsualizar_boton = ctk.CTkButton(tarjeta, text="Ver vista previa", command=self._previsualizar)
        self.previsualizar_boton.pack(fill="x", padx=16, pady=(12, 6))
        self.guardar_boton = ctk.CTkButton(
            tarjeta, text="Guardar planeación", command=self._guardar, state="disabled"
        )
        self.guardar_boton.pack(fill="x", padx=16, pady=(0, 6))
        ctk.CTkLabel(
            tarjeta, text="Revise la vista previa para poder guardar.",
            text_color=tema.TEXTO_MUTED, font=tema.fuente(11), wraplength=ANCHO_PANEL_DERECHO - 32,
            justify="left", anchor="w",
        ).pack(fill="x", padx=16)
        self.barra_subida = BarraDeSubida(tarjeta)
        self.barra_subida.pack(fill="x", padx=16, pady=(4, 16))

        self._actualizar_checklist()

    def _chequeos(self) -> list[tuple[str, bool]]:
        """Los mismos chequeos de `_validar`, pero como lista para dibujar
        de a uno (✓/!) en vez de un solo mensaje de error al primero que
        falle — `_validar` sigue siendo la fuente de verdad al guardar."""
        fecha_ok = bool(self.fecha_entry.get().strip()) and self._curso_actual() is not None
        total = sum(self._minutos_de(c) for c in self.momentos)
        faltan_objetivo = max(0, MIN_PALABRAS - contar_palabras(self.objetivo.get()))
        momentos_incompletos = sum(
            1 for clave in self.momentos if not self.momentos[clave]["texto"].es_valido()
        )
        return [
            ("Fecha y curso seleccionados", fecha_ok),
            (f"{total} de {MINUTOS_MINIMOS} min completos", total >= MINUTOS_MINIMOS),
            (
                "Objetivo completo" if faltan_objetivo == 0
                else f"Objetivo: faltan {faltan_objetivo} palabras",
                faltan_objetivo == 0,
            ),
            (
                "Momentos completos" if momentos_incompletos == 0
                else f"{momentos_incompletos} momento(s) sin descripción",
                momentos_incompletos == 0,
            ),
        ]

    def _actualizar_checklist(self):
        for w in self._chequeos_contenedor.winfo_children():
            w.destroy()
        for texto, ok in self._chequeos():
            fila = ctk.CTkFrame(self._chequeos_contenedor, fg_color="transparent")
            fila.pack(fill="x", pady=3)
            texto_color = tema.VERDE_CHIP_TEXTO if ok else tema.ROJO
            fondo_color = tema.VERDE_CHIP_BG if ok else tema.ROJO_CHIP_BG
            insignia = ctk.CTkFrame(
                fila, width=18, height=18, corner_radius=9, fg_color=fondo_color,
            )
            insignia.pack(side="left", padx=(0, 11))
            insignia.pack_propagate(False)
            ctk.CTkLabel(
                insignia, text="✓" if ok else "!", text_color=texto_color, font=tema.fuente(11, "bold"),
            ).place(relx=0.5, rely=0.5, anchor="center")
            ctk.CTkLabel(
                fila, text=texto, font=tema.fuente(13), text_color=texto_color if not ok else tema.TEXTO_OSCURO,
                anchor="w", justify="left", wraplength=ANCHO_PANEL_DERECHO - 80,
            ).pack(side="left", fill="x", expand=True)

    def _construir_este_mes(self):
        tarjeta = ctk.CTkFrame(
            self.panel_derecho, fg_color=tema.FONDO_TARJETA, corner_radius=16,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        tarjeta.pack(fill="x", pady=(18, 0))
        ctk.CTkLabel(
            tarjeta, text="Este mes", font=tema.fuente(15, "bold"), anchor="w",
        ).pack(fill="x", padx=16, pady=(16, 2))
        self.este_mes_curso_label = ctk.CTkLabel(
            tarjeta, text="Elija un curso arriba.", font=tema.fuente(12),
            text_color=tema.TEXTO_MUTED, anchor="w", justify="left", wraplength=ANCHO_PANEL_DERECHO - 32,
        )
        self.este_mes_curso_label.pack(fill="x", padx=16, pady=(0, 14))

        # Número grande + "de N clases cargadas" al lado, como en el mockup
        # (antes era una sola oración chica, sin jerarquía visual).
        fila_stat = ctk.CTkFrame(tarjeta, fg_color="transparent")
        fila_stat.pack(fill="x", padx=16)
        self.este_mes_numero_label = ctk.CTkLabel(
            fila_stat, text="0", font=tema.fuente(30, "bold"), text_color=tema.VERDE_OSCURO,
        )
        self.este_mes_numero_label.pack(side="left")
        self.este_mes_conteo_label = ctk.CTkLabel(
            fila_stat, text="de 4 clases\ncargadas", font=tema.fuente(12), text_color=tema.TEXTO_MUTED,
            justify="left", anchor="w",
        )
        self.este_mes_conteo_label.pack(side="left", padx=(10, 0))

        # Barra de 4 segmentos (uno por clase esperada, no continua) — igual
        # que el mockup, en vez de una CTkProgressBar de un solo tramo.
        self.este_mes_segmentos_fila = ctk.CTkFrame(tarjeta, fg_color="transparent")
        self.este_mes_segmentos_fila.pack(fill="x", padx=16, pady=(12, 0))
        self.este_mes_aviso = ctk.CTkLabel(
            tarjeta, text="", font=tema.fuente(11), text_color=tema.AMBAR,
            fg_color=tema.AMBAR_CHIP_BG, corner_radius=8, anchor="w", justify="left",
            wraplength=ANCHO_PANEL_DERECHO - 56,
        )
        # Este aviso solo se empaqueta cuando hay fecha de cierre fijada
        # para el mes (ver _cargar_estado_mes) — la mayoría de los meses
        # todavía no la tienen fijada, y una caja ambar vacía se vería rota.
        self._este_mes_aviso_tarjeta = tarjeta
        self._dibujar_segmentos_mes(0, 4)

    def _dibujar_segmentos_mes(self, registradas: int, esperadas: int):
        for w in self.este_mes_segmentos_fila.winfo_children():
            w.destroy()
        n = max(esperadas, 1)
        for i in range(n):
            color = tema.VERDE if i < registradas else tema.BORDE_TARJETA
            # width=1 a propósito: sin ancho explícito, CTkFrame pide 200px
            # por defecto y con 3+ hermanos a expand=True customtkinter deja
            # al tercero en adelante pegados en 1x1 en vez de repartir el
            # espacio (probado a mano — un tk.Frame sin CTk sí lo reparte
            # bien, así que es cosa de CTkFrame, no de pack). Cualquier
            # ancho chico evita el bug; total, fill="x" lo estira después.
            segmento = ctk.CTkFrame(
                self.este_mes_segmentos_fila, width=1, height=7, corner_radius=4, fg_color=color,
            )
            segmento.pack(
                side="left", fill="x", expand=True, padx=(0 if i == 0 else 5, 0),
            )

    def _cargar_estado_mes(self):
        curso = self._curso_actual()
        self.este_mes_aviso.pack_forget()
        if not curso:
            self.este_mes_curso_label.configure(text="Elija un curso arriba.")
            self.este_mes_numero_label.configure(text="0")
            self.este_mes_conteo_label.configure(text="de 4 clases\ncargadas")
            self._dibujar_segmentos_mes(0, 4)
            return

        mes = date_utils.hoy_iso()[:7]
        self.este_mes_curso_label.configure(text=curso["nombre"])

        def listo(estado):
            if isinstance(estado, Exception):
                return
            registradas = estado.get("registradas", 0)
            esperadas = estado.get("esperadas", 0)
            self.este_mes_numero_label.configure(
                text=str(registradas),
                text_color=tema.VERDE_OSCURO if registradas >= esperadas else tema.TEXTO_OSCURO,
            )
            self.este_mes_conteo_label.configure(text=f"de {esperadas} clases\ncargadas")
            self._dibujar_segmentos_mes(registradas, esperadas)

        en_segundo_plano(
            self,
            lambda: api_client.obtener_estado_mes(self.sesion["token"], curso["id"], mes),
            listo,
            lambda _exc: None,
        )

        def cierre_listo(cierre):
            if isinstance(cierre, Exception) or not cierre.get("fijada"):
                self.este_mes_aviso.pack_forget()
                return
            self.este_mes_aviso.configure(text=f"El mes se cierra el {cierre['fecha_cierre']}")
            self.este_mes_aviso.pack(fill="x", padx=16, pady=(0, 16))

        en_segundo_plano(
            self,
            lambda: api_client.fecha_de_cierre(self.sesion["token"], mes),
            cierre_listo,
            lambda _exc: None,
        )

    # --- datos ------------------------------------------------------------

    def _momentos_datos(self) -> dict:
        return {
            clave: {"texto": self.momentos[clave]["texto"].get(), "minutos": self._minutos_de(clave)}
            for clave in self.momentos
        }

    def _contexto_documento(self, historial: list | None = None) -> dict:
        """Lo que va a la plantilla del .docx. `historial` va vacío en la
        vista previa (la planeación todavía no existe, no tiene historial
        propio) y se completa recién al subir el documento definitivo, una
        vez que guardar_planeacion ya generó su primera entrada."""
        curso = self._curso_actual()
        m = self._momentos_datos()
        return {
            "historial": historial or [],
            "fecha": date_utils.a_fecha_larga(self.fecha_entry.get().strip()),
            "grupo": curso["nombre"] if curso else "",
            "objetivo": self.objetivo.get(),
            "temas_vistos": self.temas_lista.valores(),
            "momento_inicial_min": str(m["inicial"]["minutos"]),
            "momento_inicial_texto": m["inicial"]["texto"],
            "momento_desarrollo_min": str(m["desarrollo"]["minutos"]),
            "momento_desarrollo_texto": m["desarrollo"]["texto"],
            "momento_final_min": str(m["final"]["minutos"]),
            "momento_final_texto": m["final"]["texto"],
            "observaciones": self.observaciones.get(),
            "avances": self.avances.get(),
            "asistencia": [
                {"nombre": nombre, "presente": "Sí" if var.get() else "No"}
                for nombre, var in self.asistencia_vars.items()
            ],
        }

    def _confirmar_exceso(self) -> bool:
        total = sum(self._minutos_de(c) for c in self.momentos)
        if total <= MINUTOS_ESPERADOS:
            return True
        horas = total / 60
        return messagebox.askyesno(
            "La clase pasa de 2 horas",
            f"Los momentos suman {total} minutos ({horas:.1f} horas) y una clase "
            f"son {MINUTOS_ESPERADOS} minutos.\n\n"
            "Esas horas se suman en el informe del mes y en la cuenta de cobro.\n\n"
            "¿Los minutos están bien así?",
            icon="warning",
            default="no",
        )

    def _previsualizar(self):
        error = self._validar()
        if error:
            self.error_label.configure(text=error, text_color=tema.ROJO)
            return
        if not self._confirmar_exceso():
            self.error_label.configure(text="Revise los minutos de cada momento.", text_color=tema.AMBAR)
            return

        self.previsualizar_boton.configure(state="disabled", text="Generando...")
        self.error_label.configure(text="Armando el documento...", text_color=tema.GRIS)

        def trabajo():
            return vista_previa.previsualizar_planeacion(self._contexto_documento(), self.foto_paths)

        def listo(resultado):
            _ruta, es_pdf = resultado
            self.previsualizar_boton.configure(state="normal", text="Ver vista previa de nuevo")
            self.guardar_boton.configure(state="normal")
            formato = "PDF" if es_pdf else "documento de Word"
            self.error_label.configure(
                text=f"Abra el {formato} para revisarlo. Si está bien, dele a guardar.",
                text_color=tema.VERDE,
            )

        def fallo(exc):
            self.previsualizar_boton.configure(state="normal", text="Ver vista previa")
            self.error_label.configure(text=f"No se pudo armar la vista previa: {exc}", text_color=tema.ROJO)

        en_segundo_plano(self, trabajo, listo, fallo)

    # --- guardar ---------------------------------------------------------

    def _validar(self) -> str | None:
        if not self.fecha_entry.get().strip():
            return "Falta la fecha"
        if not self._curso_actual():
            return "Elija un curso"
        if not self.objetivo.es_valido():
            return f"El objetivo necesita mínimo {MIN_PALABRAS} palabras"
        if not self.temas_lista.valores():
            return "Agregue al menos un tema visto"
        for clave, etiqueta, minimo, _sug in MOMENTOS:
            if self._minutos_de(clave) <= 0:
                return f"{etiqueta}: falta cuántos minutos duró"
            if not self.momentos[clave]["texto"].es_valido():
                return f"{etiqueta}: necesita mínimo {minimo} palabras"
        total = sum(self._minutos_de(c) for c in self.momentos)
        if total < MINUTOS_MINIMOS:
            return f"Los momentos suman {total} min y la clase necesita al menos {MINUTOS_MINIMOS}"
        if not self.observaciones.es_valido():
            return f"Las observaciones de clase necesitan mínimo {MIN_PALABRAS} palabras"
        if not self.avances.es_valido():
            return f"Los avances necesitan mínimo {MIN_PALABRAS} palabras"
        if not self.foto_paths:
            return "Falta al menos una foto de la clase"

        presentes = sum(1 for v in self.asistencia_vars.values() if v.get())
        es_directivo = self.sesion["rol"] in ("directivo", "ambos")
        if presentes == 0 and not es_directivo:
            return "No puede guardar una clase sin ningún estudiante presente"
        return None

    def _guardar(self):
        error = self._validar()
        if error:
            self.error_label.configure(text=error, text_color=tema.ROJO)
            return
        if not self._confirmar_exceso():
            self.error_label.configure(text="Revise los minutos de cada momento.", text_color=tema.AMBAR)
            return

        self.guardar_boton.configure(state="disabled", text="Comprobando...")
        self.error_label.configure(text="Viendo si ya hay una planeación para esta fecha...", text_color=tema.GRIS)

        curso = self._curso_actual()
        fecha = self.fecha_entry.get().strip()

        def revisar():
            return api_client.obtener_planeaciones(self.sesion["token"], curso_id=curso["id"], resumen=True)

        def listo_revision(planeaciones):
            existente = next((p for p in planeaciones if str(p["fecha"])[:10] == fecha), None)
            if existente and not self._confirmar_sobrescribir(existente):
                self.guardar_boton.configure(state="normal", text="Guardar planeación")
                self.error_label.configure(text="", text_color=tema.GRIS)
                return
            self._guardar_confirmado()

        def fallo_revision(_exc):
            # No poder chequear no tiene por qué frenar el guardado — el
            # backend igual deduplica por curso+fecha. Es la advertencia la
            # que se pierde, no la protección real.
            self._guardar_confirmado()

        en_segundo_plano(self, revisar, listo_revision, fallo_revision)

    def _confirmar_sobrescribir(self, existente: dict) -> bool:
        fecha_legible = date_utils.a_fecha_larga(existente["fecha"])
        aviso = f"Ya existe una planeación de «{existente['grupo']}» para el {fecha_legible}."
        if existente.get("estado") == "aprobado":
            aviso += "\n\nEsa planeación ya estaba APROBADA. Si la reemplaza, vuelve a quedar pendiente de revisión."
        aviso += "\n\nSi guarda, se reemplaza el contenido — no queda como una clase aparte.\n\n¿Continuar?"
        return messagebox.askyesno("Ya existe una planeación para esta fecha", aviso, icon="warning", default="no")

    def _guardar_confirmado(self):
        self.guardar_boton.configure(state="disabled", text="Guardando...")
        self.previsualizar_boton.configure(state="disabled")
        self.error_label.configure(text="Comprimiendo las fotos...", text_color=tema.GRIS)
        self.barra_subida.iniciar("Subiendo la planeación y las fotos")

        datos = {
            "fecha": self.fecha_entry.get().strip(),
            "curso_id": self._curso_actual()["id"],
            "objetivo": self.objetivo.get(),
            "temas_vistos": self.temas_lista.valores(),
            "momentos": self._momentos_datos(),
            "observaciones": self.observaciones.get(),
            "avances": self.avances.get(),
            "asistencia": [
                {"nombre": nombre, "presente": var.get()} for nombre, var in self.asistencia_vars.items()
            ],
        }
        contexto = self._contexto_documento()

        def trabajo(reportar):
            fotos = {"fotos_clase": [image_utils.foto_a_payload(p) for p in self.foto_paths]}
            resultado = api_client.guardar_planeacion(
                self.sesion["token"], datos, fotos,
                on_progress=lambda enviado, total: reportar(("planeacion", enviado, total)),
            )
            try:
                # Recién ahora existe la planeación (y su primera entrada de
                # historial, "entregada"/"reenviada") — sin esto, el
                # documento subido quedaría sin la hoja de auditoría al final.
                historial = api_client.historial_revision(
                    self.sesion["token"], "planeacion", str(resultado["id"])
                )
                # dict(contexto, ...) y no self._contexto_documento(historial)
                # de nuevo a propósito: eso volvería a leer los campos del
                # formulario, y acá ya estamos en el hilo de fondo — los
                # widgets de Tkinter solo se pueden leer desde el hilo
                # principal. `contexto` ya los tiene, tomados antes de
                # arrancar; acá solo se le suma el historial.
                contexto_final = dict(contexto, historial=historial)
                archivo = vista_previa.planeacion_para_subir(contexto_final, self.foto_paths)
                api_client.guardar_documento_planeacion(
                    self.sesion["token"], resultado["id"], archivo,
                    on_progress=lambda enviado, total: reportar(("documento", enviado, total)),
                )
            except Exception:  # noqa: BLE001
                traceback.print_exc(file=sys.stderr)
                resultado = dict(resultado, sin_documento=True)
            return resultado

        etapa_previa = {"nombre": None}
        textos_etapa = {"planeacion": "Subiendo la planeación y las fotos", "documento": "Subiendo el documento"}

        def progreso(valor):
            etapa, enviado, total = valor
            texto = textos_etapa[etapa]
            if etapa != etapa_previa["nombre"]:
                etapa_previa["nombre"] = etapa
                self.barra_subida.iniciar(texto)
            self.barra_subida.actualizar(enviado, total, texto)

        def listo(resultado):
            self.barra_subida.detener()
            self.previsualizar_boton.configure(state="normal", text="Ver vista previa")
            self.guardar_boton.configure(text="Guardar planeación")
            self._limpiar_formulario()
            if resultado.get("sin_documento"):
                self.error_label.configure(
                    text="Planeación guardada ✓, pero no se pudo subir el documento a Drive.\n"
                         "El informe del mes va a quedar sin el link de esta clase; se arregla "
                         "abriéndola desde «Mis planeaciones» y guardándola de nuevo.",
                    text_color=tema.AMBAR,
                )
            else:
                self.error_label.configure(
                    text=f"Planeación guardada (id {resultado['id']}) ✓", text_color=tema.VERDE
                )

        def fallo(exc):
            self.barra_subida.detener()
            self.previsualizar_boton.configure(state="normal", text="Ver vista previa")
            self.guardar_boton.configure(state="normal", text="Guardar planeación")
            self.error_label.configure(text=str(exc), text_color=tema.ROJO)

        en_segundo_plano_con_progreso(self, trabajo, progreso, listo, fallo, bloquea_cierre=True)

    def _limpiar_formulario(self):
        """Deja el formulario listo para la siguiente clase, conservando la
        fecha y el curso porque suelen repetirse en la misma sesión."""
        self.objetivo.set("")
        self.temas_lista.limpiar()
        for clave, _e, _m, sug in MOMENTOS:
            self.momentos[clave]["texto"].set("")
            self.momentos[clave]["minutos"].delete(0, "end")
            self.momentos[clave]["minutos"].insert(0, str(sug))
        self.observaciones.set("")
        self.avances.set("")
        self._actualizar_minutos()

        self.foto_paths = []
        self._refrescar_fotos_ui()
        self.guardar_boton.configure(state="disabled")
        self._cargar_asistencia()
        self._actualizar_checklist()
        self._cargar_estado_mes()  # la clase recién guardada ya cuenta para "Este mes"
