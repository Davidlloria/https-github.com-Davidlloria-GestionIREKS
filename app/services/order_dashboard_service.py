from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, cast

from sqlmodel import Session, select

from app.core.database import engine
from app.models import AlbaranItem, Cliente, Distribuidor, IngredienteIreks, Pedido, PedidoPendiente
from app.services.order_query_service import OrderQueryService


@dataclass
class DashboardOrderRow:
    pedido_id: str
    almacen_id: str
    almacen_nombre: str
    pedido_fecha: date
    pedido_numero: str
    semana: int
    ordered_kg: float
    received_kg: float
    pending_kg: float
    incident_kg: float
    status: str
    last_receipt: date | None


@dataclass
class DashboardOrdersWarehouseRow:
    almacen_id: str
    almacen_nombre: str
    open_orders: int
    pending_kg: float
    last_receipt: date | None


@dataclass
class DashboardPendingArticleRow:
    pedido_id: str
    pedido_fecha: date
    pedido_numero: str
    articulo_id: str
    articulo_label: str
    article_name: str
    pending_kg: float


@dataclass
class DashboardOrdersStateRow:
    status: str
    count: int
    kg: float


@dataclass
class OrderDashboardSnapshot:
    year: int
    total_orders: int
    received_kg: float
    pending_kg: float
    incident_orders: int
    recent_orders: list[DashboardOrderRow]
    pending_orders: list[DashboardPendingArticleRow]
    warehouse_rows: list[DashboardOrdersWarehouseRow]
    state_rows: list[DashboardOrdersStateRow]
    generated_at: datetime


class OrderDashboardService:
    def __init__(self, *, order_query_service: OrderQueryService | None = None) -> None:
        self.order_query_service = order_query_service or OrderQueryService()

    def load_snapshot(self, *, year: int | None = None) -> OrderDashboardSnapshot:
        target_year = int(year or date.today().year)
        pedidos = [
            row
            for row in self.order_query_service.list_raw_orders()
            if self.order_query_service.parse_date(getattr(row, "pedido_fecha", None)).year == target_year
        ]
        pedido_ids = [str(getattr(row, "pedido_id", "") or "").strip() for row in pedidos if str(getattr(row, "pedido_id", "") or "").strip()]
        if not pedido_ids:
            return OrderDashboardSnapshot(
                year=target_year,
                total_orders=0,
                received_kg=0.0,
                pending_kg=0.0,
                incident_orders=0,
                recent_orders=[],
                pending_orders=[],
                warehouse_rows=[],
                state_rows=[],
                generated_at=datetime.now(),
            )

        with Session(engine) as session:
            clients = list(session.exec(select(Cliente)))
            distributors = list(session.exec(select(Distribuidor)))
            albaran_items = list(
                session.exec(
                    select(AlbaranItem).where(cast(Any, AlbaranItem.pedido_id).in_(pedido_ids))
                )
            )
            pendientes = list(
                session.exec(
                    select(PedidoPendiente).where(cast(Any, PedidoPendiente.pedido_id).in_(pedido_ids))
                )
            )
            article_ids = sorted(
                {
                    str(getattr(row, "articulo_id", "") or "").strip()
                    for row in [*albaran_items, *pendientes]
                    if str(getattr(row, "articulo_id", "") or "").strip()
                }
            )
            articles = (
                list(
                    session.exec(
                        select(IngredienteIreks).where(cast(Any, IngredienteIreks.articulo_id).in_(article_ids))
                    )
                )
                if article_ids
                else []
            )

        weights = {
            str(getattr(row, "articulo_id", "") or "").strip(): float(getattr(row, "articulo_envase_peso_total", 0.0) or 0.0)
            for row in articles
        }
        article_labels = {
            str(getattr(row, "articulo_id", "") or "").strip(): self._article_display_label(row)
            for row in articles
        }
        warehouse_names = self._build_warehouse_name_map(clients, distributors)
        pedidos_by_id = {
            str(getattr(row, "pedido_id", "") or "").strip(): row
            for row in pedidos
        }
        ordered_by_id = self.order_query_service.pedido_totals_kg(pedido_ids)
        received_by_id: dict[str, float] = defaultdict(float)
        pending_by_id: dict[str, float] = defaultdict(float)
        incident_by_id: dict[str, float] = defaultdict(float)
        last_receipt_by_id: dict[str, date] = {}
        pending_article_rows: list[DashboardPendingArticleRow] = []

        for row in albaran_items:
            pedido_id = str(getattr(row, "pedido_id", "") or "").strip()
            articulo_id = str(getattr(row, "articulo_id", "") or "").strip()
            qty = float(getattr(row, "articulo_cantidad", 0.0) or 0.0)
            received_by_id[pedido_id] += qty * weights.get(articulo_id, 0.0)
            received_date = self.order_query_service.parse_date(getattr(row, "albaran_fecha", None))
            current = last_receipt_by_id.get(pedido_id)
            if current is None or received_date > current:
                last_receipt_by_id[pedido_id] = received_date

        for row in pendientes:
            pedido_id = str(getattr(row, "pedido_id", "") or "").strip()
            articulo_id = str(getattr(row, "articulo_id", "") or "").strip()
            qty_pending = float(getattr(row, "cantidad_pendiente", 0.0) or 0.0)
            estado = str(getattr(row, "estado", "") or "").strip().lower()
            weight = weights.get(articulo_id, 0.0)
            if qty_pending > 1e-9 and estado != "exceso":
                pending_kg = qty_pending * weight
                pending_by_id[pedido_id] += pending_kg
                pedido = pedidos_by_id.get(pedido_id)
                if pedido is not None and pending_kg > 1e-9:
                    pending_article_rows.append(
                        DashboardPendingArticleRow(
                            pedido_id=pedido_id,
                            pedido_fecha=self.order_query_service.parse_date(getattr(pedido, "pedido_fecha", None)),
                            pedido_numero=str(getattr(pedido, "pedido_numero", "") or "").strip() or "S/N",
                            articulo_id=articulo_id,
                            articulo_label=article_labels.get(articulo_id, articulo_id or "S/N"),
                            article_name=article_labels.get(articulo_id, articulo_id or "S/N"),
                            pending_kg=pending_kg,
                        )
                    )
            if estado == "exceso" or qty_pending < -1e-9:
                incident_by_id[pedido_id] += abs(qty_pending) * weight if weight > 0 else abs(qty_pending)

        rows: list[DashboardOrderRow] = []
        for pedido in pedidos:
            pedido_id = str(getattr(pedido, "pedido_id", "") or "").strip()
            pedido_fecha = self.order_query_service.parse_date(getattr(pedido, "pedido_fecha", None))
            ordered_kg = float(ordered_by_id.get(pedido_id, 0.0))
            received_kg = float(received_by_id.get(pedido_id, 0.0))
            pending_kg = float(pending_by_id.get(pedido_id, 0.0))
            incident_kg = float(incident_by_id.get(pedido_id, 0.0))
            if pending_kg <= 1e-9 and ordered_kg > received_kg and received_kg > 0:
                pending_kg = max(ordered_kg - received_kg, 0.0)
            if incident_kg > 1e-9:
                status = "incidencia"
            elif pending_kg <= 1e-9 and received_kg > 1e-9:
                status = "completado"
            elif received_kg > 1e-9:
                status = "parcial"
            else:
                status = "pendiente"
            rows.append(
                DashboardOrderRow(
                    pedido_id=pedido_id,
                    almacen_id=str(getattr(pedido, "almacen_id", "") or "").strip(),
                    almacen_nombre=warehouse_names.get(str(getattr(pedido, "almacen_id", "") or "").strip(), str(getattr(pedido, "almacen_id", "") or "").strip()),
                    pedido_fecha=pedido_fecha,
                    pedido_numero=str(getattr(pedido, "pedido_numero", "") or "").strip() or "S/N",
                    semana=int(pedido_fecha.isocalendar()[1]),
                    ordered_kg=ordered_kg,
                    received_kg=received_kg,
                    pending_kg=pending_kg,
                    incident_kg=incident_kg,
                    status=status,
                    last_receipt=last_receipt_by_id.get(pedido_id),
                )
            )

        recent_orders = sorted(rows, key=lambda row: (row.pedido_fecha, row.pedido_numero, row.pedido_id), reverse=True)[:8]
        pending_orders = sorted(
            pending_article_rows,
            key=lambda row: (-row.pending_kg, row.pedido_fecha, row.pedido_numero, row.articulo_label.casefold()),
        )[:8]

        warehouse_buckets: dict[str, DashboardOrdersWarehouseRow] = {}
        for row in rows:
            if row.pending_kg <= 1e-9 and row.status != "incidencia":
                continue
            key = row.almacen_id or row.almacen_nombre
            current = warehouse_buckets.get(key)
            if current is None:
                current = DashboardOrdersWarehouseRow(
                    almacen_id=row.almacen_id,
                    almacen_nombre=row.almacen_nombre,
                    open_orders=0,
                    pending_kg=0.0,
                    last_receipt=row.last_receipt,
                )
                warehouse_buckets[key] = current
            current.open_orders += 1
            current.pending_kg += row.pending_kg
            if row.last_receipt and (current.last_receipt is None or row.last_receipt > current.last_receipt):
                current.last_receipt = row.last_receipt
        warehouse_rows = sorted(
            warehouse_buckets.values(),
            key=lambda row: (row.pending_kg, row.open_orders, row.almacen_nombre.casefold()),
            reverse=True,
        )[:8]

        state_counts: dict[str, int] = defaultdict(int)
        state_kgs: dict[str, float] = defaultdict(float)
        for row in rows:
            state_counts[row.status] += 1
            state_kgs[row.status] += max(row.ordered_kg, row.received_kg)
        ordered_states = [
            ("pendiente", "Pendiente"),
            ("parcial", "Parcial"),
            ("completado", "Completado"),
            ("incidencia", "Incidencia"),
        ]
        state_rows = [
            DashboardOrdersStateRow(status=label, count=int(state_counts.get(key, 0)), kg=float(state_kgs.get(key, 0.0)))
            for key, label in ordered_states
            if int(state_counts.get(key, 0)) > 0
        ]

        return OrderDashboardSnapshot(
            year=target_year,
            total_orders=len(rows),
            received_kg=sum(row.received_kg for row in rows),
            pending_kg=sum(row.pending_kg for row in rows),
            incident_orders=sum(1 for row in rows if row.status == "incidencia"),
            recent_orders=recent_orders,
            pending_orders=pending_orders,
            warehouse_rows=warehouse_rows,
            state_rows=state_rows,
            generated_at=datetime.now(),
        )

    @staticmethod
    def _article_display_label(row: IngredienteIreks) -> str:
        name = str(getattr(row, "articulo_descripcion", "") or "").strip()
        return name or str(getattr(row, "articulo_id", "") or "").strip()

    @staticmethod
    def _warehouse_display_name(primary: str, secondary: str, fallback: str) -> str:
        label = str(primary or "").strip() or str(secondary or "").strip()
        return label or fallback

    def _build_warehouse_name_map(self, clients: list[Cliente], distributors: list[Distribuidor]) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for row in distributors:
            distribuidor_id = str(getattr(row, "distribuidor_id", "") or "").strip()
            if not distribuidor_id:
                continue
            mapping[distribuidor_id] = self._warehouse_display_name(
                str(getattr(row, "distribuidor_nombre_comercial", "") or "").strip(),
                str(getattr(row, "distribuidor_razon_social", "") or "").strip(),
                distribuidor_id,
            )
        for row in clients:
            cliente_id = str(getattr(row, "cliente_id", "") or "").strip()
            if not cliente_id:
                continue
            mapping[cliente_id] = self._warehouse_display_name(
                str(getattr(row, "cliente_nombre_comercial", "") or "").strip(),
                str(getattr(row, "cliente_nombre_fiscal", "") or "").strip(),
                cliente_id,
            )
        return mapping
