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
from config import APP_VERSION, comparar_versiones
from ui.app import App
from ui.tareas import en_segundo_plano


def main():
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("green")

    app = App()

    def verificar():
        en_segundo_plano(app, api_client.version_actual, al_responder, al_fallar)

    def al_responder(info):
        vigente = str(info.get("version", "")).strip()
        minima = str(info.get("version_minima", "0.0.0")).strip() or "0.0.0"
        link = str(info.get("link_instalador", "")).strip()

        # Tres casos según dónde cae esta copia respecto de la mínima
        # obligatoria y la última publicada.
        if comparar_versiones(APP_VERSION, minima) < 0:
            # Por debajo de la mínima: bloqueo, no se puede usar.
            mensaje = (
                f"Esta computadora tiene la versión {APP_VERSION} y ya es "
                f"obligatorio actualizar a la {vigente}."
            )
            mensaje += (
                "\n\nDescargá el instalador nuevo y volvé a abrir la app."
                if link
                else "\n\nPedile a Samir el instalador nuevo."
            )
            app.bloquear(mensaje, titulo="Hay que actualizar la app", link=link or None)
            return

        if comparar_versiones(APP_VERSION, vigente) < 0:
            # Entre la mínima y la vigente: se puede usar, pero se avisa.
            aviso = (
                f"Hay una versión nueva (la {vigente}).\n"
                "Podés seguir usando esta, pero conviene actualizar."
            )
            app.version_verificada(aviso=aviso, link=link or None)
            return

        # Al día (o incluso más nueva que la Sheet, si es el equipo de Samir).
        app.version_verificada()

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
