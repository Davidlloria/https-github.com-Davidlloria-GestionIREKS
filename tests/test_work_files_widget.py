import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QItemSelectionModel
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
    QApplication.sendPostedEvents(None, 0)
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
