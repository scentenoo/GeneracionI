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
from ui.tareas import cache, en_segundo_plano

ROJO, VERDE, GRIS, AMBAR, MORADO = "#c0392b", "#2fa84f", "gray", "#8A6114", "#8e44ad"
SIN_ASIGNAR = "(sin asignar)"


class RevisoresScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None]):
        super().__init__(master, label_text="Revisores por color")
        self.sesion = sesion
        self._directivos_por_nombre: dict[str, dict] = {}

        ctk.CTkButton(self, text="← Volver", width=90, command=on_volver).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(
            self,
            text="El color de cada curso decide quién revisa sus planeaciones e informes.\n"
                 "El color se asigna curso por curso en «Cursos»; acá se dice a quién le toca.",
            text_color=GRIS, justify="left", anchor="w", wraplength=460,
        ).pack(fill="x", pady=(0, 12))

        self.verde_menu, self.verde_cursos = self._selector("Cursos verdes los revisa", VERDE)
        self.morado_menu, self.morado_cursos = self._selector("Cursos morados los revisa", MORADO)

        ctk.CTkLabel(
            self, text="Cursos sin color", font=ctk.CTkFont(weight="bold"), anchor="w"
        ).pack(fill="x", pady=(18, 0))
        self.sin_color_contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self.sin_color_contenedor.pack(fill="x")

        self.resumen_label = ctk.CTkLabel(
            self, text="Consultando...", text_color=GRIS, justify="left", anchor="w", wraplength=460
        )
        self.resumen_label.pack(fill="x", pady=(6, 0))

        self.error_label = ctk.CTkLabel(self, text="", text_color=ROJO, wraplength=460, justify="left")
        self.error_label.pack(fill="x", pady=(8, 4))

        self.guardar_boton = ctk.CTkButton(self, text="Guardar", command=self._guardar)
        self.guardar_boton.pack(pady=(4, 20))

        self._cargar()

    def _selector(self, etiqueta: str, color: str):
        """Devuelve el desplegable del revisor y el marco donde van sus cursos."""
        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.pack(fill="x", pady=(6, 0))
        # El cuadrito de color es el mismo lenguaje que usan en la sede para
        # hablar de los cursos, y evita tener que leer la etiqueta entera.
        ctk.CTkLabel(fila, text="  ", fg_color=color, corner_radius=4, width=18).pack(side="left")
        ctk.CTkLabel(fila, text=etiqueta, anchor="w").pack(side="left", padx=8)
        menu = ctk.CTkOptionMenu(self, width=340, values=["Cargando..."])
        menu.set("Cargando...")
        menu.pack(fill="x", pady=(2, 0))
        cursos = ctk.CTkFrame(self, fg_color="transparent")
        cursos.pack(fill="x", padx=(26, 0))
        return menu, cursos

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
            self._mostrar_cursos(revisores.get("cursos") or {})

        def fallo(exc):
            self.resumen_label.configure(text="", text_color=GRIS)
            self.error_label.configure(text=str(exc), text_color=ROJO)

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

    def _mostrar_cursos(self, cursos: dict):
        """Qué curso le toca a cada quien, y cuáles quedaron sin dueño."""
        verdes = cursos.get("verde") or []
        morados = cursos.get("morado") or []
        sueltos = cursos.get("sin_color") or []

        self._llenar(self.verde_cursos, verdes, "Ningún curso activo es verde todavía.")
        self._llenar(self.morado_cursos, morados, "Ningún curso activo es morado todavía.")
        # Los sueltos van en ámbar porque son el problema; que la lista esté
        # vacía es la buena noticia, y por eso ese texto va en verde.
        self._llenar(
            self.sin_color_contenedor, sueltos,
            "Ninguno: todos los cursos activos tienen quien los revise. ✓",
            color_vacio=VERDE, color_items=AMBAR,
        )

        if sueltos:
            plural = "Ese curso no lo revisa" if len(sueltos) == 1 else "Esos cursos no los revisa"
            self.resumen_label.configure(
                text=f"{plural} nadie más que vos (el administrador). Ponéles color "
                     "en «Cursos» para que le toquen a alguien.",
                text_color=AMBAR,
            )
        else:
            self.resumen_label.configure(
                text=f"{len(verdes) + len(morados)} cursos activos, todos asignados.",
                text_color=GRIS,
            )

    @staticmethod
    def _llenar(contenedor, cursos: list, texto_vacio: str, color_vacio=GRIS, color_items=GRIS):
        for w in contenedor.winfo_children():
            w.destroy()
        if not cursos:
            ctk.CTkLabel(
                contenedor, text=texto_vacio, text_color=color_vacio, anchor="w",
                font=ctk.CTkFont(size=11), wraplength=440, justify="left",
            ).pack(fill="x")
            return
        for c in sorted(cursos, key=lambda c: str(c.get("nombre", "")).lower()):
            ctk.CTkLabel(
                contenedor, text=f"· {c.get('nombre')}  —  {c.get('docente')}",
                text_color=color_items, anchor="w", font=ctk.CTkFont(size=11),
                wraplength=440, justify="left",
            ).pack(fill="x")

    def _id_elegido(self, menu: ctk.CTkOptionMenu):
        """El id del directivo elegido, o "" para desasignar el color."""
        elegido = self._directivos_por_nombre.get(menu.get())
        return elegido["id"] if elegido else ""

    def _guardar(self):
        if not self._directivos_por_nombre:
            self.error_label.configure(text="Todavía no cargaron los directivos.", text_color=ROJO)
            return

        verde_id = self._id_elegido(self.verde_menu)
        morado_id = self._id_elegido(self.morado_menu)

        self.guardar_boton.configure(state="disabled")
        self.error_label.configure(text="Guardando...", text_color=GRIS)

        def listo(_r):
            self.guardar_boton.configure(state="normal")
            self.error_label.configure(text="Revisores guardados ✓", text_color=VERDE)
            self._cargar()

        def fallo(exc):
            self.guardar_boton.configure(state="normal")
            self.error_label.configure(text=str(exc), text_color=ROJO)

        en_segundo_plano(
            self,
            lambda: api_client.fijar_revisores(self.sesion["token"], verde_id, morado_id),
            listo,
            fallo,
        )
