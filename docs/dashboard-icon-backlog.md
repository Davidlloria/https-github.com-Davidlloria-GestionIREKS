# Dashboard icon backlog

Fecha: 2026-07-26
Rama de referencia: `feature/dashboard-orders-clean`

## Dashboard pedidos

Estos son los iconos originalmente previstos para el dashboard de pedidos y que no estaban disponibles en `assets/icons/` en el momento de la implementacion.

| Uso en UI | Icono previsto | Estado actual | Nota |
|---|---|---|---|
| KPI `Kg recibidos` | `package-check.svg` | sustituido temporalmente por `circle-check.svg` | Buscar o disenar un icono de paquete recibido / validado. |
| KPI `Kg pendientes` | `package-open.svg` | sustituido temporalmente por `clipboard-list.svg` | Buscar o disenar un icono de paquete pendiente / abierto. |
| KPI `Incidencias` | `alert.svg` | sustituido temporalmente por `clock-3.svg` | Buscar o disenar un icono de alerta / incidencia. |
| Boton header `Actualizar` en modo `Pedidos` | `package-open.svg` | sustituido temporalmente por `clipboard-list.svg` | Reutilizar el icono definitivo de pendiente / abierto cuando exista. |


## Dashboard almacen

Estos son los iconos previstos y actualmente utilizados por el dashboard de almacen.

| Uso en UI | Icono previsto | Estado actual | Nota |
|---|---|---|---|
| KPI `Stock total` | `package.svg` | disponible en repo | OK. |
| KPI `Riesgos` | `alert.svg` | disponible en repo | OK. |
| KPI `Entradas mes` | `database-down.svg` | disponible en repo | OK. |
| KPI `Salidas mes` | `database-up.svg` | disponible en repo | OK. |
| Boton sidebar `Almacen` | `warehouse.svg` | disponible en repo | OK. |
| Boton header `Ver almacen` | `warehouse.svg` | disponible en repo | OK. |
| Boton header `Actualizar` en modo `Almacen` | `package-search.svg` | disponible en repo | OK. |

## Criterio para incorporarlos mas adelante

- Guardarlos en `assets/icons/`.
- Mantener nombres exactos:
  - `package-check.svg`
  - `package-open.svg`
  - `alert.svg`
- Sustituir las referencias temporales en `app/ui/widgets/dashboard_page.py`.
- Validar visualmente el dashboard de pedidos despues del cambio.
