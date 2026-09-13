"""Todo lo de usuarios en una sola pantalla, con pestañas.

Antes eran dos botones sueltos en el menú ("Crear usuario" y "Editar
usuario") y no había forma de ver de un vistazo quiénes son ni quién está
usando la app. Ahora es un solo botón: Lista, Crear y Editar conviven, y
desde la lista se salta a editar a alguien puntual.

La lista muestra el último acceso porque es el dato que más falta hace
antes de reclamarle una planeación a alguien: si nunca entró, lo que pasa
no es que no cargó la clase, es que no tiene la app instalada.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

import api_client
from services import date_utils
from ui import tema
from ui.editar_usuario_screen import EditarUsuarioScreen
from ui.cargando import Cargando
from ui.tareas import cache, en_segundo_plano
from ui.usuario_screen import UsuarioScreen
from ui.widgets import PestanasPildora, avatar_iniciales, pildora

ROJO, AMBAR, VERDE, GRIS = tema.ROJO, tema.AMBAR, tema.VERDE, tema.GRIS

# Un mes sin entrar no es raro en época de vacaciones, así que recién ahí
# deja de contar como "viene usando la app".
DIAS_INACTIVO = 30


def texto(valor) -> str:
    """Sheets devuelve números donde uno espera texto: un usuario que se
    llame "2024" vuelve como int y reventaba el armado de la tarjeta,
    dejando la lista entera en blanco."""
    return "" if valor is None else str(valor)


class UsuariosScreen(ctk.CTkFrame):
    def __init__(
        self, master, sesion: dict, on_volver: Callable[[], None],
        on_buscador: Callable[[Callable[[str], None] | None, str], None] | None = None,
    ):
        super().__init__(master)
        self.sesion = sesion
        self.on_buscador = on_buscador

        ctk.CTkButton(
            self, text="← Volver", width=90, fg_color="transparent", border_width=1,
            text_color=tema.TEXTO_OSCURO, hover_color=tema.FONDO_TARJETA, command=on_volver,
        ).pack(anchor="w", padx=12, pady=(12, 0))

        self.tabview = PestanasPildora(self, command=self._al_cambiar_pestana)
        self.tabview.pack(fill="both", expand=True, padx=8, pady=8)
        for nombre in ("Lista", "Crear", "Editar"):
            self.tabview.add(nombre)

        self.editar = EditarUsuarioScreen(self.tabview.tab("Editar"), sesion)
        self.editar.pack(fill="both", expand=True)

        self.crear = UsuarioScreen(self.tabview.tab("Crear"), sesion)
        self.crear.pack(fill="both", expand=True)

        self.lista = ListaUsuariosTab(
            self.tabview.tab("Lista"), sesion, on_editar=self._ir_a_editar,
            on_crear=self._ir_a_crear,
        )
        self.lista.pack(fill="both", expand=True)

        self.tabview.set("Lista")
        self._al_cambiar_pestana()

    def _ir_a_editar(self, usuario: dict):
        self.tabview.set("Editar")
        self.editar.seleccionar(usuario["nombre"])
        self._al_cambiar_pestana()

    def _ir_a_crear(self):
        self.tabview.set("Crear")
        self._al_cambiar_pestana()

    def _al_cambiar_pestana(self):
        if self.on_buscador is None:
            return
        if self.tabview.get() == "Lista":
            self.on_buscador(self.lista.filtrar, "Buscar nombre, usuario o rol...")
        else:
            self.on_buscador(None)


_COLUMNAS = 3


class ListaUsuariosTab(ctk.CTkScrollableFrame):
    def __init__(
        self, master, sesion: dict, on_editar: Callable[[dict], None],
        on_crear: Callable[[], None] | None = None,
    ):
        super().__init__(master, fg_color="transparent")
        self.sesion = sesion
        self.on_editar = on_editar
        self.on_crear = on_crear

        cabecera = ctk.CTkFrame(self, fg_color="transparent")
        cabecera.pack(fill="x", pady=(4, 4))
        bloque_resumen = ctk.CTkFrame(cabecera, fg_color="transparent")
        bloque_resumen.pack(side="left")
        self.resumen_label = ctk.CTkLabel(
            bloque_resumen, text="Cargando...", font=tema.fuente(17, "bold"),
            text_color=tema.TEXTO_OSCURO, anchor="w", justify="left",
        )
        self.resumen_label.pack(side="left")
        # customtkinter no acepta text_color=None para "el del tema".
        self.color_normal = self.resumen_label.cget("text_color")
        self.detalle_label = ctk.CTkLabel(
            bloque_resumen, text="", text_color=tema.TEXTO_MUTED, font=tema.fuente(12), anchor="w",
        )
        self.detalle_label.pack(side="left", padx=(12, 0))

        botones_cabecera = ctk.CTkFrame(cabecera, fg_color="transparent")
        botones_cabecera.pack(side="right")
        if self.on_crear is not None:
            ctk.CTkButton(
                botones_cabecera, text="+ Nuevo usuario", fg_color=tema.VERDE_OSCURO,
                hover_color=tema.VERDE_OSCURO_ACTIVO, command=self.on_crear,
            ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            botones_cabecera, text="Actualizar", width=90, fg_color="transparent", border_width=1,
            text_color=tema.TEXTO_OSCURO, hover_color=tema.FONDO_CONTENIDO, command=self._recargar,
        ).pack(side="right")

        self.aviso_label = ctk.CTkLabel(self, text="", wraplength=760, anchor="w", justify="left")
        self.aviso_label.pack(fill="x", pady=(0, 8))

        self.tarjetas = ctk.CTkFrame(self, fg_color="transparent")
        self.tarjetas.pack(fill="both", expand=True)
        for col in range(_COLUMNAS):
            self.tarjetas.grid_columnconfigure(col, weight=1, uniform="usuarios")

        self._usuarios_cache: list[dict] = []
        self._filtro_texto = ""
        self._cargar()

    def _recargar(self):
        cache.invalidar("usuarios")
        self._cargar()

    def filtrar(self, texto: str):
        """Lo llama el buscador del encabezado superior (ver
        `UsuariosScreen`) — filtra por nombre, usuario o rol sobre lo que
        ya está en memoria."""
        self._filtro_texto = texto.strip().lower()
        self._renderizar()

    def _cargar(self):
        for w in self.tarjetas.winfo_children():
            w.destroy()
        self.resumen_label.configure(text="", text_color=self.color_normal)
        Cargando(self.tarjetas, texto="Cargando usuarios...").grid(row=0, column=0, columnspan=_COLUMNAS, pady=16)

        def listo(usuarios):
            self._usuarios_cache = usuarios
            nunca = sum(1 for u in usuarios if not u.get("ultimo_acceso"))
            self.resumen_label.configure(text=f"{len(usuarios)} usuarios", text_color=self.color_normal)
            self.detalle_label.configure(
                text=f"{nunca} todavía no entraron a la app" if nunca else "Todos entraron alguna vez"
            )
            self._renderizar()

        def fallo(exc):
            for w in self.tarjetas.winfo_children():
                w.destroy()
            self.resumen_label.configure(text=str(exc), text_color=ROJO)

        en_segundo_plano(
            self,
            lambda: cache.usuarios(self.sesion["token"]),
            listo,
            fallo,
        )

    def _renderizar(self):
        """Redibuja con lo que ya está en `self._usuarios_cache`, sin
        pedir nada nuevo al backend — la llaman tanto la carga inicial
        como el buscador."""
        for w in self.tarjetas.winfo_children():
            w.destroy()

        usuarios = self._usuarios_cache
        if self._filtro_texto:
            def coincide(u):
                texto = f"{u.get('nombre', '')} {u.get('usuario', '')} {u.get('rol', '')}".lower()
                return self._filtro_texto in texto
            usuarios = [u for u in usuarios if coincide(u)]
            if not usuarios:
                ctk.CTkLabel(
                    self.tarjetas, text="Ningún usuario coincide con la búsqueda.", text_color=GRIS,
                ).grid(row=0, column=0, columnspan=_COLUMNAS, sticky="w", pady=10)
                return

        for i, usuario in enumerate(sorted(usuarios, key=lambda u: str(u.get("nombre", "")).lower())):
            self._tarjeta(usuario, i // _COLUMNAS, i % _COLUMNAS)

    def _puede_restablecer(self, usuario: dict) -> bool:
        """Misma regla que aplica el backend: un directivo restablece
        docentes, y para tocar a otro directivo hace falta el
        administrador. Acá solo se esconde el botón — quien manda es el
        backend."""
        if usuario["id"] == self.sesion["id"]:
            return True
        if usuario.get("rol") == "docente":
            return True
        return bool(self.sesion.get("es_admin"))

    def _tarjeta(self, usuario: dict, fila: int, columna: int):
        texto_acceso, dias = date_utils.hace_cuanto(usuario.get("ultimo_acceso"))
        if dias is None:
            color, fondo_color = tema.AMBAR, tema.AMBAR_CHIP_BG
        elif dias <= DIAS_INACTIVO:
            color, fondo_color = tema.VERDE_CHIP_TEXTO, tema.VERDE_CHIP_BG
        else:
            color, fondo_color = tema.TEXTO_MUTED, tema.FONDO_CONTENIDO

        marco = ctk.CTkFrame(
            self.tarjetas, fg_color=tema.FONDO_TARJETA, corner_radius=16,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        marco.grid(row=fila, column=columna, sticky="nsew", padx=8, pady=8)

        cuerpo = ctk.CTkFrame(marco, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True, padx=20, pady=18)

        fila_superior = ctk.CTkFrame(cuerpo, fg_color="transparent")
        fila_superior.pack(fill="x")
        avatar_iniciales(fila_superior, texto(usuario.get("nombre")) or "?", tamano=44).pack(side="left")
        textos = ctk.CTkFrame(fila_superior, fg_color="transparent")
        textos.pack(side="left", padx=(12, 0), fill="x", expand=True)
        ctk.CTkLabel(
            textos, text=texto(usuario.get("nombre")), font=tema.fuente(14, "bold"),
            text_color=tema.TEXTO_OSCURO, anchor="w", justify="left", wraplength=190,
        ).pack(fill="x")
        ctk.CTkLabel(
            textos, text=texto(usuario.get("usuario")), text_color=tema.TEXTO_MUTED,
            font=tema.fuente(11), anchor="w",
        ).pack(fill="x")

        # Fila propia para el acceso: con rol + administrador, tres píldoras
        # en una sola fila no entran en una tarjeta de este ancho (probado a
        # ojo con la captura de la sesión — la tercera quedaba cortada).
        etiquetas_fila = ctk.CTkFrame(cuerpo, fg_color="transparent")
        etiquetas_fila.pack(fill="x", pady=(12, 0))
        rol = texto(usuario.get("rol"))
        if rol:
            pildora(etiquetas_fila, rol, tema.TEXTO_MUTED, tema.FONDO_CONTENIDO).pack(side="left", padx=(0, 6))
        if usuario.get("es_admin"):
            pildora(etiquetas_fila, "administrador", tema.AMBAR, tema.AMBAR_CHIP_BG).pack(side="left")

        fila_acceso = ctk.CTkFrame(cuerpo, fg_color="transparent")
        fila_acceso.pack(fill="x", pady=(6, 0))
        pildora(fila_acceso, texto_acceso, color, fondo_color).pack(side="left")

        botones = ctk.CTkFrame(cuerpo, fg_color="transparent")
        botones.pack(fill="x", pady=(14, 0))
        ctk.CTkButton(
            botones, text="Editar", fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER,
            command=lambda: self.on_editar(usuario),
        ).pack(fill="x")
        if self._puede_restablecer(usuario):
            ctk.CTkButton(
                botones, text="Restablecer contraseña", fg_color="transparent", border_width=1,
                text_color=tema.TEXTO_MUTED,
                command=lambda: self._restablecer(usuario),
            ).pack(fill="x", pady=(6, 0))

    def _restablecer(self, usuario: dict):
        """No hay "ver la contraseña": el backend guarda un hash con salt,
        ni él la conoce. Lo que resuelve el caso real —a alguien se le
        olvidó— es ponerle una nueva y pasársela."""
        dialogo = ctk.CTkInputDialog(
            title="Restablecer contraseña",
            text=f"Contraseña nueva para {usuario.get('nombre', '')}:",
        )
        nueva = dialogo.get_input()
        if not nueva:
            return

        self.aviso_label.configure(text="Restableciendo...", text_color=GRIS)

        def listo(_r):
            self.aviso_label.configure(
                text=f"Listo. La contraseña de {usuario.get('nombre', '')} ahora es:  {nueva}\n"
                     "Pásesela y dígale que la cambie desde «Cambiar contraseña».",
                text_color=VERDE,
            )

        en_segundo_plano(
            self,
            lambda: api_client.restablecer_password(self.sesion["token"], usuario["id"], nueva),
            listo,
            lambda exc: self.aviso_label.configure(text=str(exc), text_color=ROJO),
        )
