from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, select

from app.core.database import engine
from app.models import Cliente
from app.services.order_query_service import OrderQueryService, WarehouseFilterOption
from app.services.order_service import OrderJsonImportResult, OrderService


class SettingsImportService:
    def __init__(self) -> None:
        self.order_query_service = OrderQueryService()
        self.order_service = OrderService()

    def warehouse_filter_options(self) -> list[WarehouseFilterOption]:
        return [option for option in self.order_query_service.warehouse_filter_options() if option.value]

    def import_order_json(self, source: Path, almacen_id: str) -> OrderJsonImportResult:
        return self.order_service.import_order_json(source, almacen_id)

    def resolve_igsa_cliente_id(self) -> str:
        with Session(engine) as session:
            rows = list(session.exec(select(Cliente)))
        for row in rows:
            tipo = str(getattr(row, "cliente_tipo", "") or "").strip().lower()
            if tipo not in {"distribuidor", "directo", "cliente directo", "cliente_directo"}:
                continue
            comercial = str(getattr(row, "cliente_nombre_comercial", "") or "").strip().lower()
            fiscal = str(getattr(row, "cliente_nombre_fiscal", "") or "").strip().lower()
            if "igsa" in comercial or "igsa" in fiscal:
                return str(getattr(row, "cliente_id", "") or "").strip()
        return ""
