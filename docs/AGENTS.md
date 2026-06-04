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

---

## Estado actual

La migración ya dispone de:

* FastAPI operativa
* Frontend React/Vite operativo
* Tests automatizados
* Gates de validación
* Contratos API
* Guardrails de arquitectura

La fase actual NO consiste en crear una arquitectura nueva.

La fase actual consiste en:

* reducir deuda técnica residual
* extraer lógica restante de widgets PySide6
* consolidar React/FastAPI
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

8. No importar:

   * `sqlmodel`
   * `Session`
   * `select`
   * `engine`
   * `app.core.database`

   desde `app/ui`.

9. No importar `PySide6` desde `app/services`.

10. No importar `app.ui` desde `app/api`.

11. No realizar micro-refactors de bajo retorno que no reduzcan deuda P1/P2 ni desbloqueen migración.

12. Mantener siempre los guardrails arquitectónicos existentes.

---

## Dirección arquitectónica

La dirección objetivo es:

UI React
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

Mientras exista desktop:

PySide6
↓
ViewModels / Controllers
↓
Services
↓
Repositories
↓
SQLModel

---

## Prioridad actual

Fase 5 – Reducir dependencia del desktop.

Prioridades:

1. Mantener PySide6 estable.
2. Consolidar React/FastAPI como superficie principal.
3. Extraer lógica residual desde widgets grandes.
4. Reducir dependencias desktop locales.
5. Mantener documentación y trazabilidad.

Orden de prioridad de deuda:

### P1

* orders_page.py
* settings_page.py
* ingredients_page.py

### P2

* warehouse_page.py
* customers_page.py
* courses_page.py

### P3

* limpieza de helpers legacy
* consolidación documental
* simplificación de scripts

---

## Qué NO hacer ahora

* No iniciar migraciones tecnológicas nuevas.
* No introducir nuevos frameworks.
* No rehacer módulos completos.
* No modificar contratos API estables.
* No tocar React o FastAPI salvo que el bloque actual lo requiera.
* No optimizar código únicamente por estética.

---

## Antes de modificar código

Codex debe:

1. Leer:

   * AGENTS.md
   * migration-roadmap.md
   * docs/migration-history.md

2. Resumir:

   * fase actual
   * deuda relevante
   * objetivo del bloque

3. Explicar:

   * qué archivos piensa modificar
   * riesgo esperado
   * validación prevista

4. Realizar cambios pequeños, revisables y aislados.

---

## Después de modificar código

Codex debe:

1. Ejecutar los tests relacionados.

2. Ejecutar guardrails de arquitectura cuando proceda.

3. Actualizar:

   * migration-roadmap.md
   * docs/migration-history.md

4. Listar:

   * archivos modificados
   * comportamiento preservado
   * riesgos detectados

5. Proponer validación manual.

6. Indicar claramente el siguiente bloque recomendado.

---

## Gates mínimos

Antes de considerar terminado un bloque:

### Python

python -m pytest tests -q

### Arquitectura

tests/test_architecture_boundaries.py

### Base de datos

python -c "from app.core.database import run_integrity_check; print(run_integrity_check())"

### Frontend

npm run lint

npm run build

### Gate completo

powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-gates.ps1

---

## Criterio de éxito

El éxito de la migración NO es eliminar PySide6.

El éxito es que:

* React sea la interfaz principal.
* FastAPI sea la capa principal de acceso.
* La lógica viva en servicios.
* Los widgets desktop no contengan reglas de negocio críticas.
* Los tests y gates permanezcan verdes.
* Las nuevas funcionalidades se implementen sobre servicios/API y no sobre widgets legacy.
