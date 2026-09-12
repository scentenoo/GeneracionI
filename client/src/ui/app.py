from __future__ import annotations

import time
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from config import TEMPLATES_DIR
from ui import ctk_parches, tema
from ui.barra_lateral import BarraLateral
from ui.barra_superior import BarraSuperior
from ui.cargando import Cargando
from ui.login_screen import LoginScreen
from ui.home_screen import HomeScreen
from ui.planeaciones_screen import PlaneacionesScreen
from ui.planeacion_editor_screen import PlaneacionEditorScreen
from ui.informe_screen import InformeScreen
from ui.informe_gestion_screen import InformeGestionScreen
from ui.cursos_hub_screen import CursosHubScreen
from ui.horas_gestion_screen import HorasGestionScreen
from ui.revisar_hub_screen import RevisarHubScreen
from ui.usuarios_screen import UsuariosScreen
from ui.password_screen import PasswordScreen
from ui.revisores_screen import RevisoresScreen
from ui.version_screen import VersionScreen
from ui import tareas, overlay_carga
from ui.tareas import cache, en_segundo_plano
import api_client
from services import vista_previa


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Generación-I — Planeaciones")
        self._poner_icono()
        ctk_parches.reparar_copiar_pegar(self)
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
        # Barra lateral + área de contenido: se arman una sola vez tras el
        # login (ver _armar_shell) y quedan en pie durante toda la sesión.
        # Antes de eso (login, pantallas de bloqueo) no existen.
        self._sidebar: BarraLateral | None = None
        self._encabezado: BarraSuperior | None = None
        self._content: ctk.CTkFrame | None = None

        # Los borradores de vista previa llevan nombres de estudiantes y la
        # foto de la clase: no tienen por qué sobrevivir a la sesión.
        self.protocol("WM_DELETE_WINDOW", self._al_cerrar)

        self._telon_mostrado_en: float | None = None
        self._mostrar_telon()

    def _poner_icono(self):
        """El ícono de la ventana (esquina superior, Alt+Tab, barra de
        tareas) — no confundir con el ícono del .exe en sí, que se embebe
        aparte al compilar (ver GeneracionI-Planeaciones.spec).

        `iconphoto` con la imagen maestra de 1024x1024 queda con el ícono
        vacío y sin error — probado en este equipo: un PNG de 256x256 ya
        alcanza para que el escritorio lo descarte en silencio, 128 sí
        anda. Por eso acá se usan los chicos (128 a 16), no el maestro."""
        carpeta = TEMPLATES_DIR / "assets"
        try:
            self._iconos = [
                tk.PhotoImage(file=str(carpeta / f"logo_generacion_i_{tam}.png"))
                for tam in (128, 64, 48, 32, 16)
            ]
            self.iconphoto(True, *self._iconos)
        except Exception:  # noqa: BLE001 — sin ícono la app igual funciona
            pass

    def _al_cerrar(self):
        # Cerrar en el medio de una subida mata el hilo antes de que Apps
        # Script termine de escribir: la planeación queda a medias o la
        # foto sin subir, y el docente cree que guardó.
        if tareas.hay_trabajo_pendiente():
            if not messagebox.askyesno(
                "Hay algo subiéndose",
                "Todavía se está subiendo algo al servidor.\n\n"
                "Si cierra ahora puede quedar a medio guardar y va a tener que "
                "cargarlo de nuevo.\n\n¿Cerrar igual?",
                icon="warning",
                default="no",
            ):
                return
        # Sin escritura de por medio (una descarga, una consulta) no hay
        # riesgo de quedar a medio guardar, pero cerrar en el medio sí
        # tira lo ya avanzado — y con el overlay tapando la pantalla,
        # cerrar en ese momento se siente como que algo se rompió.
        elif overlay_carga.hay_overlay_activo(self):
            if not messagebox.askyesno(
                "Todavía se está cargando algo",
                "La app está esperando una respuesta del servidor (una descarga, "
                "una consulta).\n\nSi cierra ahora se corta a la mitad y va a "
                "tener que empezar de nuevo.\n\n¿Cerrar igual?",
                icon="warning",
                default="no",
            ):
                return

        vista_previa.limpiar_borradores()
        self.destroy()

    def _limpiar(self):
        """Limpia TODA la ventana — login y pantallas de bloqueo, donde no
        hay barra lateral. Para navegar entre secciones ya logueado, usar
        `_limpiar_contenido` en vez de esto (deja la barra en pie)."""
        for widget in self.winfo_children():
            widget.destroy()
        self.pantalla_actual = None
        self._sidebar = None
        self._encabezado = None
        self._content = None

    def _limpiar_contenido(self):
        """Limpia solo el área de contenido, sin tocar la barra lateral."""
        for widget in self._content.winfo_children():
            widget.destroy()
        self.pantalla_actual = None

    def _armar_shell(self):
        """Arma barra lateral + encabezado superior + área de contenido,
        una sola vez por sesión (se llama justo después del login). Todo
        lo que se muestre de acá en más empaqueta dentro de
        `self._content`, nunca sobre `self` directo — así la barra y el
        encabezado no se destruyen en cada cambio de pantalla."""
        self._limpiar()
        cuerpo = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        cuerpo.pack(fill="both", expand=True)

        self._sidebar = BarraLateral(
            cuerpo, self.sesion, self._secciones_sidebar(), on_cerrar_sesion=self._cerrar_sesion,
        )
        self._sidebar.pack(side="left", fill="y")

        columna_derecha = ctk.CTkFrame(cuerpo, fg_color="transparent", corner_radius=0)
        columna_derecha.pack(side="left", fill="both", expand=True)

        self._encabezado = BarraSuperior(columna_derecha)
        self._encabezado.pack(fill="x")

        self._content = ctk.CTkFrame(columna_derecha, fg_color=tema.FONDO_CONTENIDO, corner_radius=0)
        self._content.pack(fill="both", expand=True)

    def _secciones_sidebar(self):
        """Qué secciones ve cada quien — misma lógica de roles que antes
        vivía en HomeScreen, ahora al servicio de la barra lateral."""
        sesion = self.sesion
        es_docente = sesion["rol"] in ("docente", "ambos")
        # El administrador entra a las pantallas de gestión aunque su rol
        # sea docente. Eso no lo vuelve directivo: ver comentario largo en
        # _mostrar_informe.
        es_directivo = sesion["rol"] in ("directivo", "ambos") or bool(sesion.get("es_admin"))

        secciones = [("home", "Inicio", self._mostrar_home)]
        if es_docente:
            secciones.append(("planeaciones", "Planeaciones y actividades", self._mostrar_planeaciones))
        secciones.append(("informe", "Generar informe mensual", self._mostrar_informe))

        if es_directivo:
            secciones.append(("revisar", "Revisar planeaciones e informes", self._mostrar_revisar))
            secciones.append(("cursos", "Cursos", self._mostrar_cursos))
            secciones.append(("horas_gestion", "Horas de gestión", self._mostrar_horas_gestion))
            secciones.append(("usuarios", "Usuarios", self._mostrar_usuarios))

        secciones.append(("password", "Cambiar contraseña", self._mostrar_password))
        # Publicar una versión bloquea a quien no la tenga, y reasignar
        # revisores cambia quién aprueba el trabajo de todos: las dos van
        # detrás del administrador único y no del rol directivo.
        if sesion.get("es_admin"):
            secciones.append(("revisores", "Revisores por color", self._mostrar_revisores))
            secciones.append(("version", "Versión de la app", self._mostrar_version))
        return secciones

    def _cerrar_sesion(self):
        # Mismo resguardo que al cerrar la ventana entera: cortar en el
        # medio de una subida la deja a medio guardar.
        if tareas.hay_trabajo_pendiente():
            if not messagebox.askyesno(
                "Hay algo subiéndose",
                "Todavía se está subiendo algo al servidor.\n\n"
                "Si cierra la sesión ahora puede quedar a medio guardar.\n\n"
                "¿Cerrar sesión igual?",
                icon="warning",
                default="no",
            ):
                return
        self.sesion = None
        vista_previa.limpiar_borradores()
        self._mostrar_login()

    def _pantalla_cargando(self, texto: str):
        """Pantalla de transición con la animación de «trabajando», para las
        aperturas que primero tienen que ir a buscar algo al backend. Devuelve
        el widget Cargando por si hay que cambiarle el texto ante un error."""
        self._limpiar_contenido()
        marco = ctk.CTkFrame(self._content, fg_color="transparent")
        marco.pack(fill="both", expand=True)
        cargando = Cargando(marco, texto=texto)
        cargando.place(relx=0.5, rely=0.5, anchor="center")
        self.pantalla_actual = marco
        return cargando

    def _mostrar_login(self):
        self._limpiar()
        self.pantalla_actual = LoginScreen(self, on_login_exitoso=self._on_login_exitoso)
        self.pantalla_actual.pack(fill="both", expand=True)

    def _mostrar_telon(self):
        """Lo primero que ve el profe al abrir la app, mientras se verifica
        la versión contra el backend (ver main.py) — reemplaza la espera
        silenciosa que antes tapaba el login con el botón deshabilitado."""
        from ui.overlay_carga import TelonVerde

        self._limpiar()
        self.pantalla_actual = TelonVerde(self)
        self.pantalla_actual.pack(fill="both", expand=True)
        self._telon_mostrado_en = time.monotonic()

    def _tras_telon_minimo(self, accion):
        """Si el telón de arranque sigue en pantalla, espera lo que falte
        para completar DURACION_MINIMA_TELON_MS antes de correr `accion`
        —así no parpadea en una conexión rápida—; si no hay telón (por
        ejemplo, un Reintentar desde la pantalla de bloqueo), corre
        `accion` de una vez."""
        from ui.overlay_carga import DURACION_MINIMA_TELON_MS, TelonVerde

        if isinstance(self.pantalla_actual, TelonVerde) and self._telon_mostrado_en is not None:
            transcurrido_ms = (time.monotonic() - self._telon_mostrado_en) * 1000
            falta_ms = DURACION_MINIMA_TELON_MS - transcurrido_ms
            if falta_ms > 0:
                self.after(int(falta_ms), accion)
                return
        accion()

    # --- chequeo de versión, que corre de fondo al abrir (ver main.py) ---

    def version_verificada(self, aviso: str | None = None, link: str | None = None):
        """La versión alcanza para entrar: se habilita el login.

        Si veníamos de la pantalla de sin conexión —porque el usuario dio
        Reintentar y esta vez sí respondió— hay que volver al login, que
        es lo que quedó tapado.

        Con `aviso` hay una versión más nueva pero no obligatoria: se
        entra igual y el login muestra el mensaje con el link.
        """
        def mostrar():
            if not isinstance(self.pantalla_actual, LoginScreen):
                self._mostrar_login()
            self.pantalla_actual.habilitar(aviso=aviso, link=link)

        self._tras_telon_minimo(mostrar)

    def bloquear(self, mensaje: str, titulo: str = "No se puede usar la app",
                 al_reintentar=None, link: str | None = None):
        """Reemplaza todo por el aviso: la app no se puede usar con una
        versión vieja ni sin poder verificarla.

        Con `al_reintentar` se muestra un botón para volver a probar, que es
        lo que corresponde cuando la causa es la conexión y no algo que el
        usuario tenga que ir a resolver a otro lado.
        """
        self._tras_telon_minimo(
            lambda: self._bloquear_ya(mensaje, titulo, al_reintentar, link)
        )

    def _bloquear_ya(self, mensaje: str, titulo: str, al_reintentar, link: str | None):
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
        self._armar_shell()
        self._mostrar_home()
        # Deja el caché listo mientras el usuario mira el menú, así las
        # pantallas abren sin esperar viajes al backend.
        en_segundo_plano(
            self, lambda: cache.precargar(sesion), lambda _r: None, lambda _e: None,
            mostrar_overlay=False,
        )
        # Al entrar, avisar qué le devolvieron para corregir y cuándo cierra
        # el mes. Va aparte del caché para que un fallo del aviso no impida
        # usar la app.
        en_segundo_plano(
            self, lambda: self._datos_aviso(sesion), self._avisos_al_entrar, lambda _e: None,
            mostrar_overlay=False,
        )

    def _datos_aviso(self, sesion: dict) -> dict:
        """Junta en un solo viaje lo que se muestra al entrar."""
        from services import date_utils

        devoluciones = api_client.mis_devoluciones(sesion["token"])
        cierre = api_client.fecha_de_cierre(sesion["token"], date_utils.hoy_iso()[:7])
        return {"devoluciones": devoluciones, "cierre": cierre}

    def _avisos_al_entrar(self, datos: dict):
        """Aviso al entrar: lo devuelto para corregir (con motivo) y, si está
        cerca, cuándo se cierra el mes. Si no hay nada que decir, no molesta."""
        from services import date_utils
        from services.avisos import texto_devoluciones

        devoluciones = datos.get("devoluciones") or []
        cierre = datos.get("cierre") or {}

        partes = []
        texto = texto_devoluciones(devoluciones)
        if texto:
            partes.append(texto)

        # El cierre solo se avisa si falta poco (y no pasó): recordárselo cada
        # día del mes sería ruido.
        fecha_cierre = str(cierre.get("fecha_cierre") or "")
        dias = self._dias_hasta(fecha_cierre)
        if dias is not None and 0 <= dias <= 5:
            cuando = "hoy" if dias == 0 else ("mañana" if dias == 1 else f"en {dias} días")
            partes.append(
                f"Ojo: el mes se cierra {cuando} ({date_utils.a_fecha_corta(fecha_cierre)}). "
                "Después de esa fecha no va a poder cargar ni corregir nada de este mes."
            )

        if not partes:
            return
        messagebox.showwarning("Antes de empezar", "\n\n———\n\n".join(partes))

    @staticmethod
    def _dias_hasta(fecha_iso: str):
        import datetime

        try:
            objetivo = datetime.date.fromisoformat(fecha_iso)
        except (ValueError, TypeError):
            return None
        return (objetivo - datetime.date.today()).days

    def _mostrar_home(self):
        self._limpiar_contenido()
        self._sidebar.marcar_activo("home")
        self._encabezado.configurar_titulo("Inicio")
        self._encabezado.configurar_buscador(None)
        self.pantalla_actual = HomeScreen(self._content, self.sesion)
        self.pantalla_actual.pack(fill="both", expand=True)

    def _mostrar_planeaciones(self):
        self._limpiar_contenido()
        self._sidebar.marcar_activo("planeaciones")
        self._encabezado.configurar_titulo("Planeaciones y actividades")
        self.pantalla_actual = PlaneacionesScreen(
            self._content,
            self.sesion,
            on_volver=self._mostrar_home,
            # Editar sale del hub al editor de pantalla completa; al volver,
            # se regresa al hub (que abre en «Mis planeaciones» recargada).
            on_editar=lambda p: self._mostrar_editor_planeacion(p, self._mostrar_planeaciones),
            on_buscador=self._encabezado.configurar_buscador,
        )
        self.pantalla_actual.pack(fill="both", expand=True)

    def _mostrar_editor_planeacion(self, planeacion, on_volver):
        """Las listas traen un resumen sin bloques ni temas, así que la
        completa se pide recién acá, para la que se va a editar."""
        cargando = self._pantalla_cargando("Cargando la planeación...")

        def listo(completa):
            self._limpiar_contenido()
            self._encabezado.configurar_titulo("Editar planeación")
            self._encabezado.configurar_buscador(None)
            self.pantalla_actual = PlaneacionEditorScreen(
                self._content, self.sesion, completa, on_volver=on_volver
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

    def _mostrar_informe(self):
        """El informe de un directivo SIN curso es otro documento (solo
        gestión), así que se decide qué pantalla mostrar según si tiene
        cursos propios. Se consulta primero —del caché, normalmente sin
        viaje— para no montar la pantalla equivocada."""
        self._pantalla_cargando("Abriendo...")
        self._sidebar.marcar_activo("informe")
        self._encabezado.configurar_titulo("Generar informe mensual")
        self._encabezado.configurar_buscador(None)

        es_directivo = self.sesion["rol"] in ("directivo", "ambos")

        def listo(mis_cursos):
            self._limpiar_contenido()
            if es_directivo and not mis_cursos:
                self.pantalla_actual = InformeGestionScreen(self._content, self.sesion, on_volver=self._mostrar_home)
            else:
                self.pantalla_actual = InformeScreen(self._content, self.sesion, on_volver=self._mostrar_home)
            self.pantalla_actual.pack(fill="both", expand=True)

        en_segundo_plano(
            self,
            lambda: cache.mis_cursos(self.sesion["token"]),
            listo,
            # Ante un error de red, cae al informe docente (el caso común).
            lambda _exc: listo([1]),
        )

    def _mostrar_cursos(self):
        self._limpiar_contenido()
        self._sidebar.marcar_activo("cursos")
        self._encabezado.configurar_titulo("Cursos")
        self.pantalla_actual = CursosHubScreen(
            self._content, self.sesion, on_volver=self._mostrar_home,
            on_buscador=self._encabezado.configurar_buscador,
        )
        self.pantalla_actual.pack(fill="both", expand=True)

    def _mostrar_horas_gestion(self):
        self._limpiar_contenido()
        self._sidebar.marcar_activo("horas_gestion")
        self._encabezado.configurar_titulo("Horas de gestión")
        self._encabezado.configurar_buscador(None)
        self.pantalla_actual = HorasGestionScreen(self._content, self.sesion, on_volver=self._mostrar_home)
        self.pantalla_actual.pack(fill="both", expand=True)

    def _mostrar_revisar(self):
        self._limpiar_contenido()
        self._sidebar.marcar_activo("revisar")
        self._encabezado.configurar_titulo("Revisar planeaciones e informes")
        self.pantalla_actual = RevisarHubScreen(
            self._content, self.sesion, on_volver=self._mostrar_home,
            on_buscador=self._encabezado.configurar_buscador,
        )
        self.pantalla_actual.pack(fill="both", expand=True)

    def _mostrar_usuarios(self):
        self._limpiar_contenido()
        self._sidebar.marcar_activo("usuarios")
        self._encabezado.configurar_titulo("Usuarios")
        self.pantalla_actual = UsuariosScreen(
            self._content, self.sesion, on_volver=self._mostrar_home,
            on_buscador=self._encabezado.configurar_buscador,
        )
        self.pantalla_actual.pack(fill="both", expand=True)

    def _mostrar_revisores(self):
        self._limpiar_contenido()
        self._sidebar.marcar_activo("revisores")
        self._encabezado.configurar_titulo("Revisores por color")
        self._encabezado.configurar_buscador(None)
        self.pantalla_actual = RevisoresScreen(self._content, self.sesion, on_volver=self._mostrar_home)
        self.pantalla_actual.pack(fill="both", expand=True)

    def _mostrar_version(self):
        self._limpiar_contenido()
        self._sidebar.marcar_activo("version")
        self._encabezado.configurar_titulo("Versión de la app")
        self._encabezado.configurar_buscador(None)
        self.pantalla_actual = VersionScreen(self._content, self.sesion, on_volver=self._mostrar_home)
        self.pantalla_actual.pack(fill="both", expand=True)

    def _mostrar_password(self):
        self._limpiar_contenido()
        self._sidebar.marcar_activo("password")
        self._encabezado.configurar_titulo("Cambiar contraseña")
        self._encabezado.configurar_buscador(None)
        self.pantalla_actual = PasswordScreen(self._content, self.sesion, on_volver=self._mostrar_home)
        self.pantalla_actual.pack(fill="both", expand=True)
