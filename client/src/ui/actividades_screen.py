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
from ui.tareas import cache, en_segundo_plano


class ActividadesScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None] | None = None):
        # Sin `on_volver` va montada como pestaña de PlaneacionesScreen.
        super().__init__(master, label_text="" if on_volver is None else "Otras actividades del mes")
        self.sesion = sesion
        self.es_directivo = sesion["rol"] in ("directivo", "ambos")
        self._cursos_por_nombre: dict[str, dict] = {}
        self._editando: dict | None = None
        self.foto_path: str | None = None

        if on_volver is not None:
            ctk.CTkButton(self, text="← Volver", width=90, command=on_volver).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(
            self,
            text="Reuniones, claustros, informes: lo que se factura y no es una clase.",
            text_color="gray",
            wraplength=450,
            justify="left",
        ).pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(self, text="Va en el informe del curso", anchor="w").pack(fill="x")
        self.curso_menu = ctk.CTkOptionMenu(
            self, values=["(cargando...)"], command=lambda _v: self._cargar_lista()
        )
        self.curso_menu.pack(fill="x", pady=(2, 8))

        ctk.CTkLabel(self, text="Fecha (AAAA-MM-DD)", anchor="w").pack(fill="x")
        self.fecha_entry = ctk.CTkEntry(self)
        self.fecha_entry.insert(0, date_utils.hoy_iso())
        self.fecha_entry.pack(fill="x", pady=(2, 8))

        ctk.CTkLabel(self, text="Actividad", anchor="w").pack(fill="x")
        self.descripcion_entry = ctk.CTkEntry(self, placeholder_text="Ej: Reunión comité de padres")
        self.descripcion_entry.pack(fill="x", pady=(2, 8))

        fila_horas = ctk.CTkFrame(self, fg_color="transparent")
        fila_horas.pack(fill="x", pady=(4, 0))
        ctk.CTkLabel(fila_horas, text="Horas en sede", width=110, anchor="w").pack(side="left")
        self.horas_sede_entry = ctk.CTkEntry(fila_horas, width=60)
        self.horas_sede_entry.pack(side="left")
        ctk.CTkLabel(fila_horas, text="   externas", width=90, anchor="w").pack(side="left")
        self.horas_externas_entry = ctk.CTkEntry(fila_horas, width=60)
        self.horas_externas_entry.pack(side="left")

        fila_foto = ctk.CTkFrame(self, fg_color="transparent")
        fila_foto.pack(fill="x", pady=(10, 0))
        ctk.CTkButton(fila_foto, text="Elegir foto...", width=110, command=self._elegir_foto).pack(side="left")
        self.foto_label = ctk.CTkLabel(fila_foto, text="", text_color="gray", anchor="w")
        self.foto_label.pack(side="left", padx=10)
        self._actualizar_foto_label()

        self.error_label = ctk.CTkLabel(self, text="", text_color="#c0392b", wraplength=450, justify="left")
        self.error_label.pack(fill="x", pady=(12, 4))

        acciones = ctk.CTkFrame(self, fg_color="transparent")
        acciones.pack(pady=(0, 16))
        self.guardar_boton = ctk.CTkButton(acciones, text="Agregar actividad", command=self._guardar)
        self.guardar_boton.pack(side="left")
        self.cancelar_boton = ctk.CTkButton(
            acciones, text="Cancelar edición", width=130, fg_color="gray", command=self._salir_de_edicion
        )

        self.total_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(weight="bold"), anchor="w")
        self.total_label.pack(fill="x", pady=(8, 4))

        self.lista_contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self.lista_contenedor.pack(fill="both", expand=True)

        self._cargar_cursos()

    def _cargar_cursos(self):
        try:
            cursos = cache.mis_cursos(self.sesion["token"])
        except api_client.ApiError as exc:
            self.error_label.configure(text=str(exc), text_color="#c0392b")
            return

        self._cursos_por_nombre = {c["nombre"]: c for c in cursos}
        nombres = list(self._cursos_por_nombre)
        if not nombres:
            self.curso_menu.configure(values=["(no tenés cursos)"])
            self.curso_menu.set("(no tenés cursos)")
            return
        self.curso_menu.configure(values=nombres)
        self.curso_menu.set(nombres[0])
        self._cargar_lista()

    def _curso_actual(self) -> dict | None:
        return self._cursos_por_nombre.get(self.curso_menu.get())

    def _mes(self) -> str:
        return self.fecha_entry.get().strip()[:7] or date_utils.hoy_iso()[:7]

    def _cargar_lista(self):
        for w in self.lista_contenedor.winfo_children():
            w.destroy()

        curso = self._curso_actual()
        if not curso:
            return

        mes = self._mes()
        self.total_label.configure(text=f"Cargando las de {mes}...", text_color="gray")

        def listo(actividades):
            total = sum(
                (float(a.get("horas_sede") or 0) + float(a.get("horas_externas") or 0))
                for a in actividades
            )
            self.total_label.configure(
                text=f"{mes}: {len(actividades)} actividades, {total:g} horas", text_color="white"
            )

            if not actividades:
                ctk.CTkLabel(
                    self.lista_contenedor, text="Ninguna registrada este mes.", text_color="gray"
                ).pack(anchor="w")
                return

            actividades.sort(key=lambda a: str(a["fecha"]))
            for a in actividades:
                self._fila(a)

        en_segundo_plano(
            self,
            lambda: api_client.obtener_actividades(self.sesion["token"], curso["id"], mes),
            listo,
            lambda exc: self.total_label.configure(text=str(exc), text_color="#c0392b"),
        )

    def _fila(self, a: dict):
        fila = ctk.CTkFrame(self.lista_contenedor, border_width=1, corner_radius=8)
        fila.pack(fill="x", pady=3)

        info = ctk.CTkFrame(fila, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=10, pady=8)

        try:
            fecha = date_utils.a_fecha_corta(a["fecha"])
        except ValueError:
            fecha = str(a["fecha"])

        horas = []
        if float(a.get("horas_sede") or 0):
            horas.append(f"{float(a['horas_sede']):g} h en sede")
        if float(a.get("horas_externas") or 0):
            horas.append(f"{float(a['horas_externas']):g} h externas")

        ctk.CTkLabel(
            info, text=a["descripcion"], font=ctk.CTkFont(weight="bold"), anchor="w", wraplength=330,
            justify="left",
        ).pack(fill="x")
        ctk.CTkLabel(
            info, text=f"{fecha}  ·  {'  ·  '.join(horas)}", text_color="gray", anchor="w"
        ).pack(fill="x")

        botones = ctk.CTkFrame(fila, fg_color="transparent")
        botones.pack(side="right", padx=10)
        ctk.CTkButton(
            botones, text="Quitar", width=80, fg_color="#c0392b", hover_color="#922b21",
            command=lambda: self._eliminar(a["id"], str(a.get("descripcion", ""))),
        ).pack(pady=2)
        ctk.CTkButton(botones, text="Editar", width=80, command=lambda: self._editar(a)).pack(pady=2)

        if not a.get("foto_drive_id"):
            ctk.CTkLabel(info, text="sin foto", text_color="#8A6114", anchor="w").pack(fill="x")

    # --- foto y modo edición ------------------------------------------------

    def _actualizar_foto_label(self):
        if self.foto_path:
            nombre = self.foto_path.replace("\\", "/").split("/")[-1]
            self.foto_label.configure(text=nombre, text_color="#2fa84f")
        elif self._editando and self._editando.get("foto_drive_id"):
            self.foto_label.configure(text="conserva la foto que ya tenía", text_color="gray")
        elif self.es_directivo:
            self.foto_label.configure(text="opcional para directivos", text_color="gray")
        else:
            self.foto_label.configure(text="obligatoria", text_color="#c0392b")

    def _elegir_foto(self):
        ruta = filedialog.askopenfilename(
            title="Elegí la foto de la actividad", filetypes=[("Imágenes", "*.jpg *.jpeg *.png")]
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
        self.horas_sede_entry.delete(0, "end")
        self.horas_sede_entry.insert(0, str(a.get("horas_sede") or ""))
        self.horas_externas_entry.delete(0, "end")
        self.horas_externas_entry.insert(0, str(a.get("horas_externas") or ""))

        self.guardar_boton.configure(text="Guardar cambios")
        self.cancelar_boton.pack(side="left", padx=(8, 0))
        self._actualizar_foto_label()
        self.error_label.configure(text=f"Editando: {a['descripcion']}", text_color="gray")

    def _salir_de_edicion(self):
        self._editando = None
        self.foto_path = None
        for e in (self.descripcion_entry, self.horas_sede_entry, self.horas_externas_entry):
            e.delete(0, "end")
        self.guardar_boton.configure(text="Agregar actividad")
        self.cancelar_boton.pack_forget()
        self._actualizar_foto_label()
        self.error_label.configure(text="")

    # --- guardar ------------------------------------------------------------

    def _guardar(self):
        curso = self._curso_actual()
        if not curso:
            self.error_label.configure(text="Elegí un curso.", text_color="#c0392b")
            return
        if not self.descripcion_entry.get().strip():
            self.error_label.configure(text="Escribí qué actividad fue.", text_color="#c0392b")
            return

        # Al editar, si ya tenía foto no hace falta subir una nueva.
        ya_tenia_foto = bool(self._editando and self._editando.get("foto_drive_id"))
        if not self.foto_path and not ya_tenia_foto and not self.es_directivo:
            self.error_label.configure(text="Falta la foto de la actividad.", text_color="#c0392b")
            return

        datos = {
            "curso_id": curso["id"],
            "fecha": self.fecha_entry.get().strip(),
            "descripcion": self.descripcion_entry.get().strip(),
            "horas_sede": self.horas_sede_entry.get().strip() or 0,
            "horas_externas": self.horas_externas_entry.get().strip() or 0,
        }
        editando = self._editando
        ruta_foto = self.foto_path

        self.guardar_boton.configure(state="disabled", text="Guardando...")
        self.error_label.configure(text="Guardando...", text_color="gray")

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
                text_color="#2fa84f",
            )

        def fallo(exc):
            self.guardar_boton.configure(
                state="normal", text="Guardar cambios" if editando else "Agregar actividad"
            )
            self.error_label.configure(text=str(exc), text_color="#c0392b")

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
            lambda exc: self.error_label.configure(text=str(exc), text_color="#c0392b"),
            bloquea_cierre=True,
        )
