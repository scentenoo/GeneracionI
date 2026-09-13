"""Horas de gestión (planeación administrativa, rol directivo) — log de
actividades administrativas del mes. Formato mucho más libre que la
planeación docente: sin momentos, sin mínimo de palabras (spec sección 6).

Lo que sí pide, desde el piloto, es la evidencia: cada actividad va con su
foto y con el producto/entregable que dejó. El link a la carpeta sigue
siendo opcional, porque la foto ya hace de soporte cuando no hay nada que
enlazar.

El mismo formulario sirve para cargar una nueva y para corregir una ya
registrada: al tocar «Editar» en una fila, sus datos suben al formulario
y «Guardar» pasa a actualizar esa en vez de crear otra.
"""

from __future__ import annotations

from tkinter import filedialog, messagebox
from typing import Callable

import customtkinter as ctk

import api_client
from services import date_utils, image_utils
from ui import tema
from ui.cargando import Cargando
from ui.tareas import en_segundo_plano
from ui.widgets import campo_label, miniatura_ctk

ANCHO_PANEL_DERECHO = 380


class HorasGestionScreen(ctk.CTkFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None]):
        super().__init__(master, fg_color="transparent")
        self.sesion = sesion
        self._editando: dict | None = None  # la fila que se está corrigiendo, o None
        self.foto_path: str | None = None  # foto elegida y todavía no subida

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
        self._cargar_lista()

    # ------------------------------------------------------------------
    # Formulario
    # ------------------------------------------------------------------

    def _construir_formulario(self):
        self.titulo_form = ctk.CTkLabel(
            self._form, text="Registrar actividad", font=tema.fuente(17, "bold"), anchor="w",
        )
        self.titulo_form.pack(fill="x")
        ctk.CTkLabel(
            self._form,
            text="Horas de gestión directiva: lo que no es clase pero queda documentado.",
            font=tema.fuente(12), text_color=tema.TEXTO_MUTED, anchor="w",
        ).pack(fill="x", pady=(3, 0))
        ctk.CTkFrame(self._form, fg_color=tema.DIVISOR, height=1).pack(fill="x", pady=(18, 20))

        fila = ctk.CTkFrame(self._form, fg_color="transparent")
        fila.pack(fill="x")
        # Sin ancho fijo por CTkFrame (y sin pack_propagate(False)): esos
        # frames por defecto piden 200px de alto, y al fijar solo el ancho
        # con propagate apagado ese alto de 200 queda pegado — como `fila`
        # empaqueta por altura del más alto, la columna de "Actividad" (sin
        # ancho fijo, alto real ~60px) termina centrada dentro de esos
        # 200px en vez de arriba. El ancho angosto de fecha/horas sale de
        # limitar el CTkEntry mismo, no el frame que lo contiene.
        col_fecha = ctk.CTkFrame(fila, fg_color="transparent")
        col_fecha.pack(side="left", padx=(0, 16))
        col_actividad = ctk.CTkFrame(fila, fg_color="transparent")
        col_actividad.pack(side="left", fill="x", expand=True, padx=(0, 16))
        col_horas = ctk.CTkFrame(fila, fg_color="transparent")
        col_horas.pack(side="left")

        campo_label(col_fecha, "Fecha").pack(fill="x")
        self.fecha_entry = ctk.CTkEntry(col_fecha, width=140)
        self.fecha_entry.insert(0, date_utils.hoy_iso())
        self.fecha_entry.pack(fill="x", pady=(4, 0))

        campo_label(col_actividad, "Actividad / tarea").pack(fill="x")
        self.actividad_entry = ctk.CTkEntry(col_actividad, placeholder_text="Ej: Claustro de docentes")
        self.actividad_entry.pack(fill="x", pady=(4, 0))

        campo_label(col_horas, "Horas").pack(fill="x")
        self.horas_entry = ctk.CTkEntry(col_horas, placeholder_text="0.0", width=90)
        self.horas_entry.pack(fill="x", pady=(4, 0))

        campo_label(self._form, "Producto / entregable").pack(fill="x", pady=(18, 0))
        self.entregable_entry = ctk.CTkEntry(
            self._form, placeholder_text="Qué quedó de la actividad: acta, listado, informe…"
        )
        self.entregable_entry.pack(fill="x", pady=(4, 0))

        fila_link = ctk.CTkFrame(self._form, fg_color="transparent")
        fila_link.pack(fill="x", pady=(18, 0))
        campo_label(fila_link, "Link a soporte / carpeta").pack(side="left")
        ctk.CTkLabel(
            fila_link, text="  (opcional)", font=tema.fuente(11), text_color=tema.TEXTO_MUTED,
        ).pack(side="left")
        self.link_entry = ctk.CTkEntry(self._form, placeholder_text="https://")
        self.link_entry.pack(fill="x", pady=(4, 0))

        campo_label(self._form, "Foto de la actividad · obligatoria").pack(fill="x", pady=(20, 9))
        self._construir_dropzone_foto()

        self.error_label = ctk.CTkLabel(
            self._form, text="", text_color=tema.ROJO, wraplength=560, justify="left",
        )
        self.error_label.pack(fill="x", pady=(14, 0))

        botones = ctk.CTkFrame(self._form, fg_color="transparent")
        botones.pack(anchor="e", pady=(16, 0))
        self.cancelar_boton = ctk.CTkButton(
            botones, text="Cancelar edición", fg_color="transparent", border_width=1,
            text_color=tema.TEXTO_OSCURO, command=self._cancelar_edicion,
        )  # se muestra solo mientras se edita
        self.guardar_boton = ctk.CTkButton(
            botones, text="Guardar", fg_color=tema.VERDE_OSCURO, hover_color=tema.VERDE_OSCURO_ACTIVO,
            command=self._guardar,
        )
        self.guardar_boton.pack(side="left")

        self.nota_editar_label = ctk.CTkLabel(
            self._form,
            text="Al editar una actividad guardada el título pasa a «Editar actividad» "
                 "y el botón a «Guardar cambios».",
            font=tema.fuente(11), text_color=tema.TEXTO_MUTED, anchor="e", justify="right",
        )
        self.nota_editar_label.pack(fill="x", pady=(6, 0))

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

    def _limpiar_form(self):
        self.fecha_entry.delete(0, "end")
        self.fecha_entry.insert(0, date_utils.hoy_iso())
        for e in (self.actividad_entry, self.horas_entry, self.entregable_entry, self.link_entry):
            e.delete(0, "end")
        self.foto_path = None
        self._actualizar_foto_label()

    def _actualizar_foto_label(self):
        """La foto es obligatoria salvo que se esté corrigiendo una fila que
        ya tiene la suya: en ese caso, no elegir ninguna la conserva."""
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
        elif self._editando:
            self.foto_label.configure(
                text="sin foto (de antes del piloto, no hace falta agregarla)", text_color=tema.TEXTO_MUTED,
            )
        else:
            self.foto_label.configure(text="Sin foto la actividad no se guarda.", text_color=tema.ROJO)

    def _elegir_foto(self):
        ruta = filedialog.askopenfilename(
            title="Elija la foto de la actividad", filetypes=[("Imágenes", "*.jpg *.jpeg *.png")]
        )
        if ruta:
            self.foto_path = ruta
            self._actualizar_foto_label()

    def _cancelar_edicion(self):
        self._editando = None
        self.titulo_form.configure(text="Registrar actividad")
        self.guardar_boton.configure(text="Guardar")
        self.cancelar_boton.pack_forget()
        self._limpiar_form()
        self.error_label.configure(text="")

    def _editar(self, a: dict):
        """Sube la fila al formulario para corregirla."""
        self._editando = a
        self.titulo_form.configure(text="Editar actividad")
        self.guardar_boton.configure(text="Guardar cambios")
        self.cancelar_boton.pack(side="left", padx=(0, 8), before=self.guardar_boton)

        self._limpiar_form()
        self.fecha_entry.delete(0, "end")
        self.fecha_entry.insert(0, str(a.get("fecha", ""))[:10])
        self.actividad_entry.insert(0, str(a.get("actividad", "")))
        self.horas_entry.insert(0, str(a.get("horas_sede", "")))
        self.entregable_entry.insert(0, str(a.get("entregable", "")))
        self.link_entry.insert(0, str(a.get("link_soporte", "")))
        self.error_label.configure(text="")

    def _guardar(self):
        if not self.actividad_entry.get().strip() or not self.horas_entry.get().strip():
            self.error_label.configure(text="Actividad y horas son obligatorias.", text_color=tema.ROJO)
            return
        if not self.entregable_entry.get().strip():
            self.error_label.configure(
                text="Falta el producto o entregable: es la prueba de la actividad.", text_color=tema.ROJO
            )
            return

        # La foto es obligatoria solo al crear. Al editar se conserva la que
        # ya tenía (incluso si esa fila es de antes del piloto y nunca tuvo
        # una) — exigirla ahí bloquearía corregir hasta la fecha.
        if not self._editando and not self.foto_path:
            self.error_label.configure(text="Falta la foto de la actividad.", text_color=tema.ROJO)
            return

        datos = {
            "fecha": self.fecha_entry.get().strip(),
            "actividad": self.actividad_entry.get().strip(),
            "horas_sede": self.horas_entry.get().strip(),
            "entregable": self.entregable_entry.get().strip(),
            "link_soporte": self.link_entry.get().strip(),
        }

        self.guardar_boton.configure(state="disabled")
        self.error_label.configure(text="Guardando...", text_color=tema.TEXTO_MUTED)
        editando = self._editando
        ruta_foto = self.foto_path

        def listo(_r):
            self.guardar_boton.configure(state="normal")
            self._cancelar_edicion()
            self.error_label.configure(
                text="Cambios guardados ✓" if editando else "Actividad guardada ✓", text_color=tema.VERDE
            )
            self._cargar_lista()

        def fallo(exc):
            self.guardar_boton.configure(state="normal")
            self.error_label.configure(text=str(exc), text_color=tema.ROJO)

        def trabajo():
            # Comprimir la foto también tarda, así que va al hilo.
            fotos = {"foto": image_utils.foto_a_payload(ruta_foto)} if ruta_foto else None
            if editando:
                return api_client.editar_horas_gestion(
                    self.sesion["token"], editando["id"], datos, fotos
                )
            return api_client.guardar_horas_gestion(self.sesion["token"], datos, fotos)

        en_segundo_plano(self, trabajo, listo, fallo, bloquea_cierre=True)

    def _eliminar(self, a: dict):
        if not messagebox.askyesno(
            "Eliminar actividad",
            f"¿Eliminar «{a.get('actividad', '')}» ({a.get('horas_sede', '')}h)?\n\n"
            "Esto no se puede deshacer.",
            icon="warning",
            default="no",
        ):
            return

        self.error_label.configure(text="Eliminando...", text_color=tema.TEXTO_MUTED)
        en_segundo_plano(
            self,
            lambda: api_client.eliminar_horas_gestion(self.sesion["token"], a["id"]),
            lambda _r: self._cargar_lista(),
            lambda exc: self.error_label.configure(text=str(exc), text_color=tema.ROJO),
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
        ctk.CTkLabel(
            encabezado, text="Actividades registradas", font=tema.fuente(15, "bold"), anchor="w",
        ).pack(side="left")
        ctk.CTkLabel(
            encabezado, text=date_utils.hoy_iso()[:7], font=tema.fuente(12), text_color=tema.TEXTO_MUTED,
        ).pack(side="right")

        fila_stats = ctk.CTkFrame(contenido, fg_color="transparent")
        fila_stats.pack(fill="x", pady=(16, 0))
        self.tile_actividades = self._tile(fila_stats, "0", "actividades")
        self.tile_actividades.pack(side="left", fill="x", expand=True, padx=(0, 7))
        self.tile_horas = self._tile(fila_stats, "0h", "de gestión")
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
        Cargando(self.lista_contenedor, texto="Cargando...").pack(pady=16)

        def listo(actividades):
            for w in self.lista_contenedor.winfo_children():
                w.destroy()

            total_horas = sum(float(a.get("horas_sede") or 0) for a in actividades)
            self.tile_actividades.numero_label.configure(text=str(len(actividades)))
            self.tile_horas.numero_label.configure(text=f"{total_horas:g}h")

            if not actividades:
                ctk.CTkLabel(
                    self.lista_contenedor, text="Todavía no hay actividades registradas.",
                    text_color=tema.TEXTO_MUTED,
                ).pack(anchor="w")
                return

            actividades.sort(key=lambda a: a["fecha"], reverse=True)
            for a in actividades:
                self._fila(a)

        def fallo(exc):
            for w in self.lista_contenedor.winfo_children():
                w.destroy()
            self.error_label.configure(text=str(exc), text_color=tema.ROJO)

        en_segundo_plano(
            self,
            lambda: api_client.obtener_horas_gestion(self.sesion["token"]),
            listo,
            fallo,
        )

    def _fila(self, a: dict):
        try:
            fecha_legible = date_utils.a_fecha_corta(a["fecha"])
        except ValueError:
            fecha_legible = a["fecha"]

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
            info, text=f"{a['actividad']}", font=tema.fuente(13, "bold"),
            anchor="w", justify="left", wraplength=260,
        ).pack(fill="x")
        ctk.CTkLabel(
            info, text=f"{fecha_legible} · {a.get('horas_sede', 0)}h", text_color=tema.TEXTO_MUTED,
            font=tema.fuente(11), anchor="w",
        ).pack(fill="x", pady=(2, 0))
        if a.get("entregable"):
            ctk.CTkLabel(
                info, text=f"Producto: {a['entregable']}", text_color=tema.TEXTO_OSCURO,
                font=tema.fuente(11), anchor="w", justify="left", wraplength=260,
            ).pack(fill="x", pady=(3, 0))
        # Las filas de antes del piloto no tienen foto: se avisa para que se
        # les pueda agregar una desde «Editar».
        if not a.get("foto_drive_id"):
            ctk.CTkLabel(
                info, text="sin foto", text_color=tema.AMBAR, font=tema.fuente(10), anchor="w",
            ).pack(fill="x", pady=(3, 0))

        botones = ctk.CTkFrame(contenido, fg_color="transparent")
        botones.pack(fill="x", pady=(10, 0))
        ctk.CTkButton(
            botones, text="Editar", fg_color="transparent", border_width=1, text_color=tema.VERDE_CHIP_TEXTO,
            border_color=tema.VERDE, command=lambda: self._editar(a),
        ).pack(side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkButton(
            botones, text="Eliminar", fg_color=tema.ROJO, hover_color=tema.ROJO_HOVER,
            command=lambda: self._eliminar(a),
        ).pack(side="left", fill="x", expand=True)
