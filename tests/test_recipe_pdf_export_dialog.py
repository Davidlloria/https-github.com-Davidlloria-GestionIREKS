from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QDialogButtonBox, QLineEdit, QWidget
from PIL import Image
from reportlab.pdfgen.canvas import Canvas

from app.services import recipe_image_storage_service
from app.ui.widgets import recipes_page
from app.ui.widgets.recipes_page import RecipePdfExportDialog, RecipePdfPreviewDialog, RecipesPage


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
    assert dialog.include_images() is False

    dialog.escandallo_si.setChecked(True)
    dialog.nutrition_si.setChecked(True)
    dialog.images_si.setChecked(True)

    assert dialog.include_escandallo() is True
    assert dialog.include_nutrition() is True
    assert dialog.include_images() is True

    dialog.baker_percentage_no.setChecked(True)

    assert dialog.include_baker_percentage() is False


def test_original_options_are_independent_exclusive_and_reset_each_export(tmp_path, monkeypatch) -> None:
    _application()
    monkeypatch.setattr(recipe_image_storage_service, "DATA_DIR", tmp_path)
    Image.new("RGB", (100, 200), "red").save(tmp_path / "principal.png")
    Image.new("RGB", (300, 100), "blue").save(tmp_path / "otra.png")
    gallery = [{"path": "otra.png"}, {"path": "principal.png", "is_main": True}, {"path": "ausente.png"}]
    dialog = RecipePdfExportDialog(images_gallery=gallery)
    assert dialog.original_options_group.isHidden()
    dialog.original_radio.setChecked(True)
    assert dialog.layout_mode() == "original"
    assert dialog.minimal_options_group.isHidden()
    assert not dialog.original_options_group.isHidden()
    assert not dialog.include_dreidoppel()
    assert not dialog.include_images()
    assert dialog.original_image_combo.isHidden()
    assert dialog.original_image_combo.count() == 2
    assert dialog.selected_image_path() == "principal.png"

    dialog.dreidoppel_si.setChecked(True)
    dialog.original_images_si.setChecked(True)
    assert dialog.include_dreidoppel() and dialog.include_images()
    assert not dialog.dreidoppel_no.isChecked()
    assert not dialog.original_images_no.isChecked()
    assert not dialog.original_image_combo.isHidden()
    pixmap = dialog.original_image_preview.pixmap()
    assert pixmap.height() == 2 * pixmap.width()
    dialog.original_image_combo.setCurrentIndex(1)
    assert dialog.selected_image_path() == "otra.png"
    pixmap = dialog.original_image_preview.pixmap()
    assert pixmap.width() == 3 * pixmap.height()

    dialog.minimal_radio.setChecked(True)
    assert dialog.original_options_group.isHidden()
    assert not dialog.include_images()
    dialog.images_si.setChecked(True)
    dialog.original_radio.setChecked(True)
    dialog.original_images_no.setChecked(True)
    assert not dialog.include_images()
    assert dialog.original_image_combo.isHidden()
    dialog.extended_radio.setChecked(True)
    assert dialog.original_options_group.isHidden()
    assert dialog.minimal_options_group.isHidden()

    fresh_dialog = RecipePdfExportDialog(images_gallery=gallery)
    fresh_dialog.original_radio.setChecked(True)
    assert not fresh_dialog.include_dreidoppel()
    assert not fresh_dialog.include_images()


def test_original_without_available_images_disables_yes(tmp_path, monkeypatch) -> None:
    _application()
    monkeypatch.setattr(recipe_image_storage_service, "DATA_DIR", tmp_path)
    dialog = RecipePdfExportDialog(images_gallery=[{"path": "no-existe.png"}])
    dialog.original_radio.setChecked(True)
    assert not dialog.original_images_si.isEnabled()
    assert dialog.original_images_no.isChecked()
    assert not dialog.include_images()


@pytest.mark.parametrize("save", [False, True])
def test_original_export_flow_previews_cleans_up_and_saves_only_when_confirmed(tmp_path, monkeypatch, save) -> None:
    _application()
    monkeypatch.setattr(recipe_image_storage_service, "DATA_DIR", tmp_path)
    Image.new("RGB", (20, 10), "blue").save(tmp_path / "foto.png")
    calls = []

    def export(recipe_id, path, **options):
        calls.append((recipe_id, path, options))
        canvas = Canvas(str(path))
        canvas.drawString(50, 750, "Preview")
        canvas.save()

    def choose_options(dialog):
        assert dialog.original_image_combo.count() == 1
        dialog.original_radio.setChecked(True)
        dialog.dreidoppel_si.setChecked(True)
        dialog.original_images_si.setChecked(True)
        return QDialog.DialogCode.Accepted

    def preview(dialog):
        assert dialog.windowTitle() == "PDF original - Vista previa"
        button_box = dialog.findChild(QDialogButtonBox)
        assert button_box.button(QDialogButtonBox.StandardButton.Save).isEnabled()
        assert dialog.pdf_document.pageCount() == 1
        return QDialog.DialogCode.Accepted if save else QDialog.DialogCode.Rejected

    target = tmp_path / "exportado.pdf"
    monkeypatch.setattr(RecipePdfExportDialog, "exec", choose_options)
    monkeypatch.setattr(RecipePdfPreviewDialog, "exec", preview)
    monkeypatch.setattr(recipes_page.QFileDialog, "getSaveFileName", lambda *_args: (str(target), "PDF"))
    monkeypatch.setattr(recipes_page.QMessageBox, "information", lambda *_args: None)
    page = QWidget()
    page.current_recipe_id = 7
    page.recipe_service = SimpleNamespace(get_recipe=lambda _id: SimpleNamespace(receta=SimpleNamespace(
        parametros_elaboracion_json=json.dumps({"images_gallery": [{"path": "foto.png"}]}),
    )))
    page.pdf_service = SimpleNamespace(export_recipe_to_pdf=export)
    page.nombre_input = QLineEdit("Pan con malta")
    page.cliente_combo = QComboBox()
    RecipesPage._export_pdf(page)
    assert len(calls) == (2 if save else 1)
    assert target.exists() == save
    assert not calls[0][1].exists()
    for recipe_id, _path, options in calls:
        assert recipe_id == 7
        assert options == {
            "layout_mode": "original", "include_escandallo": False, "include_nutrition": False,
            "include_baker_percentage": False, "include_images": True,
            "include_dreidoppel": True, "selected_image_path": "foto.png",
        }


def test_failed_preview_disables_save_and_cleans_up(monkeypatch) -> None:
    _application()
    monkeypatch.setattr(recipes_page.QMessageBox, "critical", lambda *_args: None)

    def fail(*_args, **_kwargs):
        raise ValueError("Imagen no disponible")

    dialog = RecipePdfPreviewDialog(
        SimpleNamespace(export_recipe_to_pdf=fail), 1, False, False, False, True, layout_mode="original",
    )
    path = dialog._preview_path
    button_box = dialog.findChild(QDialogButtonBox)
    assert not button_box.button(QDialogButtonBox.StandardButton.Save).isEnabled()
    dialog.cleanup_preview()
    assert not path.exists()


@pytest.mark.parametrize("mode", ["minimal", "original"])
def test_preview_loads_pdf_in_memory_and_releases_temporary_file(mode) -> None:
    _application()

    def export(_recipe_id, path, **_options):
        canvas = Canvas(str(path))
        canvas.drawString(50, 750, "Preview")
        canvas.save()

    dialog = RecipePdfPreviewDialog(
        SimpleNamespace(export_recipe_to_pdf=export), 1, False, False, False, False, layout_mode=mode,
    )
    path = dialog._preview_path
    button_box = dialog.findChild(QDialogButtonBox)
    assert button_box.button(QDialogButtonBox.StandardButton.Save).isEnabled()
    assert dialog.pdf_document.pageCount() == 1
    dialog.cleanup_preview()
    assert not path.exists()


def test_invalid_generated_pdf_cannot_be_saved(monkeypatch) -> None:
    _application()
    monkeypatch.setattr(recipes_page.QMessageBox, "critical", lambda *_args: None)

    def export(_recipe_id, path, **_options):
        path.write_bytes(b"invalid pdf")

    dialog = RecipePdfPreviewDialog(
        SimpleNamespace(export_recipe_to_pdf=export), 1, False, False, False, False, layout_mode="original",
    )
    button_box = dialog.findChild(QDialogButtonBox)
    assert not button_box.button(QDialogButtonBox.StandardButton.Save).isEnabled()
    path = dialog._preview_path
    dialog.cleanup_preview()
    assert not path.exists()
