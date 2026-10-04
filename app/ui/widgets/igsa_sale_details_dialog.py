from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QAbstractItemView, QDialog, QDialogButtonBox, QHeaderView, QLabel, QPlainTextEdit, QTableWidget, QTableWidgetItem, QVBoxLayout
from PySide6.QtWidgets import QStyledItemDelegate, QStyle, QStyleOptionViewItem, QPushButton, QComboBox, QFormLayout, QDoubleSpinBox, QLineEdit, QCheckBox, QMessageBox


INCIDENT_ROLE = Qt.ItemDataRole.UserRole + 173
COMPARISON_ROLE = Qt.ItemDataRole.UserRole + 174


class IgsaIncidentDelegate(QStyledItemDelegate):
    """Keep incident text readable even when the global theme selects a row."""

    def paint(self, painter, option, index):
        if not index.data(INCIDENT_ROLE) and not index.data(COMPARISON_ROLE):
            super().paint(painter, option, index)
            return
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        painter.save()
        painter.setClipRect(opt.rect)
        painter.fillRect(opt.rect, QColor(("#FDBA74" if selected else "#FFEDD5") if index.data(COMPARISON_ROLE) else ("#FDE68A" if selected else "#FEF3C7")))
        brush = index.data(Qt.ItemDataRole.ForegroundRole)
        painter.setPen(brush.color() if brush else QColor("#854D0E"))
        painter.setFont(opt.font)
        rect = opt.rect.adjusted(8, 0, -8, 0)
        text = opt.fontMetrics.elidedText(opt.text, Qt.TextElideMode.ElideRight, max(0, rect.width()))
        painter.drawText(rect, opt.displayAlignment | Qt.AlignmentFlag.AlignVCenter, text)
        painter.restore()


class IgsaSaleDetailsDialog(QDialog):
    def __init__(self, code, name, rows, parent=None, *, incidents_only=False, service=None, comparisons=None):
        super().__init__(parent)
        self.setWindowTitle("Explicación de incidencias" if incidents_only else "Detalle de ventas IGSA")
        self.resize(1160, 620)
        self.setMinimumWidth(1050)
        layout = QVBoxLayout(self)
        title = QLabel(f"{code} · {name}")
        title.setTextFormat(Qt.TextFormat.PlainText)
        title.setStyleSheet("font-size:18px; font-weight:600; color:#193750; padding:8px;")
        layout.addWidget(title)
        subtitle = QLabel("Registros de los dos años comparados, para el mes o acumulado seleccionado. Selecciona una línea para corregirla o registrar su revisión.")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        if incidents_only:
            explanation = QPlainTextEdit()
            explanation.setReadOnly(True)
            messages = []
            for row in rows:
                for issue in row["incidencias"]:
                    messages.append(f"{row['periodo']} · {row['tipo']} · Lote {row['lote'] or 'no informado'}\n{issue}")
                for review in row.get("historial", []):
                    messages.append(f"{row['periodo']} · Revisión {review['fecha']}: {review['motivo']}")
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
                    item.setToolTip("")
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
                    reviews = [f"Revisión {r['fecha']}: {r['motivo']}" for r in row.get("historial", [])]
                    notes.setPlainText("\n".join(row["incidencias"] + [row["observaciones"]] + reviews) or "Sin observaciones.")
            table.itemSelectionChanged.connect(show_notes)
            layout.addWidget(notes)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Cerrar")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        if comparisons:
            comparison_text = QPlainTextEdit()
            comparison_text.setReadOnly(True)
            comparison_text.setMaximumHeight(130)
            comparison_text.setPlainText("Comparación mensual · IGSA − IREKS · tolerancia 0,001 kg\n" + "\n".join(
                f"{r['periodo']} · {r['dato']} · IGSA: {r['igsa']} · IREKS: {r['ireks']} · Diferencia: {r['diferencia']} · {r['estado']}"
                for r in comparisons))
            layout.insertWidget(layout.count() - 1, comparison_text)
        if service and rows:
            selector = QComboBox()
            for row in rows:
                selector.addItem(f"{row['periodo']} · {row['tipo']} · Lote {row['lote'] or '—'}", row)
            layout.insertWidget(layout.count() - 1, selector)
            if hasattr(self, "table"):
                self.table.itemSelectionChanged.connect(lambda: selector.setCurrentIndex(self.table.currentRow()))
            edit = QPushButton("Corregir línea / Registrar revisión")
            layout.insertWidget(layout.count() - 1, edit)
            def correct():
                row = selector.currentData()
                if not row or not row.get("raw_id"):
                    return
                editor = IgsaCorrectionDialog(row, service, self)
                if editor.exec() == QDialog.DialogCode.Accepted:
                    self.accept()
            edit.clicked.connect(correct)
            history = QPushButton("Historial de la línea")
            layout.insertWidget(layout.count() - 1, history)
            def show_history():
                row = selector.currentData()
                if not row:
                    return
                show_correction_history(service, self, row.get("raw_id", ""))
            history.clicked.connect(show_history)


class IgsaCorrectionDialog(QDialog):
    def __init__(self, row, service, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Corrección manual de venta IGSA")
        self.resize(620, 500)
        layout = QFormLayout(self)
        note = QLabel("Corrige esta venta. No modifica el Excel original ni los movimientos de almacén. Una reimportación puede sustituir la corrección; el historial se conserva.")
        note.setWordWrap(True)
        layout.addRow(note)
        self.change_values = QCheckBox("Modificar datos de la venta")
        layout.addRow(self.change_values)
        self.product = QComboBox()
        for product in service.products():
            self.product.addItem(f"{product.articulo_referencia_corta or product.articulo_referencia} · {product.articulo_descripcion}", product.articulo_id)
        self.product.setCurrentIndex(self.product.findData(row.get("articulo_id")))
        layout.addRow("Producto", self.product)
        self.kind = QComboBox()
        for label, value in (("Venta", "venta"), ("Muestra", "muestra"), ("Promoción", "promocion"), ("S/C", "s/c")):
            self.kind.addItem(label, value)
        self.kind.setCurrentIndex(max(0, self.kind.findText(row["tipo"])))
        layout.addRow("Tipo", self.kind)
        self.inputs = {}
        for key, label in (("cantidad", "Envases"), ("peso", "Kg/envase"), ("euros", "Importe €")):
            box = QDoubleSpinBox()
            box.setDecimals(6)
            box.setRange(-1e9 if key != "peso" else 0, 1e9)
            box.setValue(float(row.get(key) or 0))
            layout.addRow(label, box)
            self.inputs[key] = box
        self.preview = QLabel()
        layout.addRow("Kilos resultantes", self.preview)
        def preview():
            self.preview.setText(f"{self.inputs['cantidad'].value() * self.inputs['peso'].value():,.6f}")
        for box in self.inputs.values():
            box.valueChanged.connect(preview)
        preview()
        for widget in [self.product, self.kind, *self.inputs.values()]:
            widget.setEnabled(False)
            self.change_values.toggled.connect(widget.setEnabled)
        self.resolved = QCheckBox("Incidencia del documento revisada y resuelta")
        self.resolved.setChecked(bool(row.get("resuelta")))
        layout.addRow(self.resolved)
        self.reason = QLineEdit()
        layout.addRow("Motivo / justificación", self.reason)
        self.error = QLabel()
        self.error.setWordWrap(True)
        layout.addRow(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Guardar corrección")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        layout.addRow(buttons)
        buttons.rejected.connect(self.reject)
        def save():
            try:
                values = None
                if self.change_values.isChecked():
                    values = {key: box.value() for key, box in self.inputs.items()}
                    values.update(articulo_id=self.product.currentData(), tipo=self.kind.currentData())
                service.correct(row["raw_id"], row["snapshot"], reason=self.reason.text(),
                                values=values, resolved=self.resolved.isChecked())
            except Exception as exc:
                self.error.setText(str(exc))
                return
            self.accept()
        buttons.accepted.connect(save)


def show_correction_history(service, parent=None, raw_id=None):
    import json
    dialog = QDialog(parent)
    dialog.setWindowTitle("Historial de correcciones IGSA")
    dialog.resize(850, 500)
    layout = QVBoxLayout(dialog)
    text = QPlainTextEdit()
    text.setReadOnly(True)
    messages = []
    for entry in service.history(raw_id):
        before, after = (json.loads(entry[key]) for key in ("anterior", "posterior"))
        lines = [f"{entry['fecha']} · {before['periodo']} · {before['articulo_codigo_origen']}",
                 f"Motivo: {entry['motivo']}"]
        for key, label in (("articulo_codigo_origen", "Producto"), ("venta_kilos", "Kg vendidos"),
                           ("venta_kilos_sc", "Kg sin cargo"), ("venta_euros", "Importe €")):
            lines.append(f"{label}: {before[key]} → {after[key]}")
        old_payload = json.loads(before.get("payload_json") or "{}")
        new_payload = json.loads(after.get("payload_json") or "{}")
        for key, label in (("cantidad", "Envases"), ("envase_peso", "Kg/envase"), ("tipo", "Tipo")):
            lines.append(f"{label}: {old_payload.get(key, '—')} → {new_payload.get(key, '—')}")
        lines.append("Incidencia del documento: " + ("Resuelta" if new_payload.get("incidencia_resuelta") else "Pendiente de revisión"))
        lines.append("Observación original: " + str(old_payload.get("observaciones", "")))
        messages.append("\n".join(lines))
    text.setPlainText("\n\n".join(messages) or "Sin correcciones registradas.")
    layout.addWidget(text)
    dialog.exec()
