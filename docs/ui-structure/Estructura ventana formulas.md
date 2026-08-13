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
RecipesPage (QWidget)
└── root (QVBoxLayout)
    └── splitter horizontal (sin tirador visible, childrenCollapsible=False, tamaños iniciales 332 / 930)
        ├── panel izquierdo (QWidget, ancho fijo 332 px)
        │   ├── QLabel "Recetas"
        │   └── recipe_tabs (QTabWidget)
        │       ├── IREKS
        │       │   ├── ireks_recipe_search (QLineEdit, búsqueda por ocurrencia)
        │       │   └── ireks_recipe_table (QTableWidget, 2 columnas, ordenable)
        │       │       ├── Nº (52 px)
        │       │       └── Nombre receta (stretch)
        │       └── Clientes
        │           ├── customer_filter_btn (QPushButton "Todos los clientes", btnRole="secondary")
        │           ├── load_base_btn (QPushButton "Cargar receta base", btnRole="success")
        │           └── customer_recipe_table (QTableWidget, 2 columnas, ordenable)
        │               ├── Nº (52 px)
        │               └── Nombre receta (stretch)
        └── panel derecho (QWidget, ocupa el espacio restante)
            ├── barra de acciones (QHBoxLayout)
            │   ├── Nueva (success)
            │   ├── Guardar (primary)
            │   ├── Guardar como versión (warning)
            │   ├── Duplicar (secondary)
            │   ├── Eliminar (danger)
            │   ├── Recalcular (primary)
            │   ├── Imprimir (secondary)
            │   ├── Exportar PDF (secondary)
            │   └── Exportar Excel (secondary)
            ├── header_row (alto fijo 64 px)
            │   ├── recipe_header_box (QGroupBox "Receta", 460 x 64 px)
            │   │   └── nombre_input (QLineEdit, posición absoluta, ancho 440 px)
            │   └── customer_header_box (QGroupBox "Cliente", 460 x 64 px)
            │       └── customer_name_value (QLabel de solo lectura, visible en la pestaña Clientes)
            └── editor_tabs (QTabWidget)
                ├── Receta
                │   ├── receta_left_panel
                │   │   ├── lines_group (QGroupBox "Líneas de receta")
                │   │   │   ├── acciones de línea: Añadir, Eliminar, Escalar y Técnica
                │   │   │   ├── selector de proceso editable y botones + / -
                │   │   │   └── lines_table (QTableWidget, alto fijo para 10 filas mínimas)
                │   │   │       ├── Ingrediente (stretch)
                │   │   │       ├── Nota (108 px)
                │   │   │       ├── Cantidad (86 px)
                │   │   │       ├── Und (52 px)
                │   │   │       └── Proceso (94 px)
                │   │   └── summary_group (QGroupBox "Resumen técnico")
                │   │       └── píldoras: Masa total, Total harinas, Total líquidos e Hidratación
                │   └── nutrition_panel (QGroupBox "Valores nutricionales", ancho 272 px)
                │       └── nutrition_table (QTableWidget, 8 filas, valores por 100 g)
                ├── Proceso
                │   └── process_group (QGroupBox "Proceso")
                │       └── proceso_input (ExpandablePlainTextEdit)
                ├── Observaciones
                │   └── notes_group (QGroupBox "Observaciones")
                │       └── observaciones_input (QPlainTextEdit)
                └── Imagenes
                    ├── images_ribbon (acciones Añadir imagen, Quitar y Marcar principal)
                    └── images_list (QListWidget en modo iconos, selección múltiple y reordenación interna)
```

## Comportamiento actual

- Al abrirse, carga clientes, el listado de recetas de la pestaña activa y una receta nueva en memoria.
- La pestaña `IREKS` lista recetas base; su buscador filtra por ocurrencia. La pestaña `Clientes` lista recetas del cliente seleccionado o de todos los clientes.
- Cambiar de pestaña fuerza el autosave pendiente, prepara una receta nueva y recarga el listado aplicable.
- `customer_filter_btn` abre un selector de cliente. Al elegir uno, actualiza el listado y el campo de cliente visible de la receta.
- `load_base_btn` permite cargar una receta base en una receta de cliente, clonando líneas, proceso, observaciones y parámetros; no guarda hasta la acción de guardado/autosave.
- Las tablas de recetas son de solo lectura, ordenables y cargan la receta al seleccionar una fila.
- El encabezado real conserva más datos que los visibles en esta composición: cliente, código, versión, estado, masa deseada, peso de pieza, número de piezas y merma se mantienen en el modelo y se usan en los flujos de cálculo y guardado.
- `lines_table` tiene al menos 10 filas, permite editar cantidad, unidad, nota y proceso. Un doble clic sobre ingrediente abre la búsqueda de ingrediente o de proceso origen.
- El selector de procesos filtra las líneas visibles. `Masa final` siempre existe y no se puede eliminar; eliminar otro proceso solicita el proceso de sustitución para sus líneas.
- Añadir una línea abre `IngredientSearchDialog`; puede insertar un ingrediente o reutilizar la cantidad de un proceso anterior como subproceso.
- Cada modificación de línea recalcula el resumen y programa autosave. El autosave usa un temporizador de 450 ms y también se vacía al ocultar/cerrar la página o cambiar de receta/pestaña.
- `Recalcular` sincroniza categorías, calcula la receta, actualiza las líneas y el resumen, y conserva incidencias en memoria.
- El resumen se calcula sobre el proceso principal (`Masa final` si existe): masa total, harinas, líquidos e hidratación. La tabla nutricional se recalcula por 100 g cuando hay información nutricional disponible.
- `Técnica` abre la ficha técnica de la receta, donde se editan escandallo y elaboración y se exportan PDFs simple o extendido; al aceptar, la ficha persiste inmediatamente los cambios.
- La pestaña `Proceso` abre un editor ampliado con doble clic o `Ctrl+Shift+P`; incluye la opción de generar texto con ChatGPT mediante `OpenAIProcessService`.
- La pestaña `Imagenes` permite añadir, quitar, marcar imagen principal, previsualizar con doble clic y reordenar imágenes mediante arrastre; el orden se guarda con la receta.
- `Guardar` valida nombre y, para recetas de cliente, cliente seleccionado. `Guardar como versión` pide un comentario. `Duplicar` clona la receta actual y `Eliminar` solicita confirmación.
- `Exportar PDF` exige una receta guardada y permite elegir diseño simple o extendido. `Imprimir` y `Exportar Excel` muestran actualmente un aviso de fase futura.

## Geometría actual

- El splitter principal es horizontal, sin tirador visible (`handleWidth(0)`).
- El panel izquierdo mide exactamente 332 px; el derecho recibe el factor de estiramiento disponible.
- El tamaño inicial del splitter es aproximadamente 332 px / 930 px.
- `header_row`, `recipe_header_box` y `customer_header_box` tienen alto fijo de 64 px.
- Los grupos de cabecera se posicionan de forma absoluta: receta en `0,0` y cliente en `468,0`; ambos con ancho 460 px.
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
- `CustomerSearchDialog`: filtra clientes y permite volver a “Todos los clientes”.
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
- Modal `Seleccionar cliente`: `CustomerSearchDialog`.
- Modal `Escalar receta`: `RecipeScaleDialog`.
- Modal `Ficha técnica`: `RecipeTechnicalDialog`.
- Modal `Editor de proceso`: diálogo de edición enriquecida del proceso.
- Modal `Exportar receta a PDF`: selector de diseño simple o extendido y posterior selector de archivo.
