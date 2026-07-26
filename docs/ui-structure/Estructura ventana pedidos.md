# VENTANA PEDIDOS — PYSIDE6 / BACKEND

Implementación principal:
- UI: app/ui/widgets/orders_page.py
- Estilos compartidos: assets/styles.qss
- Servicios principales:
- app/services/order_query_service.py
- app/services/order_service.py
- app/services/order_edit_flow_service.py
- app/services/order_selected_flow_service.py
- app/services/order_export_service.py
- app/services/order_mail_flow_service.py
- app/services/order_document_import_service.py
- app/services/orders_documents_import_ui_service.py
- app/services/orders_mail_settings_service.py
- Modelos: app/models/entities.py
- Pedido / PedidoItem / PedidoPendiente
- Albaran / AlbaranItem
- Factura / FacturaItem

OrdersPage (QWidget, sin objectName)
└── layout principal (QVBoxLayout, márgenes y separación heredados)
- ├── topRibbon (QFrame, pageType=contacts, fondo #FFFFFF, borde #E2E8F1)
- │   ├── new_btn (QPushButton "Nuevo", btnRole=success, icono file-text.svg, fondo #DCFCE7, texto #166534, borde #86EFAC)
- │   ├── edit_btn (QPushButton "Editar", btnRole=warning, icono file-pen.svg, fondo #FEF3C7, texto #92400E, borde #FCD34D)
- │   ├── del_btn (QPushButton "Eliminar", btnRole=danger, icono trash.svg, fondo #FEE2E2, texto #B91C1C, borde #FCA5A5)
- │   ├── export_btn (QPushButton "Exportar", btnRole=secondary, icono export.svg, fondo #E2E8F0, texto #334155, borde #CBD5E1)
- │   ├── send_mail_btn (QPushButton "Enviar Outlook", btnRole=secondary, icono mail.svg, fondo #E2E8F0, texto #334155, borde #CBD5E1)
- │   ├── print_btn (QPushButton "Imprimir", btnRole=secondary, icono printer.svg, fondo #E2E8F0, texto #334155, borde #CBD5E1)
- │   ├── espacio flexible
- │   └── help_btn (QPushButton "Ayuda", btnRole=secondary, icono circle-question-mark.svg, fondo #E2E8F0, texto #334155, borde #CBD5E1)
- └── splitter principal (QSplitter horizontal, sin objectName, fondo transparente, sin borde, tirador oculto)
- ├── sidePanel (QWidget, blanco #FFFFFF, borde #D7DEE8, radio 8 px, ancho 560–620 px)
- │   └── left_layout (QVBoxLayout, sin objectName)
- │       ├── filters_row (QHBoxLayout, sin objectName)
- │       │   ├── QLabel "Año" (sin objectName)
- │       │   ├── year_filter (QComboBox, sin objectName, ancho mínimo 90 px)
- │       │   ├── QLabel "Mes inicial" (sin objectName)
- │       │   ├── month_from_filter (QComboBox, sin objectName, ancho mínimo 120 px)
- │       │   ├── QLabel "Mes final" (sin objectName)
- │       │   └── month_to_filter (QComboBox, sin objectName, ancho mínimo 120 px)
- │       ├── almacen_row (QHBoxLayout, sin objectName)
- │       │   ├── QLabel "Cliente/Distribuidor" (sin objectName)
- │       │   └── almacen_filter (QComboBox, sin objectName, ancho mínimo 210 px)
- │       ├── table (QTableWidget, sin objectName, 6 columnas ordenables)
- │       │   ├── Almacen (180 px)
- │       │   ├── Nº (60 px)
- │       │   ├── Fecha (108 px)
- │       │   ├── Semana (60 px, orden numérico)
- │       │   ├── Total Kg (100 px, orden numérico y alineación derecha)
- │       │   └── Estado (55 px, centrado)
- │       │
## │       │   Comportamiento

- │       │   - selección de fila completa y única;
- │       │   - edición directa deshabilitada;
- │       │   - orden inicial por Semana descendente;
- │       │   - sin scroll horizontal;
- │       │   - estado E azul #1565C0, P naranja #EF6C00 y M rojo #C62828;
- │       │   - al seleccionar una fila carga detalle, pedido, albaranes,
- │       │     facturas y pendientes.
- │       └── table_totals (QTableWidget, 1 fila, sin objectName)
- │           ├── fila TOTAL fija fuera del scroll
- │           ├── Total Kg en la quinta columna
- │           └── anchos sincronizados con table
- │
- └── right_panel (QWidget, sin objectName, fondo azul #0000FF, sin borde)
- └── right_layout (QVBoxLayout, sin márgenes, separación 6 px)
- └── right_splitter (QSplitter vertical, sin objectName, fondo verde #008000, sin borde)
- ├── detailPanel (QWidget, fondo #FCFDFF, borde #E2E8F1, radio 8 px, alto máximo 170 px)
- │   └── detail_layout (QVBoxLayout, márgenes 14 px, separación 8 px)
- │       ├── detail_title (QLabel "Detalle del pedido", role=sectionTitle, sin objectName)
- │       └── row_1 (QHBoxLayout, sin objectName)
- │           ├── QLabel "Semana" (sin objectName)
- │           ├── detail_semana (QLineEdit, solo lectura, 50 px)
- │           ├── QLabel "Fecha" (sin objectName)
- │           ├── detail_fecha (QDateEdit, calendario desplegable, formato dd/MM/yyyy)
- │           ├── QLabel "Numero" (sin objectName)
- │           └── detail_pedido_numero (QLineEdit, 100 px)
- │
## │       Comportamiento

- │       - Fecha y Numero se guardan automáticamente tras 350 ms;
- │       - Semana es informativa y no editable.
- │
- └── tabs_panel (QWidget, sin objectName)
- └── tabs (QTabWidget, sin objectName)
- ├── pedido_tab (QWidget, pestaña "Pedido", sin objectName)
- │   ├── topRibbon (QFrame; comparte objectName con las demás cintas)
- │   │   ├── add_line_btn (QPushButton "Añadir", btnRole=success)
- │   │   ├── edit_line_btn (QPushButton "Editar", btnRole=warning)
- │   │   ├── del_line_btn (QPushButton "Eliminar", btnRole=danger, icono trash.svg)
- │   │   ├── edit_order_btn (QPushButton "Editar pedido", btnRole=warning)
- │   │   └── espacio flexible
- │   ├── pedido_items_table (QTableWidget, sin objectName, ordenable)
- │   │   ├── Cod. (95 px)
- │   │   ├── Nombre (ancho flexible)
- │   │   ├── Cantidad (90 px, editable)
- │   │   └── Kg (100 px)
- │   └── pedido_items_totals_table (QTableWidget, fila TOTAL fija)
- │       ├── total de Cantidad
- │       ├── total de Kg
- │       └── anchos sincronizados con pedido_items_table
- │
- ├── albaran_tab (QWidget, pestaña "Albarán", sin objectName)
- │   ├── topRibbon (QFrame)
- │   │   ├── import_albaran_btn (QPushButton "Imp. Albarán", btnRole=warning)
- │   │   └── espacio flexible
- │   ├── albaran_filter_row (QHBoxLayout, sin objectName)
- │   │   ├── QLabel "Albaran" (sin objectName)
- │   │   └── albaran_selector (QComboBox, sin objectName; Todos o albarán concreto)
- │   ├── albaran_items_table (QTableWidget, sin objectName, ordenable)
- │   │   ├── Cod. (95 px)
- │   │   ├── Nº albarán (120 px)
- │   │   ├── Nombre (ancho flexible)
- │   │   ├── Cantidad (90 px)
- │   │   └── Kg (100 px)
- │   └── albaran_items_totals_table (QTableWidget, fila TOTAL fija)
- │       ├── total de Cantidad
- │       ├── total de Kg
- │       └── anchos sincronizados con albaran_items_table
- │
- ├── factura_tab (QWidget, pestaña "Factura", sin objectName)
- │   ├── topRibbon (QFrame)
- │   │   ├── import_factura_btn (QPushButton "Imp. Factura", btnRole=warning)
- │   │   ├── edit_factura_line_btn (QPushButton "Editar línea", btnRole=primary)
- │   │   ├── delete_factura_btn (QPushButton "Eliminar Factura", btnRole=danger, icono trash.svg)
- │   │   └── espacio flexible
- │   └── factura_content (QSplitter horizontal, sin objectName, tirador oculto)
- │       ├── facturas_table (QTableWidget, sin objectName, ancho fijo 120 px)
- │       │   └── Factura
- │       └── factura_items_panel (QWidget, sin objectName)
- │           ├── factura_items_table (QTableWidget, sin objectName, ordenable)
- │           │   ├── Cod. (86 px)
- │           │   ├── Nombre (ancho flexible)
- │           │   ├── Uds. (60 px)
- │           │   ├── Kg/Lit. (78 px)
- │           │   └── Precio (82 px)
- │           └── factura_items_totals_table (QTableWidget, fila TOTAL fija)
- │               ├── total de Uds.
- │               ├── total de Kg/Lit.
- │               └── total de importe
- │
- └── pendientes_tab (QWidget, pestaña "Pendientes", sin objectName)
- └── pendientes_table (QTableWidget, sin objectName, 6 columnas)
- ├── Cod. (95 px)
- ├── Nombre (ancho flexible)
- ├── Pedida (90 px)
- ├── Recibida (90 px)
- ├── Pendiente (100 px; positivo verde #2E7D32 y negativo rojo #C62828)
- └── Estado (90 px)

# GEOMETRÍA ACTUAL

- El splitter principal es horizontal, tiene fondo transparente, no tiene borde
- y arranca aproximadamente en 580 / 660 px.
- sidePanel tiene ancho mínimo de 560 px y máximo de 620 px.
- El tirador del splitter principal está oculto y deshabilitado.
- right_splitter es vertical:
- detailPanel tiene un alto máximo de 170 px;
- tabs_panel recibe el espacio restante con factor de expansión 10.
- factura_content reserva 120 px para facturas_table y el resto para sus líneas.
- Los tiradores de factura_content están ocultos y deshabilitados.
- Las filas de totales miden 30 px y permanecen fuera del scroll de sus tablas.

# ASPECTO VISUAL ACTUAL

- La ventana usa los estilos globales de assets/styles.qss.
- sidePanel es blanco #FFFFFF, con borde gris azulado #D7DEE8 y radio de 8 px.
- detailPanel usa fondo #FCFDFF, borde #E2E8F1 y radio 8 px.
- El topRibbon principal usa pageType=contacts: fondo #FFFFFF, borde completo
- #E2E8F1, radio 8 px y botones compactos de 26 px, igual que Clientes.
- Los topRibbon interiores son blancos #FFFFFF y tienen borde inferior #D7DEE8.
- Botones por función:
- success: verde pastel #DCFCE7, texto #166534;
- warning: amarillo pastel #FEF3C7, texto #92400E;
- danger: rojo pastel #FEE2E2, texto #B91C1C;
- secondary: gris azulado #E2E8F0, texto #334155;
- primary: azul pastel #DBEAFE, texto #1D4ED8.
- Tablas: fondo #FFFFFF, filas alternas #F7F9FC, borde #D8E0EA.
- Los artículos pendientes o sin correspondencia se resaltan en rojo #C62828.
- En albaranes, los excesos respecto al pedido se resaltan en verde #2E7D32.
- En facturas, las discrepancias de precio se resaltan en rojo #C62828.

# DIÁLOGOS Y FLUJOS RELACIONADOS

Ayuda de pedidos (QMessageBox informativo)
- Explica las acciones de la cinta superior, los filtros y las pestañas de detalle.

AlbaranPreviewDialog (QDialog, sin objectName, 980 × 620 px)
- Previsualiza cabecera y seis columnas del albarán extraído.
- Tabla solo lectura: Código / Descripción / Kilos / Envases / Lote / Cons.Pref.
- Acciones: Importar / Cancelar.

FacturaPreviewDialog (QDialog, sin objectName, 1120 × 680 px)
- Previsualiza cabecera y once columnas de la factura extraída.
- Precio con discrepancia en rojo #C62828.
- Acciones: Importar / Cancelar.

FacturaItemEditDialog (QDialog, sin objectName, 940 × 280 px)
- Edita número y fecha de factura, albarán, artículo, cantidades, lote,
- caducidad, precio, descuento y total.
- Valida números y fechas antes de aceptar.

AddPedidoLineDialog (QDialog, sin objectName, 760 × 520 px)
- filter_edit (QLineEdit, sin objectName): busca por código o nombre.
- table (QTableWidget, sin objectName): Cod. / Nombre.
- Doble clic o Aceptar devuelve el artículo seleccionado.

EditPedidoLineDialog (QDialog, sin objectName, 900 × 360 px)
- filter_edit (QLineEdit amarillo #FFF4CC): filtro de artículos.
- search_table (QTableWidget): Referencia / Nombre.
- ref_edit, nombre_edit y peso_edit: datos informativos de solo lectura.
- cantidad_edit (QLineEdit amarillo #FFF4CC): cantidad editable.
- total_edit: peso total calculado y de solo lectura.

NewPedidoDialog (QDialog, sin objectName, 980 × 620 px)
- Se reutiliza para Nuevo pedido y Editar pedido.
- fecha_edit (QDateEdit): fecha del pedido.
- numero_edit (QLineEdit): número opcional.
- fabricante_filter / familia_filter / subfamilia_filter (QComboBox).
- search_edit (QLineEdit): búsqueda por referencia o nombre.
- only_nonzero_check (QCheckBox): muestra solo unidades distintas de cero.
- table (QTableWidget, 7 columnas):
- Ref. / Nombre / Peso / Uds. / Total kg / Pedido ant. / Pendiente.
- totals_lbl: total de unidades y kg.
- move_up_btn / move_down_btn: desplazan la selección.
- pending_btn: guarda como pendiente cuando el flujo lo permite.
- Cancelar y Consignar/Guardar completan el pie.

Otros flujos:
- Nuevo pedido: selecciona Cliente/Distribuidor, abre NewPedidoDialog y crea
- Pedido/PedidoItem o PedidoPendiente según el modo elegido.
- Editar pedido: reutiliza NewPedidoDialog con líneas y cabecera precargadas.
- Exportar: genera Excel del pedido seleccionado mediante OrderExportService.
- Enviar Outlook: prepara Excel, destinatario, asunto y cuerpo; muestra una
- previsualización antes de abrir el envío por Outlook.
- Imprimir: exporta temporalmente el pedido y lanza la impresión configurada.
- Importar albarán: analiza PDF, muestra AlbaranPreviewDialog y persiste tras
- confirmación.
- Importar factura: analiza PDF/OCR, muestra FacturaPreviewDialog y persiste
- tras confirmación.
- Eliminar pedido, línea o factura: requiere confirmación.

# RELACIÓN CON BACKEND / DATOS

- OrdersPage trabaja directamente con servicios Python y la base SQLite local.
- OrderQueryService concentra las lecturas de pedidos, líneas, albaranes,
- facturas, pendientes, periodos y catálogos del diálogo.
- OrderService gestiona altas, edición y eliminación de pedidos y líneas.
- OrderEditFlowService y OrderSelectedFlowService coordinan edición y guardado
- del pedido seleccionado.
- OrderDocumentImportService y OrdersDocumentsImportUiService coordinan la
- lectura, validación, correspondencia e importación de albaranes y facturas.
- OrderExportService genera los documentos Excel.
- OrderMailFlowService y OrdersMailSettingsService preparan el envío por Outlook.
- La selección de una fila de table es el contexto para cargar todas las
- pestañas del panel derecho.

# OBSERVACIONES DE ESTRUCTURA

- OrdersPage, los splitters, tabs y la mayoría de controles no tienen objectName.
- topRibbon se reutiliza como objectName en cuatro QFrame diferentes:
- cinta principal, Pedido, Albarán y Factura.
- Solo la cinta principal usa pageType=contacts y está situada encima del
- splitter principal; las otras tres permanecen dentro de sus pestañas.
- Los nombres usados en este documento son los atributos Python reales cuando
- existen; los elementos locales se identifican por su variable y se marcan
- expresamente como "sin objectName".
- No existe una hoja QSS específica de OrdersPage: la apariencia depende de
- assets/styles.qss y de algunos estilos locales en los diálogos y tablas.

- La pesta?a `Pendientes` muestra el acumulado de art?culos pendientes del mismo almac?n del pedido seleccionado.
- Si un albar?n de otro pedido recibe mercanc?a que cubre un pendiente anterior del mismo almac?n, la lista se actualiza en este acumulado y mantiene el n?mero de pedido origen.
