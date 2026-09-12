"""Panel lateral persistente (rediseño completo): bloque de cabecera
dorado con el logo, navegación por secciones con acento en el ítem
activo, y una tarjeta de perfil al fondo con avatar, rol y cierre de
sesión.

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
from ui.widgets import avatar_iniciales

ANCHO = 270
# Colores propios del bloque de perfil (fondo verde casi negro, más oscuro
# que VERDE_OSCURO): son específicos de esa tarjeta sobre el panel oscuro,
# no acentos de marca de uso general, así que quedan acá y no en tema.py.
_FONDO_PERFIL = "#0B3125"
_BORDE_PERFIL = "#1C5340"


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
        self._acentos: dict[str, ctk.CTkFrame] = {}
        self._activo: str | None = None

        # --- Cabecera dorada con el logo ------------------------------
        cabecera = ctk.CTkFrame(self, fg_color=tema.DORADO_ACENTO, corner_radius=0)
        cabecera.pack(fill="x")
        contenido_cabecera = ctk.CTkFrame(cabecera, fg_color="transparent")
        contenido_cabecera.pack(fill="x", padx=20, pady=16)
        caja_logo = ctk.CTkFrame(
            contenido_cabecera, width=42, height=42, corner_radius=9, fg_color=tema.BLANCO,
        )
        caja_logo.pack(side="left")
        caja_logo.pack_propagate(False)
        logo = self._cargar_logo()
        if logo is not None:
            ctk.CTkLabel(caja_logo, image=logo, text="").place(relx=0.5, rely=0.5, anchor="center")
            self._logo = logo  # referencia viva
        textos_cabecera = ctk.CTkFrame(contenido_cabecera, fg_color="transparent")
        textos_cabecera.pack(side="left", padx=(12, 0))
        ctk.CTkLabel(
            textos_cabecera, text="Generación-I", font=tema.fuente(17, "bold"),
            text_color=tema.VERDE_OSCURO, anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            textos_cabecera, text="Plataforma educativa", font=tema.fuente(11),
            text_color=tema.VERDE_OSCURO, anchor="w",
        ).pack(fill="x")

        # --- Menú principal --------------------------------------------
        etiqueta_menu = ctk.CTkFrame(self, fg_color="transparent")
        etiqueta_menu.pack(fill="x", padx=20, pady=(18, 6))
        ctk.CTkLabel(
            etiqueta_menu, text="MENÚ PRINCIPAL", font=tema.fuente(11, "bold"),
            text_color=tema.DORADO_ACENTO, anchor="w",
        ).pack(fill="x")
        ctk.CTkFrame(etiqueta_menu, fg_color=tema.DORADO_ACENTO, height=2, width=48).pack(
            anchor="w", pady=(4, 0)
        )

        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.pack(fill="x", padx=12)
        for clave, texto, comando in secciones:
            fila = ctk.CTkFrame(nav, fg_color="transparent")
            fila.pack(fill="x", pady=1)
            # Barra de acento a la izquierda: transparente por defecto,
            # dorada cuando `marcar_activo` señala esta sección — como el
            # borde izquierdo del ítem activo en el mockup (CTkButton no
            # soporta un borde por un solo lado). `height` explícito: sin
            # esto un CTkFrame vacío toma una altura por defecto bastante
            # mayor a la del botón (probado a ojo: la barra quedaba
            # mucho más alta que su fila, no alineada con el ítem).
            acento = ctk.CTkFrame(fila, width=3, height=38, fg_color="transparent", corner_radius=0)
            acento.pack(side="left")
            acento.pack_propagate(False)
            boton = ctk.CTkButton(
                fila, text=texto, anchor="w", fg_color="transparent",
                hover_color=tema.VERDE_OSCURO_ACTIVO, text_color=tema.TEXTO_CLARO_APAGADO,
                font=tema.fuente(13), height=38, corner_radius=9, command=comando,
                border_width=0, border_spacing=14,
            )
            boton.pack(side="left", fill="x", expand=True)
            self._botones[clave] = boton
            self._acentos[clave] = acento

        # Frame vacío que se estira: empuja el bloque de perfil al fondo.
        ctk.CTkFrame(self, fg_color="transparent").pack(fill="both", expand=True)

        # --- Tarjeta de perfil -------------------------------------------
        perfil = ctk.CTkFrame(
            self, fg_color=_FONDO_PERFIL, corner_radius=12, border_width=1,
            border_color=_BORDE_PERFIL,
        )
        perfil.pack(fill="x", side="bottom", padx=16, pady=16)

        fila_perfil = ctk.CTkFrame(perfil, fg_color="transparent")
        fila_perfil.pack(fill="x", padx=14, pady=(14, 10))
        avatar_iniciales(fila_perfil, sesion.get("nombre", "?")).pack(side="left")
        textos_perfil = ctk.CTkFrame(fila_perfil, fg_color="transparent")
        textos_perfil.pack(side="left", padx=(10, 0), fill="x", expand=True)
        ctk.CTkLabel(
            textos_perfil, text=sesion.get("nombre", ""), font=tema.fuente(13, "bold"),
            text_color=tema.TEXTO_CLARO, anchor="w",
        ).pack(fill="x")
        rol_texto = sesion.get("rol", "")
        if sesion.get("es_admin"):
            rol_texto = f"{rol_texto} · administrador" if rol_texto else "administrador"
        ctk.CTkLabel(
            textos_perfil, text=rol_texto, font=tema.fuente(11),
            text_color=tema.TEXTO_CLARO_APAGADO, anchor="w",
        ).pack(fill="x")

        ctk.CTkButton(
            perfil, text="⇥  Cerrar sesión", fg_color="transparent", border_width=1,
            border_color=_BORDE_PERFIL, hover_color=tema.VERDE_OSCURO_ACTIVO,
            text_color=tema.TEXTO_CLARO_APAGADO, font=tema.fuente(12), height=32,
            corner_radius=9, command=on_cerrar_sesion,
        ).pack(fill="x", padx=14, pady=(0, 14))

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
            self._acentos[self._activo].configure(fg_color="transparent")
        boton = self._botones.get(clave)
        if boton is not None:
            boton.configure(fg_color=tema.VERDE_OSCURO_ACTIVO, text_color=tema.TEXTO_CLARO)
            self._acentos[clave].configure(fg_color=tema.DORADO_ACENTO)
        self._activo = clave
