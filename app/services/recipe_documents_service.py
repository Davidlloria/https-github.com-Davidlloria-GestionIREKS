from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from io import BytesIO
import os
from pathlib import Path
import sqlite3
import tempfile

from pypdf import PdfReader, PdfWriter

from app.core.config import DB_PATH, DOCUMENT_LIBRARY_DB_PATH, DOCUMENTS_DIR
from app.models import RecetaLinea
from app.services.document_product_link_service import TECHNICAL_SHEET_RELATION


@dataclass(frozen=True)
class RecipeDocument:
    product: str
    document_id: str = ""
    name: str = ""
    path: Path | None = None
    status: str = "Sin ficha vinculada"


class RecipeDocumentsService:
    """Resolve existing product links without creating or updating either catalog."""

    def __init__(self, product_database=DB_PATH, document_database=DOCUMENT_LIBRARY_DB_PATH,
                 documents_dir=DOCUMENTS_DIR):
        self.product_database = Path(product_database).resolve()
        self.document_database = Path(document_database).resolve()
        self.documents_dir = Path(documents_dir).resolve()

    def list_documents(self, lines: list[RecetaLinea]) -> list[RecipeDocument]:
        products = {}
        for line in lines:
            if line.tipo_origen == "ireks" and line.tipo_linea != "proceso":
                products.setdefault(line.ingrediente_id, line.nombre_mostrado or line.codigo_ingrediente)
        if not products:
            return []
        result = []
        seen_products = set()
        with closing(sqlite3.connect(self.product_database.as_uri() + "?mode=ro", uri=True)) as products_db:
            for ingredient_id, label in products.items():
                product = products_db.execute(
                    "SELECT articulo_id FROM productos_ireks WHERE id = ?", (ingredient_id,)
                ).fetchone()
                if not product or not product[0]:
                    result.append(RecipeDocument(label, status="Producto no vinculado al catálogo"))
                    continue
                if product[0] in seen_products:
                    continue
                seen_products.add(product[0])
                if not self.document_database.is_file():
                    result.append(RecipeDocument(label, status="Catálogo documental no disponible"))
                    continue
                with closing(sqlite3.connect(self.document_database.as_uri() + "?mode=ro", uri=True)) as docs_db:
                    docs_db.row_factory = sqlite3.Row
                    tables = {row[0] for row in docs_db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    if not {"documents", "document_product_links"} <= tables:
                        result.append(RecipeDocument(label, status="Catálogo documental sin vínculos"))
                        continue
                    documents = docs_db.execute(
                        "SELECT d.document_id, d.name, d.relative_path FROM documents d "
                        "JOIN document_product_links l ON l.document_id = d.document_id "
                        "WHERE l.product_articulo_id = ? AND l.relation_type = ? AND d.active = 1 "
                        "ORDER BY d.name COLLATE NOCASE, d.document_id",
                        (product[0], TECHNICAL_SHEET_RELATION),
                    ).fetchall()
                if not documents:
                    result.append(RecipeDocument(label))
                for document in documents:
                    relative = Path(document["relative_path"])
                    path = (self.documents_dir / relative).resolve()
                    if relative.is_absolute() or not path.is_relative_to(self.documents_dir):
                        status = "Ruta de ficha no permitida"
                    elif path.suffix.lower() != ".pdf":
                        status = "Formato no compatible (se requiere PDF)"
                    elif not path.is_file():
                        status = "Archivo no encontrado"
                    else:
                        status = "Disponible"
                    result.append(RecipeDocument(label, document["document_id"], document["name"],
                                                 path if status == "Disponible" else None, status))
        return result


def combine_recipe_pdf(recipe_path: Path, documents: list[Path]) -> bytes:
    """Keep original page sizes and fail the whole operation on an unreadable sheet."""
    writer = PdfWriter()
    try:
        for path in dict.fromkeys([recipe_path, *documents]):
            try:
                reader = PdfReader(BytesIO(path.read_bytes()))
                if reader.is_encrypted or not reader.pages:
                    raise ValueError("PDF protegido o sin páginas")
                writer.append(reader, import_outline=False)
            except Exception as exc:
                raise ValueError(f"No se pudo incorporar {path.name}: {exc}") from exc
        output = BytesIO()
        writer.write(output)
        return output.getvalue()
    finally:
        writer.close()


def save_pdf_bytes(path: Path, content: bytes) -> None:
    """Replace the destination only after the complete PDF has been written."""
    handle = tempfile.NamedTemporaryFile(dir=path.parent, suffix=".pdf", delete=False)
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(content)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
