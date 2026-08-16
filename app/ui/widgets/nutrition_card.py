from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget


@dataclass(frozen=True, slots=True)
class NutritionRowData:
    """Formatted nutrition data ready to be displayed."""

    key: str
    label: str
    value: str
    icon: str | None = None
    secondary: bool = False


_SVG_TEMPLATE: Final = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">
  <g stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{body}</g>
</svg>
"""

_SVG_PATHS: Final[dict[str, str]] = {
    "energy": '<path d="m13 2-7 11h6l-1 9 7-12h-6l1-8Z"/>',
    "fat": '<path d="M12 2.8S5.5 10 5.5 15a6.5 6.5 0 0 0 13 0C18.5 10 12 2.8 12 2.8Zm-2.7 13a3.6 3.6 0 0 0 3.6 3.6"/>',
    "carbohydrate": '<path d="M12 22V7m0 4c-3.4 0-5.5-1.7-5.5-4.5C9.9 6.5 12 8.2 12 11Zm0 5c3.4 0 5.5-1.7 5.5-4.5-3.4 0-5.5 1.7-5.5 4.5Zm0 1c-3.4 0-5.5-1.7-5.5-4.5 3.4 0 5.5 1.7 5.5 4.5Zm0-10c3 0 4.7-1.5 4.7-4-3 0-4.7 1.5-4.7 4Z"/>',
    "sugar": '<path d="m12 2 8.5 5v10L12 22l-8.5-5V7L12 2Zm0 0v10m8.5-5L12 12 3.5 7m0 10 8.5-5 8.5 5"/>',
    "fiber": '<path d="M12 21V9m0 6c-4 0-6.5-2-6.5-5.5C9.5 9.5 12 11.5 12 15Zm0 2c4 0 6.5-2 6.5-5.5-4 0-6.5 2-6.5 5.5ZM12 9c0-3 1.8-5.2 4.8-6-.1 3.2-1.9 5.2-4.8 6Zm0 0C9 9 7.2 7 7.2 4c3 .8 4.8 2.8 4.8 5Z"/>',
    "protein": '<path d="M7.2 6.2A3 3 0 1 1 11.4 2l.8.8 4-1 2 2-1 4 .8.8a3 3 0 1 1-4.2 4.2l-2.6-2.6-4 1-2-2 1-4 1 1Z"/>',
    "salt": '<path d="M8 8.5h8l1.8 12H6.2L8 8.5Zm1-4.8h6L16 8H8l1-4.3ZM10.5 6h.01M13.5 6h.01M9.5 12h.01m2.5 0h.01m2.5 0h.01"/>',
    "generic": '<path d="M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-13v4l2.5 2.5"/>',
}

_ICON_ALIASES: Final = {
    "energia": "energy",
    "energy": "energy",
    "grasas": "fat",
    "fat": "fat",
    "hidratos": "carbohydrate",
    "carbohydrate": "carbohydrate",
    "azucares": "sugar",
    "sugar": "sugar",
    "fibra": "fiber",
    "fiber": "fiber",
    "proteinas": "protein",
    "protein": "protein",
    "sal": "salt",
}


class SvgIcon(QWidget):
    def __init__(self, name: str, *, color: str, size: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        icon_name = _ICON_ALIASES.get(_normalise_key(name), name)
        body = _SVG_PATHS.get(icon_name, _SVG_PATHS["generic"])
        self._renderer = QSvgRenderer(QByteArray(_SVG_TEMPLATE.format(color=color, body=body).encode("utf-8")), self)
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._renderer.render(painter, self.rect())


class NutritionCard(QFrame):
    """Read-only card for the nutrition values already calculated by the recipe view."""

    def __init__(
        self,
        rows: list[NutritionRowData] | tuple[NutritionRowData, ...] = (),
        *,
        title: str = "Valores nutricionales",
        subtitle: str = "Información media",
        serving_label: str = "Por 100 g",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._rows = list(rows)
        self.setObjectName("nutritionCard")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.setStyleSheet(_CARD_STYLESHEET)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header(title, subtitle, serving_label))
        self._content = QWidget(self)
        self._content.setObjectName("nutritionContent")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)
        root.addWidget(self._content)
        self.set_rows(rows)

    def set_rows(self, rows: list[NutritionRowData] | tuple[NutritionRowData, ...]) -> None:
        self._rows = list(rows)
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not self._rows:
            empty = QLabel("No hay información nutricional disponible.", self._content)
            empty.setObjectName("nutritionEmpty")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._content_layout.addWidget(empty)
            return
        self._content_layout.addWidget(self._build_columns_header())
        for index, row in enumerate(self._rows):
            self._content_layout.addWidget(self._build_row(row, is_last=index == len(self._rows) - 1))

    def _build_header(self, title: str, subtitle: str, serving_label: str) -> QWidget:
        header = QWidget(self)
        header.setObjectName("nutritionHeader")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        icon_box = QFrame(header)
        icon_box.setObjectName("nutritionHeaderIcon")
        icon_box.setFixedSize(34, 34)
        icon_layout = QHBoxLayout(icon_box)
        icon_layout.setContentsMargins(6, 6, 6, 6)
        icon_layout.addWidget(SvgIcon("energy", color="#39735B", size=20, parent=icon_box))
        layout.addWidget(icon_box)
        heading = QWidget(header)
        heading_layout = QVBoxLayout(heading)
        heading_layout.setContentsMargins(0, 0, 0, 0)
        heading_layout.setSpacing(0)
        title_label = QLabel(title, heading)
        title_label.setObjectName("nutritionTitle")
        subtitle_label = QLabel(subtitle, heading)
        subtitle_label.setObjectName("nutritionSubtitle")
        heading_layout.addWidget(title_label)
        heading_layout.addWidget(subtitle_label)
        layout.addWidget(heading, 1)
        serving = QLabel(serving_label, header)
        serving.setObjectName("nutritionServing")
        serving.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(serving)
        return header

    def _build_columns_header(self) -> QWidget:
        header = QWidget(self._content)
        header.setObjectName("nutritionColumns")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(12, 6, 12, 6)
        nutrient = QLabel("NUTRIENTE", header)
        nutrient.setObjectName("nutritionColumnLabel")
        amount = QLabel("CANTIDAD", header)
        amount.setObjectName("nutritionColumnLabel")
        amount.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        amount.setFixedWidth(76)
        layout.addWidget(nutrient, 1)
        layout.addWidget(amount)
        return header

    def _build_row(self, row: NutritionRowData, *, is_last: bool) -> QWidget:
        container = QFrame(self._content)
        container.setObjectName("nutritionRowLast" if is_last else "nutritionRow")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(18 if row.secondary else 12, 7, 12, 7)
        layout.setSpacing(8)
        icon_box = QFrame(container)
        icon_box.setObjectName("nutritionRowIconSecondary" if row.secondary else "nutritionRowIcon")
        icon_box.setFixedSize(24 if row.secondary else 28, 24 if row.secondary else 28)
        icon_layout = QHBoxLayout(icon_box)
        icon_layout.setContentsMargins(5, 5, 5, 5)
        icon_layout.addWidget(
            SvgIcon(
                row.icon or row.key,
                color="#6D7D76" if row.secondary else "#39735B",
                size=14 if row.secondary else 16,
                parent=icon_box,
            )
        )
        layout.addWidget(icon_box)
        label = QLabel(row.label, container)
        label.setObjectName("nutritionSecondaryLabel" if row.secondary else "nutritionRowLabel")
        label.setWordWrap(True)
        layout.addWidget(label, 1)
        value = QLabel(row.value, container)
        value.setObjectName("nutritionValue")
        value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        value.setWordWrap(True)
        value.setFixedWidth(76)
        layout.addWidget(value)
        return container


def _normalise_key(value: str) -> str:
    return value.strip().lower().translate(str.maketrans("áéíóúüñ", "aeiouun"))


_CARD_STYLESHEET: Final = """
QFrame#nutritionCard { background: #FFFFFF; border: none; border-radius: 14px; }
QWidget#nutritionHeader { background: #DCEFE4; border-top-left-radius: 14px; border-top-right-radius: 14px; border-bottom: 1px solid #CDE3D6; }
QFrame#nutritionHeaderIcon { background: #FFFFFF; border: 1px solid #D9E9E1; border-radius: 10px; }
QLabel#nutritionTitle { color: #20312B; font-size: 14px; font-weight: 700; }
QLabel#nutritionSubtitle, QLabel#nutritionSecondaryLabel { color: #6D7D76; font-size: 10px; }
QLabel#nutritionServing { color: #39735B; background: #FFFFFF; border: 1px solid #D9E9E1; border-radius: 9px; padding: 4px 7px; font-size: 10px; font-weight: 700; }
QWidget#nutritionColumns { background: #FBFDFC; border-bottom: 1px solid #E4ECE8; }
QLabel#nutritionColumnLabel { color: #718079; font-size: 9px; font-weight: 700; }
QFrame#nutritionRow { background: #FFFFFF; border-bottom: 1px solid #E7EEEA; }
QFrame#nutritionRowLast { background: #FFFFFF; border-bottom: none; border-bottom-left-radius: 14px; border-bottom-right-radius: 14px; }
QFrame#nutritionRow:hover, QFrame#nutritionRowLast:hover { background: #F8FBF9; }
QFrame#nutritionRowIcon, QFrame#nutritionRowIconSecondary { background: #EAF4EF; border: 1px solid #DFECE5; border-radius: 8px; }
QFrame#nutritionRowIconSecondary { background: #F3F6F4; border-color: #E8EEEB; border-radius: 7px; }
QLabel#nutritionRowLabel { color: #293A33; font-size: 11px; font-weight: 600; }
QLabel#nutritionValue { color: #20312B; font-size: 11px; font-weight: 700; }
QLabel#nutritionEmpty { color: #6D7D76; padding: 22px 12px; font-size: 10px; }
"""
