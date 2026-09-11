"""Panel lateral persistente (rediseño): logo, navegación por secciones y
perfil del usuario abajo, con cierre de sesión.

Antes no existía nada persistente entre pantallas — cada `_mostrar_X` de
`App` reemplazaba la ventana entera. Este widget vive parado durante toda
la sesión; `App` arma el área de contenido aparte y solo esa se reemplaza
en cada navegación (ver `App._armar_shell` / `_limpiar_contenido`).
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk
from PIL import Image

from config import TEMPLATES_DIR
from ui import tema

ANCHO = 220


class BarraLateral(ctk.CTkFrame):
    def __init__(
        self,
        master,
        sesion: dict,
        secciones: list[tuple[str, str, Callable[[], None]]],
        on_cerrar_sesion: Callable[[], None],
    ):
        super().__init__(master, width=ANCHO, corner_radius=0, fg_color=tema.VERDE_OSCURO)
        self.pack_propagate(False)

        self._botones: dict[str, ctk.CTkButton] = {}
        self._activo: str | None = None

        encabezado = ctk.CTkFrame(self, fg_color="transparent")
        encabezado.pack(fill="x", padx=16, pady=(20, 16))
        logo = self._cargar_logo()
        if logo is not None:
            ctk.CTkLabel(encabezado, image=logo, text="").pack(side="left")
            self._logo = logo  # referencia viva
        ctk.CTkLabel(
            encabezado, text="Generación-I", font=tema.fuente(15, "bold"),
            text_color=tema.TEXTO_CLARO,
        ).pack(side="left", padx=(8, 0))

        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.pack(fill="x", padx=10)
        for clave, texto, comando in secciones:
            boton = ctk.CTkButton(
                nav, text=texto, anchor="w", fg_color="transparent",
                hover_color=tema.VERDE_OSCURO_ACTIVO, text_color=tema.TEXTO_CLARO_APAGADO,
                font=tema.fuente(13), height=36, corner_radius=8, command=comando,
            )
            boton.pack(fill="x", pady=2)
            self._botones[clave] = boton

        # Frame vacío que se estira: empuja el bloque de perfil al fondo.
        ctk.CTkFrame(self, fg_color="transparent").pack(fill="both", expand=True)

        perfil = ctk.CTkFrame(self, fg_color="transparent")
        perfil.pack(fill="x", side="bottom", padx=16, pady=16)
        ctk.CTkLabel(
            perfil, text=sesion.get("nombre", ""), font=tema.fuente(13, "bold"),
            text_color=tema.TEXTO_CLARO, anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            perfil, text=sesion.get("rol", ""), font=tema.fuente(11),
            text_color=tema.TEXTO_CLARO_APAGADO, anchor="w",
        ).pack(fill="x")
        ctk.CTkButton(
            perfil, text="Cerrar sesión", anchor="w", fg_color="transparent",
            hover_color=tema.VERDE_OSCURO_ACTIVO, text_color=tema.TEXTO_CLARO_APAGADO,
            font=tema.fuente(12), height=28, command=on_cerrar_sesion,
        ).pack(fill="x", pady=(8, 0))

    def _cargar_logo(self):
        ruta = TEMPLATES_DIR / "assets" / "logo_generacion_i_32.png"
        try:
            img = Image.open(ruta)
        except Exception:  # noqa: BLE001 — sin logo la barra igual funciona
            return None
        return ctk.CTkImage(img, size=(28, 28))

    def marcar_activo(self, clave: str):
        """Resalta el ítem de la sección que se está mostrando ahora."""
        if self._activo is not None and self._activo in self._botones:
            self._botones[self._activo].configure(
                fg_color="transparent", text_color=tema.TEXTO_CLARO_APAGADO,
            )
        boton = self._botones.get(clave)
        if boton is not None:
            boton.configure(fg_color=tema.VERDE_OSCURO_ACTIVO, text_color=tema.TEXTO_CLARO)
        self._activo = clave
