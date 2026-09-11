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

import api_client
from config import APP_VERSION
from ui.tareas import en_segundo_plano


class VersionScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None]):
        super().__init__(master, label_text="Versión de la app")
        self.sesion = sesion

        ctk.CTkButton(self, text="← Volver", width=90, command=on_volver).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(
            self, text=f"Esta computadora tiene la versión {APP_VERSION}", text_color="gray", anchor="w"
        ).pack(fill="x")
        self.vigente_label = ctk.CTkLabel(self, text="Consultando la vigente...", anchor="w")
        self.vigente_label.pack(fill="x", pady=(2, 16))

        ctk.CTkLabel(self, text="Versión vigente", anchor="w").pack(fill="x")
        self.version_entry = ctk.CTkEntry(self, placeholder_text="Ej: 1.1.0")
        self.version_entry.pack(fill="x", pady=(2, 8))

        ctk.CTkLabel(self, text="Link para descargar el instalador", anchor="w").pack(fill="x")
        self.link_entry = ctk.CTkEntry(self, placeholder_text="https://drive.google.com/...")
        self.link_entry.pack(fill="x", pady=(2, 4))
        ctk.CTkLabel(
            self,
            text="Suba el .exe a Drive y pegue acá el link para compartir.",
            text_color="gray",
            font=ctk.CTkFont(size=11),
            anchor="w",
        ).pack(fill="x")

        self.obligatoria_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            self,
            text="Esta versión es obligatoria",
            variable=self.obligatoria_var,
            command=self._actualizar_aviso,
        ).pack(anchor="w", pady=(16, 2))

        self.aviso = ctk.CTkLabel(
            self, text="", text_color="#8A6114", justify="left", anchor="w", wraplength=450
        )
        self.aviso.pack(fill="x", pady=(0, 4))
        self._actualizar_aviso()

        self.error_label = ctk.CTkLabel(self, text="", text_color="#c0392b", wraplength=450, justify="left")
        self.error_label.pack(fill="x", pady=(4, 4))

        self.publicar_boton = ctk.CTkButton(self, text="Publicar esta versión", command=self._publicar)
        self.publicar_boton.pack(pady=10)

        self._cargar()

    def _actualizar_aviso(self):
        if self.obligatoria_var.get():
            self.aviso.configure(
                text="Obligatoria: quien tenga una versión anterior queda bloqueado\n"
                     "hasta que instale esta. Úsela solo para un arreglo que no puede esperar."
            )
        else:
            self.aviso.configure(
                text="Opcional: quien tenga una versión anterior ve un aviso con el link,\n"
                     "pero puede seguir usando la app. Nadie queda afuera."
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
                text_color="#2fa84f" if al_dia else "#c0392b",
            )
            self.version_entry.delete(0, "end")
            self.version_entry.insert(0, vigente)
            self.link_entry.delete(0, "end")
            self.link_entry.insert(0, link)

        en_segundo_plano(
            self,
            api_client.version_actual,
            listo,
            lambda exc: self.vigente_label.configure(text=str(exc), text_color="#c0392b"),
        )

    def _publicar(self):
        version = self.version_entry.get().strip()
        if not version:
            self.error_label.configure(text="Escriba el número de versión.", text_color="#c0392b")
            return

        self.publicar_boton.configure(state="disabled", text="Publicando...")
        self.error_label.configure(text="Publicando...", text_color="gray")

        obligatoria = bool(self.obligatoria_var.get())

        def listo(_r):
            self.publicar_boton.configure(state="normal", text="Publicar esta versión")
            self._cargar()
            tipo = "obligatoria" if obligatoria else "opcional"
            self.error_label.configure(text=f"Versión {version} publicada ({tipo}) ✓", text_color="#2fa84f")

        def fallo(exc):
            self.publicar_boton.configure(state="normal", text="Publicar esta versión")
            self.error_label.configure(text=str(exc), text_color="#c0392b")

        en_segundo_plano(
            self,
            lambda: api_client.fijar_version(
                self.sesion["token"], version, self.link_entry.get().strip(), obligatoria
            ),
            listo,
            fallo,
        )
