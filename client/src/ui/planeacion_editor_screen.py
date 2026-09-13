"""Editar una planeación ya guardada — formato Diario Pedagógico.

La usan dos caminos: el docente sobre las suyas desde "Mis planeaciones",
y el directivo sobre las de cualquiera desde "Planeaciones de un docente".
El permiso lo resuelve el backend (ver Planeaciones.js#editar_planeacion).

El curso no se edita acá: cambiarlo movería la planeación de curso, con su
asistencia y todo, que es otra operación.
"""

from __future__ import annotations

import base64
import shutil
import sys
import tempfile
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable

import customtkinter as ctk

import api_client
from services import date_utils, image_utils, vista_previa
from ui import tema
from ui.lista_dinamica import ListaDinamica
from ui.tareas import en_segundo_plano, en_segundo_plano_con_progreso
from ui.widgets import (
    Acordeon, BarraDeSubida, CampoConContador, MIN_PALABRAS, campo_label, contar_palabras, miniatura_ctk,
)

MINUTOS_MINIMOS = 120
MIN_FOTOS_CLASE = 1
MAX_FOTOS_CLASE = 3

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
        self.momentos_acordeones: dict[str, Acordeon] = {}

        ctk.CTkButton(self, text="← Volver", width=90, command=on_volver).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(
            self, text=f"Curso: {planeacion.get('grupo') or '—'}", text_color=tema.GRIS, anchor="w"
        ).pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(self, text="Fecha (AAAA-MM-DD)", anchor="w").pack(fill="x")
        self.fecha_entry = ctk.CTkEntry(self)
        self.fecha_entry.insert(0, str(planeacion["fecha"])[:10])
        self.fecha_entry.pack(fill="x", pady=(2, 8))

        self.objetivo = CampoConContador(self, "Objetivo")
        self.objetivo.set(planeacion.get("objetivo", ""))
        self.objetivo.pack(fill="x", pady=(2, 8))

        campo_label(self, "Temas vistos").pack(fill="x", pady=(8, 0))
        self.temas_lista = ListaDinamica(self, placeholder="Tema visto")
        temas = planeacion.get("temas_vistos") or []
        if temas:
            self.temas_lista.filas[0].insert(0, temas[0])
            for tema_visto in temas[1:]:
                self.temas_lista.agregar_fila(tema_visto)
        self.temas_lista.pack(fill="x", pady=(2, 8))

        encabezado = ctk.CTkFrame(self, fg_color="transparent")
        encabezado.pack(fill="x", pady=(10, 4))
        ctk.CTkLabel(
            encabezado, text="Momentos de la clase y tiempos", font=tema.fuente(peso="bold")
        ).pack(side="left")
        self.minutos_label = ctk.CTkLabel(encabezado, text="", font=tema.fuente(12))
        self.minutos_label.pack(side="right")

        guardados = planeacion.get("momentos") or {}
        for indice, (clave, etiqueta, minimo, sug) in enumerate(MOMENTOS):
            m = guardados.get(clave) or {}
            acordeon = Acordeon(self, etiqueta, abierto=(indice == 0))
            acordeon.pack(fill="x", pady=6)

            fila = ctk.CTkFrame(acordeon.contenido, fg_color="transparent")
            fila.pack(fill="x")
            ctk.CTkLabel(fila, text="Minutos:").pack(side="left")
            minutos_entry = ctk.CTkEntry(fila, width=60)
            minutos_entry.insert(0, str(m.get("minutos") or sug))
            minutos_entry.pack(side="left", padx=(4, 0))
            minutos_entry.bind("<KeyRelease>", lambda _e: self._actualizar_minutos())

            texto = CampoConContador(acordeon.contenido, "Qué pasó en este momento", alto=110, minimo=minimo)
            texto.set(m.get("texto", ""))
            texto.pack(fill="x", pady=(8, 0))
            texto.textbox.bind("<KeyRelease>", lambda _e: self._actualizar_minutos(), add="+")

            self.momentos[clave] = {"minutos": minutos_entry, "texto": texto}
            self.momentos_acordeones[clave] = acordeon

        ctk.CTkLabel(self, text="Sobre toda la clase", font=tema.fuente(peso="bold")).pack(
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

        self._construir_fotos()

        self.error_label = ctk.CTkLabel(self, text="", text_color=tema.ROJO, wraplength=450, justify="left")
        self.error_label.pack(fill="x", pady=(16, 4))
        self.guardar_boton = ctk.CTkButton(self, text="Guardar cambios", command=self._guardar)
        self.guardar_boton.pack(pady=10)
        self.barra_subida = BarraDeSubida(self)
        self.barra_subida.pack(fill="x", pady=(4, 0))

        self._actualizar_minutos()

    # --- fotos --------------------------------------------------------------

    def _construir_fotos(self):
        """Las fotos no venían con la planeación que llega al editor (esa
        versión resumida no las trae): se piden aparte, y mientras tanto se
        puede seguir corrigiendo el resto del formulario sin esperarlas."""
        ctk.CTkLabel(
            self, text="Fotos de la clase (mínimo 1, máximo 3)",
            anchor="w", font=tema.fuente(peso="bold"),
        ).pack(fill="x", pady=(16, 4))

        self.foto_paths: list[str] = []
        self._fotos_modificadas = False
        self._fotos_listas = False
        self._carpeta_temp_fotos = Path(tempfile.mkdtemp(prefix="gi_editar_fotos_"))
        self.bind("<Destroy>", self._limpiar_temp_fotos)

        self.fotos_contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self.fotos_contenedor.pack(fill="x")
        ctk.CTkLabel(self.fotos_contenedor, text="Cargando fotos...", text_color=tema.GRIS).pack(anchor="w")

        self.agregar_foto_boton = ctk.CTkButton(
            self, text="+ Agregar foto...", width=140, command=self._agregar_foto, state="disabled"
        )
        self.agregar_foto_boton.pack(anchor="w", pady=(4, 0))

        def listo(fotos):
            for i, foto in enumerate(fotos):
                ext = ".png" if "png" in (foto.get("mimeType") or "") else ".jpg"
                ruta = self._carpeta_temp_fotos / f"foto_actual_{i + 1}{ext}"
                ruta.write_bytes(base64.b64decode(foto["base64"]))
                self.foto_paths.append(str(ruta))
            self._fotos_listas = True
            self._refrescar_fotos_ui()

        def fallo(exc):
            for w in self.fotos_contenedor.winfo_children():
                w.destroy()
            ctk.CTkLabel(
                self.fotos_contenedor, text=f"No se pudieron cargar las fotos: {exc}", text_color=tema.ROJO
            ).pack(anchor="w")

        en_segundo_plano(
            self,
            lambda: api_client.obtener_foto_planeacion(self.sesion["token"], self.planeacion["id"]),
            listo,
            fallo,
        )

    def _limpiar_temp_fotos(self, _evento=None):
        try:
            shutil.rmtree(self._carpeta_temp_fotos, ignore_errors=True)
        except Exception:  # noqa: BLE001 — limpieza best-effort al cerrar la pantalla
            pass

    def _agregar_foto(self):
        if len(self.foto_paths) >= MAX_FOTOS_CLASE:
            return
        ruta = filedialog.askopenfilename(
            title="Elija una foto de la clase",
            filetypes=[("Imágenes", "*.jpg *.jpeg *.png")],
        )
        if ruta:
            self.foto_paths.append(ruta)
            self._fotos_modificadas = True
            self._refrescar_fotos_ui()

    def _quitar_foto(self, indice: int):
        del self.foto_paths[indice]
        self._fotos_modificadas = True
        self._refrescar_fotos_ui()

    def _refrescar_fotos_ui(self):
        for w in self.fotos_contenedor.winfo_children():
            w.destroy()

        if not self.foto_paths:
            ctk.CTkLabel(
                self.fotos_contenedor, text="Ninguna foto seleccionada", text_color=tema.GRIS
            ).pack(anchor="w")

        self._miniaturas = []
        for indice, ruta in enumerate(self.foto_paths):
            fila = ctk.CTkFrame(self.fotos_contenedor, fg_color="transparent")
            fila.pack(fill="x", pady=2)
            miniatura = miniatura_ctk(ruta)
            self._miniaturas.append(miniatura)
            ctk.CTkLabel(fila, image=miniatura, text="").pack(side="left", padx=(0, 8))
            if str(self._carpeta_temp_fotos) in ruta:
                nombre = f"Foto {indice + 1} (ya guardada)"
            else:
                nombre = ruta.replace("\\", "/").split("/")[-1]
            ctk.CTkLabel(fila, text=nombre).pack(side="left")
            ctk.CTkButton(
                fila, text="x", width=28, fg_color=tema.ROJO, hover_color=tema.ROJO_HOVER,
                command=lambda i=indice: self._quitar_foto(i),
            ).pack(side="left", padx=(8, 0))

        self.agregar_foto_boton.configure(
            state="normal" if len(self.foto_paths) < MAX_FOTOS_CLASE else "disabled"
        )

    def _minutos_de(self, clave: str) -> int:
        try:
            return int(self.momentos[clave]["minutos"].get().strip() or 0)
        except ValueError:
            return 0

    def _actualizar_minutos(self):
        total = sum(self._minutos_de(c) for c in self.momentos)
        color = tema.VERDE if total >= MINUTOS_MINIMOS else tema.ROJO
        self.minutos_label.configure(text=f"{total} de {MINUTOS_MINIMOS} min mínimos", text_color=color)

        for clave, etiqueta, _minimo, _sug in MOMENTOS:
            acordeon = self.momentos_acordeones.get(clave)
            if acordeon is None:
                continue
            minutos = self._minutos_de(clave)
            palabras = contar_palabras(self.momentos[clave]["texto"].get())
            acordeon.configurar_titulo(f"{etiqueta} · {minutos} min · {palabras} palabras")

    def _validar(self) -> str | None:
        if not self._fotos_listas:
            return "Espere a que terminen de cargar las fotos."
        if not self.foto_paths:
            return "Falta al menos una foto de la clase"
        if not self.fecha_entry.get().strip():
            return "Falta la fecha"
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
            return f"Las observaciones necesitan mínimo {MIN_PALABRAS} palabras"
        if not self.avances.es_valido():
            return f"Los avances necesitan mínimo {MIN_PALABRAS} palabras"
        return None

    def _momentos_cambios(self) -> dict:
        return {
            clave: {"texto": self.momentos[clave]["texto"].get(), "minutos": self._minutos_de(clave)}
            for clave in self.momentos
        }

    def _contexto_documento(self, historial: list | None) -> dict:
        """Lo que va a la plantilla del .docx al regenerarlo tras editar. La
        asistencia no se edita acá: se toma tal cual quedó guardada."""
        m = self._momentos_cambios()
        asistencia = [
            {"nombre": a.get("nombre", ""), "presente": "Sí" if a.get("presente") else "No"}
            for a in (self.planeacion.get("asistencia") or [])
        ]
        return {
            "fecha": date_utils.a_fecha_larga(self.fecha_entry.get().strip()),
            "grupo": self.planeacion.get("grupo") or "",
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
            "asistencia": asistencia,
            "historial": historial or [],
        }

    def _guardar(self):
        error = self._validar()
        if error:
            self.error_label.configure(text=error, text_color=tema.ROJO)
            return

        planeacion_id = self.planeacion["id"]
        cambios = {
            "fecha": self.fecha_entry.get().strip(),
            "objetivo": self.objetivo.get(),
            "temas_vistos": self.temas_lista.valores(),
            "momentos": self._momentos_cambios(),
            "observaciones": self.observaciones.get(),
            "avances": self.avances.get(),
        }

        self.guardar_boton.configure(state="disabled", text="Guardando...")
        hay_fotos_nuevas = self._fotos_modificadas
        foto_paths = self.foto_paths
        self.error_label.configure(
            text="Comprimiendo las fotos..." if hay_fotos_nuevas else "Guardando...",
            text_color=tema.GRIS,
        )
        if hay_fotos_nuevas:
            self.barra_subida.iniciar("Subiendo las fotos")

        # Se arma ACÁ, en el hilo principal — es la única parte que lee
        # campos de Tkinter (self.objetivo.get(), etc.), y eso no se puede
        # hacer desde el hilo de fondo. El historial se le suma más abajo,
        # ya en trabajo(), con un simple dict(contexto, historial=...): eso
        # sí es solo un dato traído del backend, no un widget.
        contexto = self._contexto_documento(historial=None)

        def trabajo(reportar):
            # La compresión de las fotos (decodificar, redimensionar,
            # recodificar a JPEG) va acá adentro y no antes: hecha en el
            # hilo principal congelaba la ventana entera durante ese rato
            # —sin poder repintar ni la barra de subida— antes de que
            # arrancara siquiera el viaje al backend.
            fotos = None
            on_progress = None
            if hay_fotos_nuevas:
                fotos = {"fotos_clase": [image_utils.foto_a_payload(p) for p in foto_paths]}
                on_progress = lambda e, t: reportar(("planeacion", e, t))
            resultado = api_client.editar_planeacion(
                self.sesion["token"], planeacion_id, cambios, fotos, on_progress=on_progress
            )
            # Regenera el documento en Drive con el texto corregido (y las
            # fotos, si cambiaron) y con la hoja de historial al final. Si
            # algo falla acá, la edición ya quedó guardada: el documento es
            # evidencia, no el dato.
            try:
                historial = api_client.historial_revision(
                    self.sesion["token"], "planeacion", str(planeacion_id)
                )
                contexto_final = dict(contexto, historial=historial)
                archivo = vista_previa.planeacion_para_subir(contexto_final, self.foto_paths)
                api_client.guardar_documento_planeacion(
                    self.sesion["token"], planeacion_id, archivo,
                    on_progress=lambda e, t: reportar(("documento", e, t)),
                )
            except Exception:
                # La edición ya se guardó — que falle el documento no debe
                # tumbar el guardado. Se deja rastro en consola porque este
                # try/except ya escondió un bug real una vez (ver historial
                # de commits): sin esto, un error de acá es invisible.
                traceback.print_exc(file=sys.stderr)
            return resultado

        textos_etapa = {"planeacion": "Subiendo las fotos", "documento": "Subiendo el documento"}
        etapa_previa = {"nombre": None}

        def progreso(valor):
            etapa, enviado, total = valor
            texto = textos_etapa[etapa]
            if etapa != etapa_previa["nombre"]:
                etapa_previa["nombre"] = etapa
                self.barra_subida.iniciar(texto)
            self.barra_subida.actualizar(enviado, total, texto)

        def listo(_resultado):
            self.barra_subida.detener()
            self.guardar_boton.configure(state="normal", text="Guardar cambios")
            self.error_label.configure(text="Cambios guardados ✓", text_color=tema.VERDE)
            messagebox.showinfo("Listo", "Los cambios de la planeación quedaron guardados.")
            self.on_volver()

        def fallo(exc):
            self.barra_subida.detener()
            self.guardar_boton.configure(state="normal", text="Guardar cambios")
            self.error_label.configure(text=str(exc), text_color=tema.ROJO)

        en_segundo_plano_con_progreso(self, trabajo, progreso, listo, fallo, bloquea_cierre=True)
