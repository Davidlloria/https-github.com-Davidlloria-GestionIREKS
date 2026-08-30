from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QFrame,
    QListWidget,
    QMessageBox,
    QScrollArea,
    QStackedWidget,
)

from app.services.local_ai_settings_service import LocalAISettingsService
from app.ui.widgets.settings_page import SettingsPage


_APP: QApplication | None = None


def _application() -> QApplication:
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def test_api_tab_uses_sidebar_and_selected_detail_card() -> None:
    _application()
    page = SettingsPage()
    page.resize(1280, 900)
    page.main_tabs.setCurrentIndex(3)
    page.show()
    QApplication.processEvents()

    menu = page.findChild(QFrame, "settingsApiMenu")
    api_list = page.findChild(QListWidget, "settingsApiList")
    detail_stack = page.findChild(QStackedWidget, "settingsApiDetailStack")
    scroll = page.findChild(QScrollArea, "settingsApiScrollArea")
    cards = [card for card in page.findChildren(QFrame, "card") if card.property("apiCard")]
    cards_by_name = {str(card.property("apiCard")): card for card in cards}

    assert menu is not None
    assert api_list is not None
    assert detail_stack is not None
    assert scroll is not None
    assert len(cards) == 4
    assert api_list.count() == 4
    assert [api_list.item(index).text() for index in range(api_list.count())] == [
        "FoodData Central",
        "FatSecret",
        "OpenAI",
        "IA local",
    ]
    assert api_list.currentRow() == 0
    assert detail_stack.currentWidget() is cards_by_name["fdc"]
    assert menu.geometry().right() < scroll.geometry().left()

    page.fdc_api_key_input.setText("valor-sin-guardar")
    card_names = ["fdc", "fatsecret", "openai", "local_ai"]
    for index, card_name in enumerate(card_names):
        api_list.setCurrentRow(index)
        QApplication.processEvents()
        assert detail_stack.currentWidget() is cards_by_name[card_name]
        assert cards_by_name[card_name].isVisibleTo(page)

    api_list.setCurrentRow(0)
    assert page.fdc_api_key_input.text() == "valor-sin-guardar"

    for field in (
        page.fdc_api_key_input,
        page.fdc_data_type_combo,
        page.fatsecret_client_id_input,
        page.fatsecret_client_secret_input,
        page.fatsecret_scope_input,
        page.openai_api_key_input,
        page.local_ai_base_url_input,
        page.local_ai_model_input,
        page.local_ai_embedding_model_input,
    ):
        parent = field.parentWidget()
        assert parent is not None
        assert field.geometry().right() <= parent.contentsRect().right()

    controls_by_card = {
        "fdc": [
            page.fdc_api_key_input,
            page.fdc_data_type_combo,
            page.fdc_save_btn,
            page.fdc_test_btn,
            page.findChild(QLabel, "settingsApiFdcInfo"),
        ],
        "fatsecret": [
            page.fatsecret_client_id_input,
            page.fatsecret_client_secret_input,
            page.fatsecret_scope_input,
            page.fatsecret_save_btn,
            page.fatsecret_test_btn,
            page.findChild(QLabel, "settingsApiFatSecretInfo"),
        ],
        "openai": [
            page.openai_api_key_input,
            page.use_ai_translation_check,
            page.openai_save_btn,
            page.openai_test_btn,
            page.findChild(QLabel, "settingsApiOpenAiInfo"),
        ],
        "local_ai": [
            page.local_ai_enabled_check,
            page.local_ai_base_url_input,
            page.local_ai_model_input,
            page.local_ai_embedding_model_input,
            page.local_ai_save_btn,
            page.local_ai_test_btn,
            page.local_ai_test_embedding_btn,
            page.findChild(QLabel, "settingsApiLocalAiInfo"),
        ],
    }
    for widgets in controls_by_card.values():
        assert all(widget is not None for widget in widgets)
        for index, widget in enumerate(widgets):
            for other in widgets[index + 1 :]:
                assert not widget.geometry().intersects(other.geometry())

    page.close()
    page.deleteLater()
    QApplication.processEvents()


def test_local_ai_card_loads_embedding_field_in_visual_order(monkeypatch) -> None:
    monkeypatch.setattr(
        LocalAISettingsService,
        "load",
        lambda _self: {
            "enabled": True,
            "base_url": "http://localhost:11434",
            "model": "chat-saved",
            "embedding_model": "embed-saved",
        },
    )
    _application()
    page = SettingsPage()
    page.resize(1280, 900)
    page.main_tabs.setCurrentIndex(3)
    page.show()
    QApplication.processEvents()

    labels = {label.text() for label in page.findChildren(QLabel)}
    assert "Configuración IA local" in labels
    assert "Modelo conversacional" in labels
    assert "Modelo de embeddings" in labels
    assert page.local_ai_model_input.placeholderText() == "qwen3.5:4b"
    assert page.local_ai_embedding_model_input.placeholderText() == "embeddinggemma"
    assert page.local_ai_model_input.text() == "chat-saved"
    assert page.local_ai_embedding_model_input.text() == "embed-saved"
    assert page.local_ai_base_url_input.y() < page.local_ai_model_input.y()
    assert page.local_ai_model_input.y() < page.local_ai_embedding_model_input.y()
    assert page.local_ai_embedding_model_input.height() == 34
    assert page.local_ai_test_embedding_btn.height() == 34
    assert page.local_ai_test_embedding_btn.text() == "Probar embeddings"

    page.close()
    page.deleteLater()
    QApplication.processEvents()


def test_local_ai_card_stays_accessible_at_reduced_api_tab_height() -> None:
    _application()
    page = SettingsPage()
    page.resize(1180, 720)
    page.main_tabs.setCurrentIndex(3)
    page.api_list.setCurrentRow(3)
    page.show()
    QApplication.processEvents()

    scroll = page.findChild(QScrollArea, "settingsApiScrollArea")
    local_card = next(
        card
        for card in page.findChildren(QFrame, "card")
        if card.property("apiCard") == "local_ai"
    )
    info = page.findChild(QLabel, "settingsApiLocalAiInfo")

    assert scroll is not None
    assert info is not None
    assert scroll.widgetResizable()
    assert local_card.minimumHeight() <= 390
    assert page.local_ai_save_btn.y() == page.local_ai_test_btn.y()
    assert page.local_ai_test_btn.y() == page.local_ai_test_embedding_btn.y()
    assert info.geometry().bottom() <= local_card.contentsRect().bottom()

    scroll.setFixedHeight(300)
    QApplication.processEvents()
    assert scroll.verticalScrollBar().maximum() > 0
    scroll.ensureWidgetVisible(info)
    QApplication.processEvents()
    assert scroll.viewport().rect().contains(
        info.mapTo(scroll.viewport(), info.rect().center())
    )

    page.close()
    page.deleteLater()
    QApplication.processEvents()


class _FakeLocalAIProvider:
    def __init__(self, *, embedding_ok=True) -> None:
        self.embedding_ok = embedding_ok
        self.saved = None
        self.tested_embedding = None

    def save_local_ai(self, **kwargs):
        self.saved = kwargs
        return type("R", (), {"ok": True, "message": "Guardado", "path": "data/api_config.json"})()

    def test_local_embedding(self, **kwargs):
        self.tested_embedding = kwargs
        if self.embedding_ok:
            return type(
                "R",
                (),
                {"ok": True, "message": "Modelo 'embed-ui' disponible. Dimensión: 768."},
            )()
        return type(
            "R",
            (),
            {"ok": False, "message": "El modelo local 'missing' no está instalado en Ollama."},
        )()


def test_local_ai_save_and_embedding_test_transmit_independent_model(monkeypatch) -> None:
    _application()
    page = SettingsPage()
    provider = _FakeLocalAIProvider()
    page.settings_provider_service = provider
    page.local_ai_enabled_check.setChecked(True)
    page.local_ai_base_url_input.setText("http://localhost:11434")
    page.local_ai_model_input.setText("chat-ui")
    page.local_ai_embedding_model_input.setText("embed-ui")
    information = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda _parent, title, message: information.append((title, message)),
    )

    page._save_local_ai_settings()
    page._test_local_embedding_connection()

    assert provider.saved == {
        "enabled": True,
        "base_url": "http://localhost:11434",
        "model": "chat-ui",
        "embedding_model": "embed-ui",
    }
    assert provider.tested_embedding == {
        "base_url": "http://localhost:11434",
        "embedding_model": "embed-ui",
    }
    assert any("Dimensión: 768" in message for _title, message in information)
    assert all("vector" not in message.casefold() for _title, message in information)

    page.close()
    page.deleteLater()


def test_local_embedding_missing_model_uses_warning_without_vectors(monkeypatch) -> None:
    _application()
    page = SettingsPage()
    provider = _FakeLocalAIProvider(embedding_ok=False)
    page.settings_provider_service = provider
    page.local_ai_base_url_input.setText("http://localhost:11434")
    page.local_ai_embedding_model_input.setText("missing")
    warnings = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, title, message: warnings.append((title, message)),
    )

    page._test_local_embedding_connection()

    assert warnings == [
        ("IA local", "El modelo local 'missing' no está instalado en Ollama.")
    ]
    assert "vector" not in warnings[0][1].casefold()

    page.close()
    page.deleteLater()


def test_local_ai_save_requires_url_and_both_models(monkeypatch) -> None:
    _application()
    page = SettingsPage()
    provider = _FakeLocalAIProvider()
    page.settings_provider_service = provider
    page.local_ai_base_url_input.setText("http://localhost:11434")
    page.local_ai_model_input.setText("chat-ui")
    page.local_ai_embedding_model_input.clear()
    warnings = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, title, message: warnings.append((title, message)),
    )

    page._save_local_ai_settings()

    assert provider.saved is None
    assert warnings and "Modelo de embeddings" in warnings[0][1]

    page.close()
    page.deleteLater()


def test_settings_page_can_be_embedded_without_duplicate_title(monkeypatch) -> None:
    _application()
    monkeypatch.setattr(SettingsPage, "_refresh_status", lambda self: None)

    page = SettingsPage(embedded=True)

    assert page.findChild(QLabel, "settingsPageTitle") is None
    assert [page.main_tabs.tabText(index) for index in range(page.main_tabs.count())] == [
        "Exportación BD",
        "Importación BD",
        "Mantenimiento BD",
        "API",
        "Correo",
        "Auxiliares",
    ]
    page.close()
    page.deleteLater()
    QApplication.processEvents()
