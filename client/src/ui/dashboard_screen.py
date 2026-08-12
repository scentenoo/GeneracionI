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

from tkinter import messagebox
from typing import Callable

import customtkinter as ctk

import api_client
from services import date_utils
from ui.cargando import Cargando
from ui.tareas import en_segundo_plano

# Rojo: ni siquiera puede entregar el informe, le faltan clases.
# Ámbar: ya puede entregarlo y no lo hizo — es lo accionable hoy.
# Verde: al día.
ROJO, AMBAR, VERDE, GRIS = "#c0392b", "#8A6114", "#2fa84f", "gray"


class DashboardScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None]):
        super().__init__(master, label_text="Cómo va el mes")
        self.sesion = sesion
        self.on_volver = on_volver

        ctk.CTkButton(self, text="← Volver", width=90, command=on_volver).pack(anchor="w", pady=(0, 10))

        fila_mes = ctk.CTkFrame(self, fg_color="transparent")
        fila_mes.pack(fill="x")
        ctk.CTkLabel(fila_mes, text="Mes").pack(side="left")
        self.mes_entry = ctk.CTkEntry(fila_mes, width=90)
        self.mes_entry.insert(0, date_utils.hoy_iso()[:7])
        self.mes_entry.pack(side="left", padx=8)
        ctk.CTkButton(fila_mes, text="Actualizar", width=100, command=self._cargar).pack(side="left")

        self.resumen_label = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=15, weight="bold"), anchor="w", justify="left"
        )
        self.resumen_label.pack(fill="x", pady=(14, 2))
        # customtkinter no acepta text_color=None para "el del tema", así que
        # nos guardamos el que trae de fábrica para poder volver a él.
        self.color_normal = self.resumen_label.cget("text_color")

        self.detalle_label = ctk.CTkLabel(self, text="", text_color=GRIS, anchor="w", justify="left")
        self.detalle_label.pack(fill="x", pady=(0, 10))

        self._construir_corte()

        self.tarjetas = ctk.CTkFrame(self, fg_color="transparent")
        self.tarjetas.pack(fill="both", expand=True)

        # Cambiar de mes deja la consulta anterior viajando: si esa llega
        # última, el directivo termina viendo el mes que ya no pidió.
        self.consulta = 0
        self._cargar()

    # --- cierre del mes -------------------------------------------------

    def _construir_corte(self):
        """El día de corte vive acá y no en una pantalla aparte: es el
        mismo lugar donde el directivo mira quién va atrasado y decide a
        quién reabrirle el mes."""
        marco = ctk.CTkFrame(self, corner_radius=8)
        marco.pack(fill="x", pady=(0, 12))

        fila = ctk.CTkFrame(marco, fg_color="transparent")
        fila.pack(fill="x", padx=12, pady=10)

        ctk.CTkLabel(fila, text="El mes se cierra el día").pack(side="left")
        self.corte_entry = ctk.CTkEntry(fila, width=45)
        self.corte_entry.pack(side="left", padx=6)
        ctk.CTkLabel(fila, text="del mes siguiente").pack(side="left")
        ctk.CTkButton(fila, text="Guardar", width=80, command=self._guardar_corte).pack(
            side="right"
        )

        self.corte_aviso = ctk.CTkLabel(
            marco,
            text="Pasada esa fecha los docentes no pueden cargar, editar ni borrar "
                 "nada de ese mes. Ustedes sí.",
            text_color=GRIS, font=ctk.CTkFont(size=11),
            anchor="w", justify="left", wraplength=600,
        )
        self.corte_aviso.pack(fill="x", padx=12, pady=(0, 10))

    def _guardar_corte(self):
        dia = self.corte_entry.get().strip()
        self.corte_aviso.configure(text="Guardando...", text_color=GRIS)

        def listo(r):
            self.corte_aviso.configure(
                text=f"Listo: los meses se cierran el día {r['dia_de_corte']} del mes siguiente.",
                text_color=VERDE,
            )
            self._cargar()

        en_segundo_plano(
            self,
            lambda: api_client.fijar_dia_de_corte(self.sesion["token"], dia),
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
        self.consulta += 1
        consulta = self.consulta
        self.resumen_label.configure(text="", text_color=GRIS)
        self.detalle_label.configure(text="")
        cargando = Cargando(self.tarjetas, texto="Cargando el mes...")
        cargando.pack(pady=20)

        def listo(estados):
            if consulta != self.consulta:
                return
            cargando.detener()
            cargando.destroy()
            if not estados:
                self.resumen_label.configure(text="Todavía no hay cursos.", text_color=GRIS)
                return

            entregados = sum(1 for e in estados if e.get("informe_entregado"))
            al_dia = sum(1 for e in estados if e["faltantes"] == 0)
            self.resumen_label.configure(
                text=f"{entregados} de {len(estados)} informes entregados",
                text_color=VERDE if entregados == len(estados) else self.color_normal,
            )
            self.detalle_label.configure(
                text=f"{al_dia} de {len(estados)} cursos con todas las clases cargadas  ·  {mes}"
            )

            corte = estados[0].get("dia_de_corte")
            if corte and not self.corte_entry.get().strip():
                self.corte_entry.insert(0, str(corte))

            for estado in sorted(estados, key=lambda e: (self._clasificar(e)[0], e.get("curso", ""))):
                self._tarjeta(estado)

        def fallo(exc):
            if consulta != self.consulta:
                return
            cargando.detener()
            cargando.destroy()
            self.resumen_label.configure(text=str(exc), text_color=ROJO)

        en_segundo_plano(
            self,
            lambda: api_client.obtener_dashboard_directivo(self.sesion["token"], mes),
            listo,
            fallo,
        )

    def _tarjeta(self, estado: dict):
        _, color, texto_informe = self._clasificar(estado)

        marco = ctk.CTkFrame(self.tarjetas, corner_radius=8, border_width=1)
        marco.pack(fill="x", pady=4)

        # Franja de color a la izquierda: el estado se ve antes de leer.
        franja = ctk.CTkFrame(marco, width=5, fg_color=color, corner_radius=0)
        franja.pack(side="left", fill="y")
        franja.pack_propagate(False)

        cuerpo = ctk.CTkFrame(marco, fg_color="transparent")
        cuerpo.pack(side="left", fill="both", expand=True, padx=12, pady=10)

        ctk.CTkLabel(
            cuerpo, text=estado.get("curso", ""), font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w", justify="left", wraplength=520,
        ).pack(fill="x")
        ctk.CTkLabel(cuerpo, text=estado.get("docente", ""), text_color=GRIS, anchor="w").pack(fill="x")

        estados_fila = ctk.CTkFrame(cuerpo, fg_color="transparent")
        estados_fila.pack(fill="x", pady=(8, 0))

        faltan = estado["faltantes"]
        texto_clases = (
            f"{estado['registradas']} de {estado['esperadas']} clases"
            if faltan == 0
            else f"{estado['registradas']} de {estado['esperadas']} clases · faltan {faltan}"
        )
        self._chip(estados_fila, texto_clases, VERDE if faltan == 0 else ROJO)
        self._chip(estados_fila, texto_informe, color)

        # Reabrir un mes cerrado es lo que hace que el corte no sea una
        # pared: el docente pide, el directivo abre acá mismo.
        if estado.get("cerrado"):
            self._chip(estados_fila, "mes cerrado", GRIS)
            ctk.CTkButton(
                estados_fila, text="Reabrir", width=80, fg_color="transparent", border_width=1,
                command=lambda: self._alternar_cierre(estado, True),
            ).pack(side="left", padx=(6, 0))
        elif estado.get("reabierto"):
            self._chip(estados_fila, "reabierto", AMBAR)
            ctk.CTkButton(
                estados_fila, text="Cerrar", width=80, fg_color="transparent", border_width=1,
                command=lambda: self._alternar_cierre(estado, False),
            ).pack(side="left", padx=(6, 0))

    def _chip(self, padre, texto: str, color: str):
        ctk.CTkLabel(
            padre, text=f"  {texto}  ", text_color=color, font=ctk.CTkFont(size=12),
            corner_radius=6, fg_color=("gray92", "gray20"),
        ).pack(side="left", padx=(0, 6))
