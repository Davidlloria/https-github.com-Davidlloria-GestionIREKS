from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PlaceholderPage(QWidget):
    def __init__(self, title: str, message: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        heading = QLabel(title)
        heading.setStyleSheet("font-size: 22px; font-weight: 600;")
        detail = QLabel(message)
        detail.setWordWrap(True)
        detail.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        layout.addWidget(heading)
        layout.addWidget(detail)
        layout.addStretch()

