"""Informes del mes (rol directivo/admin): ver quién entregó y bajar los
.docx, uno por uno o todos juntos en un ZIP.

El docente entrega su informe mensual desde «Generar informe mensual»;
esta pantalla es la contracara para quien supervisa: junta todos los
cursos del mes, muestra quién entregó y quién no, y arma la descarga. Es
lo que el equipo directivo necesita a fin de mes para consolidar.

La descarga masiva es un informe por viaje al backend, así que con 17
cursos tarda un rato: va en segundo plano con una barra, para que se vea
que avanza y no parezca colgada.
"""

from __future__ import annotations

import os
import tempfile
import zipfile
from tkinter import filedialog
from typing import Callable

import customtkinter as ctk

import api_client
from services import date_utils, docx_generator
from ui.tareas import en_segundo_plano, en_segundo_plano_con_progreso

ROJO, VERDE, GRIS = "#c0392b", "#2fa84f", "gray"


def _nombre_archivo(curso: str, mes: str) -> str:
    """Nombre de archivo sin espacios ni caracteres que rompan en Windows."""
    base = f"informe_{curso}_{mes}"
    limpio = "".join(c if c.isalnum() or c in "-_" else "_" for c in base)
    return f"{limpio}.docx"


class InformesMesScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None]):
        super().__init__(master, label_text="Informes del mes")
        self.sesion = sesion
        self._estados: list[dict] = []

        ctk.CTkButton(self, text="← Volver", width=90, command=on_volver).pack(anchor="w", pady=(0, 10))

        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.pack(fill="x")
        ctk.CTkLabel(fila, text="Mes").pack(side="left")
        self.mes_entry = ctk.CTkEntry(fila, width=90)
        self.mes_entry.insert(0, date_utils.hoy_iso()[:7])
        self.mes_entry.pack(side="left", padx=8)
        ctk.CTkButton(fila, text="Actualizar", width=100, command=self._cargar).pack(side="left")

        self.resumen_label = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=15, weight="bold"), anchor="w", justify="left"
        )
        self.resumen_label.pack(fill="x", pady=(14, 2))
        self.color_normal = self.resumen_label.cget("text_color")

        self.todos_boton = ctk.CTkButton(
            self, text="Descargar todos (ZIP)", command=self._descargar_todos, state="disabled"
        )
        self.todos_boton.pack(anchor="w", pady=(2, 4))

        self.progreso = ctk.CTkProgressBar(self)
        self.progreso.set(0)
        self.progreso_label = ctk.CTkLabel(self, text="", text_color=GRIS, anchor="w")

        self.tarjetas = ctk.CTkFrame(self, fg_color="transparent")
        self.tarjetas.pack(fill="both", expand=True, pady=(6, 0))

        self._cargar()

    # --- carga ---------------------------------------------------------

    def _cargar(self):
        for w in self.tarjetas.winfo_children():
            w.destroy()
        self.resumen_label.configure(text="Cargando...", text_color=GRIS)
        self.todos_boton.configure(state="disabled")
        mes = self.mes_entry.get().strip()

        def listo(estados):
            self._estados = estados
            entregados = [e for e in estados if e.get("informe_entregado")]
            self.resumen_label.configure(
                text=f"{len(entregados)} de {len(estados)} informes entregados",
                text_color=VERDE if entregados and len(entregados) == len(estados) else self.color_normal,
            )
            self.todos_boton.configure(state="normal" if entregados else "disabled")

            if not estados:
                ctk.CTkLabel(self.tarjetas, text="No hay cursos.", text_color=GRIS).pack(anchor="w")
                return

            # Los entregados primero: son los que se pueden bajar.
            for estado in sorted(estados, key=lambda e: (not e.get("informe_entregado"), str(e.get("curso", "")).lower())):
                self._tarjeta(estado, mes)

        en_segundo_plano(
            self,
            lambda: api_client.obtener_dashboard_directivo(self.sesion["token"], mes),
            listo,
            lambda exc: self.resumen_label.configure(text=str(exc), text_color=ROJO),
        )

    def _tarjeta(self, estado: dict, mes: str):
        entregado = bool(estado.get("informe_entregado"))
        marco = ctk.CTkFrame(self.tarjetas, corner_radius=8, border_width=1)
        marco.pack(fill="x", pady=3)

        franja = ctk.CTkFrame(marco, width=5, fg_color=VERDE if entregado else ROJO, corner_radius=0)
        franja.pack(side="left", fill="y")
        franja.pack_propagate(False)

        cuerpo = ctk.CTkFrame(marco, fg_color="transparent")
        cuerpo.pack(side="left", fill="both", expand=True, padx=12, pady=8)
        ctk.CTkLabel(
            cuerpo, text=estado.get("curso", ""), font=ctk.CTkFont(weight="bold"),
            anchor="w", justify="left", wraplength=380,
        ).pack(fill="x")
        ctk.CTkLabel(
            cuerpo, text=f"{estado.get('docente', '')}  ·  "
                         + ("entregado" if entregado else "sin entregar"),
            text_color=VERDE if entregado else ROJO, anchor="w",
        ).pack(fill="x")

        if entregado:
            ctk.CTkButton(
                marco, text="Descargar", width=100,
                command=lambda e=estado, m=mes: self._descargar_uno(e, m),
            ).pack(side="right", padx=10)

    # --- descargas -----------------------------------------------------

    def _descargar_uno(self, estado: dict, mes: str):
        ruta = filedialog.asksaveasfilename(
            title="Guardar informe",
            defaultextension=".docx",
            filetypes=[("Word", "*.docx")],
            initialfile=_nombre_archivo(estado["curso"], mes),
        )
        if not ruta:
            return

        self.progreso_label.pack(fill="x")
        self.progreso_label.configure(text=f"Armando el informe de {estado['curso']}...", text_color=GRIS)

        def trabajo():
            contexto = api_client.generar_informe_mensual(self.sesion["token"], estado["curso_id"], mes)
            docx_generator.generar_informe_mensual_docx(contexto, ruta)
            return ruta

        def listo(r):
            self.progreso_label.configure(text=f"Guardado: {r}", text_color=VERDE)

        def fallo(exc):
            self.progreso_label.configure(text=str(exc), text_color=ROJO)

        en_segundo_plano(self, trabajo, listo, fallo)

    def _descargar_todos(self):
        mes = self.mes_entry.get().strip()
        entregados = [e for e in self._estados if e.get("informe_entregado")]
        if not entregados:
            return

        ruta = filedialog.asksaveasfilename(
            title="Guardar todos los informes",
            defaultextension=".zip",
            filetypes=[("ZIP", "*.zip")],
            initialfile=f"informes_{mes}.zip",
        )
        if not ruta:
            return

        self.todos_boton.configure(state="disabled")
        self.progreso.set(0)
        self.progreso.pack(fill="x", pady=(6, 0))
        self.progreso_label.pack(fill="x")
        self.progreso_label.configure(text="Preparando...", text_color=GRIS)

        total = len(entregados)
        token = self.sesion["token"]

        def trabajo(reportar):
            # Se arma en un ZIP nuevo; si uno falla, se anota y se sigue con
            # el resto, para no perder los 16 buenos por 1 malo.
            fallados = []
            with zipfile.ZipFile(ruta, "w", zipfile.ZIP_DEFLATED) as zf:
                for i, estado in enumerate(entregados):
                    reportar((i, total, estado["curso"]))
                    try:
                        contexto = api_client.generar_informe_mensual(token, estado["curso_id"], mes)
                        tmp = os.path.join(tempfile.gettempdir(), _nombre_archivo(estado["curso"], mes))
                        docx_generator.generar_informe_mensual_docx(contexto, tmp)
                        zf.write(tmp, _nombre_archivo(estado["curso"], mes))
                        os.remove(tmp)
                    except Exception as exc:  # noqa: BLE001 — se reporta al final
                        fallados.append(f"{estado['curso']}: {exc}")
            return total - len(fallados), fallados

        def progreso(valor):
            hechos, tot, nombre = valor
            self.progreso.set(hechos / tot if tot else 0)
            self.progreso_label.configure(text=f"Bajando {hechos + 1} de {tot}: {nombre}...", text_color=GRIS)

        def listo(resultado):
            ok, fallados = resultado
            self.progreso.set(1)
            self.todos_boton.configure(state="normal")
            if fallados:
                self.progreso_label.configure(
                    text=f"Listo: {ok} guardados. No se pudo con {len(fallados)}:\n"
                         + "\n".join(fallados[:4]),
                    text_color=ROJO,
                )
            else:
                self.progreso_label.configure(
                    text=f"Listo: {ok} informes en {ruta}", text_color=VERDE
                )

        def fallo(exc):
            self.todos_boton.configure(state="normal")
            self.progreso_label.configure(text=str(exc), text_color=ROJO)

        en_segundo_plano_con_progreso(self, trabajo, progreso, listo, fallo)
