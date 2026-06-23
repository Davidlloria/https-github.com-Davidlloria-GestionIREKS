from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any
from urllib.request import ProxyHandler, Request, build_opener

from app.services.openai_process_service import OpenAIProcessService
from app.services.openai_settings_service import OpenAISettingsService
from app.services.sales_annual_comparison_service import SalesAnnualComparisonService, SalesDetailRow, SalesComparisonRow


@dataclass
class SalesQueryIntent:
    query_type: str = "general"
    year: int = 0
    year_compare: int = 0
    month: int = 0
    acumulado: bool = False
    cliente_id: str = ""
    cliente_texto: str = ""
    articulo_id: str = ""
    producto_texto: str = ""
    fabricante_id: str = ""
    familia_id: str = ""
    subfamilia_id: str = ""
    limit: int = 200


@dataclass
class SalesQueryIntentResult:
    ok: bool
    intent: SalesQueryIntent
    message: str
    used_ai: bool = False


@dataclass
class SalesQueryResult:
    ok: bool
    text: str
    message: str
    intent: SalesQueryIntent


class SalesQueryAssistantService:
    BASE_URL = "https://api.openai.com/v1/responses"

    def __init__(
        self,
        sales_service: SalesAnnualComparisonService | None = None,
        api_key: str | None = None,
        model: str = "gpt-4.1-mini",
        timeout: float = 30.0,
    ) -> None:
        cfg = OpenAISettingsService().load()
        self.api_key = str(api_key or cfg.get("api_key") or "").strip()
        self.model = str(model or "gpt-4.1-mini").strip()
        self.timeout = timeout
        self.sales_service = sales_service or SalesAnnualComparisonService()
        self.answer_service = OpenAIProcessService(api_key=self.api_key, model=self.model, timeout=self.timeout)

    def answer(self, question: str, defaults: dict[str, Any] | None = None) -> SalesQueryResult:
        intent_result = self.interpret(question, defaults=defaults)
        intent = intent_result.intent
        defaults = dict(defaults or {})

        if self._comparative_detail_requested(intent):
            blocks = self._fetch_comparative_detail_blocks(intent, defaults)
            if not blocks:
                return SalesQueryResult(
                    True,
                    "No se han encontrado ventas que coincidan con la comparativa solicitada y los filtros disponibles.",
                    "Sin datos de comparativa.",
                    intent,
                )
            text = self._build_comparative_detail_answer(question, intent, blocks, defaults)
            return SalesQueryResult(True, text, "Comparativa de detalle calculada.", intent)
        elif self._detail_requested(intent):
            rows = self.sales_service.listar_detalle_ventas(
                year=self._effective_int(defaults, "year", intent.year),
                month=self._effective_int(defaults, "month", intent.month),
                acumulado=self._effective_bool(defaults, "acumulado", intent.acumulado),
                cliente_id=self._effective_text(defaults, "cliente_id", intent.cliente_id),
                cliente_texto=self._effective_text(defaults, "cliente_texto", intent.cliente_texto),
                articulo_id=self._effective_text(defaults, "articulo_id", intent.articulo_id),
                producto_texto=self._effective_text(defaults, "producto_texto", intent.producto_texto),
                fabricante_id=self._effective_text(defaults, "fabricante_id", intent.fabricante_id),
                familia_id=self._effective_text(defaults, "familia_id", intent.familia_id),
                subfamilia_id=self._effective_text(defaults, "subfamilia_id", intent.subfamilia_id),
                limit=max(intent.limit, 1),
            )
            if not rows:
                return SalesQueryResult(
                    True,
                    "No se han encontrado ventas que coincidan con la consulta y los filtros disponibles.",
                    "Sin datos de detalle.",
                    intent,
                )
            context = self._format_detail_context(question, intent, rows, defaults)
        else:
            rows = self.sales_service.listar_resumen_anual(
                year=self._effective_int(defaults, "year", intent.year),
                month=self._effective_int(defaults, "month", intent.month),
                acumulado=self._effective_bool(defaults, "acumulado", intent.acumulado),
                cliente_id=self._effective_text(defaults, "cliente_id", intent.cliente_id),
                producto_texto=self._effective_text(defaults, "producto_texto", intent.producto_texto),
                fabricante_id=self._effective_text(defaults, "fabricante_id", intent.fabricante_id),
                familia_id=self._effective_text(defaults, "familia_id", intent.familia_id),
                subfamilia_id=self._effective_text(defaults, "subfamilia_id", intent.subfamilia_id),
            )
            if not rows:
                return SalesQueryResult(
                    True,
                    "No se han encontrado ventas que coincidan con la consulta y los filtros disponibles.",
                    "Sin datos de resumen.",
                    intent,
                )
            context = self._format_summary_context(question, intent, rows, defaults)

        prompt = self._build_prompt(question, intent, context)
        result = self.answer_service.generate_process(prompt)
        if result.ok:
            return SalesQueryResult(True, result.text.strip(), result.message, intent)
        return SalesQueryResult(False, "", result.message, intent)

    def interpret(self, question: str, defaults: dict[str, Any] | None = None) -> SalesQueryIntentResult:
        text = str(question or "").strip()
        defaults = dict(defaults or {})
        fallback = self._fallback_intent(text, defaults)
        if not text:
            return SalesQueryIntentResult(False, fallback, "Escribe una consulta de ventas.")
        if not self.api_key:
            return SalesQueryIntentResult(True, fallback, "Interpretación local. Falta API key de OpenAI.", False)

        payload: dict[str, Any] = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "Convierte consultas libres sobre ventas en JSON estricto. "
                        "No generes SQL ni texto adicional. "
                        "Devuelve solo estas claves: "
                        "query_type, year, year_compare, month, acumulado, cliente_id, cliente_texto, articulo_id, producto_texto, "
                        "fabricante_id, familia_id, subfamilia_id, limit. "
                        "query_type debe ser uno de: detalle, mensual, anual, comparativa, ranking, tendencia, general. "
                        "Si la consulta menciona un producto, un cliente o un mes concreto, usa query_type detalle. "
                        "Si pide top, ranking o evolución, usa ranking, tendencia o comparativa según corresponda. "
                        "Los valores year y month deben ser enteros; acumulado debe ser booleano; limit entero."
                    ),
                },
                {"role": "user", "content": text},
            ],
            "temperature": 0,
            "max_output_tokens": 400,
        }
        try:
            raw = json.dumps(payload).encode("utf-8")
            req = Request(self.BASE_URL, data=raw, method="POST")
            req.add_header("Authorization", f"Bearer {self.api_key}")
            req.add_header("Content-Type", "application/json")
            req.add_header("Accept", "application/json")
            opener = build_opener(ProxyHandler({}))
            with opener.open(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
            data = json.loads(body or "{}")
            parsed = self._parse_json(self._extract_text(data))
            intent = self._intent_from_mapping(parsed, fallback)
            return SalesQueryIntentResult(True, intent, "Interpretado con ChatGPT.", True)
        except Exception as exc:  # noqa: BLE001
            return SalesQueryIntentResult(True, fallback, f"Interpretación local. ChatGPT no disponible: {exc}", False)

    def _detail_requested(self, intent: SalesQueryIntent) -> bool:
        if self._comparative_detail_requested(intent):
            return False
        if intent.query_type == "detalle":
            return True
        if intent.producto_texto or intent.cliente_texto or intent.articulo_id or intent.cliente_id:
            return True
        if 1 <= int(intent.month or 0) <= 12:
            return True
        return False

    def _comparative_detail_requested(self, intent: SalesQueryIntent) -> bool:
        if intent.year <= 0 or intent.year_compare <= 0:
            return False
        if not (intent.producto_texto or intent.cliente_texto or intent.articulo_id or intent.cliente_id):
            return False
        return bool(intent.month or intent.query_type == "comparativa")

    def _fetch_comparative_detail_blocks(
        self,
        intent: SalesQueryIntent,
        defaults: dict[str, Any],
    ) -> list[dict[str, Any]]:
        year_a = self._effective_int(defaults, "year", intent.year)
        year_b = self._effective_int(defaults, "year_compare", intent.year_compare)
        if year_a <= 0 or year_b <= 0:
            return []
        month = self._effective_int(defaults, "month", intent.month)
        acumulado = self._effective_bool(defaults, "acumulado", intent.acumulado)
        cliente_id = self._effective_text(defaults, "cliente_id", intent.cliente_id)
        cliente_texto = self._effective_text(defaults, "cliente_texto", intent.cliente_texto)
        articulo_id = self._effective_text(defaults, "articulo_id", intent.articulo_id)
        producto_texto = self._effective_text(defaults, "producto_texto", intent.producto_texto)
        fabricante_id = self._effective_text(defaults, "fabricante_id", intent.fabricante_id)
        familia_id = self._effective_text(defaults, "familia_id", intent.familia_id)
        subfamilia_id = self._effective_text(defaults, "subfamilia_id", intent.subfamilia_id)
        limit = max(intent.limit, 1)
        return [
            {
                "year": year_a,
                "rows": self.sales_service.listar_detalle_ventas(
                    year=year_a,
                    month=month,
                    acumulado=acumulado,
                    cliente_id=cliente_id,
                    cliente_texto=cliente_texto,
                    articulo_id=articulo_id,
                    producto_texto=producto_texto,
                    fabricante_id=fabricante_id,
                    familia_id=familia_id,
                    subfamilia_id=subfamilia_id,
                    limit=limit,
                ),
            },
            {
                "year": year_b,
                "rows": self.sales_service.listar_detalle_ventas(
                    year=year_b,
                    month=month,
                    acumulado=acumulado,
                    cliente_id=cliente_id,
                    cliente_texto=cliente_texto,
                    articulo_id=articulo_id,
                    producto_texto=producto_texto,
                    fabricante_id=fabricante_id,
                    familia_id=familia_id,
                    subfamilia_id=subfamilia_id,
                    limit=limit,
                ),
            },
        ]

    def _format_detail_context(
        self,
        question: str,
        intent: SalesQueryIntent,
        rows: list[SalesDetailRow],
        defaults: dict[str, Any],
    ) -> str:
        year = self._effective_int(defaults, "year", intent.year)
        lines = [
            "Consulta de detalle de ventas obtenida directamente de la base de datos.",
            f"Pregunta: {question}",
            f"Intención detectada: {intent.query_type}",
            f"Filas recuperadas: {len(rows)}",
            f"Filtros efectivos: año={year}, mes={self._effective_int(defaults, 'month', intent.month)}, acumulado={'sí' if self._effective_bool(defaults, 'acumulado', intent.acumulado) else 'no'}",
        ]
        if intent.cliente_texto or intent.cliente_id:
            lines.append(f"Cliente consultado: {intent.cliente_texto or intent.cliente_id}")
        if intent.producto_texto or intent.articulo_id:
            lines.append(f"Producto consultado: {intent.producto_texto or intent.articulo_id}")
        lines.append("")
        lines.append("Filas devueltas:")
        for row in rows[: max(1, min(intent.limit, 120))]:
            lines.append(
                f"- {row.periodo} | {row.cliente_nombre} | {row.codigo} | {row.nombre} | "
                f"Kg: {self._fmt_num(row.kilos)} | S/C: {self._fmt_num(row.sc)} | Ventas: {self._fmt_money(row.ventas)}"
            )
        return "\n".join(lines).strip()

    def _format_comparative_detail_context(
        self,
        question: str,
        intent: SalesQueryIntent,
        blocks: list[dict[str, Any]],
        defaults: dict[str, Any],
    ) -> str:
        month = self._effective_int(defaults, "month", intent.month)
        lines = [
            "Comparativa de detalle de ventas obtenida directamente de la base de datos.",
            f"Pregunta: {question}",
            f"Intención detectada: {intent.query_type}",
            f"Filas comparadas: {len(blocks)} bloques",
            f"Filtros efectivos: mes={month}, acumulado={'sí' if self._effective_bool(defaults, 'acumulado', intent.acumulado) else 'no'}",
        ]
        if intent.cliente_texto or intent.cliente_id:
            lines.append(f"Cliente consultado: {intent.cliente_texto or intent.cliente_id}")
        if intent.producto_texto or intent.articulo_id:
            lines.append(f"Producto consultado: {intent.producto_texto or intent.articulo_id}")
        lines.append("")
        for block in blocks:
            year = int(block.get("year") or 0)
            rows = list(block.get("rows") or [])
            lines.append(f"Año {year}:")
            if not rows:
                lines.append("- Sin filas para este año.")
                continue
            for row in rows[: max(1, min(intent.limit, 120))]:
                lines.append(
                    f"- {row.periodo} | {row.cliente_nombre} | {row.codigo} | {row.nombre} | "
                    f"Kg: {self._fmt_num(row.kilos)} | S/C: {self._fmt_num(row.sc)} | Ventas: {self._fmt_money(row.ventas)}"
                )
        return "\n".join(lines).strip()

    def _build_comparative_detail_answer(
        self,
        question: str,
        intent: SalesQueryIntent,
        blocks: list[dict[str, Any]],
        defaults: dict[str, Any],
    ) -> str:
        month = self._effective_int(defaults, "month", intent.month)
        month_label = self._month_name(month)
        lines = [f"Comparativa de ventas en kg para {month_label}."]
        if intent.cliente_texto or intent.cliente_id:
            lines.append(f"Cliente: {intent.cliente_texto or intent.cliente_id}")
        if intent.producto_texto or intent.articulo_id:
            lines.append(f"Producto: {intent.producto_texto or intent.articulo_id}")
        lines.append("")

        totals: list[tuple[int, float, float]] = []
        for block in blocks:
            year = int(block.get("year") or 0)
            rows = list(block.get("rows") or [])
            kilos = sum(float(row.kilos or 0.0) for row in rows)
            totals.append((year, kilos, float(len(rows))))
            lines.append(f"Año {year}: {self._fmt_num(kilos)} kg")
            if not rows:
                lines.append("  Sin datos para este año.")
        if len(totals) >= 2:
            year_a, kilos_a, _ = totals[0]
            year_b, kilos_b, _ = totals[1]
            delta = kilos_b - kilos_a
            pct = self._pct(delta, kilos_a)
            lines.append("")
            lines.append(
                f"Diferencia {year_b} vs {year_a}: {self._fmt_num(delta)} kg ({self._fmt_num(pct)} %)."
            )
        lines.append("")
        lines.append("Pregunta original:")
        lines.append(question)
        return "\n".join(lines).strip()

    @staticmethod
    def _month_name(month: int) -> str:
        month_names = {
            1: "enero",
            2: "febrero",
            3: "marzo",
            4: "abril",
            5: "mayo",
            6: "junio",
            7: "julio",
            8: "agosto",
            9: "septiembre",
            10: "octubre",
            11: "noviembre",
            12: "diciembre",
        }
        return month_names.get(int(month or 0), f"mes {month}")

    @staticmethod
    def _pct(delta: float, base: float) -> float:
        base_value = float(base or 0.0)
        if abs(base_value) <= 1e-9:
            return 0.0
        return (float(delta or 0.0) / base_value) * 100.0

    def _format_summary_context(
        self,
        question: str,
        intent: SalesQueryIntent,
        rows: list[SalesComparisonRow],
        defaults: dict[str, Any],
    ) -> str:
        year = self._effective_int(defaults, "year", intent.year)
        month = self._effective_int(defaults, "month", intent.month)
        lines = [
            "Resumen de ventas obtenido directamente de la base de datos.",
            f"Pregunta: {question}",
            f"Intención detectada: {intent.query_type}",
            f"Filas recuperadas: {len(rows)}",
            f"Filtros efectivos: año={year}, mes={month}, acumulado={'sí' if self._effective_bool(defaults, 'acumulado', intent.acumulado) else 'no'}",
            "",
            "Filas devueltas:",
        ]
        for row in rows[: max(1, min(intent.limit, 100))]:
            lines.append(
                f"- {row.codigo} | {row.nombre} | "
                f"Kg prev: {self._fmt_num(row.kilos_prev)} | Kg actual: {self._fmt_num(row.kilos_curr)} | "
                f"Ventas prev: {self._fmt_money(row.ventas_prev)} | Ventas actual: {self._fmt_money(row.ventas_curr)} | "
                f"Δ kg: {self._fmt_num(row.delta_kg)} | Δ €: {self._fmt_money(row.delta_ventas)}"
            )
        return "\n".join(lines).strip()

    def _build_prompt(self, question: str, intent: SalesQueryIntent, context: str) -> str:
        return (
            "Eres un analista de ventas experto en IREKS.\n"
            "Responde en español, con foco práctico y directo.\n"
            "Usa solo los datos proporcionados. No inventes cifras.\n"
            "Si la consulta es puntual, responde con el valor o los valores exactos.\n"
            "Si faltan datos, dilo claramente.\n\n"
            f"Intención detectada:\n{json.dumps(intent.__dict__, ensure_ascii=False, indent=2)}\n\n"
            f"Datos de ventas:\n{context}\n\n"
            f"Consulta del usuario:\n{question}\n"
        )

    def _fallback_intent(self, text: str, defaults: dict[str, Any]) -> SalesQueryIntent:
        normalized = self._normalize_search_text(text)
        intent = SalesQueryIntent(
            query_type="general",
            year=self._effective_int(defaults, "year", 0),
            month=self._effective_int(defaults, "month", 0),
            acumulado=self._effective_bool(defaults, "acumulado", False),
            cliente_id=self._effective_text(defaults, "cliente_id", ""),
            cliente_texto=self._effective_text(defaults, "cliente_texto", ""),
            articulo_id=self._effective_text(defaults, "articulo_id", ""),
            producto_texto=self._effective_text(defaults, "producto_texto", ""),
            fabricante_id=self._effective_text(defaults, "fabricante_id", ""),
            familia_id=self._effective_text(defaults, "familia_id", ""),
            subfamilia_id=self._effective_text(defaults, "subfamilia_id", ""),
            limit=200,
        )
        year_matches = [int(value) for value in re.findall(r"\b(20\d{2})\b", normalized)]
        if year_matches:
            intent.year = year_matches[0]
        if len(year_matches) > 1:
            intent.year_compare = year_matches[1]
        month_map = {
            "enero": 1,
            "febrero": 2,
            "marzo": 3,
            "abril": 4,
            "mayo": 5,
            "junio": 6,
            "julio": 7,
            "agosto": 8,
            "septiembre": 9,
            "setiembre": 9,
            "octubre": 10,
            "noviembre": 11,
            "diciembre": 12,
        }
        for name, value in month_map.items():
            if re.search(rf"\b{name}\b", normalized):
                intent.month = value
                break
        comparative_markers = (
            "comparar",
            "comparado con",
            "comparadas con",
            "comparados con",
            "comparada con",
            "comparado",
            "comparada",
            " vs ",
            " contra ",
            "respecto a",
            "en comparacion con",
            "en comparación con",
        )
        if any(token in normalized for token in comparative_markers) or len(year_matches) > 1:
            intent.query_type = "comparativa"
        elif any(token in normalized for token in ("detalle", "venta de", "ventas de", "dime las ventas", "dime la venta")):
            intent.query_type = "detalle"
        elif any(token in normalized for token in ("top ", "top10", "ranking", "mayores", "más vendidos", "mas vendidos")):
            intent.query_type = "ranking"
        elif any(token in normalized for token in ("evolucion", "evolución", "tendencia", "historico", "histórico")):
            intent.query_type = "tendencia"
        elif "compar" in normalized:
            intent.query_type = "comparativa"
        elif "mensual" in normalized:
            intent.query_type = "mensual"
        elif "anual" in normalized or "resumen" in normalized:
            intent.query_type = "anual"

        producto = self._extract_after_markers(
            normalized,
            ("producto", "articulo", "artículo", "venta de", "ventas de", "del producto"),
        )
        cliente = self._extract_after_markers(
            normalized,
            ("cliente", "del cliente", "para cliente", "del cliente de", "cliente de"),
        )
        if producto:
            intent.producto_texto = producto
        if cliente:
            intent.cliente_texto = cliente
        if any(token in normalized for token in ("acumulado", "acumular", "acumulada")):
            intent.acumulado = True
        if intent.query_type != "comparativa" and (intent.producto_texto or intent.cliente_texto or intent.month):
            intent.query_type = "detalle"
        if intent.year > 0 and intent.year_compare > 0 and (intent.producto_texto or intent.cliente_texto or intent.month):
            intent.query_type = "comparativa"
        if "top 10" in normalized or "top10" in normalized:
            intent.limit = 10
        return intent

    def _intent_from_mapping(self, payload: dict[str, Any], fallback: SalesQueryIntent) -> SalesQueryIntent:
        if not isinstance(payload, dict):
            return fallback
        intent = SalesQueryIntent(
            query_type=self._normalize_query_type(payload.get("query_type"), fallback.query_type),
            year=self._coerce_int(payload.get("year"), fallback.year),
            year_compare=self._coerce_int(payload.get("year_compare"), fallback.year_compare),
            month=self._coerce_int(payload.get("month"), fallback.month),
            acumulado=self._coerce_bool(payload.get("acumulado"), fallback.acumulado),
            cliente_id=self._coerce_text(payload.get("cliente_id"), fallback.cliente_id),
            cliente_texto=self._coerce_text(payload.get("cliente_texto"), fallback.cliente_texto),
            articulo_id=self._coerce_text(payload.get("articulo_id"), fallback.articulo_id),
            producto_texto=self._coerce_text(payload.get("producto_texto"), fallback.producto_texto),
            fabricante_id=self._coerce_text(payload.get("fabricante_id"), fallback.fabricante_id),
            familia_id=self._coerce_text(payload.get("familia_id"), fallback.familia_id),
            subfamilia_id=self._coerce_text(payload.get("subfamilia_id"), fallback.subfamilia_id),
            limit=max(self._coerce_int(payload.get("limit"), fallback.limit), 1),
        )
        if intent.producto_texto or intent.cliente_texto or intent.articulo_id or intent.cliente_id:
            intent.query_type = "detalle"
        if intent.query_type == "comparativa" and intent.year_compare <= 0:
            intent.year_compare = fallback.year_compare
        return intent

    def _parse_json(self, value: str) -> dict[str, Any]:
        text = str(value or "").strip()
        if not text:
            return {}
        try:
            return json.loads(text)
        except Exception:
            pass
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                return {}
        return {}

    def _extract_text(self, payload: dict[str, Any]) -> str:
        out = str(payload.get("output_text") or "").strip()
        if out:
            return out
        output = payload.get("output") or []
        for item in output:
            content = item.get("content") or []
            for block in content:
                txt = str(block.get("text") or "").strip()
                if txt:
                    return txt
        return ""

    def _extract_after_markers(self, text: str, markers: tuple[str, ...]) -> str:
        for marker in markers:
            pattern = rf"\b{re.escape(marker)}\b\s*(?:de|del|para)?\s*(.+)$"
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                candidate = str(match.group(1) or "").strip()
                candidate = re.split(r"\b(?:de|del|para|en|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre|enero|febrero|marzo|abril|mayo|junio)\b", candidate, maxsplit=1, flags=re.IGNORECASE)[0].strip(" ,.;:")
                if candidate:
                    return candidate
        return ""

    def _normalize_query_type(self, value: Any, default: str) -> str:
        clean = self._normalize_search_text(value)
        if clean in {"detalle", "mensual", "anual", "comparativa", "ranking", "tendencia", "general"}:
            return clean
        return default

    def _coerce_int(self, value: Any, default: int) -> int:
        try:
            return int(value)
        except Exception:
            return int(default or 0)

    def _coerce_bool(self, value: Any, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return bool(default)
        text = self._normalize_search_text(value)
        if text in {"1", "true", "yes", "si", "sí", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
        return bool(default)

    def _coerce_text(self, value: Any, default: str) -> str:
        text = str(value or "").strip()
        return text if text else str(default or "").strip()

    def _effective_text(self, defaults: dict[str, Any], key: str, fallback: str) -> str:
        text = str(fallback or "").strip()
        if text:
            return text
        return str(defaults.get(key, "") or "").strip()

    def _effective_int(self, defaults: dict[str, Any], key: str, fallback: int) -> int:
        try:
            value = int(fallback or 0)
            if value:
                return value
        except Exception:
            pass
        value = defaults.get(key, None)
        try:
            if value is None:
                return 0
            return int(value)
        except Exception:
            return 0

    def _effective_bool(self, defaults: dict[str, Any], key: str, fallback: bool) -> bool:
        if isinstance(fallback, bool):
            return fallback
        value = defaults.get(key, None)
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return self._coerce_bool(value, False)

    def _normalize_search_text(self, value) -> str:
        text = str(value or "").strip().lower()
        normalized = unicodedata.normalize("NFD", text)
        normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
        return re.sub(r"\s+", " ", normalized)

    def _fmt_num(self, value: float) -> str:
        return f"{float(value or 0.0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def _fmt_money(self, value: float) -> str:
        return f"{self._fmt_num(value)} €"
