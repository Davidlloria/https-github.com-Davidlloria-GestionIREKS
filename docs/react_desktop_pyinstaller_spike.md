# PyInstaller spike

## Scope

This spike checks whether the current React + FastAPI launcher can be packaged with PyInstaller on Windows without introducing Electron, Tauri, or the legacy PySide6 app.

## What changed

- The launcher now has a frozen-runtime path.
- In source mode it keeps the current subprocess-based behavior.
- In bundled mode it starts:
  - the FastAPI app in-process with `uvicorn`;
  - the React static server in-process with `ThreadingHTTPServer`.
- The bundle expects `frontend/dist` to be included as `frontend/dist` inside the PyInstaller runtime tree.
- A minimal PyInstaller spec was added.
- A small build wrapper script was added.

## How to build

1. Build the frontend:

```powershell
cd frontend
npm.cmd run build
```

2. Build the PyInstaller bundle:

```powershell
python .\scripts\build_react_desktop_pyinstaller.py
```

Expected output:

- `dist/react_desktop_pyinstaller/GestionIREKSReactDesktop/`

## Notes

- This is an onedir spike, not a final installer.
- The launcher remains the source of truth.
- `--build` stays available only in source mode.
- The bundle is intentionally not optimized for size.

## Commands validated

- `npm.cmd run lint`
- `npm.cmd run build`
- `npm.cmd run test`
- `python -m pytest tests/test_react_desktop_launcher.py -q`

## Current risk

- PyInstaller may still need hidden imports if runtime modules are missed during analysis.
- The bundled app depends on the packaged `frontend/dist` tree being present.
