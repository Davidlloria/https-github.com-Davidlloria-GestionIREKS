from __future__ import annotations

from dataclasses import dataclass

from app.services.order_document_import_flow_service import OrderDocumentImportFlowService


@dataclass
class _FakeDocument:
    albaran_id: str = ""
    factura_id: str = ""


def test_resolve_albaran_gate_returns_ready_when_no_duplicate() -> None:
    service = OrderDocumentImportFlowService()
    calls: list[tuple[str, str]] = []

    gate = service.resolve_albaran_gate(
        pedido_id="p1",
        preview_header={"albaran_numero": "A-1"},
        find_existing_albaran=lambda pedido_id, albaran_numero: calls.append((pedido_id, albaran_numero)) or None,
        repair_existing_albaran=lambda _existing_id: (_ for _ in ()).throw(AssertionError("repair no debio llamarse")),
    )

    assert gate.already_imported is False
    assert gate.status == "ready"
    assert gate.message == ""
    assert calls == [("p1", "A-1")]


def test_resolve_albaran_gate_repairs_and_marks_duplicate() -> None:
    service = OrderDocumentImportFlowService()
    repairs: list[str] = []

    gate = service.resolve_albaran_gate(
        pedido_id="p1",
        preview_header={"albaran_numero": "A-1"},
        find_existing_albaran=lambda _pedido_id, _albaran_numero: _FakeDocument(albaran_id="alb-7"),
        repair_existing_albaran=lambda existing_id: repairs.append(existing_id),
    )

    assert gate.already_imported is True
    assert gate.status == "already_imported"
    assert gate.existing_document_id == "alb-7"
    assert "A-1" in gate.message
    assert repairs == ["alb-7"]


def test_resolve_factura_gate_returns_duplicate_without_repair() -> None:
    service = OrderDocumentImportFlowService()
    calls: list[tuple[str, str]] = []

    gate = service.resolve_factura_gate(
        pedido_id="p1",
        preview_header={"factura_numero": "F-1"},
        find_existing_factura=lambda pedido_id, factura_numero: calls.append((pedido_id, factura_numero))
        or _FakeDocument(factura_id="fac-4"),
    )

    assert gate.already_imported is True
    assert gate.status == "already_imported"
    assert gate.existing_document_id == "fac-4"
    assert "F-1" in gate.message
    assert calls == [("p1", "F-1")]


def test_resolve_gate_ignores_empty_document_number() -> None:
    service = OrderDocumentImportFlowService()
    calls: list[str] = []

    gate = service.resolve_factura_gate(
        pedido_id="p1",
        preview_header={"factura_numero": "   "},
        find_existing_factura=lambda _pedido_id, _factura_numero: calls.append("called") or None,
    )

    assert gate.already_imported is False
    assert gate.message == ""
    assert calls == []
