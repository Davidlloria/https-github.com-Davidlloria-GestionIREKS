from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from uuid import uuid4

from sqlmodel import Session, select

from app.core.database import engine
from app.models import Albaran, AlbaranItem, AlmacenMovimiento, Factura, FacturaItem, Pedido, PedidoItem, PedidoPendiente
from app.schemas.orders import OrderCreate, OrderItemRead, OrderLineWrite, OrderRead, OrderUpdate
from app.services.order_document_import_service import OrderDocumentImportService
from app.services.import_service import ImportService


@dataclass(frozen=True)
class OrderLineInput:
    articulo_id: str
    uds: float


@dataclass
class OrderJsonImportResult:
    pedido_id: str = ""
    imported_items: int = 0
    skipped_unknown: list[str] = field(default_factory=list)
    skipped_invalid: int = 0


@dataclass
class OrderItemsImportResult:
    imported: int = 0
    errors: list[str] = field(default_factory=list)


class OrderService:
    def __init__(self) -> None:
        self.document_import_service = OrderDocumentImportService()
        self.import_service = ImportService()

    def create_order(
        self,
        *,
        almacen_id: str,
        pedido_fecha: date,
        pedido_numero: str,
        lines: list[OrderLineInput],
        is_pending: bool = False,
    ) -> str:
        pedido_id = str(uuid4())
        with Session(engine) as session:
            session.add(
                Pedido(
                    pedido_id=pedido_id,
                    almacen_id=almacen_id,
                    pedido_fecha=pedido_fecha,
                    pedido_numero=pedido_numero,
                    pedido_albaran_numero="",
                    pedido_factura_numero="",
                    pedido_ref="",
                    pedido_estado="P" if is_pending else "",
                )
            )
            for line in lines:
                session.add(
                    PedidoItem(
                        pedido_id=pedido_id,
                        pedido_numero=pedido_numero,
                        pedido_albaran_numero="",
                        pedido_item_fecha=pedido_fecha,
                        articulo_id=line.articulo_id,
                        articulo_cantidad=float(line.uds),
                    )
                )
            session.commit()
        return pedido_id

    def create_from_payload(self, payload: OrderCreate | dict) -> OrderRead:
        data = self._payload_dict(payload, OrderCreate)
        pedido_id = self.create_order(
            almacen_id=str(data["almacen_id"]),
            pedido_fecha=data["pedido_fecha"],
            pedido_numero=str(data.get("pedido_numero") or ""),
            lines=self._line_inputs(data.get("lines", [])),
            is_pending=bool(data.get("is_pending", False)),
        )
        return OrderRead.from_entity(self._get_order_or_raise(pedido_id))

    def update_order(
        self,
        *,
        pedido_id: str,
        pedido_fecha: date,
        pedido_numero: str,
        lines: list[OrderLineInput],
        submit_mode: str,
    ) -> None:
        with Session(engine) as session:
            entity = session.get(Pedido, pedido_id)
            if entity is None:
                raise ValueError("Pedido no encontrado.")
            estado_actual = str(getattr(entity, "pedido_estado", "") or "").strip().upper()
            entity.pedido_fecha = pedido_fecha
            entity.pedido_numero = pedido_numero
            if estado_actual == "E":
                entity.pedido_estado = "M"
            elif submit_mode == "pendiente":
                entity.pedido_estado = "P"
            elif estado_actual == "P":
                entity.pedido_estado = ""
            session.add(entity)

            old_items = list(session.exec(select(PedidoItem).where(PedidoItem.pedido_id == pedido_id)))
            for item in old_items:
                session.delete(item)
            for line in lines:
                session.add(
                    PedidoItem(
                        pedido_id=pedido_id,
                        pedido_numero=pedido_numero,
                        pedido_albaran_numero=str(entity.pedido_albaran_numero or "").strip(),
                        pedido_item_fecha=pedido_fecha,
                        articulo_id=line.articulo_id,
                        articulo_cantidad=float(line.uds),
                    )
                )
            session.commit()

    def update_from_payload(self, pedido_id: str, payload: OrderUpdate | dict) -> OrderRead:
        data = self._payload_dict(payload, OrderUpdate)
        self.update_order(
            pedido_id=pedido_id,
            pedido_fecha=data["pedido_fecha"],
            pedido_numero=str(data.get("pedido_numero") or ""),
            lines=self._line_inputs(data.get("lines", [])),
            submit_mode=str(data.get("submit_mode") or ""),
        )
        return OrderRead.from_entity(self._get_order_or_raise(pedido_id))

    def update_order_header(self, pedido_id: str, pedido_fecha: date, pedido_numero: str) -> None:
        with Session(engine) as session:
            entity = session.get(Pedido, pedido_id)
            if entity is None:
                return
            entity.pedido_fecha = pedido_fecha
            entity.pedido_numero = pedido_numero
            session.add(entity)
            session.commit()

    def add_order_line(self, pedido_id: str, articulo_id: str, cantidad: float = 1.0) -> PedidoItem:
        with Session(engine) as session:
            pedido = session.get(Pedido, pedido_id)
            if pedido is None:
                raise ValueError("Pedido no encontrado.")
            row = PedidoItem(
                pedido_id=str(pedido.pedido_id or "").strip(),
                pedido_numero=str(pedido.pedido_numero or "").strip(),
                pedido_albaran_numero=str(pedido.pedido_albaran_numero or "").strip(),
                pedido_item_fecha=self._as_date(pedido.pedido_fecha),
                articulo_id=articulo_id,
                articulo_cantidad=float(cantidad),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def add_order_line_from_payload(self, pedido_id: str, payload: OrderLineWrite | dict) -> OrderItemRead:
        data = self._payload_dict(payload, OrderLineWrite)
        row = self.add_order_line(
            pedido_id,
            str(data["articulo_id"]),
            float(data.get("articulo_cantidad") or 0.0),
        )
        return OrderItemRead.from_entity(row)

    def get_order_line_payload(self, item_id: str) -> tuple[str, float]:
        with Session(engine) as session:
            entity = session.get(PedidoItem, item_id)
            if entity is None:
                raise ValueError("No se encontró la línea seleccionada.")
            return (
                str(getattr(entity, "articulo_id", "") or "").strip(),
                float(getattr(entity, "articulo_cantidad", 0.0) or 0.0),
            )

    def update_order_line(self, item_id: str, articulo_id: str, cantidad: float) -> PedidoItem:
        with Session(engine) as session:
            entity = session.get(PedidoItem, item_id)
            if entity is None:
                raise ValueError("La línea ya no existe.")
            entity.articulo_id = articulo_id
            entity.articulo_cantidad = float(cantidad)
            session.add(entity)
            session.commit()
            session.refresh(entity)
            return entity

    def update_order_line_from_payload(self, item_id: str, payload: OrderLineWrite | dict) -> OrderItemRead:
        data = self._payload_dict(payload, OrderLineWrite)
        row = self.update_order_line(
            item_id,
            str(data["articulo_id"]),
            float(data.get("articulo_cantidad") or 0.0),
        )
        return OrderItemRead.from_entity(row)

    def update_order_line_quantity(self, item_id: str, cantidad: float) -> None:
        with Session(engine) as session:
            entity = session.get(PedidoItem, item_id)
            if entity is None:
                return
            entity.articulo_cantidad = float(cantidad)
            session.add(entity)
            session.commit()

    def delete_order_line(self, item_id: str) -> None:
        with Session(engine) as session:
            entity = session.get(PedidoItem, item_id)
            if entity is not None:
                session.delete(entity)
                session.commit()

    def delete_order_line_if_exists(self, item_id: str) -> bool:
        with Session(engine) as session:
            entity = session.get(PedidoItem, item_id)
            if entity is None:
                return False
        self.delete_order_line(item_id)
        return True

    def delete_order(self, pedido_id: str) -> None:
        with Session(engine) as session:
            entity = session.get(Pedido, pedido_id)
            if entity is None:
                return

            clean_pedido_id = str(getattr(entity, "pedido_id", "") or "").strip()
            almacen_id = str(getattr(entity, "almacen_id", "") or "").strip()
            pedido_numero = str(getattr(entity, "pedido_numero", "") or "").strip()
            pedido_albaran_numero = str(getattr(entity, "pedido_albaran_numero", "") or "").strip()

            for item in list(session.exec(select(PedidoPendiente).where(PedidoPendiente.pedido_id == clean_pedido_id))):
                session.delete(item)

            for item in list(session.exec(select(PedidoItem).where(PedidoItem.pedido_id == clean_pedido_id))):
                session.delete(item)

            albaranes_rows = list(session.exec(select(Albaran).where(Albaran.pedido_id == clean_pedido_id)))
            albaran_ids = [str(getattr(x, "albaran_id", "") or "").strip() for x in albaranes_rows]
            albaran_ids = [x for x in albaran_ids if x]
            albaran_numbers = [str(getattr(x, "albaran_numero", "") or "").strip() for x in albaranes_rows]
            albaran_numbers = [x for x in albaran_numbers if x]

            albaran_items_rows = (
                list(session.exec(select(AlbaranItem).where(AlbaranItem.albaran_id.in_(albaran_ids)))) if albaran_ids else []
            )
            albaran_item_ids = [str(getattr(x, "item_id", "") or "").strip() for x in albaran_items_rows]
            albaran_item_ids = [x for x in albaran_item_ids if x]

            if albaran_item_ids:
                movimientos = list(
                    session.exec(select(AlmacenMovimiento).where(AlmacenMovimiento.albaran_item_id.in_(albaran_item_ids)))
                )
                for mov in movimientos:
                    session.delete(mov)

            legacy_movs: list[AlmacenMovimiento] = []
            if albaran_numbers:
                legacy_movs.extend(
                    list(
                        session.exec(
                            select(AlmacenMovimiento).where(
                                AlmacenMovimiento.almacen_id == almacen_id,
                                AlmacenMovimiento.pedido_albaran_numero.in_(albaran_numbers),
                            )
                        )
                    )
                )
            if pedido_numero:
                legacy_movs.extend(
                    list(
                        session.exec(
                            select(AlmacenMovimiento).where(
                                AlmacenMovimiento.almacen_id == almacen_id,
                                AlmacenMovimiento.pedido_numero == pedido_numero,
                                AlmacenMovimiento.pedido_albaran_numero == pedido_albaran_numero,
                            )
                        )
                    )
                )
            seen_mov_ids: set[int] = set()
            for mov in legacy_movs:
                mov_id = int(getattr(mov, "id", 0) or 0)
                if mov_id <= 0 or mov_id in seen_mov_ids:
                    continue
                seen_mov_ids.add(mov_id)
                session.delete(mov)

            for item in albaran_items_rows:
                session.delete(item)
            for item in albaranes_rows:
                session.delete(item)

            facturas_rows = list(session.exec(select(Factura).where(Factura.pedido_id == clean_pedido_id)))
            factura_ids = [str(getattr(x, "factura_id", "") or "").strip() for x in facturas_rows]
            factura_ids = [x for x in factura_ids if x]
            factura_items_rows = (
                list(session.exec(select(FacturaItem).where(FacturaItem.factura_id.in_(factura_ids)))) if factura_ids else []
            )
            for item in factura_items_rows:
                session.delete(item)
            for item in facturas_rows:
                session.delete(item)

            session.delete(entity)
            session.flush()

            pedidos_restantes = list(
                session.exec(
                    select(Pedido)
                    .where(Pedido.almacen_id == almacen_id)
                    .order_by(Pedido.pedido_fecha, Pedido.pedido_numero, Pedido.pedido_id)
                )
            )
            if pedidos_restantes:
                pedido_seed = str(getattr(pedidos_restantes[0], "pedido_id", "") or "").strip()
                remaining_ids = [str(getattr(x, "pedido_id", "") or "").strip() for x in pedidos_restantes]
                remaining_ids = [x for x in remaining_ids if x]
                albaran_seed = (
                    session.exec(
                        select(Albaran)
                        .where(Albaran.pedido_id.in_(remaining_ids))
                        .order_by(Albaran.albaran_fecha, Albaran.albaran_numero, Albaran.albaran_id)
                    ).first()
                    if remaining_ids
                    else None
                )
                if albaran_seed is not None:
                    self.document_import_service.rebuild_order_pendientes(
                        session,
                        pedido_seed,
                        str(getattr(albaran_seed, "albaran_id", "") or "").strip(),
                    )
                else:
                    stale_rows = (
                        list(session.exec(select(PedidoPendiente).where(PedidoPendiente.pedido_id.in_(remaining_ids))))
                        if remaining_ids
                        else []
                    )
                    for item in stale_rows:
                        session.delete(item)
                    session.commit()
            else:
                session.commit()

    def delete_order_if_exists(self, pedido_id: str) -> bool:
        with Session(engine) as session:
            entity = session.get(Pedido, pedido_id)
            if entity is None:
                return False
        self.delete_order(pedido_id)
        return True

    def import_order_json(self, source: Path, almacen_id: str) -> OrderJsonImportResult:
        rows = self.import_service.read_rows(source)
        if not rows:
            raise ValueError("El archivo JSON no contiene datos.")
        payload = rows[0] if isinstance(rows[0], dict) else {}
        if not isinstance(payload, dict):
            raise ValueError("Formato JSON no valido para pedido.")

        pedido_fecha = self.document_import_service.parse_required_date(payload.get("Fecha"), "Fecha")
        pedido_numero = ""
        pedido_albaran_numero = str(payload.get("Albaran") or "").strip()
        lineas = payload.get("Lineas")
        lineas_list = lineas if isinstance(lineas, list) else []
        result = OrderJsonImportResult()

        with Session(engine) as session:
            existing = session.exec(
                select(Pedido).where(
                    Pedido.almacen_id == almacen_id,
                    Pedido.pedido_ref == source.name,
                )
            ).first()

            if existing is None:
                entity = Pedido(
                    pedido_id=str(uuid4()),
                    almacen_id=almacen_id,
                    pedido_fecha=pedido_fecha,
                    pedido_numero=pedido_numero,
                    pedido_albaran_numero=pedido_albaran_numero,
                    pedido_ref=source.name,
                )
                session.add(entity)
                session.flush()
            else:
                entity = existing
                entity.pedido_fecha = pedido_fecha
                entity.pedido_numero = pedido_numero
                entity.pedido_albaran_numero = pedido_albaran_numero
                entity.pedido_ref = source.name
                session.add(entity)
                session.flush()
                old_items = list(session.exec(select(PedidoItem).where(PedidoItem.pedido_id == entity.pedido_id)))
                for row in old_items:
                    session.delete(row)
                session.flush()

            result.pedido_id = str(entity.pedido_id or "").strip()

            for raw_line in lineas_list:
                if not isinstance(raw_line, dict):
                    result.skipped_invalid += 1
                    continue
                codigo = str(raw_line.get("Codigo") or "").strip()
                if not codigo:
                    result.skipped_invalid += 1
                    continue
                cantidad = self.document_import_service.parse_float(raw_line.get("Cantidad"), default=0.0)
                if cantidad <= 0:
                    result.skipped_invalid += 1
                    continue
                article = self.document_import_service.find_article_by_code(session, codigo)
                if article is None:
                    result.skipped_unknown.append(codigo)
                    continue
                articulo_id = str(getattr(article, "articulo_id", "") or "").strip()
                if not articulo_id:
                    result.skipped_invalid += 1
                    continue
                session.add(
                    PedidoItem(
                        pedido_id=result.pedido_id,
                        pedido_numero=str(entity.pedido_numero or "").strip(),
                        pedido_albaran_numero=str(entity.pedido_albaran_numero or "").strip(),
                        pedido_item_fecha=self._as_date(entity.pedido_fecha),
                        articulo_id=articulo_id,
                        articulo_cantidad=float(cantidad),
                    )
                )
                result.imported_items += 1

            session.commit()

        return result

    def import_order_items_file(self, source: Path) -> OrderItemsImportResult:
        aliases = {
            "pedido_id": ["pedidoid", "id_pedido"],
            "articulo_id": ["articuloid", "id_articulo"],
            "articulo_cantidad": ["cantidad", "qty", "articulo_cant"],
            "articulo_lote": ["lote", "articulo_lote"],
            "articulo_caducidad": ["caduca", "caducidad", "articulo_caducidad", "fecha_caducidad"],
        }
        schema = [
            {"name": "pedido_id", "label": "Pedido_ID"},
            {"name": "articulo_id", "label": "Articulo_ID"},
            {"name": "articulo_cantidad", "label": "Articulo_Cantidad"},
        ]

        with Session(engine) as session:

            def create_row(payload: dict) -> None:
                pedido_id = str(payload.get("pedido_id") or "").strip()
                articulo_id = str(payload.get("articulo_id") or "").strip()
                cantidad_raw = payload.get("articulo_cantidad")
                cantidad = self._parse_float(cantidad_raw, default=0.0)

                if not pedido_id:
                    raise ValueError("Campo obligatorio vacio: pedido_id")
                if not articulo_id:
                    raise ValueError("Campo obligatorio vacio: articulo_id")
                if str(cantidad_raw or "").strip() == "":
                    raise ValueError("Campo obligatorio vacio: articulo_cantidad")

                pedido = session.get(Pedido, pedido_id)
                if pedido is None:
                    raise ValueError(f"Pedido no encontrado para pedido_id: {pedido_id}")

                session.add(
                    PedidoItem(
                        pedido_id=pedido_id,
                        pedido_numero=str(pedido.pedido_numero or "").strip(),
                        pedido_albaran_numero=str(pedido.pedido_albaran_numero or "").strip(),
                        pedido_item_fecha=self._as_date(pedido.pedido_fecha),
                        articulo_id=articulo_id,
                        articulo_cantidad=cantidad,
                    )
                )
                session.commit()

            imported, errors = self.import_service.import_with_schema(
                file_path=source,
                schema=schema,
                create_fn=create_row,
                required_fields=["pedido_id", "articulo_id", "articulo_cantidad"],
                aliases=aliases,
            )
        return OrderItemsImportResult(imported=imported, errors=errors)

    @staticmethod
    def _as_date(value: object) -> date:
        if isinstance(value, date):
            return value
        return date.today()

    @staticmethod
    def _parse_float(value: object, default: float = 0.0) -> float:
        text = str(value or "").strip()
        if not text:
            return default
        try:
            return float(text.replace(".", "").replace(",", ".") if "," in text else text)
        except Exception:
            return default

    @staticmethod
    def _payload_dict(payload: object, schema_cls: type) -> dict:
        if isinstance(payload, dict):
            model = schema_cls.model_validate(payload)
        else:
            model = schema_cls.model_validate(payload)
        return model.model_dump()

    @staticmethod
    def _line_inputs(rows: list[dict]) -> list[OrderLineInput]:
        result: list[OrderLineInput] = []
        for row in rows:
            articulo_id = str(row.get("articulo_id") or "").strip()
            if not articulo_id:
                continue
            result.append(OrderLineInput(articulo_id=articulo_id, uds=float(row.get("uds") or 0.0)))
        return result

    def _get_order_or_raise(self, pedido_id: str) -> Pedido:
        with Session(engine) as session:
            row = session.get(Pedido, pedido_id)
            if row is None:
                raise ValueError("Pedido no encontrado.")
            return row
