"""Indicador animado de "estoy trabajando".

Con la latencia de Apps Script hay esperas de varios segundos (entrar,
abrir una pantalla, guardar). Un texto quieto —«Ingresando...»— da
sensación de colgado en los equipos lentos de la sede. Estos cuadraditos
que laten en onda dicen, sin palabras, que la app sigue andando.

Se dibuja sobre un Canvas de Tkinter y se anima con `after()` en el hilo
principal —que es lo único seguro en Tkinter—. `iniciar()` arranca la
animación y `detener()` la corta; al destruir el widget se corta sola.
"""

from __future__ import annotations

import math
import tkinter as tk

import customtkinter as ctk

VERDE = "#2fa84f"
INTERVALO_MS = 60
PERIODO_MS = 900  # cuánto tarda una onda en recorrer los cuadros


class Cargando(ctk.CTkFrame):
    def __init__(self, master, texto: str = "Cargando...", cuadros: int = 4, tamano: int = 16):
        super().__init__(master, fg_color="transparent")
        self._n = cuadros
        self._max = tamano
        self._min = max(4, tamano // 3)
        self._sep = 10
        self._t = 0.0
        self._job = None

        ancho = cuadros * tamano + (cuadros - 1) * self._sep
        self._canvas = tk.Canvas(
            self, width=ancho, height=tamano + 4,
            highlightthickness=0, bg=self._color_fondo(), bd=0,
        )
        self._canvas.pack(pady=(0, 8))

        self.label = ctk.CTkLabel(self, text=texto, text_color="gray")
        self.label.pack()

        # Si el widget se destruye (se cambió de pantalla), cortar la animación.
        self.bind("<Destroy>", lambda _e: self.detener())
        self.iniciar()

    def _color_fondo(self) -> str:
        """El fondo del Canvas tiene que igualar al de la ventana, si no se
        ve un recuadro. customtkinter guarda los colores como [claro, oscuro]."""
        fg = ctk.ThemeManager.theme["CTkFrame"]["fg_color"]
        idx = 0 if ctk.get_appearance_mode() == "Light" else 1
        color = fg[idx] if isinstance(fg, (list, tuple)) else fg
        return color

    def configurar_texto(self, texto: str):
        self.label.configure(text=texto)

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
        try:
            if not self._canvas.winfo_exists():
                return
        except Exception:  # noqa: BLE001
            return

        self._canvas.delete("all")
        alto = self._max + 4
        fase_por_cuadro = math.pi / 2  # el desfasaje entre cuadros arma la "onda"
        for i in range(self._n):
            # Cada cuadro late entre _min y _max, desfasado del anterior.
            onda = 0.5 + 0.5 * math.sin(2 * math.pi * self._t / PERIODO_MS - i * fase_por_cuadro)
            lado = self._min + (self._max - self._min) * onda
            cx = self._max / 2 + i * (self._max + self._sep)
            cy = alto / 2
            x0, y0 = cx - lado / 2, cy - lado / 2
            x1, y1 = cx + lado / 2, cy + lado / 2
            self._canvas.create_rectangle(x0, y0, x1, y1, fill=VERDE, outline="")
