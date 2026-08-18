# VENTANA PRODUCTOS IREKS — PYSIDE6 / BACKEND

Implementación principal:

- UI: `app/ui/widgets/ingredients_page.py` (`IngredientsIreksPage`)
- Estilos compartidos: `assets/styles.qss`
- Servicios principales:
  - `app/services/ingredient_ireks_service.py`
  - `app/services/ingredient_ireks_autosave_flow_service.py`
  - `app/services/sales_annual_comparison_service.py`
  - `app/services/monthly_orders_service.py`
  - `app/services/product_report_flow_service.py`
- Modelos relevantes:
  - `IngredienteIreks`
  - `Fabricante`, `Familia`, `Subfamilia`, `Envase`
  - `ReferenciaDistribuidor`
  - `TarifaPrecioIreks`
  - `MateriaPrimaValorNutricional`
  - `AlmacenMovimiento`, `PedidoItem`

La sección se registra como `Productos IREKS` en `app/ui/main_window.py` y usa el widget `IngredientsIreksPage`.

## Estructura UI real

```text
IngredientsIreksPage (QWidget, objectName `IngredientsIreksPageRoot`, fondo #EEF3F8, sin borde, WA_StyledBackground=True)
└── layout principal (QVBoxLayout, márgenes 14 / 11 / 14 / 14 px, separación 10 px)
    ├── topRibbon (QFrame, objectName `topRibbon`, pageType="contacts", fondo #FFFFFF, borde #E2E8F1, radio 8 px)
    │   ├── Nuevo (QPushButton, icono `plus.svg`, rol `success`, 110 x 30 px)
    │   ├── Eliminar (QPushButton, icono `trash.svg`, rol `danger`, 110 x 30 px)
    │   ├── ID (QPushButton, icono `package.svg`, rol `secondary`, 110 x 30 px)
    │   ├── Listados (QPushButton, icono `list.svg`, rol `primary`, 110 x 30 px)
    │   └── espacio flexible
    └── splitter horizontal (QSplitter, objectName `ireksMainSplitter`, fondo transparente, sin borde, childrenCollapsible=False, handleWidth=5 px)
        ├── panel izquierdo (QWidget, objectName `sidePanel`, ancho fijo 420 px)
        │   └── layout vertical
        │       ├── fila de filtros de fabricante y actividad
        │       │   ├── fabricante_filter (QComboBox, ancho 280 px)
        │       │   └── activity_filter (QComboBox, ancho 120 px: Todos, Activos, Inactivos)
        │       ├── fila de taxonomía
        │       │   ├── familia_filter (QComboBox)
        │       │   └── subfamilia_filter (QComboBox)
        │       ├── search_input (QLineEdit, placeholder “Buscar productos...”, ancho 405 px)
        │       └── table (QTableWidget, selección de fila única, solo lectura, cabeceras ordenables)
        │           ├── Ref (90 px)
        │           ├── Nombre (stretch)
        │           └── Sel. (55 px; selector de inclusión para listados)
        └── panel derecho (QWidget, objectName `ireksContentPanel`, fondo transparente, sin borde)
            └── layout vertical sin márgenes
                └── splitter vertical derecho (QSplitter, objectName `ireksDetailSplitter`, fondo transparente, sin borde)
                    ├── detailPanel (QWidget, alto fijo 232 px, fondo #F8FAFC, borde #CBD5E1, radio 9 px)
                    │   ├── productDetailHeader (QFrame, alto 38 px, fondo azul marino #06213D, esquinas inferiores rectas)
                    │   │   ├── icono `assets/icons/product-detail.svg` (blanco, 21 px)
                    │   │   └── título “Detalle del producto” (blanco, 16 px, negrita)
                    │   └── productDetailBody (QFrame, fondo #FFFFFF, borde gris #CBD5E1)
                    │       ├── grupo PRODUCTO (etiqueta azul grisácea, 10 px)
                    │       │   ├── Ref. / detail_referencia (QLineEdit; factor 2)
                    │       │   ├── Ref. corta / detail_ref_corta (QLineEdit; factor 2)
                    │       │   └── Descripción / detail_descripcion (QLineEdit; factor 5)
                    │       ├── divisor horizontal #D9E2EC
                    │       ├── grupo DISTRIBUIDOR (etiqueta azul grisácea, 10 px)
                    │       │   ├── Distribuidor / detail_distribuidor_id (QComboBox; factor 3)
                    │       │   ├── Referencia / detail_referencia_distribuidor (QLineEdit; factor 2)
                    │       │   └── Descripción / detail_descripcion_distribuidor (QLineEdit; factor 5)
                    │       └── productDetailStatusRail (QFrame #F1F5F9, borde #D6E0EA, radio 7 px)
                    │           ├── Status activo: botones segmentados Sí / No
                    │           ├── Status en lista: botones segmentados Sí / No
                    │           └── Categoría: botones segmentados Harina / Líquido
                    └── tabs_host
                        └── detail_tabs (QTabWidget)
                            ├── Datos
                            │   └── ireksDataTab (QWidget, fondo #EEF3F8)
                            │       ├── tarjeta CLASIFICACIÓN (QFrame `ireksCard=True`, fondo #FFFFFF, borde #D6E0EA, radio 8 px)
                            │       │   ├── cabecera `ireksTabHeader` (alto fijo 48 px, fondo #0B2F5B, icono blanco `product-tag.svg` 20 px, título blanco 13 px)
                            │       │   └── Fabricante / detail_fabricante_id · Familia / detail_familia_id · Subfamilia / detail_subfamilia_id
                            │       ├── tarjeta PRESENTACIÓN (QFrame `ireksCard=True`, fondo #FFFFFF, borde #D6E0EA, radio 8 px)
                            │       │   ├── cabecera `ireksTabHeader` (icono blanco `presentation-container.svg`)
                            │       │   └── cuadrícula 3 columnas: Presentación / detail_envase_id · Contenido / detail_envase_cantidad · Unidad contenido / detail_contenido_unidad
                            │       │       Peso unidad / detail_envase_peso · Unidad peso / detail_envase_unidad · Total presentación / detail_envase_total (solo lectura, #F4F7FB)
                            │       └── tarjeta PALETIZACIÓN (QFrame `ireksCard=True`, fondo #FFFFFF, borde #D6E0EA, radio 8 px)
                            │           ├── cabecera `ireksTabHeader` (icono blanco `pallet.svg`)
                            │           └── cuadrícula 3 columnas: Pallet / transporte_pallet_tipo · Presentaciones/capa / transporte_cajas_por_capa · Capas / transporte_capas_por_pallet
                            │               Presentaciones/pallet / transporte_cajas_por_pallet · Uds/pallet / transporte_unidades_por_pallet · Total pallet / transporte_kg_por_pallet (los tres derivados, solo lectura, #F4F7FB)
                            │               Obs. / transporte_observaciones (ancho completo)
                            ├── Tarifa
                            │   ├── filtro de año
                            │   ├── Añadir tarifa / Editar / Eliminar
                            │   ├── tarifa_header_table (cabecera agrupada IREKS / DISTRIBUIDOR)
                            │   └── tarifa_table (10 columnas: año, precio IREKS, descuento y coste/margen de distribuidor)
                            ├── Entradas
                            │   ├── filtro Desde / Hasta / Todo
                            │   ├── entradas_table (Fecha, Pedido Nº, Albarán, Uds, Kg, Lote, Caduca)
                            │   └── entradas_totals_table (fila fija sincronizada)
                            ├── Salidas
                            │   ├── filtro Desde / Hasta / Todo
                            │   ├── salidas_table (Fecha, Pedido Nº, Albarán, Uds, Kg, Lote, Caduca)
                            │   └── salidas_totals_table (fila fija sincronizada)
                            ├── Stock
                            │   ├── filtro Desde / Hasta / Todo
                            │   ├── stock_table (Fecha, Tipo, Pedido Nº, Albarán, Uds, Kg, Lote, Caduca)
                            │   └── stock_totals_table (fila fija sincronizada)
                            ├── Mensual
                            │   ├── filtro Desde / Hasta / Limpiar
                            │   └── monthly_orders_table (Mes, Pedidos, Cantidad, Kg, Media, Últ. fecha, Últ. pedido)
                            ├── Pedidos
                            │   ├── filtro Desde / Hasta / Limpiar
                            │   └── pedidos_table (Fecha, Pedido Nº, Albarán, Cantidad, Lote, Caducidad)
                            ├── Nutición
                            │   └── nutricion_table (Nutriente / Por 100 g; 9 filas editables)
                            └── Clientes
                                ├── selector de año
                                ├── ireksCustomerConsumptionEmpty (estado vacío)
                                └── ireksCustomerConsumptionTable (Cliente, Último período, Kg, Unidades, €; ordenable)
```

## Estructura de la pestaña Datos

`ireksDataTab` organiza los campos en tres tarjetas. CLASIFICACIÓN ocupa la primera fila; PRESENTACIÓN y PALETIZACIÓN comparten una segunda fila horizontal y reciben el mismo factor de estiramiento. Las alturas fijas de cada tarjeta evitan que las cuadrículas compriman etiquetas o controles.

```text
ireksDataTab (QWidget, fondo #EEF3F8)
├── tarjeta CLASIFICACIÓN (QFrame, propiedad ireksCard=True)
│   ├── cabecera `ireksTabHeader` (azul marino #0B2F5B, icono blanco `product-tag.svg`)
│   └── taxonomía (fila responsiva)
│       ├── Fabricante / detail_fabricante_id (QComboBox)
│       ├── Familia / detail_familia_id (QComboBox)
│       └── Subfamilia / detail_subfamilia_id (QComboBox)
└── lower_cards (QHBoxLayout, separación 10 px, factor 1 para cada tarjeta)
    ├── tarjeta PRESENTACIÓN (QFrame `ireksPresentationCard`, alto fijo 204 px)
    │   ├── cabecera `ireksTabHeader` (icono blanco `presentation-container.svg`)
    │   └── cuadrícula de 3 columnas y 2 grupos de campos
    │       ├── Presentación / detail_envase_id (QComboBox)
    │       ├── Contenido / detail_envase_cantidad (QLineEdit)
    │       ├── Unidad contenido / detail_contenido_unidad (QComboBox editable)
    │       ├── Peso unidad / detail_envase_peso (QLineEdit)
    │       ├── Unidad peso / detail_envase_unidad (QComboBox)
    │       └── Total presentación / detail_envase_total (QLineEdit, solo lectura)
    └── tarjeta PALETIZACIÓN (QFrame `ireksPalletCard`, alto fijo 264 px)
        ├── cabecera `ireksTabHeader` (icono blanco `pallet.svg`)
        ├── cuadrícula de 3 columnas y 2 grupos de campos
        │   ├── Pallet / transporte_pallet_tipo (QComboBox)
        │   ├── Presentaciones/capa / transporte_cajas_por_capa (QLineEdit)
        │   ├── Capas / transporte_capas_por_pallet (QLineEdit)
        │   ├── Presentaciones/pallet / transporte_cajas_por_pallet (QLineEdit, solo lectura)
        │   ├── Uds/pallet / transporte_unidades_por_pallet (QLineEdit, solo lectura)
        │   └── Total pallet / transporte_kg_por_pallet (QLineEdit, solo lectura)
        └── Obs. / transporte_observaciones (QLineEdit, ancho completo)
```

- Las etiquetas quedan encima de los controles en Presentación y Paletización; así no se comprimen ni se solapan con sus campos.
- Los controles derivados de cálculo son de solo lectura, con fondo `#F4F7FB`.
- Los valores de presentación y paletización mantienen los mismos eventos de autosave y los mismos cálculos existentes: total de presentación, presentaciones por pallet, unidades por pallet y kg por pallet.

### Especificación visual por tarjeta

| Tarjeta | Cabecera | Componentes y disposición | Campos calculados / aspecto |
| --- | --- | --- | --- |
| **CLASIFICACIÓN** | `ireksTabHeader` de alto fijo 48 px, fondo azul marino `#0B2F5B`, sin borde, radio solo en esquinas superiores de 8 px. Icono blanco `product-tag.svg` de 20 px y título en mayúsculas blanco, 13 px y negrita. | Cuadrícula de tres columnas con etiqueta encima del control: **Fabricante** / `detail_fabricante_id`, **Familia** / `detail_familia_id` y **Subfamilia** / `detail_subfamilia_id`. `ireksClassificationCard` tiene alto fijo 142 px. | No incorpora cálculo. Etiquetas `#5E6C84`, peso 500. Combos blancos, texto `#0B2F5B`, borde `#C9D7E8`, radio 6 px, alto mínimo 28 px y foco turquesa `#087E9C`. |
| **PRESENTACIÓN** | `ireksTabHeader` de alto fijo 48 px, fondo `#0B2F5B`, radio superior de 8 px, icono blanco `presentation-container.svg` de 20 px y título blanco de 13 px. | Cuadrícula de tres columnas con etiqueta sobre control: fila 1: **Presentación** / `detail_envase_id`, **Contenido** / `detail_envase_cantidad`, **Unidad contenido** / `detail_contenido_unidad`; fila 2: **Peso unidad** / `detail_envase_peso`, **Unidad peso** / `detail_envase_unidad`, **Total presentación** / `detail_envase_total`. `ireksPresentationCard` tiene alto fijo 204 px. | `detail_envase_total` es solo lectura, fondo `#F4F7FB` y texto `#0B2F5B`; los otros controles son blancos con borde `#C9D7E8`, radio 6 px, alto mínimo 28 px y foco `#087E9C`. |
| **PALETIZACIÓN** | `ireksTabHeader` de alto fijo 48 px, fondo `#0B2F5B`, radio superior de 8 px, icono blanco `pallet.svg` de 20 px y título blanco de 13 px. | Cuadrícula de tres columnas con etiqueta sobre control: fila 1: **Pallet** / `transporte_pallet_tipo`, **Presentaciones/capa** / `transporte_cajas_por_capa`, **Capas** / `transporte_capas_por_pallet`; fila 2: **Presentaciones/pallet** / `transporte_cajas_por_pallet`, **Uds/pallet** / `transporte_unidades_por_pallet`, **Total pallet** / `transporte_kg_por_pallet`. Debajo: **Obs.** y `transporte_observaciones` a ancho completo. `ireksPalletCard` tiene alto fijo 264 px. | `transporte_cajas_por_pallet`, `transporte_unidades_por_pallet` y `transporte_kg_por_pallet` son solo lectura, fondo `#F4F7FB`; los campos fuente y observaciones son editables. Todos usan texto marino `#0B2F5B`, etiquetas `#5E6C84`, borde `#C9D7E8`, radio 6 px y foco turquesa `#087E9C`. |

#### Contenedor común de las tres tarjetas

- `QFrame` con propiedad `ireksCard=True`: fondo `#FFFFFF`, borde de 1 px `#D6E0EA` y radio de 8 px.
- La cabecera ocupa el ancho total y queda pegada al borde superior de cada tarjeta. Los campos conservan márgenes horizontales de 12 px y una separación vertical de 9 px.
- `ireksDataTab`: fondo azul grisáceo claro `#EEF3F8`, márgenes 8 / 10 / 8 / 8 px y separación de 8 px.
- Orden: **CLASIFICACIÓN** arriba; debajo, **PRESENTACIÓN** y **PALETIZACIÓN** en paralelo, separadas 10 px y con el mismo factor de crecimiento horizontal. Las alturas fijas y filas mínimas de 20 / 34 px evitan que etiquetas y controles se solapen.
- Las cabeceras no llevan sombra ni borde/acento turquesa; los iconos se renderizan en blanco sobre el azul marino.

## Comportamiento actual

- Al abrir la pantalla se cargan el catálogo de productos y sus filtros. Si hay productos, se selecciona el primero y se completa su ficha.
- La búsqueda espera 200 ms antes de recargar, y filtra junto con fabricante, familia, subfamilia, estado y distribuidor externo cuando se ha recibido ese filtro.
- La lista izquierda conserva la ordenación elegida de Ref. o Nombre. La columna `Sel.` permite marcar productos para los listados.
- Seleccionar un producto actualiza la ficha, la presentación, la taxonomía, la referencia de distribuidor y las pestañas relacionadas.
- Los cambios de ficha se guardan mediante autosave diferido de 350 ms. Durante la carga de datos, el autosave queda bloqueado.
- El total de presentación se calcula a partir de contenido y peso. Los campos de transporte derivados (presentaciones/pallet, uds/pallet y total pallet) son de solo lectura y se recalculan desde los datos de pallet.
- Cambiar fabricante restringe las familias disponibles; cambiar familia restringe las subfamilias.
- Las pestañas Entradas, Salidas y Stock se actualizan con el producto activo y respetan sus filtros de fechas. Sus filas de total no se desplazan y se alinean con las tablas.
- Mensual resume los pedidos por período; Pedidos muestra los artículos de pedido del producto filtrados por fechas.
- Tarifa permite crear, editar y eliminar tarifas del producto. La cabecera agrupa visualmente los datos IREKS y los del distribuidor.
- Nutición guarda valores por 100 g del producto seleccionado. La pestaña usa valores de energía, grasas, saturadas, hidratos, azúcares, fibra, proteínas y sal.
- La pestaña Clientes carga los consumidores del producto seleccionado. Filtra por año y, para un año concreto, muestra solo clientes con kg o euros actuales positivos. Sus magnitudes se ordenan numéricamente.
- `Nuevo` abre una ficha de creación; `Eliminar` requiere producto seleccionado y confirmación; `ID` muestra el identificador técnico del producto.
- `Listados` abre una ventana no modal para generar un listado desde una petición en lenguaje natural, previsualizarlo y exportarlo a Excel, PDF o impresora.

## Geometría actual

- El panel de lista tiene ancho fijo de 420 px; el panel de detalle comparte el resto del ancho con factor de estiramiento equivalente.
- El separador principal deja un espacio transparente de 5 px entre los paneles y no es arrastrable (`handleWidth(5)`).
- El ribbon se sitúa antes del splitter horizontal y tiene márgenes internos de 8 x 6 px y separación de 6 px entre acciones.
- `detailPanel` tiene alto fijo de 232 px. La cabecera mide 38 px; el cuerpo usa márgenes 12 × 7 px, filas de campos responsivas con separación de 8 px y rail de estado con márgenes 9 × 4 px.
- El splitter vertical derecho da prioridad a las pestañas (factor 9) sobre la ficha superior (factor 1).
- Las pestañas de movimientos usan tablas de siete u ocho columnas; fecha, pedido, albarán, unidades, kg y caducidad mantienen anchuras fijas y Lote absorbe el ancho restante.
- La tabla de tarifas fija diez columnas entre 58 y 92 px y elimina el desplazamiento horizontal; su cabecera de dos filas mide 62 px.

## Aspecto visual actual

- La página usa el estilo global de controles y tablas de `assets/styles.qss`.
- Las listas son de solo lectura, con selección de fila, cabeceras clicables y sin borde de foco en los ítems.
- `detailPanel` usa el diseño enterprise compacto: cabecera azul marino, icono de producto blanco y cuerpo gris muy claro. Sus grupos PRODUCTO y DISTRIBUIDOR ordenan los campos en proporciones responsivas 2/2/5 y 3/2/5 respectivamente.
- Los campos de detalle tienen fondo blanco, borde #C5D0DE, radio 6 px, alto 28 px y foco turquesa #087E9C. El desplegable usa `assets/icons/chevron-down-navy.svg`.
- Los radios de estado se muestran como controles segmentados: blanco con borde gris en reposo y turquesa #087E9C con texto blanco al seleccionarse; los indicadores circulares nativos quedan ocultos.
- `ireksDataTab` usa fondo blanco; sus etiquetas son azul grisáceo `#486081` y los campos tienen altura mínima de 28 px.
- Entradas se presenta en una tarjeta blanca con borde `#E5EAF1`, radio 10 px, tabla blanca y cabecera `#F7F9FC`; las filas alternas y el hover aportan contraste suave.
- Las tablas de totales de movimientos no muestran scroll, usan fondo `#F7F9FC` y quedan unidas visualmente a su tabla.
- Los botones de tarifa tienen colores propios: añadir verde, editar azul y eliminar rojo.
- Los botones del ribbon siguen los roles estándar: verde para altas, rojo para eliminación, azul para listados y gris para acciones auxiliares.

## Diálogos y flujos relacionados

- `IngredientIreksCreateDialog`: alta de un producto IREKS con catálogos disponibles.
- `AddTarifaIreksDialog`: alta o edición de una tarifa, calculando los valores por envase y por kg.
- Diálogo de ID: muestra el identificador técnico del producto seleccionado.
- Diálogo `Listados de productos IREKS`: permite generar, exportar a Excel/PDF e imprimir el resultado del listado.
- Confirmación de eliminación: evita borrar un producto sin confirmación explícita.

## Relación con backend / datos

- `IngredientsIreksPage` es UI PySide6 y consulta servicios locales; no utiliza el frontend React.
- `IngredientIreksService` centraliza la consulta de catálogo, alta, actualización, eliminación, tarifas, nutrición, referencias de distribuidor y movimientos/pedidos.
- `IngredientIreksAutosaveFlowService` valida y ejecuta la actualización diferida de la ficha seleccionada.
- `SalesAnnualComparisonService` proporciona los años y clientes consumidores de la pestaña Clientes.
- `MonthlyOrdersService` construye el resumen de pedidos mensuales.
- `ProductReportFlowService` interpreta la petición de listado y prepara las filas exportables; `ReportExportService` resuelve los destinos de exportación.

## Ajustes y limitaciones relevantes documentados

- La ficha es editable y su autosave persiste cambios reales; no existe un botón general Guardar para deshacerlos.
- El rediseño solo reorganiza visualmente los mismos campos, grupos y señales de autoguardado; no modifica la persistencia ni los contratos de datos.
- La eliminación de producto y las operaciones de tarifa son mutaciones reales sobre datos locales.
- Las pestañas de movimientos, pedidos, tarifas, nutrición y clientes dependen del producto seleccionado; sin selección muestran tabla vacía o estado vacío.
- La pestaña Clientes es de consulta: no permite cambiar la relación entre cliente y producto desde esta pantalla.
- El diálogo de listados se abre como no modal y las exportaciones solo se habilitan después de generar un resultado válido.

## Modales principales

- Modal `Nuevo producto IREKS`: `IngredientIreksCreateDialog`.
- Modal `Añadir/Editar tarifa`: `AddTarifaIreksDialog`.
- Modal `ID de producto`: muestra el ID del producto seleccionado.
- Ventana `Listados de productos IREKS`: generación, previsualización y exportación de listados.
