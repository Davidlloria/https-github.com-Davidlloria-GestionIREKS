# React + FastAPI packaging spike

## 1. Estado actual

- La app actual se ejecuta con `scripts/run_react_desktop_dev.py`.
- El launcher:
  - arranca `uvicorn` para la API;
  - arranca `python -m http.server` para `frontend/dist`;
  - abre el navegador por defecto;
  - tiene `--build`, `--exit-after-start`, `--hold-seconds` y `--no-open-browser`;
  - limpia procesos en `Ctrl+C` en Windows.
- El frontend ya está cerrado en seis pantallas read-only:
  - `SalesPage`
  - `RecipesPage`
  - `CoursesPage`
  - `IngredientsPage`
  - `CustomersPage`
  - `WarehousePage`
- El repo no tiene un `package.json` en la raíz; el frontend vive en `frontend/package.json`.
- No hay una capa de packaging distribuible todavía. Hoy el flujo sigue siendo de desarrollo local.

## 2. Opciones evaluadas

### Mantener launcher Python + navegador local

Pros:
- Cero cambios de arquitectura.
- Es lo más estable con el estado actual del repo.
- Ya está validado en Windows.
- Conserva el shutdown limpio.

Contras:
- No resuelve distribución para usuario no técnico.
- Sigue requiriendo Python y un navegador en la máquina destino.
- El frontend y la API siguen dependiendo de que el entorno local esté preparado.

### PyInstaller sobre el launcher Python

Pros:
- Es la ruta incremental más natural para este repo.
- Mantiene el launcher actual, la API FastAPI y el frontend estático.
- No obliga a introducir un nuevo shell ni a reescribir UI.
- Encaja bien con Windows y con el modelo actual de procesos.
- Permite distribuir un ejecutable o carpeta empaquetada sin cambiar el producto funcional.

Contras:
- Sigue habiendo que empaquetar dependencias Python y assets estáticos.
- Puede requerir ocultar/importar módulos de `uvicorn`, `fastapi` y dependencias transitivas.
- Hay que cuidar rutas a `frontend/dist` y al `app` empaquetado.
- El tamaño final no será pequeño.

### Electron como shell

Pros:
- Buen encaje para un producto desktop distribuible.
- Facilita empaquetado y experiencia de usuario final.

Contras:
- Introduce una nueva plataforma de shell con más dependencias.
- Obliga a mantener un runtime Node/Electron adicional.
- Aumenta la complejidad del repo y la superficie de mantenimiento.
- Para este estado del proyecto es un salto grande respecto al launcher actual.

### Tauri como shell

Pros:
- Puede dar binarios más pequeños que Electron.
- Buena orientación a desktop distribuible.

Contras:
- Añade Rust/toolchain y una integración nueva.
- Requiere una decisión de arquitectura más amplia que este spike.
- No aporta una ventaja clara frente a PyInstaller para el estado actual del repo.

### PySide6 WebEngine como shell

Pros:
- Encaja con el ecosistema Python ya existente.
- No introduce un shell completamente nuevo fuera de Python/Qt.

Contras:
- Añade Qt WebEngine, que es pesado.
- El repo ya tiene una app PySide6 legacy; mezclar el nuevo empaquetado con esa capa aumenta el riesgo de acoplamiento.
- No es la ruta más limpia si la meta es distribuir solo la experiencia React + FastAPI.

## 3. Recomendación

La mejor ruta para este repo es **PyInstaller sobre el launcher Python actual**.

Razón principal:
- Es el menor salto técnico desde el estado actual.
- Reutiliza el comportamiento que ya funciona y ya se validó en Windows.
- Evita una migración prematura a Electron/Tauri.
- No toca la app PySide6 legacy.

Orden de preferencia realista:
1. Mantener el launcher actual como baseline de desarrollo.
2. Añadir un empaquetado PyInstaller del launcher.
3. Solo si el empaquetado Python se vuelve frágil o demasiado pesado, reevaluar Electron o Tauri.

## 4. Siguiente paso implementable

El siguiente paso útil no es migrar la app a otro shell.
Es preparar un spike de empaquetado mínimo para PyInstaller:
- construir `frontend/dist`;
- empaquetar el launcher Python;
- copiar `frontend/dist` dentro del bundle o distribuirlo junto al ejecutable;
- validar arranque y apagado en Windows.

No se implementa aquí porque ya cruza la línea de "evaluación" y entra en empaquetado real.

## 5. Riesgos

- `PyInstaller` puede requerir configuración de imports ocultos para `uvicorn`/`fastapi`.
- Las rutas a `frontend/dist` cambian al empaquetar; hay que resolverlas de forma explícita.
- El bundle puede crecer bastante.
- Si se decide más adelante empaquetar también Node/frontend runtime, el proceso se complica.
- La app legacy PySide6 debe mantenerse aislada para no mezclar responsabilidades.

## 6. Comandos probados

- `python -m pytest tests/test_react_desktop_launcher.py -q`
- `python -m pytest tests/test_api_customers_contacts.py tests/test_api_customers_openapi_contract.py tests/test_api_courses.py tests/test_api_courses_openapi_contract.py tests/test_api_ingredients.py tests/test_api_ingredients_openapi_contract.py tests/test_api_orders_openapi_contract.py tests/test_api_recipes.py tests/test_api_recipes_openapi_contract.py tests/test_api_sales_annual_summary.py tests/test_api_sales_openapi_contract.py tests/test_api_warehouse_openapi_contract.py tests/test_architecture_boundaries.py -q`
- `cd frontend && npm.cmd run lint`
- `cd frontend && npm.cmd run build`
- `cd frontend && npm.cmd run test`

## 7. Conclusión

Este spike no deja un empaquetado completo, pero sí una dirección clara:

- **recomendado**: PyInstaller sobre el launcher Python actual;
- **no recomendado como siguiente paso**: migrar a Electron o Tauri;
- **evitar**: tocar la app PySide6 legacy para este objetivo.
