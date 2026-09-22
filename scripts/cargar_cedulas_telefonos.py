"""Completa cédula, teléfono y formación de los docentes que ya existen en
la Sheet, con los datos que trae el certificado de pago real de julio 2026
que pasó el equipo directivo (18 instructores, con esas tres columnas).

Por defecto NO escribe nada: se conecta, compara contra la Sheet y muestra
qué haría. Para aplicarlo de verdad hay que pasar --aplicar — esto escribe
en la Sheet de producción y no hay deshacer masivo.

    python scripts/cargar_cedulas_telefonos.py             # ver qué haría
    python scripts/cargar_cedulas_telefonos.py --aplicar   # hacerlo

Solo completa lo que esté VACÍO en la Sheet: si un docente ya tiene cédula
cargada (aunque sea distinta a la del certificado, por ejemplo si se
corrigió después), no la toca — ante la duda, gana lo que ya está en la
Sheet, no el papel viejo.

Los nombres del certificado no siempre coinciden tal cual con el nombre
en la Sheet (ahí a veces está acortado, ej. "Samir Alejandro Centeno
Torrado" vs "Alejandro Torrado", o en otro orden, ej. "Sara Zapata
Rodríguez" vs "Sara Rodríguez Zapata"). Por eso el emparejamiento no es
por texto exacto: es por conjunto de palabras, uno adentro del otro. Si
hay más de un candidato para el mismo nombre, o ninguno, esa fila queda
"sin resolver" y se lista al final para completarla a mano — no adivina.
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "client" / "src"))

import api_client  # noqa: E402

# Del certificado de pago real de julio 2026 (docencia): instructor,
# cédula, teléfono, formación. Es la única fuente que trae estos tres
# datos juntos por persona — no vive en ningún lado más del repo.
DATOS_CERTIFICADO = [
    ("Valeria Posada posada", "1036310177", "310 3665460", "Ingeniería forestal e ingeniería de alimentos"),
    ("Samir Alejandro Centeno Torrado", "1127351183", "311 8758761", "Estadística"),
    ("Mariangel Avendaño Lopez", "1033487266", "314 3083586", "Ingeniería Ambiental"),
    ("Simón Avendaño Lopez", "1020432636", "323 3407383", "Ingeniería Mecatrónica"),
    ("Julieta Monsalve Londoño", "1044501425", "314 8420872", "Ingeniería Biomédica"),
    ("Laura Nataly Gutiérrez Medina", "1040976226", "304 5207467", "Licenciatura en ciencias naturales"),
    ("Laura Tatiana Arango Arango", "1193521292", "319 5994305", "Ingeniería mecánica"),
    ("Sara Zapata Rodríguez", "1040976444", "311 6374857", "Licenciatura en educación infantil"),
    ("Manuela otalvaro muñóz", "1038869228", "321 5378253", "Licenciatura en Literatura y lengua castellana"),
    ("Paula Alejandra Sabogal Jiménez", "1023874514", "301 1101307", "Administración - Inglés 4 Udea"),
    ("Daniel Agudelo Ocampo", "1044501624", "319 2062582", "Ing en sistemas - Inglés 5 TdeA"),
    ("Sarah Pérez Zuluaga", "1025891530", "313 5037680", "Artes escénicas - Inglés B2"),
    ("Juan José Zapata López", "1035974295", "301 1820583", "Licenciatura en lenguas extranjeras (ing y francés)"),
    ("Lisbeth Mazo García", "1040976388", "323 4824290", "Diseño Gráfico"),
    ("Laura Cadavid Sosa", "1027801457", "319 3680425", "Licenciatura en Literatura y lengua castellana"),
    ("Wendy lorena Valle Londoño", "1000442468", "312 6847271", "Licenciatura en educación infantil"),
    ("Sofía Vélez Guiral", "1020302922", "310 8438035", "Psicología"),
]


def sin_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


def palabras(nombre: str) -> set[str]:
    return set(sin_acentos(str(nombre or "")).lower().split())


def buscar_usuario(nombre_certificado: str, usuarios: list[dict]):
    """Devuelve (usuario, motivo) — 'igual' (mismo texto), 'parecido' (mismo
    conjunto de palabras, orden distinto), 'contenido' (uno es subconjunto
    del otro, ej. nombre acortado en la Sheet) — o (None, 'ambiguo'/'sin
    coincidencia') si no hay una única respuesta clara."""
    objetivo = palabras(nombre_certificado)

    exactos = [u for u in usuarios if palabras(u["nombre"]) == objetivo]
    if len(exactos) == 1:
        return exactos[0], "igual"
    if len(exactos) > 1:
        return None, "ambiguo"

    contenidos = [
        u for u in usuarios
        if palabras(u["nombre"]) and (palabras(u["nombre"]) <= objetivo or objetivo <= palabras(u["nombre"]))
    ]
    if len(contenidos) == 1:
        return contenidos[0], "contenido"
    if len(contenidos) > 1:
        return None, "ambiguo"

    return None, "sin coincidencia"


def planificar(usuarios: list[dict]) -> list[dict]:
    plan = []
    for nombre, cedula, telefono, formacion in DATOS_CERTIFICADO:
        usuario, motivo = buscar_usuario(nombre, usuarios)
        cambios = {}
        if usuario:
            if not str(usuario.get("cedula") or "").strip():
                cambios["cedula"] = cedula
            if not str(usuario.get("telefono") or "").strip():
                cambios["telefono"] = telefono
            if not str(usuario.get("formacion") or "").strip():
                cambios["formacion"] = formacion
        plan.append({
            "nombre_certificado": nombre, "usuario": usuario, "motivo": motivo, "cambios": cambios,
        })
    return plan


def imprimir_plan(plan: list[dict]):
    resueltos = [i for i in plan if i["usuario"]]
    sin_resolver = [i for i in plan if not i["usuario"]]

    for item in resueltos:
        u = item["usuario"]
        etiqueta = "" if item["motivo"] == "igual" else f"  ({item['motivo']}: «{item['nombre_certificado']}»)"
        if item["cambios"]:
            campos = ", ".join(f"{k}={v!r}" for k, v in item["cambios"].items())
            print(f"  {u['nombre']}{etiqueta}: completa {campos}")
        else:
            print(f"  {u['nombre']}{etiqueta}: ya tiene todo cargado, no se toca")

    if sin_resolver:
        print(f"\n{len(sin_resolver)} sin resolver — revisar a mano en «Usuarios»:")
        for item in sin_resolver:
            print(f"  · «{item['nombre_certificado']}»: {item['motivo']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aplicar", action="store_true", help="escribir de verdad en la Sheet")
    parser.add_argument("--usuario", default="samir", help="con qué usuario administrador entrar")
    args = parser.parse_args()

    import getpass

    contrasena = getpass.getpass(f"Contraseña de {args.usuario}: ")
    sesion = api_client.login(args.usuario, contrasena)
    token = sesion["token"]
    print(f"Entré como {sesion['nombre']}.\n")

    usuarios = api_client.listar_usuarios(token)
    plan = planificar(usuarios)

    if not args.aplicar:
        imprimir_plan(plan)
        print("\nEsto fue una simulación, no se escribió nada. Para aplicarlo:")
        print("  python scripts/cargar_cedulas_telefonos.py --aplicar")
        return

    tocados = 0
    for item in plan:
        u, cambios = item["usuario"], item["cambios"]
        if not u or not cambios:
            continue
        api_client.editar_usuario(token, u["id"], cambios)
        campos = ", ".join(cambios.keys())
        print(f"  {u['nombre']}: actualizado ({campos})")
        tocados += 1

    imprimir_plan(plan)
    print(f"\nListo: {tocados} usuario(s) actualizados.")


if __name__ == "__main__":
    main()
