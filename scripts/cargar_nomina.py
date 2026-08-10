"""Carga los usuarios y cursos del programa desde la nómina.

La nómina tiene una fila por persona-y-curso, así que quien da dos cursos
aparece dos veces y quien además coordina, tres. El script agrupa por
persona, deduce el rol de las filas que tenga, y crea un curso por cada
fila de docencia.

Por defecto NO escribe nada: se conecta, compara contra la Sheet y
muestra lo que haría. Para aplicarlo de verdad hay que pasar --aplicar,
porque esto crea usuarios reales en la Sheet de producción y no hay
deshacer masivo.

    python scripts/cargar_nomina.py                    # ver qué haría
    python scripts/cargar_nomina.py --aplicar          # hacerlo
    python scripts/cargar_nomina.py --offline          # solo leer la nómina

Los nombres se comparan sin tildes ni mayúsculas, y un curso que ya
figure en la Sheet con el nombre más largo (la nómina dice "Desarrollo de
aplicaciones", la Sheet "Desarrollo de aplicaciones y bases de datos") se
reconoce como el mismo y no se duplica. Ante la duda no crea: un curso de
más queda pidiendo un informe mensual que nadie debe, y eso ensucia el
dashboard para siempre; uno de menos se agrega a mano en dos clics.

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
from datetime import date
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


def normalizar(texto: str) -> str:
    """Para comparar nombres escritos por manos distintas: la nómina y la
    Sheet no coinciden en tildes, mayúsculas ni espacios de más."""
    return " ".join(sin_acentos(str(texto or "")).lower().split())


def buscar_curso(nombre_nomina: str, cursos_del_docente: list[dict]):
    """Ubica el curso de la Sheet que corresponde a esa fila de la nómina.

    Devuelve (curso, motivo) con motivo 'igual' o 'parecido', o
    (None, None) si no hay ninguno.

    Lo de 'parecido' existe por un caso concreto: la nómina dice
    "Desarrollo de aplicaciones" y en la Sheet el curso está como
    "Desarrollo de aplicaciones y bases de datos". Son el mismo, pero por
    nombre exacto se crearían dos.
    """
    objetivo = normalizar(nombre_nomina)

    for c in cursos_del_docente:
        if normalizar(c["nombre"]) == objetivo:
            return c, "igual"

    for c in cursos_del_docente:
        existente = normalizar(c["nombre"])
        if existente.startswith(objetivo) or objetivo.startswith(existente):
            return c, "parecido"

    return None, None


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
    if not NOMINA.exists():
        raise SystemExit(
            f"No encontré la nómina en {NOMINA}.\n\n"
            "No está en el repo a propósito: trae los sueldos de todo el equipo.\n"
            "Pedísela al equipo directivo y ponela ahí.\n"
            "Ver docs/formatos-del-programa.md."
        )

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


def planificar(personas: dict[str, dict], usuarios: list[dict], cursos: list[dict]) -> list[dict]:
    """Qué haría el script, sin tocar nada.

    Lo calculan igual la simulación y la aplicación, para que lo que se ve
    antes sea exactamente lo que después pasa.
    """
    por_nombre = {normalizar(u["nombre"]): u for u in usuarios}

    cursos_por_docente: dict[int, list[dict]] = {}
    for c in cursos:
        cursos_por_docente.setdefault(c["docente_id"], []).append(c)

    plan = []
    for nombre, p in sorted(personas.items()):
        usuario = por_nombre.get(normalizar(nombre))
        suyos = cursos_por_docente.get(usuario["id"], []) if usuario else []
        plan.append({
            "nombre": nombre,
            "persona": p,
            "usuario": usuario,
            "cursos": [(curso, *buscar_curso(curso, suyos)) for curso in p["cursos"]],
        })
    return plan


def imprimir_plan(plan: list[dict], comparado: bool):
    for item in plan:
        p = item["persona"]
        print(f"  {item['nombre']}")
        print(f"      rol: {rol_de(p)}"
              f"  ·  hora docente: {p['valor_hora_docente'] or '—'}"
              f"  ·  hora directivo: {p['valor_hora_directivo'] or '—'}")

        if comparado:
            u = item["usuario"]
            print(f"      usuario: {'ya existe como ' + u['usuario'] if u else 'se crea'}")

        for curso, existente, motivo in item["cursos"]:
            if motivo == "igual":
                print(f"      curso «{curso}»: ya está")
            elif motivo == "parecido":
                print(f"      curso «{curso}»: NO lo creo, en la Sheet ya figura como")
                print(f"                       «{existente['nombre']}» — revisá si es el mismo")
            else:
                print(f"      curso «{curso}»: {'se crea' if comparado else '(sin comparar)'}")

        for c in p["cargos"]:
            print(f"      cargo «{c}»: no se crea como curso")

    parecidos = sum(1 for i in plan for _, _, m in i["cursos"] if m == "parecido")
    if parecidos:
        print(f"\n  Ojo: {parecidos} curso(s) se parecen a uno que ya existe y NO se van a crear.")
        print("  Si alguno era distinto de verdad, crealo a mano desde la pantalla de Cursos.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aplicar", action="store_true", help="escribir de verdad en la Sheet")
    parser.add_argument("--usuario", default="samir", help="con qué usuario administrador entrar")
    parser.add_argument(
        "--offline", action="store_true",
        help="solo leer la nómina, sin conectarse a comparar contra la Sheet",
    )
    args = parser.parse_args()

    personas = leer_nomina()
    print(f"La nómina tiene {len(personas)} personas.\n")

    if args.offline:
        # Sin la Sheet no se puede saber qué falta, así que esto solo sirve
        # para revisar que la nómina se haya leído bien.
        imprimir_plan(planificar(personas, [], []), comparado=False)
        print("\nEsto fue solo la lectura de la nómina, sin comparar contra la Sheet.")
        print("Sacale --offline para ver qué se crearía de verdad.")
        return

    import getpass

    contrasena = getpass.getpass(f"Contraseña de {args.usuario}: ")
    sesion = api_client.login(args.usuario, contrasena)
    token = sesion["token"]
    print(f"Entré como {sesion['nombre']}.\n")

    usuarios = api_client.listar_usuarios(token)
    plan = planificar(personas, usuarios, api_client.listar_todos_los_cursos(token))

    if not args.aplicar:
        imprimir_plan(plan, comparado=True)
        print("\nEsto fue una simulación, no se escribió nada. Para aplicarlo:")
        print("  python scripts/cargar_nomina.py --aplicar")
        return

    tomados = {u["usuario"] for u in usuarios}

    # La contraseña se anota EN EL MOMENTO en que el usuario queda creado,
    # no al final. Antes se juntaban todas en memoria y se escribían
    # recién al terminar: un timeout de Apps Script a mitad de camino
    # dejaba trece usuarios creados con contraseñas que ya no sabía nadie,
    # ni ellos ni yo. Pasó.
    nuevos = 0
    with CREDENCIALES.open("a", encoding="utf-8") as archivo:
        archivo.write(f"\n=== Corrida del {date.today().isoformat()} ===\n")
        archivo.write("Repartir a mano y borrar este archivo.\n")
        archivo.write("Cada quien la cambia al entrar, desde Cambiar contraseña.\n\n")
        archivo.flush()

        for item in plan:
            nombre, p, usuario = item["nombre"], item["persona"], item["usuario"]

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
                archivo.write(
                    f"{nombre}\n  usuario: {datos['usuario']}\n"
                    f"  clave:   {clave}\n  rol:     {datos['rol']}\n\n"
                )
                archivo.flush()  # que sobreviva a un corte, no al cierre ordenado
                nuevos += 1
                print(f"  {nombre}: creado como {datos['usuario']} ({datos['rol']})")

            for curso, existente, motivo in item["cursos"]:
                if motivo == "igual":
                    print(f"      curso «{curso}» ya estaba")
                elif motivo == "parecido":
                    print(f"      curso «{curso}» NO creado: ya figura como «{existente['nombre']}»")
                else:
                    api_client.crear_curso(token, {"docente_id": usuario["id"], "nombre": curso})
                    print(f"      curso «{curso}» creado")

    if nuevos:
        print(f"\n{nuevos} contraseñas anotadas en {CREDENCIALES}")
        print("Repartilas y borrá el archivo. No está en git.")

    print("\nSe puede volver a correr las veces que haga falta: saltea lo que")
    print("ya existe, así que si se corta a la mitad se retoma corriéndolo otra vez.")
    print("\nFalta completar a mano, desde la app: cédula, cuenta bancaria,")
    print("núcleo y rango de edades de cada curso. La nómina no los trae.")


if __name__ == "__main__":
    main()
