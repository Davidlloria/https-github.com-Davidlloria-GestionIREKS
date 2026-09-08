from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QSpinBox, QHBoxLayout, QLabel, QSizePolicy,
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
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table, 1)
        row = QHBoxLayout()
        row.addWidget(QLabel("Unidades recibidas como excedente"))
        self.excess = self._quantity_spin()
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

    def _quantity_spin(self):
        icons = Path(__file__).resolve().parents[3] / "assets" / "icons"
        amount = QSpinBox()
        amount.setSingleStep(1)
        amount.setAlignment(Qt.AlignmentFlag.AlignRight)
        amount.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # Override the global input padding/min-height, including the embedded line edit.
        amount.setStyleSheet("""
            QSpinBox { min-height: 0; padding: 3px 28px 3px 6px; border-radius: 4px; }
            QSpinBox QLineEdit { min-height: 0; padding: 0; border: none; background: transparent; }
            QSpinBox::up-button { subcontrol-origin: border; subcontrol-position: top right;
                width: 24px; border-left: 1px solid #C8D2DF; border-bottom: 1px solid #C8D2DF; }
            QSpinBox::down-button { subcontrol-origin: border; subcontrol-position: bottom right;
                width: 24px; border-left: 1px solid #C8D2DF; }
            QSpinBox::up-arrow { image: url("__UP__"); width: 10px; height: 10px; }
            QSpinBox::down-arrow { image: url("__DOWN__"); width: 10px; height: 10px; }
            QSpinBox::up-button:disabled, QSpinBox::down-button:disabled { background: #F4F6F9; }
        """.replace("__UP__", (icons / "arrow-up.svg").as_posix())
           .replace("__DOWN__", (icons / "arrow-down.svg").as_posix()))
        amount.ensurePolished()
        amount.setMinimumHeight(max(30, amount.fontMetrics().height() + 10))
        return amount

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
        self.excess.setRange(0, int(review.cantidad) if review else 0)
        self.excess.setValue(int(review.excess) if review else 0)
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
            amount = self._quantity_spin()
            amount.setRange(0, int(min(candidate.pendiente, review.cantidad)))
            amount.setValue(int(review.allocations.get(candidate.pedido_id, 0)))
            amount.valueChanged.connect(self._update_total)
            self.table.setCellWidget(index, 3, amount)
        self.table.resizeRowsToContents()
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
