"""Carga los usuarios y cursos del programa desde la nómina.

La nómina tiene una fila por persona-y-curso, así que quien da dos cursos
aparece dos veces y quien además coordina, tres. El script agrupa por
persona, deduce el rol de las filas que tenga, y crea un curso por cada
fila de docencia.

Por defecto NO escribe nada: muestra lo que haría. Para aplicarlo de
verdad hay que pasar --aplicar, porque esto crea usuarios reales en la
Sheet de producción y no hay deshacer masivo.

    python scripts/cargar_nomina.py                    # ver qué haría
    python scripts/cargar_nomina.py --aplicar          # hacerlo

Las contraseñas se generan al azar y se escriben en un archivo aparte,
que está en .gitignore. Ese archivo es para repartir a mano y borrar
después: cada quien cambia la suya al entrar.

Lo que la nómina no trae (cédula, cuenta bancaria, núcleo, edades) queda
vacío y lo completa el equipo directivo desde la app.
"""

from __future__ import annotations

import argparse
import secrets
import string
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "client" / "src"))

import openpyxl  # noqa: E402

import api_client  # noqa: E402

NOMINA = RAIZ / "Estructura" / "PagosaCadaDocenteConHorayValorHora.xlsx"
CREDENCIALES = RAIZ / "credenciales_iniciales.txt"

# Las filas de cargo administrativo se reconocen por el nombre: en la
# nómina no hay una columna que lo diga.
PREFIJOS_ADMINISTRATIVOS = ("coordinaci", "gesti")


def sin_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


def nombre_de_usuario(nombre_completo: str, tomados: set[str]) -> str:
    """nombre.apellido en minúsculas y sin acentos, con sufijo si choca."""
    partes = sin_acentos(nombre_completo).lower().split()
    base = f"{partes[0]}.{partes[1]}" if len(partes) > 1 else partes[0]
    base = "".join(c for c in base if c.isalnum() or c == ".")

    candidato, n = base, 2
    while candidato in tomados:
        candidato, n = f"{base}{n}", n + 1
    tomados.add(candidato)
    return candidato


def contrasena_al_azar() -> str:
    # Sin caracteres que se confundan al dictarlos por teléfono (l/1, O/0).
    alfabeto = "".join(c for c in string.ascii_letters + string.digits if c not in "lI1O0")
    return "".join(secrets.choice(alfabeto) for _ in range(10))


def leer_nomina() -> dict[str, dict]:
    """Devuelve {nombre: {cursos: [...], cargos: [...], valor_hora_*}}."""
    hoja = openpyxl.load_workbook(NOMINA, data_only=True)["Nómina"]

    personas: dict[str, dict] = {}
    for fila in hoja.iter_rows(min_row=4, values_only=True):
        nombre, curso = fila[0], fila[1]
        if not nombre or not curso:
            continue
        nombre = str(nombre).strip()
        curso = str(curso).strip()
        if nombre.lower().startswith(("subtotal", "horas de", "total", "valor", "presupuest", "excedente")):
            continue

        horas_sede = fila[3] if isinstance(fila[3], (int, float)) else 0
        horas_itinerantes = fila[5] if isinstance(fila[5], (int, float)) else 0
        horas_admin = fila[6] if isinstance(fila[6], (int, float)) else 0
        valor_mensual = fila[8] if isinstance(fila[8], (int, float)) else 0

        persona = personas.setdefault(
            nombre, {"cursos": [], "cargos": [], "valor_hora_docente": 0, "valor_hora_directivo": 0}
        )

        es_administrativo = curso.lower().startswith(PREFIJOS_ADMINISTRATIVOS) or horas_admin > 0
        if es_administrativo:
            persona["cargos"].append(curso)
            if horas_admin and valor_mensual:
                persona["valor_hora_directivo"] = round(valor_mensual / horas_admin)
        else:
            persona["cursos"].append(curso)
            horas = (horas_sede or 0) + (horas_itinerantes or 0)
            if horas and valor_mensual:
                persona["valor_hora_docente"] = round(valor_mensual / horas)

    return personas


def rol_de(persona: dict) -> str:
    if persona["cursos"] and persona["cargos"]:
        return "ambos"
    return "directivo" if persona["cargos"] else "docente"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aplicar", action="store_true", help="escribir de verdad en la Sheet")
    parser.add_argument("--usuario", default="samir", help="con qué usuario administrador entrar")
    args = parser.parse_args()

    personas = leer_nomina()
    print(f"La nómina tiene {len(personas)} personas.\n")

    if not args.aplicar:
        for nombre, p in sorted(personas.items()):
            print(f"  {nombre}")
            print(f"      rol: {rol_de(p)}"
                  f"  ·  hora docente: {p['valor_hora_docente'] or '—'}"
                  f"  ·  hora directivo: {p['valor_hora_directivo'] or '—'}")
            for c in p["cursos"]:
                print(f"      curso:  {c}")
            for c in p["cargos"]:
                print(f"      cargo:  {c}  (no se crea como curso)")
        print("\nEsto fue una simulación. Para aplicarlo:")
        print("  python scripts/cargar_nomina.py --aplicar")
        return

    import getpass

    contrasena = getpass.getpass(f"Contraseña de {args.usuario}: ")
    sesion = api_client.login(args.usuario, contrasena)
    token = sesion["token"]
    print(f"Entré como {sesion['nombre']}.\n")

    existentes = {u["usuario"]: u for u in api_client.listar_usuarios(token)}
    por_nombre = {u["nombre"]: u for u in existentes.values()}
    cursos_existentes = {
        (c["docente_id"], c["nombre"]) for c in api_client.listar_todos_los_cursos(token)
    }
    tomados = set(existentes)

    credenciales = []
    for nombre, p in sorted(personas.items()):
        usuario = por_nombre.get(nombre)

        if usuario:
            print(f"  {nombre}: ya existe, no lo toco")
        else:
            clave = contrasena_al_azar()
            datos = {
                "nombre": nombre,
                "usuario": nombre_de_usuario(nombre, tomados),
                "password_inicial": clave,
                "rol": rol_de(p),
                "valor_hora_docente": p["valor_hora_docente"] or "",
                "valor_hora_directivo": p["valor_hora_directivo"] or "",
            }
            creado = api_client.crear_usuario(token, datos)
            usuario = {"id": creado["id"], "nombre": nombre}
            credenciales.append((nombre, datos["usuario"], clave, datos["rol"]))
            print(f"  {nombre}: creado como {datos['usuario']} ({datos['rol']})")

        for curso in p["cursos"]:
            if (usuario["id"], curso) in cursos_existentes:
                print(f"      curso «{curso}» ya estaba")
                continue
            api_client.crear_curso(token, {"docente_id": usuario["id"], "nombre": curso})
            print(f"      curso «{curso}» creado")

    if credenciales:
        with CREDENCIALES.open("w", encoding="utf-8") as f:
            f.write("Contraseñas iniciales — repartir a mano y borrar este archivo.\n")
            f.write("Cada quien la cambia al entrar, desde Cambiar contraseña.\n\n")
            for nombre, usuario, clave, rol in credenciales:
                f.write(f"{nombre}\n  usuario: {usuario}\n  clave:   {clave}\n  rol:     {rol}\n\n")
        print(f"\nContraseñas escritas en {CREDENCIALES}")
        print("Repartilas y borrá el archivo. No está en git.")

    print("\nFalta completar a mano, desde la app: cédula, cuenta bancaria,")
    print("núcleo y rango de edades de cada curso. La nómina no los trae.")


if __name__ == "__main__":
    main()
