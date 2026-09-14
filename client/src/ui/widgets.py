"""Widgets chicos reutilizables entre pantallas."""

from __future__ import annotations

import base64
import io
import re
import tkinter as tk
from typing import Callable

import customtkinter as ctk
from PIL import Image

from services import ortografia
from ui import tema
from ui.cargando import Cargando

MIN_PALABRAS = 20  # ver spec sección 6

_TAG_ORTOGRAFIA = "ortografia_mal"
_PATRON_PALABRA = re.compile(r"[A-Za-zÁÉÍÓÚáéíóúÑñÜü]+(?:[-'][A-Za-zÁÉÍÓÚáéíóúÑñÜü]+)*")
# El principio del texto, o una letra que sigue a punto/signo de
# cierre + espacio: ahí va mayúscula.
_PATRON_INICIO_ORACION = re.compile(r"(?:\A|[.!?]\s+)([a-záéíóúñü])")


def aplicar_corrector_ortografico(textbox: tk.Text) -> Callable[[], None]:
    """Subraya en rojo, en vivo, las palabras que el corrector no reconoce
    (spec: la mayoría de devoluciones de planeaciones e informes son por
    errores de ortografía), y agrega sugerencias con el clic derecho sobre
    una palabra marcada.

    Se suma a cualquier tkinter.Text/CTkTextbox con una sola línea — usa
    `add="+"` así que no reemplaza el `<KeyRelease>` que ese campo ya tenga
    (el contador de palabras, por ejemplo). Devuelve una función para forzar
    una revisión (por ejemplo, después de un `.set()` con texto ya cargado,
    que no dispara eventos de teclado)."""
    textbox.tag_config(_TAG_ORTOGRAFIA, underline=True, foreground="#c0392b")
    trabajo_pendiente = {"id": None}

    def _revisar(_evento=None):
        if trabajo_pendiente["id"] is not None:
            try:
                textbox.after_cancel(trabajo_pendiente["id"])
            except Exception:  # noqa: BLE001
                pass
        # Con debounce: revisar en cada tecla en un campo largo se siente
        # pesado en los equipos viejos de la sede. Medio segundo de pausa
        # alcanza para que no se note el retraso, pero tampoco quede
        # revisando en cada letra mientras alguien todavía está escribiendo.
        trabajo_pendiente["id"] = textbox.after(500, _escanear)

    def _autocapitalizar():
        """Pone en mayúscula la primera letra del texto y la que sigue a
        cada punto/cierre de pregunta o exclamación — sin esto, buena parte
        de las devoluciones de planeaciones e informes son justo por esto."""
        texto = textbox.get("1.0", "end-1c")
        posiciones = [
            m.start(1) for m in _PATRON_INICIO_ORACION.finditer(texto) if texto[m.start(1)].islower()
        ]
        if not posiciones:
            return
        cursor = textbox.index(tk.INSERT)
        for pos in posiciones:
            idx = f"1.0+{pos}c"
            textbox.delete(idx, f"{idx}+1c")
            textbox.insert(idx, texto[pos].upper())
        textbox.mark_set(tk.INSERT, cursor)

    def _escanear():
        trabajo_pendiente["id"] = None
        try:
            if not textbox.winfo_exists():
                return
        except Exception:  # noqa: BLE001 — el campo ya no existe
            return
        _autocapitalizar()
        if not ortografia.disponible():
            return
        textbox.tag_remove(_TAG_ORTOGRAFIA, "1.0", "end")
        texto = textbox.get("1.0", "end")
        for coincidencia in _PATRON_PALABRA.finditer(texto):
            palabra = coincidencia.group(0)
            if len(palabra) < 3 or ortografia.es_correcta(palabra):
                continue
            textbox.tag_add(
                _TAG_ORTOGRAFIA, f"1.0+{coincidencia.start()}c", f"1.0+{coincidencia.end()}c"
            )

    def _clic_derecho(evento):
        indice = textbox.index(f"@{evento.x},{evento.y}")
        rango = None
        limites = textbox.tag_ranges(_TAG_ORTOGRAFIA)
        for i in range(0, len(limites), 2):
            inicio, fin = limites[i], limites[i + 1]
            if textbox.compare(inicio, "<=", indice) and textbox.compare(indice, "<", fin):
                rango = (inicio, fin)
                break
        if rango is None:
            return None  # clic no fue sobre una palabra marcada: no interceptar nada

        inicio, fin = rango
        palabra = textbox.get(inicio, fin)
        menu = tk.Menu(textbox, tearoff=0)
        for sugerida in ortografia.sugerencias(palabra):
            menu.add_command(
                label=sugerida,
                command=lambda s=sugerida, i=inicio, f=fin: _reemplazar(i, f, s),
            )
        if menu.index("end") is None:
            menu.add_command(label="(sin sugerencias)", state="disabled")
        menu.tk_popup(evento.x_root, evento.y_root)
        return "break"

    def _reemplazar(inicio, fin, nueva):
        textbox.delete(inicio, fin)
        textbox.insert(inicio, nueva)
        _revisar()

    textbox.bind("<KeyRelease>", _revisar, add="+")
    textbox.bind("<Button-3>", _clic_derecho, add="+")
    ortografia.cargar_en_segundo_plano()
    # Sin revisión inicial automática: quien llama decide cuándo tiene
    # sentido (por ejemplo, CampoConInstruccion no debe revisar mientras
    # todavía se ve el placeholder de instrucciones, no texto real).
    return _revisar


def miniatura_ctk(ruta_archivo: str, tamano: int = 44) -> ctk.CTkImage | None:
    """Miniatura cuadrada de una foto elegida, para mostrar junto al nombre
    del archivo en vez de solo el texto — así se ve qué foto es antes de
    guardar, sin tener que abrirla aparte. None si el archivo no se puede
    leer como imagen (no debería pasar con lo que ya filtra el selector de
    archivos, pero mejor no reventar la pantalla por una miniatura)."""
    try:
        with Image.open(ruta_archivo) as original:
            copia = original.convert("RGB")
            copia.thumbnail((tamano, tamano))
            fondo = Image.new("RGB", (tamano, tamano), "#dddddd")
            fondo.paste(copia, ((tamano - copia.width) // 2, (tamano - copia.height) // 2))
        return ctk.CTkImage(light_image=fondo, dark_image=fondo, size=(tamano, tamano))
    except Exception:  # noqa: BLE001 — sin miniatura la fila igual funciona
        return None


def imagen_desde_base64(base64_str: str, ancho_max: int, alto_max: int) -> ctk.CTkImage | None:
    """Una foto traída del backend (base64), redimensionada para entrar en
    un cuadro sin recortarla ni deformarla — a diferencia de `miniatura_ctk`,
    que sí recorta a cuadrado para un ícono chico, acá se preserva la
    proporción original de la foto real."""
    try:
        data = base64.b64decode(base64_str)
        with Image.open(io.BytesIO(data)) as original:
            copia = original.convert("RGB")
            copia.thumbnail((ancho_max, alto_max))
            copia.load()
        return ctk.CTkImage(light_image=copia, dark_image=copia, size=copia.size)
    except Exception:  # noqa: BLE001 — sin poder mostrarla, se avisa aparte
        return None


def contar_palabras(texto: str) -> int:
    return len([p for p in texto.split() if p])


class BarraDeSubida(ctk.CTkFrame):
    """Progreso real de una subida a Apps Script: mientras se mandan los
    bytes del cuerpo, una barra con el porcentaje real (no una animación
    que solo simula que algo pasa); al llegar al 100% el envío ya terminó
    pero el servidor puede seguir un rato armando carpetas en Drive, así
    que ahí se pasa a la animación de "sigue trabajando" — para que la
    pantalla nunca se vea congelada, ni durante la subida ni después.

    Uso: `iniciar()` antes de arrancar, `actualizar(enviado, total, texto)`
    en cada `reportar` de en_segundo_plano_con_progreso, y `detener()` al
    terminar (con éxito o con error)."""

    def __init__(self, master):
        # height=1 explícito: CTkFrame por defecto reserva 200px de alto
        # aunque esté vacía y sin empacar nada adentro (sale así hasta que
        # `iniciar()` empaqueta la barra/el label) — invisible al fondo de
        # un formulario scrollable, pero rompe cualquier panel de alto fijo
        # que la contenga (ver «Antes de guardar» en planeacion_screen.py).
        super().__init__(master, fg_color="transparent", height=1)
        self.barra = ctk.CTkProgressBar(self)
        self.barra.set(0)
        self.label = ctk.CTkLabel(self, text="", text_color="gray", font=ctk.CTkFont(size=11))
        self._cargando: Cargando | None = None
        self._esperando = False

    def iniciar(self, texto: str = "Subiendo..."):
        self._esperando = False
        if self._cargando is not None:
            self._cargando.detener()
            self._cargando.pack_forget()
        self.barra.set(0)
        self.barra.pack(fill="x", pady=(4, 2))
        self.label.configure(text=texto)
        self.label.pack()

    def actualizar(self, enviado: int, total: int, texto: str = "Subiendo"):
        if self._esperando:
            return
        fraccion = (enviado / total) if total else 0
        if fraccion >= 1:
            self._pasar_a_esperando()
            return
        self.barra.set(fraccion)
        mb = lambda b: b / 1_000_000  # noqa: E731 — solo para el texto de abajo
        self.label.configure(
            text=f"{texto}... {int(fraccion * 100)}% ({mb(enviado):.1f} de {mb(total):.1f} MB)"
        )

    def _pasar_a_esperando(self):
        self._esperando = True
        self.barra.pack_forget()
        self.label.pack_forget()
        if self._cargando is None:
            self._cargando = Cargando(self, texto="El servidor está terminando de guardar...")
        else:
            self._cargando.configurar_texto("El servidor está terminando de guardar...")
            self._cargando.iniciar()
        self._cargando.pack()

    def detener(self):
        self._esperando = False
        self.barra.pack_forget()
        self.label.pack_forget()
        if self._cargando is not None:
            self._cargando.detener()
            self._cargando.pack_forget()


class CampoConContador(ctk.CTkFrame):
    """Textbox multilínea + contador de palabras en vivo que se pone verde
    a partir de MIN_PALABRAS (spec sección 6: "contador en vivo mientras el
    docente escribe").

    `pregunta=True` es para las etiquetas que en realidad son la pregunta
    entera (observaciones, avances, informe mensual...): esas van en texto
    normal envuelto en varias líneas, como venían — pasarlas por
    `campo_label` (mayúscula, una sola línea) las volvería ilegibles. El
    resto (Objetivo, "Qué pasó en este momento"...) son etiquetas cortas de
    campo, como en el mockup: mayúscula chica y gris, con el contador a la
    derecha en la misma fila en vez de debajo del cuadro de texto."""

    def __init__(
        self, master, etiqueta: str, alto: int = 90, minimo: int = MIN_PALABRAS,
        pregunta: bool = False, **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.minimo = minimo
        self._pregunta = pregunta

        if pregunta:
            # Etiqueta larga (la pregunta entera): en su propia línea, texto
            # normal envuelto — como venía. El contador va debajo del cuadro,
            # que es donde entra sin achicarle el ancho a la pregunta.
            ctk.CTkLabel(self, text=etiqueta, anchor="w", justify="left", wraplength=560).pack(fill="x")
        else:
            encabezado = ctk.CTkFrame(self, fg_color="transparent")
            encabezado.pack(fill="x")
            campo_label(encabezado, etiqueta).pack(side="left")
            self.contador_label = ctk.CTkLabel(encabezado, text="", font=ctk.CTkFont(size=11))
            self.contador_label.pack(side="right")

        self.textbox = ctk.CTkTextbox(self, height=alto)
        self.textbox.pack(fill="x", pady=(4, 0))
        self.textbox.bind("<KeyRelease>", lambda _e: self._actualizar_contador())
        self._revisar_ortografia = aplicar_corrector_ortografico(self.textbox)

        if pregunta:
            self.contador_label = ctk.CTkLabel(self, text="", anchor="e", font=ctk.CTkFont(size=11))
            self.contador_label.pack(fill="x")

        self._actualizar_contador()

    def _actualizar_contador(self):
        n = contar_palabras(self.get())
        color = "#2fa84f" if n >= self.minimo else "#c0392b"
        self.contador_label.configure(text=f"{n} palabras (mínimo {self.minimo})", text_color=color)

    def get(self) -> str:
        return self.textbox.get("1.0", "end").strip()

    def set(self, texto: str):
        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", texto)
        self._actualizar_contador()
        self._revisar_ortografia()

    def es_valido(self) -> bool:
        return contar_palabras(self.get()) >= self.minimo


class CampoConInstruccion(ctk.CTkFrame):
    """Campo de texto con la pregunta arriba y la instrucción como marca de
    agua adentro: el texto gris de guía desaparece al escribir y vuelve si el
    campo queda vacío. Así el docente ve qué se espera sin que la instrucción
    se confunda con su respuesta.

    Con `minimo` muestra además el contador en vivo de CampoConContador,
    para las preguntas del informe mensual que también piden un mínimo de
    palabras."""

    def __init__(self, master, etiqueta: str, instruccion: str = "", alto: int = 70, minimo: int = 0):
        super().__init__(master, fg_color="transparent")
        self.minimo = minimo
        ctk.CTkLabel(self, text=etiqueta, anchor="w", justify="left", wraplength=560).pack(
            fill="x", pady=(10, 0)
        )
        self.instruccion = instruccion
        self.textbox = ctk.CTkTextbox(self, height=alto)
        self.textbox.pack(fill="x", pady=(2, 0))
        self._color_normal = self.textbox.cget("text_color")
        self._placeholder = False
        self.textbox.bind("<FocusIn>", self._al_entrar)
        self.textbox.bind("<FocusOut>", self._al_salir)
        self.textbox.bind("<KeyRelease>", lambda _e: self._actualizar_contador())
        # Sin revisión al construir: acá abajo todavía se pone el
        # placeholder de instrucciones, y no tiene sentido corregirle la
        # ortografía a eso — recién se revisa cuando hay texto real
        # (ver set() y _al_entrar/_al_salir).
        self._revisar_ortografia = aplicar_corrector_ortografico(self.textbox)

        if self.minimo:
            self.contador_label = ctk.CTkLabel(self, text="", anchor="e", font=ctk.CTkFont(size=11))
            self.contador_label.pack(fill="x")

        self._poner_placeholder()
        self._actualizar_contador()

    def _actualizar_contador(self):
        if not self.minimo:
            return
        n = contar_palabras(self.get())
        color = "#2fa84f" if n >= self.minimo else "#c0392b"
        self.contador_label.configure(text=f"{n} palabras (mínimo {self.minimo})", text_color=color)

    def _poner_placeholder(self):
        if self.instruccion:
            self.textbox.delete("1.0", "end")
            self.textbox.insert("1.0", self.instruccion)
            self.textbox.configure(text_color="gray")
            self._placeholder = True

    def _al_entrar(self, _e=None):
        if self._placeholder:
            self.textbox.delete("1.0", "end")
            self.textbox.configure(text_color=self._color_normal)
            self._placeholder = False

    def _al_salir(self, _e=None):
        if not self.textbox.get("1.0", "end").strip():
            self._poner_placeholder()
            self.textbox.tag_remove(_TAG_ORTOGRAFIA, "1.0", "end")
            self._actualizar_contador()

    def get(self) -> str:
        return "" if self._placeholder else self.textbox.get("1.0", "end").strip()

    def set(self, texto: str):
        if texto:
            self.textbox.delete("1.0", "end")
            self.textbox.configure(text_color=self._color_normal)
            self.textbox.insert("1.0", texto)
            self._placeholder = False
            self._revisar_ortografia()
        else:
            self._poner_placeholder()
            self.textbox.tag_remove(_TAG_ORTOGRAFIA, "1.0", "end")


def campo_label(padre, texto: str) -> ctk.CTkLabel:
    """Etiqueta de campo corto de formulario (Fecha, Curso, Horas...),
    como en el mockup: mayúscula, chica, gris, semi-negrita — muy distinta
    de un CTkLabel liso, que es lo que usaba toda la app hasta ahora. No
    la usan las preguntas largas (objetivo, observaciones, narrativa del
    informe): esas van en letra normal, ver CampoConContador/
    CampoConInstruccion — la mayúscula ahí volvería ilegible un párrafo
    entero."""
    return ctk.CTkLabel(
        padre, text=texto.upper(), font=tema.fuente(11, "bold"),
        text_color=tema.TEXTO_MUTED, anchor="w",
    )


def pildora(padre, texto: str, texto_color: str, fondo_color: str) -> ctk.CTkLabel:
    """Cápsula con fondo teñido de su propio color (mínimo/máximo de fotos,
    minutos completos, presentes en asistencia...) — a diferencia de
    `chip()`, que usa siempre el mismo fondo gris parejo sea cual sea el
    color del texto."""
    return ctk.CTkLabel(
        padre, text=f"  {texto}  ", text_color=texto_color, font=tema.fuente(12, "bold"),
        corner_radius=999, fg_color=fondo_color,
    )


def chip(padre, texto: str, color: str) -> ctk.CTkLabel:
    """Etiqueta de estado tipo cápsula (rediseño). Antes vivía duplicada
    como `_chip` adentro de dashboard_screen.py; queda acá para que
    cualquier pantalla nueva la use igual sin repetirla."""
    etiqueta = ctk.CTkLabel(
        padre, text=f"  {texto}  ", text_color=color, font=tema.fuente(12),
        corner_radius=6, fg_color=("gray92", "gray20"),
    )
    etiqueta.pack(side="left", padx=(0, 6))
    return etiqueta


class PestanasPildora(ctk.CTkFrame):
    """Barra de sub-pestañas en pastillas sueltas, como en el mockup
    («Horas en sede / Mis planeaciones / Horas externas», «Planeaciones /
    Informes / Dashboard mensual»): la activa es una pastilla verde oscuro
    sólida con texto blanco, las inactivas son pastillas blancas con borde
    y texto gris — muy distinto del CTkSegmentedButton de CTkTabview, que
    dibuja los segmentos pegados entre sí en un solo bloque con el acento
    dorado del menú lateral.

    Misma superficie mínima que CTkTabview (`add`, `tab`, `get`, `set`,
    `command`) para poder reemplazarlo sin rehacer cada pantalla que lo usa."""

    def __init__(self, master, command: Callable[[str], None] | None = None):
        super().__init__(master, fg_color="transparent")
        self._command = command
        self._botones: dict[str, ctk.CTkButton] = {}
        self._tabs: dict[str, ctk.CTkFrame] = {}
        self._actual = ""

        self._fila_botones = ctk.CTkFrame(self, fg_color="transparent")
        self._fila_botones.pack(fill="x")
        self._contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self._contenedor.pack(fill="both", expand=True, pady=(14, 0))

    def add(self, nombre: str) -> ctk.CTkFrame:
        boton = ctk.CTkButton(
            self._fila_botones, text=nombre, corner_radius=18, height=36,
            fg_color=tema.FONDO_TARJETA, hover_color=tema.FONDO_CONTENIDO,
            text_color=tema.TEXTO_MUTED, border_width=1, border_color=tema.BORDE_TARJETA,
            font=tema.fuente(13, "bold"), command=lambda n=nombre: self._al_clicar(n),
        )
        boton.pack(side="left", padx=(0, 10))
        self._botones[nombre] = boton
        marco = ctk.CTkFrame(self._contenedor, fg_color="transparent")
        self._tabs[nombre] = marco
        if len(self._tabs) == 1:
            self.set(nombre)  # CTkTabview deja la primera pestaña agregada activa de entrada
        return marco

    def tab(self, nombre: str) -> ctk.CTkFrame:
        return self._tabs[nombre]

    def get(self) -> str:
        return self._actual

    def set(self, nombre: str):
        if nombre not in self._tabs or nombre == self._actual:
            return
        if self._actual in self._tabs:
            self._tabs[self._actual].pack_forget()
        self._tabs[nombre].pack(fill="both", expand=True)
        self._actual = nombre
        for otro, boton in self._botones.items():
            activo = otro == nombre
            boton.configure(
                fg_color=tema.VERDE_OSCURO if activo else tema.FONDO_TARJETA,
                hover_color=tema.VERDE_OSCURO_ACTIVO if activo else tema.FONDO_CONTENIDO,
                text_color=tema.BLANCO if activo else tema.TEXTO_MUTED,
                border_width=0 if activo else 1,
            )

    def _al_clicar(self, nombre: str):
        # A diferencia de `set()` (para dejar todo armado en __init__ sin
        # disparar el callback antes de que la pantalla dueña esté lista),
        # un clic real sí avisa — como CTkTabview con su `command`, que se
        # llama sin argumentos: quien lo escucha consulta `.get()` para
        # saber cuál quedó activa (así están escritos todos los
        # `_al_cambiar_pestana` que ya existían antes de este widget).
        cambio = nombre != self._actual
        self.set(nombre)
        if cambio and self._command is not None:
            self._command()


class TarjetaResumen(ctk.CTkFrame):
    """Tarjeta de stat del dashboard (rediseño): ícono, número grande y
    etiqueta debajo, con un acento de color propio por tarjeta — como en
    el mockup, donde cada tarjeta trae su propio color de ícono."""

    def __init__(self, master, icono: str, numero, etiqueta: str, color_acento: str = tema.VERDE):
        super().__init__(
            master, fg_color=tema.FONDO_TARJETA, corner_radius=10,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        circulo = ctk.CTkLabel(
            self, text=icono, width=40, height=40, corner_radius=20,
            fg_color=color_acento, text_color=tema.BLANCO, font=tema.fuente(16),
        )
        circulo.pack(anchor="w", padx=16, pady=(16, 8))

        self.numero_label = ctk.CTkLabel(
            self, text=str(numero), font=tema.FUENTE_NUMERO_TARJETA(), text_color=tema.TEXTO_OSCURO,
            anchor="w",
        )
        self.numero_label.pack(fill="x", padx=16)

        ctk.CTkLabel(
            self, text=etiqueta, font=tema.FUENTE_ETIQUETA_TARJETA(), text_color=tema.GRIS,
            anchor="w", justify="left", wraplength=140,
        ).pack(fill="x", padx=16, pady=(0, 16))

    def actualizar(self, numero):
        self.numero_label.configure(text=str(numero))


def avatar_iniciales(
    padre, nombre: str, tamano: int = 40, color: str = tema.DORADO_ACENTO,
    text_color: str = tema.VERDE_OSCURO,
) -> ctk.CTkFrame:
    """Círculo con las iniciales de una persona (primera letra de las dos
    primeras palabras del nombre), para la barra lateral y las tarjetas de
    Usuarios.

    Envuelto en un `CTkFrame` con `pack_propagate(False)` en vez de un
    `CTkLabel` suelto con `width`/`height`: un `CTkLabel` se expande para
    que quepan las dos letras del texto y el círculo termina ovalado
    (probado a ojo con "AT"/"MA" — ver captura de la sesión). El frame sí
    respeta el tamaño fijo pase lo que pase adentro."""
    palabras = [p for p in nombre.split() if p]
    iniciales = "".join(p[0] for p in palabras[:2]).upper() or "?"
    circulo = ctk.CTkFrame(
        padre, width=tamano, height=tamano, corner_radius=tamano // 2, fg_color=color,
    )
    circulo.pack_propagate(False)
    ctk.CTkLabel(
        circulo, text=iniciales, text_color=text_color, font=tema.fuente(13, "bold"),
    ).place(relx=0.5, rely=0.5, anchor="center")
    return circulo


class Acordeon(ctk.CTkFrame):
    """Sección colapsable: encabezado clicleable (título + flecha) y un
    frame de contenido que se muestra/oculta. Reemplaza el patrón manual
    de "diccionario de booleanos + flecha a mano" que varias pantallas
    (momentos de clase, gestión institucional del informe) reinventaban
    cada una por su cuenta.

    Uso: `ac = Acordeon(padre, "Momento inicial"); algo.pack(in_=ac.contenido)`.
    `abierto` decide el estado inicial; `en_cambiar(abierto: bool)` es un
    callback opcional para cuando quien llama necesita reaccionar al
    abrir/cerrar (por ejemplo, revisar ortografía recién al mostrar)."""

    def __init__(
        self, master, titulo: str, abierto: bool = False,
        en_cambiar: Callable[[bool], None] | None = None,
        encabezado_extra: Callable[[ctk.CTkFrame], None] | None = None,
        prefijo: Callable[[ctk.CTkFrame], None] | None = None,
        wraplength_titulo: int | None = None,
    ):
        super().__init__(
            master, fg_color=tema.FONDO_TARJETA, corner_radius=14,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        self._abierto = abierto
        self._en_cambiar = en_cambiar

        # Transparente (no el verde-gris tenue del mockup): CTk no redondea
        # una esquina sola, y un fondo propio acá asomaría cuadrado por
        # detrás de las esquinas redondeadas de la tarjeta que lo contiene.
        self.encabezado = ctk.CTkFrame(self, fg_color="transparent", cursor="hand2")
        self.encabezado.pack(fill="x")
        if prefijo is not None:
            # El prefijo (una insignia numerada, por ejemplo) se hace cargo
            # del margen izquierdo de 16px — si el título pusiera el suyo
            # además, quedarían los dos sumados.
            prefijo(self.encabezado)
        # `wraplength_titulo`: sin esto, un título largo (una pregunta
        # entera, no una etiqueta corta como "Momento inicial") le pide al
        # packer su ancho natural completo en una sola línea — eso puede
        # superar el ancho disponible y dejar sin espacio a la flecha y al
        # `encabezado_extra` (el contador de palabras), que se arman
        # DESPUÉS del título y quedan aplastados o cortados. Con
        # wraplength el título envuelve en vez de exigir todo ese ancho.
        self.titulo_label = ctk.CTkLabel(
            self.encabezado, text=titulo, font=tema.fuente(14, "bold"), anchor="w",
            justify="left", wraplength=wraplength_titulo or 0,
        )
        padx_titulo = (0, 8) if prefijo is not None else (16, 8)
        self.titulo_label.pack(side="left", fill="x", expand=True, padx=padx_titulo, pady=12)
        # La flecha se empaqueta ANTES que `encabezado_extra`: en el
        # gestor de `pack`, cada widget nuevo del lado "right" se ubica a
        # la izquierda de los ya empacados de ese lado — así lo que agregue
        # `encabezado_extra` (minutos, contador de palabras...) queda a la
        # izquierda de la flecha, como en el mockup, y no al revés.
        self.flecha_label = ctk.CTkLabel(
            self.encabezado, text="", text_color=tema.TEXTO_MUTED, font=tema.fuente(11), width=16,
        )
        self.flecha_label.pack(side="right", padx=(0, 16))
        if encabezado_extra is not None:
            encabezado_extra(self.encabezado)

        self.contenido = ctk.CTkFrame(self, fg_color="transparent")

        for widget in (self.encabezado, self.titulo_label, self.flecha_label):
            widget.bind("<Button-1>", lambda _e: self.alternar())

        self._actualizar()

    def alternar(self):
        self._abierto = not self._abierto
        self._actualizar()
        if self._en_cambiar is not None:
            self._en_cambiar(self._abierto)

    def abrir(self):
        if not self._abierto:
            self.alternar()

    def cerrar(self):
        if self._abierto:
            self.alternar()

    def _actualizar(self):
        self.flecha_label.configure(text="▲" if self._abierto else "▼")
        if self._abierto:
            self.contenido.pack(fill="x", padx=16, pady=(0, 16))
        else:
            self.contenido.pack_forget()

    def configurar_titulo(self, titulo: str):
        self.titulo_label.configure(text=titulo)


class CampoBusqueda(ctk.CTkFrame):
    """Entry de búsqueda con ícono de lupa que llama a `on_cambiar(texto)`
    con un pequeño debounce (misma idea que el corrector ortográfico: no
    refiltrar en cada tecla, esperar una pausa corta) — para filtrar en el
    cliente listas que la pantalla ya cargó completas en memoria, sin ida
    al backend."""

    _DEBOUNCE_MS = 300
    _ALTO = 38

    def __init__(self, master, placeholder: str, on_cambiar: Callable[[str], None], ancho: int = 260):
        super().__init__(
            master, fg_color=tema.FONDO_TARJETA, corner_radius=self._ALTO // 2,
            border_width=1, border_color=tema.BORDE_TARJETA, width=ancho, height=self._ALTO,
        )
        # Sin alto fijo + pack_propagate(False) el frame crece con el
        # contenido (entry + label) y con corner_radius=999 termina como
        # un óvalo gigante en vez de una píldora angosta — visto a ojo con
        # el harness de captura de pantalla de la sesión.
        self.pack_propagate(False)
        self._on_cambiar = on_cambiar
        self._pendiente_id = None

        ctk.CTkLabel(
            self, text="🔎", font=tema.fuente(12), text_color=tema.TEXTO_MUTED, width=18,
        ).pack(side="left", padx=(12, 4))
        self.entry = ctk.CTkEntry(
            self, placeholder_text=placeholder, fg_color="transparent", border_width=0,
        )
        self.entry.pack(side="left", fill="both", expand=True, padx=(0, 12))
        self.entry.bind("<KeyRelease>", self._al_teclear)

    def _al_teclear(self, _evento=None):
        if self._pendiente_id is not None:
            try:
                self.after_cancel(self._pendiente_id)
            except Exception:  # noqa: BLE001
                pass
        self._pendiente_id = self.after(self._DEBOUNCE_MS, self._disparar)

    def _disparar(self):
        self._pendiente_id = None
        self._on_cambiar(self.entry.get().strip())

    def get(self) -> str:
        return self.entry.get().strip()

    def limpiar(self):
        self.entry.delete(0, "end")
        self._on_cambiar("")


class Tabla(ctk.CTkFrame):
    """Tabla simple con encabezado fijo y filas alineadas por columna
    (rediseño) — reemplaza de a poco las listas tipo "dos zonas con pack"
    que usan hoy Planeaciones/Revisar/etc, donde nada queda alineado en
    columnas reales. Cada celda vive en su propio frame transparente
    (grid-eado) para poder usar pack() adentro sin chocar con el grid()
    del resto de la tabla — Tkinter no deja mezclar los dos gestores de
    geometría sobre los mismos hijos de un mismo padre."""

    def __init__(self, master, columnas: list[str], anchos: list[int] | None = None):
        super().__init__(
            master, fg_color=tema.FONDO_TARJETA, corner_radius=10,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        anchos = anchos or [1] * len(columnas)
        for i, peso in enumerate(anchos):
            self.grid_columnconfigure(i, weight=peso)

        for i, titulo in enumerate(columnas):
            ctk.CTkLabel(
                self, text=titulo.upper(), font=tema.fuente(11, "bold"), text_color=tema.GRIS,
                anchor="w",
            ).grid(row=0, column=i, sticky="w", padx=12, pady=(12, 6))

        self._fila_siguiente = 1

    def agregar_fila(
        self, valores: list[str], estado: tuple[str, str] | None = None,
        boton: tuple[str, Callable[[], None]] | None = None,
    ):
        """`estado` es (texto, color): si se pasa, la ÚLTIMA columna se
        pinta como chip en vez de texto plano. `boton` es (texto, comando):
        si se pasa, agrega UNA celda más al final de la fila con un botón
        —la tabla tiene que haberse creado con una columna (aunque sea con
        título vacío) de más para que quede alineado con el resto."""
        n = len(valores)
        for i, valor in enumerate(valores):
            celda = ctk.CTkFrame(self, fg_color="transparent")
            celda.grid(row=self._fila_siguiente, column=i, sticky="w", padx=12, pady=6)
            if estado is not None and i == n - 1:
                chip(celda, estado[0], estado[1])
            else:
                ctk.CTkLabel(
                    celda, text=str(valor), font=tema.fuente(12), text_color=tema.TEXTO_OSCURO,
                ).pack(anchor="w")
        if boton is not None:
            texto, comando = boton
            celda = ctk.CTkFrame(self, fg_color="transparent")
            celda.grid(row=self._fila_siguiente, column=n, sticky="w", padx=12, pady=6)
            ctk.CTkButton(
                celda, text=texto, command=comando, width=90, height=26,
                fg_color="transparent", border_width=1, text_color=tema.TEXTO_OSCURO,
                hover_color=tema.FONDO_CONTENIDO, font=tema.fuente(11),
            ).pack(anchor="w")
        self._fila_siguiente += 1
