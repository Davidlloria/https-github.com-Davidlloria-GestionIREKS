from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.request import Request, urlopen

from app.core.database import engine
from app.services.openai_settings_service import OpenAISettingsService


REPORT_COLUMNS: dict[str, tuple[str, str]] = {
    "codigo": ("Cod.", "c.cliente_codigo"),
    "nombre_comercial": ("Nombre comercial", "c.cliente_nombre_comercial"),
    "nombre_fiscal": ("Nombre fiscal", "c.cliente_nombre_fiscal"),
    "telefono": ("Telefono", "c.cliente_telefono"),
    "email": ("Email", "c.cliente_email"),
    "isla": ("Isla", "COALESCE(i.isla_nombre, '')"),
    "municipio": ("Municipio", "COALESCE(m.municipio_nombre, '')"),
    "localidad": ("Localidad", "COALESCE(l.localidad_nombre, '')"),
    "tipo": ("Tipo", "c.cliente_tipo"),
    "grupo": ("Grupo", "c.cliente_grupo"),
    "prospeccion": ("Prospeccion", "c.cliente_prospeccion"),
    "activo": ("Activo", "c.activo"),
    "nombre_contacto": (
        "Nombre contacto",
        """
        COALESCE((
            SELECT GROUP_CONCAT(TRIM(ct.nombre || ' ' || ct.apellidos), ', ')
            FROM contactos ct
            WHERE ct.cliente_id = c.cliente_id
              AND TRIM(ct.nombre || ' ' || ct.apellidos) <> ''
        ), '')
        """,
    ),
    "contactos": ("Contactos", "(SELECT COUNT(*) FROM contactos ct WHERE ct.cliente_id = c.cliente_id)"),
    "recetas": ("Recetas", "(SELECT COUNT(*) FROM recetas r WHERE r.cliente_id = c.cliente_id)"),
    "asistentes": ("Asistentes", "(SELECT COUNT(*) FROM asistentes a WHERE a.cliente_id = c.cliente_id)"),
}

DEFAULT_REPORT_COLUMNS = ["codigo", "nombre_comercial", "telefono", "isla", "tipo", "activo"]
COUNT_FIELDS = {"contactos", "recetas", "asistentes"}
TEXT_FIELDS = {
    "nombre_comercial",
    "nombre_fiscal",
    "telefono",
    "email",
    "isla",
    "municipio",
    "localidad",
    "tipo",
    "grupo",
    "nombre_contacto",
}
BOOL_FIELDS = {"activo", "prospeccion"}


@dataclass
class ReportFilter:
    field: str
    op: str
    value: Any


@dataclass
class CustomerReportIntent:
    title: str = "Listado de clientes"
    columns: list[str] = field(default_factory=lambda: list(DEFAULT_REPORT_COLUMNS))
    filters: list[ReportFilter] = field(default_factory=list)
    order_by: list[str] = field(default_factory=lambda: ["codigo"])
    limit: int = 500


@dataclass
class ReportIntentResult:
    ok: bool
    intent: CustomerReportIntent
    message: str
    used_ai: bool = False


@dataclass
class CustomerReportResult:
    title: str
    headers: list[str]
    rows: list[list[Any]]
    intent: CustomerReportIntent


class CustomerReportIntentService:
    BASE_URL = "https://api.openai.com/v1/responses"

    def __init__(self, api_key: str | None = None, model: str = "gpt-4.1-mini", timeout: float = 20.0) -> None:
        cfg = OpenAISettingsService().load()
        self.api_key = str(api_key or cfg.get("api_key") or "").strip()
        self.model = str(model or "gpt-4.1-mini").strip()
        self.timeout = timeout

    def parse(self, prompt: str) -> ReportIntentResult:
        text = str(prompt or "").strip()
        if not text:
            return ReportIntentResult(False, CustomerReportIntent(), "Escribe que listado necesitas.")
        fallback = self._fallback_parse(text)
        if not self.api_key:
            return ReportIntentResult(True, fallback, "Generado con interpretacion local. Falta API key de OpenAI.", False)

        payload: dict[str, Any] = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "Convierte peticiones en espanol sobre listados de clientes a JSON estricto. "
                        "No generes SQL. Usa solo estos campos: "
                        f"{', '.join(REPORT_COLUMNS)}. "
                        "Operadores permitidos: =, !=, contiene, empieza, >, >=, <, <=. "
                        "Devuelve solo este JSON: "
                        'Si piden nombre del contacto usa el campo "nombre_contacto"; si piden numero de contactos usa "contactos". '
                        '{"title": "...", "columns": ["codigo"], "filters": [{"field": "activo", "op": "=", "value": true}], '
                        '"order_by": ["codigo"], "limit": 500}.'
                    ),
                },
                {"role": "user", "content": text},
            ],
            "temperature": 0,
            "max_output_tokens": 500,
        }
        try:
            raw = json.dumps(payload).encode("utf-8")
            req = Request(self.BASE_URL, data=raw, method="POST")
            req.add_header("Authorization", f"Bearer {self.api_key}")
            req.add_header("Content-Type", "application/json")
            req.add_header("Accept", "application/json")
            with urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
                body = resp.read().decode("utf-8")
            data = json.loads(body or "{}")
            parsed = self._parse_json(self._extract_text(data))
            intent = self._intent_from_mapping(parsed, fallback)
            return ReportIntentResult(True, intent, "Generado con ChatGPT.", True)
        except Exception as exc:  # noqa: BLE001
            return ReportIntentResult(True, fallback, f"ChatGPT no disponible; usado interprete local. Detalle: {exc}", False)

    def _fallback_parse(self, text: str) -> CustomerReportIntent:
        t = self._normalize(text)
        intent = CustomerReportIntent(title=f"Listado: {text[:80]}")
        filters: list[ReportFilter] = []
        columns = list(DEFAULT_REPORT_COLUMNS)

        if "indirect" in t:
            filters.append(ReportFilter("tipo", "=", "indirecto"))
        elif "direct" in t:
            filters.append(ReportFilter("tipo", "=", "directo"))
        elif "distribuidor" in t:
            filters.append(ReportFilter("tipo", "=", "distribuidor"))

        if "inactivo" in t or "baja" in t:
            filters.append(ReportFilter("activo", "=", False))
        elif "activo" in t:
            filters.append(ReportFilter("activo", "=", True))

        if "prospe" in t:
            filters.append(ReportFilter("prospeccion", "=", not any(word in t for word in ("no prospe", "sin prospe"))))

        wants_contact_name = "nombre del contacto" in t or "nombres de contacto" in t or "contacto principal" in t
        if "sin contacto" in t:
            filters.append(ReportFilter("contactos", "=", 0))
            columns.append("contactos")
        elif wants_contact_name:
            columns.append("nombre_contacto")
        elif "contacto" in t:
            columns.append("contactos")

        if "sin receta" in t:
            filters.append(ReportFilter("recetas", "=", 0))
            columns.append("recetas")
        elif "receta" in t:
            columns.append("recetas")

        for island in ("tenerife", "gran canaria", "lanzarote", "fuerteventura", "la palma", "la gomera", "el hierro"):
            if island in t:
                filters.append(ReportFilter("isla", "contiene", island))
                if "isla" not in columns:
                    columns.append("isla")

        if "email" in t or "correo" in t:
            columns.append("email")
        if "municipio" in t:
            columns.append("municipio")
        if "localidad" in t:
            columns.append("localidad")
        if "fiscal" in t:
            columns.append("nombre_fiscal")
        if "grupo" in t or "sector" in t:
            columns.append("grupo")

        intent.filters = filters
        intent.columns = self._unique_valid(columns)
        return intent

    def _intent_from_mapping(self, data: dict[str, Any], fallback: CustomerReportIntent) -> CustomerReportIntent:
        intent = CustomerReportIntent()
        intent.title = str(data.get("title") or fallback.title or "Listado de clientes").strip()
        intent.columns = self._unique_valid(data.get("columns") or fallback.columns)
        if "contactos" in intent.columns and "nombre_contacto" in fallback.columns and "nombre_contacto" not in intent.columns:
            intent.columns[intent.columns.index("contactos")] = "nombre_contacto"
        if len(intent.columns) < 2:
            intent.columns = list(fallback.columns or DEFAULT_REPORT_COLUMNS)
        for required in ("codigo", "nombre_comercial"):
            if required not in intent.columns:
                intent.columns.insert(0 if required == "codigo" else min(1, len(intent.columns)), required)
        intent.order_by = self._unique_valid(data.get("order_by") or fallback.order_by)
        if not intent.order_by:
            intent.order_by = ["codigo"]
        try:
            intent.limit = max(1, min(5000, int(data.get("limit") or fallback.limit or 500)))
        except Exception:
            intent.limit = 500
        filters: list[ReportFilter] = []
        for item in data.get("filters") or []:
            if not isinstance(item, dict):
                continue
            field_name = str(item.get("field") or "").strip()
            op = str(item.get("op") or "=").strip().lower()
            if field_name in REPORT_COLUMNS:
                filters.append(ReportFilter(field_name, op, item.get("value")))
        intent.filters = filters or fallback.filters
        return intent

    def _unique_valid(self, values: Any) -> list[str]:
        out: list[str] = []
        for value in values or []:
            key = str(value or "").strip()
            if key in REPORT_COLUMNS and key not in out:
                out.append(key)
        return out

    def _extract_text(self, payload: dict[str, Any]) -> str:
        out = str(payload.get("output_text") or "").strip()
        if out:
            return out
        for item in payload.get("output") or []:
            for block in item.get("content") or []:
                txt = str(block.get("text") or "").strip()
                if txt:
                    return txt
        return ""

    def _parse_json(self, text: str) -> dict[str, Any]:
        raw = str(text or "").strip()
        try:
            return json.loads(raw)
        except Exception:
            start = raw.find("{")
            end = raw.rfind("}")
            if start >= 0 and end > start:
                return json.loads(raw[start : end + 1])
            raise

    def _normalize(self, value: str) -> str:
        text = str(value or "").lower()
        repl = str.maketrans("áéíóúüñ", "aeiouun")
        return text.translate(repl)


class CustomerReportService:
    def run(self, intent: CustomerReportIntent) -> CustomerReportResult:
        columns = [key for key in intent.columns if key in REPORT_COLUMNS] or list(DEFAULT_REPORT_COLUMNS)
        select_parts = [f"{REPORT_COLUMNS[key][1]} AS {key}" for key in columns]
        sql = [
            "SELECT",
            ", ".join(select_parts),
            "FROM clientes c",
            "LEFT JOIN islas i ON i.isla_id = c.cliente_direccion_isla_id",
            "LEFT JOIN municipios m ON m.municipio_id = c.cliente_direccion_municipio_id",
            "LEFT JOIN localidades l ON l.localidad_id = c.cliente_direccion_localidad_id",
        ]
        params: dict[str, Any] = {}
        where = self._build_where(intent.filters, params)
        if where:
            sql.append("WHERE " + " AND ".join(where))
        order = [REPORT_COLUMNS[key][1] for key in intent.order_by if key in REPORT_COLUMNS and key not in COUNT_FIELDS]
        sql.append("ORDER BY " + ", ".join(order or ["c.cliente_codigo"]))
        params["limit"] = max(1, min(5000, int(intent.limit or 500)))
        sql.append("LIMIT :limit")

        with engine.begin() as conn:
            rows = conn.exec_driver_sql("\n".join(sql), params).fetchall()

        headers = [REPORT_COLUMNS[key][0] for key in columns]
        data_rows = [[self._format_value(columns[idx], value) for idx, value in enumerate(row)] for row in rows]
        return CustomerReportResult(intent.title or "Listado de clientes", headers, data_rows, intent)

    def _build_where(self, filters: list[ReportFilter], params: dict[str, Any]) -> list[str]:
        where: list[str] = []
        for idx, flt in enumerate(filters):
            field_name = str(flt.field or "").strip()
            if field_name not in REPORT_COLUMNS:
                continue
            expr = REPORT_COLUMNS[field_name][1]
            op = str(flt.op or "=").strip().lower()
            param = f"p{idx}"
            if field_name in BOOL_FIELDS:
                params[param] = 1 if self._to_bool(flt.value) else 0
                where.append(f"{expr} = :{param}")
            elif field_name in COUNT_FIELDS:
                sql_op = op if op in {"=", "!=", ">", ">=", "<", "<="} else "="
                params[param] = int(self._to_number(flt.value))
                where.append(f"{expr} {sql_op} :{param}")
            elif op == "contiene":
                params[param] = f"%{str(flt.value or '').strip()}%"
                where.append(f"{expr} LIKE :{param}")
            elif op == "empieza":
                params[param] = f"{str(flt.value or '').strip()}%"
                where.append(f"{expr} LIKE :{param}")
            elif op in {"=", "!="}:
                params[param] = str(flt.value or "").strip()
                where.append(f"LOWER({expr}) {op} LOWER(:{param})")
        return where

    def _to_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        text = str(value or "").strip().lower()
        return text in {"1", "true", "si", "sí", "yes", "activo", "prospecto", "prospeccion"}

    def _to_number(self, value: Any) -> float:
        try:
            return float(str(value or "0").replace(",", "."))
        except Exception:
            return 0

    def _format_value(self, field_name: str, value: Any) -> Any:
        if field_name in BOOL_FIELDS:
            return "Si" if bool(value) else "No"
        return "" if value is None else value
