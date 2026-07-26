from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, cast

from sqlmodel import Session, select

from app.core.database import engine
from app.models import AlmacenCatalogo, AlmacenMovimiento, Cliente, Distribuidor, IngredienteIreks
from app.services.warehouse_settings_service import WarehouseSettingsService


def _col(expr: object) -> Any:
    return cast(Any, expr)


@dataclass
class DashboardWarehouseRiskRow:
    almacen_id: str
    almacen_nombre: str
    articulo_id: str
    referencia: str
    nombre: str
    lote: str
    caducidad: date | None
    stock_units: float
    stock_kg: float
    state: str


@dataclass
class DashboardWarehouseMovementRow:
    almacen_id: str
    almacen_nombre: str
    articulo_id: str
    referencia: str
    nombre: str
    fecha: date
    units: float
    kg: float
    document_number: str


@dataclass
class DashboardWarehouseStockRow:
    almacen_id: str
    almacen_nombre: str
    article_count: int
    stock_kg: float


@dataclass
class WarehouseDashboardSnapshot:
    year: int
    month: int
    total_stock_kg: float
    risk_items: int
    entries_month_kg: float
    outputs_month_kg: float
    risk_rows: list[DashboardWarehouseRiskRow]
    warehouse_rows: list[DashboardWarehouseStockRow]
    entry_rows: list[DashboardWarehouseMovementRow]
    output_rows: list[DashboardWarehouseMovementRow]
    low_stock_threshold_units: float
    generated_at: datetime


class WarehouseDashboardService:
    def __init__(self, *, warehouse_settings_service: WarehouseSettingsService | None = None) -> None:
        self.warehouse_settings_service = warehouse_settings_service or WarehouseSettingsService()

    def load_snapshot(self, *, today: date | None = None) -> WarehouseDashboardSnapshot:
        target_date = today or date.today()
        with Session(engine) as session:
            moves = list(
                session.exec(
                    select(AlmacenMovimiento).order_by(
                        _col(AlmacenMovimiento.fecha_pedido).desc(),
                        _col(AlmacenMovimiento.id).desc(),
                    )
                )
            )
            article_ids = sorted(
                {
                    str(getattr(row, "articulo_id", "") or "").strip()
                    for row in moves
                    if str(getattr(row, "articulo_id", "") or "").strip()
                }
            )
            items = (
                list(
                    session.exec(
                        select(IngredienteIreks).where(_col(IngredienteIreks.articulo_id).in_(article_ids))
                    )
                )
                if article_ids
                else []
            )
            warehouses = list(session.exec(select(AlmacenCatalogo)))
            clients = list(session.exec(select(Cliente)))
            distributors = list(session.exec(select(Distribuidor)))

        weights = {
            str(getattr(row, "articulo_id", "") or "").strip(): float(getattr(row, "articulo_envase_peso_total", 0.0) or 0.0)
            for row in items
        }
        refs = {
            str(getattr(row, "articulo_id", "") or "").strip(): str(getattr(row, "articulo_referencia_corta", "") or "").strip()
            for row in items
        }
        names = {
            str(getattr(row, "articulo_id", "") or "").strip(): str(getattr(row, "articulo_descripcion", "") or "").strip()
            for row in items
        }
        warehouse_names = self._build_warehouse_name_map(warehouses, clients, distributors)
        low_stock_threshold_units = max(0.0, float(self.warehouse_settings_service.load().get("low_stock_threshold_units") or 0.0))

        stock_rows = self._compute_current_stock_rows(moves)
        total_stock_kg = sum(
            float(row.get("cantidad", 0.0) or 0.0)
            * float(weights.get(str(row.get("articulo_id", "") or "").strip(), 0.0) or 0.0)
            for row in stock_rows
        )

        today_limit = target_date + timedelta(days=30)
        risk_rows: list[DashboardWarehouseRiskRow] = []
        for row in stock_rows:
            articulo_id = str(row.get("articulo_id", "") or "").strip()
            almacen_id = str(row.get("almacen_id", "") or "").strip()
            qty_units = float(row.get("cantidad", 0.0) or 0.0)
            cad = row.get("caducidad")
            state = self._risk_state(
                qty_units=qty_units,
                caducidad=cad,
                today=target_date,
                soon_limit=today_limit,
                low_stock_threshold_units=low_stock_threshold_units,
            )
            if state == "OK":
                continue
            risk_rows.append(
                DashboardWarehouseRiskRow(
                    almacen_id=almacen_id,
                    almacen_nombre=warehouse_names.get(almacen_id, almacen_id or "Sin almacén"),
                    articulo_id=articulo_id,
                    referencia=refs.get(articulo_id, "") or articulo_id,
                    nombre=names.get(articulo_id, "") or articulo_id,
                    lote=str(row.get("lote", "") or "").strip(),
                    caducidad=cad,
                    stock_units=qty_units,
                    stock_kg=qty_units * float(weights.get(articulo_id, 0.0) or 0.0),
                    state=state,
                )
            )
        risk_count = len(risk_rows)
        risk_rows.sort(key=self._risk_sort_key)
        risk_rows = risk_rows[:8]

        warehouse_buckets: dict[str, dict[str, Any]] = {}
        for row in stock_rows:
            almacen_id = str(row.get("almacen_id", "") or "").strip()
            articulo_id = str(row.get("articulo_id", "") or "").strip()
            qty_units = float(row.get("cantidad", 0.0) or 0.0)
            bucket = warehouse_buckets.setdefault(
                almacen_id,
                {
                    "almacen_nombre": warehouse_names.get(almacen_id, almacen_id or "Sin almacén"),
                    "article_ids": set(),
                    "stock_kg": 0.0,
                },
            )
            if articulo_id:
                bucket["article_ids"].add(articulo_id)
            bucket["stock_kg"] += qty_units * float(weights.get(articulo_id, 0.0) or 0.0)
        warehouse_rows = [
            DashboardWarehouseStockRow(
                almacen_id=almacen_id,
                almacen_nombre=str(payload.get("almacen_nombre", "") or "").strip() or almacen_id or "Sin almacén",
                article_count=len(payload.get("article_ids", set())),
                stock_kg=float(payload.get("stock_kg", 0.0) or 0.0),
            )
            for almacen_id, payload in warehouse_buckets.items()
        ]
        warehouse_rows.sort(key=lambda row: (row.stock_kg, row.article_count, row.almacen_nombre.casefold()), reverse=True)
        warehouse_rows = warehouse_rows[:8]

        entry_rows: list[DashboardWarehouseMovementRow] = []
        output_rows: list[DashboardWarehouseMovementRow] = []
        entries_month_kg = 0.0
        outputs_month_kg = 0.0
        for mov in moves:
            mov_date = getattr(mov, "fecha_pedido", None)
            if mov_date is None or mov_date.year != target_date.year or mov_date.month != target_date.month:
                continue
            articulo_id = str(getattr(mov, "articulo_id", "") or "").strip()
            almacen_id = str(getattr(mov, "almacen_id", "") or "").strip()
            qty_units = float(getattr(mov, "cantidad", 0.0) or 0.0)
            qty_kg = abs(qty_units) * float(weights.get(articulo_id, 0.0) or 0.0)
            row = DashboardWarehouseMovementRow(
                almacen_id=almacen_id,
                almacen_nombre=warehouse_names.get(almacen_id, almacen_id or "Sin almacén"),
                articulo_id=articulo_id,
                referencia=refs.get(articulo_id, "") or articulo_id,
                nombre=names.get(articulo_id, "") or articulo_id,
                fecha=mov_date,
                units=abs(qty_units),
                kg=qty_kg,
                document_number=str(getattr(mov, "pedido_albaran_numero", "") or "").strip() or str(getattr(mov, "pedido_numero", "") or "").strip() or "-",
            )
            if qty_units > 0:
                entries_month_kg += qty_kg
                entry_rows.append(row)
            elif qty_units < 0:
                outputs_month_kg += qty_kg
                output_rows.append(row)
        entry_rows.sort(key=lambda row: (row.fecha, row.kg, row.almacen_nombre.casefold(), row.referencia.casefold()), reverse=True)
        output_rows.sort(key=lambda row: (row.fecha, row.kg, row.almacen_nombre.casefold(), row.referencia.casefold()), reverse=True)

        return WarehouseDashboardSnapshot(
            year=target_date.year,
            month=target_date.month,
            total_stock_kg=total_stock_kg,
            risk_items=risk_count,
            entries_month_kg=entries_month_kg,
            outputs_month_kg=outputs_month_kg,
            risk_rows=risk_rows,
            warehouse_rows=warehouse_rows,
            entry_rows=entry_rows[:8],
            output_rows=output_rows[:8],
            low_stock_threshold_units=low_stock_threshold_units,
            generated_at=datetime.now(),
        )

    @staticmethod
    def _risk_state(
        *,
        qty_units: float,
        caducidad: date | None,
        today: date,
        soon_limit: date,
        low_stock_threshold_units: float,
    ) -> str:
        if caducidad is not None and caducidad < today:
            return "Caducado"
        if caducidad is not None and caducidad <= soon_limit:
            return "Caduca pronto"
        if qty_units < low_stock_threshold_units:
            return "Bajo stock"
        return "OK"

    @staticmethod
    def _risk_sort_key(row: DashboardWarehouseRiskRow) -> tuple[int, date, float, str, str]:
        state_order = {"Caducado": 0, "Caduca pronto": 1, "Bajo stock": 2}
        return (
            state_order.get(str(row.state or ""), 9),
            row.caducidad or date.max,
            float(row.stock_units or 0.0),
            row.almacen_nombre.casefold(),
            row.referencia.casefold(),
        )

    @staticmethod
    def _warehouse_display_name(primary: str, secondary: str, fallback: str) -> str:
        label = str(primary or "").strip() or str(secondary or "").strip()
        return label or fallback

    def _build_warehouse_name_map(
        self,
        warehouses: list[AlmacenCatalogo],
        clients: list[Cliente],
        distributors: list[Distribuidor],
    ) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for row in warehouses:
            almacen_id = str(getattr(row, "almacen_id", "") or "").strip()
            if almacen_id:
                mapping[almacen_id] = str(getattr(row, "almacen_nombre", "") or "").strip() or almacen_id
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

    @staticmethod
    def _compute_current_stock_rows(moves: list[AlmacenMovimiento]) -> list[dict[str, Any]]:
        grouped: dict[tuple[str, str, str, date | None], dict[str, Any]] = {}
        for mov in moves:
            almacen_id = str(getattr(mov, "almacen_id", "") or "").strip()
            articulo_id = str(getattr(mov, "articulo_id", "") or "").strip()
            if not articulo_id:
                continue
            lote = str(getattr(mov, "articulo_lote", "") or "").strip()
            cad = getattr(mov, "articulo_caducidad", None)
            key = (almacen_id, articulo_id, lote, cad)
            row = grouped.setdefault(
                key,
                {
                    "almacen_id": almacen_id,
                    "articulo_id": articulo_id,
                    "lote": lote,
                    "caducidad": cad,
                    "cantidad": 0.0,
                    "last_date": None,
                },
            )
            row["cantidad"] = float(row["cantidad"]) + float(getattr(mov, "cantidad", 0.0) or 0.0)
            mov_date = getattr(mov, "fecha_pedido", None)
            if mov_date is not None and (row["last_date"] is None or mov_date > row["last_date"]):
                row["last_date"] = mov_date
        return [row for row in grouped.values() if float(row.get("cantidad", 0.0) or 0.0) > 1e-9]
