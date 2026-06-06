# Roadmap de migracion UI / servicios / API

## Estado ejecutivo

- Fase actual: Fase 5 - Reducir dependencia del desktop.
- Objetivo actual: mantener PySide6 estable mientras se extrae la logica que
  aun vive en widgets grandes y se consolida la paridad en React/FastAPI.
- Estado general de la migracion: avanzado. La API y React ya cubren lectura y
  varios flujos de escritura en dominios clave, pero el desktop sigue reteniendo
  orquestacion pesada, integraciones de archivos y dependencias locales.
- Proximo foco tecnico: seguir sacando logica residual de `orders_page.py`,
  `settings_page.py`, `ingredients_page.py` y `warehouse_page.py` hacia capas
  de servicio o helpers puros.
- Proximo foco tecnico: reducir dependencia de desktop sobre OCR, dialogos de
  archivo/impresion y rutas locales del servidor.
- Proximo foco tecnico: cerrar la orquestacion de reportes/impresion en
  `ingredients_page.py` ahora que la generacion del listado ya esta coordinada
  fuera del widget.
- Proximo foco tecnico: mantener gates y trazabilidad documental; cada avance
  pequeno debe quedar reflejado en la roadmap y en el historial.
- Ultimo avance validado: se extrajo la orquestacion no visual de generacion
  de reportes de producto hacia `app/services/product_report_flow_service.py`,
  dejando en `app/ui/widgets/ingredients_page.py` la lectura del prompt, los
  mensajes visibles, `QApplication.processEvents()` y la actualizacion visual
  del listado.
- Ultimo avance validado: se extrajo la preparacion de ajustes de inventario
  hacia `app/services/warehouse_inventory_adjustment_preparation_service.py`,
  dejando en `app/ui/widgets/warehouse_page.py` la lectura de la tabla Qt, los
  mensajes visibles, la asignacion de pendientes y la actualizacion visual del
  contador.
- Ultimo avance validado: se extraio al servicio la preparacion del adjunto
  y la orquestacion comun del flujo de correo de pedidos por Outlook.
- Ultimo avance validado: se extrajo el coordinador no visual de Outlook hacia
  `app/services/order_mail_flow_service.py`, dejando en `orders_page.py` la
  seleccion de modo, el preview y los mensajes visibles.
- Ultimo avance validado: se extrajo la orquestacion comun de importacion
  documental de pedidos hacia `app/services/orders_documents_import_ui_service.py`,
  dejando en `orders_page.py` solo la seleccion de archivo, la confirmacion de
  vista previa y los mensajes de interfaz.
- Ultimo avance validado: se extrajo el coordinador de flujo IGSA de preview e
  importacion hacia `app/services/settings_sales_import_flow_ui_service.py`,
  dejando en `app/ui/widgets/settings_page.py` solo el renderizado de dialogos
  y los mensajes de interfaz.
- Ultimo avance validado: se extrajo la orquestacion no visual del flujo
  FatSecret por texto hacia `app/services/ingredient_fatsecret_nutrition_flow_service.py`,
  dejando en `app/ui/widgets/ingredients_page.py` la seleccion de modo, los
  dialogos Qt, los mensajes visibles y la aplicacion final de valores.
- Ultimo avance validado: se extrajo la rama barcode del flujo FatSecret hacia
  `app/services/ingredient_fatsecret_nutrition_flow_service.py`, dejando en
  `app/ui/widgets/ingredients_page.py` la seleccion de codigo de barras, los
  dialogos Qt, los mensajes visibles y la aplicacion final de valores.
- Ultimo avance validado: se extrajo la orquestacion no visual del guardado de
  movimientos manuales de almacen hacia
  `app/services/warehouse_manual_move_flow_service.py`, dejando en
  `app/ui/widgets/warehouse_page.py` el dialogo manual, los mensajes visibles y
  el refresco de pantalla.
- Ultimo avance validado: se extrajo la orquestacion no visual del flujo
  ChatGPT nutricion hacia `app/services/ingredient_chatgpt_nutrition_flow_service.py`,
  dejando en `app/ui/widgets/ingredients_page.py` el dialogo de consulta, los
  mensajes visibles y la aplicacion final de valores.
- Cobertura de caracterizacion ampliada: se validan la preparacion del
  adjunto, la version del historico, el contrato de resultado y el manejo de
  errores previsibles del flujo Outlook sin depender de la UI PySide6.
- Cosas que no se deben hacer ahora: no añadir funcionalidad nueva, no crear
  endpoints nuevos, no crear pantallas React nuevas, no hacer refactors
  funcionales grandes, no meter nueva logica de negocio en widgets.

## Completado en Fase 5

- Flujo de correo de pedidos por Outlook extraido fuera del widget:
  - `app/services/order_export_service.py` ahora concentra la preparacion del
    adjunto del pedido (`prepare_order_mail_attachment`) y la orquestacion del
    envio/log de Outlook (`send_order_mail`);
  - `app/services/order_mail_flow_service.py` concentra la coordinacion no
    visual de preparacion, preview y envio con estados estructurados;
  - `app/ui/widgets/orders_page.py` queda centrado en seleccion, confirmacion,
    previsualizacion y mensajes visibles;
  - se mantienen los mismos textos al usuario y el mismo contrato visible.
- Flujo de edicion de pedido en `OrdersPage` coordinado fuera del widget:
  - `app/services/order_edit_flow_service.py` concentra la carga del pedido,
    la resolucion de cantidades por articulo y el guardado de la edicion;
  - `app/ui/widgets/orders_page.py` conserva el `NewPedidoDialog`, los
    mensajes visibles, el `reload` y la reseleccion del pedido;
  - se mantienen los mismos textos visibles y el mismo comportamiento de
    guardado, validacion y refresco.
- Flujo de guardado de movimientos manuales en `warehouse_page.py` coordinado
  fuera del widget:
  - `app/services/warehouse_manual_move_flow_service.py` concentra la
    validacion de payload, el calculo de stock y la coordinacion del guardado;
  - `app/ui/widgets/warehouse_page.py` conserva `ManualMovementDialog`, los
    mensajes visibles, la seleccion de movimiento y el refresco de pantalla;
  - se mantienen los mismos textos visibles, validaciones y comportamiento de
    guardado manual.
- Flujo ChatGPT de nutricion en `ingredients_page.py` coordinado fuera del
  widget:
  - `app/services/ingredient_chatgpt_nutrition_flow_service.py` concentra la
    validacion de consulta, la llamada al servicio OpenAI y la normalizacion
    del resultado;
  - `app/ui/widgets/ingredients_page.py` conserva `QInputDialog`, los mensajes
    visibles y `_apply_nutrition_values`;
  - se mantienen los mismos textos visibles y el mismo comportamiento de
    aplicacion de valores nutricionales.
- Flujo de backup de base de datos en configuracion simplificado:
  - `app/services/settings_maintenance_ui_service.py` ahora genera la ruta por
    defecto del backup con una unica funcion reutilizable;
  - `app/ui/widgets/settings_page.py` delega esa construccion y conserva solo
    el dialogo de guardado, la llamada al servicio y los mensajes visibles;
  - se mantiene el mismo patron de nombre `gestion_ireks_backup_YYYYMMDD_HHMMSS.db`;
  - la cabecera de mantenimiento reutiliza la metadata del servicio para
    botones y placeholder del log.
- Flujo de configuracion de pedidos Outlook simplificado:
  - `app/services/settings_provider_service.py` expone `load_orders_mail_view()`
    para normalizar los valores iniciales del formulario;
  - `app/ui/widgets/settings_page.py` usa un objeto tipado para rellenar los
    campos y conserva el guardado en servicio sin cambiar mensajes;
  - la tarjeta de `Pedidos Outlook` reutiliza ahora la metadata del servicio
    para textos, placeholders, botones e info visible.
- Flujo de configuracion API centralizado:
  - `app/services/settings_provider_service.py` expone `build_ui_view()` para
    agrupar titulos y textos comunes de FDC, FatSecret y OpenAI;
  - `app/ui/widgets/settings_page.py` usa esa metadata para construir la
    tarjeta de configuracion API sin hardcodear literales repetidos;
  - la tarjeta API reutiliza ahora metadata del servicio para labels, botones,
    placeholders y opciones del combo FDC.
- Flujo de importacion de pedidos JSON desde configuracion simplificado:
  - `app/services/settings_orders_import_service.py` expone
    `build_orders_import_view()` para concentrar las opciones de almacenes;
  - `app/ui/widgets/settings_page.py` usa ese objeto de vista para poblar el
    combo de importacion y mantiene intacto el dialogo de archivo;
  - el bloque de pedidos JSON reutiliza la metadata del servicio para el texto
    de la seccion, la etiqueta del selector y el boton de importacion.
- Flujo de importacion de ventas IREKS simplificado:
  - `app/services/settings_sales_import_service.py` expone `build_import_view()`
    para centralizar el titulo y filtro del dialogo de seleccion;
  - `app/ui/widgets/settings_page.py` usa esa vista para abrir el selector sin
    hardcodear el texto en la UI;
  - el bloque de ventas IREKS reutiliza la metadata del servicio para el texto
    de la seccion y el boton de importacion.
- Flujo de vista previa IGSA simplificado:
  - `app/services/settings_sales_preview_service.py` expone `build_preview_view()`
    para centralizar titulos y filtros de seleccion;
  - `app/ui/widgets/settings_page.py` usa esa vista para abrir PDFs y libros
    IGSA sin repetir literales de dialogo;
  - el dialogo de resultado de importacion de libro IGSA reutiliza ahora la
    metadata del servicio para titulos y botones;
  - el preview PDF IGSA reutiliza la metadata del servicio para los botones de
    importacion y cierre;
  - los mensajes de error visibles del flujo IGSA reutilizan titulos
    centralizados en el servicio.
- Flujo IGSA de previsualizacion e importacion coordinado fuera de UI desktop:
  - `app/services/settings_sales_import_flow_ui_service.py` concentra la
    secuencia comun de confirmacion, importacion y reimportacion del workbook;
  - `app/ui/widgets/settings_page.py` sigue abriendo los dialogos Qt y ahora
    delega la decision de reimportacion y la secuencia de importacion al
    coordinador;
  - se mantiene el mismo comportamiento visible, los mismos mensajes y el
    mismo parseo/importacion real.
- Candidatos de nutricion IREKS/STD normalizados fuera del widget:
  - `app/services/ingredient_nutrition_query_service.py` concentra la
    normalizacion de queries y la generacion pura de candidatos FDC y
    FatSecret;
  - `app/ui/widgets/ingredients_page.py` conserva los dialogos Qt y la
    aplicacion final de valores, pero ya no construye los candidatos a mano;
  - se mantienen los mismos mapeos ES/EN, el mismo orden de candidatos y la
    misma deduplicacion visible.
- Flujo FDC de nutricion extraido fuera de UI desktop:
  - `app/services/ingredient_fdc_nutrition_flow_service.py` concentra la
    orquestacion no visual del flujo FDC y el mapeo de seleccion;
  - `app/ui/widgets/ingredients_page.py` conserva los dialogos Qt, mensajes y
    aplicacion final de valores;
  - se mantienen los mismos textos visibles y el mismo orden de candidatos.
- Flujo FatSecret de nutricion por texto extraido fuera de UI desktop:
  - `app/services/ingredient_fatsecret_nutrition_flow_service.py` concentra la
    orquestacion no visual del flujo FatSecret por texto, la busqueda de
    alimentos, la seleccion de alimento y la conversion de raciones a valores;
  - `app/ui/widgets/ingredients_page.py` conserva los dialogos Qt, los mensajes
    visibles y la aplicacion final de valores;
  - se mantienen los mismos textos visibles, la misma formula de sal y el
    mismo formato visible de labels.
- Caracterizacion ampliada del flujo:
  - tests de preparacion, versionado del historico, contrato del servicio y
    errores previsibles de Outlook sin UI PySide6.

## Deuda tecnica priorizada

### P1

- `app/ui/widgets/orders_page.py`: flujo de pedidos, importaciones, exportacion
  y envio por Outlook siguen concentrando orquestacion sensible.
- `app/ui/widgets/settings_page.py`: configuracion, importaciones, preview,
  mantenimiento y backup siguen mezclando UI con decisiones de proceso.
- `app/ui/widgets/ingredients_page.py`: pantalla grande con dialogos,
  exportacion, impresion y logica de edicion que todavia es costosa de mover.
- `app/services/order_document_parser.py`: OCR, Tesseract y recuperacion por
  sidecar siguen siendo un punto de riesgo por dependencia de runtime local.
- Retirada gradual de endpoints legacy por `source_path` / `file_path` tras
  confirmar adopcion completa de los endpoints upload.

### P2

- `app/ui/widgets/warehouse_page.py`: plantilla de inventario, ajustes y
  exportaciones siguen teniendo logica de soporte que conviene aislar mas.
- `app/ui/widgets/customers_page.py`: exportacion/impresion y mantenimiento de
  cliente siguen acoplados a UI.
- `app/ui/widgets/courses_page.py`: importacion, exportacion e impresion siguen
  muy dependientes de Qt.
- `app/services/sales_reconciliation_service.py`: contiene bastante logica de
  parseo e importacion y merece extraccion incremental si vuelve a crecer.

### P3

- Limpieza de helpers legacy y wrappers sin uso en widgets ya saneados.
- Unificar nomenclatura y criterios de validacion en documentacion de API.
- Consolidar scripts locales de arranque, parada, validacion y backup.
- Revisar flags o compatibilidad heredada solo cuando ya no aporten valor.

## Mapa de riesgo actual

### Archivos mas grandes del codigo propio

- `app/ui/widgets/ingredients_page.py` - 206.2 KB
- `app/ui/widgets/recipes_page.py` - 159.9 KB
- `app/ui/widgets/orders_page.py` - 135.9 KB
- `app/ui/widgets/warehouse_page.py` - 129.5 KB
- `app/ui/widgets/settings_page.py` - 103.3 KB
- `app/ui/widgets/customers_page.py` - 90.6 KB
- `app/services/sales_reconciliation_service.py` - 90.7 KB
- `app/ui/widgets/courses_page.py` - 61.9 KB
- `app/ui/widgets/sales_page.py` - 50.6 KB

### Widgets PySide6 con logica aun sensible

- `app/ui/widgets/orders_page.py`: importacion de pedidos y documentos,
  resumenes, exportacion y envio por Outlook.
- `app/ui/widgets/settings_page.py`: preview de importaciones, backup,
  mantenimiento, configuracion de proveedores y flujos con rutas locales.
- `app/ui/widgets/ingredients_page.py`: edicion, importacion, impresion,
  exportacion y dialogos de soporte dentro de una unica pantalla muy grande.
- `app/ui/widgets/recipes_page.py`: normalizacion de datos, versionado,
  galerias de imagenes y helpers de carga/guardado.
- `app/ui/widgets/warehouse_page.py`: plantillas de inventario, conteos,
  exportaciones y apoyo a catalogos.
- `app/ui/widgets/customers_page.py`: exportacion, impresion e importacion de
  clientes siguen viviendo en la capa de UI.
- `app/ui/widgets/courses_page.py`: importacion, exportacion e impresion
  mantienen bastante logica de escritorio.

### Acceso directo a base de datos desde UI

- No se detectaron imports directos de `Session`, `select`, `engine` ni
  `app.core.database` desde `app/ui/widgets` en el barrido actual.
- Esto es una buena señal: el riesgo hoy esta mas en orquestacion y en
  dependencias desktop que en acceso directo a la base desde la UI.

### Dependencias desktop dificiles de migrar

- Outlook: `app/ui/widgets/orders_page.py` y `app/services/order_export_service.py`
  siguen dependiendo de la integracion de correo de escritorio.
- OCR / Tesseract: `app/services/order_document_parser.py` configura y usa
  `pytesseract`, rutas locales y fallback de runtime.
- Dialogos Qt: `QFileDialog`, `QInputDialog`, `QPrintDialog` y `QPrinter`
  siguen presentes en `orders_page.py`, `customers_page.py`, `ingredients_page.py`,
  `courses_page.py`, `settings_page.py`, `warehouse_page.py` y otras vistas.
- Rutas locales del servidor: los flujos legacy con `source_path`, `file_path`
  y `destination_path` todavia existen para compatibilidad temporal.
- Dependencias de archivos y previsualizacion local: Excel, PDF, JSON y
  sidecars siguen siendo parte del flujo real en varios widgets.

### Areas con paridad razonable en React/FastAPI

- Clientes: listado, detalle, CRUD, activacion y contactos asociados.
- Contactos: listado, detalle, CRUD y filtro por empresa.
- Ingredientes: IREKS/STD, nutricion, tarifas, alta, edicion y borrado.
- Pedidos: listado, detalle, lineas, pendientes, CRUD, importacion y borrado.
- Almacen: stock, movimientos, historico, ajustes y exportaciones basicas.
- Configuracion: estado de base, integridad, backups, importaciones y ajustes de API.
- API: validaciones, errores `400/404/409`, paginacion en listados grandes y
  contratos de escritura ya bastante estabilizados.

## Siguiente refactor recomendado

- Objetivo concreto: extraer la orquestacion de reportes e impresion en
  `ingredients_page.py` para dejar el widget como fachada de dialogo y salida
  visual.
- Archivos a tocar: `app/ui/widgets/ingredients_page.py`, un nuevo servicio o
  coordinador pequeno para reportes/impresion y un test pequeno de
  caracterizacion del flujo.
- Motivo: ChatGPT ya quedo completo; el siguiente borde de alto retorno en
  `ingredients_page.py` es reportes/impresion, que sigue siendo mas costoso que
  un simple dialogo de consulta.
- Riesgo: medio. Es un cambio de coordinacion y mensajes, con varias rutas de
  exportacion pero sin tocar el calculo nutricional ni la edicion de recetas.
- Tests que deben ejecutarse: `tests/test_architecture_boundaries.py` y los
  nuevos tests del coordinador de reportes/impresion cuando se creen.
- Validacion manual esperada: abrir `Ingredientes` y comprobar que los
  reportes y la impresion siguen ofreciendo el mismo dialogo y la misma
  salida visual.

## Proximos pasos

1. Tomar este roadmap como referencia operativa unica para la migracion.
2. Atacar el siguiente bloque pequeno de labels de estado de mantenimiento en
   `ingredients_page.py` reportes/impresion sin introducir comportamiento
   nuevo.
3. Mantener el historial detallado en `docs/migration-history.md`.
4. Seguir cerrando deuda tecnica solo cuando reduzca riesgo o desbloquee la
   migracion.
5. Actualizar este documento despues de cada bloque pequeno validado.

## Comandos de validacion

PowerShell, desde la raiz del proyecto:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-gates.ps1
```

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

