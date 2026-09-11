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
from ui.widgets import Tabla, TarjetaResumen


class HomeScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict):
        super().__init__(master, fg_color="transparent")
        self.sesion = sesion
        self._devoluciones: list[dict] = []
        self._nucleo_cursos: list[dict] = []
        self._nucleo_nombre = ""
        self._nucleo_mes = ""

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
        self._cargar_devoluciones()

        # Cómo va el núcleo completo este mes — ver comentario largo en
        # git history de este archivo / obtener_estado_nucleo en el backend.
        # Sin pack() todavía: si no hay núcleo que mostrar se queda sin
        # mostrarse nunca (antes quedaba un cuadrito vacío plantado ahí).
        self.nucleo_boton = ctk.CTkButton(
            indicadores, text="", width=36, height=32, fg_color="transparent",
            border_width=1, state="disabled",
        )
        if sesion["rol"] in ("docente", "ambos"):
            self._cargar_estado_nucleo()

        # --- tarjetas de resumen del mes ------------------------------------
        # Grilla de 3 columnas en vez de una sola fila de 5: la ventana por
        # defecto (700px) es angosta y con 5 en fila la última quedaba
        # aplastada — con esto la quinta pasa sola a una segunda fila.
        grilla_tarjetas = ctk.CTkFrame(self, fg_color="transparent")
        grilla_tarjetas.pack(fill="x", pady=(0, 24))
        for col in range(3):
            grilla_tarjetas.grid_columnconfigure(col, weight=1)

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
        self._cargar_resumen()

        # --- planeaciones recientes ------------------------------------------
        ctk.CTkLabel(
            self, text="Planeaciones recientes", font=tema.fuente(15, "bold"),
            text_color=tema.TEXTO_OSCURO, anchor="w",
        ).pack(fill="x", pady=(0, 8))
        self._contenedor_recientes = ctk.CTkFrame(self, fg_color="transparent")
        self._contenedor_recientes.pack(fill="x")
        self._cargar_planeaciones_recientes()

    # --- tarjetas de resumen -------------------------------------------------

    def _cargar_resumen(self):
        mes = date_utils.hoy_iso()[:7]
        en_segundo_plano(
            self,
            lambda: api_client.obtener_resumen_docente(self.sesion["token"], mes),
            self._al_cargar_resumen,
            lambda _exc: None,  # el dashboard no se rompe si esto falla
            mostrar_overlay=False,
        )

    def _al_cargar_resumen(self, resumen: dict):
        self._tarjetas["registradas"].actualizar(resumen.get("planeaciones_registradas", 0))
        self._tarjetas["pendientes"].actualizar(resumen.get("planeaciones_pendientes", 0))
        self._tarjetas["horas"].actualizar(f"{resumen.get('horas_ejecutadas', 0):g}h")
        self._tarjetas["cursos"].actualizar(resumen.get("cursos_activos", 0))
        self._tarjetas["informes"].actualizar(resumen.get("informes_pendientes", 0))

    # --- planeaciones recientes -----------------------------------------------

    def _cargar_planeaciones_recientes(self):
        en_segundo_plano(
            self,
            lambda: api_client.obtener_planeaciones(self.sesion["token"], resumen=True),
            self._al_cargar_planeaciones,
            lambda _exc: None,
            mostrar_overlay=False,
        )

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

    def _cargar_devoluciones(self):
        en_segundo_plano(
            self,
            lambda: api_client.mis_devoluciones(self.sesion["token"]),
            self._al_cargar_devoluciones,
            lambda _exc: None,  # la campanita es un extra: si falla, no molesta
            mostrar_overlay=False,  # chequeo silencioso, no tiene que tapar el menú
        )

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

    def _cargar_estado_nucleo(self):
        mes = date_utils.hoy_iso()[:7]
        self._nucleo_mes = mes
        en_segundo_plano(
            self,
            lambda: api_client.obtener_estado_nucleo(self.sesion["token"], mes),
            self._al_cargar_estado_nucleo,
            lambda _exc: None,  # es un extra: si falla, no molesta
            mostrar_overlay=False,  # chequeo silencioso, no tiene que tapar el menú
        )

    def _al_cargar_estado_nucleo(self, datos: dict):
        self._nucleo_nombre = datos.get("nucleo") or ""
        self._nucleo_cursos = datos.get("cursos") or []
        if not self._nucleo_cursos:
            return

        completos = sum(
            1 for c in self._nucleo_cursos if c.get("planeaciones_al_dia") and c.get("informe_entregado")
        )
        total = len(self._nucleo_cursos)
        al_dia = completos == total
        self.nucleo_boton.pack(side="right", padx=(0, 6))
        self.nucleo_boton.configure(
            text=f"🏫 {completos}/{total}", state="normal",
            command=self._mostrar_estado_nucleo,
            fg_color=tema.VERDE if al_dia else tema.AMBAR,
            hover_color=tema.VERDE_HOVER if al_dia else tema.AMBAR_HOVER,
            text_color=tema.BLANCO,
        )

    def _mostrar_estado_nucleo(self):
        lineas = [f"Núcleo: {self._nucleo_nombre} — mes {self._nucleo_mes}", ""]
        for c in sorted(self._nucleo_cursos, key=lambda c: not c.get("es_propio")):
            marca = "✅" if c.get("planeaciones_al_dia") and c.get("informe_entregado") else "❌"
            quien = f"{c.get('docente', '')} (usted)" if c.get("es_propio") else c.get("docente", "")
            informe = "informe entregado" if c.get("informe_entregado") else "informe pendiente"
            lineas.append(
                f"{marca} {quien} — {c.get('curso', '')}: "
                f"{c.get('registradas', 0)}/{c.get('esperadas', 0)} planeaciones, {informe}"
            )
        lineas.append("")
        lineas.append("Dirección revisa recién cuando todo el núcleo entregó.")
        messagebox.showinfo("Estado del núcleo", "\n".join(lineas))
