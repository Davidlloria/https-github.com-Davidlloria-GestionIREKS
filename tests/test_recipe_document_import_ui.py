from __future__ import annotations

import inspect
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.services.recipe_document_import_service import (
    RecipeDocumentDraft,
    RecipeDocumentLineDraft,
)
from app.ui.widgets.recipe_document_import_dialog import RecipeDocumentImportDialog
from app.ui.widgets.recipes_page import RecipesPage


class _UnusedService:
    pass


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_dialog_renders_review_and_only_enables_valid_draft() -> None:
    _app()
    dialog = RecipeDocumentImportDialog(_UnusedService())  # type: ignore[arg-type]
    draft = RecipeDocumentDraft(
        document_id="doc-1",
        document_name="formula.pdf",
        relative_path="TECNICO/RECETAS/formula.pdf",
        page_number=2,
        recipe_name="Pan documentado",
        process_text="Amasar.",
        number_of_pieces=1,
        lines=(
            RecipeDocumentLineDraft(
                source_name="Ingrediente pendiente",
                quantity_g=1000.0,
                source_quantity="1,000 kg",
                process_name="Masa final",
                notes="Revisar asociación",
            ),
        ),
        warnings=("1 ingrediente necesita revisión manual.",),
    )

    dialog._render_draft(draft)

    assert dialog.review_table.rowCount() == 1
    assert dialog.review_table.item(0, 4).text() == "Revisar"
    assert dialog.load_button.isEnabled()
    assert "revisión" in dialog.warning_label.text()
    assert not dialog.raw_material_button.isEnabled()

    dialog.review_table.selectRow(0)

    assert dialog.raw_material_button.isEnabled()
    dialog.close()


def test_document_drafts_are_excluded_from_autosave_until_explicit_save() -> None:
    schedule_source = inspect.getsource(RecipesPage._schedule_autosave)
    flush_source = inspect.getsource(RecipesPage._flush_autosave)
    perform_source = inspect.getsource(RecipesPage._perform_autosave)
    save_source = inspect.getsource(RecipesPage._save_recipe)

    assert "self._document_import_pending" in schedule_source
    assert "self._document_import_pending" in flush_source
    assert "self._document_import_pending" in perform_source
    assert "self._document_import_pending = False" in save_source


def _browser_document(name, folder=""):
    from app.services.document_content_index_service import DocumentContentSearchResult
    return DocumentContentSearchResult(name, name, "TECNICO/RECETAS/" + folder + name,
                                       "TECNICO", "RECETAS", 1, "", 0)


def test_browser_navigates_folders_and_selects_document():
    from app.ui.widgets.recipe_document_import_dialog import RecipeDocumentBrowserDialog
    app = _app()
    nested = _browser_document("pan.pdf", "Panaderia/Integral/")
    dialog = RecipeDocumentBrowserDialog([_browser_document("raiz.pdf"), nested])
    assert dialog.files.count() == 1
    root = dialog.folders.topLevelItem(0)
    dialog.folders.setCurrentItem(root.child(0))
    assert dialog.files.count() == 0
    assert not dialog.select_button.isEnabled()
    dialog.folders.setCurrentItem(root.child(0).child(0))
    assert dialog.files.item(0).text() == "pan.pdf"
    dialog.files.setCurrentRow(0)
    dialog.select_button.click()
    assert dialog.selected_document == nested
    assert dialog.result() == dialog.DialogCode.Accepted
    dialog.close()


def test_browser_cancel_preserves_current_selection(monkeypatch):
    from app.ui.widgets.recipe_document_import_dialog import RecipeDocumentBrowserDialog
    app = _app()
    class Service:
        def browse_documents(self):
            return []
    dialog = RecipeDocumentImportDialog(Service())
    old = _browser_document("anterior.pdf")
    dialog._active_result = old
    monkeypatch.setattr(RecipeDocumentBrowserDialog, "exec", lambda self: self.DialogCode.Rejected)
    dialog._browse()
    assert dialog._active_result is old
    dialog.close()


def test_missing_document_does_not_extract_or_allow_loading():
    app = _app()
    class Service:
        def resolve_document(self, identity):
            raise FileNotFoundError("Documento no disponible")
        def build_draft(self, *args, **kwargs):
            raise AssertionError("Must not extract a missing document")
    dialog = RecipeDocumentImportDialog(Service())
    dialog._render_results([_browser_document("ausente.pdf")])
    assert not dialog.load_button.isEnabled()
    assert not dialog.page_spin.isEnabled()
    assert "no disponible" in dialog.status_label.text()
    dialog.close()


def test_browser_selection_enters_existing_review_flow(monkeypatch):
    from app.ui.widgets.recipe_document_import_dialog import RecipeDocumentBrowserDialog
    app = _app()
    document = _browser_document("elegido.pdf")
    class Service:
        def browse_documents(self):
            return [document]
    def choose(browser):
        browser.selected_document = document
        return browser.DialogCode.Accepted
    monkeypatch.setattr(RecipeDocumentBrowserDialog, "exec", choose)
    dialog = RecipeDocumentImportDialog(Service())
    received = []
    monkeypatch.setattr(dialog, "_render_results", lambda rows: received.extend(rows))
    dialog._browse()
    assert received == [document]
    dialog.close()
