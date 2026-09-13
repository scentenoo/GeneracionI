"""Revisar horas externas de TODO el equipo (solo administrador): junta
las horas de gestión de los directivos y las horas_externas que cargan
los docentes en sus actividades (reuniones, claustros de un curso).

Son dos fuentes con dos flujos distintos (ver obtener_horas_del_equipo en
el backend): las de gestión llevan evidencia propia (foto+entregable) y
se aprueban o devuelven una por una acá mismo; las de los docentes ya se
revisan con el informe mensual completo de ese curso, así que acá
aparecen solo informativas, sin botones de aprobar/devolver.

Maestro-detalle: a la izquierda una tarjeta por persona con su avance
contra la meta mensual (HORAS_OBJETIVO_MENSUAL); a la derecha, las horas
de la persona elegida.
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
from ui.widgets import avatar_iniciales, imagen_desde_base64, pildora

ROJO, VERDE, GRIS, AMBAR = tema.ROJO, tema.VERDE, tema.GRIS, tema.AMBAR

# Meta mensual del mockup ("8 horas externas al mes") — HORAS_OBJETIVO_MENSUAL
# real vive en el backend; acá solo hace falta el número para el texto fijo
# del banner, el objetivo puntual de cada persona sigue viniendo del backend.
_META_MENSUAL = 8
_GRIS_TEXTO_TABLA = "#5A665F"

_PRIORIDAD_ESTADO = {"pendiente": 0, "devuelto": 1, "aprobado": 2}


def _url_drive(doc_id: str) -> str:
    return f"https://drive.google.com/file/d/{doc_id}/view"


class RevisarHorasScreen(ctk.CTkFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None] | None = None):
        super().__init__(master, fg_color="transparent")
        self.sesion = sesion
        self._resumen: list[dict] = []
        self._actividades: list[dict] = []
        self._persona_seleccionada: int | None = None
        self._filtro_texto = ""

        if on_volver is not None:
            ctk.CTkButton(
                self, text="← Volver", width=90, fg_color="transparent", border_width=1,
                text_color=tema.TEXTO_OSCURO, hover_color=tema.FONDO_CONTENIDO, command=on_volver,
            ).pack(anchor="w", padx=4, pady=(0, 12))

        # Encabezado: título + píldoras de resumen a la izquierda, mes y
        # actualizar a la derecha — como en el mockup.
        encabezado = ctk.CTkFrame(self, fg_color="transparent")
        encabezado.pack(fill="x", padx=4, pady=(0, 14))
        ctk.CTkLabel(
            encabezado, text="Horas externas del equipo", font=tema.fuente(18, "bold"),
            text_color=tema.TEXTO_OSCURO,
        ).pack(side="left", padx=(0, 14))
        self._pildora_cumplen = pildora(encabezado, f"0 cumplen las {_META_MENSUAL} h", tema.VERDE_CHIP_TEXTO, tema.VERDE_CHIP_BG)
        self._pildora_cumplen.pack(side="left", padx=(0, 8))
        self._pildora_faltan = pildora(encabezado, "0 por debajo", ROJO, tema.ROJO_CHIP_BG)
        self._pildora_faltan.pack(side="left")

        # height=1 a propósito: ver la nota en dashboard_screen.py — sin
        # esto, el espaciador vacío pide 200px de alto por defecto e infla
        # toda la fila, empujando "Mes"/"Actualizar" bien abajo del resto.
        ctk.CTkFrame(encabezado, fg_color="transparent", height=1).pack(side="left", fill="x", expand=True)

        self.mes_entry = ctk.CTkEntry(encabezado, width=110, justify="center")
        self.mes_entry.insert(0, date_utils.hoy_iso()[:7])
        self.mes_entry.pack(side="left", anchor="s", padx=(0, 10))
        ctk.CTkButton(
            encabezado, text="Actualizar", width=100, fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER,
            command=self._cargar,
        ).pack(side="left", anchor="s")

        aviso = ctk.CTkFrame(
            self, fg_color=tema.FONDO_TARJETA, corner_radius=12,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        aviso.pack(fill="x", padx=4, pady=(0, 18))
        ctk.CTkLabel(
            aviso,
            text=f"Cada docente y directivo debe cumplir {_META_MENSUAL} horas externas al mes. "
                 "La barra de cada tarjeta es contra esas horas.",
            text_color=_GRIS_TEXTO_TABLA, font=tema.fuente(11), anchor="w", justify="left", wraplength=1000,
        ).pack(fill="x", padx=18, pady=13)

        self.error_label = ctk.CTkLabel(self, text="", text_color=ROJO, anchor="w")
        self.error_label.pack(fill="x", padx=4, pady=(0, 8))

        cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True)

        # 440px fijo para la lista de personas, como en el mockup
        # (grid-template-columns: 440px minmax(0,1fr)) — el resto para el
        # detalle de la persona elegida.
        self.panel_personas = ctk.CTkScrollableFrame(
            cuerpo, width=440, label_text="", fg_color="transparent",
        )
        self.panel_personas.pack(side="left", fill="y", padx=(0, 20))

        self.panel_detalle = ctk.CTkScrollableFrame(cuerpo, label_text="", fg_color="transparent")
        self.panel_detalle.pack(side="left", fill="both", expand=True)

        self._cargar()

    # --- filtro (buscador del encabezado) ------------------------------

    def filtrar(self, texto: str):
        """Lo llama el buscador del encabezado superior (ver
        RevisarHubScreen) — filtra el equipo por nombre, sobre lo que ya
        está en memoria."""
        self._filtro_texto = texto.strip().lower()
        self._redibujar_personas()

    # --- carga ----------------------------------------------------------

    def _cargar(self):
        for w in self.panel_personas.winfo_children():
            w.destroy()
        for w in self.panel_detalle.winfo_children():
            w.destroy()
        Cargando(self.panel_personas, texto="Cargando...").pack(pady=16)
        self.error_label.configure(text="")

        mes = self.mes_entry.get().strip()

        def listo(datos):
            self._resumen = datos.get("resumen", [])
            self._actividades = datos.get("actividades", [])
            self._persona_seleccionada = None
            cumplen = sum(1 for p in self._resumen if p.get("cumple"))
            self._pildora_cumplen.configure(text=f"  {cumplen} cumplen las {_META_MENSUAL} h  ")
            self._pildora_faltan.configure(text=f"  {len(self._resumen) - cumplen} por debajo  ")
            self._redibujar_personas()
            self._redibujar_detalle()

        def fallo(exc):
            for w in self.panel_personas.winfo_children():
                w.destroy()
            self.error_label.configure(text=str(exc))

        en_segundo_plano(
            self,
            lambda: api_client.obtener_horas_del_equipo(self.sesion["token"], mes),
            listo,
            fallo,
        )

    # --- panel izquierdo: personas ---------------------------------------

    def _redibujar_personas(self):
        for w in self.panel_personas.winfo_children():
            w.destroy()

        personas = self._resumen
        if self._filtro_texto:
            personas = [p for p in personas if self._filtro_texto in str(p.get("nombre", "")).lower()]

        if not personas:
            texto = "Nadie coincide con la búsqueda." if self._filtro_texto else "Nadie registró horas este mes."
            ctk.CTkLabel(self.panel_personas, text=texto, text_color=GRIS, wraplength=220).pack(pady=10)
            return

        personas = sorted(personas, key=lambda p: str(p.get("nombre", "")).lower())
        for p in personas:
            self._tarjeta_persona(p)

    def _tarjeta_persona(self, p: dict):
        activo = p["persona_id"] == self._persona_seleccionada
        # El mockup no modela un estado "elegida" (es una lista sin
        # selección de por sí), solo hover con borde verde oscuro — acá se
        # reusa ese mismo color para la seleccionada, en vez de invertir la
        # tarjeta a fondo sólido, para no inventar un estado que Design no
        # muestra.
        marco = ctk.CTkFrame(
            self.panel_personas, fg_color=tema.FONDO_TARJETA, corner_radius=14, cursor="hand2",
            border_width=2 if activo else 1, border_color=tema.VERDE_OSCURO if activo else tema.BORDE_TARJETA,
        )
        marco.pack(fill="x", pady=6)
        contenido = ctk.CTkFrame(marco, fg_color="transparent")
        contenido.pack(fill="x", padx=18, pady=16)

        # Toda la superficie de la tarjeta tiene que reaccionar al clic, no
        # solo el fondo entre los widgets — antes solo marco/contenido/fila/
        # textos tenían el bind, y un CTkLabel hijo (como el nombre) tapa
        # el clic de su padre en Tkinter si el hijo no tiene el suyo propio.
        # Tocar el nombre, el rol, las horas o la barra —justo donde se
        # espera poder hacer clic— no hacía nada.
        clicables = [marco, contenido]

        fila = ctk.CTkFrame(contenido, fg_color="transparent")
        fila.pack(fill="x")
        clicables.append(fila)
        clicables.append(avatar_iniciales(fila, str(p.get("nombre", "?")), tamano=40, color="#F1F5F2"))
        clicables[-1].pack(side="left")
        textos = ctk.CTkFrame(fila, fg_color="transparent")
        textos.pack(side="left", padx=(13, 0), fill="x", expand=True)
        clicables.append(textos)
        nombre_label = ctk.CTkLabel(
            textos, text=str(p.get("nombre", "")), font=tema.fuente(14, "bold"),
            text_color=tema.TEXTO_OSCURO, anchor="w", wraplength=190,
        )
        nombre_label.pack(fill="x")
        clicables.append(nombre_label)
        rol_label = ctk.CTkLabel(
            textos, text=str(p.get("rol", "")), text_color=tema.TEXTO_MUTED, font=tema.fuente(12), anchor="w",
        )
        rol_label.pack(fill="x")
        clicables.append(rol_label)
        numero = ctk.CTkFrame(fila, fg_color="transparent")
        numero.pack(side="right")
        clicables.append(numero)
        horas_label = ctk.CTkLabel(
            numero, text=f"{p.get('total_horas', 0):g}", font=tema.fuente(20, "bold"),
            text_color=tema.VERDE_OSCURO,
        )
        horas_label.pack(side="left")
        clicables.append(horas_label)
        objetivo_label = ctk.CTkLabel(
            numero, text=f" / {p.get('objetivo', 0):g} h", font=tema.fuente(12), text_color=tema.TEXTO_MUTED,
        )
        objetivo_label.pack(side="left")
        clicables.append(objetivo_label)

        fila_barra = ctk.CTkFrame(contenido, fg_color="transparent")
        fila_barra.pack(fill="x", pady=(12, 0))
        clicables.append(fila_barra)
        barra = ctk.CTkProgressBar(fila_barra, height=7, progress_color=VERDE if p.get("cumple") else ROJO)
        objetivo = p.get("objetivo") or 1
        barra.set(min(p.get("total_horas", 0) / objetivo, 1.0))
        barra.pack(side="left", fill="x", expand=True, padx=(0, 12))
        clicables.append(barra)
        if p.get("cumple"):
            estado_pill = pildora(fila_barra, p.get("estado", "cumple"), tema.VERDE_CHIP_TEXTO, tema.VERDE_CHIP_BG)
        else:
            estado_pill = pildora(fila_barra, p.get("estado", "por debajo"), ROJO, tema.ROJO_CHIP_BG)
        estado_pill.pack(side="left")
        clicables.append(estado_pill)

        for widget in clicables:
            widget.bind("<Button-1>", lambda _e, pid=p["persona_id"]: self._elegir_persona(pid))

    def _elegir_persona(self, persona_id: int):
        self._persona_seleccionada = persona_id
        self._redibujar_personas()

        # Armar el detalle (una tarjeta por hora, con foto y botones) puede
        # tardarse lo suyo si la persona tiene varias — hecho todo seguido,
        # Tkinter no repinta nada hasta terminar, así que el clic se sentía
        # pegado sin ningún aviso mientras tanto. Por eso el aviso de
        # "Cargando..." se pinta primero (con update_idletasks, para que
        # salga ANTES de seguir) y recién el detalle pesado se arma un
        # instante después (after), ya con la pantalla repintada.
        for w in self.panel_detalle.winfo_children():
            w.destroy()
        Cargando(self.panel_detalle, texto="Cargando...").pack(pady=16)
        self.update_idletasks()
        self.after(1, self._redibujar_detalle)

    # --- panel derecho: horas de la persona elegida -----------------------

    def _redibujar_detalle(self):
        for w in self.panel_detalle.winfo_children():
            w.destroy()

        if self._persona_seleccionada is None:
            ctk.CTkLabel(
                self.panel_detalle, text="Elija una persona a la izquierda para ver sus horas.",
                text_color=GRIS,
            ).pack(pady=16)
            return

        persona = next(
            (p for p in self._resumen if p["persona_id"] == self._persona_seleccionada), None
        )
        if persona is not None:
            self._encabezado_persona(persona)

        actividades = [
            a for a in self._actividades if a["persona_id"] == self._persona_seleccionada
        ]
        actividades.sort(key=lambda a: a["fecha"], reverse=True)
        actividades.sort(key=lambda a: _PRIORIDAD_ESTADO.get(a.get("estado", "pendiente"), 0))

        if not actividades:
            ctk.CTkLabel(
                self.panel_detalle, text="Esta persona no registró horas este mes.", text_color=GRIS,
            ).pack(pady=16)
            return

        for a in actividades:
            self._fila_actividad(a)

    def _encabezado_persona(self, p: dict):
        """Tarjeta con la persona elegida — nombre, rol, horas del mes —
        arriba de sus actividades, como en el mockup."""
        marco = ctk.CTkFrame(
            self.panel_detalle, fg_color=tema.FONDO_TARJETA, corner_radius=16,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        marco.pack(fill="x", pady=(0, 14))
        contenido = ctk.CTkFrame(marco, fg_color="transparent")
        contenido.pack(fill="x", padx=24, pady=20)

        fila = ctk.CTkFrame(contenido, fg_color="transparent")
        fila.pack(fill="x")
        avatar_iniciales(fila, str(p.get("nombre", "?")), tamano=46, color=tema.DORADO_ACENTO).pack(side="left")
        textos = ctk.CTkFrame(fila, fg_color="transparent")
        textos.pack(side="left", fill="x", expand=True, padx=(14, 0))
        ctk.CTkLabel(
            textos, text=str(p.get("nombre", "")), font=tema.fuente(16, "bold"), text_color=tema.TEXTO_OSCURO,
            anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            textos, text=f"{p.get('rol', '')} — {self._mes_cargado_o_actual()}",
            text_color=tema.TEXTO_MUTED, font=tema.fuente(12), anchor="w",
        ).pack(fill="x", pady=(2, 0))
        if p.get("cumple"):
            pildora(
                fila, f"{p.get('total_horas', 0):g} de {p.get('objetivo', 0):g} h · cumple",
                tema.VERDE_CHIP_TEXTO, tema.VERDE_CHIP_BG,
            ).pack(side="right")
        else:
            pildora(
                fila, f"{p.get('total_horas', 0):g} de {p.get('objetivo', 0):g} h",
                ROJO, tema.ROJO_CHIP_BG,
            ).pack(side="right")

    def _mes_cargado_o_actual(self) -> str:
        return self.mes_entry.get().strip()

    def _fila_actividad(self, a: dict):
        marco = ctk.CTkFrame(
            self.panel_detalle, fg_color=tema.FONDO_TARJETA, corner_radius=16,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        marco.pack(fill="x", pady=6)
        contenido = ctk.CTkFrame(marco, fg_color="transparent")
        contenido.pack(fill="x", padx=18, pady=18)

        # Foto de evidencia a la izquierda (o el aviso de "sin foto" en
        # ámbar punteado si no cargó una) y el detalle a la derecha, como
        # en el mockup. La foto no se trae de una para toda la lista —cada
        # viaje a Drive tarda 2-3s, y traerlas todas de entrada volvería a
        # sentirse pegado— se pide recién al hacer clic, una por una.
        if a.get("foto_drive_id"):
            foto = ctk.CTkFrame(
                contenido, width=170, height=118, corner_radius=11, fg_color=tema.FONDO_CONTENIDO,
                cursor="hand2",
            )
            etiqueta_foto = ctk.CTkLabel(
                foto, text="foto de la\nactividad\n(clic para ver)", font=tema.fuente(11),
                text_color=tema.TEXTO_MUTED, justify="center",
            )
            etiqueta_foto.place(relx=0.5, rely=0.5, anchor="center")
            self._armar_click_foto(foto, etiqueta_foto, a["foto_drive_id"])
        else:
            foto = ctk.CTkFrame(
                contenido, width=170, height=118, corner_radius=11, fg_color="#FDF9F0",
                border_width=2, border_color="#E0C48A",
            )
            ctk.CTkLabel(
                foto, text="Sin foto\nno se puede verificar", font=tema.fuente(11, "bold"),
                text_color=AMBAR, justify="center",
            ).place(relx=0.5, rely=0.5, anchor="center")
        foto.pack(side="left", padx=(0, 18))
        foto.pack_propagate(False)

        cuerpo = ctk.CTkFrame(contenido, fg_color="transparent")
        cuerpo.pack(side="left", fill="both", expand=True)
        fila_titulo = ctk.CTkFrame(cuerpo, fg_color="transparent")
        fila_titulo.pack(fill="x")
        ctk.CTkLabel(
            fila_titulo, text=a.get("actividad", ""), font=tema.fuente(15, "bold"), text_color=tema.TEXTO_OSCURO,
            anchor="w", justify="left", wraplength=340,
        ).pack(side="left", fill="x", expand=True)
        pildora(
            fila_titulo, f"{a.get('horas', 0):g} h", tema.VERDE_OSCURO, tema.FONDO_CONTENIDO,
        ).pack(side="right")
        # Fecha y, si es una actividad de docente, el curso — las de
        # gestión no tienen curso de por medio.
        pie_fecha = a.get("fecha", "")
        if a.get("curso"):
            pie_fecha = f"{pie_fecha} · {a['curso']}"
        ctk.CTkLabel(
            cuerpo, text=pie_fecha, text_color=tema.TEXTO_MUTED, font=tema.fuente(12), anchor="w",
        ).pack(fill="x", pady=(3, 0))
        if a.get("entregable"):
            ctk.CTkLabel(
                cuerpo, text=a["entregable"], text_color=_GRIS_TEXTO_TABLA, font=tema.fuente(13),
                anchor="w", justify="left", wraplength=380,
            ).pack(fill="x", pady=(8, 0))

        estado_fila = ctk.CTkFrame(cuerpo, fg_color="transparent")
        estado_fila.pack(fill="x", pady=(10, 0))

        # Las horas de gestión (directivos) se aprueban o devuelven acá,
        # una por una. Las horas externas de un docente (Actividades) no
        # tienen ese flujo propio: ya se revisan con el informe mensual
        # completo de su curso, así que acá quedan solo informativas.
        if a.get("tipo") != "gestion":
            pildora(
                estado_fila, "Se revisa con el informe mensual", tema.TEXTO_MUTED, tema.FONDO_CONTENIDO,
            ).pack(side="left")
            return

        self._pintar_estado(estado_fila, a)

        botones = ctk.CTkFrame(cuerpo, fg_color="transparent")
        botones.pack(fill="x", pady=(12, 0))
        if a.get("link_soporte"):
            ctk.CTkButton(
                botones, text="Ver soporte", fg_color="transparent", border_width=1,
                text_color=tema.TEXTO_OSCURO, hover_color=tema.FONDO_CONTENIDO,
                command=lambda url=a["link_soporte"]: webbrowser.open(url),
            ).pack(side="left", fill="x", expand=True, padx=(0, 6))
        aprobar_boton = ctk.CTkButton(botones, text="Aprobar", fg_color=VERDE, hover_color=tema.VERDE_HOVER)
        aprobar_boton.pack(side="left", fill="x", expand=True, padx=(0, 6))
        devolver_boton = ctk.CTkButton(
            botones, text="Devolver al docente", fg_color=AMBAR, hover_color=tema.AMBAR_HOVER,
        )
        devolver_boton.pack(side="left", fill="x", expand=True)
        botones_revision = (aprobar_boton, devolver_boton)
        aprobar_boton.configure(command=lambda: self._revisar(a, True, estado_fila, botones_revision))
        devolver_boton.configure(command=lambda: self._revisar(a, False, estado_fila, botones_revision))

    def _armar_click_foto(self, marco: ctk.CTkFrame, etiqueta: ctk.CTkLabel, foto_drive_id: str):
        """Trae y muestra ESA foto puntual recién al hacer clic — no todas
        las de la lista de una, cada viaje a Drive tarda 2-3s. Un solo
        clic por foto: mientras carga o ya cargó, no vuelve a pedirla."""
        estado = {"cargando": False, "cargada": False}

        def _click(_evento=None):
            if estado["cargando"] or estado["cargada"]:
                return
            estado["cargando"] = True
            etiqueta.configure(text="Cargando foto...")

            def listo(foto):
                estado["cargando"] = False
                estado["cargada"] = True
                # Si mientras tanto se cambió de persona o se redibujó la
                # tarjeta, esta etiqueta ya no existe en Tk — tocarla revienta
                # con "invalid command name". El callback llega igual porque
                # viene de un hilo de fondo que no sabe que ya no hace falta.
                if not etiqueta.winfo_exists():
                    return
                imagen = imagen_desde_base64(foto["base64"], 160, 108)
                if imagen is None:
                    etiqueta.configure(text="No se pudo mostrar\nla foto")
                    return
                etiqueta.configure(image=imagen, text="")
                etiqueta.image = imagen  # referencia viva — si no, Tk la recolecta y queda en blanco
                if marco.winfo_exists():
                    marco.configure(cursor="arrow")
                    marco.unbind("<Button-1>")
                etiqueta.unbind("<Button-1>")

            def fallo(exc):
                estado["cargando"] = False
                if not etiqueta.winfo_exists():
                    return
                etiqueta.configure(text=f"No se pudo cargar la foto\n({exc})\nAbrir en Drive")
                if marco.winfo_exists():
                    marco.configure(cursor="hand2")
                    marco.bind("<Button-1>", lambda _e: webbrowser.open(_url_drive(foto_drive_id)))
                etiqueta.bind("<Button-1>", lambda _e: webbrowser.open(_url_drive(foto_drive_id)))

            en_segundo_plano(
                self,
                lambda: api_client.obtener_foto_horas_externas(self.sesion["token"], foto_drive_id),
                listo,
                fallo,
                mostrar_overlay=False,
            )

        for widget in (marco, etiqueta):
            widget.bind("<Button-1>", _click)

    def _pintar_estado(self, estado_fila: ctk.CTkFrame, a: dict):
        for w in estado_fila.winfo_children():
            w.destroy()
        estado = a.get("estado", "pendiente")
        motivo = a.get("motivo_devolucion", "")
        if estado == "aprobado":
            pildora(estado_fila, "Aprobada ✓", tema.VERDE_CHIP_TEXTO, tema.VERDE_CHIP_BG).pack(side="left")
        elif estado == "devuelto":
            pildora(estado_fila, "Devuelta", AMBAR, tema.AMBAR_CHIP_BG).pack(side="left")
            if motivo:
                ctk.CTkLabel(
                    estado_fila, text=motivo, text_color=tema.TEXTO_MUTED, font=tema.fuente(11), anchor="w",
                ).pack(side="left", padx=(8, 0))
        else:
            pildora(estado_fila, "Pendiente de revisar", tema.TEXTO_MUTED, tema.FONDO_CONTENIDO).pack(side="left")

    def _revisar(self, a: dict, aprobar: bool, estado_fila: ctk.CTkFrame, botones: tuple):
        motivo = ""
        if not aprobar:
            dialogo = ctk.CTkInputDialog(
                title="Devolver",
                text="¿Por qué la devuelve? La persona va a ver este motivo:",
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
            a["estado"] = resultado["estado"]
            a["motivo_devolucion"] = motivo if not aprobar else ""
            self._redibujar_detalle()

        def fallo(exc):
            for b in botones:
                b.configure(state="normal")
            self._pintar_estado(estado_fila, a)
            self.error_label.configure(text=str(exc))

        en_segundo_plano(
            self,
            lambda: api_client.revisar_hora_gestion(self.sesion["token"], a["id"], aprobar, motivo),
            listo,
            fallo,
        )
