from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
)


class EntityDialog(QDialog):
    def __init__(
        self,
        title: str,
        schema: list[dict[str, Any]],
        initial: dict[str, Any] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.schema = schema
        self.initial = initial or {}
        self.inputs: dict[str, Any] = {}

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        for field in self.schema:
            name = field["name"]
            label = field["label"]
            ftype = field.get("type", "text")
            value = self.initial.get(name, field.get("default", ""))

            if ftype == "bool":
                widget = QCheckBox()
                widget.setChecked(bool(value))
            elif ftype == "float":
                widget = QDoubleSpinBox()
                widget.setMaximum(10_000_000)
                widget.setDecimals(4)
                widget.setValue(float(value or 0))
            elif ftype == "multiline":
                widget = QPlainTextEdit()
                widget.setPlainText(str(value or ""))
            else:
                widget = QLineEdit(str(value or ""))

            self.inputs[name] = widget
            form.addRow(label, widget)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for field in self.schema:
            name = field["name"]
            ftype = field.get("type", "text")
            widget = self.inputs[name]

            if ftype == "bool":
                payload[name] = widget.isChecked()
            elif ftype == "float":
                payload[name] = float(widget.value())
            elif ftype == "multiline":
                payload[name] = widget.toPlainText().strip()
            else:
                payload[name] = widget.text().strip()
        return payload

