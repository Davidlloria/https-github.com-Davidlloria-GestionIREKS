from __future__ import annotations

import hashlib
import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from app.core.config import DOCUMENT_LIBRARY_DB_PATH, DOCUMENTS_DIR


ALLOWED_DOCUMENT_EXTENSIONS = frozenset(
    {".pdf", ".xlsx", ".xls", ".docx", ".md", ".markdown"}
)


class DocumentLibraryError(RuntimeError):
    """Base error for document-library operations."""


class DocumentNotFoundError(DocumentLibraryError):
    """Raised when a catalog identifier cannot be resolved."""


class UnsafeDocumentPathError(DocumentLibraryError):
    """Raised when catalog metadata points outside the document library."""


@dataclass(frozen=True)
class DocumentLibraryItem:
    document_id: str
    relative_path: str
    name: str
    area: str
    category: str
    extension: str
    size_bytes: int
    modified_at: str
    indexed_at: str
    active: bool


@dataclass(frozen=True)
class DocumentLibraryScanResult:
    available: bool
    scan_complete: bool
    added: int = 0
    updated: int = 0
    unchanged: int = 0
    deactivated: int = 0
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class _ScannedDocument:
    document_id: str
    relative_path: str
    name: str
    area: str
    category: str
    extension: str
    size_bytes: int
    modified_at: str
    modified_ns: int


class DocumentLibraryService:
    """Read-only catalog of files held outside the application repository."""

    def __init__(
        self,
        documents_dir: str | Path | None = None,
        database_path: str | Path | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.documents_dir = Path(documents_dir or DOCUMENTS_DIR).resolve()
        self.database_path = Path(database_path or DOCUMENT_LIBRARY_DB_PATH).resolve()
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def refresh_catalog(self) -> DocumentLibraryScanResult:
        self._initialize_database()
        try:
            library_available = self.documents_dir.exists() and self.documents_dir.is_dir()
        except OSError as exc:
            return DocumentLibraryScanResult(
                available=False,
                scan_complete=False,
                errors=(str(exc),),
            )
        if not library_available:
            return DocumentLibraryScanResult(available=False, scan_complete=False)

        scanned, errors = self._scan_library()
        indexed_at = self._utc_iso(self._clock())
        added = updated = unchanged = deactivated = 0

        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            with connection:
                existing_rows = {
                    row["relative_path"]: row
                    for row in connection.execute("SELECT * FROM documents")
                }
                for relative_path, document in scanned.items():
                    existing = existing_rows.get(relative_path)
                    if existing is None:
                        connection.execute(
                            """
                            INSERT INTO documents (
                                document_id, relative_path, name, area, category,
                                extension, size_bytes, modified_at, modified_ns,
                                indexed_at, active
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                            """,
                            (
                                document.document_id,
                                document.relative_path,
                                document.name,
                                document.area,
                                document.category,
                                document.extension,
                                document.size_bytes,
                                document.modified_at,
                                document.modified_ns,
                                indexed_at,
                            ),
                        )
                        added += 1
                        continue

                    changed = any(
                        (
                            existing["document_id"] != document.document_id,
                            existing["name"] != document.name,
                            existing["area"] != document.area,
                            existing["category"] != document.category,
                            existing["extension"] != document.extension,
                            existing["size_bytes"] != document.size_bytes,
                            existing["modified_ns"] != document.modified_ns,
                            existing["active"] != 1,
                        )
                    )
                    if not changed:
                        unchanged += 1
                        continue

                    connection.execute(
                        """
                        UPDATE documents
                        SET document_id = ?, name = ?, area = ?, category = ?,
                            extension = ?, size_bytes = ?, modified_at = ?,
                            modified_ns = ?, indexed_at = ?, active = 1
                        WHERE relative_path = ?
                        """,
                        (
                            document.document_id,
                            document.name,
                            document.area,
                            document.category,
                            document.extension,
                            document.size_bytes,
                            document.modified_at,
                            document.modified_ns,
                            indexed_at,
                            relative_path,
                        ),
                    )
                    updated += 1

                if not errors:
                    scanned_paths = set(scanned)
                    missing_paths = {
                        path
                        for path, row in existing_rows.items()
                        if row["active"] == 1 and path not in scanned_paths
                    }
                    if missing_paths:
                        connection.executemany(
                            """
                            UPDATE documents
                            SET active = 0, indexed_at = ?
                            WHERE relative_path = ?
                            """,
                            [(indexed_at, path) for path in missing_paths],
                        )
                        deactivated = len(missing_paths)

        return DocumentLibraryScanResult(
            available=True,
            scan_complete=not errors,
            added=added,
            updated=updated,
            unchanged=unchanged,
            deactivated=deactivated,
            errors=tuple(errors),
        )

    def list_documents(
        self,
        *,
        query: str | None = None,
        area: str | None = None,
        category: str | None = None,
        extension: str | None = None,
        active: bool | None = True,
    ) -> list[DocumentLibraryItem]:
        self._initialize_database()
        conditions: list[str] = []
        parameters: list[object] = []
        if query:
            conditions.append("(name LIKE ? COLLATE NOCASE OR relative_path LIKE ? COLLATE NOCASE)")
            pattern = f"%{query}%"
            parameters.extend((pattern, pattern))
        if area:
            conditions.append("area = ? COLLATE NOCASE")
            parameters.append(area)
        if category:
            conditions.append("category = ? COLLATE NOCASE")
            parameters.append(category)
        if extension:
            normalized_extension = extension.lower()
            if not normalized_extension.startswith("."):
                normalized_extension = f".{normalized_extension}"
            conditions.append("extension = ?")
            parameters.append(normalized_extension)
        if active is not None:
            conditions.append("active = ?")
            parameters.append(1 if active else 0)

        where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"""
                SELECT document_id, relative_path, name, area, category,
                       extension, size_bytes, modified_at, indexed_at, active
                FROM documents
                {where_clause}
                ORDER BY area COLLATE NOCASE, category COLLATE NOCASE,
                         name COLLATE NOCASE, relative_path COLLATE NOCASE
                """,
                parameters,
            ).fetchall()
        return [self._row_to_item(row) for row in rows]

    def resolve_document(self, document_id: str) -> Path:
        """Resolve a catalog identifier without reading or changing the file."""
        self._initialize_database()
        if not self._is_valid_identifier(document_id):
            raise DocumentNotFoundError("El identificador documental no es válido.")
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT relative_path
                FROM documents
                WHERE document_id = ? AND active = 1
                """,
                (document_id,),
            ).fetchone()
        if row is None:
            raise DocumentNotFoundError("El documento no existe o está inactivo.")

        relative_path = Path(row["relative_path"])
        if relative_path.is_absolute():
            raise UnsafeDocumentPathError("La ruta catalogada debe ser relativa.")
        resolved_path = (self.documents_dir / relative_path).resolve()
        try:
            resolved_path.relative_to(self.documents_dir)
        except ValueError as exc:
            raise UnsafeDocumentPathError(
                "La ruta catalogada sale de la biblioteca documental."
            ) from exc
        if resolved_path.suffix.lower() not in ALLOWED_DOCUMENT_EXTENSIONS:
            raise UnsafeDocumentPathError("El tipo de documento catalogado no está permitido.")
        if not resolved_path.is_file():
            raise DocumentNotFoundError("El archivo catalogado ya no está disponible.")
        return resolved_path

    def _scan_library(self) -> tuple[dict[str, _ScannedDocument], list[str]]:
        scanned: dict[str, _ScannedDocument] = {}
        errors: list[str] = []

        def record_walk_error(error: OSError) -> None:
            errors.append(str(error))

        for directory, _, filenames in os.walk(
            self.documents_dir,
            topdown=True,
            onerror=record_walk_error,
            followlinks=False,
        ):
            for filename in filenames:
                path = Path(directory) / filename
                extension = path.suffix.lower()
                if extension not in ALLOWED_DOCUMENT_EXTENSIONS:
                    continue
                try:
                    resolved_path = path.resolve()
                    relative_path_obj = resolved_path.relative_to(self.documents_dir)
                    stat = resolved_path.stat()
                    if not resolved_path.is_file():
                        continue
                except (OSError, ValueError) as exc:
                    errors.append(f"{path}: {exc}")
                    continue

                relative_path = relative_path_obj.as_posix()
                parent_parts = relative_path_obj.parent.parts
                area = parent_parts[0] if parent_parts else ""
                category = "/".join(parent_parts[1:]) if len(parent_parts) > 1 else ""
                scanned[relative_path] = _ScannedDocument(
                    document_id=self._stable_identifier(relative_path),
                    relative_path=relative_path,
                    name=relative_path_obj.name,
                    area=area,
                    category=category,
                    extension=extension,
                    size_bytes=stat.st_size,
                    modified_at=self._utc_iso(
                        datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                    ),
                    modified_ns=stat.st_mtime_ns,
                )
        return scanned, errors

    def _initialize_database(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.database_path)) as connection:
            with connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS documents (
                        document_id TEXT PRIMARY KEY,
                        relative_path TEXT NOT NULL UNIQUE,
                        name TEXT NOT NULL,
                        area TEXT NOT NULL,
                        category TEXT NOT NULL,
                        extension TEXT NOT NULL,
                        size_bytes INTEGER NOT NULL,
                        modified_at TEXT NOT NULL,
                        modified_ns INTEGER NOT NULL,
                        indexed_at TEXT NOT NULL,
                        active INTEGER NOT NULL CHECK (active IN (0, 1))
                    )
                    """
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS ix_documents_active ON documents(active)"
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS ix_documents_area ON documents(area)"
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS ix_documents_category ON documents(category)"
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS ix_documents_extension ON documents(extension)"
                )

    @staticmethod
    def _stable_identifier(relative_path: str) -> str:
        return hashlib.sha256(relative_path.encode("utf-8")).hexdigest()

    @staticmethod
    def _is_valid_identifier(document_id: str) -> bool:
        return (
            len(document_id) == 64
            and document_id == document_id.lower()
            and all(character in "0123456789abcdef" for character in document_id)
        )

    @staticmethod
    def _utc_iso(value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> DocumentLibraryItem:
        return DocumentLibraryItem(
            document_id=row["document_id"],
            relative_path=row["relative_path"],
            name=row["name"],
            area=row["area"],
            category=row["category"],
            extension=row["extension"],
            size_bytes=row["size_bytes"],
            modified_at=row["modified_at"],
            indexed_at=row["indexed_at"],
            active=bool(row["active"]),
        )
