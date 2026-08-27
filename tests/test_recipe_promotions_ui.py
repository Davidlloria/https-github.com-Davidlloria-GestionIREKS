import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.ui.widgets.recipes_page import PromotionEditorDialog


_APP = QApplication.instance() or QApplication([])


class _FakeRecipeService:
    def search_ingredients(self, _term: str):
        return [
            SimpleNamespace(
                tipo_origen="ireks",
                ingrediente_id=7,
                codigo="IREKS-7",
                nombre="Producto promocionado",
            ),
            SimpleNamespace(
                tipo_origen="std",
                ingrediente_id=0,
                codigo="STD-1",
                nombre="Materia prima",
            ),
        ]


def test_promotion_editor_only_offers_ireks_products_and_builds_payload() -> None:
    dialog = PromotionEditorDialog(_FakeRecipeService())  # type: ignore[arg-type]
    dialog.product_combo.setCurrentIndex(0)
    dialog.buy_spin.setValue(10)
    dialog.free_spin.setValue(2)
    dialog.from_input.setText("2026-01-01")

    payload = dialog.payload()

    assert dialog.product_combo.count() == 1
    assert payload["producto_ireks_id"] == 7
    assert payload["unidades_compra"] == 10
    assert payload["unidades_sin_cargo"] == 2
    assert payload["fecha_desde"].isoformat() == "2026-01-01"
