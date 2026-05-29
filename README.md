# Gestion IREKS

Aplicacion de gestion para clientes, contactos, ingredientes, recetas, pedidos,
almacen, cursos y documentacion interna de IREKS.

El proyecto esta en migracion desde una aplicacion de escritorio PySide6 hacia
una arquitectura con servicios reutilizables, API FastAPI y frontend React.

## Stack

- Python 3.12
- PySide6
- SQLModel / SQLite
- FastAPI / Uvicorn
- React / TypeScript / Vite
- ReportLab, PyMuPDF, Pillow y Tesseract para documentos

## Estructura

- `app/core`: configuracion, base de datos y migraciones SQLite.
- `app/models`: entidades SQLModel.
- `app/repositories`: acceso a datos.
- `app/services`: casos de uso, validaciones y transacciones.
- `app/viewmodels`: adaptacion legacy para la UI de escritorio.
- `app/ui`: interfaz de escritorio PySide6.
- `app/api`: API FastAPI.
- `app/schemas`: DTOs de entrada/salida para API.
- `frontend`: cliente React/Vite.
- `assets`: recursos visuales y plantillas.
- `data`: datos locales, configuracion y exports.
- `runtime`: dependencias empaquetadas, como Tesseract.
- `tests`: pruebas unitarias, contratos de API y reglas de arquitectura.

## Instalacion

Desde la raiz del proyecto:

```powershell
python -m pip install -r requirements.txt
```

Para el frontend:

```powershell
cd frontend
npm install
```

## Ejecucion

Aplicacion de escritorio:

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

Por defecto el frontend consume la API en `http://127.0.0.1:8000`.

## Validacion

Tests Python desde la raiz del proyecto:

```powershell
New-Item -ItemType Directory -Force .pytest_tmp
$env:TMP=(Resolve-Path .pytest_tmp).Path
$env:TEMP=$env:TMP
python -m pytest tests -q
Remove-Item -LiteralPath .pytest_tmp -Recurse -Force
```

Build y lint del frontend:

```powershell
cd frontend
npm run lint
npm run build
```

Integridad de base de datos:

```powershell
python -c "from app.core.database import run_integrity_check; print(run_integrity_check())"
```

Healthcheck de API:

```powershell
python -c "from fastapi.testclient import TestClient; from app.api.main import app; c=TestClient(app); print(c.get('/health').status_code, c.get('/health').json())"
```

## Estado actual

- Desktop PySide6 operativo como cliente principal legacy.
- Servicios separados de la UI y reutilizables desde API.
- API FastAPI disponible para clientes, contactos, ingredientes, pedidos,
  almacen y configuracion.
- Frontend React inicial con vistas de consulta para clientes, ingredientes y
  almacen.
- La hoja de ruta vive en `docs/migration-roadmap.md`.

## Datos y seguridad

`data/` puede contener base de datos real, exports, PDFs y configuraciones
locales. Revisar siempre antes de versionar o compartir. No commitear claves,
tokens, bases reales ni documentos sensibles.

## Git

Si Git marca el repositorio como propiedad dudosa en Windows, ejecutar:

```powershell
git config --global --add safe.directory E:/IREKS/APP/GestionIREKS
```

Usar una rama de trabajo para la migracion:

```powershell
git switch -c migration-ui-api-react
```
