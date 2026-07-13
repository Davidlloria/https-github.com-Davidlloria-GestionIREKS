from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.services.customer_query_service import CustomerQueryResult, CustomerQueryService

BASE_DIR = Path(__file__).resolve().parents[3]


class CustomerQueryNumericItem(QTableWidgetItem):
    def __init__(self, text: str, value: float) -> None:
        super().__init__(text)
        self.setData(Qt.ItemDataRole.UserRole, float(value or 0.0))

    def __lt__(self, other: QTableWidgetItem) -> bool:
        return float(self.data(Qt.ItemDataRole.UserRole) or 0.0) < float(
            other.data(Qt.ItemDataRole.UserRole) or 0.0
        )


class CustomerQueryWorker(QThread):
    result_ready = Signal(object)
    failed = Signal(str)

    def __init__(self, service: CustomerQueryService, prompt: str, parent=None) -> None:
        super().__init__(parent)
        self._service = service
        self._prompt = prompt

    def run(self) -> None:
        try:
            self.result_ready.emit(self._service.run(self._prompt))
        except Exception:  # noqa: BLE001
            self.failed.emit("No se pudo ejecutar la consulta.")


class CustomerQueriesDialog(QDialog):
    def __init__(
        self,
        service: CustomerQueryService | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("customerQueriesDialog")
        self.setWindowTitle("Consultas de clientes")
        self.setModal(True)
        self.resize(1040, 680)
        self.setMinimumSize(820, 540)
        self._service = service or CustomerQueryService()
        self._worker: CustomerQueryWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("Consultas de clientes")
        title.setObjectName("customerQueriesTitle")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #1E293B;")
        layout.addWidget(title)

        subtitle = QLabel(
            "Pregunta por clientes o por su evolución de compras. "
            "Las comparativas y rankings se calculan en kg."
        )
        subtitle.setObjectName("customerQueriesSubtitle")
        subtitle.setStyleSheet("color: #64748B;")
        layout.addWidget(subtitle)

        self.prompt = QPlainTextEdit()
        self.prompt.setObjectName("customerQueryPrompt")
        self.prompt.setFixedHeight(72)
        self.prompt.setPlaceholderText(
            "Ej.: dame los cinco clientes con mayores bajadas en las compras en el año actual"
        )
        layout.addWidget(self.prompt)

        examples = QHBoxLayout()
        examples.setSpacing(6)
        for text in (
            "Cinco clientes con mayores bajadas en compras este año",
            "Clientes de Tenerife",
            "Panaderías de Lanzarote",
        ):
            button = QPushButton(text)
            button.setObjectName("customerQueryExampleButton")
            button.setProperty("btnRole", "secondary")
            button.clicked.connect(lambda _checked=False, value=text: self.prompt.setPlainText(value))
            examples.addWidget(button)
        examples.addStretch(1)
        layout.addLayout(examples)

        action_row = QHBoxLayout()
        self.run_button = QPushButton("Consultar")
        self.run_button.setObjectName("customerQueryRunButton")
        self.run_button.setProperty("btnRole", "primary")
        self.run_button.setIcon(QIcon("assets/icons/brain.svg"))
        self.run_button.clicked.connect(self._run_query)
        self.run_button.setIcon(QIcon(str(BASE_DIR / 'assets' / 'icons' / 'brain.svg')))
        action_row.addWidget(self.run_button)
        action_row.addStretch(1)
        layout.addLayout(action_row)

        interpretation_panel = QFrame()
        interpretation_panel.setObjectName("customerQueryInterpretationPanel")
        interpretation_panel.setStyleSheet(
            "QFrame#customerQueryInterpretationPanel {"
            "background: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 7px; }"
        )
        interpretation_layout = QVBoxLayout(interpretation_panel)
        interpretation_layout.setContentsMargins(10, 7, 10, 7)
        self.interpretation_label = QLabel("La interpretación de la consulta aparecerá aquí.")
        self.interpretation_label.setObjectName("customerQueryInterpretation")
        self.interpretation_label.setWordWrap(True)
        self.interpretation_label.setStyleSheet("color: #1E40AF;")
        interpretation_layout.addWidget(self.interpretation_label)
        layout.addWidget(interpretation_panel)

        self.results_table = QTableWidget(0, 0)
        self.results_table.setObjectName("customerQueryResultsTable")
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSortingEnabled(True)
        self.results_table.verticalHeader().setVisible(False)
        layout.addWidget(self.results_table, 1)

        footer = QHBoxLayout()
        self.status_label = QLabel("Sin consulta ejecutada.")
        self.status_label.setObjectName("customerQueryStatusLabel")
        self.status_label.setStyleSheet("color: #64748B;")
        footer.addWidget(self.status_label)
        footer.addStretch(1)
        self.close_button = QPushButton("Cerrar")
        self.close_button.setObjectName("customerQueriesCloseButton")
        self.close_button.setProperty("btnRole", "secondary")
        self.close_button.clicked.connect(self.reject)
        footer.addWidget(self.close_button)
        layout.addLayout(footer)

    def _run_query(self) -> None:
        prompt = self.prompt.toPlainText().strip()
        if not prompt:
            self.status_label.setText("Escribe una consulta sobre los clientes.")
            self.prompt.setFocus()
            return
        if self._worker is not None and self._worker.isRunning():
            return

        self._set_busy(True)
        self.status_label.setText("Ejecutando consulta...")
        self.interpretation_label.setText("Interpretando la petición...")
        self._worker = CustomerQueryWorker(self._service, prompt, self)
        self._worker.result_ready.connect(self._show_result)
        self._worker.failed.connect(self._show_error)
        self._worker.finished.connect(lambda: self._set_busy(False))
        self._worker.start()

    def _show_result(self, result: CustomerQueryResult) -> None:
        self.interpretation_label.setText(
            result.interpretation or "No se pudo determinar una interpretación detallada."
        )
        self._render_rows(result.headers, result.rows)
        if result.status == "ready":
            source = f" · {result.source}" if result.source else ""
            self.status_label.setText(f"{result.title} · {len(result.rows)} fila(s){source}")
        else:
            self.status_label.setText(result.message or "No se encontraron resultados.")

    def _show_error(self, message: str) -> None:
        self.interpretation_label.setText("La consulta no pudo interpretarse o ejecutarse.")
        self.status_label.setText(message)

    def _render_rows(self, headers: list[str], rows: list[list[Any]]) -> None:
        self.results_table.setSortingEnabled(False)
        self.results_table.clear()
        self.results_table.setColumnCount(len(headers))
        self.results_table.setHorizontalHeaderLabels(headers)
        self.results_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(row):
                header = headers[column_index] if column_index < len(headers) else ""
                item = self._table_item(header, value)
                self.results_table.setItem(row_index, column_index, item)
        self.results_table.resizeColumnsToContents()
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setSortingEnabled(True)

    def _table_item(self, header: str, value: Any) -> QTableWidgetItem:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            text = self._format_number(float(value), percent="%" in header)
            item = CustomerQueryNumericItem(text, float(value))
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if header.startswith("Δ"):
                if float(value) < 0:
                    item.setForeground(QColor("#B42318"))
                elif float(value) > 0:
                    item.setForeground(QColor("#067647"))
            return item
        return QTableWidgetItem(str(value or ""))

    @staticmethod
    def _format_number(value: float, *, percent: bool = False) -> str:
        formatted = f"{float(value):,.2f}"
        formatted = formatted.replace(",", "_").replace(".", ",").replace("_", ".")
        return f"{formatted} %" if percent else formatted

    def _set_busy(self, busy: bool) -> None:
        self.run_button.setEnabled(not busy)
        self.close_button.setEnabled(not busy)
        self.prompt.setReadOnly(busy)

    def reject(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self.status_label.setText("Espera a que termine la consulta.")
            return
        super().reject()
