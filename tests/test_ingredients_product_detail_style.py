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


def test_detail_header_standard_is_declared_in_the_shared_theme() -> None:
    project_root = Path(__file__).resolve().parents[1]
    source = (project_root / "app" / "ui" / "widgets" / "ingredients_page.py").read_text(encoding="utf-8")
    theme = (project_root / "assets" / "styles.qss").read_text(encoding="utf-8")

    assert 'setProperty("uiRole", "detailHeader")' in source
    assert 'QFrame[uiRole="detailHeader"]' in theme
    assert 'QLabel[uiRole="detailHeaderTitle"]' in theme
    assert 'QLabel[uiRole="detailHeaderIcon"]' in theme


def test_ireks_data_cards_keep_their_controls_in_a_compact_desktop_layout(monkeypatch) -> None:
    monkeypatch.setattr(IngredientsIreksPage, "reload", lambda self: None)
    app = QApplication.instance() or QApplication([])

    page = IngredientsIreksPage()
    page.resize(1600, 900)
    page.show()
    app.processEvents()

    data_tab = page.detail_tabs.widget(0)
    classification = data_tab.findChild(QWidget, "ireksClassificationCard")
    presentation = data_tab.findChild(QWidget, "ireksPresentationCard")
    pallet = data_tab.findChild(QWidget, "ireksPalletCard")
    observations = data_tab.findChild(QWidget, "ireksObservationsCard")

    assert classification is not None
    assert presentation is not None
    assert pallet is not None
    assert observations is not None
    assert presentation.geometry().right() < pallet.geometry().left()
    assert presentation.geometry().bottom() <= data_tab.contentsRect().bottom()
    assert pallet.geometry().bottom() <= data_tab.contentsRect().bottom()
    assert observations.isAncestorOf(page.transporte_observaciones)

    page.close()
