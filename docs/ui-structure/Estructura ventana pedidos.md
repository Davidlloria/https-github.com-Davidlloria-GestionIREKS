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
  - `Pedido` / `PedidoItem` / `PedidoPendiente`
  - `Albaran` / `AlbaranItem`
  - `Factura` / `FacturaItem`

OrdersPage (QWidget, sin objectName)

├── layout principal (QVBoxLayout)
│   └── splitter principal (QSplitter horizontal, sin objectName, tirador oculto)
│
├── sidePanel (QWidget, fondo #FFFFFF, borde #D7DEE8, radio 8 px, ancho 560–620 px)
│   └── left_layout (QVBoxLayout, sin objectName)
│       ├── filters_row (QHBoxLayout)
│       │   ├── QLabel "Año"
│       │   ├── year_filter (QComboBox, ancho mínimo 90 px)
│       │   ├── QLabel "Mes inicial"
│       │   ├── month_from_filter (QComboBox, ancho mínimo 120 px)
│       │   ├── QLabel "Mes final"
│       │   └── month_to_filter (QComboBox, ancho mínimo 120 px)
│       ├── almacen_row (QHBoxLayout)
│       │   ├── QLabel "Cliente/Distribuidor"
│       │   └── almacen_filter (QComboBox editable, ancho mínimo 210 px)
│       ├── topRibbon (QFrame, pageType=contacts, fondo #FFFFFF, borde #E2E8F1, radio 8 px)
│       │   ├── new_btn (QPushButton "Nuevo", btnRole=success, 26 px)
│       │   ├── edit_btn (QPushButton "Editar", btnRole=warning, 26 px)
│       │   ├── del_btn (QPushButton "Eliminar", btnRole=danger, 26 px)
│       │   ├── export_btn (QPushButton "Exportar", btnRole=secondary, 26 px)
│       │   ├── send_mail_btn (QPushButton "Enviar Outlook", btnRole=secondary, 26 px)
│       │   ├── print_btn (QPushButton "Imprimir", btnRole=secondary, 26 px)
│       │   ├── espacio flexible
│       │   └── help_btn (QPushButton "Ayuda", btnRole=secondary, 26 px)
│       ├── table (QTableWidget, 6 columnas ordenables)
│       │   ├── Almacen (180 px)
│       │   ├── Nº (60 px)
│       │   ├── Fecha (108 px)
│       │   ├── Semana (60 px)
│       │   ├── Total Kg (100 px)
│       │   └── Estado (55 px)
│       └── table_totals (QTableWidget, 1 fila fija, alto 30 px)
│
└── customersRightPanel (QWidget, sin borde)
    └── right_layout (QVBoxLayout, márgenes 0 px, separación 10 px)
        └── customersDetailSplitter (QSplitter vertical, tirador oculto)
            ├── detailPanel (QWidget, fondo #FCFDFF, borde #E2E8F1, radio 8 px, alto máximo 170 px)
            │   └── detail_layout (QVBoxLayout, márgenes 14 px, separación 8 px)
            │       ├── detail_title (QLabel "Detalle del pedido", role=sectionTitle)
            │       └── row_1 (QHBoxLayout)
            │           ├── QLabel "Semana"
            │           ├── detail_semana (QLineEdit, solo lectura, 50 px)
            │           ├── QLabel "Fecha"
            │           ├── detail_fecha (QDateEdit, calendario desplegable, formato dd/MM/yyyy)
            │           ├── QLabel "Numero"
            │           └── detail_pedido_numero (QLineEdit, 100 px)
            └── crmCard (QWidget, contenedor de pestañas, fondo #FFFFFF, borde #E2E8F0, radio 8 px)
                └── customerTabs (QTabWidget)
                    ├── pedido_tab (QWidget, pestaña "Pedido")
                    │   ├── topRibbon (QFrame)
                    │   │   ├── add_line_btn (QPushButton "Añadir", btnRole=success, 26 px)
                    │   │   ├── edit_line_btn (QPushButton "Editar", btnRole=warning, 26 px)
                    │   │   ├── del_line_btn (QPushButton "Eliminar", btnRole=danger, 26 px)
                    │   │   ├── edit_order_btn (QPushButton "Editar pedido", btnRole=warning, 26 px)
                    │   │   └── espacio flexible
                    │   ├── pedido_items_table (QTableWidget, 7 columnas ordenables)
                    │   │   ├── Cod. (95 px)
                    │   │   ├── Nombre (flexible)
                    │   │   ├── Pedido (82 px)
                    │   │   ├── Kg (96 px)
                    │   │   ├── Recib. (82 px)
                    │   │   ├── Kg (96 px)
                    │   │   └── Δ (72 px)
                    │   └── pedido_items_totals_table (QTableWidget, 1 fila fija, alto 30 px)
                    ├── albaran_tab (QWidget, pestaña "Albarán")
                    │   ├── topRibbon (QFrame)
                    │   │   ├── import_albaran_btn (QPushButton "Imp. Albarán", btnRole=warning, 26 px)
                    │   │   └── espacio flexible
                    │   ├── albaran_filter_row (QHBoxLayout)
                    │   │   ├── QLabel "Albaran"
                    │   │   └── albaran_selector (QComboBox)
                    │   ├── albaran_items_table (QTableWidget, 5 columnas ordenables)
                    │   │   ├── Cod. (95 px)
                    │   │   ├── Nº albarán (120 px)
                    │   │   ├── Nombre (flexible)
                    │   │   ├── Cantidad (90 px)
                    │   │   └── Kg (100 px)
                    │   └── albaran_items_totals_table (QTableWidget, 1 fila fija, alto 30 px)
                    ├── factura_tab (QWidget, pestaña "Factura")
                    │   ├── topRibbon (QFrame)
                    │   │   ├── import_factura_btn (QPushButton "Imp. Factura", btnRole=warning, 26 px)
                    │   │   ├── edit_factura_line_btn (QPushButton "Editar línea", btnRole=primary, 26 px)
                    │   │   ├── delete_factura_btn (QPushButton "Eliminar Factura", btnRole=danger, 26 px)
                    │   │   └── espacio flexible
                    │   └── factura_content (QSplitter horizontal, tirador oculto)
                    │       ├── facturas_table (QTableWidget, 1 columna, ancho fijo 120 px)
                    │       └── factura_items_panel (QWidget)
                    │           ├── factura_items_table (QTableWidget, 5 columnas ordenables)
                    │           │   ├── Cod. (86 px)
                    │           │   ├── Nombre (flexible)
                    │           │   ├── Uds. (60 px)
                    │           │   ├── Kg/Lit. (78 px)
                    │           │   └── Precio (82 px)
                    │           └── factura_items_totals_table (QTableWidget, 1 fila fija, alto 30 px)
                    └── pendientes_tab (QWidget, pestaña "Pendientes")
                        └── pendientes_table (QTableWidget, 4 columnas ordenables)
                            ├── Cod. (95 px)
                            ├── Nombre (flexible)
                            ├── Pendiente (100 px)
                            └── Pedido (100 px)

## Geometría actual

- El splitter principal es horizontal, sin tirador visible.
- `sidePanel` limita el ancho entre 560 y 620 px.
- `customersRightPanel` usa separación vertical de 10 px.
- `detailPanel` limita su alto a 170 px.
- El bloque de pestañas ocupa el resto del espacio del panel derecho.
- Las filas de totales miden 30 px y quedan fuera del scroll de sus tablas.
- `factura_content` reserva 120 px al listado de facturas y deja el resto a sus líneas.

## Aspecto visual actual

- La ventana usa estilos compartidos de `assets/styles.qss`.
- El ribbon principal adopta la misma variante pastel de `Clientes` mediante `pageType=contacts`.
- Colores de botones:
  - success: fondo `#DCFCE7`, texto `#166534`
  - warning: fondo `#FEF3C7`, texto `#92400E`
  - danger: fondo `#FEE2E2`, texto `#B91C1C`
  - secondary: fondo `#E2E8F0`, texto `#334155`
  - primary: fondo `#DBEAFE`, texto `#1D4ED8`
- `detailPanel`: fondo `#FCFDFF`, borde `#E2E8F1`, radio 8 px.
- Contenedor de pestañas: tarjeta blanca con borde suave y pestañas con el mismo estilo base que `Clientes`.

## Comportamiento visible relevante

- Seleccionar una fila del listado izquierdo carga detalle, pedido, albaranes, facturas y pendientes.
- `Fecha` y `Numero` del detalle se guardan automáticamente tras edición.
- En `Pedido`, `Albarán` y `Factura` hay fila de totales fija fuera del scroll.
- El botón `Ayuda` muestra un mensaje informativo de uso básico de la ventana.

## Diálogos y flujos relacionados

- `AlbaranPreviewDialog` (QDialog)
- `FacturaPreviewDialog` (QDialog)
- `FacturaItemEditDialog` (QDialog)
- `AddPedidoLineDialog` (QDialog)
- `EditPedidoLineDialog` (QDialog)
- `NewPedidoDialog` (QDialog)
