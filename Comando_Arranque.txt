Modo desarrollo con recarga en caliente:
cd frontend
npm.cmd run dev

Backend en otra terminal:
python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000

Modo validacion del bundle:
python .\scripts\run_react_desktop_dev.py --build
