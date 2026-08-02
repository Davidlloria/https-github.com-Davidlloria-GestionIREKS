# Ventana Dashboard - PySide6 / Backend

## Implementación principal

- UI: `app/ui/widgets/dashboard_page.py`
- Clases visuales:
  - `DashboardPage`: página principal y selector de dashboards.
  - `DashboardMonthCalendar`: calendario mensual personalizado de Agenda.
  - `DashboardAgendaDialog`: alta y edición de actividades.
  - `DashboardAgendaOverviewDialog`: listado completo de la agenda.
- Servicios:
  - `app/services/customer_dashboard_service.py`
  - `app/services/customer_service.py`
  - `app/services/order_dashboard_service.py`
  - `app/services/sales_dashboard_service.py`
  - `app/services/warehouse_dashboard_service.py`

## Árbol estructural actual

```text
DashboardPage (QWidget, dashboardPageRoot)
├── root_layout (QHBoxLayout)
│   ├── dashboardSidebar (QFrame, 184 px)
│   │   ├── dashboardSidebarBrand (QLabel, logo IREKS)
│   │   ├── Agenda (dashboardSidebarButton)
│   │   ├── Pedidos (dashboardSidebarButton)
│   │   ├── Almacen (dashboardSidebarButton)
│   │   ├── Ventas (dashboardSidebarButton)
│   │   ├── Objetivos (dashboardSidebarButton, placeholder)
│   │   └── stretch
│   └── dashboardContentHost (QWidget)
│       └── dashboardContent (QWidget)
│           ├── dashboardHeader (QFrame)
│           │   ├── bloque de título y fecha
│           │   │   ├── dashboardTitle
│           │   │   └── dashboardDateLabel
│           │   ├── dashboardNewActivityButton
│           │   └── dashboardFullAgendaButton
│           ├── dashboardContentStack (QStackedWidget)
│           │   ├── dashboardAgendaView
│           │   ├── dashboardOrdersView
│           │   ├── dashboardSalesView
│           │   └── dashboardWarehouseView
│           └── dashboardFooterLabel
```

`Objetivos` no tiene widget propio dentro de `dashboardContentStack`; su botón muestra un `QMessageBox` informativo.

## Contenedor principal y navegación

- `dashboardPageRoot` usa fondo `#EEF3F8` y fuente `Segoe UI`.
- El layout raíz es un `QHBoxLayout` sin márgenes ni separación.
- `dashboardSidebar`:
  - ancho fijo de `184 px`;
  - layout vertical con márgenes `16/22/16/18 px`;
  - separación de `24 px`;
  - fondo `#F8FAFC` y borde derecho `#E2E8F0`;
  - logo IREKS escalado a `144 px` de ancho;
  - botones con altura mínima de `58 px`.
- El orden real de navegación es `Agenda`, `Pedidos`, `Almacen`, `Ventas`, `Objetivos`.
- Iconos laterales:
  - Agenda: `calendar-days.svg`;
  - Pedidos: `shopping-cart.svg`;
  - Almacen: `warehouse.svg`;
  - Ventas: `bar-chart-3.svg`;
  - Objetivos: `goal.svg`.
- Solo el modo activo usa fondo azul `#2563EB` y texto/icono blanco.
- `dashboardContent` usa márgenes `22/16/22/12 px` y separación vertical de `12 px`.
- No hay `QSplitter`, `QScrollArea` global ni vista React implicada.

## Cabecera común

- `dashboardHeader` contiene:
  - `dashboardTitle`: título del modo, `30 px`, peso `700`;
  - `dashboardDateLabel`: fecha, mes o año contextual, `14 px`;
  - `dashboardNewActivityButton`: acción primaria azul;
  - `dashboardFullAgendaButton`: acción secundaria blanca.
- Los textos e iconos cambian con el modo:

| Modo | Título auxiliar | Acción primaria | Acción secundaria |
|---|---|---|---|
| Agenda | Fecha larga actual | Nueva actividad | Ver agenda completa |
| Pedidos | Año del snapshot | Ver pedidos | Actualizar |
| Almacen | Mes y año del snapshot | Ver almacen | Actualizar |
| Ventas | Año actual frente al anterior | Ver ventas | Actualizar |

## Componentes compartidos por los cuatro dashboards

- Cada vista usa un `QVBoxLayout` sin márgenes y con separación de `12 px`.
- La primera fila contiene cuatro `dashboardKpiCard`.
- Cada tarjeta KPI:
  - altura fija de `118 px`;
  - márgenes internos `16/14/16/14 px`;
  - icono dentro de `dashboardKpiIconWrap`, círculo de `62 x 62 px`;
  - SVG renderizado a `28 x 28 px`;
  - título, valor y nota;
  - borde inferior azul, rojo, verde o naranja según `tone`.
- Los paneles de contenido se crean con `dashboardPanel=true`:
  - fondo blanco;
  - borde `#DCE4EF`;
  - radio de `16 px`;
  - márgenes internos de `14 px`;
  - separación de `10 px`.
- Las tablas embebidas son de solo lectura, sin selección, sin cuadrícula, sin ajuste de línea y con filas alternas.
- Las cabeceras de tabla tienen una altura mínima de `34 px`; las filas usan `32 px`.

## Vista Agenda

```text
dashboardAgendaView
├── fila KPI (4 tarjetas)
│   ├── Pendientes hoy
│   ├── Vencidas
│   ├── Completadas hoy
│   └── Clientes sin seguimiento
├── fila media (proporción 4:6)
│   ├── dashboardUpcomingPanel
│   │   ├── dashboardCalendarHeadingBlock
│   │   │   └── dashboardPanelTitle: Agenda del mes
│   │   ├── dashboardCalendarNavBlock
│   │   │   ├── dashboardCalendarNavButton: <
│   │   │   ├── dashboardMonthTitle
│   │   │   └── dashboardCalendarNavButton: >
│   │   ├── dashboardMonthCalendar
│   │   └── 3 dashboardCalendarSummaryChip
│   │       ├── Pendientes
│   │       ├── Hechas
│   │       └── Vencidas
│   └── dashboardTodayPanel
│       ├── dashboardPanelTitle dinámico
│       ├── dashboardActivityCard o dashboardEmptyLabel
│       └── dashboardPanelLinkButton: Ver toda la agenda
└── fila inferior (proporción 5:3)
    ├── dashboardReactivationPanel
    │   └── dashboardReactivationTable
    └── dashboardIslandPanel
        └── dashboardIslandTable
```

### Calendario mensual

- `dashboardUpcomingPanel` tiene altura fija de `312 px`; no tiene ancho máximo explícito.
- `dashboardTodayPanel` se crea como panel de lista con altura mínima de `205 px` y absorbe seis partes de la fila frente a cuatro del calendario.
- Cabecera, navegación y calendario comparten un ancho de `276 px` y quedan centrados.
- `dashboardMonthCalendar`:
  - tamaño fijo `276 x 196 px`;
  - semana iniciada en lunes;
  - cabecera de días con una sola letra;
  - columna ISO de números de semana;
  - barra de navegación nativa oculta;
  - cuadrícula nativa oculta;
  - edición directa de fecha deshabilitada.
- `paintCell()` dibuja celdas redondeadas:
  - azul para actividades pendientes;
  - verde si existe alguna actividad completada;
  - rojo para vencidas no completadas ni canceladas;
  - gris para días fuera del mes;
  - borde azul de `2 px` para la fecha seleccionada;
  - día actual en negrita.
- Los botones `<` y `>` cambian la página mensual.
- Seleccionar una fecha actualiza `dashboardTodayPanel` y su título:
  - `Agenda de hoy` para la fecha actual;
  - `Agenda del dd/mm/aaaa` para otra fecha.
- Las tarjetas diarias muestran cliente, resumen y detalle. Si no hay datos se usa `dashboardEmptyLabel`.

### Tablas de Agenda

- `dashboardReactivationTable`:
  - `Cliente / Isla / Último contacto / Variación kg / Prioridad`.
- `dashboardIslandTable`:
  - `Isla / Pend. / Aplaz. / Hechas / Total`.

## Vista Pedidos

```text
dashboardOrdersView
├── KPI: Pedidos / Kg recibidos / Kg pendientes / Incidencias
├── fila superior (6:4)
│   ├── dashboardOrdersRecentPanel
│   └── dashboardOrdersPendingPanel
└── fila inferior (5:3)
    ├── dashboardOrdersWarehousePanel
    └── dashboardOrdersStatePanel
```

- `dashboardOrdersRecentTable`:
  - `Pedido / Almacen / Fecha / Kg pedido / Kg recibido / Kg pend. / Estado`.
- `dashboardOrdersPendingTable`:
  - `Fecha / Pedido / Almacen / Kg pend.`.
- `dashboardOrdersWarehouseTable`:
  - `Almacen / Abiertos / Kg pend. / Últ. recepción`.
- `dashboardOrdersStateTable`:
  - `Estado / Pedidos / Kg`.
- `Ver pedidos` navega a la página principal `Pedidos` mediante `MainWindow` cuando está disponible.
- `Actualizar` vuelve a cargar el snapshot de pedidos.

## Vista Ventas

```text
dashboardSalesView
├── KPI: Kg vendidos / Variación kg / Clientes activos / Islas activas
├── fila superior (6:4)
│   ├── dashboardSalesDropsPanel
│   └── dashboardSalesIslandsPanel
└── fila inferior (6:4)
    ├── dashboardSalesTypesPanel
    └── dashboardSalesZeroPanel
```

- `dashboardSalesDropsTable`:
  - `Cliente / Isla / Kg ant. / Kg act. / Δ Kg`.
- `dashboardSalesIslandsTable`:
  - `Isla / Clientes / Kg act. / Δ Kg / %`.
- `dashboardSalesTypesTable`:
  - `Tipo / Clientes / Kg act. / Δ Kg / %`.
- `dashboardSalesZeroTable`:
  - `Cliente / Isla / Tipo / Kg ant.`.
- La variación anual del KPI usa verde si es positiva o cero y rojo si es negativa.
- `Ver ventas` navega a la página principal `Ventas`; `Actualizar` recarga el snapshot.

## Vista Almacen

```text
dashboardWarehouseView
├── KPI: Stock total / Riesgos / Entradas mes / Salidas mes
├── fila superior (6:4)
│   ├── dashboardWarehouseRiskPanel
│   └── dashboardWarehouseStockPanel
└── fila inferior (5:5)
    ├── dashboardWarehouseEntriesPanel
    └── dashboardWarehouseOutputsPanel
```

- `dashboardWarehouseRiskTable`:
  - `Almacen / Ref. / Producto / Lote / Caduca / Kg / Estado`.
- `dashboardWarehouseStockTable`:
  - `Almacen / Artículos / Stock kg`.
- `dashboardWarehouseEntriesTable` y `dashboardWarehouseOutputsTable`:
  - `Fecha / Almacen / Ref. / Producto / Kg`.
- `Ver almacen` navega a la página principal `Almacen`; `Actualizar` recarga el snapshot.

## Modal Nueva actividad / Editar actividad

`DashboardAgendaDialog` es un `QDialog` modal redimensionable, con tamaño inicial `620 x 520 px`.

```text
DashboardAgendaDialog
├── título: Actividad de agenda
├── QFormLayout
│   ├── Cliente (QComboBox)
│   ├── Fecha actividad (QDateEdit)
│   ├── Tipo (QComboBox)
│   ├── Estado (QComboBox)
│   ├── Prioridad (QComboBox)
│   ├── Responsable (QLineEdit)
│   ├── Resumen (QLineEdit)
│   ├── Detalle (QTextEdit, alto mínimo 120 px)
│   └── Seguimiento
│       ├── Tiene seguimiento (QCheckBox)
│       └── fecha de seguimiento (QDateEdit)
└── QDialogButtonBox
    ├── Guardar
    ├── Cancelar
    └── Eliminar (solo en edición)
```

- El selector de cliente mide como mínimo `340 px` y excluye clientes inactivos en altas; en edición los incluye para poder conservar la relación existente.
- Los dos selectores de fecha usan popup, formato `dd/MM/yyyy` y `objectName=dashboardPopupCalendar` en el calendario interno.
- Tipos actuales: `Visita prevista`, `Visita realizada`, `Llamada`, `Seguimiento`, `Desarrollo futuro`, `Incidencia`, `Nota`.
- Estados actuales: `Pendiente`, `Hecha`, `Aplazada`, `Cancelada`.
- Prioridades: `Alta`, `Media`, `Normal`, `Baja`.
- Valores iniciales de un alta:
  - fecha de actividad y seguimiento: día actual;
  - tipo: `Seguimiento`;
  - estado: `Pendiente`;
  - prioridad: `Normal`;
  - seguimiento desactivado.
- Guardar exige cliente y al menos resumen o detalle.
- El alta, edición y borrado se realizan mediante `CustomerService`.

## Modal Agenda completa

`DashboardAgendaOverviewDialog` es un `QDialog` de tamaño inicial `1120 x 640 px`.

```text
DashboardAgendaOverviewDialog
├── título: Agenda completa
├── summary_label: N actividad(es) activas en agenda
├── table (QTableWidget, 8 columnas)
└── fila de acciones
    ├── Nueva actividad
    ├── Editar
    ├── stretch
    └── Cerrar
```

- Columnas: `Fecha / Seguimiento / Cliente / Isla / Tipo / Estado / Resumen / Responsable`.
- La tabla es de solo lectura, con selección de una fila y filas alternas.
- Doble clic o `Editar` abre `DashboardAgendaDialog` para la actividad seleccionada.
- `Nueva actividad` abre el mismo diálogo en modo alta.
- Tras un cambio, el listado se refresca y el Dashboard se recarga al cerrar el modal.

## Flujo de carga y datos

- El Dashboard arranca en modo Agenda y `reload()` solo actualiza el modo activo.
- `CustomerDashboardService` aporta KPI de agenda, actividades, clientes a reactivar y resumen por isla.
- `CustomerService` aporta clientes y las operaciones de alta, edición y borrado de agenda.
- `OrderDashboardService` aporta KPI, pedidos recientes, pendientes y agregados por almacén y estado.
- `SalesDashboardService` aporta KPI y agregados anuales por cliente, isla y tipo.
- `WarehouseDashboardService` aporta KPI de stock, riesgos y movimientos mensuales.
- `dashboardFooterLabel` muestra la hora de generación y el contexto propio de cada snapshot.
- Todo el flujo pertenece a PySide6/backend local y trabaja contra la base local; no depende del frontend React.

## Estado funcional actual

- Implementados: `Agenda`, `Pedidos`, `Ventas`, `Almacen`.
- Pendiente: `Objetivos`, actualmente solo muestra un mensaje informativo.
- `DashboardPage` no añade un `QScrollArea` global; cada `QTableWidget` conserva su desplazamiento nativo cuando el contenido lo requiere.
- Las vistas agregadas son de consulta; las únicas mutaciones de esta ventana pertenecen a los diálogos de agenda.
