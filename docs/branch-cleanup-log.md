# Branch cleanup log

Fecha de inicio del registro: 2026-07-27
Rama base de trabajo: `main`
Rama origen a vaciar por extracciones: `feature/pedidos-window-tweaks`

## Objetivo

Vaciar `feature/pedidos-window-tweaks` mediante cortes minimos y verificables.

Flujo acordado:

1. partir de `main` limpia
2. crear una rama temporal especifica del bloque
3. extraer solo ese bloque desde `feature/pedidos-window-tweaks`
4. validar el corte de forma aislada
5. hacer commit del corte
6. mergear en `main`
7. borrar la rama temporal
8. repetir con el siguiente bloque

## Extracciones ya integradas en `main`

| Fecha | Rama temporal | Resultado en `main` | Estado |
|---|---|---|---|
| 2026-07-27 | `feature/dashboard-orders-clean` | `9d23ce8d0` mergeado | Cerrado |
| 2026-07-27 | `feature/dashboard-warehouse-clean` | `eb24a431d` mergeado | Cerrado |
| 2026-07-27 | `feature/pedidos-pendientes-clean` | `d3cb90705` mergeado | Cerrado |
| 2026-07-27 | ajuste directo en `main` | `c0de65be9` nombres de almacen en pedidos | Cerrado |
| 2026-07-27 | ajuste directo en `main` | `6c18cf3b6` priorizacion de distribuidores en filtros | Cerrado |
| 2026-07-27 | ajuste directo en `main` | `8a4fa542d` deduplicacion de variantes tipo CADELSA/IGSA | Cerrado |

## Estado actual de ramas locales

| Rama | Estado |
|---|---|
| `main` | activa, limpia |
| `feature/pedidos-window-tweaks` | pendiente de vaciado por extracciones |

## Bloques pendientes detectados en `feature/pedidos-window-tweaks`

Orden recomendado de extraccion restante:

1. `dashboard ventas`
2. `dashboard objetivos` (boton y placeholder)
3. revisar si queda algun ajuste comun de `dashboard_page.py`
4. despues, bloques no dashboard: pedidos, almacen, clientes, ventas AI

## Estado del siguiente corte: `dashboard ventas`

Situacion verificada el 2026-07-27:

- commit base detectado: `5e37ed9cf` (`feat: add sales dashboard view`)
- no es seguro cherry-pick directo
- el bloque esta mezclado con otros cambios del mismo `dashboard_page.py`
- la extraccion correcta debe ser manual sobre una rama nueva, partiendo de `main`

Archivos minimos previstos para el corte:

- `app/services/sales_dashboard_service.py`
- `app/ui/widgets/dashboard_page.py`
- `tests/test_dashboard_page_ui.py`
- iconos estrictamente usados por la vista de ventas

## Criterio operativo

No mergear `feature/pedidos-window-tweaks` completa.

Solo se considera cerrada cuando:

- no queden bloques utiles sin extraer
- `main` tenga integrados los cortes aprobados
- la rama temporal ya no aporte codigo necesario
- pueda borrarse sin perdida de trabajo
