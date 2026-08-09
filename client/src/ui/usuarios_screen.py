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
from ui.editar_usuario_screen import EditarUsuarioScreen
from ui.tareas import cache, en_segundo_plano
from ui.usuario_screen import UsuarioScreen

ROJO, AMBAR, VERDE, GRIS = "#c0392b", "#8A6114", "#2fa84f", "gray"

# Un mes sin entrar no es raro en época de vacaciones, así que recién ahí
# deja de contar como "viene usando la app".
DIAS_INACTIVO = 30


class UsuariosScreen(ctk.CTkFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None]):
        super().__init__(master)
        self.sesion = sesion

        ctk.CTkButton(self, text="← Volver", width=90, command=on_volver).pack(
            anchor="w", padx=12, pady=(12, 0)
        )

        self.tabview = ctk.CTkTabview(self)
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

    def _ir_a_editar(self, usuario: dict):
        self.tabview.set("Editar")
        self.editar.seleccionar(usuario["nombre"])


class ListaUsuariosTab(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_editar: Callable[[dict], None]):
        super().__init__(master)
        self.sesion = sesion
        self.on_editar = on_editar

        cabecera = ctk.CTkFrame(self, fg_color="transparent")
        cabecera.pack(fill="x")
        self.resumen_label = ctk.CTkLabel(
            cabecera, text="Cargando...", font=ctk.CTkFont(size=15, weight="bold"),
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

        self._cargar()

    def _recargar(self):
        cache.invalidar("usuarios")
        self._cargar()

    def _cargar(self):
        for w in self.tarjetas.winfo_children():
            w.destroy()
        self.resumen_label.configure(text="Cargando...", text_color=GRIS)

        def listo(usuarios):
            nunca = sum(1 for u in usuarios if not u.get("ultimo_acceso"))
            self.resumen_label.configure(text=f"{len(usuarios)} usuarios", text_color=self.color_normal)
            self.detalle_label.configure(
                text=f"{nunca} todavía no entraron a la app" if nunca else "Todos entraron alguna vez"
            )
            for usuario in sorted(usuarios, key=lambda u: str(u.get("nombre", "")).lower()):
                self._tarjeta(usuario)

        en_segundo_plano(
            self,
            lambda: cache.usuarios(self.sesion["token"]),
            listo,
            lambda exc: self.resumen_label.configure(text=str(exc), text_color=ROJO),
        )

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

        marco = ctk.CTkFrame(self.tarjetas, corner_radius=8, border_width=1)
        marco.pack(fill="x", pady=4)

        franja = ctk.CTkFrame(marco, width=5, fg_color=color, corner_radius=0)
        franja.pack(side="left", fill="y")
        franja.pack_propagate(False)

        cuerpo = ctk.CTkFrame(marco, fg_color="transparent")
        cuerpo.pack(side="left", fill="both", expand=True, padx=12, pady=10)

        ctk.CTkLabel(
            cuerpo, text=usuario.get("nombre", ""), font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w", justify="left", wraplength=460,
        ).pack(fill="x")

        etiquetas = [usuario.get("usuario", ""), usuario.get("rol", "")]
        if usuario.get("es_admin"):
            etiquetas.append("administrador")
        ctk.CTkLabel(
            cuerpo, text="  ·  ".join(e for e in etiquetas if e), text_color=GRIS, anchor="w"
        ).pack(fill="x")
        ctk.CTkLabel(cuerpo, text=texto_acceso, text_color=color, anchor="w").pack(fill="x", pady=(4, 0))

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
                     "Pasásela y decile que la cambie desde «Cambiar contraseña».",
                text_color=VERDE,
            )

        en_segundo_plano(
            self,
            lambda: api_client.restablecer_password(self.sesion["token"], usuario["id"], nueva),
            listo,
            lambda exc: self.aviso_label.configure(text=str(exc), text_color=ROJO),
        )
