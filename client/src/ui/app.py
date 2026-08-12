from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from ui.cargando import Cargando
from ui.login_screen import LoginScreen
from ui.home_screen import HomeScreen
from ui.planeaciones_screen import PlaneacionesScreen
from ui.planeacion_editor_screen import PlaneacionEditorScreen
from ui.dashboard_screen import DashboardScreen
from ui.informe_screen import InformeScreen
from ui.informe_gestion_screen import InformeGestionScreen
from ui.informes_mes_screen import InformesMesScreen
from ui.grupo_screen import GrupoScreen
from ui.cursos_screen import CursosScreen
from ui.horas_gestion_screen import HorasGestionScreen
from ui.planeaciones_docente_screen import PlaneacionesDocenteScreen
from ui.usuarios_screen import UsuariosScreen
from ui.password_screen import PasswordScreen
from ui.version_screen import VersionScreen
from ui import tareas
from ui.tareas import cache, en_segundo_plano
import api_client
from services import vista_previa


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Generación-I — Planeaciones")
        # Los equipos de la sede son viejos, así que hay que contar con
        # pantallas de 1366x768: descontando barra de tareas y título quedan
        # unos 696 px de alto útiles, y 720 se salía por abajo.
        self.geometry("700x670")
        self.minsize(560, 480)

        self.sesion: dict | None = None
        # customtkinter (CTkScrollableFrame en particular) no siempre queda
        # accesible recorriendo winfo_children(), así que guardamos la
        # pantalla activa acá para poder referenciarla directo.
        self.pantalla_actual: ctk.CTkBaseClass | None = None

        # Los borradores de vista previa llevan nombres de estudiantes y la
        # foto de la clase: no tienen por qué sobrevivir a la sesión.
        self.protocol("WM_DELETE_WINDOW", self._al_cerrar)

        self._mostrar_login()

    def _al_cerrar(self):
        # Cerrar en el medio de una subida mata el hilo antes de que Apps
        # Script termine de escribir: la planeación queda a medias o la
        # foto sin subir, y el docente cree que guardó.
        if tareas.hay_trabajo_pendiente():
            if not messagebox.askyesno(
                "Hay algo subiéndose",
                "Todavía se está subiendo algo al servidor.\n\n"
                "Si cerrás ahora puede quedar a medio guardar y vas a tener que "
                "cargarlo de nuevo.\n\n¿Cerrar igual?",
                icon="warning",
                default="no",
            ):
                return

        vista_previa.limpiar_borradores()
        self.destroy()

    def _limpiar(self):
        for widget in self.winfo_children():
            widget.destroy()
        self.pantalla_actual = None

    def _pantalla_cargando(self, texto: str):
        """Pantalla de transición con la animación de «trabajando», para las
        aperturas que primero tienen que ir a buscar algo al backend. Devuelve
        el widget Cargando por si hay que cambiarle el texto ante un error."""
        self._limpiar()
        marco = ctk.CTkFrame(self)
        marco.pack(fill="both", expand=True)
        cargando = Cargando(marco, texto=texto)
        cargando.place(relx=0.5, rely=0.5, anchor="center")
        self.pantalla_actual = marco
        return cargando

    def _mostrar_login(self):
        self._limpiar()
        self.pantalla_actual = LoginScreen(self, on_login_exitoso=self._on_login_exitoso)
        self.pantalla_actual.pack(fill="both", expand=True)

    # --- chequeo de versión, que corre de fondo al abrir (ver main.py) ---

    def version_verificada(self, aviso: str | None = None, link: str | None = None):
        """La versión alcanza para entrar: se habilita el login.

        Si veníamos de la pantalla de sin conexión —porque el usuario dio
        Reintentar y esta vez sí respondió— hay que volver al login, que
        es lo que quedó tapado.

        Con `aviso` hay una versión más nueva pero no obligatoria: se
        entra igual y el login muestra el mensaje con el link.
        """
        if not isinstance(self.pantalla_actual, LoginScreen):
            self._mostrar_login()
        self.pantalla_actual.habilitar(aviso=aviso, link=link)

    def bloquear(self, mensaje: str, titulo: str = "No se puede usar la app",
                 al_reintentar=None, link: str | None = None):
        """Reemplaza todo por el aviso: la app no se puede usar con una
        versión vieja ni sin poder verificarla.

        Con `al_reintentar` se muestra un botón para volver a probar, que es
        lo que corresponde cuando la causa es la conexión y no algo que el
        usuario tenga que ir a resolver a otro lado.
        """
        self._limpiar()
        aviso = ctk.CTkFrame(self)
        aviso.pack(fill="both", expand=True)

        contenido = ctk.CTkFrame(aviso, fg_color="transparent")
        contenido.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            contenido, text=titulo, font=ctk.CTkFont(size=18, weight="bold"), wraplength=380
        ).pack(pady=(0, 12))
        ctk.CTkLabel(
            contenido, text=mensaje, wraplength=380, justify="center", text_color="gray"
        ).pack()

        if link:
            # Para que el docente baje el instalador solo, sin que nadie
            # tenga que ir hasta su computador.
            import webbrowser

            ctk.CTkButton(
                contenido,
                text="Descargar el instalador",
                width=200,
                command=lambda: webbrowser.open(link),
            ).pack(pady=(20, 0))

        if al_reintentar is not None:
            boton = ctk.CTkButton(contenido, text="Reintentar", width=200)

            def reintentar():
                boton.configure(state="disabled", text="Probando...")
                al_reintentar()

            boton.configure(command=reintentar)
            boton.pack(pady=(20, 0))

        self.pantalla_actual = aviso

    def _on_login_exitoso(self, sesion: dict):
        self.sesion = sesion
        self._mostrar_home()
        # Deja el caché listo mientras el usuario mira el menú, así las
        # pantallas abren sin esperar viajes al backend.
        en_segundo_plano(self, lambda: cache.precargar(sesion), lambda _r: None, lambda _e: None)

    def _mostrar_home(self):
        self._limpiar()
        self.pantalla_actual = HomeScreen(
            self,
            self.sesion,
            on_planeaciones=self._mostrar_planeaciones,
            on_dashboard=self._mostrar_dashboard,
            on_informe=self._mostrar_informe,
            on_informes_mes=self._mostrar_informes_mes,
            on_grupo=self._mostrar_grupo,
            on_cursos=self._mostrar_cursos,
            on_horas_gestion=self._mostrar_horas_gestion,
            on_planeaciones_docente=self._mostrar_planeaciones_docente,
            on_usuarios=self._mostrar_usuarios,
            on_cambiar_password=self._mostrar_password,
            on_version=self._mostrar_version,
        )
        self.pantalla_actual.pack(fill="both", expand=True)

    def _mostrar_planeaciones(self):
        self._limpiar()
        self.pantalla_actual = PlaneacionesScreen(
            self,
            self.sesion,
            on_volver=self._mostrar_home,
            # Editar sale del hub al editor de pantalla completa; al volver,
            # se regresa al hub (que abre en «Mis planeaciones» recargada).
            on_editar=lambda p: self._mostrar_editor_planeacion(p, self._mostrar_planeaciones),
        )
        self.pantalla_actual.pack(fill="both", expand=True)

    def _mostrar_editor_planeacion(self, planeacion, on_volver):
        """Las listas traen un resumen sin bloques ni temas, así que la
        completa se pide recién acá, para la que se va a editar."""
        cargando = self._pantalla_cargando("Cargando la planeación...")

        def listo(completa):
            self._limpiar()
            self.pantalla_actual = PlaneacionEditorScreen(
                self, self.sesion, completa, on_volver=on_volver
            )
            self.pantalla_actual.pack(fill="both", expand=True)

        def fallo(exc):
            cargando.detener()
            cargando.configurar_texto(str(exc))

        en_segundo_plano(
            self,
            lambda: api_client.obtener_planeacion(self.sesion["token"], planeacion["id"]),
            listo,
            fallo,
        )

    def _mostrar_dashboard(self):
        self._limpiar()
        self.pantalla_actual = DashboardScreen(self, self.sesion, on_volver=self._mostrar_home)
        self.pantalla_actual.pack(fill="both", expand=True)

    def _mostrar_informe(self):
        """El informe de un directivo SIN curso es otro documento (solo
        gestión), así que se decide qué pantalla mostrar según si tiene
        cursos propios. Se consulta primero —del caché, normalmente sin
        viaje— para no montar la pantalla equivocada."""
        self._pantalla_cargando("Abriendo...")

        es_directivo = self.sesion["rol"] in ("directivo", "ambos")

        def listo(mis_cursos):
            self._limpiar()
            if es_directivo and not mis_cursos:
                self.pantalla_actual = InformeGestionScreen(self, self.sesion, on_volver=self._mostrar_home)
            else:
                self.pantalla_actual = InformeScreen(self, self.sesion, on_volver=self._mostrar_home)
            self.pantalla_actual.pack(fill="both", expand=True)

        en_segundo_plano(
            self,
            lambda: cache.mis_cursos(self.sesion["token"]),
            listo,
            # Ante un error de red, cae al informe docente (el caso común).
            lambda _exc: listo([1]),
        )

    def _mostrar_informes_mes(self):
        self._limpiar()
        self.pantalla_actual = InformesMesScreen(self, self.sesion, on_volver=self._mostrar_home)
        self.pantalla_actual.pack(fill="both", expand=True)

    def _mostrar_grupo(self):
        self._limpiar()
        self.pantalla_actual = GrupoScreen(self, self.sesion, on_volver=self._mostrar_home)
        self.pantalla_actual.pack(fill="both", expand=True)

    def _mostrar_cursos(self):
        self._limpiar()
        self.pantalla_actual = CursosScreen(self, self.sesion, on_volver=self._mostrar_home)
        self.pantalla_actual.pack(fill="both", expand=True)

    def _mostrar_horas_gestion(self):
        self._limpiar()
        self.pantalla_actual = HorasGestionScreen(self, self.sesion, on_volver=self._mostrar_home)
        self.pantalla_actual.pack(fill="both", expand=True)

    def _mostrar_planeaciones_docente(self):
        self._limpiar()
        self.pantalla_actual = PlaneacionesDocenteScreen(
            self,
            self.sesion,
            on_volver=self._mostrar_home,
            on_editar=lambda p: self._mostrar_editor_planeacion(p, self._mostrar_planeaciones_docente),
        )
        self.pantalla_actual.pack(fill="both", expand=True)

    def _mostrar_usuarios(self):
        self._limpiar()
        self.pantalla_actual = UsuariosScreen(self, self.sesion, on_volver=self._mostrar_home)
        self.pantalla_actual.pack(fill="both", expand=True)

    def _mostrar_version(self):
        self._limpiar()
        self.pantalla_actual = VersionScreen(self, self.sesion, on_volver=self._mostrar_home)
        self.pantalla_actual.pack(fill="both", expand=True)

    def _mostrar_password(self):
        self._limpiar()
        self.pantalla_actual = PasswordScreen(self, self.sesion, on_volver=self._mostrar_home)
        self.pantalla_actual.pack(fill="both", expand=True)
