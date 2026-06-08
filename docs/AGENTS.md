# AGENTS.md

## Objetivo del proyecto

Modernizar una aplicación desktop Python PySide6/Qt sin romper funcionalidad existente.

Objetivo final:

* mantener la lógica Python existente
* consolidar FastAPI como capa de servicios
* consolidar React como interfaz principal de operación
* mantener PySide6 operativo durante la transición
* reducir progresivamente la dependencia de widgets desktop grandes
* evitar regresiones funcionales durante la migración

Esta aplicación es de uso personal/comercial. No es una aplicación safety-critical. Priorizar avance práctico, estabilidad razonable y reducción de deuda real sobre análisis extensos.

---

## Estado actual

La migración ya dispone de:

* FastAPI operativa
* Frontend React/Vite operativo
* Tests automatizados
* Gates de validación
* Contratos API
* Guardrails de arquitectura
* Varios flujos legacy extraídos desde widgets hacia servicios
* `migration-roadmap.md` y `docs/migration-history.md` como contexto cuando aporten decisiones activas

La fase actual NO consiste en crear una arquitectura nueva.

La fase actual consiste en:

* reducir deuda técnica residual con retorno claro
* evitar sobreingeniería
* consolidar React/FastAPI
* mantener PySide6 estable mientras siga existiendo
* preparar el sistema para mantenimiento a largo plazo

---

## Reglas obligatorias

1. No reescribir la aplicación desde cero.
2. No añadir funcionalidad nueva salvo instrucción explícita.
3. No crear endpoints FastAPI nuevos salvo instrucción explícita.
4. No crear pantallas React nuevas salvo instrucción explícita.
5. No cambiar comportamiento funcional sin crear o actualizar tests.
6. No introducir lógica de negocio nueva dentro de widgets PySide6.
7. No usar `Session(engine)` directamente desde archivos UI nuevos o modificados.
8. No importar desde `app/ui`:
   * `sqlmodel`
   * `Session`
   * `select`
   * `engine`
   * `app.core.database`
9. No importar `PySide6` desde `app/services`.
10. No importar `app.ui` desde `app/api`.
11. No incluir nunca en commits:
   * `.env`
   * bases de datos
   * backups
   * exports
   * runtime
   * datos reales
   * credenciales
12. No cambiar contratos API, formato de salida ni comportamiento visible salvo instrucción explícita.
13. Mantener siempre los guardrails arquitectónicos existentes.
14. Antes de tocar un bloque, leer el contexto relevante y declarar qué se va a validar.
15. Usar tests concretos del bloque tocado y, cuando aplique, ejecutar `tests/test_architecture_boundaries.py` si se tocan límites UI/services/API.
16. Evitar refactors amplios sin retorno claro y no degradar la separación UI/services/API.

---

## Modo de trabajo por defecto

El modo por defecto es ejecución pragmática, no consultoría extensa.

Cuando se pida mejorar, refactorizar o limpiar un bloque:

1. Inspeccionar el código.
2. Revisar contexto/histórico relevante.
3. Declarar qué se va a validar.
4. Implementar si el retorno es claro.
5. Añadir tests mínimos relevantes.
6. Ejecutar tests concretos del bloque y gates aplicables.
7. Ejecutar solo los tests/lint/build relacionados.
8. Crear commit si todo pasa.
9. Dejar el worktree limpio.
10. Mantener el alcance pequeño y los cambios revisables.

No generar informes largos salvo petición explícita.
No generar rankings, matrices o análisis P1/P2 salvo petición explícita.
No abrir debates arquitectónicos si el cambio es pequeño, claro y seguro.

---

## Criterio para refactor

Hacer refactor solo si cumple al menos una condición:

* elimina lógica real de negocio u orquestación
* mejora claramente la testabilidad
* reduce riesgo operativo
* simplifica un bloque sustancial
* desbloquea migración hacia servicios/API/React
* reduce dependencia local desktop relevante
* mantiene o mejora claramente la separación UI/services/API

No hacer refactor si:

* solo mueve 10-20 líneas
* solo mueve wrappers de Qt
* solo cambia nombres o estética interna
* crea una capa artificial
* el bloque ya es UI pura
* el beneficio es marginal
* no reduce deuda P1/P2 ni desbloquea migración

Regla práctica:

* No crear un servicio/helper/capa nueva si la extracción no elimina al menos unas 50 líneas de complejidad real o no mejora claramente la testabilidad.

Gates típicos:

* `python -m pytest tests -q` cuando el bloque sea amplio
* `tests/test_architecture_boundaries.py` cuando se toquen límites entre UI, services o API

---

## Dirección arquitectónica

La dirección objetivo es:

```text
React
↓
FastAPI
↓
Services
↓
Repositories
↓
SQLModel
↓
SQLite / PostgreSQL
```
