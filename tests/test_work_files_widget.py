import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEvent, QItemSelectionModel
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from app.services.work_files_service import WorkFilesService
from app.ui.widgets.work_files_widget import WorkFilesWidget

_APP = None


@pytest.fixture
def browser(tmp_path):
    global _APP
    _APP = QApplication.instance() or QApplication([])
    root = tmp_path / "Trabajo"
    root.mkdir()
    (root / "Clientes").mkdir()
    (root / "Pedidos").mkdir()
    (root / "nota.txt").write_text("prueba", encoding="utf-8")
    widget = WorkFilesWidget(service=WorkFilesService(root))
    widget.resize(1150, 650)
    widget.show()
    wait_for(lambda: widget.files_proxy.rowCount(widget.list_view.rootIndex()) == 3)
    yield widget
    widget.close()
    widget.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QApplication.processEvents()


def wait_for(condition):
    for _ in range(150):
        QApplication.processEvents()
        if condition():
            return
        QTest.qWait(10)
    assert condition()


def select(browser, path):
    source = browser.files_model.index(str(path))
    index = browser.files_proxy.mapFromSource(source)
    assert index.isValid()
    browser.list_view.selectionModel().setCurrentIndex(
        index, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
    )


def test_navigation_history_filter_views_and_details(browser):
    root = browser.service.root
    assert not browser.up_button.isEnabled()
    assert browser.navigate(root / "Clientes")
    assert browser.up_button.isEnabled()
    browser.go_back()
    assert browser.current_path == root
    browser.go_forward()
    assert browser.current_path == root / "Clientes"
    browser.go_up()
    browser.filter_edit.setText("NOTA")
    assert browser.files_proxy.rowCount(browser.list_view.rootIndex()) == 1
    select(browser, root / "nota.txt")
    browser.details_button.click()
    assert browser.details.isVisible()
    assert browser.details_name.text() == "nota.txt"
    browser.icons_button.click()
    assert browser.file_views.currentWidget() is browser.icons_view
    assert browser._selected_path() == root / "nota.txt"
    browser.list_button.click()
    browser.filter_edit.clear()
    assert browser.files_proxy.rowCount(browser.list_view.rootIndex()) == 3


def test_open_uses_windows_association_but_outside_and_missing_paths_are_blocked(browser, monkeypatch, tmp_path):
    from app.ui.widgets import work_files_widget
    opened = []
    warnings = []
    monkeypatch.setattr(work_files_widget.QDesktopServices, "openUrl", lambda url: opened.append(url.toLocalFile()) or True)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[-1]))
    path = browser.service.root / "nota.txt"
    select(browser, path)
    browser.open_selected()
    browser.open_in_windows()
    assert [Path(p) for p in opened] == [path, browser.service.root]
    path.unlink()
    browser._open_path(path)
    assert not browser.navigate(tmp_path)
    assert len(warnings) == 2
    assert len(opened) == 2


def test_missing_root_and_deleted_current_folder_recover_without_creating_data(browser, monkeypatch):
    root = browser.service.root
    browser.navigate(root / "Clientes")
    (root / "Clientes").rmdir()
    browser.refresh()
    assert browser.current_path == root
    missing = root / "sin-crear"
    widget = WorkFilesWidget(service=WorkFilesService(missing))
    assert widget.splitter.isHidden()
    assert "No se puede abrir Trabajo" in widget.message.text()
    assert not missing.exists()
    missing.mkdir()
    widget.refresh()
    assert not widget.splitter.isHidden()
    assert widget.open_windows_button.isEnabled()
    widget.deleteLater()


def test_create_folder_cancellation_and_selection(browser, monkeypatch):
    from app.ui.widgets import work_files_widget
    monkeypatch.setattr(work_files_widget.QInputDialog, "getText", lambda *a, **kw: ("Cancelada", False))
    browser.create_button.click()
    assert not (browser.service.root / "Cancelada").exists()
    monkeypatch.setattr(work_files_widget.QInputDialog, "getText", lambda *a, **kw: ("Nueva carpeta", True))
    browser.create_button.click()
    created = browser.service.root / "Nueva carpeta"
    wait_for(lambda: browser._selected_path() == created)
    assert created.is_dir()


def test_rename_selected_and_cancel_extension_change(browser, monkeypatch):
    from app.ui.widgets import work_files_widget
    root = browser.service.root
    assert not browser.rename_button.isEnabled()
    select(browser, root / "nota.txt")
    assert browser.rename_button.isEnabled()
    monkeypatch.setattr(work_files_widget.QInputDialog, "getText", lambda *a, **kw: ("nueva.pdf", True))
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.No)
    browser.rename_button.click()
    assert (root / "nota.txt").exists() and not (root / "nueva.pdf").exists()
    monkeypatch.setattr(work_files_widget.QInputDialog, "getText", lambda *a, **kw: ("renombrada.txt", True))
    browser.rename_button.click()
    wait_for(lambda: browser._selected_path() == root / "renombrada.txt")
    assert (root / "renombrada.txt").read_text(encoding="utf-8") == "prueba"


def test_move_cancel_and_success_refresh_current_folder(browser, monkeypatch):
    root = browser.service.root
    select(browser, root / "nota.txt")
    monkeypatch.setattr(browser, "_choose_destination", lambda: None)
    browser.move_button.click()
    assert (root / "nota.txt").exists()
    monkeypatch.setattr(browser, "_choose_destination", lambda: root / "Pedidos")
    browser.move_button.click()
    assert (root / "Pedidos/nota.txt").read_text(encoding="utf-8") == "prueba"
    assert browser.current_path == root
    assert not (root / "nota.txt").exists()
    assert not browser.move_button.isEnabled()


def test_move_destination_dialog_starts_at_work_and_cancel_is_non_mutating(browser, monkeypatch):
    from PySide6.QtWidgets import QDialog, QTreeView
    def cancel(dialog):
        tree = dialog.findChild(QTreeView, "workMoveDestinationTree")
        index = browser.tree_proxy.mapToSource(tree.currentIndex())
        assert Path(browser.tree_model.filePath(index)) == browser.service.root
        return QDialog.DialogCode.Rejected
    monkeypatch.setattr(QDialog, "exec", cancel)
    assert browser._choose_destination() is None


def test_recycle_requires_confirmation_and_does_not_intercept_filter_delete(browser, monkeypatch):
    from app.services import work_files_service
    from PySide6.QtCore import Qt
    recycled = []
    monkeypatch.setattr(work_files_service, "_recycle_windows", recycled.append)
    path = browser.service.root / "nota.txt"
    select(browser, path)
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.No)
    browser.recycle_button.click()
    assert recycled == [] and path.exists()
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Yes)
    browser.filter_edit.setText("notaa")
    browser.filter_edit.setFocus()
    browser.filter_edit.setCursorPosition(4)
    QTest.keyClick(browser.filter_edit, Qt.Key.Key_Delete)
    assert browser.filter_edit.text() == "nota"
    assert recycled == []
    select(browser, path)
    browser.recycle_button.click()
    assert recycled == [path]


def test_recycle_error_is_visible_and_file_is_preserved(browser, monkeypatch):
    warnings = []
    path = browser.service.root / "nota.txt"
    select(browser, path)
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[-1]))
    from app.services.work_files_service import WorkFilesError
    def fail(_path):
        raise WorkFilesError("Archivo en uso")
    monkeypatch.setattr(browser.service, "recycle", fail)
    browser.recycle_button.click()
    assert path.exists()
    assert warnings == ["Archivo en uso"]


def test_icon_click_selects_file_and_enables_management_actions(browser):
    from PySide6.QtCore import QRect, Qt
    path = browser.service.root / "nota.txt"
    browser.icons_button.click()
    def file_rect():
        # QFileSystemModel loads and sorts asynchronously; reacquire indexes
        # after processing events instead of holding a transient QModelIndex.
        index = browser.files_proxy.mapFromSource(browser.files_model.index(str(path)))
        return browser.icons_view.visualRect(index) if index.isValid() else QRect()
    wait_for(lambda: file_rect().isValid())
    QTest.mouseClick(browser.icons_view.viewport(), Qt.MouseButton.LeftButton,
                     pos=file_rect().center())
    assert browser._selected_path() == path
    assert browser.rename_button.isEnabled()
    assert browser.move_button.isEnabled()
    assert browser.recycle_button.isEnabled()


def test_deep_breadcrumbs_scroll_inside_the_bar(browser):
    deepest = browser.service.root
    for number in range(9):
        deepest = deepest / f"carpeta{number:02d}"
        deepest.mkdir()
    browser.resize(950, 650)
    browser.navigate(deepest)
    wait_for(lambda: browser.breadcrumb_scroll.horizontalScrollBar().maximum() > 0)
    assert browser.minimumSizeHint().width() <= 950
    assert browser.breadcrumb_scroll.width() < browser.width()
