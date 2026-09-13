"""Cursos de cada docente (rol directivo). Un docente puede tener varios:
en la nómina, Wendy Valle figura con "Matemáticas niños" y "Español
adolescentes" como dos filas separadas.

El núcleo y el rango de edades viven en el curso y no en la persona,
porque cambian de un curso a otro aunque sea el mismo docente, y ambos
salen en el informe mensual —que también va por curso.

La carga de la nómina ya no crea cursos —no sabe de qué color va cada uno—
así que los cursos nuevos nacen todos desde acá. El color es obligatorio al
crear porque es lo que define quién lo revisa; el núcleo y las edades se
pueden completar después, editando. Por eso la edición no es un lujo, es
parte del alta.
"""

from __future__ import annotations

from tkinter import messagebox
from typing import Callable

import customtkinter as ctk

import api_client
from ui import tema
from ui.cargando import Cargando
from ui.tareas import cache, en_segundo_plano
from ui.widgets import campo_label, pildora

SIN_COLOR = "(sin asignar)"
AMBAR = tema.AMBAR
_MORADO, _MORADO_CHIP_BG = "#8e44ad", "#F3E8F8"
_GRIS_TEXTO_TABLA = "#5A665F"
_ANCHO_FORM = 400

# (clave interna, etiqueta del mockup, color de texto/borde cuando está
# elegido, fondo cuando está elegido)
_COLORES = [
    ("verde", "Verde", tema.VERDE_CHIP_TEXTO, tema.VERDE_CHIP_BG, tema.VERDE),
    ("morado", "Morado", _MORADO, _MORADO_CHIP_BG, _MORADO),
    ("", "Sin asignar", tema.TEXTO_MUTED, tema.FONDO_CONTENIDO, tema.BORDE_TARJETA),
]


class CursosScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None] | None = None):
        # Sin `on_volver` va montada como pestaña de CursosHubScreen.
        super().__init__(master, label_text="" if on_volver is None else "Cursos", fg_color="transparent")
        self.sesion = sesion
        self._docentes_por_nombre: dict[str, int] = {}
        self._nombre_por_docente_id: dict[int, str] = {}
        self._cursos_cache: list[dict] = []
        self._filtro_texto = ""
        self._color_elegido = ""
        self._color_botones: dict[str, ctk.CTkButton] = {}

        if on_volver is not None:
            ctk.CTkButton(
                self, text="← Volver", width=90, fg_color="transparent", border_width=1,
                text_color=tema.TEXTO_OSCURO, hover_color=tema.FONDO_CONTENIDO, command=on_volver,
            ).pack(anchor="w", pady=(0, 12))

        # Dos columnas como en el mockup: el alta a la izquierda con ancho
        # fijo, la lista de cursos existentes ocupa el resto.
        # fill="x" y no "both"/expand: `self` es un CTkScrollableFrame, y
        # un hijo directo suyo no puede "llenar" un alto disponible —esa
        # región mide lo que el contenido pida, no al revés. Pedirle
        # expand=True acá (y a los hijos de abajo) no solo no lograba que
        # la columna de la lista se estirara: además hacía que el resto de
        # los campos del formulario, más allá del 4º o 5º widget, quedaran
        # con tamaño degenerado 1x1 (visto a mano con winfo_height()) — el
        # cálculo de espacio "extra" de pack no tiene ningún límite real
        # del cual repartir dentro de un scrollable frame.
        cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        cuerpo.pack(fill="x")

        # width Y height explícitos (no solo width): sin los dos,
        # pack_propagate(False) fija el ancho pero el alto por defecto de
        # CTkFrame (200) recorta el resto del formulario; sin
        # pack_propagate(False), es el ancho el que se pierde (los hijos
        # con fill="x" no piden ningún ancho propio, así que el frame se
        # encoge al mínimo). 900 es de sobra para el contenido real; si
        # sobra alto no se nota, `tarjeta` no lo rellena (fill="x" nomás).
        columna_form = ctk.CTkFrame(cuerpo, fg_color="transparent", width=_ANCHO_FORM, height=900)
        # anchor="n": columna_form queda fija en 900 de alto (ver arriba) y
        # columna_lista es bastante más baja (crece con la cantidad real de
        # cursos) — sin esto, pack centra verticalmente al más chico dentro
        # de la fila compartida y "Cursos existentes" aparecía corrido bien
        # abajo de "Nuevo curso" en vez de arrancar a la misma altura.
        columna_form.pack(side="left", padx=(0, 22), anchor="n")
        columna_form.pack_propagate(False)

        tarjeta = ctk.CTkFrame(
            columna_form, fg_color=tema.FONDO_TARJETA, corner_radius=16,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        tarjeta.pack(fill="x")
        contenido = ctk.CTkFrame(tarjeta, fg_color="transparent")
        contenido.pack(fill="both", expand=True, padx=24, pady=24)

        ctk.CTkLabel(
            contenido, text="Nuevo curso", font=tema.fuente(17, "bold"), text_color=tema.TEXTO_OSCURO, anchor="w",
        ).pack(fill="x", pady=(0, 18))

        campo_label(contenido, "Docente").pack(fill="x")
        self.docente_menu = ctk.CTkOptionMenu(contenido, values=["(cargando...)"])
        self.docente_menu.pack(fill="x", pady=(7, 16))

        self.nombre_entry = self._campo(contenido, "Nombre del curso", "Ej: Matemáticas niños")
        self.nucleo_entry = self._campo(contenido, "Núcleo", "Ej: Matemáticas")

        campo_label(contenido, "Edades").pack(fill="x")
        fila_edades = ctk.CTkFrame(contenido, fg_color="transparent")
        fila_edades.pack(fill="x", pady=(7, 0))
        self.edad_desde_entry = ctk.CTkEntry(fila_edades, placeholder_text="desde")
        self.edad_desde_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(fila_edades, text="a", text_color=tema.TEXTO_MUTED).pack(side="left", padx=10)
        self.edad_hasta_entry = ctk.CTkEntry(fila_edades, placeholder_text="hasta")
        self.edad_hasta_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(fila_edades, text="años", text_color=tema.TEXTO_MUTED).pack(side="left", padx=(10, 0))
        ctk.CTkLabel(
            contenido, text="Sale en la cuenta de cobro.", font=tema.fuente(11), text_color=tema.TEXTO_MUTED,
            anchor="w",
        ).pack(fill="x", pady=(6, 16))

        # El color va en el alta y no solo en «Editar»: un curso que nace sin
        # color no lo revisa nadie más que el administrador, y sin avisar.
        campo_label(contenido, "Color · define quién lo revisa").pack(fill="x")
        fila_color = ctk.CTkFrame(contenido, fg_color="transparent")
        fila_color.pack(fill="x", pady=(7, 0))
        for clave, etiqueta, color_texto, color_fondo, color_borde in _COLORES:
            boton = ctk.CTkButton(
                fila_color, text=etiqueta, font=tema.fuente(12), fg_color=tema.FONDO_TARJETA, border_width=1,
                border_color=tema.BORDE_TARJETA, text_color=tema.TEXTO_MUTED, hover_color=tema.FONDO_CONTENIDO,
                command=lambda c=clave: self._elegir_color(c),
            )
            boton.pack(side="left", fill="x", expand=True, padx=(0 if clave == "verde" else 6, 0))
            self._color_botones[clave] = boton
        self._elegir_color("")  # arranca en "Sin asignar"

        self.error_label = ctk.CTkLabel(
            contenido, text="", text_color=tema.ROJO, wraplength=_ANCHO_FORM - 48, justify="left", anchor="w",
        )
        self.error_label.pack(fill="x", pady=(16, 0))

        self.crear_boton = ctk.CTkButton(
            contenido, text="Crear curso", fg_color=tema.VERDE_OSCURO,
            hover_color=tema.VERDE_OSCURO_ACTIVO, command=self._crear,
        )
        self.crear_boton.pack(fill="x", pady=(12, 0))

        columna_lista = ctk.CTkFrame(cuerpo, fg_color="transparent")
        columna_lista.pack(side="left", fill="x", expand=True, anchor="n")

        encabezado_lista = ctk.CTkFrame(columna_lista, fg_color="transparent")
        encabezado_lista.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(
            encabezado_lista, text="Cursos existentes", font=tema.fuente(18, "bold"), text_color=tema.TEXTO_OSCURO,
        ).pack(side="left", padx=(0, 12))
        self._pildora_activos = pildora(encabezado_lista, "0 activos", _GRIS_TEXTO_TABLA, tema.FONDO_CONTENIDO)
        self._pildora_activos.pack(side="left")

        self.lista_contenedor = ctk.CTkFrame(
            columna_lista, fg_color=tema.FONDO_TARJETA, corner_radius=16,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        self.lista_contenedor.pack(fill="x")
        self.cargando_label = ctk.CTkLabel(self.lista_contenedor, text="Cargando...", text_color=tema.TEXTO_MUTED)
        self.cargando_label.pack(anchor="w", padx=20, pady=16)

        self._cargar_docentes()

    def _elegir_color(self, clave: str):
        self._color_elegido = clave
        for c, etiqueta, color_texto, color_fondo, color_borde in _COLORES:
            boton = self._color_botones[c]
            elegido = c == clave
            boton.configure(
                fg_color=color_fondo if elegido else tema.FONDO_TARJETA,
                border_width=2 if elegido else 1,
                border_color=color_borde if elegido else tema.BORDE_TARJETA,
                text_color=color_texto if elegido else tema.TEXTO_MUTED,
            )

    def _campo(self, padre, etiqueta: str, placeholder: str = "") -> ctk.CTkEntry:
        campo_label(padre, etiqueta).pack(fill="x")
        entry = ctk.CTkEntry(padre, placeholder_text=placeholder)
        entry.pack(fill="x", pady=(7, 16))
        return entry

    def _trabajando(self, texto: str):
        self.error_label.configure(text=texto, text_color=tema.TEXTO_MUTED)

    # --- carga (en segundo plano: la lista de usuarios y cursos puede costar
    # un viaje al backend si el caché no está caliente, y hacerlo en el hilo
    # de Tk congelaba la ventana un par de segundos al abrir) ---------------

    def _cargar_docentes(self):
        def listo(usuarios):
            docentes = [u for u in usuarios if u["rol"] in ("docente", "ambos")]
            self._docentes_por_nombre = {d["nombre"]: d["id"] for d in docentes}
            self._nombre_por_docente_id = {d["id"]: d["nombre"] for d in docentes}

            nombres = list(self._docentes_por_nombre) or ["(sin docentes)"]
            self.docente_menu.configure(values=nombres)
            self.docente_menu.set(nombres[0])
            self._cargar_lista()

        en_segundo_plano(
            self,
            lambda: cache.usuarios(self.sesion["token"]),
            listo,
            lambda exc: self.error_label.configure(text=str(exc), text_color=tema.ROJO),
        )

    def filtrar(self, texto: str):
        """Lo llama el buscador del encabezado superior (ver
        `CursosHubScreen._al_cambiar_pestana`) — filtra por nombre,
        docente o núcleo sobre lo que ya está en memoria."""
        self._filtro_texto = texto.strip().lower()
        self._renderizar_lista()

    def _cargar_lista(self):
        for w in self.lista_contenedor.winfo_children():
            w.destroy()
        Cargando(self.lista_contenedor, texto="Cargando...").pack(pady=16)

        def listo(cursos):
            self._cursos_cache = cursos
            self._renderizar_lista()

        def fallo(exc):
            for w in self.lista_contenedor.winfo_children():
                w.destroy()
            self.error_label.configure(text=str(exc), text_color=tema.ROJO)

        en_segundo_plano(
            self,
            lambda: cache.cursos(self.sesion["token"]),
            listo,
            fallo,
        )

    def _renderizar_lista(self):
        """Redibuja con lo que ya está en `self._cursos_cache`, sin pedir
        nada nuevo al backend — la llaman tanto la carga inicial como el
        buscador."""
        for w in self.lista_contenedor.winfo_children():
            w.destroy()

        activos = [c for c in self._cursos_cache if c.get("activo")]
        self._pildora_activos.configure(text=f"  {len(activos)} activos  ")
        if self._filtro_texto:
            def coincide(c):
                docente = self._nombre_por_docente_id.get(c.get("docente_id"), "")
                texto = f"{c.get('nombre', '')} {docente} {c.get('nucleo', '')}".lower()
                return self._filtro_texto in texto
            activos = [c for c in activos if coincide(c)]

        if not activos:
            mensaje = "Ningún curso coincide con la búsqueda." if self._filtro_texto else "Todavía no hay cursos."
            ctk.CTkLabel(self.lista_contenedor, text=mensaje, text_color=tema.GRIS).pack(
                anchor="w", padx=20, pady=16
            )
            return

        # Los que les falta núcleo o edad van primero: son los que hay
        # que completar antes de que su cuenta de cobro salga bien.
        def incompleto(c):
            return not c.get("nucleo") or not (c.get("edad_desde") and c.get("edad_hasta"))

        # Un curso sin color tampoco está terminado —no tiene quien lo
        # revise— así que sube al mismo grupo de "hay que completar".
        def pendiente(c):
            return incompleto(c) or not str(c.get("color") or "").strip()

        ordenados = sorted(activos, key=lambda c: (not pendiente(c), str(c["nombre"]).lower()))
        for indice, curso in enumerate(ordenados):
            self._fila_curso(curso, incompleto(curso), es_ultima=(indice == len(ordenados) - 1))

    def _fila_curso(self, curso: dict, incompleto: bool, es_ultima: bool):
        # Una sola tabla con filas separadas por una línea fina —como en el
        # mockup— en vez de una tarjeta propia por curso.
        fila = ctk.CTkFrame(self.lista_contenedor, fg_color="transparent")
        fila.pack(fill="x")
        cuerpo = ctk.CTkFrame(fila, fg_color="transparent")
        cuerpo.pack(fill="x", padx=22, pady=17)

        color = str(curso.get("color") or "").strip().lower()
        color_barra = {"verde": tema.VERDE, "morado": _MORADO}.get(color, tema.BORDE_TARJETA)
        ctk.CTkFrame(cuerpo, width=5, height=38, corner_radius=3, fg_color=color_barra).pack(side="left", padx=(0, 18))

        info = ctk.CTkFrame(cuerpo, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            info, text=curso["nombre"], font=tema.fuente(15, "bold"), text_color=tema.TEXTO_OSCURO, anchor="w",
        ).pack(fill="x")

        docente = self._nombre_por_docente_id.get(curso["docente_id"], f"id {curso['docente_id']}")
        meta = f"{docente}  ·  núcleo: {curso.get('nucleo') or '—'}"
        if curso.get("edad_desde") or curso.get("edad_hasta"):
            meta += f"  ·  {curso.get('edad_desde')}–{curso.get('edad_hasta')} años"
        ctk.CTkLabel(
            info, text=meta, text_color=tema.TEXTO_MUTED, font=tema.fuente(12), anchor="w",
        ).pack(fill="x", pady=(3, 0))

        if incompleto:
            pildora(info, "falta núcleo o edades", AMBAR, tema.AMBAR_CHIP_BG).pack(anchor="w", pady=(8, 0))

        if color == "verde":
            pildora(cuerpo, "Verde", tema.VERDE_CHIP_TEXTO, tema.VERDE_CHIP_BG).pack(side="left", padx=(12, 0))
        elif color == "morado":
            pildora(cuerpo, "Morado", _MORADO, _MORADO_CHIP_BG).pack(side="left", padx=(12, 0))
        else:
            pildora(cuerpo, "Sin color: solo lo revisa el administrador", AMBAR, tema.AMBAR_CHIP_BG).pack(
                side="left", padx=(12, 0)
            )

        botones = ctk.CTkFrame(cuerpo, fg_color="transparent")
        botones.pack(side="right", padx=(16, 0))
        ctk.CTkButton(
            botones, text="Editar", width=80, fg_color="transparent", border_width=1, border_color=tema.VERDE,
            text_color=tema.VERDE_CHIP_TEXTO, hover_color=tema.VERDE_CHIP_BG,
            command=lambda c=curso: self._editar(c),
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            botones, text="Desactivar", width=100, fg_color="transparent", border_width=1, border_color="#F0D2CE",
            text_color=tema.ROJO, hover_color=tema.ROJO_CHIP_BG,
            command=lambda c=curso: self._desactivar(c),
        ).pack(side="left")

        if not es_ultima:
            ctk.CTkFrame(self.lista_contenedor, fg_color=tema.BORDE_TARJETA, height=1).pack(fill="x")

    def _crear(self):
        docente_id = self._docentes_por_nombre.get(self.docente_menu.get())
        nombre = self.nombre_entry.get().strip()
        if docente_id is None or not nombre:
            self.error_label.configure(text="Elija un docente y escriba el nombre del curso.", text_color=tema.ROJO)
            return
        if not self._color_elegido:
            self.error_label.configure(
                text="Elija el color del curso: es lo que define quién lo revisa.", text_color=tema.ROJO
            )
            return

        datos = {
            "docente_id": docente_id,
            "nombre": nombre,
            "nucleo": self.nucleo_entry.get().strip(),
            "edad_desde": self.edad_desde_entry.get().strip(),
            "edad_hasta": self.edad_hasta_entry.get().strip(),
            "color": self._color_elegido,
        }

        self.crear_boton.configure(state="disabled")
        self._trabajando("Creando...")

        def listo(_r):
            self.crear_boton.configure(state="normal")
            cache.invalidar("cursos")
            for entry in (self.nombre_entry, self.nucleo_entry, self.edad_desde_entry, self.edad_hasta_entry):
                entry.delete(0, "end")
            self._elegir_color("")
            self._cargar_lista()
            self.error_label.configure(text=f"Curso «{nombre}» creado ✓", text_color=tema.VERDE)

        def fallo(exc):
            self.crear_boton.configure(state="normal")
            self.error_label.configure(text=str(exc), text_color=tema.ROJO)

        en_segundo_plano(
            self,
            lambda: api_client.crear_curso(self.sesion["token"], datos),
            listo,
            fallo,
        )

    def _editar(self, curso: dict):
        DialogoEditarCurso(
            self, curso, self._docentes_por_nombre, self._guardar_edicion,
            es_admin=bool(self.sesion.get("es_admin")),
        )

    def _guardar_edicion(self, curso_id: int, cambios: dict, dialogo):
        def listo(_r):
            cache.invalidar("cursos")
            dialogo.destroy()
            self._cargar_lista()
            self.error_label.configure(text="Curso actualizado ✓", text_color=tema.VERDE)

        en_segundo_plano(
            self,
            lambda: api_client.editar_curso(self.sesion["token"], curso_id, cambios),
            listo,
            lambda exc: dialogo.mostrar_error(str(exc)),
        )

    def _desactivar(self, curso: dict):
        if not messagebox.askyesno(
            "Desactivar curso",
            f"¿Desactivar «{curso['nombre']}»?\n\n"
            "No se borra: las planeaciones e informes de meses anteriores lo siguen usando. "
            "Solo deja de aparecer para cargar clases nuevas.",
        ):
            return

        self._trabajando("Desactivando...")

        def listo(_r):
            cache.invalidar("cursos")
            self._cargar_lista()
            self.error_label.configure(text="Curso desactivado.", text_color=tema.VERDE)

        en_segundo_plano(
            self,
            lambda: api_client.desactivar_curso(self.sesion["token"], curso["id"]),
            listo,
            lambda exc: self.error_label.configure(text=str(exc), text_color=tema.ROJO),
        )


class DialogoEditarCurso(ctk.CTkToplevel):
    """Ventanita para completar/corregir un curso, incluido reasignarlo a
    otro docente. Cambiar el docente NO toca las planeaciones e informes
    ya cargados: cada uno guarda su propio docente_id de cuando se creó,
    así que siguen atribuidos a quien los cargó — el curso simplemente deja
    de aparecerle a partir de ahora al que lo tenía y empieza a aparecerle
    al nuevo."""

    def __init__(
        self, master, curso: dict, docentes_por_nombre: dict[str, int], on_guardar,
        es_admin: bool = False,
    ):
        super().__init__(master)
        self.curso = curso
        self.on_guardar = on_guardar
        self._docentes_por_nombre = docentes_por_nombre
        self._nombre_docente_original = next(
            (nombre for nombre, id_ in docentes_por_nombre.items() if id_ == curso.get("docente_id")),
            None,
        )
        self._excluido_certificado_original = bool(curso.get("excluido_certificado"))

        self.title("Editar curso")
        self.geometry(f"380x{560 if es_admin else 490}")
        self.transient(master.winfo_toplevel())
        # Esperar a que la ventana exista antes de robar el foco, si no
        # customtkinter tira error en algunos equipos.
        self.after(200, self.grab_set)

        ctk.CTkLabel(
            self, text=curso["nombre"], font=tema.fuente(15, "bold"), text_color=tema.TEXTO_OSCURO,
        ).pack(pady=(16, 8))

        campo_label(self, "Docente").pack(fill="x", padx=20)
        nombres = list(docentes_por_nombre) or ["(sin docentes)"]
        self.docente_menu = ctk.CTkOptionMenu(self, width=340, values=nombres)
        self.docente_menu.pack(padx=20)
        self.docente_menu.set(self._nombre_docente_original or nombres[0])

        self.nombre_entry = self._campo("Nombre del curso", curso.get("nombre"))
        self.nucleo_entry = self._campo("Núcleo", curso.get("nucleo"))

        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.pack(pady=(8, 0))
        ctk.CTkLabel(fila, text="Edades", width=60, anchor="w", text_color=tema.TEXTO_MUTED).pack(side="left")
        self.desde_entry = ctk.CTkEntry(fila, width=60, placeholder_text="desde")
        self.desde_entry.pack(side="left")
        if curso.get("edad_desde"):
            self.desde_entry.insert(0, str(curso["edad_desde"]))
        ctk.CTkLabel(fila, text="a", text_color=tema.TEXTO_MUTED).pack(side="left", padx=6)
        self.hasta_entry = ctk.CTkEntry(fila, width=60, placeholder_text="hasta")
        self.hasta_entry.pack(side="left")
        if curso.get("edad_hasta"):
            self.hasta_entry.insert(0, str(curso["edad_hasta"]))

        # El color decide quién revisa el curso: verde lo revisa Mariangel,
        # morado Lorena (ver Config revisor_verde/revisor_morado).
        campo_label(self, "Color (define quién lo revisa)").pack(fill="x", padx=20, pady=(10, 0))
        self.color_menu = ctk.CTkOptionMenu(self, width=340, values=[SIN_COLOR, "verde", "morado"])
        self.color_menu.pack(padx=20)
        self.color_menu.set(str(curso.get("color") or SIN_COLOR))

        # Solo administrador: es lo mismo que decide quién genera y ve el
        # certificado de pago (Revisar → Certificado de pago), así que el
        # control de a quién se le excluye de ese documento queda con el
        # mismo permiso.
        self.excluido_certificado_var = ctk.BooleanVar(value=self._excluido_certificado_original)
        if es_admin:
            ctk.CTkFrame(self, fg_color=tema.DIVISOR, height=1).pack(fill="x", padx=20, pady=(14, 10))
            ctk.CTkSwitch(
                self, text="Excluir del certificado de pago", variable=self.excluido_certificado_var,
                onvalue=True, offvalue=False,
            ).pack(padx=20, anchor="w")
            ctk.CTkLabel(
                self,
                text="El curso sigue activo igual — solo no certifica horas en ese documento.",
                font=tema.fuente(11), text_color=tema.TEXTO_MUTED, anchor="w", justify="left",
                wraplength=340,
            ).pack(fill="x", padx=20, pady=(2, 0))

        self.error_label = ctk.CTkLabel(self, text="", text_color=tema.ROJO, wraplength=340)
        self.error_label.pack(pady=(10, 0))

        botones = ctk.CTkFrame(self, fg_color="transparent")
        botones.pack(pady=16)
        ctk.CTkButton(
            botones, text="Cancelar", width=100, fg_color="transparent", border_width=1,
            text_color=tema.TEXTO_OSCURO, hover_color=tema.FONDO_CONTENIDO, command=self.destroy,
        ).pack(side="left", padx=6)
        self.guardar_boton = ctk.CTkButton(
            botones, text="Guardar", width=100, fg_color=tema.VERDE_OSCURO,
            hover_color=tema.VERDE_OSCURO_ACTIVO, command=self._guardar,
        )
        self.guardar_boton.pack(side="left", padx=6)

    def _campo(self, etiqueta: str, valor) -> ctk.CTkEntry:
        campo_label(self, etiqueta).pack(fill="x", padx=20, pady=(8, 0))
        entry = ctk.CTkEntry(self, width=340)
        entry.pack(padx=20)
        if valor:
            entry.insert(0, str(valor))
        return entry

    def mostrar_error(self, texto: str):
        self.guardar_boton.configure(state="normal", text="Guardar")
        self.error_label.configure(text=texto)

    def _guardar(self):
        nombre = self.nombre_entry.get().strip()
        if not nombre:
            self.error_label.configure(text="El nombre no puede quedar vacío.")
            return

        nombre_docente = self.docente_menu.get()
        docente_id = self._docentes_por_nombre.get(nombre_docente)
        cambia_docente = docente_id is not None and nombre_docente != self._nombre_docente_original
        if cambia_docente and not messagebox.askyesno(
            "Cambiar de docente",
            f"«{self.curso['nombre']}» va a pasar de {self._nombre_docente_original or 'sin asignar'} "
            f"a {nombre_docente}.\n\n"
            "Las planeaciones e informes ya cargados siguen atribuidos a quien los cargó — "
            "esto solo cambia quién ve y carga el curso de ahora en adelante.\n\n¿Confirmar?",
        ):
            return

        # Volver a incluirlo (pasa de excluido a NO excluido) es lo que
        # puede hacer que alguien empiece a cobrar de nuevo en el próximo
        # certificado — a diferencia de excluirlo, que solo dice "no le
        # certifiques esto", nunca "hay que pagarle": esa dirección pide
        # confirmación explícita, es un documento importante.
        excluido_certificado = self.excluido_certificado_var.get()
        vuelve_a_incluirse = self._excluido_certificado_original and not excluido_certificado
        if vuelve_a_incluirse and not messagebox.askyesno(
            "Volver a incluir en el certificado",
            f"«{self.curso['nombre']}» va a volver a aparecer (con sus horas) en el próximo "
            "certificado de pago.\n\n¿Confirmar?",
        ):
            return

        color = self.color_menu.get()
        cambios = {
            "nombre": nombre,
            "nucleo": self.nucleo_entry.get().strip(),
            "edad_desde": self.desde_entry.get().strip(),
            "edad_hasta": self.hasta_entry.get().strip(),
            "color": "" if color == SIN_COLOR else color,
            "excluido_certificado": excluido_certificado,
        }
        if docente_id is not None:
            cambios["docente_id"] = docente_id
        self.guardar_boton.configure(state="disabled", text="Guardando...")
        self.on_guardar(self.curso["id"], cambios, self)
