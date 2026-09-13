"""Editar el perfil de un usuario existente + subir su firma — rol
directivo únicamente. Un docente no edita sus propios datos, se los pide
al equipo directivo (así lo pidió Samir).

También vive acá la gestión del administrador único y el borrado de
usuarios: un directivo puede eliminar docentes; eliminar a otro
directivo/ambos, o transferir el cargo de administrador, requiere ser el
administrador actual.
"""

from __future__ import annotations

from tkinter import filedialog, messagebox
from typing import Callable

import customtkinter as ctk

import api_client
from ui import tema
from ui.tareas import cache, en_segundo_plano
from services import image_utils
from ui.usuario_form_fields import construir_campos_perfil, leer_campos_perfil
from ui.widgets import avatar_iniciales, campo_label, pildora

ROLES = [("docente", "Docente"), ("directivo", "Directivo"), ("ambos", "Ambos")]


class EditarUsuarioScreen(ctk.CTkScrollableFrame):
    def __init__(self, master, sesion: dict, on_volver: Callable[[], None] | None = None):
        # Sin `on_volver` va montada como pestaña de UsuariosScreen, que ya
        # tiene su propio Volver: dos seguidos confunden.
        super().__init__(
            master, label_text="" if on_volver is None else "Editar usuario", fg_color="transparent",
        )
        self.sesion = sesion
        self.on_volver = on_volver
        self._usuarios_por_nombre: dict[str, dict] = {}

        cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True)
        cuerpo.grid_columnconfigure(0, weight=1)
        cuerpo.grid_columnconfigure(1, weight=0, minsize=320)
        cuerpo.grid_rowconfigure(0, weight=1)

        # --- columna izquierda: el formulario -----------------------------
        tarjeta = ctk.CTkFrame(
            cuerpo, fg_color=tema.FONDO_TARJETA, corner_radius=16,
            border_width=1, border_color=tema.BORDE_TARJETA,
        )
        tarjeta.grid(row=0, column=0, sticky="nsew", padx=(0, 22))
        self.columna_form = ctk.CTkFrame(tarjeta, fg_color="transparent")
        self.columna_form.pack(fill="both", expand=True, padx=26, pady=24)

        if on_volver is not None:
            ctk.CTkButton(
                self.columna_form, text="← Volver", width=90, fg_color="transparent", border_width=1,
                text_color=tema.TEXTO_OSCURO, command=on_volver,
            ).pack(anchor="w", pady=(0, 14))

        fila_selector = ctk.CTkFrame(self.columna_form, fg_color="transparent")
        fila_selector.pack(fill="x")
        self.avatar_contenedor = ctk.CTkFrame(fila_selector, fg_color="transparent")
        self.avatar_contenedor.pack(side="left")
        self.usuario_menu = ctk.CTkOptionMenu(
            fila_selector, values=["(cargando...)"], command=lambda _v: self._cargar(),
        )
        self.usuario_menu.pack(side="left", fill="x", expand=True, padx=(14, 10))
        self.badges_contenedor = ctk.CTkFrame(fila_selector, fg_color="transparent")
        self.badges_contenedor.pack(side="left")

        ctk.CTkFrame(self.columna_form, fg_color=tema.DIVISOR, height=1).pack(fill="x", pady=18)

        grid = ctk.CTkFrame(self.columna_form, fg_color="transparent")
        grid.pack(fill="x")
        grid.grid_columnconfigure((0, 1), weight=1, uniform="editar")

        col_nombre = self._celda(grid, 0, 0, columnspan=2)
        campo_label(col_nombre, "Nombre completo").pack(fill="x")
        self.nombre_entry = ctk.CTkEntry(col_nombre)
        self.nombre_entry.pack(fill="x", pady=(4, 0))

        col_rol = self._celda(grid, 1, 0)
        campo_label(col_rol, "Rol").pack(fill="x")
        self.rol_selector = ctk.CTkSegmentedButton(
            col_rol, values=[etiqueta for _clave, etiqueta in ROLES],
            selected_color=tema.VERDE, selected_hover_color=tema.VERDE_HOVER,
            unselected_color=tema.BLANCO, text_color=tema.TEXTO_OSCURO,
        )
        self.rol_selector.pack(fill="x", pady=(4, 0))

        self.campos_perfil = {}
        etiquetas_perfil = dict(
            [("cedula", "Cédula"), ("telefono", "Teléfono"),
             ("valor_hora_docente", "Valor hora docente"), ("valor_hora_directivo", "Valor hora directivo"),
             ("numero_cuenta", "Número de cuenta"), ("tipo_cuenta", "Tipo de cuenta"),
             ("entidad_bancaria", "Entidad bancaria"),
             # Título/profesión: lo pide el certificado de pago mensual
             # (columna FORMACIÓN) — va de último y a todo el ancho porque
             # suele ser más largo que el resto ("Licenciatura en...").
             ("formacion", "Formación (profesión/título)")]
        )
        posiciones = [(1, 1), (2, 0), (2, 1), (3, 0), (3, 1), (4, 0), (4, 1)]
        for (fila_idx, columna_idx), (clave, etiqueta) in zip(posiciones, list(etiquetas_perfil.items())[:-1]):
            celda = self._celda(grid, fila_idx, columna_idx)
            campo_label(celda, etiqueta).pack(fill="x")
            entry = ctk.CTkEntry(celda)
            entry.pack(fill="x", pady=(4, 0))
            self.campos_perfil[clave] = entry
        ultima_clave, ultima_etiqueta = list(etiquetas_perfil.items())[-1]
        celda_ultima = self._celda(grid, 5, 0, columnspan=2)
        campo_label(celda_ultima, ultima_etiqueta).pack(fill="x")
        entry_ultima = ctk.CTkEntry(celda_ultima)
        entry_ultima.pack(fill="x", pady=(4, 0))
        self.campos_perfil[ultima_clave] = entry_ultima

        self.error_label = ctk.CTkLabel(
            self.columna_form, text="", text_color=tema.ROJO, wraplength=560, justify="left",
        )
        self.error_label.pack(fill="x", pady=(18, 0))

        botones = ctk.CTkFrame(self.columna_form, fg_color="transparent")
        botones.pack(anchor="e", pady=(10, 0))
        ctk.CTkButton(
            botones, text="Descartar", fg_color="transparent", border_width=1,
            text_color=tema.TEXTO_OSCURO, command=lambda: self._cargar(),
        ).pack(side="left", padx=(0, 8))
        self.guardar_boton = ctk.CTkButton(
            botones, text="Guardar cambios", fg_color=tema.VERDE_OSCURO,
            hover_color=tema.VERDE_OSCURO_ACTIVO, command=self._guardar,
        )
        self.guardar_boton.pack(side="left")

        # --- columna derecha: firma, administrador, acceso -----------------
        panel = ctk.CTkFrame(
            cuerpo, fg_color=tema.FONDO_TARJETA, corner_radius=16,
            border_width=1, border_color=tema.BORDE_TARJETA, width=320,
        )
        panel.grid(row=0, column=1, sticky="nsew")
        self.columna_panel = ctk.CTkFrame(panel, fg_color="transparent")
        self.columna_panel.pack(fill="both", expand=True, padx=22, pady=22)

        ctk.CTkLabel(
            self.columna_panel, text="Firma", font=tema.fuente(15, "bold"), anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            self.columna_panel, text="Se estampa en los informes mensuales y en la cuenta de cobro.",
            font=tema.fuente(11), text_color=tema.TEXTO_MUTED, anchor="w", justify="left", wraplength=270,
        ).pack(fill="x", pady=(4, 14))

        dropzone = ctk.CTkFrame(
            self.columna_panel, fg_color=tema.FONDO_CONTENIDO, corner_radius=14,
            border_width=1.5, border_color=tema.BORDE_TARJETA,
        )
        dropzone.pack(fill="x")
        ctk.CTkFrame(
            dropzone, width=120, height=48, fg_color=tema.BORDE_TARJETA, corner_radius=8,
        ).pack(pady=(22, 12))
        self.firma_label = ctk.CTkLabel(dropzone, text="", font=tema.fuente(12, "bold"), text_color=tema.AMBAR)
        self.firma_label.pack()
        ctk.CTkButton(
            dropzone, text="Subir firma...", fg_color=tema.VERDE, hover_color=tema.VERDE_HOVER,
            command=self._subir_firma,
        ).pack(pady=(14, 22))

        ctk.CTkFrame(self.columna_panel, fg_color=tema.DIVISOR, height=1).pack(fill="x", pady=18)
        campo_label(self.columna_panel, "Administrador").pack(fill="x")
        self.admin_label = ctk.CTkLabel(
            self.columna_panel, text="", text_color=tema.TEXTO_MUTED, font=tema.fuente(12),
            anchor="w", justify="left", wraplength=270,
        )
        self.admin_label.pack(fill="x", pady=(8, 0))
        self.admin_boton = ctk.CTkButton(
            self.columna_panel, text="", fg_color="transparent", border_width=1,
            text_color=tema.TEXTO_OSCURO, hover_color=tema.AMBAR_CHIP_BG, command=self._accion_admin,
        )
        self.admin_boton.pack(fill="x", pady=(10, 0))

        ctk.CTkFrame(self.columna_panel, fg_color=tema.DIVISOR, height=1).pack(fill="x", pady=18)
        campo_label(self.columna_panel, "Acceso").pack(fill="x", pady=(0, 10))
        ctk.CTkButton(
            self.columna_panel, text="Restablecer contraseña", fg_color="transparent", border_width=1,
            text_color=tema.TEXTO_OSCURO, command=self._restablecer_password,
        ).pack(fill="x")
        self.eliminar_boton = ctk.CTkButton(
            self.columna_panel, text="Eliminar este usuario", fg_color=tema.ROJO, hover_color=tema.ROJO_HOVER,
            command=self._eliminar,
        )
        self.eliminar_boton.pack(fill="x", pady=(9, 0))
        ctk.CTkLabel(
            self.columna_panel,
            text="Un directivo elimina docentes; para eliminar a otro directivo hace falta ser el administrador.",
            font=tema.fuente(10), text_color=tema.TEXTO_MUTED, anchor="w", justify="left", wraplength=270,
        ).pack(fill="x", pady=(8, 0))

        self._cargar_usuarios()

    def _celda(self, grid: ctk.CTkFrame, fila: int, columna: int, columnspan: int = 1) -> ctk.CTkFrame:
        celda = ctk.CTkFrame(grid, fg_color="transparent")
        celda.grid(row=fila, column=columna, columnspan=columnspan, sticky="ew", padx=(0, 0), pady=(0, 14))
        return celda

    def _rol_clave(self) -> str:
        etiqueta_elegida = self.rol_selector.get()
        for clave, etiqueta in ROLES:
            if etiqueta == etiqueta_elegida:
                return clave
        return "docente"

    def _rol_etiqueta(self, clave: str) -> str:
        for c, etiqueta in ROLES:
            if c == clave:
                return etiqueta
        return "Docente"

    def _cargar_usuarios(self, seleccionar: str | None = None):
        """La lista sale del caché, que ya viene precargado desde el login,
        así que normalmente no cuesta ningún viaje al backend. Igual va en
        segundo plano por si toca ir a buscarla."""

        def listo(usuarios):
            self._usuarios_por_nombre = {u["nombre"]: u for u in usuarios}
            self._hay_admin = any(u.get("es_admin") for u in usuarios)
            nombres = list(self._usuarios_por_nombre) or ["(sin usuarios)"]
            self.usuario_menu.configure(values=nombres)
            self.usuario_menu.set(seleccionar if seleccionar in nombres else nombres[0])
            self._cargar()

        en_segundo_plano(
            self,
            lambda: cache.usuarios(self.sesion["token"]),
            listo,
            lambda exc: self.error_label.configure(text=str(exc), text_color=tema.ROJO),
        )

    def seleccionar(self, nombre: str):
        """Deja abierto ese usuario. La usa la lista para saltar acá."""
        if nombre in self._usuarios_por_nombre:
            self.usuario_menu.set(nombre)
            self._cargar()
        else:
            self._cargar_usuarios(seleccionar=nombre)

    def _usuario_actual(self) -> dict | None:
        return self._usuarios_por_nombre.get(self.usuario_menu.get())

    def _set_entry(self, entry: ctk.CTkEntry, valor):
        entry.delete(0, "end")
        entry.insert(0, "" if valor is None else str(valor))

    def _cargar(self):
        usuario = self._usuario_actual()
        if not usuario:
            return

        for w in self.avatar_contenedor.winfo_children():
            w.destroy()
        avatar_iniciales(self.avatar_contenedor, usuario.get("nombre", "?"), tamano=48).pack()

        for w in self.badges_contenedor.winfo_children():
            w.destroy()
        rol = usuario.get("rol", "")
        if rol:
            pildora(self.badges_contenedor, rol, tema.TEXTO_MUTED, tema.FONDO_CONTENIDO).pack(side="left", padx=(0, 6))
        if usuario.get("es_admin"):
            pildora(self.badges_contenedor, "administrador", tema.AMBAR, tema.AMBAR_CHIP_BG).pack(side="left")

        self._set_entry(self.nombre_entry, usuario.get("nombre"))
        self.rol_selector.set(self._rol_etiqueta(usuario.get("rol", "docente")))
        for clave, entry in self.campos_perfil.items():
            self._set_entry(entry, usuario.get(clave))

        tiene_firma = bool(usuario.get("firma_drive_id"))
        self.firma_label.configure(
            text="Ya tiene firma cargada" if tiene_firma else "Todavía no tiene firma",
            text_color=tema.VERDE_CHIP_TEXTO if tiene_firma else tema.AMBAR,
        )

        self._actualizar_controles_admin(usuario)

    def _es_yo_mismo(self, usuario: dict) -> bool:
        return usuario["id"] == self.sesion["id"]

    def _actualizar_controles_admin(self, usuario: dict):
        yo_soy_admin = bool(self.sesion.get("es_admin"))

        if usuario.get("es_admin"):
            self.admin_label.configure(text=f"{usuario['nombre']} es el administrador actual.")
        elif not self._hay_admin:
            self.admin_label.configure(text="Todavía no hay ningún administrador asignado.")
        else:
            self.admin_label.configure(text="")

        if usuario.get("es_admin"):
            self.admin_boton.pack_forget()
        elif not self._hay_admin and not yo_soy_admin:
            # Bootstrap: solo tiene sentido que la propia sesión (directivo/ambos) se autoproclame.
            if self._es_yo_mismo(usuario):
                self.admin_boton.configure(text="Convertirme en administrador")
                self.admin_boton.pack(fill="x", pady=(10, 0))
            else:
                self.admin_boton.pack_forget()
        elif yo_soy_admin and not self._es_yo_mismo(usuario):
            self.admin_boton.configure(text=f"Transferirle el cargo a {usuario['nombre']}")
            self.admin_boton.pack(fill="x", pady=(10, 0))
        else:
            self.admin_boton.pack_forget()

        puede_eliminar = (
            not self._es_yo_mismo(usuario)
            and (yo_soy_admin or usuario.get("rol") == "docente")
        )
        if puede_eliminar:
            self.eliminar_boton.pack(fill="x", pady=(9, 0))
        else:
            self.eliminar_boton.pack_forget()

    def _accion_admin(self):
        usuario = self._usuario_actual()
        if not usuario:
            return

        me_autoproclamo = not self._hay_admin

        def trabajo():
            if me_autoproclamo:
                api_client.convertirme_administrador(self.sesion["token"])
            else:
                api_client.transferir_administrador(self.sesion["token"], usuario["id"])

        def listo(_r):
            self.admin_boton.configure(state="normal")
            if me_autoproclamo:
                self.sesion["es_admin"] = True
            self.error_label.configure(text="Listo ✓", text_color=tema.VERDE)
            self._cargar_usuarios()

        def fallo(exc):
            self.admin_boton.configure(state="normal")
            self.error_label.configure(text=str(exc), text_color=tema.ROJO)

        self.admin_boton.configure(state="disabled")
        en_segundo_plano(self, trabajo, listo, fallo)

    def _restablecer_password(self):
        usuario = self._usuario_actual()
        if not usuario:
            return

        dialogo = ctk.CTkInputDialog(
            title="Restablecer contraseña",
            text=f"Contraseña nueva para {usuario.get('nombre', '')}:",
        )
        nueva = dialogo.get_input()
        if not nueva:
            return

        self.error_label.configure(text="Restableciendo...", text_color=tema.TEXTO_MUTED)

        def listo(_r):
            self.error_label.configure(
                text=f"Listo. La contraseña de {usuario.get('nombre', '')} ahora es:  {nueva}\n"
                     "Pásesela y dígale que la cambie desde «Cambiar contraseña».",
                text_color=tema.VERDE,
            )

        en_segundo_plano(
            self,
            lambda: api_client.restablecer_password(self.sesion["token"], usuario["id"], nueva),
            listo,
            lambda exc: self.error_label.configure(text=str(exc), text_color=tema.ROJO),
        )

    def _eliminar(self):
        usuario = self._usuario_actual()
        if not usuario:
            return

        if not messagebox.askyesno(
            "Eliminar usuario", f"¿Seguro que quiere eliminar a {usuario['nombre']} ({usuario['usuario']})?"
        ):
            return

        def listo(_r):
            cache.invalidar("usuarios")
            self.eliminar_boton.configure(state="normal")
            self.error_label.configure(text="Usuario eliminado.", text_color=tema.VERDE)
            self._cargar_usuarios()

        def fallo(exc):
            self.eliminar_boton.configure(state="normal")
            self.error_label.configure(text=str(exc), text_color=tema.ROJO)

        self.eliminar_boton.configure(state="disabled")
        en_segundo_plano(
            self, lambda: api_client.eliminar_usuario(self.sesion["token"], usuario["id"]), listo, fallo,
        )

    def _subir_firma(self):
        usuario = self._usuario_actual()
        if not usuario:
            return

        ruta = filedialog.askopenfilename(
            title="Elija la imagen de la firma", filetypes=[("Imágenes", "*.jpg *.jpeg *.png")]
        )
        if not ruta:
            return

        def trabajo():
            # Comprimir la imagen también tarda, así que va al hilo — igual
            # que con las fotos de clase (ver services/image_utils.py).
            return api_client.subir_firma(
                self.sesion["token"], usuario["id"], image_utils.foto_a_payload(ruta)
            )

        def listo(_r):
            self.firma_label.configure(text="Firma actualizada ✓", text_color=tema.VERDE_CHIP_TEXTO)

        def fallo(exc):
            self.error_label.configure(text=str(exc), text_color=tema.ROJO)

        en_segundo_plano(self, trabajo, listo, fallo, bloquea_cierre=True)

    def _guardar(self):
        usuario = self._usuario_actual()
        if not usuario:
            self.error_label.configure(text="No hay usuario seleccionado.", text_color=tema.ROJO)
            return

        cambios = {
            "nombre": self.nombre_entry.get().strip(),
            "rol": self._rol_clave(),
            **leer_campos_perfil(self.campos_perfil),
        }

        def listo(resultado):
            cache.invalidar("usuarios")
            self.guardar_boton.configure(state="normal")
            self.error_label.configure(
                text=f"Guardado ({resultado['cambios']} campos actualizados) ✓", text_color=tema.VERDE
            )
            self._cargar_usuarios()

        def fallo(exc):
            self.guardar_boton.configure(state="normal")
            self.error_label.configure(text=str(exc), text_color=tema.ROJO)

        self.guardar_boton.configure(state="disabled")
        en_segundo_plano(
            self, lambda: api_client.editar_usuario(self.sesion["token"], usuario["id"], cambios), listo, fallo,
        )
