"""Widgets chicos reutilizables entre pantallas."""

from __future__ import annotations

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
        super().__init__(master, fg_color="transparent")
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
    docente escribe")."""

    def __init__(self, master, etiqueta: str, alto: int = 90, minimo: int = MIN_PALABRAS, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.minimo = minimo

        ctk.CTkLabel(self, text=etiqueta, anchor="w").pack(fill="x")
        self.textbox = ctk.CTkTextbox(self, height=alto)
        self.textbox.pack(fill="x", pady=(2, 0))
        self.textbox.bind("<KeyRelease>", lambda _e: self._actualizar_contador())
        self._revisar_ortografia = aplicar_corrector_ortografico(self.textbox)

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

    def agregar_fila(self, valores: list[str], estado: tuple[str, str] | None = None):
        """`estado` es (texto, color): si se pasa, la ÚLTIMA columna se
        pinta como chip en vez de texto plano."""
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
        self._fila_siguiente += 1
