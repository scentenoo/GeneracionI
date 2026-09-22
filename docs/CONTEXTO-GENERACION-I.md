# Generación-I — Documento de contexto completo de la aplicación

> **Para quién es esto:** para un asistente de IA (Claude en modo chat) que NO tiene acceso al código.
> **Para qué:** que el dueño de la app (Samir) pueda preguntarle "¿puedo hacer X con esto?", "¿qué me toca cambiar para llevármela?", "¿qué se rompe si...?" y obtener respuestas reales, no inventadas.
> **Fuente:** este documento se armó leyendo el código completo del repositorio (backend, cliente, scripts, plantillas) y su historial de git. Versión de la app al momento de escribirlo: **2.2.0** (septiembre de 2026).

---

## 0. Instrucciones para el asistente que lea esto

1. Trata este documento como la fuente de verdad sobre la app. Si algo que te pregunten no está aquí, dilo ("eso no está en el documento, habría que mirar el código") en vez de suponer.
2. Distingue siempre tres cosas cuando respondas: **(a) lo que la app hace hoy**, **(b) lo que se podría hacer con cambios razonables**, **(c) lo que no se puede / no conviene**. Las secciones 13, 14 y 15 están hechas para eso.
3. El usuario no es un desarrollador senior de Google Apps Script; es una persona que construyó esto junto con una herramienta de IA (Claude Code) durante ~6 semanas para un programa real. Explica sin asumir jerga, pero sin tratarlo como novato: entiende la lógica del sistema.
4. Cuando propongas cambios, ten presente que **el sistema está en producción con ~18 personas usándolo** (mientras siga en Generación-I). Cualquier cambio de esquema en la Sheet o del contrato del backend puede romper instalaciones viejas del cliente.
5. Este documento **no contiene** datos personales de nadie (cédulas, cuentas bancarias, contraseñas), ni URLs/IDs de producción. Si el usuario los pega en el chat, recuérdale que no es buena idea compartirlos.

---

## 1. Resumen en un párrafo

Generación-I es una aplicación de **escritorio para Windows** (Python + customtkinter) que usan unos 18–20 docentes y directivos de un programa educativo municipal para: cargar sus **planeaciones de clase** (formato "Diario Pedagógico") con fotos y asistencia, registrar **horas externas/de gestión**, entregar el **informe mensual** (que además es la base de su **cuenta de cobro por horas**), y que el equipo directivo **revise, apruebe o devuelva** ese trabajo, cierre el mes y genere certificados y reportes (certificado de pago, informe de asistencia, reporte de inasistencias). No hay servidor propio: el "backend" es un **Google Apps Script** publicado como Web App, que usa una **Google Sheet como base de datos** y **Google Drive como almacén de archivos**. Los documentos Word/PDF se generan **en el cliente** con plantillas `.docx`.

---

## 2. Contexto del negocio (por qué existe cada regla)

- **Cliente/entorno:** programa educativo de una **alcaldía municipal en Antioquia, Colombia** (San Pedro de los Milagros), operado por una organización contratista. Los documentos llevan el membrete oficial del municipio (escudo, código de trámite `PC-PA-003-F03` para el Diario Pedagógico, pie de página con dirección y correo institucional).
- **Personas:** ~18–20 en total. Docentes (dan cursos a niños/adolescentes), directivos (coordinan; algunos también dan clase) y un administrador de la app (el propio Samir, que además da clase).
- **Se les paga por hora.** El informe mensual de cada docente funciona como **cuenta de cobro**: suma horas de clases + horas de otras actividades × valor de hora, y escribe el total en números y en letras. Por eso el sistema es estricto con evidencias (fotos, asistencia, mínimos de texto): las horas se pagan con plata pública y se auditan.
- **Revisión por "color":** cada curso tiene color verde o morado; el color decide qué coordinadora (revisora) aprueba o devuelve sus planeaciones e informes.
- **Computadores viejos y conexión mediocre:** se diseñó para pantallas de 1366×768, equipos lentos y con internet inestable → animaciones de carga, reintentos, mensajes claros sin internet, fotos comprimidas.
- **Origen del rediseño visual:** el equipo (incluido un curso de programación de estudiantes que arma el frontend) eligió un mockup; el tema verde oscuro + dorado sale de ahí. Hay un mockup HTML en `docs/diseno/`.
- **Nota:** en el código hay comentarios que citan "la spec, sección N". Esa especificación **no está en el repositorio**; lo que se sabe de ella es lo que dicen esos comentarios (roles, mínimos de palabras, etc.).

---

## 3. Arquitectura

```
┌───────────────────────────────┐        HTTPS POST (JSON)         ┌─────────────────────────────┐
│  CLIENTE (Windows, .exe)      │ ───────────────────────────────▶ │  BACKEND: Google Apps Script │
│  Python 3 + customtkinter     │  {action, params:[token, ...]}   │  (Web App, un solo endpoint) │
│  - pantallas (ui/)            │ ◀─────────────────────────────── │  doPost → ACCIONES_PERMITIDAS_│
│  - api_client.py (única       │  {ok:true,data} | {ok:false,     │                              │
│    puerta al backend)         │   error:"..."}                   └──────────┬───────────┬───────┘
│  - services/: docx, excel,    │                                             │           │
│    pdf, fotos, ortografía     │                                  Google Sheets      Google Drive
│  - genera .docx con docxtpl   │                                  (base de datos,   (fotos, .docx,
└───────────────────────────────┘                                   11 pestañas)     firmas)
```

**Decisiones de arquitectura clave (y el porqué):**

| Decisión | Motivo |
|---|---|
| Google Sheets como base de datos | Cero costo, cero servidor que mantener, el equipo directivo puede abrir la Sheet y ver/arreglar datos a mano (en la práctica lo hacen). |
| Un solo endpoint (`doPost`) que enruta por `action` | Más simple que un deployment por función; un único lugar para errores. Whitelist en `ACCIONES_PERMITIDAS_` (72 acciones). |
| Documentos `.docx` se generan **en el cliente** (docxtpl) | Apps Script no puede correr docxtpl ni LibreOffice. El backend solo agrega datos y devuelve un JSON "contexto"; el cliente rellena la plantilla. |
| Login propio (usuario/contraseña en la Sheet), no cuentas de Google | Los docentes no necesitan cuenta Google institucional para entrar; el acceso a la URL del Web App es "cualquiera", el control real lo hace `login()`. |
| Sesión = token UUID guardado en `CacheService` (8 h) | No hace falta persistirla ni escribir en Sheets en cada request. |
| Fotos se comprimen en el cliente (Pillow) antes de subir | Cuota de Drive y velocidad de subida. Máx. 1600 px, JPEG calidad 75. |
| `batch` (varias acciones en un viaje) | Cada llamada a Apps Script cuesta ~2–3 s de ida y vuelta, casi todo overhead fijo. |
| Dos entornos: **pruebas** y **real** | Proyectos de Apps Script separados, cada uno con su Sheet y su carpeta de Drive. |

**Stack exacto:**
- Backend: Google Apps Script (runtime V8, zona horaria `America/Bogota`), desplegado con `clasp` v3 desde Node.
- Cliente: Python, `customtkinter>=5.2`, `requests`, `Pillow`, `docxtpl` (y `python-docx`), `openpyxl`, `tkcalendar`, `spylls` (corrector Hunspell puro Python), `pyinstaller`, `pywin32` (solo Windows, para convertir a PDF con Word).
- Empaquetado: PyInstaller (modo carpeta) + instalador Inno Setup (sin permisos de administrador; instala en la carpeta del usuario).
- Tamaño aproximado: ~21 mil líneas: backend ≈4,9 mil (JS), cliente ≈14,6 mil (Python) y scripts ≈1,8 mil. 81 commits (7-ago-2026 → 17-sep-2026).

---

## 4. Roles y permisos

Hay **tres roles** en la columna `rol` y **un privilegio aparte** (`es_admin`):

| Rol | Qué es |
|---|---|
| `docente` | Da cursos. Carga planeaciones, actividades, entrega informe de cada curso. |
| `directivo` | Cargo de gestión en el programa. Puede no tener cursos. Registra "horas de gestión". Supervisa. |
| `ambos` | Da clase **y** tiene cargo directivo. |
| `es_admin` (bandera) | **Un solo usuario a la vez.** No es un cargo del programa; es quien administra la app. Se transfiere, nunca se duplica. |

**Conceptos de permiso distintos (importante, costó bugs reales):**
- `esDirectivo_` = "¿ocupa un cargo directivo *en el programa*?" (rol directivo/ambos). De esto depende: foto opcional en actividades, saltarse el cierre de mes, tener sección de gestión en el informe y cobrar horas de gestión. **El administrador NO lo hereda** por serlo.
- `puedeSupervisar_` = directivo/ambos **o** administrador. Sirve para ver/tocar lo de otra persona (planeaciones, estudiantes, informes).
- `requireAdministrador_` = solo `es_admin`, y **revalida contra la Sheet** (no confía en la sesión) para acciones irreversibles.
- `requireRole_(sesion, [roles])` = por rol; deja pasar al administrador si se pide directivo.

**Quién puede qué (resumen):**

| Acción | Docente | Directivo/Ambos | Administrador |
|---|---|---|---|
| Cargar/editar/eliminar **sus** planeaciones y actividades | ✔ (mes abierto) | ✔ (si tiene componente docente) | ✔ solo si tiene cursos |
| Editar planeación/actividad **de otro** | ✘ | ✔ (nunca elimina lo ajeno) | ✔ |
| Ver planeaciones/estudiantes/informes de otros | ✘ | ✔ | ✔ |
| Crear/editar cursos, estudiantes, usuarios, firmas | ✘ | ✔ | ✔ |
| Eliminar usuario | ✘ | Solo docentes | Cualquiera menos a sí mismo ni a otro admin |
| Restablecer contraseña de otro | ✘ | Solo de docentes | Cualquiera |
| Revisar (aprobar/devolver) planeaciones e informes | ✘ | Según color asignado (ver §7.4) | Todo |
| Registrar horas de gestión | ✘ | ✔ | Solo si es directivo/ambos |
| Cerrar/reabrir mes, fijar fecha de cierre | ✘ | ✔ | ✔ |
| Certificado de pago | ✘ | ✘ | ✔ **solo admin** |
| Informe de asistencia / reporte de inasistencias | ✘ | ✔ | ✔ |
| Fijar revisores por color | ✘ | ✘ | ✔ |
| Publicar versión de la app | ✘ | ✘ | ✔ |
| Eliminar curso definitivo (cascada), eliminar informe entregado | ✘ | ✘ | ✔ |
| Ejecutar migraciones de esquema desde la app | ✘ | ✘ | ✔ |

**Contraseñas:** hash SHA-256 con *salt* (UUID por usuario), formato `salt:hash`. Nadie puede "ver" una contraseña; el directivo solo puede **restablecerla**. Mínimo 6 caracteres. El nombre de usuario se normaliza (minúsculas, sin espacios) para comparar — existió un bug donde un usuario llamado "1" nunca podía entrar porque Sheets lo convertía a número.

**Bootstrap:** si la pestaña Usuarios está vacía, `crear_usuario` se permite sin sesión (para crear al primero). Mientras no exista administrador, cualquier directivo puede autoproclamarse (`convertirme_administrador`). Existe `restaurar_administrador` (recuperación) porque **se llegó a borrar al administrador por error** y con él el dueño de todos los cursos.

---

## 5. Modelo de datos (Google Sheet)

Cada pestaña: fila 1 = encabezados, columna `id` numérica autoincremental (máximo+1, **se reutilizan ids** de filas borradas). `setupSheets()` crea pestañas faltantes y **solo agrega** columnas nuevas al final; nunca reordena ni borra (quitar columnas es tarea de las migraciones).

| Pestaña | Columnas principales | Notas |
|---|---|---|
| **Usuarios** | id, nombre, usuario, password_hash, rol, es_admin, valor_hora_docente, valor_hora_directivo, cedula, telefono, formacion, numero_cuenta, tipo_cuenta, entidad_bancaria, firma_drive_id, ultimo_acceso | Datos personales y bancarios para la cuenta de cobro. La firma (imagen) va a Drive. |
| **Cursos** | id, docente_id, nombre, nucleo, edad_desde, edad_hasta, activo, color, excluido_certificado | **El curso es la unidad del informe mensual.** Un docente puede tener varios. `color` ∈ {verde, morado} (obligatorio al crear). `excluido_certificado` saca un curso del certificado de pago sin desactivarlo. |
| **Planeaciones** | id, docente_id, curso_id, fecha, grupo, objetivo, temas_vistos (JSON), bloques (legacy), momentos (JSON), observaciones, avances, asistencia (JSON snapshot), horas, foto_clase_drive_id, fotos_clase_drive_ids (JSON), doc_drive_id, creado_en, estado, revisado_por, revisado_en, motivo_devolucion | **Única por curso+fecha**: guardar de nuevo *actualiza* (evita duplicados por doble clic). La asistencia se guarda como **copia** `{nombre, presente}` del día, no como referencia al estudiante. |
| **Actividades** | id, usuario_id, curso_id, fecha, descripcion, horas_sede, horas_externas, foto_drive_id, creado_en | Lo que se factura y **no** es clase: reuniones, claustros, informes. Sin esto, la cuenta de cobro salía por la mitad. |
| **InformesMensuales** | id, curso_id, docente_id, mes, 6 campos narrativos, avance_semanal (JSON), incluye_gestion, gestion_* (5), creado_en, actualizado_en, estado, revisado_por, revisado_en, motivo_devolucion, doc_drive_id | Una fila por **curso y mes**. `curso_id` puede ser la clave sintética `gestion:<id_directivo>` para el informe de un directivo sin curso. |
| **Estudiantes** | id, nombre, curso_id (legacy) | **Una ficha por persona.** |
| **Inscripciones** | id, estudiante_id, curso_id, creado_en | Un estudiante puede estar en varios cursos. Al agregar por nombre se **reusa** la ficha si el nombre normalizado (sin tildes/mayúsculas) ya existe. |
| **HorasGestion** | id, directivo_id, fecha, actividad, horas_sede, entregable, link_soporte, foto_drive_id, creado_en, estado, revisado_por, revisado_en, motivo_devolucion | Foto y entregable obligatorios al crear. |
| **Reaperturas** | id, curso_id, mes, abierta, abierto_por, actualizado_en | Excepciones al cierre de mes, por curso y mes. |
| **Revisiones** | id, tipo, ref, accion, motivo, autor, fecha | Historial de auditoría. `tipo` ∈ planeacion / informe / hora_gestion; `ref` = id de planeación, o `"<curso_id>|<mes>"` para informes. |
| **Config** | key, value | Clave/valor: `version_actual`, `version_minima`, `link_instalador`, `dia_de_corte`, `cierre_YYYY-MM`, `revisor_verde`, `revisor_morado`. |

**Trampas de Google Sheets que el código ya maneja (y que cualquier reimplementación debe recordar):**
- Sheets convierte celdas con forma de fecha (`2026-08`, `2026-08-07`) a objetos `Date` → hay helpers `fechaISO_`, `mesDeFecha_`, etc. para normalizar.
- Convierte a número textos que parecen número (un usuario "1", un nombre "2024") → se fuerza `String(...)` en comparaciones.
- Una fila **sin `estado`** cuenta como *pendiente* (filas anteriores al flujo de revisión o agregadas a mano).
- Escrituras concurrentes se protegen con `LockService.getScriptLock()` (espera hasta 30 s).
- Cada `readAllRows_` lee **toda** la pestaña. Se optimizó cacheando el handle del Spreadsheet por ejecución, el último id por pestaña, y agrupando lecturas en memoria (dashboard) — pero el diseño sigue siendo "leer tabla completa".

---

## 6. Estructura de carpetas en Google Drive

Todo cuelga de una carpeta raíz (`DRIVE_ROOT_FOLDER_ID`, Script Property). Las subcarpetas se crean solas:

```
<raíz>/
  Planeaciones/<curso>/<YYYY-MM - Mes>/Fotos/       (hasta 3 fotos por clase)
  Planeaciones/<curso>/<YYYY-MM - Mes>/Documentos/  (.docx de la planeación)
  Informes/<curso>/<YYYY-MM - Mes>/                  (.docx del informe entregado)
  Actividades/<curso>/<YYYY-MM - Mes>/Fotos/
  Fotos de horas de gestión/
  Firmas/                                            (una imagen por usuario)
```
- Los archivos se comparten como **"cualquiera con el link puede ver"** (para que un revisor abra sin pedir acceso); si el dominio Workspace lo bloquea, se ignora el error y el archivo se guarda igual.
- Nombres de archivo con prefijo legible: `Planeacion - <curso> - <fecha>.docx`, `Informe - <curso> - <mes>.docx`.
- Al borrar (planeación, actividad, curso) los archivos van a la **papelera**, sin fallar si ya no existen.

---

## 7. Funcionalidades y reglas de negocio

### 7.1 Constantes del programa (definidas en `Validation.js`, `Cierre.js`)

| Regla | Valor |
|---|---|
| Palabras mínimas en campos de detalle (objetivo, observaciones, avances, gestión) | 20 |
| Palabras mínimas en las 6 preguntas narrativas del informe (2.1–2.6) | 80 |
| Palabras mínimas por momento de la clase | inicial 80 · desarrollo 100 · final 70 |
| Duración mínima de una clase (suma de momentos) | 120 min (2 h) |
| Clases esperadas al mes / mínimas para poder entregar informe | 4 / **3** |
| Fotos por clase | mín. 1, máx. 3 |
| Horas externas objetivo por persona al mes | 8 |
| Umbral de alerta de inasistencias | más de 3 faltas |
| Largo mínimo de contraseña | 6 |
| Vigencia de sesión | 8 horas |
| Día de corte por defecto (cierre de mes) | 5 del mes siguiente (rango permitido 1–28) |

### 7.2 Planeación de clase (docente) — formato Diario Pedagógico
- Campos: fecha, curso (desplegable con sus cursos), objetivo, temas de la clase (lista de viñetas, ≥1), **tres momentos** (inicial/desarrollo/cierre, cada uno con texto y minutos), evaluación de la clase (observaciones del desempeño de los estudiantes), asistencia (checklist de los estudiantes inscritos), 1–3 fotos.
- Un docente puro **no puede guardar una clase con 0 estudiantes presentes**; un directivo sí.
- Horas = suma de minutos de los momentos / 60. Si pasa de 2 h, el cliente pide confirmar (esas horas se cobran).
- **Vista previa** antes de guardar: se arma el `.docx` con lo del formulario, se convierte a PDF si el equipo tiene LibreOffice o Word, si no se abre el `.docx`.
- Al guardar: se sube el registro a la Sheet + fotos a Drive; luego el cliente genera el `.docx` final y lo archiva con `guardar_documento_planeacion` (llamada aparte a propósito: si el documento falla, la clase igual queda registrada).
- Guardar una del mismo curso+fecha **actualiza** y la deja otra vez *pendiente*. Al editar cambiando la fecha, si choca con otra clase del curso, se rechaza.
- Corrector ortográfico en vivo (español Colombia, sin internet), autocapitalización tras punto, contador de palabras.

### 7.3 Actividades / "horas externas" (docente)
- Reuniones, claustros, informes, atención a padres. Se registran por **curso** (el informe va por curso; quien tiene varios elige en cuál reporta para no contarla dos veces).
- `horas_sede` y `horas_externas` son solo *dónde* se hizo; se pagan al mismo valor. Foto obligatoria (excepto directivos).

### 7.4 Flujo de revisión
- Estados: `pendiente` → `aprobado` | `devuelto` (con motivo obligatorio). Editar o volver a guardar deja `pendiente` (si venía devuelto, se registra como "reenviado").
- Cada acción se anota en **Revisiones** y ese historial se imprime al **final de cada documento** (hoja "Historial de revisión").
- **Quién revisa qué:** `Config.revisor_verde` y `revisor_morado` (ids de usuario, los fija el administrador). Quien tiene un color asignado solo revisa cursos de **su** color; el resto del equipo directivo y el administrador revisan cualquiera. Un curso sin color queda sin revisor (aviso en la pantalla de revisores).
- El docente ve una **campanita** y un aviso al entrar con lo que le devolvieron y por qué; se re-chequea periódicamente.
- Horas de gestión externas también se aprueban/devuelven una por una (cualquiera del equipo directivo).

### 7.5 Informe mensual (por curso)
- Solo se puede **entregar** si el curso tiene ≥3 planeaciones del mes.
- Contenido: 6 preguntas narrativas (≥80 palabras c/u) + **evaluación de avance por semana** (una fila por clase con nivel y observación; la "unidad trabajada" se arma sola desde los temas vistos) + opcionalmente **sección de gestión** (5 campos, ≥20 palabras) para directivos con curso — se marca en **un solo** informe del mes para no cobrar dos veces las horas de gestión.
- El backend arma el JSON: actividades (clases + otras actividades ordenadas por fecha, con semana, horas, asistentes, link al documento de Drive), evidencias fotográficas, totales, **cuenta de cobro** (número, mes, periodo, horas, valor en números y en letras, datos bancarios, firma). Valor = horas × `valor_hora_docente` (+ horas de gestión × `valor_hora_directivo` si incluye gestión).
- El cliente rellena `informe_mensual.docx`, lo sube a Drive y queda guardado en `doc_drive_id`.
- **Directivo sin curso** → informe de gestión aparte (`informe_gestion.docx`): solo gestión + cuenta de cobro con la hora directiva. Se guarda en la misma pestaña con `curso_id = "gestion:<id>"` para no reescribir el modelo.
- Un directivo/administrador puede descargar el informe ya entregado de cualquiera (uno a uno o **todos en ZIP**).

### 7.6 Cierre de mes
- Pasada la fecha de cierre del mes, el docente **no puede** cargar, editar ni borrar planeaciones/actividades ni volver a entregar el informe (porque dirección ya armó la cuenta de cobro). La fecha de cierre incluye todo ese día; cierra al siguiente.
- La fecha se fija **por mes** con calendario (`Config.cierre_YYYY-MM`); si no hay, se usa el día de corte por defecto.
- Un directivo puede **reabrir un curso y mes puntuales** (tabla Reaperturas) y volver a cerrarlo. **Los directivos nunca quedan bloqueados.** Las horas de gestión no tienen cierre.

### 7.7 Cursos y estudiantes (directivo)
- Alta de cursos con núcleo, rango de edades, color (obligatorio). Editar, **desactivar** (conserva historia) o **eliminar definitivo** (solo administrador; borra en cascada planeaciones, actividades, informes, inscripciones, reaperturas, historial y manda a papelera sus archivos de Drive).
- Estudiantes: importar CSV (acepta separador `,` o `;` porque Excel en español exporta con `;`; requiere columna `nombre`), agregar/quitar por curso, búsqueda para inscribir a alguien en un segundo curso sin duplicarlo. Quitar de un curso no toca planeaciones ya guardadas; una ficha sin ninguna inscripción se elimina.

### 7.8 Dashboard mensual (directivo)
Una fila por **curso** (no por docente): clases registradas vs. esperadas, faltantes, si entregó informe, horas externas vs. objetivo de 8, si el mes está cerrado/reabierto. Ordenado por urgencia con colores.

### 7.9 Reportes del equipo directivo / administrador
- **Certificado de pago** (solo administrador): por docente y curso, total de horas del mes (sede + externas), con excluidos y sin-horas listados aparte en la vista previa. Se descarga como `.docx` (a propósito, para completar a mano teléfono/formación faltante).
- **Informe de asistencia** del mes (PDF; consolidado de todos los cursos, o **por curso con espacio de firma** del docente y la coordinadora). Cruza la asistencia guardada en cada clase contra el roster real usando nombres normalizados; lo que no coincide queda en `no_identificados` en vez de descartarse. Pedido originalmente por la Secretaría de Educación.
- **Reporte de inasistencias** (Excel, una hoja por curso): acumulado de **todas** las clases del curso, resalta a quien faltó más de 3 veces, más un bloque de "en cuántos cursos activos está cada estudiante". (Nota histórica: se dejó de acotar desde la fecha de inscripción porque ese dato no era confiable.)

### 7.10 Administración
- **Usuarios** (pestañas Lista / Crear / Editar): último acceso visible (para saber quién ni siquiera instaló la app), firma digital (imagen subida una vez y reutilizada en los informes), transferir administrador, restablecer contraseña.
- **Mi cuenta:** ver el propio perfil (solo lectura; lo carga dirección) y cambiar contraseña.
- **Revisores por color** y **Versión de la app** (solo administrador).
- **Migraciones** ejecutables desde la API (`setupSheets`, `migrarACursos`, `limpiarColumnasViejas`, `eliminarHistorial`, `migrarAInscripciones`, `limpiarColumnaCursoDeEstudiantes`): whitelist, solo admin, idempotentes.

---

## 8. Documentos que genera la app (plantillas en `templates/`)

| Plantilla / salida | Quién | Formato | Notas |
|---|---|---|---|
| `planeacion_individual.docx` | docente | Word (y PDF en vista previa) | Diario Pedagógico, código `PC-PA-003-F03`, hasta 3 fotos, asistencia en tabla. |
| `informe_mensual.docx` | docente / directivo con curso | Word/PDF | Informe + cuenta de cobro + evidencias + firma. Sección 5 (gestión) condicional (`es_directivo`). |
| `informe_gestion.docx` | directivo sin curso | Word | Sin código de trámite a propósito (no existe un formato oficial del que copiarlo). |
| `certificado_pago.docx` | administrador | Word | Correo de Secretaría de Educación (distinto al de Gobierno), fuente Arial. |
| Informe de asistencia (sin plantilla: `client/src/services/informe_asistencia_docx.py`) | supervisión | PDF | Una página por curso con firmas (consolidado de todos, o uno solo). Se arma con `python-docx` porque las columnas dependen de cuántas clases hubo; pensado para imprimirse también en blanco y negro. Muestra a los retirados del mes. |
| Reporte de inasistencias | supervisión | Excel (`openpyxl`) | Una hoja por curso; los nombres de hoja se sanean (Excel prohíbe `\ / ? * [ ] :` y corta a 31 caracteres). |

- Motor: **docxtpl** (Jinja dentro de Word). Convención importante: en las tablas, `{%tr for ...%}` y `{%tr endfor%}` van en **filas separadas**, o docxtpl falla con "unknown tag 'endfor'".
- Las plantillas se **construyen con scripts** (`scripts/construir_plantilla_*.py`, con `python-docx`) para que sean reproducibles; las dos plantillas docentes originales se hicieron a mano a partir de los formatos reales. El membrete municipal (escudo, encabezado, pie) sale de `scripts/_membrete_municipio.py`.
- Imágenes: fotos y firma viajan como base64 desde el backend y el cliente las convierte a `InlineImage`; si no hay imagen se pasa `""` (con `None`, docxtpl imprimiría literalmente "None").
- Se anexa siempre una **hoja final de historial de revisión** al documento.
- **PDF:** `pdf_converter` intenta LibreOffice (`soffice --headless`) y luego Microsoft Word vía `pywin32`; si ninguno existe, se ofrece el `.docx`. No hay garantía de que los 18 equipos tengan alguno.
- **Número a letras** (para el valor en la cuenta de cobro) está implementado a mano en `NumeroALetras.js` (español).

---

## 9. Contrato de la API

**Petición:** `POST <URL del Web App>` con cuerpo JSON `{"action": "guardar_planeacion", "params": [token, datos, fotos]}`. Los parámetros son **posicionales** y el primero suele ser el token de sesión (excepciones: `login`, `version_actual`).
**Respuesta:** siempre `{"ok": true, "data": ...}` o `{"ok": false, "error": "mensaje"}`. `GET` devuelve la versión (sin sesión).
**`batch`:** `{"action":"batch","params":[[{action, params}, ...]]}` → lista de resultados, cada uno con su propio ok/error; no se anida.

**Acciones (agrupadas):**
- Sesión/versión: `login`, `cambiarPassword`, `version_actual`, `fijar_version`
- Planeaciones: `guardar_planeacion`, `guardar_documento_planeacion`, `obtener_planeaciones`, `obtener_planeacion`, `obtener_foto_planeacion`, `editar_planeacion`, `eliminar_planeacion`, `obtener_estado_mes`
- Actividades: `guardar_actividad`, `editar_actividad`, `obtener_actividades`, `eliminar_actividad`
- Horas de gestión: `guardar_horas_gestion`, `editar_horas_gestion`, `eliminar_horas_gestion`, `obtener_horas_gestion`, `obtener_horas_del_equipo`, `obtener_foto_horas_externas`, `revisar_hora_gestion`
- Informes: `generar_informe_mensual`, `guardar_informe_mensual`, `guardar_documento_informe`, `obtener_informe_mensual`, `eliminar_informe_mensual`, `obtener_avance_sugerido`, `guardar_informe_gestion`, `obtener_informe_gestion`, `generar_informe_gestion`, `directivos_sin_curso_del_mes`
- Revisión: `revisar_planeacion`, `revisar_informe`, `revision_del_mes`, `mis_devoluciones`, `historial_revision`, `fijar_revisores`, `obtener_revisores`
- Cursos/estudiantes: `crear_curso`, `listar_cursos`, `listar_todos_los_cursos`, `editar_curso`, `desactivar_curso`, `eliminar_curso_definitivo`, `obtener_estado_nucleo`, `obtener_resumen_docente`, `importar_estudiantes`, `obtener_estudiantes`, `buscar_estudiantes`, `modificar_grupo`
- Usuarios: `crear_usuario`, `editar_usuario`, `obtener_mi_perfil`, `eliminar_usuario`, `listar_usuarios`, `restablecer_password`, `subir_firma`, `convertirme_administrador`, `restaurar_administrador`, `transferir_administrador`
- Cierre: `estado_cierre`, `fijar_dia_de_corte`, `fijar_fecha_de_cierre`, `fecha_de_cierre`, `reabrir_mes`
- Reportes: `obtener_dashboard_directivo`, `generar_certificado_pago`, `generar_informe_asistencia`, `generar_reporte_inasistencias`
- Mantenimiento: `ejecutar_migracion`

(Convención de nombres: casi todo es `snake_case`; las únicas excepciones son `login` y `cambiarPassword`.)

**Comportamiento del cliente (`api_client.py`):**
- Es la **única** puerta al backend; las pantallas nunca usan `requests` directo. Timeout 60 s (medido: 1 foto ≈ 13–14 s, 3 fotos ≈ 25–30 s al guardar una planeación).
- **Reintentos solo en acciones de lectura** (2 reintentos, pausa 2,5 s), porque reintentar una escritura que quizá sí se guardó duplicaría datos. Las escrituras nunca se reintentan solas.
- Sabe distinguir: `SinConexion` (ofrece "Reintentar"), `SesionExpirada` (volver a loguear) y `ApiError` (error de negocio). Nunca muestra al usuario la URL ni detalles técnicos. Códigos 401/403 → "problema de configuración, avísele a Samir".
- Valida que ciertas respuestas tengan la forma esperada (`login`, `obtener_foto_horas_externas`) porque Apps Script bajo carga a veces devuelve el cuerpo **de otra petición**.
- Subidas con **barra de progreso real** (cuerpo enviado por trozos de 16 KB). Ojo: no se debe poner `Content-Length` a mano junto con el cuerpo por trozos: Google responde 400.

---

## 10. El cliente de escritorio

**Estructura (`client/src/`):**
- `main.py` — arranque: aplica parches, tema claro fijo, carga el diccionario en segundo plano, muestra un "telón" verde mientras consulta la versión; luego login o pantalla de bloqueo.
- `config.py` — `APP_VERSION`, URL del backend (`GENERACIONI_BACKEND_URL` de entorno o la de producción), rutas de plantillas/tema/diccionario (distintas si está empaquetado con PyInstaller: `sys._MEIPASS`).
- `api_client.py` — cliente HTTP (§9). `services/` — lógica sin UI: `docx_generator`, `excel_generator`, `pdf_converter`, `vista_previa`, `image_utils`, `ortografia`, `date_utils`, `avisos`.
- `ui/` — pantallas customtkinter. `app.py` es el shell: barra lateral + encabezado + área de contenido, armado una sola vez tras el login.
- `assets/` — tema JSON de customtkinter, diccionario Hunspell `es_CO`, ícono.

**Menú lateral según rol:** Inicio · Planeaciones y actividades (docentes; pestañas *Horas en sede / Mis planeaciones / Horas externas*) · Generar informe mensual · *(directivo/admin)* Revisar planeaciones e informes (pestañas: Planeaciones, Informes, Horas externas, Dashboard mensual, Certificado de pago [solo admin], Informe de asistencia) · Cursos (pestañas Cursos/Estudiantes) · Horas de gestión · Usuarios · Mi cuenta · *(solo admin)* Revisores por color, Versión de la app.

**Patrones técnicos que importa conocer:**
- **Nunca** se llama al backend en el hilo de Tkinter: `tareas.en_segundo_plano(widget, trabajo, al_terminar, al_fallar)` corre en un hilo y devuelve el resultado por una **cola** que el hilo principal vacía cada 50 ms (Tkinter no es thread-safe; ni `winfo_exists()` ni `after()` se pueden llamar desde un hilo).
- Un **overlay de carga** (logo + frase + progreso real cuando lo hay) tapa la ventana durante esperas; hay contador de "trabajo pendiente" que avisa antes de cerrar la app o la sesión si algo se está subiendo.
- **Caché en memoria** (`tareas.cache`): usuarios, cursos, mis cursos; se precarga en un `batch` al entrar y las pantallas que modifican deben llamar `invalidar()`.
- Ventana abre **maximizada** (`zoomed`, pedida con `after(10, ...)` porque en `__init__` no se sostenía), tamaño mínimo 560×480, pensada para 1366×768.
- Borradores de vista previa van a una carpeta temporal y se borran al cerrar o cerrar sesión (llevan nombres de estudiantes y fotos).
- Existe `ctk_parches.py` que corrige comportamientos de customtkinter (p. ej. copiar/pegar).
- Tema: verde oscuro `#0F3D2E`, verde marca `#2fa84f`, dorado `#F2A900`/`#E8A11C`; centralizado en `ui/tema.py` (algunas pantallas viejas aún tienen colores locales duplicados).

---

## 11. Despliegue y operación

### 11.1 Backend (Apps Script)
- Dos proyectos: **pruebas** y **real**, cada uno con su Sheet y carpeta de Drive. En cada uno, *Script Properties*: `SHEET_ID` y `DRIVE_ROOT_FOLDER_ID`. `inicializarProyecto()` puede crear Sheet y carpeta y guardar los ids; `setupSheets()` crea las pestañas.
- `backend/entorno.js` es un puente sobre `clasp`: cada comando pide explícitamente `test` o `prod` (`npm run prueba:push` / `real:push`), genera `.clasp.json` al vuelo, corre clasp y lo borra. Empujar a **prod pide escribir literalmente `SI PRODUCCION`**. Motivo: una vez se creyó estar editando pruebas y era producción. `entornos.json` (con los scriptId) no se versiona.
- Web App: ejecutar como el usuario que despliega, acceso "Anyone" (anónimo) — el control real es `login()`.
- **Cambiar código sin cambiar la URL:** Gestionar implementaciones → editar implementación existente → *Nueva versión*. **Nunca** usar una "Test deployment" (@HEAD) como URL del cliente: solo funciona con sesión de navegador con permiso de edición, así que `requests.post` recibe "No se encontró la página". Ya pasó una vez ("El servidor rechazó la conexión").
- Cambiar el esquema: `clasp push` → correr `setupSheets` (desde el editor o desde la app con `ejecutar_migracion`) → migración si aplica.

### 11.2 Cliente
1. Subir `APP_VERSION` en `config.py`.
2. `pyinstaller` con el `.spec` (modo carpeta; incluye `templates/`, diccionario, tema, y datos de `tkcalendar`/`babel`). Sin el tema en el bundle el `.exe` "explota apenas arranca".
3. Compilar el `.iss` con Inno Setup → `GeneracionI-Planeaciones-Setup.exe`. `AppId` fijo (no cambiar) para que Windows actualice en vez de duplicar. Se instala sin permisos de administrador.
4. Subir el instalador a un lugar descargable (Drive/GitHub) y **recién ahí** publicar la versión desde la pantalla "Versión de la app" (admin) con el link.
- **Orden importa:** publicar como obligatoria antes de que el instalador exista deja a los 18 computadores bloqueados.

### 11.3 Actualizaciones
Al abrir, el cliente consulta `version_actual` (sin login): si su versión < `version_minima` **queda bloqueado** con botón de descarga; si < `version_actual` solo ve un aviso. La comparación es numérica por partes (como texto, "1.9.0" > "1.10.0").

### 11.4 Scripts (`scripts/`)
- `cargar_nomina.py` — crea usuarios desde el Excel de nómina (contraseñas aleatorias en un archivo ignorado por git; **no** crea cursos porque necesitan color). Por defecto solo simula; `--aplicar` escribe.
- `cargar_cedulas_telefonos.py` — completa cédula/teléfono/formación de docentes existentes (solo campos vacíos; empareja nombres por conjunto de palabras; no adivina ambigüedades). Igual, `--aplicar`.
- `construir_plantilla_*.py` — regeneran las plantillas `.docx`.
- `simulacro_mes.py` — prueba de extremo a extremo de un mes con 18 personas contra el backend real, anota "HALLAZGOS" y limpia lo creado. **Es lo más parecido a una suite de pruebas que existe.**
- `prueba.py` (raíz) — archivo suelto de un "hola mundo" de Tkinter; no es parte de la app.

---

## 12. Decisiones de diseño y lecciones aprendidas (bugs reales que explican el código)

1. **Dos entornos con confirmación literal** — se editó producción creyendo que era pruebas.
2. **Test deployment como URL** → la app no arrancaba; siempre una implementación versionada.
3. **Se borró al administrador** → el cargo vive en `es_admin` (no en el rol), se revalida contra la Sheet, nadie puede eliminarlo (hay que transferir), y existe `restaurar_administrador`.
4. **Al pasar al admin a rol docente perdió acceso a los datos** → se separó `esDirectivo_` de `puedeSupervisar_`.
5. **Login de usuario "1" imposible** (Sheets → número) → normalización de usuario.
6. **Duplicados por doble clic / timeout** → planeación única por curso+fecha, con guardado idempotente.
7. **Informe mostraba 3 semanas con 4 clases** (agrupaba por `día/7`) → ahora cada clase es una semana por orden de fecha; el mismo criterio en pantalla y en el documento.
8. **Cuenta de cobro por la mitad** → nacieron las *Actividades* (8 de las 16 horas de un mes eran reuniones/informes).
9. **Fichas de estudiante duplicadas** ("Ana Pérez" en dos cursos) → separación Estudiantes/Inscripciones y reuso por nombre normalizado.
10. **Ids reutilizados** (max+1) → al borrar una planeación/curso se limpia su historial de revisión para que no lo herede otra.
11. **Latencia de Apps Script (2–3 s/llamada)** → `batch`, precarga, caché de handles y agrupar lecturas en el backend, listas en modo `resumen`.
12. **Respuestas cruzadas bajo carga** → validación de forma de respuesta y reintento en lecturas.
13. **Mes cerrado** → evita que cambie lo ya cobrado; con excepciones controladas por dirección.
14. **Fotos**: de 1 a 3 por clase; se mantiene `foto_clase_drive_id` (la primera) por compatibilidad con informes y planeaciones viejas.
15. **Compatibilidad hacia atrás**: el backend acepta `fotos.foto_clase` (formato viejo) y `fotos.fotos_clase` (nuevo) porque conviven versiones del cliente.

---

## 13. Limitaciones y deuda técnica conocidas (sé honesto con esto)

**Del diseño (Sheets + Apps Script):**
- **Escalabilidad:** cada lectura recorre pestañas completas. Con ~20 usuarios y algunos meses de datos anda; con cientos de usuarios/años de historia se volvería lento. Apps Script tiene **cuotas y límites de tiempo de ejecución** (verificar los valores vigentes en la documentación de Google; cambian).
- **Sin transacciones reales:** solo `LockService` (bloqueo global del script). Borrados en cascada dependen del orden y de que no falle a mitad.
- **Latencia inherente** de 2–3 s por llamada y guardados con fotos de 13–30 s.
- **Sin notificaciones:** el backend no envía correos ni usa *triggers* (no hay `MailApp`/`GmailApp`/`ScriptApp`). Los avisos son solo dentro de la app (campanita/aviso al entrar).
- **Dependencia total de una cuenta de Google:** el script se ejecuta "como el usuario que despliega"; si esa cuenta pierde acceso, se suspende o cambia el dominio, la app cae. La Sheet y Drive viven en esa cuenta.

**De seguridad (revisar antes de reutilizar con otro cliente):**
- Hash `SHA-256 + salt` de un solo paso, **no** bcrypt/argon2/PBKDF2 (Apps Script no trae uno nativo; existen alternativas con librerías). No hay límite de intentos de login.
- La URL del Web App es pública ("Anyone anonymous"); toda la seguridad está en `login()` y los tokens en caché.
- Los tokens de sesión viven en `CacheService` (~8 h); no hay revocación explícita salvo expiración.
- La **URL de producción está escrita en `client/src/config.py`** y versionada en git (no es un secreto criptográfico —hay que hacer login—, pero sí un dato que conviene sacar a configuración).
- Las fotos y documentos son "cualquiera con el enlace puede ver" (decisión de comodidad del piloto).
- Datos sensibles (cédula, cuenta bancaria) en texto plano en la Sheet.

**De ingeniería:**
- **No hay pruebas automatizadas** (ni unitarias ni de integración); existe `simulacro_mes.py` que se corre a mano contra el backend real.
- **Solo Windows** (uso de `pywin32`, `os.startfile`, instalador Inno Setup, rutas). El código tiene ramas para macOS/Linux en algunos puntos pero no está probado.
- Mucha lógica de negocio está **hardcodeada al programa**: mínimos de palabras, 4 clases al mes, 8 h externas, dos colores fijos (verde/morado), nombres de coordinadoras en comentarios, textos institucionales.
- Pantallas viejas con colores locales duplicados frente a `tema.py`.
- Comentarios citan una "spec" que no está en el repo.
- Convención mixta de nombres en la API (`login`, `cambiarPassword` vs `snake_case`).
- `client/build/` y `client/dist/` (artefactos de PyInstaller) están en el disco, no en git.

---

## 14. Qué es específico de Generación-I (lo que habría que cambiar para otro contexto)

| Elemento | Dónde está | Qué implica cambiarlo |
|---|---|---|
| Membrete, escudo, código `PC-PA-003-F03`, pie de página, correos institucionales | `scripts/_membrete_municipio.py`, `templates/assets/escudo_municipio.jpg`, plantillas `.docx` | Regenerar plantillas con otro membrete. El escudo/formatos son del municipio, no del autor de la app. |
| Formato "Diario Pedagógico" (3 momentos, evaluación de la clase) | `Validation.js`, `Planeaciones.js`, plantilla, `planeacion_screen.py` | Es el corazón del formulario; otro formato pedagógico = rehacer validación, formulario y plantilla. |
| Reglas numéricas (§7.1) | `Validation.js`, `Cierre.js` | Cambiar constantes; algunas se repiten en el cliente (p. ej. 80 palabras en `informe_screen.py`, 20 en `widgets.py`). |
| Modelo de pago por hora con "cuenta de cobro" | `Informes.js`, `NumeroALetras.js`, plantillas | Si el nuevo cliente no paga por hora, esa parte sobra. |
| Revisión por color verde/morado | `Revisiones.js`, `Config`, `Cursos.js` | Generalizable a N revisores/áreas, pero hoy son exactamente dos claves. |
| Certificado de pago, informe de asistencia (pedido de la Secretaría de Educación) | `Certificados.js`, `Asistencia.js` | Específicos del trámite municipal. |
| Nombre "Generación-I", logos, íconos | `templates/assets/`, `config`, `.iss` | Cambiar marca. Íconos de cohete/estrella son Twemoji (CC-BY 4.0, requiere atribución). |
| Zona horaria `America/Bogota`, textos en español de Colombia, diccionario `es_CO` | `appsscript.json`, `DateUtils.js`, `assets/diccionario` | Para otro país: zona, moneda (`toLocaleString('es-CO')`), número a letras, diccionario. |
| Datos reales | Sheet de producción, Drive, carpeta `Estructura/` (no versionada) | **No forman parte de "la app"**: son de la organización/las personas. |

---

## 15. Guía para responder "¿puedo hacer X?" (portabilidad)

> **Advertencia para el asistente:** aquí solo se describe el lado técnico. Si el usuario habla de llevarse la aplicación a otro lugar o a otra organización, recuérdale —sin dramatizar— que la **titularidad y el derecho de uso del código, de las plantillas/formatos oficiales, de la marca y de los datos** dependen de su contrato o acuerdo con la organización y con el municipio, y que eso hay que confirmarlo con ellos (o con un abogado) antes de reutilizar. Los datos personales de docentes y estudiantes (cédulas, cuentas bancarias, nombres de menores) no deben salir de la organización.

**Lo que técnicamente se puede llevar / reutilizar tal cual:** la arquitectura, el patrón cliente/servidor sobre Apps Script, `api_client.py`, el patrón de hilos + overlay + caché, el sistema de roles/permisos, el flujo de revisión con historial, el cierre de mes, el sistema de versiones obligatorias/opcionales, `entorno.js` (guardas de producción), la lógica de generación con docxtpl, y los scripts de construcción de plantillas (cambiando el membrete).

**Escenarios típicos y qué implican:**

1. **Usarlo para otra organización educativa parecida (misma idea, distinto cliente).** Viable. Necesita: su propio proyecto de Apps Script + Sheet + Drive (ver §11.1), nuevas plantillas con su membrete, revisar las reglas numéricas (§7.1) y el modelo de pago. Trabajo estimado: medio; lo más laborioso son las plantillas y ajustar validaciones/formatos.
2. **Venderlo como producto a varios clientes (multi-organización).** Hoy es **de una sola organización por despliegue** (una Sheet = una organización, sin columna de "organización"). Multi-cliente = un despliegue por cliente (viable, simple, pero operativamente pesado: N proyectos de Apps Script, N instaladores/URLs) o rediseñar con una base de datos real y multitenancy (trabajo grande).
3. **Migrar la base de datos de Sheets a algo "de verdad" (PostgreSQL, Firebase, Supabase...).** Viable y es el cambio con más sentido si crece. Impacto: reescribir el backend (las ~4,9 mil líneas de JS) pero **el cliente casi no cambia** si se conserva el mismo contrato `{action, params}` → `{ok, data}` — esa fue la intención del diseño. Lo que Sheets daba gratis (que el equipo edite datos a mano) se pierde y habría que darle una herramienta de administración.
4. **Convertir la app de escritorio en web.** Viable, pero es una **reescritura del cliente** (toda la carpeta `ui/`). La lógica de negocio del backend se reutiliza. La generación de `.docx` tendría que pasar a un servidor (docxtpl en Python/Node) porque Apps Script no puede. Ventaja: cero instalación y actualizaciones instantáneas.
5. **Que funcione en Mac/Linux.** Difícil pero no imposible: quitar `pywin32`/`os.startfile`, otro empaquetado, probar `customtkinter` allí. Hoy no está probado.
6. **Notificaciones por correo/WhatsApp** (recordatorios de entrega, aviso de devolución). No existe hoy. Apps Script sí puede enviar correo y programar *triggers*; agregar avisos es un cambio pequeño-mediano en el backend.
7. **Modo offline.** No existe; todo requiere internet (solo el corrector ortográfico es local). Agregarlo implica cola local de escrituras y resolución de conflictos: cambio grande.
8. **Endurecer seguridad** (mejor hash, límite de intentos, roles más finos, cifrado de datos sensibles). Viable en el backend; ver §13.
9. **Cambiar el modelo de pago o de revisión** (más de 2 revisores, otro cálculo de horas). Viable; está concentrado en `Informes.js`, `Revisiones.js`, `Validation.js`.
10. **Seguir usándolo sin Generación-I pero con los mismos datos.** Los datos viven en la Sheet/Drive de la cuenta de la organización, no en el código. Sin esa cuenta, la app no tiene backend. Un desarrollador necesitaría montar un backend nuevo con su propia Sheet.

**Lo que NO se puede / no conviene (resumen):**
- No se puede quitar la dependencia de Google sin reescribir el backend.
- No se puede tener PDF garantizado en todos los equipos (depende de Word/LibreOffice instalado).
- No se debe reutilizar el escudo, los códigos de trámite ni los formatos oficiales fuera del contexto autorizado por el municipio.
- No conviene escalar a cientos de usuarios sin cambiar la base de datos.
- No hay pruebas automáticas: cualquier cambio grande debe validarse con el simulacro y en el entorno de pruebas primero.

---

## 16. Glosario

- **Apps Script / clasp:** entorno de Google para correr JavaScript en su nube; `clasp` es su herramienta de línea de comandos para subir código.
- **Web App:** un Apps Script publicado con una URL que acepta peticiones HTTP.
- **Deployment / implementación:** una versión publicada del script con URL fija; se actualiza creando una *nueva versión* de la misma implementación.
- **Script Properties:** variables privadas del proyecto de Apps Script (aquí: `SHEET_ID`, `DRIVE_ROOT_FOLDER_ID`).
- **docxtpl:** librería de Python que rellena plantillas Word con marcas tipo Jinja (`{{ variable }}`, `{% for %}`).
- **Núcleo:** agrupación de cursos del programa (la revisión de dirección se piensa por núcleo entregado completo).
- **Curso:** unidad de trabajo; un docente puede tener varios; el informe, los estudiantes y las planeaciones cuelgan del curso.
- **Horas en sede / horas externas:** *dónde* se hizo; se pagan igual. En la app las clases son "horas en sede" y el resto de actividades "horas externas".
- **Horas de gestión:** horas de un directivo por tareas administrativas (con foto y entregable).
- **Cuenta de cobro:** documento (incluido en el informe mensual) con el valor a pagar por las horas del mes.
- **Diario Pedagógico:** el formato oficial de planeación de clase del programa (`PC-PA-003-F03`).
- **Telón:** pantalla verde de arranque mientras se verifica la versión.
- **Simulacro:** script que reproduce un mes completo de uso contra el backend.

---

## 17. Cómo pedirle ayuda a este chat con esta app

El asistente **no ve el código**. Para preguntas de detalle, el usuario puede pegar archivos concretos. Los más útiles según el tema:
- Reglas de negocio y validaciones → `backend/src/Validation.js`, `Cierre.js`, `Revisiones.js`
- Cómo se calcula un pago → `backend/src/Informes.js`, `Certificados.js`, `InformesGestion.js`
- Permisos → `backend/src/Auth.js`, `Usuarios.js`
- Datos y columnas → `backend/src/SetupSheets.js`
- Contrato con el cliente → `backend/src/Main.js`, `client/src/api_client.py`
- Generación de documentos → `client/src/services/docx_generator.py`, `scripts/construir_plantilla_*.py`
- Despliegue → `backend/README.md`, `backend/entorno.js`, `client/README.md`, `client/GeneracionI-Planeaciones.iss`

*Fin del documento.*
