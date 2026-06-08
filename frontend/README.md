# Frontend React

Prototipo local de React para consumir la API read-only.

## Configuracion

Crear `frontend/.env` si quieres sobrescribir la URL de API:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Existe `frontend/.env.example` con el valor por defecto.

## Ejecucion local

1. Levantar la API:

```powershell
cd ..
.\.venv\Scripts\Activate.ps1
python -m pip install python-multipart
python -m uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000
```

2. Levantar el frontend:

```powershell
cd frontend
npm.cmd run dev -- --host 127.0.0.1 --port 5174
```

3. Abrir:

- Frontend: `http://127.0.0.1:5174`
- API docs: `http://127.0.0.1:8000/docs`

## Scripts utiles

- `npm.cmd run lint`
- `npm.cmd run build`
