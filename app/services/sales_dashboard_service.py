from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime

from sqlmodel import Session, col, select

from app.core.database import engine
from app.models import Cliente, Isla, VentaMensualRaw
from app.services.sales_annual_comparison_service import SalesAnnualComparisonService


@dataclass
class DashboardSalesCustomerRow:
    cliente_id: str
    cliente_codigo: str
    cliente_nombre: str
    isla: str
    cliente_tipo: str
    kg_prev: float
    kg_curr: float
    delta_kg: float
    delta_pct: float


@dataclass
class DashboardSalesIslandRow:
    isla: str
    customers: int
    kg_prev: float
    kg_curr: float
    delta_kg: float
    share_pct: float


@dataclass
class DashboardSalesTypeRow:
    cliente_tipo: str
    customers: int
    kg_curr: float
    delta_kg: float
    share_pct: float


@dataclass
class SalesDashboardSnapshot:
    year: int
    previous_year: int
    total_kg: float
    delta_kg: float
    delta_pct: float
    active_customers: int
    active_islands: int
    customers_down: int
    customer_drop_rows: list[DashboardSalesCustomerRow]
    island_rows: list[DashboardSalesIslandRow]
    type_rows: list[DashboardSalesTypeRow]
    zero_consumption_rows: list[DashboardSalesCustomerRow]
    generated_at: datetime


class SalesDashboardService:
    def __init__(
        self,
        *,
        db_engine=None,
        annual_sales_service: SalesAnnualComparisonService | None = None,
    ) -> None:
        self._engine = db_engine if db_engine is not None else engine
        self.annual_sales_service = annual_sales_service or SalesAnnualComparisonService(db_engine=self._engine)

    def load_snapshot(self, *, today: date | None = None) -> SalesDashboardSnapshot:
        target_date = today or date.today()
        years = self.annual_sales_service.list_years()
        current_year = max(years) if years else target_date.year
        previous_year = current_year - 1

        with Session(self._engine) as session:
            raw_rows = list(session.exec(select(VentaMensualRaw).where(col(VentaMensualRaw.fuente) == "ireks")))
            clients = list(session.exec(select(Cliente)))
            islands = list(session.exec(select(Isla)))

        island_by_id = {
            str(getattr(row, "isla_id", "") or "").strip(): str(getattr(row, "isla_nombre", "") or "").strip()
            for row in islands
        }
        client_by_id = {
            str(getattr(row, "cliente_id", "") or "").strip(): row
            for row in clients
        }

        buckets: dict[str, dict[str, object]] = {}
        for raw_row in raw_rows:
            row_year = self._period_year(str(getattr(raw_row, "periodo", "") or ""))
            if row_year not in {previous_year, current_year}:
                continue
            cliente_id = str(getattr(raw_row, "cliente_id", "") or "").strip()
            if not cliente_id:
                continue
            client = client_by_id.get(cliente_id)
            island_id = str(getattr(client, "cliente_direccion_isla_id", "") or "").strip() if client is not None else ""
            island_name = island_by_id.get(island_id, "").strip() or "Sin isla"
            customer_name = (
                str(getattr(client, "cliente_nombre_comercial", "") or "").strip()
                or str(getattr(client, "cliente_nombre_fiscal", "") or "").strip()
                or cliente_id
            )
            customer_code = str(getattr(client, "cliente_codigo", "") or "").strip()
            customer_type = self._normalize_customer_type(str(getattr(client, "cliente_tipo", "") or "").strip())
            bucket = buckets.setdefault(
                cliente_id,
                {
                    "cliente_codigo": customer_code,
                    "cliente_nombre": customer_name,
                    "isla": island_name,
                    "cliente_tipo": customer_type,
                    "kg_prev": 0.0,
                    "kg_curr": 0.0,
                },
            )
            kilos = float(getattr(raw_row, "venta_kilos", 0.0) or 0.0) + float(getattr(raw_row, "venta_kilos_sc", 0.0) or 0.0)
            key = "kg_curr" if row_year == current_year else "kg_prev"
            bucket[key] = float(bucket.get(key, 0.0) or 0.0) + kilos

        customer_rows: list[DashboardSalesCustomerRow] = []
        total_kg = 0.0
        total_prev_kg = 0.0
        active_customers = 0
        customers_down = 0
        active_islands_set: set[str] = set()
        for cliente_id, payload in buckets.items():
            kg_prev = float(payload.get("kg_prev", 0.0) or 0.0)
            kg_curr = float(payload.get("kg_curr", 0.0) or 0.0)
            delta_kg = kg_curr - kg_prev
            row = DashboardSalesCustomerRow(
                cliente_id=cliente_id,
                cliente_codigo=str(payload.get("cliente_codigo", "") or "").strip(),
                cliente_nombre=str(payload.get("cliente_nombre", "") or "").strip() or cliente_id,
                isla=str(payload.get("isla", "") or "").strip() or "Sin isla",
                cliente_tipo=str(payload.get("cliente_tipo", "") or "").strip() or "Sin tipo",
                kg_prev=kg_prev,
                kg_curr=kg_curr,
                delta_kg=delta_kg,
                delta_pct=self._pct(delta_kg, kg_prev),
            )
            customer_rows.append(row)
            total_prev_kg += kg_prev
            total_kg += kg_curr
            if kg_curr > 1e-9:
                active_customers += 1
                if row.isla and row.isla != "Sin isla":
                    active_islands_set.add(row.isla)
            if delta_kg < -1e-9:
                customers_down += 1

        delta_kg = total_kg - total_prev_kg
        delta_pct = self._pct(delta_kg, total_prev_kg)

        customer_drop_rows = [row for row in customer_rows if row.delta_kg < -1e-9]
        customer_drop_rows.sort(key=lambda row: (row.delta_kg, row.kg_curr, row.cliente_nombre.casefold(), row.cliente_codigo.casefold()))

        zero_consumption_rows = [row for row in customer_rows if row.kg_prev > 1e-9 and abs(row.kg_curr) <= 1e-9]
        zero_consumption_rows.sort(key=lambda row: (-row.kg_prev, row.cliente_nombre.casefold(), row.cliente_codigo.casefold()))

        island_buckets: dict[str, dict[str, object]] = defaultdict(lambda: {"customers": set(), "kg_prev": 0.0, "kg_curr": 0.0})
        type_buckets: dict[str, dict[str, object]] = defaultdict(lambda: {"customers": set(), "kg_prev": 0.0, "kg_curr": 0.0})
        for row in customer_rows:
            island_bucket = island_buckets[row.isla]
            island_bucket["customers"].add(row.cliente_id)
            island_bucket["kg_prev"] = float(island_bucket["kg_prev"] or 0.0) + row.kg_prev
            island_bucket["kg_curr"] = float(island_bucket["kg_curr"] or 0.0) + row.kg_curr

            type_bucket = type_buckets[row.cliente_tipo]
            type_bucket["customers"].add(row.cliente_id)
            type_bucket["kg_prev"] = float(type_bucket["kg_prev"] or 0.0) + row.kg_prev
            type_bucket["kg_curr"] = float(type_bucket["kg_curr"] or 0.0) + row.kg_curr

        island_rows = [
            DashboardSalesIslandRow(
                isla=isla,
                customers=len(payload["customers"]),
                kg_prev=float(payload["kg_prev"] or 0.0),
                kg_curr=float(payload["kg_curr"] or 0.0),
                delta_kg=float(payload["kg_curr"] or 0.0) - float(payload["kg_prev"] or 0.0),
                share_pct=self._pct(float(payload["kg_curr"] or 0.0), total_kg) if total_kg > 1e-9 else 0.0,
            )
            for isla, payload in island_buckets.items()
        ]
        island_rows.sort(key=lambda row: (-row.kg_curr, row.isla.casefold()))

        type_rows = [
            DashboardSalesTypeRow(
                cliente_tipo=cliente_tipo,
                customers=len(payload["customers"]),
                kg_curr=float(payload["kg_curr"] or 0.0),
                delta_kg=float(payload["kg_curr"] or 0.0) - float(payload["kg_prev"] or 0.0),
                share_pct=self._pct(float(payload["kg_curr"] or 0.0), total_kg) if total_kg > 1e-9 else 0.0,
            )
            for cliente_tipo, payload in type_buckets.items()
        ]
        type_rows.sort(key=lambda row: (-row.kg_curr, row.cliente_tipo.casefold()))

        return SalesDashboardSnapshot(
            year=current_year,
            previous_year=previous_year,
            total_kg=total_kg,
            delta_kg=delta_kg,
            delta_pct=delta_pct,
            active_customers=active_customers,
            active_islands=len(active_islands_set),
            customers_down=customers_down,
            customer_drop_rows=customer_drop_rows[:8],
            island_rows=island_rows[:8],
            type_rows=type_rows[:8],
            zero_consumption_rows=zero_consumption_rows[:8],
            generated_at=datetime.now(),
        )

    @staticmethod
    def _pct(delta: float, base: float) -> float:
        if abs(base) <= 1e-9:
            return 0.0
        return (float(delta or 0.0) / float(base or 0.0)) * 100.0

    @staticmethod
    def _normalize_customer_type(value: str) -> str:
        normalized = str(value or '').strip().lower()
        if not normalized:
            return 'Sin tipo'
        if 'indirect' in normalized:
            return 'Indirecto'
        if 'distrib' in normalized:
            return 'Distribuidor'
        if 'direct' in normalized:
            return 'Directo'
        return normalized.replace('_', ' ').title()

    @staticmethod
    def _period_year(periodo: str) -> int:
        text = str(periodo or '').strip()
        if len(text) >= 4 and text[:4].isdigit():
            return int(text[:4])
        return 0
