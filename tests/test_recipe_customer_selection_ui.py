import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QComboBox

from app.ui.widgets import recipes_page


_APP = QApplication.instance() or QApplication([])


def test_new_recipe_assigns_customer_created_after_initial_load(monkeypatch) -> None:
    customers = [SimpleNamespace(cliente_id="previous", cliente_nombre_comercial="Previo")]

    class Page:
        _load_customers = recipes_page.RecipesPage._load_customers
        _set_combo_by_data = recipes_page.RecipesPage._set_combo_by_data
        _selected_cliente_id = recipes_page.RecipesPage._selected_cliente_id

        def __init__(self):
            self.cliente_combo = QComboBox()
            self.recipe_service = SimpleNamespace(list_customers=lambda: list(customers))
            self.recipe_tabs = SimpleNamespace(currentIndex=lambda: 1)

        def _update_inline_customer_name(self):
            self.customer_name = self.cliente_combo.currentText()

        def _reload_customer_filter(self, customers):
            pass

        def _new_recipe(self, cliente_id=""):
            self._set_combo_by_data(self.cliente_combo, cliente_id)

    page = Page()
    page._load_customers()
    customers.append(SimpleNamespace(cliente_id="new", cliente_nombre_comercial="Regular Burguer"))
    assert page.cliente_combo.findData("new") == -1

    monkeypatch.setattr(
        recipes_page,
        "CustomerRecipeSelectionDialog",
        lambda *args: SimpleNamespace(exec=lambda: 1, selected_customer_id="new"),
    )

    recipes_page.RecipesPage._start_new_recipe(page)

    assert page._selected_cliente_id() == "new"
    assert page.customer_name == "Regular Burguer"
