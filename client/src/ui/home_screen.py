"""Dashboard post-login (rediseño). La navegación por secciones se movió a
la barra lateral persistente (ver barra_lateral.py) — esta pantalla ahora es
puro contenido: saludo, tarjetas con el resumen del mes y las planeaciones
más recientes.
"""

from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

import api_client
from services import date_utils
from services.avisos import texto_devoluciones
from ui import tema
from ui.tareas import en_segundo_plano
from ui.widgets import Tabla, TarjetaResumen, pildora


class HomeScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict):
        super().__init__(master, fg_color="transparent")
        self.sesion = sesion
        self._devoluciones: list[dict] = []
        self._nucleo_cursos: list[dict] = []
        self._nucleo_nombre = ""

        # --- encabezado: saludo + campanita + estado del núcleo ------------
        encabezado = ctk.CTkFrame(self, fg_color="transparent")
        encabezado.pack(fill="x", pady=(0, 20))

        saludo = ctk.CTkFrame(encabezado, fg_color="transparent")
        saludo.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            saludo, text=f"¡Buenas, {sesion['nombre']}!", font=tema.fuente(20, "bold"),
            text_color=tema.TEXTO_OSCURO, anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            saludo, text="Aquí tiene su resumen de Generación-I", font=tema.fuente(12),
            text_color=tema.GRIS, anchor="w",
        ).pack(anchor="w")
        # El pedido a `_cargar_todo` va sin overlay (ver más abajo) porque
        # tapar toda la pantalla apenas se entra se siente pesado — pero sin
        # ESTE aviso, las tarjetas quedaban con el "—" de siempre y la lista
        # de abajo vacía, sin decir que faltaba algo: se veía como que
        # Inicio "es así", estático, en vez de como que estaba cargando.
        self._estado_carga = ctk.CTkLabel(
            saludo, text="Cargando su resumen...", font=tema.fuente(11),
            text_color=tema.GRIS, anchor="w",
        )
        self._estado_carga.pack(anchor="w", pady=(2, 0))

        indicadores = ctk.CTkFrame(encabezado, fg_color="transparent")
        indicadores.pack(side="right")
        # Repite lo mismo que ya se avisa al entrar (ver App._avisos_al_entrar),
        # pero acá queda a mano todo el tiempo: si el docente cerró el aviso
        # sin leerlo bien, o vuelve horas después, no lo perdió.
        self.campana_boton = ctk.CTkButton(
            indicadores, text="🔔", width=36, height=32, fg_color="transparent",
            border_width=1, state="disabled", command=self._mostrar_devoluciones,
        )
        self.campana_boton.pack(side="right")

        # --- estado del núcleo: quién le falta algo este mes ----------------
        # Dirección no revisa nada del núcleo hasta que TODOS entregaron
        # (planeaciones e informe), así que entre compañeros conviene que
        # se vea quién falta — la presión de los propios colegas apura más
        # que un aviso genérico. Solo para docentes; la tarjeta se arma acá
        # sin empaquetar (self._grilla_tarjetas sirve de ancla con
        # `before=` para insertarla siempre en este mismo lugar, sin
        # importar cuándo responda el backend) y `_reconstruir_tarjeta_nucleo`
        # decide si mostrarla: nada si el docente no tiene núcleo o si el
        # núcleo ya está completo — no tiene sentido dejar un cuadro vacío
        # o una felicitación permanente ocupando espacio.
        self._nucleo_card = ctk.CTkFrame(
            self, fg_color=tema.FONDO_TARJETA, corner_radius=14,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        self._es_docente = sesion["rol"] in ("docente", "ambos")

        # --- tarjetas de resumen del mes ------------------------------------
        # Grilla de 3 columnas en vez de una sola fila de 5: la ventana por
        # defecto (700px) es angosta y con 5 en fila la última quedaba
        # aplastada — con esto la quinta pasa sola a una segunda fila.
        self._grilla_tarjetas = grilla_tarjetas = ctk.CTkFrame(self, fg_color="transparent")
        grilla_tarjetas.pack(fill="x", pady=(0, 24))
        for col in range(3):
            grilla_tarjetas.grid_columnconfigure(col, weight=1)

        self._error_resumen = ctk.CTkLabel(
            self, text="", text_color=tema.ROJO, font=tema.fuente(12), anchor="w", wraplength=560,
        )

        self._tarjetas: dict[str, TarjetaResumen] = {}
        datos_tarjetas = [
            ("registradas", "📋", "Planeaciones\nregistradas", tema.VERDE),
            ("pendientes", "⏳", "Planeaciones\npendientes", tema.AMBAR),
            ("horas", "🕐", "Horas\nejecutadas", tema.AZUL),
            ("cursos", "🏫", "Cursos\nactivos", tema.DORADO),
            ("informes", "📄", "Informes\npendientes", tema.MORADO),
        ]
        for i, (clave, icono, etiqueta, color) in enumerate(datos_tarjetas):
            tarjeta = TarjetaResumen(grilla_tarjetas, icono, "—", etiqueta, color_acento=color)
            tarjeta.grid(row=i // 3, column=i % 3, sticky="nsew", padx=(0, 10), pady=(0, 10))
            self._tarjetas[clave] = tarjeta
        self._error_resumen.pack(fill="x", pady=(0, 12))

        # --- planeaciones recientes ------------------------------------------
        ctk.CTkLabel(
            self, text="Planeaciones recientes", font=tema.fuente(15, "bold"),
            text_color=tema.TEXTO_OSCURO, anchor="w",
        ).pack(fill="x", pady=(0, 8))
        self._contenedor_recientes = ctk.CTkFrame(self, fg_color="transparent")
        self._contenedor_recientes.pack(fill="x")
        ctk.CTkLabel(
            self._contenedor_recientes, text="Cargando...", text_color=tema.GRIS,
        ).pack(anchor="w", pady=8)

        # Un solo viaje para las cuatro cosas de arriba (devoluciones,
        # núcleo, resumen, planeaciones recientes) en vez de cuatro viajes
        # sueltos — Inicio es lo primero que se ve después de loguear, y
        # justo ahí es cuando más otras llamadas hay en paralelo
        # (cache.precargar, el aviso de App): menos viajes acá es menos
        # espera Y menos chance de que Apps Script se pise entre pedidos
        # simultáneos.
        self._cargar_todo()

    def _cargar_todo(self):
        token = self.sesion["token"]
        mes = date_utils.hoy_iso()[:7]
        en_segundo_plano(
            self,
            lambda: api_client.batch([
                ("mis_devoluciones", [token]),
                ("obtener_estado_nucleo", [token, mes]),
                ("obtener_resumen_docente", [token, mes]),
                ("obtener_planeaciones", [token, None, None, True]),
            ]),
            self._al_cargar_todo,
            self._al_fallar_todo,
            mostrar_overlay=False,
        )

    def _al_cargar_todo(self, resultados: list):
        self._estado_carga.pack_forget()
        devoluciones, estado_nucleo, resumen, planeaciones = resultados

        # Devoluciones y núcleo son extras silenciosos: si fallan solo
        # ellos, no molestan más que eso — igual que antes.
        if not isinstance(devoluciones, api_client.ApiError):
            self._al_cargar_devoluciones(devoluciones)
        if self._es_docente and not isinstance(estado_nucleo, api_client.ApiError):
            self._al_cargar_estado_nucleo(estado_nucleo)

        if isinstance(resumen, api_client.ApiError):
            self._error_resumen.configure(text=f"No se pudo cargar el resumen: {resumen}")
        else:
            self._al_cargar_resumen(resumen)

        if isinstance(planeaciones, api_client.ApiError):
            self._al_fallar_planeaciones(planeaciones)
        else:
            self._al_cargar_planeaciones(planeaciones)

    def _al_fallar_todo(self, exc):
        # Todo el viaje falló de entrada (sin conexión, etc.) — cada
        # sección degrada igual que si solo hubiera fallado ella sola.
        self._estado_carga.pack_forget()
        self._error_resumen.configure(text=f"No se pudo cargar el resumen: {exc}")
        self._al_fallar_planeaciones(exc)

    # --- tarjetas de resumen -------------------------------------------------

    def _al_cargar_resumen(self, resumen: dict):
        self._error_resumen.configure(text="")
        self._tarjetas["registradas"].actualizar(resumen.get("planeaciones_registradas", 0))
        self._tarjetas["pendientes"].actualizar(resumen.get("planeaciones_pendientes", 0))
        self._tarjetas["horas"].actualizar(f"{resumen.get('horas_ejecutadas', 0):g}h")
        self._tarjetas["cursos"].actualizar(resumen.get("cursos_activos", 0))
        self._tarjetas["informes"].actualizar(resumen.get("informes_pendientes", 0))

    # --- planeaciones recientes -----------------------------------------------

    def _al_fallar_planeaciones(self, exc):
        for w in self._contenedor_recientes.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self._contenedor_recientes, text=f"No se pudieron cargar: {exc}", text_color=tema.ROJO,
        ).pack(anchor="w", pady=8)

    def _al_cargar_planeaciones(self, planeaciones: list[dict]):
        for w in self._contenedor_recientes.winfo_children():
            w.destroy()

        recientes = sorted(planeaciones, key=lambda p: p.get("fecha") or "", reverse=True)[:6]
        if not recientes:
            ctk.CTkLabel(
                self._contenedor_recientes, text="Todavía no cargó ninguna planeación este mes.",
                text_color=tema.GRIS,
            ).pack(anchor="w", pady=8)
            return

        colores_estado = {"aprobado": tema.VERDE, "devuelto": tema.ROJO}
        tabla = Tabla(self._contenedor_recientes, ["Fecha", "Curso", "Horas", "Estado"], anchos=[2, 3, 1, 2])
        tabla.pack(fill="x")
        for p in recientes:
            estado = str(p.get("estado") or "pendiente")
            color = colores_estado.get(estado, tema.AMBAR)
            tabla.agregar_fila(
                [date_utils.a_fecha_corta(p.get("fecha", "")), p.get("grupo", ""), f"{p.get('horas', 0):g}h", estado],
                estado=(estado, color),
            )

    # --- campanita de devoluciones ---------------------------------------

    def _al_cargar_devoluciones(self, devoluciones: list[dict]):
        self._devoluciones = devoluciones or []
        if not self._devoluciones:
            return
        self.campana_boton.configure(
            text=f"🔔 {len(self._devoluciones)}", state="normal",
            fg_color=tema.AMBAR, hover_color=tema.AMBAR_HOVER, text_color=tema.BLANCO,
        )

    def _mostrar_devoluciones(self):
        messagebox.showwarning("Le devolvieron esto", texto_devoluciones(self._devoluciones))

    # --- estado del núcleo -------------------------------------------------

    def _al_cargar_estado_nucleo(self, datos: dict):
        self._nucleo_nombre = datos.get("nucleo") or ""
        self._nucleo_cursos = datos.get("cursos") or []
        self._reconstruir_tarjeta_nucleo()

    def _reconstruir_tarjeta_nucleo(self):
        for w in self._nucleo_card.winfo_children():
            w.destroy()

        pendientes = [
            c for c in self._nucleo_cursos
            if not (c.get("planeaciones_al_dia") and c.get("informe_entregado"))
        ]
        # Sin núcleo (docente suelto) o núcleo ya al día: la tarjeta no
        # aporta nada. `pack_forget` no rompe nada si ya estaba oculta.
        if not self._nucleo_cursos or not pendientes:
            self._nucleo_card.pack_forget()
            return

        cabecera = ctk.CTkFrame(self._nucleo_card, fg_color="transparent")
        cabecera.pack(fill="x", padx=18, pady=(16, 4))
        ctk.CTkLabel(
            cabecera, text=f"🏫 Núcleo {self._nucleo_nombre}: falta entregar",
            font=tema.fuente(14, "bold"), text_color=tema.TEXTO_OSCURO, anchor="w",
            wraplength=360, justify="left",
        ).pack(side="left")
        completos = len(self._nucleo_cursos) - len(pendientes)
        pildora(
            cabecera, f"{completos}/{len(self._nucleo_cursos)} al día", tema.AMBAR, tema.AMBAR_CHIP_BG,
        ).pack(side="right")

        # Propios primero: a uno le importa antes que nada si el que falta
        # es usted mismo.
        for c in sorted(pendientes, key=lambda c: not c.get("es_propio")):
            fila = ctk.CTkFrame(self._nucleo_card, fg_color="transparent")
            fila.pack(fill="x", padx=18, pady=4)
            quien = c.get("docente", "")
            if c.get("es_propio"):
                quien += " (usted)"
            ctk.CTkLabel(
                fila, text=f"{quien} — {c.get('curso', '')}", font=tema.fuente(12),
                text_color=tema.TEXTO_OSCURO, anchor="w", wraplength=280, justify="left",
            ).pack(side="left")

            chips = ctk.CTkFrame(fila, fg_color="transparent")
            chips.pack(side="right")
            if not c.get("planeaciones_al_dia"):
                texto = f"planeaciones {c.get('registradas', 0)}/{c.get('esperadas', 0)}"
                pildora(chips, texto, tema.ROJO, tema.ROJO_CHIP_BG).pack(side="left", padx=(0, 6))
            if not c.get("informe_entregado"):
                pildora(chips, "informe pendiente", tema.ROJO, tema.ROJO_CHIP_BG).pack(side="left")

        ctk.CTkLabel(
            self._nucleo_card,
            text="Dirección revisa el núcleo recién cuando todos entreguen.",
            font=tema.fuente(11), text_color=tema.TEXTO_MUTED, anchor="w", justify="left", wraplength=560,
        ).pack(fill="x", padx=18, pady=(6, 16))

        self._nucleo_card.pack(fill="x", pady=(0, 20), before=self._grilla_tarjetas)
