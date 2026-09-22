"""Revisar los informes del mes y descargarlos (Mariangel, Lorena,
administrador).

Junta dos cosas que antes vivían separadas: revisar (aprobar/devolver, acá
mismo con lo que ya se archivó en Drive) y descargar —de a uno o todos en
un ZIP—, que antes era la pantalla aparte «Informes del mes». Los informes
de gestión (directivos sin curso) no tienen revisión —el administrador no
"aprueba" la gestión de otro directivo— así que esos solo se descargan.

Igual que con las planeaciones: aprobar o devolver un informe no lo saca
de la lista, se ve ahí mismo con el estado nuevo — sin volver a pedirle
nada al backend, y sin tapar la ventana: el estado aparece apenas el
backend lo confirma y el documento archivado en Drive se actualiza en
segundo plano justo después (ver services/revision_documentos.py).
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
from services import date_utils, docx_generator, revision_documentos
from ui import tema
from ui.cargando import Cargando
from ui.tareas import cache, en_segundo_plano, en_segundo_plano_con_progreso
from ui.widgets import pildora

ROJO, VERDE, GRIS, AMBAR = tema.ROJO, tema.VERDE, tema.GRIS, tema.AMBAR

# Lo que falta por decidir va primero; lo devuelto (a mitad de corregirse)
# en el medio; lo ya aprobado, al final — es lo que menos hace falta mirar.
_PRIORIDAD_ESTADO = {"pendiente": 0, "devuelto": 1, "aprobado": 2}

# Cuántas tarjetas se ARMAN de una vez antes de devolverle el control a la
# ventana (armar una cuesta ~100 ms): ver _TANDA/_ARMADO_POR_TANDA en
# revisar_planeaciones_screen.py.
_ARMADO_POR_TANDA = 4


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
        # Las tarjetas de curso se CREAN una vez y después solo se reordenan
        # y se refrescan (ver revisar_planeaciones_screen.py, que explica el
        # porqué): la clave es el curso, en un mes hay un solo informe por
        # curso. Se vacía al recargar del backend (_vaciar_contenedor).
        self._grilla_curso: ctk.CTkFrame | None = None
        self._tarjetas: dict[int, dict] = {}
        self._redibujo_id: str | None = None  # `after` pendiente para seguir armando tarjetas

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
            command=lambda: self._cargar(forzar=True),
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

    def _cancelar_redibujo(self):
        if self._redibujo_id is not None:
            self.after_cancel(self._redibujo_id)
            self._redibujo_id = None

    def _seguir_redibujando(self):
        self._redibujo_id = None
        try:
            if not self.winfo_exists():
                return
        except Exception:  # noqa: BLE001 — la ventana ya se cerró
            return
        self._redibujar()

    def _vaciar_contenedor(self):
        self._cancelar_redibujo()
        for w in self.contenedor.winfo_children():
            w.destroy()
        self._grilla_curso = None
        self._tarjetas.clear()

    def _cargar(self, forzar: bool = False):
        self._vaciar_contenedor()
        self.resumen_label.configure(text="", text_color=GRIS)
        self.todos_boton.configure(state="disabled")
        cargando = Cargando(self.contenedor, texto="Cargando informes...")
        cargando.pack(pady=16)
        mes = self.mes_entry.get().strip()

        def traer():
            # Los directivos primero: mientras la pestaña de Planeaciones
            # (que se arma a la vez y pide lo mismo de la revisión) hace su
            # viaje, este corre en paralelo — y después la revisión sale del
            # caché compartido en vez de repetir otro viaje.
            directivos = api_client.directivos_sin_curso_del_mes(self.sesion["token"], mes)
            revision = cache.revision_del_mes(self.sesion["token"], mes, forzar)
            informes_curso = revision.get("informes", [])
            for i in informes_curso:
                i["tipo"] = "curso"

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
            self._vaciar_contenedor()
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
        """Pone la lista al día con lo que ya está en memoria —no le pide
        nada de nuevo al backend—, con los informes de curso ordenados:
        pendientes primero, devueltos en el medio, aprobados al final.
        Reutiliza las tarjetas de curso ya armadas (ver `_tarjetas`)."""
        self._cancelar_redibujo()  # esta pasada ya reemplaza a la que estaba en espera
        # Lo único que se rehace cada vez: títulos, mensajes y la sección de
        # gestión (pocos widgets). La grilla de cursos se conserva.
        for w in self.contenedor.winfo_children():
            if w is not self._grilla_curso:
                w.destroy()
        if self._grilla_curso is not None:
            self._grilla_curso.pack_forget()

        entregados = len(self._informes_curso) + len(self._informes_gestion)
        self.todos_boton.configure(state="normal" if entregados else "disabled")

        if not entregados:
            self._quitar_tarjetas_no_visibles([])
            ctk.CTkLabel(
                self.contenedor, text="Nadie entregó su informe todavía este mes.", text_color=GRIS
            ).pack(anchor="w", pady=10)
            return

        informes_curso = [i for i in self._informes_curso if self._coincide_filtro(i)]
        informes_gestion = [d for d in self._informes_gestion if self._coincide_filtro(d)]
        informes_curso.sort(key=lambda i: _PRIORIDAD_ESTADO.get(i.get("estado", "pendiente"), 0))
        self._quitar_tarjetas_no_visibles([i["curso_id"] for i in informes_curso])

        if not informes_curso and not informes_gestion:
            ctk.CTkLabel(
                self.contenedor, text="Ningún informe coincide con la búsqueda.", text_color=GRIS,
            ).pack(anchor="w", pady=10)
            return

        if informes_curso:
            if informes_gestion:
                # El título "Informes de curso" solo hace falta cuando hay
                # las dos secciones separadas — con una sola no aporta nada.
                ctk.CTkLabel(
                    self.contenedor, text="Informes de curso", font=tema.fuente(13, "bold"),
                    text_color=tema.TEXTO_OSCURO, anchor="w",
                ).pack(fill="x", pady=(0, 10))
            if self._grilla_curso is None:
                self._grilla_curso = ctk.CTkFrame(self.contenedor, fg_color="transparent")
                self._grilla_curso.grid_columnconfigure((0, 1), weight=1, uniform="informes")
            self._grilla_curso.pack(fill="x")
            armadas = 0
            faltan_por_armar = False
            indice = 0
            for i in informes_curso:
                tarjeta = self._tarjetas.get(i["curso_id"])
                if tarjeta is None:
                    if armadas >= _ARMADO_POR_TANDA:
                        faltan_por_armar = True  # se arman en la próxima tanda
                        continue
                    tarjeta = self._crear_tarjeta(i)
                    armadas += 1
                self._refrescar_tarjeta(tarjeta, i)
                celda = (indice // 2, indice % 2)
                indice += 1
                if tarjeta["celda"] != celda:
                    tarjeta["celda"] = celda
                    tarjeta["marco"].grid(
                        row=celda[0], column=celda[1], sticky="nsew",
                        padx=(0, 8) if celda[1] == 0 else (8, 0), pady=8,
                    )
            if faltan_por_armar:
                self._redibujo_id = self.after(10, self._seguir_redibujando)

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

    def _quitar_tarjetas_no_visibles(self, visibles: list[int]):
        """Saca de la grilla (sin destruirlas) las tarjetas que ya no se ven
        — filtradas por el buscador o el núcleo."""
        for curso_id, tarjeta in self._tarjetas.items():
            if curso_id not in visibles and tarjeta["celda"] is not None:
                tarjeta["marco"].grid_forget()
                tarjeta["celda"] = None

    def _actualizar_resumen(self):
        total = len(self._informes_curso) + len(self._informes_gestion)
        pendientes = sum(1 for i in self._informes_curso if i.get("estado", "pendiente") == "pendiente")
        self._pildora_entregados.configure(text=f"  {total} entregados  ")
        self._pildora_pendientes.configure(text=f"  {pendientes} pendientes de revisar  ")

    # --- informes de curso: revisar + descargar ---------------------------

    def _crear_tarjeta(self, i: dict) -> dict:
        """Arma los widgets de la tarjeta del informe `i` (sin ubicarla en la
        grilla: de eso se ocupa _redibujar) y los deja registrados para
        poder refrescarlos."""
        marco = ctk.CTkFrame(
            self._grilla_curso, fg_color=tema.FONDO_TARJETA, corner_radius=16,
            border_width=1, border_color=tema.BORDE_TARJETA,
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

        botones = ctk.CTkFrame(contenido, fg_color="transparent")
        botones.pack(fill="x", pady=(14, 0))
        abrir_boton = None
        if i.get("doc_drive_id"):
            abrir_boton = ctk.CTkButton(
                botones, text="Abrir", fg_color="transparent", border_width=1,
                text_color=tema.TEXTO_OSCURO, hover_color=tema.FONDO_CONTENIDO,
                command=lambda e=i: webbrowser.open(_url_drive(e["doc_drive_id"])),
            )
            abrir_boton.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkButton(
            botones, text="Descargar", fg_color="transparent", border_width=1,
            text_color=tema.TEXTO_OSCURO, hover_color=tema.FONDO_CONTENIDO,
            command=lambda e=i, m=self._mes_cargado: self._descargar_uno(e, m),
        ).pack(side="left", fill="x", expand=True, padx=(0, 6))
        aprobar_boton = ctk.CTkButton(
            botones, text="Aprobar", fg_color=VERDE, hover_color=tema.VERDE_HOVER,
            command=lambda: self._revisar(i, True),
        )
        aprobar_boton.pack(side="left", fill="x", expand=True, padx=(0, 6))
        devolver_boton = ctk.CTkButton(
            botones, text="Devolver", fg_color=AMBAR, hover_color=tema.AMBAR_HOVER,
            command=lambda: self._revisar(i, False),
        )
        devolver_boton.pack(side="left", fill="x", expand=True)

        tarjeta = {
            "marco": marco, "contenido": contenido, "estado_fila": estado_fila,
            "abrir": abrir_boton, "botones": (aprobar_boton, devolver_boton),
            "nota": None, "celda": None,
            "firma": None,  # None = todavía sin pintar el estado
        }
        self._tarjetas[i["curso_id"]] = tarjeta
        return tarjeta

    @staticmethod
    def _firma(i: dict) -> tuple:
        """Todo lo que cambia cómo se ve la parte VIVA de una tarjeta
        (estado, motivo, avisos). Si no cambió, no hace falta tocarla."""
        return (
            i.get("estado", "pendiente"), i.get("motivo_devolucion", ""),
            bool(i.get("_guardando")), bool(i.get("_docs_pendientes")), bool(i.get("_doc_error")),
        )

    def _refrescar_tarjeta(self, tarjeta: dict, i: dict):
        firma = self._firma(i)
        if tarjeta["firma"] == firma:
            return
        tarjeta["firma"] = firma
        self._pintar_estado(tarjeta["estado_fila"], i)
        for b in tarjeta["botones"]:
            b.configure(state="disabled" if i.get("_guardando") else "normal")
        if tarjeta["abrir"] is not None:
            # Mientras el documento se actualiza, abrirlo mostraría la
            # versión SIN la revisión que se acaba de hacer.
            tarjeta["abrir"].configure(state="disabled" if i.get("_docs_pendientes") else "normal")

        if tarjeta["nota"] is not None:
            tarjeta["nota"].destroy()
            tarjeta["nota"] = None
        if i.get("_docs_pendientes"):
            texto, color = "Actualizando documento...", tema.TEXTO_MUTED
        elif i.get("_doc_error"):
            texto, color = "Documento sin actualizar", ROJO
        else:
            return
        tarjeta["nota"] = ctk.CTkLabel(
            tarjeta["contenido"], text=texto, text_color=color, font=tema.fuente(11), anchor="w",
        )
        tarjeta["nota"].pack(fill="x", pady=(8, 0))

    def _refrescar_tarjeta_de(self, i: dict):
        tarjeta = self._tarjetas.get(i["curso_id"])
        if tarjeta is not None:
            self._refrescar_tarjeta(tarjeta, i)

    def _documento_terminado(self, i: dict, con_error: bool):
        """Terminó una actualización del documento de `i` (bien o mal):
        apaga el aviso y prende "Abrir" sin reconstruir la lista."""
        i["_docs_pendientes"] = max(0, i.get("_docs_pendientes", 0) - 1)
        if con_error:
            i["_doc_error"] = True
        if i["_docs_pendientes"] > 0:
            return  # todavía queda otra revisión del mismo documento en cola
        self._refrescar_tarjeta_de(i)

    def _pintar_estado(self, estado_fila: ctk.CTkFrame, i: dict):
        for w in estado_fila.winfo_children():
            w.destroy()
        if i.get("_guardando"):
            ctk.CTkLabel(estado_fila, text="Guardando...", text_color=GRIS, anchor="w").pack(side="left")
            return
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

    def _revisar(self, i: dict, aprobar: bool):
        motivo = ""
        if not aprobar:
            dialogo = ctk.CTkInputDialog(
                title="Devolver",
                text="¿Por qué la devuelve? El docente va a ver este motivo:",
            )
            motivo = (dialogo.get_input() or "").strip()
            if not motivo:
                return  # sin motivo no se devuelve

        i["_guardando"] = True
        self._refrescar_tarjeta_de(i)

        token = self.sesion["token"]
        curso_id, mes = i["curso_id"], i["mes"]
        # Sin documento archivado no hay nada que actualizar (y no vale la
        # pena un viaje para averiguarlo).
        hay_documento = bool(i.get("doc_drive_id"))

        def trabajo(reportar):
            # Ver la explicación de los dos tiempos en
            # revisar_planeaciones_screen._revisar.
            with revision_documentos.candado_revision:
                resultado = api_client.revisar_informe(token, curso_id, mes, aprobar, motivo)
            reportar(("estado", resultado))
            if not hay_documento:
                return None
            try:
                nuevo_doc_id = revision_documentos.sincronizar_informe(
                    token, curso_id, mes, resultado.get("historial")
                )
            except Exception as exc:  # noqa: BLE001 — se le avisa a la persona
                reportar(("doc_error", str(exc)))
            else:
                reportar(("doc", nuevo_doc_id))
            return None

        def progreso(valor):
            tipo, dato = valor
            if tipo == "estado":
                i["_guardando"] = False
                i["estado"] = dato["estado"]
                i["motivo_devolucion"] = motivo if not aprobar else ""
                i["_doc_error"] = False
                if hay_documento:
                    i["_docs_pendientes"] = i.get("_docs_pendientes", 0) + 1
                cache.invalidar("revision")  # lo compartido con Planeaciones ya quedó viejo
                self._actualizar_resumen()
                self._redibujar()  # mueve la tarjeta a su lugar nuevo según el estado
            elif tipo == "doc":
                if dato:
                    # Si el backend tuvo que recrear el archivo (no pudo
                    # pisarlo), el id cambió y "Abrir" iría a uno en la papelera.
                    i["doc_drive_id"] = dato
                self._documento_terminado(i, con_error=False)
            elif tipo == "doc_error":
                self._documento_terminado(i, con_error=True)
                self.resumen_label.configure(
                    text=f"El informe de «{i['curso']}» quedó {'aprobado' if aprobar else 'devuelto'}, pero no "
                         f"se pudo actualizar su documento en Drive: {dato}",
                    text_color=AMBAR,
                )

        def fallo(exc):
            # Solo llega acá si falló el cambio de estado en sí.
            i["_guardando"] = False
            self._refrescar_tarjeta_de(i)  # vuelve a lo último guardado, no a lo que se intentó
            self.resumen_label.configure(text=str(exc), text_color=ROJO)

        en_segundo_plano_con_progreso(
            self, trabajo, progreso, lambda _r: None, fallo,
            bloquea_cierre=True, mostrar_overlay=False,
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
