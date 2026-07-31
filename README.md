# Gestion IREKS

Aplicacion de gestion para clientes, contactos, ingredientes, recetas, pedidos, almacen, cursos y documentacion interna de IREKS.

El proyecto esta en migracion desde una aplicacion de escritorio PySide6 hacia una arquitectura con servicios reutilizables, API FastAPI y frontend React.

## Stack

- Python 3.12
- PySide6
- SQLModel / SQLite
- FastAPI / Uvicorn
- React / TypeScript / Vite
- ReportLab, PyMuPDF, Pillow y Tesseract para documentos

## Estructura principal

- `app/`: desktop PySide6, servicios, modelos y API FastAPI
- `frontend/`: cliente React/Vite
- `assets/`: recursos visuales y plantillas
- `data/`: datos locales, configuracion y exports
- `runtime/`: dependencias locales como Tesseract
- `tests/`: pruebas unitarias, contratos y arquitectura
- `docs/`: documentacion del proyecto

## Primeros documentos a leer

- mapa documental: `docs/README.md`
- entorno local: `docs/setup/local-environment.md`
- roadmap de migracion: `docs/architecture/migration-roadmap.md`
- estado corto del trabajo: `docs/worklog/progress-log.md`

## Instalacion rapida

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Frontend:

```powershell
cd frontend
npm ci
```

## Ejecucion rapida

Desktop PySide6:

```powershell
python run.py
```

API FastAPI:

```powershell
python -m uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend React:

```powershell
cd frontend
npm run dev
```

## Validacion util

Tests Python:

```powershell
python -m pytest tests -q
```

Lint y build frontend:

```powershell
cd frontend
npm run lint
npm run build
```

## Datos y seguridad

`data/` puede contener base de datos real, exports, PDFs y configuraciones locales. No commitear claves, tokens, bases reales ni documentos sensibles.

## Git

Si Git marca el repositorio como propiedad dudosa en Windows:

```powershell
git config --global --add safe.directory E:/IREKS/APP/GestionIREKS
```
