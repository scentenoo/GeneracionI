"""Crear un usuario nuevo (docente/directivo/ambos) — rol directivo, spec
sección 3: "Samir asigna la contraseña inicial"."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

import api_client
from ui import tema
from ui.tareas import cache, en_segundo_plano
from ui.usuario_form_fields import (
    CAMPOS_PERFIL,
    construir_campos_perfil,
    leer_campos_perfil,
    limpiar_campos_perfil,
)
from ui.widgets import Acordeon, campo_label

ROLES = [("docente", "Docente"), ("directivo", "Directivo"), ("ambos", "Ambos")]


class UsuarioScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None] | None = None):
        # Sin `on_volver` va montada como pestaña de UsuariosScreen, que ya
        # tiene su propio Volver: dos seguidos confunden.
        super().__init__(master, label_text="" if on_volver is None else "Crear usuario", fg_color="transparent")
        self.sesion = sesion
        self.on_volver = on_volver

        tarjeta = ctk.CTkFrame(
            self, fg_color=tema.FONDO_TARJETA, corner_radius=16,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        tarjeta.pack(fill="x", pady=(0, 16))
        contenido = ctk.CTkFrame(tarjeta, fg_color="transparent")
        contenido.pack(fill="both", expand=True, padx=26, pady=24)

        ctk.CTkLabel(
            contenido, text="Datos de acceso", font=tema.fuente(16, "bold"), anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            contenido, text="Con esto el docente entra a la app.", font=tema.fuente(12),
            text_color=tema.TEXTO_MUTED, anchor="w",
        ).pack(fill="x", pady=(2, 0))
        ctk.CTkFrame(contenido, fg_color=tema.DIVISOR, height=1).pack(fill="x", pady=(16, 18))

        fila_1 = ctk.CTkFrame(contenido, fg_color="transparent")
        fila_1.pack(fill="x")
        self.nombre_entry = self._campo(fila_1, "Nombre completo", "Ej: Laura Cadavid", lado="left")
        self.usuario_entry = self._campo(fila_1, "Usuario (login)", "laura.cadavid", lado="left", padx=(16, 0))

        fila_2 = ctk.CTkFrame(contenido, fg_color="transparent")
        fila_2.pack(fill="x", pady=(16, 0))
        columna_password = ctk.CTkFrame(fila_2, fg_color="transparent")
        columna_password.pack(side="left", fill="x", expand=True)
        campo_label(columna_password, "Contraseña inicial").pack(fill="x")
        self.password_entry = ctk.CTkEntry(columna_password)
        self.password_entry.pack(fill="x", pady=(4, 0))

        columna_rol = ctk.CTkFrame(fila_2, fg_color="transparent")
        columna_rol.pack(side="left", fill="x", expand=True, padx=(16, 0))
        campo_label(columna_rol, "Rol").pack(fill="x")
        self.rol_selector = ctk.CTkSegmentedButton(
            columna_rol, values=[etiqueta for _clave, etiqueta in ROLES],
            selected_color=tema.VERDE, selected_hover_color=tema.VERDE_HOVER,
            unselected_color=tema.BLANCO, text_color=tema.TEXTO_OSCURO,
        )
        self.rol_selector.set("Docente")
        self.rol_selector.pack(fill="x", pady=(4, 0))

        tarjeta_perfil = Acordeon(
            self, "Datos para el informe mensual",
            encabezado_extra=lambda fila: self._badge_campos(fila),
        )
        tarjeta_perfil.pack(fill="x")
        ctk.CTkLabel(
            tarjeta_perfil.contenido, text="Opcionales — se pueden completar después.",
            font=tema.fuente(12), text_color=tema.TEXTO_MUTED, anchor="w",
        ).pack(fill="x", pady=(0, 10))
        self.campos_perfil = construir_campos_perfil(tarjeta_perfil.contenido)

        ctk.CTkLabel(
            self, text="Los cursos se asignan aparte, en la pantalla de Cursos.",
            text_color=tema.TEXTO_MUTED, font=tema.fuente(11), anchor="w",
        ).pack(fill="x", pady=(12, 0))

        self.error_label = ctk.CTkLabel(self, text="", text_color=tema.ROJO, wraplength=700, justify="left")
        self.error_label.pack(fill="x", pady=(14, 4))

        botones = ctk.CTkFrame(self, fg_color="transparent")
        botones.pack(anchor="e", pady=(4, 10))
        ctk.CTkButton(
            botones, text="Cancelar", fg_color="transparent", border_width=1,
            text_color=tema.TEXTO_OSCURO, command=self._cancelar,
        ).pack(side="left", padx=(0, 8))
        self.crear_boton = ctk.CTkButton(
            botones, text="Crear usuario", fg_color=tema.VERDE_OSCURO,
            hover_color=tema.VERDE_OSCURO_ACTIVO, command=self._crear,
        )
        self.crear_boton.pack(side="left")

    def _badge_campos(self, fila: ctk.CTkFrame):
        ctk.CTkLabel(
            fila, text=f"  {len(CAMPOS_PERFIL)} campos  ", font=tema.fuente(12, "bold"),
            text_color=tema.TEXTO_MUTED, fg_color=tema.FONDO_CONTENIDO, corner_radius=999,
        ).pack(side="right", padx=(0, 8))

    def _campo(self, padre, etiqueta: str, placeholder: str, lado: str, padx=(0, 0)) -> ctk.CTkEntry:
        columna = ctk.CTkFrame(padre, fg_color="transparent")
        columna.pack(side=lado, fill="x", expand=True, padx=padx)
        campo_label(columna, etiqueta).pack(fill="x")
        entry = ctk.CTkEntry(columna, placeholder_text=placeholder)
        entry.pack(fill="x", pady=(4, 0))
        return entry

    def _rol_clave(self) -> str:
        etiqueta_elegida = self.rol_selector.get()
        for clave, etiqueta in ROLES:
            if etiqueta == etiqueta_elegida:
                return clave
        return "docente"

    def _cancelar(self):
        if self.on_volver is not None:
            self.on_volver()
        else:
            self.nombre_entry.delete(0, "end")
            self.usuario_entry.delete(0, "end")
            self.password_entry.delete(0, "end")
            self.rol_selector.set("Docente")
            limpiar_campos_perfil(self.campos_perfil)
            self.error_label.configure(text="")

    def _crear(self):
        if not self.nombre_entry.get().strip() or not self.usuario_entry.get().strip() or not self.password_entry.get():
            self.error_label.configure(text="Nombre, usuario y contraseña son obligatorios.", text_color=tema.ROJO)
            return

        datos = {
            "nombre": self.nombre_entry.get().strip(),
            "usuario": self.usuario_entry.get().strip(),
            "password_inicial": self.password_entry.get(),
            "rol": self._rol_clave(),
            **leer_campos_perfil(self.campos_perfil),
        }

        # En segundo plano para no congelar la ventana en los equipos lentos.
        self.crear_boton.configure(state="disabled")
        self.error_label.configure(text="Creando...", text_color=tema.TEXTO_MUTED)

        def listo(resultado):
            self.crear_boton.configure(state="normal")
            cache.invalidar("usuarios")
            nombre_creado = datos["nombre"]
            self.nombre_entry.delete(0, "end")
            self.usuario_entry.delete(0, "end")
            self.password_entry.delete(0, "end")
            limpiar_campos_perfil(self.campos_perfil)
            self.error_label.configure(
                text=f"{nombre_creado} creado (id {resultado['id']}) ✓", text_color=tema.VERDE
            )

        def fallo(exc):
            self.crear_boton.configure(state="normal")
            self.error_label.configure(text=str(exc), text_color=tema.ROJO)

        en_segundo_plano(
            self,
            lambda: api_client.crear_usuario(self.sesion["token"], datos),
            listo,
            fallo,
        )
