# Roadmap de migracion UI / servicios / API

## Estado verificado

Revision local: 2026-05-29.

- Rama principal local sincronizada con `origin/main`.
- PR inicial de migracion fusionado en GitHub: `Merge pull request #1`.
- Rama activa para el siguiente bloque: `api-hardening`.
- La aplicacion de escritorio sigue entrando por `run.py` y `app/main.py`.
- `app/api` expone FastAPI con routers para clientes, contactos, ingredientes,
  pedidos, almacen y configuracion.
- `frontend` existe con React/Vite y consume la API para vistas de consulta de
  clientes, ingredientes IREKS y almacen.
- La base `data/gestion_ireks.db` existe, pasa `PRAGMA integrity_check` y queda
  fuera de Git.
- `orphan_contact_links = 0` tras backup y reparacion.
- `data/*.db`, `data/*.json`, `data/backups/`, `data/exports/` y `runtime/`
  quedan ignorados para evitar subir datos reales, secretos o binarios pesados.
- Validacion tras el bloque actual de Fase 2: `53 passed`, `npm run lint` y
  `npm run build`.

## Arquitectura objetivo

```text
React / FastAPI / desktop UI
        |
        v
app/services        Casos de uso y transacciones
        |
        v
app/viewmodels      Adaptacion legacy mientras se migra
        |
        v
app/repositories    Persistencia SQLModel
        |
        v
app/models          Entidades ORM
```

## Reglas de arquitectura

- No importar `Session`, `select`, `engine` ni `app.core.database` desde
  `app/ui`.
- No importar `PySide6` desde `app/services`.
- No reutilizar widgets ni viewmodels nuevos desde routers FastAPI.
- Crear metodos de servicio por caso de uso, no por evento visual.
- Mantener validaciones, normalizacion y transacciones en servicios.
- Dejar en UI solo formato visual, seleccion de filas, dialogos y mensajes.
- Toda respuesta API debe salir mediante DTOs de `app/schemas`, no mediante ORM.
- Cada endpoint de escritura debe tener al menos un test de contrato o de flujo.

## Bloques completados

1. Extraccion de logica de entidades simples a servicios.
2. Extraccion de pedidos, documentos, almacen, recetas e ingredientes IREKS/STD.
3. Separacion de operaciones de mantenimiento de base de datos usadas por
   configuracion.
4. Limpieza del bridge QML de clientes para que consuma `CustomerService`.
5. Creacion inicial de contratos DTO en `app/schemas` para clientes, contactos,
   ingredientes, pedidos, almacen, recetas y configuracion.
6. Adaptacion de `CustomerService` y `ContactService` con metodos
   serializables, manteniendo compatibilidad con desktop.
7. Creacion de `app/api` con FastAPI, dependencias de servicios y routers.
8. Tests de API con `TestClient` para CRUD basico y contratos de payload.
9. Routers de consulta y escritura para clientes, contactos, ingredientes,
   almacen, pedidos y configuracion.
10. Importacion JSON/PDF de pedidos desde API reutilizando servicios.
11. Endpoint de ajustes aprobados de inventario.
12. CRUD completo de productos IREKS/STD en API.
13. Frontend React/Vite inicial con estructura `api/`, `pages/`,
   `components/`, `features/` y `types/`.
14. Pantallas React de consulta para clientes, ingredientes y almacen.
15. Configuracion de Git, rama de migracion, PR inicial y fusion a `main`.
16. Limpieza operativa de datos locales: backup, reparacion de huerfanos e
    ignorado de datos/runtime locales.
17. Primer endurecimiento API: validacion de query params en ingredientes,
    pedidos y almacen.
18. Normalizacion inicial de errores API con helper comun para respuestas
    `400` y `404`.
19. Validacion de rutas locales en API para importaciones JSON/PDF y backups.

## Progreso vivo

### Fase actual

Fase 2 - Endurecer API.

### Completado en Fase 2

- Rama `api-hardening` creada desde `main` actualizado.
- Query params endurecidos:
  - `activity_filter` limitado a `all`, `active`, `inactive`;
  - meses de pedidos limitados a `0..12`;
  - historico de inventario limitado a `1..200`;
  - filtros de texto principales con longitud maxima.
- Tests nuevos en `tests/test_api_query_validation.py`.
- Helper comun `app/api/errors.py` para respuestas `400` y `404` coherentes.
- Routers de clientes, contactos, ingredientes, pedidos, configuracion y
  almacen migrados al helper comun para errores previsibles.
- Helper `app/api/paths.py` para validar rutas locales usadas por API.
- Importaciones JSON/PDF y backup validan extension esperada, archivo existente
  en entradas y destino no-directorio en salidas.

### Pendiente en Fase 2

- Completar la revision semantica de errores: decidir caso por caso si cada
  fallo debe mapear a `400`, `404` o `409`.
- Documentar la politica de rutas locales de API y decidir si React debe migrar
  importaciones a subida de archivos en vez de enviar rutas del servidor.
- Revisar endpoints de borrado con dependencias para devolver errores
  previsibles cuando haya bloqueos.
- Valorar paginacion real para listados grandes antes de ampliar React.
- Documentar una forma comoda de arrancar API y frontend juntos.
- Mantener gates verdes: `pytest`, `npm run lint`, `npm run build` e integridad
  de base de datos.

## Hoja de ruta

### Fase 0 - Estabilizar el punto de partida

Estado: completada.

Objetivo: dejar el trabajo actual versionado, reproducible y con comandos de
validacion claros.

- Activar Git para este directorio con `safe.directory`.
- Revisar `.gitignore` antes de hacer `git add`, especialmente `data/`,
  `runtime/`, exports, PDFs, configuraciones con claves y bases de datos.
- Crear una rama de trabajo para la migracion.
- Separar commits por bloques: backend/API, frontend, datos/assets, tests y
  documentacion.
- Actualizar README con comandos para escritorio, API, frontend y tests.
- Corregir el lint de React hasta que `npm run lint` pase.
- Mantener como gate minimo:
  - `python -m pytest tests -q`
  - `npm run build`
  - `npm run lint`
  - `python -c "from app.core.database import run_integrity_check; print(run_integrity_check())"`

Criterio de salida: arbol Git sin cambios accidentales, tests Python verdes,
build React verde, lint React verde y README actualizado.

### Fase 1 - Sanear datos y mantenimiento

Estado: completada operativamente; queda documentacion fina de politicas.

Objetivo: que la base real pueda mantenerse desde desktop y API sin acciones
manuales peligrosas.

- Hacer backup antes de cualquier reparacion.
- Resolver el enlace huerfano contacto-cliente mediante mantenimiento.
- Revisar si `data/*.json` contiene secretos antes de versionar o compartir.
- Decidir que datos son fixtures, que datos son runtime local y que datos deben
  quedar fuera de Git.
- Documentar el flujo de backup, integridad, reparacion y optimizacion.

Criterio de salida: integridad `ok`, `orphan_contact_links = 0`, backup probado
y politica clara de versionado para `data/`.

### Fase 2 - Endurecer API

Estado: en progreso.

Objetivo: convertir FastAPI en una superficie estable para React sin romper la
app de escritorio.

- Revisar todos los routers para devolver errores HTTP coherentes.
- Mantener validacion explicita en endpoints que reciben rutas locales o
  ficheros.
- Completar tests de endpoints criticos de escritura y borrado.
- Asegurar que los routers no importan UI ni acceden a base de datos directa.
- Alinear nombres de campos entre DTOs, servicios y frontend.
- Preparar script o instruccion oficial para levantar API:
  `python -m uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000`.
- Valorar paginacion o limites en listados grandes antes de cargar mas pantallas
  React.

Criterio de salida: contratos API estables, tests de escritura suficientes y
documentacion de arranque de API.

### Fase 3 - Completar React de solo lectura

Objetivo: cubrir las consultas principales en navegador sin tocar aun flujos de
edicion complejos.

- Clientes: listado, busqueda, detalle y contactos asociados.
- Contactos: listado, detalle y filtro por empresa.
- Ingredientes: IREKS, STD, nutricion, tarifas y referencias de distribuidor.
- Almacen: stock, movimientos, historico de inventarios y exportacion.
- Pedidos: listado, detalle, lineas, pendientes, albaranes y facturas.
- Configuracion: estado de base, integridad, proveedores API y utilidades de
  importacion.

Criterio de salida: React cubre los mismos listados prioritarios que desktop,
sin edicion, con estados de carga, error y vacio consistentes.

### Fase 4 - Migrar escrituras a React

Objetivo: empezar a operar desde React con flujos pequenos, reversibles y bien
probados.

- Empezar por acciones de bajo riesgo: activar/desactivar, filtros guardados,
  tarifas, movimientos manuales y ajustes con confirmacion.
- Despues migrar CRUD de clientes/contactos.
- Despues migrar CRUD de ingredientes IREKS/STD.
- Finalmente migrar pedidos, importaciones PDF/JSON e inventarios.
- Cada pantalla de escritura debe tener validacion frontend, validacion backend,
  feedback de error y test de API.

Criterio de salida: cada flujo migrado puede usarse en React sin depender de la
pantalla equivalente de escritorio.

### Fase 5 - Reducir dependencia del desktop

Objetivo: dejar PySide6 como cliente legacy o administrativo mientras React
asume los flujos principales.

- Mantener desktop estable mientras React alcanza paridad funcional.
- Evitar nuevas reglas de negocio en widgets PySide6.
- Extraer logica residual de widgets grandes hacia servicios.
- Revisar `USE_QML_CUSTOMERS` y decidir si QML queda como experimento, bridge
  temporal o se elimina.
- Priorizar refactors solo cuando desbloqueen migracion o reduzcan riesgo real.

Criterio de salida: nuevas funcionalidades se implementan en servicios/API y
React, no en widgets de escritorio.

### Fase 6 - Preparacion de entrega

Objetivo: preparar una forma reproducible de instalar, ejecutar y actualizar la
aplicacion.

- Definir instalacion Python y Node.
- Definir si Tesseract empaquetado en `runtime/` se versiona, se descarga o se
  documenta como requisito.
- Preparar backup automatico antes de migraciones destructivas.
- Documentar variables/configuraciones locales.
- Crear checklist de release: tests, build, lint, integridad DB, backup, smoke
  test API y smoke test UI.

Criterio de salida: otra maquina puede clonar, instalar, arrancar API/frontend
y validar la base siguiendo README.

## Comandos de validacion

PowerShell, desde la raiz del proyecto:

```powershell
New-Item -ItemType Directory -Force .pytest_tmp
$env:TMP=(Resolve-Path .pytest_tmp).Path
$env:TEMP=$env:TMP
python -m pytest tests -q
Remove-Item -LiteralPath .pytest_tmp -Recurse -Force
```

```powershell
python -c "from app.core.database import run_integrity_check; print(run_integrity_check())"
```

```powershell
cd frontend
npm run lint
npm run build
```

## Git

Git ya esta activado y el remoto apunta al repositorio de GitHub. El flujo
actual recomendado es:

1. Mantener `main` sincronizada con `origin/main`.
2. Trabajar cada bloque en una rama corta, por ejemplo `api-hardening`.
3. Hacer commits pequenos por area y ejecutar los gates antes de subir.
4. Subir la rama a GitHub y abrir Pull Request para revisar/fusionar.
5. No commitear claves, bases reales, backups, exports sensibles ni runtime
   local.
