from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPalette, QPolygon
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QFileDialog, QHBoxLayout, QHeaderView,
    QLabel, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QStyledItemDelegate, QStyle, QStyleOptionViewItem,
)

from app.services.product_consumers_export import export_excel, export_pdf, format_value


NAVY = "#173653"


class _SelectionDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        brush = index.data(Qt.ItemDataRole.ForegroundRole)
        option.palette.setColor(QPalette.ColorRole.HighlightedText, brush.color() if brush else QColor(NAVY))
        if option.state & QStyle.StateFlag.State_Selected:
            # The application stylesheet forces selected text to white. Paint the
            # selection background here, keeping each cell's normal text colour.
            option.state &= ~QStyle.StateFlag.State_Selected
            option.features &= ~QStyleOptionViewItem.ViewItemFeature.Alternate
            option.backgroundBrush = QBrush(QColor("#DBF3F2"))
            option.palette.setColor(QPalette.ColorRole.Highlight, QColor("#DBF3F2"))


class _SortableItem(QTableWidgetItem):
    def __init__(self, text, key, value):
        super().__init__(text)
        self.key = key
        self.value = value

    def __lt__(self, other):
        return self.key < other.key


class _ComparisonHeader(QHeaderView):
    """One real, sortable header with a second painted tier for the years."""

    def __init__(self, year, parent):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.year = year
        self.setSectionsClickable(True)
        self.setSortIndicatorShown(True)
        self.setMinimumHeight(66)

    def sizeHint(self):
        return QSize(super().sizeHint().width(), 66)

    def paintSection(self, painter, rect, index):
        painter.save()
        painter.fillRect(rect, QColor(NAVY))
        painter.setPen(QColor("#496078"))
        painter.drawRect(rect.adjusted(0, 0, -1, -1))
        lower = rect if index < 2 else QRect(rect.x(), rect.y() + 32, rect.width(), rect.height() - 32)
        painter.setPen(Qt.GlobalColor.white)
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        label = str(self.model().headerData(index, self.orientation()))
        painter.drawText(lower.adjusted(6, 0, -18, 0), Qt.AlignmentFlag.AlignCenter, label)
        if self.sortIndicatorSection() == index:
            x, y = lower.right() - 9, lower.center().y()
            direction = 1 if self.sortIndicatorOrder() == Qt.SortOrder.AscendingOrder else -1
            painter.setBrush(Qt.GlobalColor.white)
            painter.drawPolygon(QPolygon([QPoint(x - 3, y + 2 * direction), QPoint(x + 3, y + 2 * direction), QPoint(x, y - 2 * direction)]))
        painter.restore()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self.viewport())
        painter.setClipRect(event.rect())
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        for start, title in ((2, str(self.year - 1)), (4, str(self.year)), (6, "Diferencias")):
            rect = QRect(self.sectionViewportPosition(start), 0, self.sectionSize(start) + self.sectionSize(start + 1), 32)
            painter.fillRect(rect, QColor(NAVY))
            painter.setPen(QColor("#496078"))
            painter.drawRect(rect.adjusted(0, 0, -1, -1))
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, title)
        painter.end()


class ProductConsumersDialog(QDialog):
    def __init__(self, year, code, name, rows, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Clientes que compran el producto")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.resize(1320, 740)
        self.setMinimumSize(1000, 520)
        self.subtitle = f"Años {year - 1} y {year} | {code}" + (f" - {name}" if name else "")
        self.export_headers = ["Código", "Cliente", f"{year - 1} · Kilos", f"{year - 1} · €", f"{year} · Kilos", f"{year} · €", "Δ Kilos", "Δ €"]
        self.setStyleSheet("""
            QDialog { background: #F4F7FA; }
            QWidget#hero { background: #173653; border-bottom: 4px solid #1DB8B1; }
            QLabel { background: transparent; }
            QTableWidget { background: white; alternate-background-color: #F3F6F9;
                color: #173653; border: none; font-size: 13px;
                selection-background-color: #DBF3F2; selection-color: #173653; }
            QTableWidget::item { padding: 6px; border: none; }
            QTableWidget::item:selected { background: #DBF3F2; }
            QPushButton { padding: 9px 18px; border-radius: 5px; font-weight: 600;
                background: #E8EEF4; color: #173653; border: 1px solid #BDCAD7; }
            QPushButton:disabled { background: #8493A2; color: #D8E0E8; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 14)
        layout.setSpacing(0)
        hero = QWidget()
        hero.setObjectName("hero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(20, 18, 20, 18)
        titles = QVBoxLayout()
        title = QLabel(self.windowTitle())
        title.setStyleSheet("color: white; font-size: 24px; font-weight: 700; border: none;")
        subtitle = QLabel(self.subtitle)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #BDD5E8; font-size: 13px; border: none;")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        hero_layout.addLayout(titles, 1)
        icons = Path(__file__).resolve().parents[3] / "assets" / "icons"
        self.export_buttons = []
        for label, suffix, icon, color in (("Pdf", "pdf", "file-text.svg", "#D82E40"), ("Excel", "xlsx", "sheet.svg", "#087C45")):
            button = QPushButton(label)
            pixmap = QIcon(str(icons / icon)).pixmap(22, 22)
            painter = QPainter(pixmap)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(pixmap.rect(), Qt.GlobalColor.white)
            painter.end()
            button.setIcon(QIcon(pixmap))
            button.setIconSize(QSize(22, 22))
            button.setStyleSheet(f"QPushButton {{ background: {color}; color: white; border: none; }} QPushButton:hover {{ border: 2px solid #B5E5E2; }}")
            button.setEnabled(bool(rows))
            button.clicked.connect(lambda checked=False, kind=suffix: self._export(kind))
            hero_layout.addWidget(button)
            self.export_buttons.append(button)
        layout.addWidget(hero)
        body = QVBoxLayout()
        body.setContentsMargins(16, 12, 16, 0)
        body.setSpacing(0)
        layout.addLayout(body, 1)
        self.table = QTableWidget(len(rows), 8)
        self.table.setHorizontalHeader(_ComparisonHeader(year, self.table))
        self.table.setHorizontalHeaderLabels(["Código", "Cliente", "Kilos", "€", "Kilos", "€", "Δ Kilos", "Δ €"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setItemDelegate(_SelectionDelegate(self.table))
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setStretchLastSection(False)
        for col, width in enumerate((64, 350, 125, 145, 125, 145, 125, 145)):
            self.table.setColumnWidth(col, width)
        self.totals = [0.0] * 6
        for index, row in enumerate(rows):
            values = [float(getattr(row, attr, 0) or 0) for attr in ("kg_prev", "euros_prev", "kg_curr", "euros_curr")]
            values.extend([float(getattr(row, "delta_kg", values[2] - values[0]) or 0), float(getattr(row, "delta_euros", values[3] - values[1]) or 0)])
            code_text = str(getattr(row, "cliente_codigo", "") or "")
            name_text = str(getattr(row, "cliente_nombre", "") or "")
            code_key = (0, int(code_text)) if code_text.isdecimal() else (1, code_text.casefold())
            items = [_SortableItem(code_text, code_key, code_text), _SortableItem(name_text, name_text.casefold(), name_text)]
            for col, value in enumerate(values, 2):
                self.totals[col - 2] += value
                item = _SortableItem(format_value(value, col), value, value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if col >= 6 and value:
                    item.setForeground(QColor("#07804B" if value > 0 else "#C32939"))
                items.append(item)
            for col, item in enumerate(items):
                item.setToolTip(item.text())
                self.table.setItem(index, col, item)
        self.table.setSortingEnabled(True)
        self.table.sortItems(4, Qt.SortOrder.DescendingOrder)
        body.addWidget(self.table, 1)
        if not rows:
            empty = QLabel("No hay clientes con ventas registradas para este producto en el año seleccionado.")
            empty.setWordWrap(True)
            body.addWidget(empty)
        self.footer = QTableWidget(1, 8)
        self.footer.setStyleSheet("QTableWidget { background: #173653; color: white; font-weight: 700; border: none; } QTableWidget::item { padding: 6px; }")
        self.footer.horizontalHeader().hide()
        self.footer.verticalHeader().hide()
        self.footer.setShowGrid(False)
        self.footer.setWordWrap(False)
        self.footer.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.footer.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.footer.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.footer.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.footer.setSpan(0, 0, 1, 2)
        self.footer.setItem(0, 0, QTableWidgetItem("Totales generales"))
        for col, value in enumerate(self.totals, 2):
            item = QTableWidgetItem(format_value(value, col))
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if col >= 6 and value:
                item.setForeground(QColor("#76E2B6" if value > 0 else "#FF8585"))
            self.footer.setItem(0, col, item)
        self.footer.setRowHeight(0, 44)
        self.footer.setFixedHeight(44)
        footer_row = QHBoxLayout()
        footer_row.setSpacing(0)
        footer_row.addWidget(self.footer)
        self.scrollbar_space = QWidget()
        self.scrollbar_space.setStyleSheet("background: #173653;")
        footer_row.addWidget(self.scrollbar_space)
        body.addLayout(footer_row)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.footer.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.horizontalScrollBar().valueChanged.connect(self.footer.horizontalScrollBar().setValue)
        header.sectionResized.connect(self._sync_footer)
        self.table.viewport().installEventFilter(self)
        self._sync_footer()
        close_row = QHBoxLayout()
        close_row.setContentsMargins(16, 14, 16, 0)
        close_row.addStretch()
        close = QPushButton("Cerrar")
        close.clicked.connect(self.accept)
        close_row.addWidget(close)
        layout.addLayout(close_row)

    def eventFilter(self, watched, event):
        if watched is self.table.viewport() and event.type() == QEvent.Type.Resize:
            QTimer.singleShot(0, self._sync_footer)
        return super().eventFilter(watched, event)

    def _sync_footer(self, *args):
        for col in range(8):
            self.footer.setColumnWidth(col, self.table.columnWidth(col))
        self.scrollbar_space.setFixedWidth(max(0, self.table.width() - self.table.viewport().width()))
        self.footer.horizontalScrollBar().setValue(self.table.horizontalScrollBar().value())

    def ordered_rows(self):
        return [[self.table.item(row, col).value for col in range(8)] for row in range(self.table.rowCount())]

    def _export(self, suffix):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar clientes del producto", f"Clientes_producto.{suffix}", "PDF (*.pdf)" if suffix == "pdf" else "Excel (*.xlsx)")
        if not path:
            return
        if not path.lower().endswith(f".{suffix}"):
            path += f".{suffix}"
        try:
            writer = export_pdf if suffix == "pdf" else export_excel
            writer(path, self.subtitle, self.export_headers, self.ordered_rows(), self.totals)
        except Exception as exc:
            QMessageBox.warning(self, "Error de exportación", f"No se pudo guardar el archivo.\n{exc}")
            return
        QMessageBox.information(self, "Exportación completada", f"Archivo guardado en:\n{path}")
