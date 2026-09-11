"""Pantalla de login (rediseño: landing de dos paneles, calcado lo más
cerca posible del mockup que eligieron los niños — logo, frase de marca en
dos tonos, círculos decorativos, campos redondeados). Funcionalmente no
cambia nada de acá para abajo — solo el layout alrededor de los mismos
widgets.

El botón arranca deshabilitado hasta que el chequeo de versión que corre
de fondo confirme que la app está al día (ver main.py). Mientras se espera
—verificar versión, ingresar— se muestra la animación de «Cargando» en vez
de un texto quieto: con la latencia de Apps Script, un texto fijo parece
que la app se colgó.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable

import customtkinter as ctk
from PIL import Image

import api_client
from config import TEMPLATES_DIR
from ui import tema
from ui.cargando import Cargando
from ui.tareas import en_segundo_plano

_PUNTOS_DECORACION = (
    # (relx, rely, radio, color) — fijos, no aleatorios: si fueran al azar
    # saltarían de lugar cada vez que se redimensiona la ventana.
    (0.88, 0.10, 3, "dorado"),
    (0.78, 0.22, 2, "verde_claro"),
    (0.95, 0.30, 2, "dorado"),
    (0.10, 0.85, 2, "dorado"),
    (0.22, 0.93, 3, "verde_claro"),
    (0.06, 0.68, 2, "dorado"),
)


class LoginScreen(ctk.CTkFrame):
    def __init__(self, master, on_login_exitoso: Callable[[dict], None]):
        super().__init__(master, fg_color=tema.BLANCO, corner_radius=0)
        self.on_login_exitoso = on_login_exitoso
        self._mostrando_password = False

        self.grid_columnconfigure(0, weight=5)
        self.grid_columnconfigure(1, weight=6)
        self.grid_rowconfigure(0, weight=1)

        self._armar_panel_marca()
        self._armar_panel_formulario()

    # ------------------------------------------------------------------
    # Panel izquierdo: la marca (mismo espíritu que la landing del mockup)
    # ------------------------------------------------------------------

    def _armar_panel_marca(self):
        panel = ctk.CTkFrame(self, corner_radius=0, fg_color=tema.VERDE_OSCURO)
        panel.grid(row=0, column=0, sticky="nsew")

        fondo = tk.Canvas(panel, highlightthickness=0, bd=0, bg=tema.VERDE_OSCURO)
        fondo.place(relx=0, rely=0, relwidth=1, relheight=1)
        fondo.bind("<Configure>", self._dibujar_decoracion)
        self._canvas_decoracion = fondo

        # --- encabezado: logo ---
        bloque_marca = ctk.CTkFrame(panel, fg_color="transparent")
        bloque_marca.place(x=22, y=20)
        logo = self._cargar_logo()
        if logo is not None:
            ctk.CTkLabel(bloque_marca, image=logo, text="").pack(side="left")
            self._logo = logo  # referencia viva
        texto_marca = ctk.CTkFrame(bloque_marca, fg_color="transparent")
        texto_marca.pack(side="left", padx=(8, 0))
        ctk.CTkLabel(
            texto_marca, text="GENERACIÓN-I", font=tema.fuente(13, "bold"), text_color=tema.TEXTO_CLARO,
        ).pack(anchor="w")
        ctk.CTkLabel(
            texto_marca, text="Ciencia, tecnología e innovación", font=tema.fuente(9),
            text_color=tema.TEXTO_CLARO_APAGADO,
        ).pack(anchor="w")

        # --- centro: título en dos tonos + bajada ---
        contenido = ctk.CTkFrame(panel, fg_color="transparent")
        contenido.place(relx=0.09, rely=0.5, anchor="w")

        ctk.CTkLabel(
            contenido, text="Una generación que", font=tema.fuente(20, "bold"),
            text_color=tema.TEXTO_CLARO, anchor="w",
        ).pack(anchor="w")
        linea_resaltada = ctk.CTkFrame(contenido, fg_color="transparent")
        linea_resaltada.pack(anchor="w")
        ctk.CTkLabel(
            linea_resaltada, text="transforma", font=tema.fuente(20, "bold"), text_color=tema.DORADO,
        ).pack(side="left")
        ctk.CTkLabel(
            linea_resaltada, text=" la educación", font=tema.fuente(20, "bold"), text_color=tema.TEXTO_CLARO,
        ).pack(side="left")

        ctk.CTkLabel(
            contenido,
            text="Una plataforma para convertir ideas y clases\nen experiencias de aprendizaje.",
            font=tema.fuente(11), text_color=tema.TEXTO_CLARO_APAGADO, justify="left", anchor="w",
        ).pack(anchor="w", pady=(16, 0))

        # --- pie: tagline chica ---
        ctk.CTkLabel(
            panel, text="CIENCIA   ·   TECNOLOGÍA   ·   INNOVACIÓN", font=tema.fuente(10, "bold"),
            text_color=tema.TEXTO_CLARO_APAGADO,
        ).place(relx=0.09, rely=0.95, anchor="w")

    def _cargar_logo(self):
        ruta = TEMPLATES_DIR / "assets" / "logo_generacion_i_48.png"
        try:
            img = Image.open(ruta)
        except Exception:  # noqa: BLE001 — sin logo el login igual funciona
            return None
        return ctk.CTkImage(img, size=(40, 40))

    def _dibujar_decoracion(self, event=None):
        """Los anillos y puntitos sueltos del mockup — a mano alzada con
        Canvas, ya que no hay una imagen de fondo con licencia libre para
        esto. Puramente decorativo: si algo falla acá, no importa."""
        c = self._canvas_decoracion
        try:
            c.delete("deco")
            ancho = c.winfo_width()
            alto = c.winfo_height()
            if ancho < 10 or alto < 10:
                return
            verde_claro = tema.VERDE_OSCURO_ACTIVO
            colores = {"dorado": tema.DORADO, "verde_claro": verde_claro}

            # un par de anillos finos, como los del mockup
            c.create_oval(
                ancho * 0.50, -alto * 0.10, ancho * 1.25, alto * 0.55,
                outline=verde_claro, width=1, tags="deco",
            )
            c.create_oval(
                ancho * 0.62, alto * 0.02, ancho * 1.05, alto * 0.32,
                outline=tema.DORADO, width=1, tags="deco",
            )
            c.create_oval(
                -ancho * 0.20, alto * 0.62, ancho * 0.28, alto * 1.20,
                outline=verde_claro, width=1, tags="deco",
            )

            for relx, rely, radio, color in _PUNTOS_DECORACION:
                x, y = relx * ancho, rely * alto
                c.create_oval(
                    x - radio, y - radio, x + radio, y + radio,
                    fill=colores[color], outline="", tags="deco",
                )
        except Exception:  # noqa: BLE001 — puramente decorativo
            pass

    # ------------------------------------------------------------------
    # Panel derecho: formulario
    # ------------------------------------------------------------------

    def _armar_panel_formulario(self):
        panel = ctk.CTkFrame(self, fg_color=tema.BLANCO, corner_radius=0)
        panel.grid(row=0, column=1, sticky="nsew")

        contenido = ctk.CTkFrame(panel, fg_color="transparent")
        contenido.place(relx=0.5, rely=0.46, anchor="center")

        titulo = ctk.CTkFrame(contenido, fg_color="transparent")
        titulo.pack()
        ctk.CTkLabel(
            titulo, text="Bienvenido a ", font=tema.fuente(19, "bold"), text_color=tema.TEXTO_OSCURO,
        ).pack(side="left")
        ctk.CTkLabel(
            titulo, text="Generación-I", font=tema.fuente(19, "bold"), text_color=tema.VERDE,
        ).pack(side="left")

        ctk.CTkLabel(
            contenido,
            text="Gestione su planeación, cursos, horas\ne informes desde un solo lugar.",
            font=tema.fuente(12), text_color=tema.GRIS, justify="center",
        ).pack(pady=(4, 26))

        # --- usuario ---
        ctk.CTkLabel(
            contenido, text="Usuario", font=tema.fuente(11), text_color=tema.TEXTO_OSCURO, anchor="w",
        ).pack(fill="x", padx=2)
        self.usuario_entry = ctk.CTkEntry(
            contenido, placeholder_text="usuario", width=280, height=40, corner_radius=18,
        )
        self.usuario_entry.pack(pady=(4, 14))

        # --- contraseña (con "mostrar") ---
        ctk.CTkLabel(
            contenido, text="Contraseña", font=tema.fuente(11), text_color=tema.TEXTO_OSCURO, anchor="w",
        ).pack(fill="x", padx=2)

        fila_entrada_password = ctk.CTkFrame(contenido, fg_color="transparent")
        fila_entrada_password.pack(pady=(4, 4))
        self.password_entry = ctk.CTkEntry(
            fila_entrada_password, placeholder_text="contraseña", show="*", width=230, height=40, corner_radius=18,
        )
        self.password_entry.pack(side="left")
        self.password_entry.bind("<Return>", lambda _e: self._intentar_login())
        self._boton_mostrar = ctk.CTkButton(
            fila_entrada_password, text="Mostrar", width=44, height=28, font=tema.fuente(10),
            fg_color="transparent", text_color=tema.GRIS, hover_color=("gray90", "gray25"),
            command=self._alternar_mostrar_password,
        )
        self._boton_mostrar.pack(side="left", padx=(6, 0))

        self.boton = ctk.CTkButton(
            contenido, text="Ingresar  →", command=self._intentar_login, width=280, height=42,
            corner_radius=18, state="disabled", fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER,
            font=tema.fuente(13, "bold"),
        )
        self.boton.pack(pady=(18, 6))

        # Animación de "estoy trabajando". Arranca visible: lo primero que
        # pasa es el chequeo de versión, que también tarda.
        self.cargando = Cargando(contenido, texto="Verificando versión...")
        self.cargando.pack(pady=(0, 6))

        self.error_label = ctk.CTkLabel(contenido, text="", text_color=tema.ROJO)
        self.error_label.pack(pady=(4, 0))

        # Aviso de versión nueva no obligatoria: aparece bajo el botón, sin
        # tapar el login. Se llena recién si hay algo que avisar.
        self.aviso_frame = ctk.CTkFrame(contenido, fg_color="transparent")

        ctk.CTkLabel(
            contenido, text="✓  Acceso exclusivo para docentes y coordinadores académicos",
            font=tema.fuente(10), text_color=tema.GRIS,
        ).pack(pady=(18, 0))

    def _alternar_mostrar_password(self):
        self._mostrando_password = not self._mostrando_password
        self.password_entry.configure(show="" if self._mostrando_password else "*")
        self._boton_mostrar.configure(text="Ocultar" if self._mostrando_password else "Mostrar")

    # ------------------------------------------------------------------
    # Comportamiento (sin cambios respecto a la versión anterior)
    # ------------------------------------------------------------------

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
                self.aviso_frame, text=aviso, text_color=tema.AMBAR,
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
            self.error_label.configure(text="Complete usuario y contraseña", text_color=tema.ROJO)
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
        self.boton.configure(state="normal", text="Ingresar  →")
        self.error_label.configure(text=str(exc), text_color=tema.ROJO)
