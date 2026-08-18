from pathlib import Path
from xml.etree import ElementTree

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


def test_ireks_detail_icon_assets_are_valid_svg() -> None:
    icon_dir = Path(__file__).resolve().parents[1] / "assets" / "icons"
    icon_names = (
        "product-tag.svg",
        "presentation-container.svg",
        "pallet.svg",
        "calendar-chart.svg",
        "nutrition-lab.svg",
    )

    for icon_name in icon_names:
        icon_path = icon_dir / icon_name
        assert icon_path.is_file()
        assert ElementTree.parse(icon_path).getroot().tag.endswith("svg")


def test_ireks_tabs_use_local_enterprise_style_helpers() -> None:
    source = (Path(__file__).resolve().parents[1] / "app" / "ui" / "widgets" / "ingredients_page.py").read_text(
        encoding="utf-8"
    )

    assert "def _ireks_tab_header" in source
    assert "def _apply_ireks_table_style" in source
    for title in (
        "Clasificación",
        "Presentación",
        "Paletización",
        "Histórico de tarifas",
        "Entradas de almacén",
        "Salidas de almacén",
        "Stock y movimientos",
        "Resumen mensual",
        "Pedidos relacionados",
        "Información nutricional",
        "Consumo por cliente",
    ):
        assert title in source
