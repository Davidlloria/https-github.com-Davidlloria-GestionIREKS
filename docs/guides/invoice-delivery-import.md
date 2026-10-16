# Facturas y albaran ausente

En Pedidos, seleccionar el pedido correcto y pulsar **Imp. Factura**. El PDF puede
contener varias facturas y paginas de continuacion. Las paginas identificadas
como instrucciones de entrega no aportan lineas; una pagina no identificable
detiene la lectura para evitar omisiones silenciosas.

La vista previa muestra a que factura pertenece cada linea y el plan completo:

- Facturas nuevas: se importan por separado con sus propios totales.
- Facturas ya importadas: se omiten.
- Albaran ausente: se crea una sola vez, reuniendo las lineas de todas las
  facturas del archivo que lo referencian. Su fecha es la fecha de factura.
- Albaran existente: se conserva sin reparar ni modificar lineas, fechas,
  decisiones de recepcion o entradas de almacen.
- Si la factura existe pero falta el albaran, se puede completar este ultimo
  desde las lineas del documento sin duplicar la factura.

Se comprueban pedido y almacen, coincidencias ambiguas, productos reconocidos,
cantidades e importes. Para crear un albaran se requieren lote y caducidad.
No se admite que un albaran nuevo tenga facturas con fechas distintas. El albaran
no puede ser anterior al pedido. Las lineas mantienen los distintos lotes y las
cantidades/envases del PDF; un precio cero explicito no se sustituye por tarifa.

Las cifras recuperadas del escaneo o calculadas a partir del importe, descuento
y cantidad se senalan en el plan y tienen un aviso al pasar el puntero sobre la
linea. Deben revisarse antes de confirmar. La lectura utiliza el OCR local ya
disponible; no envia el documento a servicios externos. La suma de lineas debe
coincidir con el neto cuando este figura en la cabecera (tolerancia de 0,02 para
redondeos). El PDF puede contener ajustes de centimos en la cabecera.

Al confirmar, el conjunto se guarda en una unica transaccion SQLite. Se repiten
las comprobaciones bajo bloqueo de escritura; cualquier fallo revierte facturas,
albaranes, movimientos, recepciones, pendientes y referencias del pedido.
Crear un albaran registra sus entradas de almacen y utiliza las reglas existentes
de asignacion de recepciones. Reimportar el mismo archivo no duplica existencias.
Cancelar la vista previa no escribe datos.

## Caso comprobado

El PDF aportado de IGSA contiene las facturas 60062 (1.499,28 EUR) y 60063
(21.070,82 EUR), ambas del 13/10/2026, con 17 lineas y el albaran 2026090131.
El ensayo se realiza exclusivamente con una base y un catalogo temporales:
dos facturas, un albaran del 13/10/2026 y 17 movimientos. La repeticion no duplica
registros. Se conserva el lote promocional 111.260827 y su precio cero. Tres
lineas requieren recuperacion numerica y se advierten en la vista previa.

Las pruebas del repositorio generan sus propios PDF y datos; el documento real,
las capturas y las bases temporales no se incluyen en Git. Este cambio no importa
el PDF en la base operativa ni confirma que todos sus productos esten dados de
alta alli. Si falta una referencia real, se informa y se detiene antes de guardar.

## Limites del primer corte

- Una importacion se vincula al pedido seleccionado; no distribuye facturas
  entre varios pedidos automaticamente.
- Si un albaran ya existe, no se completa aunque parezca parcial: se respeta la
  regla de importar solo la factura. No ejecutar este flujo para repararlo.
- Si las facturas se reciben en archivos separados, el primer archivo solo puede
  aportar sus propias lineas al albaran ausente. Para un albaran compartido, importar
  juntas las facturas que contienen todo su detalle, como en el PDF comprobado.
- No se crea ni se simula el PDF original del albaran: se crean sus registros
  operativos a partir de las facturas.
- Los importadores independientes de albaranes y el metodo legacy de factura
  conservan su comportamiento. El boton Imp. Factura y la entrada PDF del servicio
  utilizan el nuevo flujo conjunto. No hay cambios en API, React ni packaging.

## Comprobacion manual

1. Abrir la app y seleccionar el pedido y almacen a los que pertenecen las facturas.
2. Pulsar Imp. Factura y seleccionar el PDF conjunto.
3. Verificar 60062, 60063, albaran 2026090131 y fecha 2026-10-13 en el plan.
4. Revisar las tres lineas advertidas, lotes, cantidades y los totales de cabecera.
5. Cancelar para comprobar que no se ha guardado nada, o confirmar cuando los datos
   sean correctos. La confirmacion si modifica la base operativa y las existencias.
6. Revisar las dos facturas y el albaran en las pestanas del pedido. Una segunda
   importacion del mismo PDF debe informar de que los documentos ya existen.
