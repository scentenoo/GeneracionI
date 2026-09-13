"""Parches a bugs conocidos de customtkinter (6.0.0) que no dependen de
nuestro código, solo de la versión de Tk instalada. Se aplican una sola vez
al arrancar, antes de crear cualquier ventana."""

from __future__ import annotations


def aplicar():
    _parchar_scroll_sobre_desplegables()
    _parchar_repintado_al_scrollear()
    _parchar_scrollbar_lenta_al_agregar_filas()


def reparar_copiar_pegar(root):
    """En teclados que no son inglés de EE.UU. (el latinoamericano, entre
    otros), Tk a veces no reconoce Ctrl+C/Ctrl+V/Ctrl+X ni Ctrl+A en
    Entry/Textbox: el keysym que llega para esa combinación no es el que
    esperan los bindings por defecto de Tk, y copiar/pegar queda mudo, aun
    cuando el resto de la app anda bien.

    Se repara re-conectando el atajo por el CÓDIGO FÍSICO de la tecla
    (estable entre teclados) en vez de por el carácter que produce, y
    generando directamente el evento virtual (<<Copy>>, etc.) que Tk ya
    sabe ejecutar — eso sí funciona, lo que fallaba era solo el primer
    paso, la detección del atajo.

    A diferencia de _parchar_scroll_sobre_desplegables, esto necesita una
    ventana Tk ya creada (bind_class no existe antes), así que se llama
    aparte, después de armar la ventana principal."""
    _COPIAR, _PEGAR, _CORTAR, _SELECCIONAR_TODO = 67, 86, 88, 65  # C, V, X, A

    def _manejar(event):
        # bit 0x4 = Control, en Windows y X11.
        if not (event.state & 0x4):
            return None
        accion = {
            _COPIAR: "<<Copy>>",
            _PEGAR: "<<Paste>>",
            _CORTAR: "<<Cut>>",
            _SELECCIONAR_TODO: "<<SelectAll>>",
        }.get(event.keycode)
        if accion is None:
            return None
        event.widget.event_generate(accion)
        return "break"

    for clase in ("Entry", "Text"):
        root.bind_class(clase, "<KeyPress>", _manejar, add="+")


def _parchar_scroll_sobre_desplegables():
    """CTkScrollableFrame asume que event.widget siempre es un widget de
    Tkinter y le busca .master recursivamente para saber si el scroll caía
    adentro suyo. En Linux, cuando el mouse desplaza estando sobre el
    desplegable de un CTkOptionMenu/CTkComboBox, Tk a veces entrega el
    nombre del widget (un string) en vez del objeto — .master de un string
    no existe, y sin este parche eso tira un AttributeError por consola en
    cada scroll sobre un desplegable. No rompe nada, pero llena la consola
    de basura; acá se lo trata como "no, este scroll no es válido" en vez
    de reventar."""
    from customtkinter.windows.widgets.ctk_scrollable_frame import CTkScrollableFrame

    original = CTkScrollableFrame._check_if_valid_scroll

    def _seguro(self, widget):
        try:
            return original(self, widget)
        except AttributeError:
            return False

    CTkScrollableFrame._check_if_valid_scroll = _seguro


def _parchar_repintado_al_scrollear():
    """Bug de fondo de Tk en Windows (sin arreglo conocido, ver
    https://github.com/TomSchimansky/CustomTkinter/issues/215): el canvas
    que hace de scroll en CTkScrollableFrame corrompe el repintado cuando
    el gesto de scroll es más rápido de lo que Tk llega a redibujar —
    quedan filas viejas superpuestas con las nuevas.

    Como el disparador es la VELOCIDAD (no cuánto contenido haya, ya
    probado y descartado), esto frena el scroll en vez de intentar
    repintar más rápido: si dos pasos de scroll llegan demasiado seguidos
    (menos de 20ms entre uno y otro — más de lo que Tk puede redibujar a
    tiempo en los equipos de la sede), el segundo se descarta en vez de
    ejecutarse encima del primero sin que la pantalla haya terminado de
    ponerse al día. Se nota un poco menos fluido; se cambia por evitar el
    efecto roto.

    Va en `Canvas.yview`, el punto en común de la rueda del mouse y de
    arrastrar la barra — así cubre las dos formas de scrollear con un solo
    parche. Afecta a todos los Canvas de la app, pero es inofensivo: a uno
    que nunca haga scroll (como el de la animación de «cargando») esto no
    le cambia nada, `yview` ahí ni se llama."""
    import time
    import tkinter
    import weakref

    original_yview = tkinter.Canvas.yview
    _ultimo_por_canvas = weakref.WeakKeyDictionary()
    _MIN_MS_ENTRE_SCROLLS = 20

    def _yview_frenado(self, *args, **kwargs):
        ahora = time.monotonic()
        anterior = _ultimo_por_canvas.get(self, 0.0)
        if (ahora - anterior) * 1000 < _MIN_MS_ENTRE_SCROLLS:
            return None  # demasiado seguido del anterior: se descarta este paso
        _ultimo_por_canvas[self] = ahora
        return original_yview(self, *args, **kwargs)

    tkinter.Canvas.yview = _yview_frenado


def _parchar_scrollbar_lenta_al_agregar_filas():
    """CTkScrollbar.set() —que el canvas de una CTkScrollableFrame llama
    solo, cada vez que cambia su scrollregion, es decir cada vez que se
    agrega o saca UN widget de la lista— redibuja el "thumb" de la barra Y
    llama canvas.update_idletasks() sin condición ninguna. update_idletasks
    fuerza un repintado sincrónico de TODA la ventana, no solo de la barra.

    Con una pantalla que arma una lista de filas en un `for` (Mis
    planeaciones, Usuarios, Revisar...), cada fila mete varios widgets, así
    que esto se dispara decenas de veces seguidas — y cada una repinta de
    nuevo lo que ya se había agregado antes. El costo crece con el cuadrado
    de la cantidad de widgets: medido a mano, redibujar una lista de 20
    filas (unos 200 widgets) tardaba ~2.9s, con esta cascada sola
    explicando cerca de la mitad. Es la causa real de que cambiar a una
    pantalla con una lista larga se sienta pesado, más allá de cualquier
    espera al backend.

    El arreglo: en vez de redibujar en el momento en cada `set()`, se junta
    la ráfaga con `after_idle` y se dibuja una sola vez, con el valor más
    reciente, cuando Tk se queda libre — que es también el único momento en
    que alguien puede llegar a VER la barra, así que no se pierde nada
    visualmente. El arrastre manual de la barra (`_on_motion`,
    `_mouse_scroll_event`) no pasa por acá, llama a `_draw()` directo, así
    que sigue tan sincrónico como antes."""
    from customtkinter.windows.widgets.ctk_scrollbar import CTkScrollbar

    def _set_agrupado(self, start_value, end_value):
        self._start_value = float(start_value)
        self._end_value = float(end_value)
        if getattr(self, "_ctk_parche_redibujo_pendiente", False):
            return

        def _dibujar_ya():
            self._ctk_parche_redibujo_pendiente = False
            if self.winfo_exists():
                self._draw()

        self._ctk_parche_redibujo_pendiente = True
        self.after_idle(_dibujar_ya)

    CTkScrollbar.set = _set_agrupado
