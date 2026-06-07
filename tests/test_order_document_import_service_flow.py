from __future__ import annotations

from dataclasses import dataclass

from app.services.order_document_import_flow_service import OrderDocumentImportGateResult
from app.services.order_document_import_service import OrderDocumentImportService


@dataclass
class _FakePedido:
    pedido_id: str = "p1"
    almacen_id: str = "alm-1"
    pedido_numero: str = ""
    pedido_albaran_numero: str = ""
    pedido_factura_numero: str = ""


class _FakeSession:
    def __init__(self) -> None:
        self.add_calls: list[object] = []
        self.commit_calls = 0
        self.delete_calls: list[object] = []
        self.flush_calls = 0
        self.exec_called = False

    def __enter__(self) -> "_FakeSession":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def get(self, model, object_id):  # noqa: ANN001
        return _FakePedido() if getattr(model, "__name__", "") == "Pedido" else None

    def exec(self, *_args, **_kwargs):  # noqa: ANN001
        self.exec_called = True
        raise AssertionError("No se debio consultar nada cuando el gate ya resolvio duplicado")

    def add(self, obj):  # noqa: ANN001
        self.add_calls.append(obj)

    def commit(self) -> None:
        self.commit_calls += 1

    def delete(self, obj) -> None:  # noqa: ANN001
        self.delete_calls.append(obj)

    def flush(self) -> None:
        self.flush_calls += 1


class _FakeSessionFactory:
    def __init__(self) -> None:
        self.session = _FakeSession()

    def __call__(self, *_args, **_kwargs) -> _FakeSession:
        return self.session


class _DuplicateGateService:
    def __init__(self, result: OrderDocumentImportGateResult) -> None:
        self.result = result
        self.albaran_calls: list[tuple[str, dict[str, str]]] = []
        self.factura_calls: list[tuple[str, dict[str, str]]] = []

    def resolve_albaran_gate(self, *, pedido_id: str, preview_header: dict[str, str], find_existing_albaran, repair_existing_albaran):  # noqa: ANN001
        self.albaran_calls.append((pedido_id, preview_header))
        return self.result

    def resolve_factura_gate(self, *, pedido_id: str, preview_header: dict[str, str], find_existing_factura):  # noqa: ANN001
        self.factura_calls.append((pedido_id, preview_header))
        return self.result


def test_import_albaran_short_circuits_on_duplicate_gate(monkeypatch) -> None:
    from app.services import order_document_import_service as module

    fake_session_factory = _FakeSessionFactory()
    monkeypatch.setattr(module, "Session", fake_session_factory)
    fake_gate_service = _DuplicateGateService(
        OrderDocumentImportGateResult(status="already_imported", message="ya estaba importado", existing_document_id="alb-1")
    )
    service = OrderDocumentImportService(import_flow_service=fake_gate_service)

    result = service.import_albaran(
        "p1",
        {"albaran_numero": "A-1"},
        [{"albaran_numero": "A-1", "albaran_fecha": "2024-01-01", "articulo_codigo": "X"}],
    )

    assert result.already_imported is True
    assert result.message == "ya estaba importado"
    assert fake_gate_service.albaran_calls == [("p1", {"albaran_numero": "A-1"})]
    assert fake_session_factory.session.exec_called is False
    assert fake_session_factory.session.commit_calls == 0


def test_import_factura_short_circuits_on_duplicate_gate(monkeypatch) -> None:
    from app.services import order_document_import_service as module

    fake_session_factory = _FakeSessionFactory()
    monkeypatch.setattr(module, "Session", fake_session_factory)
    fake_gate_service = _DuplicateGateService(
        OrderDocumentImportGateResult(status="already_imported", message="ya estaba importada", existing_document_id="fac-1")
    )
    service = OrderDocumentImportService(import_flow_service=fake_gate_service)

    result = service.import_factura(
        "p1",
        {"factura_numero": "F-1"},
        [{"factura_numero": "F-1", "factura_fecha": "2024-01-01", "articulo_codigo": "X"}],
    )

    assert result.already_imported is True
    assert result.message == "ya estaba importada"
    assert fake_gate_service.factura_calls == [("p1", {"factura_numero": "F-1"})]
    assert fake_session_factory.session.exec_called is False
    assert fake_session_factory.session.commit_calls == 0
