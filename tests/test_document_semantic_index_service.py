from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path

import pytest

from app.services.document_content_index_service import DocumentContentIndexService
from app.services.document_library_service import DocumentLibraryService
from app.services.document_semantic_index_service import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    MAX_SEMANTIC_SEARCH_RESULTS,
    DocumentSemanticIndexService,
    DocumentSemanticModelMismatchError,
    chunk_document_pages,
    chunk_page_text,
)
from app.services.local_embedding_service import LocalEmbeddingResult


class FakeEmbeddingService:
    def __init__(self, model: str = "fake-embed", *, fail: bool = False) -> None:
        self.model = model
        self.fail = fail
        self.calls: list[list[str]] = []

    def embed(self, texts) -> LocalEmbeddingResult:
        values = list(texts)
        self.calls.append(values)
        if self.fail:
            return LocalEmbeddingResult(False, model=self.model, message="fallo simulado")
        vectors = []
        for text in values:
            digest = hashlib.sha256(text.casefold().encode()).digest()
            raw = [float(digest[0] + 1), float(digest[1] + 1), float(digest[2] + 1)]
            norm = sum(value * value for value in raw) ** 0.5
            vectors.append(tuple(value / norm for value in raw))
        return LocalEmbeddingResult(True, tuple(vectors), self.model, 3)


def _services(tmp_path: Path, *, model="fake-embed", fail=False):
    library = tmp_path / "library"
    library.mkdir()
    database = tmp_path / "data" / "document_library.sqlite"
    catalog = DocumentLibraryService(library, database)
    content = DocumentContentIndexService(catalog, database)
    embedding = FakeEmbeddingService(model, fail=fail)
    semantic = DocumentSemanticIndexService(content, embedding)
    return library, database, catalog, content, embedding, semantic


def _add_markdown(library: Path, relative: str, text: str) -> Path:
    path = library / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _prepare(tmp_path: Path, docs: dict[str, str], **kwargs):
    values = _services(tmp_path, **kwargs)
    library, _, catalog, content, _, _ = values
    for relative, text in docs.items():
        _add_markdown(library, relative, text)
    catalog.refresh_catalog()
    content.update_index()
    return values


def test_chunker_handles_short_empty_and_whitespace() -> None:
    assert chunk_page_text("doc", 1, "") == ()
    chunks = chunk_page_text("doc", 1, "  texto   corto\n")
    assert [chunk.text for chunk in chunks] == ["texto corto"]


def test_long_chunking_is_deterministic_overlapping_and_word_bounded() -> None:
    text = " ".join(f"palabra{i}" for i in range(400))
    first = chunk_page_text("doc", 1, text)
    second = chunk_page_text("doc", 1, text)
    assert first == second and len(first) > 2
    assert all(len(chunk.text) <= DEFAULT_CHUNK_SIZE for chunk in first)
    assert len({chunk.text for chunk in first}) == len(first)
    for left, right in zip(first, first[1:]):
        left_words = left.text.split()
        right_words = right.text.split()
        assert set(left_words[-25:]) & set(right_words[:25])
        assert not right.text.startswith(" ")


def test_pages_never_mix_and_chunk_indexes_restart() -> None:
    chunks = chunk_document_pages("doc", [(1, "uno " * 400), (2, "dos " * 400)])
    page_one = [chunk for chunk in chunks if chunk.page_number == 1]
    page_two = [chunk for chunk in chunks if chunk.page_number == 2]
    assert page_one and page_two
    assert page_one[0].chunk_index == page_two[0].chunk_index == 0
    assert all("dos" not in chunk.text for chunk in page_one)
    assert all("uno" not in chunk.text for chunk in page_two)


def test_chunker_rejects_loop_prone_configuration() -> None:
    with pytest.raises(ValueError):
        chunk_page_text("doc", 1, "texto", chunk_size=10, overlap=10)
    assert DEFAULT_CHUNK_OVERLAP < DEFAULT_CHUNK_SIZE


def test_first_index_and_second_unchanged_use_batches(tmp_path: Path) -> None:
    library, database, _, _, embedding, semantic = _prepare(
        tmp_path, {"Calidad/Guias/largo.md": "contenido " * 2500}
    )
    result = semantic.update_index()
    calls_after_first = len(embedding.calls)
    second = semantic.update_index()
    with sqlite3.connect(database) as connection:
        status = connection.execute(
            "SELECT status,chunk_count,dimension,model FROM document_semantic_status"
        ).fetchone()
        blobs = connection.execute("SELECT vector,dimension FROM document_semantic_chunks").fetchall()
    assert result.indexed == 1 and result.chunks_generated > 1
    assert all(len(call) <= 12 for call in embedding.calls)
    assert status == ("indexed", result.chunks_generated, 3, "fake-embed")
    assert all(len(blob) == dimension * 4 for blob, dimension in blobs)
    assert second.unchanged == 1 and len(embedding.calls) == calls_after_first
    assert str(library) not in repr(embedding.calls)


def test_modified_document_replaces_chunks(tmp_path: Path) -> None:
    library, database, catalog, content, _, semantic = _prepare(
        tmp_path, {"Notas/cambio.md": "antiguo " * 500}
    )
    semantic.update_index()
    path = library / "Notas/cambio.md"
    old_ns = path.stat().st_mtime_ns
    path.write_text("nuevo contenido", encoding="utf-8")
    os.utime(path, ns=(old_ns + 2_000_000_000, old_ns + 2_000_000_000))
    catalog.refresh_catalog()
    content.update_index()
    result = semantic.update_index()
    with sqlite3.connect(database) as connection:
        texts = [row[0] for row in connection.execute("SELECT text FROM document_semantic_chunks")]
    assert result.indexed == 1
    assert texts == ["nuevo contenido"]


def test_model_change_requires_and_then_performs_reindex(tmp_path: Path) -> None:
    *_, embedding, semantic = _prepare(tmp_path, {"Notas/a.md": "texto"})
    semantic.update_index()
    embedding.model = "new-model"
    with pytest.raises(DocumentSemanticModelMismatchError, match="reindexarlo"):
        semantic.search("texto")
    result = semantic.update_index()
    assert result.indexed == 1
    assert semantic.search("texto")


def test_failed_document_does_not_stop_following_candidate(tmp_path: Path) -> None:
    _, database, _, _, embedding, semantic = _prepare(
        tmp_path, {"A/uno.md": "uno", "B/dos.md": "dos"}
    )
    original = embedding.embed
    count = 0
    def fail_first(texts):
        nonlocal count
        count += 1
        return LocalEmbeddingResult(False, model=embedding.model, message="fallo") if count == 1 else original(texts)
    embedding.embed = fail_first
    result = semantic.update_index()
    with sqlite3.connect(database) as connection:
        statuses = connection.execute("SELECT status FROM document_semantic_status ORDER BY document_id").fetchall()
    assert result.failed == result.indexed == 1
    assert sorted(row[0] for row in statuses) == ["failed", "indexed"]


def test_cancellation_between_batches_leaves_no_partial_document(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.document_semantic_index_service.EMBEDDING_BATCH_SIZE", 1
    )
    _, database, _, _, embedding, semantic = _prepare(
        tmp_path, {"Notas/largo.md": "texto " * 5000}
    )
    def cancelled():
        return len(embedding.calls) >= 1
    result = semantic.update_index(cancellation_callback=cancelled)
    with sqlite3.connect(database) as connection:
        count = connection.execute("SELECT COUNT(*) FROM document_semantic_chunks").fetchone()[0]
    assert result.cancelled == 1 and count == 0


def test_unavailable_library_preserves_existing_semantic_index(tmp_path: Path) -> None:
    library, database, _, _, _, semantic = _prepare(tmp_path, {"Notas/a.md": "conservado"})
    semantic.update_index()
    library.rename(tmp_path / "offline")
    result = semantic.update_index(force=True)
    with sqlite3.connect(database) as connection:
        count = connection.execute("SELECT COUNT(*) FROM document_semantic_chunks").fetchone()[0]
    assert result.candidates == 0 and result.errors and count == 1


def test_search_uses_one_embedding_filters_and_deterministic_limit(tmp_path: Path) -> None:
    _, _, _, _, embedding, semantic = _prepare(
        tmp_path,
        {"Calidad/Guias/a.md": "igual", "Tecnica/Fichas/b.md": "igual"},
    )
    semantic.update_index()
    embedding.calls.clear()
    results = semantic.search("consulta", area="Calidad", category="Guias", limit=999)
    assert len(embedding.calls) == 1 and embedding.calls[0] == ["consulta"]
    assert len(results) == 1 and results[0].relative_path == "Calidad/Guias/a.md"
    assert len(semantic.search("consulta", limit=999)) <= MAX_SEMANTIC_SEARCH_RESULTS
    calls = len(embedding.calls)
    assert semantic.search(" ") == [] and len(embedding.calls) == calls


def test_inactive_documents_and_corrupt_vectors_are_excluded(tmp_path: Path) -> None:
    library, database, catalog, _, _, semantic = _prepare(
        tmp_path, {"Notas/a.md": "activo", "Notas/b.md": "retirado"}
    )
    semantic.update_index()
    (library / "Notas/b.md").unlink()
    catalog.refresh_catalog()
    with sqlite3.connect(database) as connection, connection:
        active_id = connection.execute("SELECT document_id FROM documents WHERE active=1").fetchone()[0]
        connection.execute(
            "UPDATE document_semantic_chunks SET vector=? WHERE document_id=?", (b"bad", active_id)
        )
    assert semantic.search("algo") == []


def test_progress_contains_only_identifier_and_force_reindexes(tmp_path: Path) -> None:
    library, _, _, _, embedding, semantic = _prepare(tmp_path, {"Notas/a.md": "texto"})
    progress = []
    semantic.update_index(progress_callback=lambda *args: progress.append(args))
    calls = len(embedding.calls)
    result = semantic.update_index(force=True)
    assert result.indexed == 1 and len(embedding.calls) == calls + 1
    assert progress and str(library) not in repr(progress) and "texto" not in repr(progress)


def test_status_without_semantic_index_reports_pending_without_embedding(tmp_path: Path) -> None:
    _, _, _, _, embedding, semantic = _prepare(
        tmp_path, {"Notas/a.md": "contenido disponible"}
    )
    calls = len(embedding.calls)

    status = semantic.get_status()

    assert status.configured_model == "fake-embed"
    assert status.content_documents == 1
    assert status.indexed_documents == status.available_chunks == 0
    assert not status.available and status.requires_reindex
    assert len(embedding.calls) == calls


def test_status_available_counts_documents_chunks_and_date(tmp_path: Path) -> None:
    _, _, _, _, embedding, semantic = _prepare(
        tmp_path,
        {"Calidad/a.md": "uno", "Tecnica/b.md": "dos " * 800},
    )
    result = semantic.update_index()
    calls = len(embedding.calls)

    status = semantic.get_status()

    assert status.indexed_documents == 2
    assert status.available_chunks == result.chunks_generated
    assert status.failed_documents == status.other_model_documents == 0
    assert status.available and not status.requires_reindex
    assert status.last_indexed_at
    assert semantic.is_search_available()
    assert len(embedding.calls) == calls


def test_status_partial_failure_remains_available_and_requires_reindex(tmp_path: Path) -> None:
    _, database, _, _, _, semantic = _prepare(
        tmp_path, {"A/uno.md": "uno", "B/dos.md": "dos"}
    )
    semantic.update_index()
    with sqlite3.connect(database) as connection, connection:
        failed_id = connection.execute(
            "SELECT document_id FROM documents ORDER BY relative_path DESC LIMIT 1"
        ).fetchone()[0]
        connection.execute(
            "DELETE FROM document_semantic_chunks WHERE document_id=?", (failed_id,)
        )
        connection.execute(
            """UPDATE document_semantic_status
               SET status='failed', dimension=0, chunk_count=0, error_message='fallo'
               WHERE document_id=?""",
            (failed_id,),
        )

    status = semantic.get_status()

    assert status.indexed_documents == status.failed_documents == 1
    assert status.available and status.requires_reindex


def test_status_model_change_is_incompatible(tmp_path: Path) -> None:
    _, _, _, _, embedding, semantic = _prepare(tmp_path, {"Notas/a.md": "texto"})
    semantic.update_index()
    embedding.model = "new-model"

    status = semantic.get_status()

    assert status.other_model_documents == 1
    assert status.indexed_documents == 0
    assert not status.available and status.requires_reindex
    assert not semantic.is_search_available()


def test_status_excludes_inactive_documents(tmp_path: Path) -> None:
    library, database, catalog, content, _, semantic = _prepare(
        tmp_path, {"Notas/a.md": "texto"}
    )
    semantic.update_index()
    (library / "Notas/a.md").unlink()
    catalog.refresh_catalog()
    content.update_index()
    semantic.update_index()

    status = semantic.get_status()

    assert status.indexed_documents == status.available_chunks == 0
    assert not status.available
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM document_semantic_status"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM document_semantic_chunks"
        ).fetchone()[0] == 0


def test_status_handles_database_not_initialized_without_creating_it(tmp_path: Path) -> None:
    library = tmp_path / "library"
    library.mkdir()
    database = tmp_path / "data" / "missing.sqlite"
    catalog = DocumentLibraryService(library, database)
    content = DocumentContentIndexService(catalog, database)
    embedding = FakeEmbeddingService()
    semantic = DocumentSemanticIndexService(content, embedding)

    status = semantic.get_status()

    assert status.configured_model == "fake-embed"
    assert not status.available and not status.requires_reindex
    assert not database.exists()
    assert embedding.calls == []
