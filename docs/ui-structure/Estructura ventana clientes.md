# VENTANA CLIENTES ? PYSIDE6 / BACKEND

Implementaci?n principal:
- UI: `app/ui/widgets/customers_page.py`
- Servicio: `app/services/customer_service.py`
- Modelos: `app/models.py`

## Estructura UI real

```text
CustomersPage (QWidget, objectName: CustomersPageRoot, fondo transparente)
??? layout principal (QVBoxLayout, m?rgenes 14 px, separaci?n 10 px)
    ??? t?tulo de p?gina "Clientes" (QLabel, actualmente oculto)
    ??? topRibbon (QFrame, fondo blanco #FFFFFF, borde #E2E8F1)
    ?   ??? Nuevo (verde claro #DCFCE7, texto #166534)
    ?   ??? Editar (amarillo claro #FEF3C7, texto #92400E)
    ?   ??? Eliminar (rojo claro #FEE2E2, texto #B91C1C)
    ?   ??? Imprimir (gris azulado #E2E8F0, texto #334155)
    ?   ??? Exportar (QPushButton + QMenu, azul claro #DBEAFE, texto #1D4ED8)
    ?   ?   ??? Listados
    ?   ?   ??? Importar Excel/CSV
    ?   ?   ??? ID
    ?   ??? Actualizar (violeta claro #F3E8FF, texto #6B21A8)
    ?   ??? customerQueriesButton (QPushButton, etiqueta "Consultas", icono `assets/icons/brain.svg`)
    ?   ??? espacio flexible
    ?   ??? Ayuda (gris azulado #E2E8F0, texto #334155)
    ??? customersMainSplitter (QSplitter horizontal, transparente, tirador oculto)
        ??? customersLeftPanel (QWidget, blanco #FFFFFF, borde #D7DEE8)
        ?   ??? layout vertical (QVBoxLayout, m?rgenes 14 px, separaci?n 10 px)
        ?       ??? filtro de isla (QComboBox, blanco #FFFFFF, borde #D1D5DB, ancho 390 px)
        ?       ??? fila de b?squeda
        ?       ?   ??? buscador "Buscar cliente..." (QLineEdit, blanco #FFFFFF, borde #D1D5DB, ancho 352 px)
        ?       ?   ??? limpiar filtro (QPushButton rojo #EF4444, texto blanco, 30 ? 30 px)
        ?       ??? customersListTable (QTableWidget, blanco #FFFFFF, alterno #FAFBFF, selecci?n #3A78CF, ancho 390 px)
        ?           ??? Cod. (60 px)
        ?           ??? Nombre (268 px)
        ?           ??? Isla (48 px)
        ??? customersRightPanel (QWidget, fondo transparente)
            ??? layout vertical sin m?rgenes
                ??? customersDetailSplitter (QSplitter vertical, fondo transparente, sin borde)
                    ??? detailTopArea (QWidget, fondo transparente, ancho fijo 932 px, alto 300 px)
                    ?   ??? t?tulo "Detalle de cliente"
                    ?   ??? t?tulo "Clasificaci?n del cliente"
                    ?   ??? detailLeftCard (QFrame, blanco #FFFFFF, borde #D7DEE8)
                    ?   ?   ??? ficha principal del cliente
                    ?   ?       ??? c?digo
                    ?   ?       ??? nombre comercial
                    ?   ?       ??? tel?fono
                    ?   ?       ??? CIF
                    ?   ?       ??? nombre fiscal
                    ?   ?       ??? provincia / isla / municipio
                    ?   ?       ??? calle / CP / localidad
                    ?   ??? detailRightCard (QFrame, blanco #FFFFFF, borde #D7DEE8)
                    ?       ??? clasificaci?n del cliente
                    ?           ??? actividades / sectores seleccionables
                    ?           ??? tipo de cliente
                    ?           ??? abreviatura de pedido
                    ?           ??? estado Activo / Inactivo
                    ?           ??? prospecci?n S? / No
                    ??? crmCard (QWidget, fondo transparente, alto m?nimo 300 px, expansi?n vertical)
                        ??? customerTabs (QTabWidget, panel transparente; pesta?as blanco #FFFFFF / gris #F8FAFC; activa azul #3B82F6)
                            ??? Contactos
                            ?   ??? relatedContactsPanel (QWidget)
                            ?   ??? relatedContactsTable (QTableWidget, 5 columnas)
                            ?   ?   ??? Avatar
                            ?   ?   ??? Nombre
                            ?   ?   ??? Cargo
                            ?   ?   ??? Tel?fono
                            ?   ?   ??? Email
                            ?   ??? doble clic: abre el contacto
                            ?   ??? men? contextual: alta / edici?n relacionada
                            ?   ??? relatedContactsEmpty (QLabel, estado vac?o)
                            ??? Ventas
                            ?   ??? customerSalesPanel (QWidget)
                            ?   ??? fila de acciones (QHBoxLayout)
                            ?   ?   ??? customerSalesYearFilter (QComboBox, selector de a?o)
                            ?   ?   ??? customerSalesCompareButton (QPushButton "Comp.", se habilita si hay cliente, a?o y filas)
                            ?   ??? customerSalesTable (QTableWidget, 5 columnas ordenables)
                            ?   ?   ??? Referencia
                            ?   ?   ??? Descripci?n
                            ?   ?   ??? Unid.
                            ?   ?   ??? Kg
                            ?   ?   ??? ?
                            ?   ??? customerSalesTotals (QTableWidget, fila fija de totales)
                            ?   ??? customerSalesEmpty (QLabel, visible si no hay ventas)
                            ?   ??? QDialog comparativa de ventas
                            ?       ??? cabecera con nombre del cliente
                            ?       ??? customerSalesComparisonGroups (QTableWidget, grupos: a?o anterior / a?o seleccionado / Diferencia)
                            ?       ??? customerSalesComparisonTable (QTableWidget, 11 columnas ordenables)
                            ?       ?   ??? Referencia
                            ?       ?   ??? Descripci?n
                            ?       ?   ??? Unid. a?o anterior
                            ?       ?   ??? Kg a?o anterior
                            ?       ?   ??? ? a?o anterior
                            ?       ?   ??? Unid. a?o seleccionado
                            ?       ?   ??? Kg a?o seleccionado
                            ?       ?   ??? ? a?o seleccionado
                            ?       ?   ??? ? Unid.
                            ?       ?   ??? ? Kg
                            ?       ?   ??? ? ?
                            ?       ??? customerSalesComparisonTotals (QTableWidget, fila fija de totales)
                            ?       ??? customerSalesEmpty (QLabel, visible si la comparativa no tiene filas)
                            ?       ??? pie en una l?nea (QHBoxLayout)
                            ?           ??? customerSalesComparisonChartButton (QPushButton "Graf.", icono `assets/icons/chart-no-axes-combined.svg`)
                            ?           ?   ??? abre `CustomerSalesComparisonChartDialog` con barras comparativas en kg
                            ?           ??? customerSalesComparisonPdfButton (QPushButton "Pdf", icono `assets/icons/file-text.svg`)
                            ?           ?   ??? exporta PDF mediante `ReportExportService.export_customer_sales_comparison_pdf(...)`
                            ?           ??? customerSalesComparisonCloseButton (QPushButton "Cerrar")
                            ??? Recetas
                            ?   ??? relatedRecipesTable (QTableWidget, 3 columnas)
                            ?   ?   ??? N?
                            ?   ?   ??? Receta
                            ?   ?   ??? Versi?n
                            ?   ??? doble clic: abre la receta
                            ?   ??? relatedRecipesEmpty (QLabel, estado vac?o)
                            ??? Agenda
                                ??? t?tulo "Historial de actividades"
                                ??? fila de filtros
                                ?   ??? tipo
                                ?   ??? estado
                                ?   ??? fecha desde
                                ?   ??? fecha hasta
                                ?   ??? Actualizar
                                ??? customerAgendaTable (QTableWidget, 6 columnas)
                                ?   ??? icono de tipo
                                ?   ??? Fecha
                                ?   ??? Tipo
                                ?   ??? Estado
                                ?   ??? Resumen
                                ?   ??? Seguimiento
                                ??? doble clic: abre la actividad
                                ??? men? contextual: Nueva / Editar / Eliminar
                                ??? customerAgendaEmpty (QLabel, estado vac?o)
```

## Comportamiento actual

- `customersListTable` usa selecci?n de fila completa y ?nica.
- La edici?n directa en el listado de clientes est? deshabilitada.
- El orden inicial del listado es ascendente por c?digo.
- Al seleccionar un cliente se recargan detalle, contactos, ventas, recetas y agenda.
- `customerSalesYearFilter` carga a?os disponibles desde `CustomerService.related_sales_years()`.
- La pesta?a Ventas carga datos desde `CustomerService.related_sales(cliente_id, year)`.
- `customerSalesCompareButton` solo se habilita si hay comparativa posible.
- La comparativa colorea deltas positivos en verde `#067647` y negativos en rojo `#B42318`.
- El gr?fico depende opcionalmente de `pyqtgraph`; si no est? instalado, el di?logo informa de ello.

## Geometr?a actual del detalle

- El panel izquierdo del splitter principal queda limitado a un m?ximo de 400 px.
- `detailTopArea` mide 932 ? 300 px.
- Las dos tarjetas usan geometr?a absoluta dentro de `detailTopArea`:
  - `detailLeftCard`: x=5, y=25, ancho=540, alto=270.
  - separaci?n entre tarjetas: 5 px.
  - `detailRightCard`: x=550, y=25, ancho=290, alto=270.
- El bloque inferior de pesta?as tiene un m?nimo de 300 px y ocupa el resto del alto.
- Los tiradores de ambos splitters est?n ocultos y deshabilitados.
- `resizeEvent` reaplica proporciones y geometr?as para conservar el dise?o.

## Aspecto visual actual

- `CustomersPageRoot`, `detailTopArea` y `customersRightPanel` tienen fondo transparente.
- `customersLeftPanel` es blanco, con borde gris `#D7DEE8` y radio de 8 px.
- `detailLeftCard` y `detailRightCard` son blancas, con borde gris y radio de 8 px.
- La cinta superior usa botones compactos con colores por funci?n e iconos.
- Inputs y combos son blancos, con borde gris, radio de 8 px y foco azul.
- La fila seleccionada de clientes usa fondo azul `#3A78CF` y texto blanco.
- Las pesta?as tienen fondo blanco/gris claro y la activa se identifica en azul.
- Contactos, ventas, recetas y agenda usan tablas blancas con bordes suaves.
- La Agenda muestra iconos circulares por tipo y estados con color.

## Di?logos y flujos relacionados

- Nuevo / Editar cliente: `EntityDialog` con el esquema de `Cliente`.
- Eliminar cliente: confirmaci?n antes de borrar.
- Listados: di?logo asistido mediante `CustomerReportFlowService`.
- `customerQueriesDialog` (QDialog modal): consultas read-only sobre clientes.
- La comparativa de ventas abre un QDialog propio desde la pesta?a Ventas.
- El gr?fico de comparativa usa `CustomerSalesComparisonChartDialog`.
- El PDF de comparativa usa `ReportExportService`.
- Agenda: di?logo modal para crear o editar actividad con tipo, fecha, estado, resumen, detalle y seguimiento.
- Ayuda: di?logo explicativo de la ventana Clientes.

## Relaci?n con backend / datos

- `CustomersPage` no consume el frontend React ni depende de sus componentes.
- La UI llama a `CustomerService` para clientes, contactos, ventas, recetas y agenda.
- `CustomerService` trabaja con los modelos SQLAlchemy y la base de datos local.
- Los listados usan `CustomerReportIntentService`, `CustomerReportService`, `CustomerReportFlowService` y `ReportExportService`.
- La selecci?n de cliente act?a como contexto para cargar toda la informaci?n relacionada.

## ?ltimos ajustes relevantes

- Restaurada la pesta?a Ventas desde el placeholder a una tabla funcional con filtro de a?o.
- Restaurada la comparativa anual con modal, gr?fico y exportaci?n PDF.
- Corregida la geometr?a documentada de `detailLeftCard` y `detailRightCard` para que coincida con el c?digo real.
