# Cliente (escritorio, Python)

## Desarrollo

```bash
pip install -r requirements.txt
```

Configurar `src/config.py` con la URL real del Web App de Apps Script
(`BACKEND_URL`) antes de correr.

```bash
cd src
python main.py
```

## Qué construye cada quién (spec sección 8)

- **`ui/`** — pantallas Tkinter/customtkinter. Es la parte que arma
  Generación-I: login, formulario de planeación por bloques, checklist de
  asistencia, dashboard directivo, mockup con logo/eslogan. Lo que hay hoy
  (`login_screen.py`, `home_screen.py`, `app.py`) es un punto de partida
  funcional, no el diseño final.
- **`api_client.py`, `services/`, `config.py`, `main.py`** — lógica de
  backend/documentos (Samir + Claude Code). Las pantallas de `ui/` deberían
  llamar solo a las funciones de `api_client` y nunca tocar `requests`,
  `docxtpl` o credenciales directamente.

## Empaquetar como ejecutable

```bash
pyinstaller --noconfirm --onefile --windowed ^
  --add-data "../../templates;templates" ^
  --name GeneracionI-Planeaciones ^
  src/main.py
```

`--add-data` es necesario para que las plantillas .docx viajen dentro del
.exe (ver `config.TEMPLATES_DIR`, que resuelve la ruta distinto si la app
está empaquetada).
