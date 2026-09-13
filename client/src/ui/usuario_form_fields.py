"""Campos de perfil compartidos entre crear y editar usuario (curso,
tarifas, cuenta bancaria, etc. — los datos que necesita el informe
mensual). Evita repetir los mismos ~10 campos en dos pantallas."""

from __future__ import annotations

import customtkinter as ctk

# Curso, núcleo y edades ya no están acá: se cargan por curso, en la
# pantalla de Cursos, porque un docente puede tener varios y cada uno con
# su propio núcleo y rango de edades.
CAMPOS_PERFIL = [
    ("cedula", "Cédula"),
    ("telefono", "Teléfono"),
    ("valor_hora_docente", "Valor hora docente"),
    ("valor_hora_directivo", "Valor hora directivo"),
    ("numero_cuenta", "Número de cuenta"),
    ("tipo_cuenta", "Tipo de cuenta"),
    ("entidad_bancaria", "Entidad bancaria"),
    # Título/profesión: lo pide el certificado de pago mensual (columna
    # FORMACIÓN), no se usa en ningún otro documento.
    ("formacion", "Formación (profesión/título)"),
]


def construir_campos_perfil(parent: ctk.CTkBaseClass) -> dict[str, ctk.CTkEntry]:
    """Crea (y empaqueta con .pack) un CTkEntry por cada campo de perfil,
    devueltos en un dict {clave: entry}."""
    entradas: dict[str, ctk.CTkEntry] = {}
    for clave, etiqueta in CAMPOS_PERFIL:
        ctk.CTkLabel(parent, text=etiqueta, anchor="w").pack(fill="x", pady=(8, 0))
        entry = ctk.CTkEntry(parent)
        entry.pack(fill="x", pady=(2, 0))
        entradas[clave] = entry
    return entradas


def leer_campos_perfil(entradas: dict[str, ctk.CTkEntry]) -> dict[str, str]:
    return {clave: entry.get().strip() for clave, entry in entradas.items()}


def limpiar_campos_perfil(entradas: dict[str, ctk.CTkEntry]):
    for entry in entradas.values():
        entry.delete(0, "end")
