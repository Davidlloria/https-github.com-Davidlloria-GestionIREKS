from contextlib import closing
from io import BytesIO
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QWidget, QLineEdit, QComboBox, QPushButton

from app.models import RecetaLinea
from app.services.recipe_documents_service import RecipeDocument, RecipeDocumentsService, combine_recipe_pdf, save_pdf_bytes
from app.ui.widgets.recipe_documents_widget import RecipeDocumentsWidget
from app.ui.widgets import recipes_page
from app.ui.widgets.recipes_page import RecipePdfExportDialog, RecipePdfPreviewDialog, RecipesPage


def pdf(path, text, size=(595, 842)):
    canvas = Canvas(str(path), pagesize=size)
    canvas.drawString(40, size[1] - 60, text)
    canvas.save()


@pytest.fixture
def catalog(tmp_path):
    products = tmp_path / "products.db"
    documents = tmp_path / "documents.db"
    with closing(sqlite3.connect(products)) as db, db:
        db.execute("CREATE TABLE productos_ireks (id INTEGER, articulo_id TEXT)")
        db.executemany("INSERT INTO productos_ireks VALUES (?, ?)", [(1, "A"), (2, "B"), (3, "C"), (4, "A")])
    with closing(sqlite3.connect(documents)) as db, db:
        db.execute("CREATE TABLE documents (document_id TEXT, name TEXT, relative_path TEXT, active INTEGER)")
        db.execute("CREATE TABLE document_product_links (document_id TEXT, product_articulo_id TEXT, relation_type TEXT)")
        db.executemany("INSERT INTO documents VALUES (?, ?, ?, ?)", [
            ("one", "Ficha A", "a.pdf", 1), ("two", "Ficha A alternativa", "b.pdf", 1),
            ("old", "Antigua", "old.pdf", 0), ("other", "Otro documento", "other.pdf", 1),
            ("missing", "Ficha B", "missing.pdf", 1),
        ])
        db.executemany("INSERT INTO document_product_links VALUES (?, ?, ?)", [
            ("one", "A", "technical_sheet"), ("two", "A", "technical_sheet"),
            ("old", "A", "technical_sheet"), ("other", "A", "other"),
            ("missing", "B", "technical_sheet"),
        ])
    pdf(tmp_path / "a.pdf", "Ficha A")
    pdf(tmp_path / "b.pdf", "Ficha alternativa", (842, 595))
    return RecipeDocumentsService(products, documents, tmp_path)


def line(id, process="Masa final", source="ireks", **kwargs):
    return RecetaLinea(receta_id=1, ingrediente_id=id, nombre_mostrado=f"Producto {id}",
                       tipo_origen=source, proceso_nombre=process, **kwargs)


def test_catalog_read_only_deduplicates_products_across_processes(catalog):
    before = [path.read_bytes() for path in (catalog.product_database, catalog.document_database)]
    rows = catalog.list_documents([line(1), line(1, "Poolish"), line(4), line(2), line(3), line(99), line(1, source="std"), line(2, tipo_linea="proceso")])
    assert [row.document_id for row in rows] == ["one", "two", "missing", "", ""]
    assert [row.status for row in rows] == ["Disponible", "Disponible", "Archivo no encontrado", "Sin ficha vinculada", "Producto no vinculado al catálogo"]
    assert before == [path.read_bytes() for path in (catalog.product_database, catalog.document_database)]


@pytest.mark.parametrize("relative,status", [("../outside.pdf", "Ruta de ficha no permitida"), ("sheet.docx", "Formato no compatible (se requiere PDF)")])
def test_catalog_rejects_unsafe_and_non_pdf_paths(catalog, relative, status):
    with closing(sqlite3.connect(catalog.document_database)) as db, db:
        db.execute("UPDATE documents SET relative_path=? WHERE document_id='one'", (relative,))
    assert catalog.list_documents([line(1)])[0].status == status


def test_missing_catalog_is_not_created(catalog):
    catalog.document_database.unlink()
    assert catalog.list_documents([line(1)])[0].status == "Catálogo documental no disponible"
    assert not catalog.document_database.exists()
    assert catalog.list_documents([line(1, source="std")]) == []


def test_merge_retains_page_order_size_and_deduplicates(tmp_path):
    recipe, sheet = tmp_path / "recipe.pdf", tmp_path / "sheet.pdf"
    pdf(recipe, "Receta")
    pdf(sheet, "Ficha", (842, 595))
    original = sheet.read_bytes()
    result = combine_recipe_pdf(recipe, [sheet, sheet])
    reader = PdfReader(BytesIO(result))
    assert len(reader.pages) == 2
    assert "Receta" in reader.pages[0].extract_text()
    assert "Ficha" in reader.pages[1].extract_text()
    assert float(reader.pages[1].mediabox.width) == 842
    assert sheet.read_bytes() == original
    target = tmp_path / "output.pdf"
    save_pdf_bytes(target, result)
    assert target.read_bytes() == result


@pytest.mark.parametrize("problem", ["missing", "invalid", "encrypted"])
def test_merge_failure_preserves_recipe(tmp_path, problem):
    recipe, sheet = tmp_path / "recipe.pdf", tmp_path / "sheet.pdf"
    pdf(recipe, "Receta")
    original = recipe.read_bytes()
    if problem == "invalid":
        sheet.write_bytes(b"not pdf")
    elif problem == "encrypted":
        writer = PdfWriter()
        writer.add_blank_page(100, 100)
        writer.encrypt("secret")
        writer.write(sheet)
        writer.close()
    with pytest.raises(ValueError, match="sheet.pdf"):
        combine_recipe_pdf(recipe, [sheet])
    assert recipe.read_bytes() == original


@pytest.fixture(scope="module")
def application():
    app = QApplication.instance() or QApplication([])
    yield app


def test_widget_choices_refresh_and_reset_between_recipes(application, catalog):
    widget = RecipeDocumentsWidget(service=catalog)
    widget.refresh(1, [line(1), line(2)])
    assert len(widget.selected_paths()) == 2
    assert "Producto 2" in widget.issues()[0]
    widget.table.item(0, 0).setCheckState(Qt.CheckState.Unchecked)
    widget.refresh(1, [line(1)])
    assert widget.selected_paths() == [catalog.documents_dir / "b.pdf"]
    widget.refresh(2, [line(1)])
    assert len(widget.selected_paths()) == 2
    widget.refresh(2, [])
    assert not widget.selected_paths() and not widget.open_button.isEnabled()
    widget.close()


@pytest.mark.parametrize("mode", ["minimal", "original", "simple", "extended"])
def test_combined_preview_shows_all_pages(application, tmp_path, mode):
    sheet = tmp_path / "sheet.pdf"
    pdf(sheet, "Ficha")
    service = SimpleNamespace(export_recipe_to_pdf=lambda _id, path, **_: pdf(path, "Receta"))
    dialog = RecipePdfPreviewDialog(service, 1, False, False, False, False, layout_mode=mode, technical_sheets=[sheet])
    assert dialog.pdf_document.pageCount() == 2
    assert dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Save).isEnabled()
    temporary = dialog._preview_path
    dialog.cleanup_preview()
    assert not temporary.exists()


def test_failed_sheet_disables_preview_save(application, tmp_path, monkeypatch):
    errors = []
    monkeypatch.setattr(recipes_page.QMessageBox, "critical", lambda *args: errors.append(args[-1]))
    service = SimpleNamespace(export_recipe_to_pdf=lambda _id, path, **_: pdf(path, "Receta"))
    dialog = RecipePdfPreviewDialog(service, 1, False, False, False, False, technical_sheets=[tmp_path / "missing.pdf"])
    assert not dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Save).isEnabled()
    assert "missing.pdf" in errors[0]
    dialog.cleanup_preview()


@pytest.mark.parametrize("accept", [True, False])
def test_export_saves_exact_combined_preview_and_cancellation_writes_nothing(application, tmp_path, monkeypatch, accept):
    sheet = tmp_path / "sheet.pdf"
    pdf(sheet, "Ficha")
    widget = QWidget()
    widget.documents_tab = RecipeDocumentsWidget(service=SimpleNamespace(list_documents=lambda _: [RecipeDocument("Producto", "id", "Ficha", sheet, "Disponible")]))
    widget.recipe_pdf_btn = QPushButton()
    widget._document_import_pending = False
    widget._autosave_timer = SimpleNamespace(stop=lambda: None)
    widget._build_recipe_payload = lambda: None
    widget._build_lines = lambda: [line(1)]
    widget._selected_cliente_id = lambda: ""
    widget.recipe_tabs = SimpleNamespace(currentIndex=lambda: 0)
    calls = []
    def save(*args, **kwargs):
        calls.append("save")
        return SimpleNamespace(status="saved", saved_recipe_id=1)
    widget.recipe_active_flow_service = SimpleNamespace(save_recipe=save)
    widget.recipe_service = SimpleNamespace(get_recipe=lambda _: SimpleNamespace(receta=SimpleNamespace(parametros_elaboracion_json="{}"), lineas=[line(1)]))
    def export(_id, path, **kwargs):
        calls.append("pdf")
        pdf(path, "Receta")
    widget.pdf_service = SimpleNamespace(export_recipe_to_pdf=export)
    widget.nombre_input = QLineEdit("Receta")
    widget.cliente_combo = QComboBox()
    target = tmp_path / "final.pdf"
    previews = []
    def preview(dialog):
        previews.append(dialog._preview_path.read_bytes())
        return QDialog.DialogCode.Accepted if accept else QDialog.DialogCode.Rejected
    monkeypatch.setattr(RecipePdfExportDialog, "exec", lambda _: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(RecipePdfPreviewDialog, "exec", preview)
    monkeypatch.setattr(recipes_page.QFileDialog, "getSaveFileName", lambda *_: (str(target), "PDF"))
    monkeypatch.setattr(recipes_page.QMessageBox, "information", lambda *_: None)
    RecipesPage._export_pdf(widget)
    assert calls == ["save", "pdf"]
    assert target.exists() == accept
    if accept:
        assert target.read_bytes() == previews[0]
        assert len(PdfReader(target).pages) == 2
    widget.close()


@pytest.mark.parametrize("problem", ["save", "missing", "unselected", "catalog"])
def test_export_blocks_unsaved_or_incomplete_documents(application, tmp_path, monkeypatch, problem):
    sheet = tmp_path / "sheet.pdf"
    pdf(sheet, "Ficha")
    def documents(_):
        if problem == "catalog":
            raise OSError("Catálogo no disponible")
        return [RecipeDocument("Producto", "id", "Ficha", None if problem == "missing" else sheet,
                               "Archivo no encontrado" if problem == "missing" else "Disponible")]
    widget = QWidget()
    widget.documents_tab = RecipeDocumentsWidget(service=SimpleNamespace(list_documents=documents))
    widget.documents_tab.refresh(1, [])
    if problem == "unselected":
        widget.documents_tab.table.item(0, 0).setCheckState(Qt.CheckState.Unchecked)
    widget.recipe_pdf_btn = QPushButton()
    widget._document_import_pending = False
    widget._autosave_timer = SimpleNamespace(stop=lambda: None)
    widget._build_recipe_payload = lambda: None
    widget._build_lines = lambda: [line(1)]
    widget._selected_cliente_id = lambda: ""
    widget.recipe_tabs = SimpleNamespace(currentIndex=lambda: 0)
    widget.recipe_active_flow_service = SimpleNamespace(save_recipe=lambda *_, **__: SimpleNamespace(
        status="error" if problem == "save" else "saved", message="Error guardando", saved_recipe_id=1))
    widget.recipe_service = SimpleNamespace(get_recipe=lambda _: SimpleNamespace(
        receta=SimpleNamespace(parametros_elaboracion_json="{}"), lineas=[line(1)]))
    widget.pdf_service = SimpleNamespace(export_recipe_to_pdf=lambda *_args, **_kwargs: pytest.fail("Must not export"))
    warnings = []
    monkeypatch.setattr(RecipePdfExportDialog, "exec", lambda _: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(recipes_page.QMessageBox, "warning", lambda *args: warnings.append(args[-1]))
    RecipesPage._export_pdf(widget)
    assert len(warnings) == 1
    expected = {"save": "No se pudo guardar", "missing": "Producto", "unselected": "Selecciona al menos", "catalog": "Catálogo no disponible"}
    assert expected[problem] in warnings[0]
    widget.close()
