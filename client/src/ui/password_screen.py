"""Mi cuenta: el propio perfil (de solo lectura — lo carga dirección desde
"Usuarios") y cambiar la propia contraseña (spec sección 3: Samir asigna
la inicial, cada usuario la cambia después).

El perfil se agregó porque antes esos datos (cédula, teléfono, formación)
solo se veían desde "Usuarios", una pantalla de directivo/administrador —
un docente no tenía forma de chequear si ya se los habían cargado."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

import api_client
from ui import tema
from ui.tareas import en_segundo_plano
from ui.widgets import campo_label

ANCHO_PANEL_DERECHO = 280

_CAMPOS_PERFIL = [
    ("cedula", "Cédula"),
    ("telefono", "Teléfono"),
    ("formacion", "Formación"),
    ("numero_cuenta", "Número de cuenta"),
    ("tipo_cuenta", "Tipo de cuenta"),
    ("entidad_bancaria", "Entidad bancaria"),
]


class PasswordScreen(ctk.CTkScrollableFrame):
    # CTkScrollableFrame y no CTkFrame: con la tarjeta "Mi perfil" nueva de
    # arriba, el contenido ya no entra siempre en el alto de la ventana
    # (sobre todo restaurada, no maximizada) — sin scroll, "Contraseña
    # nueva" y todo lo de abajo del formulario quedaba fuera de la
    # pantalla y sin ninguna forma de llegar ahí.
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None]):
        super().__init__(master, fg_color="transparent")
        self.sesion = sesion

        envoltorio = ctk.CTkFrame(self, fg_color="transparent")
        envoltorio.pack(expand=True, pady=(30, 0))

        ctk.CTkButton(
            envoltorio, text="← Volver", width=90, fg_color="transparent", border_width=1,
            text_color=tema.TEXTO_OSCURO, hover_color=tema.FONDO_TARJETA, command=on_volver,
        ).pack(anchor="w", pady=(0, 14))

        self._construir_perfil(envoltorio)

        cuerpo = ctk.CTkFrame(envoltorio, fg_color="transparent")
        cuerpo.pack()

        tarjeta = ctk.CTkFrame(
            cuerpo, fg_color=tema.FONDO_TARJETA, corner_radius=18,
            border_width=1, border_color=tema.BORDE_TARJETA, width=560,
        )
        tarjeta.pack(side="left", fill="y")
        contenido = ctk.CTkFrame(tarjeta, fg_color="transparent")
        contenido.pack(padx=36, pady=34)

        ctk.CTkLabel(
            contenido, text="Cambiar contraseña", font=tema.fuente(20, "bold"), anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            contenido, text="La nueva contraseña se usa la próxima vez que entre a la app.",
            font=tema.fuente(12), text_color=tema.TEXTO_MUTED, anchor="w",
        ).pack(fill="x", pady=(4, 0))
        ctk.CTkFrame(contenido, fg_color=tema.DIVISOR, height=1).pack(fill="x", pady=(22, 22))

        self.actual_entry = self._campo(contenido, "Contraseña actual")
        self.nueva_entry = self._campo(contenido, "Contraseña nueva")
        self.confirmar_entry = self._campo(contenido, "Repetir contraseña nueva")

        self.error_label = ctk.CTkLabel(contenido, text="", text_color=tema.ROJO, wraplength=420, justify="left")
        self.error_label.pack(fill="x", pady=(14, 0))

        self.boton = ctk.CTkButton(
            contenido, text="Cambiar", fg_color=tema.VERDE_OSCURO, hover_color=tema.VERDE_OSCURO_ACTIVO,
            height=42, command=self._cambiar,
        )
        self.boton.pack(fill="x", pady=(20, 0))

        panel = ctk.CTkFrame(
            cuerpo, fg_color=tema.FONDO_TARJETA, corner_radius=18,
            border_width=1, border_color=tema.BORDE_TARJETA, width=ANCHO_PANEL_DERECHO,
        )
        panel.pack(side="left", fill="y", padx=(18, 0))
        panel.pack_propagate(False)
        contenido_panel = ctk.CTkFrame(panel, fg_color="transparent")
        contenido_panel.pack(fill="both", expand=True, padx=22, pady=22)

        ctk.CTkLabel(
            contenido_panel, text="Lo que pide la app", font=tema.fuente(14, "bold"), anchor="w",
        ).pack(fill="x", pady=(0, 12))
        self._chequeos_contenedor = ctk.CTkFrame(contenido_panel, fg_color="transparent")
        self._chequeos_contenedor.pack(fill="x")
        ctk.CTkLabel(
            contenido_panel,
            text="Eso es todo lo que valida la app. Si no coinciden avisa "
                 "«Las contraseñas nuevas no coinciden».",
            font=tema.fuente(11), text_color=tema.TEXTO_MUTED, anchor="w", justify="left",
            wraplength=ANCHO_PANEL_DERECHO - 44,
        ).pack(fill="x", pady=(14, 0))

        self._pintar_chequeos(False, False)

    def _construir_perfil(self, padre):
        tarjeta = ctk.CTkFrame(
            padre, fg_color=tema.FONDO_TARJETA, corner_radius=18,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        tarjeta.pack(fill="x", pady=(0, 18))
        contenido = ctk.CTkFrame(tarjeta, fg_color="transparent")
        contenido.pack(fill="x", padx=36, pady=28)

        ctk.CTkLabel(
            contenido, text="Mi perfil", font=tema.fuente(18, "bold"), anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            contenido,
            text="Esto lo carga dirección desde «Usuarios» — si algo falta o está mal, avisen.",
            font=tema.fuente(12), text_color=tema.TEXTO_MUTED, anchor="w",
        ).pack(fill="x", pady=(4, 0))

        grilla = ctk.CTkFrame(contenido, fg_color="transparent")
        grilla.pack(fill="x", pady=(18, 0))
        grilla.grid_columnconfigure((0, 1, 2), weight=1, uniform="perfil")

        _ROL_ETIQUETA = {"docente": "Docente", "directivo": "Directivo", "ambos": "Docente y directivo"}

        self._valores_perfil: dict[str, ctk.CTkLabel] = {}
        campos = [("nombre", "Nombre"), ("rol", "Rol")] + _CAMPOS_PERFIL
        for i, (clave, etiqueta) in enumerate(campos):
            celda = ctk.CTkFrame(grilla, fg_color="transparent")
            celda.grid(row=i // 3, column=i % 3, sticky="w", padx=(0, 20), pady=(0, 14))
            ctk.CTkLabel(
                celda, text=etiqueta.upper(), font=tema.fuente(10, "bold"), text_color=tema.TEXTO_MUTED,
                anchor="w",
            ).pack(fill="x")
            valor = ctk.CTkLabel(
                celda, text="Cargando...", font=tema.fuente(13), text_color=tema.TEXTO_OSCURO, anchor="w",
                wraplength=200, justify="left",
            )
            valor.pack(fill="x")
            self._valores_perfil[clave] = valor

        # Nombre y rol ya los trae la sesión — no hace falta esperar al
        # backend para mostrar esos dos.
        self._valores_perfil["nombre"].configure(text=self.sesion.get("nombre") or "—")
        rol = self.sesion.get("rol", "")
        self._valores_perfil["rol"].configure(text=_ROL_ETIQUETA.get(rol, rol or "—"))

        self._cargar_perfil()

    def _cargar_perfil(self):
        en_segundo_plano(
            self,
            lambda: api_client.obtener_mi_perfil(self.sesion["token"]),
            self._al_cargar_perfil,
            self._al_fallar_perfil,
            mostrar_overlay=False,
        )

    def _al_cargar_perfil(self, perfil: dict):
        for clave, _etiqueta in _CAMPOS_PERFIL:
            label = self._valores_perfil[clave]
            valor = str(perfil.get(clave) or "").strip()
            if valor:
                label.configure(text=valor, text_color=tema.TEXTO_OSCURO)
            else:
                label.configure(text="Sin cargar", text_color=tema.TEXTO_MUTED)

    def _al_fallar_perfil(self, _exc):
        # Un extra que no debería tapar la pantalla si el backend falla:
        # deja de decir "Cargando..." para siempre en vez de mostrar un
        # error que no aporta nada acá.
        for clave, _etiqueta in _CAMPOS_PERFIL:
            self._valores_perfil[clave].configure(text="—", text_color=tema.TEXTO_MUTED)

    def _campo(self, padre, etiqueta: str) -> ctk.CTkEntry:
        campo_label(padre, etiqueta).pack(fill="x", pady=(0, 4))
        entry = ctk.CTkEntry(padre, show="*", width=420, height=38)
        entry.pack(fill="x", pady=(0, 16))
        entry.bind("<KeyRelease>", lambda _e: self._actualizar_chequeos())
        return entry

    def _pintar_chequeos(self, seis_caracteres: bool, coinciden: bool):
        for w in self._chequeos_contenedor.winfo_children():
            w.destroy()
        for texto, ok in (
            ("Al menos 6 caracteres", seis_caracteres),
            ("Las dos nuevas coinciden", coinciden),
        ):
            fila = ctk.CTkFrame(self._chequeos_contenedor, fg_color="transparent")
            fila.pack(fill="x", pady=3)
            texto_color = tema.VERDE_CHIP_TEXTO if ok else tema.TEXTO_MUTED
            fondo_color = tema.VERDE_CHIP_BG if ok else tema.FONDO_CONTENIDO
            insignia = ctk.CTkFrame(fila, width=18, height=18, corner_radius=9, fg_color=fondo_color)
            insignia.pack(side="left", padx=(0, 10))
            insignia.pack_propagate(False)
            ctk.CTkLabel(
                insignia, text="✓" if ok else "", text_color=texto_color, font=tema.fuente(11, "bold"),
            ).place(relx=0.5, rely=0.5, anchor="center")
            ctk.CTkLabel(
                fila, text=texto, font=tema.fuente(12), text_color=tema.TEXTO_OSCURO, anchor="w",
            ).pack(side="left")

    def _actualizar_chequeos(self):
        nueva = self.nueva_entry.get()
        self._pintar_chequeos(
            len(nueva) >= 6, bool(nueva) and nueva == self.confirmar_entry.get(),
        )

    def _cambiar(self):
        if self.nueva_entry.get() != self.confirmar_entry.get():
            self.error_label.configure(text="Las contraseñas nuevas no coinciden", text_color=tema.ROJO)
            return
        if len(self.nueva_entry.get()) < 6:
            self.error_label.configure(
                text="La contraseña nueva necesita al menos 6 caracteres", text_color=tema.ROJO
            )
            return

        # En segundo plano: en los equipos lentos de la sede, hacerlo en el
        # hilo de la interfaz congelaba la ventana ~3s sin ningún aviso.
        self.boton.configure(state="disabled", text="Cambiando...")
        self.error_label.configure(text="", text_color=tema.TEXTO_MUTED)

        actual, nueva = self.actual_entry.get(), self.nueva_entry.get()

        def listo(_r):
            self.boton.configure(state="normal", text="Cambiar")
            self.error_label.configure(text="Contraseña cambiada ✓", text_color=tema.VERDE)
            self.actual_entry.delete(0, "end")
            self.nueva_entry.delete(0, "end")
            self.confirmar_entry.delete(0, "end")
            self._pintar_chequeos(False, False)

        def fallo(exc):
            self.boton.configure(state="normal", text="Cambiar")
            self.error_label.configure(text=str(exc), text_color=tema.ROJO)

        en_segundo_plano(
            self,
            lambda: api_client.cambiar_password(self.sesion["token"], actual, nueva),
            listo,
            fallo,
        )
