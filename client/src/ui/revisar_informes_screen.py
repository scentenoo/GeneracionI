"""Revisar los informes del mes y descargarlos (Mariangel, Lorena,
administrador).

Junta dos cosas que antes vivían separadas: revisar (aprobar/devolver, acá
mismo con lo que ya se archivó en Drive) y descargar —de a uno o todos en
un ZIP—, que antes era la pantalla aparte «Informes del mes». Los informes
de gestión (directivos sin curso) no tienen revisión —el administrador no
"aprueba" la gestión de otro directivo— así que esos solo se descargan.

Igual que con las planeaciones: aprobar o devolver un informe no lo saca
de la lista, se ve ahí mismo con el estado nuevo — sin volver a pedirle
nada al backend.
"""

from __future__ import annotations

import os
import tempfile
import webbrowser
import zipfile
from tkinter import filedialog
from typing import Callable

import customtkinter as ctk

import api_client
from services import date_utils, docx_generator, vista_previa
from ui.cargando import Cargando
from ui.tareas import en_segundo_plano, en_segundo_plano_con_progreso

ROJO, VERDE, GRIS, AMBAR = "#c0392b", "#2fa84f", "gray", "#8A6114"

# Lo que falta por decidir va primero; lo devuelto (a mitad de corregirse)
# en el medio; lo ya aprobado, al final — es lo que menos hace falta mirar.
_PRIORIDAD_ESTADO = {"pendiente": 0, "devuelto": 1, "aprobado": 2}


def _url_drive(doc_id: str) -> str:
    return f"https://drive.google.com/file/d/{doc_id}/view"


def _contexto_y_docx(token, estado, mes, ruta):
    """Baja el contexto del informe (docente o de gestión) y arma el
    .docx. Concentra acá la rama por tipo para no repetirla en la descarga
    de a uno y en el ZIP."""
    if estado.get("tipo") == "gestion":
        contexto = api_client.generar_informe_gestion(token, estado["directivo_id"], mes)
        docx_generator.generar_informe_gestion_docx(contexto, ruta)
    else:
        contexto = api_client.generar_informe_mensual(token, estado["curso_id"], mes)
        docx_generator.generar_informe_mensual_docx(contexto, ruta)


def _nombre_archivo(curso: str, mes: str) -> str:
    """Nombre de archivo sin espacios ni caracteres que rompan en Windows."""
    base = f"informe_{curso}_{mes}"
    limpio = "".join(c if c.isalnum() or c in "-_" else "_" for c in base)
    return f"{limpio}.docx"


class RevisarInformesScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None] | None = None):
        # Sin `on_volver` va montada como pestaña de RevisarHubScreen.
        super().__init__(master, label_text="" if on_volver is None else "Informes")
        self.sesion = sesion
        self._informes_curso: list[dict] = []
        self._informes_gestion: list[dict] = []
        self._mes_cargado = ""

        if on_volver is not None:
            ctk.CTkButton(self, text="← Volver", width=90, command=on_volver).pack(anchor="w", pady=(0, 10))

        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.pack(fill="x")
        ctk.CTkLabel(fila, text="Mes").pack(side="left")
        self.mes_entry = ctk.CTkEntry(fila, width=90)
        self.mes_entry.insert(0, date_utils.hoy_iso()[:7])
        self.mes_entry.pack(side="left", padx=8)
        ctk.CTkButton(fila, text="Actualizar", width=100, command=self._cargar).pack(side="left")

        self.resumen_label = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=15, weight="bold"), anchor="w"
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

        self.contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self.contenedor.pack(fill="both", expand=True, pady=(6, 0))

        self._cargar()

    # --- carga -----------------------------------------------------------

    def _cargar(self):
        for w in self.contenedor.winfo_children():
            w.destroy()
        self.resumen_label.configure(text="", text_color=GRIS)
        self.todos_boton.configure(state="disabled")
        cargando = Cargando(self.contenedor, texto="Cargando informes...")
        cargando.pack(pady=16)
        mes = self.mes_entry.get().strip()

        def traer():
            revision = api_client.revision_del_mes(self.sesion["token"], mes)
            informes_curso = revision.get("informes", [])
            for i in informes_curso:
                i["tipo"] = "curso"

            directivos = api_client.directivos_sin_curso_del_mes(self.sesion["token"], mes)
            informes_gestion = [d for d in directivos if d.get("informe_entregado")]
            for d in informes_gestion:
                d["tipo"] = "gestion"
                d["curso"] = f"Gestión — {d['nombre']}"
                d["docente"] = d["nombre"]

            return informes_curso, informes_gestion

        def listo(resultado):
            self._mes_cargado = mes
            self._informes_curso, self._informes_gestion = resultado
            self._actualizar_resumen()
            self._redibujar()

        def fallo(exc):
            for w in self.contenedor.winfo_children():
                w.destroy()
            self.resumen_label.configure(text=str(exc), text_color=ROJO)

        en_segundo_plano(self, traer, listo, fallo)

    def _redibujar(self):
        """Reconstruye la lista con lo que ya está en memoria —no le pide
        nada de nuevo al backend—, con los informes de curso ordenados:
        pendientes primero, devueltos en el medio, aprobados al final."""
        for w in self.contenedor.winfo_children():
            w.destroy()

        entregados = len(self._informes_curso) + len(self._informes_gestion)
        self.todos_boton.configure(state="normal" if entregados else "disabled")

        if not entregados:
            ctk.CTkLabel(
                self.contenedor, text="Nadie entregó su informe todavía este mes.", text_color=GRIS
            ).pack(anchor="w", pady=10)
            return

        if self._informes_curso:
            self._informes_curso.sort(
                key=lambda i: _PRIORIDAD_ESTADO.get(i.get("estado", "pendiente"), 0)
            )
            ctk.CTkLabel(
                self.contenedor, text="Informes de curso", font=ctk.CTkFont(weight="bold")
            ).pack(anchor="w", pady=(6, 2))
            for i in self._informes_curso:
                self._fila_informe_curso(i)

        if self._informes_gestion:
            ctk.CTkLabel(
                self.contenedor, text="Informes de gestión", font=ctk.CTkFont(weight="bold")
            ).pack(anchor="w", pady=(12, 2))
            for d in self._informes_gestion:
                self._fila_informe_gestion(d)

    def _actualizar_resumen(self):
        total = len(self._informes_curso) + len(self._informes_gestion)
        pendientes = sum(1 for i in self._informes_curso if i.get("estado", "pendiente") == "pendiente")
        self.resumen_label.configure(
            text=f"{total} informe(s) entregado(s)  ·  {pendientes} pendiente(s) de revisar  ·  {self._mes_cargado}",
            text_color=self.color_normal if pendientes else VERDE,
        )

    # --- informes de curso: revisar + descargar ---------------------------

    def _fila_informe_curso(self, i: dict):
        marco = ctk.CTkFrame(self.contenedor, corner_radius=8, border_width=1)
        marco.pack(fill="x", pady=3)
        cuerpo = ctk.CTkFrame(marco, fg_color="transparent")
        cuerpo.pack(side="left", fill="both", expand=True, padx=12, pady=8)
        ctk.CTkLabel(
            cuerpo, text=f"Informe — {i['curso']}", font=ctk.CTkFont(weight="bold"), anchor="w",
            justify="left", wraplength=380,
        ).pack(fill="x")
        ctk.CTkLabel(cuerpo, text=i.get("docente", ""), text_color=GRIS, anchor="w").pack(fill="x")
        estado_label = ctk.CTkLabel(cuerpo, text="", anchor="w", font=ctk.CTkFont(size=12))
        estado_label.pack(fill="x", pady=(2, 0))
        self._pintar_estado(estado_label, i)

        botones = ctk.CTkFrame(marco, fg_color="transparent")
        botones.pack(side="right", padx=10)
        abrir_boton = ctk.CTkButton(
            botones, text="Abrir", width=90, fg_color="transparent", border_width=1,
            command=lambda: self._abrir_informe(i, abrir_boton),
        )
        abrir_boton.pack(pady=2)
        aprobar_boton = ctk.CTkButton(botones, text="Aprobar", width=90, fg_color=VERDE, hover_color="#248a3d")
        aprobar_boton.pack(pady=2)
        devolver_boton = ctk.CTkButton(botones, text="Devolver", width=90, fg_color=AMBAR, hover_color="#6b4d10")
        devolver_boton.pack(pady=2)
        botones_revision = (aprobar_boton, devolver_boton)
        aprobar_boton.configure(command=lambda: self._revisar(i, True, estado_label, botones_revision))
        devolver_boton.configure(command=lambda: self._revisar(i, False, estado_label, botones_revision))
        ctk.CTkButton(
            botones, text="Descargar", width=90,
            command=lambda e=i, m=self._mes_cargado: self._descargar_uno(e, m),
        ).pack(pady=2)

    def _pintar_estado(self, estado_label: ctk.CTkLabel, i: dict):
        estado = i.get("estado", "pendiente")
        motivo = i.get("motivo_devolucion", "")
        if estado == "aprobado":
            estado_label.configure(text="Aprobado ✓", text_color=VERDE)
        elif estado == "devuelto":
            estado_label.configure(text=f"Devuelto: {motivo}" if motivo else "Devuelto", text_color=AMBAR)
        else:
            estado_label.configure(text="Pendiente de revisar", text_color=GRIS)

    def _revisar(self, i: dict, aprobar: bool, estado_label: ctk.CTkLabel, botones: tuple):
        motivo = ""
        if not aprobar:
            dialogo = ctk.CTkInputDialog(
                title="Devolver",
                text="¿Por qué la devolvés? El docente va a ver este motivo:",
            )
            motivo = (dialogo.get_input() or "").strip()
            if not motivo:
                return  # sin motivo no se devuelve

        for b in botones:
            b.configure(state="disabled")
        estado_label.configure(text="Guardando...", text_color=GRIS)

        def listo(resultado):
            i["estado"] = resultado["estado"]
            i["motivo_devolucion"] = motivo if not aprobar else ""
            self._actualizar_resumen()
            self._redibujar()  # mueve la tarjeta a su lugar nuevo según el estado

        def fallo(exc):
            for b in botones:
                b.configure(state="normal")
            self._pintar_estado(estado_label, i)  # vuelve a lo último guardado, no a lo que se intentó
            self.resumen_label.configure(text=str(exc), text_color=ROJO)

        en_segundo_plano(
            self,
            lambda: api_client.revisar_informe(self.sesion["token"], i["curso_id"], i["mes"], aprobar, motivo),
            listo,
            fallo,
        )

    def _abrir_informe(self, i: dict, boton: ctk.CTkButton):
        """Abre el .docx archivado en Drive. Los informes entregados antes
        de que esto se guardara en Drive no tienen doc_drive_id: para esos
        se arma local con lo ya entregado, como respaldo."""
        if i.get("doc_drive_id"):
            webbrowser.open(_url_drive(i["doc_drive_id"]))
            return

        boton.configure(state="disabled", text="Generando...")

        def trabajo():
            contexto = api_client.generar_informe_mensual(self.sesion["token"], i["curso_id"], i["mes"])
            return vista_previa.previsualizar_informe(contexto)

        def listo(_resultado):
            boton.configure(state="normal", text="Abrir")

        def fallo(exc):
            boton.configure(state="normal", text="Abrir")
            self.resumen_label.configure(text=str(exc), text_color=ROJO)

        en_segundo_plano(self, trabajo, listo, fallo)

    # --- informes de gestión: solo descargar -------------------------------

    def _fila_informe_gestion(self, d: dict):
        marco = ctk.CTkFrame(self.contenedor, corner_radius=8, border_width=1)
        marco.pack(fill="x", pady=3)
        cuerpo = ctk.CTkFrame(marco, fg_color="transparent")
        cuerpo.pack(side="left", fill="both", expand=True, padx=12, pady=8)
        ctk.CTkLabel(
            cuerpo, text=d["curso"], font=ctk.CTkFont(weight="bold"), anchor="w",
            justify="left", wraplength=380,
        ).pack(fill="x")

        ctk.CTkButton(
            marco, text="Descargar", width=100,
            command=lambda e=d, m=self._mes_cargado: self._descargar_uno(e, m),
        ).pack(side="right", padx=10)

    # --- descargas ---------------------------------------------------------

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
            _contexto_y_docx(self.sesion["token"], estado, mes, ruta)
            return ruta

        def listo(r):
            self.progreso_label.configure(text=f"Guardado: {r}", text_color=VERDE)

        def fallo(exc):
            self.progreso_label.configure(text=str(exc), text_color=ROJO)

        en_segundo_plano(self, trabajo, listo, fallo)

    def _descargar_todos(self):
        mes = self._mes_cargado
        entregados = list(self._informes_curso) + list(self._informes_gestion)
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
                        tmp = os.path.join(tempfile.gettempdir(), _nombre_archivo(estado["curso"], mes))
                        _contexto_y_docx(token, estado, mes, tmp)
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
