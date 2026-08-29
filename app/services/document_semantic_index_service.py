from __future__ import annotations

import math
import sqlite3
import struct
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import PurePosixPath, PureWindowsPath
from typing import Callable, Iterable, Sequence

from app.services.document_content_index_service import DocumentContentIndexService
from app.services.local_embedding_service import (
    MAX_EMBEDDING_BATCH_SIZE,
    LocalEmbeddingService,
)


DEFAULT_CHUNK_SIZE = 1_000
DEFAULT_CHUNK_OVERLAP = 150
EMBEDDING_BATCH_SIZE = 12
MAX_SEMANTIC_SEARCH_RESULTS = 100

ProgressCallback = Callable[[int, int, str], None]
CancellationCallback = Callable[[], bool]


class DocumentSemanticIndexError(RuntimeError):
    pass


class DocumentSemanticModelMismatchError(DocumentSemanticIndexError):
    pass


@dataclass(frozen=True)
class DocumentSemanticChunk:
    document_id: str
    page_number: int
    chunk_index: int
    text: str


@dataclass(frozen=True)
class DocumentSemanticIndexResult:
    candidates: int = 0
    indexed: int = 0
    unchanged: int = 0
    failed: int = 0
    cancelled: int = 0
    chunks_generated: int = 0
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class DocumentSemanticSearchResult:
    document_id: str
    name: str
    relative_path: str
    area: str
    category: str
    page_number: int
    chunk_index: int
    fragment: str
    similarity: float


@dataclass(frozen=True)
class _Candidate:
    document_id: str
    modified_ns: int


def chunk_page_text(
    document_id: str,
    page_number: int,
    text: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> tuple[DocumentSemanticChunk, ...]:
    if chunk_size < 1 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("El tamaño y solapamiento de fragmentos no son válidos.")
    normalized = " ".join(str(text or "").split())
    if not normalized:
        return ()
    chunks: list[DocumentSemanticChunk] = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        if end < len(normalized):
            boundary = normalized.rfind(" ", start + max(1, chunk_size // 2), end + 1)
            if boundary > start:
                end = boundary
        fragment = normalized[start:end].strip()
        if fragment and (not chunks or chunks[-1].text != fragment):
            chunks.append(
                DocumentSemanticChunk(document_id, page_number, len(chunks), fragment)
            )
        if end >= len(normalized):
            break
        next_start = max(start + 1, end - overlap)
        boundary = normalized.find(" ", next_start, end)
        if boundary != -1:
            next_start = boundary + 1
        if next_start <= start:
            next_start = start + 1
        start = next_start
    return tuple(chunks)


def chunk_document_pages(
    document_id: str,
    pages: Iterable[tuple[int, str]],
) -> tuple[DocumentSemanticChunk, ...]:
    chunks: list[DocumentSemanticChunk] = []
    for page_number, text in pages:
        chunks.extend(chunk_page_text(document_id, int(page_number), text))
    return tuple(chunks)


class DocumentSemanticIndexService:
    def __init__(
        self,
        content_index_service: DocumentContentIndexService,
        embedding_service: LocalEmbeddingService,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.content_index_service = content_index_service
        self.embedding_service = embedding_service
        self.database_path = content_index_service.database_path
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def update_index(
        self,
        *,
        progress_callback: ProgressCallback | None = None,
        cancellation_callback: CancellationCallback | None = None,
        force: bool = False,
    ) -> DocumentSemanticIndexResult:
        if not self.content_index_service.library_service.is_library_available():
            return DocumentSemanticIndexResult(
                errors=("La biblioteca documental no está disponible.",)
            )
        self._initialize_schema()
        candidates = self._load_candidates()
        statuses = self._load_statuses()
        indexed = unchanged = failed = chunks_generated = processed = 0
        errors: list[str] = []
        for candidate in candidates:
            if cancellation_callback and cancellation_callback():
                return DocumentSemanticIndexResult(
                    candidates=len(candidates), indexed=indexed, unchanged=unchanged,
                    failed=failed, cancelled=len(candidates) - processed,
                    chunks_generated=chunks_generated, errors=tuple(errors),
                )
            status = statuses.get(candidate.document_id)
            if (
                not force
                and status is not None
                and status[0] == candidate.modified_ns
                and status[1] == self.embedding_service.model
                and status[2] == "indexed"
            ):
                unchanged += 1
            else:
                chunks = chunk_document_pages(
                    candidate.document_id, self._load_pages(candidate.document_id)
                )
                outcome = self._embed_chunks(chunks, cancellation_callback)
                if outcome is None:
                    return DocumentSemanticIndexResult(
                        candidates=len(candidates), indexed=indexed, unchanged=unchanged,
                        failed=failed, cancelled=len(candidates) - processed,
                        chunks_generated=chunks_generated, errors=tuple(errors),
                    )
                vectors, error = outcome
                if error:
                    failed += 1
                    errors.append(f"{candidate.document_id}: {error}")
                    try:
                        self._mark_failed(candidate, error)
                    except sqlite3.Error:
                        errors.append(
                            f"{candidate.document_id}: no se pudo guardar el estado fallido."
                        )
                else:
                    try:
                        self._replace_document(candidate, chunks, vectors)
                    except sqlite3.Error:
                        failed += 1
                        errors.append(
                            f"{candidate.document_id}: no se pudo guardar el índice semántico."
                        )
                        try:
                            self._mark_failed(
                                candidate, "No se pudo guardar el índice semántico."
                            )
                        except sqlite3.Error:
                            errors.append(
                                f"{candidate.document_id}: no se pudo guardar el estado fallido."
                            )
                    else:
                        indexed += 1
                        chunks_generated += len(chunks)
            processed += 1
            if progress_callback:
                progress_callback(processed, len(candidates), candidate.document_id)
        return DocumentSemanticIndexResult(
            candidates=len(candidates), indexed=indexed, unchanged=unchanged,
            failed=failed, chunks_generated=chunks_generated, errors=tuple(errors),
        )

    def search(
        self,
        query: str,
        *,
        area: str | None = None,
        category: str | None = None,
        limit: int = 20,
    ) -> list[DocumentSemanticSearchResult]:
        if not str(query or "").strip() or limit <= 0:
            return []
        self._initialize_schema()
        models = self._active_index_models()
        configured_model = self.embedding_service.model
        if any(model != configured_model for model in models):
            raise DocumentSemanticModelMismatchError(
                f"El índice semántico no corresponde al modelo '{configured_model}'; "
                "es necesario reindexarlo explícitamente."
            )
        if not models:
            return []
        query_result = self.embedding_service.embed([query])
        if not query_result.ok:
            raise DocumentSemanticIndexError(query_result.message)
        query_vector = query_result.vectors[0]
        rows = self._load_search_rows(area, category)
        matches: list[DocumentSemanticSearchResult] = []
        for row in rows:
            dimension = int(row["dimension"])
            if dimension != len(query_vector):
                continue
            vector = self._decode_vector(row["vector"], dimension)
            if vector is None:
                continue
            relative_path = str(row["relative_path"])
            if PurePosixPath(relative_path).is_absolute() or PureWindowsPath(relative_path).is_absolute():
                continue
            similarity = sum(left * right for left, right in zip(query_vector, vector))
            if not math.isfinite(similarity):
                continue
            matches.append(
                DocumentSemanticSearchResult(
                    document_id=row["document_id"], name=row["name"],
                    relative_path=relative_path, area=row["area"], category=row["category"],
                    page_number=int(row["page_number"]), chunk_index=int(row["chunk_index"]),
                    fragment=row["text"], similarity=similarity,
                )
            )
        matches.sort(
            key=lambda item: (
                -item.similarity, item.relative_path.casefold(),
                item.page_number, item.chunk_index,
            )
        )
        return matches[: min(int(limit), MAX_SEMANTIC_SEARCH_RESULTS)]

    def _initialize_schema(self) -> None:
        self.content_index_service._initialize_schema()
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS document_semantic_status (
                    document_id TEXT PRIMARY KEY, modified_ns INTEGER NOT NULL,
                    model TEXT NOT NULL, dimension INTEGER NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('indexed', 'failed')),
                    chunk_count INTEGER NOT NULL, indexed_at TEXT NOT NULL,
                    error_message TEXT)"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS document_semantic_chunks (
                    chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id TEXT NOT NULL, page_number INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL, text TEXT NOT NULL,
                    vector BLOB NOT NULL, dimension INTEGER NOT NULL, model TEXT NOT NULL,
                    UNIQUE(document_id, page_number, chunk_index))"""
            )
            connection.execute(
                """CREATE INDEX IF NOT EXISTS ix_semantic_chunks_document_model
                   ON document_semantic_chunks(document_id, model)"""
            )

    def _load_candidates(self) -> list[_Candidate]:
        with closing(sqlite3.connect(self.database_path)) as connection:
            rows = connection.execute(
                """SELECT d.document_id, d.modified_ns FROM documents d
                   JOIN document_content_status c ON c.document_id=d.document_id
                   WHERE d.active=1 AND c.status='indexed'
                     AND c.indexed_modified_ns=d.modified_ns
                     AND EXISTS (
                         SELECT 1 FROM document_pages_fts p
                         WHERE p.document_id=d.document_id AND trim(p.text)<>''
                     )
                   ORDER BY d.relative_path COLLATE NOCASE, d.document_id"""
            ).fetchall()
        return [_Candidate(str(row[0]), int(row[1])) for row in rows]

    def _load_statuses(self) -> dict[str, tuple[int, str, str]]:
        with closing(sqlite3.connect(self.database_path)) as connection:
            return {
                str(row[0]): (int(row[1]), str(row[2]), str(row[3]))
                for row in connection.execute(
                    "SELECT document_id, modified_ns, model, status FROM document_semantic_status"
                )
            }

    def _load_pages(self, document_id: str) -> list[tuple[int, str]]:
        with closing(sqlite3.connect(self.database_path)) as connection:
            return [
                (int(row[0]), str(row[1]))
                for row in connection.execute(
                    """SELECT CAST(page_number AS INTEGER), text FROM document_pages_fts
                       WHERE document_id=? ORDER BY CAST(page_number AS INTEGER)""",
                    (document_id,),
                )
                if str(row[1] or "").strip()
            ]

    def _embed_chunks(
        self,
        chunks: Sequence[DocumentSemanticChunk],
        cancellation_callback: CancellationCallback | None,
    ) -> tuple[tuple[tuple[float, ...], ...], str] | None:
        vectors: list[tuple[float, ...]] = []
        dimension = 0
        for offset in range(0, len(chunks), min(EMBEDDING_BATCH_SIZE, MAX_EMBEDDING_BATCH_SIZE)):
            if cancellation_callback and cancellation_callback():
                return None
            batch = chunks[offset : offset + EMBEDDING_BATCH_SIZE]
            result = self.embedding_service.embed([chunk.text for chunk in batch])
            if not result.ok:
                return (), result.message
            if len(result.vectors) != len(batch):
                return (), "La respuesta de embeddings está incompleta."
            if result.dimension < 1 or any(
                len(vector) != result.dimension
                or any(not math.isfinite(value) for value in vector)
                or not math.isclose(
                    math.sqrt(sum(value * value for value in vector)),
                    1.0,
                    rel_tol=1e-6,
                    abs_tol=1e-6,
                )
                for vector in result.vectors
            ):
                return (), "La respuesta contiene vectores inválidos."
            if dimension and result.dimension != dimension:
                return (), "La dimensión de embeddings cambió durante el documento."
            dimension = dimension or result.dimension
            vectors.extend(result.vectors)
        if not vectors:
            return (), "El documento no produjo fragmentos con texto."
        return tuple(vectors), ""

    def _replace_document(
        self,
        candidate: _Candidate,
        chunks: Sequence[DocumentSemanticChunk],
        vectors: Sequence[Sequence[float]],
    ) -> None:
        dimension = len(vectors[0])
        indexed_at = self._clock().astimezone(timezone.utc).isoformat()
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            connection.execute(
                "DELETE FROM document_semantic_chunks WHERE document_id=?",
                (candidate.document_id,),
            )
            connection.executemany(
                """INSERT INTO document_semantic_chunks
                   (document_id,page_number,chunk_index,text,vector,dimension,model)
                   VALUES (?,?,?,?,?,?,?)""",
                [
                    (chunk.document_id, chunk.page_number, chunk.chunk_index, chunk.text,
                     self._encode_vector(vector), dimension, self.embedding_service.model)
                    for chunk, vector in zip(chunks, vectors)
                ],
            )
            connection.execute(
                """INSERT INTO document_semantic_status
                   (document_id,modified_ns,model,dimension,status,chunk_count,indexed_at,error_message)
                   VALUES (?,?,?,?, 'indexed',?,?,NULL)
                   ON CONFLICT(document_id) DO UPDATE SET
                   modified_ns=excluded.modified_ns, model=excluded.model,
                   dimension=excluded.dimension, status='indexed',
                   chunk_count=excluded.chunk_count, indexed_at=excluded.indexed_at,
                   error_message=NULL""",
                (candidate.document_id, candidate.modified_ns, self.embedding_service.model,
                 dimension, len(chunks), indexed_at),
            )

    def _mark_failed(self, candidate: _Candidate, error: str) -> None:
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            connection.execute(
                "DELETE FROM document_semantic_chunks WHERE document_id=?",
                (candidate.document_id,),
            )
            connection.execute(
                """INSERT INTO document_semantic_status
                   (document_id,modified_ns,model,dimension,status,chunk_count,indexed_at,error_message)
                   VALUES (?,?,?,0,'failed',0,?,?)
                   ON CONFLICT(document_id) DO UPDATE SET
                   modified_ns=excluded.modified_ns,model=excluded.model,dimension=0,
                   status='failed',chunk_count=0,indexed_at=excluded.indexed_at,
                   error_message=excluded.error_message""",
                (candidate.document_id, candidate.modified_ns, self.embedding_service.model,
                 self._clock().astimezone(timezone.utc).isoformat(), error[:500]),
            )

    def _active_index_models(self) -> set[str]:
        with closing(sqlite3.connect(self.database_path)) as connection:
            return {
                str(row[0]) for row in connection.execute(
                    """SELECT DISTINCT s.model FROM document_semantic_status s
                       JOIN documents d ON d.document_id=s.document_id
                       WHERE d.active=1 AND s.status='indexed'
                         AND s.modified_ns=d.modified_ns"""
                )
            }

    def _load_search_rows(self, area: str | None, category: str | None) -> list[sqlite3.Row]:
        conditions = [
            "d.active=1", "s.status='indexed'", "s.modified_ns=d.modified_ns",
            "s.model=?", "c.model=s.model",
        ]
        parameters: list[object] = [self.embedding_service.model]
        if area:
            conditions.append("d.area=? COLLATE NOCASE")
            parameters.append(area)
        if category:
            conditions.append("d.category=? COLLATE NOCASE")
            parameters.append(category)
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            return connection.execute(
                f"""SELECT d.document_id,d.name,d.relative_path,d.area,d.category,
                    c.page_number,c.chunk_index,c.text,c.vector,c.dimension
                    FROM document_semantic_chunks c
                    JOIN documents d ON d.document_id=c.document_id
                    JOIN document_semantic_status s ON s.document_id=c.document_id
                    WHERE {' AND '.join(conditions)}""",
                parameters,
            ).fetchall()

    @staticmethod
    def _encode_vector(vector: Sequence[float]) -> bytes:
        return struct.pack(f"<{len(vector)}f", *vector)

    @staticmethod
    def _decode_vector(value: bytes, dimension: int) -> tuple[float, ...] | None:
        if dimension < 1 or not isinstance(value, bytes) or len(value) != dimension * 4:
            return None
        vector = struct.unpack(f"<{dimension}f", value)
        if any(not math.isfinite(component) for component in vector):
            return None
        norm = math.sqrt(sum(component * component for component in vector))
        if not math.isfinite(norm) or not math.isclose(norm, 1.0, rel_tol=1e-5, abs_tol=1e-5):
            return None
        return vector
