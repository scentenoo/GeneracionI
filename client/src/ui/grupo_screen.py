"""Gestión de los estudiantes de un curso (rol directivo, spec sección 3:
"Crea y gestiona el grupo de estudiantes de cada docente").

Los estudiantes cuelgan del curso, así que un docente con dos cursos
tiene dos listas separadas y acá se elige de cuál."""

from __future__ import annotations

from tkinter import filedialog, messagebox
from typing import Callable

import customtkinter as ctk

import api_client
from ui import tema
from ui.cargando import Cargando
from ui.tareas import cache, en_segundo_plano
from ui.widgets import pildora

_GRIS_TEXTO_TABLA = "#5A665F"
_FONDO_SELECTOR_CURSO = "#F8FAF8"
_ANCHO_PANEL_DERECHO = 380


class GrupoScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None] | None = None):
        # Sin `on_volver` va montada como pestaña de CursosHubScreen.
        super().__init__(
            master, label_text="" if on_volver is None else "Estudiantes de un curso", fg_color="transparent",
        )
        self.sesion = sesion
        self.on_volver = on_volver
        self._cursos_por_etiqueta: dict[str, dict] = {}
        self._checkboxes: dict[int, tuple[ctk.CTkCheckBox, ctk.BooleanVar]] = {}
        self._estudiantes_cache: list[dict] = []
        self._filtro_texto = ""

        if on_volver is not None:
            ctk.CTkButton(
                self, text="← Volver", width=90, fg_color="transparent", border_width=1,
                text_color=tema.TEXTO_OSCURO, hover_color=tema.FONDO_CONTENIDO, command=on_volver,
            ).pack(anchor="w", pady=(0, 12))

        # Dos columnas como en el mockup: el panel de estudiantes ocupa el
        # resto, "Agregar uno" / "Importar lista" quedan a la derecha con
        # ancho fijo.
        #
        # Todo acá abajo usa fill="x" (nunca "both"/expand vertical): `self`
        # es un CTkScrollableFrame, y un hijo directo suyo no puede
        # "llenar" un alto disponible —esa región mide lo que el contenido
        # pida, no al revés—. Pedir expand=True acá no solo no estiraba la
        # columna: además dejaba con tamaño degenerado 1x1 a los widgets
        # que vinieran después del 4º o 5º (visto a mano con
        # winfo_height() — ver la misma nota en cursos_screen.py).
        cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        cuerpo.pack(fill="x")

        columna_izquierda = ctk.CTkFrame(cuerpo, fg_color="transparent")
        columna_izquierda.pack(side="left", fill="x", expand=True, padx=(0, 22), anchor="n")

        tarjeta = ctk.CTkFrame(
            columna_izquierda, fg_color=tema.FONDO_TARJETA, corner_radius=16,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        tarjeta.pack(fill="x")
        contenido = ctk.CTkFrame(tarjeta, fg_color="transparent")
        contenido.pack(fill="x", padx=24, pady=22)

        encabezado = ctk.CTkFrame(contenido, fg_color="transparent")
        encabezado.pack(fill="x", pady=(0, 18))
        ctk.CTkLabel(
            encabezado, text="Estudiantes actuales", font=tema.fuente(16, "bold"), text_color=tema.TEXTO_OSCURO,
        ).pack(side="left", padx=(0, 12))
        self._pildora_cantidad = pildora(encabezado, "0 en el curso", _GRIS_TEXTO_TABLA, tema.FONDO_CONTENIDO)
        self._pildora_cantidad.pack(side="left")

        marco_curso = ctk.CTkFrame(
            contenido, corner_radius=10, border_width=1, border_color=tema.BORDE_TARJETA,
            fg_color=_FONDO_SELECTOR_CURSO,
        )
        marco_curso.pack(fill="x", pady=(0, 18))
        self.curso_menu = ctk.CTkOptionMenu(
            marco_curso, values=["(cargando...)"], command=lambda _v: self._cargar(),
            fg_color=_FONDO_SELECTOR_CURSO, button_color=_FONDO_SELECTOR_CURSO,
            button_hover_color=tema.FONDO_CONTENIDO,
        )
        self.curso_menu.pack(fill="x", padx=2, pady=2)

        self.lista_contenedor = ctk.CTkFrame(contenido, fg_color="transparent")
        self.lista_contenedor.pack(fill="x")
        self.lista_contenedor.grid_columnconfigure((0, 1), weight=1, uniform="estudiantes")

        self.error_label = ctk.CTkLabel(
            contenido, text="", text_color=tema.ROJO, wraplength=700, justify="left", anchor="w",
        )
        self.error_label.pack(fill="x", pady=(14, 0))

        self.quitar_boton = ctk.CTkButton(
            contenido, text="Quitar seleccionados", fg_color="transparent", border_width=1,
            border_color="#F0D2CE", text_color=tema.ROJO, hover_color=tema.ROJO_CHIP_BG,
            command=self._quitar_seleccionados,
        )
        self.quitar_boton.pack(anchor="e", pady=(14, 0))

        # Columna derecha: agregar de a uno + importar CSV, cada una en su
        # propia tarjeta — como en el mockup.
        #
        # width Y height explícitos a propósito (no solo width): ver la
        # misma nota en cursos_screen.py — sin los dos, pack_propagate(False)
        # deja el ancho fijo pero el alto por defecto de CTkFrame (200)
        # recorta el resto. 700 es de sobra para las dos tarjetas de acá.
        columna_derecha = ctk.CTkFrame(cuerpo, fg_color="transparent", width=_ANCHO_PANEL_DERECHO, height=700)
        columna_derecha.pack(side="left", anchor="n")
        columna_derecha.pack_propagate(False)

        tarjeta_agregar = ctk.CTkFrame(
            columna_derecha, fg_color=tema.FONDO_TARJETA, corner_radius=16,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        tarjeta_agregar.pack(fill="x", pady=(0, 16))
        contenido_agregar = ctk.CTkFrame(tarjeta_agregar, fg_color="transparent")
        contenido_agregar.pack(fill="x", padx=22, pady=22)
        ctk.CTkLabel(
            contenido_agregar, text="Agregar uno", font=tema.fuente(15, "bold"), text_color=tema.TEXTO_OSCURO,
            anchor="w",
        ).pack(fill="x", pady=(0, 14))
        self.nuevo_nombre_entry = ctk.CTkEntry(contenido_agregar, placeholder_text="Nombre del estudiante")
        self.nuevo_nombre_entry.pack(fill="x")
        self.agregar_boton = ctk.CTkButton(
            contenido_agregar, text="+ Agregar", fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER,
            command=self._agregar_uno,
        )
        self.agregar_boton.pack(fill="x", pady=(10, 0))

        tarjeta_importar = ctk.CTkFrame(
            columna_derecha, fg_color=tema.FONDO_TARJETA, corner_radius=16,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        tarjeta_importar.pack(fill="x")
        contenido_importar = ctk.CTkFrame(tarjeta_importar, fg_color="transparent")
        contenido_importar.pack(fill="x", padx=22, pady=22)
        ctk.CTkLabel(
            contenido_importar, text="Importar lista", font=tema.fuente(15, "bold"), text_color=tema.TEXTO_OSCURO,
            anchor="w",
        ).pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(
            contenido_importar,
            text="Archivo CSV con una columna nombre y una fila por estudiante.",
            font=tema.fuente(12), text_color=tema.TEXTO_MUTED, anchor="w", justify="left", wraplength=300,
        ).pack(fill="x", pady=(0, 14))
        zona_csv = ctk.CTkFrame(
            contenido_importar, corner_radius=12, fg_color="#FAFBFA",
            border_width=2, border_color=tema.BORDE_TARJETA,
        )
        zona_csv.pack(fill="x")
        contenido_zona = ctk.CTkFrame(zona_csv, fg_color="transparent")
        contenido_zona.pack(pady=22)
        ctk.CTkFrame(
            contenido_zona, width=44, height=44, corner_radius=11, fg_color=tema.FONDO_CONTENIDO,
        ).pack(pady=(0, 12))
        ctk.CTkButton(
            contenido_zona, text="Importar CSV…", fg_color="transparent", border_width=1,
            text_color=tema.TEXTO_OSCURO, hover_color=tema.FONDO_CONTENIDO, command=self._importar_csv,
        ).pack()

        self._cargar_cursos()

    # --- feedback ---------------------------------------------------------

    def _trabajando(self, texto: str):
        """Deja claro que la llamada está en curso, en vez de dejar fijo el
        mensaje de la operación anterior."""
        self.error_label.configure(text=texto, text_color=tema.TEXTO_MUTED)
        self.update_idletasks()

    # --- carga ------------------------------------------------------------

    def _cargar_cursos(self):
        self._trabajando("Cargando cursos...")

        def traer():
            token = self.sesion["token"]
            return cache.cursos(token), cache.nombres_de_usuarios(token)

        def listo(datos):
            cursos, usuarios = datos
            activos = [c for c in cursos if c.get("activo")]
            self._cursos_por_etiqueta = {
                f"{c['nombre']} — {usuarios.get(c['docente_id'], 'docente ' + str(c['docente_id']))}": c
                for c in activos
            }
            etiquetas = list(self._cursos_por_etiqueta) or ["(sin cursos)"]
            self.curso_menu.configure(values=etiquetas)
            self.curso_menu.set(etiquetas[0])
            self.error_label.configure(text="")
            self._cargar()

        en_segundo_plano(self, traer, listo, self._mostrar_error)

    def _mostrar_error(self, exc):
        for w in self.lista_contenedor.winfo_children():
            w.destroy()
        self.error_label.configure(text=str(exc), text_color=tema.ROJO)

    def _curso_actual(self) -> dict | None:
        return self._cursos_por_etiqueta.get(self.curso_menu.get())

    def filtrar(self, texto: str):
        """Lo llama el buscador del encabezado superior (ver
        `CursosHubScreen._al_cambiar_pestana`) — filtra por nombre sobre
        los estudiantes del curso elegido, ya cargados en memoria."""
        self._filtro_texto = texto.strip().lower()
        self._renderizar_estudiantes()

    def _cargar(self):
        for w in self.lista_contenedor.winfo_children():
            w.destroy()
        self._checkboxes.clear()

        curso = self._curso_actual()
        if not curso:
            return

        self.error_label.configure(text="")
        Cargando(self.lista_contenedor, texto="Cargando estudiantes...").pack(pady=16)

        def listo(estudiantes):
            self._estudiantes_cache = estudiantes
            self._renderizar_estudiantes()

        en_segundo_plano(
            self,
            lambda: api_client.obtener_estudiantes(self.sesion["token"], curso["id"]),
            listo,
            self._mostrar_error,
        )

    def _renderizar_estudiantes(self):
        """Redibuja con lo que ya está en `self._estudiantes_cache`, sin
        pedir nada nuevo al backend — la llaman tanto la carga inicial
        como el buscador. Las casillas marcadas se pierden al refiltrar
        (es lo mismo que ya pasaba al recargar), no vale la pena guardar
        selección entre filtros para una lista que se usa para tildar y
        quitar de una sola vez."""
        for w in self.lista_contenedor.winfo_children():
            w.destroy()
        self._checkboxes.clear()

        estudiantes = self._estudiantes_cache
        self._pildora_cantidad.configure(text=f"  {len(estudiantes)} en el curso  ")
        if self._filtro_texto:
            estudiantes = [e for e in estudiantes if self._filtro_texto in str(e["nombre"]).lower()]

        if not estudiantes:
            mensaje = (
                "Ningún estudiante coincide con la búsqueda." if self._filtro_texto
                else "Todavía no hay estudiantes."
            )
            ctk.CTkLabel(self.lista_contenedor, text=mensaje, text_color=tema.TEXTO_MUTED).grid(
                row=0, column=0, columnspan=2, sticky="w", pady=6
            )
            return

        # Grilla de 2 columnas, como en el mockup (antes: una sola columna
        # de filas apiladas).
        for indice, est in enumerate(estudiantes):
            var = ctk.BooleanVar(value=False)
            # Quien está en otro curso sigue inscrito ahí si lo sacás de
            # este: conviene verlo antes de marcarlo.
            otros = est.get("otros_cursos", 0)
            fila = ctk.CTkFrame(
                self.lista_contenedor, fg_color="transparent", corner_radius=11,
                border_width=1, border_color=tema.DIVISOR,
            )
            fila.grid(
                row=indice // 2, column=indice % 2, sticky="nsew",
                padx=(0, 5) if indice % 2 == 0 else (5, 0), pady=4,
            )
            contenido_fila = ctk.CTkFrame(fila, fg_color="transparent")
            contenido_fila.pack(fill="x", padx=14, pady=10)
            cb = ctk.CTkCheckBox(
                contenido_fila, text=str(est["nombre"]), variable=var, text_color=tema.TEXTO_OSCURO,
                fg_color=tema.VERDE_OSCURO, hover_color=tema.VERDE_OSCURO_ACTIVO,
            )
            cb.pack(side="left")
            if otros:
                ctk.CTkLabel(
                    contenido_fila, text=f"también en {otros} curso{'s' if otros > 1 else ''}",
                    text_color=tema.TEXTO_MUTED, font=tema.fuente(11), anchor="e",
                ).pack(side="right")
            self._checkboxes[est["id"]] = (cb, var)

    # --- acciones ---------------------------------------------------------

    def _importar_csv(self):
        curso = self._curso_actual()
        if not curso:
            self.error_label.configure(text="Elija un curso primero.", text_color=tema.ROJO)
            return

        ruta = filedialog.askopenfilename(title="Elija el CSV de estudiantes", filetypes=[("CSV", "*.csv")])
        if not ruta:
            return

        with open(ruta, encoding="utf-8") as f:
            contenido = f.read()

        self._trabajando("Importando...")

        def listo(resultado):
            self._cargar()
            # Los reusados son los que ya estaban en otro curso: se
            # inscriben acá con la misma ficha, no se duplican.
            reusados = resultado.get("reusados", 0)
            texto = f"Se importaron {resultado['creados']} estudiantes."
            if reusados:
                texto += f" Otros {reusados} ya existían en el programa y se inscribieron acá."
            self.error_label.configure(text=texto, text_color=tema.VERDE)

        en_segundo_plano(
            self,
            lambda: api_client.importar_estudiantes(self.sesion["token"], curso["id"], contenido),
            listo,
            self._mostrar_error,
        )

    def _agregar_uno(self):
        curso = self._curso_actual()
        nombre = self.nuevo_nombre_entry.get().strip()
        if not curso or not nombre:
            self.error_label.configure(text="Elija un curso y escriba un nombre.", text_color=tema.ROJO)
            return

        self.agregar_boton.configure(state="disabled")
        self._trabajando(f"Agregando a {nombre}...")

        def listo(_resultado):
            self.agregar_boton.configure(state="normal")
            self.nuevo_nombre_entry.delete(0, "end")
            self._cargar()
            self.error_label.configure(text=f"{nombre} agregado ✓", text_color=tema.VERDE)

        def fallo(exc):
            self.agregar_boton.configure(state="normal")
            self._mostrar_error(exc)

        en_segundo_plano(
            self,
            lambda: api_client.modificar_grupo(
                self.sesion["token"], curso["id"], {"agregar": [{"nombre": nombre}]}
            ),
            listo,
            fallo,
        )

    def _quitar_seleccionados(self):
        curso = self._curso_actual()
        ids_a_quitar = [est_id for est_id, (_, var) in self._checkboxes.items() if var.get()]
        if not curso or not ids_a_quitar:
            self.error_label.configure(text="Marque al menos un estudiante para quitar.", text_color=tema.ROJO)
            return

        # La asistencia ya guardada no se toca (es una copia del día), pero
        # el estudiante deja de aparecer para las clases que vienen.
        if not messagebox.askyesno(
            "Quitar estudiantes",
            f"¿Quitar {len(ids_a_quitar)} estudiante(s) de este curso?\n\n"
            "Las planeaciones ya guardadas conservan la asistencia de ese día; "
            "dejan de aparecer para las clases nuevas.",
            icon="warning",
            default="no",
        ):
            return

        self.quitar_boton.configure(state="disabled")
        self._trabajando("Quitando...")

        def listo(_resultado):
            self.quitar_boton.configure(state="normal")
            self._cargar()
            self.error_label.configure(
                text=f"Se quitaron {len(ids_a_quitar)} estudiantes.", text_color=tema.VERDE
            )

        def fallo(exc):
            self.quitar_boton.configure(state="normal")
            self._mostrar_error(exc)

        en_segundo_plano(
            self,
            lambda: api_client.modificar_grupo(self.sesion["token"], curso["id"], {"quitar": ids_a_quitar}),
            listo,
            fallo,
        )
