from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlmodel import Session, select

from app.core.database import engine as default_engine
from app.models import Cliente, ClienteAgenda, Isla, VentaMensualRaw


@dataclass(slots=True)
class DashboardActivityRow:
    agenda_id: str
    cliente_id: str
    cliente_codigo: int
    cliente_nombre: str
    isla_nombre: str
    fecha_actividad: date
    fecha_seguimiento: date | None
    tipo: str
    estado: str
    resumen: str
    detalle: str
    prioridad: str
    responsable: str
    created_at: datetime
    updated_at: datetime

    @property
    def due_date(self) -> date:
        return self.fecha_actividad


@dataclass(slots=True)
class DashboardReactivationRow:
    cliente_id: str
    cliente_codigo: int
    cliente_nombre: str
    isla_nombre: str
    last_contact: date | None
    current_kg: float
    previous_kg: float
    delta_kg: float
    priority: str


@dataclass(slots=True)
class DashboardIslandRow:
    isla_nombre: str
    pending: int = 0
    postponed: int = 0
    completed: int = 0
    total: int = 0


@dataclass(slots=True)
class DashboardSnapshot:
    pending_today: int = 0
    overdue: int = 0
    completed_today: int = 0
    customers_without_follow_up: int = 0
    today_items: list[DashboardActivityRow] = field(default_factory=list)
    upcoming_tomorrow: list[DashboardActivityRow] = field(default_factory=list)
    upcoming_next_three_days: list[DashboardActivityRow] = field(default_factory=list)
    upcoming_week: list[DashboardActivityRow] = field(default_factory=list)
    reactivation_rows: list[DashboardReactivationRow] = field(default_factory=list)
    island_rows: list[DashboardIslandRow] = field(default_factory=list)
    reactivation_metric_label: str = ""
    generated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(slots=True)
class CustomerDashboardService:
    engine: object = default_engine

    def list_all_activities(self) -> list[DashboardActivityRow]:
        with Session(self.engine) as session:
            customers = {row.cliente_id: row for row in session.exec(select(Cliente))}
            islands = {
                row.isla_id: str(row.isla_nombre or "").strip()
                for row in session.exec(select(Isla))
            }
            agenda_entries = list(
                session.exec(
                    select(ClienteAgenda).order_by(
                        ClienteAgenda.fecha_actividad.desc(),
                        ClienteAgenda.updated_at.desc(),
                        ClienteAgenda.created_at.desc(),
                    )
                )
            )

        rows: list[DashboardActivityRow] = []
        for agenda in agenda_entries:
            customer = customers.get(str(agenda.cliente_id or "").strip())
            if customer is None or not bool(getattr(customer, "activo", True)):
                continue
            isla_nombre = islands.get(str(getattr(customer, "cliente_direccion_isla_id", "") or "").strip(), "")
            rows.append(
                DashboardActivityRow(
                    agenda_id=str(agenda.agenda_id or "").strip(),
                    cliente_id=str(agenda.cliente_id or "").strip(),
                    cliente_codigo=int(getattr(customer, "cliente_codigo", 0) or 0),
                    cliente_nombre=str(getattr(customer, "cliente_nombre_comercial", "") or "").strip(),
                    isla_nombre=isla_nombre,
                    fecha_actividad=agenda.fecha_actividad,
                    fecha_seguimiento=agenda.fecha_seguimiento,
                    tipo=str(agenda.tipo or "").strip(),
                    estado=str(agenda.estado or "").strip(),
                    resumen=str(agenda.resumen or "").strip(),
                    detalle=str(agenda.detalle or "").strip(),
                    prioridad=str(agenda.prioridad or "").strip(),
                    responsable=str(agenda.responsable or "").strip(),
                    created_at=agenda.created_at,
                    updated_at=agenda.updated_at,
                )
            )
        return sorted(rows, key=self._activity_sort_key)

    def load_snapshot(
        self,
        *,
        today: date | None = None,
        horizon_days: int = 7,
        reactivation_days: int = 30,
        reactivation_limit: int = 8,
    ) -> DashboardSnapshot:
        today_value = today or date.today()
        horizon_end = today_value + timedelta(days=max(1, int(horizon_days or 7)))
        reactivation_cutoff = today_value - timedelta(days=max(1, int(reactivation_days or 30)))
        current_period, previous_period = self._monthly_periods(today_value)

        rows = self.list_all_activities()
        active_customers = self._active_customers()
        last_contact_by_customer: dict[str, date] = {}
        sales_by_customer = self._sales_delta_by_customer(current_period=current_period, previous_period=previous_period)

        for row in rows:
            previous = last_contact_by_customer.get(row.cliente_id)
            if previous is None or row.due_date > previous:
                last_contact_by_customer[row.cliente_id] = row.due_date

        today_items = sorted([row for row in rows if row.fecha_actividad == today_value], key=self._today_sort_key)
        overdue = [
            row
            for row in rows
            if row.due_date < today_value and self._state_group(row.estado) not in {"completed", "cancelled"}
        ]
        completed_today = [
            row
            for row in rows
            if self._state_group(row.estado) == "completed"
            and (row.updated_at.date() == today_value or row.fecha_actividad == today_value)
        ]

        upcoming_open = [
            row
            for row in rows
            if today_value < row.due_date <= horizon_end and self._state_group(row.estado) not in {"completed", "cancelled"}
        ]
        upcoming_tomorrow = sorted(
            [row for row in upcoming_open if row.due_date == today_value + timedelta(days=1)],
            key=self._activity_sort_key,
        )
        upcoming_next_three_days = sorted(
            [row for row in upcoming_open if today_value + timedelta(days=2) <= row.due_date <= today_value + timedelta(days=3)],
            key=self._activity_sort_key,
        )
        upcoming_week = sorted(
            [row for row in upcoming_open if today_value + timedelta(days=4) <= row.due_date <= horizon_end],
            key=self._activity_sort_key,
        )

        reactivation_rows: list[DashboardReactivationRow] = []
        for customer in active_customers:
            last_contact = last_contact_by_customer.get(customer["cliente_id"])
            if last_contact is not None and last_contact >= reactivation_cutoff:
                continue
            sales_data = sales_by_customer.get(customer["cliente_id"], {"current_kg": 0.0, "previous_kg": 0.0, "delta_kg": 0.0})
            reactivation_rows.append(
                DashboardReactivationRow(
                    cliente_id=customer["cliente_id"],
                    cliente_codigo=customer["cliente_codigo"],
                    cliente_nombre=customer["cliente_nombre"],
                    isla_nombre=customer["isla_nombre"],
                    last_contact=last_contact,
                    current_kg=float(sales_data["current_kg"]),
                    previous_kg=float(sales_data["previous_kg"]),
                    delta_kg=float(sales_data["delta_kg"]),
                    priority=self._reactivation_priority(last_contact, float(sales_data["delta_kg"])),
                )
            )
        reactivation_rows.sort(
            key=lambda row: (
                row.delta_kg,
                row.last_contact is not None,
                row.last_contact or date.min,
                row.cliente_nombre.lower(),
            )
        )

        island_rows = self._build_island_rows(rows, today_value=today_value, horizon_end=horizon_end)

        return DashboardSnapshot(
            pending_today=sum(1 for row in today_items if self._state_group(row.estado) not in {"completed", "cancelled"}),
            overdue=len(overdue),
            completed_today=len(completed_today),
            customers_without_follow_up=len(reactivation_rows),
            today_items=today_items,
            upcoming_tomorrow=upcoming_tomorrow,
            upcoming_next_three_days=upcoming_next_three_days,
            upcoming_week=upcoming_week,
            reactivation_rows=reactivation_rows[: max(1, int(reactivation_limit or 8))],
            island_rows=island_rows,
            reactivation_metric_label=f"Variación kg · {previous_period} vs {current_period}",
            generated_at=datetime.utcnow(),
        )

    def _active_customers(self) -> list[dict[str, object]]:
        with Session(self.engine) as session:
            customers = list(session.exec(select(Cliente).order_by(Cliente.cliente_nombre_comercial, Cliente.cliente_codigo)))
            islands = {
                row.isla_id: str(row.isla_nombre or "").strip()
                for row in session.exec(select(Isla))
            }

        active_rows: list[dict[str, object]] = []
        for customer in customers:
            if not bool(getattr(customer, "activo", True)):
                continue
            active_rows.append(
                {
                    "cliente_id": str(getattr(customer, "cliente_id", "") or "").strip(),
                    "cliente_codigo": int(getattr(customer, "cliente_codigo", 0) or 0),
                    "cliente_nombre": str(getattr(customer, "cliente_nombre_comercial", "") or "").strip(),
                    "isla_nombre": islands.get(str(getattr(customer, "cliente_direccion_isla_id", "") or "").strip(), ""),
                }
            )
        return active_rows

    def _sales_delta_by_customer(self, *, current_period: str, previous_period: str) -> dict[str, dict[str, float]]:
        with Session(self.engine) as session:
            monthly_rows = list(
                session.exec(
                    select(VentaMensualRaw).where(VentaMensualRaw.periodo.in_([current_period, previous_period]))
                )
            )

        grouped: dict[str, dict[str, float]] = {}
        for row in monthly_rows:
            cliente_id = str(getattr(row, "cliente_id", "") or "").strip()
            if not cliente_id:
                continue
            bucket = grouped.setdefault(cliente_id, {"current_kg": 0.0, "previous_kg": 0.0, "delta_kg": 0.0})
            kilos = float(getattr(row, "venta_kilos", 0.0) or 0.0)
            if str(getattr(row, "periodo", "") or "").strip() == current_period:
                bucket["current_kg"] += kilos
            elif str(getattr(row, "periodo", "") or "").strip() == previous_period:
                bucket["previous_kg"] += kilos

        for bucket in grouped.values():
            bucket["delta_kg"] = bucket["current_kg"] - bucket["previous_kg"]
        return grouped

    def _build_island_rows(
        self,
        rows: list[DashboardActivityRow],
        *,
        today_value: date,
        horizon_end: date,
    ) -> list[DashboardIslandRow]:
        grouped: dict[str, DashboardIslandRow] = {}
        for row in rows:
            if not (today_value <= row.due_date <= horizon_end):
                continue
            state_group = self._state_group(row.estado)
            if state_group == "cancelled":
                continue
            label = row.isla_nombre or "Sin isla"
            island_row = grouped.setdefault(label, DashboardIslandRow(isla_nombre=label))
            if state_group == "completed":
                island_row.completed += 1
            elif state_group == "postponed":
                island_row.postponed += 1
            else:
                island_row.pending += 1
            island_row.total += 1

        return sorted(grouped.values(), key=lambda row: (-row.total, row.isla_nombre.lower()))

    @staticmethod
    def _reactivation_priority(last_contact: date | None, delta_kg: float) -> str:
        if last_contact is None and delta_kg <= 0:
            return "Alta"
        if delta_kg <= -100.0:
            return "Alta"
        if delta_kg < 0:
            return "Media"
        return "Baja"

    @staticmethod
    def _monthly_periods(today_value: date) -> tuple[str, str]:
        current_month = date(today_value.year, today_value.month, 1)
        previous_month_end = current_month - timedelta(days=1)
        previous_month = date(previous_month_end.year, previous_month_end.month, 1)
        return current_month.strftime("%Y-%m"), previous_month.strftime("%Y-%m")

    @staticmethod
    def _state_group(state: str) -> str:
        normalized = str(state or "").strip().lower()
        if normalized == "hecho":
            return "completed"
        if normalized == "aplazado":
            return "postponed"
        if normalized == "cancelado":
            return "cancelled"
        return "pending"

    @classmethod
    def _activity_sort_key(cls, row: DashboardActivityRow) -> tuple[date, int, int, str]:
        return (
            row.due_date,
            cls._state_sort_rank(row.estado),
            cls._priority_sort_rank(row.prioridad),
            row.cliente_nombre.lower(),
        )

    @classmethod
    def _today_sort_key(cls, row: DashboardActivityRow) -> tuple[int, int, str]:
        return (
            cls._state_sort_rank(row.estado),
            cls._priority_sort_rank(row.prioridad),
            row.cliente_nombre.lower(),
        )

    @staticmethod
    def _state_sort_rank(state: str) -> int:
        group = CustomerDashboardService._state_group(state)
        if group == "pending":
            return 0
        if group == "postponed":
            return 1
        if group == "completed":
            return 2
        return 3

    @staticmethod
    def _priority_sort_rank(priority: str) -> int:
        normalized = str(priority or "").strip().lower()
        if normalized == "alta":
            return 0
        if normalized == "media":
            return 1
        if normalized == "baja":
            return 3
        return 2
