"""Publicar una versión de la app. Solo el administrador.

Dejar a los 18 computadores afuera por error no es algo que deba poder
hacer cualquiera, así que va detrás del administrador único y no del rol
directivo.

Publicar una actualización es: subir el .exe a Drive, pegar acá el link y
el número de versión nuevo. Quien abra la app con una versión distinta
queda bloqueado y ve un botón para descargarlo.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk
from PIL import Image

import api_client
from config import APP_VERSION, TEMPLATES_DIR
from ui import tema
from ui.tareas import en_segundo_plano
from ui.widgets import campo_label

ANCHO = 680


class VersionScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None]):
        super().__init__(master, label_text="", fg_color="transparent")
        self.sesion = sesion

        ctk.CTkButton(
            self, text="← Volver", width=90, fg_color="transparent", border_width=1,
            text_color=tema.TEXTO_OSCURO, hover_color=tema.FONDO_TARJETA, command=on_volver,
        ).pack(anchor="w", pady=(0, 16))

        envoltorio = ctk.CTkFrame(self, fg_color="transparent", width=ANCHO)
        envoltorio.pack()

        cabecera = ctk.CTkFrame(envoltorio, fg_color=tema.VERDE_OSCURO, corner_radius=20, width=ANCHO)
        cabecera.pack(fill="x")
        contenido_cabecera = ctk.CTkFrame(cabecera, fg_color="transparent")
        contenido_cabecera.pack(padx=30, pady=26)
        caja_logo = ctk.CTkFrame(contenido_cabecera, width=72, height=72, corner_radius=14, fg_color=tema.BLANCO)
        caja_logo.pack(side="left")
        caja_logo.pack_propagate(False)
        logo = self._cargar_logo()
        if logo is not None:
            ctk.CTkLabel(caja_logo, image=logo, text="").place(relx=0.5, rely=0.5, anchor="center")
            self._logo = logo  # referencia viva
        textos_cabecera = ctk.CTkFrame(contenido_cabecera, fg_color="transparent")
        textos_cabecera.pack(side="left", padx=(20, 0))
        ctk.CTkLabel(
            textos_cabecera, text="Publicar una versión", font=tema.fuente(22, "bold"),
            text_color=tema.TEXTO_CLARO, anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            textos_cabecera, text="Generación-I · Planeaciones", font=tema.fuente(12),
            text_color=tema.TEXTO_CLARO_APAGADO, anchor="w",
        ).pack(fill="x", pady=(4, 0))

        tarjeta = ctk.CTkFrame(
            envoltorio, fg_color=tema.FONDO_TARJETA, corner_radius=16,
            border_width=1, border_color=tema.BORDE_TARJETA, width=ANCHO,
        )
        tarjeta.pack(fill="x", pady=(14, 0))
        contenido = ctk.CTkFrame(tarjeta, fg_color="transparent")
        contenido.pack(fill="x", padx=26, pady=24)

        ctk.CTkLabel(
            contenido, text=f"Esta computadora tiene la versión {APP_VERSION}",
            font=tema.fuente(12), text_color=tema.TEXTO_MUTED, anchor="w",
        ).pack(fill="x")
        self.vigente_label = ctk.CTkLabel(
            contenido, text="Consultando la vigente...", font=tema.fuente(14, "bold"), anchor="w",
        )
        self.vigente_label.pack(fill="x", pady=(3, 0))
        ctk.CTkFrame(contenido, fg_color=tema.DIVISOR, height=1).pack(fill="x", pady=(18, 20))

        fila = ctk.CTkFrame(contenido, fg_color="transparent")
        fila.pack(fill="x")
        # Sin pack_propagate(False) ni ancho fijo en el frame: ver la nota
        # equivalente en horas_gestion_screen.py — el ancho angosto sale de
        # limitar el CTkEntry, no el frame que lo contiene.
        col_version = ctk.CTkFrame(fila, fg_color="transparent")
        col_version.pack(side="left", padx=(0, 18))
        col_link = ctk.CTkFrame(fila, fg_color="transparent")
        col_link.pack(side="left", fill="x", expand=True)

        campo_label(col_version, "Versión vigente").pack(fill="x")
        self.version_entry = ctk.CTkEntry(col_version, placeholder_text="Ej: 1.1.0", width=140)
        self.version_entry.pack(fill="x", pady=(4, 0))

        campo_label(col_link, "Link para descargar el instalador").pack(fill="x")
        self.link_entry = ctk.CTkEntry(col_link, placeholder_text="https://drive.google.com/...")
        self.link_entry.pack(fill="x", pady=(4, 0))

        ctk.CTkLabel(
            contenido, text="Suba el .exe a Drive y pegue acá el link para compartir.",
            text_color=tema.TEXTO_MUTED, font=tema.fuente(11), anchor="w",
        ).pack(fill="x", pady=(6, 0))

        fila_obligatoria = ctk.CTkFrame(contenido, fg_color="transparent")
        fila_obligatoria.pack(fill="x", pady=(20, 0))
        self.obligatoria_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            fila_obligatoria, text="Esta versión es obligatoria", variable=self.obligatoria_var,
            font=tema.fuente(13), command=self._actualizar_aviso,
        ).pack(anchor="w")

        self.aviso = ctk.CTkLabel(
            contenido, text="", text_color=tema.AMBAR, fg_color=tema.AMBAR_CHIP_BG, corner_radius=10,
            justify="left", anchor="w", wraplength=ANCHO - 80, font=tema.fuente(11),
        )
        self.aviso.pack(fill="x", pady=(12, 0))
        self._actualizar_aviso()

        self.error_label = ctk.CTkLabel(
            contenido, text="", text_color=tema.ROJO, wraplength=ANCHO - 60, justify="left",
        )
        self.error_label.pack(fill="x", pady=(12, 0))

        self.publicar_boton = ctk.CTkButton(
            contenido, text="Publicar esta versión", fg_color=tema.VERDE_OSCURO,
            hover_color=tema.VERDE_OSCURO_ACTIVO, height=42, command=self._publicar,
        )
        self.publicar_boton.pack(fill="x", pady=(20, 0))

        ctk.CTkLabel(
            envoltorio, text="Publicar bloquea o avisa a los 18 equipos de la sede: "
                              "solo el administrador ve esta pantalla.",
            text_color=tema.TEXTO_MUTED, font=tema.fuente(11), justify="center", wraplength=ANCHO,
        ).pack(pady=(16, 0))

        self._cargar()

    def _cargar_logo(self):
        ruta = TEMPLATES_DIR / "assets" / "logo_generacion_i_64.png"
        try:
            img = Image.open(ruta)
        except Exception:  # noqa: BLE001 — sin logo la pantalla igual funciona
            return None
        return ctk.CTkImage(img, size=(52, 52))

    def _actualizar_aviso(self):
        if self.obligatoria_var.get():
            self.aviso.configure(
                text="  Obligatoria: quien tenga una versión anterior queda bloqueado hasta que "
                     "instale esta. Úsela solo para un arreglo que no puede esperar.  "
            )
        else:
            self.aviso.configure(
                text="  Opcional: quien tenga una versión anterior ve un aviso con el link, pero "
                     "puede seguir usando la app. Nadie queda afuera.  "
            )

    def _cargar(self):
        def listo(info):
            vigente = str(info.get("version", ""))
            minima = str(info.get("version_minima", "0.0.0"))
            link = str(info.get("link_instalador", ""))
            al_dia = vigente == APP_VERSION
            self.vigente_label.configure(
                text=f"La vigente es la {vigente}  ·  mínima obligatoria: {minima}"
                     + ("  (coincide)" if al_dia else "  (no coincide)"),
                text_color=tema.VERDE_CHIP_TEXTO if al_dia else tema.ROJO,
            )
            self.version_entry.delete(0, "end")
            self.version_entry.insert(0, vigente)
            self.link_entry.delete(0, "end")
            self.link_entry.insert(0, link)

        en_segundo_plano(
            self,
            api_client.version_actual,
            listo,
            lambda exc: self.vigente_label.configure(text=str(exc), text_color=tema.ROJO),
        )

    def _publicar(self):
        version = self.version_entry.get().strip()
        if not version:
            self.error_label.configure(text="Escriba el número de versión.", text_color=tema.ROJO)
            return

        self.publicar_boton.configure(state="disabled", text="Publicando...")
        self.error_label.configure(text="Publicando...", text_color=tema.TEXTO_MUTED)

        obligatoria = bool(self.obligatoria_var.get())

        def listo(_r):
            self.publicar_boton.configure(state="normal", text="Publicar esta versión")
            self._cargar()
            tipo = "obligatoria" if obligatoria else "opcional"
            self.error_label.configure(text=f"Versión {version} publicada ({tipo}) ✓", text_color=tema.VERDE)

        def fallo(exc):
            self.publicar_boton.configure(state="normal", text="Publicar esta versión")
            self.error_label.configure(text=str(exc), text_color=tema.ROJO)

        en_segundo_plano(
            self,
            lambda: api_client.fijar_version(
                self.sesion["token"], version, self.link_entry.get().strip(), obligatoria
            ),
            listo,
            fallo,
        )
