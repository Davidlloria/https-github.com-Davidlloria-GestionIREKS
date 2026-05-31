from __future__ import annotations

from pathlib import Path

from app.services.settings_sales_import_service import SettingsSalesImportService


class _Result:
    def __init__(self, *, ok: bool, message: str, imported: int = 0, incidencias: int = 0) -> None:
        self.ok = ok
        self.message = message
        self.imported = imported
        self.incidencias = incidencias


class _FakeSalesService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def import_ireks_json(self, source: Path) -> _Result:
        self.calls.append(("import_ireks_json", (source,), {}))
        return _Result(ok=True, message="OK IREKS", imported=4, incidencias=1)

    def import_igsa_excel(self, source: Path) -> _Result:
        self.calls.append(("import_igsa_excel", (source,), {}))
        return _Result(ok=True, message="OK IGSA", imported=3, incidencias=0)

    def import_igsa_pdf_lines(self, lines: list[object], cliente_id: str) -> _Result:
        self.calls.append(("import_igsa_pdf_lines", (list(lines),), {"cliente_id": cliente_id}))
        return _Result(ok=False, message="ERROR PDF", imported=0, incidencias=2)

    def import_igsa_workbook_lines(
        self,
        lines: list[object],
        *,
        cliente_id: str,
        force_reimport: bool,
    ) -> _Result:
        self.calls.append(
            (
                "import_igsa_workbook_lines",
                (list(lines),),
                {"cliente_id": cliente_id, "force_reimport": force_reimport},
            )
        )
        return _Result(ok=True, message="OK BOOK", imported=7, incidencias=3)

    def rebuild_igsa_warehouse_movements(self, periodo: str) -> _Result:
        self.calls.append(("rebuild_igsa_warehouse_movements", (periodo,), {}))
        return _Result(ok=True, message="OK REBUILD", imported=11, incidencias=0)


class _FakeSettingsImportService:
    def __init__(self, cliente_id: str = "cliente-1") -> None:
        self.cliente_id = cliente_id

    def resolve_igsa_cliente_id(self) -> str:
        return self.cliente_id


def test_import_services_build_messages_and_logs(tmp_path: Path) -> None:
    fake = _FakeSalesService()
    service = SettingsSalesImportService(
        sales_service=fake,  # type: ignore[arg-type]
        settings_import_service=_FakeSettingsImportService(),
    )

    json_file = tmp_path / "ventas.json"
    json_file.write_text("[]", encoding="utf-8")
    ires = service.import_ireks_json(json_file)
    assert ires.ok is True
    assert "Registros: 4" in ires.message
    assert "Filas omitidas: 1" in ires.message
    assert "Importacion IREKS OK" in ires.log_message

    xlsx_file = tmp_path / "igsa.xlsx"
    xlsx_file.write_text("fake", encoding="utf-8")
    igsa = service.import_igsa_excel(xlsx_file)
    assert igsa.ok is True
    assert "Registros: 3" in igsa.message
    assert "Importacion IGSA OK" in igsa.log_message

    pdf = service.import_igsa_pdf_lines([{"row": 1}])
    assert pdf.ok is False
    assert "Filas omitidas: 2" in pdf.message
    assert "Importacion PDF IGSA ERROR" in pdf.log_message

    book = service.import_igsa_workbook_lines([{"row": 1}], force_reimport=True)
    assert book.ok is True
    assert "Registros: 7" in book.message
    assert "Filas omitidas: 3" in book.message
    assert "Importacion IGSA libro OK" in book.log_message

    rebuild = service.rebuild_igsa_warehouse_movements("2026-04")
    assert rebuild.ok is True
    assert "Filas procesadas: 11" in rebuild.message
    assert "Regenerar IGSA OK" in rebuild.log_message

    assert [name for name, _args, _kwargs in fake.calls] == [
        "import_ireks_json",
        "import_igsa_excel",
        "import_igsa_pdf_lines",
        "import_igsa_workbook_lines",
        "rebuild_igsa_warehouse_movements",
    ]


def test_validations_raise_value_error(tmp_path: Path) -> None:
    fake = _FakeSalesService()
    service = SettingsSalesImportService(
        sales_service=fake,  # type: ignore[arg-type]
        settings_import_service=_FakeSettingsImportService(),
    )

    invalid_file = tmp_path / "ventas.txt"
    invalid_file.write_text("x", encoding="utf-8")
    try:
        service.import_ireks_json(invalid_file)
    except ValueError as exc:
        assert ".json" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for non-json file")

    missing = tmp_path / "missing.xlsx"
    try:
        service.import_igsa_excel(missing)
    except ValueError as exc:
        assert "no existe" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for missing file")

    try:
        service.import_igsa_pdf_lines([])
    except ValueError as exc:
        assert "vista previa" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for empty lines")

    no_client = SettingsSalesImportService(
        sales_service=fake,  # type: ignore[arg-type]
        settings_import_service=_FakeSettingsImportService(cliente_id=""),
    )
    try:
        no_client.import_igsa_workbook_lines([{"row": 1}])
    except ValueError as exc:
        assert "cliente/distribuidor" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for unresolved IGSA client")

    try:
        service.rebuild_igsa_warehouse_movements("04-2026")
    except ValueError as exc:
        assert "aaaa-mm" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for invalid periodo format")
