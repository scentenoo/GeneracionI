
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

        if comparar_versiones(APP_VERSION, minima) < 0:
            mensaje = (
                f"Esta computadora tiene la versión {APP_VERSION} y ya es "
                f"obligatorio actualizar a la {vigente}."
            )
            mensaje += (
                "\n\nDescarga el instalador nuevo y vuelve a abrir la app."
                if link
                else "\n\nPedile a Samir el instalador nuevo."
            )
            app.bloquear(mensaje, titulo="Hay que actualizar la app", link=link or None)
            return

        if comparar_versiones(APP_VERSION, vigente) < 0:
            aviso = (
                f"Hay una versión nueva (la {vigente}).\n"
                "Podés seguir usando esta, pero conviene actualizar."
            )
            app.version_verificada(aviso=aviso, link=link or None)
            return


        app.version_verificada()

    def al_fallar(exc):
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
