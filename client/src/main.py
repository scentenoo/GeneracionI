"""Punto de entrada de la app de escritorio.

La ventana aparece de una y el chequeo de versión corre de fondo (spec
sección 6: la app se bloquea si la versión local no coincide con
`Config.version_actual`). Antes se consultaba el backend *antes* de dibujar
nada, así que la app parecía trabada 1 a 3 segundos al abrirla.

Mientras el chequeo corre, el botón de ingresar queda deshabilitado: no
tendría sentido dejar entrar a alguien y bloquearlo un segundo después.
"""

from __future__ import annotations

import customtkinter as ctk

import api_client
from config import APP_VERSION
from ui.app import App
from ui.tareas import en_segundo_plano


def _mensaje_de_bloqueo(version_backend: str) -> str | None:
    """El texto a mostrar si hay que bloquear el uso, o None si está OK."""
    if version_backend != APP_VERSION:
        return (
            f"Esta versión de la app ({APP_VERSION}) quedó desactualizada "
            f"(la vigente es {version_backend}). Pedile a Samir el instalador nuevo."
        )
    return None


def main():
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("green")

    app = App()

    def al_responder(version_backend):
        bloqueo = _mensaje_de_bloqueo(str(version_backend))
        if bloqueo:
            app.bloquear(bloqueo)
        else:
            app.version_verificada()

    def al_fallar(exc):
        app.bloquear(f"No se pudo verificar la versión de la app:\n{exc}")

    en_segundo_plano(app, api_client.version_actual, al_responder, al_fallar)

    app.mainloop()


if __name__ == "__main__":
    main()
