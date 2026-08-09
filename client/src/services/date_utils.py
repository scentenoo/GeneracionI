"""La fecha se manda al backend en ISO ('YYYY-MM-DD'), pero Google Sheets
autoconvierte esas celdas a su propio tipo Date — al releerlas, Apps Script
las serializa como datetime ISO completo ('2026-08-07T05:00:00.000Z'), no
como el string simple que mandamos. `_solo_fecha` normaliza cualquiera de
los dos formatos antes de parsear, para no repetir ese manejo en cada
lugar que toca una fecha."""

from __future__ import annotations

from datetime import date, datetime

_MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def hoy_iso() -> str:
    return date.today().isoformat()


def _solo_fecha(fecha: str) -> date:
    return datetime.strptime(fecha[:10], "%Y-%m-%d").date()


def a_fecha_larga(fecha: str) -> str:
    """'2026-08-05' o '2026-08-05T05:00:00.000Z' -> '5 de Agosto de 2026'"""
    d = _solo_fecha(fecha)
    return f"{d.day} de {_MESES_ES[d.month - 1].capitalize()} de {d.year}"


def a_fecha_corta(fecha: str) -> str:
    """'2026-08-05' o '2026-08-05T05:00:00.000Z' -> '05/08/2026'"""
    return _solo_fecha(fecha).strftime("%d/%m/%Y")


def hace_cuanto(fecha: str | None) -> tuple[str, int | None]:
    """Devuelve ('entró hoy', 0) y similares, más los días transcurridos.

    Los días vuelven aparte para que quien llama decida qué es "hace
    mucho" — acá no sabemos si eso son 7 días o 30. `None` significa que
    la fecha viene vacía: nunca pasó.
    """
    if not fecha:
        return "nunca entró", None

    try:
        dias = (date.today() - _solo_fecha(str(fecha))).days
    except ValueError:
        return str(fecha), None

    if dias <= 0:
        return "entró hoy", 0
    if dias == 1:
        return "entró ayer", 1
    if dias < 30:
        return f"entró hace {dias} días", dias
    return f"entró el {a_fecha_corta(str(fecha))}", dias
