# Release Checklist

Fecha:
- [ ] YYYY-MM-DD

Responsable:
- [ ] Nombre/equipo

## 1) Preparacion de entorno

- [ ] Rama objetivo sincronizada con `origin/main`.
- [ ] Dependencias Python instaladas: `python -m pip install -r requirements.txt`.
- [ ] Dependencias frontend instaladas: `cd frontend && npm install`.
- [ ] Carpeta local de backups disponible (`data/backups/`).

## 2) Backup previo obligatorio

- [ ] Ejecutar backup local antes de cualquier accion destructiva:
  - `.\scripts\backup-db.ps1 -Tag "pre-release"`
- [ ] Confirmar que el archivo `.db` se creo en `data/backups/`.

## 3) Gates tecnicos

- [ ] Ejecutar gate completo:
  - `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-gates.ps1`
- [ ] Resultado esperado: `pytest` verde, `integrity_check = ['ok']`, `npm run lint` verde y `npm run build` verde.

## 4) Smoke tests minimos

- [ ] API:
  - `python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000`
  - verificar `GET /health` -> `200`.
- [ ] Frontend:
  - `cd frontend && npm run dev -- --host 127.0.0.1 --port 5173 --strictPort`
  - abrir `http://127.0.0.1:5173` y validar carga de vistas principales.
- [ ] Desktop:
  - `python run.py`
  - validar apertura de ventana y navegacion basica.

## 5) Cierre de release

- [ ] `git status` limpio.
- [ ] Commits agrupados por bloque (backend/frontend/docs/scripts).
- [ ] PR creada en GitHub con resumen tecnico y evidencia de gates.
- [ ] No se incluyen datos sensibles: `data/*.db`, `data/backups/`, `runtime/`, exports reales, claves o tokens.

## 6) Evidencias (rellenar)

- [ ] SHA release:
- [ ] URL PR:
- [ ] Resultado gates:
- [ ] Ruta backup generado:
