from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.services.customer_query_service import CustomerQueryResult, CustomerQueryService
from app.services.report_export_service import ReportExportService

BASE_DIR = Path(__file__).resolve().parents[3]


def _tinted_icon(path: Path, color: QColor, size: int = 16) -> QIcon:
    pixmap = QIcon(str(path)).pixmap(size, size)
    painter = QPainter(pixmap)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), color)
    painter.end()
    return QIcon(pixmap)


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
        report_export_service: ReportExportService | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("customerQueriesDialog")
        self.setWindowTitle("Consultas de clientes")
        self.setModal(True)
        self.resize(1040, 680)
        self.setMinimumSize(820, 540)
        self._service = service or CustomerQueryService()
        self._report_export_service = report_export_service or ReportExportService()
        self._worker: CustomerQueryWorker | None = None
        self._last_result: CustomerQueryResult | None = None
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

        action_row = QHBoxLayout()
        self.run_button = QPushButton("Consultar")
        self.run_button.setObjectName("customerQueryRunButton")
        self.run_button.setProperty("btnRole", "primary")
        self.run_button.clicked.connect(self._run_query)
        self.run_button.setIcon(
            _tinted_icon(BASE_DIR / 'assets' / 'icons' / 'brain.svg', QColor('#FFFFFF'), 16)
        )
        self.run_button.setStyleSheet(
            'QPushButton#customerQueryRunButton {'
            'background: #60A5FA; color: #FFFFFF; border: 1px solid #3B82F6; '
            'border-radius: 6px; padding: 5px 12px; font-weight: 600; }'
            'QPushButton#customerQueryRunButton:hover { background: #3B82F6; }'
            'QPushButton#customerQueryRunButton:disabled { background: #BFDBFE; }'
        )
        action_row.addWidget(self.run_button)

        self.excel_button = QPushButton('Excel')
        self.excel_button.setObjectName('customerQueryExcelButton')
        self.excel_button.setProperty('btnRole', 'success')
        self.excel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.excel_button.setEnabled(False)
        self.excel_button.setIcon(
            _tinted_icon(BASE_DIR / 'assets' / 'icons' / 'sheet.svg', QColor('#FFFFFF'), 16)
        )
        self.excel_button.setStyleSheet(
            'QPushButton#customerQueryExcelButton {'
            'background: #16A34A; color: #FFFFFF; border: 1px solid #15803D; '
            'border-radius: 6px; padding: 5px 12px; font-weight: 600; }'
            'QPushButton#customerQueryExcelButton:hover { background: #15803D; }'
            'QPushButton#customerQueryExcelButton:disabled {'
            'background: #F3F4F6; color: #374151; border-color: #9CA3AF; }'
        )
        self.excel_button.clicked.connect(self._export_excel)
        action_row.addWidget(self.excel_button)

        self.pdf_button = QPushButton('Pdf')
        self.pdf_button.setObjectName('customerQueryPdfButton')
        self.pdf_button.setProperty('btnRole', 'danger')
        self.pdf_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pdf_button.setEnabled(False)
        self.pdf_button.setIcon(
            _tinted_icon(BASE_DIR / 'assets' / 'icons' / 'file-text.svg', QColor('#FFFFFF'), 16)
        )
        self.pdf_button.setStyleSheet(
            'QPushButton#customerQueryPdfButton {'
            'background: #DC2626; color: #FFFFFF; border: 1px solid #B91C1C; '
            'border-radius: 6px; padding: 5px 12px; font-weight: 600; }'
            'QPushButton#customerQueryPdfButton:hover { background: #B91C1C; }'
            'QPushButton#customerQueryPdfButton:disabled {'
            'background: #F3F4F6; color: #374151; border-color: #9CA3AF; }'
        )
        self.pdf_button.clicked.connect(self._export_pdf)
        action_row.addWidget(self.pdf_button)

        self.clear_button = QPushButton('Limpiar')
        self.clear_button.setObjectName('customerQueryClearButton')
        self.clear_button.setProperty('btnRole', 'warning')
        self.clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_button.setStyleSheet(
            'QPushButton#customerQueryClearButton {'
            'background: #F59E0B; color: #FFFFFF; border: 1px solid #D97706; '
            'border-radius: 6px; padding: 5px 12px; font-weight: 600; }'
            'QPushButton#customerQueryClearButton:hover { background: #D97706; }'
            'QPushButton#customerQueryClearButton:disabled {'
            'background: #F3F4F6; color: #374151; border-color: #9CA3AF; }'
        )
        self.clear_button.clicked.connect(self._clear_query)
        action_row.addWidget(self.clear_button)
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

    def _clear_query(self) -> None:
        self.prompt.clear()
        self.results_table.clear()
        self.results_table.setRowCount(0)
        self.results_table.setColumnCount(0)
        self._last_result = None
        self._set_export_buttons_enabled(False)
        self.interpretation_label.setText('La interpretación de la consulta aparecerá aquí.')
        self.status_label.setText('Sin consulta ejecutada.')
        self.prompt.setFocus()

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
        self._last_result = result if result.status == "ready" else None
        self.interpretation_label.setText(
            result.interpretation or "No se pudo determinar una interpretación detallada."
        )
        self._render_rows(result.headers, result.rows)
        self._set_export_buttons_enabled(result.status == "ready" and bool(result.rows))
        if result.status == "ready":
            source = f" · {result.source}" if result.source else ""
            self.status_label.setText(f"{result.title} · {len(result.rows)} fila(s){source}")
        else:
            self.status_label.setText(result.message or "No se encontraron resultados.")

    def _show_error(self, message: str) -> None:
        self._last_result = None
        self._set_export_buttons_enabled(False)
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
        normalized_header = str(header or '').strip().lower()
        if normalized_header in {'cod.', 'cod', 'codigo', 'código'}:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                number = float(value)
                text = str(int(number)) if number.is_integer() else str(value)
                return QTableWidgetItem(text)
            return QTableWidgetItem(str(value or ''))
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
        self.clear_button.setEnabled(not busy)
        self._set_export_buttons_enabled(not busy and self._has_exportable_rows())
        self.close_button.setEnabled(not busy)
        self.prompt.setReadOnly(busy)

    def _has_exportable_rows(self) -> bool:
        return bool(
            self._last_result
            and self.results_table.rowCount() > 0
            and self.results_table.columnCount() > 0
        )

    def _set_export_buttons_enabled(self, enabled: bool) -> None:
        if hasattr(self, 'excel_button'):
            self.excel_button.setEnabled(enabled)
        if hasattr(self, 'pdf_button'):
            self.pdf_button.setEnabled(enabled)

    def _visible_table_data(self) -> tuple[list[str], list[list[Any]]]:
        headers = [
            str(self.results_table.horizontalHeaderItem(column).text() or '')
            if self.results_table.horizontalHeaderItem(column) is not None
            else ''
            for column in range(self.results_table.columnCount())
        ]
        rows: list[list[Any]] = []
        for row_index in range(self.results_table.rowCount()):
            row: list[Any] = []
            for column_index in range(self.results_table.columnCount()):
                item = self.results_table.item(row_index, column_index)
                if item is None:
                    row.append('')
                    continue
                value = item.data(Qt.ItemDataRole.UserRole)
                row.append(value if value is not None else item.text())
            rows.append(row)
        return headers, rows

    def _export_title(self) -> str:
        if self._last_result is not None and self._last_result.title:
            return self._last_result.title
        return 'Consulta de clientes'

    def _export_excel(self) -> None:
        if not self._has_exportable_rows():
            QMessageBox.warning(self, 'Consultas de clientes', 'No hay resultados para exportar.')
            return
        headers, rows = self._visible_table_data()
        title = self._export_title()
        default = str(self._report_export_service.default_path(title, 'xlsx', folder='consultas_clientes'))
        path, _ = QFileDialog.getSaveFileName(self, 'Exportar consulta a Excel', default, 'Excel (*.xlsx)')
        if not path:
            return
        out = self._report_export_service.export_excel(path, title, headers, rows, sheet_title='Consulta clientes')
        QMessageBox.information(self, 'Consultas de clientes', f'Excel exportado:\n{out}')

    def _export_pdf(self) -> None:
        if not self._has_exportable_rows():
            QMessageBox.warning(self, 'Consultas de clientes', 'No hay resultados para exportar.')
            return
        headers, rows = self._visible_table_data()
        title = self._export_title()
        default = str(self._report_export_service.default_path(title, 'pdf', folder='consultas_clientes'))
        path, _ = QFileDialog.getSaveFileName(self, 'Exportar consulta a PDF', default, 'PDF (*.pdf)')
        if not path:
            return
        out = self._report_export_service.export_pdf(path, title, headers, rows)
        QMessageBox.information(self, 'Consultas de clientes', f'PDF exportado:\n{out}')

    def reject(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self.status_label.setText("Espera a que termine la consulta.")
            return
        super().reject()
