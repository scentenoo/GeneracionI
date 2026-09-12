"""Paleta y tipografía centrales del rediseño (el que eligieron los niños:
panel lateral verde oscuro, tarjetas de resumen, acentos dorados).

Las pantallas viejas siguen con sus propios `VERDE`/`ROJO`/`AMBAR` locales
por ahora — esto no las migra, es la base para lo nuevo. Cuando una pantalla
vieja se rediseñe en una etapa siguiente, pasa a importar de acá y se le
borran los duplicados.

Los valores exactos salieron de mirar el mockup a ojo (no hay forma de sacar
el hex exacto de un PDF) — se van a seguir afinando con el mismo ciclo de
captura de pantalla que se usó para el overlay y el cohete.
"""

from __future__ import annotations

import customtkinter as ctk

# --- Verdes (marca + panel lateral) ----------------------------------------
VERDE_OSCURO = "#0F3D2E"       # fondo del panel lateral
VERDE_OSCURO_ACTIVO = "#17573F"  # ítem de menú activo / hover en el panel
VERDE = "#2fa84f"              # verde de marca ya usado en toda la app (botones)
VERDE_HOVER = "#248a3d"

# --- Dorado / naranja (acento de marca, ya está en el logo) ----------------
DORADO = "#F2A900"
DORADO_HOVER = "#D99400"
# Dorado exacto del mockup de rediseño completo (barra lateral, acentos
# nuevos) — distinto por muy poco de DORADO, que sigue usándose donde ya
# estaba (badge de administrador) para no desarmar nada.
DORADO_ACENTO = "#E8A11C"
DORADO_ACENTO_HOVER = "#D0900E"

# --- Neutros ------------------------------------------------------------
BLANCO = "#FFFFFF"
FONDO_CONTENIDO = "#F5F6F5"    # fondo del área de contenido (no del panel lateral)
FONDO_TARJETA = "#FFFFFF"
BORDE_TARJETA = "#E4E6E4"
TEXTO_OSCURO = "#1F2A24"
TEXTO_CLARO = "#FFFFFF"
TEXTO_CLARO_APAGADO = "#B9C7C0"  # texto secundario sobre el panel oscuro
GRIS = "gray"
TEXTO_MUTED = "#7A857E"  # gris de metadatos (fechas, conteos) sobre fondo claro

# --- Estado (coinciden con lo que ya usan las pantallas existentes) --------
ROJO = "#c0392b"
ROJO_HOVER = "#922b21"
AMBAR = "#8A6114"
AMBAR_HOVER = "#6b4d10"

# --- Cápsulas de estado (fondo tintado + texto del mismo color, del mockup:
# contadores de sección — minutos, fotos, asistencia — y los ítems del
# checklist "Antes de guardar") — distintas de `chip()`, que usa un fondo
# gris parejo para todos los colores. ---------------------------------------
VERDE_CHIP_BG = "#E7F6EC"
VERDE_CHIP_TEXTO = "#1F7A3F"
ROJO_CHIP_BG = "#FDECEA"
AMBAR_CHIP_BG = "#FDF2DC"

# Línea divisoria fina entre secciones de una misma tarjeta (más clara que
# BORDE_TARJETA, que es el borde exterior de la tarjeta).
DIVISOR = "#EDEFED"

# --- Acentos de tarjeta (variedad como en el mockup: cada tarjeta un color) -
AZUL = "#2F80ED"
MORADO = "#8e44ad"


def fuente(tamano: int = 13, peso: str = "normal") -> ctk.CTkFont:
    """Fuente estándar de la app — no hay una tipografía con licencia
    propia, así que se usa la que trae customtkinter por defecto, solo
    variando tamaño/peso desde un solo lugar."""
    return ctk.CTkFont(size=tamano, weight=peso)


FUENTE_TITULO = lambda: fuente(24, "bold")  # noqa: E731
FUENTE_SUBTITULO = lambda: fuente(15)  # noqa: E731
FUENTE_NUMERO_TARJETA = lambda: fuente(26, "bold")  # noqa: E731
FUENTE_ETIQUETA_TARJETA = lambda: fuente(12)  # noqa: E731
