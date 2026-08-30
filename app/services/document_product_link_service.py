from __future__ import annotations

import re
import sqlite3
from collections import defaultdict
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from app.core.config import DB_PATH, DOCUMENT_LIBRARY_DB_PATH


TECHNICAL_SHEET_AREA = "FICHAS TECNICAS"
TECHNICAL_SHEET_RELATION = "technical_sheet"
AUTOMATIC_FILENAME_ORIGIN = "automatic_filename"


class DocumentProductLinkError(RuntimeError):
    """Raised when document-product links cannot be synchronized safely."""


@dataclass(frozen=True)
class DocumentProductLink:
    document_id: str
    product_articulo_id: str
    relation_type: str
    origin: str
    matched_code: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class DocumentProductLinkSyncResult:
    technical_documents: int = 0
    linked: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    removed: int = 0
    unmatched: int = 0
    ambiguous: int = 0


@dataclass(frozen=True)
class _Product:
    articulo_id: str
    short_reference: str
    full_reference: str
    manufacturer: str
    active: bool


@dataclass(frozen=True)
class _TechnicalDocument:
    document_id: str
    name: str
    category: str


class DocumentProductLinkService:
    """Derive product links from technical-sheet filename codes."""

    def __init__(
        self,
        product_database_path: str | Path | None = None,
        document_database_path: str | Path | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.product_database_path = Path(product_database_path or DB_PATH).resolve()
        self.document_database_path = Path(
            document_database_path or DOCUMENT_LIBRARY_DB_PATH
        ).resolve()
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def sync_technical_sheets(self) -> DocumentProductLinkSyncResult:
        products = self._load_products()
        documents = self._load_technical_documents()
        self._initialize_schema()

        products_by_code: dict[tuple[str, str], list[_Product]] = defaultdict(list)
        for product in products:
            code = self._product_document_code(product)
            if code:
                products_by_code[(product.manufacturer, code)].append(product)

        desired: dict[tuple[str, str, str], str] = {}
        unmatched = ambiguous = 0
        for document in documents:
            manufacturer = self._document_manufacturer(document.category)
            code = self._document_code(document.name)
            candidates = products_by_code.get((manufacturer, code), [])
            active_candidates = [candidate for candidate in candidates if candidate.active]
            preferred = active_candidates or candidates
            if not preferred:
                unmatched += 1
                continue
            if len(preferred) != 1:
                ambiguous += 1
                continue
            product = preferred[0]
            desired[
                (document.document_id, product.articulo_id, TECHNICAL_SHEET_RELATION)
            ] = code

        created = updated = unchanged = removed = 0
        timestamp = self._utc_iso(self._clock())
        with closing(sqlite3.connect(self.document_database_path)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            with connection:
                existing_rows = connection.execute(
                    """
                    SELECT document_id, product_articulo_id, relation_type,
                           origin, matched_code
                    FROM document_product_links
                    WHERE relation_type = ?
                    """,
                    (TECHNICAL_SHEET_RELATION,),
                ).fetchall()
                existing = {
                    (
                        str(row["document_id"]),
                        str(row["product_articulo_id"]),
                        str(row["relation_type"]),
                    ): row
                    for row in existing_rows
                }
                automatic_keys = {
                    key
                    for key, row in existing.items()
                    if row["origin"] == AUTOMATIC_FILENAME_ORIGIN
                }
                obsolete_keys = automatic_keys - set(desired)
                for document_id, product_articulo_id, relation_type in obsolete_keys:
                    connection.execute(
                        """
                        DELETE FROM document_product_links
                        WHERE document_id = ? AND product_articulo_id = ?
                          AND relation_type = ? AND origin = ?
                        """,
                        (
                            document_id,
                            product_articulo_id,
                            relation_type,
                            AUTOMATIC_FILENAME_ORIGIN,
                        ),
                    )
                    removed += 1

                for key, matched_code in desired.items():
                    row = existing.get(key)
                    if row is not None and row["origin"] != AUTOMATIC_FILENAME_ORIGIN:
                        unchanged += 1
                        continue
                    if row is None:
                        connection.execute(
                            """
                            INSERT INTO document_product_links (
                                document_id, product_articulo_id, relation_type,
                                origin, matched_code, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (*key, AUTOMATIC_FILENAME_ORIGIN, matched_code, timestamp, timestamp),
                        )
                        created += 1
                        continue
                    if row["matched_code"] == matched_code:
                        unchanged += 1
                        continue
                    connection.execute(
                        """
                        UPDATE document_product_links
                        SET matched_code = ?, updated_at = ?
                        WHERE document_id = ? AND product_articulo_id = ?
                          AND relation_type = ? AND origin = ?
                        """,
                        (
                            matched_code,
                            timestamp,
                            *key,
                            AUTOMATIC_FILENAME_ORIGIN,
                        ),
                    )
                    updated += 1

        return DocumentProductLinkSyncResult(
            technical_documents=len(documents),
            linked=len(desired),
            created=created,
            updated=updated,
            unchanged=unchanged,
            removed=removed,
            unmatched=unmatched,
            ambiguous=ambiguous,
        )

    def list_links(self, *, product_articulo_id: str | None = None) -> list[DocumentProductLink]:
        self._initialize_schema()
        conditions = ""
        parameters: tuple[str, ...] = ()
        if product_articulo_id is not None:
            conditions = "WHERE product_articulo_id = ?"
            parameters = (str(product_articulo_id).strip(),)
        with closing(sqlite3.connect(self.document_database_path)) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"""
                SELECT document_id, product_articulo_id, relation_type, origin,
                       matched_code, created_at, updated_at
                FROM document_product_links
                {conditions}
                ORDER BY product_articulo_id, relation_type, document_id
                """,
                parameters,
            ).fetchall()
        return [
            DocumentProductLink(
                document_id=str(row["document_id"]),
                product_articulo_id=str(row["product_articulo_id"]),
                relation_type=str(row["relation_type"]),
                origin=str(row["origin"]),
                matched_code=str(row["matched_code"]),
                created_at=str(row["created_at"]),
                updated_at=str(row["updated_at"]),
            )
            for row in rows
        ]

    def _load_products(self) -> list[_Product]:
        if not self.product_database_path.is_file():
            raise DocumentProductLinkError("La base de datos de productos no está disponible.")
        with closing(sqlite3.connect(self.product_database_path)) as connection:
            connection.row_factory = sqlite3.Row
            if not self._table_exists(connection, "productos_ireks"):
                raise DocumentProductLinkError("No existe el catálogo de productos IREKS.")
            if not self._table_exists(connection, "fabricantes"):
                raise DocumentProductLinkError("No existe el catálogo de fabricantes.")
            rows = connection.execute(
                """
                SELECT p.articulo_id, p.articulo_referencia_corta,
                       p.articulo_referencia, p.articulo_status_activo,
                       f.fabricante_nombre
                FROM productos_ireks p
                LEFT JOIN fabricantes f ON f.fabricante_id = p.fabricante_id
                """
            ).fetchall()
        return [
            _Product(
                articulo_id=str(row["articulo_id"] or "").strip(),
                short_reference=str(row["articulo_referencia_corta"] or "").strip(),
                full_reference=str(row["articulo_referencia"] or "").strip(),
                manufacturer=str(row["fabricante_nombre"] or "").strip().upper(),
                active=bool(row["articulo_status_activo"]),
            )
            for row in rows
            if str(row["articulo_id"] or "").strip()
        ]

    def _load_technical_documents(self) -> list[_TechnicalDocument]:
        if not self.document_database_path.is_file():
            raise DocumentProductLinkError("El catálogo documental no está disponible.")
        with closing(sqlite3.connect(self.document_database_path)) as connection:
            connection.row_factory = sqlite3.Row
            if not self._table_exists(connection, "documents"):
                raise DocumentProductLinkError("El catálogo documental no está inicializado.")
            rows = connection.execute(
                """
                SELECT document_id, name, category
                FROM documents
                WHERE active = 1 AND area = ? COLLATE NOCASE
                ORDER BY relative_path COLLATE NOCASE
                """,
                (TECHNICAL_SHEET_AREA,),
            ).fetchall()
        return [
            _TechnicalDocument(
                document_id=str(row["document_id"]),
                name=str(row["name"]),
                category=str(row["category"]),
            )
            for row in rows
        ]

    def _initialize_schema(self) -> None:
        with closing(sqlite3.connect(self.document_database_path)) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            with connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS document_product_links (
                        document_id TEXT NOT NULL,
                        product_articulo_id TEXT NOT NULL,
                        relation_type TEXT NOT NULL,
                        origin TEXT NOT NULL,
                        matched_code TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY (document_id, product_articulo_id, relation_type),
                        FOREIGN KEY (document_id) REFERENCES documents(document_id)
                            ON DELETE CASCADE
                    )
                    """
                )
                connection.execute(
                    """CREATE INDEX IF NOT EXISTS ix_document_product_links_product
                       ON document_product_links(product_articulo_id)"""
                )
                connection.execute(
                    """CREATE INDEX IF NOT EXISTS ix_document_product_links_origin
                       ON document_product_links(origin)"""
                )

    @staticmethod
    def _product_document_code(product: _Product) -> str:
        if product.manufacturer == "IREKS":
            return product.full_reference.upper()
        if product.manufacturer == "DREIDOPPEL":
            match = re.fullmatch(r"D1(\d{5})\d", product.short_reference.upper())
            return match.group(1) if match else ""
        if product.manufacturer == "GELATOP":
            match = re.fullmatch(r"D(\d{5})\d", product.short_reference.upper())
            return match.group(1) if match else ""
        return ""

    @staticmethod
    def _document_manufacturer(category: str) -> str:
        return str(category or "").replace("\\", "/").split("/", 1)[0].strip().upper()

    @staticmethod
    def _document_code(name: str) -> str:
        match = re.match(r"^([A-Za-z0-9]+)", str(name or "").strip())
        return match.group(1).upper() if match else ""

    @staticmethod
    def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
        return (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table_name,),
            ).fetchone()
            is not None
        )

    @staticmethod
    def _utc_iso(value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
