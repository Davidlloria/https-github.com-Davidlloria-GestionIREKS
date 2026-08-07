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
    compare_year: int = 0
    limit: int = 500
    customer_type: str = ''
    island: str = ''
    direction: str = "asc"
    metric: str = "kg"
    zero_consumption: bool = False
    columns: list[str] = field(default_factory=list)
    sort_by_island: bool = True
    sort_metric: str = "kg"


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
        if intent.query_type == 'sales_customer_year_comparison':
            return self._run_sales_customer_year_comparison(intent)
        if intent.query_type == 'sales_customer_list':
            return self._run_sales_customer_list(intent)
        if intent.query_type in {"sales_drop_ranking", "sales_growth_ranking"}:
            return self._run_sales_ranking(intent)
        return self._run_customer_filter(text, intent)

    def interpret(self, prompt: str) -> CustomerQueryIntent:
        normalized = self._normalize(prompt)
        years = [int(item) for item in re.findall(r"\b(20\d{2})\b", normalized)]
        year = years[0] if years else date.today().year
        compare_year = years[1] if len(years) > 1 else 0
        limit = self._extract_limit(normalized)

        sales_terms = ("compra", "venta", "kg", "kilo", "consumo")
        drop_terms = ("bajada", "bajado", "bajan", "caida", "caido", "descenso", "perdido", "menos")
        growth_terms = ("subida", "subido", "suben", "aumento", "crecimiento", "crecido", "mas")
        ranking_terms = ("mayor", "mayores", "top", "ranking", "primer", "peor", "mejor")
        is_sales = any(term in normalized for term in sales_terms)
        wants_drop = any(term in normalized for term in drop_terms)
        wants_growth = any(term in normalized for term in growth_terms)
        wants_ranking = any(term in normalized for term in ranking_terms) or limit != 500
        wants_year_comparison = bool(
            compare_year
            and any(
                term in normalized
                for term in (
                    ' versus ',
                    ' vs ',
                    ' contra ',
                    ' comparado con ',
                    ' comparativa con ',
                    ' comparativa entre ',
                    ' comparar con ',
                )
            )
        )
        sales_columns = self._extract_sales_columns(normalized, year=year, compare_year=compare_year)
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
        explicit_descending = any(
            term in normalized
            for term in ('mayor a menor', 'descendente', 'decreciente')
        )
        explicit_ascending = any(
            term in normalized
            for term in ('menor a mayor', 'ascendente', 'creciente')
        )
        positive_ranking = any(
            term in normalized
            for term in (
                'top',
                'ranking',
                'mayores ventas',
                'mayor venta',
                'mas ventas',
                'mas venta',
                'mas kg',
                'mayores kg',
                'mejores clientes',
                'primeros',
            )
        )
        negative_ranking = any(
            term in normalized
            for term in (
                'menores ventas',
                'menor venta',
                'menos ventas',
                'menos venta',
                'menos kg',
                'menores kg',
                'peores clientes',
                'bottom',
            )
        )
        list_direction = 'asc'
        if explicit_descending or (positive_ranking and not negative_ranking):
            list_direction = 'desc'
        if explicit_ascending or negative_ranking:
            list_direction = 'asc'
        sort_metric = 'kg'
        if wants_year_comparison:
            sort_metric = (
                'delta_kg'
                if wants_drop
                or wants_growth
                or any(term in normalized for term in ('ordenar por diferencia', 'ordenado por diferencia', 'por diferencia'))
                else 'kg_curr'
            )
            if wants_drop or negative_ranking:
                list_direction = 'asc'
            elif wants_growth or positive_ranking:
                list_direction = 'desc'
        sort_by_island = any(
            term in normalized
            for term in (
                'por isla',
                'por islas',
                'ordenada por isla',
                'ordenadas por isla',
                'ordenado por isla',
                'ordenados por isla',
            )
        )
        zero_consumption = bool(
            re.search(r'\bconsumo\s*(?:=|igual\s+a)?\s*0(?:[,.]0+)?\b', normalized)
            or any(
                term in normalized
                for term in ('sin consumo', 'no han consumido', 'no ha consumido')
            )
        )

        if is_sales and wants_year_comparison:
            return CustomerQueryIntent(
                query_type='sales_customer_year_comparison',
                year=year,
                compare_year=compare_year,
                limit=min(max(limit if limit != 500 else 10, 1), 500),
                direction=list_direction,
                metric='kg',
                customer_type=customer_type,
                island=island,
                columns=sales_columns,
                sort_by_island=sort_by_island,
                sort_metric=sort_metric,
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
                columns=sales_columns,
                sort_by_island=sort_by_island,
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
            sort_by_island=intent.sort_by_island,
        )
        safe_limit = min(max(int(intent.limit or 500), 1), 5000)
        rows = rows[:safe_limit]
        column_map = {
            'isla': ('Isla', lambda row: row.isla),
            'codigo': ('Cod.', lambda row: row.cliente_codigo),
            'nombre': ('Nombre comercial', lambda row: row.cliente_nombre),
            'kg': ('Kg', lambda row: row.kg),
        }
        selected_columns = [key for key in intent.columns if key in column_map] or ['isla', 'codigo', 'nombre', 'kg']
        headers = [column_map[key][0] for key in selected_columns]
        data = [[column_map[key][1](row) for key in selected_columns] for row in rows]
        customer_type = f' de clientes {intent.customer_type}s' if intent.customer_type else ''
        location = f' de {intent.island}' if intent.island else ''
        consumption = ' con consumo 0 kg' if intent.zero_consumption else ''
        order_label = 'mayor a menor' if intent.direction == 'desc' else 'menor a mayor'
        return CustomerQueryResult(
            status='ready' if data else 'empty',
            title=f'Listado de ventas {intent.year}{customer_type}{location}{consumption}',
            headers=headers,
            rows=data,
            message='' if data else 'No se encontraron clientes para los filtros indicados.',
            source='cálculo local',
            interpretation=(
                f'Ventas {intent.year}{customer_type}{location}{consumption} · métrica Kg · '
                f'orden: kg de {order_label}'
            ),
            intent=intent,
        )

    def _run_sales_customer_year_comparison(self, intent: CustomerQueryIntent) -> CustomerQueryResult:
        rows = self.sales_service.listar_comparativa_anual_clientes(
            year=intent.year,
            compare_year=intent.compare_year,
            limit=intent.limit,
            direction=intent.direction,
            sort_metric=intent.sort_metric,
            cliente_tipo=intent.customer_type,
            isla=intent.island,
        )
        column_map = {
            'codigo': ('Cod.', lambda row: row.cliente_codigo),
            'nombre': ('Nombre comercial', lambda row: row.cliente_nombre),
            'kg_curr': (f'Kg {intent.year}', lambda row: row.kg_curr),
            'kg_prev': (f'Kg {intent.compare_year}', lambda row: row.kg_prev),
            'delta_kg': ('Dif. Kg', lambda row: row.delta_kg),
            'delta_kg_pct': ('Dif. Kg %', lambda row: row.delta_kg_pct),
        }
        selected_columns = [key for key in intent.columns if key in column_map] or [
            'codigo',
            'nombre',
            'kg_curr',
            'kg_prev',
            'delta_kg',
            'delta_kg_pct',
        ]
        headers = [column_map[key][0] for key in selected_columns]
        data = [[column_map[key][1](row) for key in selected_columns] for row in rows]
        customer_type = f' de clientes {intent.customer_type}s' if intent.customer_type else ''
        location = f' de {intent.island}' if intent.island else ''
        order_label = 'mayor a menor' if intent.direction == 'desc' else 'menor a mayor'
        metric_label = 'diferencia kg' if intent.sort_metric == 'delta_kg' else f'kg {intent.year}'
        return CustomerQueryResult(
            status='ready' if data else 'empty',
            title=f'Comparativa ventas {intent.year} vs {intent.compare_year}{customer_type}{location}',
            headers=headers,
            rows=data,
            message='' if data else 'No se encontraron ventas para los años indicados.',
            source='cálculo local',
            interpretation=(
                f'Comparativa {intent.year} vs {intent.compare_year}{customer_type}{location} · '
                f'métrica Kg · orden: {metric_label} de {order_label}'
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

    def _extract_sales_columns(self, normalized: str, *, year: int = 0, compare_year: int = 0) -> list[str]:
        if not any(marker in normalized for marker in ('campos', 'columnas', 'solo los campos', 'solo campos')):
            return []
        tail = re.split(r'\b(?:campos|columnas|solo los campos|solo campos)\b\s*:?', normalized, maxsplit=1)
        if len(tail) < 2:
            return []
        raw = re.split(r'\b(?:ordenad[oa]s?|ordenar|de mayor|de menor|mayor a menor|menor a mayor)\b', tail[1], maxsplit=1)[0]
        parts = [part.strip(" .;:") for part in re.split(r',|\by\b', raw) if part.strip(" .;:")]
        columns: list[str] = []
        for part in parts:
            token = part.strip()
            key = ''
            if token in {'isla', 'islas'}:
                key = 'isla'
            elif token in {'cod', 'cod.', 'codigo', 'codigo cliente', 'codigo interno'}:
                key = 'codigo'
            elif token in {'nombre', 'cliente', 'nombre comercial'}:
                key = 'nombre'
            elif compare_year and (
                token in {f'kg {year}', f'kilos {year}', f'kilogramos {year}', f'ventas {year}'}
                or (str(year) in token and any(term in token for term in ('kg', 'kilo', 'venta')))
            ):
                key = 'kg_curr'
            elif compare_year and (
                token in {f'kg {compare_year}', f'kilos {compare_year}', f'kilogramos {compare_year}', f'ventas {compare_year}'}
                or (str(compare_year) in token and any(term in token for term in ('kg', 'kilo', 'venta')))
            ):
                key = 'kg_prev'
            elif compare_year and (
                token in {'diferencia kg %', 'dif kg %', 'delta kg %', 'variacion kg %', 'porcentaje'}
                or '%' in token
            ):
                key = 'delta_kg_pct'
            elif compare_year and (
                token in {'diferencia kg', 'dif kg', 'delta kg', 'variacion kg', 'variacion'}
                or 'diferencia' in token
                or 'delta' in token
                or 'variacion' in token
            ):
                key = 'delta_kg'
            elif token in {'kg', 'kilos', 'kilogramos'}:
                key = 'kg'
            if key and key not in columns:
                columns.append(key)
        return columns

    @staticmethod
    def _normalize(value: str) -> str:
        decomposed = unicodedata.normalize("NFKD", str(value or "").lower())
        return "".join(char for char in decomposed if not unicodedata.combining(char))
