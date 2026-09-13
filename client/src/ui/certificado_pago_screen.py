"""Certificado mensual de horas de docencia para pago (solo
administradores, spec: "certificado para pago") — junta las horas de
docencia del mes (de sede y externas, ya sumadas — ver
Certificados.js#generar_certificado_pago) por docente y curso, y arma el
.docx con esa información tal cual, con la fecha del día en que se genera.
Se descarga como .docx (no PDF) a propósito: si falta un teléfono o una
formación que todavía no está cargada en el perfil del docente, se
completa a mano en Word antes de firmarlo.
"""

from __future__ import annotations

import datetime
from tkinter import filedialog
from typing import Callable

import customtkinter as ctk

import api_client
from services import date_utils, docx_generator
from ui import tema
from ui.cargando import Cargando
from ui.tareas import en_segundo_plano
from ui.widgets import Tabla

ROJO, VERDE, GRIS = tema.ROJO, tema.VERDE, tema.GRIS


def _nombre_archivo(mes: str) -> str:
    return f"certificado_pago_{mes}.docx"


class CertificadoPagoScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None] | None = None):
        # Sin `on_volver` va montada como pestaña de RevisarHubScreen.
        super().__init__(master, label_text="" if on_volver is None else "Certificado de pago")
        self.sesion = sesion
        self._contexto: dict | None = None

        if on_volver is not None:
            ctk.CTkButton(
                self, text="← Volver", width=90, fg_color="transparent", border_width=1,
                text_color=tema.TEXTO_OSCURO, hover_color=tema.FONDO_CONTENIDO, command=on_volver,
            ).pack(anchor="w", pady=(0, 12))

        ctk.CTkLabel(
            self, text="Certificado de pago mensual", font=tema.fuente(18, "bold"),
            text_color=tema.TEXTO_OSCURO, anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            self,
            text="Junta, por docente y curso, las horas de docencia del mes (de sede y "
                 "externas, con el total) para certificar el pago al operador. Un curso sin "
                 "horas ese mes no sale en el certificado — se lista aparte, para que se vea "
                 "quién todavía no cargó nada antes de descargarlo.",
            text_color=tema.TEXTO_MUTED, font=tema.fuente(12), anchor="w", justify="left",
            wraplength=700,
        ).pack(anchor="w", pady=(2, 16))

        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(
            fila, text="Mes", font=tema.fuente(12), text_color=tema.TEXTO_MUTED,
        ).pack(side="left", padx=(0, 8))
        self.mes_entry = ctk.CTkEntry(fila, width=110, justify="center")
        self.mes_entry.insert(0, date_utils.hoy_iso()[:7])
        self.mes_entry.pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            fila, text="Generar", width=100, fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER,
            command=self._generar,
        ).pack(side="left", padx=(0, 10))
        self.descargar_boton = ctk.CTkButton(
            fila, text="Descargar .docx", width=140, fg_color=tema.FONDO_TARJETA,
            border_width=1, border_color=tema.VERDE, text_color=tema.VERDE_CHIP_TEXTO,
            hover_color=tema.VERDE_CHIP_BG, command=self._descargar, state="disabled",
        )
        self.descargar_boton.pack(side="left")

        self.resumen_label = ctk.CTkLabel(self, text="", text_color=tema.ROJO, anchor="w")
        self.resumen_label.pack(fill="x", pady=(0, 8))

        self.contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self.contenedor.pack(fill="x")

    def _generar(self):
        for w in self.contenedor.winfo_children():
            w.destroy()
        self.descargar_boton.configure(state="disabled")
        self.resumen_label.configure(text="", text_color=GRIS)
        self._contexto = None
        cargando = Cargando(self.contenedor, texto="Juntando las horas del mes...")
        cargando.pack(pady=16)
        mes = self.mes_entry.get().strip()

        def listo(contexto):
            cargando.detener()
            cargando.destroy()
            self._contexto = contexto
            self._redibujar(contexto)
            self.descargar_boton.configure(state="normal" if contexto.get("filas") else "disabled")

        def fallo(exc):
            cargando.detener()
            cargando.destroy()
            self.resumen_label.configure(text=str(exc), text_color=ROJO)

        en_segundo_plano(
            self,
            lambda: api_client.generar_certificado_pago(self.sesion["token"], mes),
            listo,
            fallo,
        )

    def _redibujar(self, contexto: dict):
        filas = contexto.get("filas", [])
        excluidos = contexto.get("excluidos", [])

        if not filas and not excluidos:
            ctk.CTkLabel(
                self.contenedor, text="No hay cursos activos.", text_color=GRIS,
            ).pack(anchor="w", pady=10)
            return

        if filas:
            self.resumen_label.configure(
                text=f"{len(filas)} filas · {contexto.get('total_horas', 0)} horas en total.",
                text_color=tema.TEXTO_MUTED,
            )
            tabla = Tabla(
                self.contenedor, ["Docente", "Curso", "Sede", "Externas", "Total"],
                anchos=[3, 3, 1, 1, 1],
            )
            tabla.pack(fill="x")
            for f in filas:
                tabla.agregar_fila([
                    f.get("docente", ""), f.get("curso", ""),
                    f.get("horas_sede", 0), f.get("horas_externas", 0), f.get("horas", 0),
                ])
        else:
            ctk.CTkLabel(
                self.contenedor, text="Nadie tiene horas cargadas ese mes.", text_color=GRIS,
            ).pack(anchor="w", pady=10)

        if excluidos:
            ctk.CTkLabel(
                self.contenedor,
                text=f"No van a salir en el certificado — sin horas cargadas ese mes ({len(excluidos)}):",
                font=tema.fuente(13, "bold"), text_color=tema.TEXTO_OSCURO, anchor="w",
            ).pack(anchor="w", pady=(20, 8))
            tabla_excluidos = Tabla(self.contenedor, ["Docente", "Curso", "Motivo"], anchos=[2, 2, 2])
            tabla_excluidos.pack(fill="x")
            for e in excluidos:
                tabla_excluidos.agregar_fila([e.get("docente", ""), e.get("curso", ""), e.get("motivo", "")])

    def _descargar(self):
        if not self._contexto:
            return
        mes = self._contexto.get("mes") or self.mes_entry.get().strip()
        ruta = filedialog.asksaveasfilename(
            title="Guardar certificado de pago",
            defaultextension=".docx",
            filetypes=[("Word", "*.docx")],
            initialfile=_nombre_archivo(mes),
        )
        if not ruta:
            return

        self.resumen_label.configure(text="Generando el .docx...", text_color=GRIS)
        # La fecha final va con el día real de la descarga, no el de cuando
        # se armó la vista previa (pueden ser días distintos si el
        # administrador se demora en revisar la tabla antes de bajarlo).
        contexto = dict(self._contexto, fecha_emision=datetime.date.today().strftime("%d/%m/%Y"))

        def trabajo():
            docx_generator.generar_certificado_pago_docx(contexto, ruta)
            return ruta

        def listo(r):
            self.resumen_label.configure(text=f"Guardado: {r}", text_color=VERDE)

        def fallo(exc):
            self.resumen_label.configure(text=str(exc), text_color=ROJO)

        en_segundo_plano(self, trabajo, listo, fallo)
