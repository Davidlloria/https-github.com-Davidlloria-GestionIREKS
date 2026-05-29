from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlmodel import Session, select

from app.core.database import engine
from app.models import IngredienteIreks, Pedido, PedidoItem


@dataclass
class ProductMonthlyOrderRow:
    year: int
    month: int
    order_count: int
    quantity: float
    kg: float
    last_order_date: date | None
    last_order_number: str


@dataclass
class AnnualProductOrderRow:
    articulo_id: str
    referencia: str
    descripcion: str
    monthly_quantities: list[float]
    total_quantity: float
    total_kg: float
    order_count: int
    last_order_date: date | None


@dataclass
class ProductOrderDetailRow:
    pedido_id: str
    pedido_numero: str
    pedido_albaran_numero: str
    fecha: date | None
    quantity: float
    kg: float


class MonthlyOrdersService:
    def product_monthly_rows_for(
        self,
        *,
        articulo_id: str,
        almacen_id: str = "",
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[ProductMonthlyOrderRow]:
        with Session(engine) as session:
            return self.product_monthly_rows(
                session,
                articulo_id=articulo_id,
                almacen_id=almacen_id,
                date_from=date_from,
                date_to=date_to,
            )

    def annual_product_matrix_for(
        self,
        *,
        year: int,
        almacen_id: str = "",
        search: str = "",
    ) -> list[AnnualProductOrderRow]:
        with Session(engine) as session:
            return self.annual_product_matrix(session, year=year, almacen_id=almacen_id, search=search)

    def product_order_details_for(self, *, articulo_id: str, almacen_id: str = "") -> list[ProductOrderDetailRow]:
        with Session(engine) as session:
            return self.product_order_details(session, articulo_id=articulo_id, almacen_id=almacen_id)

    def available_years_for(self, *, almacen_id: str = "") -> list[int]:
        with Session(engine) as session:
            return self.available_years(session, almacen_id=almacen_id)

    def product_monthly_rows(
        self,
        session: Session,
        *,
        articulo_id: str,
        almacen_id: str = "",
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[ProductMonthlyOrderRow]:
        target_articulo_id = str(articulo_id or "").strip()
        if not target_articulo_id:
            return []

        item_rows = self._load_order_items(
            session,
            articulo_id=target_articulo_id,
            almacen_id=almacen_id,
            date_from=date_from,
            date_to=date_to,
        )
        product = session.exec(
            select(IngredienteIreks).where(IngredienteIreks.articulo_id == target_articulo_id)
        ).first()
        unit_kg = float(getattr(product, "articulo_envase_peso_total", 0.0) or 0.0)

        grouped: dict[tuple[int, int], dict[str, Any]] = {}
        for item, pedido in item_rows:
            row_date = self._item_date(item, pedido)
            if row_date is None:
                continue
            key = (row_date.year, row_date.month)
            bucket = grouped.setdefault(
                key,
                {
                    "order_ids": set(),
                    "quantity": 0.0,
                    "last_order_date": None,
                    "last_order_number": "",
                },
            )
            pedido_id = str(getattr(item, "pedido_id", "") or "").strip()
            if pedido_id:
                bucket["order_ids"].add(pedido_id)
            bucket["quantity"] += float(getattr(item, "articulo_cantidad", 0.0) or 0.0)
            if bucket["last_order_date"] is None or row_date > bucket["last_order_date"]:
                bucket["last_order_date"] = row_date
                bucket["last_order_number"] = str(
                    getattr(item, "pedido_numero", "") or getattr(pedido, "pedido_numero", "") or ""
                ).strip()

        result: list[ProductMonthlyOrderRow] = []
        for year, month in sorted(grouped.keys(), reverse=True):
            bucket = grouped[(year, month)]
            quantity = float(bucket["quantity"] or 0.0)
            result.append(
                ProductMonthlyOrderRow(
                    year=year,
                    month=month,
                    order_count=len(bucket["order_ids"]),
                    quantity=quantity,
                    kg=quantity * unit_kg,
                    last_order_date=bucket["last_order_date"],
                    last_order_number=str(bucket["last_order_number"] or ""),
                )
            )
        return result

    def annual_product_matrix(
        self,
        session: Session,
        *,
        year: int,
        almacen_id: str = "",
        search: str = "",
    ) -> list[AnnualProductOrderRow]:
        if year <= 0:
            return []
        date_from = date(year, 1, 1)
        date_to = date(year, 12, 31)
        item_rows = self._load_order_items(
            session,
            almacen_id=almacen_id,
            date_from=date_from,
            date_to=date_to,
        )
        articulo_ids = sorted(
            {
                str(getattr(item, "articulo_id", "") or "").strip()
                for item, _pedido in item_rows
                if str(getattr(item, "articulo_id", "") or "").strip()
            }
        )
        products = (
            list(session.exec(select(IngredienteIreks).where(IngredienteIreks.articulo_id.in_(articulo_ids))))
            if articulo_ids
            else []
        )
        product_by_id = {str(row.articulo_id or "").strip(): row for row in products}
        terms = [term for term in str(search or "").strip().lower().split() if term]

        grouped: dict[str, dict[str, Any]] = {}
        for item, pedido in item_rows:
            row_date = self._item_date(item, pedido)
            if row_date is None:
                continue
            articulo_id = str(getattr(item, "articulo_id", "") or "").strip()
            if not articulo_id:
                continue
            product = product_by_id.get(articulo_id)
            referencia = str(getattr(product, "articulo_referencia_corta", "") or "").strip()
            if not referencia:
                referencia = str(getattr(product, "articulo_referencia", "") or "").strip()
            descripcion = str(getattr(product, "articulo_descripcion", "") or "").strip()
            searchable = " ".join([articulo_id, referencia, descripcion]).lower()
            if terms and not all(term in searchable for term in terms):
                continue

            bucket = grouped.setdefault(
                articulo_id,
                {
                    "referencia": referencia or articulo_id,
                    "descripcion": descripcion or articulo_id,
                    "unit_kg": float(getattr(product, "articulo_envase_peso_total", 0.0) or 0.0),
                    "months": [0.0 for _ in range(12)],
                    "order_ids": set(),
                    "last_order_date": None,
                },
            )
            quantity = float(getattr(item, "articulo_cantidad", 0.0) or 0.0)
            bucket["months"][row_date.month - 1] += quantity
            pedido_id = str(getattr(item, "pedido_id", "") or "").strip()
            if pedido_id:
                bucket["order_ids"].add(pedido_id)
            if bucket["last_order_date"] is None or row_date > bucket["last_order_date"]:
                bucket["last_order_date"] = row_date

        result: list[AnnualProductOrderRow] = []
        for articulo_id, bucket in grouped.items():
            monthly = [float(value or 0.0) for value in bucket["months"]]
            total_quantity = sum(monthly)
            result.append(
                AnnualProductOrderRow(
                    articulo_id=articulo_id,
                    referencia=str(bucket["referencia"] or articulo_id),
                    descripcion=str(bucket["descripcion"] or articulo_id),
                    monthly_quantities=monthly,
                    total_quantity=total_quantity,
                    total_kg=total_quantity * float(bucket["unit_kg"] or 0.0),
                    order_count=len(bucket["order_ids"]),
                    last_order_date=bucket["last_order_date"],
                )
            )
        return sorted(result, key=lambda row: (row.descripcion.lower(), row.referencia.lower()))

    def product_order_details(
        self,
        session: Session,
        *,
        articulo_id: str,
        almacen_id: str = "",
    ) -> list[ProductOrderDetailRow]:
        target_articulo_id = str(articulo_id or "").strip()
        if not target_articulo_id:
            return []
        item_rows = self._load_order_items(
            session,
            articulo_id=target_articulo_id,
            almacen_id=almacen_id,
        )
        product = session.exec(
            select(IngredienteIreks).where(IngredienteIreks.articulo_id == target_articulo_id)
        ).first()
        unit_kg = float(getattr(product, "articulo_envase_peso_total", 0.0) or 0.0)

        result: list[ProductOrderDetailRow] = []
        for item, pedido in item_rows:
            quantity = float(getattr(item, "articulo_cantidad", 0.0) or 0.0)
            result.append(
                ProductOrderDetailRow(
                    pedido_id=str(getattr(item, "pedido_id", "") or "").strip(),
                    pedido_numero=str(
                        getattr(item, "pedido_numero", "") or getattr(pedido, "pedido_numero", "") or ""
                    ).strip(),
                    pedido_albaran_numero=str(
                        getattr(item, "pedido_albaran_numero", "")
                        or getattr(pedido, "pedido_albaran_numero", "")
                        or ""
                    ).strip(),
                    fecha=self._item_date(item, pedido),
                    quantity=quantity,
                    kg=quantity * unit_kg,
                )
            )
        return result

    def available_years(self, session: Session, *, almacen_id: str = "") -> list[int]:
        item_rows = self._load_order_items(session, almacen_id=almacen_id)
        years = {
            row_date.year
            for item, pedido in item_rows
            for row_date in [self._item_date(item, pedido)]
            if row_date is not None
        }
        return sorted(years, reverse=True)

    def _load_order_items(
        self,
        session: Session,
        *,
        articulo_id: str = "",
        almacen_id: str = "",
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[tuple[PedidoItem, Pedido]]:
        stmt = select(PedidoItem, Pedido).join(Pedido, Pedido.pedido_id == PedidoItem.pedido_id)
        target_articulo_id = str(articulo_id or "").strip()
        target_almacen_id = str(almacen_id or "").strip()
        if target_articulo_id:
            stmt = stmt.where(PedidoItem.articulo_id == target_articulo_id)
        if target_almacen_id:
            stmt = stmt.where(Pedido.almacen_id == target_almacen_id)
        if date_from is not None:
            stmt = stmt.where(PedidoItem.pedido_item_fecha >= date_from)
        if date_to is not None:
            stmt = stmt.where(PedidoItem.pedido_item_fecha <= date_to)
        stmt = stmt.order_by(PedidoItem.pedido_item_fecha.desc(), PedidoItem.pedido_id.desc())
        return [(item, pedido) for item, pedido in session.exec(stmt)]

    def _item_date(self, item: PedidoItem, pedido: Pedido) -> date | None:
        value = getattr(item, "pedido_item_fecha", None) or getattr(pedido, "pedido_fecha", None)
        return value if isinstance(value, date) else None
