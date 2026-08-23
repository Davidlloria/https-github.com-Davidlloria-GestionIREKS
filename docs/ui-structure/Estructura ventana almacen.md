# VENTANA ALMACÉN — PYSIDE6 / BACKEND

Implementación principal:

- UI: `app/ui/widgets/warehouse_page.py` (`WarehousePage`)
- Catálogo de artículos: `app/ui/widgets/ingredients_page.py` (`IngredientsIreksPage`, modo compacto)
- Servicios principales:
  - `app/services/warehouse_catalog_service.py`
  - `app/services/warehouse_movement_service.py`
  - `app/services/warehouse_inventory_service.py`
  - `app/services/warehouse_manual_move_flow_service.py`
  - `app/services/warehouse_history_flow_service.py`
  - `app/services/warehouse_count_template_flow_service.py`
  - `app/services/monthly_orders_service.py`
  - `app/services/warehouse_reference_service.py`
- Modelos y datos relevantes: artículos IREKS, movimientos de almacén, lotes, caducidades, pedidos, fabricantes, familias, subfamilias, envases y referencias de distribuidor.

La sección se registra como `Almacen` en `app/ui/main_window.py` y se construye con `WarehousePage`.

## Estructura UI real

```text
WarehousePage (QWidget, objectName `warehousePage`, fondo gris #EEF3F8, sin borde, WA_StyledBackground=True)
└── layout principal (QVBoxLayout, márgenes 10 / 8 / 10 / 10 px, separación 6 px)
    ├── warehouseScopeBar (QFrame, fondo blanco #FFFFFF, borde #D6E0EA, radio 10 px)
    │   ├── icono `data-scope.svg` (25 px)
    │   ├── “ÁMBITO DE DATOS” (QLabel, #64748B, 9 px, negrita)
    │   ├── “Cliente / distribuidor” (QLabel, #0B2F5B, 13 px, negrita)
    │   └── almacen_combo / warehouseScopeCombo (QComboBox expansible; “Todos” + clientes directos/distribuidores)
    └── main_tabs / warehouseMainTabs (QTabWidget, fondo transparente, sin borde)
        ├── Artículos
    │   └── IngredientsIreksPage (QWidget, `compact_mode=True`; sin título de página
    │       ni ribbon propios; margen izquierdo local 0 px, fondo #EEF3F8)
    │       ├── ireksMainSplitter (QSplitter horizontal, separación visual 5 px)
    │       ├── sidePanel / catálogo lateral (QWidget, ancho fijo 420 px, fondo #FFFFFF,
    │       │   borde #D7DEE8 de 1 px, radio 10 px)
    │       │   ├── catalogHeader (QFrame, alto fijo 54 px, ancho completo, fondo #0B2F5B,
    │       │   │   sin borde; radios superiores 9 px e inferiores rectos)
    │       │   │   ├── icono `product-tag.svg` recoloreado en blanco, 20 × 20 px
    │       │   │   ├── “CATÁLOGO DE PRODUCTOS” (QLabel, blanco, 14 px, negrita)
    │       │   │   └── “Filtra y selecciona productos” (QLabel, #CDECE8, 10 px)
    │       │   └── catalogBody (QWidget, fondo #FFFFFF, sin borde; radios inferiores 9 px;
    │       │       márgenes 10 px, separación interna 8 px)
    │       │       ├── filtersGrid (QGridLayout 2 × 2; separación horizontal 8 px,
    │       │       │   vertical 6 px; columnas equitativas)
    │       │       │   ├── Fabricante / fabricante_filter (QComboBox: “Todos”)
    │       │       │   ├── Estado / activity_filter (QComboBox: Todos, Activos, Inactivos)
    │       │       │   ├── Familia / familia_filter (QComboBox: “Todas”)
    │       │       │   └── Subfamilia / subfamilia_filter (QComboBox: “Todas”)
    │       │       │       └── Cada etiqueta: #5E6C84, 10 px, seminegrita; cada selector:
    │       │       │           alto fijo 34 px, fondo blanco, texto #0B2F5B, borde #C9D7E8,
    │       │       │           radio 6 px y borde turquesa #16B8A6 al foco.
    │       │       ├── catalogSearch (QLineEdit, alto fijo 36 px, placeholder
    │       │       │   “Buscar por referencia o nombre”; blanco, #0B2F5B, borde #C9D7E8,
    │       │       │   radio 6 px)
    │       │       ├── catalogResultCount (QLabel; contador real de productos, texto #0B2F5B,
    │       │       │   fondo #DDF3F0, borde #9DDCD4, radio 10 px, padding 4 / 7 px, negrita)
    │       │       └── catalogProductTable (QTableWidget, expansiva; columnas REF. 90 px,
    │       │           NOMBRE flexible y SEL. 55 px; una única fila seleccionable; sin edición)
    │       │           ├── fondo blanco, borde #D6E0EA, radio 8 px, cuadrícula #E1E8F0,
    │       │           │   filas alternas #F8FAFD y scrollbar vertical de 8 px
    │       │           ├── cabecera #EEF3F8, texto #0B2F5B, negrita, padding 7 / 6 px
    │       │           └── selección #E5F7F4, texto #0B2F5B; check turquesa y blanco
    │       └── ireksContentPanel (QWidget, transparente, sin borde)
    │           └── ireksDetailSplitter (QSplitter vertical)
    │               ├── detailPanel (QWidget, alto fijo 232 px, fondo #F8FAFC,
    │               │   borde #CBD5E1, radio 9 px)
    │               │   ├── productDetailHeader (QFrame, alto fijo 38 px, fondo #0B2F5B,
    │               │   │   sin borde; radios superiores 8 px e inferiores rectos)
    │               │   │   ├── icono `product-detail.svg` blanco, 21 px
    │               │   │   └── “Detalle del producto” (QLabel, blanco, 16 px, negrita)
    │               │   └── productDetailBody (QFrame, fondo blanco, borde #CBD5E1 sin borde
    │               │       superior; márgenes 12 / 7 px, separación 3 px)
    │               │       ├── grupo PRODUCTO y campos Ref., Ref. corta y Descripción
    │               │       ├── divisor #D9E2EC de 1 px
    │               │       ├── grupo DISTRIBUIDOR y campos Distribuidor, Referencia y Descripción
    │               │       └── productDetailStatusRail (QFrame, #F1F5F9, borde #D6E0EA,
    │               │           radio 7 px): segmentos Status activo Sí/No, Status en lista Sí/No
    │               │           y Categoría Harina/Líquido; seleccionado #087E9C con texto blanco.
    │               └── ireksDetailTabs (QTabWidget; margen superior 4 px; panel transparente,
    │                   sin borde; pestañas expansivas)
    │                   ├── pestañas: Datos, Tarifa, Entradas, Salidas, Stock, Mensual, Pedidos,
    │                   │   Nutrición y Clientes
    │                   ├── pestaña inactiva: #F4F7FB, texto #5E6C84, borde #DCE5F1,
    │                   │   radios superiores 8 px, padding 8 / 6 px; activa: blanca, texto #087E9C,
    │                   │   seminegrita y línea inferior turquesa de 3 px.
    │                   ├── Datos / ireksDataTab (fondo #EEF3F8, márgenes 8 / 0 / 8 / 8 px,
    │                   │   separación 8 px)
    │                   │   ├── ireksClassificationCard (QFrame, alto fijo 146 px, blanco,
    │                   │   │   borde #EEF3F8, radio 8 px)
    │                   │   │   ├── cabecera estándar “CLASIFICACIÓN”, 38 px, #0B2F5B,
    │                   │   │   │   icono blanco `product-tag.svg` 21 px, título blanco 16 px;
    │                   │   │   │   ajustada al borde superior, sin borde y radios inferiores rectos.
    │                   │   │   └── grid de tres columnas: Fabricante, Familia y Subfamilia;
    │                   │   │       etiquetas #5E6C84 y selects blancos de 34 px, borde #C9D7E8,
    │                   │   │       radio 6 px; margen horizontal 12 px.
    │                   │   ├── fila de dos tarjetas, separación 10 px:
    │                   │   │   ├── ireksPresentationCard (alto fijo 204 px) con cabecera estándar
    │                   │   │   │   “PRESENTACIÓN”, icono `presentation-container.svg`; grid 3 × 2:
    │                   │   │   │   Presentación, Contenido, Unidad contenido, Peso unidad,
    │                   │   │   │   Unidad peso y Total presentación (solo lectura #F4F7FB).
    │                   │   │   └── ireksPalletCard (alto fijo 204 px) con cabecera estándar
    │                   │   │       “PALETIZACIÓN”, icono `pallet.svg`; grid 3 × 2: Pallet,
    │                   │   │       Presentaciones/capa, Capas, Presentaciones/pallet, Uds/pallet
    │                   │   │       y Total pallet (las tres últimas calculadas, solo lectura #F4F7FB).
    │                   │   └── ireksObservationsCard (alto fijo 46 px, blanco, borde #EEF3F8,
    │                   │       radio 8 px; margen 12 / 6 px): etiqueta “Obs.” y QLineEdit expansivo.
    │                   ├── Tarifa / tarifaTab: tarjeta con cabecera estándar “HISTÓRICO DE TARIFAS”,
    │                   │   icono `product-tag.svg`; filtro Año, acciones Añadir tarifa / Editar /
    │                   │   Eliminar y tabla de precios IREKS y distribuidor.
    │                   ├── Entradas / entradasTab: tarjeta “ENTRADAS DE ALMACÉN”, icono de entrada;
    │                   │   filtros Desde/Hasta y Todo, tabla Fecha, Pedido Nº, Albarán, Uds, Kg,
    │                   │   Lote y Caduca, más fila Total sincronizada.
    │                   ├── Salidas / salidasTab: tarjeta “SALIDAS DE ALMACÉN”, icono de salida;
    │                   │   filtros Desde/Hasta y Todo, tabla Fecha, Pedido Nº, Albarán, Uds, Kg,
    │                   │   Lote y Caduca; empty state cuando no hay registros.
    │                   ├── Stock / stockTab: tarjeta “STOCK Y MOVIMIENTOS”, icono de almacén;
    │                   │   filtros Desde/Hasta y Todo, tabla Fecha, Tipo, Pedido Nº, Albarán, Uds,
    │                   │   Kg, Lote y Caduca; Tipo se muestra como chip y Total neto resaltado.
    │                   ├── Mensual / mensualTab: tarjeta “RESUMEN MENSUAL”, icono
    │                   │   `calendar-chart.svg`; filtros Desde/Hasta y Limpiar; tabla Mes, Pedidos,
    │                   │   Cantidad, Kg, Media, Últ. fecha y Últ. pedido.
    │                   ├── Pedidos / pedidosTab: tarjeta “PEDIDOS RELACIONADOS”, icono de pedido;
    │                   │   filtros Desde/Hasta y Limpiar; tabla Fecha, Pedido Nº, Albarán, Cantidad,
    │                   │   Lote y Caducidad.
    │                   ├── Nutrición / nutricionTab: tarjeta “INFORMACIÓN NUTRICIONAL”, icono
    │                   │   `nutrition-lab.svg`, badge `ireksNutritionBadge` “Valores por 100 g”;
    │                   │   tabla Nutriente / Por 100 g.
    │                   └── Clientes / clientesTab: tarjeta “CONSUMO POR CLIENTE”, icono de usuarios;
    │                       filtro Año y tabla Cliente, Último período, Kg, Unidades y €.
        ├── Entradas
        │   └── MovimientosTab (`mode="in"`)
        │       ├── filtros: Año, Mes inicial/final, Fabricante, Familia, Subfamilia
        │       ├── búsqueda “Producto o lote” (nombre, referencia o lote)
        │       ├── acciones: Nueva manual, Editar manual y Anular manual
        │       ├── tabla: Fecha, Ref., Nombre flexible, Uds, Kg, Lote, Caduca, Albarán
        │       └── entriesTotalsTable (totales sincronizados de Uds y Kg)
        ├── Salidas
        │   └── MovimientosTab (`mode="out"`)
        │       ├── filtros: Año, Mes inicial/final, Fabricante, Familia, Subfamilia
        │       ├── búsqueda “Producto” (nombre o referencia)
        │       ├── acciones: Nueva manual, Editar manual y Anular manual
        │       └── tabla: Fecha, Ref., Nombre flexible, Uds, Kg, Lote, Concepto
        ├── Stock
        │   └── StockTab
        │       ├── filtros: Fabricante, Familia, Subfamilia y Riesgo
        │       ├── Riesgo: Todos, Caducado, Caduca <= 30 días y Bajo stock
        │       ├── Umbral bajo stock (QDoubleSpinBox, 2 decimales)
        │       ├── búsqueda “Nombre o ref...”
        │       └── tabla: Ref., Nombre, Lote, Caduca, Días, Stock Uds, Stock Kg,
        │           Últ. mov. y Estado
        ├── Pedidos mensual
        │   └── AnnualMonthlyOrdersTab
        │       ├── filtros: Año, Producto (“Ref. o nombre...”) y Refrescar
        │       └── tabla anual: Ref., Producto, Ene–Dic, Total, Kg, Ped. y Último
        ├── Inventarios
        │   └── InventariosTab
        │       └── inner_tabs (QTabWidget)
        │           ├── Conteo
        │           │   ├── Exportar plantilla, Importar conteo, Refrescar,
        │           │   │   Preparar ajustes y Aprobar y aplicar
        │           │   ├── búsqueda, campos Contador / Aprobador e indicador pendientes
        │           │   └── tabla: Ref., Nombre, Lote, Caduca, Teórico Uds,
        │           │       Conteo Uds editable, Diferencia y Kg ajuste
        │           └── Historial
        │               ├── Exportar historial
        │               ├── tabla: Código, Fecha, Contador, Aprobador, Líneas,
        │               │   Ajustes y Estado
        │               └── tabla de detalle del inventario seleccionado
        ├── Caducidad
        │   └── CaducidadTab
        │       ├── filtros: Caduca desde/hasta, Próxima caducidad (7–120 días),
        │       │   modo y acción Todo
        │       └── tabla: Pedido Nº, Albarán, Fecha, Ref., Nombre, Uds, Kg, Lote,
        │           Caduca (caducados en rojo)
        ├── separador visual “|” (QWidget, pestaña deshabilitada)
        ├── Fabricantes
        │   └── EntityPage: título, búsqueda, Nuevo, Editar, Eliminar,
        │       Importar Excel/CSV cuando aplica, Refrescar y tabla del catálogo
        ├── Otras ref.
        │   └── OtrasReferenciasTab
        │       ├── título, búsqueda libre y filtro Distribuidor
        │       ├── Nuevo, Editar, Eliminar, Importar Excel/CSV y Refrescar
        │       └── tabla ordenable: Ref. fabricante, Descripción fabricante,
        │           Ref. distribuidor y Descripción distribuidor
        ├── Familias
        │   └── EntityPage: título, búsqueda, acciones de mantenimiento y tabla
        ├── Subfamilias
        │   └── EntityPage: título, búsqueda, filtros Familia/Subfamilia cuando
        │       aplica, acciones de mantenimiento y tabla
        └── Envases
            └── EntityPage: título, búsqueda, acciones de mantenimiento y tabla
```

### Filtro global de almacén

`almacen_combo` contiene `Todos` y las entidades que pueden operar como almacén: distribuidores y clientes directos. Al cambiarlo se propaga su identificador a Artículos, Entradas, Salidas, Stock, Pedidos mensual, Inventarios y Caducidad. La carga inicial selecciona `Todos` y aplica el contexto general sin disparar recargas duplicadas. No hay botón de actualización en la barra superior.

### Resumen de Artículos

La pestaña reutiliza el catálogo de `IngredientsIreksPage` en modo compacto. Oculta su título y ribbon propios y usa `IngredientWarehouseViewModel`.

```text
Artículos
└── catálogo de artículos IREKS compacto
    ├── filtros por fabricante, estado, familia y subfamilia
    ├── búsqueda por referencia o nombre
    ├── tabla de catálogo (Ref. · Nombre · selección)
    └── detalle y pestañas de producto IREKS
```

La selección de un artículo se reutiliza desde Entradas y Salidas: doble clic sobre una línea de movimiento abre el artículo correspondiente en esta pestaña.

### Resumen de Entradas y Salidas

Ambas instancias usan `MovimientosTab`; la diferencia funcional la determina `mode`.

```text
MovimientosTab
├── barra de filtros
│   ├── fechas Desde / Hasta
│   ├── búsqueda de producto, referencia, pedido o albarán
│   ├── filtro de lote y caducidad cuando aplica
│   └── acciones de movimiento y actualización según el modo
├── tabla de movimientos
│   ├── fecha
│   ├── tipo
│   ├── pedido / albarán
│   ├── referencia y descripción de artículo
│   ├── unidades y kg (alineados a la derecha)
│   ├── lote
│   └── caducidad
└── tabla de totales (cuando aplica)
    └── acumulados sincronizados de unidades y kg
```

- `Entradas` muestra movimientos de entrada y dispone de `entriesTotalsTable`.
- `Salidas` muestra movimientos de salida y sus acumulados correspondientes.
- Las tablas son de solo lectura, permiten selección de una fila y sus cabeceras son clicables para ordenar.

### Resumen de Stock

```text
StockTab
├── filtros de clasificación
│   ├── Fabricante
│   ├── Familia
│   ├── Subfamilia
│   ├── Riesgo (Todos · Caducado · Caduca ≤ 30 días · Bajo stock)
│   └── Umbral bajo stock (uds)
├── búsqueda de producto por nombre o referencia
└── tabla de stock
    ├── Ref.
    ├── Nombre
    ├── Lote
    ├── Caduca
    ├── Días
    ├── Stock Uds
    ├── Stock Kg
    ├── Últ. mov.
    └── Estado
```

El umbral de bajo stock se conserva mediante `WarehouseSettingsService`. Las columnas de cantidades se alinean a la derecha y el estado comunica riesgo de caducidad o disponibilidad.

### Resumen de Pedidos mensual

```text
AnnualMonthlyOrdersTab
├── filtros: Año · Producto (referencia o nombre) · Refrescar
└── tabla anual de producto
    ├── Ref. · Producto
    ├── Ene … Dic
    ├── Total
    ├── Kg
    ├── Ped.
    └── Último
```

La tabla usa 18 columnas. Las cantidades mensuales, total, kg y pedidos se ordenan por valor numérico real; `Kg` muestra el sufijo `kg`. El doble clic abre el detalle de pedidos del artículo seleccionado.

### Resumen de Inventarios

`InventariosTab` agrupa Conteo e Historial en `inner_tabs`.

```text
Inventarios
├── Conteo
│   ├── acciones: Exportar plantilla · Importar conteo · Refrescar
│   ├── búsqueda por producto, referencia o lote
│   ├── campos de contador y aprobador
│   ├── Preparar ajustes · Aprobar y aplicar
│   └── tabla de conteo físico con edición de “Conteo Uds”
└── Historial
    ├── Exportar historial
    ├── tabla de inventarios aplicados
    └── tabla de detalle del inventario seleccionado
```

La aplicación de ajustes se realiza mediante los flujos específicos de inventario; el listado y la preparación no modifican movimientos hasta la acción de aprobación.

### Resumen de Caducidad

```text
CaducidadTab
├── filtros
│   ├── Caduca desde / hasta
│   ├── Próxima caducidad (7 a 120 días)
│   ├── modo: Caducados + próximos · Solo caducados · Solo próximos
│   └── Todo
└── tabla
    ├── Pedido Nº · Albarán · Fecha
    ├── Ref. · Nombre
    ├── Uds · Kg
    ├── Lote
    └── Caduca
```

Las caducidades vencidas se muestran en rojo y las próximas se distinguen visualmente. La tabla está ordenada desde su cabecera y opera sobre el contexto del almacén seleccionado.

### Resumen de mantenimiento

`Fabricantes`, `Familias`, `Subfamilias` y `Envases` reutilizan `EntityPage` con sus columnas de código y nombre. Incorporan alta, edición, eliminación e importación mediante sus servicios de catálogo.

`OtrasReferenciasTab` incluye:

```text
Otras referencias
├── búsqueda libre
├── filtro de distribuidor
├── acciones: Nuevo · Editar · Eliminar · Importar Excel/CSV · Refrescar
└── tabla: Ref. fabricante · Descripción fabricante · Ref. distribuidor · Descripción distribuidor
```

### Aspecto visual actual

- La ventana usa los estilos globales de `assets/styles.qss`: fondo claro, campos blancos, bordes grises suaves y botones por rol.
- La zona superior es una barra compacta de ámbito de datos, sin título grande ni botón de actualización; queda separada 6 px de las pestañas para reducir el espacio vertical.
- Las tablas son blancas, con cuadrícula tenue, filas alternas y cabeceras gris azulado. Las tablas de movimientos, stock, pedidos, caducidad y mantenimiento evitan el foco de celda visible.
- La selección es por fila única; las columnas de unidades, kg y otras métricas numéricas se alinean a la derecha.
- `main_tabs` separa el flujo operativo (Artículos a Caducidad) del mantenimiento de catálogos mediante la pestaña separadora `|` deshabilitada.

### Componentes completos por pestaña

#### Artículos

```text
articles_tab / IngredientsIreksPage (modo compacto)
├── catálogo lateral de productos
│   ├── cabecera y contador real de productos
│   ├── filtros Fabricante, Estado, Familia y Subfamilia
│   ├── búsqueda “Buscar por referencia o nombre”
│   └── tabla seleccionable: referencia, nombre y selección
└── detalle del artículo seleccionado
    ├── cabecera de producto
    └── pestañas Datos, Tarifa, Entradas, Salidas, Stock, Mensual,
        Pedidos, Nutrición y Clientes
```

La cabecera propia y el ribbon de acciones de `IngredientsIreksPage` permanecen ocultos en este uso compacto. El filtro global de almacén se entrega al view-model de esta pestaña.

#### Entradas

```text
entradas_tab / MovimientosTab(mode="in")
├── filtros de contexto
│   ├── Año
│   ├── Mes inicial y Mes final
│   ├── Fabricante, Familia y Subfamilia
│   └── búsqueda “Producto o lote” (nombre, referencia o lote)
├── acciones
│   ├── Nueva manual
│   ├── Editar manual
│   └── Anular manual
├── tabla de entradas
│   ├── Fecha
│   ├── Ref.
│   ├── Nombre (columna flexible)
│   ├── Uds y Kg (a la derecha)
│   ├── Lote
│   ├── Caduca
│   └── Albarán
└── entriesTotalsTable
    └── fila de totales sincronizada con las columnas de la tabla
```

La tabla es de una única selección, no permite edición directa y abre el artículo asociado mediante doble clic.

#### Salidas

```text
salidas_tab / MovimientosTab(mode="out")
├── filtros de contexto
│   ├── Año
│   ├── Mes inicial y Mes final
│   ├── Fabricante, Familia y Subfamilia
│   └── búsqueda “Producto” (nombre o referencia)
├── acciones: Nueva manual, Editar manual y Anular manual
└── tabla de salidas
    ├── Fecha
    ├── Ref.
    ├── Nombre (columna flexible)
    ├── Uds y Kg (a la derecha)
    ├── Lote
    └── Concepto
```

Mantiene selección por fila, orden desde cabecera y apertura por doble clic del artículo correspondiente en Artículos.

#### Stock

```text
stock_tab / StockTab
├── filtros de clasificación: Fabricante, Familia y Subfamilia
├── filtro Riesgo
│   └── Todos | Caducado | Caduca <= 30 días | Bajo stock
├── campo “Umbral bajo stock (uds)” (QDoubleSpinBox, 2 decimales)
├── búsqueda Producto: “Nombre o ref...”
└── tabla de stock
    ├── Ref. y Nombre
    ├── Lote, Caduca y Días
    ├── Stock Uds y Stock Kg (a la derecha)
    ├── Últ. mov.
    └── Estado
```

El umbral se persiste con `WarehouseSettingsService`; la pestaña solamente visualiza el riesgo y las existencias calculadas por el servicio existente.

#### Pedidos mensual

```text
monthly_orders_tab / AnnualMonthlyOrdersTab
├── filtros: Año, Producto (“Ref. o nombre...”) y Refrescar
└── tabla anual de 18 columnas
    ├── Ref. y Producto
    ├── Ene, Feb, Mar, Abr, May, Jun, Jul, Ago, Sep, Oct, Nov y Dic
    ├── Total
    ├── Kg (sufijo kg, a la derecha)
    ├── Ped.
    └── Último
```

Las cabeceras ordenan por el valor real de los datos. El doble clic conserva la apertura del detalle de pedidos del artículo seleccionado.

#### Inventarios

```text
inventarios_tab / InventariosTab
└── inner_tabs (QTabWidget)
    ├── Conteo
    │   ├── texto introductorio
    │   ├── Exportar plantilla, Importar conteo, Refrescar,
    │   │   Preparar ajustes y Aprobar y aplicar
    │   ├── búsqueda de producto, referencia o lote
    │   ├── campos Contador y Aprobador
    │   ├── indicador de pendientes
    │   └── tabla: Ref., Nombre, Lote, Caduca, Teórico Uds,
    │       Conteo Uds (editable), Diferencia y Kg ajuste
    └── Historial
        ├── título “Historial de inventarios”
        ├── acción Exportar historial
        ├── tabla: Código, Fecha, Contador, Aprobador, Líneas,
        │   Ajustes y Estado
        └── tabla de detalle del inventario seleccionado
```

Las acciones de ajuste quedan asociadas al flujo explícito de preparación y aprobación; consultar o filtrar no crea movimientos.

#### Caducidad

```text
caducidad_tab / CaducidadTab
├── filtros
│   ├── Caduca desde y Caduca hasta (QDateEdit)
│   ├── Próxima caducidad: 7, 15, 30, 45, 60, 90 o 120 días
│   ├── modo: Caducados + próximos | Solo caducados | Solo próximos
│   └── acción Todo
└── tabla de lotes
    ├── Pedido Nº, Albarán y Fecha
    ├── Ref. y Nombre
    ├── Uds y Kg (a la derecha)
    ├── Lote
    └── Caduca
```

Los lotes caducados usan texto rojo; los próximos mantienen la señalización visual existente.

#### Fabricantes, Familias, Subfamilias y Envases

```text
EntityPage (una instancia por catálogo)
├── título de la entidad
├── barra de mantenimiento
│   ├── búsqueda “Buscar...”
│   ├── filtros Familia y Subfamilia, solo donde el catálogo los admite
│   ├── Nuevo, Editar y Eliminar
│   ├── Importar Excel/CSV, cuando el servicio lo admite
│   └── Refrescar
└── tabla de entidad
    ├── columnas de código, nombre y atributos definidos por cada schema
    └── última columna expansible
```

Los diálogos de alta y edición usan `EntityDialog` y los servicios del catálogo ya existentes; las tablas no permiten editar celdas directamente.

#### Otras ref.

```text
OtrasReferenciasTab
├── título “Otras referencias”
├── barra de mantenimiento
│   ├── búsqueda “Buscar...”
│   ├── filtro Distribuidor
│   ├── Nuevo, Editar y Eliminar
│   ├── Importar Excel/CSV
│   └── Refrescar
└── tabla seleccionable y ordenable
    ├── Ref. fabricante
    ├── Descripción fabricante
    ├── Ref. distribuidor
    └── Descripción distribuidor
```

El filtro de distribuidor se reconstruye conservando la selección actual cuando sigue disponible.

## Comportamiento actual

- El filtro de Cliente/Distribuidor sincroniza todas las pestañas operativas.
- El doble clic en Entradas o Salidas abre el artículo asociado en Artículos.
- Stock, Caducidad y Pedidos mensual se recalculan conforme a sus filtros sin alterar datos.
- Inventarios permite preparar y aplicar ajustes por un flujo explícito de aprobación.
- Las pestañas de mantenimiento gestionan los catálogos de apoyo al almacén.

## Relación con backend / datos

- `WarehousePage` no consume React ni FastAPI directamente.
- Los servicios de almacén trabajan contra la base de datos local y los modelos existentes.
- Las exportaciones de plantilla, historial y referencias usan los flujos y formatos ya definidos por cada servicio.
- La selección visual y los filtros no modifican existencias; las mutaciones se limitan a las acciones explícitas de entradas, salidas e inventarios.
