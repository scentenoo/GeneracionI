"""Quién revisa cada color. Solo el administrador.

El color del curso decide quién aprueba o devuelve sus planeaciones e
informes: verde lo revisa Mariangel, morado Lorena (así salió del piloto).
El color se pone curso por curso en la pantalla de Cursos; acá se dice a
quién le toca cada uno.

Hasta ahora esto solo existía en el backend y había que correr la función
a mano en el editor de Apps Script, o sea que reasignar a alguien —una
licencia, un cambio de equipo— no lo podía hacer nadie del programa.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

import api_client
from ui import tema
from ui.tareas import cache, en_segundo_plano
from ui.widgets import CampoBusqueda

SIN_ASIGNAR = "(sin asignar)"
_MORADO, _MORADO_CHIP_BG = "#8e44ad", "#F3E8F8"


class RevisoresScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None]):
        super().__init__(master, label_text="", fg_color="transparent")
        self.sesion = sesion
        self._directivos_por_nombre: dict[str, dict] = {}
        self._cursos_por_color: dict = {}
        self._filtro_texto = ""

        ctk.CTkButton(
            self, text="← Volver", width=90, fg_color="transparent", border_width=1,
            text_color=tema.TEXTO_OSCURO, hover_color=tema.FONDO_TARJETA, command=on_volver,
        ).pack(anchor="w", pady=(0, 12))

        intro = ctk.CTkFrame(
            self, fg_color=tema.FONDO_TARJETA, corner_radius=14,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        intro.pack(fill="x", pady=(0, 18))
        ctk.CTkLabel(
            intro,
            text="El color de cada curso decide quién revisa sus planeaciones e informes.\n"
                 "El color se asigna curso por curso en «Cursos»; acá se dice a quién le toca.",
            text_color=tema.TEXTO_MUTED, justify="left", anchor="w", wraplength=760,
        ).pack(fill="x", padx=20, pady=16)

        CampoBusqueda(self, "Buscar curso o docente…", self.filtrar, ancho=320).pack(
            anchor="w", pady=(0, 18)
        )

        fila_cards = ctk.CTkFrame(self, fg_color="transparent")
        fila_cards.pack(fill="x")
        fila_cards.grid_columnconfigure((0, 1), weight=1, uniform="revisores")

        self.verde_menu, self.verde_cursos, self.verde_contador = self._tarjeta_color(
            fila_cards, 0, "Cursos verdes los revisa", tema.VERDE,
        )
        self.morado_menu, self.morado_cursos, self.morado_contador = self._tarjeta_color(
            fila_cards, 1, "Cursos morados los revisa", _MORADO,
        )

        sin_color_tarjeta = ctk.CTkFrame(
            self, fg_color=tema.FONDO_TARJETA, corner_radius=16,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        sin_color_tarjeta.pack(fill="x", pady=(20, 0))
        contenido_sin_color = ctk.CTkFrame(sin_color_tarjeta, fg_color="transparent")
        contenido_sin_color.pack(fill="x", padx=24, pady=20)
        encabezado_sin_color = ctk.CTkFrame(contenido_sin_color, fg_color="transparent")
        encabezado_sin_color.pack(fill="x")
        ctk.CTkFrame(
            encabezado_sin_color, width=16, height=16, corner_radius=5, fg_color="transparent",
            border_width=2, border_color="#C8A24A",
        ).pack(side="left")
        ctk.CTkLabel(
            encabezado_sin_color, text="Cursos sin color", font=tema.fuente(15, "bold"), anchor="w",
        ).pack(side="left", padx=(10, 0))
        self.sin_color_contenedor = ctk.CTkFrame(contenido_sin_color, fg_color="transparent")
        self.sin_color_contenedor.pack(fill="x", pady=(10, 0))

        self.resumen_label = ctk.CTkLabel(
            self, text="Consultando...", text_color=tema.TEXTO_MUTED, justify="left", anchor="w", wraplength=760,
        )
        self.resumen_label.pack(fill="x", pady=(10, 0))

        self.error_label = ctk.CTkLabel(self, text="", text_color=tema.ROJO, wraplength=760, justify="left")
        self.error_label.pack(fill="x", pady=(8, 4))

        self.guardar_boton = ctk.CTkButton(
            self, text="Guardar", fg_color=tema.VERDE_OSCURO, hover_color=tema.VERDE_OSCURO_ACTIVO,
            command=self._guardar,
        )
        self.guardar_boton.pack(anchor="e", pady=(4, 20))

        self._cargar()

    def _tarjeta_color(self, padre, columna: int, etiqueta: str, color: str):
        """Una tarjeta "a quién le toca este color": encabezado con el
        selector de revisor, y debajo la lista de cursos que le tocan."""
        tarjeta = ctk.CTkFrame(
            padre, fg_color=tema.FONDO_TARJETA, corner_radius=16,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        tarjeta.grid(row=0, column=columna, sticky="nsew", padx=(0, 10) if columna == 0 else (10, 0))

        encabezado = ctk.CTkFrame(tarjeta, fg_color="transparent")
        encabezado.pack(fill="x", padx=22, pady=(20, 14))
        ctk.CTkFrame(encabezado, width=16, height=16, corner_radius=5, fg_color=color).pack(side="left")
        textos = ctk.CTkFrame(encabezado, fg_color="transparent")
        textos.pack(side="left", fill="x", expand=True, padx=(12, 0))
        ctk.CTkLabel(
            textos, text=etiqueta.upper(), font=tema.fuente(10, "bold"), text_color=tema.TEXTO_MUTED, anchor="w",
        ).pack(fill="x")
        menu = ctk.CTkOptionMenu(textos, values=["Cargando..."])
        menu.set("Cargando...")
        menu.pack(fill="x", pady=(4, 0))

        ctk.CTkFrame(tarjeta, fg_color=tema.DIVISOR, height=1).pack(fill="x")
        cursos = ctk.CTkFrame(tarjeta, fg_color="transparent")
        cursos.pack(fill="x", padx=22, pady=(10, 6))

        contador = ctk.CTkLabel(
            tarjeta, text="", font=tema.fuente(11), text_color=tema.TEXTO_MUTED, anchor="w",
            fg_color=tema.FONDO_CONTENIDO,
        )
        contador.pack(fill="x", padx=0, pady=(8, 0))
        return menu, cursos, contador

    def filtrar(self, texto: str):
        self._filtro_texto = texto.strip().lower()
        self._mostrar_cursos(self._cursos_por_color)

    def _cargar(self):
        """Trae en un solo viaje los directivos (para las listas) y quién
        está asignado hoy."""
        def trabajo():
            usuarios = cache.usuarios(self.sesion["token"])
            return usuarios, api_client.obtener_revisores(self.sesion["token"])

        def listo(resultado):
            usuarios, revisores = resultado
            self._directivos_por_nombre = {
                u["nombre"]: u for u in usuarios if u.get("rol") in ("directivo", "ambos")
            }
            nombres = [SIN_ASIGNAR] + sorted(self._directivos_por_nombre)
            for menu, clave in ((self.verde_menu, "revisor_verde"), (self.morado_menu, "revisor_morado")):
                menu.configure(values=nombres)
                menu.set(self._nombre_de(revisores.get(clave)))
            self._cursos_por_color = revisores.get("cursos") or {}
            self._mostrar_cursos(self._cursos_por_color)

        def fallo(exc):
            self.resumen_label.configure(text="", text_color=tema.TEXTO_MUTED)
            self.error_label.configure(text=str(exc), text_color=tema.ROJO)

        en_segundo_plano(self, trabajo, listo, fallo)

    def _nombre_de(self, revisor_id) -> str:
        if not revisor_id:
            return SIN_ASIGNAR
        for nombre, u in self._directivos_por_nombre.items():
            if str(u["id"]) == str(revisor_id):
                return nombre
        # Quedó asignado alguien que ya no es directivo (o que se eliminó):
        # se muestra sin asignar, que es como se comporta de hecho.
        return SIN_ASIGNAR

    def _filtrados(self, cursos: list) -> list:
        if not self._filtro_texto:
            return cursos
        def coincide(c):
            texto = f"{c.get('nombre', '')} {c.get('docente', '')}".lower()
            return self._filtro_texto in texto
        return [c for c in cursos if coincide(c)]

    def _mostrar_cursos(self, cursos: dict):
        """Qué curso le toca a cada quien, y cuáles quedaron sin dueño."""
        verdes = self._filtrados(cursos.get("verde") or [])
        morados = self._filtrados(cursos.get("morado") or [])
        sueltos = self._filtrados(cursos.get("sin_color") or [])

        self._llenar(self.verde_cursos, verdes, "Ningún curso activo es verde todavía.", tema.VERDE)
        self._llenar(self.morado_cursos, morados, "Ningún curso activo es morado todavía.", _MORADO)
        self.verde_contador.configure(text=f"  {len(verdes)} cursos  ")
        self.morado_contador.configure(text=f"  {len(morados)} cursos  ")

        # Los sueltos van en ámbar porque son el problema; que la lista esté
        # vacía es la buena noticia, y por eso ese texto va en verde.
        self._llenar(
            self.sin_color_contenedor, sueltos,
            "Ninguno: todos los cursos activos tienen quien los revise. ✓",
            "#C8A24A", color_vacio=tema.VERDE_CHIP_TEXTO, color_items=tema.AMBAR,
        )

        total = len(cursos.get("verde") or []) + len(cursos.get("morado") or [])
        sueltos_totales = cursos.get("sin_color") or []
        if sueltos_totales:
            plural = "Ese curso no lo revisa" if len(sueltos_totales) == 1 else "Esos cursos no los revisa"
            self.resumen_label.configure(
                text=f"{plural} nadie más que usted (el administrador). Póngales color "
                     "en «Cursos» para que le toquen a alguien.",
                text_color=tema.AMBAR,
            )
        else:
            self.resumen_label.configure(
                text=f"{total} cursos activos, todos asignados.",
                text_color=tema.TEXTO_MUTED,
            )

    @staticmethod
    def _llenar(contenedor, cursos: list, texto_vacio: str, color_punto: str, color_vacio=None, color_items=None):
        color_vacio = color_vacio or tema.TEXTO_MUTED
        color_items = color_items or tema.TEXTO_OSCURO
        for w in contenedor.winfo_children():
            w.destroy()
        if not cursos:
            ctk.CTkLabel(
                contenedor, text=texto_vacio, text_color=color_vacio, anchor="w",
                font=tema.fuente(12), wraplength=440, justify="left",
            ).pack(fill="x", pady=4)
            return
        for c in sorted(cursos, key=lambda c: str(c.get("nombre", "")).lower()):
            fila = ctk.CTkFrame(contenedor, fg_color="transparent")
            fila.pack(fill="x", pady=4)
            ctk.CTkFrame(fila, width=6, height=6, corner_radius=3, fg_color=color_punto).pack(side="left")
            ctk.CTkLabel(
                fila, text=str(c.get("nombre", "")), text_color=color_items, font=tema.fuente(12),
                anchor="w", wraplength=260,
            ).pack(side="left", padx=(10, 6), fill="x", expand=True)
            ctk.CTkLabel(
                fila, text=str(c.get("docente", "")), text_color=tema.TEXTO_MUTED, font=tema.fuente(11),
                anchor="e",
            ).pack(side="right")

    def _id_elegido(self, menu: ctk.CTkOptionMenu):
        """El id del directivo elegido, o "" para desasignar el color."""
        elegido = self._directivos_por_nombre.get(menu.get())
        return elegido["id"] if elegido else ""

    def _guardar(self):
        if not self._directivos_por_nombre:
            self.error_label.configure(text="Todavía no cargaron los directivos.", text_color=tema.ROJO)
            return

        verde_id = self._id_elegido(self.verde_menu)
        morado_id = self._id_elegido(self.morado_menu)

        self.guardar_boton.configure(state="disabled")
        self.error_label.configure(text="Guardando...", text_color=tema.TEXTO_MUTED)

        def listo(_r):
            self.guardar_boton.configure(state="normal")
            self.error_label.configure(text="Revisores guardados ✓", text_color=tema.VERDE)
            self._cargar()

        def fallo(exc):
            self.guardar_boton.configure(state="normal")
            self.error_label.configure(text=str(exc), text_color=tema.ROJO)

        en_segundo_plano(
            self,
            lambda: api_client.fijar_revisores(self.sesion["token"], verde_id, morado_id),
            listo,
            fallo,
        )
