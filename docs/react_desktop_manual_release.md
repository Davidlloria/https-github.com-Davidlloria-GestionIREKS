# React + FastAPI manual release guide

## Scope

This guide describes the manual steps to build, package, test, and hand over the Windows bundle for the React + FastAPI desktop app.

It applies to the PyInstaller onedir bundle produced by the current launcher spike.

## Build

1. Build the frontend:

```powershell
cd frontend
npm.cmd run build
```

2. Build the PyInstaller bundle:

```powershell
cd ..
python .\scripts\build_react_desktop_pyinstaller.py
```

## Deliverable

Deliver this folder as the release artifact:

```text
dist\react_desktop_pyinstaller\GestionIREKSReactDesktop\
```

Do not deliver only the executable.

The release folder must stay together with:

```text
data\gestion_ireks.db
_internal\...
```

If you move only `GestionIREKSReactDesktop.exe`, the app will not have the runtime files it needs.

## Start

Launch the bundled app from the release folder:

```powershell
.\GestionIREKSReactDesktop.exe
```

Optional override for the database location:

```powershell
$env:GESTION_IREKS_DATA_DIR = "E:\path\to\data"
.\GestionIREKSReactDesktop.exe
```

The override directory must contain `gestion_ireks.db`.

## Stop

- Use `Ctrl+C` in the terminal running the app.
- Confirm that ports `8000` and `5173` are released after shutdown.

## Manual validation checklist

- `data\gestion_ireks.db` exists next to the release folder or in the override directory.
- `gestion_ireks.db` size is greater than 0 bytes.
- The executable starts without errors.
- `GET http://127.0.0.1:8000/health` returns `200`.
- `GET http://127.0.0.1:8000/sales/annual-summary/years` returns `200`.
- `GET http://127.0.0.1:5173/` returns `200`.
- The six React tabs load:
  - Ventas
  - Recetas
  - Cursos
  - Ingredientes
  - Clientes
  - Almacén
- `Ctrl+C` closes the API and frontend servers.
- Ports `8000` and `5173` are free afterward.

## Troubleshooting

- `no such table`: the executable is reading the wrong database, a zero-byte database, or no database at all.
- `Failed to fetch`: check the API first with `curl.exe -i http://127.0.0.1:8000/health`.
- Port already in use: close the previous app instance before starting a new one.
- Windows Defender or SmartScreen blocks the exe: only run the bundle generated locally from this repo.
- Moving only the exe breaks the app: keep the whole release folder together.

## Notes

- The bundle is still a manual release flow, not a formal installer.
- The launcher remains the source of truth for startup and shutdown behavior.
- The release process does not add mutating endpoints or change the UI.
