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
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Para el frontend:

```powershell
cd frontend
npm ci
```

La guia completa de entorno local, variables y runtime esta en
`docs/local-environment.md`.

## Ejecucion

Aplicacion de escritorio:

```powershell
python run.py
```

Para activar experimentalmente la pagina de clientes en QML:

```powershell
$env:USE_QML_CUSTOMERS="1"
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

Arranque conjunto en dos ventanas de PowerShell, desde la raiz del proyecto:

```powershell
.\scripts\start-dev.ps1
```

Si necesitas autorecarga de API durante desarrollo:

```powershell
.\scripts\start-dev.ps1 -Reload
```

Detener API y frontend lanzados por el script:

```powershell
.\scripts\stop-dev.ps1
```

Backup de base de datos con nombre automatico (recomendado antes de tareas
destructivas o mantenimientos):

```powershell
.\scripts\backup-db.ps1
```

Backup con etiqueta de contexto:

```powershell
.\scripts\backup-db.ps1 -Tag "pre-mantenimiento"
```

Si PowerShell bloquea scripts por politica de ejecucion, usar:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\stop-dev.ps1 -Force
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\backup-db.ps1
```

## Validacion

Chequeo rapido de prerequisitos locales (Python/Node/npm y OCR opcional):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\check-local-env.ps1
```

Si la entrega requiere OCR (albaranes/facturas), forzar validacion de Tesseract:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\check-local-env.ps1 -RequireTesseract
```

Gate completo recomendado (incluye tests Python, reglas de arquitectura,
integridad de base de datos, lint y build frontend):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-gates.ps1
```

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

Reglas de arquitectura (incluidas en `pytest tests -q`):

```powershell
python -m pytest tests/test_architecture_boundaries.py -q
```

Checklist de release (operativa de entrega):

- `docs/release-checklist.md`

Entorno local y runtime:

- `docs/local-environment.md`
- `scripts/check-local-env.ps1`

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

Los overrides `.env` de la raiz y `frontend/.env` quedan ignorados por Git. Hay
plantillas sin secretos en `.env.example` y `frontend/.env.example`.

Tesseract se trata como runtime local: no se versionan sus binarios. Puede
usarse una instalacion del sistema, `TESSERACT_CMD` o una copia portable en
`runtime/tesseract/Tesseract-OCR/`.

Los endpoints API que reciben `source_path`, `file_path` o `destination_path`
usan rutas del sistema de archivos del servidor, no del navegador. Actualmente
solo se aceptan importaciones `.json` y `.pdf`, y backups `.db`; los archivos de
entrada deben existir y el destino de backup no puede ser un directorio.

Ademas, para pedidos/configuracion existen endpoints multipart de subida:
`/orders/import/json/upload`,
`/orders/{order_id}/import/albaran-pdf/upload`,
`/orders/{order_id}/import/factura-pdf/upload` y
`/settings/imports/orders-json/upload`.
La UI React usa estos endpoints upload por defecto.

## Git

Si Git marca el repositorio como propiedad dudosa en Windows, ejecutar:

```powershell
git config --global --add safe.directory E:/IREKS/APP/GestionIREKS
```

El flujo actual es trabajar en ramas cortas desde `main` sincronizada, subirlas
a GitHub y abrir Pull Request. La rama activa de endurecimiento API es:

```powershell
git switch api-hardening
```
