"""Dashboard directivo: cómo va cada curso en el mes (spec sección 3,
"qué docente tiene qué pendiente").

Un dashboard se mira de reojo, no se lee. Por eso: primero el resumen en
una línea, después una tarjeta por curso ordenada por urgencia —lo que
necesita atención arriba— y el estado codificado en color además de en
texto, para que se entienda sin leer.

Va por curso y no por docente porque quien tiene dos puede ir al día en
uno y atrasado en el otro.
"""

from __future__ import annotations

import datetime
from tkinter import messagebox
from typing import Callable

import customtkinter as ctk
from tkcalendar import DateEntry

import api_client
from services import date_utils
from ui import tema
from ui.cargando import Cargando
from ui.tareas import en_segundo_plano
from ui.widgets import campo_label, pildora

# Rojo: ni siquiera puede entregar el informe, le faltan clases.
# Ámbar: ya puede entregarlo y no lo hizo — es lo accionable hoy.
# Verde: al día.
ROJO, AMBAR, VERDE, GRIS = tema.ROJO, tema.AMBAR, tema.VERDE, tema.GRIS

# Gris puntual del mockup de Design para las etiquetas de las tarjetas KPI
# y el cuerpo de las tarjetas de curso — no tiene equivalente exacto en
# tema.py.
_GRIS_TEXTO_TABLA = "#5A665F"


class DashboardScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None] | None = None):
        # Sin `on_volver` va montada como pestaña de RevisarHubScreen.
        super().__init__(master, label_text="" if on_volver is None else "Cómo va el mes")
        self.sesion = sesion
        self.on_volver = on_volver

        if on_volver is not None:
            ctk.CTkButton(
                self, text="← Volver", width=90, fg_color="transparent", border_width=1,
                text_color=tema.TEXTO_OSCURO, hover_color=tema.FONDO_CONTENIDO, command=on_volver,
            ).pack(anchor="w", pady=(0, 12))

        # Encabezado: "Cierre de {mes}" a la izquierda (como en el mockup),
        # mes a consultar + actualizar a la derecha — igual que las otras
        # pestañas de Revisar, para poder mirar meses anteriores.
        fila_mes = ctk.CTkFrame(self, fg_color="transparent")
        fila_mes.pack(fill="x", pady=(0, 18))
        self.titulo_label = ctk.CTkLabel(
            fila_mes, text="Cierre de —", font=tema.fuente(18, "bold"), text_color=tema.TEXTO_OSCURO,
        )
        self.titulo_label.pack(side="left")
        # height=1 a propósito: sin ancho/alto explícitos, CTkFrame pide
        # 200px de alto por defecto — este espaciador vacío inflaba toda la
        # fila a 200px y el título terminaba centrado bien abajo del inicio
        # real de la fila, con un hueco enorme arriba (mismo bug que
        # cursos_screen.py, otra variante: acá no era pack_propagate, era
        # el alto por defecto de un frame sin ninguna dimensión fijada).
        ctk.CTkFrame(fila_mes, fg_color="transparent", height=1).pack(side="left", fill="x", expand=True)
        # Filtro por núcleo (spec: dirección revisa núcleo por núcleo, recién
        # cuando ese núcleo completo entregó — con esto puede mirar solo el
        # que le toca revisar en vez de los cursos de todos mezclados). Las
        # opciones salen de los cursos que trae cada carga (ver _cargar) y
        # no de un catálogo aparte, para no listar núcleos vacíos o viejos.
        self._NUCLEO_TODOS = "Todos los núcleos"
        self.nucleo_menu = ctk.CTkOptionMenu(
            fila_mes, values=[self._NUCLEO_TODOS], width=170, command=self._al_cambiar_nucleo,
        )
        self.nucleo_menu.pack(side="left", anchor="s", padx=(0, 10))
        self.mes_entry = ctk.CTkEntry(fila_mes, width=110, justify="center")
        self.mes_entry.insert(0, date_utils.hoy_iso()[:7])
        self.mes_entry.pack(side="left", anchor="s", padx=(0, 10))
        ctk.CTkButton(
            fila_mes, text="Actualizar", width=100, fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER,
            command=self._cargar,
        ).pack(side="left", anchor="s")

        self.resumen_label = ctk.CTkLabel(self, text="", text_color=tema.ROJO, anchor="w")
        self.resumen_label.pack(fill="x", pady=(0, 8))
        # customtkinter no acepta text_color=None para "el del tema", así que
        # nos guardamos el que trae de fábrica para poder volver a él.
        self.color_normal = self.resumen_label.cget("text_color")

        self._construir_kpis()
        self._construir_aviso()

        # fill="x" y no "both"/expand: `self` es un CTkScrollableFrame, y un
        # hijo directo suyo no puede "llenar" un alto disponible (ver la
        # misma nota en cursos_screen.py).
        self.tarjetas = ctk.CTkFrame(self, fg_color="transparent")
        self.tarjetas.pack(fill="x")
        self.tarjetas.grid_columnconfigure((0, 1, 2), weight=1, uniform="dash")

        # Cambiar de mes deja la consulta anterior viajando: si esa llega
        # última, el directivo termina viendo el mes que ya no pidió.
        self.consulta = 0
        self._estados_cache: list[dict] = []
        self._filtro_texto = ""
        self._filtro_nucleo = self._NUCLEO_TODOS
        self._cargar()

    def _construir_kpis(self):
        """Las 3 tarjetas blancas + la tarjeta oscura de cierre, en fila,
        como en el mockup — reemplaza lo que antes era una sola línea de
        texto de resumen más una tarjeta de cierre aparte."""
        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.pack(fill="x", pady=(0, 16))
        fila.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="kpi")

        self._kpi_entregados = self._tarjeta_kpi(fila, 0, "informes entregados")
        self._kpi_al_dia = self._tarjeta_kpi(fila, 1, "cursos con todas las clases cargadas")
        self._kpi_horas = self._tarjeta_kpi(fila, 2, "docentes con las 8 h externas al mes")

        tarjeta_cierre = ctk.CTkFrame(fila, fg_color=tema.VERDE_OSCURO, corner_radius=16)
        tarjeta_cierre.grid(row=0, column=3, sticky="nsew")
        contenido_cierre = ctk.CTkFrame(tarjeta_cierre, fg_color="transparent")
        contenido_cierre.pack(fill="both", expand=True, padx=20, pady=20)
        ctk.CTkLabel(
            contenido_cierre, text="ESTE MES SE CIERRA EL", font=tema.fuente(11, "bold"),
            text_color=tema.TEXTO_CLARO_APAGADO, anchor="w",
        ).pack(fill="x", pady=(0, 10))
        # DateEntry (tkcalendar) es ttk, no customtkinter, pero convive bien
        # dentro del frame. Muestra un calendario desplegable al hacer clic.
        self.cierre_cal = DateEntry(
            contenido_cierre, date_pattern="yyyy-mm-dd", locale="es",
            background=tema.VERDE_OSCURO_ACTIVO, foreground=tema.BLANCO, borderwidth=0,
        )
        self.cierre_cal.pack(fill="x")
        ctk.CTkButton(
            contenido_cierre, text="Guardar fecha", fg_color=tema.DORADO_ACENTO,
            hover_color=tema.DORADO_ACENTO_HOVER, text_color=tema.VERDE_OSCURO,
            command=self._guardar_corte,
        ).pack(fill="x", pady=(10, 0))

    @staticmethod
    def _tarjeta_kpi(padre, columna: int, etiqueta: str, valor_inicial: str = "0 / 0") -> ctk.CTkLabel:
        tarjeta = ctk.CTkFrame(
            padre, fg_color=tema.FONDO_TARJETA, corner_radius=16,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        tarjeta.grid(row=0, column=columna, sticky="nsew", padx=(0, 14))
        contenido = ctk.CTkFrame(tarjeta, fg_color="transparent")
        contenido.pack(fill="both", expand=True, padx=20, pady=18)
        ctk.CTkFrame(
            contenido, width=34, height=34, corner_radius=10, fg_color=tema.FONDO_CONTENIDO,
        ).pack(anchor="w", pady=(0, 12))
        numero_label = ctk.CTkLabel(
            contenido, text=valor_inicial, font=tema.fuente(24, "bold"), text_color=tema.VERDE_OSCURO,
            anchor="w",
        )
        numero_label.pack(fill="x")
        ctk.CTkLabel(
            contenido, text=etiqueta, font=tema.fuente(12), text_color=_GRIS_TEXTO_TABLA, anchor="w",
            justify="left", wraplength=180,
        ).pack(fill="x", pady=(4, 0))
        return numero_label

    def _construir_aviso(self):
        aviso = ctk.CTkFrame(
            self, fg_color=tema.FONDO_TARJETA, corner_radius=12,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        aviso.pack(fill="x", pady=(0, 20))
        self.corte_aviso = ctk.CTkLabel(
            aviso,
            text="Pasada esa fecha los docentes no pueden cargar, editar ni borrar nada de ese mes. "
                 "Ustedes sí.",
            text_color=tema.TEXTO_MUTED, font=tema.fuente(11),
            anchor="w", justify="left", wraplength=900,
        )
        self.corte_aviso.pack(fill="x", padx=18, pady=13)

    def filtrar(self, texto: str):
        """Lo llama el buscador del encabezado superior (ver
        `RevisarHubScreen`) — filtra por curso o docente sobre lo que ya
        está en memoria."""
        self._filtro_texto = texto.strip().lower()
        self._renderizar_tarjetas()

    def _al_cambiar_nucleo(self, valor: str):
        self._filtro_nucleo = valor
        self._renderizar_tarjetas()

    # --- cierre del mes -------------------------------------------------

    def _aplicar_cierre(self, r: dict):
        """Deja en el calendario la fecha de cierre ya traída por `_cargar`
        (junto con el estado del mes, en el mismo viaje — ver ahí)."""
        fecha = str((r or {}).get("fecha_cierre") or "")
        try:
            self.cierre_cal.set_date(datetime.date.fromisoformat(fecha))
        except (ValueError, TypeError):
            pass

    def _guardar_corte(self):
        mes = self.mes_entry.get().strip()
        fecha = self.cierre_cal.get_date().isoformat()
        self.corte_aviso.configure(text="Guardando...", text_color=GRIS)

        def listo(r):
            self.corte_aviso.configure(
                text=f"Listo: {mes} se cierra el {date_utils.a_fecha_corta(r['fecha_cierre'])}.",
                text_color=VERDE,
            )
            self._cargar()

        en_segundo_plano(
            self,
            lambda: api_client.fijar_fecha_de_cierre(self.sesion["token"], mes, fecha),
            listo,
            lambda exc: self.corte_aviso.configure(text=str(exc), text_color=ROJO),
        )

    def _alternar_cierre(self, estado: dict, abrir: bool):
        curso, mes = estado["curso_id"], estado["mes"]
        nombre = estado.get("curso", "")
        if not abrir and not messagebox.askyesno(
            "Cerrar el mes",
            f"¿Cerrar {mes} para «{nombre}»?\n\n"
            "El docente no va a poder cambiar nada más de ese mes.",
        ):
            return

        self.corte_aviso.configure(text="Guardando...", text_color=GRIS)

        def listo(_r):
            self.corte_aviso.configure(
                text=f"{'Reabierto' if abrir else 'Cerrado'} {mes} para «{nombre}».",
                text_color=VERDE,
            )
            self._cargar()

        en_segundo_plano(
            self,
            lambda: api_client.reabrir_mes(self.sesion["token"], curso, mes, abrir),
            listo,
            lambda exc: self.corte_aviso.configure(text=str(exc), text_color=ROJO),
        )

    # --- estado de cada curso ------------------------------------------

    def _clasificar(self, estado: dict):
        """Devuelve (prioridad, color, texto del informe). Prioridad más
        baja se muestra primero: lo que necesita atención va arriba."""
        if estado["faltantes"] > 0:
            return 0, ROJO, "no puede entregar todavía"
        if not estado.get("informe_entregado"):
            return 1, AMBAR, "informe pendiente"
        return 2, VERDE, "informe entregado"

    def _cargar(self):
        for w in self.tarjetas.winfo_children():
            w.destroy()

        mes = self.mes_entry.get().strip()
        self.titulo_label.configure(text=f"Cierre de {mes}")
        self.consulta += 1
        consulta = self.consulta
        self.resumen_label.configure(text="")
        cargando = Cargando(self.tarjetas, texto="Cargando el mes...")
        cargando.pack(pady=20)

        def listo(resultado):
            if consulta != self.consulta:
                return
            estados, cierre = resultado
            if isinstance(estados, api_client.ApiError):
                fallo(estados)
                return
            cargando.detener()
            cargando.destroy()
            self._estados_cache = estados
            self._aplicar_cierre(cierre if not isinstance(cierre, api_client.ApiError) else {})
            if not estados:
                self.resumen_label.configure(text="Todavía no hay cursos.", text_color=GRIS)
                return

            entregados = sum(1 for e in estados if e.get("informe_entregado"))
            al_dia = sum(1 for e in estados if e["faltantes"] == 0)
            self._kpi_entregados.configure(text=f"{entregados} / {len(estados)}")
            self._kpi_al_dia.configure(text=f"{al_dia} / {len(estados)}")

            # Un docente puede tener dos cursos, cada uno con sus propias
            # actividades: sumamos por docente para no contar "cumple" a
            # alguien que llegó a 8 h repartidas entre los dos, ni "no
            # cumple" a alguien que sí llegó pero se ve partido en dos filas.
            objetivo = next((e["objetivo_horas_externas"] for e in estados if "objetivo_horas_externas" in e), 8)
            horas_por_docente: dict = {}
            for e in estados:
                clave = e.get("docente_id")
                horas_por_docente[clave] = horas_por_docente.get(clave, 0) + e.get("horas_externas", 0)
            cumplen = sum(1 for h in horas_por_docente.values() if h >= objetivo)
            self._kpi_horas.configure(text=f"{cumplen} / {len(horas_por_docente)}")

            nucleos = sorted({e.get("nucleo", "").strip() for e in estados if e.get("nucleo", "").strip()})
            self.nucleo_menu.configure(values=[self._NUCLEO_TODOS] + nucleos)
            # Si el núcleo que tenía elegido ya no está entre los de este
            # mes (cambió de mes, o ya no tiene cursos), vuelve a "Todos" en
            # vez de quedar mostrando un filtro que no filtra nada.
            if self._filtro_nucleo not in ([self._NUCLEO_TODOS] + nucleos):
                self._filtro_nucleo = self._NUCLEO_TODOS
            self.nucleo_menu.set(self._filtro_nucleo)

            self._renderizar_tarjetas()

        def fallo(exc):
            if consulta != self.consulta:
                return
            cargando.detener()
            cargando.destroy()
            self.resumen_label.configure(text=str(exc), text_color=ROJO)

        def trabajo():
            # Un solo viaje para el estado del mes y la fecha de cierre —
            # antes eran dos llamadas seguidas (obtener_dashboard_directivo
            # y fecha_de_cierre), el doble de espera en la pantalla que se
            # abre apenas entra un directivo.
            token = self.sesion["token"]
            return api_client.batch([
                ("obtener_dashboard_directivo", [token, mes]),
                ("fecha_de_cierre", [token, mes]),
            ])

        en_segundo_plano(self, trabajo, listo, fallo)

    def _renderizar_tarjetas(self):
        """Redibuja con lo que ya está en `self._estados_cache`, sin pedir
        nada nuevo al backend — la llama tanto la carga inicial como el
        buscador y el filtro de núcleo."""
        for w in self.tarjetas.winfo_children():
            w.destroy()

        estados = self._estados_cache
        if self._filtro_nucleo != self._NUCLEO_TODOS:
            estados = [e for e in estados if e.get("nucleo", "").strip() == self._filtro_nucleo]
        if self._filtro_texto:
            estados = [
                e for e in estados
                if self._filtro_texto in f"{e.get('curso', '')} {e.get('docente', '')}".lower()
            ]
        if not estados:
            mensaje = (
                "Ningún curso coincide con la búsqueda."
                if self._filtro_texto
                else "Ese núcleo no tiene cursos este mes."
            )
            ctk.CTkLabel(self.tarjetas, text=mensaje, text_color=GRIS).pack(anchor="w", pady=10)
            return

        # Grilla de 3 columnas, como en el mockup (antes: una sola columna
        # de filas apiladas).
        ordenados = sorted(estados, key=lambda e: (self._clasificar(e)[0], e.get("curso", "")))
        for indice, estado in enumerate(ordenados):
            self._tarjeta(indice, estado)

    def _tarjeta(self, indice: int, estado: dict):
        _, color, texto_informe = self._clasificar(estado)

        marco = ctk.CTkFrame(
            self.tarjetas, fg_color=tema.FONDO_TARJETA, corner_radius=16,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        marco.grid(
            row=indice // 3, column=indice % 3, sticky="nsew",
            padx=(0 if indice % 3 == 0 else 7, 0 if indice % 3 == 2 else 7), pady=7,
        )
        # Franja de color arriba (no a la izquierda): el estado se ve antes
        # de leer, igual que en el mockup.
        ctk.CTkFrame(marco, height=4, fg_color=color, corner_radius=0).pack(fill="x")

        cuerpo = ctk.CTkFrame(marco, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True, padx=20, pady=18)

        ctk.CTkLabel(
            cuerpo, text=estado.get("curso", ""), font=tema.fuente(14, "bold"), text_color=tema.TEXTO_OSCURO,
            anchor="w", justify="left", wraplength=280,
        ).pack(fill="x")
        ctk.CTkLabel(
            cuerpo, text=estado.get("docente", ""), text_color=tema.TEXTO_MUTED,
            font=tema.fuente(12), anchor="w",
        ).pack(fill="x", pady=(3, 0))

        # Barra de 4 segmentos (uno por clase esperada), como en "Este mes"
        # de planeacion_screen.py — más claro de un vistazo que un solo
        # tramo continuo.
        segmentos_fila = ctk.CTkFrame(cuerpo, fg_color="transparent")
        segmentos_fila.pack(fill="x", pady=(14, 10))
        registradas, esperadas = estado["registradas"], max(estado["esperadas"], 1)
        for i in range(esperadas):
            seg_color = VERDE if i < registradas else tema.BORDE_TARJETA
            # width=1 a propósito: ver la nota en planeacion_screen.py
            # (_dibujar_segmentos_mes) sobre el bug de CTkFrame con 3+
            # hermanos a expand=True sin ancho explícito.
            ctk.CTkFrame(segmentos_fila, width=1, height=7, corner_radius=4, fg_color=seg_color).pack(
                side="left", fill="x", expand=True, padx=(0 if i == 0 else 5, 0),
            )

        estados_fila = ctk.CTkFrame(cuerpo, fg_color="transparent")
        estados_fila.pack(fill="x")

        faltan = estado["faltantes"]
        texto_clases = (
            f"{estado['registradas']} de {estado['esperadas']} clases"
            if faltan == 0
            else f"{estado['registradas']} de {estado['esperadas']} clases · faltan {faltan}"
        )
        fondo_clases = tema.VERDE_CHIP_BG if faltan == 0 else tema.ROJO_CHIP_BG
        pildora(estados_fila, texto_clases, VERDE if faltan == 0 else ROJO, fondo_clases).pack(
            side="left", padx=(0, 6), pady=(0, 6)
        )
        fondo_informe = tema.VERDE_CHIP_BG if color == VERDE else (
            tema.AMBAR_CHIP_BG if color == AMBAR else tema.ROJO_CHIP_BG
        )
        pildora(estados_fila, texto_informe, color, fondo_informe).pack(side="left", padx=(0, 6), pady=(0, 6))

        objetivo = estado.get("objetivo_horas_externas", 8)
        horas_externas = estado.get("horas_externas", 0)
        cumple_externas = estado.get("cumple_horas_externas", horas_externas >= objetivo)
        texto_externas = f"{horas_externas:g} de {objetivo:g} h externas"
        color_externas = VERDE if cumple_externas else ROJO
        fondo_externas = tema.VERDE_CHIP_BG if cumple_externas else tema.ROJO_CHIP_BG
        pildora(estados_fila, texto_externas, color_externas, fondo_externas).pack(side="left", pady=(0, 6))

        # Reabrir un mes cerrado es lo que hace que el corte no sea una
        # pared: el docente pide, el directivo abre acá mismo. Nota: el
        # mockup muestra "Reabrir"/"Cerrar" siempre juntos, pero acá solo
        # tiene sentido ofrecer la acción que de verdad aplica al estado
        # real del curso — mostrar las dos a la vez dejaría "Cerrar" un mes
        # que ya está abierto sin que haga nada.
        if estado.get("cerrado"):
            pildora(cuerpo, "mes cerrado", tema.TEXTO_MUTED, tema.FONDO_CONTENIDO).pack(
                anchor="w", pady=(0, 10)
            )
            ctk.CTkButton(
                cuerpo, text="Reabrir", fg_color="transparent", border_width=1,
                text_color=tema.TEXTO_OSCURO, hover_color=tema.FONDO_CONTENIDO,
                command=lambda: self._alternar_cierre(estado, True),
            ).pack(fill="x")
        elif estado.get("reabierto"):
            pildora(cuerpo, "reabierto", AMBAR, tema.AMBAR_CHIP_BG).pack(anchor="w", pady=(0, 10))
            ctk.CTkButton(
                cuerpo, text="Cerrar", fg_color="transparent", border_width=1,
                text_color=tema.TEXTO_OSCURO, hover_color=tema.FONDO_CONTENIDO,
                command=lambda: self._alternar_cierre(estado, False),
            ).pack(fill="x")
