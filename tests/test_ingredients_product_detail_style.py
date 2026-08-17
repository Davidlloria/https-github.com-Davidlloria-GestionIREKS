from pathlib import Path

from PySide6.QtWidgets import QApplication, QLabel, QWidget

from app.ui.widgets.ingredients_page import IngredientsIreksPage


def test_ireks_product_detail_uses_enterprise_panel(monkeypatch) -> None:
    monkeypatch.setattr(IngredientsIreksPage, "reload", lambda self: None)
    app = QApplication.instance() or QApplication([])

    page = IngredientsIreksPage()
    page.resize(1360, 820)
    page.show()
    app.processEvents()

    panel = page.findChild(QWidget, "detailPanel")
    title = page.findChild(QLabel, "productDetailTitle")

    assert panel is not None
    assert panel.height() == 232
    assert title is not None
    assert title.text() == "Detalle del producto"
    assert page.detail_status_activo_si.property("detailSegment") is True
    assert page.detail_status_en_lista_no.property("detailSegment") is True
    assert page.detail_categoria_harina.property("detailSegment") is True
    assert page.detail_status_activo_si.isChecked()
    assert page.detail_status_en_lista_no.isChecked()

    icon_dir = Path(__file__).resolve().parents[1] / "assets" / "icons"
    assert (icon_dir / "product-detail.svg").is_file()
    assert (icon_dir / "chevron-down-navy.svg").is_file()

    page.close()
