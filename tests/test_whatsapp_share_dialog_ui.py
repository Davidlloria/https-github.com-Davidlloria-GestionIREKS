from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QComboBox, QCompleter

from app.services.whatsapp_share_service import WhatsAppRecipient
from app.ui.widgets.whatsapp_share_dialog import WhatsAppShareDialog


_APP: QApplication | None = None


def _application() -> QApplication:
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


class _FakeShareService:
    def list_recipients(self) -> list[WhatsAppRecipient]:
        return [
            WhatsAppRecipient(
                label="Ana López · Panadería Norte",
                phone="600111222",
                source="Contacto",
            ),
            WhatsAppRecipient(
                label="Panadería Sur",
                phone="600333444",
                source="Cliente",
            ),
        ]


def test_recipient_filter_matches_occurrences_in_any_position() -> None:
    application = _application()
    dialog = WhatsAppShareDialog(
        "Ficha técnica.pdf",
        _FakeShareService(),  # type: ignore[arg-type]
    )
    combo = dialog.recipient_combo
    completer = combo.completer()

    assert combo.isEditable() is True
    assert combo.insertPolicy() == QComboBox.InsertPolicy.NoInsert
    assert completer.caseSensitivity() == Qt.CaseSensitivity.CaseInsensitive
    assert completer.filterMode() == Qt.MatchFlag.MatchContains
    assert completer.completionMode() == QCompleter.CompletionMode.PopupCompletion
    assert combo.lineEdit() is not None
    assert combo.lineEdit().placeholderText() == (
        "Buscar por nombre, empresa o teléfono..."
    )

    completer.setCompletionPrefix("lópez")
    application.processEvents()
    assert completer.completionModel().rowCount() == 1

    contact_index = combo.findText(
        "López",
        Qt.MatchFlag.MatchContains,
    )
    combo.setCurrentIndex(contact_index)
    assert dialog.phone_input.text() == "600111222"
