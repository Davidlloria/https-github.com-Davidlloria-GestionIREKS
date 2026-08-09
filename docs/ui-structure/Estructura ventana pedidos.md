# VENTANA PEDIDOS — PYSIDE6 / BACKEND

Implementación principal:

- UI: `app/ui/widgets/orders_page.py`
- Estilos compartidos: `assets/styles.qss`
- Servicios principales:
  - `app/services/order_query_service.py`
  - `app/services/order_service.py`
  - `app/services/order_edit_flow_service.py`
  - `app/services/order_selected_flow_service.py`
  - `app/services/order_export_service.py`
  - `app/services/order_mail_flow_service.py`
  - `app/services/order_document_import_service.py`
  - `app/services/orders_documents_import_ui_service.py`
  - `app/services/orders_mail_settings_service.py`
- Modelos relevantes:
  - `Pedido`
  - `PedidoItem`
  - `PedidoPendiente`
  - `Albaran`
  - `AlbaranItem`
  - `Factura`
  - `FacturaItem`

## Estructura UI real

```text
OrdersPage (QWidget, sin objectName propio; usa estilos globales de `assets/styles.qss`)
└── layout principal (QVBoxLayout)
    └── splitter principal (QSplitter horizontal, tirador oculto, childrenCollapsible=False)
        ├── sidePanel (QWidget, objectName `sidePanel`, ancho 560-620 px)
        │   └── left_layout (QVBoxLayout)
        │       ├── fila de filtros de periodo (QHBoxLayout)
        │       │   ├── QLabel "Año"
        │       │   ├── year_filter (QComboBox, ancho mínimo 90 px, recarga al cambiar)
        │       │   ├── QLabel "Mes inicial"
        │       │   ├── month_from_filter (QComboBox, ancho mínimo 120 px, recarga al cambiar)
        │       │   ├── QLabel "Mes final"
        │       │   └── month_to_filter (QComboBox, ancho mínimo 120 px, recarga al cambiar)
        │       ├── fila de almacén / cliente-distribuidor (QHBoxLayout)
        │       │   ├── QLabel "Cliente/Distribuidor"
        │       │   └── almacen_filter (QComboBox editable, ancho mínimo 210 px, sin inserción manual, completer por ocurrencia)
        │       ├── topRibbon (QFrame, objectName `topRibbon`, pageType="contacts")
        │       │   ├── new_btn (QPushButton "Nuevo", btnRole="success", alto 26 px, icono 14 px)
        │       │   ├── edit_btn (QPushButton "Editar", btnRole="warning", alto 26 px, icono 14 px)
        │       │   ├── del_btn (QPushButton "Eliminar", btnRole="danger", alto 26 px, icono 14 px)
        │       │   ├── export_btn (QPushButton "Exportar", btnRole="secondary", alto 26 px, icono 14 px)
        │       │   ├── send_mail_btn (QPushButton "Enviar Outlook", btnRole="secondary", alto 26 px, icono 14 px)
        │       │   ├── print_btn (QPushButton "Imprimir", btnRole="secondary", alto 26 px, icono 14 px)
        │       │   ├── espacio flexible
        │       │   └── help_btn (QPushButton "Ayuda", btnRole="secondary", alto 26 px, icono 14 px)
        │       ├── table (QTableWidget, listado principal de pedidos, 6 columnas, ordenable, selección de fila completa)
        │       │   ├── Almacen (180 px)
        │       │   ├── Nº (60 px)
        │       │   ├── Fecha (108 px)
        │       │   ├── Semana (60 px)
        │       │   ├── Total Kg (100 px)
        │       │   └── Estado (55 px, cabecera centrada)
        │       └── table_totals (QTableWidget, 1 fila fija de totales, 6 columnas sincronizadas, alto 30 px)
        └── customersRightPanel (QWidget, objectName `customersRightPanel`, fondo transparente / sin borde por estilo compartido)
            └── right_layout (QVBoxLayout, márgenes 0 px, separación 10 px)
                └── customersDetailSplitter (QSplitter vertical, objectName `customersDetailSplitter`, tirador oculto)
                    ├── detailPanel (QWidget, objectName `detailPanel`, alto máximo 170 px)
                    │   └── detail_layout (QVBoxLayout, márgenes 14 px, separación 8 px)
                    │       ├── detail_title (QLabel "Detalle del pedido", role="sectionTitle")
                    │       └── row_1 (QHBoxLayout)
                    │           ├── QLabel "Semana"
                    │           ├── detail_semana (QLineEdit, solo lectura, 50 px)
                    │           ├── QLabel "Fecha"
                    │           ├── detail_fecha (QDateEdit, calendario desplegable, formato `dd/MM/yyyy`, centrado, ancho mínimo 130 px)
                    │           ├── QLabel "Numero"
                    │           ├── detail_pedido_numero (QLineEdit, 100 px)
                    │           └── espacio flexible
                    └── crmCard (QWidget, objectName `crmCard`, contenedor de pestañas)
                        └── tabs_layout (QVBoxLayout, márgenes 12 px, separación 8 px)
                            └── customerTabs (QTabWidget, objectName `customerTabs`)
                                ├── Pedido
                                │   ├── pedido_actions_ribbon (QFrame, objectName `topRibbon`)
                                │   │   ├── add_line_btn (QPushButton "Añadir", btnRole="success", alto 26 px)
                                │   │   ├── edit_line_btn (QPushButton "Editar", btnRole="warning", alto 26 px)
                                │   │   ├── del_line_btn (QPushButton "Eliminar", btnRole="danger", alto 26 px)
                                │   │   ├── edit_order_btn (QPushButton "Editar pedido", btnRole="warning", alto 26 px)
                                │   │   └── espacio flexible
                                │   ├── pedido_items_table (QTableWidget, 7 columnas, ordenable, selección de fila completa, edición directa habilitada)
                                │   │   ├── Cod. (95 px)
                                │   │   ├── Nombre (stretch)
                                │   │   ├── Pedido (82 px)
                                │   │   ├── Kg (96 px)
                                │   │   ├── Recib. (82 px)
                                │   │   ├── Kg (96 px)
                                │   │   └── Δ (72 px)
                                │   └── pedido_items_totals_table (QTableWidget, 1 fila fija de totales, 7 columnas sincronizadas, alto 30 px)
                                ├── Albarán
                                │   ├── albaran_actions_ribbon (QFrame, objectName `topRibbon`)
                                │   │   ├── import_albaran_btn (QPushButton "Imp. Albarán", btnRole="warning", alto 26 px, deshabilitado sin pedido)
                                │   │   └── espacio flexible
                                │   ├── albaran_filter_row (QHBoxLayout)
                                │   │   ├── QLabel "Albaran"
                                │   │   └── albaran_selector (QComboBox, cambia las líneas visibles del albarán)
                                │   ├── albaran_items_table (QTableWidget, 5 columnas, ordenable, selección de fila completa, menú contextual)
                                │   │   ├── Cod. (95 px)
                                │   │   ├── Nº albarán (120 px)
                                │   │   ├── Nombre (stretch)
                                │   │   ├── Cantidad (90 px)
                                │   │   └── Kg (100 px)
                                │   └── albaran_items_totals_table (QTableWidget, 1 fila fija de totales, 5 columnas sincronizadas, alto 30 px)
                                ├── Factura
                                │   ├── factura_actions_ribbon (QFrame, objectName `topRibbon`)
                                │   │   ├── import_factura_btn (QPushButton "Imp. Factura", btnRole="warning", alto 26 px, deshabilitado sin pedido)
                                │   │   ├── edit_factura_line_btn (QPushButton "Editar línea", btnRole="primary", alto 26 px, deshabilitado sin línea)
                                │   │   ├── delete_factura_btn (QPushButton "Eliminar Factura", btnRole="danger", alto 26 px, deshabilitado sin factura)
                                │   │   └── espacio flexible
                                │   └── factura_content (QSplitter horizontal, tirador oculto, childrenCollapsible=False)
                                │       ├── facturas_table (QTableWidget, 1 columna, ancho fijo 120 px, ordenable)
                                │       │   └── Factura (stretch)
                                │       └── factura_items_panel (QWidget)
                                │           └── factura_items_layout (QVBoxLayout, márgenes 0 px, separación 0 px)
                                │               ├── factura_items_table (QTableWidget, 5 columnas, ordenable, selección de fila completa, doble clic edita línea)
                                │               │   ├── Cod. (86 px)
                                │               │   ├── Nombre (stretch)
                                │               │   ├── Uds. (60 px)
                                │               │   ├── Kg/Lit. (78 px)
                                │               │   └── Precio (82 px)
                                │               └── factura_items_totals_table (QTableWidget, 1 fila fija de totales, 5 columnas sincronizadas, alto 30 px)
                                └── Pendientes
                                    └── pendientes_table (QTableWidget, 4 columnas, ordenable, selección de fila completa)
                                        ├── Cod. (95 px)
                                        ├── Nombre (stretch)
                                        ├── Pendiente (100 px)
                                        └── Pedido (100 px)
```

## Comportamiento actual

- `OrdersPage` carga datos al inicializar mediante `reload()`.
- `year_filter`, `month_from_filter`, `month_to_filter` y `almacen_filter` recargan el listado al cambiar.
- `almacen_filter` es editable y usa autocompletado por ocurrencia (`MatchContains`) sin distinguir mayúsculas/minúsculas.
- `table` usa selección única de fila completa y dispara `_show_selected_details()` al cambiar la selección.
- La selección de un pedido carga:
  - detalle de pedido;
  - líneas de pedido;
  - albaranes;
  - facturas;
  - artículos pendientes.
- `detail_fecha` y `detail_pedido_numero` programan autosave con `_schedule_autosave()`.
- `pedido_items_table` permite edición directa por doble clic, tecla de edición o clic sobre celda seleccionada; los cambios se procesan en `_on_pedido_item_cell_changed()`.
- `albaran_items_table` tiene menú contextual propio mediante `_show_albaran_items_context_menu()`.
- `factura_items_table` habilita `edit_factura_line_btn` si hay línea seleccionada y abre edición con doble clic.
- Las tablas principales y de detalle tienen ordenación activada desde cabecera.
- Las filas de totales se mantienen fuera del scroll de cada tabla y se sincronizan con sus columnas correspondientes.
- El botón `Ayuda` abre un mensaje informativo de uso de la ventana.

## Geometría actual

- El splitter principal es horizontal.
- Panel izquierdo `sidePanel`:
  - ancho mínimo 560 px;
  - ancho máximo 620 px;
  - tamaño inicial aproximado 580 px.
- Panel derecho:
  - ocupa el resto del ancho disponible;
  - layout sin márgenes;
  - separación vertical de 10 px.
- `customersDetailSplitter` es vertical:
  - `detailPanel` arriba;
  - `crmCard` debajo;
  - el panel de pestañas tiene factor de estiramiento superior al detalle (`0 / 10`).
- `detailPanel`:
  - alto máximo 170 px;
  - márgenes internos 14 px.
- `factura_content`:
  - splitter horizontal interno;
  - `facturas_table` fijo a 120 px;
  - panel de líneas de factura ocupa el resto;
  - tirador oculto y deshabilitado.
- Todas las filas de totales tienen alto fijo de 30 px.
- El splitter principal tiene tirador de ancho 0 y `handle(1)` deshabilitado.

## Aspecto visual actual

- La ventana usa los estilos globales de `assets/styles.qss`.
- `sidePanel` se estiliza mediante `#sidePanel`: fondo blanco, borde gris suave y radio de 8 px.
- `detailPanel` se estiliza mediante `#detailPanel`: fondo claro `#FCFDFF`, borde `#E2E8F1`, radio 8 px.
- `customersRightPanel`, `customersDetailSplitter`, `crmCard` y `customerTabs` reutilizan nombres de objeto heredados del patrón de clientes.
- `topRibbon` usa variante pastel con `pageType="contacts"` en el ribbon principal.
- Los botones se colorean por `btnRole`:
  - `success`: acciones de alta / añadir.
  - `warning`: edición e importaciones.
  - `danger`: eliminación.
  - `secondary`: exportar, enviar, imprimir, ayuda.
  - `primary`: edición de línea de factura.
- Las tablas usan selección azul global, cabeceras con estilo compartido y foco visual eliminado mediante `QTableWidget::item:focus { border: none; outline: 0; }`.
- Las columnas numéricas se rellenan con `NumericTableWidgetItem` donde aplica para conservar ordenación numérica real.

## Diálogos y flujos relacionados

- `NewPedidoDialog`:
  - crea un pedido nuevo;
  - incluye número, filtros de fabricante/familia/subfamilia, buscador y tabla de artículos.
- `AddPedidoLineDialog`:
  - selecciona artículo y cantidad para añadir línea al pedido.
- `EditPedidoLineDialog`:
  - edita datos de una línea existente.
- `AlbaranPreviewDialog`:
  - previsualiza importaciones de albarán antes de confirmar.
- `FacturaPreviewDialog`:
  - previsualiza importaciones de factura antes de confirmar.
- `FacturaItemEditDialog`:
  - edita línea de factura.
- Flujo Outlook:
  - usa `OrderMailFlowService`;
  - usa configuración de `OrdersMailSettingsService`;
  - permite preparar/enviar el pedido seleccionado por correo si la configuración está disponible.
- Flujo de exportación:
  - `export_btn` exporta el pedido seleccionado a Excel mediante `OrderExportService`.
  - `print_btn` imprime el pedido seleccionado.

## Relación con backend / datos

- `OrdersPage` no consume el frontend React.
- La UI trabaja sobre servicios Python/PySide6 y modelos locales.
- `OrderQueryService` alimenta el listado y filtros.
- `OrderService` gestiona lectura y persistencia de pedidos, líneas, albaranes, facturas y pendientes.
- `OrderEditFlowService` y `OrderSelectedFlowService` encapsulan operaciones sobre el pedido seleccionado.
- `OrderDocumentImportService` y `OrdersDocumentsImportUiService` preparan/importan documentos de albarán y factura.
- `OrderExportService` genera exportaciones del pedido.
- `OrderMailFlowService` prepara el envío por Outlook.

## Últimos ajustes relevantes documentados

- El filtro `almacen_filter` es editable con búsqueda por ocurrencia para manejar listas largas.
- La tabla principal mantiene columnas fijas para `Almacen`, `Nº`, `Fecha`, `Semana`, `Total Kg` y `Estado`.
- La parte derecha conserva el patrón visual heredado de clientes (`customersRightPanel`, `customersDetailSplitter`, `crmCard`, `customerTabs`).
- Las tablas de Pedido, Albarán y Factura tienen filas de totales fijas fuera del scroll.
- La pestaña Factura usa splitter horizontal interno para separar listado de facturas y detalle de líneas.

## Modales principales

- Modal `Nuevo pedido`: `NewPedidoDialog`, selección de artículos con filtros y tabla de líneas candidatas.
- Modal `Añadir línea`: `AddPedidoLineDialog`, búsqueda de artículo y cálculo de kg por cantidad.
- Modal `Editar línea`: `EditPedidoLineDialog`, edición de la línea seleccionada.
- Modal `Previsualización albarán`: `AlbaranPreviewDialog`, tabla de líneas detectadas antes de importar.
- Modal `Previsualización factura`: `FacturaPreviewDialog`, tabla de líneas y datos de factura antes de importar.
- Modal `Editar línea factura`: `FacturaItemEditDialog`, edición de importes/cantidades de una línea de factura.
