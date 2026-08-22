from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from app.services.customer_service import CustomerService
from app.services.local_ai_service import LocalAIService


@dataclass(frozen=True)
class CustomerAISnapshot:
    customer_id: str
    customer_name: str
    customer_type: str
    activity: str
    active: bool
    year: int
    previous_year: int
    kg_current: float
    kg_previous: float
    euros_current: float
    delta_kg: float
    delta_kg_pct: float | None
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


class CustomerAISummaryService:
    """Build a read-only customer snapshot and optionally explain it with local AI."""

    def __init__(
        self,
        *,
        customer_service: CustomerService | None = None,
        local_ai_service: LocalAIService | None = None,
    ) -> None:
        self.customer_service = customer_service or CustomerService()
        self.local_ai_service = local_ai_service or LocalAIService(timeout=90.0)

    def summarize(self, customer: Any) -> CustomerAISummaryResult:
        customer_id = str(getattr(customer, "cliente_id", "") or "").strip()
        if not customer_id:
            return CustomerAISummaryResult(False, "", "Selecciona un cliente para generar el resumen.")

        try:
            snapshot = self._build_snapshot(customer)
        except Exception as exc:  # noqa: BLE001
            return CustomerAISummaryResult(False, "", f"No se pudieron preparar los datos del cliente.\n{exc}")

        deterministic_text = self._deterministic_summary(snapshot)
        if not self.local_ai_service.enabled:
            return CustomerAISummaryResult(
                True,
                deterministic_text,
                "Resumen calculado. La IA local no está activada.",
                False,
                snapshot,
            )

        ai_result = self.local_ai_service.generate_process(self._build_prompt(snapshot))
        if not ai_result.ok:
            return CustomerAISummaryResult(
                True,
                deterministic_text,
                f"Resumen calculado sin redacción IA: {ai_result.message}",
                False,
                snapshot,
            )
        return CustomerAISummaryResult(
            True,
            ai_result.text.strip(),
            "Resumen redactado con IA local a partir de datos calculados por GestionIREKS.",
            True,
            snapshot,
        )

    def _build_snapshot(self, customer: Any) -> CustomerAISnapshot:
        customer_id = str(getattr(customer, "cliente_id", "") or "").strip()
        years = sorted(
            {int(value) for value in self.customer_service.related_sales_years() if int(value or 0) > 0},
            reverse=True,
        )
        year = years[0] if years else date.today().year
        rows = list(self.customer_service.related_sales(customer_id, year) or [])
        contacts = list(self.customer_service.related_contacts(customer_id) or [])
        recipes = list(self.customer_service.related_recipes(customer_id) or [])
        agenda = list(self.customer_service.related_agenda(customer_id) or [])

        kg_current = sum(float(getattr(row, "kg_curr", 0.0) or 0.0) for row in rows)
        kg_previous = sum(float(getattr(row, "kg_prev", 0.0) or 0.0) for row in rows)
        euros_current = sum(float(getattr(row, "euros_curr", 0.0) or 0.0) for row in rows)
        delta_kg = kg_current - kg_previous
        delta_kg_pct = (delta_kg / kg_previous * 100.0) if abs(kg_previous) > 1e-9 else None

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
        )[:5]
        declining_rows = sorted(
            (
                row
                for row in current_rows
                if float(getattr(row, "kg_prev", 0.0) or 0.0) > 1e-9
                and float(getattr(row, "kg_curr", 0.0) or 0.0) < float(getattr(row, "kg_prev", 0.0) or 0.0)
            ),
            key=lambda row: float(getattr(row, "kg_curr", 0.0) or 0.0) - float(getattr(row, "kg_prev", 0.0) or 0.0),
        )[:5]

        agenda_dates = [getattr(item, "fecha_actividad", None) for item in agenda]
        valid_agenda_dates = [value for value in agenda_dates if isinstance(value, date)]
        latest_date = max(valid_agenda_dates) if valid_agenda_dates else None
        opportunities = self._build_opportunities(
            kg_current=kg_current,
            kg_previous=kg_previous,
            delta_kg_pct=delta_kg_pct,
            stopped_rows=stopped_rows,
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
            kg_current=kg_current,
            kg_previous=kg_previous,
            euros_current=euros_current,
            delta_kg=delta_kg,
            delta_kg_pct=delta_kg_pct,
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
        contact_count: int,
        latest_activity: date | None,
    ) -> list[str]:
        items: list[str] = []
        if kg_previous > 1e-9 and kg_current <= 1e-9:
            items.append("Revisar la pérdida total de consumo respecto al periodo anterior.")
        elif delta_kg_pct is not None and delta_kg_pct <= -20.0:
            items.append(f"Revisar la caída de consumo del {abs(delta_kg_pct):.1f}% respecto al periodo anterior.")
        if stopped_rows:
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
        variation = "sin base de comparación"
        if data.delta_kg_pct is not None:
            variation = f"{data.delta_kg_pct:+.1f}%"
        return "\n".join(
            [
                f"RESUMEN COMERCIAL · {data.customer_name}",
                "",
                "Perfil",
                f"Tipo: {data.customer_type or 'No indicado'} · Actividad: {data.activity or 'No indicada'} · Estado: {'Activo' if data.active else 'Inactivo'}",
                f"Contactos: {data.contact_count} · Recetas: {data.recipe_count} · Actividades de agenda: {data.agenda_count}",
                f"Última actividad: {data.latest_activity or 'Sin actividad registrada'}",
                "",
                f"Ventas {data.year} frente a {data.previous_year}",
                f"Kg actuales: {self._number(data.kg_current)} · Kg anteriores: {self._number(data.kg_previous)} · Variación: {variation}",
                f"Facturación actual: {self._number(data.euros_current)} €",
                "",
                "Productos principales",
                self._bullets(data.top_products, "Sin ventas de productos en el periodo actual."),
                "",
                "Productos sin consumo actual",
                self._bullets(data.stopped_products, "No se detectan productos abandonados."),
                "",
                "Productos en descenso",
                self._bullets(data.declining_products, "No se detectan productos en descenso."),
                "",
                "Oportunidades y seguimiento",
                self._bullets(data.opportunities, "Sin recomendaciones automáticas."),
            ]
        )

    def _build_prompt(self, data: CustomerAISnapshot) -> str:
        return (
            "Redacta en español un resumen comercial breve y claro usando exclusivamente los datos siguientes. "
            "No inventes causas, fechas, productos ni importes. Distingue los hechos de las acciones sugeridas. "
            "No propongas modificar la base de datos. Conserva las cifras y organiza la respuesta en: situación, "
            "ventas, productos y oportunidades.\n\n"
            f"{self._deterministic_summary(data)}"
        )

    @staticmethod
    def _bullets(items: tuple[str, ...], empty_text: str) -> str:
        return "\n".join(f"• {item}" for item in items) if items else f"• {empty_text}"

    @staticmethod
    def _number(value: float) -> str:
        return f"{float(value):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
