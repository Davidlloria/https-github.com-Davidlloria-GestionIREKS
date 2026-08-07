import json
from pathlib import Path

from openpyxl import Workbook
import pytest
from sqlmodel import SQLModel, Session, create_engine, select

import app.services.sales_reconciliation_service as sales_reconciliation_service_module
from app.models import AlmacenMovimiento, Distribuidor, IngredienteIreks, VentaMensualRaw
from app.services.sales_reconciliation_service import ClientesImportPreview, SalesReconciliationService


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


@pytest.fixture()
def isolated_sales_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'sales-reconciliation.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(sales_reconciliation_service_module, "engine", engine)
    return engine


def _build_igsa_consolidado_workbook(path: Path, *, include_invalid: bool = False) -> None:
    workbook = Workbook()
    ws = workbook.active
    ws.title = "consolidado"
    ws.append(
        [
            "Empresa",
            "Empresa ID",
            "Año",
            "Mes",
            "Nº mes",
            "Tipo salida",
            "Ref distribuidor",
            "Ref corta",
            "ID",
            "Descripción",
            "Cantidad",
            "Lote",
            "Caducidad",
            "Observaciones",
        ]
    )
    ws.append(["IGSA", "dist-igsa", 2026, "JULIO", 7, "Venta", 36, "D123", "art-1", "Producto Excel", 4, "L001", None, None])
    ws.append(["IGSA", "dist-igsa", 2026, "JULIO", 7, "Muestra", 36, "D123", "art-1", "Producto Excel", 2, "L002", None, None])
    if include_invalid:
        ws.append(["IGSA", "dist-igsa", 2026, "JULIO", 7, "Venta", 99, "D999", "missing-art", "Producto sin ficha", 1, "L003", None, None])
    workbook.save(path)


def _seed_igsa_product(session: Session) -> None:
    session.add(Distribuidor(distribuidor_id="dist-igsa", distribuidor_codigo=2, distribuidor_nombre_comercial="IGSA"))
    session.add(
        IngredienteIreks(
            articulo_id="art-1",
            almacen_id="alm-central",
            distribuidor_id="dist-igsa",
            articulo_referencia="D123",
            articulo_referencia_corta="D123",
            articulo_descripcion="Producto ficha",
            articulo_envase_peso_total=2.5,
            articulo_envase_peso=2.5,
        )
    )
    session.commit()


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


def test_preview_igsa_excel_reads_consolidado_and_classifies_sc(isolated_sales_engine, tmp_path: Path) -> None:
    workbook_path = tmp_path / "igsa-julio.xlsx"
    _build_igsa_consolidado_workbook(workbook_path, include_invalid=True)
    with Session(isolated_sales_engine) as session:
        _seed_igsa_product(session)

    preview = SalesReconciliationService().preview_igsa_excel(workbook_path)

    assert preview.total_rows == 3
    assert preview.valid_rows == 2
    assert preview.invalid_rows == 1
    assert preview.periodos == ["2026-07"]
    assert preview.preview_rows[0]["destino"] == "Venta"
    assert preview.preview_rows[0]["kilos"] == 10.0
    assert preview.preview_rows[1]["destino"] == "S/C"
    assert preview.preview_rows[1]["kilos"] == 5.0
    assert any("missing-art" in issue for issue in preview.issues)


def test_import_igsa_excel_persists_sales_and_warehouse_outputs(isolated_sales_engine, tmp_path: Path) -> None:
    workbook_path = tmp_path / "igsa-julio.xlsx"
    _build_igsa_consolidado_workbook(workbook_path)
    with Session(isolated_sales_engine) as session:
        _seed_igsa_product(session)

    result = SalesReconciliationService().import_igsa_excel(workbook_path)

    assert result.ok is True
    assert result.imported == 2
    assert result.incidencias == 0
    with Session(isolated_sales_engine) as session:
        rows = list(session.exec(select(VentaMensualRaw).order_by(VentaMensualRaw.venta_kilos.desc())))
        assert len(rows) == 2
        assert rows[0].fuente == "igsa"
        assert rows[0].cliente_id == "dist-igsa"
        assert rows[0].periodo == "2026-07"
        assert rows[0].venta_kilos == 10.0
        assert rows[0].venta_kilos_sc == 0.0
        assert rows[1].venta_kilos == 0.0
        assert rows[1].venta_kilos_sc == 5.0
        movements = list(session.exec(select(AlmacenMovimiento).order_by(AlmacenMovimiento.articulo_lote)))
        assert len(movements) == 2
        assert {movement.almacen_id for movement in movements} == {"dist-igsa"}
        assert [movement.cantidad for movement in movements] == [-4.0, -2.0]
        assert {movement.pedido_numero for movement in movements} == {"IGSA-2026-07"}

    second = SalesReconciliationService().import_igsa_excel(workbook_path)

    assert second.ok is True
    assert second.imported == 2
    with Session(isolated_sales_engine) as session:
        assert len(list(session.exec(select(VentaMensualRaw)))) == 2
        assert len(list(session.exec(select(AlmacenMovimiento)))) == 2


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


def test_parse_clientes_workbook_expands_ventas_bruto_month_columns(tmp_path) -> None:
    path = tmp_path / "clientes.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Ventas_Bruto"
    sheet.append(
        [
            "UUID Cliente",
            "Codigo IREKS",
            "Codigo IGSA",
            "Cliente",
            "Marca",
            "UUID Producto",
            "Codigo Producto",
            "Nombre Porducto",
            "Año",
            "ENERO",
            "FEBRERO",
            "MARZO",
            "TOTAL",
        ]
    )
    sheet.append(
        [
            "cliente-1",
            502,
            "1000 301",
            "Cliente Uno",
            "IREKS",
            "producto-1",
            "3874",
            "Producto Excel",
            2026,
            2,
            None,
            3,
            5,
        ]
    )
    workbook.save(path)

    rows, year = SalesReconciliationService()._parse_clientes_workbook(path)

    assert year == 2026
    assert [(row.anio, row.mes, row.unidades) for row in rows] == [(2026, 1, 2.0), (2026, 3, 3.0)]
    assert rows[0].cliente_codigo_distribuidor == "1000 301"
    assert rows[0].articulo_id == "producto-1"
    assert rows[0].articulo_codigo_excel == "3874"
    assert rows[0].articulo_descripcion == "Producto Excel"


def test_import_clientes_from_preview_uses_only_importable_rows(tmp_path, monkeypatch) -> None:
    path = tmp_path / "clientes.xlsx"
    path.write_bytes(b"preview-test")

    preview_rows = [
        {
            "source_row": 2,
            "anio": 2026,
            "mes": 3,
            "mes_nombre": "MARZO",
            "cliente_id": "cliente-1",
            "cliente_codigo": "C001",
            "cliente_codigo_distribuidor": "1000 301",
            "cliente_nombre": "Cliente Uno",
            "articulo_codigo": "DIST-01",
            "articulo_id": "prod-1",
            "articulo_codigo_corto": "IREKS-01",
            "articulo_codigo_excel": "DIST-01",
            "articulo_descripcion_excel": "Producto Uno Excel",
            "articulo_descripcion": "Producto Uno",
            "articulo_label": "IREKS-01 - Producto Uno",
            "envase": 12.5,
            "unidades": 4,
            "kg": 50.0,
            "precio_kg": 0.0,
            "euros": 0.0,
            "status": "warning",
            "issue_text": "sin tarifa valida para el ano 2026 del producto IREKS IREKS-01 - Producto Uno; se importara con precio 0.",
            "can_import": True,
        },
        {
            "source_row": 3,
            "anio": 2026,
            "cliente_id": "cliente-2",
            "cliente_codigo": "C002",
            "cliente_nombre": "Cliente Dos",
            "articulo_codigo": "DIST-02",
            "articulo_id": "prod-2",
            "articulo_codigo_corto": "",
            "articulo_descripcion": "Producto Dos",
            "articulo_label": "Producto Dos",
            "envase": 0.0,
            "unidades": 0.0,
            "kg": 0.0,
            "precio_kg": 0.0,
            "euros": 0.0,
            "status": "error",
            "issue_text": "Cliente no valido o no indirecto (cliente-2).",
            "can_import": False,
        },
    ]
    preview = ClientesImportPreview(
        total_rows=2,
        valid_rows=1,
        invalid_rows=1,
        preview_rows=preview_rows,
        issues=[preview_rows[0]["issue_text"], preview_rows[1]["issue_text"]],
        anio=2026,
        duplicate_rows=0,
        import_rows=[preview_rows[0]],
    )

    fake_session_factory = _FakeSessionFactory()
    monkeypatch.setattr("app.services.sales_reconciliation_service.Session", fake_session_factory)

    service = SalesReconciliationService()
    result = service._import_clientes_from_preview(path, preview, replace_existing=False)

    assert result.ok is True
    assert result.imported == 1
    assert result.incidencias == 2
    assert fake_session_factory.last_session is not None
    inserted_rows = [obj for obj in fake_session_factory.last_session.added if obj.__class__.__name__ == "VentaClientesRaw"]
    assert len(inserted_rows) == 1
    assert inserted_rows[0].cliente_id == "cliente-1"
    assert inserted_rows[0].articulo_id == "prod-1"
    assert inserted_rows[0].mes == 3
    assert inserted_rows[0].precio_kg == 0.0
    assert any("Cliente no valido" in line for line in result.warnings)


def test_resolve_tarifa_precio_kg_converts_envase_price_to_kg_price(monkeypatch) -> None:
    class _Tarifa:
        precio_distribuidor = 41.95
        precio_fabricante = 0.0

    class _ExecResult:
        def first(self):
            return _Tarifa()

    class _Session:
        def exec(self, _stmt):
            return _ExecResult()

    service = SalesReconciliationService()

    precio_kg = service._resolve_tarifa_precio_kg(_Session(), "product-1", 2025, envase_peso=12.5)

    assert round(precio_kg, 2) == 3.36
