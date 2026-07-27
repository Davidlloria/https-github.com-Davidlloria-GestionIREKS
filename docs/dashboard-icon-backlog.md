# Dashboard icon backlog

Ultima actualizacion: 2026-07-27
Rama de referencia principal: `main`
Rama origen pendiente de extraccion: `feature/pedidos-window-tweaks`

## Objetivo del backlog

Registrar los iconos que faltan o que deben revisarse en cada movimiento de limpieza del dashboard, para restaurarlos de forma controlada mas adelante.

## Estado por movimientos ya cerrados

### Dashboard agenda

Sin backlog abierto especifico en este momento.

### Dashboard pedidos

Estado actual: sin faltantes criticos registrados.

Notas:

- durante la extraccion limpia se revisaron y restauraron los iconos del dashboard de pedidos
- si aparece alguna desviacion visual nueva, se registrara como incidencia nueva y no se reabre este bloque sin motivo funcional

### Dashboard almacen

Estado actual: sin faltantes criticos registrados.

Notas:

- el dashboard de almacen ya tiene su corte limpio integrado en `main`
- no quedan iconos pendientes documentados para este bloque

## Proximo movimiento: dashboard ventas

Iconos usados por el bloque en `feature/pedidos-window-tweaks` que no constan ahora mismo en `assets/icons/` de `main`:

| Uso en UI | Icono esperado en rama feature | Estado en `main` | Nota |
|---|---|---|---|
| Boton lateral `Ventas` | `bar-chart-3.svg` | no disponible | Incorporar antes o durante la extraccion limpia. |
| Boton header principal en modo `Ventas` | `bar-chart-3.svg` | no disponible | Debe reutilizar el mismo icono del boton lateral. |
| KPI `Variacion kg` | `trending-down.svg` | no disponible | Confirmar si se mantiene ese nombre o se sustituye por otro equivalente. |
| KPI `Clientes activos` | `briefcase.svg` | no disponible | Pendiente de incorporar. |
| KPI `Islas activas` | `map.svg` | no disponible | Pendiente de incorporar. |

## Movimiento posterior previsto: dashboard objetivos

| Uso en UI | Icono esperado en rama feature | Estado en `main` | Nota |
|---|---|---|---|
| Boton lateral `Objetivos` | `goal.svg` | no disponible | Registrar para incorporarlo cuando se extraiga el boton/placeholder. |

## Regla de actualizacion

Cada vez que se extraiga un bloque nuevo de dashboard:

1. registrar aqui los iconos faltantes detectados en ese corte
2. incorporarlos al repo cuando corresponda
3. cerrar la entrada cuando el bloque quede integrado y validado en `main`
