# Backend (Google Apps Script)

## Dos entornos, nunca uno ambiguo

Hay DOS proyectos de Apps Script separados, cada uno con su propia Sheet y
carpeta de Drive:

- **pruebas** — una copia, sin datos reales. Acá se prueba todo primero.
- **real** — producción. Lo usan los profes y directivos todos los días.

Nunca hay un `.clasp.json` suelto apuntando a "el que sea" — cada comando
pide explícitamente `prueba` o `real`, arma `.clasp.json` al vuelo con el
scriptId correcto, corre clasp, y lo borra apenas termina (ver
`entorno.js`). Empujar a `real` además pide escribir una confirmación
literal. Así no puede pasar de nuevo lo que pasó una vez: creer que se
estaba editando el de pruebas y en realidad ser el real.

## Puesta en marcha (una sola vez, sobre la cuenta Workspace institucional)

```bash
npm install
npm run login          # abre el navegador, inicia sesión con la cuenta institucional
cp entornos.json.example entornos.json
```

Completá en `entornos.json` (no se versiona) el `scriptId` de cada
proyecto — Project Settings > IDs del proyecto de secuencia de comandos, en
el editor de cada uno. Si el de pruebas todavía no existe, se crea una vez
haciendo "Archivo > Hacer una copia" del proyecto real en el editor de
Apps Script, y esa copia le da su propio scriptId, Sheet y carpeta de
Drive.

## Configurar Script Properties

En cada editor de Apps Script (`npm run prueba:abrir` / `npm run
real:abrir`): Project Settings > Script properties, agregar:

- `SHEET_ID` — id de la Google Sheet que hace de base de datos (la copia
  para pruebas, la real para real)
- `DRIVE_ROOT_FOLDER_ID` — id de la carpeta raíz dedicada en Drive

## Crear las pestañas de la Sheet

En el editor, seleccionar la función `setupSheets` en el desplegable de
funciones y darle Run. Es seguro volver a correrla si se agrega una columna
nueva al esquema.

## Desplegar como Web App

Deploy > New deployment > Web app. Ejecutar como el usuario que despliega,
acceso "Anyone" (el control de acceso real lo hace `login()` con su propio
token, no el acceso a la URL). Guardar la URL del deployment — la necesita
el cliente Python (`GENERACIONI_BACKEND_URL` para pruebas, `_URL_PRODUCCION`
en `config.py` para real).

Actualizar código sin crear una implementación nueva (misma URL): en el
editor, Gestionar implementaciones > lápiz sobre la implementación
existente > Nueva versión > Implementar.

**Nunca uses una "Test deployment" (la que no pide elegir versión, sirve
@HEAD) como URL para el cliente.** Se ve tentadora porque no hay que
redesplegar después de cada push — pero Google solo la deja invocar a una
cuenta con sesión de navegador y permiso de edición sobre el proyecto; un
`requests.post` sin login (como hace `api_client.py`) recibe "No se
encontró la página" pase lo que pase. Esto ya pasó una vez: la URL de
pruebas quedó apuntando a esa deployment y la app no arrancaba con "El
servidor rechazó la conexión". La URL del cliente siempre tiene que ser
una implementación con versión fija (`Gestionar implementaciones`).

## Flujo de cambios

```bash
npm run prueba:push   # sube src/ al proyecto de PRUEBAS
# ... verificar ahí, redesplegar esa implementación, probar con la app ...
npm run real:push     # sube src/ al proyecto REAL — pide confirmación
```
