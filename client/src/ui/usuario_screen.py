"""Crear un usuario nuevo (docente/directivo/ambos) — rol directivo, spec
sección 3: "Samir asigna la contraseña inicial"."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

import api_client

ROLES = ["docente", "directivo", "ambos"]


class UsuarioScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None]):
        super().__init__(master, label_text="Crear usuario")
        self.sesion = sesion

        ctk.CTkButton(self, text="← Volver", width=90, command=on_volver).pack(anchor="w", pady=(0, 10))

        self.nombre_entry = self._campo("Nombre completo")
        self.usuario_entry = self._campo("Usuario (login)")
        self.password_entry = self._campo("Contraseña inicial")

        ctk.CTkLabel(self, text="Rol").pack(anchor="w", pady=(10, 0))
        self.rol_menu = ctk.CTkOptionMenu(self, values=ROLES)
        self.rol_menu.pack(anchor="w", pady=(2, 0))

        ctk.CTkLabel(self, text="Datos para el informe mensual (opcionales, se pueden completar después)",
                     text_color="gray").pack(anchor="w", pady=(16, 4))

        self.curso_entry = self._campo("Curso")
        self.nucleo_entry = self._campo("Núcleo")
        self.cedula_entry = self._campo("Cédula")
        self.valor_hora_docente_entry = self._campo("Valor hora docente")
        self.valor_hora_directivo_entry = self._campo("Valor hora directivo")
        self.edad_desde_entry = self._campo("Edad desde")
        self.edad_hasta_entry = self._campo("Edad hasta")
        self.numero_cuenta_entry = self._campo("Número de cuenta")
        self.tipo_cuenta_entry = self._campo("Tipo de cuenta")
        self.entidad_bancaria_entry = self._campo("Entidad bancaria")

        self.error_label = ctk.CTkLabel(self, text="", text_color="#c0392b", wraplength=450, justify="left")
        self.error_label.pack(fill="x", pady=(16, 4))
        ctk.CTkButton(self, text="Crear usuario", command=self._crear).pack(pady=10)

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
            "curso": self.curso_entry.get().strip(),
            "nucleo": self.nucleo_entry.get().strip(),
            "cedula": self.cedula_entry.get().strip(),
            "valor_hora_docente": self.valor_hora_docente_entry.get().strip(),
            "valor_hora_directivo": self.valor_hora_directivo_entry.get().strip(),
            "edad_desde": self.edad_desde_entry.get().strip(),
            "edad_hasta": self.edad_hasta_entry.get().strip(),
            "numero_cuenta": self.numero_cuenta_entry.get().strip(),
            "tipo_cuenta": self.tipo_cuenta_entry.get().strip(),
            "entidad_bancaria": self.entidad_bancaria_entry.get().strip(),
        }

        try:
            resultado = api_client.crear_usuario(self.sesion["token"], datos)
        except api_client.ApiError as exc:
            self.error_label.configure(text=str(exc), text_color="#c0392b")
            return

        self.error_label.configure(text=f"Usuario creado (id {resultado['id']}) ✓", text_color="#2fa84f")
        self.usuario_entry.delete(0, "end")
        self.password_entry.delete(0, "end")
