from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.request import Request, urlopen

from app.core.database import engine
from app.services.openai_settings_service import OpenAISettingsService


PRICE_YEAR_EXPR = """
COALESCE((
    SELECT t.tarifa_ano
    FROM tarifa_precios_ireks t
    WHERE t.articulo_id = p.articulo_id
    ORDER BY t.tarifa_ano DESC
    LIMIT 1
), 0)
"""
PRICE_FAB_EXPR = """
COALESCE((
    SELECT t.precio_fabricante
    FROM tarifa_precios_ireks t
    WHERE t.articulo_id = p.articulo_id
    ORDER BY t.tarifa_ano DESC
    LIMIT 1
), 0)
"""
PRICE_DIST_EXPR = """
COALESCE((
    SELECT t.precio_distribuidor
    FROM tarifa_precios_ireks t
    WHERE t.articulo_id = p.articulo_id
    ORDER BY t.tarifa_ano DESC
    LIMIT 1
), 0)
"""
PRICE_DISCOUNT_EXPR = """
COALESCE((
    SELECT t.descuento_pct
    FROM tarifa_precios_ireks t
    WHERE t.articulo_id = p.articulo_id
    ORDER BY t.tarifa_ano DESC
    LIMIT 1
), 0)
"""


PRODUCT_REPORT_COLUMNS: dict[str, tuple[str, str]] = {
    "articulo": (
        "Articulo",
        "COALESCE(p.articulo_referencia, '') || ' ' || COALESCE(p.articulo_referencia_corta, '') || ' ' || COALESCE(p.articulo_descripcion, '')",
    ),
    "referencia": ("Ref.", "p.articulo_referencia"),
    "referencia_corta": ("Ref. corta", "p.articulo_referencia_corta"),
    "descripcion": ("Descripcion", "p.articulo_descripcion"),
    "fabricante": ("Fabricante", "COALESCE(f.fabricante_nombre, p.fabricante_id, '')"),
    "familia": ("Familia", "COALESCE(fa.articulo_familia_nombre, p.articulo_familia_id, '')"),
    "subfamilia": ("Subfamilia", "COALESCE(sf.articulo_subfamilia_nombre, p.articulo_subfamilia_id, '')"),
    "distribuidor": ("Distribuidor", "COALESCE(d.distribuidor_nombre_comercial, d.distribuidor_razon_social, '')"),
    "presentacion": ("Presentacion", "COALESCE(e.envase_nombre, p.articulo_envase_id, '')"),
    "contenido": ("Contenido", "p.articulo_envase_cantidad"),
    "unidad_contenido": ("Unidad contenido", "p.articulo_contenido_unidad"),
    "peso_unidad": ("Peso unidad", "p.articulo_envase_peso"),
    "unidad_peso": ("Unidad peso", "p.articulo_envase_unidad_medida"),
    "total_presentacion": ("Total presentacion", "p.articulo_envase_peso_total"),
    "pallet": ("Pallet", "p.transporte_pallet_tipo"),
    "presentaciones_capa": ("Presentaciones/capa", "p.transporte_cajas_por_capa"),
    "capas": ("Capas", "p.transporte_capas_por_pallet"),
    "presentaciones_pallet": ("Presentaciones/pallet", "p.transporte_cajas_por_pallet"),
    "unidades_pallet": ("Unidades/pallet", "p.transporte_unidades_por_pallet"),
    "total_pallet": ("Total pallet", "p.transporte_kg_por_pallet"),
    "observaciones_transporte": ("Obs. transporte", "p.transporte_observaciones"),
    "categoria": ("Categoria", "p.categoria"),
    "activo": ("Activo", "p.articulo_status_activo"),
    "en_lista": ("En lista", "p.articulo_status_en_lista"),
    "tarifa_ano": ("Ano tarifa", PRICE_YEAR_EXPR),
    "precio_fabricante": ("Precio fabricante", PRICE_FAB_EXPR),
    "precio_distribuidor": ("Precio distribuidor", PRICE_DIST_EXPR),
    "descuento": ("Descuento %", PRICE_DISCOUNT_EXPR),
}

DEFAULT_PRODUCT_REPORT_COLUMNS = ["referencia_corta", "descripcion", "familia", "subfamilia", "total_presentacion", "activo"]
HIDDEN_REPORT_COLUMNS = {"articulo"}
PRODUCT_REPORT_COLUMN_BLOCKS: dict[str, list[str]] = {
    "formato_venta": [
        "presentacion",
        "contenido",
        "unidad_contenido",
        "peso_unidad",
        "unidad_peso",
        "total_presentacion",
        "pallet",
        "presentaciones_capa",
        "capas",
        "presentaciones_pallet",
        "unidades_pallet",
        "total_pallet",
        "observaciones_transporte",
    ],
    "logistica": [
        "pallet",
        "presentaciones_capa",
        "capas",
        "presentaciones_pallet",
        "unidades_pallet",
        "total_pallet",
        "observaciones_transporte",
    ],
    "tarifa": [
        "tarifa_ano",
        "precio_fabricante",
        "precio_distribuidor",
        "descuento",
    ],
}
TEXT_FIELDS = {
    "referencia",
    "referencia_corta",
    "articulo",
    "descripcion",
    "fabricante",
    "familia",
    "subfamilia",
    "distribuidor",
    "presentacion",
    "unidad_contenido",
    "unidad_peso",
    "pallet",
    "observaciones_transporte",
    "categoria",
}
BOOL_FIELDS = {"activo", "en_lista"}
NUMERIC_FIELDS = {
    "contenido",
    "peso_unidad",
    "total_presentacion",
    "presentaciones_capa",
    "capas",
    "presentaciones_pallet",
    "unidades_pallet",
    "total_pallet",
    "tarifa_ano",
    "precio_fabricante",
    "precio_distribuidor",
    "descuento",
}


@dataclass
class ProductReportFilter:
    field: str
    op: str
    value: Any


@dataclass
class ProductReportIntent:
    title: str = "Listado de productos IREKS"
    columns: list[str] = field(default_factory=lambda: list(DEFAULT_PRODUCT_REPORT_COLUMNS))
    filters: list[ProductReportFilter] = field(default_factory=list)
    order_by: list[str] = field(default_factory=lambda: ["referencia_corta"])
    limit: int = 500
    selected_ids: list[int] = field(default_factory=list)


@dataclass
class ProductReportIntentResult:
    ok: bool
    intent: ProductReportIntent
    message: str
    used_ai: bool = False


@dataclass
class ProductReportResult:
    title: str
    headers: list[str]
    rows: list[list[Any]]
    intent: ProductReportIntent


class ProductReportIntentService:
    BASE_URL = "https://api.openai.com/v1/responses"

    def __init__(self, api_key: str | None = None, model: str = "gpt-4.1-mini", timeout: float = 20.0) -> None:
        cfg = OpenAISettingsService().load()
        self.api_key = str(api_key or cfg.get("api_key") or "").strip()
        self.model = str(model or "gpt-4.1-mini").strip()
        self.timeout = timeout

    def parse(self, prompt: str) -> ProductReportIntentResult:
        text = str(prompt or "").strip()
        if not text:
            return ProductReportIntentResult(False, ProductReportIntent(), "Escribe que listado necesitas.")
        fallback = self._fallback_parse(text)
        if not self.api_key:
            return ProductReportIntentResult(True, fallback, "Generado con interpretacion local. Falta API key de OpenAI.", False)

        payload: dict[str, Any] = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "Convierte peticiones en espanol sobre listados de productos IREKS a JSON estricto. "
                        "No generes SQL. Usa solo estos campos: "
                        f"{', '.join(PRODUCT_REPORT_COLUMNS)}. "
                        "Operadores permitidos: =, !=, contiene, empieza, >, >=, <, <=. "
                        "Alias de columnas: si piden formato de venta incluye presentacion, contenido, unidad_contenido, "
                        "peso_unidad, unidad_peso, total_presentacion, pallet, presentaciones_capa, capas, "
                        "presentaciones_pallet, unidades_pallet, total_pallet y observaciones_transporte. "
                        "Si piden logistica incluye solo los campos de pallet/transporte. "
                        "Si piden tarifa incluye tarifa_ano, precio_fabricante, precio_distribuidor y descuento. "
                        "Campos utiles: presentacion es envase; contenido es unidades dentro de la presentacion; "
                        "unidad_contenido puede ser BOLSA, BOTELLA, SACO; total_presentacion es kg por presentacion; "
                        "total_pallet es kg por pallet. Si piden articulos por descripcion usa descripcion; "
                        "si piden articulos por referencia usa referencia o referencia_corta; "
                        "si piden una busqueda general por texto usa articulo con operador contiene. Devuelve solo este JSON: "
                        '{"title": "...", "columns": ["referencia_corta"], "filters": [{"field": "activo", "op": "=", "value": true}], '
                        '"order_by": ["referencia_corta"], "limit": 500}.'
                    ),
                },
                {"role": "user", "content": text},
            ],
            "temperature": 0,
            "max_output_tokens": 600,
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
            return ProductReportIntentResult(True, intent, "Generado con ChatGPT.", True)
        except Exception as exc:  # noqa: BLE001
            return ProductReportIntentResult(True, fallback, f"ChatGPT no disponible; usado interprete local. Detalle: {exc}", False)

    def _fallback_parse(self, text: str) -> ProductReportIntent:
        t = self._normalize(text)
        filter_text = self._filter_text(t)
        intent = ProductReportIntent(title=f"Listado: {text[:80]}")
        filters: list[ProductReportFilter] = []
        columns = list(DEFAULT_PRODUCT_REPORT_COLUMNS)

        if "inactivo" in filter_text or "baja" in filter_text:
            filters.append(ProductReportFilter("activo", "=", False))
        elif "activo" in filter_text:
            filters.append(ProductReportFilter("activo", "=", True))
        if "en lista" in filter_text:
            filters.append(ProductReportFilter("en_lista", "=", not any(word in filter_text for word in ("no en lista", "sin lista"))))
        if "harina" in filter_text:
            filters.append(ProductReportFilter("categoria", "=", "harina"))
        if "liquido" in filter_text:
            filters.append(ProductReportFilter("categoria", "=", "liquido"))

        format_requested = "formato de venta" in t or "unidad de venta" in t or "unidades de venta" in t
        if format_requested:
            columns = ["referencia_corta", "descripcion"]
            self._add_column_block(columns, "formato_venta")
        if "logistica" in t or "logistico" in t or "transporte" in t:
            self._add_column_block(columns, "logistica")
        if "tarifa" in t or "precios" in t or "precio" in t:
            self._add_column_block(columns, "tarifa")

        for key, words in {
            "referencia": ("referencia", "ref "),
            "referencia_corta": ("ref corta", "referencia corta"),
            "descripcion": ("descripcion", "descripcion articulo", "nombre"),
            "fabricante": ("fabricante", "marca"),
            "familia": ("familia",),
            "subfamilia": ("subfamilia",),
            "distribuidor": ("distribuidor", "proveedor"),
            "presentacion": ("presentacion", "envase"),
            "contenido": ("contenido", "cantidad"),
            "unidad_contenido": ("unidad contenido", "bolsa", "botella", "saco"),
            "peso_unidad": ("peso unidad",),
            "total_presentacion": ("total presentacion", "kg por presentacion", "kg/envase"),
            "pallet": ("pallet",),
            "presentaciones_capa": ("capa",),
            "presentaciones_pallet": ("presentaciones/pallet", "envases/pallet"),
            "unidades_pallet": ("unidades/pallet", "uds/pallet"),
            "total_pallet": ("total pallet", "kg/pallet"),
            "tarifa_ano": ("ano tarifa", "año tarifa", "tarifa"),
            "precio_fabricante": ("precio fabricante", "precio ireks"),
            "precio_distribuidor": ("precio distribuidor",),
            "descuento": ("descuento",),
        }.items():
            if any(word in t for word in words) and key not in columns:
                columns.append(key)

        for field_name in ("familia", "subfamilia", "fabricante", "presentacion", "unidad_contenido"):
            value = self._value_after(filter_text, field_name)
            if value:
                filters.append(ProductReportFilter(field_name, "contiene", value))
        referencia = self._value_after_any(filter_text, ("referencia corta", "ref corta", "referencia", "ref"))
        if referencia:
            filters.append(ProductReportFilter("referencia", "contiene", referencia))
        descripcion = self._value_after_any(filter_text, ("descripcion", "nombre"))
        if descripcion:
            filters.append(ProductReportFilter("descripcion", "contiene", descripcion))
        articulo = self._search_value(filter_text)
        if articulo and not referencia and not descripcion:
            filters.append(ProductReportFilter("articulo", "contiene", articulo))

        if "ordenado por familia" in t and "familia" in PRODUCT_REPORT_COLUMNS:
            intent.order_by = ["familia", "subfamilia", "descripcion"]
        elif "ordenado por subfamilia" in t:
            intent.order_by = ["subfamilia", "descripcion"]
        elif "ordenado por pallet" in t:
            intent.order_by = ["total_pallet"]
        elif "ordenado por tarifa" in t or "ordenado por precio" in t:
            intent.order_by = ["precio_fabricante"]

        intent.filters = filters
        intent.columns = self._unique_valid(columns)
        return intent

    def _add_column_block(self, columns: list[str], block_name: str) -> None:
        for key in PRODUCT_REPORT_COLUMN_BLOCKS.get(block_name, []):
            if key not in columns:
                columns.append(key)

    def _intent_from_mapping(self, data: dict[str, Any], fallback: ProductReportIntent) -> ProductReportIntent:
        intent = ProductReportIntent()
        intent.title = str(data.get("title") or fallback.title or "Listado de productos IREKS").strip()
        if self._is_format_sales_columns(fallback.columns):
            intent.columns = list(fallback.columns)
        else:
            intent.columns = self._unique_visible(data.get("columns") or fallback.columns)
        if len(intent.columns) < 2:
            intent.columns = list(fallback.columns or DEFAULT_PRODUCT_REPORT_COLUMNS)
        intent.columns = self._unique_visible(intent.columns)
        for required in ("referencia_corta", "descripcion"):
            if required not in intent.columns:
                intent.columns.insert(0 if required == "referencia_corta" else min(1, len(intent.columns)), required)
        intent.order_by = self._unique_valid(data.get("order_by") or fallback.order_by)
        if not intent.order_by:
            intent.order_by = ["referencia_corta"]
        try:
            intent.limit = max(1, min(5000, int(data.get("limit") or fallback.limit or 500)))
        except Exception:
            intent.limit = 500
        filters: list[ProductReportFilter] = []
        for item in data.get("filters") or []:
            if not isinstance(item, dict):
                continue
            field_name = str(item.get("field") or "").strip()
            op = str(item.get("op") or "=").strip().lower()
            if field_name in PRODUCT_REPORT_COLUMNS:
                filters.append(ProductReportFilter(field_name, op, item.get("value")))
        intent.filters = filters or fallback.filters
        return intent

    def _is_format_sales_columns(self, columns: list[str]) -> bool:
        visible = set(columns or [])
        return set(PRODUCT_REPORT_COLUMN_BLOCKS["formato_venta"]).issubset(visible)

    def _unique_visible(self, values: Any) -> list[str]:
        return [key for key in self._unique_valid(values) if key not in HIDDEN_REPORT_COLUMNS]

    def _unique_valid(self, values: Any) -> list[str]:
        out: list[str] = []
        for value in values or []:
            key = str(value or "").strip()
            if key in PRODUCT_REPORT_COLUMNS and key not in out:
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

    def _filter_text(self, text: str) -> str:
        return re.split(r"\b(?:muestra|mostrar|incluye|con columnas|campos)\b", text, maxsplit=1)[0].strip()

    def _value_after(self, text: str, marker: str) -> str:
        needle = f"{marker} "
        if needle not in text:
            return ""
        tail = text.split(needle, 1)[1].strip()
        return tail.split(",", 1)[0].split(" ordenado", 1)[0].strip()

    def _value_after_any(self, text: str, markers: tuple[str, ...]) -> str:
        for marker in markers:
            value = self._value_after(text, marker)
            if value:
                return value
        return ""

    def _search_value(self, text: str) -> str:
        patterns = (
            r"\b(?:contiene|contengan|contenga|con descripcion|con referencia|buscar|busca|buscame)\s+(.+)$",
            r"\barticulos?\s+(?:de|con|que contengan|que contenga)\s+(.+)$",
        )
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                value = match.group(1).strip()
                value = re.split(r"\s+ordenado\b|,", value, maxsplit=1)[0].strip()
                for prefix in ("descripcion ", "referencia ", "ref "):
                    if value.startswith(prefix):
                        value = value[len(prefix) :].strip()
                return value
        return ""


class ProductReportService:
    def run(self, intent: ProductReportIntent) -> ProductReportResult:
        columns = [
            key for key in intent.columns
            if key in PRODUCT_REPORT_COLUMNS and key not in HIDDEN_REPORT_COLUMNS
        ] or list(DEFAULT_PRODUCT_REPORT_COLUMNS)
        select_parts = [f"{PRODUCT_REPORT_COLUMNS[key][1]} AS {key}" for key in columns]
        sql = [
            "SELECT",
            ", ".join(select_parts),
            "FROM productos_ireks p",
            "LEFT JOIN fabricantes f ON f.fabricante_id = p.fabricante_id",
            "LEFT JOIN familias fa ON fa.articulo_familia_id = p.articulo_familia_id",
            "LEFT JOIN subfamilias sf ON sf.articulo_familia_id = p.articulo_familia_id AND sf.articulo_subfamilia_id = p.articulo_subfamilia_id",
            "LEFT JOIN envases e ON e.envase_id = p.articulo_envase_id",
            "LEFT JOIN distribuidores d ON d.distribuidor_id = p.distribuidor_id",
        ]
        params: dict[str, Any] = {}
        where = self._build_where(intent.filters, params)
        selected_ids = [int(item_id) for item_id in getattr(intent, "selected_ids", []) if int(item_id or 0) > 0]
        if selected_ids:
            placeholders: list[str] = []
            for idx, item_id in enumerate(selected_ids):
                key = f"selected_id_{idx}"
                params[key] = item_id
                placeholders.append(f":{key}")
            where.append(f"p.id IN ({', '.join(placeholders)})")
        if where:
            sql.append("WHERE " + " AND ".join(where))
        order = [PRODUCT_REPORT_COLUMNS[key][1] for key in intent.order_by if key in PRODUCT_REPORT_COLUMNS]
        sql.append("ORDER BY " + ", ".join(order or ["p.articulo_referencia_corta", "p.articulo_descripcion"]))
        params["limit"] = max(1, min(5000, int(intent.limit or 500)))
        sql.append("LIMIT :limit")

        with engine.begin() as conn:
            rows = conn.exec_driver_sql("\n".join(sql), params).fetchall()

        headers = [PRODUCT_REPORT_COLUMNS[key][0] for key in columns]
        data_rows = [[self._format_value(columns[idx], value) for idx, value in enumerate(row)] for row in rows]
        return ProductReportResult(intent.title or "Listado de productos IREKS", headers, data_rows, intent)

    def _build_where(self, filters: list[ProductReportFilter], params: dict[str, Any]) -> list[str]:
        where: list[str] = []
        for idx, flt in enumerate(filters):
            field_name = str(flt.field or "").strip()
            if field_name not in PRODUCT_REPORT_COLUMNS:
                continue
            expr = PRODUCT_REPORT_COLUMNS[field_name][1]
            op = str(flt.op or "=").strip().lower()
            param = f"p{idx}"
            if field_name in BOOL_FIELDS:
                params[param] = 1 if self._to_bool(flt.value) else 0
                where.append(f"{expr} = :{param}")
            elif field_name in NUMERIC_FIELDS:
                sql_op = op if op in {"=", "!=", ">", ">=", "<", "<="} else "="
                params[param] = self._to_number(flt.value)
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
        return text in {"1", "true", "si", "sí", "yes", "activo", "lista", "en lista"}

    def _to_number(self, value: Any) -> float:
        try:
            return float(str(value or "0").replace(",", "."))
        except Exception:
            return 0.0

    def _format_value(self, field_name: str, value: Any) -> Any:
        if field_name in BOOL_FIELDS:
            return "Si" if bool(value) else "No"
        if field_name in NUMERIC_FIELDS:
            try:
                number = float(value or 0)
                return f"{number:.4f}".rstrip("0").rstrip(".")
            except Exception:
                return value
        return "" if value is None else value
