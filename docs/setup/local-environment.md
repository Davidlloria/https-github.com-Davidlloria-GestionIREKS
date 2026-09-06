# Entorno local y runtime

Este documento fija la instalacion minima para desarrollo y la politica de
configuracion local. No sustituye a la checklist de release; la complementa.

## Requisitos base

- Windows 10/11 con PowerShell.
- Python 3.12.
- Node.js 20 LTS o superior compatible con Vite 5.
- Git.
- Tesseract solo si se van a usar flujos OCR de albaranes/facturas.

## Instalacion Python

Desde la raiz del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

La carpeta `.venv/` queda fuera de Git.

## Instalacion frontend

Desde la raiz del proyecto:

```powershell
cd frontend
npm ci
```

Usar `npm ci` cuando exista `package-lock.json` para reproducir las versiones
bloqueadas. Usar `npm install` solo cuando se vaya a modificar dependencias.
`node_modules/` queda fuera de Git por ser artefacto local.

## Configuracion local

### Datos externos para PySide6

La instalacion local utiliza dos carpetas hermanas:

```text
Proyectos/
    GestionIREKS/        # codigo, recursos y entorno Python
    GestionIREKS-Datos/  # bases, configuracion, imagenes, exports y backups
```

`GESTION_IREKS_DATA_DIR` apunta a la carpeta de datos. La variable de usuario
se aplica a las nuevas terminales; reinicia las terminales abiertas antes de
ejecutar `python run.py`. `run-desktop.bat` tambien selecciona la carpeta
hermana cuando contiene `gestion_ireks.db` y no hay un override explicito.

La migracion local del 2026-09-06 copio y verifico 168 archivos, comprobo la
integridad y los recuentos de las dos bases SQLite, y ajusto la preferencia
de exportacion que apuntaba al antiguo `data`. El original `GestionIREKS/data`
se conserva como copia anterior a la migracion; no se sincroniza con los datos
activos. No volver a usarlo como base activa sin revisar los cambios posteriores.

Las rutas relativas de imagenes se resuelven desde la carpeta externa. Los
logos, estilos y plantillas distribuidos con el programa siguen en `assets`.
La biblioteca de documentos fuente mantiene su ubicacion independiente;
su indice `document_library.sqlite` se copia con los datos.

Si cambia la ubicacion, actualizar la variable y revisar las rutas absolutas
de configuracion. Con la app cerrada, una vuelta atras requiere primero
conservar los datos externos actuales y elegir explicitamente la carpeta
que contiene la base que se desea utilizar. Las copias en el mismo disco no
sustituyen un backup en otra unidad.

Los datos y secretos locales no se versionan:

- `data/*.db`
- `data/*.json`
- `data/backups/`
- `data/exports/`
- `runtime/`
- `.env`
- `frontend/.env`

Variables y ficheros relevantes:

| Clave | Donde se usa | Uso |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `frontend/.env` o entorno del proceso Vite | URL de la API para React. Por defecto `http://127.0.0.1:8000`. |
| `USE_QML_CUSTOMERS` | entorno del proceso Python | Activa la pagina QML experimental de clientes con `1`, `true`, `yes` u `on`. Desactivada por defecto. |
| `FDC_API_KEY` | entorno del proceso Python | Fallback para consultas FDC si no se configura desde la pantalla/API de configuracion. |
| `FATSECRET_CLIENT_ID` | entorno o `.env` de la raiz | Credencial FatSecret. |
| `FATSECRET_CLIENT_SECRET` | entorno o `.env` de la raiz | Credencial FatSecret. |
| `FATSECRET_SCOPE` | entorno o `.env` de la raiz | Scope FatSecret; por defecto `basic`. |
| `TESSERACT_CMD` | entorno del proceso Python | Ruta explicita a `tesseract.exe` si no se usa runtime local ni instalacion del sistema. |
| `TESSDATA_PREFIX` | entorno del proceso Python | Ruta a `tessdata` cuando la deteccion automatica no la encuentre. |

Plantillas disponibles:

- `.env.example`: fallback FatSecret leido por `FatSecretClient`.
- `frontend/.env.example`: URL de API para Vite.

El resto de claves de proveedores (`fdc`, `openai`, `fatsecret`,
`orders_mail`, `warehouse`) se guarda desde Configuracion/API en
`data/api_config.json`, que queda ignorado por Git.

## Tesseract

Politica actual: los binarios de Tesseract no se versionan. `runtime/` queda
ignorado porque puede contener binarios pesados y dependencias de maquina.

Opciones soportadas:

1. Instalar Tesseract en Windows, por ejemplo en `C:\Program Files\Tesseract-OCR`.
2. Definir `TESSERACT_CMD` apuntando a un `tesseract.exe` local.
3. Copiar una distribucion portable en `runtime/tesseract/Tesseract-OCR/`.

Estructura portable admitida:

```text
runtime/
  tesseract/
    Tesseract-OCR/
      tesseract.exe
      tessdata/
        eng.traineddata
        spa.traineddata
```

La aplicacion intenta resolver Tesseract en este orden:

1. `TESSERACT_CMD`.
2. `runtime/tesseract` dentro de un bundle PyInstaller.
3. `runtime/tesseract` junto al `.exe`.
4. `runtime/tesseract` dentro del proyecto.
5. Instalaciones normales de Windows.

Para una entrega, adjuntar o descargar Tesseract fuera del repositorio y dejar
registrada la version usada en las notas de release.

## Validacion

Despues de preparar el entorno:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\check-local-env.ps1
```

Si una entrega depende de OCR:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\check-local-env.ps1 -RequireTesseract
```

Despues ejecutar el gate completo:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-gates.ps1
```

Para desarrollo local:

```powershell
.\scripts\start-dev.ps1
```
