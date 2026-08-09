"""Crear un usuario nuevo (docente/directivo/ambos) — rol directivo, spec
sección 3: "Samir asigna la contraseña inicial"."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

import api_client
from ui.tareas import cache
from ui.usuario_form_fields import (
    construir_campos_perfil,
    leer_campos_perfil,
    limpiar_campos_perfil,
)

ROLES = ["docente", "directivo", "ambos"]


class UsuarioScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None] | None = None):
        # Sin `on_volver` va montada como pestaña de UsuariosScreen, que ya
        # tiene su propio Volver: dos seguidos confunden.
        super().__init__(master, label_text="" if on_volver is None else "Crear usuario")
        self.sesion = sesion

        if on_volver is not None:
            ctk.CTkButton(self, text="← Volver", width=90, command=on_volver).pack(anchor="w", pady=(0, 10))

        self.nombre_entry = self._campo("Nombre completo")
        self.usuario_entry = self._campo("Usuario (login)")
        self.password_entry = self._campo("Contraseña inicial")

        ctk.CTkLabel(self, text="Rol").pack(anchor="w", pady=(10, 0))
        self.rol_menu = ctk.CTkOptionMenu(self, values=ROLES)
        self.rol_menu.pack(anchor="w", pady=(2, 0))

        ctk.CTkLabel(self, text="Datos para el informe mensual (opcionales, se pueden completar después)",
                     text_color="gray").pack(anchor="w", pady=(16, 4))
        self.campos_perfil = construir_campos_perfil(self)

        ctk.CTkLabel(
            self,
            text="Los cursos se asignan aparte, en la pantalla de Cursos.",
            text_color="gray",
            font=ctk.CTkFont(size=11),
        ).pack(anchor="w", pady=(10, 0))

        self.error_label = ctk.CTkLabel(self, text="", text_color="#c0392b", wraplength=450, justify="left")
        self.error_label.pack(fill="x", pady=(16, 4))
        self.crear_boton = ctk.CTkButton(self, text="Crear usuario", command=self._crear)
        self.crear_boton.pack(pady=10)

    def _campo(self, etiqueta: str) -> ctk.CTkEntry:
        ctk.CTkLabel(self, text=etiqueta, anchor="w").pack(fill="x", pady=(8, 0))
        entry = ctk.CTkEntry(self)
        entry.pack(fill="x", pady=(2, 0))
        return entry

    def _crear(self):
        if not self.nombre_entry.get().strip() or not self.usuario_entry.get().strip() or not self.password_entry.get():
            self.error_label.configure(text="Nombre, usuario y contraseña son obligatorios.")
            return

        datos = {
            "nombre": self.nombre_entry.get().strip(),
            "usuario": self.usuario_entry.get().strip(),
            "password_inicial": self.password_entry.get(),
            "rol": self.rol_menu.get(),
            **leer_campos_perfil(self.campos_perfil),
        }

        self.crear_boton.configure(state="disabled")
        self.error_label.configure(text="Creando...", text_color="gray")
        self.update_idletasks()
        try:
            resultado = api_client.crear_usuario(self.sesion["token"], datos)
            cache.invalidar("usuarios")
        except api_client.ApiError as exc:
            self.error_label.configure(text=str(exc), text_color="#c0392b")
            return
        finally:
            self.crear_boton.configure(state="normal")

        nombre_creado = datos["nombre"]
        self.nombre_entry.delete(0, "end")
        self.usuario_entry.delete(0, "end")
        self.password_entry.delete(0, "end")
        limpiar_campos_perfil(self.campos_perfil)

        self.error_label.configure(
            text=f"{nombre_creado} creado (id {resultado['id']}) ✓", text_color="#2fa84f"
        )
