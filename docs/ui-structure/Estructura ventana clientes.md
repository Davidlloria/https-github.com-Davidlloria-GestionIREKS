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
    │   ├── Nuevo (verde claro #DCFCE7, texto #166534, icono `assets/icons/user-round-plus.svg`, ancho fijo común del ribbon, icono 16 px)
    │   ├── Editar (amarillo claro #FEF3C7, texto #92400E, icono `assets/icons/file-pen.svg`, ancho fijo común del ribbon, icono 16 px)
    │   ├── Eliminar (rojo claro #FEE2E2, texto #B91C1C, icono `assets/icons/trash.svg`, ancho fijo común del ribbon, icono 16 px)
    │   ├── Listados (gris azulado #E2E8F0, texto #334155, icono `assets/icons/list.svg`, ancho fijo común del ribbon, icono 16 px)
    │   ├── Actualizar (violeta claro #F3E8FF, texto #6B21A8, icono `assets/icons/refresh-cw.svg`, ancho fijo común del ribbon, icono 16 px)
    │   ├── customerQueriesButton (QPushButton, etiqueta "Consultas", icono `assets/icons/brain.svg`, ancho fijo común del ribbon, icono 16 px)
    │   ├── espacio flexible
    │   └── Ayuda (gris azulado #E2E8F0, texto #334155, icono `assets/icons/circle-question-mark.svg`, ancho fijo común del ribbon, icono 16 px)
    └── customersMainSplitter (QSplitter horizontal, fondo transparente, sin borde, tirador oculto)
        ├── customersLeftPanel (QWidget, fondo blanco #FFFFFF, borde #D7DEE8)
        │   └── layout vertical (QVBoxLayout, márgenes 14 px, separación 10 px)
        │       ├── filtro de isla (QComboBox, blanco #FFFFFF, borde #D1D5DB, ancho 390 px)
        │       ├── fila de búsqueda
        │       │   ├── buscador "Buscar cliente..." (QLineEdit, blanco #FFFFFF, borde #D1D5DB, ancho 220 px)
        │       │   ├── contador `encontrados/totales` (QLabel, objectName `customerSearchCounterLabel`, formato `xxx/yyy`)
        │       │   └── limpiar filtro (QPushButton rojo #EF4444, texto blanco, 30 × 30 px, alineado al final de la fila)
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
                            │   ├── relatedContactsTable (QTableWidget, 5 columnas, tableVariant="standard")
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
                            │   ├── customerSalesTable (QTableWidget, 5 columnas ordenables, tableVariant="standard"; columna Kg con sufijo "kg"; columna € con sufijo "€")
                            │   │   ├── Referencia
                            │   │   ├── Descripción
                            │   │   ├── Unid.
                            │   │   ├── Kg
                            │   │   └── €
                            │   ├── customerSalesTotals (QTableWidget, fila fija de totales, columnas sincronizadas con la tabla, columnas 1-2 unificadas visualmente, separadores verticales visibles, fondo pastel #EEF4FF, alto 34 px, Kg con sufijo "kg", € con sufijo "€", resincronización diferida al mostrar la pestaña)
                            │   ├── customerSalesEmpty (QLabel, permanece oculto; la tabla de ventas se muestra siempre)
                            │   └── QDialog comparativa de ventas (tamaño inicial 1360 × 720 px)
                            │       ├── cabecera con nombre del cliente y contexto de comparación (órden: año anterior vs año actual · Unid. / Kg / €)
                            │       ├── customerSalesComparisonGroupsBar (QWidget con pastillas sincronizadas: año anterior / año actual / Diferencia)
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
                            │       ├── customerSalesComparisonTotals (QTableWidget, fila fija de totales, columnas sincronizadas, primeras 2 columnas unificadas, fondo pastel #EEF4FF, Kg con sufijo "kg", € con sufijo "€")
                            │       ├── customerSalesEmpty (QLabel, visible si la comparativa no tiene filas)
                            │       └── pie en una línea (QHBoxLayout, botones con ancho fijo común y color por acción)
                            │           ├── customerSalesComparisonChartButton (QPushButton "Graf.", icono `assets/icons/chart-no-axes-combined.svg`, color info)
                            │           │   └── abre `CustomerSalesComparisonChartDialog` con barras comparativas en kg
                            │           ├── customerSalesComparisonExcelButton (QPushButton "Excel", icono `assets/icons/sheet.svg`, color success)
                            │           │   └── exporta Excel mediante `ReportExportService.export_excel(...)`
                            │           ├── customerSalesComparisonPdfButton (QPushButton "Pdf", icono `assets/icons/file-text.svg`, color primary)
                            │           │   └── exporta PDF mediante `ReportExportService.export_customer_sales_comparison_pdf(...)`
                            │           └── customerSalesComparisonCloseButton (QPushButton "Cerrar", color danger)
                            ├── Recetas
                            │   ├── customerRecipesPanel (QWidget, fondo verde #0BF75D)
                            │   ├── relatedRecipesTable (QTableWidget, 3 columnas)
                            │   │   ├── Nº
                            │   │   ├── Receta
                            │   │   └── Versión
                            │   ├── doble clic: abre la receta
                            │   └── relatedRecipesEmpty (QLabel, estado vacío)
                            └── Agenda
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
```

## Comportamiento actual

- `customersListTable` usa selección de fila completa y única.
- La edición directa en el listado de clientes está deshabilitada.
- El orden inicial del listado es ascendente por código.
- Al seleccionar un cliente se recargan detalle, contactos, ventas, recetas y agenda.
- `customerSalesYearFilter` carga años disponibles desde `CustomerService.related_sales_years()`.
- La pestaña Ventas carga datos desde `CustomerService.related_sales(cliente_id, year)`.
- `customerSalesCompareButton` solo se habilita si hay comparativa posible.
- La comparativa colorea deltas positivos en verde `#067647` y negativos en rojo `#B42318`, también en la fila de totales.
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
- Los filtros de agenda usan texto a 11 px; las fechas se muestran centradas en los QDateEdit.

## Diálogos y flujos relacionados

- Nuevo / Editar cliente: `EntityDialog` con el esquema de `Cliente`.
- Eliminar cliente: confirmación antes de borrar.
- Listados: diálogo asistido mediante `CustomerReportFlowService`.
- `customerQueriesDialog` (QDialog modal): consultas read-only sobre clientes.
- La comparativa de ventas abre un QDialog propio desde la pestaña Ventas.
- El gráfico de comparativa usa `CustomerSalesComparisonChartDialog`.
- El PDF de comparativa usa `ReportExportService`.
- Agenda: diálogo modal para crear o editar actividad con tipo (una única opción `Visita` sustituye a `Visita prevista` y `Visita realizada`, conservando también `Demo` y los demás tipos), fecha, estado, resumen, detalle y seguimiento. El estado determina si la visita está pendiente o completada. Los selectores de fecha muestran un calendario emergente compacto, con semana iniciada en lunes, cabeceras y números de semana sobre fondo azul, cuadrícula fina y fines de semana destacados en rojo.
- Ayuda: diálogo explicativo de la ventana Clientes.

## Relación con backend / datos

- `CustomersPage` no consume el frontend React ni depende de sus componentes.
- La UI llama a `CustomerService` para clientes, contactos, ventas, recetas y agenda.
- `CustomerService` trabaja con los modelos SQLAlchemy y la base de datos local.
- Los listados usan `CustomerReportIntentService`, `CustomerReportService`, `CustomerReportFlowService` y `ReportExportService`.
- La selección de cliente actúa como contexto para cargar toda la información relacionada.

## Últimos ajustes relevantes

- Restaurada la pestaña Ventas desde el placeholder a una tabla funcional con filtro de año.
- Restaurada la comparativa anual con modal, grafico y exportacion PDF; el titulo muestra solo cliente y anos, y las columnas numericas ordenan por valor real.
- Corregida la geometría documentada de `detailLeftCard` y `detailRightCard` para que coincida con el código real.
- Actualizado el fondo real de `CustomersPageRoot` a `#EEF3F8` y alineada la documentación.

## Modales principales

- Modal `Nuevo cliente` / `Editar cliente`: `QDialog`, fondo `#EEF3F8`, tamano fijo `958 x 418 px`.
- Cuerpo con dos tarjetas centradas horizontalmente y con margen lateral equilibrado: `detailLeftCard` (`590 x 300 px`) y `detailRightCard` (`300 x 300 px`).
- Tarjeta izquierda: mismo formato visual que el detalle del cliente para `Cod.`, `Nombre Comercial`, `Telef.`, `C.I.F.`, `Nombre Fiscal`, `Provincia`, `Isla`, `Municipio`, `Calle`, `C.P.` y `Localidad`.
- Tarjeta derecha: mismo formato visual que la clasificacion del cliente para `Actividad`, `Tipo`, `Abrev. pedido`, `ACTIVO / INACTIVO` y `Prospeccion Si / No`.
- Pie de acciones: `Cancelar` con estilo secundario gris azulado y `Guardar` con estilo primario azul.
