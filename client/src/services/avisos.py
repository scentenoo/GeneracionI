"""Formato del aviso de devoluciones: una planeación o informe que un
revisor mandó a corregir. Lo usan tanto el aviso al entrar (app.py) como
la campanita del menú (home_screen.py), para no tener el mismo texto
armado en dos lugares distintos."""

from __future__ import annotations


def texto_devoluciones(devoluciones: list[dict]) -> str:
    """Arma el texto de "esto te devolvieron". Vacío si no hay nada."""
    if not devoluciones:
        return ""

    lineas = []
    for d in devoluciones:
        por = d.get("por") or "el revisor"
        motivo = d.get("motivo") or "(sin motivo)"
        if d.get("tipo") == "planeacion":
            cabeza = f"• Planeación de {d.get('curso') or 'tu curso'} ({d.get('fecha', '')})"
        else:
            cabeza = f"• Informe del mes {d.get('mes', '')}"
        lineas.append(f"{cabeza}\n   Devuelto por {por}: {motivo}")

    plural = "cosas" if len(devoluciones) > 1 else "cosa"
    return (
        f"Un revisor te devolvió {len(devoluciones)} {plural} para corregir y volver a "
        "enviar:\n\n" + "\n\n".join(lineas) +
        "\n\nCorregilas y guardá de nuevo: vuelven a quedar pendientes de revisión."
    )
