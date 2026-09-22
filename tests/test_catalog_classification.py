import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from sqlmodel import SQLModel, Session, create_engine, select
from sqlalchemy.pool import StaticPool
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog

from app.models import Fabricante, Familia, Subfamilia, IngredienteIreks
from app.services import warehouse_catalog_service as module
from app.ui.widgets.catalog_classification_page import CatalogClassificationPage, CatalogEditor

APP = None


@pytest.fixture
def catalog(monkeypatch):
    global APP
    APP = QApplication.instance() or QApplication([])
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(module, "engine", engine)
    with Session(engine) as session:
        session.add_all([
            Fabricante(fabricante_id="a", fabricante_codigo=1, fabricante_nombre="IREKS"),
            Fabricante(fabricante_id="b", fabricante_codigo=2, fabricante_nombre="DREIDOPPEL"),
            Familia(articulo_familia_id="f1", fabricante_id="a", articulo_familia_nombre="Panes", articulo_familia_codigo="10"),
            Familia(articulo_familia_id="f2", fabricante_id="b", articulo_familia_nombre="Aromas", articulo_familia_codigo="20"),
            Subfamilia(articulo_familia_id="f1", articulo_subfamilia_id="same", articulo_subfamilia_nombre="Especiales"),
            Subfamilia(articulo_familia_id="f2", articulo_subfamilia_id="same", articulo_subfamilia_nombre="Líquidos"),
        ])
        session.commit()
    page = CatalogClassificationPage(service=module.WarehouseCatalogService())
    yield page, engine
    page.close()
    page.deleteLater()
    APP.processEvents()
    engine.dispose()


def choose(page, level, identity):
    table = page.tables[level]
    for row in range(table.rowCount()):
        if table.item(row, 0).data(Qt.ItemDataRole.UserRole) == identity:
            table.selectRow(row)
            return
    raise AssertionError(identity)


def test_cascade_search_and_sorted_selection(catalog):
    page, _ = catalog
    assert page.tables[1].rowCount() == 0
    assert not page.new_buttons[1].isEnabled()
    page.tables[0].sortItems(1, Qt.SortOrder.AscendingOrder)
    choose(page, 0, "a")
    assert page.tables[1].item(0, 1).text() == "Panes"
    choose(page, 1, "f1")
    choose(page, 2, "same")
    assert page.path.text() == "IREKS  ›  Panes  ›  Especiales"
    choose(page, 0, "b")
    assert page.selected == ["b", None, None]
    assert page.tables[2].rowCount() == 0
    choose(page, 1, "f2")
    choose(page, 2, "same")
    assert page._row(2).articulo_subfamilia_nombre == "Líquidos"
    page.searches[0].setText("IREKS")
    assert page.selected == [None, None, None]
    assert not page.edit_buttons[2].isEnabled()


def test_create_family_links_parent_and_selects_new_record(catalog, monkeypatch):
    page, engine = catalog
    choose(page, 0, "a")
    def accept(dialog):
        dialog.code.setText("30")
        dialog.name.setText("Pastelería")
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(CatalogEditor, "exec", accept)
    page._edit(1, new=True)
    row = page._row(1)
    assert row.fabricante_id == "a"
    assert row.articulo_familia_nombre == "Pastelería"
    assert row.articulo_familia_id
    with Session(engine) as session:
        assert len(list(session.exec(select(Familia)))) == 3


def test_subfamily_edit_uses_parent_composite_key(catalog, monkeypatch):
    page, engine = catalog
    choose(page, 0, "b")
    choose(page, 1, "f2")
    choose(page, 2, "same")
    def accept(dialog):
        dialog.name.setText("Aromas líquidos")
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(CatalogEditor, "exec", accept)
    page._edit(2)
    with Session(engine) as session:
        assert session.get(Subfamilia, ("f1", "same")).articulo_subfamilia_nombre == "Especiales"
        assert session.get(Subfamilia, ("f2", "same")).articulo_subfamilia_nombre == "Aromas líquidos"


def test_deletion_guards_and_composite_key(catalog):
    page, engine = catalog
    with pytest.raises(ValueError, match="asociadas"):
        page.service.delete_classification("fabricante", "a")
    with pytest.raises(ValueError, match="asociadas"):
        page.service.delete_classification("familia", "f1")
    with Session(engine) as session:
        session.add(IngredienteIreks(articulo_id="p", articulo_familia_id="f1", articulo_subfamilia_id="same"))
        session.commit()
    with pytest.raises(ValueError, match="productos asociados"):
        page.service.delete_classification("subfamilia", "same", familia_id="f1")
    page.service.delete_classification("subfamilia", "same", familia_id="f2")
    with Session(engine) as session:
        assert session.get(Subfamilia, ("f1", "same")) is not None
        assert session.get(Subfamilia, ("f2", "same")) is None


def test_tables_fit_and_reload_preserves_selection(catalog):
    page, _ = catalog
    choose(page, 0, "a")
    choose(page, 1, "f1")
    page.show()
    for width in (1250, 1050):
        page.resize(width, 700)
        APP.processEvents()
        assert all(t.horizontalScrollBar().maximum() == 0 for t in page.tables)
    page.reload()
    assert page.selected[:2] == ["a", "f1"]


def test_cancel_edit_does_not_write(catalog, monkeypatch):
    page, engine = catalog
    monkeypatch.setattr(CatalogEditor, "exec", lambda _: QDialog.DialogCode.Rejected)
    page._edit(0, new=True)
    with Session(engine) as session:
        assert len(list(session.exec(select(Fabricante)))) == 2


def test_warehouse_tab_and_product_entry(catalog, monkeypatch):
    from app.ui.widgets.ingredients_page import IngredientsIreksPage
    from app.ui.widgets.warehouse_page import WarehousePage
    from app.ui.widgets import catalog_classification_page as ui
    monkeypatch.setattr(IngredientsIreksPage, "reload", lambda self: None)
    monkeypatch.setattr(WarehousePage, "reload", lambda self: None)
    warehouse = WarehousePage()
    titles = [warehouse.main_tabs.tabText(i) for i in range(warehouse.main_tabs.count())]
    assert titles == ["Stock", "Entradas", "Salidas", "Inventarios", "Caducidades"]
    assert warehouse.main_tabs.currentWidget() is warehouse.stock_tab
    warehouse.almacen_combo.addItem("IGSA", "igsa")
    warehouse.almacen_combo.setCurrentIndex(warehouse.almacen_combo.count() - 1)
    warehouse.monthly_report_action.trigger()
    assert warehouse.monthly_dialog.isVisible()
    assert warehouse.monthly_orders_tab._almacen_id == "igsa"
    warehouse.monthly_dialog.close()
    products = IngredientsIreksPage()
    opened = []
    monkeypatch.setattr(ui, "open_classification", lambda parent: opened.append(parent))
    products.classification_btn.click()
    assert opened == [products]
    from app.ui.widgets import product_catalog_dialog
    sections = []
    monkeypatch.setattr(product_catalog_dialog, "open_catalog_section", lambda parent, section: sections.append(section))
    products.packaging_btn.click()
    products.references_btn.click()
    assert sections == ["envases", "referencias"]
    products.close()
    warehouse.close()
