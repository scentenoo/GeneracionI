"""Editar el perfil de un usuario existente + subir su firma — rol
directivo únicamente. Un docente no edita sus propios datos, se los pide
al equipo directivo (así lo pidió Samir).

También vive acá la gestión del administrador único y el borrado de
usuarios: un directivo puede eliminar docentes; eliminar a otro
directivo/ambos, o transferir el cargo de administrador, requiere ser el
administrador actual.
"""

from __future__ import annotations

from tkinter import filedialog, messagebox
from typing import Callable

import customtkinter as ctk

import api_client
from ui import tema
from ui.tareas import cache, en_segundo_plano
from services import image_utils
from ui.usuario_form_fields import construir_campos_perfil, leer_campos_perfil


class EditarUsuarioScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None] | None = None):
        # Sin `on_volver` va montada como pestaña de UsuariosScreen, que ya
        # tiene su propio Volver: dos seguidos confunden.
        super().__init__(master, label_text="" if on_volver is None else "Editar usuario")
        self.sesion = sesion
        self.on_volver = on_volver
        self._usuarios_por_nombre: dict[str, dict] = {}

        if on_volver is not None:
            ctk.CTkButton(self, text="← Volver", width=90, command=on_volver).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(self, text="Usuario").pack(anchor="w")
        self.usuario_menu = ctk.CTkOptionMenu(self, values=["(cargando...)"], command=lambda _v: self._cargar())
        self.usuario_menu.pack(anchor="w", pady=(2, 10))

        self.nombre_entry = self._campo("Nombre completo")
        ctk.CTkLabel(self, text="Rol").pack(anchor="w", pady=(8, 0))
        self.rol_menu = ctk.CTkOptionMenu(self, values=["docente", "directivo", "ambos"])
        self.rol_menu.pack(anchor="w", pady=(2, 0))

        self.campos_perfil = construir_campos_perfil(self)

        fila_firma = ctk.CTkFrame(self, fg_color="transparent")
        fila_firma.pack(fill="x", pady=(16, 4))
        ctk.CTkButton(fila_firma, text="Subir firma...", command=self._subir_firma).pack(side="left")
        self.firma_label = ctk.CTkLabel(fila_firma, text="", text_color=tema.GRIS)
        self.firma_label.pack(side="left", padx=10)

        self.error_label = ctk.CTkLabel(self, text="", text_color=tema.ROJO, wraplength=450, justify="left")
        self.error_label.pack(fill="x", pady=(16, 4))
        ctk.CTkButton(self, text="Guardar cambios", command=self._guardar).pack(pady=10)

        ctk.CTkLabel(self, text="Administrador", font=tema.fuente(peso="bold")).pack(anchor="w", pady=(20, 4))
        self.admin_label = ctk.CTkLabel(self, text="", text_color=tema.GRIS)
        self.admin_label.pack(anchor="w")
        self.admin_boton = ctk.CTkButton(self, text="", command=self._accion_admin)
        self.admin_boton.pack(anchor="w", pady=(6, 0))

        self.eliminar_boton = ctk.CTkButton(
            self, text="Eliminar este usuario", fg_color=tema.ROJO, hover_color=tema.ROJO_HOVER,
            command=self._eliminar,
        )
        self.eliminar_boton.pack(anchor="w", pady=(20, 10))

        self._cargar_usuarios()

    def _campo(self, etiqueta: str) -> ctk.CTkEntry:
        ctk.CTkLabel(self, text=etiqueta, anchor="w").pack(fill="x", pady=(8, 0))
        entry = ctk.CTkEntry(self)
        entry.pack(fill="x", pady=(2, 0))
        return entry

    def _cargar_usuarios(self, seleccionar: str | None = None):
        """La lista sale del caché, que ya viene precargado desde el login,
        así que normalmente no cuesta ningún viaje al backend. Igual va en
        segundo plano por si toca ir a buscarla."""

        def listo(usuarios):
            self._usuarios_por_nombre = {u["nombre"]: u for u in usuarios}
            self._hay_admin = any(u.get("es_admin") for u in usuarios)
            nombres = list(self._usuarios_por_nombre) or ["(sin usuarios)"]
            self.usuario_menu.configure(values=nombres)
            self.usuario_menu.set(seleccionar if seleccionar in nombres else nombres[0])
            self._cargar()

        en_segundo_plano(
            self,
            lambda: cache.usuarios(self.sesion["token"]),
            listo,
            lambda exc: self.error_label.configure(text=str(exc), text_color=tema.ROJO),
        )

    def seleccionar(self, nombre: str):
        """Deja abierto ese usuario. La usa la lista para saltar acá."""
        if nombre in self._usuarios_por_nombre:
            self.usuario_menu.set(nombre)
            self._cargar()
        else:
            self._cargar_usuarios(seleccionar=nombre)

    def _usuario_actual(self) -> dict | None:
        return self._usuarios_por_nombre.get(self.usuario_menu.get())

    def _set_entry(self, entry: ctk.CTkEntry, valor):
        entry.delete(0, "end")
        entry.insert(0, "" if valor is None else str(valor))

    def _cargar(self):
        usuario = self._usuario_actual()
        if not usuario:
            return

        self._set_entry(self.nombre_entry, usuario.get("nombre"))
        self.rol_menu.set(usuario.get("rol", "docente"))
        for clave, entry in self.campos_perfil.items():
            self._set_entry(entry, usuario.get(clave))

        tiene_firma = bool(usuario.get("firma_drive_id"))
        self.firma_label.configure(text="Ya tiene firma cargada" if tiene_firma else "Todavía no tiene firma")

        self._actualizar_controles_admin(usuario)

    def _es_yo_mismo(self, usuario: dict) -> bool:
        return usuario["id"] == self.sesion["id"]

    def _actualizar_controles_admin(self, usuario: dict):
        yo_soy_admin = bool(self.sesion.get("es_admin"))

        if usuario.get("es_admin"):
            self.admin_label.configure(text=f"{usuario['nombre']} es el administrador actual.")
        elif not self._hay_admin:
            self.admin_label.configure(text="Todavía no hay ningún administrador asignado.")
        else:
            self.admin_label.configure(text="")

        if usuario.get("es_admin"):
            self.admin_boton.pack_forget()
        elif not self._hay_admin and not yo_soy_admin:
            # Bootstrap: solo tiene sentido que la propia sesión (directivo/ambos) se autoproclame.
            if self._es_yo_mismo(usuario):
                self.admin_boton.configure(text="Convertirme en administrador")
                self.admin_boton.pack(anchor="w", pady=(6, 0))
            else:
                self.admin_boton.pack_forget()
        elif yo_soy_admin and not self._es_yo_mismo(usuario):
            self.admin_boton.configure(text=f"Transferirle el cargo a {usuario['nombre']}")
            self.admin_boton.pack(anchor="w", pady=(6, 0))
        else:
            self.admin_boton.pack_forget()

        puede_eliminar = (
            not self._es_yo_mismo(usuario)
            and (yo_soy_admin or usuario.get("rol") == "docente")
        )
        if puede_eliminar:
            self.eliminar_boton.pack(anchor="w", pady=(20, 10))
        else:
            self.eliminar_boton.pack_forget()

    def _accion_admin(self):
        usuario = self._usuario_actual()
        if not usuario:
            return

        try:
            if not self._hay_admin:
                api_client.convertirme_administrador(self.sesion["token"])
                self.sesion["es_admin"] = True
            else:
                api_client.transferir_administrador(self.sesion["token"], usuario["id"])
        except api_client.ApiError as exc:
            self.error_label.configure(text=str(exc), text_color=tema.ROJO)
            return

        self.error_label.configure(text="Listo ✓", text_color=tema.VERDE)
        self._cargar_usuarios()

    def _eliminar(self):
        usuario = self._usuario_actual()
        if not usuario:
            return

        if not messagebox.askyesno(
            "Eliminar usuario", f"¿Seguro que quiere eliminar a {usuario['nombre']} ({usuario['usuario']})?"
        ):
            return

        try:
            api_client.eliminar_usuario(self.sesion["token"], usuario["id"])
            cache.invalidar("usuarios")
        except api_client.ApiError as exc:
            self.error_label.configure(text=str(exc), text_color=tema.ROJO)
            return

        self.error_label.configure(text="Usuario eliminado.", text_color=tema.VERDE)
        self._cargar_usuarios()

    def _subir_firma(self):
        usuario = self._usuario_actual()
        if not usuario:
            return

        ruta = filedialog.askopenfilename(
            title="Elija la imagen de la firma", filetypes=[("Imágenes", "*.jpg *.jpeg *.png")]
        )
        if not ruta:
            return

        try:
            api_client.subir_firma(self.sesion["token"], usuario["id"], image_utils.foto_a_payload(ruta))
        except api_client.ApiError as exc:
            self.error_label.configure(text=str(exc), text_color=tema.ROJO)
            return

        self.firma_label.configure(text="Firma actualizada ✓", text_color=tema.VERDE)

    def _guardar(self):
        usuario = self._usuario_actual()
        if not usuario:
            self.error_label.configure(text="No hay usuario seleccionado.")
            return

        cambios = {
            "nombre": self.nombre_entry.get().strip(),
            "rol": self.rol_menu.get(),
            **leer_campos_perfil(self.campos_perfil),
        }

        try:
            resultado = api_client.editar_usuario(self.sesion["token"], usuario["id"], cambios)
            cache.invalidar("usuarios")
        except api_client.ApiError as exc:
            self.error_label.configure(text=str(exc), text_color=tema.ROJO)
            return

        self.error_label.configure(text=f"Guardado ({resultado['cambios']} campos actualizados) ✓", text_color=tema.VERDE)
        self._cargar_usuarios()
