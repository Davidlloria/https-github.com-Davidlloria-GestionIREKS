from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

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


def _labels(combo) -> list[str]:
    return [combo.itemText(index) for index in range(1, combo.count())]


def test_customer_address_filters_cp_and_municipio_bidirectionally() -> None:
    dialog = _dialog()
    dialog.provincia_combo.setCurrentIndex(dialog.provincia_combo.findData("prov"))
    dialog.isla_combo.setCurrentIndex(dialog.isla_combo.findData("isla"))

    assert dialog.cp_combo.isEditable()
    assert _labels(dialog.municipio_combo) == ["Municipio A", "Municipio B"]
    assert _labels(dialog.cp_combo) == ["35001", "35002", "35003"]

    dialog.cp_combo.lineEdit().setText("35002")
    dialog.cp_combo.lineEdit().editingFinished.emit()
    assert dialog.cp_combo.currentData() == "35002"
    assert _labels(dialog.municipio_combo) == ["Municipio A"]

    dialog.municipio_combo.setCurrentIndex(dialog.municipio_combo.findData("mun-a"))
    assert _labels(dialog.cp_combo) == ["35001", "35002"]
    assert dialog.cp_combo.currentData() == "35002"
    assert _labels(dialog.localidad_combo) == ["Localidad A2"]

    dialog.cp_combo.setCurrentIndex(0)
    dialog.municipio_combo.setCurrentIndex(dialog.municipio_combo.findData("mun-b"))
    assert _labels(dialog.cp_combo) == ["35001", "35003"]
    assert dialog.cp_combo.currentData() == ""
    assert _labels(dialog.localidad_combo) == []
