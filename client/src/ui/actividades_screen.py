"""Actividades del mes que no son clases: reuniones, claustros, informes,
atención a padres.

Son la mitad de lo que factura un docente —en el informe de julio, 8 de
16 horas— y hasta ahora no había dónde cargarlas, así que la cuenta de
cobro salía por la mitad.

Las clases no van acá: esas se cargan como planeación, que ya lleva sus
horas. El informe mensual junta las dos.
"""

from __future__ import annotations

from tkinter import filedialog, messagebox
from typing import Callable

import customtkinter as ctk

import api_client
from services import date_utils, image_utils
from ui import tema
from ui.cargando import Cargando
from ui.tareas import cache, en_segundo_plano
from ui.widgets import campo_label, miniatura_ctk

ANCHO_PANEL_DERECHO = 420


class ActividadesScreen(ctk.CTkFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None] | None = None):
        super().__init__(master, fg_color="transparent")
        self.sesion = sesion
        self.es_directivo = sesion["rol"] in ("directivo", "ambos")
        self._cursos_por_nombre: dict[str, dict] = {}
        self._editando: dict | None = None
        self.foto_path: str | None = None

        if on_volver is not None:
            ctk.CTkButton(
                self, text="← Volver", width=90, fg_color="transparent", border_width=1,
                text_color=tema.TEXTO_OSCURO, hover_color=tema.FONDO_TARJETA, command=on_volver,
            ).pack(anchor="w", pady=(0, 12))

        cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True)

        self.columna_izquierda = ctk.CTkScrollableFrame(cuerpo, fg_color="transparent", label_text="")
        self.columna_izquierda.pack(side="left", fill="both", expand=True, padx=(0, 22))

        self._tarjeta_formulario = ctk.CTkFrame(
            self.columna_izquierda, fg_color=tema.FONDO_TARJETA, corner_radius=16,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        self._tarjeta_formulario.pack(fill="both", expand=True)
        self._form = ctk.CTkFrame(self._tarjeta_formulario, fg_color="transparent")
        self._form.pack(fill="both", expand=True, padx=28, pady=26)

        self.panel_derecho = ctk.CTkScrollableFrame(
            cuerpo, fg_color="transparent", label_text="", width=ANCHO_PANEL_DERECHO,
        )
        self.panel_derecho.pack(side="right", fill="y")

        self._construir_formulario()
        self._construir_panel_derecho()
        self._cargar_cursos()

    # ------------------------------------------------------------------
    # Formulario
    # ------------------------------------------------------------------

    def _construir_formulario(self):
        self.titulo_form = ctk.CTkLabel(
            self._form, text="Registrar hora externa", font=tema.fuente(17, "bold"), anchor="w",
        )
        self.titulo_form.pack(fill="x")
        ctk.CTkLabel(
            self._form,
            text="Reuniones, claustros e informes: lo que se factura y no es una clase.",
            font=tema.fuente(12), text_color=tema.TEXTO_MUTED, anchor="w",
        ).pack(fill="x", pady=(3, 0))
        ctk.CTkFrame(self._form, fg_color=tema.DIVISOR, height=1).pack(fill="x", pady=(18, 20))

        fila_1 = ctk.CTkFrame(self._form, fg_color="transparent")
        fila_1.pack(fill="x")
        col_curso = ctk.CTkFrame(fila_1, fg_color="transparent")
        col_curso.pack(side="left", fill="x", expand=True, padx=(0, 16))
        col_fecha = ctk.CTkFrame(fila_1, fg_color="transparent")
        col_fecha.pack(side="left")

        campo_label(col_curso, "Va en el informe del curso").pack(fill="x")
        self.curso_menu = ctk.CTkOptionMenu(
            col_curso, values=["(cargando...)"], command=lambda _v: self._cargar_lista()
        )
        self.curso_menu.pack(fill="x", pady=(4, 0))

        campo_label(col_fecha, "Fecha").pack(fill="x")
        self.fecha_entry = ctk.CTkEntry(col_fecha, width=140)
        self.fecha_entry.insert(0, date_utils.hoy_iso())
        self.fecha_entry.bind("<KeyRelease>", lambda _e: self._al_cambiar_mes())
        self.fecha_entry.pack(fill="x", pady=(4, 0))

        fila_2 = ctk.CTkFrame(self._form, fg_color="transparent")
        fila_2.pack(fill="x", pady=(18, 0))
        col_actividad = ctk.CTkFrame(fila_2, fg_color="transparent")
        col_actividad.pack(side="left", fill="x", expand=True, padx=(0, 16))
        col_horas = ctk.CTkFrame(fila_2, fg_color="transparent")
        col_horas.pack(side="left")

        campo_label(col_actividad, "Actividad").pack(fill="x")
        self.descripcion_entry = ctk.CTkEntry(col_actividad, placeholder_text="Ej: Reunión comité de padres")
        self.descripcion_entry.pack(fill="x", pady=(4, 0))

        campo_label(col_horas, "Horas externas").pack(fill="x")
        self.horas_externas_entry = ctk.CTkEntry(col_horas, placeholder_text="0.0", width=90)
        self.horas_externas_entry.pack(fill="x", pady=(4, 0))

        etiqueta_foto = "obligatoria" if not self.es_directivo else "opcional"
        campo_label(self._form, f"Foto de la actividad · {etiqueta_foto}").pack(fill="x", pady=(20, 9))
        self._construir_dropzone_foto()

        self.error_label = ctk.CTkLabel(
            self._form, text="", text_color=tema.ROJO, wraplength=560, justify="left",
        )
        self.error_label.pack(fill="x", pady=(14, 0))

        botones = ctk.CTkFrame(self._form, fg_color="transparent")
        botones.pack(anchor="e", pady=(16, 0))
        self.cancelar_boton = ctk.CTkButton(
            botones, text="Cancelar edición", fg_color=tema.TEXTO_MUTED, hover_color=tema.GRIS,
            command=self._salir_de_edicion,
        )  # se muestra solo mientras se edita
        self.guardar_boton = ctk.CTkButton(
            botones, text="Agregar actividad", fg_color=tema.VERDE_OSCURO, hover_color=tema.VERDE_OSCURO_ACTIVO,
            command=self._guardar,
        )
        self.guardar_boton.pack(side="left")

        ctk.CTkLabel(
            self._form,
            text="«Cancelar edición» solo aparece mientras se está editando una actividad ya guardada.",
            font=tema.fuente(11), text_color=tema.TEXTO_MUTED, anchor="e", justify="right",
        ).pack(fill="x", pady=(6, 0))

    def _construir_dropzone_foto(self):
        self.dropzone = ctk.CTkFrame(
            self._form, fg_color=tema.FONDO_CONTENIDO, corner_radius=14,
            border_width=1.5, border_color=tema.BORDE_TARJETA,
        )
        self.dropzone.pack(fill="x")
        contenido = ctk.CTkFrame(self.dropzone, fg_color="transparent")
        contenido.pack(fill="x", padx=18, pady=18)

        self.foto_miniatura_label = ctk.CTkLabel(contenido, image=None, text="")
        self.foto_miniatura_label.pack(side="left")

        textos = ctk.CTkFrame(contenido, fg_color="transparent")
        textos.pack(side="left", fill="x", expand=True, padx=(16, 12))
        self.foto_titulo_label = ctk.CTkLabel(
            textos, text="", font=tema.fuente(14, "bold"), anchor="w",
        )
        self.foto_titulo_label.pack(fill="x")
        self.foto_label = ctk.CTkLabel(
            textos, text="", font=tema.fuente(11), text_color=tema.TEXTO_MUTED, anchor="w",
        )
        self.foto_label.pack(fill="x", pady=(2, 0))

        self.foto_boton = ctk.CTkButton(
            contenido, text="Elegir foto…", fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER,
            command=self._elegir_foto,
        )
        self.foto_boton.pack(side="left")
        self._actualizar_foto_label()

    # --- helpers del formulario -----------------------------------------

    def _actualizar_foto_label(self):
        if self.foto_path:
            self._miniatura_actual = miniatura_ctk(self.foto_path, tamano=64)
            self.foto_miniatura_label.configure(image=self._miniatura_actual)
            nombre = self.foto_path.replace("\\", "/").split("/")[-1]
            self.foto_titulo_label.configure(text=nombre)
            self.foto_label.configure(text="Lista para subir", text_color=tema.VERDE_CHIP_TEXTO)
            self.foto_boton.configure(text="Cambiar foto…")
            return
        self._miniatura_actual = None
        self.foto_miniatura_label.configure(image=None)
        self.foto_titulo_label.configure(text="Arrastre la foto o elíjala del equipo")
        self.foto_boton.configure(text="Elegir foto…")
        if self._editando and self._editando.get("foto_drive_id"):
            self.foto_label.configure(text="conserva la foto que ya tenía", text_color=tema.TEXTO_MUTED)
        elif self.es_directivo:
            self.foto_label.configure(text="JPG o PNG · opcional para directivos", text_color=tema.TEXTO_MUTED)
        else:
            self.foto_label.configure(
                text="JPG o PNG · sin foto la actividad no se guarda", text_color=tema.ROJO,
            )

    def _elegir_foto(self):
        ruta = filedialog.askopenfilename(
            title="Elija la foto de la actividad", filetypes=[("Imágenes", "*.jpg *.jpeg *.png")]
        )
        if ruta:
            self.foto_path = ruta
            self._actualizar_foto_label()

    def _editar(self, a: dict):
        """Carga la actividad en el formulario de arriba."""
        self._editando = a
        self.foto_path = None

        self.fecha_entry.delete(0, "end")
        self.fecha_entry.insert(0, str(a["fecha"])[:10])
        self.descripcion_entry.delete(0, "end")
        self.descripcion_entry.insert(0, a["descripcion"])
        self.horas_externas_entry.delete(0, "end")
        self.horas_externas_entry.insert(0, str(a.get("horas_externas") or ""))

        self.titulo_form.configure(text="Editar hora externa")
        self.guardar_boton.configure(text="Guardar cambios")
        self.cancelar_boton.pack(side="left", padx=(0, 8), before=self.guardar_boton)
        self._actualizar_foto_label()
        self.error_label.configure(text="")

    def _salir_de_edicion(self):
        self._editando = None
        self.foto_path = None
        for e in (self.descripcion_entry, self.horas_externas_entry):
            e.delete(0, "end")
        self.titulo_form.configure(text="Registrar hora externa")
        self.guardar_boton.configure(text="Agregar actividad")
        self.cancelar_boton.pack_forget()
        self._actualizar_foto_label()
        self.error_label.configure(text="")

    # --- carga de cursos y guardado ---------------------------------------

    def _cargar_cursos(self):
        # En segundo plano para no congelar la pestaña al abrirla si el
        # caché de cursos todavía no está caliente.
        self.curso_menu.configure(values=["Cargando..."])
        self.curso_menu.set("Cargando...")

        def listo(cursos):
            self._cursos_por_nombre = {c["nombre"]: c for c in cursos}
            nombres = list(self._cursos_por_nombre)
            if not nombres:
                self.curso_menu.configure(values=["(no tiene cursos)"])
                self.curso_menu.set("(no tiene cursos)")
                return
            self.curso_menu.configure(values=nombres)
            self.curso_menu.set(nombres[0])
            self._cargar_lista()

        en_segundo_plano(
            self,
            lambda: cache.mis_cursos(self.sesion["token"]),
            listo,
            lambda exc: self.error_label.configure(text=str(exc), text_color=tema.ROJO),
        )

    def _curso_actual(self) -> dict | None:
        return self._cursos_por_nombre.get(self.curso_menu.get())

    def _mes(self) -> str:
        return self.fecha_entry.get().strip()[:7] or date_utils.hoy_iso()[:7]

    def _al_cambiar_mes(self):
        if self._mes() != getattr(self, "_mes_cargada", None):
            self._cargar_lista()

    def _guardar(self):
        curso = self._curso_actual()
        if not curso:
            self.error_label.configure(text="Elija un curso.", text_color=tema.ROJO)
            return
        if not self.descripcion_entry.get().strip():
            self.error_label.configure(text="Escriba qué actividad fue.", text_color=tema.ROJO)
            return

        # Al editar, si ya tenía foto no hace falta subir una nueva.
        ya_tenia_foto = bool(self._editando and self._editando.get("foto_drive_id"))
        if not self.foto_path and not ya_tenia_foto and not self.es_directivo:
            self.error_label.configure(text="Falta la foto de la actividad.", text_color=tema.ROJO)
            return

        datos = {
            "curso_id": curso["id"],
            "fecha": self.fecha_entry.get().strip(),
            "descripcion": self.descripcion_entry.get().strip(),
            # Esta pantalla es solo para horas externas — "horas en sede" ya
            # se cargan como clase, con su planeación.
            "horas_sede": 0,
            "horas_externas": self.horas_externas_entry.get().strip() or 0,
        }
        editando = self._editando
        ruta_foto = self.foto_path

        self.guardar_boton.configure(state="disabled", text="Guardando...")
        self.error_label.configure(text="Guardando...", text_color=tema.TEXTO_MUTED)

        def trabajo():
            # Comprimir la foto también tarda, así que va al hilo.
            fotos = {"foto": image_utils.foto_a_payload(ruta_foto)} if ruta_foto else None
            if editando:
                return api_client.editar_actividad(
                    self.sesion["token"], editando["id"], datos, fotos
                )
            return api_client.guardar_actividad(self.sesion["token"], datos, fotos)

        def listo(_r):
            self.guardar_boton.configure(state="normal")
            self._salir_de_edicion()
            self._cargar_lista()
            self.error_label.configure(
                text="Cambios guardados ✓" if editando else "Actividad agregada ✓",
                text_color=tema.VERDE,
            )

        def fallo(exc):
            self.guardar_boton.configure(
                state="normal", text="Guardar cambios" if editando else "Agregar actividad"
            )
            self.error_label.configure(text=str(exc), text_color=tema.ROJO)

        en_segundo_plano(self, trabajo, listo, fallo, bloquea_cierre=True)

    def _eliminar(self, actividad_id: int, descripcion: str = ""):
        # Estas horas van a la cuenta de cobro del mes: borrar una por
        # error se paga con plata, así que se pregunta.
        corta = descripcion[:80] + ("..." if len(descripcion) > 80 else "")
        if not messagebox.askyesno(
            "Eliminar actividad",
            f"¿Eliminar «{corta}»?\n\n"
            "Sus horas dejan de contar en el informe del mes.\n"
            "Esto no se puede deshacer.",
            icon="warning",
            default="no",
        ):
            return

        if self._editando and self._editando["id"] == actividad_id:
            self._salir_de_edicion()
        en_segundo_plano(
            self,
            lambda: api_client.eliminar_actividad(self.sesion["token"], actividad_id),
            lambda _r: self._cargar_lista(),
            lambda exc: self.error_label.configure(text=str(exc), text_color=tema.ROJO),
            bloquea_cierre=True,
        )

    # ------------------------------------------------------------------
    # Panel derecho: resumen del mes + actividades registradas
    # ------------------------------------------------------------------

    def _construir_panel_derecho(self):
        tarjeta = ctk.CTkFrame(
            self.panel_derecho, fg_color=tema.FONDO_TARJETA, corner_radius=16,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        tarjeta.pack(fill="both", expand=True)
        contenido = ctk.CTkFrame(tarjeta, fg_color="transparent")
        contenido.pack(fill="both", expand=True, padx=22, pady=22)

        encabezado = ctk.CTkFrame(contenido, fg_color="transparent")
        encabezado.pack(fill="x")
        self.mes_label = ctk.CTkLabel(
            encabezado, text="", font=tema.fuente(15, "bold"), anchor="w",
        )
        self.mes_label.pack(side="left")
        ctk.CTkLabel(
            encabezado, text="Horas externas del mes", font=tema.fuente(12), text_color=tema.TEXTO_MUTED,
        ).pack(side="right")

        fila_stats = ctk.CTkFrame(contenido, fg_color="transparent")
        fila_stats.pack(fill="x", pady=(16, 0))
        self.tile_actividades = self._tile(fila_stats, "0", "actividades")
        self.tile_actividades.pack(side="left", fill="x", expand=True, padx=(0, 7))
        self.tile_horas = self._tile(fila_stats, "0h", "registradas")
        self.tile_horas.pack(side="left", fill="x", expand=True, padx=(7, 0))

        ctk.CTkFrame(contenido, fg_color=tema.DIVISOR, height=1).pack(fill="x", pady=18)

        self.lista_contenedor = ctk.CTkFrame(contenido, fg_color="transparent")
        self.lista_contenedor.pack(fill="both", expand=True)

    def _tile(self, padre, numero: str, etiqueta: str) -> ctk.CTkFrame:
        tile = ctk.CTkFrame(padre, fg_color=tema.FONDO_CONTENIDO, corner_radius=12)
        numero_label = ctk.CTkLabel(
            tile, text=numero, font=tema.fuente(24, "bold"), text_color=tema.VERDE_OSCURO, anchor="w",
        )
        numero_label.pack(fill="x", padx=14, pady=(14, 0))
        ctk.CTkLabel(
            tile, text=etiqueta, font=tema.fuente(11), text_color=tema.TEXTO_MUTED, anchor="w",
        ).pack(fill="x", padx=14, pady=(2, 14))
        tile.numero_label = numero_label  # type: ignore[attr-defined]
        return tile

    def _cargar_lista(self):
        for w in self.lista_contenedor.winfo_children():
            w.destroy()

        curso = self._curso_actual()
        if not curso:
            return

        mes = self._mes()
        self._mes_cargada = mes
        self.mes_label.configure(text=mes)
        Cargando(self.lista_contenedor, texto=f"Cargando las de {mes}...").pack(pady=16)

        def listo(actividades):
            for w in self.lista_contenedor.winfo_children():
                w.destroy()
            total = sum(
                (float(a.get("horas_sede") or 0) + float(a.get("horas_externas") or 0))
                for a in actividades
            )
            self.tile_actividades.numero_label.configure(text=str(len(actividades)))
            self.tile_horas.numero_label.configure(text=f"{total:g}h")

            if not actividades:
                ctk.CTkLabel(
                    self.lista_contenedor, text="Ninguna registrada este mes.", text_color=tema.TEXTO_MUTED,
                ).pack(anchor="w")
                return

            actividades.sort(key=lambda a: str(a["fecha"]))
            for a in actividades:
                self._fila(a)

        def fallo(exc):
            for w in self.lista_contenedor.winfo_children():
                w.destroy()
            self.error_label.configure(text=str(exc), text_color=tema.ROJO)

        en_segundo_plano(
            self,
            lambda: api_client.obtener_actividades(self.sesion["token"], curso["id"], mes),
            listo,
            fallo,
        )

    def _fila(self, a: dict):
        try:
            fecha = date_utils.a_fecha_corta(a["fecha"])
        except ValueError:
            fecha = str(a["fecha"])

        horas = []
        if float(a.get("horas_sede") or 0):
            horas.append(f"{float(a['horas_sede']):g}h en sede")
        if float(a.get("horas_externas") or 0):
            horas.append(f"{float(a['horas_externas']):g}h externas")

        marco = ctk.CTkFrame(
            self.lista_contenedor, fg_color=tema.BLANCO, corner_radius=12,
            border_width=1, border_color=tema.DIVISOR,
        )
        marco.pack(fill="x", pady=5)
        contenido = ctk.CTkFrame(marco, fg_color="transparent")
        contenido.pack(fill="x", padx=14, pady=12)

        fila_superior = ctk.CTkFrame(contenido, fg_color="transparent")
        fila_superior.pack(fill="x")
        ctk.CTkFrame(
            fila_superior, width=44, height=44, fg_color=tema.FONDO_CONTENIDO, corner_radius=9,
        ).pack(side="left")

        info = ctk.CTkFrame(fila_superior, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=(12, 0))
        ctk.CTkLabel(
            info, text=a["descripcion"], font=tema.fuente(13, "bold"),
            anchor="w", justify="left", wraplength=280,
        ).pack(fill="x")
        ctk.CTkLabel(
            info, text=f"{fecha} · {'  ·  '.join(horas)}", text_color=tema.TEXTO_MUTED,
            font=tema.fuente(11), anchor="w",
        ).pack(fill="x", pady=(2, 0))
        if not a.get("foto_drive_id"):
            ctk.CTkLabel(
                info, text="sin foto", text_color=tema.AMBAR, font=tema.fuente(10), anchor="w",
            ).pack(fill="x", pady=(3, 0))

        if a.get("bloqueada"):
            ctk.CTkLabel(
                contenido, text="Mes cerrado — pídale al equipo directivo que lo reabra.",
                font=tema.fuente(11), text_color=tema.AMBAR, fg_color=tema.AMBAR_CHIP_BG,
                anchor="w", wraplength=340, justify="left",
            ).pack(fill="x", pady=(10, 0))
            return

        botones = ctk.CTkFrame(contenido, fg_color="transparent")
        botones.pack(fill="x", pady=(10, 0))
        ctk.CTkButton(
            botones, text="Editar", fg_color="transparent", border_width=1, text_color=tema.VERDE_CHIP_TEXTO,
            border_color=tema.VERDE, command=lambda: self._editar(a),
        ).pack(side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkButton(
            botones, text="Quitar", fg_color=tema.ROJO, hover_color=tema.ROJO_HOVER,
            command=lambda: self._eliminar(a["id"], str(a.get("descripcion", ""))),
        ).pack(side="left", fill="x", expand=True)
