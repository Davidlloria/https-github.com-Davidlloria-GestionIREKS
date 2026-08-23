from PySide6.QtWidgets import QApplication, QSizePolicy, QWidget

from app.ui.widgets.ingredients_page import IngredientsIreksPage
from app.ui.widgets.warehouse_page import WarehousePage


def test_warehouse_classification_uses_spaced_labels_and_compact_bottom_margin(monkeypatch) -> None:
    monkeypatch.setattr(IngredientsIreksPage, "reload", lambda self: None)
    monkeypatch.setattr(WarehousePage, "reload", lambda self: None)
    app = QApplication.instance() or QApplication([])

    page = WarehousePage()
    page.resize(1800, 950)
    page.show()
    app.processEvents()

    assert page.articles_tab is not None
    classification = page.articles_tab.findChild(QWidget, "ireksClassificationCard")
    assert classification is not None

    label = page.articles_tab.lbl_detail_fabricante
    field = page.articles_tab.detail_fabricante_id
    label_bottom = label.mapTo(classification, label.rect().bottomLeft()).y()
    field_top = field.mapTo(classification, field.rect().topLeft()).y()
    field_bottom = field.mapTo(classification, field.rect().bottomLeft()).y()
    content_bottom = classification.contentsRect().bottom()

    assert field_top - label_bottom - 1 == 3
    assert content_bottom - field_bottom <= 7
    assert classification.height() == 101

    page.close()


def test_warehouse_presentation_uses_exact_vertical_spacing(monkeypatch) -> None:
    monkeypatch.setattr(IngredientsIreksPage, "reload", lambda self: None)
    monkeypatch.setattr(WarehousePage, "reload", lambda self: None)
    app = QApplication.instance() or QApplication([])

    page = WarehousePage()
    page.resize(1800, 950)
    page.show()
    app.processEvents()

    assert page.articles_tab is not None
    presentation = page.articles_tab.findChild(QWidget, "ireksPresentationCard")
    assert presentation is not None
    presentation_layout = presentation.layout()
    assert presentation_layout is not None
    header = presentation_layout.itemAt(0).widget()
    assert header is not None

    first_label = page.articles_tab.lbl_detail_envase
    first_field = page.articles_tab.detail_envase_id
    second_label = page.articles_tab.lbl_detail_envase_peso
    second_field = page.articles_tab.detail_envase_peso

    def top(widget: QWidget) -> int:
        return widget.mapTo(presentation, widget.rect().topLeft()).y()

    def bottom(widget: QWidget) -> int:
        return widget.mapTo(presentation, widget.rect().bottomLeft()).y()

    assert top(first_label) - bottom(header) - 1 == 4
    assert top(first_field) - bottom(first_label) - 1 == 3
    assert top(second_label) - bottom(first_field) - 1 == 4
    assert top(second_field) - bottom(second_label) - 1 == 3
    assert presentation_layout.contentsMargins().bottom() == 4
    assert presentation.height() == 154

    page.close()


def test_warehouse_palletization_uses_exact_vertical_spacing(monkeypatch) -> None:
    monkeypatch.setattr(IngredientsIreksPage, "reload", lambda self: None)
    monkeypatch.setattr(WarehousePage, "reload", lambda self: None)
    app = QApplication.instance() or QApplication([])

    page = WarehousePage()
    page.resize(1800, 950)
    page.show()
    app.processEvents()

    assert page.articles_tab is not None
    pallet = page.articles_tab.findChild(QWidget, "ireksPalletCard")
    assert pallet is not None
    pallet_layout = pallet.layout()
    assert pallet_layout is not None
    header = pallet_layout.itemAt(0).widget()
    assert header is not None

    first_label = page.articles_tab.lbl_transporte_pallet
    first_field = page.articles_tab.transporte_pallet_tipo
    second_label = page.articles_tab.lbl_transporte_cajas_pallet
    second_field = page.articles_tab.transporte_cajas_por_pallet

    def top(widget: QWidget) -> int:
        return widget.mapTo(pallet, widget.rect().topLeft()).y()

    def bottom(widget: QWidget) -> int:
        return widget.mapTo(pallet, widget.rect().bottomLeft()).y()

    assert top(first_label) - bottom(header) - 1 == 4
    assert top(first_field) - bottom(first_label) - 1 == 3
    assert top(second_label) - bottom(first_field) - 1 == 4
    assert top(second_field) - bottom(second_label) - 1 == 3
    assert pallet_layout.contentsMargins().bottom() == 4
    assert pallet.height() == 154

    page.close()


def test_warehouse_observations_fill_remaining_detail_tab_height(monkeypatch) -> None:
    monkeypatch.setattr(IngredientsIreksPage, "reload", lambda self: None)
    monkeypatch.setattr(WarehousePage, "reload", lambda self: None)
    app = QApplication.instance() or QApplication([])

    page = WarehousePage()
    page.resize(1800, 950)
    page.show()
    app.processEvents()

    assert page.articles_tab is not None
    observations = page.articles_tab.findChild(QWidget, "ireksObservationsCard")
    assert observations is not None
    data_tab = observations.parentWidget()
    assert data_tab is not None
    data_layout = data_tab.layout()
    assert data_layout is not None

    assert observations.height() > 46
    assert page.articles_tab.transporte_observaciones.height() > 30
    assert observations.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Expanding
    assert page.articles_tab.transporte_observaciones.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Expanding
    assert data_layout.itemAt(data_layout.count() - 1).widget() is observations
    assert (
        data_tab.contentsRect().bottom() - observations.geometry().bottom()
        == data_layout.contentsMargins().bottom()
    )
    assert (
        observations.contentsRect().bottom()
        - page.articles_tab.transporte_observaciones.geometry().bottom()
        <= observations.layout().contentsMargins().bottom()
    )

    page.close()
