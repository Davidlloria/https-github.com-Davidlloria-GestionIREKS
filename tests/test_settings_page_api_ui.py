from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFrame, QWidget

from app.ui.widgets.settings_page import SettingsPage


_APP: QApplication | None = None


def _application() -> QApplication:
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def test_api_cards_keep_fields_and_actions_inside_the_centered_column() -> None:
    _application()
    page = SettingsPage()
    page.resize(1280, 900)
    page.main_tabs.setCurrentIndex(3)
    page.show()
    QApplication.processEvents()

    column = page.findChild(QWidget, "settingsApiCards")
    cards = [card for card in page.findChildren(QFrame, "card") if card.property("apiCard")]

    assert column is not None
    assert column.width() <= 720
    assert len(cards) == 4
    assert all(card.width() == column.width() for card in cards)
    assert all(cards[index].geometry().bottom() < cards[index + 1].geometry().top() for index in range(3))

    for field in (
        page.fdc_api_key_input,
        page.fdc_data_type_combo,
        page.fatsecret_client_id_input,
        page.fatsecret_client_secret_input,
        page.fatsecret_scope_input,
        page.openai_api_key_input,
        page.local_ai_base_url_input,
        page.local_ai_model_input,
    ):
        parent = field.parentWidget()
        assert parent is not None
        assert field.geometry().right() <= parent.contentsRect().right()

    page.close()
    page.deleteLater()
    QApplication.processEvents()
