from __future__ import annotations

from datetime import date, timedelta
from html import escape
from pathlib import Path

from PySide6.QtCore import QDate, QEvent, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPageLayout, QPainter, QPen, QPixmap, QTextCharFormat, QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCalendarWidget,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QStackedWidget,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.services.customer_dashboard_service import (
    CustomerDashboardService,
    DashboardActivityRow,
    DashboardIslandRow,
    DashboardReactivationRow,
    DashboardSnapshot,
)
from app.services.customer_service import CustomerService
from app.services.order_dashboard_service import (
    DashboardOrderRow,
    DashboardPendingArticleRow,
    DashboardOrdersStateRow,
    DashboardOrdersWarehouseRow,
    DashboardTopArticleRow,
    OrderDashboardService,
)
from app.services.report_export_service import ReportExportService
from app.services.sales_dashboard_service import (
    DashboardSalesCustomerRow,
    DashboardSalesIslandRow,
    DashboardSalesTypeRow,
    SalesDashboardService,
)
from app.services.warehouse_dashboard_service import (
    DashboardWarehouseMovementRow,
    DashboardWarehouseRiskRow,
    DashboardWarehouseStockRow,
    WarehouseDashboardService,
)

BASE_DIR = Path(__file__).resolve().parents[3]


class DashboardAgendaPdfPreviewDialog(QDialog):
    def __init__(
        self,
        *,
        report_export_service: ReportExportService,
        title: str,
        headers: list[str],
        rows: list[list[str]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.report_export_service = report_export_service
        self.report_title = title
        self.report_headers = list(headers)
        self.report_rows = [list(row) for row in rows]

        self.setObjectName('dashboardAgendaPdfPreviewDialog')
        self.setWindowTitle(f'Vista previa de entradas · {title}')
        self.setModal(True)
        self.resize(920, 620)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        heading = QLabel(title)
        heading.setObjectName('dashboardAgendaPdfPreviewTitle')
        layout.addWidget(heading)
        summary = QLabel(f'{len(self.report_rows)} entrada(s) se guardarán en el documento PDF.')
        summary.setObjectName('dashboardAgendaPdfPreviewSummary')
        layout.addWidget(summary)

        self.entries_scroll = QScrollArea(self)
        self.entries_scroll.setObjectName('dashboardAgendaPdfPreviewScroll')
        self.entries_scroll.setWidgetResizable(True)
        self.entries_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        entries_host = QWidget()
        entries_host.setObjectName('dashboardAgendaPdfPreviewHost')
        entries_layout = QVBoxLayout(entries_host)
        entries_layout.setContentsMargins(0, 0, 0, 0)
        entries_layout.setSpacing(8)
        entries_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        for row in self.report_rows:
            values = [str(value or '') for value in row]
            values.extend([''] * (4 - len(values)))
            event_date, customer_text, content_text, state_text = values[:4]
            card = QFrame()
            card.setObjectName('dashboardAgendaPdfPreviewCard')
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 10, 12, 11)
            card_layout.setSpacing(7)
            top_line = QHBoxLayout()
            top_line.setContentsMargins(0, 0, 0, 0)
            top_line.setSpacing(12)
            date_label = QLabel(event_date)
            date_label.setObjectName('dashboardAgendaPdfPreviewDate')
            date_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
            customer_label = QLabel(customer_text)
            customer_label.setObjectName('dashboardAgendaPdfPreviewCustomer')
            customer_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            state_label = QLabel(state_text)
            state_label.setObjectName('dashboardAgendaPdfPreviewState')
            state_label.setProperty('tone', ReportExportService.agenda_state_tone(state_text))
            state_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            state_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
            top_line.addWidget(date_label)
            top_line.addWidget(customer_label, 1)
            top_line.addWidget(state_label)
            content_label = QLabel(content_text)
            content_label.setObjectName('dashboardAgendaPdfPreviewContent')
            content_label.setWordWrap(True)
            content_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            content_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            card_layout.addLayout(top_line)
            card_layout.addWidget(content_label)
            entries_layout.addWidget(card)
        self.entries_scroll.setWidget(entries_host)
        layout.addWidget(self.entries_scroll, 1)

        buttons = QDialogButtonBox(self)
        buttons.setObjectName('dashboardAgendaPdfPreviewButtons')
        self.save_btn = buttons.addButton('Guardar', QDialogButtonBox.ButtonRole.AcceptRole)
        self.save_btn.setObjectName('dashboardAgendaPdfSaveButton')
        self.cancel_btn = buttons.addButton('Cancelar', QDialogButtonBox.ButtonRole.RejectRole)
        self.cancel_btn.setObjectName('dashboardAgendaPdfCancelButton')
        self.save_btn.clicked.connect(self._save_pdf)
        self.cancel_btn.clicked.connect(self.reject)
        layout.addWidget(buttons)
        self.setStyleSheet(
            'QDialog#dashboardAgendaPdfPreviewDialog { background: #F8FAFC; }'
            'QLabel#dashboardAgendaPdfPreviewTitle { color: #0F172A; font-size: 18px; font-weight: 700; }'
            'QLabel#dashboardAgendaPdfPreviewSummary { color: #475569; font-size: 13px; }'
            'QScrollArea#dashboardAgendaPdfPreviewScroll, QWidget#dashboardAgendaPdfPreviewHost {'
            ' background: transparent; border: none; }'
            'QFrame#dashboardAgendaPdfPreviewCard {'
            ' background: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 10px; }'
            'QLabel#dashboardAgendaPdfPreviewDate { color: #334155; font-size: 13px; font-weight: 600; }'
            'QLabel#dashboardAgendaPdfPreviewCustomer { color: #0F172A; font-size: 13px; font-weight: 700; }'
            'QLabel#dashboardAgendaPdfPreviewState {'
            ' color: #475569; background: #F1F5F9; border: 1px solid #CBD5E1;'
            ' border-radius: 8px; padding: 3px 8px; font-size: 13px; font-weight: 700; }'
            'QLabel#dashboardAgendaPdfPreviewState[tone="pending"] {'
            ' color: #1D4ED8; background: #DBEAFE; border-color: #93C5FD; }'
            'QLabel#dashboardAgendaPdfPreviewState[tone="completed"] {'
            ' color: #15803D; background: #DCFCE7; border-color: #86EFAC; }'
            'QLabel#dashboardAgendaPdfPreviewState[tone="postponed"] {'
            ' color: #C2410C; background: #FFEDD5; border-color: #FDBA74; }'
            'QLabel#dashboardAgendaPdfPreviewState[tone="cancelled"] {'
            ' color: #B91C1C; background: #FEE2E2; border-color: #FCA5A5; }'
            'QLabel#dashboardAgendaPdfPreviewContent { color: #1E293B; font-size: 13px; }'
            'QPushButton#dashboardAgendaPdfSaveButton {'
            ' background: #16A34A; color: white; border: none; border-radius: 8px;'
            ' min-width: 96px; padding: 8px 14px; font-weight: 700; }'
            'QPushButton#dashboardAgendaPdfSaveButton:hover { background: #15803D; }'
            'QPushButton#dashboardAgendaPdfCancelButton {'
            ' background: #FFFFFF; color: #B91C1C; border: 1px solid #FCA5A5; border-radius: 8px;'
            ' min-width: 96px; padding: 8px 14px; font-weight: 700; }'
            'QPushButton#dashboardAgendaPdfCancelButton:hover { background: #FEF2F2; }'
        )

    def _save_pdf(self) -> None:
        default_path = str(
            self.report_export_service.default_path(self.report_title, 'pdf', folder='agenda_dashboard')
        )
        path, _ = QFileDialog.getSaveFileName(self, 'Guardar agenda en PDF', default_path, 'PDF (*.pdf)')
        if not path:
            return
        try:
            output = self.report_export_service.export_dashboard_agenda_pdf(
                path,
                self.report_title,
                self.report_rows,
            )
        except Exception as exc:
            QMessageBox.warning(self, 'Agenda', f'No se pudo guardar el PDF.\n\n{exc}')
            return
        QMessageBox.information(self, 'Agenda', f'PDF guardado correctamente.\n\n{output}')
        self.accept()


class DashboardAgendaDialog(QDialog):
    def __init__(self, page: "DashboardPage", *, agenda_id: str = "", default_customer_id: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent or page)
        self._page = page
        self._agenda_id = str(agenda_id or "").strip()
        self._activity = page.customer_service.get_agenda_activity(self._agenda_id) if self._agenda_id else None
        self.setWindowTitle("Nueva actividad" if self._activity is None else "Editar actividad")
        self.setModal(True)
        self.resize(620, 520)
        self._build_ui(default_customer_id=default_customer_id)

    def _build_ui(self, *, default_customer_id: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        title = QLabel("Actividad de agenda")
        layout.addWidget(title)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        layout.addLayout(form)

        self.customer_combo = QComboBox()
        self.customer_combo.setMinimumWidth(340)
        for customer_id, label in self._page.customer_choices(include_inactive=self._activity is not None):
            self.customer_combo.addItem(label, customer_id)
        form.addRow("Cliente", self.customer_combo)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        self._page.configure_dashboard_calendar(self.date_edit)
        form.addRow("Fecha actividad", self.date_edit)

        self.type_combo = QComboBox()
        for key, label in self._page.agenda_type_options():
            self.type_combo.addItem(label, key)
        form.addRow("Tipo", self.type_combo)

        self.state_combo = QComboBox()
        for key, label in self._page.agenda_state_options():
            self.state_combo.addItem(label, key)
        form.addRow("Estado", self.state_combo)

        self.priority_combo = QComboBox()
        for value in ("Alta", "Media", "Normal", "Baja"):
            self.priority_combo.addItem(value, value.lower())
        form.addRow("Prioridad", self.priority_combo)

        self.responsible_edit = QLineEdit()
        form.addRow("Responsable", self.responsible_edit)

        self.summary_edit = QLineEdit()
        form.addRow("Resumen", self.summary_edit)

        self.detail_edit = QTextEdit()
        self.detail_edit.setMinimumHeight(120)
        form.addRow("Detalle", self.detail_edit)

        follow_up_row = QHBoxLayout()
        follow_up_row.setContentsMargins(0, 0, 0, 0)
        follow_up_row.setSpacing(10)
        self.follow_up_check = QCheckBox("Tiene seguimiento")
        self.follow_up_date = QDateEdit()
        self.follow_up_date.setCalendarPopup(True)
        self.follow_up_date.setDisplayFormat("dd/MM/yyyy")
        self._page.configure_dashboard_calendar(self.follow_up_date)
        self.follow_up_date.setEnabled(False)
        self.follow_up_check.toggled.connect(self.follow_up_date.setEnabled)
        follow_up_row.addWidget(self.follow_up_check)
        follow_up_row.addWidget(self.follow_up_date)
        follow_up_row.addStretch(1)
        follow_up_container = QWidget()
        follow_up_container.setLayout(follow_up_row)
        form.addRow("Seguimiento", follow_up_container)

        buttons = QDialogButtonBox()
        buttons.addButton("Guardar", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton("Cancelar", QDialogButtonBox.ButtonRole.RejectRole)
        self.delete_btn: QPushButton | None = None
        if self._activity is not None:
            self.delete_btn = buttons.addButton("Eliminar", QDialogButtonBox.ButtonRole.DestructiveRole)
            self.delete_btn.clicked.connect(self._delete_current_activity)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._load_activity(default_customer_id=default_customer_id)

    def _load_activity(self, *, default_customer_id: str) -> None:
        if self._activity is None:
            default_index = self.customer_combo.findData(str(default_customer_id or "").strip())
            if default_index >= 0:
                self.customer_combo.setCurrentIndex(default_index)
            self.date_edit.setDate(QDate.currentDate())
            self.follow_up_date.setDate(QDate.currentDate())
            self.type_combo.setCurrentIndex(max(0, self.type_combo.findData("seguimiento")))
            self.state_combo.setCurrentIndex(max(0, self.state_combo.findData("pendiente")))
            self.priority_combo.setCurrentIndex(max(0, self.priority_combo.findData("normal")))
            return

        customer_index = self.customer_combo.findData(str(getattr(self._activity, "cliente_id", "") or "").strip())
        if customer_index >= 0:
            self.customer_combo.setCurrentIndex(customer_index)
        self.date_edit.setDate(self._page.qdate_from_value(getattr(self._activity, "fecha_actividad", None)))
        self.follow_up_date.setDate(self._page.qdate_from_value(getattr(self._activity, "fecha_seguimiento", None), fallback_today=True))
        self.type_combo.setCurrentIndex(max(0, self.type_combo.findData(str(getattr(self._activity, "tipo", "") or "nota"))))
        self.state_combo.setCurrentIndex(max(0, self.state_combo.findData(str(getattr(self._activity, "estado", "") or "pendiente"))))
        self.priority_combo.setCurrentIndex(max(0, self.priority_combo.findData(str(getattr(self._activity, "prioridad", "") or "normal").strip().lower())))
        self.responsible_edit.setText(str(getattr(self._activity, "responsable", "") or ""))
        self.summary_edit.setText(str(getattr(self._activity, "resumen", "") or ""))
        self.detail_edit.setPlainText(str(getattr(self._activity, "detalle", "") or ""))
        has_follow_up = getattr(self._activity, "fecha_seguimiento", None) is not None
        self.follow_up_check.setChecked(has_follow_up)
        self.follow_up_date.setEnabled(has_follow_up)

    def _save(self) -> None:
        customer_id = str(self.customer_combo.currentData() or "").strip()
        if not customer_id:
            QMessageBox.warning(self, "Agenda", "Selecciona un cliente.")
            return
        summary = self.summary_edit.text().strip()
        detail = self.detail_edit.toPlainText().strip()
        if not summary and not detail:
            QMessageBox.warning(self, "Agenda", "El resumen o el detalle no pueden quedar vacíos.")
            return
        payload = {
            "cliente_id": customer_id,
            "fecha_actividad": self.date_edit.date().toString("yyyy-MM-dd"),
            "tipo": str(self.type_combo.currentData() or "nota"),
            "estado": str(self.state_combo.currentData() or "pendiente"),
            "resumen": summary,
            "detalle": detail,
            "fecha_seguimiento": self.follow_up_date.date().toString("yyyy-MM-dd") if self.follow_up_check.isChecked() else "",
            "prioridad": str(self.priority_combo.currentData() or "normal"),
            "responsable": self.responsible_edit.text().strip(),
        }
        try:
            self._page.customer_service.upsert_agenda_activity(self._agenda_id, payload)
        except Exception as exc:
            QMessageBox.warning(self, "Agenda", f"No se pudo guardar la actividad: {exc}")
            return
        self.accept()

    def _delete_current_activity(self) -> None:
        if self._activity is None:
            return
        answer = QMessageBox.question(self, "Agenda", "La actividad se eliminará de la agenda.\n\n¿Continuar?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._page.customer_service.delete_agenda_activity(str(getattr(self._activity, "agenda_id", "") or ""))
        except Exception as exc:
            QMessageBox.warning(self, "Agenda", f"No se pudo eliminar la actividad: {exc}")
            return
        self.accept()


class DashboardAgendaOverviewDialog(QDialog):
    def __init__(self, page: "DashboardPage", parent: QWidget | None = None) -> None:
        super().__init__(parent or page)
        self._page = page
        self._changed = False
        self.setWindowTitle("Agenda de clientes")
        self.resize(1120, 640)
        self._build_ui()
        self.refresh()

    @property
    def changed(self) -> bool:
        return self._changed

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel("Agenda completa")
        layout.addWidget(title)

        self.summary_label = QLabel("")
        layout.addWidget(self.summary_label)

        self.table = QTableWidget(0, 8)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setHorizontalHeaderLabels(["Fecha", "Seguimiento", "Cliente", "Isla", "Tipo", "Estado", "Resumen", "Responsable"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        self.table.cellDoubleClicked.connect(self._edit_selected)
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)
        self.new_btn = QPushButton("Nueva actividad")
        self.new_btn.clicked.connect(self._create_activity)
        actions.addWidget(self.new_btn)
        self.edit_btn = QPushButton("Editar")
        self.edit_btn.clicked.connect(self._edit_selected)
        actions.addWidget(self.edit_btn)
        actions.addItem(QSpacerItem(10, 10, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        self.close_btn = QPushButton("Cerrar")
        self.close_btn.clicked.connect(self.accept)
        actions.addWidget(self.close_btn)
        layout.addLayout(actions)

    def refresh(self) -> None:
        rows = self._page.dashboard_service.list_all_activities()
        self.summary_label.setText(f"{len(rows)} actividad(es) activas en agenda.")
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                self._page.format_date(row.fecha_actividad),
                self._page.format_date(row.fecha_seguimiento, allow_blank=True),
                self._page.customer_label(row.cliente_codigo, row.cliente_nombre),
                row.isla_nombre or "Sin isla",
                self._page.agenda_type_label(row.tipo),
                self._page.agenda_state_label(row.estado),
                row.resumen or row.detalle or "-",
                row.responsable or "-",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, row.agenda_id)
                self.table.setItem(row_index, column, item)
        if rows:
            self.table.selectRow(0)

    def _selected_agenda_id(self) -> str:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return ""
        item = self.table.item(selected[0].row(), 0)
        return str(item.data(Qt.ItemDataRole.UserRole) or "").strip() if item is not None else ""

    def _create_activity(self) -> None:
        dialog = DashboardAgendaDialog(self._page, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._changed = True
            self.refresh()

    def _edit_selected(self, *_args) -> None:
        agenda_id = self._selected_agenda_id()
        if not agenda_id:
            return
        dialog = DashboardAgendaDialog(self._page, agenda_id=agenda_id, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._changed = True
            self.refresh()


class DashboardCalendarDelegate(QStyledItemDelegate):
    HEADER_TEXT_COLOR = "#FFFFFF"
    SELECTED_BACKGROUND = "#F1F5F9"
    SELECTED_BORDER = "#475569"
    TODAY_BACKGROUND = "#FDE68A"
    TODAY_BORDER = "#F59E0B"

    def __init__(self, calendar: "DashboardMonthCalendar", page: "DashboardPage") -> None:
        super().__init__(calendar)
        self._calendar = calendar
        self._page = page

    def paint(self, painter: QPainter, option, index) -> None:
        display = index.data(Qt.ItemDataRole.DisplayRole)
        if display is None:
            return

        is_header = index.row() == 0 or index.column() == 0
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if is_header:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#5B8DEF"))
            painter.drawRoundedRect(option.rect.adjusted(2, 2, -2, -2), 4, 4)
            font = option.font
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QColor(self.HEADER_TEXT_COLOR))
            painter.drawText(option.rect, Qt.AlignmentFlag.AlignCenter, str(display))
            painter.restore()
            return

        calendar_date = self._date_for_index(index.row(), index.column())
        if not calendar_date.isValid():
            painter.restore()
            return
        day_value = date(calendar_date.year(), calendar_date.month(), calendar_date.day())
        rows_for_day = self._page._agenda_rows_for_date(day_value)
        tone = self._page._agenda_day_tone(rows_for_day, today_value=date.today())
        in_month = calendar_date.month() == self._calendar.monthShown() and calendar_date.year() == self._calendar.yearShown()
        selected = calendar_date == self._calendar.selectedDate()
        is_today = calendar_date == QDate.currentDate()
        weekend = calendar_date.dayOfWeek() in {Qt.DayOfWeek.Saturday.value, Qt.DayOfWeek.Sunday.value}

        background = QColor("#FFFFFF")
        text_color = QColor("#D94C5C") if weekend else QColor("#0F172A")
        if not in_month:
            text_color = QColor("#A8B0BC")
        elif tone == "blue":
            background = QColor("#EFF6FF")
            text_color = QColor("#1D4ED8")
        elif tone == "green":
            background = QColor("#F0FDF4")
            text_color = QColor("#15803D")
        elif tone == "red":
            background = QColor("#FEF2F2")
            text_color = QColor("#DC2626")

        border_color: QColor | None = None
        border_width = 0
        if is_today:
            background = QColor(self.TODAY_BACKGROUND)
            text_color = QColor("#78350F")
            border_color = QColor(self.TODAY_BORDER)
            border_width = 1
        if selected:
            if not is_today:
                background = QColor(self.SELECTED_BACKGROUND)
                text_color = QColor("#0F172A")
            border_color = QColor(self.SELECTED_BORDER)
            border_width = 2

        painter.fillRect(option.rect, QColor("#FFFFFF"))
        if selected or is_today or tone is not None:
            if border_color is None:
                painter.setPen(Qt.PenStyle.NoPen)
            else:
                pen = painter.pen()
                pen.setColor(border_color)
                pen.setWidth(border_width)
                painter.setPen(pen)
            painter.setBrush(background)
            painter.drawRoundedRect(option.rect.adjusted(3, 2, -3, -2), 4, 4)

        font = option.font
        font.setBold(is_today)
        painter.setFont(font)
        painter.setPen(text_color)
        painter.drawText(option.rect, Qt.AlignmentFlag.AlignCenter, str(calendar_date.day()))
        painter.restore()

    def _date_for_index(self, row: int, column: int) -> QDate:
        if row <= 0 or column <= 0:
            return QDate()
        month_start = QDate(self._calendar.yearShown(), self._calendar.monthShown(), 1)
        first_day = self._calendar.firstDayOfWeek().value
        offset = (month_start.dayOfWeek() - first_day) % 7
        first_visible = month_start.addDays(-offset)
        return first_visible.addDays(((row - 1) * 7) + (column - 1))


class DashboardMonthCalendar(QCalendarWidget):
    weekSelected = Signal(object, object, int)

    def __init__(self, page: 'DashboardPage', parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._page = page
        self.setObjectName('dashboardMonthCalendar')
        self.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
        self.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.ShortDayNames)
        self.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.ISOWeekNumbers)
        self.setNavigationBarVisible(True)
        self.setGridVisible(True)
        self.setDateEditEnabled(False)
        self.setMinimumSize(320, 220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        header_format = QTextCharFormat()
        header_format.setBackground(QColor("#5B8DEF"))
        header_format.setForeground(QColor("#FFFFFF"))
        self.setHeaderTextFormat(header_format)
        weekend_format = QTextCharFormat()
        weekend_format.setForeground(QColor("#D94C5C"))
        self.setWeekdayTextFormat(Qt.DayOfWeek.Saturday, weekend_format)
        self.setWeekdayTextFormat(Qt.DayOfWeek.Sunday, weekend_format)

        calendar_view = self.findChild(QAbstractItemView, "qt_calendar_calendarview")
        if calendar_view is not None:
            self._delegate = DashboardCalendarDelegate(self, page)
            calendar_view.setItemDelegate(self._delegate)
            self._calendar_view = calendar_view
            self._calendar_viewport = calendar_view.viewport()
            self._calendar_viewport.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        if (
            watched is getattr(self, '_calendar_viewport', None)
            and event.type() == QEvent.Type.MouseButtonRelease
            and event.button() == Qt.MouseButton.LeftButton
        ):
            index = self._calendar_view.indexAt(event.position().toPoint())
            self._emit_week_for_index(index)
        return super().eventFilter(watched, event)

    def _emit_week_for_index(self, index) -> None:
        if index.row() <= 0 or index.column() != 0:
            return
        monday_qdate = self._delegate._date_for_index(index.row(), 1)
        if not monday_qdate.isValid():
            return
        week_start = date(monday_qdate.year(), monday_qdate.month(), monday_qdate.day())
        week_end = week_start + timedelta(days=6)
        week_number = monday_qdate.weekNumber()[0]
        self.weekSelected.emit(week_start, week_end, week_number)


class DashboardActivityCard(QFrame):
    editRequested = Signal(str)

    def __init__(self, agenda_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.agenda_id = str(agenda_id or '').strip()
        self.setObjectName('dashboardActivityCard')
        self.setProperty('agendaId', self.agenda_id)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.RightButton and self.agenda_id:
            self.editRequested.emit(self.agenda_id)
            event.accept()
            return
        super().mousePressEvent(event)

    def contextMenuEvent(self, event) -> None:
        event.accept()


class DashboardSortableItem(QTableWidgetItem):
    def __init__(self, text: str, sort_value: object) -> None:
        super().__init__(text)
        self._sort_value = sort_value

    def __lt__(self, other: QTableWidgetItem) -> bool:
        if isinstance(other, DashboardSortableItem):
            return self._sort_value < other._sort_value
        return super().__lt__(other)


class DashboardDonutChart(QWidget):
    COLORS = ['#2563EB', '#16A34A', '#F97316', '#EF4444', '#8B5CF6']

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('dashboardOrdersTopArticlesDonut')
        self._rows: list[DashboardTopArticleRow] = []
        self.setMinimumHeight(170)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_rows(self, rows: list[DashboardTopArticleRow]) -> None:
        self._rows = list(rows[:5])
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(8, 8, -8, -8)
        total = sum(max(row.ordered_kg, 0.0) for row in self._rows)
        if total <= 1e-9:
            painter.setPen(QColor('#64748B'))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, 'Sin datos')
            return

        side = max(80, min(rect.height() - 6, rect.width() // 2 - 16))
        donut_rect = QRectF(rect.left(), rect.top() + max(0, (rect.height() - side) // 2), side, side)
        pen = QPen()
        pen.setWidth(max(14, side // 7))
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        start_angle = 90 * 16
        for index, row in enumerate(self._rows):
            span = int(round(-360 * 16 * (max(row.ordered_kg, 0.0) / total)))
            pen.setColor(QColor(self.COLORS[index % len(self.COLORS)]))
            painter.setPen(pen)
            painter.drawArc(donut_rect, start_angle, span)
            start_angle += span

        painter.setPen(QColor('#0F172A'))
        painter.drawText(donut_rect, Qt.AlignmentFlag.AlignCenter, f'{DashboardPage.format_kg(total)}')

        legend_left = int(donut_rect.right()) + 18
        legend_top = rect.top() + 6
        line_height = 23
        painter.setPen(QColor('#334155'))
        for index, row in enumerate(self._rows):
            y = legend_top + index * line_height
            painter.setBrush(QColor(self.COLORS[index % len(self.COLORS)]))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(legend_left, y + 5, 10, 10, 3, 3)
            painter.setPen(QColor('#334155'))
            label_width = max(60, rect.right() - legend_left - 82)
            painter.drawText(
                QRectF(legend_left + 16, y, label_width, line_height),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                row.article_name,
            )
            painter.setPen(QColor('#0F172A'))
            painter.drawText(
                QRectF(rect.right() - 66, y, 66, line_height),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                DashboardPage.format_kg(row.ordered_kg),
            )
            painter.setPen(QColor('#334155'))


class DashboardPage(QWidget):
    def __init__(
        self,
        *,
        customer_service: CustomerService | None = None,
        dashboard_service: CustomerDashboardService | None = None,
        order_dashboard_service: OrderDashboardService | None = None,
        sales_dashboard_service: SalesDashboardService | None = None,
        warehouse_dashboard_service: WarehouseDashboardService | None = None,
        report_export_service: ReportExportService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.customer_service = customer_service or CustomerService()
        self.dashboard_service = dashboard_service or CustomerDashboardService()
        self.order_dashboard_service = order_dashboard_service or OrderDashboardService()
        self.sales_dashboard_service = sales_dashboard_service or SalesDashboardService()
        self.warehouse_dashboard_service = warehouse_dashboard_service or WarehouseDashboardService()
        self.report_export_service = report_export_service or ReportExportService()
        self.setObjectName('dashboardPageRoot')
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.agenda_calendar_selected_date = date.today()
        self.agenda_calendar_month = date.today().replace(day=1)
        self.agenda_calendar_week_range: tuple[date, date] | None = None
        self.agenda_calendar_rows: list[DashboardActivityRow] = []
        self.today_report_rows: list[DashboardActivityRow] = []
        self.current_dashboard = 'agenda'
        self.dashboard_nav_buttons: dict[str, QPushButton] = {}
        self._build_ui()
        self.reload()

    def _configure_row_select_table(self, table: QTableWidget) -> None:
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

    def _build_ui(self) -> None:
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName('dashboardSidebar')
        sidebar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        sidebar.setFixedWidth(184)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 22, 16, 18)
        sidebar_layout.setSpacing(24)

        brand = QLabel()
        brand.setObjectName('dashboardSidebarBrand')
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_path = BASE_DIR / 'assets' / 'logos' / 'corporativos' / 'IREKS_Logo_transparente.png'
        if brand_path.exists():
            brand.setPixmap(QPixmap(str(brand_path)).scaledToWidth(144, Qt.TransformationMode.SmoothTransformation))
        sidebar_layout.addWidget(brand)

        agenda_btn = QPushButton('Agenda')
        agenda_btn.setObjectName('dashboardSidebarButton')
        agenda_btn.setMinimumHeight(58)
        agenda_btn.clicked.connect(lambda: self._set_dashboard_mode('agenda'))
        sidebar_layout.addWidget(agenda_btn)
        self.dashboard_nav_buttons['agenda'] = agenda_btn

        pedidos_btn = QPushButton('Pedidos')
        pedidos_btn.setObjectName('dashboardSidebarButton')
        pedidos_btn.setMinimumHeight(58)
        pedidos_btn.clicked.connect(lambda: self._set_dashboard_mode('pedidos'))
        sidebar_layout.addWidget(pedidos_btn)
        self.dashboard_nav_buttons['pedidos'] = pedidos_btn

        almacen_btn = QPushButton('Almacen')
        almacen_btn.setObjectName('dashboardSidebarButton')
        almacen_btn.setMinimumHeight(58)
        almacen_btn.clicked.connect(lambda: self._set_dashboard_mode('almacen'))
        sidebar_layout.addWidget(almacen_btn)
        self.dashboard_nav_buttons['almacen'] = almacen_btn

        ventas_btn = QPushButton('Ventas')
        ventas_btn.setObjectName('dashboardSidebarButton')
        ventas_btn.setMinimumHeight(58)
        ventas_btn.clicked.connect(lambda: self._set_dashboard_mode('ventas'))
        sidebar_layout.addWidget(ventas_btn)
        self.dashboard_nav_buttons['ventas'] = ventas_btn

        objetivos_btn = QPushButton('Objetivos')
        objetivos_btn.setObjectName('dashboardSidebarButton')
        objetivos_btn.setMinimumHeight(58)
        self._set_button_icon(objetivos_btn, 'goal.svg', '#475569', 20)
        objetivos_btn.clicked.connect(lambda: self._show_placeholder_dashboard('Objetivos'))
        sidebar_layout.addWidget(objetivos_btn)

        sidebar_layout.addStretch(1)
        root_layout.addWidget(sidebar)

        content_host = QWidget()
        content_host.setObjectName('dashboardContentHost')
        content_host.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        content_host_layout = QVBoxLayout(content_host)
        content_host_layout.setContentsMargins(0, 0, 0, 0)
        content_host_layout.setSpacing(0)

        content = QWidget()
        content.setObjectName('dashboardContent')
        content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(22, 16, 22, 12)
        self.content_layout.setSpacing(12)
        content_host_layout.addWidget(content)
        root_layout.addWidget(content_host, 1)

        header = QFrame()
        header.setObjectName('dashboardHeader')
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        header_copy = QVBoxLayout()
        header_copy.setContentsMargins(0, 0, 0, 0)
        header_copy.setSpacing(4)
        self.title_label = QLabel('Agenda')
        self.title_label.setObjectName('dashboardTitle')
        header_copy.addWidget(self.title_label)
        self.date_label = QLabel('')
        self.date_label.setObjectName('dashboardDateLabel')
        self.date_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        header_copy.addWidget(self.date_label)
        header_layout.addLayout(header_copy, 1)

        self.new_activity_btn = QPushButton('Nueva actividad')
        self.new_activity_btn.setObjectName('dashboardNewActivityButton')
        self._set_button_icon(self.new_activity_btn, 'plus.svg', '#FFFFFF', 18)
        self.new_activity_btn.clicked.connect(self._handle_primary_action)
        header_layout.addWidget(self.new_activity_btn)

        self.full_agenda_btn = QPushButton('Ver agenda completa')
        self.full_agenda_btn.setObjectName('dashboardFullAgendaButton')
        self._set_button_icon(self.full_agenda_btn, 'calendar.svg', '#2563EB', 18)
        self.full_agenda_btn.clicked.connect(self._handle_secondary_action)
        header_layout.addWidget(self.full_agenda_btn)

        self.content_layout.addWidget(header)
        self.dashboard_stack = QStackedWidget()
        self.dashboard_stack.setObjectName('dashboardContentStack')
        self.agenda_dashboard = self._build_agenda_dashboard()
        self.orders_dashboard = self._build_orders_dashboard()
        self.sales_dashboard = self._build_sales_dashboard()
        self.warehouse_dashboard = self._build_warehouse_dashboard()
        self.dashboard_stack.addWidget(self.agenda_dashboard)
        self.dashboard_stack.addWidget(self.orders_dashboard)
        self.dashboard_stack.addWidget(self.sales_dashboard)
        self.dashboard_stack.addWidget(self.warehouse_dashboard)
        self.content_layout.addWidget(self.dashboard_stack, 1)

        self.footer_label = QLabel('')
        self.footer_label.setObjectName('dashboardFooterLabel')
        self.footer_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.content_layout.addWidget(self.footer_label)
        self._apply_styles()
        self._set_dashboard_mode('agenda', reload=False)

    def _build_agenda_dashboard(self) -> QWidget:
        widget = QWidget()
        widget.setObjectName('dashboardAgendaView')
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        kpi_row = QGridLayout()
        kpi_row.setHorizontalSpacing(12)
        kpi_row.setVerticalSpacing(12)
        self.kpi_labels: dict[str, QLabel] = {}
        self.kpi_notes: dict[str, QLabel] = {}
        for column, (key, title, tone, icon_name) in enumerate([
            ('pending_today', 'Pendientes hoy', 'blue', 'clipboard-list.svg'),
            ('overdue', 'Vencidas', 'red', 'clock-3.svg'),
            ('completed_today', 'Completadas hoy', 'green', 'circle-check.svg'),
            ('customers_without_follow_up', 'Clientes sin seguimiento', 'orange', 'users.svg'),
        ]):
            card, value_label, _unit_label, note_label = self._build_kpi_card(title, tone, icon_name)
            self.kpi_labels[key] = value_label
            self.kpi_notes[key] = note_label
            kpi_row.addWidget(card, 0, column)
            kpi_row.setColumnStretch(column, 1)
        layout.addLayout(kpi_row, 0)

        middle_row = QHBoxLayout()
        middle_row.setContentsMargins(0, 0, 0, 0)
        middle_row.setSpacing(12)
        self.upcoming_panel = self._build_upcoming_panel()
        today_panel, self.today_items_layout, self.today_panel_title = self._build_list_panel(
            'Agenda de hoy',
            'dashboardTodayPanel',
            empty_text='Hoy no hay actividades registradas.',
        )
        middle_row.addWidget(self.upcoming_panel, 4)
        middle_row.addWidget(today_panel, 6)
        layout.addLayout(middle_row, 3)

        lower_row = QHBoxLayout()
        lower_row.setContentsMargins(0, 0, 0, 0)
        lower_row.setSpacing(12)

        reactivation_panel = self._build_table_panel('Clientes a reactivar', 'dashboardReactivationPanel')
        self.reactivation_table = QTableWidget(0, 5)
        self.reactivation_table.setObjectName('dashboardReactivationTable')
        self.reactivation_table.setHorizontalHeaderLabels(['Cliente', 'Isla', 'Último contacto', 'Variación kg', 'Prioridad'])
        self._configure_table(self.reactivation_table)
        header = self.reactivation_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        reactivation_panel.layout().addWidget(self.reactivation_table)
        lower_row.addWidget(reactivation_panel, 5)

        island_panel = self._build_table_panel('Agenda por isla', 'dashboardIslandPanel')
        self.island_table = QTableWidget(0, 5)
        self.island_table.setObjectName('dashboardIslandTable')
        self.island_table.setHorizontalHeaderLabels(['Isla', 'Pend.', 'Aplaz.', 'Hechas', 'Total'])
        self._configure_table(self.island_table)
        island_header = self.island_table.horizontalHeader()
        island_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 5):
            island_header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        island_panel.layout().addWidget(self.island_table)
        lower_row.addWidget(island_panel, 3)
        layout.addLayout(lower_row, 2)
        return widget

    def _build_kpi_card(self, title: str, tone: str, icon_name: str) -> tuple[QFrame, QLabel, QLabel, QLabel]:
        card = QFrame()
        card.setObjectName('dashboardKpiCard')
        card.setProperty('tone', tone)
        card.setMinimumHeight(104)
        card.setMaximumHeight(104)
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)

        icon_wrap = QFrame()
        icon_wrap.setObjectName('dashboardKpiIconWrap')
        icon_wrap.setProperty('tone', tone)
        icon_wrap.setFixedSize(62, 62)
        icon_layout = QVBoxLayout(icon_wrap)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setSpacing(0)
        icon_label = QLabel()
        icon_label.setObjectName('dashboardKpiIcon')
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setPixmap(self._icon_pixmap(icon_name, self._tone_color(tone), 28))
        icon_layout.addWidget(icon_label)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName('dashboardKpiTitle')
        title_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        value_label = QLabel('0')
        value_label.setObjectName('dashboardKpiValue')
        value_label.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Preferred)
        unit_label = QLabel('')
        unit_label.setObjectName('dashboardKpiUnit')
        unit_label.setVisible(False)
        unit_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        note_label = QLabel('')
        note_label.setObjectName('dashboardKpiNote')
        note_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        value_row = QHBoxLayout()
        value_row.setContentsMargins(0, 0, 0, 0)
        value_row.setSpacing(5)
        value_row.addWidget(value_label, 1)
        value_row.addWidget(unit_label, 0, Qt.AlignmentFlag.AlignBottom)
        value_row.addStretch(1)
        text_layout.addWidget(title_label)
        text_layout.addSpacing(2)
        text_layout.addLayout(value_row)
        text_layout.addWidget(note_label)
        text_layout.addStretch(1)

        layout.addWidget(icon_wrap, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(text_layout, 1)
        return card, value_label, unit_label, note_label

    def _build_list_panel(self, title: str, object_name: str, *, empty_text: str) -> tuple[QFrame, QVBoxLayout, QLabel]:
        panel = QFrame()
        panel.setObjectName(object_name)
        panel.setProperty('dashboardPanel', True)
        panel.setMinimumHeight(205)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        heading = QLabel(title)
        heading.setObjectName('dashboardPanelTitle')
        heading.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        heading_layout = QHBoxLayout()
        heading_layout.setContentsMargins(0, 0, 0, 0)
        heading_layout.setSpacing(8)
        heading_layout.addWidget(heading, 1)
        self.today_pdf_btn = QPushButton('PDF')
        self.today_pdf_btn.setObjectName('dashboardTodayPdfButton')
        self.today_pdf_btn.setFixedWidth(96)
        self.today_pdf_btn.setEnabled(False)
        self._set_button_icon(self.today_pdf_btn, 'file-text.svg', '#FFFFFF', 15)
        self.today_pdf_btn.clicked.connect(self._export_today_panel_pdf)
        heading_layout.addWidget(self.today_pdf_btn, 0)
        self.today_print_btn = QPushButton('Imprimir')
        self.today_print_btn.setObjectName('dashboardTodayPrintButton')
        self.today_print_btn.setFixedWidth(96)
        self.today_print_btn.setEnabled(False)
        self._set_button_icon(self.today_print_btn, 'printer.svg', '#FFFFFF', 15)
        self.today_print_btn.clicked.connect(self._print_today_panel)
        heading_layout.addWidget(self.today_print_btn, 0)
        layout.addLayout(heading_layout, 0)

        scroll_area = QScrollArea()
        scroll_area.setObjectName('dashboardTodayScrollArea')
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_content = QWidget()
        scroll_content.setObjectName('dashboardTodayItemsHost')
        container = QVBoxLayout(scroll_content)
        container.setContentsMargins(0, 0, 0, 0)
        container.setSpacing(8)
        container.setAlignment(Qt.AlignmentFlag.AlignTop)
        empty = QLabel(empty_text)
        empty.setObjectName('dashboardEmptyLabel')
        empty.setWordWrap(True)
        empty.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        container.addWidget(empty)
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area, 1)
        return panel, container, heading

    def _build_table_panel(self, title: str, object_name: str) -> QFrame:
        panel = QFrame()
        panel.setObjectName(object_name)
        panel.setProperty('dashboardPanel', True)
        panel.setMinimumHeight(170)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        heading = QLabel(title)
        heading.setObjectName('dashboardPanelTitle')
        heading.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(heading)
        return panel

    def _build_upcoming_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName('dashboardUpcomingPanel')
        panel.setProperty('dashboardPanel', True)
        panel.setMinimumHeight(312)
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        heading_row = QWidget()
        heading_row.setObjectName('dashboardCalendarHeadingBlock')
        heading_row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        heading_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        heading_row.setAutoFillBackground(False)
        heading_row.setStyleSheet('background: transparent; border: none;')
        heading_row_layout = QHBoxLayout(heading_row)
        heading_row_layout.setContentsMargins(0, 0, 0, 0)
        heading_row_layout.setSpacing(0)
        heading = QLabel('Agenda del mes')
        heading.setObjectName('dashboardPanelTitle')
        heading_row_layout.addWidget(heading, 0, Qt.AlignmentFlag.AlignLeft)
        heading_row_layout.addStretch(1)
        layout.addWidget(heading_row, 0)

        self.agenda_month_calendar = DashboardMonthCalendar(self, panel)
        self.agenda_month_calendar.selectionChanged.connect(self._handle_agenda_calendar_selection_changed)
        self.agenda_month_calendar.currentPageChanged.connect(self._handle_agenda_calendar_page_changed)
        self.agenda_month_calendar.weekSelected.connect(self._handle_agenda_calendar_week_selected)
        layout.addWidget(self.agenda_month_calendar, 1)

        summary_row = QHBoxLayout()
        summary_row.setContentsMargins(0, 0, 0, 0)
        summary_row.setSpacing(6)
        self.pending_summary = self._build_summary_chip('Pendientes', 'blue')
        self.done_summary = self._build_summary_chip('Hechas', 'green')
        self.overdue_summary = self._build_summary_chip('Vencidas', 'red')
        summary_row.addWidget(self.pending_summary[0], 1)
        summary_row.addWidget(self.done_summary[0], 1)
        summary_row.addWidget(self.overdue_summary[0], 1)
        layout.addLayout(summary_row)
        return panel

    def _build_summary_chip(self, title: str, tone: str) -> tuple[QFrame, QLabel]:
        frame = QFrame()
        frame.setObjectName('dashboardCalendarSummaryChip')
        frame.setProperty('tone', tone)
        frame.setFixedHeight(34)
        inner = QHBoxLayout(frame)
        inner.setContentsMargins(10, 3, 10, 3)
        inner.setSpacing(8)
        title_label = QLabel(title)
        title_label.setObjectName('dashboardCalendarSummaryTitle')
        title_label.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        value_label = QLabel('0')
        value_label.setObjectName('dashboardCalendarSummaryValue')
        value_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        inner.addWidget(title_label)
        inner.addStretch(1)
        inner.addWidget(value_label)
        return frame, value_label

    def _configure_table(self, table: QTableWidget) -> None:
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.setWordWrap(False)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(32)
        table.horizontalHeader().setStretchLastSection(False)
        table.horizontalHeader().setMinimumHeight(34)

    def _build_orders_dashboard(self) -> QWidget:
        widget = QWidget()
        widget.setObjectName('dashboardOrdersView')
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        kpi_row = QGridLayout()
        kpi_row.setHorizontalSpacing(12)
        kpi_row.setVerticalSpacing(12)
        self.orders_kpi_labels: dict[str, QLabel] = {}
        self.orders_kpi_units: dict[str, QLabel] = {}
        self.orders_kpi_notes: dict[str, QLabel] = {}
        for column, (key, title, tone, icon_name) in enumerate([
            ('total_orders', 'Pedidos', 'blue', 'shopping-cart.svg'),
            ('received_kg', 'Kg recibidos', 'green', 'circle-check.svg'),
            ('pending_kg', 'Kg pendientes', 'orange', 'clipboard-list.svg'),
            ('incident_orders', 'Incidencias', 'red', 'clock-3.svg'),
        ]):
            card, value_label, unit_label, note_label = self._build_kpi_card(title, tone, icon_name)
            self.orders_kpi_labels[key] = value_label
            self.orders_kpi_units[key] = unit_label
            self.orders_kpi_notes[key] = note_label
            kpi_row.addWidget(card, 0, column)
            kpi_row.setColumnStretch(column, 1)
        layout.addLayout(kpi_row, 0)

        upper_row = QHBoxLayout()
        upper_row.setContentsMargins(0, 0, 0, 0)
        upper_row.setSpacing(12)

        recent_panel = self._build_table_panel('Pedidos recientes', 'dashboardOrdersRecentPanel')
        self.orders_recent_table = QTableWidget(0, 7)
        self.orders_recent_table.setObjectName('dashboardOrdersRecentTable')
        self.orders_recent_table.setHorizontalHeaderLabels(['Pedido', 'Almacén', 'Sem', 'Fecha', 'Kg pedido', 'Kg recibido', 'Kg pend.'])
        self._configure_table(self.orders_recent_table)
        self._configure_row_select_table(self.orders_recent_table)
        self.orders_recent_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.orders_recent_table.customContextMenuRequested.connect(self._show_orders_recent_context_menu)
        recent_header = self.orders_recent_table.horizontalHeader()
        recent_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        recent_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        recent_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        recent_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        for col in (4, 5, 6):
            recent_header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        recent_panel.layout().addWidget(self.orders_recent_table)
        upper_row.addWidget(recent_panel, 6)

        pending_panel = self._build_table_panel('Artículos pendientes', 'dashboardOrdersPendingPanel')
        self.orders_pending_table = QTableWidget(0, 4)
        self.orders_pending_table.setObjectName('dashboardOrdersPendingTable')
        self.orders_pending_table.setHorizontalHeaderLabels(['Fecha', 'Pedido', 'Artículo', 'Kg pend.'])
        self._configure_table(self.orders_pending_table)
        self._configure_row_select_table(self.orders_pending_table)
        self.orders_pending_table.setSortingEnabled(True)
        pending_header = self.orders_pending_table.horizontalHeader()
        pending_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        pending_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        pending_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        pending_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        pending_panel.layout().addWidget(self.orders_pending_table)
        upper_row.addWidget(pending_panel, 4)
        layout.addLayout(upper_row, 1)

        lower_row = QHBoxLayout()
        lower_row.setContentsMargins(0, 0, 0, 0)
        lower_row.setSpacing(12)

        top_articles_panel = self._build_table_panel('Top artículos pedidos', 'dashboardOrdersTopArticlesPanel')
        self.orders_top_articles_donut = DashboardDonutChart()
        top_articles_panel.layout().addWidget(self.orders_top_articles_donut, 1)
        lower_row.addWidget(top_articles_panel, 4)

        warehouse_panel = self._build_table_panel('Más pendiente por almacén', 'dashboardOrdersWarehousePanel')
        self.orders_warehouse_table = QTableWidget(0, 4)
        self.orders_warehouse_table.setObjectName('dashboardOrdersWarehouseTable')
        self.orders_warehouse_table.setHorizontalHeaderLabels(['Almacén', 'Abiertos', 'Kg pend.', 'Últ. recepción'])
        self._configure_table(self.orders_warehouse_table)
        warehouse_header = self.orders_warehouse_table.horizontalHeader()
        warehouse_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        warehouse_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        warehouse_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        warehouse_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        warehouse_panel.layout().addWidget(self.orders_warehouse_table)
        lower_row.addWidget(warehouse_panel, 4)

        state_panel = self._build_table_panel('Resumen por estado', 'dashboardOrdersStatePanel')
        self.orders_state_table = QTableWidget(0, 3)
        self.orders_state_table.setObjectName('dashboardOrdersStateTable')
        self.orders_state_table.setHorizontalHeaderLabels(['Estado', 'Pedidos', 'Kg'])
        self._configure_table(self.orders_state_table)
        state_header = self.orders_state_table.horizontalHeader()
        state_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        state_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        state_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        state_panel.layout().addWidget(self.orders_state_table)
        lower_row.addWidget(state_panel, 3)
        layout.addLayout(lower_row, 1)
        return widget




    def _build_sales_dashboard(self) -> QWidget:
        widget = QWidget()
        widget.setObjectName('dashboardSalesView')
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        kpi_row = QGridLayout()
        kpi_row.setHorizontalSpacing(12)
        kpi_row.setVerticalSpacing(12)
        self.sales_kpi_labels: dict[str, QLabel] = {}
        self.sales_kpi_notes: dict[str, QLabel] = {}
        for column, (key, title, tone, icon_name) in enumerate([
            ('total_kg', 'Kg vendidos', 'blue', 'scale.svg'),
            ('delta_kg', 'Variación kg', 'blue', 'trending-down.svg'),
            ('active_customers', 'Clientes activos', 'green', 'briefcase.svg'),
            ('active_islands', 'Islas activas', 'orange', 'map.svg'),
        ]):
            card, value_label, _unit_label, note_label = self._build_kpi_card(title, tone, icon_name)
            self.sales_kpi_labels[key] = value_label
            self.sales_kpi_notes[key] = note_label
            kpi_row.addWidget(card, 0, column)
            kpi_row.setColumnStretch(column, 1)
        layout.addLayout(kpi_row, 0)

        upper_row = QHBoxLayout()
        upper_row.setContentsMargins(0, 0, 0, 0)
        upper_row.setSpacing(12)

        drops_panel = self._build_table_panel('Mayores bajadas por cliente', 'dashboardSalesDropsPanel')
        self.sales_drops_table = QTableWidget(0, 5)
        self.sales_drops_table.setObjectName('dashboardSalesDropsTable')
        self.sales_drops_table.setHorizontalHeaderLabels(['Cliente', 'Isla', 'Kg ant.', 'Kg act.', 'Î” Kg'])
        self._configure_table(self.sales_drops_table)
        drops_header = self.sales_drops_table.horizontalHeader()
        drops_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        drops_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        for col in (2, 3, 4):
            drops_header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        drops_panel.layout().addWidget(self.sales_drops_table)
        upper_row.addWidget(drops_panel, 6)

        islands_panel = self._build_table_panel('Ventas por isla', 'dashboardSalesIslandsPanel')
        self.sales_islands_table = QTableWidget(0, 5)
        self.sales_islands_table.setObjectName('dashboardSalesIslandsTable')
        self.sales_islands_table.setHorizontalHeaderLabels(['Isla', 'Clientes', 'Kg act.', 'Î” Kg', '%'])
        self._configure_table(self.sales_islands_table)
        islands_header = self.sales_islands_table.horizontalHeader()
        islands_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3, 4):
            islands_header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        islands_panel.layout().addWidget(self.sales_islands_table)
        upper_row.addWidget(islands_panel, 4)
        layout.addLayout(upper_row, 1)

        lower_row = QHBoxLayout()
        lower_row.setContentsMargins(0, 0, 0, 0)
        lower_row.setSpacing(12)

        types_panel = self._build_table_panel('Ventas por tipo de cliente', 'dashboardSalesTypesPanel')
        self.sales_types_table = QTableWidget(0, 5)
        self.sales_types_table.setObjectName('dashboardSalesTypesTable')
        self.sales_types_table.setHorizontalHeaderLabels(['Tipo', 'Clientes', 'Kg act.', 'Î” Kg', '%'])
        self._configure_table(self.sales_types_table)
        types_header = self.sales_types_table.horizontalHeader()
        types_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3, 4):
            types_header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        types_panel.layout().addWidget(self.sales_types_table)
        lower_row.addWidget(types_panel, 6)

        zero_panel = self._build_table_panel('Clientes sin consumo actual', 'dashboardSalesZeroPanel')
        self.sales_zero_table = QTableWidget(0, 4)
        self.sales_zero_table.setObjectName('dashboardSalesZeroTable')
        self.sales_zero_table.setHorizontalHeaderLabels(['Cliente', 'Isla', 'Tipo', 'Kg ant.'])
        self._configure_table(self.sales_zero_table)
        zero_header = self.sales_zero_table.horizontalHeader()
        zero_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        zero_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        zero_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        zero_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        zero_panel.layout().addWidget(self.sales_zero_table)
        lower_row.addWidget(zero_panel, 4)
        layout.addLayout(lower_row, 1)
        return widget

    def _build_warehouse_dashboard(self) -> QWidget:
        widget = QWidget()
        widget.setObjectName('dashboardWarehouseView')
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        kpi_row = QGridLayout()
        kpi_row.setHorizontalSpacing(12)
        kpi_row.setVerticalSpacing(12)
        self.warehouse_kpi_labels: dict[str, QLabel] = {}
        self.warehouse_kpi_notes: dict[str, QLabel] = {}
        for column, (key, title, tone, icon_name) in enumerate([
            ('total_stock_kg', 'Stock total', 'blue', 'package.svg'),
            ('risk_items', 'Riesgos', 'red', 'alert.svg'),
            ('entries_month_kg', 'Entradas mes', 'green', 'database-down.svg'),
            ('outputs_month_kg', 'Salidas mes', 'orange', 'database-up.svg'),
        ]):
            card, value_label, _unit_label, note_label = self._build_kpi_card(title, tone, icon_name)
            self.warehouse_kpi_labels[key] = value_label
            self.warehouse_kpi_notes[key] = note_label
            kpi_row.addWidget(card, 0, column)
            kpi_row.setColumnStretch(column, 1)
        layout.addLayout(kpi_row, 0)

        upper_row = QHBoxLayout()
        upper_row.setContentsMargins(0, 0, 0, 0)
        upper_row.setSpacing(12)
        risk_panel = self._build_table_panel('Riesgos de stock y caducidad', 'dashboardWarehouseRiskPanel')
        self.warehouse_risk_table = QTableWidget(0, 7)
        self.warehouse_risk_table.setObjectName('dashboardWarehouseRiskTable')
        self.warehouse_risk_table.setHorizontalHeaderLabels(['Almacén', 'Ref.', 'Producto', 'Lote', 'Caduca', 'Kg', 'Estado'])
        self._configure_table(self.warehouse_risk_table)
        risk_header = self.warehouse_risk_table.horizontalHeader()
        risk_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        risk_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        risk_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for col in (3, 4, 5, 6):
            risk_header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        risk_panel.layout().addWidget(self.warehouse_risk_table)
        upper_row.addWidget(risk_panel, 6)

        stock_panel = self._build_table_panel('Stock por almacén', 'dashboardWarehouseStockPanel')
        self.warehouse_stock_table = QTableWidget(0, 3)
        self.warehouse_stock_table.setObjectName('dashboardWarehouseStockTable')
        self.warehouse_stock_table.setHorizontalHeaderLabels(['Almacén', 'Artículos', 'Stock kg'])
        self._configure_table(self.warehouse_stock_table)
        stock_header = self.warehouse_stock_table.horizontalHeader()
        stock_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        stock_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        stock_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        stock_panel.layout().addWidget(self.warehouse_stock_table)
        upper_row.addWidget(stock_panel, 4)
        layout.addLayout(upper_row, 1)

        lower_row = QHBoxLayout()
        lower_row.setContentsMargins(0, 0, 0, 0)
        lower_row.setSpacing(12)
        entries_panel = self._build_table_panel('Entradas del mes', 'dashboardWarehouseEntriesPanel')
        self.warehouse_entries_table = QTableWidget(0, 5)
        self.warehouse_entries_table.setObjectName('dashboardWarehouseEntriesTable')
        self.warehouse_entries_table.setHorizontalHeaderLabels(['Fecha', 'Almacén', 'Ref.', 'Producto', 'Kg'])
        self._configure_table(self.warehouse_entries_table)
        entries_header = self.warehouse_entries_table.horizontalHeader()
        entries_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        entries_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        entries_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        entries_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        entries_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        entries_panel.layout().addWidget(self.warehouse_entries_table)
        lower_row.addWidget(entries_panel, 5)

        outputs_panel = self._build_table_panel('Salidas del mes', 'dashboardWarehouseOutputsPanel')
        self.warehouse_outputs_table = QTableWidget(0, 5)
        self.warehouse_outputs_table.setObjectName('dashboardWarehouseOutputsTable')
        self.warehouse_outputs_table.setHorizontalHeaderLabels(['Fecha', 'Almacén', 'Ref.', 'Producto', 'Kg'])
        self._configure_table(self.warehouse_outputs_table)
        outputs_header = self.warehouse_outputs_table.horizontalHeader()
        outputs_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        outputs_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        outputs_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        outputs_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        outputs_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        outputs_panel.layout().addWidget(self.warehouse_outputs_table)
        lower_row.addWidget(outputs_panel, 5)
        layout.addLayout(lower_row, 1)
        return widget

    def reload(self) -> None:
        if self.current_dashboard == 'pedidos':
            self._reload_orders_dashboard()
        elif self.current_dashboard == 'almacen':
            self._reload_warehouse_dashboard()
        elif self.current_dashboard == 'ventas':
            self._reload_sales_dashboard()
        else:
            self._reload_agenda_dashboard()
    def _reload_agenda_dashboard(self) -> None:
        snapshot = self.dashboard_service.load_snapshot()
        activity_rows = self.dashboard_service.list_all_activities()
        self.date_label.setText(self.format_date(date.today(), long=True))
        self.kpi_labels['pending_today'].setText(str(snapshot.pending_today))
        self.kpi_notes['pending_today'].setText('actividades')
        self.kpi_labels['overdue'].setText(str(snapshot.overdue))
        self.kpi_notes['overdue'].setText('actividades')
        self.kpi_labels['completed_today'].setText(str(snapshot.completed_today))
        self.kpi_notes['completed_today'].setText('actividades')
        self.kpi_labels['customers_without_follow_up'].setText(str(snapshot.customers_without_follow_up))
        self.kpi_notes['customers_without_follow_up'].setText('clientes')
        if self.agenda_calendar_week_range is None:
            self._reload_today_panel(activity_rows, self.agenda_calendar_selected_date)
        else:
            week_start, week_end = self.agenda_calendar_week_range
            self._reload_week_panel(activity_rows, week_start, week_end)
        self._reload_reactivation_table(snapshot.reactivation_rows)
        self._reload_island_table(snapshot.island_rows)
        self._reload_agenda_calendar_panel(activity_rows, today_value=date.today())
        self.footer_label.setText(
            f'Última actualización: {snapshot.generated_at.strftime("%d/%m/%Y %H:%M")} · {snapshot.reactivation_metric_label}'
        )

    def _reload_today_panel(self, rows: list[DashboardActivityRow], selected_day: date) -> None:
        self._clear_today_items()
        self.today_panel_title.setText('Agenda de hoy' if selected_day == date.today() else f'Agenda del {self.format_date(selected_day)}')
        filtered = [row for row in rows if row.due_date == selected_day]
        self._render_activity_cards(filtered, empty_text='No hay actividades para el día seleccionado.')

    def _reload_week_panel(self, rows: list[DashboardActivityRow], week_start: date, week_end: date) -> None:
        self._clear_today_items()
        week_number = week_start.isocalendar().week
        self.today_panel_title.setText(
            f'Agenda semana {week_number} · {self.format_date(week_start)} - {self.format_date(week_end)}'
        )
        filtered = [row for row in rows if week_start <= row.due_date <= week_end]
        self._render_activity_cards(filtered, empty_text='No hay actividades para la semana seleccionada.')

    def _clear_today_items(self) -> None:
        while self.today_items_layout.count():
            item = self.today_items_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _render_activity_cards(self, rows: list[DashboardActivityRow], *, empty_text: str) -> None:
        self.today_report_rows = list(rows)
        has_rows = bool(self.today_report_rows)
        self.today_pdf_btn.setEnabled(has_rows)
        self.today_print_btn.setEnabled(has_rows)
        if not rows:
            empty = QLabel(empty_text)
            empty.setObjectName('dashboardEmptyLabel')
            empty.setWordWrap(True)
            empty.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            self.today_items_layout.addWidget(empty)
            return
        for row in rows:
            card = DashboardActivityCard(row.agenda_id)
            card.setToolTip('Clic derecho para editar la actividad')
            card.editRequested.connect(self._edit_dashboard_activity)
            layout = QHBoxLayout(card)
            layout.setContentsMargins(10, 10, 10, 10)
            layout.setSpacing(12)
            customer = QLabel(f'{row.cliente_codigo} · {row.cliente_nombre}')
            customer.setObjectName('dashboardActivityCustomer')
            customer.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
            summary = QLabel(row.resumen or row.detalle or '-')
            summary.setObjectName('dashboardActivitySummary')
            summary.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            state = QLabel(self.agenda_state_label(row.estado))
            state.setObjectName('dashboardActivityState')
            state.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            state.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
            for label in (customer, summary, state):
                label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            layout.addWidget(customer, 0)
            layout.addWidget(summary, 1)
            layout.addWidget(state, 0)
            self.today_items_layout.addWidget(card)

    def _today_report_data(self) -> tuple[str, list[str], list[list[str]]]:
        title = self.today_panel_title.text().strip() or 'Agenda'
        rows = [
            [
                self.format_date(row.due_date),
                f'{row.cliente_codigo} · {row.cliente_nombre}',
                self._agenda_event_content(row),
                self.agenda_state_label(row.estado),
            ]
            for row in self.today_report_rows
        ]
        return title, ['Fecha', 'Cliente', 'Contenido', 'Estado'], rows

    @staticmethod
    def _agenda_event_content(row: DashboardActivityRow) -> str:
        summary = str(row.resumen or '').strip()
        detail = str(row.detalle or '').strip()
        if summary and detail and summary.casefold() != detail.casefold():
            return f'{summary} — {detail}'
        return summary or detail or '-'

    def _export_today_panel_pdf(self) -> None:
        if not self.today_report_rows:
            QMessageBox.warning(self, 'Agenda', 'No hay actividades para exportar.')
            return
        title, headers, rows = self._today_report_data()
        try:
            dialog = DashboardAgendaPdfPreviewDialog(
                report_export_service=self.report_export_service,
                title=title,
                headers=headers,
                rows=rows,
                parent=self,
            )
        except Exception as exc:
            QMessageBox.warning(self, 'Agenda', f'No se pudo generar la vista previa del PDF.\n\n{exc}')
            return
        dialog.exec()

    def _print_today_panel(self) -> None:
        if not self.today_report_rows:
            QMessageBox.warning(self, 'Agenda', 'No hay actividades para imprimir.')
            return
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageOrientation(QPageLayout.Orientation.Portrait)
        dialog = QPrintDialog(printer, self)
        if dialog.exec() != QPrintDialog.DialogCode.Accepted:
            return
        document = QTextDocument(self)
        document.setHtml(self._today_report_html())
        document.print_(printer)

    def _today_report_html(self) -> str:
        title, _headers, rows = self._today_report_data()
        cards = ''.join(
            '<table class="card" width="100%" cellspacing="0" cellpadding="0">'
            '<tr class="top">'
            f'<td class="date">{escape(str(row[0]))}</td>'
            f'<td class="customer">{escape(str(row[1]))}</td>'
            f'<td class="state {ReportExportService.agenda_state_tone(row[3])}" align="right">{escape(str(row[3]))}</td>'
            '</tr>'
            f'<tr><td class="content" colspan="3">{escape(str(row[2])).replace(chr(10), "<br/>")}</td></tr>'
            '</table><div class="gap"></div>'
            for row in rows
        )
        return (
            '<html><head><style>'
            'body { font-family: "Segoe UI", sans-serif; color: #0F172A; }'
            'h1 { font-size: 18px; margin-bottom: 14px; }'
            '.card { width: 100%; border: 1px solid #CBD5E1; background: #F8FAFC; page-break-inside: avoid; }'
            '.card td { padding: 7px 9px; font-size: 10px; }'
            '.top td { padding-bottom: 4px; }'
            '.date { width: 16%; color: #334155; font-weight: 600; }'
            '.customer { color: #0F172A; font-weight: 700; }'
            '.state { width: 16%; color: #475569; background: #F1F5F9; font-weight: 700; }'
            '.state.pending { color: #1D4ED8; background: #DBEAFE; }'
            '.state.completed { color: #15803D; background: #DCFCE7; }'
            '.state.postponed { color: #C2410C; background: #FFEDD5; }'
            '.state.cancelled { color: #B91C1C; background: #FEE2E2; }'
            '.content { padding-top: 4px; color: #1E293B; }'
            '.gap { height: 7px; }'
            '</style></head><body>'
            f'<h1>{escape(title)}</h1>{cards}</body></html>'
        )

    def _reload_reactivation_table(self, rows: list[DashboardReactivationRow]) -> None:
        self.reactivation_table.setRowCount(len(rows))
        for idx, row in enumerate(rows):
            values = [
                f'{row.cliente_codigo} · {row.cliente_nombre}',
                row.isla_nombre,
                self.format_date(row.last_contact) if row.last_contact else 'Sin registro',
                self._format_number_es(row.delta_kg, suffix=' kg', signed=True),
                row.priority,
            ]
            for col, value in enumerate(values):
                self.reactivation_table.setItem(idx, col, QTableWidgetItem(value))

    def _reload_island_table(self, rows: list[DashboardIslandRow]) -> None:
        self.island_table.setRowCount(len(rows))
        for idx, row in enumerate(rows):
            values = [row.isla_nombre, str(row.pending), str(row.postponed), str(row.completed), str(row.total)]
            for col, value in enumerate(values):
                self.island_table.setItem(idx, col, QTableWidgetItem(value))

    def _reload_agenda_calendar_panel(self, rows: list[DashboardActivityRow], *, today_value: date) -> None:
        self.agenda_calendar_rows = list(rows)
        month_start = self.agenda_calendar_month.replace(day=1)
        self.agenda_month_calendar.blockSignals(True)
        self.agenda_month_calendar.setCurrentPage(month_start.year, month_start.month)
        if self.agenda_calendar_selected_date.year == month_start.year and self.agenda_calendar_selected_date.month == month_start.month:
            selected = self.agenda_calendar_selected_date
        else:
            selected = today_value if today_value.year == month_start.year and today_value.month == month_start.month else month_start
            self.agenda_calendar_selected_date = selected
        self.agenda_month_calendar.setSelectedDate(QDate(selected.year, selected.month, selected.day))
        self.agenda_month_calendar.blockSignals(False)
        self._refresh_agenda_calendar(today_value=today_value)

    def _refresh_agenda_calendar(self, *, today_value: date) -> None:
        month_start = self.agenda_calendar_month.replace(day=1)
        month_rows = [
            row for row in self.agenda_calendar_rows
            if row.due_date.year == month_start.year and row.due_date.month == month_start.month
        ]
        pending = 0
        done = 0
        overdue = 0
        for row in month_rows:
            state_group = self._state_group(row.estado)
            if state_group == 'completed':
                done += 1
            elif row.due_date < today_value and state_group not in {'completed', 'cancelled'}:
                overdue += 1
            elif state_group != 'cancelled':
                pending += 1
        self.pending_summary[1].setText(str(pending))
        self.done_summary[1].setText(str(done))
        self.overdue_summary[1].setText(str(overdue))
        self.agenda_month_calendar.updateCells()

    def _handle_agenda_calendar_selection_changed(self) -> None:
        selected = self.agenda_month_calendar.selectedDate()
        self.set_selected_date(date(selected.year(), selected.month(), selected.day()))

    def _handle_agenda_calendar_week_selected(self, week_start: date, week_end: date, _week_number: int) -> None:
        self.agenda_calendar_week_range = (week_start, week_end)
        self._reload_week_panel(self.dashboard_service.list_all_activities(), week_start, week_end)

    def _handle_agenda_calendar_page_changed(self, year: int, month: int) -> None:
        self.agenda_calendar_month = date(year, month, 1)
        self._refresh_agenda_calendar(today_value=date.today())

    def set_selected_date(self, selected_day: date) -> None:
        self.agenda_calendar_week_range = None
        self.agenda_calendar_selected_date = selected_day
        self._reload_today_panel(self.dashboard_service.list_all_activities(), selected_day)
        self._reload_agenda_calendar_panel(self.dashboard_service.list_all_activities(), today_value=date.today())

    def _handle_primary_action(self) -> None:
        if self.current_dashboard == 'pedidos':
            self._open_orders_page()
            return
        if self.current_dashboard == 'almacen':
            self._open_warehouse_page()
            return
        if self.current_dashboard == 'ventas':
            self._open_sales_page()
            return
        self._open_new_activity()
    def _handle_secondary_action(self) -> None:
        if self.current_dashboard in {'pedidos', 'almacen', 'ventas'}:
            self.reload()
            return
        self._open_full_agenda()
    def _set_dashboard_mode(self, mode: str, *, reload: bool = True) -> None:
        clean_mode = mode if mode in {'agenda', 'pedidos', 'almacen', 'ventas'} else 'agenda'
        self.current_dashboard = clean_mode
        for key, button in self.dashboard_nav_buttons.items():
            active = key == clean_mode
            button.setProperty('active', active)
            if key == 'agenda':
                icon_name = 'calendar-days.svg'
            elif key == 'pedidos':
                icon_name = 'shopping-cart.svg'
            elif key == 'almacen':
                icon_name = 'warehouse.svg'
            else:
                icon_name = 'bar-chart-3.svg'
            self._set_button_icon(button, icon_name, '#FFFFFF' if active else '#475569', 20)
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()
        if clean_mode == 'agenda':
            current_widget = self.agenda_dashboard
        elif clean_mode == 'pedidos':
            current_widget = self.orders_dashboard
        elif clean_mode == 'almacen':
            current_widget = self.warehouse_dashboard
        else:
            current_widget = self.sales_dashboard
        self.dashboard_stack.setCurrentWidget(current_widget)
        self._refresh_header_for_mode()
        if reload:
            self.reload()
    def _refresh_header_for_mode(self) -> None:
        if self.current_dashboard == 'pedidos':
            self.title_label.setText('Pedidos')
            self.date_label.setText(str(date.today().year))
            self.new_activity_btn.setText('Ver pedidos')
            self.full_agenda_btn.setText('Actualizar')
            self._set_button_icon(self.new_activity_btn, 'shopping-cart.svg', '#FFFFFF', 18)
            self._set_button_icon(self.full_agenda_btn, 'clipboard-list.svg', '#2563EB', 18)
        elif self.current_dashboard == 'almacen':
            self.title_label.setText('Almacen')
            self.date_label.setText(self._month_caption(date.today()))
            self.new_activity_btn.setText('Ver almacen')
            self.full_agenda_btn.setText('Actualizar')
            self._set_button_icon(self.new_activity_btn, 'warehouse.svg', '#FFFFFF', 18)
            self._set_button_icon(self.full_agenda_btn, 'package-search.svg', '#2563EB', 18)
        elif self.current_dashboard == 'ventas':
            self.title_label.setText('Ventas')
            self.date_label.setText(str(date.today().year))
            self.new_activity_btn.setText('Ver ventas')
            self.full_agenda_btn.setText('Actualizar')
            self._set_button_icon(self.new_activity_btn, 'bar-chart-3.svg', '#FFFFFF', 18)
            self._set_button_icon(self.full_agenda_btn, 'clipboard-list.svg', '#2563EB', 18)
        else:
            self.title_label.setText('Agenda')
            self.date_label.setText(self.format_date(date.today(), long=True))
            self.new_activity_btn.setText('Nueva actividad')
            self.full_agenda_btn.setText('Ver agenda completa')
            self._set_button_icon(self.new_activity_btn, 'plus.svg', '#FFFFFF', 18)
            self._set_button_icon(self.full_agenda_btn, 'calendar.svg', '#2563EB', 18)
    def _reload_orders_dashboard(self) -> None:
        snapshot = self.order_dashboard_service.load_snapshot()
        self.date_label.setText(str(snapshot.year))
        self.orders_kpi_labels['total_orders'].setText(str(snapshot.total_orders))
        self.orders_kpi_notes['total_orders'].setText('pedido(s)')
        self.orders_kpi_labels['received_kg'].setText(self._format_number_es(snapshot.received_kg))
        self.orders_kpi_units['received_kg'].setText('kg')
        self.orders_kpi_units['received_kg'].setVisible(True)
        self.orders_kpi_notes['received_kg'].setText('kg recibidos')
        self.orders_kpi_labels['pending_kg'].setText(self._format_number_es(snapshot.pending_kg))
        self.orders_kpi_units['pending_kg'].setText('kg')
        self.orders_kpi_units['pending_kg'].setVisible(True)
        self.orders_kpi_notes['pending_kg'].setText('kg pendientes')
        self.orders_kpi_labels['incident_orders'].setText(str(snapshot.incident_orders))
        self.orders_kpi_notes['incident_orders'].setText('pedido(s)')
        self._populate_order_recent_table(snapshot.recent_orders)
        self._populate_order_pending_table(snapshot.pending_orders)
        self.orders_top_articles_donut.set_rows(snapshot.top_articles)
        self._populate_order_warehouse_table(snapshot.warehouse_rows)
        self._populate_order_state_table(snapshot.state_rows)
        self.footer_label.setText(
            f'Última actualización: {snapshot.generated_at.strftime("%d/%m/%Y %H:%M")} · Dashboard pedidos {snapshot.year}'
        )

    def _populate_order_recent_table(self, rows: list[DashboardOrderRow]) -> None:
        self.orders_recent_table.setRowCount(len(rows))
        for idx, row in enumerate(rows):
            values = [
                row.pedido_numero,
                row.almacen_nombre or row.almacen_id,
                str(row.semana),
                self.format_date(row.pedido_fecha),
                self._format_number_es(row.ordered_kg, suffix=' kg'),
                self._format_number_es(row.received_kg, suffix=' kg'),
                self._format_number_es(row.pending_kg, suffix=' kg'),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, row.pedido_id)
                if col in (4, 5, 6):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.orders_recent_table.setItem(idx, col, item)

    def _populate_order_pending_table(self, rows: list[DashboardPendingArticleRow]) -> None:
        self.orders_pending_table.setSortingEnabled(False)
        self.orders_pending_table.setRowCount(len(rows))
        for idx, row in enumerate(rows):
            values = [
                self.format_date(row.pedido_fecha),
                row.pedido_numero,
                row.articulo_label,
                self._format_number_es(row.pending_kg, suffix=' kg'),
            ]
            for col, value in enumerate(values):
                if col == 0:
                    item = DashboardSortableItem(value, row.pedido_fecha)
                elif col == 2:
                    item = QTableWidgetItem(row.article_name)
                elif col == 3:
                    item = DashboardSortableItem(value, row.pending_kg)
                else:
                    item = QTableWidgetItem(value)
                if col == 3:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.orders_pending_table.setItem(idx, col, item)
        self.orders_pending_table.setSortingEnabled(True)
        self.orders_pending_table.sortItems(0, Qt.SortOrder.DescendingOrder)

    def _populate_order_warehouse_table(self, rows: list[DashboardOrdersWarehouseRow]) -> None:
        self.orders_warehouse_table.setRowCount(len(rows))
        for idx, row in enumerate(rows):
            values = [
                row.almacen_nombre or row.almacen_id,
                str(row.open_orders),
                self._format_number_es(row.pending_kg, suffix=' kg'),
                self.format_date(row.last_receipt),
            ]
            for col, value in enumerate(values):
                self.orders_warehouse_table.setItem(idx, col, QTableWidgetItem(value))

    def _populate_order_state_table(self, rows: list[DashboardOrdersStateRow]) -> None:
        self.orders_state_table.setRowCount(len(rows))
        for idx, row in enumerate(rows):
            values = [row.status, str(row.count), self._format_number_es(row.kg, suffix=' kg')]
            for col, value in enumerate(values):
                self.orders_state_table.setItem(idx, col, QTableWidgetItem(value))




    def _reload_sales_dashboard(self) -> None:
        snapshot = self.sales_dashboard_service.load_snapshot()
        self.date_label.setText(f'{snapshot.year} vs {snapshot.previous_year}')
        self.sales_kpi_labels['total_kg'].setText(self._format_number_es(snapshot.total_kg))
        self.sales_kpi_notes['total_kg'].setText(f'kg vendidos en {snapshot.year}')
        self.sales_kpi_labels['delta_kg'].setText(self._format_number_es(snapshot.delta_kg, signed=True))
        self.sales_kpi_notes['delta_kg'].setText(f'vs {snapshot.previous_year} · {self._format_number_es(snapshot.delta_pct, signed=True, suffix=" %")}')
        self.sales_kpi_labels['active_customers'].setText(str(snapshot.active_customers))
        self.sales_kpi_notes['active_customers'].setText('clientes activos')
        self.sales_kpi_labels['active_islands'].setText(str(snapshot.active_islands))
        self.sales_kpi_notes['active_islands'].setText('islas activas')
        delta_color = '#16A34A' if snapshot.delta_kg >= 0.0 else '#DC2626'
        self.sales_kpi_labels['delta_kg'].setStyleSheet(f'color: {delta_color}; font-size: 28px; font-weight: 800;')
        self.sales_kpi_notes['delta_kg'].setStyleSheet(f'color: {delta_color}; font-size: 13px; font-weight: 600;')
        self._populate_sales_drops_table(snapshot.customer_drop_rows)
        self._populate_sales_islands_table(snapshot.island_rows)
        self._populate_sales_types_table(snapshot.type_rows)
        self._populate_sales_zero_table(snapshot.zero_consumption_rows)
        self.footer_label.setText(
            f'Última actualización: {snapshot.generated_at.strftime("%d/%m/%Y %H:%M")} · Ventas {snapshot.year} vs {snapshot.previous_year}'
        )

    def _populate_sales_drops_table(self, rows: list[DashboardSalesCustomerRow]) -> None:
        self.sales_drops_table.setRowCount(len(rows))
        for idx, row in enumerate(rows):
            values = [
                f'{row.cliente_codigo} · {row.cliente_nombre}',
                row.isla,
                self._format_number_es(row.kg_prev, suffix=' kg'),
                self._format_number_es(row.kg_curr, suffix=' kg'),
                self._format_number_es(row.delta_kg, suffix=' kg', signed=True),
            ]
            for col, value in enumerate(values):
                self.sales_drops_table.setItem(idx, col, QTableWidgetItem(value))

    def _populate_sales_islands_table(self, rows: list[DashboardSalesIslandRow]) -> None:
        self.sales_islands_table.setRowCount(len(rows))
        for idx, row in enumerate(rows):
            values = [
                row.isla,
                str(row.customers),
                self._format_number_es(row.kg_curr, suffix=' kg'),
                self._format_number_es(row.delta_kg, suffix=' kg', signed=True),
                self._format_number_es(row.share_pct, suffix=' %'),
            ]
            for col, value in enumerate(values):
                self.sales_islands_table.setItem(idx, col, QTableWidgetItem(value))

    def _populate_sales_types_table(self, rows: list[DashboardSalesTypeRow]) -> None:
        self.sales_types_table.setRowCount(len(rows))
        for idx, row in enumerate(rows):
            values = [
                row.cliente_tipo,
                str(row.customers),
                self._format_number_es(row.kg_curr, suffix=' kg'),
                self._format_number_es(row.delta_kg, suffix=' kg', signed=True),
                self._format_number_es(row.share_pct, suffix=' %'),
            ]
            for col, value in enumerate(values):
                self.sales_types_table.setItem(idx, col, QTableWidgetItem(value))

    def _populate_sales_zero_table(self, rows: list[DashboardSalesCustomerRow]) -> None:
        self.sales_zero_table.setRowCount(len(rows))
        for idx, row in enumerate(rows):
            values = [
                f'{row.cliente_codigo} · {row.cliente_nombre}',
                row.isla,
                row.cliente_tipo,
                self._format_number_es(row.kg_prev, suffix=' kg'),
            ]
            for col, value in enumerate(values):
                self.sales_zero_table.setItem(idx, col, QTableWidgetItem(value))

    def _reload_warehouse_dashboard(self) -> None:
        snapshot = self.warehouse_dashboard_service.load_snapshot()
        self.date_label.setText(self._month_caption(date(snapshot.year, snapshot.month, 1)))
        self.warehouse_kpi_labels['total_stock_kg'].setText(self.format_kg(snapshot.total_stock_kg))
        self.warehouse_kpi_notes['total_stock_kg'].setText('kg netos')
        self.warehouse_kpi_labels['risk_items'].setText(str(snapshot.risk_items))
        self.warehouse_kpi_notes['risk_items'].setText('lote(s)')
        self.warehouse_kpi_labels['entries_month_kg'].setText(self.format_kg(snapshot.entries_month_kg))
        self.warehouse_kpi_notes['entries_month_kg'].setText('kg entrados')
        self.warehouse_kpi_labels['outputs_month_kg'].setText(self.format_kg(snapshot.outputs_month_kg))
        self.warehouse_kpi_notes['outputs_month_kg'].setText('kg salidos')
        self._populate_warehouse_risk_table(snapshot.risk_rows)
        self._populate_warehouse_stock_table(snapshot.warehouse_rows)
        self._populate_warehouse_movement_table(self.warehouse_entries_table, snapshot.entry_rows)
        self._populate_warehouse_movement_table(self.warehouse_outputs_table, snapshot.output_rows)
        self.footer_label.setText(f'Última actualización: {snapshot.generated_at.strftime("%d/%m/%Y %H:%M")} · umbral bajo stock: {self._format_number_es(snapshot.low_stock_threshold_units)} uds.')



    def _populate_warehouse_risk_table(self, rows: list[DashboardWarehouseRiskRow]) -> None:
        self.warehouse_risk_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [row.almacen_nombre, row.referencia, row.nombre, row.lote, self.format_date(row.caducidad) if row.caducidad else '-', self.format_kg(row.stock_kg), row.state]
            for column, value in enumerate(values):
                self.warehouse_risk_table.setItem(row_index, column, QTableWidgetItem(value))



    def _populate_warehouse_stock_table(self, rows: list[DashboardWarehouseStockRow]) -> None:
        self.warehouse_stock_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column, value in enumerate([row.almacen_nombre, str(row.article_count), self.format_kg(row.stock_kg)]):
                self.warehouse_stock_table.setItem(row_index, column, QTableWidgetItem(value))



    def _populate_warehouse_movement_table(self, table: QTableWidget, rows: list[DashboardWarehouseMovementRow]) -> None:
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [self.format_date(row.fecha), row.almacen_nombre, row.referencia, row.nombre, self.format_kg(row.kg)]
            for column, value in enumerate(values):
                table.setItem(row_index, column, QTableWidgetItem(value))

    def _recent_order_id_for_row(self, row_index: int) -> str:
        if row_index < 0 or row_index >= self.orders_recent_table.rowCount():
            return ''
        item = self.orders_recent_table.item(row_index, 0)
        return str(item.data(Qt.ItemDataRole.UserRole) or '').strip() if item is not None else ''

    def _show_orders_recent_context_menu(self, pos) -> None:
        index = self.orders_recent_table.indexAt(pos)
        if not index.isValid():
            return
        row_index = index.row()
        self.orders_recent_table.selectRow(row_index)
        pedido_id = self._recent_order_id_for_row(row_index)
        if not pedido_id:
            return

        menu = QMenu(self)
        action_view = menu.addAction('Ver pedido')
        chosen = menu.exec(self.orders_recent_table.viewport().mapToGlobal(pos))
        if chosen == action_view:
            self._open_order_from_dashboard(pedido_id)

    def _open_orders_page(self) -> None:
        window = self.window()
        page_names = getattr(window, 'page_names', None)
        setter = getattr(window, '_set_current_page', None)
        if isinstance(page_names, list) and callable(setter) and 'Pedidos' in page_names:
            setter(page_names.index('Pedidos'))
            return
        QMessageBox.information(self, 'Pedidos', 'La vista completa de pedidos no est? disponible desde este contexto.')

    def _open_order_from_dashboard(self, pedido_id: str) -> None:
        clean_pedido_id = str(pedido_id or '').strip()
        if not clean_pedido_id:
            return
        window = self.window()
        page_names = getattr(window, 'page_names', None)
        pages = getattr(window, 'pages', None)
        setter = getattr(window, '_set_current_page', None)
        if not (isinstance(page_names, list) and callable(setter) and 'Pedidos' in page_names):
            QMessageBox.information(self, 'Pedidos', 'La vista completa de pedidos no est? disponible desde este contexto.')
            return

        page_index = page_names.index('Pedidos')
        setter(page_index)
        orders_page = pages.widget(page_index) if pages is not None and hasattr(pages, 'widget') else None
        selector = getattr(orders_page, '_select_by_id', None)
        if callable(selector):
            selector(clean_pedido_id)
            return
        QMessageBox.information(self, 'Pedidos', 'No se pudo seleccionar el pedido en la vista de Pedidos.')



    def _open_warehouse_page(self) -> None:
        window = self.window()
        page_names = getattr(window, 'page_names', None)
        setter = getattr(window, '_set_current_page', None)
        if isinstance(page_names, list) and callable(setter) and 'Almacen' in page_names:
            setter(page_names.index('Almacen'))
            return
        QMessageBox.information(self, 'Dashboard', 'La página de Almacén no está disponible en esta ventana.')


    def customer_choices(self, *, include_inactive: bool = False) -> list[tuple[str, str]]:
        rows = self.customer_service.list('')
        out: list[tuple[str, str]] = []
        for row in rows:
            if not include_inactive and getattr(row, 'activo', True) in {False, 0, '0', 'false', 'False'}:
                continue
            customer_id = str(getattr(row, 'cliente_id', '') or '').strip()
            if not customer_id:
                continue
            label = self.customer_label(getattr(row, 'cliente_codigo', ''), str(getattr(row, 'cliente_nombre_comercial', '') or getattr(row, 'cliente_nombre_fiscal', '') or customer_id))
            out.append((customer_id, label))
        return out

    @staticmethod
    def agenda_type_options() -> list[tuple[str, str]]:
        return [
            ('visita_prevista', 'Visita prevista'),
            ('visita_realizada', 'Visita realizada'),
            ('llamada', 'Llamada'),
            ('seguimiento', 'Seguimiento'),
            ('desarrollo_futuro', 'Desarrollo futuro'),
            ('incidencia', 'Incidencia'),
            ('nota', 'Nota'),
        ]

    @staticmethod
    def agenda_state_options() -> list[tuple[str, str]]:
        return [('pendiente', 'Pendiente'), ('hecho', 'Hecha'), ('aplazado', 'Aplazada'), ('cancelado', 'Cancelada')]

    def agenda_type_label(self, value: str) -> str:
        return dict(self.agenda_type_options()).get(str(value or '').strip().lower(), str(value or '').strip() or 'Nota')

    def agenda_state_label(self, value: str) -> str:
        return dict(self.agenda_state_options()).get(str(value or '').strip().lower(), str(value or '').strip() or 'Pendiente')

    def qdate_from_value(self, value: object, *, fallback_today: bool = False) -> QDate:
        if isinstance(value, QDate):
            return value
        if hasattr(value, 'year') and hasattr(value, 'month') and hasattr(value, 'day'):
            return QDate(int(value.year), int(value.month), int(value.day))
        parsed = QDate.fromString(str(value or ''), 'yyyy-MM-dd')
        if parsed.isValid():
            return parsed
        return QDate.currentDate() if fallback_today else QDate()

    def configure_dashboard_calendar(self, date_edit: QDateEdit) -> None:
        date_edit.setCalendarPopup(True)
        date_edit.setDisplayFormat('dd/MM/yyyy')
        calendar = date_edit.calendarWidget()
        if calendar is not None:
            calendar.setObjectName('dashboardPopupCalendar')

    @staticmethod
    def customer_label(code: object, name: str) -> str:
        code_text = str(code or '').strip()
        name_text = str(name or '').strip()
        return f'{code_text} · {name_text}' if code_text else name_text

    def _open_new_activity(self) -> None:
        if not self.customer_choices():
            QMessageBox.warning(self, 'Agenda', 'No hay clientes disponibles para registrar actividades.')
            return
        dialog = DashboardAgendaDialog(self, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.reload()

    def _open_full_agenda(self) -> None:
        dialog = DashboardAgendaOverviewDialog(self, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.changed:
            self.reload()
        elif dialog.changed:
            self.reload()

    def _open_activity_dialog(self, *, agenda_id: str = '', default_customer_id: str = '') -> None:
        dialog = DashboardAgendaDialog(self, agenda_id=agenda_id, default_customer_id=default_customer_id, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.reload()

    def _edit_dashboard_activity(self, agenda_id: str) -> None:
        self._open_activity_dialog(agenda_id=agenda_id)

    def _show_placeholder_dashboard(self, name: str) -> None:
        QMessageBox.information(self, 'Dashboard', f'El dashboard de {name} se implementará en una siguiente fase.')

    def _open_sales_page(self) -> None:
        window = self.window()
        page_names = getattr(window, 'page_names', None)
        setter = getattr(window, '_set_current_page', None)
        if isinstance(page_names, list) and callable(setter) and 'Ventas' in page_names:
            setter(page_names.index('Ventas'))
            return
        QMessageBox.information(self, 'Dashboard', 'La página de Ventas no está disponible en esta ventana.')



    @staticmethod
    def _month_caption(value: date) -> str:
        months = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
        return f"{months[value.month - 1].capitalize()} {value.year}"



    @classmethod
    def format_kg(cls, value: float, *, signed: bool = False, suffix: str = ' kg') -> str:
        return cls._format_number_es(value, suffix=suffix, signed=signed)

    def _agenda_rows_for_date(self, day_value: date) -> list[DashboardActivityRow]:
        return [row for row in self.agenda_calendar_rows if row.due_date == day_value]

    def _agenda_day_tone(self, rows: list[DashboardActivityRow], *, today_value: date) -> str | None:
        if not rows:
            return None
        if any(self._state_group(row.estado) == 'completed' for row in rows):
            return 'green'
        if any(row.due_date < today_value and self._state_group(row.estado) not in {'completed', 'cancelled'} for row in rows):
            return 'red'
        return 'blue'

    @staticmethod
    def _state_group(state: str) -> str:
        normalized = str(state or '').strip().lower()
        if normalized in {'hecho', 'completada', 'completado'}:
            return 'completed'
        if normalized in {'cancelado', 'cancelada'}:
            return 'cancelled'
        return normalized or 'pending'

    @staticmethod
    def format_date(value: date | None, *, long: bool = False, allow_blank: bool = False) -> str:
        if value is None:
            return '' if allow_blank else ''
        if long:
            months = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
            weekdays = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
            return f"{weekdays[value.weekday()]}, {value.day:02d} de {months[value.month - 1]} de {value.year}"
        return value.strftime('%d/%m/%Y')

    @staticmethod
    def _format_number_es(value: float, *, suffix: str = '', signed: bool = False) -> str:
        number = float(value or 0.0)
        fmt = f'{{:{"+" if signed else ""},.2f}}'.format(number)
        fmt = fmt.replace(',', '_').replace('.', ',').replace('_', '.')
        return f'{fmt}{suffix}'

    @staticmethod
    def _tone_color(tone: str) -> str:
        return {
            'blue': '#2563EB',
            'red': '#EF4444',
            'green': '#16A34A',
            'orange': '#F97316',
        }.get(tone, '#2563EB')

    @staticmethod
    def _icon_path(asset_name: str) -> Path:
        return BASE_DIR / 'assets' / 'icons' / asset_name

    def _icon_pixmap(self, asset_name: str, color: str, size: int) -> QPixmap:
        path = self._icon_path(asset_name)
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        if not path.exists():
            return pixmap
        renderer = QSvgRenderer(str(path))
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor(color))
        painter.end()
        return pixmap

    def _set_button_icon(self, button: QPushButton, asset_name: str, color: str, size: int) -> None:
        button.setIcon(QIcon(self._icon_pixmap(asset_name, color, size)))
        button.setIconSize(QSize(size, size))

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget#dashboardPageRoot { background-color: #EEF3F8; font-family: "Segoe UI"; }
            QFrame#dashboardSidebar { background-color: #F8FAFC; border-right: 1px solid #E2E8F0; }
            QLabel#dashboardSidebarBrand { background-color: transparent; padding: 8px 0 6px 0; }
            QPushButton#dashboardSidebarButton {
                background-color: transparent;
                color: #334155;
                border: none;
                border-radius: 16px;
                padding: 14px 16px;
                font-size: 15px;
                font-weight: 600;
                text-align: left;
            }
            QPushButton#dashboardSidebarButton[active="true"] {
                background-color: #2563EB;
                color: #FFFFFF;
            }
            QWidget#dashboardContentHost, QWidget#dashboardContent, QWidget#dashboardAgendaView, QWidget#dashboardOrdersView, QWidget#dashboardWarehouseView, QWidget#dashboardSalesView { background-color: transparent; }
            QStackedWidget#dashboardContentStack { background-color: transparent; border: none; }
            QFrame#dashboardHeader { background-color: transparent; border: none; }
            QLabel#dashboardTitle { font-size: 30px; font-weight: 700; color: #0F172A; }
            QLabel#dashboardDateLabel { font-size: 14px; color: #64748B; }
            QPushButton#dashboardNewActivityButton {
                background-color: #2563EB; color: #FFFFFF; border: 1px solid #2563EB;
                border-radius: 12px; padding: 11px 16px; font-size: 14px; font-weight: 700;
            }
            QPushButton#dashboardFullAgendaButton {
                background-color: #FFFFFF; color: #1D4ED8; border: 1px solid #CBD5E1;
                border-radius: 12px; padding: 11px 16px; font-size: 14px; font-weight: 700;
            }
            QPushButton#dashboardNewActivityButton:hover { background-color: #1D4ED8; }
            QPushButton#dashboardFullAgendaButton:hover {
                background-color: #EFF6FF; border-color: #93C5FD;
            }
            QFrame#dashboardKpiCard, QFrame[dashboardPanel='true'] {
                background-color: #FFFFFF; border: 1px solid #DCE4EF; border-radius: 16px;
            }
            QFrame#dashboardKpiCard[tone='blue'] { border-bottom: 4px solid #2563EB; }
            QFrame#dashboardKpiCard[tone='red'] { border-bottom: 4px solid #EF4444; }
            QFrame#dashboardKpiCard[tone='green'] { border-bottom: 4px solid #16A34A; }
            QFrame#dashboardKpiCard[tone='orange'] { border-bottom: 4px solid #F97316; }
            QFrame#dashboardKpiIconWrap {
                background-color: #EFF6FF; border: none; border-radius: 31px;
            }
            QFrame#dashboardKpiIconWrap[tone='red'] { background-color: #FEF2F2; }
            QFrame#dashboardKpiIconWrap[tone='green'] { background-color: #F0FDF4; }
            QFrame#dashboardKpiIconWrap[tone='orange'] { background-color: #FFF7ED; }
            QLabel#dashboardKpiTitle, QLabel#dashboardPanelTitle { color: #1E293B; font-size: 15px; font-weight: 700; }
            QLabel#dashboardKpiValue { color: #0F172A; font-size: 28px; font-weight: 800; }
            QLabel#dashboardKpiUnit { color: #0F172A; font-size: 22px; font-weight: 800; }
            QLabel#dashboardKpiNote, QLabel#dashboardFooterLabel, QLabel#dashboardEmptyLabel, QLabel#dashboardActivityState {
                color: #64748B; font-size: 13px;
            }
            QLabel#dashboardActivityCustomer { color: #0F172A; font-size: 14px; font-weight: 700; }
            QLabel#dashboardActivitySummary { color: #1E293B; font-size: 13px; }
            QFrame#dashboardActivityCard { background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 10px; }
            QScrollArea#dashboardTodayScrollArea, QWidget#dashboardTodayItemsHost { background: transparent; border: none; }
            QPushButton#dashboardTodayPdfButton, QPushButton#dashboardTodayPrintButton {
                color: #FFFFFF; border: none;
                border-radius: 8px; padding: 4px 8px; font-size: 12px; font-weight: 600;
            }
            QPushButton#dashboardTodayPdfButton { background-color: #2563EB; }
            QPushButton#dashboardTodayPdfButton:hover { background-color: #1D4ED8; }
            QPushButton#dashboardTodayPrintButton { background-color: #16A34A; }
            QPushButton#dashboardTodayPrintButton:hover { background-color: #15803D; }
            QPushButton#dashboardTodayPdfButton:disabled, QPushButton#dashboardTodayPrintButton:disabled {
                background-color: #F8FAFC; color: #94A3B8; border-color: #E2E8F0;
            }
            QWidget#dashboardCalendarHeadingBlock { background-color: transparent; border: none; }
            QCalendarWidget#dashboardMonthCalendar {
                background: #FFFFFF;
                border: 1px solid #DCE4EF;
                border-radius: 10px;
            }
            QCalendarWidget#dashboardMonthCalendar QWidget#qt_calendar_navigationbar {
                min-height: 26px;
                max-height: 26px;
                border: 1px solid #CBD5E1;
                border-radius: 10px;
                background: transparent;
                padding: 1px 5px;
            }
            QCalendarWidget#dashboardMonthCalendar QToolButton {
                min-height: 20px;
                max-height: 20px;
                padding: 0;
                margin: 0;
                border: none;
                background: transparent;
                icon-size: 12px;
            }
            QCalendarWidget#dashboardMonthCalendar QToolButton::menu-indicator {
                image: none;
            }
            QCalendarWidget#dashboardMonthCalendar QToolButton#qt_calendar_prevmonth,
            QCalendarWidget#dashboardMonthCalendar QToolButton#qt_calendar_nextmonth {
                min-width: 20px;
                max-width: 20px;
                border-radius: 10px;
                background: #4D9B31;
            }
            QCalendarWidget#dashboardMonthCalendar QToolButton#qt_calendar_prevmonth:hover,
            QCalendarWidget#dashboardMonthCalendar QToolButton#qt_calendar_nextmonth:hover {
                background: #3F8128;
            }
            QCalendarWidget#dashboardMonthCalendar QToolButton#qt_calendar_monthbutton,
            QCalendarWidget#dashboardMonthCalendar QToolButton#qt_calendar_yearbutton {
                min-width: 72px;
                max-width: 72px;
                color: #000000;
                font-size: 13px;
                font-weight: 700;
            }
            QCalendarWidget#dashboardMonthCalendar QToolButton#qt_calendar_yearbutton {
                min-width: 48px;
                max-width: 48px;
            }
            QCalendarWidget#dashboardMonthCalendar QAbstractSpinBox {
                min-width: 64px;
                max-width: 64px;
                min-height: 20px;
                max-height: 20px;
                border: 1px solid #CBD5E1;
                border-radius: 5px;
                background: #FFFFFF;
                color: #334155;
            }
            QCalendarWidget#dashboardMonthCalendar QTableView {
                background: #FFFFFF;
                gridline-color: #D8DEE8;
                outline: 0;
                selection-background-color: transparent;
            }
            QCalendarWidget#dashboardMonthCalendar QAbstractItemView:enabled {
                color: #0F172A;
                font-size: 11px;
                selection-background-color: transparent;
                selection-color: #0F172A;
            }
            QFrame#dashboardCalendarSummaryChip {
                background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 10px;
            }
            QFrame#dashboardCalendarSummaryChip[tone='blue'] { background-color: #EFF6FF; border-color: #BFDBFE; }
            QFrame#dashboardCalendarSummaryChip[tone='green'] { background-color: #F0FDF4; border-color: #BBF7D0; }
            QFrame#dashboardCalendarSummaryChip[tone='red'] { background-color: #FEF2F2; border-color: #FECACA; }
            QLabel#dashboardCalendarSummaryTitle { color: #000000; font-size: 12px; font-weight: 600; }
            QLabel#dashboardCalendarSummaryValue { color: #000000; font-size: 16px; font-weight: 800; }
            QTableWidget#dashboardReactivationTable, QTableWidget#dashboardIslandTable, QTableWidget#dashboardOrdersRecentTable, QTableWidget#dashboardOrdersPendingTable, QTableWidget#dashboardOrdersWarehouseTable, QTableWidget#dashboardOrdersStateTable, QTableWidget#dashboardWarehouseRiskTable, QTableWidget#dashboardWarehouseStockTable, QTableWidget#dashboardWarehouseEntriesTable, QTableWidget#dashboardWarehouseOutputsTable, QTableWidget#dashboardSalesDropsTable, QTableWidget#dashboardSalesIslandsTable, QTableWidget#dashboardSalesTypesTable, QTableWidget#dashboardSalesZeroTable {
                background-color: #FFFFFF; alternate-background-color: #F8FAFC; border: none; color: #334155;
            }
            QTableWidget#dashboardOrdersRecentTable, QTableWidget#dashboardOrdersPendingTable {
                selection-background-color: #2F80ED; selection-color: #FFFFFF;
            }
            QTableWidget#dashboardOrdersRecentTable::item:selected, QTableWidget#dashboardOrdersPendingTable::item:selected {
                background-color: #2F80ED; color: #FFFFFF;
            }
            QHeaderView::section {
                background-color: #F8FAFC; color: #475569; padding: 7px; border: none;
                border-bottom: 1px solid #E2E8F0; font-weight: 700;
            }
            """
        )
