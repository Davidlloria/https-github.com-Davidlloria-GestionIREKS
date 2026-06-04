# Architecture Decisions

## ADR-001: Mantener PySide6 durante la migración

Decisión:
La app PySide6 seguirá funcionando mientras se extrae lógica.

Motivo:
Reducir riesgo y evitar reescritura total.

## ADR-002: Services como capa de negocio

Decisión:
La lógica de negocio debe vivir en `app/services`.

No debe vivir en:
- widgets Qt
- dialogs Qt
- código React futuro
- endpoints FastAPI futuros

## ADR-003: FastAPI vendrá después

Decisión:
FastAPI no se introduce hasta que la lógica crítica esté separada.

Motivo:
Evitar crear una API sobre código todavía acoplado a UI.

## ADR-004: React vendrá después de FastAPI

Decisión:
React no debe construirse antes de tener contratos claros de datos.