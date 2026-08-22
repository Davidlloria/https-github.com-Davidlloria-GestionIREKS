from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.services.customer_service import CustomerService
from app.services.local_ai_service import LocalAIService


CUSTOMER_AI_SUMMARY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "situation": {"type": "string"},
        "sales": {"type": "string"},
        "products": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 3,
        },
        "opportunities": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 3,
        },
        "conclusion": {"type": "string"},
    },
    "required": ["situation", "sales", "products", "opportunities", "conclusion"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class CustomerAISummarySections:
    situation: str
    sales: str
    products: tuple[str, ...] = ()
    opportunities: tuple[str, ...] = ()
    conclusion: str = ""


@dataclass(frozen=True)
class CustomerAISnapshot:
    customer_id: str
    customer_name: str
    customer_type: str
    activity: str
    active: bool
    year: int
    previous_year: int
    month_from: int
    month_to: int
    period_label: str
    comparison_available: bool
    comparison_note: str
    kg_current: float
    kg_previous: float
    euros_current: float
    delta_kg: float | None
    delta_kg_pct: float | None
    historical_prior_year: int = 0
    historical_prior_kg: float = 0.0
    historical_delta_pct: float | None = None
    top_products: tuple[str, ...] = ()
    stopped_products: tuple[str, ...] = ()
    declining_products: tuple[str, ...] = ()
    contact_count: int = 0
    recipe_count: int = 0
    agenda_count: int = 0
    latest_activity: str = ""
    opportunities: tuple[str, ...] = ()


@dataclass(frozen=True)
class CustomerAISummaryResult:
    ok: bool
    text: str
    message: str
    used_ai: bool = False
    snapshot: CustomerAISnapshot | None = None
    sections: CustomerAISummarySections | None = None


class CustomerAISummaryService:
    """Build a read-only customer snapshot and optionally explain it with local AI."""

    def __init__(
        self,
        *,
        customer_service: CustomerService | None = None,
        local_ai_service: LocalAIService | None = None,
    ) -> None:
        self.customer_service = customer_service or CustomerService()
        self.local_ai_service = local_ai_service or LocalAIService(timeout=180.0)

    def summarize(self, customer: Any) -> CustomerAISummaryResult:
        customer_id = str(getattr(customer, "cliente_id", "") or "").strip()
        if not customer_id:
            return CustomerAISummaryResult(False, "", "Selecciona un cliente para generar el resumen.")

        try:
            snapshot = self._build_snapshot(customer)
        except Exception as exc:  # noqa: BLE001
            return CustomerAISummaryResult(False, "", f"No se pudieron preparar los datos del cliente.\n{exc}")

        fallback_sections = self._fallback_sections(snapshot)
        deterministic_text = self._sections_text(fallback_sections)
        if not self.local_ai_service.enabled:
            return CustomerAISummaryResult(
                True,
                deterministic_text,
                "Resumen calculado. La IA local no está activada.",
                False,
                snapshot,
                fallback_sections,
            )

        ai_result = self.local_ai_service.generate_json(
            self._build_prompt(snapshot),
            schema=CUSTOMER_AI_SUMMARY_SCHEMA,
            max_tokens=700,
        )
        if not ai_result.ok:
            return CustomerAISummaryResult(
                True,
                deterministic_text,
                f"Resumen calculado sin redacción IA: {ai_result.message}",
                False,
                snapshot,
                fallback_sections,
            )
        try:
            sections = self._parse_sections(ai_result.text)
        except (json.JSONDecodeError, TypeError, ValueError):
            return CustomerAISummaryResult(
                True,
                deterministic_text,
                "Resumen calculado sin redacción IA: la respuesta no tenía el formato esperado.",
                False,
                snapshot,
                fallback_sections,
            )
        sections = self._enforce_comparison_rules(snapshot, sections, fallback_sections)
        return CustomerAISummaryResult(
            True,
            self._sections_text(sections),
            "Resumen redactado con IA local a partir de datos calculados por GestionIREKS.",
            True,
            snapshot,
            sections,
        )

    def _build_snapshot(self, customer: Any) -> CustomerAISnapshot:
        customer_id = str(getattr(customer, "cliente_id", "") or "").strip()
        years = sorted(
            {int(value) for value in self.customer_service.related_sales_years() if int(value or 0) > 0},
            reverse=True,
        )
        year = years[0] if years else date.today().year
        latest_month = int(self.customer_service.related_sales_latest_month(year) or 0)
        month_to = max(1, min(latest_month or 12, 12))
        previous_months = self.customer_service.related_sales_months(customer_id, year - 1)
        previous_is_annual_total = month_to < 12 and previous_months == (12,)
        rows = list(
            self.customer_service.related_sales(
                customer_id,
                year,
                month_from=1,
                month_to=month_to,
            )
            or []
        )
        reference_rows = rows
        historical_prior_year = 0
        historical_prior_kg = 0.0
        historical_delta_pct = None
        if previous_is_annual_total:
            reference_rows = list(
                self.customer_service.related_sales(
                    customer_id,
                    year,
                    month_from=1,
                    month_to=12,
                )
                or []
            )
            prior_year = year - 2
            if self.customer_service.related_sales_months(customer_id, prior_year) == (12,):
                prior_reference_rows = list(
                    self.customer_service.related_sales(
                        customer_id,
                        year - 1,
                        month_from=1,
                        month_to=12,
                    )
                    or []
                )
                historical_prior_year = prior_year
                historical_prior_kg = sum(
                    float(getattr(row, "kg_prev", 0.0) or 0.0) for row in prior_reference_rows
                )
        contacts = list(self.customer_service.related_contacts(customer_id) or [])
        recipes = list(self.customer_service.related_recipes(customer_id) or [])
        agenda = list(self.customer_service.related_agenda(customer_id) or [])

        kg_current = sum(float(getattr(row, "kg_curr", 0.0) or 0.0) for row in rows)
        kg_previous = sum(float(getattr(row, "kg_prev", 0.0) or 0.0) for row in reference_rows)
        euros_current = sum(float(getattr(row, "euros_curr", 0.0) or 0.0) for row in rows)
        comparison_available = not previous_is_annual_total
        if previous_is_annual_total and abs(historical_prior_kg) > 1e-9:
            historical_delta_pct = (kg_previous - historical_prior_kg) / historical_prior_kg * 100.0
        delta_kg = kg_current - kg_previous if comparison_available else None
        delta_kg_pct = (
            delta_kg / kg_previous * 100.0
            if comparison_available and delta_kg is not None and abs(kg_previous) > 1e-9
            else None
        )

        current_rows = [row for row in rows if float(getattr(row, "kg_curr", 0.0) or 0.0) > 1e-9]
        top_rows = sorted(
            current_rows,
            key=lambda row: float(getattr(row, "kg_curr", 0.0) or 0.0),
            reverse=True,
        )[:5]
        stopped_rows = sorted(
            (
                row
                for row in rows
                if float(getattr(row, "kg_prev", 0.0) or 0.0) > 1e-9
                and float(getattr(row, "kg_curr", 0.0) or 0.0) <= 1e-9
            ),
            key=lambda row: float(getattr(row, "kg_prev", 0.0) or 0.0),
            reverse=True,
        )[:5] if comparison_available else []
        declining_rows = sorted(
            (
                row
                for row in current_rows
                if float(getattr(row, "kg_prev", 0.0) or 0.0) > 1e-9
                and float(getattr(row, "kg_curr", 0.0) or 0.0) < float(getattr(row, "kg_prev", 0.0) or 0.0)
            ),
            key=lambda row: float(getattr(row, "kg_curr", 0.0) or 0.0) - float(getattr(row, "kg_prev", 0.0) or 0.0),
        )[:5] if comparison_available else []

        agenda_dates = [getattr(item, "fecha_actividad", None) for item in agenda]
        valid_agenda_dates = [value for value in agenda_dates if isinstance(value, date)]
        latest_date = max(valid_agenda_dates) if valid_agenda_dates else None
        opportunities = self._build_opportunities(
            kg_current=kg_current,
            kg_previous=kg_previous,
            delta_kg_pct=delta_kg_pct,
            stopped_rows=stopped_rows,
            comparison_available=comparison_available,
            annual_years=tuple(
                value for value in (year - 1, historical_prior_year) if value
            ),
            contact_count=len(contacts),
            latest_activity=latest_date,
        )

        return CustomerAISnapshot(
            customer_id=customer_id,
            customer_name=str(
                getattr(customer, "cliente_nombre_comercial", "")
                or getattr(customer, "cliente_nombre_fiscal", "")
                or customer_id
            ).strip(),
            customer_type=str(getattr(customer, "cliente_tipo", "") or "").strip(),
            activity=str(getattr(customer, "cliente_actividad", "") or "").strip(),
            active=bool(getattr(customer, "activo", False)),
            year=year,
            previous_year=year - 1,
            month_from=1,
            month_to=month_to,
            period_label=self._period_label(
                year,
                month_to,
                comparison_available=comparison_available,
                historical_prior_year=historical_prior_year,
            ),
            comparison_available=comparison_available,
            comparison_note=(
                f"{year} es parcial y no se compara con los acumulados anuales de {year - 1}"
                f"{' y ' + str(historical_prior_year) if historical_prior_year else ''}."
                if previous_is_annual_total
                else ""
            ),
            kg_current=kg_current,
            kg_previous=kg_previous,
            euros_current=euros_current,
            delta_kg=delta_kg,
            delta_kg_pct=delta_kg_pct,
            historical_prior_year=historical_prior_year,
            historical_prior_kg=historical_prior_kg,
            historical_delta_pct=historical_delta_pct,
            top_products=tuple(self._product_line(row, "kg_curr") for row in top_rows),
            stopped_products=tuple(self._product_line(row, "kg_prev") for row in stopped_rows),
            declining_products=tuple(self._declining_product_line(row) for row in declining_rows),
            contact_count=len(contacts),
            recipe_count=len(recipes),
            agenda_count=len(agenda),
            latest_activity=latest_date.isoformat() if latest_date else "",
            opportunities=tuple(opportunities),
        )

    @staticmethod
    def _build_opportunities(
        *,
        kg_current: float,
        kg_previous: float,
        delta_kg_pct: float | None,
        stopped_rows: list[Any],
        comparison_available: bool,
        annual_years: tuple[int, ...],
        contact_count: int,
        latest_activity: date | None,
    ) -> list[str]:
        items: list[str] = []
        if not comparison_available:
            years_text = " y ".join(str(value) for value in annual_years)
            items.append(
                f"Los datos mensuales de {years_text} no están disponibles; sus cifras se tratan como acumulados anuales."
            )
        if comparison_available and kg_previous > 1e-9 and kg_current <= 1e-9:
            items.append("Revisar la pérdida total de consumo respecto al periodo anterior.")
        elif comparison_available and delta_kg_pct is not None and delta_kg_pct <= -20.0:
            items.append(f"Revisar la caída de consumo del {abs(delta_kg_pct):.1f}% respecto al periodo anterior.")
        if comparison_available and stopped_rows:
            items.append(f"Revisar {len(stopped_rows)} producto(s) con consumo anterior y sin consumo actual.")
        if contact_count == 0:
            items.append("Completar un contacto comercial antes del próximo seguimiento.")
        if latest_activity is None:
            items.append("Planificar una primera actividad de seguimiento.")
        elif (date.today() - latest_activity).days > 90:
            items.append("Actualizar el seguimiento: la última actividad registrada tiene más de 90 días.")
        if not items:
            items.append("No se detectan alertas automáticas con las reglas actuales.")
        return items

    @staticmethod
    def _product_line(row: Any, value_field: str) -> str:
        code = str(getattr(row, "codigo", "") or "").strip()
        name = str(getattr(row, "nombre", "") or "").strip()
        value = float(getattr(row, value_field, 0.0) or 0.0)
        label = " · ".join(part for part in (code, name) if part) or "Producto sin identificar"
        return f"{label}: {CustomerAISummaryService._number(value)} kg"

    @staticmethod
    def _declining_product_line(row: Any) -> str:
        code = str(getattr(row, "codigo", "") or "").strip()
        name = str(getattr(row, "nombre", "") or "").strip()
        current = float(getattr(row, "kg_curr", 0.0) or 0.0)
        previous = float(getattr(row, "kg_prev", 0.0) or 0.0)
        label = " · ".join(part for part in (code, name) if part) or "Producto sin identificar"
        return f"{label}: {CustomerAISummaryService._number(previous)} → {CustomerAISummaryService._number(current)} kg"

    def _deterministic_summary(self, data: CustomerAISnapshot) -> str:
        variation = self._variation_text(data)
        lines = [
                f"RESUMEN COMERCIAL · {data.customer_name}",
                "",
                "Perfil",
                f"Tipo: {data.customer_type or 'No indicado'} · Actividad: {data.activity or 'No indicada'} · Estado: {'Activo' if data.active else 'Inactivo'}",
                f"Contactos: {data.contact_count} · Recetas: {data.recipe_count} · Actividades de agenda: {data.agenda_count}",
                f"Última actividad: {data.latest_activity or 'Sin actividad registrada'}",
                "",
                f"Ventas {data.period_label}",
                self._sales_text(data),
                f"Variación del periodo actual: {variation}",
                data.comparison_note,
                "",
                "Productos principales",
                self._bullets(data.top_products, "Sin ventas de productos en el periodo actual."),
        ]
        if data.comparison_available:
            lines.extend(
                [
                    "",
                    "Productos sin consumo actual",
                    self._bullets(data.stopped_products, "No se detectan productos abandonados."),
                    "",
                    "Productos en descenso",
                    self._bullets(data.declining_products, "No se detectan productos en descenso."),
                ]
            )
        else:
            lines.extend(
                [
                    "",
                    "Comparación histórica de productos",
                    "No evaluable: 2024 y 2025 solo contienen acumulados anuales.",
                ]
            )
        lines.extend(
            [
                "",
                "Oportunidades y seguimiento",
                self._bullets(data.opportunities, "Sin recomendaciones automáticas."),
            ]
        )
        return "\n".join(lines)

    def _build_prompt(self, data: CustomerAISnapshot) -> str:
        historical_instruction = ""
        if not data.comparison_available:
            historical_instruction = (
                f"Los datos de {data.historical_prior_year or data.previous_year - 1} y {data.previous_year} son "
                f"totales anuales a diciembre: nunca los describas como el mismo periodo de {data.year}. No deduzcas "
                "abandonos, descensos ni aumentos de producto usando esos históricos. "
            )
        return (
            "Devuelve un JSON en español con un resumen comercial breve usando exclusivamente los datos siguientes. "
            "No inventes causas, fechas, productos ni importes. Distingue los hechos de las acciones sugeridas. "
            "No propongas modificar la base de datos. Conserva las cifras y el periodo comparado. "
            "Cada texto debe tener una sola frase corta. Usa situation para el perfil, sales para las ventas, products "
            "para un máximo de tres observaciones, opportunities para un máximo de tres acciones y conclusion para una "
            "frase final. Si se indica que los periodos no son comparables, no calcules ni sugieras una variación. "
            f"{historical_instruction}"
            "Sin Markdown ni texto fuera del JSON.\n\n"
            f"{self._deterministic_summary(data)}"
        )

    def _fallback_sections(self, data: CustomerAISnapshot) -> CustomerAISummarySections:
        product_notes = [
            f"Productos principales: {', '.join(data.top_products)}"
            if data.top_products
            else "Sin ventas de productos en el periodo actual."
        ]
        if data.comparison_available:
            product_notes.extend(
                [
                    f"Sin consumo actual: {', '.join(data.stopped_products)}"
                    if data.stopped_products
                    else "No se detectan productos abandonados.",
                    f"En descenso: {', '.join(data.declining_products)}"
                    if data.declining_products
                    else "No se detectan productos en descenso.",
                ]
            )
        else:
            product_notes.append("No se evalúan abandonos ni descensos porque el histórico no es mensual.")
        return CustomerAISummarySections(
            situation=(
                f"Cliente {'activo' if data.active else 'inactivo'}, tipo {data.customer_type or 'no indicado'}, "
                f"actividad {data.activity or 'no indicada'}. Contactos: {data.contact_count}; recetas: "
                f"{data.recipe_count}; actividades de agenda: {data.agenda_count}. Última actividad: "
                f"{data.latest_activity or 'sin actividad registrada'}."
            ),
            sales=self._sales_text(data),
            products=tuple(product_notes),
            opportunities=data.opportunities,
            conclusion=self._conclusion_text(data),
        )

    def _enforce_comparison_rules(
        self,
        data: CustomerAISnapshot,
        sections: CustomerAISummarySections,
        fallback: CustomerAISummarySections,
    ) -> CustomerAISummarySections:
        if data.comparison_available:
            return sections
        unsafe_terms = (
            "2024",
            "2025",
            "anterior",
            "compar",
            "descens",
            "abandon",
            "perdid",
            "caída",
            "inferior",
            "superior",
        )
        safe_products = tuple(
            item for item in sections.products
            if not any(term in item.casefold() for term in unsafe_terms)
        )[:3]
        return CustomerAISummarySections(
            situation=sections.situation,
            sales=self._sales_text(data),
            products=safe_products or fallback.products[:3],
            opportunities=data.opportunities[:3],
            conclusion=self._conclusion_text(data),
        )

    def _sales_text(self, data: CustomerAISnapshot) -> str:
        current_period = self._current_period_label(data.year, data.month_to)
        if data.comparison_available:
            return (
                f"{data.period_label}: {self._number(data.kg_current)} kg frente a "
                f"{self._number(data.kg_previous)} kg; variación {self._variation_text(data)}. "
                f"Facturación actual: {self._number(data.euros_current)} €."
            )
        history = f"{data.previous_year}: {self._number(data.kg_previous)} kg acumulados a diciembre"
        if data.historical_prior_year:
            history += f"; {data.historical_prior_year}: {self._number(data.historical_prior_kg)} kg acumulados a diciembre"
        if data.historical_delta_pct is not None:
            annual_variation = f"{data.historical_delta_pct:+.1f}".replace(".", ",")
            history += (
                f"; variación anual {data.previous_year} frente a {data.historical_prior_year}: "
                f"{annual_variation}%"
            )
        return (
            f"{current_period}: {self._number(data.kg_current)} kg y {self._number(data.euros_current)} € de facturación. "
            f"Es un acumulado parcial y no se compara con años completos. Históricos anuales: {history}."
        )

    def _conclusion_text(self, data: CustomerAISnapshot) -> str:
        if data.comparison_available:
            return "Resumen calculado exclusivamente con datos de GestionIREKS."
        if data.historical_delta_pct is not None:
            direction = "disminuyó" if data.historical_delta_pct < 0 else "aumentó"
            annual_variation = f"{abs(data.historical_delta_pct):.1f}".replace(".", ",")
            return (
                f"El consumo anual de {data.previous_year} {direction} un {annual_variation}% frente a "
                f"{data.historical_prior_year}; el acumulado parcial de {data.year} debe analizarse por separado."
            )
        return f"El acumulado parcial de {data.year} debe analizarse por separado de los históricos anuales."

    @staticmethod
    def _parse_sections(text: str) -> CustomerAISummarySections:
        parsed = json.loads(str(text or "").strip())
        if not isinstance(parsed, dict):
            raise ValueError("La respuesta no es un objeto.")

        def clean_list(value: Any) -> tuple[str, ...]:
            if not isinstance(value, list):
                raise ValueError("La respuesta no contiene una lista válida.")
            return tuple(str(item or "").strip() for item in value if str(item or "").strip())[:3]

        situation = str(parsed.get("situation") or "").strip()
        sales = str(parsed.get("sales") or "").strip()
        conclusion = str(parsed.get("conclusion") or "").strip()
        if not situation or not sales or not conclusion:
            raise ValueError("Faltan secciones obligatorias.")
        return CustomerAISummarySections(
            situation=situation,
            sales=sales,
            products=clean_list(parsed.get("products")),
            opportunities=clean_list(parsed.get("opportunities")),
            conclusion=conclusion,
        )

    @staticmethod
    def _sections_text(sections: CustomerAISummarySections) -> str:
        product_text = "\n".join(f"• {item}" for item in sections.products)
        opportunity_text = "\n".join(f"• {item}" for item in sections.opportunities)
        return "\n\n".join(
            [
                f"Situación\n{sections.situation}",
                f"Ventas\n{sections.sales}",
                f"Productos\n{product_text}",
                f"Oportunidades\n{opportunity_text}",
                f"Conclusión\n{sections.conclusion}",
            ]
        )

    @staticmethod
    def _period_label(
        year: int,
        month_to: int,
        *,
        comparison_available: bool = True,
        historical_prior_year: int = 0,
    ) -> str:
        month_names = (
            "enero",
            "febrero",
            "marzo",
            "abril",
            "mayo",
            "junio",
            "julio",
            "agosto",
            "septiembre",
            "octubre",
            "noviembre",
            "diciembre",
        )
        end_month = month_names[max(1, min(int(month_to or 12), 12)) - 1]
        if not comparison_available:
            history = f"históricos anuales {year - 1}"
            if historical_prior_year:
                history += f" y {historical_prior_year}"
            return f"enero–{end_month} {year} · {history}"
        return f"enero–{end_month} {year} frente a enero–{end_month} {year - 1}"

    @staticmethod
    def _current_period_label(year: int, month_to: int) -> str:
        label = CustomerAISummaryService._period_label(year, month_to)
        return label.split(" frente a ", 1)[0]

    @staticmethod
    def _variation_text(data: CustomerAISnapshot) -> str:
        if not data.comparison_available:
            return "no comparable"
        if data.delta_kg_pct is None:
            return "sin base de comparación"
        return f"{data.delta_kg_pct:+.1f}%"

    @staticmethod
    def _bullets(items: tuple[str, ...], empty_text: str) -> str:
        return "\n".join(f"• {item}" for item in items) if items else f"• {empty_text}"

    @staticmethod
    def _number(value: float) -> str:
        return f"{float(value):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
