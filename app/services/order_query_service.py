from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, cast

from sqlmodel import Session, select

from app.core.database import engine
from app.core.pagination import DEFAULT_PAGE_LIMIT, page_items
from app.models import Albaran, AlbaranItem, Cliente, Fabricante, Familia, IngredienteIreks, Pedido, PedidoItem, PedidoPendiente, Subfamilia
from app.schemas.orders import (
    OrderItemListResponse,
    OrderItemRead,
    OrderListItem,
    OrderListResponse,
    OrderPendingListResponse,
    OrderPendingRead,
    OrderRead,
)


@dataclass
class OrderListRow:
    pedido_id: str
    almacen_id: str
    almacen_nombre: str
    pedido_fecha: date
    pedido_numero: str
    pedido_albaran_numero: str
    pedido_factura_numero: str
    pedido_ref: str
    pedido_estado: str
    semana: int
    total_kg: float


@dataclass
class PendingAggregateRow:
    pedido_id: str
    articulo_id: str
    cantidad_pedida: float
    cantidad_recibida: float
    cantidad_pendiente: float
    estado: str = "pendiente"


@dataclass
class WarehouseFilterOption:
    label: str
    value: str


class OrderQueryService:
    def list_active_ingredients(self) -> list[IngredienteIreks]:
        with Session(engine) as session:
            return list(
                session.exec(
                    select(IngredienteIreks)
                    .where(IngredienteIreks.articulo_status_en_lista == True)  # noqa: E712
                    .order_by(IngredienteIreks.articulo_descripcion, IngredienteIreks.articulo_referencia)
                )
            )

    def order_dialog_catalogs(
        self,
        almacen_id: str,
        preload_history: bool,
        *,
        reference_date: date | None = None,
        exclude_pedido_id: str = "",
    ) -> tuple[list[IngredienteIreks], list[Fabricante], list[Familia], list[Subfamilia], dict[str, float], dict[str, float]]:
        clean_exclude_pedido_id = str(exclude_pedido_id or "").strip()
        clean_reference_date = reference_date or date.today()
        with Session(engine) as session:
            rows = list(
                session.exec(
                    select(IngredienteIreks)
                    .where(IngredienteIreks.articulo_status_en_lista == True)  # noqa: E712
                    .order_by(IngredienteIreks.articulo_descripcion, IngredienteIreks.articulo_referencia)
                )
            )
            fabricantes = list(session.exec(select(Fabricante).order_by(Fabricante.fabricante_nombre)))
            familias = list(session.exec(select(Familia).order_by(Familia.articulo_familia_nombre)))
            subfamilias = list(session.exec(select(Subfamilia).order_by(Subfamilia.articulo_subfamilia_nombre)))
            prev_qty_by_articulo: dict[str, float] = {}
            pending_qty_by_articulo: dict[str, float] = {}
            if preload_history:
                prev_order_query = select(Pedido).where(
                    Pedido.almacen_id == almacen_id,
                    Pedido.pedido_fecha <= clean_reference_date,
                )
                if clean_exclude_pedido_id:
                    prev_order_query = prev_order_query.where(Pedido.pedido_id != clean_exclude_pedido_id)
                prev_order = session.exec(
                    prev_order_query.order_by(
                        Pedido.pedido_fecha.desc(),
                        Pedido.pedido_numero.desc(),
                        Pedido.pedido_id.desc(),
                    )
                ).first()
                if prev_order is not None:
                    prev_order_id = str(getattr(prev_order, "pedido_id", "") or "").strip()
                    prev_received_rows = list(
                        session.exec(
                            select(AlbaranItem)
                            .where(AlbaranItem.pedido_id == prev_order_id)
                            .order_by(AlbaranItem.albaran_fecha, AlbaranItem.albaran_numero, AlbaranItem.item_id)
                        )
                    )
                    for item in prev_received_rows:
                        articulo_id = str(getattr(item, "articulo_id", "") or "").strip()
                        if not articulo_id:
                            continue
                        prev_qty_by_articulo[articulo_id] = prev_qty_by_articulo.get(articulo_id, 0.0) + float(
                            getattr(item, "articulo_cantidad", 0.0) or 0.0
                        )
                pendientes_rows = list(
                    session.exec(
                        select(PedidoPendiente, Pedido)
                        .join(Pedido, Pedido.pedido_id == PedidoPendiente.pedido_id)
                        .where(
                            Pedido.almacen_id == almacen_id,
                            Pedido.pedido_fecha < clean_reference_date,
                            Pedido.pedido_id != clean_exclude_pedido_id,
                            PedidoPendiente.estado == "pendiente",
                        )
                    )
                )
                for pending, _pedido in pendientes_rows:
                    articulo_id = str(getattr(pending, "articulo_id", "") or "").strip()
                    if not articulo_id:
                        continue
                    qty = float(getattr(pending, "cantidad_pendiente", 0.0) or 0.0)
                    if qty > 0:
                        pending_qty_by_articulo[articulo_id] = pending_qty_by_articulo.get(articulo_id, 0.0) + qty
        return rows, fabricantes, familias, subfamilias, prev_qty_by_articulo, pending_qty_by_articulo

    def resolve_warehouse_id(self, raw_value: str) -> str:
        candidate = str(raw_value or "").strip()
        if not candidate:
            return ""
        with Session(engine) as session:
            direct = session.get(Cliente, candidate)
            if direct is not None:
                return str(direct.cliente_id or "").strip()

            rows = list(session.exec(select(Cliente)))
        normalized = candidate.strip().lower()
        for row in rows:
            nombre_comercial = str(getattr(row, "cliente_nombre_comercial", "") or "").strip()
            nombre_fiscal = str(getattr(row, "cliente_nombre_fiscal", "") or "").strip()
            if normalized in {nombre_comercial.lower(), nombre_fiscal.lower()}:
                tipo = str(getattr(row, "cliente_tipo", "") or "").strip().lower()
                if tipo in {"distribuidor", "directo", "cliente directo", "cliente_directo"}:
                    return str(getattr(row, "cliente_id", "") or "").strip()
        return candidate

    def get_order_edit_payload(self, pedido_id: str) -> tuple[Pedido, dict[str, float]]:
        with Session(engine) as session:
            pedido = session.get(Pedido, pedido_id)
            if pedido is None:
                raise ValueError("Pedido no encontrado.")
            rows = list(session.exec(select(PedidoItem).where(PedidoItem.pedido_id == pedido_id)))
        qty_by_articulo: dict[str, float] = {}
        for item in rows:
            articulo_id = str(getattr(item, "articulo_id", "") or "").strip()
            if not articulo_id:
                continue
            qty_by_articulo[articulo_id] = qty_by_articulo.get(articulo_id, 0.0) + float(
                getattr(item, "articulo_cantidad", 0.0) or 0.0
            )
        return pedido, qty_by_articulo

    def detail_payload(self, pedido_id: str) -> OrderRead | None:
        clean_pedido_id = str(pedido_id or "").strip()
        if not clean_pedido_id:
            return None
        with Session(engine) as session:
            row = session.get(Pedido, clean_pedido_id)
        return OrderRead.from_entity(row) if row is not None else None

    def _build_operational_assignment(
        self,
        session: Session,
        pedido_id: str,
    ) -> tuple[Pedido | None, dict[tuple[str, str], dict[str, float]], dict[str, Pedido]]:
        clean_pedido_id = str(pedido_id or "").strip()
        if not clean_pedido_id:
            return None, {}, {}
        pedido = session.get(Pedido, clean_pedido_id)
        if pedido is None:
            return None, {}, {}
        almacen_id = str(getattr(pedido, "almacen_id", "") or "").strip()
        if not almacen_id:
            return pedido, {}, {}

        pedidos_almacen = list(
            session.exec(
                select(Pedido)
                .where(Pedido.almacen_id == almacen_id)
                .order_by(cast(Any, Pedido.pedido_fecha), Pedido.pedido_numero, Pedido.pedido_id)
            )
        )
        pedido_by_id = {
            str(getattr(row, "pedido_id", "") or "").strip(): row
            for row in pedidos_almacen
            if str(getattr(row, "pedido_id", "") or "").strip()
        }
        pedido_ids = list(pedido_by_id.keys())
        if not pedido_ids:
            return pedido, {}, pedido_by_id

        ordered_rows = list(
            session.exec(select(PedidoItem).where(cast(Any, PedidoItem.pedido_id).in_(pedido_ids)))
        )
        ordered_by_article_pedido: dict[str, dict[str, float]] = {}
        for row in ordered_rows:
            row_pedido_id = str(getattr(row, "pedido_id", "") or "").strip()
            articulo_id = str(getattr(row, "articulo_id", "") or "").strip()
            if not row_pedido_id or not articulo_id:
                continue
            by_pedido = ordered_by_article_pedido.setdefault(articulo_id, {})
            by_pedido[row_pedido_id] = by_pedido.get(row_pedido_id, 0.0) + float(getattr(row, "articulo_cantidad", 0.0) or 0.0)

        stats: dict[tuple[str, str], dict[str, float]] = {}
        open_by_article: dict[str, list[dict[str, float | str]]] = {}
        pedido_order = {pid: idx for idx, pid in enumerate(pedido_ids)}
        for articulo_id, by_pedido in ordered_by_article_pedido.items():
            for row_pedido_id in sorted(by_pedido.keys(), key=lambda pid: pedido_order.get(pid, 10**9)):
                ordered_qty = float(by_pedido.get(row_pedido_id, 0.0) or 0.0)
                if ordered_qty <= 1e-9:
                    continue
                stats[(row_pedido_id, articulo_id)] = {"ordered": ordered_qty, "received": 0.0}
                open_by_article.setdefault(articulo_id, []).append({"pedido_id": row_pedido_id, "remaining": ordered_qty})

        albaran_rows = list(
            session.exec(
                select(AlbaranItem, Albaran)
                .outerjoin(Albaran, cast(Any, Albaran.albaran_id == AlbaranItem.albaran_id))
                .where(cast(Any, AlbaranItem.pedido_id).in_(pedido_ids))
                .order_by(cast(Any, Albaran.albaran_fecha), Albaran.albaran_numero, AlbaranItem.item_id)
            )
        )
        for albaran_item, _albaran in albaran_rows:
            articulo_id = str(getattr(albaran_item, "articulo_id", "") or "").strip()
            source_pedido_id = str(getattr(albaran_item, "pedido_id", "") or "").strip()
            cantidad = float(getattr(albaran_item, "articulo_cantidad", 0.0) or 0.0)
            if not articulo_id or cantidad <= 1e-9:
                continue
            pending_queue = open_by_article.get(articulo_id, [])
            remaining = cantidad
            if source_pedido_id and pending_queue:
                own_index = next(
                    (
                        idx
                        for idx, candidate in enumerate(pending_queue)
                        if str(candidate.get("pedido_id") or "").strip() == source_pedido_id
                    ),
                    -1,
                )
                if own_index >= 0:
                    target = pending_queue[own_index]
                    target_remaining = float(target.get("remaining", 0.0) or 0.0)
                    if target_remaining > 1e-9:
                        applied = min(target_remaining, remaining)
                        stats[(source_pedido_id, articulo_id)]["received"] += applied
                        target["remaining"] = target_remaining - applied
                        remaining -= applied
                    if float(target.get("remaining", 0.0) or 0.0) <= 1e-9:
                        pending_queue.pop(own_index)
            while remaining > 1e-9 and pending_queue:
                target = pending_queue[0]
                target_pedido_id = str(target.get("pedido_id") or "").strip()
                target_remaining = float(target.get("remaining", 0.0) or 0.0)
                if target_remaining <= 1e-9:
                    pending_queue.pop(0)
                    continue
                applied = min(target_remaining, remaining)
                stats[(target_pedido_id, articulo_id)]["received"] += applied
                target["remaining"] = target_remaining - applied
                remaining -= applied
                if float(target["remaining"] or 0.0) <= 1e-9:
                    pending_queue.pop(0)

        return pedido, stats, pedido_by_id

    def list_order_items(
        self,
        pedido_id: str,
    ) -> tuple[list[tuple[PedidoItem, IngredienteIreks | None]], set[str], dict[str, float]]:
        clean_pedido_id = str(pedido_id or "").strip()
        if not clean_pedido_id:
            return [], set(), {}
        with Session(engine) as session:
            rows = list(
                session.exec(
                    select(PedidoItem, IngredienteIreks)
                    .outerjoin(IngredienteIreks, cast(Any, IngredienteIreks.articulo_id == PedidoItem.articulo_id))
                    .where(PedidoItem.pedido_id == clean_pedido_id)
                    .order_by(PedidoItem.item_id)
                )
            )
            albaran_rows = list(
                session.exec(
                    select(AlbaranItem)
                    .where(AlbaranItem.pedido_id == clean_pedido_id)
                    .order_by(AlbaranItem.item_id)
                )
            )
            _pedido, stats, _pedido_by_id = self._build_operational_assignment(session, clean_pedido_id)
        pending_article_ids = {
            articulo_id
            for (row_pedido_id, articulo_id), values in stats.items()
            if row_pedido_id == clean_pedido_id and float((values.get("ordered", 0.0) or 0.0) - (values.get("received", 0.0) or 0.0)) > 1e-9
        }
        received_by_article: dict[str, float] = {}
        for row in albaran_rows:
            articulo_id = str(getattr(row, "articulo_id", "") or "").strip()
            if not articulo_id:
                continue
            received_by_article[articulo_id] = received_by_article.get(articulo_id, 0.0) + float(getattr(row, "articulo_cantidad", 0.0) or 0.0)
        return rows, pending_article_ids, received_by_article

    def list_order_items_payload(
        self,
        pedido_id: str,
        *,
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> OrderItemListResponse:
        rows, _pending_article_ids, _received_by_article = self.list_order_items(pedido_id)
        items = [item for item, _article in rows]
        return OrderItemListResponse(
            items=OrderItemRead.list_from_entities(page_items(items, limit=limit, offset=offset)),
            total=len(items),
            limit=limit,
            offset=offset,
        )

    def list_albaranes(self, pedido_id: str) -> list[Albaran]:
        clean_pedido_id = str(pedido_id or "").strip()
        if not clean_pedido_id:
            return []
        with Session(engine) as session:
            return list(
                session.exec(
                    select(Albaran)
                    .where(Albaran.pedido_id == clean_pedido_id)
                    .order_by(Albaran.albaran_fecha.desc(), Albaran.albaran_numero)
                )
            )

    def list_albaran_items(
        self,
        pedido_id: str,
        albaran_id: str = "",
    ) -> tuple[list[tuple[AlbaranItem, IngredienteIreks | None]], set[str]]:
        clean_pedido_id = str(pedido_id or "").strip()
        clean_albaran_id = str(albaran_id or "").strip()
        if not clean_pedido_id:
            return [], set()
        with Session(engine) as session:
            query = (
                select(AlbaranItem, IngredienteIreks)
                .outerjoin(IngredienteIreks, cast(Any, IngredienteIreks.articulo_id == AlbaranItem.articulo_id))
                .where(AlbaranItem.pedido_id == clean_pedido_id)
            )
            if clean_albaran_id:
                query = query.where(AlbaranItem.albaran_id == clean_albaran_id)
            rows = list(session.exec(query.order_by(AlbaranItem.item_id)))
            excess_rows = list(
                session.exec(
                    select(PedidoPendiente).where(
                        PedidoPendiente.pedido_id == clean_pedido_id,
                        PedidoPendiente.estado == "exceso",
                    )
                )
            )
        excess_article_ids = {
            str(getattr(row, "articulo_id", "") or "").strip()
            for row in excess_rows
            if float(getattr(row, "cantidad_recibida", 0.0) or 0.0) > 1e-9
        }
        return rows, excess_article_ids

    def list_pendientes(self, pedido_id: str) -> tuple[list[PedidoPendiente], list[IngredienteIreks]]:
        clean_pedido_id = str(pedido_id or "").strip()
        if not clean_pedido_id:
            return [], []
        with Session(engine) as session:
            rows = list(session.exec(select(PedidoPendiente).where(PedidoPendiente.pedido_id == clean_pedido_id)))
            article_ids = sorted(
                {str(getattr(x, "articulo_id", "") or "").strip() for x in rows if str(getattr(x, "articulo_id", "") or "").strip()}
            )
            articles = (
                list(session.exec(select(IngredienteIreks).where(cast(Any, IngredienteIreks.articulo_id).in_(article_ids))))
                if article_ids
                else []
            )
        return rows, articles


    def list_pendientes_acumulados(self, pedido_id: str) -> tuple[list[tuple[PendingAggregateRow, Pedido]], list[IngredienteIreks]]:
        clean_pedido_id = str(pedido_id or "").strip()
        if not clean_pedido_id:
            return [], []
        with Session(engine) as session:
            pedido, stats, pedido_by_id = self._build_operational_assignment(session, clean_pedido_id)
            if pedido is None:
                return [], []
            rows: list[tuple[PendingAggregateRow, Pedido]] = []
            article_ids: set[str] = set()
            for (row_pedido_id, articulo_id), values in stats.items():
                ordered = float(values.get("ordered", 0.0) or 0.0)
                received = float(values.get("received", 0.0) or 0.0)
                pending = ordered - received
                if pending <= 1e-9:
                    continue
                pedido_row = pedido_by_id.get(row_pedido_id)
                if pedido_row is None:
                    continue
                rows.append((
                    PendingAggregateRow(
                        pedido_id=row_pedido_id,
                        articulo_id=articulo_id,
                        cantidad_pedida=ordered,
                        cantidad_recibida=received,
                        cantidad_pendiente=pending,
                        estado="pendiente",
                    ),
                    pedido_row,
                ))
                article_ids.add(articulo_id)
            articles = (
                list(session.exec(select(IngredienteIreks).where(cast(Any, IngredienteIreks.articulo_id).in_(sorted(article_ids)))))
                if article_ids
                else []
            )
        rows.sort(key=lambda pair: (pair[1].pedido_fecha, pair[1].pedido_numero, pair[1].pedido_id, pair[0].articulo_id))
        return rows, articles

    def list_pendientes_payload(
        self,
        pedido_id: str,
        *,
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> OrderPendingListResponse:
        rows, _articles = self.list_pendientes(pedido_id)
        return OrderPendingListResponse(
            items=OrderPendingRead.list_from_entities(page_items(rows, limit=limit, offset=offset)),
            total=len(rows),
            limit=limit,
            offset=offset,
        )

    def warehouse_filter_options(self) -> list[WarehouseFilterOption]:
        with Session(engine) as session:
            rows = list(session.exec(select(Cliente).order_by(Cliente.cliente_nombre_comercial)))
        options = [WarehouseFilterOption("Todos", "")]
        for row in rows:
            tipo = str(getattr(row, "cliente_tipo", "") or "").strip().lower()
            if tipo not in {"distribuidor", "directo", "cliente directo", "cliente_directo"}:
                continue
            cliente_id = str(getattr(row, "cliente_id", "") or "").strip()
            if not cliente_id:
                continue
            label = str(getattr(row, "cliente_nombre_comercial", "") or "").strip() or str(
                getattr(row, "cliente_nombre_fiscal", "") or ""
            ).strip()
            options.append(WarehouseFilterOption(label or cliente_id, cliente_id))
        return options

    def list_raw_orders(self) -> list[Pedido]:
        with Session(engine) as session:
            return list(session.exec(select(Pedido).order_by(Pedido.pedido_fecha.desc(), Pedido.pedido_numero)))

    def list_order_rows(
        self,
        *,
        year_filter: str,
        month_from: int,
        month_to: int,
        almacen_filter: str,
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> list[OrderListRow]:
        pedidos = self.list_raw_orders()
        with Session(engine) as session:
            clientes = list(session.exec(select(Cliente)))
        cliente_name_by_id = {
            str(row.cliente_id or ""): (
                str(row.cliente_nombre_comercial or "").strip() or str(row.cliente_nombre_fiscal or "").strip()
            )
            for row in clientes
        }

        filtered = self._filter_orders(
            pedidos,
            year_filter=year_filter,
            month_from=month_from,
            month_to=month_to,
            almacen_filter=almacen_filter,
        )

        page = page_items(filtered, limit=limit, offset=offset)
        totals_map = self.pedido_totals_kg([str(row.pedido_id or "") for row in page])
        out: list[OrderListRow] = []
        for row in page:
            pedido_id = str(row.pedido_id or "")
            almacen_id = str(row.almacen_id or "")
            p_date = self.parse_date(row.pedido_fecha)
            out.append(
                OrderListRow(
                    pedido_id=pedido_id,
                    almacen_id=almacen_id,
                    almacen_nombre=cliente_name_by_id.get(almacen_id, almacen_id),
                    pedido_fecha=p_date,
                    pedido_numero=str(row.pedido_numero or ""),
                    pedido_albaran_numero=str(row.pedido_albaran_numero or ""),
                    pedido_factura_numero=str(row.pedido_factura_numero or ""),
                    pedido_ref=str(row.pedido_ref or ""),
                    pedido_estado=str(getattr(row, "pedido_estado", "") or "").strip().upper(),
                    semana=int(p_date.isocalendar()[1]),
                    total_kg=float(totals_map.get(pedido_id, 0.0)),
                )
            )
        return out

    def list_order_payloads(
        self,
        *,
        year_filter: str = "",
        month_from: int = 0,
        month_to: int = 0,
        almacen_filter: str = "",
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> OrderListResponse:
        filtered = self._filter_orders(
            self.list_raw_orders(),
            year_filter=year_filter,
            month_from=month_from,
            month_to=month_to,
            almacen_filter=almacen_filter,
        )
        rows = self.list_order_rows(
            year_filter=year_filter,
            month_from=month_from,
            month_to=month_to,
            almacen_filter=almacen_filter,
            limit=limit,
            offset=offset,
        )
        return OrderListResponse(
            items=OrderListItem.list_from_entities(rows),
            total=len(filtered),
            limit=limit,
            offset=offset,
        )

    def _filter_orders(
        self,
        pedidos: list[Pedido],
        *,
        year_filter: str,
        month_from: int,
        month_to: int,
        almacen_filter: str,
    ) -> list[Pedido]:
        if month_from and month_to and month_from > month_to:
            month_from, month_to = month_to, month_from

        filtered: list[Pedido] = []
        for row in pedidos:
            p_date = self.parse_date(row.pedido_fecha)
            if year_filter and str(p_date.year) != year_filter:
                continue
            if month_from and p_date.month < month_from:
                continue
            if month_to and p_date.month > month_to:
                continue
            if almacen_filter and str(row.almacen_id or "").strip() != almacen_filter:
                continue
            filtered.append(row)
        return filtered

    def pedido_totals_kg(self, pedido_ids: list[str]) -> dict[str, float]:
        if not pedido_ids:
            return {}
        with engine.begin() as conn:
            tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            if "pedidos_items" in tables:
                placeholders = ", ".join(["?"] * len(pedido_ids))
                rows = conn.exec_driver_sql(
                    f"""
                    SELECT pi.pedido_id, COALESCE(SUM(COALESCE(pi.articulo_cantidad, 0) * COALESCE(pr.articulo_envase_peso_total, 0)), 0)
                    FROM pedidos_items pi
                    LEFT JOIN productos_ireks pr ON pr.articulo_id = pi.articulo_id
                    WHERE pi.pedido_id IN ({placeholders})
                    GROUP BY pi.pedido_id
                    """,
                    tuple(pedido_ids),
                ).fetchall()
                return {str(row[0]): float(row[1] or 0.0) for row in rows}

            table_name = "pedido_items" if "pedido_items" in tables else ""
            if not table_name:
                return {}
            info_rows = conn.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()
            columns = {str(row[1]) for row in info_rows}
            if "pedido_id" not in columns:
                return {}
            kg_col = ""
            for candidate in ("articulo_cantidad", "kg", "kilos", "pedido_item_kg", "total_kg", "cantidad_kg"):
                if candidate in columns:
                    kg_col = candidate
                    break
            if not kg_col:
                return {}
            placeholders = ", ".join(["?"] * len(pedido_ids))
            rows = conn.exec_driver_sql(
                f"""
                SELECT pedido_id, COALESCE(SUM({kg_col}), 0)
                FROM {table_name}
                WHERE pedido_id IN ({placeholders})
                GROUP BY pedido_id
                """,
                tuple(pedido_ids),
            ).fetchall()
        return {str(row[0]): float(row[1] or 0.0) for row in rows}

    @staticmethod
    def parse_date(value: object) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        text = str(value or "").strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%y", "%d-%m-%y"):
            try:
                return datetime.strptime(text, fmt).date()
            except Exception:
                continue
        return date.today()
