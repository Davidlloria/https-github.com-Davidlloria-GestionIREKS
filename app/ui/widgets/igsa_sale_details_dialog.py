from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QAbstractItemView, QDialog, QDialogButtonBox, QHeaderView, QLabel, QPlainTextEdit, QTableWidget, QTableWidgetItem, QVBoxLayout
from PySide6.QtWidgets import QStyledItemDelegate, QStyle, QStyleOptionViewItem


INCIDENT_ROLE = Qt.ItemDataRole.UserRole + 173


class IgsaIncidentDelegate(QStyledItemDelegate):
    """Keep incident text readable even when the global theme selects a row."""

    def paint(self, painter, option, index):
        if not index.data(INCIDENT_ROLE):
            super().paint(painter, option, index)
            return
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        painter.save()
        painter.setClipRect(opt.rect)
        painter.fillRect(opt.rect, QColor("#FDE68A" if selected else "#FEF3C7"))
        brush = index.data(Qt.ItemDataRole.ForegroundRole)
        painter.setPen(brush.color() if brush else QColor("#854D0E"))
        painter.setFont(opt.font)
        rect = opt.rect.adjusted(8, 0, -8, 0)
        text = opt.fontMetrics.elidedText(opt.text, Qt.TextElideMode.ElideRight, max(0, rect.width()))
        painter.drawText(rect, opt.displayAlignment | Qt.AlignmentFlag.AlignVCenter, text)
        painter.restore()


class IgsaSaleDetailsDialog(QDialog):
    def __init__(self, code, name, rows, parent=None, *, incidents_only=False):
        super().__init__(parent)
        self.setWindowTitle("Explicación de incidencias" if incidents_only else "Detalle de ventas IGSA")
        self.resize(1160, 620)
        self.setMinimumWidth(1050)
        layout = QVBoxLayout(self)
        title = QLabel(f"{code} · {name}")
        title.setTextFormat(Qt.TextFormat.PlainText)
        title.setStyleSheet("font-size:18px; font-weight:600; color:#193750; padding:8px;")
        layout.addWidget(title)
        subtitle = QLabel("Registros de los dos años comparados, para el mes o acumulado seleccionado. Los datos no se pueden editar aquí.")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        if incidents_only:
            explanation = QPlainTextEdit()
            explanation.setReadOnly(True)
            messages = []
            for row in rows:
                for issue in row["incidencias"]:
                    messages.append(f"{row['periodo']} · {row['tipo']} · Lote {row['lote'] or 'no informado'}\n{issue}")
            explanation.setPlainText("\n\n".join(messages) or "No hay incidencias detectadas en el período seleccionado.")
            explanation.setStyleSheet("color:#854D0E; background:#FFFBEB; padding:12px;")
            layout.addWidget(explanation)
        else:
            columns = [("Mes", "periodo"), ("Tipo", "tipo"), ("Envases", "cantidad"), ("Kg/envase", "peso"), ("Kilos", "kilos"), ("€/kg", "precio"), ("Importe €", "euros"), ("Lote", "lote"), ("Caducidad", "caducidad")]
            table = QTableWidget(len(rows), len(columns))
            self.table = table
            table.setItemDelegate(IgsaIncidentDelegate(table))
            table.setWordWrap(False)
            table.verticalHeader().setDefaultSectionSize(38)
            table.setHorizontalHeaderLabels([c[0] for c in columns])
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            table.verticalHeader().hide()
            table.setAlternatingRowColors(True)
            table.setStyleSheet("QTableWidget {alternate-background-color:#F1F5F9; color:#193750; selection-background-color:#CEE8ED; selection-color:#193750;} QHeaderView::section {background:#193750; color:white; padding:8px;}")
            for i, row in enumerate(rows):
                for j, (_, key) in enumerate(columns):
                    value = row[key]
                    text = "—" if value is None or value == "" else str(value)
                    if isinstance(value, (int, float)):
                        text = f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
                    item = QTableWidgetItem(text)
                    if key in {"cantidad", "peso", "kilos", "precio", "euros"}:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    if row["incidencias"]:
                        item.setData(INCIDENT_ROLE, True)
                        item.setForeground(QColor("#854D0E"))
                    if isinstance(value, (int, float)) and value < 0:
                        item.setForeground(QColor("#B42318"))
                    item.setToolTip("\n".join(row["incidencias"]) or text)
                    table.setItem(i, j, item)
            table.horizontalHeader().setMinimumSectionSize(100)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Interactive)
            table.setColumnWidth(7, 120)
            layout.addWidget(table)
            notes = QPlainTextEdit()
            notes.setReadOnly(True)
            notes.setMaximumHeight(110)
            notes.setPlaceholderText("Selecciona una línea para consultar sus observaciones e incidencias.")
            def show_notes():
                index = table.currentRow()
                if 0 <= index < len(rows):
                    row = rows[index]
                    notes.setPlainText("\n".join(row["incidencias"] + [row["observaciones"]]) or "Sin observaciones.")
            table.itemSelectionChanged.connect(show_notes)
            layout.addWidget(notes)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Cerrar")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
