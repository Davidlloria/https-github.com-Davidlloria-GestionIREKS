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
