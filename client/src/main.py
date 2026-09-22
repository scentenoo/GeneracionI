
from __future__ import annotations

import datetime

import customtkinter as ctk

import api_client
from config import (
    APP_VERSION,
    FECHA_EXPIRACION_LICENCIA,
    MENSAJE_LICENCIA_EXPIRADA,
    TEMA_JSON,
    comparar_versiones,
)
from services import ortografia
from ui import ctk_parches
from ui.app import App
from ui.tareas import en_segundo_plano


def main():
    ctk_parches.aplicar()
    ctk.set_appearance_mode("light")
    # Tema propio (ver ui/tema.py y client/assets/tema_generacion_i.json):
    # sin esto, cualquier widget que no fije sus colores a mano cae en el
    # azul/verde-menta genérico de customtkinter y con esquinas casi rectas
    # (radius 6) — el motivo real por el que la app entera no se parecía al
    # mockup, más que cualquier pantalla puntual. "light" fijo y no "system"
    # porque el mockup es un diseño de un solo modo: con "system" un equipo
    # en modo oscuro de Windows mezclaría este tema claro con la mitad
    # "dark" del tema, que no está diseñada aparte.
    ctk.set_default_color_theme(str(TEMA_JSON))

    # El diccionario del corrector ortográfico tarda un momento en cargar
    # (~60 mil palabras); arrancarlo ya, mientras se ve el login, hace que
    # esté listo para cuando el docente llegue al primer campo largo.
    ortografia.cargar_en_segundo_plano()

    app = App()

    def verificar():
        # Atajo de vigencia de licencia: si el reloj de esta computadora ya
        # pasó la fecha límite, la respuesta del backend ya se sabe y no
        # vale la pena el viaje. La fuente de verdad sigue siendo el backend
        # (Licencia.js, ver ui/tareas.py) — si alguien atrasa el reloj local
        # para saltarse esto, el primer viaje real igual vuelve bloqueado
        # desde ahí, con el mismo aviso.
        if datetime.datetime.now() > FECHA_EXPIRACION_LICENCIA:
            app.bloquear(MENSAJE_LICENCIA_EXPIRADA, titulo="Servicio no disponible")
            return

        # Sin overlay: el telón (ver App._mostrar_telon) ya cubre esta
        # espera. Mostrar el overlay genérico encima solo duplicaba trabajo
        # de construcción justo al abrir, sin agregar nada que el telón no
        # dijera ya.
        en_segundo_plano(
            app, api_client.version_actual, al_responder, al_fallar, mostrar_overlay=False
        )

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
                "\n\nDescargue el instalador nuevo y vuelva a abrir la app."
                if link
                else "\n\nPídale a Samir el instalador nuevo."
            )
            app.bloquear(mensaje, titulo="Hay que actualizar la app", link=link or None)
            return

        if comparar_versiones(APP_VERSION, vigente) < 0:
            aviso = (
                f"Hay una versión nueva (la {vigente}).\n"
                "Puede seguir usando esta, pero conviene actualizar."
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
