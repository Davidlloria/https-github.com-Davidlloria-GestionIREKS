from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QWidget, QVBoxLayout

from app.ui.bridges.customers_bridge import CustomersBridge


class CustomersQmlPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.bridge = CustomersBridge(self)
        self.quick = QQuickWidget()
        self.quick.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        self.quick.rootContext().setContextProperty("customersBridge", self.bridge)
        qml_path = Path(__file__).resolve().parent.parent / "ui_qml" / "customers" / "CustomersPage.qml"
        self.quick.setSource(QUrl.fromLocalFile(str(qml_path)))
        layout.addWidget(self.quick, 1)

        self.reload()

    def reload(self) -> None:
        self.bridge.loadCustomers("")
