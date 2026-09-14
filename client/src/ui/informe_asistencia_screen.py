"""Informe de asistencia de un mes, para mandar a la Secretaría de
Educación (spec: pedido de Miguel) — solo administradores. Dos formas de
bajarlo: un documento consolidado con TODOS los cursos juntos (para tener
la foto completa del mes), o uno individual por curso con espacio de firma
para el docente y la coordinadora de área — para que cada quien firme solo
lo suyo (pedido después de entregar la primera versión: la Secretaría
necesita el documento firmado curso por curso, no uno solo con todo).

Mismo esqueleto que certificado_pago_screen.py (vista previa en tabla +
botón de descarga), pero acá se descarga en PDF: se arma el .docx con
docxtpl como siempre y se convierte con pdf_converter, con el mismo
manejo de error si no hay LibreOffice/Word instalado (se ofrece el .docx).
"""

from __future__ import annotations

import datetime
import shutil
import tempfile
import zipfile
from pathlib import Path
from tkinter import filedialog
from typing import Callable

import customtkinter as ctk

import api_client
from services import date_utils, docx_generator, excel_generator, pdf_converter
from ui import tema
from ui.cargando import Cargando
from ui.tareas import en_segundo_plano, en_segundo_plano_con_progreso
from ui.widgets import Tabla

ROJO, VERDE, GRIS, AMBAR = tema.ROJO, tema.VERDE, tema.GRIS, tema.AMBAR


def _nombre_archivo(mes: str) -> str:
    return f"informe_asistencia_{mes}.pdf"


def _nombre_archivo_curso(curso: str, mes: str) -> str:
    base = f"informe_asistencia_{curso}_{mes}"
    limpio = "".join(c if c.isalnum() or c in "-_" else "_" for c in base)
    return f"{limpio}.pdf"


def _generar_docx_y_pdf_curso(
    mes_nombre: str, anio: str, fecha_emision: str, curso: dict, carpeta_tmp: str
) -> tuple[Path, bool]:
    """Arma el .docx de UN curso y lo convierte a PDF; si no hay
    LibreOffice/Word en el equipo, devuelve el .docx igual (es_pdf=False).
    Usado tanto para la descarga de a uno como para el ZIP de todos, para
    no repetir la rama de conversión en los dos lugares."""
    docx_tmp = Path(carpeta_tmp) / "informe.docx"
    docx_generator.generar_informe_asistencia_curso_docx(mes_nombre, anio, fecha_emision, curso, docx_tmp)
    try:
        return pdf_converter.docx_a_pdf(docx_tmp, carpeta_tmp), True
    except pdf_converter.ConversionNoDisponible:
        return docx_tmp, False


class InformeAsistenciaScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None] | None = None):
        # Sin `on_volver` va montada como pestaña de RevisarHubScreen.
        super().__init__(master, label_text="" if on_volver is None else "Informe de asistencia")
        self.sesion = sesion
        self._contexto: dict | None = None

        if on_volver is not None:
            ctk.CTkButton(
                self, text="← Volver", width=90, fg_color="transparent", border_width=1,
                text_color=tema.TEXTO_OSCURO, hover_color=tema.FONDO_CONTENIDO, command=on_volver,
            ).pack(anchor="w", pady=(0, 12))

        ctk.CTkLabel(
            self, text="Informe de asistencia mensual", font=tema.fuente(18, "bold"),
            text_color=tema.TEXTO_OSCURO, anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            self,
            text="Un solo documento con la asistencia de TODOS los cursos del mes: qué "
                 "estudiante asistió o faltó en cada clase, y el total del mes por "
                 "estudiante y por curso.",
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
            fila, text="Descargar PDF", width=140, fg_color=tema.FONDO_TARJETA,
            border_width=1, border_color=tema.VERDE, text_color=tema.VERDE_CHIP_TEXTO,
            hover_color=tema.VERDE_CHIP_BG, command=self._descargar, state="disabled",
        )
        self.descargar_boton.pack(side="left", padx=(0, 10))
        self.descargar_por_curso_boton = ctk.CTkButton(
            fila, text="Descargar por curso (ZIP)", width=190, fg_color=tema.FONDO_TARJETA,
            border_width=1, border_color=tema.VERDE, text_color=tema.VERDE_CHIP_TEXTO,
            hover_color=tema.VERDE_CHIP_BG, command=self._descargar_por_curso, state="disabled",
        )
        self.descargar_por_curso_boton.pack(side="left")

        self.resumen_label = ctk.CTkLabel(self, text="", text_color=tema.ROJO, anchor="w")
        self.resumen_label.pack(fill="x", pady=(0, 8))

        self.progreso = ctk.CTkProgressBar(self, progress_color=tema.VERDE)
        self.progreso.set(0)
        self.progreso_label = ctk.CTkLabel(self, text="", text_color=tema.TEXTO_MUTED, anchor="w")

        self.contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self.contenedor.pack(fill="x")

        # --- reporte de inasistencias acumuladas (Excel) ---------------------
        # Aparte del informe mensual de arriba: esto es acumulado "desde que
        # cada estudiante se inscribió" en cada curso activo, no de un mes
        # puntual — así que no depende del selector de mes ni de "Generar".
        ctk.CTkFrame(self, fg_color=tema.DIVISOR, height=1).pack(fill="x", pady=(24, 20))
        ctk.CTkLabel(
            self, text="Inasistencias acumuladas por curso", font=tema.fuente(16, "bold"),
            text_color=tema.TEXTO_OSCURO, anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            self,
            text="Un Excel con una hoja por curso activo: cada estudiante con el total de "
                 "clases, asistencias e inasistencias desde la primera clase registrada en la app, marcados los "
                 "que tienen más de 3 inasistencias.",
            text_color=tema.TEXTO_MUTED, font=tema.fuente(12), anchor="w", justify="left",
            wraplength=700,
        ).pack(anchor="w", pady=(2, 12))
        ctk.CTkButton(
            self, text="Descargar Excel", width=150, fg_color=tema.FONDO_TARJETA,
            border_width=1, border_color=tema.VERDE, text_color=tema.VERDE_CHIP_TEXTO,
            hover_color=tema.VERDE_CHIP_BG, command=self._descargar_inasistencias,
        ).pack(anchor="w")
        self.inasistencias_label = ctk.CTkLabel(self, text="", text_color=tema.ROJO, anchor="w")
        self.inasistencias_label.pack(fill="x", pady=(8, 0))

    def _generar(self):
        for w in self.contenedor.winfo_children():
            w.destroy()
        self.descargar_boton.configure(state="disabled")
        self.descargar_por_curso_boton.configure(state="disabled")
        self.resumen_label.configure(text="", text_color=GRIS)
        self._contexto = None
        cargando = Cargando(self.contenedor, texto="Juntando la asistencia del mes...")
        cargando.pack(pady=16)
        mes = self.mes_entry.get().strip()

        def listo(contexto):
            cargando.detener()
            cargando.destroy()
            self._contexto = contexto
            self._redibujar(contexto)
            estado = "normal" if contexto.get("cursos") else "disabled"
            self.descargar_boton.configure(state=estado)
            self.descargar_por_curso_boton.configure(state=estado)

        def fallo(exc):
            cargando.detener()
            cargando.destroy()
            self.resumen_label.configure(text=str(exc), text_color=ROJO)

        en_segundo_plano(
            self,
            lambda: api_client.generar_informe_asistencia(self.sesion["token"], mes),
            listo,
            fallo,
        )

    def _redibujar(self, contexto: dict):
        cursos = contexto.get("cursos", [])
        sin_clases = contexto.get("cursos_sin_clases", [])
        no_identificados = contexto.get("no_identificados", [])

        if not cursos and not sin_clases:
            ctk.CTkLabel(
                self.contenedor, text="No hay cursos activos.", text_color=GRIS,
            ).pack(anchor="w", pady=10)
            return

        if cursos:
            self.resumen_label.configure(
                text=f"{len(cursos)} cursos con clases este mes.", text_color=tema.TEXTO_MUTED,
            )
            tabla = Tabla(
                self.contenedor,
                ["Curso", "Docente", "Núcleo", "Clases", "Estudiantes", "% asistencia", ""],
                anchos=[3, 2, 2, 1, 1, 1, 1],
            )
            tabla.pack(fill="x")
            for c in cursos:
                tabla.agregar_fila(
                    [
                        c.get("nombre", ""), c.get("docente", ""), c.get("nucleo", ""),
                        c.get("total_clases", 0), c.get("total_estudiantes", 0),
                        f"{c.get('porcentaje_asistencia', 0)}%",
                    ],
                    boton=("Descargar", lambda curso=c: self._descargar_curso(curso)),
                )
        else:
            ctk.CTkLabel(
                self.contenedor, text="Ningún curso tiene clases cargadas ese mes.", text_color=GRIS,
            ).pack(anchor="w", pady=10)

        if sin_clases:
            ctk.CTkLabel(
                self.contenedor,
                text=f"Cursos activos sin ninguna clase cargada este mes ({len(sin_clases)}):",
                font=tema.fuente(13, "bold"), text_color=tema.TEXTO_OSCURO, anchor="w",
            ).pack(anchor="w", pady=(20, 8))
            tabla_sin_clases = Tabla(self.contenedor, ["Curso", "Docente"], anchos=[2, 2])
            tabla_sin_clases.pack(fill="x")
            for c in sin_clases:
                tabla_sin_clases.agregar_fila([c.get("nombre", ""), c.get("docente", "")])

        if no_identificados:
            ctk.CTkLabel(
                self.contenedor,
                text=f"Nombres marcados presentes que no matchean con la lista de "
                     f"inscritos — revisar antes de descargar ({len(no_identificados)}):",
                font=tema.fuente(13, "bold"), text_color=ROJO, anchor="w",
            ).pack(anchor="w", pady=(20, 8))
            tabla_no_id = Tabla(self.contenedor, ["Nombre", "Curso", "Clase", "Fecha"], anchos=[2, 2, 1, 1])
            tabla_no_id.pack(fill="x")
            for n in no_identificados:
                tabla_no_id.agregar_fila([
                    n.get("nombre", ""), n.get("curso", ""), n.get("clase", ""), n.get("fecha", ""),
                ])

    def _descargar(self):
        if not self._contexto:
            return
        mes = self._contexto.get("mes") or self.mes_entry.get().strip()
        ruta = filedialog.asksaveasfilename(
            title="Guardar informe de asistencia",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=_nombre_archivo(mes),
        )
        if not ruta:
            return

        self.resumen_label.configure(text="Generando el informe...", text_color=GRIS)
        # La fecha de emisión final va con el día real de la descarga, no el
        # de cuando se armó la vista previa.
        contexto = dict(self._contexto, fecha_emision=datetime.date.today().strftime("%d/%m/%Y"))

        def trabajo():
            with tempfile.TemporaryDirectory() as carpeta_tmp:
                docx_tmp = Path(carpeta_tmp) / f"informe_asistencia_{mes}.docx"
                docx_generator.generar_informe_asistencia_docx(contexto, docx_tmp)
                try:
                    pdf_tmp = pdf_converter.docx_a_pdf(docx_tmp, carpeta_tmp)
                    shutil.copyfile(pdf_tmp, ruta)
                    return ruta, True
                except pdf_converter.ConversionNoDisponible:
                    ruta_docx = str(Path(ruta).with_suffix(".docx"))
                    shutil.copyfile(docx_tmp, ruta_docx)
                    return ruta_docx, False

        def listo(resultado):
            guardado, es_pdf = resultado
            if es_pdf:
                self.resumen_label.configure(text=f"Guardado: {guardado}", text_color=VERDE)
            else:
                self.resumen_label.configure(
                    text=f"No se encontró LibreOffice ni Word en este equipo para "
                         f"convertir a PDF — se guardó el .docx igual: {guardado}",
                    text_color=AMBAR,
                )

        def fallo(exc):
            self.resumen_label.configure(text=str(exc), text_color=ROJO)

        en_segundo_plano(self, trabajo, listo, fallo)

    def _descargar_por_curso(self):
        """Un PDF por curso, cada uno con su espacio de firma para el
        docente y la coordinadora de área — para que cada quien firme solo
        lo suyo, en vez de un documento único de todos los cursos."""
        if not self._contexto:
            return
        cursos = self._contexto.get("cursos", [])
        if not cursos:
            return
        mes = self._contexto.get("mes") or self.mes_entry.get().strip()

        ruta = filedialog.asksaveasfilename(
            title="Guardar informes de asistencia por curso",
            defaultextension=".zip",
            filetypes=[("ZIP", "*.zip")],
            initialfile=f"informes_asistencia_{mes}.zip",
        )
        if not ruta:
            return

        mes_nombre = self._contexto.get("mes_nombre", "")
        anio = self._contexto.get("anio", "")
        fecha_emision = datetime.date.today().strftime("%d/%m/%Y")

        self.descargar_por_curso_boton.configure(state="disabled")
        self.progreso.set(0)
        self.progreso.pack(fill="x", pady=(6, 0))
        self.progreso_label.pack(fill="x")
        self.progreso_label.configure(text="Preparando...", text_color=GRIS)

        total = len(cursos)

        def trabajo(reportar):
            fallados = []
            hubo_pdf = False
            hubo_docx = False
            with zipfile.ZipFile(ruta, "w", zipfile.ZIP_DEFLATED) as zf:
                for i, curso in enumerate(cursos):
                    reportar((i, total, curso.get("nombre", "")))
                    try:
                        with tempfile.TemporaryDirectory() as carpeta_tmp:
                            generado, es_pdf = _generar_docx_y_pdf_curso(
                                mes_nombre, anio, fecha_emision, curso, carpeta_tmp
                            )
                            if es_pdf:
                                zf.write(generado, _nombre_archivo_curso(curso.get("nombre", ""), mes))
                                hubo_pdf = True
                            else:
                                nombre_docx = _nombre_archivo_curso(
                                    curso.get("nombre", ""), mes
                                ).replace(".pdf", ".docx")
                                zf.write(generado, nombre_docx)
                                hubo_docx = True
                    except Exception as exc:  # noqa: BLE001 — se reporta al final
                        fallados.append(f"{curso.get('nombre', '')}: {exc}")
            return total - len(fallados), fallados, hubo_pdf, hubo_docx

        def progreso(valor):
            hechos, tot, nombre = valor
            self.progreso.set(hechos / tot if tot else 0)
            self.progreso_label.configure(text=f"Generando {hechos + 1} de {tot}: {nombre}...", text_color=GRIS)

        def listo(resultado):
            ok, fallados, hubo_pdf, hubo_docx = resultado
            self.progreso.set(1)
            self.descargar_por_curso_boton.configure(state="normal")
            aviso_conversion = (
                " (no se encontró LibreOffice ni Word: algunos quedaron en .docx)"
                if hubo_docx and hubo_pdf
                else " (no se encontró LibreOffice ni Word: se guardaron todos en .docx)"
                if hubo_docx and not hubo_pdf
                else ""
            )
            if fallados:
                self.progreso_label.configure(
                    text=f"Listo: {ok} guardados{aviso_conversion}. No se pudo con {len(fallados)}:\n"
                         + "\n".join(fallados[:4]),
                    text_color=ROJO,
                )
            else:
                self.progreso_label.configure(
                    text=f"Listo: {ok} informes en {ruta}{aviso_conversion}",
                    text_color=VERDE if not hubo_docx else AMBAR,
                )

        def fallo(exc):
            self.descargar_por_curso_boton.configure(state="normal")
            self.progreso_label.configure(text=str(exc), text_color=ROJO)

        en_segundo_plano_con_progreso(self, trabajo, progreso, listo, fallo)

    def _descargar_curso(self, curso: dict):
        """El botón "Descargar" de una fila puntual de la tabla — el mismo
        documento individual (con firmas) que el ZIP de "Descargar por
        curso", pero de a uno, para cuando solo hace falta el de un curso."""
        if not self._contexto:
            return
        mes = self._contexto.get("mes") or self.mes_entry.get().strip()
        ruta = filedialog.asksaveasfilename(
            title=f"Guardar informe de asistencia — {curso.get('nombre', '')}",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=_nombre_archivo_curso(curso.get("nombre", ""), mes),
        )
        if not ruta:
            return

        mes_nombre = self._contexto.get("mes_nombre", "")
        anio = self._contexto.get("anio", "")
        fecha_emision = datetime.date.today().strftime("%d/%m/%Y")

        self.progreso_label.pack(fill="x")
        self.progreso_label.configure(text=f"Generando el informe de {curso.get('nombre', '')}...", text_color=GRIS)

        def trabajo():
            with tempfile.TemporaryDirectory() as carpeta_tmp:
                generado, es_pdf = _generar_docx_y_pdf_curso(mes_nombre, anio, fecha_emision, curso, carpeta_tmp)
                if es_pdf:
                    shutil.copyfile(generado, ruta)
                    return ruta, True
                ruta_docx = str(Path(ruta).with_suffix(".docx"))
                shutil.copyfile(generado, ruta_docx)
                return ruta_docx, False

        def listo(resultado):
            guardado, es_pdf = resultado
            if es_pdf:
                self.progreso_label.configure(text=f"Guardado: {guardado}", text_color=VERDE)
            else:
                self.progreso_label.configure(
                    text=f"No se encontró LibreOffice ni Word en este equipo para "
                         f"convertir a PDF — se guardó el .docx igual: {guardado}",
                    text_color=AMBAR,
                )

        def fallo(exc):
            self.progreso_label.configure(text=str(exc), text_color=ROJO)

        en_segundo_plano(self, trabajo, listo, fallo)

    def _descargar_inasistencias(self):
        """No depende de "Generar": pide los datos y arma el Excel de una
        sola vez al apretar el botón, como certificado_pago_screen.py pero
        sin vista previa en pantalla (acá no hace falta, va directo al
        archivo)."""
        ruta = filedialog.asksaveasfilename(
            title="Guardar inasistencias acumuladas",
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialfile=f"inasistencias_{date_utils.hoy_iso()[:10]}.xlsx",
        )
        if not ruta:
            return

        self.inasistencias_label.configure(text="Juntando las inasistencias...", text_color=GRIS)

        def trabajo():
            contexto = api_client.generar_reporte_inasistencias(self.sesion["token"])
            excel_generator.generar_reporte_inasistencias_xlsx(contexto, ruta)
            return ruta

        def listo(r):
            self.inasistencias_label.configure(text=f"Guardado: {r}", text_color=VERDE)

        def fallo(exc):
            self.inasistencias_label.configure(text=str(exc), text_color=ROJO)

        en_segundo_plano(self, trabajo, listo, fallo)
