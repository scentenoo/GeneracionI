"""Pantalla de login — punto de partida para que Generación-I la termine de
diseñar (logo, eslogan, frases motivadoras elegidas por votación, ver spec
sección 8). Funcionalmente ya llama al backend real; lo que falta es
estética y pulir la experiencia.

El botón arranca deshabilitado hasta que el chequeo de versión que corre
de fondo confirme que la app está al día (ver main.py). Mientras se espera
—verificar versión, ingresar— se muestra la animación de «Cargando» en vez
de un texto quieto: con la latencia de Apps Script, un texto fijo parece
que la app se colgó.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

import api_client
from ui.cargando import Cargando
from ui.tareas import en_segundo_plano


class LoginScreen(ctk.CTkFrame):
    def __init__(self, master, on_login_exitoso: Callable[[dict], None]):
        super().__init__(master)
        self.on_login_exitoso = on_login_exitoso

        ctk.CTkLabel(self, text="Generación-I", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(40, 10))
        ctk.CTkLabel(self, text="Planeaciones y asistencia").pack(pady=(0, 30))

        self.usuario_entry = ctk.CTkEntry(self, placeholder_text="Usuario", width=260)
        self.usuario_entry.pack(pady=8)

        self.password_entry = ctk.CTkEntry(self, placeholder_text="Contraseña", show="*", width=260)
        self.password_entry.pack(pady=8)
        self.password_entry.bind("<Return>", lambda _e: self._intentar_login())

        self.boton = ctk.CTkButton(
            self, text="Ingresar", command=self._intentar_login, width=260, state="disabled"
        )
        self.boton.pack(pady=20)

        # Animación de "estoy trabajando". Arranca visible: lo primero que
        # pasa es el chequeo de versión, que también tarda.
        self.cargando = Cargando(self, texto="Verificando versión...")
        self.cargando.pack(pady=(0, 6))

        self.error_label = ctk.CTkLabel(self, text="", text_color="#c0392b")
        self.error_label.pack(pady=(4, 0))

        # Aviso de versión nueva no obligatoria: aparece bajo el botón, sin
        # tapar el login. Se llena recién si hay algo que avisar.
        self.aviso_frame = ctk.CTkFrame(self, fg_color="transparent")

    def habilitar(self, aviso: str | None = None, link: str | None = None):
        """La llama App cuando el chequeo de versión terminó bien.

        Con `aviso` hay una versión más nueva que no es obligatoria: se
        deja entrar igual, pero se muestra el mensaje y, si hay, un botón
        para descargar el instalador nuevo.
        """
        self.cargando.detener()
        self.cargando.pack_forget()
        self.boton.configure(state="normal")
        self.error_label.configure(text="")
        self.usuario_entry.focus_set()

        for w in self.aviso_frame.winfo_children():
            w.destroy()
        if aviso:
            self.aviso_frame.pack(pady=(0, 10))
            ctk.CTkLabel(
                self.aviso_frame, text=aviso, text_color="#8A6114",
                wraplength=280, justify="center",
            ).pack()
            if link:
                import webbrowser

                ctk.CTkButton(
                    self.aviso_frame, text="Descargar la versión nueva", width=220,
                    fg_color="transparent", border_width=1,
                    command=lambda: webbrowser.open(link),
                ).pack(pady=(6, 0))
        else:
            self.aviso_frame.pack_forget()

    def _intentar_login(self):
        usuario = self.usuario_entry.get().strip()
        password = self.password_entry.get()
        if not usuario or not password:
            self.error_label.configure(text="Completá usuario y contraseña", text_color="#c0392b")
            return

        self.boton.configure(state="disabled", text="Ingresando...")
        self.error_label.configure(text="")
        # Animación mientras espera la respuesta del backend.
        self.cargando.configurar_texto("Ingresando...")
        self.cargando.iniciar()
        self.cargando.pack(pady=(0, 6))

        en_segundo_plano(
            self,
            lambda: api_client.login(usuario, password),
            self._al_entrar,
            self._al_fallar,
        )

    def _al_entrar(self, sesion):
        self.cargando.detener()
        self.on_login_exitoso(sesion)

    def _al_fallar(self, exc):
        self.cargando.detener()
        self.cargando.pack_forget()
        self.boton.configure(state="normal", text="Ingresar")
        self.error_label.configure(text=str(exc), text_color="#c0392b")
