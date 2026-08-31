from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal

import fitz

from app.services.document_library_service import (
    DocumentLibraryService,
    DocumentNotFoundError,
    UnsafeDocumentPathError,
)


SUPPORTED_CONTENT_EXTENSIONS = frozenset({".pdf", ".md", ".markdown"})
MAX_SEARCH_RESULTS = 100
DEFAULT_PAGE_TEXT_MAX_CHARS = 4_000
MAX_PAGE_TEXT_CHARS = 12_000
_SEARCH_TOKEN_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)
_DOCUMENT_IDENTIFIER_PATTERN = re.compile(r"[0-9a-f]{64}")

IndexStatus = Literal["indexed", "no_text", "failed"]
ProgressCallback = Callable[[int, int, str], None]
CancellationCallback = Callable[[], bool]


class DocumentContentIndexError(RuntimeError):
    """Base error for document content indexing."""


class DocumentContentCatalogNotInitializedError(DocumentContentIndexError):
    """Raised when the document catalog schema does not exist."""


class DocumentContentFTSUnavailableError(DocumentContentIndexError):
    """Raised when SQLite FTS5 is not available."""


@dataclass(frozen=True)
class DocumentContentIndexResult:
    candidates: int
    indexed: int = 0
    unchanged: int = 0
    no_text: int = 0
    failed: int = 0
    cancelled: int = 0
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class DocumentContentSearchResult:
    document_id: str
    name: str
    relative_path: str
    area: str
    category: str
    page_number: int
    fragment: str
    score: float


@dataclass(frozen=True)
class _ContentCandidate:
    document_id: str
    extension: str
    modified_ns: int


@dataclass(frozen=True)
class _ExtractionOutcome:
    status: IndexStatus
    page_count: int
    pages: tuple[tuple[int, str], ...] = ()
    error_message: str | None = None


class DocumentContentIndexService:
    """Local, synchronous full-text index for cataloged documents."""

    def __init__(
        self,
        library_service: DocumentLibraryService | None = None,
        database_path: str | Path | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.library_service = library_service or DocumentLibraryService()
        default_database = self.library_service.database_path
        self.database_path = Path(database_path or default_database).resolve()
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def update_index(
        self,
        *,
        progress_callback: ProgressCallback | None = None,
        cancellation_callback: CancellationCallback | None = None,
        force: bool = False,
    ) -> DocumentContentIndexResult:
        if not self.library_service.is_library_available():
            return DocumentContentIndexResult(
                candidates=0,
                errors=("La biblioteca documental no está disponible.",),
            )

        self._initialize_schema()
        self._prune_inactive_documents()
        candidates = self._load_candidates()
        existing_versions = self._load_existing_versions()
        indexed = unchanged = no_text = failed = cancelled = 0
        processed = 0
        errors: list[str] = []

        for candidate in candidates:
            if cancellation_callback is not None and cancellation_callback():
                cancelled = len(candidates) - processed
                break

            indexed_version = existing_versions.get(candidate.document_id)
            if not force and indexed_version == candidate.modified_ns:
                unchanged += 1
                processed += 1
                self._notify_progress(
                    progress_callback,
                    processed,
                    len(candidates),
                    candidate.document_id,
                )
                continue

            outcome = self._extract_candidate(candidate)
            extracted_at = self._utc_iso(self._clock())
            try:
                self._replace_document_content(candidate, outcome, extracted_at)
            except sqlite3.Error:
                failed += 1
                errors.append(
                    f"{candidate.document_id}: no se pudo guardar el índice de contenido."
                )
            else:
                if outcome.status == "indexed":
                    indexed += 1
                elif outcome.status == "no_text":
                    no_text += 1
                else:
                    failed += 1
                    errors.append(
                        f"{candidate.document_id}: "
                        f"{outcome.error_message or 'extracción fallida.'}"
                    )
            processed += 1
            self._notify_progress(
                progress_callback,
                processed,
                len(candidates),
                candidate.document_id,
            )

        return DocumentContentIndexResult(
            candidates=len(candidates),
            indexed=indexed,
            unchanged=unchanged,
            no_text=no_text,
            failed=failed,
            cancelled=cancelled,
            errors=tuple(errors),
        )

    def search(
        self,
        query: str,
        *,
        area: str | None = None,
        category: str | None = None,
        category_prefix: str | None = None,
        limit: int = 20,
    ) -> list[DocumentContentSearchResult]:
        match_expression = self._safe_match_expression(query)
        if not match_expression or limit <= 0:
            return []
        safe_limit = min(int(limit), MAX_SEARCH_RESULTS)
        self._initialize_schema()

        conditions = [
            "document_pages_fts MATCH ?",
            "documents.active = 1",
            "document_content_status.status = 'indexed'",
        ]
        parameters: list[object] = [match_expression]
        if area:
            conditions.append("documents.area = ? COLLATE NOCASE")
            parameters.append(area)
        if category:
            conditions.append("documents.category = ? COLLATE NOCASE")
            parameters.append(category)
        if category_prefix:
            conditions.append("documents.category LIKE ? ESCAPE '\\' COLLATE NOCASE")
            escaped_prefix = (
                str(category_prefix)
                .replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
            )
            parameters.append(f"{escaped_prefix}%")
        parameters.append(safe_limit)

        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"""
                SELECT
                    documents.document_id,
                    documents.name,
                    documents.relative_path,
                    documents.area,
                    documents.category,
                    CAST(document_pages_fts.page_number AS INTEGER) AS page_number,
                    snippet(document_pages_fts, 2, '[', ']', ' … ', 16) AS fragment,
                    bm25(document_pages_fts) AS score
                FROM document_pages_fts
                JOIN documents
                  ON documents.document_id = document_pages_fts.document_id
                JOIN document_content_status
                  ON document_content_status.document_id = documents.document_id
                WHERE {' AND '.join(conditions)}
                ORDER BY score ASC,
                         documents.relative_path COLLATE NOCASE ASC,
                         page_number ASC
                LIMIT ?
                """,
                parameters,
            ).fetchall()
        return [
            DocumentContentSearchResult(
                document_id=row["document_id"],
                name=row["name"],
                relative_path=row["relative_path"],
                area=row["area"],
                category=row["category"],
                page_number=int(row["page_number"]),
                fragment=row["fragment"],
                score=float(row["score"]),
            )
            for row in rows
        ]

    def get_page_text(
        self,
        document_id: str,
        page_number: int,
        *,
        max_chars: int = DEFAULT_PAGE_TEXT_MAX_CHARS,
    ) -> str | None:
        safe_document_id = str(document_id or "")
        if _DOCUMENT_IDENTIFIER_PATTERN.fullmatch(safe_document_id) is None:
            return None
        if isinstance(page_number, bool) or not isinstance(page_number, int):
            return None
        if page_number < 1:
            return None
        try:
            safe_max_chars = min(int(max_chars), MAX_PAGE_TEXT_CHARS)
        except (TypeError, ValueError):
            return None
        if safe_max_chars < 1:
            return None

        self._initialize_schema()
        with closing(sqlite3.connect(self.database_path)) as connection:
            row = connection.execute(
                """
                SELECT document_pages_fts.text
                FROM document_pages_fts
                JOIN documents
                  ON documents.document_id = document_pages_fts.document_id
                JOIN document_content_status
                  ON document_content_status.document_id = documents.document_id
                WHERE document_pages_fts.document_id = ?
                  AND CAST(document_pages_fts.page_number AS INTEGER) = ?
                  AND documents.active = 1
                  AND document_content_status.status = 'indexed'
                LIMIT 1
                """,
                (safe_document_id, page_number),
            ).fetchone()
        if row is None:
            return None
        text = str(row[0] or "")
        return text[:safe_max_chars] or None

    def _initialize_schema(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.database_path)) as connection:
            catalog_exists = connection.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type = 'table' AND name = 'documents'
                """
            ).fetchone()
            if catalog_exists is None:
                raise DocumentContentCatalogNotInitializedError(
                    "El catálogo documental no está inicializado."
                )
            try:
                with connection:
                    connection.execute(
                        """
                        CREATE TABLE IF NOT EXISTS document_content_status (
                            document_id TEXT PRIMARY KEY,
                            indexed_modified_ns INTEGER NOT NULL,
                            status TEXT NOT NULL
                                CHECK (status IN ('indexed', 'no_text', 'failed')),
                            page_count INTEGER NOT NULL,
                            extracted_at TEXT NOT NULL,
                            error_message TEXT
                        )
                        """
                    )
                    connection.execute(
                        """
                        CREATE VIRTUAL TABLE IF NOT EXISTS document_pages_fts
                        USING fts5(
                            document_id UNINDEXED,
                            page_number UNINDEXED,
                            text,
                            tokenize = 'unicode61 remove_diacritics 2'
                        )
                        """
                    )
            except sqlite3.OperationalError as exc:
                if "fts5" in str(exc).casefold():
                    raise DocumentContentFTSUnavailableError(
                        "SQLite FTS5 no está disponible."
                    ) from exc
                raise

    def _load_candidates(self) -> list[_ContentCandidate]:
        placeholders = ", ".join("?" for _ in SUPPORTED_CONTENT_EXTENSIONS)
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"""
                SELECT document_id, extension, modified_ns
                FROM documents
                WHERE active = 1 AND extension IN ({placeholders})
                ORDER BY relative_path COLLATE NOCASE ASC
                """,
                sorted(SUPPORTED_CONTENT_EXTENSIONS),
            ).fetchall()
        return [
            _ContentCandidate(
                document_id=row["document_id"],
                extension=row["extension"],
                modified_ns=int(row["modified_ns"]),
            )
            for row in rows
        ]

    def _prune_inactive_documents(self) -> None:
        with closing(sqlite3.connect(self.database_path)) as connection:
            with connection:
                connection.execute(
                    """DELETE FROM document_pages_fts
                       WHERE document_id IN (
                           SELECT document_id FROM documents WHERE active = 0
                       )"""
                )
                connection.execute(
                    """DELETE FROM document_content_status
                       WHERE document_id IN (
                           SELECT document_id FROM documents WHERE active = 0
                       )"""
                )

    def _load_existing_versions(self) -> dict[str, int]:
        with closing(sqlite3.connect(self.database_path)) as connection:
            return {
                document_id: int(modified_ns)
                for document_id, modified_ns in connection.execute(
                    """
                    SELECT document_id, indexed_modified_ns
                    FROM document_content_status
                    """
                )
            }

    def _extract_candidate(self, candidate: _ContentCandidate) -> _ExtractionOutcome:
        try:
            path = self.library_service.resolve_document(candidate.document_id)
        except (DocumentNotFoundError, UnsafeDocumentPathError):
            return _ExtractionOutcome(
                status="failed",
                page_count=0,
                error_message="No se pudo resolver el documento catalogado.",
            )
        if candidate.extension == ".pdf":
            return self._extract_pdf(path)
        return self._extract_markdown(path)

    def _extract_pdf(self, path: Path) -> _ExtractionOutcome:
        try:
            with fitz.open(path) as document:
                if document.needs_pass:
                    return _ExtractionOutcome(
                        status="failed",
                        page_count=document.page_count,
                        error_message="El PDF está protegido.",
                    )
                pages = tuple(
                    (page_number, normalized)
                    for page_number, page in enumerate(document, start=1)
                    if (normalized := self._normalize_text(page.get_text("text")))
                )
                page_count = document.page_count
        except (fitz.FileDataError, RuntimeError, ValueError, OSError):
            return _ExtractionOutcome(
                status="failed",
                page_count=0,
                error_message="El PDF está corrupto o no puede leerse.",
            )
        if not pages:
            return _ExtractionOutcome(status="no_text", page_count=page_count)
        return _ExtractionOutcome(
            status="indexed",
            page_count=page_count,
            pages=pages,
        )

    def _extract_markdown(self, path: Path) -> _ExtractionOutcome:
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeError:
            return _ExtractionOutcome(
                status="failed",
                page_count=1,
                error_message="El Markdown no tiene una codificación UTF-8 compatible.",
            )
        except OSError:
            return _ExtractionOutcome(
                status="failed",
                page_count=1,
                error_message="No se pudo leer el documento Markdown.",
            )
        normalized = self._normalize_text(text)
        if not normalized:
            return _ExtractionOutcome(status="no_text", page_count=1)
        return _ExtractionOutcome(
            status="indexed",
            page_count=1,
            pages=((1, normalized),),
        )

    def _replace_document_content(
        self,
        candidate: _ContentCandidate,
        outcome: _ExtractionOutcome,
        extracted_at: str,
    ) -> None:
        with closing(sqlite3.connect(self.database_path)) as connection:
            with connection:
                connection.execute(
                    "DELETE FROM document_pages_fts WHERE document_id = ?",
                    (candidate.document_id,),
                )
                if outcome.pages:
                    connection.executemany(
                        """
                        INSERT INTO document_pages_fts(document_id, page_number, text)
                        VALUES (?, ?, ?)
                        """,
                        [
                            (candidate.document_id, page_number, text)
                            for page_number, text in outcome.pages
                        ],
                    )
                connection.execute(
                    """
                    INSERT INTO document_content_status (
                        document_id, indexed_modified_ns, status, page_count,
                        extracted_at, error_message
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(document_id) DO UPDATE SET
                        indexed_modified_ns = excluded.indexed_modified_ns,
                        status = excluded.status,
                        page_count = excluded.page_count,
                        extracted_at = excluded.extracted_at,
                        error_message = excluded.error_message
                    """,
                    (
                        candidate.document_id,
                        candidate.modified_ns,
                        outcome.status,
                        outcome.page_count,
                        extracted_at,
                        outcome.error_message,
                    ),
                )

    @staticmethod
    def _normalize_text(text: str) -> str:
        normalized_lines = [" ".join(line.split()) for line in text.splitlines()]
        useful_lines = [line for line in normalized_lines if line]
        normalized = "\n".join(useful_lines)
        return normalized if any(character.isalnum() for character in normalized) else ""

    @staticmethod
    def _safe_match_expression(query: str) -> str:
        tokens = _SEARCH_TOKEN_PATTERN.findall(str(query or ""))
        return " AND ".join(f'"{token}"' for token in tokens)

    @staticmethod
    def _notify_progress(
        callback: ProgressCallback | None,
        processed: int,
        total: int,
        document_id: str,
    ) -> None:
        if callback is not None:
            callback(processed, total, document_id)

    @staticmethod
    def _utc_iso(value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
