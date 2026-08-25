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
from ui.lista_dinamica import ListaDinamica
from ui.tareas import cache, en_segundo_plano
from ui.widgets import CampoConContador, MIN_PALABRAS

MINUTOS_MINIMOS = 120
MINUTOS_ESPERADOS = 120
MIN_FOTOS_CLASE = 1
MAX_FOTOS_CLASE = 3

# (clave, etiqueta, mínimo de palabras, minutos sugeridos)
MOMENTOS = [
    ("inicial", "Momento inicial", 80, 60),
    ("desarrollo", "Momento de desarrollo", 100, 40),
    ("final", "Momento final", 70, 20),
]


class PlaneacionScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None] | None = None):
        # Sin `on_volver` va montada como pestaña de PlaneacionesScreen.
        super().__init__(master, label_text="" if on_volver is None else "Nueva planeación de clase")
        self.sesion = sesion
        self.on_volver = on_volver
        self.foto_paths: list[str] = []
        self._cursos_por_nombre: dict[str, dict] = {}
        # Por momento: {clave: {"minutos": Entry, "texto": CampoConContador}}
        self.momentos: dict[str, dict] = {}

        self._construir_encabezado()
        self._construir_temas_vistos()
        self._construir_momentos()
        self._construir_columnas_clase()
        self._construir_foto()
        self._construir_asistencia()
        self._construir_acciones()

        self._cargar_cursos()

    # --- secciones -----------------------------------------------------

    def _construir_encabezado(self):
        if self.on_volver is not None:
            ctk.CTkButton(self, text="← Volver", width=90, command=self.on_volver).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(self, text="Fecha (AAAA-MM-DD)", anchor="w").pack(fill="x")
        self.fecha_entry = ctk.CTkEntry(self)
        self.fecha_entry.insert(0, date_utils.hoy_iso())
        self.fecha_entry.pack(fill="x", pady=(2, 8))

        ctk.CTkLabel(self, text="Curso", anchor="w").pack(fill="x")
        self.curso_menu = ctk.CTkOptionMenu(
            self, values=["(cargando...)"], command=lambda _v: self._cargar_asistencia()
        )
        self.curso_menu.pack(fill="x", pady=(2, 8))

        self.objetivo = CampoConContador(self, "Objetivo de la clase")
        self.objetivo.pack(fill="x", pady=4)

    def _cargar_cursos(self):
        self.curso_menu.configure(values=["Cargando..."])
        self.curso_menu.set("Cargando...")

        def listo(cursos):
            self._cursos_por_nombre = {c["nombre"]: c for c in cursos}
            nombres = list(self._cursos_por_nombre)
            if not nombres:
                self.curso_menu.configure(values=["(no tenés cursos asignados)"])
                self.curso_menu.set("(no tenés cursos asignados)")
                self.error_label.configure(
                    text="No tenés ningún curso asignado. Pedile al equipo directivo que te cree uno."
                )
                return
            self.curso_menu.configure(values=nombres)
            self.curso_menu.set(nombres[0])
            self._cargar_asistencia()

        en_segundo_plano(
            self,
            lambda: cache.mis_cursos(self.sesion["token"]),
            listo,
            lambda exc: self.error_label.configure(text=str(exc), text_color="#c0392b"),
        )

    def _curso_actual(self) -> dict | None:
        return self._cursos_por_nombre.get(self.curso_menu.get())

    def _construir_temas_vistos(self):
        ctk.CTkLabel(self, text="Temas vistos (uno por renglón)", anchor="w").pack(fill="x", pady=(10, 0))
        self.temas_lista = ListaDinamica(self, placeholder="Tema visto")
        self.temas_lista.pack(fill="x", pady=(2, 0))

    def _construir_momentos(self):
        encabezado = ctk.CTkFrame(self, fg_color="transparent")
        encabezado.pack(fill="x", pady=(16, 4))
        ctk.CTkLabel(
            encabezado, text="Momentos de la clase y tiempos", font=ctk.CTkFont(weight="bold")
        ).pack(side="left")
        self.minutos_label = ctk.CTkLabel(encabezado, text="", font=ctk.CTkFont(size=12))
        self.minutos_label.pack(side="right")

        for clave, etiqueta, minimo, minutos_sug in MOMENTOS:
            marco = ctk.CTkFrame(self, border_width=1, corner_radius=8)
            marco.pack(fill="x", pady=6)

            fila = ctk.CTkFrame(marco, fg_color="transparent")
            fila.pack(fill="x", padx=10, pady=(8, 0))
            ctk.CTkLabel(fila, text=etiqueta, font=ctk.CTkFont(weight="bold")).pack(side="left")
            ctk.CTkLabel(fila, text="Minutos:").pack(side="left", padx=(12, 4))
            minutos_entry = ctk.CTkEntry(fila, width=60)
            minutos_entry.insert(0, str(minutos_sug))
            minutos_entry.pack(side="left")
            minutos_entry.bind("<KeyRelease>", lambda _e: self._actualizar_minutos())

            texto = CampoConContador(marco, "Qué pasó en este momento", alto=110, minimo=minimo)
            texto.pack(fill="x", padx=10, pady=(4, 10))

            self.momentos[clave] = {"minutos": minutos_entry, "texto": texto}

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

    def _construir_columnas_clase(self):
        ctk.CTkLabel(
            self, text="Sobre toda la clase", font=ctk.CTkFont(weight="bold")
        ).pack(fill="x", pady=(16, 0))
        self.observaciones = CampoConContador(
            self,
            "Observaciones de clase que contribuyan a la fundamentación de Generación-I "
            "(pequeña reflexión pedagógica, incluye también lo disciplinar)",
            alto=100,
        )
        self.observaciones.pack(fill="x", pady=4)
        self.avances = CampoConContador(
            self,
            "Avances o retrocesos observados en clase "
            "(se puede nombrar al estudiante, tipo evaluación cualitativa)",
            alto=100,
        )
        self.avances.pack(fill="x", pady=4)

    def _construir_foto(self):
        ctk.CTkLabel(
            self, text="Fotos de la clase (mínimo 1, máximo 3)",
            anchor="w", font=ctk.CTkFont(weight="bold"),
        ).pack(fill="x", pady=(16, 4))
        self.fotos_contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self.fotos_contenedor.pack(fill="x")
        self.agregar_foto_boton = ctk.CTkButton(
            self, text="+ Agregar foto...", width=140, command=self._agregar_foto
        )
        self.agregar_foto_boton.pack(anchor="w", pady=(4, 0))
        self._refrescar_fotos_ui()

    def _agregar_foto(self):
        if len(self.foto_paths) >= MAX_FOTOS_CLASE:
            return
        ruta = filedialog.askopenfilename(
            title="Elegí una foto de la clase",
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
                self.fotos_contenedor, text="Ninguna foto seleccionada", text_color="gray"
            ).pack(anchor="w")

        for indice, ruta in enumerate(self.foto_paths):
            fila = ctk.CTkFrame(self.fotos_contenedor, fg_color="transparent")
            fila.pack(fill="x", pady=2)
            nombre = ruta.replace("\\", "/").split("/")[-1]
            ctk.CTkLabel(fila, text=nombre).pack(side="left")
            ctk.CTkButton(
                fila, text="x", width=28, fg_color="#c0392b", hover_color="#922b21",
                command=lambda i=indice: self._quitar_foto(i),
            ).pack(side="left", padx=(8, 0))

        self.agregar_foto_boton.configure(
            state="normal" if len(self.foto_paths) < MAX_FOTOS_CLASE else "disabled"
        )

    def _construir_asistencia(self):
        ctk.CTkLabel(self, text="Asistencia", anchor="w", font=ctk.CTkFont(weight="bold")).pack(
            fill="x", pady=(16, 4)
        )
        self.asistencia_vars: dict[str, ctk.BooleanVar] = {}
        self.asistencia_contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self.asistencia_contenedor.pack(fill="x")

    def _cargar_asistencia(self):
        for w in self.asistencia_contenedor.winfo_children():
            w.destroy()
        self.asistencia_vars = {}

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
                    text_color="gray",
                ).pack(anchor="w")
                return
            for est in estudiantes:
                var = ctk.BooleanVar(value=True)
                ctk.CTkCheckBox(self.asistencia_contenedor, text=est["nombre"], variable=var).pack(anchor="w", pady=2)
                self.asistencia_vars[est["nombre"]] = var

        def fallo(exc):
            for w in self.asistencia_contenedor.winfo_children():
                w.destroy()
            ctk.CTkLabel(
                self.asistencia_contenedor, text=f"No se pudo cargar el grupo: {exc}", text_color="#c0392b"
            ).pack(anchor="w")

        en_segundo_plano(
            self,
            lambda: api_client.obtener_estudiantes(self.sesion["token"], curso["id"]),
            listo,
            fallo,
        )

    def _construir_acciones(self):
        self.error_label = ctk.CTkLabel(self, text="", text_color="#c0392b", wraplength=450, justify="left")
        self.error_label.pack(fill="x", pady=(16, 4))

        self.previsualizar_boton = ctk.CTkButton(self, text="Ver vista previa", command=self._previsualizar)
        self.previsualizar_boton.pack(pady=(0, 6))
        self.guardar_boton = ctk.CTkButton(
            self, text="Guardar planeación", command=self._guardar, state="disabled"
        )
        self.guardar_boton.pack(pady=(0, 10))
        ctk.CTkLabel(
            self, text="Revisá la vista previa para poder guardar.",
            text_color="gray", font=ctk.CTkFont(size=11),
        ).pack()

    # --- datos ------------------------------------------------------------

    def _momentos_datos(self) -> dict:
        return {
            clave: {"texto": self.momentos[clave]["texto"].get(), "minutos": self._minutos_de(clave)}
            for clave in self.momentos
        }

    def _contexto_documento(self) -> dict:
        """Lo que va a la plantilla del .docx."""
        curso = self._curso_actual()
        m = self._momentos_datos()
        return {
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
            self.error_label.configure(text=error, text_color="#c0392b")
            return
        if not self._confirmar_exceso():
            self.error_label.configure(text="Revisá los minutos de cada momento.", text_color="#8A6114")
            return

        self.previsualizar_boton.configure(state="disabled", text="Generando...")
        self.error_label.configure(text="Armando el documento...", text_color="gray")

        def trabajo():
            return vista_previa.previsualizar_planeacion(self._contexto_documento(), self.foto_paths)

        def listo(resultado):
            _ruta, es_pdf = resultado
            self.previsualizar_boton.configure(state="normal", text="Ver vista previa de nuevo")
            self.guardar_boton.configure(state="normal")
            formato = "PDF" if es_pdf else "documento de Word"
            self.error_label.configure(
                text=f"Abrí el {formato} para revisarlo. Si está bien, dale a guardar.",
                text_color="#2fa84f",
            )

        def fallo(exc):
            self.previsualizar_boton.configure(state="normal", text="Ver vista previa")
            self.error_label.configure(text=f"No se pudo armar la vista previa: {exc}", text_color="#c0392b")

        en_segundo_plano(self, trabajo, listo, fallo)

    # --- guardar ---------------------------------------------------------

    def _validar(self) -> str | None:
        if not self.fecha_entry.get().strip():
            return "Falta la fecha"
        if not self._curso_actual():
            return "Elegí un curso"
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
            return f"Las observaciones de clase necesitan mínimo {MIN_PALABRAS} palabras"
        if not self.avances.es_valido():
            return f"Los avances necesitan mínimo {MIN_PALABRAS} palabras"
        if not self.foto_paths:
            return "Falta al menos una foto de la clase"

        presentes = sum(1 for v in self.asistencia_vars.values() if v.get())
        es_directivo = self.sesion["rol"] in ("directivo", "ambos")
        if presentes == 0 and not es_directivo:
            return "No podés guardar una clase sin ningún estudiante presente"
        return None

    def _guardar(self):
        error = self._validar()
        if error:
            self.error_label.configure(text=error, text_color="#c0392b")
            return
        if not self._confirmar_exceso():
            self.error_label.configure(text="Revisá los minutos de cada momento.", text_color="#8A6114")
            return

        self.guardar_boton.configure(state="disabled", text="Comprobando...")
        self.error_label.configure(text="Viendo si ya hay una planeación para esta fecha...", text_color="gray")

        curso = self._curso_actual()
        fecha = self.fecha_entry.get().strip()

        def revisar():
            return api_client.obtener_planeaciones(self.sesion["token"], curso_id=curso["id"], resumen=True)

        def listo_revision(planeaciones):
            existente = next((p for p in planeaciones if str(p["fecha"])[:10] == fecha), None)
            if existente and not self._confirmar_sobrescribir(existente):
                self.guardar_boton.configure(state="normal", text="Guardar planeación")
                self.error_label.configure(text="", text_color="gray")
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
            aviso += "\n\nEsa planeación ya estaba APROBADA. Si la reemplazás, vuelve a quedar pendiente de revisión."
        aviso += "\n\nSi guardás, se reemplaza el contenido — no queda como una clase aparte.\n\n¿Continuar?"
        return messagebox.askyesno("Ya existe una planeación para esta fecha", aviso, icon="warning", default="no")

    def _guardar_confirmado(self):
        self.guardar_boton.configure(state="disabled", text="Guardando...")
        self.previsualizar_boton.configure(state="disabled")
        self.error_label.configure(text="Comprimiendo la foto y subiendo...", text_color="gray")

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

        def trabajo():
            fotos = {"fotos_clase": [image_utils.foto_a_payload(p) for p in self.foto_paths]}
            resultado = api_client.guardar_planeacion(self.sesion["token"], datos, fotos)
            try:
                archivo = vista_previa.planeacion_para_subir(contexto, self.foto_paths)
                api_client.guardar_documento_planeacion(self.sesion["token"], resultado["id"], archivo)
            except Exception:  # noqa: BLE001
                traceback.print_exc(file=sys.stderr)
                resultado = dict(resultado, sin_documento=True)
            return resultado

        def listo(resultado):
            self.previsualizar_boton.configure(state="normal", text="Ver vista previa")
            self.guardar_boton.configure(text="Guardar planeación")
            self._limpiar_formulario()
            if resultado.get("sin_documento"):
                self.error_label.configure(
                    text="Planeación guardada ✓, pero no se pudo subir el documento a Drive.\n"
                         "El informe del mes va a quedar sin el link de esta clase; se arregla "
                         "abriéndola desde «Mis planeaciones» y guardándola de nuevo.",
                    text_color="#8A6114",
                )
            else:
                self.error_label.configure(
                    text=f"Planeación guardada (id {resultado['id']}) ✓", text_color="#2fa84f"
                )

        def fallo(exc):
            self.previsualizar_boton.configure(state="normal", text="Ver vista previa")
            self.guardar_boton.configure(state="normal", text="Guardar planeación")
            self.error_label.configure(text=str(exc), text_color="#c0392b")

        en_segundo_plano(self, trabajo, listo, fallo, bloquea_cierre=True)

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
