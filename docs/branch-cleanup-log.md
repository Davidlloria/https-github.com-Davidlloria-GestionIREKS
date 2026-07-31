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
| 2026-07-27 | `feature/dashboard-sales-clean` | `86a18b183` mergeado | Cerrado |
| 2026-07-27 | `feature/dashboard-goals-clean` | `94be53470` mergeado | Cerrado |
| 2026-07-27 | `feature/dashboard-agenda-actions-clean` | `bf1765de3` mergeado | Cerrado |
| 2026-07-31 | `feature/warehouse-filters-clean` | `11264a8e8` mergeado | Cerrado |
| 2026-07-31 | `feature/dashboard-agenda-calendar-refine-clean` | `42fd8a35e` mergeado | Cerrado |
| 2026-07-31 | `feature/customer-recipes-ownership-clean` | `c9031af42` mergeado | Cerrado |
| 2026-07-31 | `feature/customer-agenda-service-test-clean` | `f91557a67` mergeado | Cerrado |
| 2026-07-31 | `feature/customer-queries-clean` | `3b23acb8f` mergeado | Cerrado |
| 2026-07-31 | `feature/orders-pending-received-clean` | `b3dbcb0f4` mergeado | Cerrado |
| 2026-07-31 | `feature/customer-related-sales-clean` | `f04931683` mergeado | Cerrado |
| 2026-07-31 | `feature/customer-sales-pdf-clean` | `9736ff40d` mergeado | Cerrado |
| 2026-07-31 | `feature/customer-sales-chart-clean` | `8146a33ef` mergeado | Cerrado |
| 2026-07-31 | `feature/sales-ai-core-clean` | `b080c6d53` mergeado | Cerrado |
| 2026-07-31 | `feature/warehouse-repair-core-clean` | `7a7c2fe13` mergeado | Cerrado |
| 2026-07-31 | `feature/sales-reconciliation-warehouse-clean` | `8142e81be` mergeado | Cerrado |
| 2026-07-31 | `feature/ingredients-warehouse-ui-clean` | `cfdbb73ee` mergeado | Cerrado |
| 2026-07-31 | `feature/sales-analysis-dialog-clean` | `bc1464419` mergeado | Cerrado |
| 2026-07-31 | `feature/customer-agenda-ui-clean` | `53a7abfc4` mergeado | Cerrado |
| 2026-07-31 | `feature/orders-receipts-pending-clean` | `1c8c3b447` mergeado | Cerrado |

## Estado actual de ramas locales

| Rama | Estado |
|---|---|
| `main` | activa |
| `feature/pedidos-window-tweaks` | pendiente de vaciado por extracciones |

## Bloques pendientes detectados en `feature/pedidos-window-tweaks`

## Corte en analisis: `sales AI`

Situacion verificada el 2026-07-31:

- no existe endpoint FastAPI propio para `sales AI` en `feature/pedidos-window-tweaks`
- el bloque esta montado sobre PySide6 legacy en `app/ui/widgets/sales_page.py`
- el nucleo funcional nuevo esta en `app/services/sales_ai_assistant_service.py` y `app/services/sales_text_normalizer.py`
- el test especifico pendiente esta en `tests/test_sales_ai_assistant_service.py`
- el servicio depende de `OpenAIProcessService`, `OpenAISettingsService` y `SalesAnnualComparisonService`
- el diff de `sales_page.py` es demasiado grande para extraerlo completo como siguiente corte minimo
- siguiente corte recomendado: extraer primero servicio + normalizador + test, sin integrar todavia la UI legacy de ventas

Orden recomendado de extraccion restante:

1. revisar si queda algun ajuste comun de `dashboard_page.py`
2. despues, bloques no dashboard: pedidos, clientes y ventas AI

## Estado del siguiente corte: salida de la zona dashboard

Situacion verificada el 2026-07-27:

- `dashboard ventas` ya fue extraido, validado y mergeado en `main`
- `dashboard objetivos` ya fue extraido, validado y mergeado en `main`
- `dashboard agenda` ya tiene operativas las acciones `Nueva actividad` y `Ver agenda completa`
- a partir de aqui, el siguiente frente recomendado ya no es otro corte de dashboard, sino bloques no dashboard: pedidos, clientes y ventas AI

## Criterio operativo

No mergear `feature/pedidos-window-tweaks` completa.

Solo se considera cerrada cuando:

- no queden bloques utiles sin extraer
- `main` tenga integrados los cortes aprobados
- la rama temporal ya no aporte codigo necesario
- pueda borrarse sin perdida de trabajo
