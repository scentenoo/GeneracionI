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
from ui.widgets import avatar_iniciales, chip

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

        self.tabview = ctk.CTkTabview(
            self,
            segmented_button_selected_color=tema.DORADO_ACENTO,
            segmented_button_selected_hover_color=tema.DORADO_ACENTO_HOVER,
            segmented_button_unselected_color=tema.FONDO_TARJETA,
            text_color=tema.TEXTO_OSCURO,
            command=self._al_cambiar_pestana,
        )
        self.tabview.pack(fill="both", expand=True, padx=8, pady=8)
        for nombre in ("Lista", "Crear", "Editar"):
            self.tabview.add(nombre)

        self.editar = EditarUsuarioScreen(self.tabview.tab("Editar"), sesion)
        self.editar.pack(fill="both", expand=True)

        self.crear = UsuarioScreen(self.tabview.tab("Crear"), sesion)
        self.crear.pack(fill="both", expand=True)

        self.lista = ListaUsuariosTab(
            self.tabview.tab("Lista"), sesion, on_editar=self._ir_a_editar
        )
        self.lista.pack(fill="both", expand=True)

        self.tabview.set("Lista")
        self._al_cambiar_pestana()

    def _ir_a_editar(self, usuario: dict):
        self.tabview.set("Editar")
        self.editar.seleccionar(usuario["nombre"])
        self._al_cambiar_pestana()

    def _al_cambiar_pestana(self):
        if self.on_buscador is None:
            return
        if self.tabview.get() == "Lista":
            self.on_buscador(self.lista.filtrar, "Buscar nombre, usuario o rol...")
        else:
            self.on_buscador(None)


class ListaUsuariosTab(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_editar: Callable[[dict], None]):
        super().__init__(master)
        self.sesion = sesion
        self.on_editar = on_editar

        cabecera = ctk.CTkFrame(self, fg_color="transparent")
        cabecera.pack(fill="x")
        self.resumen_label = ctk.CTkLabel(
            cabecera, text="Cargando...", font=tema.fuente(15, "bold"),
            anchor="w", justify="left",
        )
        self.resumen_label.pack(side="left")
        # customtkinter no acepta text_color=None para "el del tema".
        self.color_normal = self.resumen_label.cget("text_color")
        ctk.CTkButton(cabecera, text="Actualizar", width=90, command=self._recargar).pack(side="right")

        self.detalle_label = ctk.CTkLabel(self, text="", text_color=GRIS, anchor="w", justify="left")
        self.detalle_label.pack(fill="x", pady=(0, 10))

        self.aviso_label = ctk.CTkLabel(self, text="", wraplength=560, anchor="w", justify="left")
        self.aviso_label.pack(fill="x")

        self.tarjetas = ctk.CTkFrame(self, fg_color="transparent")
        self.tarjetas.pack(fill="both", expand=True)

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
        self.resumen_label.configure(text="", text_color=GRIS)
        Cargando(self.tarjetas, texto="Cargando usuarios...").pack(pady=16)

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
                ).pack(anchor="w", pady=10)
                return

        for usuario in sorted(usuarios, key=lambda u: str(u.get("nombre", "")).lower()):
            self._tarjeta(usuario)

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

    def _tarjeta(self, usuario: dict):
        texto_acceso, dias = date_utils.hace_cuanto(usuario.get("ultimo_acceso"))
        if dias is None:
            color = AMBAR
        elif dias <= DIAS_INACTIVO:
            color = VERDE
        else:
            color = GRIS

        marco = ctk.CTkFrame(
            self.tarjetas, fg_color=tema.FONDO_TARJETA, corner_radius=10,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        marco.pack(fill="x", pady=4)

        franja = ctk.CTkFrame(marco, width=5, fg_color=color, corner_radius=0)
        franja.pack(side="left", fill="y")
        franja.pack_propagate(False)

        fila_superior = ctk.CTkFrame(marco, fg_color="transparent")
        fila_superior.pack(side="left", fill="both", expand=True, padx=12, pady=10)

        avatar_iniciales(fila_superior, texto(usuario.get("nombre")) or "?").pack(side="left")

        cuerpo = ctk.CTkFrame(fila_superior, fg_color="transparent")
        cuerpo.pack(side="left", fill="both", expand=True, padx=(10, 0))

        ctk.CTkLabel(
            cuerpo, text=texto(usuario.get("nombre")), font=tema.fuente(14, "bold"),
            anchor="w", justify="left", wraplength=420,
        ).pack(fill="x")
        ctk.CTkLabel(
            cuerpo, text=texto(usuario.get("usuario")), text_color=GRIS, anchor="w"
        ).pack(fill="x")

        etiquetas_fila = ctk.CTkFrame(cuerpo, fg_color="transparent")
        etiquetas_fila.pack(fill="x", pady=(4, 0))
        rol = texto(usuario.get("rol"))
        if rol:
            chip(etiquetas_fila, rol, tema.GRIS)
        if usuario.get("es_admin"):
            chip(etiquetas_fila, "administrador", tema.DORADO)
        chip(etiquetas_fila, texto_acceso, color)

        botones = ctk.CTkFrame(cuerpo, fg_color="transparent")
        botones.pack(fill="x", pady=(8, 0))
        ctk.CTkButton(
            botones, text="Editar", width=80, command=lambda: self.on_editar(usuario)
        ).pack(side="left", padx=(0, 6))
        if self._puede_restablecer(usuario):
            ctk.CTkButton(
                botones, text="Restablecer contraseña", width=170,
                fg_color="transparent", border_width=1,
                command=lambda: self._restablecer(usuario),
            ).pack(side="left")

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
