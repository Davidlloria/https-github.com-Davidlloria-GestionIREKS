# Explorador de Trabajo en Inicio

La aplicacion PySide6 incluye la seccion **Inicio > Trabajo**. Se carga al
seleccionarla por primera vez y conserva la carpeta actual al cambiar de seccion.
La raiz es `Trabajo`, hermana del repositorio `GestionIREKS`; no depende de la
carpeta de datos de prueba ni modifica las bases de datos.

## Uso

La barra superior agrupa navegacion, ruta y filtro. La segunda barra contiene
las acciones y los selectores Lista/Iconos y Detalles. Abrir en Windows queda
en el pie. Los botones usan los SVG existentes, con estados de seleccion,
desactivacion y peligro; los archivos conservan los iconos nativos de Windows.

- Utilizar el arbol izquierdo o el doble clic para entrar en carpetas.
- Volver con Atras/Adelante, subir un nivel o pulsar un tramo de la ruta.
- Usar Lista o Iconos; las columnas de Lista permiten ordenar los elementos.
- El campo **Filtrar esta carpeta** filtra nombres de la carpeta actual.
- **Detalles** muestra u oculta el nombre, tipo y ubicacion del elemento seleccionado.
- Abrir un archivo con doble clic o **Abrir** utiliza su programa asociado en Windows.
- **Abrir en Windows** abre la carpeta actual en el Explorador del sistema.
- **Nueva carpeta** pide un nombre. Los documentos se crean con sus aplicaciones habituales.
- **Renombrar** o F2 cambia el nombre del elemento seleccionado. Cambiar la extension
  de un archivo requiere una confirmacion adicional.
- **Mover a...** abre un selector de carpetas restringido a Trabajo. Cancelar no cambia nada.
- **Eliminar**, el menu contextual o Supr desde la lista de archivos solicitan
  confirmacion para enviar el elemento a la Papelera de Windows. Las carpetas
  incluyen su contenido. Restaurar se realiza desde la Papelera de Windows.
- F5 actualiza; Alt+Izquierda, Alt+Derecha y Alt+Arriba controlan la navegacion.

Los cambios realizados desde Windows u otros programas se recogen con
**Actualizar/F5**. Las operaciones hechas desde la app actualizan la vista
automaticamente. Los modelos no vigilan las carpetas con manejadores nativos,
porque en Windows esa vigilancia bloqueaba el renombrado de carpetas visitadas
o de sus antecesoras, tanto desde la app como desde el Explorador de Windows.

Los botones de gestion se habilitan al seleccionar un elemento. El menu contextual
de la lista ofrece las mismas operaciones. Supr al escribir en el filtro edita el
texto y no solicita eliminar archivos.

## Limites y errores

Las operaciones se limitan a Trabajo; su raiz no se renombra, mueve ni elimina.
Los enlaces simbolicos y junctions se excluyen de la navegacion y gestion.
Se rechazan nombres reservados de Windows, colisiones y movimientos de una carpeta
dentro de si misma. Los destinos existentes se conservan.

Una carpeta ausente o sin permisos se indica expresamente. No se crea la raiz
automaticamente. Si una carpeta abierta desaparece, actualizar vuelve a un
antecesor existente. Archivos bloqueados o cambios externos pueden impedir una
operacion y producen un mensaje; el historial puede contener rutas desaparecidas.

La Papelera utiliza `IFileOperation` con `FOFX_RECYCLEONDELETE`, mediante pywin32,
que ya es dependencia de Windows. Los errores o cancelaciones no recurren a un
borrado permanente. Referencia del indicador:
[Microsoft: SetOperationFlags](https://learn.microsoft.com/es-es/windows/win32/api/shobjidl_core/nf-shobjidl_core-ifileoperation-setoperationflags).

El explorador no actualiza referencias que otros programas o registros puedan
tener a un archivo renombrado o movido. Conviene mantener estables los documentos
ya utilizados por otros flujos.

## Validacion del corte

- 44 pruebas de servicio, widget y limites de arquitectura.
- 16 pruebas de Inicio, incluida la carga diferida y reutilizacion de Trabajo.
- Una prueba de ventana principal en un proceso independiente.
- Total: 61 pruebas pasadas. ReportLab produjo un aviso de deprecacion por proceso.
- La prueba heredada de impresion de Inicio emitio excepciones COM de Windows
  `0x80040155` durante la inicializacion de QPrinter; las 16 pruebas terminaron
  pasando. La impresion real no forma parte de este corte y no se modifico.
- El ensayo inicial de iconos encontro un acceso nativo invalido por conservar
  un QModelIndex transitorio en la prueba; se corrigio adquiriendolo de nuevo
  tras los eventos asincronos y la regresion completa paso.
- Renderizado con Qt nativo de Windows, ventana oculta y servicios de dashboard
  de prueba; 15 ciclos de navegacion, cambios de vista y actualizacion correctos.
- Un archivo temporal se envio a la Papelera real, se encontro alli con contenido
  intacto y se restauro. Ningun archivo real de Trabajo fue modificado por las pruebas.

No se ejecuto la suite completa. No se modificaron API, React, contratos, bases,
launcher ni packaging. Capturas, inventarios y datos de prueba permanecen en `.tmp`
y no se incluyen en Git.

## Revision visual y correccion de modelos (2026-10-16)

Se desconectan las vistas antes de sustituir los modelos y se ignoran eventos
pendientes de modelos anteriores. Esto corrige `index from wrong model passed
to mapToSource` sin ocultar los avisos de Qt. Dos pruebas cubren la actualizacion
con seleccion y la activacion tardia de indices antiguos.

La revision pasa 46 pruebas de servicio/widget/arquitectura, 14 de Inicio y una
de ventana principal (61 en total). Se excluyen dos pruebas de PDF/impresion
ajenas a este cambio. Solo aparece la deprecacion conocida de ReportLab.
Las capturas nativas de lista, iconos y detalles, y 15 ciclos de navegacion,
cambio de vista y actualizacion, no reproducen el aviso del modelo.
Se conserva el desplazamiento local para rutas largas y no se modifican las
operaciones de archivos, el servicio ni los datos reales. No se ejecuta la suite completa.

## Comprobacion manual

1. Abrir Gestion IREKS desde el acceso directo y seleccionar **Inicio > Trabajo**.
2. Navegar por Clientes y volver; alternar Lista/Iconos y activar Detalles.
3. Crear una carpeta de prueba, renombrarla y moverla a otra carpeta de prueba.
4. Enviarla a la Papelera y restaurarla desde Windows.
5. Volver a Agenda para comprobar que conserva su funcionamiento.
