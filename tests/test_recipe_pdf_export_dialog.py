from __future__ import annotations

from PySide6.QtWidgets import QApplication

from app.ui.widgets.recipes_page import RecipePdfExportDialog


_APP: QApplication | None = None


def _application() -> QApplication:
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def test_minimal_export_options_are_exclusive_and_only_visible_for_minimal() -> None:
    _application()
    dialog = RecipePdfExportDialog()

    assert dialog.layout_mode() == "minimal"
    assert not dialog.minimal_options_group.isHidden()

    dialog.simple_radio.setChecked(True)

    assert dialog.layout_mode() == "simple"
    assert dialog.minimal_options_group.isHidden()

    dialog.minimal_radio.setChecked(True)

    assert dialog.layout_mode() == "minimal"
    assert not dialog.minimal_options_group.isHidden()
    assert dialog.include_escandallo() is False
    assert dialog.include_nutrition() is False
    assert dialog.include_baker_percentage() is True

    dialog.escandallo_si.setChecked(True)
    dialog.nutrition_si.setChecked(True)

    assert dialog.include_escandallo() is True
    assert dialog.include_nutrition() is True

    dialog.baker_percentage_no.setChecked(True)

    assert dialog.include_baker_percentage() is False
