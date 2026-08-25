; Instalador de Generación-I — Planeaciones, armado con Inno Setup a partir
; del build de PyInstaller en modo carpeta (ver GeneracionI-Planeaciones.spec).
;
; Orden para publicar una versión nueva:
;   1. Subir APP_VERSION en client/src/config.py.
;   2. python -m PyInstaller GeneracionI-Planeaciones.spec --noconfirm
;      (desde la carpeta client/, con el venv activado) -> deja el build en client/dist/.
;   3. Compilar este .iss con Inno Setup (ISCC.exe o "Compile" en la app) ->
;      deja el .exe en client/dist/instalador/.
;   4. Subir ese .exe como asset del release en GitHub.
;   5. Publicar la versión desde la pantalla "Versión de la app".
;
; #MyAppVersion se pasa desde afuera (ISCC /DMyAppVersion=1.1.3) para no
; tener que editar este archivo en cada release; si se compila sin pasarlo,
; usa el valor por defecto de acá abajo.
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif

#define MyAppName "Generación-I — Planeaciones"
#define MyAppPublisher "Generación-I"
#define MyAppExeName "GeneracionI-Planeaciones.exe"

[Setup]
; AppId fijo: NO cambiar entre versiones — es lo que le permite a Windows
; reconocer una instalación anterior y actualizarla en vez de dejar dos
; entradas separadas en "Agregar o quitar programas".
AppId={{E5821168-C953-48F5-AE42-948DB3FA1B5F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; Sin privilegios de administrador: se instala en la carpeta del usuario,
; para que cualquier docente lo pueda instalar en su propia cuenta sin
; pedirle la contraseña de administrador a nadie.
PrivilegesRequired=lowest
OutputDir=dist\instalador
OutputBaseFilename=GeneracionI-Planeaciones-Setup
SetupIconFile=assets\icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "dist\GeneracionI-Planeaciones\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName}"; Flags: nowait postinstall skipifsilent
