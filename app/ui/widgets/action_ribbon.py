from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QWidget


BASE_DIR = Path(__file__).resolve().parents[3]

STANDARD_RIBBON_BUTTON_WIDTH = 154
STANDARD_RIBBON_BUTTON_HEIGHT = 26
STANDARD_RIBBON_ICON_SIZE = QSize(16, 16)
STANDARD_RIBBON_MARGINS = (8, 6, 8, 6)
STANDARD_RIBBON_SPACING = 6

_ROLE_STYLES = {
    "primary": ("#DBEAFE", "#1D4ED8", "#93C5FD", "#BFDBFE", "#60A5FA"),
    "success": ("#DCFCE7", "#166534", "#86EFAC", "#BBF7D0", "#4ADE80"),
    "warning": ("#FEF3C7", "#92400E", "#FCD34D", "#FDE68A", "#FBBF24"),
    "danger": ("#FEE2E2", "#B91C1C", "#FCA5A5", "#FECACA", "#F87171"),
    "secondary": ("#E2E8F0", "#334155", "#CBD5E1", "#CBD5E1", "#94A3B8"),
    "info": ("#F3E8FF", "#6B21A8", "#D8B4FE", "#E9D5FF", "#C084FC"),
}


def create_standard_top_ribbon(parent: QWidget | None = None) -> tuple[QFrame, QHBoxLayout]:
    ribbon = QFrame(parent)
    ribbon.setObjectName("topRibbon")
    ribbon.setProperty("pageType", "contacts")
    ribbon.setFrameShape(QFrame.Shape.StyledPanel)

    layout = QHBoxLayout(ribbon)
    layout.setContentsMargins(*STANDARD_RIBBON_MARGINS)
    layout.setSpacing(STANDARD_RIBBON_SPACING)
    return ribbon, layout


def create_standard_ribbon_button(
    text: str,
    *,
    role: str,
    icon_name: str,
    object_name: str | None = None,
    tooltip: str | None = None,
) -> QPushButton:
    button = QPushButton(text)
    if object_name:
        button.setObjectName(object_name)
    button.setProperty("btnRole", role)
    button.setIcon(QIcon(str(BASE_DIR / "assets" / "icons" / icon_name)))
    button.setIconSize(STANDARD_RIBBON_ICON_SIZE)
    button.setStyleSheet(_standard_button_style(role))
    button.setFixedHeight(STANDARD_RIBBON_BUTTON_HEIGHT)
    button.setFixedWidth(STANDARD_RIBBON_BUTTON_WIDTH)
    if tooltip:
        button.setToolTip(tooltip)
    return button


def _standard_button_style(role: str) -> str:
    bg, fg, border, hover_bg, hover_border = _ROLE_STYLES.get(role, _ROLE_STYLES["secondary"])
    return f"""
        QPushButton {{
            min-height: 24px;
            max-height: 24px;
            padding: 0 10px;
            margin: 0;
            border-radius: 7px;
            font-weight: 600;
            background-color: {bg};
            color: {fg};
            border: 1px solid {border};
        }}
        QPushButton:hover {{
            background-color: {hover_bg};
            border-color: {hover_border};
        }}
        QPushButton:disabled {{
            background-color: #F1F5F9;
            color: #94A3B8;
            border-color: #CBD5E1;
        }}
    """
