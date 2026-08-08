# Backend (Google Apps Script)

## Puesta en marcha (una sola vez, sobre la cuenta Workspace institucional)

```bash
npm install
npm run login          # abre el navegador, inicia sesión con la cuenta institucional
cp .clasp.json.example .clasp.json
```

Si el proyecto de Apps Script ya existe, poné su `scriptId` en `.clasp.json`
(Project Settings > IDs del proyecto de secuencia de comandos, en el editor
de Apps Script) y corré `npm run pull` para traerlo. Si no existe todavía:

```bash
npx clasp create --title "Generación-i backend" --type webapp --rootDir src
```

## Configurar Script Properties

En el editor de Apps Script (`npm run open`): Project Settings > Script
properties, agregar:

- `SHEET_ID` — id de la Google Sheet que hace de base de datos
- `DRIVE_ROOT_FOLDER_ID` — id de la carpeta raíz dedicada en Drive

## Crear las pestañas de la Sheet

En el editor, seleccionar la función `setupSheets` en el desplegable de
funciones y darle Run. Es seguro volver a correrla si se agrega una columna
nueva al esquema.

## Desplegar como Web App

Deploy > New deployment > Web app. Ejecutar como el usuario que despliega,
acceso "Anyone" (el control de acceso real lo hace `login()` con su propio
token, no el acceso a la URL). Guardar la URL del deployment — la necesita
el cliente Python.

## Flujo de cambios

```bash
npm run push   # sube src/ al proyecto real de Apps Script
```
