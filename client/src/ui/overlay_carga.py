"""Overlay de carga a pantalla completa — el mismo efecto que usa la
Registraduría al procesar un trámite: mientras se espera al backend, tapa
toda la ventana, no deja tocar nada, y muestra el logo del programa con una
frase al azar debajo (las que escribieron los niños para los profes),
cambiando cada varios segundos.

Cuatro estilos, elegidos por Design Claude sobre el mockup que armaron los
niños («Pantalla de espera»):

- `MarcaQueRespira` (1A) y `TarjetaEstado` (1B): se turnan al azar para la
  espera genérica (sin un porcentaje real que mostrar) — una vez por cada
  aparición del overlay, no cambian de estilo a mitad de una espera.
- `ProgresoCohete` (1C): entra apenas hay un avance real que reportar
  (subir o bajar un archivo) — el cohete viaja hacia la estrella según el
  porcentaje real, no una animación que solo simula que algo pasa.
- `TelonVerde` (1D): pantalla de arranque, aparte de las otras tres — la
  usa `ui.app.App` antes de mostrar el login, mientras se verifica la
  versión contra el backend.

Se engancha solo en tareas.en_segundo_plano / en_segundo_plano_con_progreso:
ninguna pantalla tiene que acordarse de mostrarlo a mano.
"""

from __future__ import annotations

import math
import random
import tkinter as tk

import customtkinter as ctk
from PIL import Image, ImageTk

from config import TEMPLATES_DIR

# Las escribieron los niños para los profes — se dejan tal cual, con su
# ortografía y todo, que es parte de la gracia. Aparecen en los 4 estilos.
FRASES = [
    "Python no es una serpiente?",
    "Profes y if vamos de paseo?",
    "Y recuerden el peaton no es un bache",
    "La vida no es una recocha",
    "Si fuera facil cualquiera lo haria",
    "No tienes que ser el mejor solo no tienes que rendirte",
    "El hombre debe de dormir lo que le hace falta",
    "Baneen a Jeronimo G",
    "Me encanta hacer recocha, los adoro profes",
    "Pero porqueeeee como me vas a decir que no tienes datos",
    "Profe, lo estás haciendo mejor de lo que crees",
    "Una buena clase puede quedarse en la memoria para toda la vida",
    "Profe, paciencia... hasta el internet está pensando",
    "Profe, el internet está haciendo lo mejor que puede",
    "Lo que hoy enseñas puede convertirse en el sueño de alguien mañana",
    "Estas frases son de los niños para los profes, y no tienen que ser perfectas, solo sinceras",
    "Todo el curso de Desarrollo de apps formo estas frases con mucho amor",
]

DURACION_FRASE_MS = 15000
# Si la espera dura menos que esto, ni se muestra: evita el parpadeo en las
# llamadas que resuelven casi al toque (por ejemplo, un dato ya en caché).
RETRASO_MOSTRAR_MS = 350
# El telón de arranque (1D) es lo primero que ve el profe al abrir la app:
# sin este mínimo, en una conexión rápida se vería solo un parpadeo. Corto
# a propósito (la construcción del telón mismo ya se come un rato) — más
# que esto se sentía como que la app tardaba más en abrir, no menos.
DURACION_MINIMA_TELON_MS = 300

_ARCHIVO_LOGO = "logo_generacion_i_128.png"
_ARCHIVO_COHETE = "icono_cohete.png"
_ARCHIVO_ESTRELLA = "icono_estrella.png"

# Paleta del mockup («Pantalla de espera»). Este módulo no importa
# ui.tema — nació antes que esa paleta y sus 4 pantallas tienen su propio
# fondo oscuro/claro que no calza con las tarjetas del resto de la app —
# así que quedan acá, calcadas del mockup.
_COLOR_FONDO = "#F5F6F5"
_COLOR_TEXTO = "#1F2A24"
_COLOR_TEXTO_APAGADO = "#5A665F"
_VERDE_OSCURO = "#0F3D2E"
_DORADO = "#E8A11C"
_VERDE = "#2fa84f"
_BLANCO = "#FFFFFF"
_BORDE_TARJETA = "#E4E6E4"
_PISTA = "#EDEFED"
_TEXTO_CLARO = "#EAF2EC"
_TEXTO_CLARO_APAGADO = "#7FA08F"

INTERVALO_MS = 60


def _lerp_color(desde: str, hasta: str, t: float) -> str:
    """Interpola linealmente entre dos colores hex — Tkinter no tiene
    opacidad real en formas de Canvas, así que la «respiración» (opacity)
    de 1A y el brillo de la estrella en 1C se simulan mezclando el color
    real con uno más apagado."""
    t = max(0.0, min(1.0, t))
    d = tuple(int(desde[i : i + 2], 16) for i in (1, 3, 5))
    h = tuple(int(hasta[i : i + 2], 16) for i in (1, 3, 5))
    mezcla = tuple(round(d[i] + (h[i] - d[i]) * t) for i in range(3))
    return "#%02x%02x%02x" % mezcla


class MarcaQueRespira(ctk.CTkFrame):
    """1A: los bloques de la G del logo laten en secuencia, como píxeles
    encendiéndose — sin porcentaje ni texto de estado, solo la marca
    respirando mientras se espera."""

    # (x, y, ancho, alto, color, desfasaje en ms) — mismas proporciones que
    # la G del logo, tal como las armó Design Claude sobre un lienzo de
    # 144×144.
    _BLOQUES = [
        (18, 4, 27, 23, _DORADO, 0),
        (54, 4, 72, 23, _VERDE_OSCURO, 130),
        (18, 36, 27, 108, _VERDE_OSCURO, 260),
        (52, 90, 72, 23, _DORADO, 390),
        (104, 90, 20, 54, _DORADO, 520),
        (18, 121, 79, 23, _VERDE_OSCURO, 650),
    ]
    _ESCALA = 0.72
    _PERIODO_MS = 1700

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        lado = int(144 * self._ESCALA)
        self._canvas = tk.Canvas(
            self, width=lado, height=lado, highlightthickness=0, bg=_COLOR_FONDO, bd=0
        )
        self._canvas.pack()
        ctk.CTkLabel(
            self, text="TRABAJANDO", text_color=_VERDE_OSCURO,
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(pady=(14, 6))
        self._frase_label = ctk.CTkLabel(
            self, text="", text_color=_COLOR_TEXTO_APAGADO,
            font=ctk.CTkFont(size=13, slant="italic"),
            wraplength=380, justify="center",
        )
        self._frase_label.pack()

        self._t = 0.0
        self._job = None
        self.bind("<Destroy>", lambda _e: self.detener())
        self.iniciar()

    def mostrar_frase(self, texto: str):
        self._frase_label.configure(text=texto)

    def iniciar(self):
        if self._job is None:
            self._tic()

    def detener(self):
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:  # noqa: BLE001 — ya no existe la ventana
                pass
            self._job = None

    def _tic(self):
        self._t += INTERVALO_MS
        self._dibujar()
        try:
            self._job = self.after(INTERVALO_MS, self._tic)
        except Exception:  # noqa: BLE001 — la ventana se cerró
            self._job = None

    def _dibujar(self):
        c = self._canvas
        try:
            if not c.winfo_exists():
                return
        except Exception:  # noqa: BLE001
            return
        c.delete("all")
        for x, y, ancho, alto, color, desfasaje in self._BLOQUES:
            fase = 2 * math.pi * (self._t - desfasaje) / self._PERIODO_MS
            onda = 0.5 + 0.5 * math.sin(fase)
            tono = _lerp_color(_lerp_color(color, _COLOR_FONDO, 0.45), color, onda)
            c.create_rectangle(
                x * self._ESCALA, y * self._ESCALA,
                (x + ancho) * self._ESCALA, (y + alto) * self._ESCALA,
                fill=tono, outline="",
            )


class TarjetaEstado(ctk.CTkFrame):
    """1B: tarjeta blanca con el logo, un texto de estado, una barra de
    progreso indeterminada (no hay cómo saber cuánto falta en la mayoría
    de las esperas) y la frase abajo."""

    _ANCHO = 380
    _PERIODO_BARRA_MS = 1500

    def __init__(self, master):
        super().__init__(
            master, fg_color=_BLANCO, corner_radius=18,
            border_width=1, border_color=_BORDE_TARJETA, width=self._ANCHO,
        )
        self.pack_propagate(False)

        encabezado = ctk.CTkFrame(self, fg_color="transparent")
        encabezado.pack(fill="x", padx=28, pady=(26, 0))
        logo = self._cargar_logo()
        if logo is not None:
            ctk.CTkLabel(encabezado, image=logo, text="").pack(side="left", padx=(0, 14))
            self._logo_ref = logo
        textos = ctk.CTkFrame(encabezado, fg_color="transparent")
        textos.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            textos, text="Trabajando...", text_color=_COLOR_TEXTO,
            font=ctk.CTkFont(size=16, weight="bold"), anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            textos, text="Esto puede tardar unos segundos", text_color=_COLOR_TEXTO_APAGADO,
            font=ctk.CTkFont(size=12), anchor="w",
        ).pack(fill="x")

        ancho_barra = self._ANCHO - 56
        self._canvas_barra = tk.Canvas(
            self, width=ancho_barra, height=7, highlightthickness=0, bg=_BLANCO, bd=0,
        )
        self._canvas_barra.pack(padx=28, pady=(20, 18))

        separador = ctk.CTkFrame(self, fg_color=_BORDE_TARJETA, height=1)
        separador.pack(fill="x", padx=28)

        self._frase_label = ctk.CTkLabel(
            self, text="", text_color=_COLOR_TEXTO_APAGADO,
            font=ctk.CTkFont(size=12, slant="italic"),
            wraplength=self._ANCHO - 56, justify="center",
        )
        self._frase_label.pack(padx=28, pady=(16, 24))

        self._t = 0.0
        self._job = None
        self.bind("<Destroy>", lambda _e: self.detener())
        self.iniciar()

    def _cargar_logo(self):
        ruta = TEMPLATES_DIR / "assets" / _ARCHIVO_LOGO
        try:
            img = Image.open(ruta)
        except Exception:  # noqa: BLE001 — sin logo la tarjeta igual funciona
            return None
        return ctk.CTkImage(img, size=(38, 38))

    def mostrar_frase(self, texto: str):
        self._frase_label.configure(text=texto)

    def iniciar(self):
        if self._job is None:
            self._tic()

    def detener(self):
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:  # noqa: BLE001
                pass
            self._job = None

    def _tic(self):
        self._t += INTERVALO_MS
        self._dibujar_barra()
        try:
            self._job = self.after(INTERVALO_MS, self._tic)
        except Exception:  # noqa: BLE001 — la ventana se cerró
            self._job = None

    def _dibujar_barra(self):
        c = self._canvas_barra
        try:
            if not c.winfo_exists():
                return
        except Exception:  # noqa: BLE001
            return
        c.delete("all")
        ancho = int(c["width"])
        c.create_rectangle(0, 0, ancho, 7, fill=_PISTA, outline="")
        t_frac = (self._t % self._PERIODO_BARRA_MS) / self._PERIODO_BARRA_MS
        segmento = ancho * 0.38
        x0 = -segmento + t_frac * (ancho + segmento)
        c.create_rectangle(x0, 0, x0 + segmento, 7, fill=_VERDE, outline="")


class ProgresoCohete(ctk.CTkFrame):
    """1C: barra de progreso con onda infantil para cuando SÍ se sabe
    cuánto falta (subir o bajar un archivo): un cohete que viaja hacia una
    estrella según el porcentaje real — nada de animación genérica, el
    avance que se ve es el que de verdad va habiendo. Suma el porcentaje
    en grande, el conteo «X de Y» cuando se conoce, y la frase de los
    niños debajo (para no perder la compañía en las esperas largas entre
    un aviso de progreso y el siguiente).

    Los íconos son de Twemoji (twemoji.twitter.com / github.com/jdecked/
    twemoji), licencia CC-BY 4.0 — ver templates/assets/CREDITOS.md.
    """

    _ANCHO_CANVAS = 340
    _ALTO_CANVAS = 60
    _PERIODO_FLOTE_MS = 2400

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        cabecera = ctk.CTkFrame(self, fg_color="transparent")
        cabecera.pack(fill="x", padx=6)
        self._pct_label = ctk.CTkLabel(
            cabecera, text="0%", text_color=_VERDE_OSCURO,
            font=ctk.CTkFont(size=30, weight="bold"),
        )
        self._pct_label.pack(side="left")
        self._conteo_label = ctk.CTkLabel(
            cabecera, text="", text_color=_COLOR_TEXTO_APAGADO,
            font=ctk.CTkFont(size=12),
        )
        self._conteo_label.pack(side="right")

        self._canvas = tk.Canvas(
            self, width=self._ANCHO_CANVAS, height=self._ALTO_CANVAS,
            highlightthickness=0, bg=_COLOR_FONDO, bd=0,
        )
        self._canvas.pack(pady=(6, 0))
        self._label = ctk.CTkLabel(self, text="", text_color=_COLOR_TEXTO, font=ctk.CTkFont(size=11))
        self._label.pack(pady=(2, 0))

        self._frase_label = ctk.CTkLabel(
            self, text="", text_color=_COLOR_TEXTO_APAGADO,
            font=ctk.CTkFont(size=12, slant="italic"),
            wraplength=380, justify="center",
        )
        self._frase_label.pack(pady=(10, 0))

        self._fraccion = 0.0
        self._texto_extra = ""
        # El ícono de Twemoji viene dibujado en diagonal (apuntando arriba a
        # la derecha); rotado queda horizontal, apuntando hacia la meta.
        self._img_cohete = self._cargar_imagen(_ARCHIVO_COHETE, 34, rotar=-45)
        self._img_estrella = self._cargar_imagen(_ARCHIVO_ESTRELLA, 28)

        self._t = 0.0
        self._job = None
        self.bind("<Destroy>", lambda _e: self.detener())
        self._dibujar()
        self.iniciar()

    def _cargar_imagen(self, nombre: str, tamano: int, rotar: float = 0):
        ruta = TEMPLATES_DIR / "assets" / nombre
        try:
            img = Image.open(ruta).convert("RGBA")
            if rotar:
                img = img.rotate(rotar, expand=True, resample=Image.BICUBIC)
            img.thumbnail((tamano, tamano), Image.LANCZOS)
        except Exception:  # noqa: BLE001 — sin ícono el cohete no se dibuja, pero no revienta
            return None
        return ImageTk.PhotoImage(img)

    def mostrar_frase(self, texto: str):
        self._frase_label.configure(text=texto)

    def actualizar(self, fraccion: float, hecho: float | None = None, total: float | None = None):
        self._fraccion = max(0.0, min(1.0, fraccion))
        if hecho is not None and total:
            self._texto_extra = f"{int(hecho)} de {int(total)}"
        else:
            self._texto_extra = ""
        self._dibujar()

    def iniciar(self):
        if self._job is None:
            self._tic()

    def detener(self):
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:  # noqa: BLE001
                pass
            self._job = None

    def _tic(self):
        self._t += INTERVALO_MS
        self._dibujar()
        try:
            self._job = self.after(INTERVALO_MS, self._tic)
        except Exception:  # noqa: BLE001 — la ventana se cerró
            self._job = None

    def _dibujar(self):
        c = self._canvas
        try:
            if not c.winfo_exists():
                return
        except Exception:  # noqa: BLE001
            return
        c.delete("all")
        margen = 30
        y_base = self._ALTO_CANVAS / 2
        x0, x1 = margen, self._ANCHO_CANVAS - margen
        c.create_line(x0, y_base, x1, y_base, dash=(3, 4), fill="#c9c9c9", width=2)

        # La estrella respira despacio en el lugar, para que la meta no se
        # sienta quieta del todo mientras el cohete todavía está lejos.
        brillo = 0.5 + 0.5 * math.sin(2 * math.pi * self._t / 2400)
        if self._img_estrella is not None:
            c.create_image(x1, y_base - 2 * brillo, image=self._img_estrella, anchor="center")

        # El cohete flota apenas, en vez de quedar clavado en el lugar
        # exacto del porcentaje — así se ve vivo incluso cuando pasa un
        # rato largo entre un aviso de progreso real y el siguiente.
        flote = 3 * math.sin(2 * math.pi * self._t / self._PERIODO_FLOTE_MS)
        x = x0 + self._fraccion * (x1 - x0)
        if self._img_cohete is not None:
            c.create_image(x, y_base + flote, image=self._img_cohete, anchor="center")

        porcentaje = int(round(self._fraccion * 100))
        self._pct_label.configure(text=f"{porcentaje}%")
        self._conteo_label.configure(text=self._texto_extra)
        self._label.configure(text="")


class TelonVerde(ctk.CTkFrame):
    """1D: pantalla de arranque de la app, aparte de las otras tres — la
    usa `ui.app.App` antes de mostrar el login, mientras se verifica la
    versión contra el backend. Es la única de las cuatro que arma su
    propia rotación de frases: no depende de `OverlayCarga`, porque corre
    antes de que exista ninguna sesión."""

    def __init__(self, master):
        super().__init__(master, fg_color=_VERDE_OSCURO, corner_radius=0)

        self._ultimo_tamano_puntos: tuple[int, int] | None = None
        self._canvas_fondo = tk.Canvas(
            self, highlightthickness=0, bg=_VERDE_OSCURO, bd=0,
        )
        self._canvas_fondo.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._canvas_fondo.bind("<Configure>", lambda _e: self._dibujar_puntos())

        contenido = ctk.CTkFrame(self, fg_color="transparent")
        contenido.place(relx=0.5, rely=0.5, anchor="center")

        tarjeta = ctk.CTkFrame(contenido, fg_color=_BLANCO, corner_radius=22)
        tarjeta.pack(padx=20, pady=20)
        logo = self._cargar_logo()
        if logo is not None:
            ctk.CTkLabel(tarjeta, image=logo, text="").pack(padx=28, pady=28)
            self._logo_ref = logo

        self._canvas_barras = tk.Canvas(
            contenido, width=70, height=30, highlightthickness=0, bg=_VERDE_OSCURO, bd=0,
        )
        self._canvas_barras.pack(pady=(30, 0))

        self._frase_label = ctk.CTkLabel(
            contenido, text="", text_color=_TEXTO_CLARO,
            font=ctk.CTkFont(size=18, slant="italic"),
            wraplength=560, justify="center",
        )
        self._frase_label.pack(pady=(28, 0))

        ctk.CTkLabel(
            self, text="CIENCIA  ·  TECNOLOGÍA  ·  INNOVACIÓN",
            text_color=_TEXTO_CLARO_APAGADO,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).place(relx=0.5, rely=0.94, anchor="center")

        self._t = 0.0
        self._job = None
        self._frases_restantes: list[str] = []
        self._despues_frase_id = None

        self.bind("<Destroy>", lambda _e: self.detener())
        self._dibujar_puntos()
        self._siguiente_frase()
        self.iniciar()

    def _cargar_logo(self):
        ruta = TEMPLATES_DIR / "assets" / _ARCHIVO_LOGO
        try:
            img = Image.open(ruta)
        except Exception:  # noqa: BLE001 — sin logo el telón igual funciona
            return None
        return ctk.CTkImage(img, size=(112, 112))

    def _dibujar_puntos(self):
        """Puntos apagados por todo el fondo, como el patrón del mockup —
        en posiciones fijas de una grilla (no al azar), para que no
        salten al redimensionar la ventana."""
        c = self._canvas_fondo
        try:
            ancho, alto = c.winfo_width(), c.winfo_height()
        except Exception:  # noqa: BLE001
            return
        if ancho <= 1 or alto <= 1:
            return
        # <Configure> dispara varias veces con el mismo tamaño final mientras
        # se acomoda el layout inicial — redibujar los puntos cada vez (unos
        # cientos de create_oval) se sentía en el arranque. Si el tamaño no
        # cambió de verdad, no hay nada que rehacer.
        if (ancho, alto) == self._ultimo_tamano_puntos:
            return
        self._ultimo_tamano_puntos = (ancho, alto)
        c.delete("puntos")
        espaciado = 34
        color = _lerp_color(_DORADO, _VERDE_OSCURO, 0.84)
        radio = 1.6
        y = espaciado / 2
        while y < alto:
            x = espaciado / 2
            while x < ancho:
                c.create_oval(
                    x - radio, y - radio, x + radio, y + radio,
                    fill=color, outline="", tags="puntos",
                )
                x += espaciado
            y += espaciado
        c.tag_lower("puntos")

    def iniciar(self):
        if self._job is None:
            self._tic()

    def detener(self):
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:  # noqa: BLE001
                pass
            self._job = None
        if self._despues_frase_id is not None:
            try:
                self.after_cancel(self._despues_frase_id)
            except Exception:  # noqa: BLE001
                pass
            self._despues_frase_id = None

    def _tic(self):
        self._t += INTERVALO_MS
        self._dibujar_barras()
        try:
            self._job = self.after(INTERVALO_MS, self._tic)
        except Exception:  # noqa: BLE001 — la ventana se cerró
            self._job = None

    def _dibujar_barras(self):
        c = self._canvas_barras
        try:
            if not c.winfo_exists():
                return
        except Exception:  # noqa: BLE001
            return
        c.delete("all")
        n, ancho_barra, sep = 5, 5, 6
        alto_max, alto_min = 26, 6
        periodo_ms = 1100
        base = 30
        for i in range(n):
            fase = 2 * math.pi * self._t / periodo_ms - i * (math.pi / 3.6)
            onda = 0.5 + 0.5 * math.sin(fase)
            alto = alto_min + (alto_max - alto_min) * onda
            cx = ancho_barra / 2 + i * (ancho_barra + sep)
            c.create_rectangle(
                cx - ancho_barra / 2, base - alto, cx + ancho_barra / 2, base,
                fill=_DORADO, outline="",
            )

    def _siguiente_frase(self):
        if not self._frases_restantes:
            self._frases_restantes = FRASES.copy()
            random.shuffle(self._frases_restantes)
        frase = self._frases_restantes.pop()
        self._frase_label.configure(text=frase)
        try:
            self._despues_frase_id = self.after(DURACION_FRASE_MS, self._siguiente_frase)
        except Exception:  # noqa: BLE001 — la ventana se cerró
            self._despues_frase_id = None


class OverlayCarga(ctk.CTkFrame):
    """Se coloca con `.place(relx=0, rely=0, relwidth=1, relheight=1)` por
    encima de lo que haya en la ventana en ese momento.

    `mostrar()`/`ocultar()` llevan la cuenta de cuántas llamadas la están
    pidiendo a la vez (varias pueden solaparse) y solo la esconden cuando la
    última termina.

    Para la espera genérica (sin porcentaje real) se turnan al azar,
    `MarcaQueRespira` (1A) y `TarjetaEstado` (1B) — una vez por cada
    aparición del overlay. Apenas llega progreso real se reemplazan por
    `ProgresoCohete` (1C).
    """

    def __init__(self, master):
        super().__init__(master, fg_color=_COLOR_FONDO, corner_radius=0)

        self._contenido = ctk.CTkFrame(self, fg_color="transparent")
        self._contenido.place(relx=0.5, rely=0.5, anchor="center")

        self._generico_actual: ctk.CTkFrame | None = None
        self._cohete = ProgresoCohete(self._contenido)
        self._modo_progreso = False

        self._contador = 0
        self._mostrar_pendiente_id = None
        self._frase_actual = ""
        self._frases_restantes: list[str] = []
        self._despues_id = None

        # Absorbe clicks para que no lleguen a la pantalla de abajo.
        for evento in ("<Button-1>", "<Button-2>", "<Button-3>"):
            self.bind(evento, lambda _e: "break")

    def mostrar(self):
        self._contador += 1
        if self._contador == 1 and self._mostrar_pendiente_id is None:
            try:
                self._mostrar_pendiente_id = self.after(RETRASO_MOSTRAR_MS, self._mostrar_ya)
            except Exception:  # noqa: BLE001 — la ventana se cerró
                pass

    def _mostrar_ya(self):
        self._mostrar_pendiente_id = None
        if self._contador <= 0:
            return  # ya terminó todo antes de que se cumpliera el retraso
        try:
            self.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.lift()
            self.focus_set()
        except Exception:  # noqa: BLE001
            return

        # Se elige acá, no en __init__: así cada aparición nueva del
        # overlay sortea de nuevo, en vez de quedar pegada siempre al
        # mismo estilo. OJO: no tocar el modo cohete acá — ver el
        # comentario en ocultar() sobre por qué el reseteo va ahí.
        estilo = random.choice([MarcaQueRespira, TarjetaEstado])
        self._generico_actual = estilo(self._contenido)
        self._generico_actual.pack()
        self._generico_actual.mostrar_frase(self._frase_actual)
        self._siguiente_frase()

    def actualizar_progreso(
        self, fraccion: float | None, hecho: float | None = None, total: float | None = None,
    ):
        """Reemplaza el estilo genérico por el cohete apenas hay un
        porcentaje real que mostrar. `fraccion` en None no hace nada (se
        llama así cuando no se pudo calcular un porcentaje de lo que
        reportó la pantalla)."""
        if fraccion is None:
            return
        if not self._modo_progreso:
            self._modo_progreso = True
            if self._generico_actual is not None:
                self._generico_actual.pack_forget()
            self._cohete.pack()
            self._cohete.mostrar_frase(self._frase_actual)
        self._cohete.actualizar(fraccion, hecho, total)

    def ocultar(self):
        self._contador = max(0, self._contador - 1)
        if self._contador > 0:
            return

        if self._mostrar_pendiente_id is not None:
            try:
                self.after_cancel(self._mostrar_pendiente_id)
            except Exception:  # noqa: BLE001
                pass
            self._mostrar_pendiente_id = None

        if self._despues_id is not None:
            try:
                self.after_cancel(self._despues_id)
            except Exception:  # noqa: BLE001
                pass
            self._despues_id = None

        # El reseteo va acá, con el ciclo ya cerrado del todo — así la
        # próxima vez que se muestre arranca sin arrastrar el estilo o el
        # modo cohete de una llamada anterior.
        self._cohete.pack_forget()
        if self._generico_actual is not None:
            self._generico_actual.destroy()
            self._generico_actual = None
        self._modo_progreso = False
        try:
            self.place_forget()
        except Exception:  # noqa: BLE001 — ya no existe la ventana
            pass

    def _siguiente_frase(self):
        if not self._frases_restantes:
            self._frases_restantes = FRASES.copy()
            random.shuffle(self._frases_restantes)
        self._frase_actual = self._frases_restantes.pop()
        if self._generico_actual is not None:
            self._generico_actual.mostrar_frase(self._frase_actual)
        self._cohete.mostrar_frase(self._frase_actual)
        try:
            self._despues_id = self.after(DURACION_FRASE_MS, self._siguiente_frase)
        except Exception:  # noqa: BLE001 — la ventana se cerró
            self._despues_id = None


def obtener_overlay(root) -> OverlayCarga | None:
    """Una instancia por ventana raíz. `_limpiar()` en App destruye todos
    los hijos del root al cambiar de pantalla, así que esta instancia puede
    quedar destruida entre una llamada y otra — acá se repone sola."""
    overlay = getattr(root, "_overlay_carga", None)
    try:
        existe = overlay is not None and overlay.winfo_exists()
    except Exception:  # noqa: BLE001
        existe = False
    if not existe:
        try:
            overlay = OverlayCarga(root)
        except Exception:  # noqa: BLE001 — la ventana se cerró
            return None
        root._overlay_carga = overlay
    return overlay


def hay_overlay_activo(root) -> bool:
    """True mientras el overlay esté tapando la ventana (o por tapar: el
    retraso de 350ms todavía no se cumplió). Para el aviso de "¿cerrar
    igual?" — que la ventana esté esperando algo, aunque sea una descarga
    de solo lectura, ya es motivo para preguntar antes de cerrar."""
    overlay = getattr(root, "_overlay_carga", None)
    try:
        return overlay is not None and overlay.winfo_exists() and overlay._contador > 0
    except Exception:  # noqa: BLE001
        return False
