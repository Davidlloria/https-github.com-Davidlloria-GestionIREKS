# VENTANA CLIENTES — PYSIDE6 / BACKEND

Implementación principal:
- UI: `app/ui/widgets/customers_page.py`
- Servicio: `app/services/customer_service.py`
- Modelos: `app/models.py`

## Estructura UI real

```text
CustomersPage (QWidget, objectName: CustomersPageRoot, fondo gris #EEF3F8, sin borde, WA_StyledBackground=True)
└── layout principal (QVBoxLayout, márgenes 14 px, separación 10 px)
    ├── título de página "Clientes" (QLabel, actualmente oculto)
    ├── topRibbon (QFrame, fondo blanco #FFFFFF, borde #E2E8F1)
    │   ├── Nuevo (verde claro #DCFCE7, texto #166534)
    │   ├── Editar (amarillo claro #FEF3C7, texto #92400E)
    │   ├── Eliminar (rojo claro #FEE2E2, texto #B91C1C)
    │   ├── Imprimir (gris azulado #E2E8F0, texto #334155)
    │   ├── Exportar (QPushButton + QMenu, azul claro #DBEAFE, texto #1D4ED8)
    │   │   ├── Listados
    │   │   ├── Importar Excel/CSV
    │   │   └── ID
    │   ├── Actualizar (violeta claro #F3E8FF, texto #6B21A8)
    │   ├── customerQueriesButton (QPushButton, etiqueta "Consultas", icono `assets/icons/brain.svg`)
    │   ├── espacio flexible
    │   └── Ayuda (gris azulado #E2E8F0, texto #334155)
    └── customersMainSplitter (QSplitter horizontal, fondo transparente, sin borde, tirador oculto)
        ├── customersLeftPanel (QWidget, fondo blanco #FFFFFF, borde #D7DEE8)
        │   └── layout vertical (QVBoxLayout, márgenes 14 px, separación 10 px)
        │       ├── filtro de isla (QComboBox, blanco #FFFFFF, borde #D1D5DB, ancho 390 px)
        │       ├── fila de búsqueda
        │       │   ├── buscador "Buscar cliente..." (QLineEdit, blanco #FFFFFF, borde #D1D5DB, ancho 352 px)
        │       │   └── limpiar filtro (QPushButton rojo #EF4444, texto blanco, 30 × 30 px)
        │       └── customersListTable (QTableWidget, blanco #FFFFFF, alterno #FAFBFF, selección #3083FF, cabecera gris #D1D1D1 con esquina superior izquierda redondeada y separadores grises, ancho 390 px, tableVariant="standard")
        │           ├── Cod. (60 px)
        │           ├── Nombre (268 px)
        │           └── Isla (48 px)
        └── customersRightPanel (QWidget, fondo transparente, sin borde)
            └── layout vertical sin márgenes
                └── customersDetailSplitter (QSplitter vertical, fondo transparente, sin borde)
                    ├── detailTopArea (QWidget, fondo transparente, sin borde, x=0, y=0, ancho 932 px, alto 300 px)
                    │   ├── detailLeftCard (QFrame, blanco #FFFFFF, borde #D7DEE8, x=5, y=0, ancho 590 px, alto 300 px)
                    │   │   ├── título "Detalle de cliente"
                    │   │   └── ficha principal del cliente
                    │   │       ├── código
                    │   │       ├── nombre comercial
                    │   │       ├── teléfono
                    │   │       ├── CIF
                    │   │       ├── nombre fiscal
                    │   │       ├── provincia / isla / municipio
                    │   │       └── calle / CP / localidad
                    │   └── detailRightCard (QFrame, blanco #FFFFFF, borde #D7DEE8, x=600, y=0, ancho 300 px, alto 300 px)
                    │       ├── título "Clasificación del cliente"
                    │       └── clasificación del cliente
                    │           ├── actividades / sectores seleccionables
                    │           ├── tipo de cliente
                    │           ├── abreviatura de pedido
                    │           ├── estado Activo / Inactivo
                    │           └── prospección Sí / No
                    └── crmCard (QWidget, fondo transparente, sin borde, radio 8 px, alto mínimo 300 px, expansión vertical)
                        └── customerTabs (QTabWidget, panel verde #DCFCE7; pestañas blanco #FFFFFF / gris #F8FAFC; activa azul #3B82F6, x=5, y=5, ancho=crmCard-10 px, alto=crmCard-10 px)
                            ├── Contactos
                            │   ├── relatedContactsPanel (QWidget, fondo verde #0BF75D)
                            │   ├── relatedContactsTable (QTableWidget, 5 columnas)
                            │   │   ├── Avatar
                            │   │   ├── Nombre
                            │   │   ├── Cargo
                            │   │   ├── Teléfono
                            │   │   └── Email
                            │   ├── doble clic: abre el contacto
                            │   ├── menú contextual: alta / edición relacionada
                            │   └── relatedContactsEmpty (QLabel, estado vacío)
                            ├── Ventas
                            │   ├── customerSalesPanel (QWidget, fondo verde #0BF75D)
                            │   ├── fila de acciones (QHBoxLayout)
                            │   │   ├── customerSalesYearFilter (QComboBox, selector de año)
                            │   │   └── customerSalesCompareButton (QPushButton "Comp.", se habilita si hay cliente, año y filas)
                            │   ├── customerSalesTable (QTableWidget, 5 columnas ordenables)
                            │   │   ├── Referencia
                            │   │   ├── Descripción
                            │   │   ├── Unid.
                            │   │   ├── Kg
                            │   │   └── €
                            │   ├── customerSalesTotals (QTableWidget, fila fija de totales)
                            │   ├── customerSalesEmpty (QLabel, visible si no hay ventas)
                            │   └── QDialog comparativa de ventas
                            │       ├── cabecera con nombre del cliente
                            │       ├── customerSalesComparisonGroups (QTableWidget, grupos: año anterior / año seleccionado / Diferencia)
                            │       ├── customerSalesComparisonTable (QTableWidget, 11 columnas ordenables)
                            │       │   ├── Referencia
                            │       │   ├── Descripción
                            │       │   ├── Unid. año anterior
                            │       │   ├── Kg año anterior
                            │       │   ├── € año anterior
                            │       │   ├── Unid. año seleccionado
                            │       │   ├── Kg año seleccionado
                            │       │   ├── € año seleccionado
                            │       │   ├── Δ Unid.
                            │       │   ├── Δ Kg
                            │       │   └── Δ €
                            │       ├── customerSalesComparisonTotals (QTableWidget, fila fija de totales)
                            │       ├── customerSalesEmpty (QLabel, visible si la comparativa no tiene filas)
                            │       └── pie en una línea (QHBoxLayout)
                            │           ├── customerSalesComparisonChartButton (QPushButton "Graf.", icono `assets/icons/chart-no-axes-combined.svg`)
                            │           │   └── abre `CustomerSalesComparisonChartDialog` con barras comparativas en kg
                            │           ├── customerSalesComparisonPdfButton (QPushButton "Pdf", icono `assets/icons/file-text.svg`)
                            │           │   └── exporta PDF mediante `ReportExportService.export_customer_sales_comparison_pdf(...)`
                            │           └── customerSalesComparisonCloseButton (QPushButton "Cerrar")
                            ├── Recetas
                            │   ├── customerRecipesPanel (QWidget, fondo verde #0BF75D)
                            │   ├── relatedRecipesTable (QTableWidget, 3 columnas)
                            │   │   ├── Nº
                            │   │   ├── Receta
                            │   │   └── Versión
                            │   ├── doble clic: abre la receta
                            │   └── relatedRecipesEmpty (QLabel, estado vacío)
                            └── Agenda
                                ├── título "Historial de actividades"
                                ├── fila de filtros
                                │   ├── tipo
                                │   ├── estado
                                │   ├── fecha desde
                                │   ├── fecha hasta
                                │   └── Actualizar
                                ├── customerAgendaTable (QTableWidget, 6 columnas)
                                │   ├── icono de tipo
                                │   ├── Fecha
                                │   ├── Tipo
                                │   ├── Estado
                                │   ├── Resumen
                                │   └── Seguimiento
                                ├── doble clic: abre la actividad
                                ├── menú contextual: Nueva / Editar / Eliminar
                                └── customerAgendaEmpty (QLabel, estado vacío)
```

## Comportamiento actual

- `customersListTable` usa selección de fila completa y única.
- La edición directa en el listado de clientes está deshabilitada.
- El orden inicial del listado es ascendente por código.
- Al seleccionar un cliente se recargan detalle, contactos, ventas, recetas y agenda.
- `customerSalesYearFilter` carga años disponibles desde `CustomerService.related_sales_years()`.
- La pestaña Ventas carga datos desde `CustomerService.related_sales(cliente_id, year)`.
- `customerSalesCompareButton` solo se habilita si hay comparativa posible.
- La comparativa colorea deltas positivos en verde `#067647` y negativos en rojo `#B42318`.
- El gráfico depende opcionalmente de `pyqtgraph`; si no está instalado, el diálogo informa de ello.

## Geometría actual del detalle

- El panel izquierdo del splitter principal queda limitado a un máximo de 400 px.
- `detailTopArea`: x=0, y=0, ancho=932, alto=300.
- Las dos tarjetas usan geometría absoluta dentro de `detailTopArea`:
- `detailLeftCard`: x=5, y=0, ancho=590, alto=300.
  - separación entre tarjetas: 5 px.
- `detailRightCard`: x=600, y=0, ancho=300, alto=300.
- El bloque inferior de pestañas tiene un mínimo de 300 px y ocupa el resto del alto.
- Los tiradores de ambos splitters están ocultos y deshabilitados.
- `resizeEvent` reaplica proporciones y geometrías para conservar el diseño.

## Aspecto visual actual

- `CustomersPageRoot` tiene fondo gris `#EEF3F8`, sin borde y `WA_StyledBackground=True`; `customersMainSplitter` usa fondo transparente y sin borde; `customersDetailSplitter` usa fondo transparente y sin borde; `detailTopArea` usa fondo transparente y sin borde; `customersRightPanel` tiene fondo transparente y sin borde.
- `customersLeftPanel` tiene fondo blanco `#FFFFFF`, borde gris `#D7DEE8` y radio de 8 px.
- `detailLeftCard` y `detailRightCard` son blancas, con borde gris y radio de 8 px.
- `customerTabs`: x=5, y=5, ancho=crmCard-10, alto=crmCard-10, panel verde `#0BF75D` en las páginas internas (rellena `crmCard` con márgenes uniformes de 5 px).
- La cinta superior usa botones compactos con colores por función e iconos.
- Inputs y combos son blancos, con borde gris, radio de 8 px y foco azul.
- La fila seleccionada de clientes usa fondo azul `#3A78CF` y texto blanco.
- Las pestañas tienen fondo blanco/gris claro y la activa se identifica en azul.
- Contactos, ventas, recetas y agenda usan tablas blancas con bordes suaves.
- La Agenda muestra iconos circulares por tipo y estados con color.

## Diálogos y flujos relacionados

- Nuevo / Editar cliente: `EntityDialog` con el esquema de `Cliente`.
- Eliminar cliente: confirmación antes de borrar.
- Listados: diálogo asistido mediante `CustomerReportFlowService`.
- `customerQueriesDialog` (QDialog modal): consultas read-only sobre clientes.
- La comparativa de ventas abre un QDialog propio desde la pestaña Ventas.
- El gráfico de comparativa usa `CustomerSalesComparisonChartDialog`.
- El PDF de comparativa usa `ReportExportService`.
- Agenda: diálogo modal para crear o editar actividad con tipo, fecha, estado, resumen, detalle y seguimiento.
- Ayuda: diálogo explicativo de la ventana Clientes.

## Relación con backend / datos

- `CustomersPage` no consume el frontend React ni depende de sus componentes.
- La UI llama a `CustomerService` para clientes, contactos, ventas, recetas y agenda.
- `CustomerService` trabaja con los modelos SQLAlchemy y la base de datos local.
- Los listados usan `CustomerReportIntentService`, `CustomerReportService`, `CustomerReportFlowService` y `ReportExportService`.
- La selección de cliente actúa como contexto para cargar toda la información relacionada.

## Últimos ajustes relevantes

- Restaurada la pestaña Ventas desde el placeholder a una tabla funcional con filtro de año.
- Restaurada la comparativa anual con modal, gráfico y exportación PDF.
- Corregida la geometría documentada de `detailLeftCard` y `detailRightCard` para que coincida con el código real.
- Actualizado el fondo real de `CustomersPageRoot` a `#EEF3F8` y alineada la documentación.
