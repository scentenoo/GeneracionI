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


def main():
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("green")

    app = App()

    def verificar():
        en_segundo_plano(app, api_client.version_actual, al_responder, al_fallar)

    def al_responder(info):
        vigente = str(info.get("version", ""))
        link = str(info.get("link_instalador", "")).strip()

        if vigente == APP_VERSION:
            app.version_verificada()
            return

        mensaje = (
            f"Esta computadora tiene la versión {APP_VERSION} y la vigente "
            f"es la {vigente}."
        )
        mensaje += (
            "\n\nDescargá el instalador nuevo y volvé a abrir la app."
            if link
            else "\n\nPedile a Samir el instalador nuevo."
        )
        app.bloquear(mensaje, titulo="La app quedó desactualizada", link=link or None)

    def al_fallar(exc):
        # Sin conexión se puede reintentar sin cerrar la app; cualquier otra
        # cosa es algo que hay que ir a resolver a otro lado.
        sin_conexion = isinstance(exc, api_client.SinConexion)
        app.bloquear(
            str(exc),
            titulo="Sin conexión" if sin_conexion else "No se pudo abrir la app",
            al_reintentar=verificar if sin_conexion else None,
        )

    verificar()
    app.mainloop()


if __name__ == "__main__":
    main()
