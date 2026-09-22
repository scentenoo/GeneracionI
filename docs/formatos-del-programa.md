
# Los formatos reales del programa

Las plantillas de `templates/` se construyeron a partir de los formatos que
usa hoy el programa, diligenciados con datos reales. **Esos archivos no
están en el repo a propósito**, y hay que conseguirlos aparte para trabajar
con ellos.

## Por qué no están versionados

Traen datos personales de terceros:

- Los informes mensuales incluyen la **cédula y el número de cuenta** del
  docente que los llenó.
- La nómina tiene **cuántas horas y cuánto cobra cada una de las ~20
  personas** del programa.

Este repo lo trabajan también los chicos del curso de programación, que
arman el frontend. Y git guarda todo para siempre: una vez que algo entra a
la historia, sacarlo obliga a reescribirla, y si alguien ya clonó, ya salió.

## Qué va en `Estructura/`

Pedile los archivos al equipo directivo y ponelos en una carpeta
`Estructura/` en la raíz del repo. Está en `.gitignore`, así que no se
commitean por accidente.

| Archivo | Para qué se usó |
|---|---|
| `PlaneacionClase1007.docx` | base de `templates/planeacion_individual.docx` |
| `InformemensualSoloProfe.docx` | base del informe mensual, variante docente |
| `InformeMensualProfeDirectiva.docx` | la misma con la sección 5 de gestión |
| `PagosaCadaDocenteConHorayValorHora.xlsx` | nómina — la lee `scripts/cargar_nomina.py` |
| `EstructuraInformeAdministrativos.png` | detalle de la tabla 5.1 |

## Qué se conserva sin ellos

Todo lo que hacía falta ya está en el repo: las dos plantillas de
`templates/` tienen la estructura completa con marcadores en lugar de los
datos, y las decisiones que salieron de leerlos están documentadas en los
comentarios del código y en los mensajes de commit.

Los formatos originales solo hacen falta para dos cosas: rehacer una
plantilla desde cero, o correr el script de carga de la nómina.
