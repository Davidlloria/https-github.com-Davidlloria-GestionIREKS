import json
from pathlib import Path

from app.services.sales_reconciliation_service import SalesReconciliationService


class _FakeExecResult:
    def __init__(self, rows: list[object] | None = None, first_value: object = None) -> None:
        self._rows = list(rows or [])
        self._first_value = first_value

    def first(self) -> object:
        return self._first_value

    def __iter__(self):
        return iter(self._rows)


class _FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.flushed = False
        self.committed = False

    def __enter__(self) -> "_FakeSession":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def exec(self, _stmt) -> _FakeExecResult:
        return _FakeExecResult()

    def add(self, obj: object) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        self.flushed = True

    def commit(self) -> None:
        self.committed = True

    def delete(self, obj: object) -> None:
        self.deleted.append(obj)


class _FakeSessionFactory:
    def __init__(self) -> None:
        self.last_session: _FakeSession | None = None

    def __call__(self, *args, **kwargs) -> _FakeSession:
        self.last_session = _FakeSession()
        return self.last_session


def test_read_ireks_json_accepts_utf16_bom(tmp_path) -> None:
    path = tmp_path / "ireks.json"
    rows = [{"venta_Anio": 2025, "venta_Mes": "Enero", "Codigo": "123"}]
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-16")

    data = SalesReconciliationService()._read_json(path)

    assert data == rows


def test_import_ireks_json_returns_result_for_invalid_json(tmp_path) -> None:
    path = tmp_path / "ireks.json"
    path.write_text("{", encoding="utf-8")

    result = SalesReconciliationService().import_ireks_json(path)

    assert not result.ok
    assert "JSON valido" in result.message


def test_import_ireks_json_accepts_structured_payload(tmp_path, monkeypatch) -> None:
    path = tmp_path / "ireks.json"
    payload = {
        "cliente": {
            "id": "249B7F5F-433A-F64F-9986-A056ECB1AB36",
            "codigo": "91",
            "nombre": "IGSA",
        },
        "periodo": {
            "anio": 2026,
            "mes": "Mayo",
            "hoja": "05 MAYO",
        },
        "articulos": [
            {
                "codigo": "17002",
                "articulo_id": "294CCF4D-E6A1-D849-817B-063C3E8D93AF",
                "descripcion": "IREKS REX 8",
                "kilos": 425,
                "sc": 0,
                "ventas": 880.6,
                "total_kg": 425,
            },
            {
                "codigo": "170051",
                "articulo_id": "C9470E4C-A4E4-7A41-A557-14BE52545E24",
                "descripcion": "REX CUATRO-GRANOS 12,5",
                "kilos": 50,
                "sc": 0,
                "ventas": 115.6,
                "total_kg": 50,
            },
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    fake_session_factory = _FakeSessionFactory()
    monkeypatch.setattr("app.services.sales_reconciliation_service.Session", fake_session_factory)

    result = SalesReconciliationService().import_ireks_json(path)

    assert result.ok is True
    assert result.imported == 2
    assert result.incidencias == 0
    assert fake_session_factory.last_session is not None
    inserted_rows = [obj for obj in fake_session_factory.last_session.added if obj.__class__.__name__ == "VentaMensualRaw"]
    assert len(inserted_rows) == 2
    assert inserted_rows[0].cliente_id == "249B7F5F-433A-F64F-9986-A056ECB1AB36"
    assert inserted_rows[0].periodo == "2026-05"
    assert inserted_rows[0].articulo_codigo_origen == "17002"
    assert inserted_rows[0].venta_kilos == 425
    assert inserted_rows[0].venta_kilos_sc == 0
    assert inserted_rows[0].venta_euros == 880.6


def test_total_rows_are_skipped() -> None:
    service = SalesReconciliationService()

    assert service._is_total_row(" TOTAL ")


class _FakePdfFlowService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def parse_igsa_pdf_files(self, file_paths: list[Path]) -> tuple[list[object], list[str]]:
        self.calls.append(("parse_igsa_pdf_files", (list(file_paths),), {}))
        return ["parsed"], ["parse-error"]

    def import_igsa_pdf_lines(
        self,
        lines: list[object],
        cliente_id: str = "",
        *,
        sync_warehouse_callback=None,
    ):
        self.calls.append(
            (
                "import_igsa_pdf_lines",
                (list(lines),),
                {"cliente_id": cliente_id, "sync_warehouse_callback": sync_warehouse_callback},
            )
        )
        return type("Result", (), {"ok": True, "message": "ok", "imported": 2, "incidencias": 1})()


def test_pdf_wrappers_delegate_to_flow_service() -> None:
    service = SalesReconciliationService()
    fake = _FakePdfFlowService()
    service._igsa_pdf_flow_service = fake  # type: ignore[assignment]

    parsed = service.parse_igsa_pdf_files([Path("a.pdf")])
    result = service.import_igsa_pdf_lines([object()], cliente_id="cliente-1")

    assert parsed == (["parsed"], ["parse-error"])
    assert result.ok is True
    assert fake.calls[0][0] == "parse_igsa_pdf_files"
    assert fake.calls[1][0] == "import_igsa_pdf_lines"
    assert fake.calls[1][2]["cliente_id"] == "cliente-1"
    assert callable(fake.calls[1][2]["sync_warehouse_callback"])
