from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QHeaderView,
)

from app.services.order_receipt_assignment_service import ReceiptAssignmentService, ReceiptReview


class ReceiptAssignmentDialog(QDialog):
    def __init__(self, service: ReceiptAssignmentService, parent=None, *, almacen_id="", pedido_id=""):
        super().__init__(parent)
        self.service = service
        self.almacen_id = almacen_id
        self.pedido_id = pedido_id
        self.reviews: list[ReceiptReview] = []
        self.setWindowTitle("Asignar recepciones pendientes")
        self.resize(820, 610)
        layout = QVBoxLayout(self)
        self.show_confirmed = QCheckBox("Mostrar también asignaciones confirmadas")
        self.show_confirmed.toggled.connect(self._load)
        layout.addWidget(self.show_confirmed)
        self.selector = QComboBox()
        self.selector.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.selector.currentIndexChanged.connect(self._render)
        layout.addWidget(self.selector)
        self.info = QLabel()
        self.info.setWordWrap(True)
        layout.addWidget(self.info)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Pedido", "Fecha", "Pendiente disponible", "Unidades a asignar"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)
        row = QHBoxLayout()
        row.addWidget(QLabel("Unidades recibidas como excedente"))
        self.excess = QDoubleSpinBox()
        self.excess.setDecimals(4)
        self.excess.setRange(0, 1e9)
        self.excess.valueChanged.connect(self._update_total)
        row.addWidget(self.excess)
        layout.addLayout(row)
        self.total = QLabel()
        layout.addWidget(self.total)
        self.history = QTextEdit()
        self.history.setReadOnly(True)
        self.history.setMaximumHeight(95)
        self.history.setPlaceholderText("Sin cambios anteriores registrados.")
        layout.addWidget(self.history)
        actions = QHBoxLayout()
        self.later = QPushButton("Resolver después")
        self.later.clicked.connect(self.reject)
        actions.addWidget(self.later)
        self.confirm = QPushButton("Confirmar asignación")
        self.confirm.clicked.connect(self._save)
        actions.addWidget(self.confirm)
        layout.addLayout(actions)
        self._load()

    def _current(self):
        index = self.selector.currentIndex()
        return self.reviews[index] if 0 <= index < len(self.reviews) else None

    def _load(self):
        self.reviews = self.service.list_reviews(self.almacen_id, self.pedido_id,
                                                pending_only=not self.show_confirmed.isChecked())
        self.selector.blockSignals(True)
        self.selector.clear()
        for review in self.reviews:
            state = "Sin asignar" if review.pendiente else "Confirmada"
            self.selector.addItem(f"{review.albaran} · {review.articulo} · {state}")
        self.selector.blockSignals(False)
        self._render()

    def _render(self):
        review = self._current()
        self.table.setRowCount(0)
        self.excess.blockSignals(True)
        self.excess.setValue(review.excess if review else 0)
        self.excess.blockSignals(False)
        self.confirm.setEnabled(review is not None)
        self.excess.setEnabled(review is not None)
        if review is None:
            self.info.setText("No hay recepciones pendientes de asignar en esta selección.")
            self.history.clear()
            self.total.clear()
            return
        self.info.setText(f"{review.articulo}: {review.cantidad:g} unidades recibidas.\n"
                          "Indica su destino. Resolver después conserva el albarán sin descontar las unidades pendientes de asignar.")
        self.table.setRowCount(len(review.candidates))
        for index, candidate in enumerate(review.candidates):
            for col, text in enumerate((candidate.numero, candidate.fecha.strftime("%d/%m/%Y"), f"{candidate.pendiente:g}")):
                cell = QTableWidgetItem(text)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(index, col, cell)
            amount = QDoubleSpinBox()
            amount.setDecimals(4)
            amount.setRange(0, min(candidate.pendiente, review.cantidad))
            amount.setValue(review.allocations.get(candidate.pedido_id, 0))
            amount.valueChanged.connect(self._update_total)
            self.table.setCellWidget(index, 3, amount)
        self.history.setPlainText("\n".join(review.history))
        self._update_total()

    def _allocations(self):
        review = self._current()
        return {row.pedido_id: self.table.cellWidget(index, 3).value()
                for index, row in enumerate(review.candidates)} if review else {}

    def _update_total(self):
        review = self._current()
        if review is None:
            return
        total = sum(self._allocations().values()) + self.excess.value()
        self.total.setText(f"Repartidas y excedente: {total:g} / {review.cantidad:g} unidades")
        self.confirm.setEnabled(abs(total - review.cantidad) <= 1e-6)

    def _save(self):
        review = self._current()
        if review is None:
            return
        try:
            self.service.confirm(review, self._allocations(), self.excess.value())
        except ValueError as exc:
            QMessageBox.warning(self, "Asignación pendiente", str(exc))
            self._load()
            return
        except Exception as exc:
            QMessageBox.warning(self, "Asignación pendiente", f"No se pudo guardar la asignación: {exc}")
            return
        self._load()
