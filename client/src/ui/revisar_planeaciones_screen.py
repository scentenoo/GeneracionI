"""Revisar las planeaciones del mes (Mariangel, Lorena, administrador).

Muestra TODAS las planeaciones del mes de los cursos que le tocan, no solo
las pendientes: aprobar o devolver una no la hace desaparecer de la lista,
se actualiza ahí mismo con el estado nuevo. Antes, aprobar/devolver volvía
a pedir todo de nuevo y la tarjeta se esfumaba — para revisar varias
seguidas era lento y confuso, no quedaba claro qué se había hecho.
"""

from __future__ import annotations

import webbrowser
from typing import Callable

import customtkinter as ctk

import api_client
from services import date_utils
from ui import tema
from ui.cargando import Cargando
from ui.tareas import en_segundo_plano
from ui.widgets import pildora

ROJO, VERDE, GRIS, AMBAR = tema.ROJO, tema.VERDE, tema.GRIS, tema.AMBAR

# Colores puntuales del mockup de Design que no tienen equivalente exacto
# en tema.py (ese es el gris/fondo general del resto de la app; acá se
# busca calcar la pantalla de Design tal cual, no reinterpretarla).
_FONDO_ENCABEZADO_TABLA = "#F8FAF8"
_GRIS_TEXTO_TABLA = "#5A665F"
_GRIS_TEXTO_DOCENTE = "#4A574F"
# El mockup pide #F2F4F2 para la línea entre filas, pero en Tkinter (sin
# el antialiasing del navegador) ese gris tan claro se pierde del todo
# contra el blanco de la tabla — mismo problema que los separadores de
# planeacion_screen.py e informe_screen.py. Se usa el borde de tarjeta,
# que sí se nota.
_DIVISOR_FILA = tema.BORDE_TARJETA

# Ancho fijo de las columnas "Docente", "Estado" y "Revisión" — el resto
# (Curso y fecha / Objetivo) se reparte lo que quede, como en el mockup
# (grid-template-columns: minmax(0,1fr) 200px minmax(0,1.4fr) 150px 290px).
_ANCHO_DOCENTE = 160
_ANCHO_ESTADO = 140
_ANCHO_REVISION = 280

# (título, peso, ancho mínimo) de cada columna — mismo patrón que
# planeacion_list_screen.py: cada FILA es su propio frame con su propia
# grid_columnconfigure, en vez de una sola grid compartida por header y
# filas. Con una sola grid para toda la tabla, las columnas que dependen
# de "weight" (sin minsize) quedaban congeladas en ancho cero la primera
# vez que se armaba — Curso/fecha, Objetivo y Revisión directamente no se
# veían — porque esa grid se calcula una única vez, con el ancho que el
# contenedor tenía en ese instante (adentro de una pestaña, no siempre es
# el ancho final). Repitiendo la configuración en cada fila, cada una se
# ajusta con el ancho real que tiene al momento de armarse.
#
# Cada columna lleva su PROPIO `uniform` (revpl_col0..4), no uno compartido
# entre varias: `uniform` sincroniza el ancho entre grids de widgets
# distintos que usen el mismo valor —es justo lo que hace falta para que
# "Curso y fecha"/"Objetivo" midan lo mismo en todas las filas, ya que cada
# fila es un frame con su propia grid—, pero si dos columnas DISTINTAS
# comparten el mismo valor (p. ej. todas las de ancho fijo con "col"),
# Tk las fuerza a las tres al mismo ancho entre sí, no solo consigo mismas
# entre filas. Con un valor único por índice de columna, cada una se
# sincroniza solo con su propia columna en las demás filas.
_COLUMNAS = [
    ("Curso y fecha", 10, 0),
    ("Docente", 0, _ANCHO_DOCENTE),
    ("Objetivo", 14, 0),
    ("Estado", 0, _ANCHO_ESTADO),
    ("Revisión", 0, _ANCHO_REVISION),
]


def _configurar_columnas(frame: ctk.CTkFrame):
    for i, (_titulo, peso, minsize) in enumerate(_COLUMNAS):
        frame.grid_columnconfigure(i, weight=peso, minsize=minsize, uniform=f"revpl_col{i}")


# padx (izquierda, derecha) de cada columna, tal como se le pasa a cada
# .grid() en _fila_planeacion — hace falta repetirlo acá para poder
# calcular a mano cuánto le toca en píxeles a "Curso y fecha"/"Objetivo".
_PADX_COLUMNAS = [(24, 9), (9, 9), (9, 9), (9, 9), (9, 24)]


def _anchos_columnas_peso(ancho_fila: int) -> dict[int, int]:
    """Cuántos píxeles le tocan a cada columna de PESO (weight>0, sin
    minsize) dado el ancho real de la fila — a mano, en vez de leerlo de
    `grid_bbox()`. `grid_bbox()` de una columna de peso depende de cuánto
    pida su propio contenido (sin wraplength todavía, el texto entero sin
    envolver), así que usarlo para fijar el wraplength de ESE MISMO
    contenido arma un círculo: se angosta -> grid_bbox() vuelve a medir más
    chico -> se angosta más -> termina en una letra por línea. Con esta
    cuenta, en cambio, todo sale del ancho de la FILA (que lo pone el
    contenedor de afuera, `pack(fill="x")`, no el contenido de las
    celdas) — no hay ciclo posible."""
    fijo = sum(minsize for _t, peso, minsize in _COLUMNAS if peso == 0)
    fijo += sum(izq + der for izq, der in _PADX_COLUMNAS)
    peso_total = sum(peso for _t, peso, _m in _COLUMNAS if peso > 0)
    disponible = max(ancho_fila - fijo, 0)
    return {
        i: int(disponible * peso / peso_total)
        for i, (_t, peso, _m) in enumerate(_COLUMNAS) if peso > 0
    }

# Cuántas filas se muestran de entrada, con un botón "Cargar más" para el
# resto. CTkScrollableFrame tiene un bug de fondo, sin arreglo, de Tk en
# Windows: con listas largas el repintado durante el scroll se corrompe
# (ver https://github.com/TomSchimansky/CustomTkinter/issues/215). Mientras
# menos filas haya que scrollear de una, menos chance de que se note.
_TANDA = 20

# Lo que falta por decidir va primero; lo devuelto (a mitad de corregirse)
# en el medio; lo ya aprobado, al final — es lo que menos hace falta mirar.
_PRIORIDAD_ESTADO = {"pendiente": 0, "devuelto": 1, "aprobado": 2}


def _url_drive(doc_id: str) -> str:
    return f"https://drive.google.com/file/d/{doc_id}/view"


class RevisarPlaneacionesScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None] | None = None):
        # Sin `on_volver` va montada como pestaña de RevisarHubScreen.
        super().__init__(master, label_text="" if on_volver is None else "Planeaciones")
        self.sesion = sesion
        self._planeaciones: list[dict] = []
        self._mes_cargado = ""
        self._mostrar_hasta = _TANDA
        self._filtro_texto = ""
        self._NUCLEO_TODOS = "Todos los núcleos"
        self._filtro_nucleo = self._NUCLEO_TODOS

        if on_volver is not None:
            ctk.CTkButton(
                self, text="← Volver", width=90, fg_color="transparent", border_width=1,
                text_color=tema.TEXTO_OSCURO, hover_color=tema.FONDO_CONTENIDO, command=on_volver,
            ).pack(anchor="w", pady=(0, 12))

        # Fila de arriba: 3 tarjetas KPI (total / pendientes / aprobadas) a
        # la izquierda, mes + actualizar a la derecha — como en el mockup.
        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.pack(fill="x", pady=(0, 20))

        self._kpi_total = self._tarjeta_kpi(fila, "0", "planeaciones este mes", tema.VERDE_OSCURO)
        self._kpi_pendientes = self._tarjeta_kpi(fila, "0", "pendientes de revisar", AMBAR)
        self._kpi_aprobadas = self._tarjeta_kpi(fila, "0", "aprobadas", tema.VERDE_CHIP_TEXTO)

        # height=1 a propósito: ver la nota en dashboard_screen.py — sin
        # esto, el espaciador vacío pide 200px de alto por defecto e infla
        # toda la fila, empujando "Mes"/"Actualizar" bien abajo del resto.
        ctk.CTkFrame(fila, fg_color="transparent", height=1).pack(side="left", fill="x", expand=True)

        # Filtro por núcleo (spec: dirección revisa núcleo por núcleo, recién
        # cuando ese núcleo completo entregó) — mismo patrón que
        # dashboard_screen.py: las opciones salen de lo que trae cada carga,
        # no de un catálogo aparte.
        self.nucleo_menu = ctk.CTkOptionMenu(
            fila, values=[self._NUCLEO_TODOS], width=170, command=self._al_cambiar_nucleo,
        )
        self.nucleo_menu.pack(side="left", anchor="s", padx=(0, 10))

        self.mes_entry = ctk.CTkEntry(fila, width=110, justify="center")
        self.mes_entry.insert(0, date_utils.hoy_iso()[:7])
        self.mes_entry.pack(side="left", anchor="s", padx=(0, 10))
        ctk.CTkButton(
            fila, text="Actualizar", width=100, fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER,
            command=self._cargar,
        ).pack(side="left", anchor="s")

        self.resumen_label = ctk.CTkLabel(self, text="", text_color=tema.ROJO, anchor="w")
        self.resumen_label.pack(fill="x", pady=(0, 8))
        self.color_normal = self.resumen_label.cget("text_color")

        # fill="x" y no "both"/expand: `self` es un CTkScrollableFrame, y un
        # hijo directo suyo no puede "llenar" un alto disponible — esa
        # región mide lo que el contenido pida, no al revés (ver la misma
        # nota en cursos_screen.py).
        self.contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self.contenedor.pack(fill="x")

        self._cargar()

    @staticmethod
    def _tarjeta_kpi(padre, numero: str, etiqueta: str, color: str) -> ctk.CTkLabel:
        tarjeta = ctk.CTkFrame(
            padre, fg_color=tema.FONDO_TARJETA, corner_radius=14,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        tarjeta.pack(side="left", padx=(0, 16))
        numero_label = ctk.CTkLabel(
            tarjeta, text=numero, font=tema.fuente(26, "bold"), text_color=color, anchor="w",
        )
        numero_label.pack(anchor="w", padx=22, pady=(16, 0))
        ctk.CTkLabel(
            tarjeta, text=etiqueta, font=tema.fuente(12), text_color=_GRIS_TEXTO_TABLA, anchor="w",
        ).pack(anchor="w", padx=22, pady=(3, 16))
        return numero_label

    def _cargar(self):
        for w in self.contenedor.winfo_children():
            w.destroy()
        self.resumen_label.configure(text="", text_color=GRIS)
        cargando = Cargando(self.contenedor, texto="Cargando planeaciones...")
        cargando.pack(pady=16)
        mes = self.mes_entry.get().strip()

        def listo(datos):
            self._mes_cargado = mes
            self._planeaciones = datos.get("planeaciones", [])
            self._mostrar_hasta = _TANDA
            self._actualizar_opciones_nucleo()
            self._actualizar_resumen()
            self._redibujar()

        def fallo(exc):
            for w in self.contenedor.winfo_children():
                w.destroy()
            self.resumen_label.configure(text=str(exc), text_color=ROJO)

        en_segundo_plano(
            self,
            lambda: api_client.revision_del_mes(self.sesion["token"], mes),
            listo,
            fallo,
        )

    def filtrar(self, texto: str):
        """Lo llama el buscador del encabezado superior (ver
        `RevisarHubScreen`) — filtra por curso o docente sobre lo que ya
        está en memoria."""
        self._filtro_texto = texto.strip().lower()
        self._mostrar_hasta = _TANDA
        self._redibujar()

    def _actualizar_opciones_nucleo(self):
        nucleos = sorted({p.get("nucleo", "").strip() for p in self._planeaciones if p.get("nucleo", "").strip()})
        self.nucleo_menu.configure(values=[self._NUCLEO_TODOS] + nucleos)
        # Si el núcleo elegido ya no aparece en este mes (cambió de mes,
        # o ya no tiene planeaciones), vuelve a "Todos" en vez de quedar
        # mostrando un filtro que no filtra nada.
        if self._filtro_nucleo not in ([self._NUCLEO_TODOS] + nucleos):
            self._filtro_nucleo = self._NUCLEO_TODOS
        self.nucleo_menu.set(self._filtro_nucleo)

    def _al_cambiar_nucleo(self, valor: str):
        self._filtro_nucleo = valor
        self._mostrar_hasta = _TANDA
        self._redibujar()

    def _redibujar(self):
        """Reconstruye la lista con lo que ya está en memoria —no le pide
        nada de nuevo al backend—, ordenada: pendientes primero, devueltas
        en el medio, aprobadas al final."""
        for w in self.contenedor.winfo_children():
            w.destroy()

        if not self._planeaciones:
            ctk.CTkLabel(
                self.contenedor, text="No hay planeaciones cargadas este mes.", text_color=GRIS
            ).pack(anchor="w", pady=10)
            return

        # Dos pasadas porque el sort de Python es estable: ordenar primero
        # por fecha y después por estado deja, dentro de cada estado, la
        # fecha más nueva arriba — sin eso un sort solo perdería ese orden.
        self._planeaciones.sort(key=lambda p: p["fecha"], reverse=True)
        self._planeaciones.sort(key=lambda p: _PRIORIDAD_ESTADO.get(p.get("estado", "pendiente"), 0))

        filtradas = self._planeaciones
        if self._filtro_nucleo != self._NUCLEO_TODOS:
            filtradas = [p for p in filtradas if p.get("nucleo", "").strip() == self._filtro_nucleo]
        if self._filtro_texto:
            filtradas = [
                p for p in filtradas
                if self._filtro_texto in f"{p.get('curso', '')} {p.get('docente', '')}".lower()
            ]
        if not filtradas:
            mensaje = (
                "Ninguna planeación coincide con la búsqueda."
                if self._filtro_texto
                else "Ese núcleo no tiene planeaciones este mes."
            )
            ctk.CTkLabel(self.contenedor, text=mensaje, text_color=GRIS).pack(anchor="w", pady=10)
            return

        # De a tandas, con "Cargar más" al final: ver _TANDA arriba.
        visibles = filtradas[: self._mostrar_hasta]
        restantes = len(filtradas) - len(visibles)

        # Tarjeta que envuelve la tabla — como en el mockup: cabecera gris
        # clara mayúscula, filas separadas por una línea fina, columnas
        # fijas para docente/estado/revisión y el resto repartido. Cada fila
        # es su propio frame con su propia grid_columnconfigure (mismo
        # patrón que planeacion_list_screen.py) en vez de una sola grid
        # compartida entre encabezado y filas — ver el porqué en el
        # comentario de _COLUMNAS, arriba del todo.
        tarjeta = ctk.CTkFrame(
            self.contenedor, fg_color=tema.FONDO_TARJETA, corner_radius=16,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        tarjeta.pack(fill="x")

        encabezado_tabla = ctk.CTkFrame(tarjeta, fg_color="transparent")
        encabezado_tabla.pack(fill="x")
        _configurar_columnas(encabezado_tabla)
        for col, (titulo, _peso, _minsize) in enumerate(_COLUMNAS):
            ctk.CTkLabel(
                encabezado_tabla, text=titulo.upper(), font=tema.fuente(11, "bold"), text_color=tema.TEXTO_MUTED,
                fg_color=_FONDO_ENCABEZADO_TABLA, anchor="e" if col == 4 else "w",
            ).grid(row=0, column=col, sticky="nsew", padx=(24 if col == 0 else 9, 9), pady=15)

        filas_contenedor = ctk.CTkFrame(tarjeta, fg_color="transparent")
        filas_contenedor.pack(fill="x")
        for p in visibles:
            self._fila_planeacion(filas_contenedor, p, es_ultima=(p is visibles[-1]))

        if restantes > 0:
            ctk.CTkButton(
                self.contenedor, text=f"Cargar {min(restantes, _TANDA)} más ({restantes} sin mostrar)",
                fg_color="transparent", border_width=1, text_color=tema.TEXTO_OSCURO,
                hover_color=tema.FONDO_CONTENIDO, command=self._cargar_mas,
            ).pack(pady=10)

    def _cargar_mas(self):
        self._mostrar_hasta += _TANDA
        self._redibujar()

    def _actualizar_resumen(self):
        total = len(self._planeaciones)
        pendientes = sum(1 for p in self._planeaciones if p.get("estado", "pendiente") == "pendiente")
        aprobadas = sum(1 for p in self._planeaciones if p.get("estado") == "aprobado")
        self._kpi_total.configure(text=str(total))
        self._kpi_pendientes.configure(text=str(pendientes))
        self._kpi_aprobadas.configure(text=str(aprobadas))
        self.resumen_label.configure(text="")

    def _fila_planeacion(self, contenedor: ctk.CTkFrame, p: dict, es_ultima: bool):
        pady_fila = (14, 20 if es_ultima else 14)

        fila = ctk.CTkFrame(contenedor, fg_color="transparent")
        fila.pack(fill="x")
        _configurar_columnas(fila)

        # sticky solo "n_w"/"n_e" (sin la "s"): estas celdas no necesitan
        # estirarse verticalmente para llenar la fila, solo quedar ancladas
        # arriba — con "nsw"/"nse" el widget SÍ se estira a la altura de la
        # fila más alta (la del Objetivo más largo), y como pack()/anchor="w"
        # centran verticalmente dentro de ese espacio de más, Docente/Estado/
        # Revisión terminaban "corridos" hacia abajo respecto a Curso/fecha.
        # "Curso y fecha" y "Objetivo" son columnas de PESO (ver _COLUMNAS),
        # no de ancho fijo: cuánto miden en píxeles depende del ancho de la
        # ventana. Un `wraplength` fijo (320/340, lo que medían "de
        # costumbre") se quedaba corto o largo según ese ancho real — con un
        # curso largo en una ventana angosta, el texto no envolvía a tiempo
        # y se metía encima de Docente/Objetivo. El wraplength de cada label
        # se recalcula en cada resize de la FILA (ver _anchos_columnas_peso
        # arriba del todo — importante que sea del ancho de la fila, no del
        # propio frame de la celda, para no armar un círculo).
        celda_curso = ctk.CTkFrame(fila, fg_color="transparent")
        celda_curso.grid(row=0, column=0, sticky="new", padx=(24, 9), pady=pady_fila)
        curso_label = ctk.CTkLabel(
            celda_curso, text=p["curso"], font=tema.fuente(14, "bold"), text_color=tema.TEXTO_OSCURO,
            anchor="w", justify="left",
        )
        curso_label.pack(fill="x")
        ctk.CTkLabel(
            celda_curso, text=p["fecha"], text_color=tema.TEXTO_MUTED, font=tema.fuente(12), anchor="w",
        ).pack(fill="x", pady=(2, 0))

        ctk.CTkLabel(
            fila, text=p["docente"], text_color=_GRIS_TEXTO_DOCENTE, font=tema.fuente(13), anchor="nw",
            wraplength=_ANCHO_DOCENTE - 10, justify="left",
        ).grid(row=0, column=1, sticky="nw", padx=9, pady=pady_fila)

        celda_objetivo = ctk.CTkFrame(fila, fg_color="transparent")
        celda_objetivo.grid(row=0, column=2, sticky="new", padx=9, pady=pady_fila)
        objetivo_label = ctk.CTkLabel(
            celda_objetivo, text=str(p.get("objetivo", "")), text_color=_GRIS_TEXTO_TABLA, font=tema.fuente(13),
            anchor="w", justify="left",
        )
        objetivo_label.pack(fill="x")

        def _actualizar_wraplength(_evento=None, _fila=fila, _curso=curso_label, _objetivo=objetivo_label):
            anchos = _anchos_columnas_peso(_fila.winfo_width())
            if anchos.get(0, 0) > 1:
                _curso.configure(wraplength=anchos[0])
            if anchos.get(2, 0) > 1:
                _objetivo.configure(wraplength=anchos[2])

        fila.bind("<Configure>", _actualizar_wraplength)

        celda_estado = ctk.CTkFrame(fila, fg_color="transparent")
        celda_estado.grid(row=0, column=3, sticky="nw", padx=9, pady=pady_fila)
        self._pintar_estado(celda_estado, p)

        botones = ctk.CTkFrame(fila, fg_color="transparent")
        botones.grid(row=0, column=4, sticky="ne", padx=(9, 24), pady=pady_fila)
        if p.get("doc_drive_id"):
            ctk.CTkButton(
                botones, text="Abrir", width=70, fg_color="transparent", border_width=1,
                text_color=tema.TEXTO_OSCURO, hover_color=tema.FONDO_CONTENIDO,
                command=lambda: webbrowser.open(_url_drive(p["doc_drive_id"])),
            ).pack(side="left", padx=(0, 6))
        aprobar_boton = ctk.CTkButton(
            botones, text="Aprobar", width=80, fg_color=VERDE, hover_color=tema.VERDE_HOVER
        )
        aprobar_boton.pack(side="left", padx=(0, 6))
        devolver_boton = ctk.CTkButton(
            botones, text="Devolver", width=80, fg_color=AMBAR, hover_color=tema.AMBAR_HOVER
        )
        devolver_boton.pack(side="left")
        botones_revision = (aprobar_boton, devolver_boton)
        aprobar_boton.configure(command=lambda: self._revisar(p, True, celda_estado, botones_revision))
        devolver_boton.configure(command=lambda: self._revisar(p, False, celda_estado, botones_revision))

        if not es_ultima:
            ctk.CTkFrame(contenedor, fg_color=_DIVISOR_FILA, height=1).pack(fill="x")

    def _pintar_estado(self, estado_fila: ctk.CTkFrame, p: dict):
        for w in estado_fila.winfo_children():
            w.destroy()
        estado = p.get("estado", "pendiente")
        motivo = p.get("motivo_devolucion", "")
        if estado == "aprobado":
            pildora(estado_fila, "Aprobada ✓", tema.VERDE_CHIP_TEXTO, tema.VERDE_CHIP_BG).pack(side="left")
        elif estado == "devuelto":
            pildora(estado_fila, "Devuelta", AMBAR, tema.AMBAR_CHIP_BG).pack(anchor="w")
            if motivo:
                # Debajo de la píldora, no al lado (pack "left"): la Estado
                # es una columna de ANCHO FIJO (_ANCHO_ESTADO) y un motivo
                # largo sin wraplength empujaba esa columna mucho más ancha
                # de lo que le corresponde, corriendo Revisión y descolocando
                # toda la fila. Envuelto dentro de ese mismo ancho fijo, en
                # cambio, se queda adentro de su columna.
                ctk.CTkLabel(
                    estado_fila, text=motivo, text_color=tema.TEXTO_MUTED, font=tema.fuente(11),
                    anchor="w", justify="left", wraplength=_ANCHO_ESTADO - 10,
                ).pack(anchor="w", pady=(4, 0))
        else:
            pildora(estado_fila, "Pendiente de revisar", tema.TEXTO_MUTED, tema.FONDO_CONTENIDO).pack(side="left")

    def _revisar(self, p: dict, aprobar: bool, estado_fila: ctk.CTkFrame, botones: tuple):
        motivo = ""
        if not aprobar:
            dialogo = ctk.CTkInputDialog(
                title="Devolver",
                text="¿Por qué la devuelve? El docente va a ver este motivo:",
            )
            motivo = (dialogo.get_input() or "").strip()
            if not motivo:
                return  # sin motivo no se devuelve

        for b in botones:
            b.configure(state="disabled")
        for w in estado_fila.winfo_children():
            w.destroy()
        ctk.CTkLabel(estado_fila, text="Guardando...", text_color=GRIS, anchor="w").pack(side="left")

        def listo(resultado):
            p["estado"] = resultado["estado"]
            p["motivo_devolucion"] = motivo if not aprobar else ""
            self._actualizar_resumen()
            self._redibujar()  # mueve la tarjeta a su lugar nuevo según el estado

        def fallo(exc):
            for b in botones:
                b.configure(state="normal")
            self._pintar_estado(estado_fila, p)  # vuelve a lo último guardado, no a lo que se intentó
            self.resumen_label.configure(text=str(exc), text_color=ROJO)

        en_segundo_plano(
            self,
            lambda: api_client.revisar_planeacion(self.sesion["token"], p["id"], aprobar, motivo),
            listo,
            fallo,
        )
