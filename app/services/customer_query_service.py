from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import re
import unicodedata
from typing import Any

from app.services.customer_report_flow_service import CustomerReportFlowService
from app.services.sales_annual_comparison_service import SalesAnnualComparisonService


@dataclass
class CustomerQueryIntent:
    query_type: str = "customer_filter"
    year: int = 0
    limit: int = 500
    customer_type: str = ''
    island: str = ''
    direction: str = "asc"
    metric: str = "kg"
    zero_consumption: bool = False


@dataclass
class CustomerQueryResult:
    status: str
    title: str = ""
    headers: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)
    message: str = ""
    source: str = ""
    interpretation: str = ""
    intent: CustomerQueryIntent = field(default_factory=CustomerQueryIntent)


class CustomerQueryService:
    """Routes natural-language customer queries to read-only deterministic services."""

    _NUMBER_WORDS = {
        "un": 1,
        "uno": 1,
        "dos": 2,
        "tres": 3,
        "cuatro": 4,
        "cinco": 5,
        "seis": 6,
        "siete": 7,
        "ocho": 8,
        "nueve": 9,
        "diez": 10,
        "veinte": 20,
    }

    def __init__(
        self,
        report_flow_service: CustomerReportFlowService | None = None,
        sales_service: SalesAnnualComparisonService | None = None,
    ) -> None:
        self.report_flow_service = report_flow_service or CustomerReportFlowService()
        self.sales_service = sales_service or SalesAnnualComparisonService()

    def run(self, prompt: str) -> CustomerQueryResult:
        text = str(prompt or "").strip()
        if not text:
            return CustomerQueryResult(status="empty", message="Escribe una consulta sobre los clientes.")

        intent = self.interpret(text)
        if intent.query_type == 'sales_customer_list':
            return self._run_sales_customer_list(intent)
        if intent.query_type in {"sales_drop_ranking", "sales_growth_ranking"}:
            return self._run_sales_ranking(intent)
        return self._run_customer_filter(text, intent)

    def interpret(self, prompt: str) -> CustomerQueryIntent:
        normalized = self._normalize(prompt)
        year_match = re.search(r"\b(20\d{2})\b", normalized)
        year = int(year_match.group(1)) if year_match else date.today().year
        limit = self._extract_limit(normalized)

        sales_terms = ("compra", "venta", "kg", "kilo", "consumo")
        drop_terms = ("bajada", "bajado", "bajan", "caida", "caido", "descenso", "perdido", "menos")
        growth_terms = ("subida", "subido", "suben", "aumento", "crecimiento", "crecido", "mas")
        ranking_terms = ("mayor", "mayores", "top", "ranking", "primer", "peor", "mejor")
        is_sales = any(term in normalized for term in sales_terms)
        wants_drop = any(term in normalized for term in drop_terms)
        wants_growth = any(term in normalized for term in growth_terms)
        wants_ranking = any(term in normalized for term in ranking_terms) or limit != 500
        customer_type = ''
        if 'indirect' in normalized:
            customer_type = 'indirecto'
        elif 'distribuidor' in normalized:
            customer_type = 'distribuidor'
        elif 'direct' in normalized:
            customer_type = 'directo'

        island = ''
        island_names = {
            'gran canaria': 'Gran Canaria',
            'tenerife': 'Tenerife',
            'lanzarote': 'Lanzarote',
            'fuerteventura': 'Fuerteventura',
            'la palma': 'La Palma',
            'la gomera': 'La Gomera',
            'el hierro': 'El Hierro',
        }
        for island_term, island_name in island_names.items():
            if island_term in normalized:
                island = island_name
                break
        descending = any(
            term in normalized
            for term in ('mayor a menor', 'descendente', 'decreciente')
        )
        list_direction = 'desc' if descending else 'asc'
        zero_consumption = bool(
            re.search(r'\bconsumo\s*(?:=|igual\s+a)?\s*0(?:[,.]0+)?\b', normalized)
            or any(
                term in normalized
                for term in ('sin consumo', 'no han consumido', 'no ha consumido')
            )
        )

        if is_sales and not (wants_ranking and (wants_drop or wants_growth)):
            return CustomerQueryIntent(
                query_type='sales_customer_list',
                year=year,
                limit=limit,
                direction=list_direction,
                metric='kg',
                customer_type=customer_type,
                island=island,
                zero_consumption=zero_consumption,
            )

        if is_sales and wants_ranking and (wants_drop or wants_growth):
            query_type = "sales_drop_ranking" if wants_drop else "sales_growth_ranking"
            return CustomerQueryIntent(
                query_type=query_type,
                year=year,
                limit=min(max(limit if limit != 500 else 10, 1), 500),
                direction="asc" if wants_drop else "desc",
                metric="kg",
            )
        return CustomerQueryIntent(query_type="customer_filter", year=year, limit=limit, metric="kg")

    def _run_customer_filter(self, prompt: str, intent: CustomerQueryIntent) -> CustomerQueryResult:
        flow_result = self.report_flow_service.generate_report(prompt)
        report = flow_result.report
        if report is None:
            return CustomerQueryResult(
                status=flow_result.status,
                message=flow_result.message,
                source=flow_result.source,
                intent=intent,
            )
        filters = ", ".join(
            f"{item.field} {item.op} {item.value}" for item in report.intent.filters
        ) or "sin filtros adicionales"
        return CustomerQueryResult(
            status=flow_result.status,
            title=report.title,
            headers=list(report.headers),
            rows=[list(row) for row in report.rows],
            message=flow_result.message,
            source=flow_result.source,
            interpretation=f"Listado de clientes · {filters}",
            intent=intent,
        )

    def _run_sales_customer_list(self, intent: CustomerQueryIntent) -> CustomerQueryResult:
        rows = self.sales_service.listar_ventas_anuales_clientes(
            year=intent.year,
            cliente_tipo=intent.customer_type,
            isla=intent.island,
            direction=intent.direction,
            zero_consumption=intent.zero_consumption,
        )
        safe_limit = min(max(int(intent.limit or 500), 1), 5000)
        rows = rows[:safe_limit]
        data = [[row.isla, row.cliente_codigo, row.cliente_nombre, row.kg] for row in rows]
        customer_type = f' de clientes {intent.customer_type}s' if intent.customer_type else ''
        location = f' de {intent.island}' if intent.island else ''
        consumption = ' con consumo 0 kg' if intent.zero_consumption else ''
        order_label = 'mayor a menor' if intent.direction == 'desc' else 'menor a mayor'
        return CustomerQueryResult(
            status='ready' if data else 'empty',
            title=f'Listado de ventas {intent.year}{customer_type}{location}{consumption}',
            headers=['Isla', 'Cod.', 'Nombre comercial', 'Kg'],
            rows=data,
            message='' if data else 'No se encontraron clientes para los filtros indicados.',
            source='cálculo local',
            interpretation=(
                f'Ventas {intent.year}{customer_type}{location}{consumption} · métrica Kg · '
                f'orden: kg de {order_label}'
            ),
            intent=intent,
        )

    def _run_sales_ranking(self, intent: CustomerQueryIntent) -> CustomerQueryResult:
        rows = self.sales_service.listar_ranking_anual_clientes(
            year=intent.year,
            limit=intent.limit,
            direction=intent.direction,
        )
        previous_year = intent.year - 1
        data = [
            [
                row.cliente_codigo,
                row.cliente_nombre,
                row.kg_prev,
                row.kg_curr,
                row.delta_kg,
                row.delta_kg_pct,
            ]
            for row in rows
        ]
        movement = "mayores bajadas" if intent.direction == "asc" else "mayores subidas"
        status = "ready" if data else "empty"
        return CustomerQueryResult(
            status=status,
            title=f"Clientes con {movement} en compras",
            headers=["Cod.", "Cliente", f"Kg {previous_year}", f"Kg {intent.year}", "Δ Kg", "Δ Kg %"],
            rows=data,
            message="" if data else "No se encontraron ventas para los años comparados.",
            source="cálculo local",
            interpretation=(
                f"Comparativa {intent.year} vs. {previous_year} · métrica Kg · "
                f"{movement} · límite {intent.limit}"
            ),
            intent=intent,
        )

    def _extract_limit(self, normalized: str) -> int:
        digit_match = re.search(r"\b(?:top\s*)?(\d{1,3})\b", normalized)
        if digit_match:
            value = int(digit_match.group(1))
            if 1 <= value < 1900:
                return min(max(value, 1), 500)
        for word, value in self._NUMBER_WORDS.items():
            if word in ('un', 'uno'):
                continue
            if re.search(rf"\b{word}\b", normalized):
                return value
        return 500

    @staticmethod
    def _normalize(value: str) -> str:
        decomposed = unicodedata.normalize("NFKD", str(value or "").lower())
        return "".join(char for char in decomposed if not unicodedata.combining(char))
