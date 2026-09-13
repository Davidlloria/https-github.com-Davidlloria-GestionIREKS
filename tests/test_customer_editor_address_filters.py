from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLineEdit

from app.models import CodigoPostal, Isla, Localidad, Municipio, Provincia
from app.ui.widgets.customers_page import CustomerEditorDialog


_APP: QApplication | None = None


def _application() -> QApplication:
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def _dialog() -> CustomerEditorDialog:
    _application()
    return CustomerEditorDialog(
        title="Cliente",
        provincias=[Provincia(provincia_id="prov", provincia_nombre="Provincia", provincia_codigo="P")],
        islas=[Isla(isla_id="isla", provincia_id="prov", isla_nombre="Isla", isla_codigo="I", isla_iniciales="I")],
        municipios=[
            Municipio(municipio_id="mun-a", isla_id="isla", provincia_id="prov", municipio_nombre="Municipio A", municipio_codigo="A"),
            Municipio(municipio_id="mun-b", isla_id="isla", provincia_id="prov", municipio_nombre="Municipio B", municipio_codigo="B"),
        ],
        codigos_postales=[
            CodigoPostal(municipio_id="mun-a", codigo_postal="35001"),
            CodigoPostal(municipio_id="mun-a", codigo_postal="35002"),
            CodigoPostal(municipio_id="mun-b", codigo_postal="35001"),
            CodigoPostal(municipio_id="mun-b", codigo_postal="35003"),
        ],
        localidades=[
            Localidad(localidad_id="loc-a-1", municipio_id="mun-a", localidad_nombre="Localidad A1", codigo_postal="35001"),
            Localidad(localidad_id="loc-a-2", municipio_id="mun-a", localidad_nombre="Localidad A2", codigo_postal="35002"),
            Localidad(localidad_id="loc-b-1", municipio_id="mun-b", localidad_nombre="Localidad B1", codigo_postal="35001"),
        ],
    )


def test_customer_address_filters_cp_and_municipio_bidirectionally() -> None:
    dialog = _dialog()
    dialog.provincia_combo.setCurrentIndex(dialog.provincia_combo.findData("prov"))
    dialog.isla_combo.setCurrentIndex(dialog.isla_combo.findData("isla"))

    assert isinstance(dialog.municipio_edit, QLineEdit)
    assert isinstance(dialog.cp_edit, QLineEdit)
    assert dialog.municipio_edit.completer() is not None
    assert dialog.cp_edit.completer() is not None
    assert list(dialog._municipio_options) == ["Municipio A", "Municipio B"]
    assert dialog._cp_options == {"35001", "35002", "35003"}

    dialog.cp_edit.setText("35002")
    dialog.cp_edit.editingFinished.emit()
    assert dialog._selected_cp == "35002"
    assert list(dialog._municipio_options) == ["Municipio A"]

    dialog.municipio_edit.setText("Municipio A")
    dialog.municipio_edit.editingFinished.emit()
    assert dialog._selected_municipio_id == "mun-a"
    assert dialog._cp_options == {"35001", "35002"}
    assert dialog._selected_cp == "35002"
    assert dialog.localidad_combo.itemText(1) == "Localidad A2"

    dialog.cp_edit.clear()
    dialog.cp_edit.editingFinished.emit()
    dialog.municipio_edit.setText("Municipio B")
    dialog.municipio_edit.editingFinished.emit()
    assert dialog._cp_options == {"35001", "35003"}
    assert dialog._selected_cp == ""
    assert dialog.localidad_combo.count() == 1


def test_customer_detail_opens_all_cp_municipalities_on_focus() -> None:
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QFocusEvent
    from PySide6.QtWidgets import QWidget, QComboBox
    from app.ui.widgets.customers_page import CustomersPage

    class DetailHarness(CustomersPage):
        def __init__(self):
            QWidget.__init__(self)
            self._is_loading_details = False
            self.detail_municipio = QLineEdit(self)
            self.detail_municipio.installEventFilter(self)
            self.detail_municipio_completer = self._build_detail_lookup_completer(self.detail_municipio)
            self.detail_isla = QComboBox(self)
            self.detail_isla.addItem("Isla", "isla")
            self.detail_selected_cp = "35001"
            self.detail_selected_municipio_id = "mun-a"
            self.municipios = [
                Municipio(municipio_id="mun-a", isla_id="isla", municipio_nombre="Municipio A"),
                Municipio(municipio_id="mun-b", isla_id="isla", municipio_nombre="Municipio B"),
                Municipio(municipio_id="mun-c", isla_id="isla", municipio_nombre="Municipio C"),
            ]
            self.codigos_postales = [
                CodigoPostal(municipio_id="mun-a", codigo_postal="35001"),
                CodigoPostal(municipio_id="mun-b", codigo_postal="35001"),
                CodigoPostal(municipio_id="mun-c", codigo_postal="35002"),
            ]

    app = _application()
    page = DetailHarness()
    page.show()
    page.activateWindow()
    app.processEvents()
    page.detail_municipio.setFocus()
    QApplication.sendEvent(page.detail_municipio, QFocusEvent(QEvent.Type.FocusIn))
    app.processEvents()
    app.processEvents()
    assert page.detail_municipio_completer.popup().isVisible()
    assert page.detail_municipio_completer.completionCount() == 2
    assert list(page.detail_municipio_options) == ["Municipio A", "Municipio B"]
    assert page.detail_selected_municipio_id == "mun-a"
    page.detail_municipio_completer.popup().hide()
    page.close()
