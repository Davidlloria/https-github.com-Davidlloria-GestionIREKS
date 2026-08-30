from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

import app.services.document_library_service as document_library_module
from app.core import config
from app.services.document_library_service import (
    DocumentLibraryService,
    DocumentNotFoundError,
    UnsafeDocumentPathError,
)


def _write_document(path: Path, content: bytes = b"document") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _service(
    library: Path,
    database: Path,
    *,
    clock=None,
) -> DocumentLibraryService:
    return DocumentLibraryService(library, database, clock=clock)


def test_default_configuration_uses_portable_sibling_and_separate_database() -> None:
    if not config._DOCUMENTS_DIR_ENV:
        assert config.DOCUMENTS_DIR == config.BASE_DIR.parent / "Documentos"
    assert config.DOCUMENT_LIBRARY_DB_PATH == config.DATA_DIR / "document_library.sqlite"


def test_first_catalog_records_supported_metadata_recursively(tmp_path: Path) -> None:
    library = tmp_path / "Documentos"
    database = tmp_path / "data" / "document_library.sqlite"
    paths = [
        "Calidad/Fichas/ficha.PDF",
        "Calidad/Tablas/datos.xlsx",
        "Ventas/precios.xls",
        "Tecnica/manual.docx",
        "Notas/inicio.md",
        "Notas/guia.markdown",
    ]
    for relative_path in paths:
        _write_document(library / relative_path)
    _write_document(library / "Notas/ignorado.txt")

    service = _service(library, database)
    result = service.refresh_catalog()
    documents = service.list_documents()

    assert result.available is True
    assert result.scan_complete is True
    assert result.added == len(paths)
    assert result.updated == result.unchanged == result.deactivated == 0
    assert database.is_file()
    assert len(documents) == len(paths)
    assert {document.extension for document in documents} == {
        ".pdf",
        ".xlsx",
        ".xls",
        ".docx",
        ".md",
        ".markdown",
    }
    ficha = next(document for document in documents if document.name == "ficha.PDF")
    assert ficha.area == "Calidad"
    assert ficha.category == "Fichas"
    assert ficha.relative_path == "Calidad/Fichas/ficha.PDF"
    assert ficha.size_bytes == len(b"document")
    assert len(ficha.document_id) == 64
    assert ficha.active is True


def test_second_scan_without_changes_preserves_indexing_date(tmp_path: Path) -> None:
    library = tmp_path / "library"
    database = tmp_path / "catalog.sqlite"
    _write_document(library / "Calidad/ficha.pdf")
    times = iter(
        (
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
    )
    service = _service(library, database, clock=lambda: next(times))

    first = service.refresh_catalog()
    first_item = service.list_documents()[0]
    second = service.refresh_catalog()
    second_item = service.list_documents()[0]

    assert first.added == 1
    assert second.added == second.updated == second.deactivated == 0
    assert second.unchanged == 1
    assert second_item.document_id == first_item.document_id
    assert second_item.indexed_at == first_item.indexed_at


def test_modified_file_updates_metadata_and_keeps_identifier(tmp_path: Path) -> None:
    library = tmp_path / "library"
    database = tmp_path / "catalog.sqlite"
    path = _write_document(library / "Tecnica/manual.docx", b"old")
    times = iter(
        (
            datetime(2026, 2, 1, tzinfo=timezone.utc),
            datetime(2026, 2, 2, tzinfo=timezone.utc),
        )
    )
    service = _service(library, database, clock=lambda: next(times))
    service.refresh_catalog()
    before = service.list_documents()[0]

    path.write_bytes(b"new and larger content")
    result = service.refresh_catalog()
    after = service.list_documents()[0]

    assert result.updated == 1
    assert result.added == result.unchanged == result.deactivated == 0
    assert after.document_id == before.document_id
    assert after.size_bytes == len(b"new and larger content")
    assert after.indexed_at != before.indexed_at


def test_disappeared_file_is_marked_inactive(tmp_path: Path) -> None:
    library = tmp_path / "library"
    database = tmp_path / "catalog.sqlite"
    path = _write_document(library / "Ventas/precios.xlsx")
    service = _service(library, database)
    service.refresh_catalog()

    path.unlink()
    result = service.refresh_catalog()

    assert result.scan_complete is True
    assert result.deactivated == 1
    assert service.list_documents() == []
    all_documents = service.list_documents(active=None)
    assert len(all_documents) == 1
    assert all_documents[0].active is False


def test_unavailable_library_does_not_deactivate_catalog(tmp_path: Path) -> None:
    library = tmp_path / "library"
    database = tmp_path / "catalog.sqlite"
    _write_document(library / "Calidad/ficha.pdf")
    service = _service(library, database)
    service.refresh_catalog()
    assert service.is_library_available() is True
    library.rename(tmp_path / "library-offline")

    result = service.refresh_catalog()

    assert service.is_library_available() is False
    assert result.available is False
    assert result.scan_complete is False
    assert result.deactivated == 0
    assert service.list_documents()[0].active is True


def test_failed_scan_does_not_deactivate_catalog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library = tmp_path / "library"
    database = tmp_path / "catalog.sqlite"
    _write_document(library / "Calidad/ficha.pdf")
    service = _service(library, database)
    service.refresh_catalog()

    def failed_walk(*_args, onerror=None, **_kwargs):
        assert onerror is not None
        onerror(PermissionError("scan denied"))
        return iter(())

    monkeypatch.setattr(document_library_module.os, "walk", failed_walk)
    result = service.refresh_catalog()

    assert result.available is True
    assert result.scan_complete is False
    assert result.deactivated == 0
    assert "scan denied" in result.errors[0]
    assert service.list_documents()[0].active is True


def test_catalog_filters_by_query_area_category_extension_and_status(tmp_path: Path) -> None:
    library = tmp_path / "library"
    database = tmp_path / "catalog.sqlite"
    _write_document(library / "Calidad/Fichas/Trigo.pdf")
    removed = _write_document(library / "Calidad/Normas/Antigua.docx")
    _write_document(library / "Ventas/Tarifas/Precios.xlsx")
    service = _service(library, database)
    service.refresh_catalog()
    removed.unlink()
    service.refresh_catalog()

    assert [item.name for item in service.list_documents(query="trigo")] == ["Trigo.pdf"]
    assert {item.name for item in service.list_documents(area="calidad")} == {"Trigo.pdf"}
    assert [item.name for item in service.list_documents(category="tarifas")] == [
        "Precios.xlsx"
    ]
    assert [item.name for item in service.list_documents(extension="PDF")] == ["Trigo.pdf"]
    assert [item.name for item in service.list_documents(active=False)] == ["Antigua.docx"]


def test_resolve_by_identifier_rejects_paths_outside_library(tmp_path: Path) -> None:
    library = tmp_path / "library"
    database = tmp_path / "catalog.sqlite"
    _write_document(library / "Calidad/ficha.pdf")
    outside = _write_document(tmp_path / "outside.pdf")
    service = _service(library, database)
    service.refresh_catalog()
    item = service.list_documents()[0]

    assert service.resolve_document(item.document_id) == library / "Calidad/ficha.pdf"
    with pytest.raises(DocumentNotFoundError):
        service.resolve_document(str(outside.resolve()))

    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE documents SET relative_path = ? WHERE document_id = ?",
            ("../outside.pdf", item.document_id),
        )

    with pytest.raises(UnsafeDocumentPathError):
        service.resolve_document(item.document_id)
