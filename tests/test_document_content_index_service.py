from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import fitz
import pytest

from app.services.document_content_index_service import (
    MAX_SEARCH_RESULTS,
    DocumentContentCatalogNotInitializedError,
    DocumentContentIndexService,
)
from app.services.document_library_service import DocumentLibraryService


def _write_pdf(path: Path, pages: list[str | None]) -> Path:
    if path.exists():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    document = fitz.open()
    try:
        for text in pages:
            page = document.new_page()
            if text:
                page.insert_text((72, 72), text)
        document.save(path)
    finally:
        document.close()
    return path


def _write_markdown(path: Path, text: str, *, bom: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoding = "utf-8-sig" if bom else "utf-8"
    path.write_text(text, encoding=encoding)
    return path


def _build_services(
    tmp_path: Path,
) -> tuple[Path, Path, DocumentLibraryService, DocumentContentIndexService]:
    library = tmp_path / "library"
    library.mkdir()
    database = tmp_path / "data" / "document_library.sqlite"
    catalog = DocumentLibraryService(library, database)
    content = DocumentContentIndexService(catalog, database)
    return library, database, catalog, content


def _status(database: Path, document_id: str) -> sqlite3.Row:
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT * FROM document_content_status WHERE document_id = ?",
            (document_id,),
        ).fetchone()
    assert row is not None
    return row


def _bump_mtime(path: Path, previous_ns: int) -> None:
    current = path.stat().st_mtime_ns
    target = max(current, previous_ns + 1_000_000_000)
    os.utime(path, ns=(target, target))


def test_indexes_multipage_pdf_and_preserves_page_numbers(tmp_path: Path) -> None:
    library, _, catalog, content = _build_services(tmp_path)
    _write_pdf(
        library / "Tecnica/Manuales/Proceso.pdf",
        ["Primera pagina con amasado", "Segunda pagina con fermentacion"],
    )
    catalog.refresh_catalog()

    result = content.update_index()
    first_page = content.search("amasado")
    second_page = content.search("fermentacion")

    assert result.candidates == result.indexed == 1
    assert result.failed == result.no_text == 0
    assert first_page[0].page_number == 1
    assert second_page[0].page_number == 2
    assert "fermentacion" in second_page[0].fragment.casefold()


def test_indexes_markdown_as_page_one_and_preserves_headers(tmp_path: Path) -> None:
    library, database, catalog, content = _build_services(tmp_path)
    _write_markdown(
        library / "Calidad/Guias/masa.md",
        "# Guía de masa\n\nCódigo   ABC-42 y  25 kg",
        bom=True,
    )
    catalog.refresh_catalog()
    document = catalog.list_documents()[0]

    result = content.update_index()
    matches = content.search("codigo ABC 42")
    with sqlite3.connect(database) as connection:
        stored_text = connection.execute(
            "SELECT text FROM document_pages_fts WHERE document_id = ?",
            (document.document_id,),
        ).fetchone()[0]

    assert result.indexed == 1
    assert matches[0].page_number == 1
    assert "# Guía de masa" in stored_text
    assert "Código ABC-42 y 25 kg" in stored_text


def test_second_update_skips_unchanged_document(tmp_path: Path) -> None:
    library, _, catalog, content = _build_services(tmp_path)
    _write_markdown(library / "Notas/estable.md", "Contenido estable")
    catalog.refresh_catalog()
    first = content.update_index()

    second = content.update_index()

    assert first.indexed == 1
    assert second.candidates == 1
    assert second.unchanged == 1
    assert second.indexed == second.failed == second.no_text == 0


def test_modified_document_replaces_all_old_pages_transactionally(tmp_path: Path) -> None:
    library, database, catalog, content = _build_services(tmp_path)
    path = _write_pdf(
        library / "Tecnica/cambio.pdf",
        ["contenido antiguo uno", "contenido antiguo dos"],
    )
    catalog.refresh_catalog()
    document_id = catalog.list_documents()[0].document_id
    content.update_index()
    previous_ns = path.stat().st_mtime_ns

    _write_pdf(path, ["contenido completamente nuevo"])
    _bump_mtime(path, previous_ns)
    catalog.refresh_catalog()
    result = content.update_index()

    assert result.indexed == 1
    assert content.search("antiguo") == []
    assert content.search("completamente nuevo")[0].page_number == 1
    with sqlite3.connect(database) as connection:
        pages = connection.execute(
            "SELECT COUNT(*) FROM document_pages_fts WHERE document_id = ?",
            (document_id,),
        ).fetchone()[0]
    assert pages == 1


def test_valid_pdf_without_text_is_marked_no_text(tmp_path: Path) -> None:
    library, database, catalog, content = _build_services(tmp_path)
    _write_pdf(library / "Escaneados/vacio.pdf", [None, None])
    catalog.refresh_catalog()
    document = catalog.list_documents()[0]

    result = content.update_index()
    status = _status(database, document.document_id)

    assert result.no_text == 1
    assert result.failed == 0
    assert status["status"] == "no_text"
    assert status["page_count"] == 2
    assert status["error_message"] is None


def test_corrupt_pdf_is_failed_without_stopping_batch(tmp_path: Path) -> None:
    library, database, catalog, content = _build_services(tmp_path)
    corrupt = library / "Calidad/corrupto.pdf"
    corrupt.parent.mkdir(parents=True)
    corrupt.write_bytes(b"not a pdf")
    _write_markdown(library / "Calidad/valido.md", "Documento valido posterior")
    catalog.refresh_catalog()
    documents = {item.name: item for item in catalog.list_documents()}

    result = content.update_index()

    assert result.candidates == 2
    assert result.failed == 1
    assert result.indexed == 1
    assert _status(database, documents["corrupto.pdf"].document_id)["status"] == "failed"
    assert content.search("posterior")[0].name == "valido.md"
    assert all(str(library) not in error for error in result.errors)


def test_invalid_markdown_encoding_is_failed(tmp_path: Path) -> None:
    library, database, catalog, content = _build_services(tmp_path)
    path = library / "Notas/invalido.md"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"\xff\xfe\xfa")
    catalog.refresh_catalog()
    document = catalog.list_documents()[0]

    result = content.update_index()

    assert result.failed == 1
    assert _status(database, document.document_id)["status"] == "failed"


def test_inactive_document_is_excluded_from_search(tmp_path: Path) -> None:
    library, _, catalog, content = _build_services(tmp_path)
    path = _write_markdown(library / "Notas/retirado.md", "termino retirado")
    catalog.refresh_catalog()
    content.update_index()
    assert content.search("retirado")

    path.unlink()
    catalog.refresh_catalog()

    assert content.search("retirado") == []


def test_unavailable_library_preserves_existing_index(tmp_path: Path) -> None:
    library, _, catalog, content = _build_services(tmp_path)
    _write_markdown(library / "Notas/disponible.md", "contenido conservado")
    catalog.refresh_catalog()
    content.update_index()
    library.rename(tmp_path / "library-offline")

    result = content.update_index()

    assert result.candidates == 0
    assert result.errors == ("La biblioteca documental no está disponible.",)
    assert content.search("conservado")[0].name == "disponible.md"


def test_search_is_case_and_accent_insensitive_and_supports_filters(tmp_path: Path) -> None:
    library, _, catalog, content = _build_services(tmp_path)
    _write_markdown(
        library / "Calidad/Procesos/pan.md",
        "Panadería artesanal con árbol de decisión",
    )
    _write_markdown(
        library / "Ventas/Argumentos/pan.md",
        "Panadería comercial con promociones",
    )
    catalog.refresh_catalog()
    content.update_index()

    matches = content.search(
        "PANADERIA ARBOL",
        area="calidad",
        category="procesos",
    )

    assert len(matches) == 1
    assert matches[0].area == "Calidad"
    assert matches[0].category == "Procesos"


def test_special_characters_are_text_not_fts_syntax(tmp_path: Path) -> None:
    library, _, catalog, content = _build_services(tmp_path)
    _write_markdown(library / "Notas/especial.md", "Panadería segura y local")
    catalog.refresh_catalog()
    content.update_index()

    assert content.search('panadería* "')
    assert content.search('" OR 1=1 --') == []
    assert content.search("") == []


def test_search_limit_is_capped_and_results_do_not_expose_absolute_paths(
    tmp_path: Path,
) -> None:
    library, _, catalog, content = _build_services(tmp_path)
    _write_pdf(
        library / "Tecnica/extenso.pdf",
        [f"harina comun pagina {number}" for number in range(MAX_SEARCH_RESULTS + 5)],
    )
    catalog.refresh_catalog()
    content.update_index()

    matches = content.search("harina comun", limit=MAX_SEARCH_RESULTS + 500)

    assert len(matches) == MAX_SEARCH_RESULTS
    assert all(not Path(match.relative_path).is_absolute() for match in matches)
    assert all(str(library) not in match.relative_path for match in matches)
    assert all(len(match.fragment) < 250 for match in matches)


def test_progress_callback_reports_every_candidate(tmp_path: Path) -> None:
    library, _, catalog, content = _build_services(tmp_path)
    _write_markdown(library / "Notas/a.md", "contenido alfa")
    _write_markdown(library / "Notas/b.md", "contenido beta")
    catalog.refresh_catalog()
    progress: list[tuple[int, int, str]] = []

    result = content.update_index(progress_callback=lambda *args: progress.append(args))

    assert result.indexed == 2
    assert [entry[:2] for entry in progress] == [(1, 2), (2, 2)]
    assert all(len(entry[2]) == 64 for entry in progress)


def test_cancellation_stops_cleanly_between_documents(tmp_path: Path) -> None:
    library, _, catalog, content = _build_services(tmp_path)
    _write_markdown(library / "Notas/a.md", "contenido alfa")
    _write_markdown(library / "Notas/b.md", "contenido beta")
    catalog.refresh_catalog()
    cancelled = False

    def progress(_processed: int, _total: int, _document_id: str) -> None:
        nonlocal cancelled
        cancelled = True

    result = content.update_index(
        progress_callback=progress,
        cancellation_callback=lambda: cancelled,
    )

    assert result.candidates == 2
    assert result.indexed == 1
    assert result.cancelled == 1
    assert len(content.search("contenido")) == 1


def test_unsupported_formats_are_not_candidates(tmp_path: Path) -> None:
    library, _, catalog, content = _build_services(tmp_path)
    unsupported = library / "Oficina/datos.docx"
    unsupported.parent.mkdir(parents=True)
    unsupported.write_bytes(b"not parsed")
    _write_markdown(library / "Oficina/notas.md", "contenido compatible")
    catalog.refresh_catalog()

    result = content.update_index()

    assert result.candidates == 1
    assert result.indexed == 1
    assert result.failed == 0


def test_missing_catalog_schema_raises_specific_error(tmp_path: Path) -> None:
    library = tmp_path / "library"
    library.mkdir()
    database = tmp_path / "missing.sqlite"
    catalog = DocumentLibraryService(library, database)
    content = DocumentContentIndexService(catalog, database)

    with pytest.raises(DocumentContentCatalogNotInitializedError):
        content.update_index()


def test_content_index_service_does_not_import_pyside6() -> None:
    source = Path(
        "app/services/document_content_index_service.py"
    ).read_text(encoding="utf-8")
    assert "PySide6" not in source


def test_get_page_text_returns_existing_indexed_page(tmp_path: Path) -> None:
    library, _, catalog, content = _build_services(tmp_path)
    _write_pdf(
        library / "Tecnica/paginas.pdf",
        ["texto primera pagina", "texto segunda pagina"],
    )
    catalog.refresh_catalog()
    document = catalog.list_documents()[0]
    content.update_index()

    page_text = content.get_page_text(document.document_id, 2)

    assert page_text is not None
    assert "segunda pagina" in page_text


def test_get_page_text_returns_none_for_missing_page(tmp_path: Path) -> None:
    library, _, catalog, content = _build_services(tmp_path)
    _write_markdown(library / "Notas/unica.md", "pagina unica")
    catalog.refresh_catalog()
    document = catalog.list_documents()[0]
    content.update_index()

    assert content.get_page_text(document.document_id, 2) is None


def test_get_page_text_excludes_inactive_document(tmp_path: Path) -> None:
    library, _, catalog, content = _build_services(tmp_path)
    path = _write_markdown(library / "Notas/inactivo.md", "texto retirado")
    catalog.refresh_catalog()
    document = catalog.list_documents()[0]
    content.update_index()
    path.unlink()
    catalog.refresh_catalog()

    assert content.get_page_text(document.document_id, 1) is None


def test_get_page_text_excludes_document_not_yet_indexed(tmp_path: Path) -> None:
    library, _, catalog, content = _build_services(tmp_path)
    _write_markdown(library / "Notas/pendiente.md", "texto pendiente")
    catalog.refresh_catalog()
    document = catalog.list_documents()[0]

    assert content.get_page_text(document.document_id, 1) is None


def test_get_page_text_applies_character_limit(tmp_path: Path) -> None:
    library, _, catalog, content = _build_services(tmp_path)
    _write_markdown(library / "Notas/largo.md", "abcdefghij")
    catalog.refresh_catalog()
    document = catalog.list_documents()[0]
    content.update_index()

    assert content.get_page_text(document.document_id, 1, max_chars=4) == "abcd"


@pytest.mark.parametrize("page_number", [0, -1, True, 1.5, "1"])
def test_get_page_text_rejects_invalid_page_number(
    tmp_path: Path,
    page_number: object,
) -> None:
    library, _, catalog, content = _build_services(tmp_path)
    _write_markdown(library / "Notas/valido.md", "texto valido")
    catalog.refresh_catalog()
    document = catalog.list_documents()[0]
    content.update_index()

    assert content.get_page_text(document.document_id, page_number) is None  # type: ignore[arg-type]


def test_get_page_text_rejects_invalid_identifier(tmp_path: Path) -> None:
    _library, _, _catalog, content = _build_services(tmp_path)

    assert content.get_page_text("../documento", 1) is None
