"""Overlay de carga a pantalla completa — el mismo efecto que usa la
Registraduría al procesar un trámite: mientras se espera al backend, tapa
toda la ventana, no deja tocar nada, y muestra el logo del programa con una
frase al azar debajo (las que escribieron los niños para los profes),
cambiando cada varios segundos.

Se engancha solo en tareas.en_segundo_plano / en_segundo_plano_con_progreso:
ninguna pantalla tiene que acordarse de mostrarlo a mano.
"""

from __future__ import annotations

import random
import tkinter as tk

import customtkinter as ctk
from PIL import Image, ImageTk

from config import TEMPLATES_DIR
from ui.cargando import Cargando

# Las escribieron los niños para los profes — se dejan tal cual, con su
# ortografía y todo, que es parte de la gracia.
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
_ARCHIVO_LOGO = "logo_generacion_i_128.png"
_ARCHIVO_COHETE = "icono_cohete.png"
_ARCHIVO_ESTRELLA = "icono_estrella.png"
_COLOR_FONDO = "#f2f2f2"
_COLOR_TEXTO = "#333333"


class ProgresoCohete(ctk.CTkFrame):
    """Barra de progreso con onda infantil para cuando SÍ se sabe cuánto
    falta (subir o bajar un archivo): un cohete que viaja hacia una
    estrella según el porcentaje real — nada de animación genérica, el
    avance que se ve es el que de verdad va habiendo.

    Los íconos son de Twemoji (twemoji.twitter.com / github.com/jdecked/
    twemoji), licencia CC-BY 4.0 — ver templates/assets/CREDITOS.md.
    """

    def __init__(self, master, ancho: int = 260, alto: int = 54):
        super().__init__(master, fg_color="transparent")
        self._ancho = ancho
        self._alto = alto
        self._canvas = tk.Canvas(
            self, width=ancho, height=alto, highlightthickness=0, bg=_COLOR_FONDO, bd=0
        )
        self._canvas.pack()
        self._label = ctk.CTkLabel(self, text="", text_color=_COLOR_TEXTO, font=ctk.CTkFont(size=11))
        self._label.pack(pady=(4, 0))
        self._fraccion = 0.0
        self._texto_extra = ""
        # El ícono de Twemoji viene dibujado en diagonal (apuntando arriba a
        # la derecha); rotado queda horizontal, apuntando hacia la meta.
        self._img_cohete = self._cargar_imagen(_ARCHIVO_COHETE, 32, rotar=-45)
        self._img_estrella = self._cargar_imagen(_ARCHIVO_ESTRELLA, 26)
        self._dibujar()

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

    def actualizar(self, fraccion: float, texto_extra: str = ""):
        self._fraccion = max(0.0, min(1.0, fraccion))
        self._texto_extra = texto_extra
        self._dibujar()

    def _dibujar(self):
        c = self._canvas
        c.delete("all")
        margen = 26
        y = self._alto / 2
        x0, x1 = margen, self._ancho - margen
        c.create_line(x0, y, x1, y, dash=(3, 4), fill="#c9c9c9", width=2)

        if self._img_estrella is not None:
            c.create_image(x1, y, image=self._img_estrella, anchor="center")

        x = x0 + self._fraccion * (x1 - x0)
        if self._img_cohete is not None:
            c.create_image(x, y, image=self._img_cohete, anchor="center")

        porcentaje = int(round(self._fraccion * 100))
        texto = f"{porcentaje}%"
        if self._texto_extra:
            texto = f"{self._texto_extra} — {texto}"
        self._label.configure(text=texto)


class OverlayCarga(ctk.CTkFrame):
    """Se coloca con `.place(relx=0, rely=0, relwidth=1, relheight=1)` por
    encima de lo que haya en la ventana en ese momento.

    `mostrar()`/`ocultar()` llevan la cuenta de cuántas llamadas la están
    pidiendo a la vez (varias pueden solaparse) y solo la esconden cuando la
    última termina.
    """

    def __init__(self, master):
        super().__init__(master, fg_color=_COLOR_FONDO, corner_radius=0)

        contenido = ctk.CTkFrame(self, fg_color="transparent")
        contenido.place(relx=0.5, rely=0.5, anchor="center")

        self._logo = self._cargar_logo()
        if self._logo is not None:
            ctk.CTkLabel(contenido, image=self._logo, text="").pack(pady=(0, 6))

        self._cargando = Cargando(contenido, texto="", tamano=14)
        self._cargando.label.configure(text_color=_COLOR_TEXTO, wraplength=380, justify="center")
        self._cargando.pack()

        # Se muestra ADEMÁS de los cuadraditos (no en vez de) apenas hay
        # progreso real que reportar — ver actualizar_progreso(). Si una
        # descarga tarda un rato largo entre un aviso de progreso y el
        # siguiente (la masiva avisa una vez por informe), el cohete quieto
        # se ve colgado; los cuadraditos siguen latiendo todo el tiempo y
        # dejan claro que la app sigue viva.
        self._cohete = ProgresoCohete(contenido)
        self._modo_progreso = False

        self._contador = 0
        self._mostrar_pendiente_id = None
        self._despues_id = None
        self._frases_restantes: list[str] = []

        # Absorbe clicks para que no lleguen a la pantalla de abajo.
        for evento in ("<Button-1>", "<Button-2>", "<Button-3>"):
            self.bind(evento, lambda _e: "break")

    def _cargar_logo(self):
        ruta = TEMPLATES_DIR / "assets" / _ARCHIVO_LOGO
        try:
            img = Image.open(ruta)
        except Exception:  # noqa: BLE001 — sin logo el overlay igual funciona
            return None
        return ctk.CTkImage(img, size=(96, 96))

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
        # Los cuadraditos arrancan siempre (late todo el rato que dure la
        # espera); el cohete se suma aparte si llega progreso real — ver
        # actualizar_progreso(). OJO: no tocar acá el modo cohete. Si el
        # progreso real llega ANTES de que se cumplan estos 350ms (pasa
        # seguido: la descarga masiva avisa el primer ítem casi al toque),
        # forget()-earlo acá lo haría desaparecer justo cuando apareció. El
        # reseteo va en ocultar(), que corre una sola vez por ciclo completo.
        self._cargando.iniciar()
        self._siguiente_frase()

    def actualizar_progreso(self, fraccion: float | None, texto_extra: str = ""):
        """Suma el cohete debajo de los cuadraditos apenas hay un porcentaje
        real que mostrar (no lo reemplaza: entre un aviso de progreso y el
        siguiente puede pasar un buen rato, y el cohete quieto solo se vería
        colgado). `fraccion` en None no hace nada (se llama así cuando no se
        pudo calcular un porcentaje de lo que reportó la pantalla)."""
        if fraccion is None:
            return
        if not self._modo_progreso:
            self._modo_progreso = True
            self._cohete.pack(pady=(10, 0))
        self._cohete.actualizar(fraccion, texto_extra)

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

        self._cargando.detener()
        # El cohete se saca recién acá, con el ciclo ya cerrado del todo —
        # así la próxima vez que se muestre arranca sin arrastrar el de una
        # llamada anterior. Los cuadraditos quedan siempre listos, nunca se
        # sacan del todo.
        if self._modo_progreso:
            self._modo_progreso = False
            self._cohete.pack_forget()
        try:
            self.place_forget()
        except Exception:  # noqa: BLE001 — ya no existe la ventana
            pass

    def _siguiente_frase(self):
        if not self._frases_restantes:
            self._frases_restantes = FRASES.copy()
            random.shuffle(self._frases_restantes)
        frase = self._frases_restantes.pop()
        self._cargando.configurar_texto(frase)
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
