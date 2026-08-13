# VENTANA FORMULAS — PYSIDE6 / BACKEND

Implementación principal:

- UI: `app/ui/widgets/recipes_page.py`
- Estilos compartidos: `assets/styles.qss`
- Servicios principales:
  - `app/services/recipe_service.py`
  - `app/services/recipe_active_flow_service.py`
  - `app/services/recipe_calculation_service.py`
  - `app/services/recipe_scaling_service.py`
  - `app/services/pdf_service.py`
  - `app/services/openai_process_service.py`
- Modelos relevantes:
  - `Receta`
  - `RecetaLinea`
  - `IngredienteIreks`
  - `IngredienteStd`
  - `MateriaPrimaPrecio`
  - `MateriaPrimaValorNutricional`

La sección principal se registra como `Formulas` en `app/ui/main_window.py`, aunque su widget se denomina `RecipesPage`.

## Estructura UI real

```text
RecipesPage (QWidget, objectName `RecipesPageRoot`, fondo #EEF3F8, sin borde, WA_StyledBackground=True)
└── root (QVBoxLayout, transparente, sin borde, márgenes 14 px, separación 10 px)
    ├── topRibbon (QFrame, objectName `topRibbon`, pageType="contacts", fondo #FFFFFF, borde #E2E8F1, radio 8 px)
    │   ├── Nueva (QPushButton, icono `plus.svg`, fondo #DCFCE7, borde #86EFAC, radio 7 px, 110 x 30 px)
    │   ├── Guardar (QPushButton, icono `save.svg`, fondo #DBEAFE, borde #93C5FD, radio 7 px, 110 x 30 px)
    │   ├── Versión (QPushButton, icono `history.svg`, fondo #FEF3C7, borde #FCD34D, radio 7 px, 110 x 30 px)
    │   ├── Duplicar (QPushButton, icono `file-text.svg`, fondo #E2E8F0, borde #CBD5E1, radio 7 px, 110 x 30 px)
    │   ├── Eliminar (QPushButton, icono `trash.svg`, fondo #FEE2E2, borde #FCA5A5, radio 7 px, 110 x 30 px)
    │   ├── Recalcular (QPushButton, icono `refresh-cw.svg`, fondo #F3E8FF, borde #D8B4FE, radio 7 px, 110 x 30 px)
    │   ├── Imprimir (QPushButton, icono `printer.svg`, fondo #E2E8F0, borde #CBD5E1, radio 7 px, 110 x 30 px)
    │   ├── PDF (QPushButton, icono `file-text.svg`, fondo #E2E8F0, borde #CBD5E1, radio 7 px, 110 x 30 px)
    │   ├── Excel (QPushButton, icono `sheet.svg`, fondo #E2E8F0, borde #CBD5E1, radio 7 px, 110 x 30 px)
    │   └── espacio flexible (transparente, sin borde)
    └── splitter horizontal (objectName `recipesMainSplitter`, fondo transparente, sin borde, handle transparente de 5 px, childrenCollapsible=False, tamaños iniciales 332 / 930)
        ├── panel izquierdo (QWidget, objectName `recipesSidePanel`, fondo #FFFFFF, borde #D7DEE8, radio 8 px, ancho fijo 332 px)
        │   └── recipe_tabs (QTabWidget, pane fondo #FFFFFF, borde #D7DEE8, radio 8 px)
        │       ├── pestaña IREKS (tab no seleccionado fondo #F7FAFD, borde #DDE5F0; seleccionado fondo #FFFFFF, borde inferior #2563EB)
        │       │   ├── ireks_tab (QWidget, fondo transparente, sin borde)
        │       │   ├── ireks_recipe_search (QLineEdit, fondo #FFFFFF, borde #C8D2DF, radio 6 px)
        │       │   └── ireks_recipe_table (QTableWidget, fondo #FFFFFF, borde #D8E0EA, radio 8 px, 2 columnas, ordenable)
        │       │       ├── Nº (52 px; item transparente, sin borde; cabecera fondo #EEF2F7, borde inferior #D8E0EA)
        │       │       └── Nombre receta (stretch; item transparente, sin borde; cabecera fondo #EEF2F7, borde inferior #D8E0EA)
        │       └── pestaña Clientes (tab no seleccionado fondo #F7FAFD, borde #DDE5F0; seleccionado fondo #FFFFFF, borde inferior #2563EB)
        │           ├── customer_tab (QWidget, fondo transparente, sin borde)
        │           ├── customer_filter_row (QHBoxLayout, transparente, sin borde)
        │           │   ├── customer_filter_input (QLineEdit, objectName `customerRecipeFilterInput`, fondo #FFFFFF, borde #C8D2DF, radio 6 px, alto 34 px; selecciona todo el texto al recibir foco)
        │           │   └── customer_filter_clear_btn (QPushButton, objectName `customerRecipeFilterClearButton`, icono blanco `eraser.svg`, fondo rojo #D96464, borde blanco #FFFFFF, límites 34 x 34 px y sin padding; fondo rojo pálido #F7CACA si está deshabilitado)
        │           ├── customer_filter_results (QTableWidget, objectName `customerRecipeFilterResults`, fondo #FFFFFF, borde #D8E0EA, radio 8 px, oculto hasta escribir, alto máximo 180 px)
        │           │   ├── Código (cabecera fondo #EEF2F7, borde inferior #D8E0EA)
        │           │   └── Cliente (cabecera fondo #EEF2F7, borde inferior #D8E0EA)
        │           └── customer_recipe_table (QTableWidget, fondo #FFFFFF, borde #D8E0EA, radio 8 px, 2 columnas, ordenable)
        │               ├── Nº (52 px; item transparente, sin borde; cabecera fondo #EEF2F7, borde inferior #D8E0EA)
        │               └── Nombre receta (stretch; item transparente, sin borde; cabecera fondo #EEF2F7, borde inferior #D8E0EA)
        └── panel derecho (QWidget, objectName `recipesContentPanel`, fondo transparente, sin borde, ocupa el espacio restante; layout sin márgenes y separación 10 px)
            ├── header_row (QWidget, objectName `recipesHeaderRow`, fondo #FFFFFF, borde #D7DEE8, radio 8 px, alto fijo 64 px)
            │   ├── recipe_header_box (QGroupBox, objectName `recipeHeaderBox`, fondo transparente, sin borde, posición y=4 px, 460 x 58 px)
            │   │   └── nombre_input (QLineEdit, fondo #FFFFFF, borde #C8D2DF, radio 6 px, posición y=21 px, ancho 440 px)
            │   ├── header_separator (QFrame, objectName `recipesHeaderSeparator`, fondo #D7DEE8, sin borde, 1 x 48 px)
            │   └── customer_header_box (QGroupBox, objectName `customerHeaderBox`, fondo transparente, sin borde, posición y=4 px, 500 x 58 px)
            │       ├── customer_name_value (QLabel, objectName `customerNameValue`, fondo #FFFFFF, borde #D7DEE8, radio 6 px, posición y=21 px, alto 34 px y ancho disponible hasta el botón, visible en la pestaña Clientes)
            │       └── change_customer_btn (QPushButton, objectName `changeRecipeCustomerButton`, icono blanco `user-round-pen.svg`, fondo azul #2563EB, borde #2563EB, 34 x 34 px; a la derecha del cliente y habilitado solo para recetas de cliente guardadas)
            └── editor_tabs (QTabWidget, objectName `recipeEditorTabs`, contenedor y paneles de pestaña fondo transparente, sin borde)
                ├── pestaña Receta (tab no seleccionado fondo #F7FAFD, borde #DDE5F0; seleccionado fondo #FFFFFF, borde inferior #2563EB)
                │   ├── receta_tab / receta_left_panel (QWidget, fondo transparente, sin borde)
                │   │   ├── recipe_ribbon (QFrame, objectName `recipeRibbon`, fondo transparente, sin borde)
                │   │   │   ├── Escalar (QPushButton, icono `scale.svg`, estilo estándar primary)
                │   │   │   ├── Técnica (QPushButton, icono `cooking-pot.svg`, estilo estándar secondary)
                │   │   │   ├── Cargar (QPushButton, icono `download.svg`, estilo estándar success; visible solo en la pestaña Clientes)
                │   │   │   ├── Pdf (QPushButton, icono `file-text.svg`, estilo estándar secondary)
                │   │   │   └── Excel (QPushButton, icono `sheet.svg`, estilo estándar secondary)
                │   │   ├── recipe_process_row (QWidget, transparente, sin borde; situado bajo `recipeRibbon`)
                │   │   │   ├── QLabel "Proceso" (fondo transparente, sin borde)
                │   │   │   ├── active_process_combo (QComboBox editable, fondo #FFFFFF, borde #C8D2DF, radio 6 px, alto 30 px)
                │   │   │   ├── + (QPushButton, fondo #5BBE6A, borde #5BBE6A, radio 6 px, alto 30 px)
                │   │   │   └── - (QPushButton, fondo #D96464, borde #D96464, radio 6 px, alto 30 px)
                │   │   ├── lines_group (QGroupBox "Líneas de receta", fondo #FFFFFF, borde #D8E0EA, radio 8 px)
                │   │   │   └── lines_table (QTableWidget, fondo #FFFFFF, borde #D8E0EA, radio 8 px, alto fijo para 10 filas mínimas; menú contextual: Añadir fila y Eliminar fila)
                │   │   │       ├── Ingrediente (stretch; cabecera fondo #EEF2F7, borde inferior #D8E0EA)
                │   │   │       ├── Nota (108 px; cabecera fondo #EEF2F7, borde inferior #D8E0EA)
                │   │   │       ├── Cantidad (86 px; cabecera fondo #EEF2F7, borde inferior #D8E0EA)
                │   │   │       ├── Und (52 px; cabecera fondo #EEF2F7, borde inferior #D8E0EA)
                │   │   │       └── Proceso (94 px; cabecera fondo #EEF2F7, borde inferior #D8E0EA)
                │   │   └── summary_group (QGroupBox "Resumen técnico", fondo #FFFFFF, borde #D8E0EA, radio 8 px)
                │   │       └── píldoras (QFrame, fondo #F8FAFD, borde #CAD3DF, radio 14 px): Masa total, Total harinas, Total líquidos e Hidratación
                │   └── nutrition_panel (QGroupBox "Valores nutricionales", fondo #FFFFFF, borde #D8E0EA, radio 8 px, ancho 272 px)
                │       └── nutrition_table (QTableWidget, fondo transparente, sin borde, 8 filas, valores por 100 g; cabecera fondo #E6EAF0, sin borde)
                ├── pestaña Escandallo (QWidget, fondo transparente, sin borde)
                │   ├── escandallo_ribbon (QFrame, objectName `escandalloRibbon`, fondo transparente, sin borde; separación de 5 px con escandallo_group)
                │   │   ├── Excel (QPushButton, icono `sheet.svg`, estilo estándar secondary)
                │   │   └── Pdf (QPushButton, icono `file-text.svg`, estilo estándar secondary)
                │   ├── escandallo_group (QGroupBox sin etiqueta, fondo #FFFFFF, borde #D8E0EA, radio 8 px; ocupa el lado izquierdo)
                │   │   ├── escandallo_table (QTableWidget, columnas Ingrediente, Cantidad, % panadero, €/kg y €/ingrediente; €/kg editable)
                │   │   └── escandallo_totals_frame (QFrame azul #2F80ED, radio 8 px) → escandallo_totals_table (QTableWidget transparente, totales sin barras de desplazamiento y columnas sincronizadas con la tabla)
                │   └── total_panel (QFrame, objectName `totalPanel`, fondo #FFFFFF, borde #D8E0EA, radio 8 px, ancho 300 px; a la derecha y con la misma altura que escandallo_group)
                │       └── píldoras superiores, texto ampliado: Total masa (valor técnico), Peso por pieza (QLineEdit editable y sincronizado bidireccionalmente con la ficha técnica), Total piezas (Total masa / Peso por pieza, mismo rendimiento técnico) y Coste unitario (mismo cálculo de la ficha técnica)
                │   └── escandallo_summary_group (QGroupBox sin etiqueta, fondo #FFFFFF, borde #D8E0EA, radio 8 px)
                │       └── píldoras centradas verticalmente y sin borde interno: texto 13 px; Total masa #DBEAFE, Peso por pieza #DCFCE7, Total piezas #FEF3C7 y Coste unitario #F3E8FF
                ├── pestaña Proceso (tab no seleccionado fondo #F7FAFD, borde #DDE5F0; seleccionado fondo #FFFFFF, borde inferior #2563EB)
                │   └── process_group (QGroupBox "Proceso", fondo #FFFFFF, borde #D8E0EA, radio 8 px)
                │       └── proceso_input (ExpandablePlainTextEdit, fondo #F8FAFD, borde #CAD3DF, radio 6 px)
                ├── pestaña Observaciones (tab no seleccionado fondo #F7FAFD, borde #DDE5F0; seleccionado fondo #FFFFFF, borde inferior #2563EB)
                │   └── notes_group (QGroupBox "Observaciones", fondo #FFFFFF, borde #D8E0EA, radio 8 px)
                │       └── observaciones_input (QPlainTextEdit, fondo #F8FAFD, borde #CAD3DF, radio 6 px)
                └── pestaña Imagenes (tab no seleccionado fondo #F7FAFD, borde #DDE5F0; seleccionado fondo #FFFFFF, borde inferior #2563EB)
                    ├── images_ribbon (QWidget, objectName `recipesImagesRibbon`, fondo transparente, sin borde)
                    │   ├── Añadir imagen (QPushButton, fondo #2FA84F, sin borde, radio 6 px)
                    │   ├── Quitar (QPushButton, fondo #D96464, borde #D96464, radio 6 px)
                    │   └── Marcar principal (QPushButton, fondo #2563EB, borde #2563EB, radio 6 px)
                    └── images_list (QListWidget, fondo transparente, sin borde; tarjetas fondo #F8FAFD, borde #CAD3DF, radio 10 px)
```

## Comportamiento actual

- Al abrirse, carga clientes, el listado de recetas de la pestaña activa y una receta nueva en memoria.
- La pestaña `IREKS` lista recetas base; su buscador filtra por ocurrencia. La pestaña `Clientes` lista recetas del cliente seleccionado o de todos los clientes.
- Cambiar de pestaña fuerza el autosave pendiente, prepara una receta nueva y recarga el listado aplicable.
- `customer_filter_input` sustituye al selector modal: al escribir consulta clientes y despliega `customer_filter_results`; al hacer clic en una fila (o pulsar Intro) filtra el listado. Limpiar el campo vuelve a mostrar recetas de todos los clientes. El campo visible de la receta permanece vacío hasta seleccionar una receta.
- `Nueva` limpia todos los campos en IREKS. En Clientes abre `CustomerRecipeSelectionDialog`, que filtra clientes y exige seleccionar uno antes de preparar la receta nueva.
- `change_customer_btn` abre el selector de clientes, solicita confirmación y reasigna únicamente el cliente de una receta de cliente guardada; después actualiza el encabezado y el listado.
- `load_base_btn` permite cargar una receta base en una receta de cliente, clonando líneas, proceso, observaciones y parámetros; no guarda hasta la acción de guardado/autosave.
- Las tablas de recetas son de solo lectura, ordenables y cargan la receta al seleccionar una fila.
- El encabezado real conserva más datos que los visibles en esta composición: cliente, código, versión, estado, masa deseada, peso de pieza, número de piezas y merma se mantienen en el modelo y se usan en los flujos de cálculo y guardado.
- `lines_table` tiene al menos 10 filas, permite editar cantidad, unidad, nota y proceso. Un doble clic sobre ingrediente abre la búsqueda de ingrediente o de proceso origen.
- El menú contextual de `lines_table` ofrece `Añadir fila` y `Eliminar fila`. `Añadir fila` ejecuta el mismo flujo que la acción de añadir anterior: abre `IngredientSearchDialog`; `Eliminar fila` elimina la fila pulsada y mantiene el mínimo de 10 filas.
- El selector de procesos filtra las líneas visibles. `Masa final` siempre existe y no se puede eliminar; eliminar otro proceso solicita el proceso de sustitución para sus líneas.
- La incorporación de una línea desde el menú contextual abre `IngredientSearchDialog`; puede insertar un ingrediente o reutilizar la cantidad de un proceso anterior como subproceso.
- Cada modificación de línea recalcula el resumen y programa autosave. El autosave usa un temporizador de 450 ms y también se vacía al ocultar/cerrar la página o cambiar de receta/pestaña.
- `Recalcular` sincroniza categorías, calcula la receta, actualiza las líneas y el resumen, y conserva incidencias en memoria.
- El resumen se calcula sobre el proceso principal (`Masa final` si existe): masa total, harinas, líquidos e hidratación. La tabla nutricional se recalcula por 100 g cuando hay información nutricional disponible.
- `Técnica` abre la ficha técnica de la receta, donde se editan escandallo y elaboración y se exportan PDFs simple o extendido; al aceptar, la ficha persiste inmediatamente los cambios. Peso por pieza y coste unitario se reflejan en las píldoras de `total_panel`.
- La pestaña `Proceso` abre un editor ampliado con doble clic o `Ctrl+Shift+P`; incluye la opción de generar texto con ChatGPT mediante `OpenAIProcessService`.
- La pestaña `Imagenes` permite añadir, quitar, marcar imagen principal, previsualizar con doble clic y reordenar imágenes mediante arrastre; el orden se guarda con la receta.
- `Guardar` valida nombre y, para recetas de cliente, cliente seleccionado. `Guardar como versión` pide un comentario. `Duplicar` clona la receta actual y `Eliminar` solicita confirmación.
- `Exportar PDF` exige una receta guardada y permite elegir diseño simple, extendido o mínimo. En el formato `Mínimo` primero se selecciona mediante radios excluyentes si se incluye el escandallo y después se genera una única vista previa; muestra una copia de la tabla Receta y, opcionalmente, las píldoras de Total masa, Peso por pieza, Total piezas y Coste unitario junto con la tabla Escandallo. El título es el nombre de la receta. `Imprimir` y `Exportar Excel` muestran actualmente un aviso de fase futura.

## Geometría actual

- El splitter principal es horizontal y deja un espacio transparente de 5 px entre panel izquierdo y derecho (`handleWidth(5)`).
- El panel izquierdo mide exactamente 332 px; el derecho recibe el factor de estiramiento disponible.
- El layout del panel derecho no tiene márgenes: `header_row` queda alineado con su borde superior; mantiene 10 px de separación respecto al editor de pestañas.
- El tamaño inicial del splitter es aproximadamente 332 px / 930 px.
- `header_row`, `recipe_header_box` y `customer_header_box` tienen alto fijo de 64 px.
- Los grupos de cabecera se posicionan de forma absoluta: receta en `0,0` y cliente en `468,0`; ambos con ancho 460 px.
- `recipeRibbon` se sitúa antes de `lines_group`; la fila de controles de proceso se sitúa inmediatamente debajo. El selector y los botones de proceso tienen alto fijo de 30 px.
- `lines_table` tiene una altura fija equivalente a cabecera más 10 filas de 30 px, para mantener un editor de líneas compacto y estable.
- `nutrition_panel` tiene ancho mínimo y máximo de 272 px; sus columnas miden 146 px y 88 px.
- Las píldoras del resumen técnico miden 150 x 48 px.
- La pestaña de imágenes usa una cinta superior de 56 px y una lista de iconos con cuadrícula de 154 x 140 px e iconos de 132 x 98 px.

## Aspecto visual actual

- La página usa los estilos globales de `assets/styles.qss` para botones, tablas, pestañas, cuadros de grupo, campos y selección.
- Los botones se colorean por `btnRole`: `success` para altas/carga de base, `primary` para guardado o cálculo, `warning` para versiones, `danger` para borrados y `secondary` para acciones auxiliares.
- `lines_table` usa selección de fila completa, sin foco visual y delegados específicos para nota, cantidad, unidad y proceso.
- La tabla nutricional es compacta: fondo transparente, sin grid, cabecera gris y valores alineados a la derecha.
- Las píldoras del resumen técnico usan fondo `#F8FAFD`, borde `#CAD3DF`, radio de 14 px e iconos circulares sobre fondo blanco.
- Los editores de proceso y observaciones usan fondo `#F8FAFD`, borde `#CAD3DF`, radio de 6 px y relleno interno.
- La galería de imágenes utiliza tarjetas `#F8FAFD` con borde `#CAD3DF`, radio de 10 px; la selección usa borde azul y fondo `#EAF2FF`.

## Diálogos y flujos relacionados

- `IngredientSearchDialog`: busca ingredientes por código, nombre o familia; también permite insertar la salida de otro proceso.
- `BaseRecipeSearchDialog`: filtra y selecciona una receta base IREKS para convertirla en punto de partida de una receta de cliente.
- `CustomerRecipeSelectionDialog`: filtra y selecciona el cliente obligatorio al crear una nueva receta desde la pestaña Clientes.
- `RecipeScaleDialog`: escala la receta por harina, masa total o piezas, según el modo elegido.
- `ProcessSourceDialog`: está definido para seleccionar un proceso fuente, pero `RecipesPage` no lo invoca actualmente; la inserción desde otro proceso se resuelve en `IngredientSearchDialog`.
- `RecipeTechnicalDialog`: concentra escandallo, parámetros de elaboración, costes, edición por proceso y exportación PDF simple/extendida.
- Editor ampliado de proceso: admite edición enriquecida y generación asistida por ChatGPT; su uso depende de la configuración disponible de `OpenAIProcessService`.
- Previsualización de imagen: abre la imagen seleccionada en un diálogo independiente.

## Relación con backend / datos

- `RecipesPage` es una UI PySide6; no consume el frontend React.
- `RecipeService` centraliza la consulta de recetas, clientes e ingredientes, cálculo, escalado, guardado, versionado, duplicado y borrado.
- `RecipeActiveFlowService` construye el payload activo y valida los requisitos de guardado antes de persistir.
- `RecipeService` delega los cálculos y la persistencia en `RecipeViewModel` y los repositorios/modelos locales.
- Los datos de escandallo, elaboración enriquecida y galería de imágenes se serializan en campos JSON de `Receta`.
- `PdfService` genera el documento de receta simple o extendido para una receta guardada.
- La información nutricional se resuelve a partir de ingredientes IREKS/STD y `MateriaPrimaValorNutricional`.

## Ajustes y limitaciones relevantes documentados

- La sección visible en navegación se llama `Formulas`, mientras el dominio y los nombres de clases usan “recetas”.
- Las acciones de guardar, duplicar, eliminar, versionar y autosave son mutaciones reales sobre datos locales.
- El autosave no persiste una receta sin nombre y, en la pestaña Clientes, tampoco persiste sin cliente seleccionado.
- `Imprimir` y `Exportar Excel` no están implementados; solo muestran un mensaje informativo de fase futura.
- La generación de proceso con ChatGPT depende del servicio/configuración local disponible; no es un flujo garantizado sin esa configuración.
- La ficha técnica puede guardar parámetros adicionales y precios de escandallo al cerrarse correctamente.

## Modales principales

- Modal `Buscar ingrediente`: `IngredientSearchDialog`.
- Modal `Cargar receta base`: `BaseRecipeSearchDialog`.
- Modal `Nueva receta de cliente`: `CustomerRecipeSelectionDialog`.
- Modal `Escalar receta`: `RecipeScaleDialog`.
- Modal `Ficha técnica`: `RecipeTechnicalDialog`.
- Modal `Editor de proceso`: diálogo de edición enriquecida del proceso.
- Modal `Exportar receta a PDF`: selector de diseño simple o extendido y posterior selector de archivo.
