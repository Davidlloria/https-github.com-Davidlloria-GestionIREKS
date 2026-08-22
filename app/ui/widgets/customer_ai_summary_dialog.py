from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QPlainTextEdit, QVBoxLayout, QWidget


class CustomerAISummaryDialog(QDialog):
    def __init__(
        self,
        *,
        customer_name: str,
        summary: str,
        status: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("customerAISummaryDialog")
        self.setWindowTitle(f"Resumen IA · {customer_name}")
        self.resize(760, 620)
        self.setMinimumSize(620, 460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel(f"Resumen comercial · {customer_name}")
        title.setObjectName("customerAISummaryTitle")
        title.setProperty("role", "sectionTitle")
        layout.addWidget(title)

        self.status_label = QLabel(status)
        self.status_label.setObjectName("customerAISummaryStatus")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #64748B;")
        layout.addWidget(self.status_label)

        self.summary_text = QPlainTextEdit()
        self.summary_text.setObjectName("customerAISummaryText")
        self.summary_text.setReadOnly(True)
        self.summary_text.setPlainText(summary)
        layout.addWidget(self.summary_text, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.setObjectName("customerAISummaryButtons")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
