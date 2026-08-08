"""Punto de entrada de la app de escritorio. Chequea versión antes que nada
(spec sección 6: la app se bloquea si la versión local no coincide con
`Config.version_actual` del backend) y recién después abre el login."""

from __future__ import annotations

import sys

import customtkinter as ctk

import api_client
from config import APP_VERSION


def _chequear_version() -> str | None:
    """Devuelve un mensaje de error si hay que bloquear el uso, o None si está OK."""
    try:
        version_backend = api_client.version_actual()
    except api_client.ApiError as exc:
        return f"No se pudo verificar la versión de la app: {exc}"

    if version_backend != APP_VERSION:
        return (
            f"Esta versión de la app ({APP_VERSION}) quedó desactualizada "
            f"(la vigente es {version_backend}). Pedile a Samir el instalador nuevo."
        )
    return None


def main():
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("green")

    error_version = _chequear_version()
    if error_version:
        # Ventana mínima solo para mostrar el bloqueo, sin dar acceso al resto de la app.
        root = ctk.CTk()
        root.title("Generación-I")
        root.geometry("420x180")
        ctk.CTkLabel(root, text=error_version, wraplength=380, justify="left").pack(
            padx=20, pady=40, fill="both", expand=True
        )
        root.mainloop()
        sys.exit(1)

    from ui.app import App  # import diferido: solo hace falta si pasó el chequeo de versión

    App().mainloop()


if __name__ == "__main__":
    main()
