from __future__ import annotations

from PySide6.QtWidgets import QApplication, QLabel

from app.ui.widgets.nutrition_card import NutritionCard, NutritionRowData


_APP: QApplication | None = None


def _application() -> QApplication:
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def test_nutrition_card_renders_formatted_rows() -> None:
    _application()
    card = NutritionCard(
        [
            NutritionRowData("energia", "Energía (kJ/kcal)", "100,00 kJ\n24,00 kcal", icon="energy"),
            NutritionRowData("azucares", "de los cuales azúcares", "3,00 g", icon="sugar", secondary=True),
        ]
    )

    labels = [label.text() for label in card.findChildren(QLabel)]

    assert "Valores nutricionales" in labels
    assert "Energía (kJ/kcal)" in labels
    assert "100,00 kJ\n24,00 kcal" in labels
    assert "de los cuales azúcares" in labels
