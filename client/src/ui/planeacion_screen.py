"""Formulario de planeación de clase por bloques + checklist de asistencia
(spec sección 8). Punto de partida funcional para que Generación-I lo
termine de diseñar — hoy ya guarda de verdad contra el backend.

El curso sale de un desplegable con los cursos de ese docente: no se
escribe a mano, y quien tiene varios elige cuál. Al cambiar de curso se
recarga la lista de estudiantes, porque la asistencia es por curso.
"""

from __future__ import annotations

import sys
import traceback
from tkinter import filedialog, messagebox
from typing import Callable

import customtkinter as ctk

import api_client
from services import date_utils, image_utils, vista_previa
from ui.bloque_editor import BloqueEditor
from ui.lista_dinamica import ListaDinamica
from ui.tareas import cache, en_segundo_plano
from ui.widgets import CampoConContador, MIN_PALABRAS

MINUTOS_MINIMOS = 120
# Una clase dura 2 horas y se cobra por eso. Pasarse no está prohibido
# —a veces la clase se estira— pero sí suele ser un error de tipeo, y en
# el informe mensual esas horas se suman y descuadran la cuenta de cobro.
MINUTOS_ESPERADOS = 120


class PlaneacionScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None] | None = None):
        # Sin `on_volver` va montada como pestaña de PlaneacionesScreen, que
        # ya tiene su propio Volver arriba: dos seguidos confunden.
        super().__init__(master, label_text="" if on_volver is None else "Nueva planeación de clase")
        self.sesion = sesion
        self.on_volver = on_volver
        self.foto_path: str | None = None
        self.bloques: list[BloqueEditor] = []
        self._cursos_por_nombre: dict[str, dict] = {}

        self._construir_encabezado()
        self._construir_temas_vistos()
        self._construir_bloques()
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
        # En segundo plano: leer los cursos podía costar un viaje al backend
        # si el caché todavía no estaba caliente, y hacerlo en el hilo de la
        # interfaz congelaba «Nueva clase» al abrirla.
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

    def _construir_bloques(self):
        encabezado = ctk.CTkFrame(self, fg_color="transparent")
        encabezado.pack(fill="x", pady=(16, 4))
        ctk.CTkLabel(encabezado, text="Momentos de la clase", font=ctk.CTkFont(weight="bold")).pack(side="left")
        self.minutos_label = ctk.CTkLabel(encabezado, text="", font=ctk.CTkFont(size=12))
        self.minutos_label.pack(side="right")

        self.bloques_contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self.bloques_contenedor.pack(fill="x")
        ctk.CTkButton(self, text="+ Agregar bloque", command=self._agregar_bloque).pack(anchor="w", pady=(6, 0))
        self._agregar_bloque()

    def _agregar_bloque(self):
        bloque = BloqueEditor(
            self.bloques_contenedor, len(self.bloques) + 1, self._quitar_bloque, self._actualizar_minutos
        )
        bloque.pack(fill="x", pady=6)
        self.bloques.append(bloque)
        self._actualizar_minutos()

    def _quitar_bloque(self, bloque: BloqueEditor):
        if len(self.bloques) <= 1:
            return  # siempre tiene que quedar al menos un bloque
        self.bloques.remove(bloque)
        bloque.destroy()
        self._actualizar_minutos()

    def _actualizar_minutos(self):
        total = sum(b.minutos() for b in self.bloques)
        color = "#2fa84f" if total >= MINUTOS_MINIMOS else "#c0392b"
        self.minutos_label.configure(
            text=f"{total} de {MINUTOS_MINIMOS} min mínimos", text_color=color
        )

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
        self.asistencia_contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self.asistencia_contenedor.pack(fill="x")

    def _cargar_asistencia(self):
        for w in self.asistencia_contenedor.winfo_children():
            w.destroy()
        self.asistencia_vars = {}

        curso = self._curso_actual()
        if not curso:
            return

        try:
            estudiantes = api_client.obtener_estudiantes(self.sesion["token"], curso["id"])
        except api_client.ApiError as exc:
            ctk.CTkLabel(
                self.asistencia_contenedor, text=f"No se pudo cargar el grupo: {exc}", text_color="#c0392b"
            ).pack(anchor="w")
            return

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

    def _construir_acciones(self):
        self.error_label = ctk.CTkLabel(self, text="", text_color="#c0392b", wraplength=450, justify="left")
        self.error_label.pack(fill="x", pady=(16, 4))

        # Primero se revisa el documento, después se sube: guardar queda
        # deshabilitado hasta haber visto la vista previa.
        self.previsualizar_boton = ctk.CTkButton(
            self, text="Ver vista previa", command=self._previsualizar
        )
        self.previsualizar_boton.pack(pady=(0, 6))

        self.guardar_boton = ctk.CTkButton(
            self, text="Guardar planeación", command=self._guardar, state="disabled"
        )
        self.guardar_boton.pack(pady=(0, 10))

        ctk.CTkLabel(
            self,
            text="Revisá la vista previa para poder guardar.",
            text_color="gray",
            font=ctk.CTkFont(size=11),
        ).pack()

    # --- vista previa ------------------------------------------------------

    def _contexto_documento(self) -> dict:
        """Lo que va a la plantilla, armado con lo que hay en pantalla."""
        curso = self._curso_actual()
        return {
            "fecha": date_utils.a_fecha_larga(self.fecha_entry.get().strip()),
            "grupo": curso["nombre"] if curso else "",
            "objetivo": self.objetivo.get(),
            "temas_vistos": self.temas_lista.valores(),
            "bloques": [
                dict(b.a_dict(), momento=f"{b.momento_entry.get().strip()} ({b.minutos()} min)")
                for b in self.bloques
            ],
            "asistencia": [
                {"nombre": nombre, "presente": "Sí" if var.get() else "No"}
                for nombre, var in self.asistencia_vars.items()
            ],
        }

    def _confirmar_exceso(self) -> bool:
        """Avisa si la clase pasa de las 2 horas. Devuelve False si el
        docente prefiere volver a revisar los minutos."""
        total = sum(b.minutos() for b in self.bloques)
        if total <= MINUTOS_ESPERADOS:
            return True

        horas = total / 60
        return messagebox.askyesno(
            "La clase pasa de 2 horas",
            f"Los bloques suman {total} minutos ({horas:.1f} horas) y una clase "
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
            self.error_label.configure(text="Revisá los minutos de cada bloque.", text_color="#8A6114")
            return

        self.previsualizar_boton.configure(state="disabled", text="Generando...")
        self.error_label.configure(text="Armando el documento...", text_color="gray")
        self.update_idletasks()

        def trabajo():
            return vista_previa.previsualizar_planeacion(self._contexto_documento(), self.foto_path)

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
            self.error_label.configure(
                text=f"No se pudo armar la vista previa: {exc}", text_color="#c0392b"
            )

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
        for i, bloque in enumerate(self.bloques, start=1):
            if not bloque.momento_entry.get().strip():
                return f"Bloque {i}: falta el momento"
            if bloque.minutos() <= 0:
                return f"Bloque {i}: falta cuántos minutos duró"
            if not bloque.observacion.es_valido() or not bloque.avance.es_valido():
                return f"Bloque {i}: la observación y los avances necesitan {MIN_PALABRAS} palabras cada uno"
        total_minutos = sum(b.minutos() for b in self.bloques)
        if total_minutos < MINUTOS_MINIMOS:
            return f"Los bloques suman {total_minutos} min y la clase necesita al menos {MINUTOS_MINIMOS}"
        if not self.foto_path:
            return "Falta la foto de la clase"

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
        # Se vuelve a preguntar acá y no solo en la vista previa: entre una
        # cosa y la otra el docente pudo haber corregido los minutos.
        if not self._confirmar_exceso():
            self.error_label.configure(text="Revisá los minutos de cada bloque.", text_color="#8A6114")
            return

        self.guardar_boton.configure(state="disabled", text="Guardando...")
        self.previsualizar_boton.configure(state="disabled")
        self.error_label.configure(text="Comprimiendo la foto y subiendo...", text_color="gray")
        self.update_idletasks()

        datos = {
            "fecha": self.fecha_entry.get().strip(),
            "curso_id": self._curso_actual()["id"],
            "objetivo": self.objetivo.get(),
            "temas_vistos": self.temas_lista.valores(),
            "bloques": [b.a_dict() for b in self.bloques],
            "asistencia": [
                {"nombre": nombre, "presente": var.get()} for nombre, var in self.asistencia_vars.items()
            ],
        }

        contexto = self._contexto_documento()

        def trabajo():
            # La compresión de la foto también tarda, así que va al hilo.
            fotos = {"foto_clase": image_utils.foto_a_payload(self.foto_path)}
            resultado = api_client.guardar_planeacion(self.sesion["token"], datos, fotos)

            # El documento va después y aparte: si falla, la clase igual
            # quedó registrada. Lo único que se pierde es el link del
            # informe, que se puede rehacer editando la planeación.
            try:
                archivo = vista_previa.planeacion_para_subir(contexto, self.foto_path)
                api_client.guardar_documento_planeacion(
                    self.sesion["token"], resultado["id"], archivo
                )
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

        for bloque in self.bloques:
            bloque.destroy()
        self.bloques = []
        self._agregar_bloque()

        self.foto_path = None
        self.foto_label.configure(text="Ninguna foto seleccionada", text_color="gray")

        # La próxima planeación también hay que revisarla antes de subirla.
        self.guardar_boton.configure(state="disabled")

        self._cargar_asistencia()
