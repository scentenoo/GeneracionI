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
from services import date_utils, docx_generator
from ui import tema
from ui.cargando import Cargando
from ui.tareas import en_segundo_plano, en_segundo_plano_con_progreso
from ui.widgets import pildora

ROJO, VERDE, GRIS, AMBAR = tema.ROJO, tema.VERDE, tema.GRIS, tema.AMBAR

# Lo que falta por decidir va primero; lo devuelto (a mitad de corregirse)
# en el medio; lo ya aprobado, al final — es lo que menos hace falta mirar.
_PRIORIDAD_ESTADO = {"pendiente": 0, "devuelto": 1, "aprobado": 2}


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


def _url_drive(doc_id: str) -> str:
    return f"https://drive.google.com/file/d/{doc_id}/view"


class RevisarInformesScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None] | None = None):
        # Sin `on_volver` va montada como pestaña de RevisarHubScreen.
        super().__init__(master, label_text="" if on_volver is None else "Informes")
        self.sesion = sesion
        self._informes_curso: list[dict] = []
        self._informes_gestion: list[dict] = []
        self._mes_cargado = ""
        self._filtro_texto = ""
        self._NUCLEO_TODOS = "Todos los núcleos"
        self._filtro_nucleo = self._NUCLEO_TODOS

        if on_volver is not None:
            ctk.CTkButton(
                self, text="← Volver", width=90, fg_color="transparent", border_width=1,
                text_color=tema.TEXTO_OSCURO, hover_color=tema.FONDO_CONTENIDO, command=on_volver,
            ).pack(anchor="w", pady=(0, 12))

        # Encabezado: título + píldoras de conteo a la izquierda, mes y ZIP
        # a la derecha — como en el mockup.
        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.pack(fill="x", pady=(0, 20))
        ctk.CTkLabel(
            fila, text="Informes de curso", font=tema.fuente(18, "bold"), text_color=tema.TEXTO_OSCURO,
        ).pack(side="left", padx=(0, 14))
        self._pildora_entregados = pildora(fila, "0 entregados", tema.VERDE_CHIP_TEXTO, tema.VERDE_CHIP_BG)
        self._pildora_entregados.pack(side="left", padx=(0, 8))
        self._pildora_pendientes = pildora(
            fila, "0 pendientes de revisar", AMBAR, tema.AMBAR_CHIP_BG
        )
        self._pildora_pendientes.pack(side="left")

        # height=1 a propósito: ver la nota en dashboard_screen.py — sin
        # esto, el espaciador vacío pide 200px de alto por defecto e infla
        # toda la fila, empujando "Mes"/"Actualizar"/ZIP bien abajo del resto.
        ctk.CTkFrame(fila, fg_color="transparent", height=1).pack(side="left", fill="x", expand=True)

        # Filtro por núcleo (spec: dirección revisa núcleo por núcleo, recién
        # cuando ese núcleo completo entregó) — mismo patrón que
        # dashboard_screen.py y revisar_planeaciones_screen.py. Los informes
        # de gestión (directivos sin curso) no tienen núcleo, así que un
        # filtro puntual los deja afuera — no pertenecen a ninguno.
        self.nucleo_menu = ctk.CTkOptionMenu(
            fila, values=[self._NUCLEO_TODOS], width=170, command=self._al_cambiar_nucleo,
        )
        self.nucleo_menu.pack(side="left", anchor="s", padx=(0, 10))

        self.mes_entry = ctk.CTkEntry(fila, width=110, justify="center")
        self.mes_entry.insert(0, date_utils.hoy_iso()[:7])
        self.mes_entry.pack(side="left", anchor="s", padx=(0, 10))
        ctk.CTkButton(
            fila, text="Actualizar", width=100, fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER,
            command=self._cargar,
        ).pack(side="left", anchor="s", padx=(0, 10))
        self.todos_boton = ctk.CTkButton(
            fila, text="Descargar todos (ZIP)", width=170, fg_color=tema.FONDO_TARJETA,
            border_width=1, border_color=tema.VERDE, text_color=tema.VERDE_CHIP_TEXTO,
            hover_color=tema.VERDE_CHIP_BG, command=self._descargar_todos, state="disabled",
        )
        self.todos_boton.pack(side="left", anchor="s")

        self.resumen_label = ctk.CTkLabel(self, text="", text_color=tema.ROJO, anchor="w")
        self.resumen_label.pack(fill="x", pady=(0, 8))
        self.color_normal = self.resumen_label.cget("text_color")

        self.progreso = ctk.CTkProgressBar(self, progress_color=tema.VERDE)
        self.progreso.set(0)
        self.progreso_label = ctk.CTkLabel(self, text="", text_color=tema.TEXTO_MUTED, anchor="w")

        # fill="x" y no "both"/expand: `self` es un CTkScrollableFrame, y un
        # hijo directo suyo no puede "llenar" un alto disponible (ver la
        # misma nota en cursos_screen.py).
        self.contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self.contenedor.pack(fill="x", pady=(10, 0))

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
            self._actualizar_opciones_nucleo()
            self._actualizar_resumen()
            self._redibujar()

        def fallo(exc):
            for w in self.contenedor.winfo_children():
                w.destroy()
            self.resumen_label.configure(text=str(exc), text_color=ROJO)

        en_segundo_plano(self, traer, listo, fallo)

    def filtrar(self, texto: str):
        """Lo llama el buscador del encabezado superior (ver
        `RevisarHubScreen`) — filtra por curso o docente sobre lo que ya
        está en memoria. El botón de ZIP sigue bajando TODO lo entregado
        del mes, no solo lo filtrado: es una descarga administrativa, no
        depende de qué se esté mirando en pantalla."""
        self._filtro_texto = texto.strip().lower()
        self._redibujar()

    def _actualizar_opciones_nucleo(self):
        # Solo los de curso tienen núcleo — los de gestión no pertenecen a
        # ninguno (ver comentario en __init__).
        nucleos = sorted(
            {i.get("nucleo", "").strip() for i in self._informes_curso if i.get("nucleo", "").strip()}
        )
        self.nucleo_menu.configure(values=[self._NUCLEO_TODOS] + nucleos)
        if self._filtro_nucleo not in ([self._NUCLEO_TODOS] + nucleos):
            self._filtro_nucleo = self._NUCLEO_TODOS
        self.nucleo_menu.set(self._filtro_nucleo)

    def _al_cambiar_nucleo(self, valor: str):
        self._filtro_nucleo = valor
        self._redibujar()

    def _coincide_filtro(self, item: dict) -> bool:
        if self._filtro_nucleo != self._NUCLEO_TODOS and item.get("nucleo", "").strip() != self._filtro_nucleo:
            return False
        if not self._filtro_texto:
            return True
        texto = f"{item.get('curso', '')} {item.get('docente', '')}".lower()
        return self._filtro_texto in texto

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

        informes_curso = [i for i in self._informes_curso if self._coincide_filtro(i)]
        informes_gestion = [d for d in self._informes_gestion if self._coincide_filtro(d)]

        if not informes_curso and not informes_gestion:
            ctk.CTkLabel(
                self.contenedor, text="Ningún informe coincide con la búsqueda.", text_color=GRIS,
            ).pack(anchor="w", pady=10)
            return

        if informes_curso:
            informes_curso.sort(
                key=lambda i: _PRIORIDAD_ESTADO.get(i.get("estado", "pendiente"), 0)
            )
            if informes_gestion:
                # El título "Informes de curso" solo hace falta cuando hay
                # las dos secciones separadas — con una sola no aporta nada.
                ctk.CTkLabel(
                    self.contenedor, text="Informes de curso", font=tema.fuente(13, "bold"),
                    text_color=tema.TEXTO_OSCURO, anchor="w",
                ).pack(fill="x", pady=(0, 10))
            grilla = ctk.CTkFrame(self.contenedor, fg_color="transparent")
            grilla.pack(fill="x")
            grilla.grid_columnconfigure((0, 1), weight=1, uniform="informes")
            for indice, i in enumerate(informes_curso):
                self._fila_informe_curso(grilla, indice, i)

        if informes_gestion:
            ctk.CTkLabel(
                self.contenedor, text="Informes de gestión", font=tema.fuente(13, "bold"),
                text_color=tema.TEXTO_OSCURO, anchor="w",
            ).pack(fill="x", pady=(16, 10))
            grilla_gestion = ctk.CTkFrame(self.contenedor, fg_color="transparent")
            grilla_gestion.pack(fill="x")
            grilla_gestion.grid_columnconfigure((0, 1), weight=1, uniform="informes")
            for indice, d in enumerate(informes_gestion):
                self._fila_informe_gestion(grilla_gestion, indice, d)

    def _actualizar_resumen(self):
        total = len(self._informes_curso) + len(self._informes_gestion)
        pendientes = sum(1 for i in self._informes_curso if i.get("estado", "pendiente") == "pendiente")
        self._pildora_entregados.configure(text=f"  {total} entregados  ")
        self._pildora_pendientes.configure(text=f"  {pendientes} pendientes de revisar  ")

    # --- informes de curso: revisar + descargar ---------------------------

    def _fila_informe_curso(self, grilla: ctk.CTkFrame, indice: int, i: dict):
        marco = ctk.CTkFrame(
            grilla, fg_color=tema.FONDO_TARJETA, corner_radius=16,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        marco.grid(
            row=indice // 2, column=indice % 2, sticky="nsew",
            padx=(0, 8) if indice % 2 == 0 else (8, 0), pady=8,
        )
        contenido = ctk.CTkFrame(marco, fg_color="transparent")
        contenido.pack(fill="both", expand=True, padx=22, pady=20)

        encabezado = ctk.CTkFrame(contenido, fg_color="transparent")
        encabezado.pack(fill="x")
        ctk.CTkFrame(
            encabezado, width=40, height=40, corner_radius=11, fg_color=tema.FONDO_CONTENIDO,
        ).pack(side="left", padx=(0, 14))
        textos = ctk.CTkFrame(encabezado, fg_color="transparent")
        textos.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            textos, text=i["curso"], font=tema.fuente(15, "bold"), text_color=tema.TEXTO_OSCURO,
            anchor="w", justify="left", wraplength=280,
        ).pack(fill="x")
        ctk.CTkLabel(
            textos, text=f"{i.get('docente', '')} · entregado {i.get('fecha', '')}",
            text_color=tema.TEXTO_MUTED, font=tema.fuente(12), anchor="w",
        ).pack(fill="x", pady=(3, 0))
        estado_fila = ctk.CTkFrame(encabezado, fg_color="transparent")
        estado_fila.pack(side="right")
        self._pintar_estado(estado_fila, i)

        botones = ctk.CTkFrame(contenido, fg_color="transparent")
        botones.pack(fill="x", pady=(14, 0))
        if i.get("doc_drive_id"):
            ctk.CTkButton(
                botones, text="Abrir", fg_color="transparent", border_width=1,
                text_color=tema.TEXTO_OSCURO, hover_color=tema.FONDO_CONTENIDO,
                command=lambda e=i: webbrowser.open(_url_drive(e["doc_drive_id"])),
            ).pack(side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkButton(
            botones, text="Descargar", fg_color="transparent", border_width=1,
            text_color=tema.TEXTO_OSCURO, hover_color=tema.FONDO_CONTENIDO,
            command=lambda e=i, m=self._mes_cargado: self._descargar_uno(e, m),
        ).pack(side="left", fill="x", expand=True, padx=(0, 6))
        aprobar_boton = ctk.CTkButton(
            botones, text="Aprobar", fg_color=VERDE, hover_color=tema.VERDE_HOVER
        )
        aprobar_boton.pack(side="left", fill="x", expand=True, padx=(0, 6))
        devolver_boton = ctk.CTkButton(
            botones, text="Devolver", fg_color=AMBAR, hover_color=tema.AMBAR_HOVER
        )
        devolver_boton.pack(side="left", fill="x", expand=True)
        botones_revision = (aprobar_boton, devolver_boton)
        aprobar_boton.configure(command=lambda: self._revisar(i, True, estado_fila, botones_revision))
        devolver_boton.configure(command=lambda: self._revisar(i, False, estado_fila, botones_revision))

    def _pintar_estado(self, estado_fila: ctk.CTkFrame, i: dict):
        for w in estado_fila.winfo_children():
            w.destroy()
        estado = i.get("estado", "pendiente")
        motivo = i.get("motivo_devolucion", "")
        if estado == "aprobado":
            pildora(estado_fila, "Aprobado ✓", tema.VERDE_CHIP_TEXTO, tema.VERDE_CHIP_BG).pack(side="left")
        elif estado == "devuelto":
            pildora(estado_fila, "Devuelto", AMBAR, tema.AMBAR_CHIP_BG).pack(side="left")
            if motivo:
                ctk.CTkLabel(
                    estado_fila, text=motivo, text_color=tema.TEXTO_MUTED, font=tema.fuente(11), anchor="w",
                ).pack(side="left", padx=(8, 0))
        else:
            pildora(estado_fila, "Pendiente de revisar", tema.TEXTO_MUTED, tema.FONDO_CONTENIDO).pack(side="left")

    def _revisar(self, i: dict, aprobar: bool, estado_fila: ctk.CTkFrame, botones: tuple):
        motivo = ""
        if not aprobar:
            dialogo = ctk.CTkInputDialog(
                title="Devolver",
                text="¿Por qué la devuelve? El docente va a ver este motivo:",
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
            i["estado"] = resultado["estado"]
            i["motivo_devolucion"] = motivo if not aprobar else ""
            self._actualizar_resumen()
            self._redibujar()  # mueve la tarjeta a su lugar nuevo según el estado

        def fallo(exc):
            for b in botones:
                b.configure(state="normal")
            self._pintar_estado(estado_fila, i)  # vuelve a lo último guardado, no a lo que se intentó
            self.resumen_label.configure(text=str(exc), text_color=ROJO)

        en_segundo_plano(
            self,
            lambda: api_client.revisar_informe(self.sesion["token"], i["curso_id"], i["mes"], aprobar, motivo),
            listo,
            fallo,
        )

    # --- informes de gestión: solo descargar -------------------------------

    def _fila_informe_gestion(self, grilla: ctk.CTkFrame, indice: int, d: dict):
        marco = ctk.CTkFrame(
            grilla, fg_color=tema.FONDO_TARJETA, corner_radius=16,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        marco.grid(
            row=indice // 2, column=indice % 2, sticky="nsew",
            padx=(0, 8) if indice % 2 == 0 else (8, 0), pady=8,
        )
        contenido = ctk.CTkFrame(marco, fg_color="transparent")
        contenido.pack(fill="both", expand=True, padx=22, pady=20)

        encabezado = ctk.CTkFrame(contenido, fg_color="transparent")
        encabezado.pack(fill="x")
        ctk.CTkFrame(
            encabezado, width=40, height=40, corner_radius=11, fg_color=tema.FONDO_CONTENIDO,
        ).pack(side="left", padx=(0, 14))
        ctk.CTkLabel(
            encabezado, text=d["curso"], font=tema.fuente(15, "bold"), text_color=tema.TEXTO_OSCURO,
            anchor="w", justify="left", wraplength=280,
        ).pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            contenido, text="Descargar", fg_color="transparent", border_width=1,
            text_color=tema.TEXTO_OSCURO, hover_color=tema.FONDO_CONTENIDO,
            command=lambda e=d, m=self._mes_cargado: self._descargar_uno(e, m),
        ).pack(fill="x", pady=(14, 0))

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
