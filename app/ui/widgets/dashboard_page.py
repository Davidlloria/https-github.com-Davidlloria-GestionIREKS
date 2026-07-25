from __future__ import annotations

import calendar
from datetime import date
from pathlib import Path

from PySide6.QtCore import QBuffer, QDate, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
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
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.services.customer_dashboard_service import (
    CustomerDashboardService,
    DashboardActivityRow,
    DashboardReactivationRow,
    DashboardSnapshot,
)
from app.services.customer_service import CustomerService
from app.services.order_dashboard_service import (
    DashboardOrderRow,
    DashboardOrdersStateRow,
    DashboardOrdersWarehouseRow,
    OrderDashboardService,
)
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


class DashboardAgendaDialog(QDialog):
    def __init__(
        self,
        page: "DashboardPage",
        *,
        agenda_id: str = "",
        default_customer_id: str = "",
        parent: QWidget | None = None,
    ) -> None:
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
        title.setObjectName("dashboardDialogTitle")
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
        self.save_btn = buttons.addButton("Guardar", QDialogButtonBox.ButtonRole.AcceptRole)
        self.save_btn.setProperty("btnRole", "success")
        self.cancel_btn = buttons.addButton("Cancelar", QDialogButtonBox.ButtonRole.RejectRole)
        self.cancel_btn.setProperty("btnRole", "secondary")
        self.delete_btn: QPushButton | None = None
        if self._activity is not None:
            self.delete_btn = buttons.addButton("Eliminar", QDialogButtonBox.ButtonRole.DestructiveRole)
            self.delete_btn.setProperty("btnRole", "danger")
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
        self.priority_combo.setCurrentIndex(
            max(0, self.priority_combo.findData(str(getattr(self._activity, "prioridad", "") or "normal").strip().lower()))
        )
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
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Agenda", f"No se pudo guardar la actividad: {exc}")
            return
        self.accept()

    def _delete_current_activity(self) -> None:
        if self._activity is None:
            return
        answer = QMessageBox.question(
            self,
            "Agenda",
            "La actividad se eliminará de la agenda.\n\n¿Continuar?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._page.customer_service.delete_agenda_activity(str(getattr(self._activity, "agenda_id", "") or ""))
        except Exception as exc:  # noqa: BLE001
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
        title.setObjectName("dashboardDialogTitle")
        layout.addWidget(title)

        self.summary_label = QLabel("")
        self.summary_label.setObjectName("dashboardDialogSummary")
        layout.addWidget(self.summary_label)

        self.table = QTableWidget(0, 8)
        self.table.setObjectName("dashboardAgendaOverviewTable")
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setHorizontalHeaderLabels(
            ["Fecha", "Seguimiento", "Cliente", "Isla", "Tipo", "Estado", "Resumen", "Responsable"]
        )
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
        self.new_btn.setProperty("btnRole", "primary")
        self.new_btn.clicked.connect(self._create_activity)
        actions.addWidget(self.new_btn)
        self.edit_btn = QPushButton("Editar")
        self.edit_btn.setProperty("btnRole", "warning")
        self.edit_btn.clicked.connect(self._edit_selected)
        actions.addWidget(self.edit_btn)
        actions.addItem(QSpacerItem(10, 10, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        self.close_btn = QPushButton("Cerrar")
        self.close_btn.setProperty("btnRole", "secondary")
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


class DashboardPage(QWidget):
    def __init__(
        self,
        *,
        customer_service: CustomerService | None = None,
        dashboard_service: CustomerDashboardService | None = None,
        order_dashboard_service: OrderDashboardService | None = None,
        sales_dashboard_service: SalesDashboardService | None = None,
        warehouse_dashboard_service: WarehouseDashboardService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.customer_service = customer_service or CustomerService()
        self.dashboard_service = dashboard_service or CustomerDashboardService()
        self.order_dashboard_service = order_dashboard_service or OrderDashboardService()
        self.sales_dashboard_service = sales_dashboard_service or SalesDashboardService()
        self.warehouse_dashboard_service = warehouse_dashboard_service or WarehouseDashboardService()
        self.setObjectName("dashboardPageRoot")
        self.current_dashboard = "agenda"
        self.agenda_calendar_month = date.today().replace(day=1)
        self.agenda_calendar_selected_date = date.today()
        self.agenda_calendar_rows: list[DashboardActivityRow] = []
        self.dashboard_nav_buttons: dict[str, QPushButton] = {}
        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.sidebar = self._build_sidebar()
        root_layout.addWidget(self.sidebar)

        content_host = QWidget()
        content_host.setObjectName("dashboardContentHost")
        content_host_layout = QVBoxLayout(content_host)
        content_host_layout.setContentsMargins(0, 0, 0, 0)
        content_host_layout.setSpacing(0)

        content = QWidget()
        content.setObjectName("dashboardContent")
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(14, 6, 14, 6)
        self.content_layout.setSpacing(8)
        content_host_layout.addWidget(content)
        root_layout.addWidget(content_host, 1)

        header = QFrame()
        header.setObjectName("dashboardHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        header_copy = QVBoxLayout()
        header_copy.setContentsMargins(0, 0, 0, 0)
        header_copy.setSpacing(4)
        self.title_label = QLabel("Agenda")
        self.title_label.setObjectName("dashboardTitle")
        header_copy.addWidget(self.title_label)
        self.date_label = QLabel("")
        self.date_label.setObjectName("dashboardDateLabel")
        header_copy.addWidget(self.date_label)
        header_layout.addLayout(header_copy, 1)

        self.new_activity_btn = QPushButton("Nueva actividad")
        self.new_activity_btn.setObjectName("dashboardNewActivityButton")
        self.new_activity_btn.setProperty("btnRole", "primary")
        self.new_activity_btn.clicked.connect(self._handle_primary_action)
        header_layout.addWidget(self.new_activity_btn)

        self.full_agenda_btn = QPushButton("Ver agenda completa")
        self.full_agenda_btn.setObjectName("dashboardFullAgendaButton")
        self.full_agenda_btn.setProperty("btnRole", "secondary")
        self.full_agenda_btn.clicked.connect(self._handle_secondary_action)
        header_layout.addWidget(self.full_agenda_btn)

        self.content_layout.addWidget(header)

        self.dashboard_stack = QStackedWidget()
        self.dashboard_stack.setObjectName("dashboardContentStack")
        self.agenda_dashboard = self._build_agenda_dashboard()
        self.warehouse_dashboard = self._build_warehouse_dashboard()
        self.orders_dashboard = self._build_orders_dashboard()
        self.sales_dashboard = self._build_sales_dashboard()
        self.dashboard_stack.addWidget(self.agenda_dashboard)
        self.dashboard_stack.addWidget(self.warehouse_dashboard)
        self.dashboard_stack.addWidget(self.orders_dashboard)
        self.dashboard_stack.addWidget(self.sales_dashboard)
        self.content_layout.addWidget(self.dashboard_stack, 1)

        self.footer_label = QLabel("")
        self.footer_label.setObjectName("dashboardFooterLabel")
        self.content_layout.addWidget(self.footer_label)

        self._apply_styles()
        self._set_dashboard_mode("agenda", reload=False)

    def _build_agenda_dashboard(self) -> QWidget:
        widget = QWidget()
        widget.setObjectName("dashboardAgendaView")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        kpi_row = QGridLayout()
        kpi_row.setHorizontalSpacing(12)
        kpi_row.setVerticalSpacing(12)
        self.kpi_labels: dict[str, QLabel] = {}
        self.kpi_notes: dict[str, QLabel] = {}
        for column, (key, title, tone, icon_name) in enumerate(
            [
                ("pending_today", "Pendientes hoy", "blue", "clipboard-list.svg"),
                ("overdue", "Vencidas", "red", "clock-3.svg"),
                ("completed_today", "Completadas hoy", "green", "circle-check.svg"),
                ("customers_without_follow_up", "Clientes sin seguimiento", "orange", "users.svg"),
            ]
        ):
            card, value_label, note_label = self._build_kpi_card(title, tone=tone, icon_name=icon_name)
            self.kpi_labels[key] = value_label
            self.kpi_notes[key] = note_label
            kpi_row.addWidget(card, 0, column)
        layout.addLayout(kpi_row)

        middle_row = QHBoxLayout()
        middle_row.setContentsMargins(0, 0, 0, 0)
        middle_row.setSpacing(14)
        today_panel, self.today_items_layout = self._build_list_panel(
            "Agenda de hoy",
            "dashboardTodayPanel",
            empty_text="Hoy no hay actividades registradas.",
        )
        self.today_link_btn = QPushButton("Ver toda la agenda")
        self.today_link_btn.setObjectName("dashboardPanelLinkButton")
        self.today_link_btn.setProperty("btnRole", "secondary")
        self.today_link_btn.clicked.connect(self._open_full_agenda)
        today_panel.layout().addWidget(self.today_link_btn)
        middle_row.addWidget(today_panel, 5)

        self.upcoming_panel = self._build_upcoming_panel()
        middle_row.addWidget(self.upcoming_panel, 3)
        layout.addLayout(middle_row)

        lower_row = QHBoxLayout()
        lower_row.setContentsMargins(0, 0, 0, 0)
        lower_row.setSpacing(14)

        reactivation_panel = self._build_table_panel("Clientes a reactivar", "dashboardReactivationPanel")
        self.reactivation_table = QTableWidget(0, 5)
        self.reactivation_table.setObjectName("dashboardReactivationTable")
        self.reactivation_table.setHorizontalHeaderLabels(["Cliente", "Isla", "Último contacto", "Variación kg", "Prioridad"])
        self._configure_table(self.reactivation_table)
        reactivation_header = self.reactivation_table.horizontalHeader()
        reactivation_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        reactivation_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        reactivation_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        reactivation_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        reactivation_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        reactivation_panel.layout().addWidget(self.reactivation_table)
        lower_row.addWidget(reactivation_panel, 5)

        island_panel = self._build_table_panel("Agenda por isla", "dashboardIslandPanel")
        self.island_table = QTableWidget(0, 5)
        self.island_table.setObjectName("dashboardIslandTable")
        self.island_table.setHorizontalHeaderLabels(["Isla", "Pend.", "Aplaz.", "Hechas", "Total"])
        self._configure_table(self.island_table)
        island_header = self.island_table.horizontalHeader()
        island_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 5):
            island_header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        island_panel.layout().addWidget(self.island_table)
        lower_row.addWidget(island_panel, 3)
        layout.addLayout(lower_row)
        return widget

    def _build_warehouse_dashboard(self) -> QWidget:
        widget = QWidget()
        widget.setObjectName("dashboardWarehouseView")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        kpi_row = QGridLayout()
        kpi_row.setHorizontalSpacing(12)
        kpi_row.setVerticalSpacing(12)
        self.warehouse_kpi_labels: dict[str, QLabel] = {}
        self.warehouse_kpi_notes: dict[str, QLabel] = {}
        for column, (key, title, tone, icon_name) in enumerate(
            [
                ("total_stock_kg", "Stock actual", "blue", "package-open.svg"),
                ("risk_items", "Riesgos activos", "red", "triangle-alert.svg"),
                ("entries_month_kg", "Entradas del mes", "green", "arrow-down-to-line.svg"),
                ("outputs_month_kg", "Salidas del mes", "orange", "arrow-down-from-line.svg"),
            ]
        ):
            card, value_label, note_label = self._build_kpi_card(title, tone=tone, icon_name=icon_name)
            self.warehouse_kpi_labels[key] = value_label
            self.warehouse_kpi_notes[key] = note_label
            kpi_row.addWidget(card, 0, column)
        layout.addLayout(kpi_row)

        middle_row = QHBoxLayout()
        middle_row.setContentsMargins(0, 0, 0, 0)
        middle_row.setSpacing(14)

        risk_panel = self._build_table_panel("Riesgos de stock y caducidad", "dashboardWarehouseRiskPanel")
        self.warehouse_risk_table = QTableWidget(0, 7)
        self.warehouse_risk_table.setObjectName("dashboardWarehouseRiskTable")
        self.warehouse_risk_table.setHorizontalHeaderLabels(["Almacén", "Ref", "Producto", "Lote", "Caduca", "Kg", "Estado"])
        self._configure_table(self.warehouse_risk_table)
        risk_header = self.warehouse_risk_table.horizontalHeader()
        risk_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        risk_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        risk_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        risk_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        risk_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        risk_header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        risk_header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        risk_panel.layout().addWidget(self.warehouse_risk_table)
        middle_row.addWidget(risk_panel, 5)

        stock_panel = self._build_table_panel("Stock por almacén", "dashboardWarehouseStockPanel")
        self.warehouse_stock_table = QTableWidget(0, 3)
        self.warehouse_stock_table.setObjectName("dashboardWarehouseStockTable")
        self.warehouse_stock_table.setHorizontalHeaderLabels(["Almacén", "Artículos", "Stock kg"])
        self._configure_table(self.warehouse_stock_table)
        stock_header = self.warehouse_stock_table.horizontalHeader()
        stock_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        stock_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        stock_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        stock_panel.layout().addWidget(self.warehouse_stock_table)
        middle_row.addWidget(stock_panel, 3)
        layout.addLayout(middle_row)

        lower_row = QHBoxLayout()
        lower_row.setContentsMargins(0, 0, 0, 0)
        lower_row.setSpacing(14)

        entries_panel = self._build_table_panel("Entradas del mes", "dashboardWarehouseEntriesPanel")
        self.warehouse_entries_table = QTableWidget(0, 5)
        self.warehouse_entries_table.setObjectName("dashboardWarehouseEntriesTable")
        self.warehouse_entries_table.setHorizontalHeaderLabels(["Fecha", "Almacén", "Ref", "Producto", "Kg"])
        self._configure_table(self.warehouse_entries_table)
        entries_header = self.warehouse_entries_table.horizontalHeader()
        entries_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        entries_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        entries_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        entries_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        entries_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        entries_panel.layout().addWidget(self.warehouse_entries_table)
        lower_row.addWidget(entries_panel, 5)

        outputs_panel = self._build_table_panel("Salidas del mes", "dashboardWarehouseOutputsPanel")
        self.warehouse_outputs_table = QTableWidget(0, 5)
        self.warehouse_outputs_table.setObjectName("dashboardWarehouseOutputsTable")
        self.warehouse_outputs_table.setHorizontalHeaderLabels(["Fecha", "Almacén", "Ref", "Producto", "Kg"])
        self._configure_table(self.warehouse_outputs_table)
        outputs_header = self.warehouse_outputs_table.horizontalHeader()
        outputs_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        outputs_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        outputs_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        outputs_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        outputs_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        outputs_panel.layout().addWidget(self.warehouse_outputs_table)
        lower_row.addWidget(outputs_panel, 3)
        layout.addLayout(lower_row)
        return widget

    def _build_orders_dashboard(self) -> QWidget:
        widget = QWidget()
        widget.setObjectName("dashboardOrdersView")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        kpi_row = QGridLayout()
        kpi_row.setHorizontalSpacing(12)
        kpi_row.setVerticalSpacing(12)
        self.order_kpi_labels: dict[str, QLabel] = {}
        self.order_kpi_notes: dict[str, QLabel] = {}
        for column, (key, title, tone, icon_name) in enumerate(
            [
                ("total_orders", "Pedidos del año", "blue", "shopping-cart.svg"),
                ("received_kg", "Kg recibidos", "green", "package-check.svg"),
                ("pending_kg", "Kg pendientes", "orange", "scale.svg"),
                ("incident_orders", "Incidencias", "red", "circle-alert.svg"),
            ]
        ):
            card, value_label, note_label = self._build_kpi_card(title, tone=tone, icon_name=icon_name)
            self.order_kpi_labels[key] = value_label
            self.order_kpi_notes[key] = note_label
            kpi_row.addWidget(card, 0, column)
        layout.addLayout(kpi_row)

        middle_row = QHBoxLayout()
        middle_row.setContentsMargins(0, 0, 0, 0)
        middle_row.setSpacing(14)

        recent_panel = self._build_table_panel("Pedidos recientes", "dashboardOrdersRecentPanel")
        self.orders_recent_table = QTableWidget(0, 7)
        self.orders_recent_table.setObjectName("dashboardOrdersRecentTable")
        self.orders_recent_table.setHorizontalHeaderLabels(["Pedido", "Almacén", "Fecha", "Kg pedido", "Kg recibido", "Kg pend.", "Estado"])
        self._configure_table(self.orders_recent_table)
        recent_header = self.orders_recent_table.horizontalHeader()
        recent_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        recent_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        recent_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        for column in range(3, 7):
            recent_header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        recent_panel.layout().addWidget(self.orders_recent_table)
        middle_row.addWidget(recent_panel, 5)

        pending_panel = self._build_table_panel("Pendientes de recibir", "dashboardOrdersPendingPanel")
        self.orders_pending_table = QTableWidget(0, 4)
        self.orders_pending_table.setObjectName("dashboardOrdersPendingTable")
        self.orders_pending_table.setHorizontalHeaderLabels(["Fecha", "Pedido", "Almacén", "Kg pend."])
        self._configure_table(self.orders_pending_table)
        pending_header = self.orders_pending_table.horizontalHeader()
        pending_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        pending_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        pending_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        pending_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        pending_panel.layout().addWidget(self.orders_pending_table)
        middle_row.addWidget(pending_panel, 3)
        layout.addLayout(middle_row)

        lower_row = QHBoxLayout()
        lower_row.setContentsMargins(0, 0, 0, 0)
        lower_row.setSpacing(14)

        warehouse_panel = self._build_table_panel("Más pendiente por almacén", "dashboardOrdersWarehousePanel")
        self.orders_warehouse_table = QTableWidget(0, 4)
        self.orders_warehouse_table.setObjectName("dashboardOrdersWarehouseTable")
        self.orders_warehouse_table.setHorizontalHeaderLabels(["Almacén", "Abiertos", "Kg pend.", "Últ. recepción"])
        self._configure_table(self.orders_warehouse_table)
        warehouse_header = self.orders_warehouse_table.horizontalHeader()
        warehouse_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        warehouse_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        warehouse_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        warehouse_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        warehouse_panel.layout().addWidget(self.orders_warehouse_table)
        lower_row.addWidget(warehouse_panel, 5)

        state_panel = self._build_table_panel("Resumen por estado", "dashboardOrdersStatePanel")
        self.orders_state_table = QTableWidget(0, 3)
        self.orders_state_table.setObjectName("dashboardOrdersStateTable")
        self.orders_state_table.setHorizontalHeaderLabels(["Estado", "Pedidos", "Kg"])
        self._configure_table(self.orders_state_table)
        state_header = self.orders_state_table.horizontalHeader()
        state_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        state_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        state_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        state_panel.layout().addWidget(self.orders_state_table)
        lower_row.addWidget(state_panel, 3)
        layout.addLayout(lower_row)
        return widget


    def _build_sales_dashboard(self) -> QWidget:
        widget = QWidget()
        widget.setObjectName("dashboardSalesView")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        kpi_row = QGridLayout()
        kpi_row.setHorizontalSpacing(12)
        kpi_row.setVerticalSpacing(12)
        self.sales_kpi_labels: dict[str, QLabel] = {}
        self.sales_kpi_notes: dict[str, QLabel] = {}
        for column, (key, title, tone, icon_name) in enumerate(
            [
                ("total_kg", "Kg vendidos", "blue", "scale.svg"),
                ("delta_kg", "Variación kg", "blue", "trending-down.svg"),
                ("active_customers", "Clientes activos", "green", "briefcase.svg"),
                ("active_islands", "Islas activas", "orange", "map.svg"),
            ]
        ):
            card, value_label, note_label = self._build_kpi_card(title, tone=tone, icon_name=icon_name)
            self.sales_kpi_labels[key] = value_label
            self.sales_kpi_notes[key] = note_label
            kpi_row.addWidget(card, 0, column)
        layout.addLayout(kpi_row)

        middle_row = QHBoxLayout()
        middle_row.setContentsMargins(0, 0, 0, 0)
        middle_row.setSpacing(14)

        drops_panel = self._build_table_panel("Mayores bajadas por cliente", "dashboardSalesDropsPanel")
        self.sales_drops_table = QTableWidget(0, 5)
        self.sales_drops_table.setObjectName("dashboardSalesDropsTable")
        self.sales_drops_table.setHorizontalHeaderLabels(["Cliente", "Isla", "Kg ant.", "Kg act.", "Δ Kg"])
        self._configure_table(self.sales_drops_table)
        drops_header = self.sales_drops_table.horizontalHeader()
        drops_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        drops_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        for column in range(2, 5):
            drops_header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        drops_panel.layout().addWidget(self.sales_drops_table)
        middle_row.addWidget(drops_panel, 5)

        islands_panel = self._build_table_panel("Ventas por isla", "dashboardSalesIslandsPanel")
        self.sales_islands_table = QTableWidget(0, 5)
        self.sales_islands_table.setObjectName("dashboardSalesIslandsTable")
        self.sales_islands_table.setHorizontalHeaderLabels(["Isla", "Clientes", "Kg act.", "Δ Kg", "%"])
        self._configure_table(self.sales_islands_table)
        islands_header = self.sales_islands_table.horizontalHeader()
        islands_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 5):
            islands_header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        islands_panel.layout().addWidget(self.sales_islands_table)
        middle_row.addWidget(islands_panel, 3)
        layout.addLayout(middle_row)

        lower_row = QHBoxLayout()
        lower_row.setContentsMargins(0, 0, 0, 0)
        lower_row.setSpacing(14)

        types_panel = self._build_table_panel("Ventas por tipo de cliente", "dashboardSalesTypesPanel")
        self.sales_types_table = QTableWidget(0, 5)
        self.sales_types_table.setObjectName("dashboardSalesTypesTable")
        self.sales_types_table.setHorizontalHeaderLabels(["Tipo", "Clientes", "Kg act.", "Δ Kg", "%"])
        self._configure_table(self.sales_types_table)
        types_header = self.sales_types_table.horizontalHeader()
        types_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 5):
            types_header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        types_panel.layout().addWidget(self.sales_types_table)
        lower_row.addWidget(types_panel, 5)

        zero_panel = self._build_table_panel("Clientes sin consumo actual", "dashboardSalesZeroPanel")
        self.sales_zero_table = QTableWidget(0, 4)
        self.sales_zero_table.setObjectName("dashboardSalesZeroTable")
        self.sales_zero_table.setHorizontalHeaderLabels(["Cliente", "Isla", "Tipo", "Kg ant."])
        self._configure_table(self.sales_zero_table)
        zero_header = self.sales_zero_table.horizontalHeader()
        zero_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        zero_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        zero_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        zero_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        zero_panel.layout().addWidget(self.sales_zero_table)
        lower_row.addWidget(zero_panel, 3)
        layout.addLayout(lower_row)
        return widget

    def reload(self) -> None:
        self.date_label.setText(self.format_header_date(date.today()))
        if self.current_dashboard == "pedidos":
            self._reload_orders_dashboard()
            return
        if self.current_dashboard == "almacen":
            self._reload_warehouse_dashboard()
            return
        if self.current_dashboard == "ventas":
            self._reload_sales_dashboard()
            return
        self._reload_agenda_dashboard()

    def _reload_agenda_dashboard(self) -> None:
        snapshot = self.dashboard_service.load_snapshot()
        self.kpi_labels["pending_today"].setText(str(snapshot.pending_today))
        self.kpi_notes["pending_today"].setText("actividad(es)")
        self.kpi_labels["overdue"].setText(str(snapshot.overdue))
        self.kpi_notes["overdue"].setText("actividad(es)")
        self.kpi_labels["completed_today"].setText(str(snapshot.completed_today))
        self.kpi_notes["completed_today"].setText("actividad(es)")
        self.kpi_labels["customers_without_follow_up"].setText(str(snapshot.customers_without_follow_up))
        self.kpi_notes["customers_without_follow_up"].setText("cliente(s)")

        self.populate_activity_list(
            self.today_items_layout,
            snapshot.today_items,
            empty_text="Hoy no hay actividades registradas.",
        )
        self._reload_agenda_calendar_panel(self.dashboard_service.list_all_activities(), today_value=date.today())
        self._populate_reactivation_table(snapshot.reactivation_rows)
        self._populate_island_table(snapshot)
        self.footer_label.setText(
            f"Última actualización: {snapshot.generated_at.strftime('%d/%m/%Y %H:%M')} · {snapshot.reactivation_metric_label}"
        )

    def _reload_orders_dashboard(self) -> None:
        snapshot = self.order_dashboard_service.load_snapshot()
        self.order_kpi_labels["total_orders"].setText(str(snapshot.total_orders))
        self.order_kpi_notes["total_orders"].setText("pedido(s)")
        self.order_kpi_labels["received_kg"].setText(self.format_kg(snapshot.received_kg))
        self.order_kpi_notes["received_kg"].setText("kg recibidos")
        self.order_kpi_labels["pending_kg"].setText(self.format_kg(snapshot.pending_kg))
        self.order_kpi_notes["pending_kg"].setText("kg pendientes")
        self.order_kpi_labels["incident_orders"].setText(str(snapshot.incident_orders))
        self.order_kpi_notes["incident_orders"].setText("pedido(s)")
        self._populate_order_recent_table(snapshot.recent_orders)
        self._populate_order_pending_table(snapshot.pending_orders)
        self._populate_order_warehouse_table(snapshot.warehouse_rows)
        self._populate_order_state_table(snapshot.state_rows)
        self.footer_label.setText(
            f"Última actualización: {snapshot.generated_at.strftime('%d/%m/%Y %H:%M')} · Pedidos {snapshot.year} · métrica principal kg"
        )


    def _reload_sales_dashboard(self) -> None:
        snapshot = self.sales_dashboard_service.load_snapshot()
        self.sales_kpi_labels["total_kg"].setText(self.format_kg(snapshot.total_kg))
        self.sales_kpi_notes["total_kg"].setText(f"kg vendidos en {snapshot.year}")
        self.sales_kpi_labels["delta_kg"].setText(self.format_kg(snapshot.delta_kg, signed=True))
        self.sales_kpi_notes["delta_kg"].setText(f"vs {snapshot.previous_year} · {self.format_kg(snapshot.delta_pct, signed=True, suffix='%')}")
        delta_color = "#16A34A" if snapshot.delta_kg >= 0.0 else "#DC2626"
        self.sales_kpi_labels["delta_kg"].setStyleSheet(f"color: {delta_color}; font-size: 30px; font-weight: 700;")
        self.sales_kpi_notes["delta_kg"].setStyleSheet(f"color: {delta_color}; font-size: 12px; font-weight: 600;")
        self.sales_kpi_labels["active_customers"].setText(str(snapshot.active_customers))
        self.sales_kpi_notes["active_customers"].setText("cliente(s) con compra")
        self.sales_kpi_labels["active_islands"].setText(str(snapshot.active_islands))
        self.sales_kpi_notes["active_islands"].setText("isla(s) con venta")
        self._populate_sales_drops_table(snapshot.customer_drop_rows)
        self._populate_sales_islands_table(snapshot.island_rows)
        self._populate_sales_types_table(snapshot.type_rows)
        self._populate_sales_zero_table(snapshot.zero_consumption_rows)
        self.footer_label.setText(
            f"Última actualización: {snapshot.generated_at.strftime('%d/%m/%Y %H:%M')} · Ventas {snapshot.year} vs {snapshot.previous_year} · {snapshot.customers_down} cliente(s) en bajada"
        )

    def _reload_warehouse_dashboard(self) -> None:
        snapshot = self.warehouse_dashboard_service.load_snapshot()
        self.warehouse_kpi_labels["total_stock_kg"].setText(self.format_kg(snapshot.total_stock_kg))
        self.warehouse_kpi_notes["total_stock_kg"].setText("kg netos")
        self.warehouse_kpi_labels["risk_items"].setText(str(snapshot.risk_items))
        self.warehouse_kpi_notes["risk_items"].setText("lote(s)")
        self.warehouse_kpi_labels["entries_month_kg"].setText(self.format_kg(snapshot.entries_month_kg))
        self.warehouse_kpi_notes["entries_month_kg"].setText("kg entrados")
        self.warehouse_kpi_labels["outputs_month_kg"].setText(self.format_kg(snapshot.outputs_month_kg))
        self.warehouse_kpi_notes["outputs_month_kg"].setText("kg salidos")
        self._populate_warehouse_risk_table(snapshot.risk_rows)
        self._populate_warehouse_stock_table(snapshot.warehouse_rows)
        self._populate_warehouse_movement_table(self.warehouse_entries_table, snapshot.entry_rows, tone="#067647")
        self._populate_warehouse_movement_table(self.warehouse_outputs_table, snapshot.output_rows, tone="#B42318")
        threshold_text = self.format_kg(snapshot.low_stock_threshold_units)
        self.footer_label.setText(
            f"Última actualización: {snapshot.generated_at.strftime('%d/%m/%Y %H:%M')} · Almacén {snapshot.month:02d}/{snapshot.year} · umbral bajo stock {threshold_text} uds"
        )

    def _set_dashboard_mode(self, mode: str, *, reload: bool = True) -> None:
        clean_mode = str(mode or "agenda").strip().lower()
        if clean_mode not in {"agenda", "almacen", "pedidos", "ventas"}:
            return
        self.current_dashboard = clean_mode
        if clean_mode == "pedidos":
            self.dashboard_stack.setCurrentWidget(self.orders_dashboard)
            self.title_label.setText("Pedidos")
            self.new_activity_btn.setText("Ver pedidos")
            self.full_agenda_btn.setText("Actualizar")
            self._set_button_icon(self.new_activity_btn, "shopping-cart.svg", color="#FFFFFF", size=24)
            self._set_button_icon(self.full_agenda_btn, "refresh-cw.svg", color="#1D4ED8", size=24)
        elif clean_mode == "almacen":
            self.dashboard_stack.setCurrentWidget(self.warehouse_dashboard)
            self.title_label.setText("Almacén")
            self.new_activity_btn.setText("Ver almacén")
            self.full_agenda_btn.setText("Actualizar")
            self._set_button_icon(self.new_activity_btn, "warehouse.svg", color="#FFFFFF", size=24)
            self._set_button_icon(self.full_agenda_btn, "refresh-cw.svg", color="#1D4ED8", size=24)
        elif clean_mode == "ventas":
            self.dashboard_stack.setCurrentWidget(self.sales_dashboard)
            self.title_label.setText("Ventas")
            self.new_activity_btn.setText("Ver ventas")
            self.full_agenda_btn.setText("Actualizar")
            self._set_button_icon(self.new_activity_btn, "bar-chart-3.svg", color="#FFFFFF", size=24)
            self._set_button_icon(self.full_agenda_btn, "refresh-cw.svg", color="#1D4ED8", size=24)
        else:
            self.dashboard_stack.setCurrentWidget(self.agenda_dashboard)
            self.title_label.setText("Agenda")
            self.new_activity_btn.setText("Nueva actividad")
            self.full_agenda_btn.setText("Ver agenda completa")
            self._set_button_icon(self.new_activity_btn, "plus.svg", color="#FFFFFF", size=24)
            self._set_button_icon(self.full_agenda_btn, "calendar.svg", color="#1D4ED8", size=24)
        self._refresh_dashboard_nav_buttons()
        if reload:
            self.reload()

    def _refresh_dashboard_nav_buttons(self) -> None:
        icon_names = {
            "agenda": "calendar-days.svg",
            "almacen": "box.svg",
            "pedidos": "shopping-cart.svg",
            "ventas": "bar-chart-3.svg",
        }
        for key, button in self.dashboard_nav_buttons.items():
            active = key == self.current_dashboard
            button.setProperty("active", active)
            icon_name = icon_names.get(key, "calendar-days.svg")
            icon_color = "#FFFFFF" if active else "#475569"
            self._set_button_icon(button, icon_name, color=icon_color, size=28)
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

    def _handle_primary_action(self) -> None:
        if self.current_dashboard == "pedidos":
            self._open_orders_page()
            return
        if self.current_dashboard == "almacen":
            self._open_warehouse_page()
            return
        if self.current_dashboard == "ventas":
            self._open_sales_page()
            return
        self._open_new_activity()

    def _handle_secondary_action(self) -> None:
        if self.current_dashboard in {"pedidos", "almacen", "ventas"}:
            self.reload()
            return
        self._open_full_agenda()

    def _open_orders_page(self) -> None:
        widget: QWidget | None = self
        while widget is not None:
            page_names = getattr(widget, "page_names", None)
            setter = getattr(widget, "_set_current_page", None)
            if isinstance(page_names, list) and callable(setter) and "Pedidos" in page_names:
                setter(page_names.index("Pedidos"))
                return
            widget = widget.parentWidget()
        QMessageBox.information(self, "Pedidos", "La vista completa de pedidos no está disponible desde este contexto.")


    def _open_sales_page(self) -> None:
        widget: QWidget | None = self
        while widget is not None:
            page_names = getattr(widget, "page_names", None)
            setter = getattr(widget, "_set_current_page", None)
            if isinstance(page_names, list) and callable(setter) and "Ventas" in page_names:
                setter(page_names.index("Ventas"))
                return
            widget = widget.parentWidget()
        QMessageBox.information(self, "Ventas", "La vista completa de ventas no está disponible desde este contexto.")

    def _open_warehouse_page(self) -> None:
        widget: QWidget | None = self
        while widget is not None:
            page_names = getattr(widget, "page_names", None)
            setter = getattr(widget, "_set_current_page", None)
            if isinstance(page_names, list) and callable(setter) and "Almacen" in page_names:
                setter(page_names.index("Almacen"))
                return
            widget = widget.parentWidget()
        QMessageBox.information(self, "Almacén", "La vista completa de almacén no está disponible desde este contexto.")

    def _populate_order_recent_table(self, rows: list[DashboardOrderRow]) -> None:
        self.orders_recent_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            status_label, status_color = self._order_status_meta(row.status)
            values = [
                row.pedido_numero,
                row.almacen_nombre,
                self.format_date(row.pedido_fecha),
                self.format_kg(row.ordered_kg),
                self.format_kg(row.received_kg),
                self.format_kg(row.pending_kg),
                status_label,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in {3, 4, 5}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if column == 6:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    item.setForeground(QColor(status_color))
                self.orders_recent_table.setItem(row_index, column, item)

    def _populate_order_pending_table(self, rows: list[DashboardOrderRow]) -> None:
        self.orders_pending_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                self.format_date(row.pedido_fecha),
                row.pedido_numero,
                row.almacen_nombre,
                self.format_kg(row.pending_kg),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 3:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    item.setForeground(QColor("#C62828") if row.pending_kg > 1e-9 else QColor("#B54708"))
                self.orders_pending_table.setItem(row_index, column, item)

    def _populate_order_warehouse_table(self, rows: list[DashboardOrdersWarehouseRow]) -> None:
        self.orders_warehouse_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row.almacen_nombre,
                str(row.open_orders),
                self.format_kg(row.pending_kg),
                self.format_date(row.last_receipt, allow_blank=True) or "-",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in {1, 2}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.orders_warehouse_table.setItem(row_index, column, item)

    def _populate_order_state_table(self, rows: list[DashboardOrdersStateRow]) -> None:
        self.orders_state_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            _status_label, status_color = self._order_status_meta(row.status)
            values = [row.status, str(row.count), self.format_kg(row.kg)]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setForeground(QColor(status_color))
                if column in {1, 2}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.orders_state_table.setItem(row_index, column, item)


    def _populate_sales_drops_table(self, rows: list[DashboardSalesCustomerRow]) -> None:
        self.sales_drops_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                self.customer_label(int(row.cliente_codigo or 0), row.cliente_nombre),
                row.isla,
                self.format_kg(row.kg_prev),
                self.format_kg(row.kg_curr),
                self.format_kg(row.delta_kg, signed=True),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in {2, 3, 4}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if column == 4:
                    item.setForeground(QColor("#C62828" if row.delta_kg < 0.0 else "#067647"))
                self.sales_drops_table.setItem(row_index, column, item)

    def _populate_sales_islands_table(self, rows: list[DashboardSalesIslandRow]) -> None:
        self.sales_islands_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row.isla,
                str(row.customers),
                self.format_kg(row.kg_curr),
                self.format_kg(row.delta_kg, signed=True),
                self.format_kg(row.share_pct, suffix="%"),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in {1, 2, 3, 4}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if column == 3:
                    item.setForeground(QColor("#067647" if row.delta_kg >= 0.0 else "#C62828"))
                self.sales_islands_table.setItem(row_index, column, item)

    def _populate_sales_types_table(self, rows: list[DashboardSalesTypeRow]) -> None:
        self.sales_types_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row.cliente_tipo,
                str(row.customers),
                self.format_kg(row.kg_curr),
                self.format_kg(row.delta_kg, signed=True),
                self.format_kg(row.share_pct, suffix="%"),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in {1, 2, 3, 4}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if column == 3:
                    item.setForeground(QColor("#067647" if row.delta_kg >= 0.0 else "#C62828"))
                self.sales_types_table.setItem(row_index, column, item)

    def _populate_sales_zero_table(self, rows: list[DashboardSalesCustomerRow]) -> None:
        self.sales_zero_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                self.customer_label(int(row.cliente_codigo or 0), row.cliente_nombre),
                row.isla,
                row.cliente_tipo,
                self.format_kg(row.kg_prev),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 3:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    item.setForeground(QColor("#B54708"))
                self.sales_zero_table.setItem(row_index, column, item)

    def _populate_warehouse_risk_table(self, rows: list[DashboardWarehouseRiskRow]) -> None:
        self.warehouse_risk_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row.almacen_nombre,
                row.referencia,
                row.nombre,
                row.lote,
                self.format_date(row.caducidad, allow_blank=True) or "-",
                self.format_kg(row.stock_kg),
                row.state,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 5:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if column == 6:
                    state_color = "#B42318" if row.state == "Caducado" else "#B54708" if row.state == "Caduca pronto" else "#1D4ED8"
                    item.setForeground(QColor(state_color))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.warehouse_risk_table.setItem(row_index, column, item)

    def _populate_warehouse_stock_table(self, rows: list[DashboardWarehouseStockRow]) -> None:
        self.warehouse_stock_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [row.almacen_nombre, str(row.article_count), self.format_kg(row.stock_kg)]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in {1, 2}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.warehouse_stock_table.setItem(row_index, column, item)

    def _populate_warehouse_movement_table(
        self,
        table: QTableWidget,
        rows: list[DashboardWarehouseMovementRow],
        *,
        tone: str,
    ) -> None:
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                self.format_date(row.fecha),
                row.almacen_nombre,
                row.referencia,
                row.nombre,
                self.format_kg(row.kg),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 4:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    item.setForeground(QColor(tone))
                table.setItem(row_index, column, item)

    @staticmethod
    def _order_status_meta(status: str) -> tuple[str, str]:
        normalized = str(status or "").strip().lower()
        if normalized == "incidencia":
            return "Incidencia", "#C62828"
        if normalized == "completado":
            return "Completado", "#067647"
        if normalized == "parcial":
            return "Parcial", "#B54708"
        return "Pendiente", "#1D4ED8"

    def customer_choices(self, *, include_inactive: bool = False) -> list[tuple[str, str]]:
        rows = []
        for customer in self.customer_service.list(""):
            if not include_inactive and not bool(getattr(customer, "activo", True)):
                continue
            customer_id = str(getattr(customer, "cliente_id", "") or "").strip()
            if not customer_id:
                continue
            rows.append(
                (
                    customer_id,
                    self.customer_label(
                        int(getattr(customer, "cliente_codigo", 0) or 0),
                        str(getattr(customer, "cliente_nombre_comercial", "") or ""),
                    ),
                )
            )
        return rows

    def agenda_type_options(self) -> list[tuple[str, str]]:
        return [
            ("visita_realizada", "Visita realizada"),
            ("visita_prevista", "Visita prevista"),
            ("llamada", "Llamada"),
            ("seguimiento", "Seguimiento"),
            ("desarrollo_futuro", "Desarrollo futuro"),
            ("incidencia", "Incidencia"),
            ("nota", "Nota"),
        ]

    def agenda_state_options(self) -> list[tuple[str, str]]:
        return [
            ("pendiente", "Pendiente"),
            ("hecho", "Completada"),
            ("aplazado", "Aplazado"),
            ("cancelado", "Cancelado"),
        ]

    def agenda_type_label(self, value: str) -> str:
        options = dict(self.agenda_type_options())
        return options.get(str(value or "").strip(), str(value or "").replace("_", " ").title())

    def agenda_state_label(self, value: str) -> str:
        options = dict(self.agenda_state_options())
        return options.get(str(value or "").strip(), str(value or "").replace("_", " ").title())

    def qdate_from_value(self, value: object, *, fallback_today: bool = False) -> QDate:
        if isinstance(value, date):
            return QDate(value.year, value.month, value.day)
        if fallback_today:
            return QDate.currentDate()
        return QDate.currentDate()

    def configure_dashboard_calendar(self, date_edit: QDateEdit) -> None:
        date_edit.setMinimumWidth(142)
        calendar = date_edit.calendarWidget()
        if calendar is None:
            calendar = QCalendarWidget(date_edit)
            date_edit.setCalendarWidget(calendar)
        calendar.setObjectName("dashboardPopupCalendar")
        calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        calendar.setMinimumSize(340, 272)

    def customer_label(self, code: int, name: str) -> str:
        if code > 0:
            return f"{code} · {name.strip()}"
        return name.strip()

    def format_date(self, value: date | None, *, allow_blank: bool = False) -> str:
        if value is None:
            return "" if allow_blank else "-"
        return value.strftime("%d/%m/%Y")

    def format_header_date(self, value: date) -> str:
        weekdays = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
        months = [
            "enero",
            "febrero",
            "marzo",
            "abril",
            "mayo",
            "junio",
            "julio",
            "agosto",
            "septiembre",
            "octubre",
            "noviembre",
            "diciembre",
        ]
        weekday = weekdays[value.weekday()]
        month = months[value.month - 1]
        return f"{weekday}, {value.day:02d} de {month} de {value.year}"

    def populate_activity_list(
        self,
        layout: QVBoxLayout,
        rows: list[DashboardActivityRow],
        *,
        empty_text: str,
    ) -> None:
        self._clear_layout(layout)
        if not rows:
            layout.addWidget(self._empty_label(empty_text))
            return
        for row in rows:
            layout.addWidget(self._build_activity_card(row))
        layout.addStretch(1)

    def _build_kpi_card(self, title: str, *, tone: str, icon_name: str) -> tuple[QFrame, QLabel, QLabel]:
        card = QFrame()
        card.setObjectName("dashboardKpiCard")
        card.setProperty("tone", tone)
        card.setFixedHeight(100)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(14)

        icon_wrap = QFrame()
        icon_wrap.setObjectName("dashboardKpiIcon")
        icon_wrap.setProperty("tone", tone)
        icon_wrap.setFixedSize(64, 64)
        icon_wrap_layout = QVBoxLayout(icon_wrap)
        icon_wrap_layout.setContentsMargins(0, 0, 0, 0)
        icon_wrap_layout.setSpacing(0)

        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setFixedSize(46, 46)
        icon_label.setPixmap(self._icon_pixmap(icon_name, 42, color=self._kpi_tone_color(tone)))
        icon_wrap_layout.addStretch(1)
        icon_wrap_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignCenter)
        icon_wrap_layout.addStretch(1)
        layout.addWidget(icon_wrap, 0, Qt.AlignmentFlag.AlignVCenter)

        copy_layout = QVBoxLayout()
        copy_layout.setContentsMargins(0, 0, 0, 0)
        copy_layout.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("dashboardKpiTitle")
        copy_layout.addWidget(title_label)
        value_label = QLabel("0")
        value_label.setObjectName("dashboardKpiValue")
        copy_layout.addWidget(value_label)
        note_label = QLabel("actividad(es)")
        note_label.setObjectName("dashboardKpiNote")
        copy_layout.addWidget(note_label)
        copy_layout.addStretch(1)
        layout.addLayout(copy_layout, 1)
        return card, value_label, note_label

    def _build_list_panel(self, title: str, object_name: str, *, empty_text: str) -> tuple[QFrame, QVBoxLayout]:
        panel = QFrame()
        panel.setObjectName(object_name)
        panel.setProperty("dashboardPanel", True)
        panel.setFixedHeight(312)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)
        heading = QLabel(title)
        heading.setObjectName("dashboardPanelTitle")
        layout.addWidget(heading)
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(6)
        container_layout.addWidget(self._empty_label(empty_text))
        layout.addWidget(container, 1)
        return panel, container_layout

    def _build_table_panel(self, title: str, object_name: str) -> QFrame:
        panel = QFrame()
        panel.setObjectName(object_name)
        panel.setProperty("dashboardPanel", True)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        heading = QLabel(title)
        heading.setObjectName("dashboardPanelTitle")
        layout.addWidget(heading)
        return panel

    def _build_upcoming_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("dashboardUpcomingPanel")
        panel.setProperty("dashboardPanel", True)
        panel.setFixedHeight(304)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        heading = QLabel("Agenda del mes")
        heading.setObjectName("dashboardPanelTitle")
        layout.addWidget(heading)

        top_section = QWidget()
        top_layout = QVBoxLayout(top_section)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(4)

        nav_row = QHBoxLayout()
        nav_row.setContentsMargins(0, 0, 0, 0)
        nav_row.setSpacing(8)
        self.agenda_prev_month_btn = QPushButton("<")
        self.agenda_prev_month_btn.setObjectName("dashboardCalendarNavButton")
        self.agenda_prev_month_btn.clicked.connect(lambda: self._shift_agenda_calendar_month(-1))
        nav_row.addWidget(self.agenda_prev_month_btn, 0)

        self.agenda_month_label = QLabel("")
        self.agenda_month_label.setObjectName("dashboardMonthTitle")
        self.agenda_month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav_row.addWidget(self.agenda_month_label, 1)

        self.agenda_next_month_btn = QPushButton(">")
        self.agenda_next_month_btn.setObjectName("dashboardCalendarNavButton")
        self.agenda_next_month_btn.clicked.connect(lambda: self._shift_agenda_calendar_month(1))
        nav_row.addWidget(self.agenda_next_month_btn, 0)
        top_layout.addLayout(nav_row)

        legend_row = QHBoxLayout()
        legend_row.setContentsMargins(0, 0, 0, 0)
        legend_row.setSpacing(6)
        legend_row.addWidget(self._meta_badge("Pendiente", "#DBEAFE", "#1D4ED8"))
        legend_row.addWidget(self._meta_badge("Hecha", "#DCFCE7", "#16A34A"))
        legend_row.addWidget(self._meta_badge("Vencida", "#FEE2E2", "#DC2626"))
        legend_row.addStretch(1)
        top_layout.addLayout(legend_row)

        weekdays_row = QHBoxLayout()
        weekdays_row.setContentsMargins(0, 0, 0, 0)
        weekdays_row.setSpacing(2)
        for label_text in ("L", "M", "X", "J", "V", "S", "D"):
            weekdays_row.addWidget(self._build_weekday_label(label_text))
        top_layout.addLayout(weekdays_row)

        grid_host = QFrame()
        grid_host.setObjectName("dashboardMonthGrid")
        grid_host.setFixedHeight(154)
        grid_layout = QGridLayout(grid_host)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setHorizontalSpacing(2)
        grid_layout.setVerticalSpacing(2)
        self.agenda_day_buttons = []
        for row_index in range(6):
            for column_index in range(7):
                button = QPushButton("")
                button.setObjectName("dashboardMonthDayButton")
                button.setCheckable(False)
                button.setProperty("selected", False)
                button.setProperty("today", False)
                button.setProperty("hasAgenda", False)
                button.setProperty("outsideMonth", False)
                button.setProperty("tone", "none")
                button.setMinimumHeight(24)
                button.setMaximumHeight(24)
                button.clicked.connect(lambda _checked=False, current_button=button: self._handle_agenda_calendar_button(current_button))
                grid_layout.addWidget(button, row_index, column_index)
                self.agenda_day_buttons.append(button)
        top_layout.addWidget(grid_host)
        layout.addWidget(top_section, 0)

        bottom_section = QWidget()
        bottom_layout = QVBoxLayout(bottom_section)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(4)

        summary_row = QHBoxLayout()
        summary_row.setContentsMargins(0, 0, 0, 0)
        summary_row.setSpacing(6)
        self.agenda_month_summary_labels = {}
        for key, title, tone in (
            ("pending", "Pendientes", "blue"),
            ("completed", "Hechas", "green"),
            ("overdue", "Vencidas", "red"),
        ):
            chip, value_label = self._build_calendar_summary_chip(title, tone=tone)
            self.agenda_month_summary_labels[key] = value_label
            summary_row.addWidget(chip)
        bottom_layout.addLayout(summary_row)

        self.agenda_month_detail_title = QLabel("Agenda del día seleccionado")
        self.agenda_month_detail_title.setObjectName("dashboardUpcomingSectionTitle")
        bottom_layout.addWidget(self.agenda_month_detail_title)

        detail_container = QWidget()
        detail_container.setObjectName("dashboardCalendarDetailContainer")
        detail_container.setFixedHeight(54)
        self.agenda_month_detail_layout = QVBoxLayout(detail_container)
        self.agenda_month_detail_layout.setContentsMargins(0, 0, 0, 0)
        self.agenda_month_detail_layout.setSpacing(4)
        bottom_layout.addWidget(detail_container)

        layout.addWidget(bottom_section, 0)
        layout.addStretch(1)
        return panel

    def _build_weekday_label(self, text_value: str) -> QLabel:
        label = QLabel(text_value)
        label.setObjectName("dashboardWeekdayLabel")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return label

    def _build_calendar_summary_chip(self, title: str, *, tone: str) -> tuple[QFrame, QLabel]:
        frame = QFrame()
        frame.setObjectName("dashboardCalendarSummaryChip")
        frame.setProperty("tone", tone)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(6)
        title_label = QLabel(title)
        title_label.setObjectName("dashboardCalendarSummaryTitle")
        layout.addWidget(title_label)
        layout.addStretch(1)
        value_label = QLabel("0")
        value_label.setObjectName("dashboardCalendarSummaryValue")
        layout.addWidget(value_label)
        return frame, value_label

    def _reload_agenda_calendar_panel(self, rows: list[DashboardActivityRow], *, today_value: date) -> None:
        self.agenda_calendar_rows = list(rows)
        month_start = self.agenda_calendar_month.replace(day=1)
        self.agenda_month_label.setText(self._agenda_month_title(month_start))
        self._refresh_agenda_calendar(today_value=today_value)

    def _refresh_agenda_calendar(self, *, today_value: date) -> None:
        month_start = self.agenda_calendar_month.replace(day=1)
        month_days = list(calendar.Calendar(firstweekday=0).itermonthdates(month_start.year, month_start.month))
        month_rows = self._agenda_month_rows(month_start)

        pending_count = 0
        completed_count = 0
        overdue_count = 0
        for row in month_rows:
            state_group = self._agenda_state_group(row.estado)
            if state_group == "completed":
                completed_count += 1
            elif self._is_overdue_activity(row, today_value):
                overdue_count += 1
            elif state_group != "cancelled":
                pending_count += 1

        self.agenda_month_summary_labels["pending"].setText(str(pending_count))
        self.agenda_month_summary_labels["completed"].setText(str(completed_count))
        self.agenda_month_summary_labels["overdue"].setText(str(overdue_count))

        if self.agenda_calendar_selected_date.year != month_start.year or self.agenda_calendar_selected_date.month != month_start.month:
            self.agenda_calendar_selected_date = today_value if today_value.year == month_start.year and today_value.month == month_start.month else month_start

        for button, day_value in zip(self.agenda_day_buttons, month_days):
            rows_for_day = self._agenda_rows_for_date(day_value)
            has_agenda = bool(rows_for_day)
            tone = self._agenda_day_tone(rows_for_day, today_value=today_value)
            in_month = day_value.month == month_start.month
            button.setText(str(day_value.day))
            button.setEnabled(in_month)
            button.setProperty("outsideMonth", not in_month)
            button.setProperty("hasAgenda", has_agenda)
            button.setProperty("tone", tone)
            button.setProperty("selected", day_value == self.agenda_calendar_selected_date)
            button.setProperty("today", day_value == today_value)
            button.setProperty("agendaDate", day_value.isoformat())
            if has_agenda:
                tooltip_parts = [self.customer_label(row.cliente_codigo, row.cliente_nombre) for row in rows_for_day[:4]]
                extra = "" if len(rows_for_day) <= 4 else f"\n+{len(rows_for_day) - 4} más"
                button.setToolTip("\n".join(tooltip_parts) + extra)
            else:
                button.setToolTip("")
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

        self._refresh_agenda_day_detail(today_value=today_value)

    def _handle_agenda_calendar_button(self, button: QPushButton) -> None:
        raw_value = str(button.property("agendaDate") or "").strip()
        try:
            year, month, day = [int(part) for part in raw_value.split("-")]
        except Exception:
            return
        self.agenda_calendar_selected_date = date(year, month, day)
        self._refresh_agenda_calendar(today_value=date.today())

    def _shift_agenda_calendar_month(self, offset: int) -> None:
        current_month = self.agenda_calendar_month.replace(day=1)
        month_index = (current_month.year * 12 + (current_month.month - 1)) + int(offset or 0)
        next_year = month_index // 12
        next_month = (month_index % 12) + 1
        self.agenda_calendar_month = date(next_year, next_month, 1)
        selected_day = min(self.agenda_calendar_selected_date.day, calendar.monthrange(next_year, next_month)[1])
        self.agenda_calendar_selected_date = date(next_year, next_month, selected_day)
        self.agenda_month_label.setText(self._agenda_month_title(self.agenda_calendar_month))
        self._refresh_agenda_calendar(today_value=date.today())

    def _agenda_month_rows(self, month_start: date) -> list[DashboardActivityRow]:
        return [
            row for row in self.agenda_calendar_rows
            if row.due_date.year == month_start.year and row.due_date.month == month_start.month
        ]

    def _agenda_rows_for_date(self, day_value: date) -> list[DashboardActivityRow]:
        rows = [row for row in self.agenda_calendar_rows if row.due_date == day_value]
        return sorted(rows, key=CustomerDashboardService._today_sort_key)

    def _agenda_day_tone(self, rows: list[DashboardActivityRow], *, today_value: date) -> str:
        if not rows:
            return "none"
        if any(self._is_overdue_activity(row, today_value) for row in rows):
            return "red"
        if any(self._agenda_state_group(row.estado) in {"pending", "postponed"} for row in rows):
            return "blue"
        if any(self._agenda_state_group(row.estado) == "completed" for row in rows):
            return "green"
        return "muted"

    def _refresh_agenda_day_detail(self, *, today_value: date) -> None:
        selected_rows = self._agenda_rows_for_date(self.agenda_calendar_selected_date)
        self.agenda_month_detail_title.setText(f"Agenda del {self.format_date(self.agenda_calendar_selected_date)}")
        self._clear_layout(self.agenda_month_detail_layout)
        if not selected_rows:
            self.agenda_month_detail_layout.addWidget(self._calendar_detail_empty_label("No hay actividades para el día seleccionado."))
            return
        for row in selected_rows[:2]:
            self.agenda_month_detail_layout.addWidget(self._build_calendar_detail_row(row, today_value=today_value))
        if len(selected_rows) > 2:
            self.agenda_month_detail_layout.addWidget(self._calendar_detail_empty_label(f"+{len(selected_rows) - 2} actividad(es) más en este día."))

    def _build_calendar_detail_row(self, row: DashboardActivityRow, *, today_value: date) -> QFrame:
        frame = QFrame()
        frame.setObjectName("dashboardUpcomingRow")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        accent_label = QLabel(self.agenda_type_label(row.tipo))
        accent_label.setObjectName("dashboardUpcomingDate")
        accent_label.setMinimumWidth(72)
        layout.addWidget(accent_label, 0)

        text = QLabel(row.resumen or self.customer_label(row.cliente_codigo, row.cliente_nombre))
        text.setObjectName("dashboardUpcomingText")
        text.setWordWrap(True)
        layout.addWidget(text, 1)

        meta = QLabel(self.customer_label(row.cliente_codigo, row.cliente_nombre))
        meta.setObjectName("dashboardActivityDetail")
        meta.setWordWrap(True)
        layout.addWidget(meta, 1)

        state = QLabel(self.agenda_state_label(row.estado) if not self._is_overdue_activity(row, today_value) else "Vencida")
        state.setObjectName("dashboardUpcomingState")
        fg_color = "#DC2626" if self._is_overdue_activity(row, today_value) else self._state_palette(row.estado)[0]
        bg_color = "#FEE2E2" if self._is_overdue_activity(row, today_value) else self._state_palette(row.estado)[1]
        state.setStyleSheet(
            "QLabel#dashboardUpcomingState {"
            f"background: {bg_color}; color: {fg_color}; padding: 2px 8px; border-radius: 999px;"
            "font-weight: 600;"
            "}"
        )
        layout.addWidget(state, 0)
        return frame

    @staticmethod
    def _agenda_state_group(state: str) -> str:
        normalized = str(state or "").strip().lower()
        if normalized == "hecho":
            return "completed"
        if normalized == "aplazado":
            return "postponed"
        if normalized == "cancelado":
            return "cancelled"
        return "pending"

    def _is_overdue_activity(self, row: DashboardActivityRow, today_value: date) -> bool:
        return row.due_date < today_value and self._agenda_state_group(row.estado) not in {"completed", "cancelled"}

    def _agenda_month_title(self, value: date) -> str:
        months = [
            "enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
        ]
        return f"{months[value.month - 1].capitalize()} {value.year}"

    def _build_activity_card(self, row: DashboardActivityRow) -> QFrame:
        accent, badge_bg = self._type_palette(row.tipo)
        fg_color, bg_color = self._state_palette(row.estado)

        card = QFrame()
        card.setObjectName("dashboardActivityCard")
        card.setStyleSheet(
            "QFrame#dashboardActivityCard {"
            f"background: #FFFFFF; border: 1px solid #E2E8F1; border-left: 4px solid {accent}; border-radius: 10px;"
            "}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)
        customer_label = QLabel(self.customer_label(row.cliente_codigo, row.cliente_nombre))
        customer_label.setObjectName("dashboardActivityCustomer")
        top_row.addWidget(customer_label, 1)
        state_label = QLabel(self.agenda_state_label(row.estado))
        state_label.setObjectName("dashboardStatePill")
        state_label.setStyleSheet(
            "QLabel#dashboardStatePill {"
            f"background: {bg_color}; color: {fg_color}; border: 1px solid {bg_color};"
            "padding: 3px 10px; border-radius: 999px; font-weight: 600;"
            "}"
        )
        top_row.addWidget(state_label, 0)
        edit_btn = QPushButton("Editar")
        edit_btn.setProperty("btnRole", "secondary")
        edit_btn.clicked.connect(lambda _checked=False, agenda_id=row.agenda_id: self._open_activity_dialog(agenda_id=agenda_id))
        top_row.addWidget(edit_btn, 0)
        layout.addLayout(top_row)

        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(0, 0, 0, 0)
        meta_row.setSpacing(6)
        meta_row.addWidget(self._meta_badge(self.agenda_type_label(row.tipo), badge_bg, "#1F2937"))
        meta_row.addWidget(self._meta_badge(row.isla_nombre or "Sin isla", "#EEF2FF", "#3730A3"))
        follow_up_text = (
            f"Seguimiento {self.format_date(row.fecha_seguimiento)}"
            if row.fecha_seguimiento is not None
            else f"Actividad {self.format_date(row.fecha_actividad)}"
        )
        meta_row.addWidget(self._meta_badge(follow_up_text, "#F8FAFC", "#475569"))
        if row.responsable:
            meta_row.addWidget(self._meta_badge(row.responsable, "#ECFDF3", "#067647"))
        meta_row.addStretch(1)
        layout.addLayout(meta_row)

        summary_label = QLabel(row.resumen or row.detalle or "-")
        summary_label.setWordWrap(True)
        summary_label.setObjectName("dashboardActivitySummary")
        layout.addWidget(summary_label)

        if row.detalle and row.detalle.strip() and row.detalle.strip() != row.resumen.strip():
            detail_label = QLabel(row.detalle.strip())
            detail_label.setWordWrap(True)
            detail_label.setObjectName("dashboardActivityDetail")
            layout.addWidget(detail_label)

        return card

    def _meta_badge(self, text: str, background: str, foreground: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("dashboardMetaBadge")
        label.setStyleSheet(
            "QLabel#dashboardMetaBadge {"
            f"background: {background}; color: {foreground}; padding: 3px 8px; border-radius: 999px;"
            "font-size: 12px; font-weight: 500;"
            "}"
        )
        return label

    def _empty_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("dashboardEmptyLabel")
        label.setWordWrap(True)
        return label

    def _calendar_detail_empty_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("dashboardCalendarDetailEmptyLabel")
        label.setWordWrap(True)
        return label

    def _populate_reactivation_table(self, rows: list[DashboardReactivationRow]) -> None:
        self.reactivation_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                QTableWidgetItem(self.customer_label(row.cliente_codigo, row.cliente_nombre)),
                QTableWidgetItem(row.isla_nombre or "Sin isla"),
                QTableWidgetItem(self.format_date(row.last_contact, allow_blank=True) or "Sin registro"),
                QTableWidgetItem(self.format_kg(row.delta_kg, signed=True, suffix=" kg")),
                QTableWidgetItem(row.priority),
            ]
            for column, item in enumerate(values):
                if column in {3, 4}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column == 3:
                    item.setForeground(QColor("#DC2626") if row.delta_kg < 0 else QColor("#067647") if row.delta_kg > 0 else QColor("#475569"))
                    item.setData(Qt.ItemDataRole.UserRole, float(row.delta_kg or 0.0))
                self.reactivation_table.setItem(row_index, column, item)

    def _populate_island_table(self, snapshot: DashboardSnapshot) -> None:
        rows = snapshot.island_rows
        self.island_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row.isla_nombre,
                str(row.pending),
                str(row.postponed),
                str(row.completed),
                str(row.total),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column > 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.island_table.setItem(row_index, column, item)

    def _configure_table(self, table: QTableWidget) -> None:
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.verticalHeader().setVisible(False)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def _clear_layout(self, layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                self._clear_layout(child_layout)  # type: ignore[arg-type]

    @staticmethod
    def format_kg(value: float, *, signed: bool = False, suffix: str = "") -> str:
        number = float(value or 0.0)
        text = f"{number:+,.2f}" if signed else f"{number:,.2f}"
        text = text.replace(",", "_").replace(".", ",").replace("_", ".")
        return f"{text}{suffix}"

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("dashboardSidebar")
        sidebar.setFixedWidth(188)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(12)

        brand_logo = BASE_DIR / "assets" / "logos" / "corporativos" / "IREKS_Logo_transparente.png"
        brand_icon = self._path_data_uri(brand_logo, 92, color=None)
        brand = QLabel(f"<div align='center'><img src='{brand_icon}' width='92' height='92'/></div>")
        brand.setObjectName("dashboardSidebarBrand")
        brand.setTextFormat(Qt.TextFormat.RichText)
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(brand, 0, Qt.AlignmentFlag.AlignHCenter)

        agenda_btn = QPushButton("Agenda")
        agenda_btn.setObjectName("dashboardSidebarButton")
        agenda_btn.clicked.connect(lambda: self._set_dashboard_mode("agenda"))
        layout.addWidget(agenda_btn)
        self.dashboard_nav_buttons["agenda"] = agenda_btn

        almacen_btn = QPushButton("Almacen")
        almacen_btn.setObjectName("dashboardSidebarButton")
        almacen_btn.clicked.connect(lambda: self._set_dashboard_mode("almacen"))
        layout.addWidget(almacen_btn)
        self.dashboard_nav_buttons["almacen"] = almacen_btn

        pedidos_btn = QPushButton("Pedidos")
        pedidos_btn.setObjectName("dashboardSidebarButton")
        pedidos_btn.clicked.connect(lambda: self._set_dashboard_mode("pedidos"))
        layout.addWidget(pedidos_btn)
        self.dashboard_nav_buttons["pedidos"] = pedidos_btn

        ventas_btn = QPushButton("Ventas")
        ventas_btn.setObjectName("dashboardSidebarButton")
        ventas_btn.clicked.connect(lambda: self._set_dashboard_mode("ventas"))
        layout.addWidget(ventas_btn)
        self.dashboard_nav_buttons["ventas"] = ventas_btn

        objetivos_btn = QPushButton("Objetivos")
        objetivos_btn.setObjectName("dashboardSidebarButton")
        self._set_button_icon(objetivos_btn, "goal.svg", color="#475569", size=28)
        objetivos_btn.clicked.connect(lambda: self._show_placeholder_dashboard("Objetivos"))
        layout.addWidget(objetivos_btn)

        layout.addStretch(1)
        return sidebar

    def _show_placeholder_dashboard(self, name: str) -> None:
        QMessageBox.information(self, "Dashboard", f"El dashboard de {name} se implementará en una siguiente fase.")

    def _icon_path(self, icon_name: str) -> Path:
        return BASE_DIR / "assets" / "icons" / icon_name

    def _icon_pixmap(self, icon_name: str, size: int, *, color: str | None = None) -> QPixmap:
        path = self._icon_path(icon_name)
        if not path.exists():
            return QPixmap(size, size)

        pixmap = self._render_icon_source(path, size)
        pixmap = self._trim_transparent_margins(pixmap, size)
        if color is not None:
            pixmap = self._recolor_pixmap(pixmap, QColor(color))
        return self._compose_centered_pixmap(pixmap, size)

    def _set_button_icon(self, button: QPushButton, icon_name: str, *, color: str, size: int = 18) -> None:
        button.setIcon(QIcon(self._icon_pixmap(icon_name, size, color=color)))
        button.setIconSize(QSize(size, size))

    def _icon_data_uri(self, icon_name: str, size: int, *, color: str | None = None) -> str:
        return self._path_data_uri(self._icon_path(icon_name), size, color=color)

    def _path_data_uri(self, asset_path: Path, size: int, *, color: str | None = None) -> str:
        if not asset_path.exists():
            return ""
        pixmap = self._render_icon_source(asset_path, size)
        pixmap = self._trim_transparent_margins(pixmap, size)
        if color is not None:
            pixmap = self._recolor_pixmap(pixmap, QColor(color))
        pixmap = self._compose_centered_pixmap(pixmap, size)
        if pixmap.isNull():
            return ""
        buffer = QBuffer()
        buffer.open(QBuffer.OpenModeFlag.WriteOnly)
        pixmap.save(buffer, "PNG")
        payload = bytes(buffer.data().toBase64()).decode("ascii")
        return f"data:image/png;base64,{payload}"

    @staticmethod
    def _recolor_pixmap(pixmap: QPixmap, color: QColor) -> QPixmap:
        if pixmap.isNull():
            return pixmap
        tinted = QPixmap(pixmap.size())
        tinted.fill(Qt.GlobalColor.transparent)
        painter = QPainter(tinted)
        painter.drawPixmap(0, 0, pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(tinted.rect(), color)
        painter.end()
        return tinted

    @staticmethod
    def _render_icon_source(path: Path, target_size: int) -> QPixmap:
        render_size = max(target_size * 4, 64)
        if path.suffix.lower() == ".svg":
            renderer = QSvgRenderer(str(path))
            pixmap = QPixmap(render_size, render_size)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter, QRectF(0, 0, render_size, render_size))
            painter.end()
            return pixmap
        source = QPixmap(str(path))
        return source.scaled(render_size, render_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

    @staticmethod
    def _compose_centered_pixmap(pixmap: QPixmap, target_size: int) -> QPixmap:
        if pixmap.isNull():
            return pixmap
        canvas = QPixmap(target_size, target_size)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        x = (target_size - pixmap.width()) / 2
        y = (target_size - pixmap.height()) / 2
        painter.drawPixmap(int(round(x)), int(round(y)), pixmap)
        painter.end()
        return canvas

    @staticmethod
    def _trim_transparent_margins(pixmap: QPixmap, target_size: int) -> QPixmap:
        if pixmap.isNull():
            return pixmap
        image = pixmap.toImage()
        rect = image.rect()
        left = rect.right()
        top = rect.bottom()
        right = rect.left()
        bottom = rect.top()
        found = False
        for y in range(image.height()):
            for x in range(image.width()):
                if QColor(image.pixelColor(x, y)).alpha() > 0:
                    left = min(left, x)
                    top = min(top, y)
                    right = max(right, x)
                    bottom = max(bottom, y)
                    found = True
        if not found:
            return pixmap
        cropped = pixmap.copy(left, top, right - left + 1, bottom - top + 1)
        return cropped.scaled(target_size, target_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

    @staticmethod
    def _kpi_tone_color(tone: str) -> str:
        return {
            "blue": "#2563EB",
            "red": "#EF4444",
            "green": "#16A34A",
            "orange": "#F97316",
        }.get(tone, "#2563EB")

    def _open_new_activity(self) -> None:
        if not self.customer_choices():
            QMessageBox.warning(self, "Agenda", "No hay clientes disponibles para registrar actividades.")
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

    def _open_activity_dialog(self, *, agenda_id: str = "", default_customer_id: str = "") -> None:
        dialog = DashboardAgendaDialog(self, agenda_id=agenda_id, default_customer_id=default_customer_id, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.reload()

    @staticmethod
    def _type_palette(activity_type: str) -> tuple[str, str]:
        normalized = str(activity_type or "").strip().lower()
        palettes = {
            "visita_realizada": ("#2563EB", "#DBEAFE"),
            "visita_prevista": ("#1D4ED8", "#DBEAFE"),
            "llamada": ("#7C3AED", "#EDE9FE"),
            "seguimiento": ("#0F766E", "#DDF6F1"),
            "desarrollo_futuro": ("#B45309", "#FEF3C7"),
            "incidencia": ("#DC2626", "#FEE2E2"),
            "nota": ("#475569", "#E2E8F0"),
        }
        return palettes.get(normalized, ("#475569", "#E2E8F0"))

    @staticmethod
    def _state_palette(state: str) -> tuple[str, str]:
        normalized = str(state or "").strip().lower()
        if normalized == "hecho":
            return "#067647", "#ECFDF3"
        if normalized == "aplazado":
            return "#B54708", "#FFF7ED"
        if normalized == "cancelado":
            return "#6B7280", "#F1F5F9"
        return "#1D4ED8", "#EFF6FF"

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget#dashboardPageRoot {
                background: #EEF3F8;
            }
            QFrame#dashboardSidebar {
                background: #F8FAFC;
                border: none;
                border-right: 1px solid #E2E8F0;
            }
            QLabel#dashboardSidebarBrand {
                color: #0F172A;
                background: transparent;
                border: none;
                border-radius: 16px;
                padding: 8px;
            }
            QPushButton#dashboardSidebarButton {
                background: transparent;
                color: #334155;
                border: none;
                border-radius: 16px;
                padding: 14px 16px;
                text-align: left;
                font-size: 15px;
                font-weight: 600;
            }
            QPushButton#dashboardSidebarButton[active="true"] {
                background: #2563EB;
                color: #FFFFFF;
            }
            QWidget#dashboardContentHost,
            QWidget#dashboardContent,
            QWidget#dashboardAgendaView,
            QWidget#dashboardWarehouseView,
            QWidget#dashboardOrdersView,
            QWidget#dashboardSalesView {
                background: transparent;
            }
            QStackedWidget#dashboardContentStack {
                background: transparent;
                border: none;
            }
            QFrame#dashboardHeader {
                background: transparent;
                border: none;
            }
            QLabel#dashboardTitle {
                color: #0F172A;
                font-size: 26px;
                font-weight: 700;
            }
            QLabel#dashboardDateLabel {
                color: #475569;
                font-size: 13px;
            }
            QFrame#dashboardKpiCard {
                background: #FFFFFF;
                border: 1px solid #E2E8F1;
                border-radius: 14px;
            }
            QFrame#dashboardKpiIcon {
                background: #EFF6FF;
                border-radius: 32px;
                border: none;
            }
            QFrame#dashboardKpiIcon[tone="red"] {
                background: #FEF2F2;
            }
            QFrame#dashboardKpiIcon[tone="green"] {
                background: #F0FDF4;
            }
            QFrame#dashboardKpiIcon[tone="orange"] {
                background: #FFF7ED;
            }
            QFrame#dashboardKpiCard[tone="blue"] {
                border-bottom: 3px solid #2563EB;
            }
            QFrame#dashboardKpiCard[tone="red"] {
                border-bottom: 3px solid #DC2626;
            }
            QFrame#dashboardKpiCard[tone="green"] {
                border-bottom: 3px solid #16A34A;
            }
            QFrame#dashboardKpiCard[tone="orange"] {
                border-bottom: 3px solid #EA580C;
            }
            QLabel#dashboardKpiTitle {
                color: #334155;
                font-size: 13px;
                font-weight: 600;
            }
            QLabel#dashboardKpiValue {
                color: #0F172A;
                font-size: 30px;
                font-weight: 700;
            }
            QLabel#dashboardKpiNote {
                color: #64748B;
                font-size: 12px;
            }
            QFrame[dashboardPanel="true"] {
                background: #FFFFFF;
                border: 1px solid #DCE4EF;
                border-radius: 14px;
            }
            QLabel#dashboardPanelTitle {
                color: #0F172A;
                font-size: 16px;
                font-weight: 700;
            }
            QLabel#dashboardEmptyLabel {
                color: #64748B;
                background: #F8FAFC;
                border: 1px dashed #CBD5E1;
                border-radius: 10px;
                padding: 14px;
                font-size: 12px;
            }
            QLabel#dashboardActivityCustomer {
                color: #0F172A;
                font-size: 14px;
                font-weight: 700;
            }
            QLabel#dashboardActivitySummary {
                color: #1E293B;
                font-size: 13px;
                font-weight: 600;
            }
            QLabel#dashboardActivityDetail {
                color: #475569;
                font-size: 11px;
            }
            QFrame#dashboardUpcomingRow {
                background: #FFFFFF;
                border: 1px solid #E2E8F1;
                border-radius: 10px;
            }
            QPushButton#dashboardCalendarNavButton {
                background: #F8FAFC;
                border: 1px solid #DCE4EF;
                border-radius: 10px;
                min-width: 24px;
                min-height: 24px;
                max-width: 24px;
                max-height: 24px;
                color: #1D4ED8;
                font-size: 14px;
                font-weight: 700;
                padding: 0;
            }
            QLabel#dashboardMonthTitle {
                color: #0F172A;
                font-size: 16px;
                font-weight: 700;
            }
            QLabel#dashboardWeekdayLabel {
                color: #475569;
                font-size: 11px;
                font-weight: 700;
                min-height: 14px;
            }
            QFrame#dashboardMonthGrid {
                background: transparent;
                border: none;
            }
            QPushButton#dashboardMonthDayButton {
                background: #FFFFFF;
                border: 1px solid #E2E8F1;
                border-radius: 10px;
                color: #0F172A;
                font-size: 11px;
                font-weight: 600;
                padding: 0;
                text-align: center;
            }
            QPushButton#dashboardMonthDayButton[outsideMonth="true"] {
                color: #94A3B8;
                background: #F8FAFC;
                border-color: #EDF2F7;
            }
            QPushButton#dashboardMonthDayButton[hasAgenda="true"][tone="blue"] {
                background: #EFF6FF;
                color: #1D4ED8;
                border-color: #BFDBFE;
            }
            QPushButton#dashboardMonthDayButton[hasAgenda="true"][tone="green"] {
                background: #F0FDF4;
                color: #15803D;
                border-color: #BBF7D0;
            }
            QPushButton#dashboardMonthDayButton[hasAgenda="true"][tone="red"] {
                background: #FEF2F2;
                color: #DC2626;
                border-color: #FECACA;
            }
            QPushButton#dashboardMonthDayButton[hasAgenda="true"][tone="muted"] {
                background: #F8FAFC;
                color: #64748B;
                border-color: #CBD5E1;
            }
            QPushButton#dashboardMonthDayButton[selected="true"] {
                border: 2px solid #2563EB;
            }
            QPushButton#dashboardMonthDayButton[today="true"] {
                font-weight: 800;
            }
            QFrame#dashboardCalendarSummaryChip {
                border-radius: 10px;
                border: 1px solid #DCE4EF;
                background: #FFFFFF;
            }
            QFrame#dashboardCalendarSummaryChip[tone="blue"] {
                background: #EFF6FF;
                border-color: #BFDBFE;
            }
            QFrame#dashboardCalendarSummaryChip[tone="green"] {
                background: #F0FDF4;
                border-color: #BBF7D0;
            }
            QFrame#dashboardCalendarSummaryChip[tone="red"] {
                background: #FEF2F2;
                border-color: #FECACA;
            }
            QLabel#dashboardCalendarSummaryTitle {
                color: #334155;
                font-size: 12px;
                font-weight: 600;
            }
            QLabel#dashboardCalendarSummaryValue {
                color: #0F172A;
                font-size: 18px;
                font-weight: 800;
            }
            QLabel#dashboardUpcomingDate {
                color: #1D4ED8;
                font-weight: 700;
                min-width: 58px;
            }
            QLabel#dashboardUpcomingText {
                color: #1E293B;
                font-size: 12px;
            }
            QLabel#dashboardUpcomingSectionTitle {
                color: #334155;
                font-size: 12px;
                font-weight: 700;
                min-height: 16px;
            }
            QWidget#dashboardCalendarDetailContainer {
                background: transparent;
                border: none;
            }
            QLabel#dashboardCalendarDetailEmptyLabel {
                color: #64748B;
                background: #F8FAFC;
                border: 1px dashed #CBD5E1;
                border-radius: 10px;
                padding: 8px 10px;
                font-size: 11px;
            }
            QPushButton#dashboardPanelLinkButton {
                text-align: center;
            }
            QLabel#dashboardFooterLabel,
            QLabel#dashboardDialogSummary {
                color: #64748B;
                font-size: 11px;
            }
            QLabel#dashboardDialogTitle {
                color: #0F172A;
                font-size: 20px;
                font-weight: 700;
            }
            QTableWidget#dashboardReactivationTable,
            QTableWidget#dashboardIslandTable,
            QTableWidget#dashboardAgendaOverviewTable,
            QTableWidget#dashboardOrdersRecentTable,
            QTableWidget#dashboardOrdersPendingTable,
            QTableWidget#dashboardOrdersWarehouseTable,
            QTableWidget#dashboardOrdersStateTable {
                background: #FFFFFF;
                border: 1px solid #E2E8F1;
                border-radius: 10px;
                alternate-background-color: #F8FBFF;
                selection-background-color: #DBEAFE;
                selection-color: #0F172A;
            }
            QHeaderView::section {
                background: #F8FAFC;
                color: #334155;
                border: none;
                border-bottom: 1px solid #E2E8F1;
                padding: 6px 8px;
                font-weight: 700;
            }
            QCalendarWidget#dashboardPopupCalendar QWidget#qt_calendar_navigationbar {
                background: #FFFFFF;
                border-bottom: 1px solid #D7DEE8;
            }
            QCalendarWidget#dashboardPopupCalendar QAbstractItemView::item {
                min-width: 30px;
                min-height: 26px;
            }
            """
        )
