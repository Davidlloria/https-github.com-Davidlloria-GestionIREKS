@echo off
setlocal

cd /d "%~dp0"

rem Prefer the sibling data folder after migration; explicit overrides take precedence.
if not defined GESTION_IREKS_DATA_DIR (
    if exist "%~dp0..\GestionIREKS-Datos\gestion_ireks.db" (
        set "GESTION_IREKS_DATA_DIR=%~dp0..\GestionIREKS-Datos"
    )
)

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run.py
) else (
    python run.py
)

if errorlevel 1 (
    echo.
    echo El arranque ha fallado con codigo %errorlevel%.
    pause
)

endlocal
