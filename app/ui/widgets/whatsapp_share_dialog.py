from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.services.whatsapp_share_service import (
    WhatsAppPhoneError,
    WhatsAppShareService,
)


class WhatsAppShareDialog(QDialog):
    def __init__(
        self,
        document_name: str,
        share_service: WhatsAppShareService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._share_service = share_service
        self.normalized_phone = ""
        self.setWindowTitle("WhatsApp")
        self.setMinimumWidth(540)

        layout = QVBoxLayout(self)
        title = QLabel(f"Compartir «{document_name}»")
        title.setProperty("role", "sectionTitle")
        layout.addWidget(title)

        form = QFormLayout()
        self.recipient_combo = QComboBox()
        self.recipient_combo.setObjectName("whatsappRecipientCombo")
        self.recipient_combo.addItem("Introducir otro número", "")
        self._load_recipients()
        self.recipient_combo.currentIndexChanged.connect(
            self._recipient_changed
        )
        form.addRow("Destinatario", self.recipient_combo)

        self.phone_input = QLineEdit()
        self.phone_input.setObjectName("whatsappPhoneInput")
        self.phone_input.setPlaceholderText("+34 600 000 000")
        form.addRow("Teléfono", self.phone_input)

        self.message_input = QTextEdit()
        self.message_input.setObjectName("whatsappMessageInput")
        self.message_input.setPlainText(
            f"Hola, te envío el documento «{document_name}»."
        )
        self.message_input.setFixedHeight(92)
        form.addRow("Mensaje", self.message_input)
        layout.addLayout(form)

        notice = QLabel(
            "Se abrirá la conversación y el Explorador dejará marcado el archivo. "
            "Arrástralo al chat y confirma el envío en WhatsApp Business."
        )
        notice.setObjectName("whatsappShareNotice")
        notice.setWordWrap(True)
        notice.setProperty("role", "secondaryText")
        layout.addWidget(notice)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.setObjectName("whatsappDialogButtons")
        continue_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        continue_button.setText("Continuar")
        continue_button.setProperty("btnRole", "success")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def message(self) -> str:
        return self.message_input.toPlainText().strip()

    def accept(self) -> None:
        try:
            self.normalized_phone = self._share_service.normalize_phone(
                self.phone_input.text()
            )
        except WhatsAppPhoneError as exc:
            QMessageBox.warning(self, "WhatsApp", str(exc))
            self.phone_input.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        super().accept()

    def _load_recipients(self) -> None:
        try:
            recipients = self._share_service.list_recipients()
        except Exception:  # noqa: BLE001
            recipients = []
        for recipient in recipients:
            self.recipient_combo.addItem(
                f"{recipient.label} — {recipient.phone}",
                recipient.phone,
            )

    def _recipient_changed(self, index: int) -> None:
        phone = str(self.recipient_combo.itemData(index) or "")
        self.phone_input.setText(phone)
        if not phone:
            self.phone_input.setFocus(Qt.FocusReason.OtherFocusReason)
