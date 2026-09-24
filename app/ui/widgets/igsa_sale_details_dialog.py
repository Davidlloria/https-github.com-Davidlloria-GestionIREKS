from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QAbstractItemView, QDialog, QDialogButtonBox, QHeaderView, QLabel, QPlainTextEdit, QTableWidget, QTableWidgetItem, QVBoxLayout


class IgsaSaleDetailsDialog(QDialog):
    def __init__(self, code, name, rows, parent=None, *, incidents_only=False):
        super().__init__(parent)
        self.setWindowTitle("Explicación de incidencias" if incidents_only else "Detalle de ventas IGSA")
        self.resize(1160, 620)
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
                        item.setForeground(QColor("#854D0E"))
                    if isinstance(value, (int, float)) and value < 0:
                        item.setForeground(QColor("#B42318"))
                    item.setToolTip("\n".join(row["incidencias"]) or text)
                    table.setItem(i, j, item)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
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
