# Ventana Dashboard - PySide6 / Backend

## Implementación principal

```text
Dashboard
├── UI
│   └── app/ui/widgets/dashboard_page.py
├── Clases visuales
│   ├── DashboardPage
│   │   └── Página principal y selector de dashboards
│   ├── DashboardMonthCalendar
│   │   └── Calendario mensual personalizado de Agenda
│   ├── DashboardAgendaDialog
│   │   └── Alta y edición de actividades
│   └── DashboardAgendaOverviewDialog
│       └── Listado completo de la agenda
└── Servicios
    ├── app/services/customer_dashboard_service.py
    ├── app/services/customer_service.py
    ├── app/services/order_dashboard_service.py
    ├── app/services/sales_dashboard_service.py
    └── app/services/warehouse_dashboard_service.py
```

## Árbol estructural actual

```text
DashboardPage (QWidget, dashboardPageRoot)
└── root_layout (QHBoxLayout)
    ├── dashboardSidebar (QFrame, 184 px)
    │   ├── dashboardSidebarBrand (QLabel, logo IREKS)
    │   ├── Agenda (dashboardSidebarButton)
    │   ├── Pedidos (dashboardSidebarButton)
    │   ├── Almacen (dashboardSidebarButton)
    │   ├── Ventas (dashboardSidebarButton)
    │   ├── Objetivos (dashboardSidebarButton, placeholder)
    │   └── stretch
    └── dashboardContentHost (QWidget)
        └── dashboardContent (QWidget)
            ├── dashboardHeader (QFrame)
            │   ├── bloque de título y fecha
            │   │   ├── dashboardTitle
            │   │   └── dashboardDateLabel
            │   ├── dashboardNewActivityButton
            │   └── dashboardFullAgendaButton
            ├── dashboardContentStack (QStackedWidget)
            │   ├── dashboardAgendaView
            │   ├── dashboardOrdersView
            │   ├── dashboardSalesView
            │   └── dashboardWarehouseView
            └── dashboardFooterLabel
```

## Contenedor principal y navegación

```text
dashboardPageRoot
├── Aspecto
│   ├── fondo: #EEF3F8
│   └── fuente: Segoe UI
├── root_layout
│   ├── tipo: QHBoxLayout
│   ├── márgenes: 0 px
│   └── separación: 0 px
├── dashboardSidebar
│   ├── ancho fijo: 184 px
│   ├── layout: QVBoxLayout
│   ├── márgenes: 16 / 22 / 16 / 18 px
│   ├── separación: 24 px
│   ├── fondo: #F8FAFC
│   ├── borde derecho: #E2E8F0
│   ├── logo IREKS: 144 px de ancho
│   └── botones: altura mínima de 58 px
├── Orden de navegación
│   ├── Agenda
│   ├── Pedidos
│   ├── Almacen
│   ├── Ventas
│   └── Objetivos
├── Iconos laterales
│   ├── Agenda: calendar-days.svg
│   ├── Pedidos: shopping-cart.svg
│   ├── Almacen: warehouse.svg
│   ├── Ventas: bar-chart-3.svg
│   └── Objetivos: goal.svg
├── Estado activo
│   ├── fondo: #2563EB
│   └── texto e icono: blanco
├── dashboardContent
│   ├── márgenes: 22 / 16 / 22 / 12 px
│   └── separación vertical: 12 px
└── Elementos no utilizados
    ├── QSplitter: no existe
    ├── QScrollArea global: no existe
    └── React: no interviene
```

## Cabecera común

```text
dashboardHeader
├── Aspecto
│   ├── fondo: transparente
│   └── borde: ninguno
├── dashboardTitle
│   ├── contenido: título del modo
│   ├── tamaño: 30 px
│   └── peso: 700
├── dashboardDateLabel
│   ├── contenido: fecha, mes o año contextual
│   └── tamaño: 14 px
├── dashboardNewActivityButton
│   └── acción primaria azul
├── dashboardFullAgendaButton
│   └── acción secundaria blanca
└── Variantes por modo
    ├── Agenda
    │   ├── auxiliar: fecha larga actual
    │   ├── primaria: Nueva actividad
    │   └── secundaria: Ver agenda completa
    ├── Pedidos
    │   ├── auxiliar: año del snapshot
    │   ├── primaria: Ver pedidos
    │   └── secundaria: Actualizar
    ├── Almacen
    │   ├── auxiliar: mes y año del snapshot
    │   ├── primaria: Ver almacen
    │   └── secundaria: Actualizar
    └── Ventas
        ├── auxiliar: año actual frente al anterior
        ├── primaria: Ver ventas
        └── secundaria: Actualizar
```

## Componentes compartidos

```text
Componentes de dashboard
├── Vista de cada modo
│   ├── layout: QVBoxLayout
│   ├── márgenes: 0 px
│   └── separación: 12 px
├── Fila KPI
│   └── cuatro dashboardKpiCard
│       ├── altura fija: 104 px
│       ├── márgenes internos: 16 / 14 / 16 / 14 px
│       ├── dashboardKpiIconWrap: 62 x 62 px
│       ├── SVG: 28 x 28 px
│       ├── contenido
│       │   ├── título
│       │   ├── valor
│       │   └── nota
│       └── tone
│           ├── blue
│           ├── red
│           ├── green
│           └── orange
├── Paneles dashboardPanel=true
│   ├── fondo: blanco
│   ├── borde: #DCE4EF
│   ├── radio: 16 px
│   ├── márgenes internos: 14 px
│   └── separación: 10 px
└── Tablas embebidas
    ├── solo lectura
    ├── sin selección
    ├── sin cuadrícula
    ├── sin ajuste de línea
    ├── filas alternas
    ├── cabecera: altura mínima de 34 px
    └── filas: 32 px
```

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
│   │   ├── dashboardMonthCalendar
│   │   │   └── navegación mensual nativa integrada
│   │   └── dashboardCalendarSummaryChip
│   │       ├── altura fija: 34 px
│   │       ├── Pendientes
│   │       ├── Hechas
│   │       └── Vencidas
│   └── dashboardTodayPanel
│       ├── dashboardPanelTitle fijo en la parte superior
│       └── dashboardTodayScrollArea
│           └── dashboardTodayItemsHost
│               └── dashboardActivityCard o dashboardEmptyLabel
└── fila inferior (proporción 5:3)
    ├── dashboardReactivationPanel
    │   └── dashboardReactivationTable
    └── dashboardIslandPanel
        └── dashboardIslandTable
```

### Calendario mensual

```text
Calendario mensual de Agenda
├── dashboardUpcomingPanel
│   ├── altura mínima: 312 px
│   ├── tamaño horizontal: expandible
│   ├── tamaño vertical: expandible
│   └── ancho máximo explícito: no tiene
├── dashboardTodayPanel
│   ├── altura mínima: 205 px
│   ├── proporción frente al calendario: 6 frente a 4
│   ├── dashboardPanelTitle fuera del desplazamiento
│   └── dashboardTodayScrollArea
│       ├── desplazamiento vertical solo para las tarjetas
│       ├── contenido alineado arriba
│       └── sin botón de enlace inferior
├── dashboardMonthCalendar
│   ├── tamaño mínimo: 320 x 220 px
│   ├── política horizontal: Expanding
│   ├── política vertical: Expanding
│   ├── ocupa el espacio restante del dashboardUpcomingPanel
│   ├── primer día: lunes
│   ├── cabecera: nombres cortos
│   ├── columna ISO de semanas: visible
│   ├── navegación nativa: visible
│   │   ├── fondo transparente
│   │   ├── borde gris con esquinas redondeadas
│   │   ├── mes y año en negro a 13 px
│   │   └── flechas circulares verdes
│   ├── cuadrícula fina: visible
│   ├── fines de semana: rojo
│   └── edición directa: deshabilitada
├── DashboardCalendarDelegate
│   ├── cabeceras de días: fondo azul
│   ├── texto de todas las cabeceras: blanco
│   ├── números de semana: fondo azul
│   ├── azul: actividades pendientes
│   ├── verde: existe alguna actividad completada
│   ├── rojo: vencidas no completadas ni canceladas
│   ├── gris: días fuera del mes
│   ├── fecha seleccionada
│   │   ├── fondo gris claro
│   │   ├── borde gris oscuro de 2 px
│   │   └── texto negro
│   └── día actual
│       ├── fondo amarillo
│       ├── borde ámbar
│       └── texto oscuro en negrita
├── dashboardCalendarSummaryChip
│   ├── altura fija: 34 px
│   ├── márgenes internos: 10 / 3 / 10 / 3 px
│   ├── reparto horizontal: tres partes iguales
│   ├── texto del título: negro
│   ├── ancho del título: política Minimum para impedir que colapse
│   ├── texto del valor: negro
│   ├── ancho del valor: política Fixed
│   └── contenido conservado: título y valor
└── Interacción
    ├── flechas nativas: cambio de mes
    ├── fecha actual: título Agenda de hoy
    ├── otra fecha: título Agenda del dd/mm/aaaa
    ├── selección diaria: filtra por fecha efectiva `due_date`
    ├── número ISO de semana: muestra todas las entradas de lunes a domingo
    └── tarjetas diarias o semanales en una sola línea
        ├── código · nombre del cliente
        ├── resumen
        ├── estado traducido
        └── dashboardEmptyLabel cuando no hay datos
```

### Tablas de Agenda

```text
Tablas de Agenda
├── dashboardReactivationTable
│   ├── Cliente
│   ├── Isla
│   ├── Último contacto
│   ├── Variación kg
│   └── Prioridad
└── dashboardIslandTable
    ├── Isla
    ├── Pend.
    ├── Aplaz.
    ├── Hechas
    └── Total
```

## Vista Pedidos

```text
dashboardOrdersView
├── KPI
│   ├── Pedidos
│   ├── Kg recibidos
│   ├── Kg pendientes
│   └── Incidencias
├── fila superior (6:4)
│   ├── dashboardOrdersRecentPanel
│   │   └── dashboardOrdersRecentTable
│   │       ├── Pedido
│   │       ├── Almacen
│   │       ├── Fecha
│   │       ├── Kg pedido
│   │       ├── Kg recibido
│   │       ├── Kg pend.
│   │       └── Estado
│   └── dashboardOrdersPendingPanel
│       └── dashboardOrdersPendingTable
│           ├── Fecha
│           ├── Pedido
│           ├── Almacen
│           └── Kg pend.
├── fila inferior (5:3)
│   ├── dashboardOrdersWarehousePanel
│   │   └── dashboardOrdersWarehouseTable
│   │       ├── Almacen
│   │       ├── Abiertos
│   │       ├── Kg pend.
│   │       └── Últ. recepción
│   └── dashboardOrdersStatePanel
│       └── dashboardOrdersStateTable
│           ├── Estado
│           ├── Pedidos
│           └── Kg
└── Acciones
    ├── Ver pedidos: navega a la página Pedidos
    └── Actualizar: recarga el snapshot
```

## Vista Ventas

```text
dashboardSalesView
├── KPI
│   ├── Kg vendidos
│   ├── Variación kg
│   ├── Clientes activos
│   └── Islas activas
├── fila superior (6:4)
│   ├── dashboardSalesDropsPanel
│   │   └── dashboardSalesDropsTable
│   │       ├── Cliente
│   │       ├── Isla
│   │       ├── Kg ant.
│   │       ├── Kg act.
│   │       └── Δ Kg
│   └── dashboardSalesIslandsPanel
│       └── dashboardSalesIslandsTable
│           ├── Isla
│           ├── Clientes
│           ├── Kg act.
│           ├── Δ Kg
│           └── %
├── fila inferior (6:4)
│   ├── dashboardSalesTypesPanel
│   │   └── dashboardSalesTypesTable
│   │       ├── Tipo
│   │       ├── Clientes
│   │       ├── Kg act.
│   │       ├── Δ Kg
│   │       └── %
│   └── dashboardSalesZeroPanel
│       └── dashboardSalesZeroTable
│           ├── Cliente
│           ├── Isla
│           ├── Tipo
│           └── Kg ant.
├── KPI Variación kg
│   ├── verde: positiva o cero
│   └── rojo: negativa
└── Acciones
    ├── Ver ventas: navega a la página Ventas
    └── Actualizar: recarga el snapshot
```

## Vista Almacen

```text
dashboardWarehouseView
├── KPI
│   ├── Stock total
│   ├── Riesgos
│   ├── Entradas mes
│   └── Salidas mes
├── fila superior (6:4)
│   ├── dashboardWarehouseRiskPanel
│   │   └── dashboardWarehouseRiskTable
│   │       ├── Almacen
│   │       ├── Ref.
│   │       ├── Producto
│   │       ├── Lote
│   │       ├── Caduca
│   │       ├── Kg
│   │       └── Estado
│   └── dashboardWarehouseStockPanel
│       └── dashboardWarehouseStockTable
│           ├── Almacen
│           ├── Artículos
│           └── Stock kg
├── fila inferior (5:5)
│   ├── dashboardWarehouseEntriesPanel
│   │   └── dashboardWarehouseEntriesTable
│   │       ├── Fecha
│   │       ├── Almacen
│   │       ├── Ref.
│   │       ├── Producto
│   │       └── Kg
│   └── dashboardWarehouseOutputsPanel
│       └── dashboardWarehouseOutputsTable
│           ├── Fecha
│           ├── Almacen
│           ├── Ref.
│           ├── Producto
│           └── Kg
└── Acciones
    ├── Ver almacen: navega a la página Almacen
    └── Actualizar: recarga el snapshot
```

## Modal Nueva actividad / Editar actividad

```text
DashboardAgendaDialog (QDialog modal)
├── Geometría
│   ├── tamaño inicial: 620 x 520 px
│   └── redimensionable: sí
├── título: Actividad de agenda
├── QFormLayout
│   ├── Cliente (QComboBox)
│   │   ├── ancho mínimo: 340 px
│   │   ├── alta: excluye clientes inactivos
│   │   └── edición: incluye clientes inactivos
│   ├── Fecha actividad (QDateEdit)
│   ├── Tipo (QComboBox)
│   │   ├── Visita prevista
│   │   ├── Visita realizada
│   │   ├── Llamada
│   │   ├── Seguimiento
│   │   ├── Desarrollo futuro
│   │   ├── Incidencia
│   │   └── Nota
│   ├── Estado (QComboBox)
│   │   ├── Pendiente
│   │   ├── Hecha
│   │   ├── Aplazada
│   │   └── Cancelada
│   ├── Prioridad (QComboBox)
│   │   ├── Alta
│   │   ├── Media
│   │   ├── Normal
│   │   └── Baja
│   ├── Responsable (QLineEdit)
│   ├── Resumen (QLineEdit)
│   ├── Detalle (QTextEdit)
│   │   └── altura mínima: 120 px
│   └── Seguimiento
│       ├── Tiene seguimiento (QCheckBox)
│       └── fecha de seguimiento (QDateEdit)
├── Selectores de fecha
│   ├── popup: activo
│   ├── formato: dd/MM/yyyy
│   └── calendario interno: dashboardPopupCalendar
├── Valores iniciales de alta
│   ├── fecha actividad: día actual
│   ├── fecha seguimiento: día actual
│   ├── tipo: Seguimiento
│   ├── estado: Pendiente
│   ├── prioridad: Normal
│   └── seguimiento: desactivado
├── QDialogButtonBox
│   ├── Guardar
│   ├── Cancelar
│   └── Eliminar (solo en edición)
└── Persistencia
    ├── validación: cliente obligatorio
    ├── validación: resumen o detalle obligatorio
    └── servicio: CustomerService
```

## Modal Agenda completa

```text
DashboardAgendaOverviewDialog (QDialog)
├── Geometría
│   └── tamaño inicial: 1120 x 640 px
├── título: Agenda completa
├── summary_label
│   └── N actividad(es) activas en agenda
├── table (QTableWidget)
│   ├── solo lectura
│   ├── selección: una fila
│   ├── filas alternas
│   └── columnas
│       ├── Fecha
│       ├── Seguimiento
│       ├── Cliente
│       ├── Isla
│       ├── Tipo
│       ├── Estado
│       ├── Resumen
│       └── Responsable
├── fila de acciones
│   ├── Nueva actividad
│   ├── Editar
│   ├── stretch
│   └── Cerrar
└── Comportamiento
    ├── doble clic: editar actividad seleccionada
    ├── Nueva actividad: abre DashboardAgendaDialog en alta
    ├── Editar: abre DashboardAgendaDialog en edición
    ├── cambio guardado: refresca el listado
    └── cierre tras cambios: recarga DashboardPage
```

## Flujo de carga y datos

```text
Flujo del Dashboard
├── Inicio
│   ├── modo inicial: Agenda
│   └── reload(): actualiza solo el modo activo
├── CustomerDashboardService
│   ├── KPI de agenda
│   ├── actividades
│   ├── clientes a reactivar
│   └── resumen por isla
├── CustomerService
│   ├── carga de clientes
│   ├── alta de agenda
│   ├── edición de agenda
│   └── borrado de agenda
├── OrderDashboardService
│   ├── KPI de pedidos
│   ├── pedidos recientes
│   ├── pendientes
│   └── agregados por almacén y estado
├── SalesDashboardService
│   ├── KPI anuales
│   └── agregados por cliente, isla y tipo
├── WarehouseDashboardService
│   ├── KPI de stock
│   ├── riesgos
│   └── movimientos mensuales
├── dashboardFooterLabel
│   └── hora de generación y contexto del snapshot
└── Plataforma
    ├── PySide6 / backend local
    ├── base de datos local
    └── sin dependencia del frontend React
```

## Estado funcional actual

```text
Estado del Dashboard
├── Modos implementados
│   ├── Agenda
│   ├── Pedidos
│   ├── Ventas
│   └── Almacen
├── Modo pendiente
│   └── Objetivos
│       ├── no existe en dashboardContentStack
│       └── muestra un QMessageBox informativo
├── Desplazamiento
│   ├── QScrollArea global: no existe
│   └── QTableWidget: conserva scroll nativo cuando se necesita
└── Mutaciones
    ├── vistas agregadas: consulta
    └── diálogos de agenda: alta, edición y borrado
```
