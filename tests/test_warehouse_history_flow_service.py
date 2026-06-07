from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest

from app.services.warehouse_history_flow_service import WarehouseHistoryFlowService


@dataclass
class _Header:
    inventario_id: str
    fecha: date
    contador: str
    aprobador: str
    lineas: int
    ajustes: int
    estado: str


@dataclass
class _Detail:
    inventario_id: str
    articulo_id: str
    articulo_lote: str
    articulo_caducidad: date | None
    teorico_uds: float
    conteo_uds: float
    diferencia_uds: float
    kg_ajuste: float


@dataclass
class _Item:
    articulo_id: str
    articulo_referencia_corta: str
    articulo_descripcion: str


class _FakeInventoryService:
    def __init__(self, headers=None, details=None, items=None) -> None:
        self._headers = headers or []
        self._details = details or []
        self._items = items or []

    def history(self, almacen_id: str):
        assert almacen_id == "warehouse-1"
        return self._headers

    def history_detail(self, inventario_id: str):
        assert inventario_id == "inv-1"
        return type("Payload", (), {"details": self._details, "items": self._items})()

    def export_payload(self, *, almacen_id: str = "", selected_id: str = ""):
        assert almacen_id == "warehouse-1"
        assert selected_id in {"", "inv-1"}
        return type("Payload", (), {"headers": self._headers, "details": self._details, "items": self._items})()


def _service(headers=None, details=None, items=None) -> WarehouseHistoryFlowService:
    return WarehouseHistoryFlowService(inventory_service=_FakeInventoryService(headers, details, items))


def test_load_history_with_rows_returns_selected_detail_and_export_payload() -> None:
    service = _service(
        headers=[
            _Header("inv-1", date(2026, 6, 1), "Ana", "Luis", 2, 1, "aprobado"),
            _Header("inv-2", date(2026, 5, 1), "Bob", "Marta", 1, 0, "borrador"),
        ],
        details=[
            _Detail("inv-1", "art-1", "L-1", date(2026, 6, 30), 10.0, 12.5, 2.5, 1.0),
        ],
        items=[_Item("art-1", "REF-1", "Harina")],
    )

    result = service.load_history("warehouse-1")

    assert result.status == "ready"
    assert result.selected_id == "inv-1"
    assert [row.inventario_id for row in result.rows] == ["inv-1", "inv-2"]
    assert result.detail_rows[0].ref == "REF-1"
    assert result.detail_rows[0].nombre == "Harina"
    assert result.detail_rows[0].kg_ajuste_text == "1.00 kg"
    assert result.export_payload is not None
    assert len(result.export_payload.headers) == 2


def test_load_history_empty_returns_empty_status() -> None:
    result = _service().load_history("warehouse-1")

    assert result.status == "empty"
    assert result.rows == []
    assert result.selected_id == ""
    assert result.export_payload is None


def test_resolve_selected_id_valid_and_invalid_indexes() -> None:
    service = _service()

    assert service.resolve_selected_id(["inv-1", "inv-2"], 0) == "inv-1"
    assert service.resolve_selected_id(["inv-1", "inv-2"], 1) == "inv-2"
    assert service.resolve_selected_id(["inv-1"], 2) == ""
    assert service.resolve_selected_id([], 0) == ""


def test_load_history_detail_without_id_returns_empty() -> None:
    service = _service()

    assert service.load_history_detail("") == []


def test_prepare_export_payload_returns_simple_payload() -> None:
    service = _service(
        headers=[_Header("inv-1", date(2026, 6, 1), "Ana", "Luis", 2, 1, "aprobado")],
        details=[_Detail("inv-1", "art-1", "L-1", None, 10.0, 12.0, 2.0, 1.0)],
        items=[_Item("art-1", "REF-1", "Harina")],
    )

    payload = service.prepare_export_payload("warehouse-1", "inv-1")

    assert len(payload.headers) == 1
    assert len(payload.details) == 1
    assert len(payload.items) == 1


def test_export_rows_without_headers_returns_empty_status() -> None:
    result = _service().export_rows("warehouse-1", "inv-1")

    assert result.status == "empty"
    assert result.message == "No hay historial para exportar con el filtro actual."
