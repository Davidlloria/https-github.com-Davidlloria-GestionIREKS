from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PlaceholderPage(QWidget):
    def __init__(self, title: str, message: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        heading = QLabel(title)
        heading.setProperty("role", "pageTitle")
        detail = QLabel(message)
        detail.setProperty("role", "secondaryText")
        detail.setWordWrap(True)
        detail.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(heading)
        layout.addWidget(detail)
        layout.addStretch()
