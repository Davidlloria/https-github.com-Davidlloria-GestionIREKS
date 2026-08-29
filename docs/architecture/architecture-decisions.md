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

## ADR-005: Biblioteca documental local derivada

Decisión:
La biblioteca de origen es externa y de solo lectura. Un índice derivado y
separado guarda metadatos, contenido FTS5 y embeddings reconstruibles. Los
servicios Python de catálogo, contenido, semántica, recuperación híbrida y
preguntas son compartidos; PySide6 los consume sin acceder directamente a
SQLite. La IA documental usa Ollama local y las respuestas requieren fuentes
documentales válidas.

Consecuencias:

- Los documentos originales quedan fuera de Git y de SQLite.
- Los índices pueden eliminarse y reconstruirse sin alterar los originales.
- Sin biblioteca documental, el resto de GestionIREKS continúa operativo.
- Cambiar el modelo de embeddings requiere reindexación semántica.
- OCR queda fuera del MVP documental.
