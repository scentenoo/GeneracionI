"""Campos de perfil compartidos entre crear y editar usuario (curso,
tarifas, cuenta bancaria, etc. — los datos que necesita el informe
mensual). Evita repetir los mismos ~10 campos en dos pantallas."""

from __future__ import annotations

import customtkinter as ctk

CAMPOS_PERFIL = [
    ("curso", "Curso"),
    ("nucleo", "Núcleo"),
    ("cedula", "Cédula"),
    ("valor_hora_docente", "Valor hora docente"),
    ("valor_hora_directivo", "Valor hora directivo"),
    ("edad_desde", "Edad desde"),
    ("edad_hasta", "Edad hasta"),
    ("numero_cuenta", "Número de cuenta"),
    ("tipo_cuenta", "Tipo de cuenta"),
    ("entidad_bancaria", "Entidad bancaria"),
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
