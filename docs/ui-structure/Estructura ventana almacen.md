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
WarehousePage (QWidget)
└── layout principal (QVBoxLayout)
    ├── título “Almacen” (QLabel, role="pageTitle")
    ├── filtro global (QHBoxLayout)
    │   ├── etiqueta “Cliente/Distribuidor”
    │   ├── almacen_combo (QComboBox; “Todos” + clientes directos/distribuidores)
    │   ├── Refrescar (QPushButton, rol secondary)
    │   └── espacio flexible
    └── main_tabs (QTabWidget)
        ├── Artículos
        │   └── IngredientsIreksPage (sin cabecera ni ribbon propios, `compact_mode=True`)
        ├── Entradas
        │   └── MovimientosTab (`mode="in"`)
        ├── Salidas
        │   └── MovimientosTab (`mode="out"`)
        ├── Stock
        │   └── StockTab
        ├── Pedidos mensual
        │   └── AnnualMonthlyOrdersTab
        ├── Inventarios
        │   └── InventariosTab
        ├── Caducidad
        │   └── CaducidadTab
        ├── separador visual “|” (QWidget, pestaña deshabilitada)
        ├── Fabricantes
        │   └── EntityPage (mantenimiento de fabricante)
        ├── Otras ref.
        │   └── OtrasReferenciasTab
        ├── Familias
        │   └── EntityPage (mantenimiento de familia)
        ├── Subfamilias
        │   └── EntityPage (mantenimiento de subfamilia)
        └── Envases
            └── EntityPage (mantenimiento de envase)
```

## Filtro global de almacén

`almacen_combo` contiene `Todos` y las entidades que pueden operar como almacén: distribuidores y clientes directos. Al cambiarlo se propaga su identificador a Artículos, Entradas, Salidas, Stock, Pedidos mensual, Inventarios y Caducidad. El botón `Refrescar` recarga el selector y restablece el contexto global a `Todos`.

## Pestaña Artículos

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

## Pestañas Entradas y Salidas

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

## Pestaña Stock

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

## Pestaña Pedidos mensual

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

## Pestaña Inventarios

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

## Pestaña Caducidad

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

## Pestañas de mantenimiento

`Fabricantes`, `Familias`, `Subfamilias` y `Envases` reutilizan `EntityPage` con sus columnas de código y nombre. Incorporan alta, edición, eliminación e importación mediante sus servicios de catálogo.

`OtrasReferenciasTab` incluye:

```text
Otras referencias
├── búsqueda libre
├── filtro de distribuidor
├── acciones: Nuevo · Editar · Eliminar · Importar Excel/CSV · Refrescar
└── tabla: Ref. fabricante · Descripción fabricante · Ref. distribuidor · Descripción distribuidor
```

## Aspecto visual actual

- La ventana usa los estilos globales de `assets/styles.qss`: fondo claro, campos blancos, bordes grises suaves y botones por rol.
- Las tablas son blancas, con cuadrícula tenue, filas alternas y cabeceras gris azulado. Las tablas de movimientos, stock, pedidos, caducidad y mantenimiento evitan el foco de celda visible.
- La selección es por fila única; las columnas de unidades, kg y otras métricas numéricas se alinean a la derecha.
- `main_tabs` separa el flujo operativo (Artículos a Caducidad) del mantenimiento de catálogos mediante la pestaña separadora `|` deshabilitada.

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
