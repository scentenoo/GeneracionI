"""Parches a bugs conocidos de customtkinter (6.0.0) que no dependen de
nuestro código, solo de la versión de Tk instalada. Se aplican una sola vez
al arrancar, antes de crear cualquier ventana."""

from __future__ import annotations


def aplicar():
    _parchar_scroll_sobre_desplegables()


def _parchar_scroll_sobre_desplegables():
    """CTkScrollableFrame asume que event.widget siempre es un widget de
    Tkinter y le busca .master recursivamente para saber si el scroll caía
    adentro suyo. En Linux, cuando el mouse desplaza estando sobre el
    desplegable de un CTkOptionMenu/CTkComboBox, Tk a veces entrega el
    nombre del widget (un string) en vez del objeto — .master de un string
    no existe, y sin este parche eso tira un AttributeError por consola en
    cada scroll sobre un desplegable. No rompe nada, pero llena la consola
    de basura; acá se lo trata como "no, este scroll no es válido" en vez
    de reventar."""
    from customtkinter.windows.widgets.ctk_scrollable_frame import CTkScrollableFrame

    original = CTkScrollableFrame._check_if_valid_scroll

    def _seguro(self, widget):
        try:
            return original(self, widget)
        except AttributeError:
            return False

    CTkScrollableFrame._check_if_valid_scroll = _seguro
