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
  clientes, contactos, ingredientes (IREKS/STD), pedidos y almacen.
- La base `data/gestion_ireks.db` existe, pasa `PRAGMA integrity_check` y queda
  fuera de Git.
- `orphan_contact_links = 0` tras backup y reparacion.
- `data/*.db`, `data/*.json`, `data/backups/`, `data/exports/` y `runtime/`
  quedan ignorados para evitar subir datos reales, secretos o binarios pesados.
- Validacion tras el bloque actual de Fase 2: `68 passed`, `npm run lint` y
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
20. Respuestas `409 Conflict` para borrados de clientes/contactos bloqueados
    por dependencias.
21. README actualizado con politica de rutas locales y arranque API/frontend.
22. Parametros `limit` y `offset` en listados grandes sin cambiar la forma de
    respuesta existente.
23. Scripts `start-dev.ps1` y `stop-dev.ps1` para arrancar/parar API y
    frontend de forma reproducible.
24. Respuestas `409 Conflict` extendidas a borrado de ingredientes IREKS/STD
    con dependencias operativas.

## Progreso vivo

### Fase actual

Fase 4 - Migrar escrituras a React.

### Completado en Fase 2

- Rama `api-hardening` creada desde `main` actualizado.
- Query params endurecidos:
  - `activity_filter` limitado a `all`, `active`, `inactive`;
  - meses de pedidos limitados a `0..12`;
  - historico de inventario limitado a `1..200`;
  - filtros de texto principales con longitud maxima.
- Tests nuevos en `tests/test_api_query_validation.py`.
- Helper comun `app/api/errors.py` para respuestas `400`, `404` y `409`
  coherentes.
- Routers de clientes, contactos, ingredientes, pedidos, configuracion y
  almacen migrados al helper comun para errores previsibles.
- Helper `app/api/paths.py` para validar rutas locales usadas por API.
- Importaciones JSON/PDF y backup validan extension esperada, archivo existente
  en entradas y destino no-directorio en salidas.
- Borrado de clientes y contactos devuelve `409 Conflict` cuando existen
  contactos, recetas o asistentes asociados.
- README documenta que `source_path`, `file_path` y `destination_path` son
  rutas del servidor, y da comandos para arrancar API y frontend.
- Listados principales aceptan paginacion compatible: clientes, contactos,
  ingredientes IREKS/STD, pedidos, stock, movimientos e historico de
  inventarios.
- Arranque/parada unificada documentada y soportada por scripts locales.
- Borrado de ingredientes IREKS/STD devuelve `409 Conflict` cuando hay
  referencias en pedidos, albaranes, facturas, pendientes o almacen.
- Ajustes API de configuracion con mapeo semantico:
  - `PUT /settings/api/{provider}` devuelve `404` para proveedor no soportado;
  - devuelve `400` para configuracion invalida (por ejemplo, umbral de stock no numerico).
- Tests de contrato de `settings` ampliados para validar el mapeo `400/404`.
- `DELETE /orders/{order_id}` devuelve `409 Conflict` cuando una restriccion de
  integridad impide eliminar el pedido.
- `POST /warehouse/movements` devuelve `409 Conflict` cuando una salida manual
  dejaria stock negativo para producto/lote.
- Importaciones PDF de pedidos devuelven `404` cuando el `order_id` no existe:
  - `POST /orders/{order_id}/import/albaran-pdf`
  - `POST /orders/{order_id}/import/factura-pdf`
- Tests de contrato ampliados para validar esos `404` en importaciones PDF.
- Contactos endurecido frente a referencias invalidas de cliente:
  - `POST /contacts` y `PATCH /contacts/{contact_id}` devuelven `400` cuando
    `cliente_id` no existe.
  - Validacion explicita en servicio para no depender de constraints del motor
    de base de datos en entorno de pruebas.
- Duplicados de clientes/contactos mapeados a `409 Conflict`:
  - `POST /customers` devuelve `409` ante `cliente_id`/campos unicos en conflicto.
  - `POST /contacts` devuelve `409` ante `contacto_id`/campos unicos en conflicto.
  - `PATCH /customers/{customer_id}` y `PATCH /contacts/{contact_id}` devuelven
    `409` para colisiones de unicidad.

### Pendiente en Fase 2

- Mantener la matriz semantica de errores de escritura (`400/404/409`) cuando
  se incorporen nuevos endpoints o reglas de negocio.
- Decidir si React debe migrar importaciones a subida de archivos en vez de
  enviar rutas del servidor.
- Extender la revision de `409 Conflict` a otros dominios si aparecen nuevas
  dependencias bloqueantes (por ejemplo tarifas/configuraciones con reglas de
  negocio adicionales).
- Evolucionar la paginacion hacia respuestas con metadatos (`total`, `limit`,
  `offset`) cuando React necesite controles de pagina visibles.
- Revisar si conviene empaquetar los scripts de arranque/parada en comandos npm
  o task runner para equipos mixtos Windows/Linux.
- Mantener gates verdes: `pytest`, `npm run lint`, `npm run build` e integridad
  de base de datos.

### Completado en Fase 3

- Nueva pantalla React de contactos en solo lectura:
  - listado con busqueda por texto;
  - filtro por empresa usando `/contacts/companies`;
  - panel de detalle usando `/contacts/{contact_id}`.
- Navegacion principal ampliada para incluir la vista `Contactos`.
- Tipos y cliente API frontend extendidos para contratos de contactos.
- Vista de clientes mejorada en solo lectura:
  - seleccion de cliente desde listado;
  - panel de detalle con datos fiscales/comerciales;
  - tabla de contactos asociados del cliente seleccionado.
- Vista de ingredientes ampliada en solo lectura:
  - selector de modo `IREKS` / `STD`;
  - listado y seleccion por fila en ambos modos;
  - detalle IREKS con nutricion y tarifas;
  - detalle STD con nutricion e historico de precios.
- Nueva vista de pedidos en solo lectura:
  - listado filtrable por año, rango de meses y almacen;
  - seleccion de pedido con panel de detalle;
  - tablas de lineas y pendientes del pedido seleccionado.
- Nueva vista de configuracion en solo lectura:
  - estado de base de datos y conteos por tabla;
  - ejecucion manual de `integrity_check` desde React;
  - lectura de proveedores API y almacenes para importacion.

### Completado en Fase 4

- Primer flujo de escritura en React (bajo riesgo):
  - activar/desactivar materias primas STD desde la vista de ingredientes;
  - usa `PATCH /ingredients/std/{articulo_id}/active`;
  - refresca listado y detalle tras guardar, con feedback de exito/error.
- Segundo flujo de escritura en React (bajo riesgo):
  - activar/desactivar clientes desde la vista de clientes;
  - usa `PATCH /customers/{customer_id}` con payload parcial `{ "activo": true|false }`;
  - refresca listado y detalle tras guardar, con feedback de exito/error.
- Tercer flujo de escritura en React:
  - crear y editar contactos desde la vista `Contactos`;
  - usa `POST /contacts` y `PATCH /contacts/{contact_id}`;
  - valida en frontend empresa obligatoria y al menos nombre o apellidos;
  - refresca listado/detalle y muestra feedback de guardado o error.

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
