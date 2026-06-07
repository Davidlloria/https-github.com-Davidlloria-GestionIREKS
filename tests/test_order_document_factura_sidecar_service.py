from __future__ import annotations

import json
from pathlib import Path

from app.services.order_document_factura_sidecar_service import OrderDocumentFacturaSidecarService


def _write_sidecar(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_load_rows_accepts_valid_sidecar(tmp_path: Path) -> None:
    pdf_path = tmp_path / "factura_60003.pdf"
    pdf_path.write_text("")
    _write_sidecar(
        tmp_path / "factura_60003_sidecar.json",
        [
            {
                "Factura": "60003",
                "Codigo": "D1329086",
                "Lote": "2510061",
                "Descripcion": "POWERFULLUNG MELOCOTON - MARACUYA",
                "Fecha": "19/01/26",
                "Albaran": "2026090005",
                "Uds": "198",
                "Precio": "6,20",
                "Dto": "20,0",
                "Caducidad": "01/10/26",
            }
        ],
    )

    rows = OrderDocumentFacturaSidecarService().load_rows(pdf_path, "60003")

    assert len(rows) == 1
    assert rows[0]["factura_numero"] == "60003"
    assert rows[0]["factura_referencia"] == ""
    assert rows[0]["articulo_codigo"] == "D1329086"
    assert rows[0]["articulo_lote"] == "2510061"
    assert rows[0]["dto_pct"] == "20,0"


def test_load_rows_ignores_corrupt_json(tmp_path: Path) -> None:
    pdf_path = tmp_path / "factura_60003.pdf"
    pdf_path.write_text("")
    (tmp_path / "factura_60003_bad.json").write_text("{", encoding="utf-8")

    rows = OrderDocumentFacturaSidecarService().load_rows(pdf_path, "60003")

    assert rows == []


def test_load_rows_ignores_non_list_payload(tmp_path: Path) -> None:
    pdf_path = tmp_path / "factura_60003.pdf"
    pdf_path.write_text("")
    _write_sidecar(tmp_path / "factura_60003_bad.json", {"Factura": "60003"})

    rows = OrderDocumentFacturaSidecarService().load_rows(pdf_path, "60003")

    assert rows == []


def test_load_rows_requires_codigo_and_lote(tmp_path: Path) -> None:
    pdf_path = tmp_path / "factura_60003.pdf"
    pdf_path.write_text("")
    _write_sidecar(
        tmp_path / "factura_60003_bad.json",
        [{"Factura": "60003", "Codigo": "", "Lote": "2510061"}],
    )

    rows = OrderDocumentFacturaSidecarService().load_rows(pdf_path, "60003")

    assert rows == []


def test_load_rows_skips_non_matching_filename(tmp_path: Path) -> None:
    pdf_path = tmp_path / "factura_60003.pdf"
    pdf_path.write_text("")
    _write_sidecar(
        tmp_path / "factura_99999_sidecar.json",
        [{"Factura": "60003", "Codigo": "D1329086", "Lote": "2510061"}],
    )

    rows = OrderDocumentFacturaSidecarService().load_rows(pdf_path, "60003")

    assert rows == []


def test_load_rows_normalizes_keys_with_and_without_accents(tmp_path: Path) -> None:
    pdf_path = tmp_path / "factura_60003.pdf"
    pdf_path.write_text("")
    _write_sidecar(
        tmp_path / "factura_60003_sidecar.json",
        [
            {
                "Factura": "60003",
                "CÃ³digo": "D1329086",
                "Lote": "2510061",
                "DescripciÃ³n": "POWERFULLUNG MELOCOTON - MARACUYA",
                "Unidades": "198",
                "Caducidad": "01/10/26",
            }
        ],
    )

    rows = OrderDocumentFacturaSidecarService().load_rows(pdf_path, "60003")

    assert len(rows) == 1
    assert rows[0]["articulo_codigo"] == "D1329086"
    assert rows[0]["articulo_descripcion"] == "POWERFULLUNG MELOCOTON - MARACUYA"
    assert rows[0]["articulo_cantidad"] == "198"
    assert rows[0]["articulo_caducidad"] == "01/10/26"
