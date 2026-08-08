from __future__ import annotations

import customtkinter as ctk

from ui.login_screen import LoginScreen
from ui.home_screen import HomeScreen
from ui.planeacion_screen import PlaneacionScreen
from ui.dashboard_screen import DashboardScreen
from ui.informe_screen import InformeScreen
from ui.grupo_screen import GrupoScreen
from ui.usuario_screen import UsuarioScreen
from ui.password_screen import PasswordScreen


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Generación-I — Planeaciones")
        self.geometry("560x720")

        self.sesion: dict | None = None
        # customtkinter (CTkScrollableFrame en particular) no siempre queda
        # accesible recorriendo winfo_children(), así que guardamos la
        # pantalla activa acá para poder referenciarla directo.
        self.pantalla_actual: ctk.CTkBaseClass | None = None
        self._mostrar_login()

    def _limpiar(self):
        for widget in self.winfo_children():
            widget.destroy()
        self.pantalla_actual = None

    def _mostrar_login(self):
        self._limpiar()
        self.pantalla_actual = LoginScreen(self, on_login_exitoso=self._on_login_exitoso)
        self.pantalla_actual.pack(fill="both", expand=True)

    def _on_login_exitoso(self, sesion: dict):
        self.sesion = sesion
        self._mostrar_home()

    def _mostrar_home(self):
        self._limpiar()
        self.pantalla_actual = HomeScreen(
            self,
            self.sesion,
            on_nueva_planeacion=self._mostrar_planeacion,
            on_dashboard=self._mostrar_dashboard,
            on_informe=self._mostrar_informe,
            on_grupo=self._mostrar_grupo,
            on_crear_usuario=self._mostrar_crear_usuario,
            on_cambiar_password=self._mostrar_password,
        )
        self.pantalla_actual.pack(fill="both", expand=True)

    def _mostrar_planeacion(self):
        self._limpiar()
        self.pantalla_actual = PlaneacionScreen(self, self.sesion, on_volver=self._mostrar_home)
        self.pantalla_actual.pack(fill="both", expand=True)

    def _mostrar_dashboard(self):
        self._limpiar()
        self.pantalla_actual = DashboardScreen(self, self.sesion, on_volver=self._mostrar_home)
        self.pantalla_actual.pack(fill="both", expand=True)

    def _mostrar_informe(self):
        self._limpiar()
        self.pantalla_actual = InformeScreen(self, self.sesion, on_volver=self._mostrar_home)
        self.pantalla_actual.pack(fill="both", expand=True)

    def _mostrar_grupo(self):
        self._limpiar()
        self.pantalla_actual = GrupoScreen(self, self.sesion, on_volver=self._mostrar_home)
        self.pantalla_actual.pack(fill="both", expand=True)

    def _mostrar_crear_usuario(self):
        self._limpiar()
        self.pantalla_actual = UsuarioScreen(self, self.sesion, on_volver=self._mostrar_home)
        self.pantalla_actual.pack(fill="both", expand=True)

    def _mostrar_password(self):
        self._limpiar()
        self.pantalla_actual = PasswordScreen(self, self.sesion, on_volver=self._mostrar_home)
        self.pantalla_actual.pack(fill="both", expand=True)
