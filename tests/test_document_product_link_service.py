from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.services.document_library_service import DocumentLibraryService
from app.services.document_product_link_service import (
    AUTOMATIC_FILENAME_ORIGIN,
    TECHNICAL_SHEET_RELATION,
    DocumentProductLinkError,
    DocumentProductLinkService,
)


def _create_product_database(path: Path, products: list[tuple[object, ...]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE fabricantes (
                fabricante_id TEXT PRIMARY KEY,
                fabricante_nombre TEXT NOT NULL
            );
            CREATE TABLE productos_ireks (
                articulo_id TEXT PRIMARY KEY,
                articulo_referencia_corta TEXT NOT NULL,
                articulo_referencia TEXT NOT NULL,
                articulo_status_activo INTEGER NOT NULL,
                fabricante_id TEXT
            );
            INSERT INTO fabricantes VALUES ('ireks', 'IREKS');
            INSERT INTO fabricantes VALUES ('dreidoppel', 'DREIDOPPEL');
            INSERT INTO fabricantes VALUES ('gelatop', 'GELATOP');
            """
        )
        connection.executemany(
            """INSERT INTO productos_ireks (
                   articulo_id, articulo_referencia_corta, articulo_referencia,
                   articulo_status_activo, fabricante_id
               ) VALUES (?, ?, ?, ?, ?)""",
            products,
        )


def _create_document_catalog(library: Path, database: Path, paths: list[str]) -> None:
    for relative_path in paths:
        path = library / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"pdf")
    DocumentLibraryService(library, database).refresh_catalog()


def _service(tmp_path: Path, products: list[tuple[object, ...]], paths: list[str]):
    product_database = tmp_path / "gestion_ireks.db"
    document_database = tmp_path / "document_library.sqlite"
    library = tmp_path / "Documentos"
    _create_product_database(product_database, products)
    _create_document_catalog(library, document_database, paths)
    service = DocumentProductLinkService(
        product_database,
        document_database,
        clock=lambda: datetime(2026, 8, 30, tzinfo=timezone.utc),
    )
    return library, document_database, service


def test_sync_links_unique_technical_sheets_for_all_manufacturers(tmp_path: Path) -> None:
    _, _, service = _service(
        tmp_path,
        [
            ("ireks-product", "14715", "114715E", 1, "ireks"),
            ("dreidoppel-product", "D1164038", "D1164038", 1, "dreidoppel"),
            ("gelatop-product", "D125008", "D125008", 1, "gelatop"),
        ],
        [
            "FICHAS TECNICAS/IREKS/114715E_es_MELLA TOP BISKUIT.pdf",
            "FICHAS TECNICAS/DREIDOPPEL/AROMAS/16403.SUPRANIL.pdf",
            "FICHAS TECNICAS/GELATOP/Español/12500.BASE 50 ANIVERSARIO.pdf",
            "TECNICO/RECETAS/114715E_receta.pdf",
        ],
    )

    result = service.sync_technical_sheets()
    links = service.list_links()

    assert result.technical_documents == 3
    assert result.linked == result.created == 3
    assert result.updated == result.unchanged == result.removed == 0
    assert result.unmatched == result.ambiguous == 0
    assert {link.product_articulo_id for link in links} == {
        "ireks-product",
        "dreidoppel-product",
        "gelatop-product",
    }
    assert {link.matched_code for link in links} == {"114715E", "16403", "12500"}
    assert {link.relation_type for link in links} == {TECHNICAL_SHEET_RELATION}
    assert {link.origin for link in links} == {AUTOMATIC_FILENAME_ORIGIN}
    ireks_documents = service.list_product_documents("ireks-product")
    assert len(ireks_documents) == 1
    assert ireks_documents[0].name == "114715E_es_MELLA TOP BISKUIT.pdf"
    assert ireks_documents[0].category == "IREKS"
    assert ireks_documents[0].relation_type == TECHNICAL_SHEET_RELATION


def test_product_documents_exclude_inactive_catalog_records(tmp_path: Path) -> None:
    library, document_database, service = _service(
        tmp_path,
        [("product", "14715", "114715E", 1, "ireks")],
        ["FICHAS TECNICAS/IREKS/114715E_ficha.pdf"],
    )
    service.sync_technical_sheets()
    assert len(service.list_product_documents("product")) == 1

    (library / "FICHAS TECNICAS/IREKS/114715E_ficha.pdf").unlink()
    DocumentLibraryService(library, document_database).refresh_catalog()

    assert service.list_product_documents("product") == []
    assert service.list_product_documents("") == []


def test_sync_prioritizes_one_active_duplicate_and_rejects_active_ambiguity(
    tmp_path: Path,
) -> None:
    _, _, service = _service(
        tmp_path,
        [
            ("cream-old", "D1265049", "D1265049", 0, "dreidoppel"),
            ("cream-active", "D1265049", "D1265049", 1, "dreidoppel"),
            ("supranil-a", "D1164038", "D1164038", 1, "dreidoppel"),
            ("supranil-b", "D1164038", "D1164038", 1, "dreidoppel"),
        ],
        [
            "FICHAS TECNICAS/DREIDOPPEL/26504.PASTA CREAM LIQUEUR.pdf",
            "FICHAS TECNICAS/DREIDOPPEL/16403.SUPRANIL.pdf",
        ],
    )

    result = service.sync_technical_sheets()

    assert result.linked == result.created == 1
    assert result.ambiguous == 1
    assert result.unmatched == 0
    assert [link.product_articulo_id for link in service.list_links()] == ["cream-active"]


def test_sync_reports_unmatched_and_ignores_non_technical_documents(tmp_path: Path) -> None:
    _, _, service = _service(
        tmp_path,
        [("product", "14715", "114715E", 1, "ireks")],
        [
            "FICHAS TECNICAS/IREKS/sin-codigo.pdf",
            "FICHAS TECNICAS/OTRO/114715E_desconocido.pdf",
            "TECNICO/RECETAS/114715E_receta.pdf",
        ],
    )

    result = service.sync_technical_sheets()

    assert result.technical_documents == 2
    assert result.unmatched == 2
    assert result.linked == result.created == result.ambiguous == 0
    assert service.list_links() == []


def test_second_sync_is_unchanged_and_removes_obsolete_automatic_links(
    tmp_path: Path,
) -> None:
    library, document_database, service = _service(
        tmp_path,
        [("product", "14715", "114715E", 1, "ireks")],
        [
            "FICHAS TECNICAS/IREKS/114715E_ficha.pdf",
            "FICHAS TECNICAS/IREKS/aviso.pdf",
        ],
    )
    first = service.sync_technical_sheets()
    second = service.sync_technical_sheets()
    manual_document = next(
        document
        for document in DocumentLibraryService(library, document_database).list_documents()
        if document.name == "aviso.pdf"
    )
    with sqlite3.connect(document_database) as connection:
        connection.execute(
            """INSERT INTO document_product_links (
                   document_id, product_articulo_id, relation_type, origin,
                   matched_code, created_at, updated_at
               ) VALUES (?, ?, ?, 'manual', '', 'now', 'now')""",
            (manual_document.document_id, "manual-product", TECHNICAL_SHEET_RELATION),
        )

    (library / "FICHAS TECNICAS/IREKS/114715E_ficha.pdf").unlink()
    DocumentLibraryService(library, document_database).refresh_catalog()
    third = service.sync_technical_sheets()

    assert first.created == 1
    assert second.unchanged == 1
    assert second.created == second.updated == second.removed == 0
    assert third.removed == 1
    assert [(link.product_articulo_id, link.origin) for link in service.list_links()] == [
        ("manual-product", "manual")
    ]


def test_missing_source_databases_raise_specific_errors(tmp_path: Path) -> None:
    missing_products = tmp_path / "missing-products.sqlite"
    missing_documents = tmp_path / "missing-documents.sqlite"

    with pytest.raises(DocumentProductLinkError, match="productos"):
        DocumentProductLinkService(missing_products, missing_documents).sync_technical_sheets()

    _create_product_database(missing_products, [])
    with pytest.raises(DocumentProductLinkError, match="documental"):
        DocumentProductLinkService(missing_products, missing_documents).sync_technical_sheets()
