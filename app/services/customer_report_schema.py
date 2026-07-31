from __future__ import annotations

REPORT_COLUMNS = (
    'codigo', 'nombre_comercial', 'nombre_fiscal', 'telefono', 'email', 'isla',
    'municipio', 'localidad', 'tipo', 'actividad', 'grupo', 'prospeccion', 'activo',
    'nombre_contacto', 'contactos', 'recetas', 'asistentes',
)


CUSTOMER_REPORT_RESPONSE_FORMAT = {
    "type": "json_schema",
    "name": "customer_report_intent",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "columns": {
                "type": "array",
                "items": {"type": "string", "enum": sorted(REPORT_COLUMNS)},
            },
            "filters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "field": {"type": "string", "enum": sorted(REPORT_COLUMNS)},
                        "op": {
                            "type": "string",
                            "enum": ["=", "!=", "contiene", "empieza", ">", ">=", "<", "<="],
                        },
                        "value": {
                            "anyOf": [
                                {"type": "string"},
                                {"type": "number"},
                                {"type": "boolean"},
                            ]
                        },
                    },
                    "required": ["field", "op", "value"],
                    "additionalProperties": False,
                },
            },
            "order_by": {
                "type": "array",
                "items": {"type": "string", "enum": sorted(REPORT_COLUMNS)},
            },
            "limit": {"type": "integer"},
        },
        "required": ["title", "columns", "filters", "order_by", "limit"],
        "additionalProperties": False,
    },
}
