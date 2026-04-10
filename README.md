# Gestion Formulas

Aplicacion de escritorio para gestion de clientes, ingredientes y recetas de panaderia/pasteleria.

## Stack

- Python
- PySide6
- SQLite
- SQLModel

## Estructura

- `app/core`: configuracion y base de datos
- `app/models`: modelos SQLModel
- `app/repositories`: acceso a datos
- `app/services`: logica de negocio y servicios de exportacion
- `app/viewmodels`: capa intermedia para UI
- `app/ui`: interfaz de escritorio
- `app/reports`: generacion de informes
- `data`: base de datos SQLite
- `assets`: recursos visuales
- `tests`: pruebas

## Ejecucion

```bash
pip install -r requirements.txt
python run.py
```

## Roadmap

- Fase 1: estructura, DB, modelos, CRUD clientes e ingredientes
- Fase 2: editor de recetas y motor tecnico
- Fase 3: escandallos, costes, PDF e impresion
- Fase 4: versionado, subrecetas, duplicado, importacion Excel/CSV

