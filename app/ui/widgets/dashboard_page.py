from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCalendarWidget,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
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
    DashboardOrdersStateRow,
    DashboardOrdersWarehouseRow,
    OrderDashboardService,
)

BASE_DIR = Path(__file__).resolve().parents[3]


class DashboardMonthCalendar(QCalendarWidget):
    def __init__(self, page: 'DashboardPage', parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._page = page
        self.setObjectName('dashboardMonthCalendar')
        self.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.setNavigationBarVisible(True)
        self.selectionChanged.connect(self._on_selection_changed)

    def _on_selection_changed(self) -> None:
        selected = self.selectedDate()
        self._page.set_selected_date(date(selected.year(), selected.month(), selected.day()))

    def paintCell(self, painter: QPainter, rect, calendar_date: QDate) -> None:  # type: ignore[override]
        day_value = date(calendar_date.year(), calendar_date.month(), calendar_date.day())
        rows_for_day = self._page._agenda_rows_for_date(day_value)
        tone = self._page._agenda_day_tone(rows_for_day, today_value=date.today())
        in_month = calendar_date.month() == self.monthShown() and calendar_date.year() == self.yearShown()
        selected = calendar_date == self.selectedDate()

        background = QColor('#FFFFFF')
        border = QColor('#E2E8F0')
        text_color = QColor('#0F172A')
        if not in_month:
            background = QColor('#F8FAFC')
            border = QColor('#E2E8F0')
            text_color = QColor('#94A3B8')
        elif tone == 'blue':
            background = QColor('#EFF6FF')
            border = QColor('#BFDBFE')
            text_color = QColor('#1D4ED8')
        elif tone == 'green':
            background = QColor('#F0FDF4')
            border = QColor('#BBF7D0')
            text_color = QColor('#15803D')
        elif tone == 'red':
            background = QColor('#FEF2F2')
            border = QColor('#FECACA')
            text_color = QColor('#DC2626')

        if selected:
            border = QColor('#2563EB')

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(Qt.GlobalColor.transparent)
        painter.drawRect(rect)
        painter.setBrush(background)
        pen = painter.pen()
        pen.setColor(border)
        pen.setWidth(2 if selected else 1)
        painter.setPen(pen)
        cell_rect = rect.adjusted(2, 2, -2, -2)
        painter.drawRoundedRect(cell_rect, 8, 8)
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        painter.setPen(text_color)
        painter.drawText(cell_rect, int(Qt.AlignmentFlag.AlignCenter), str(calendar_date.day()))
        painter.restore()


class DashboardPage(QWidget):
    def __init__(
        self,
        *,
        customer_service: CustomerService | None = None,
        dashboard_service: CustomerDashboardService | None = None,
        order_dashboard_service: OrderDashboardService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.customer_service = customer_service or CustomerService()
        self.dashboard_service = dashboard_service or CustomerDashboardService()
        self.order_dashboard_service = order_dashboard_service or OrderDashboardService()
        self.setObjectName('dashboardPageRoot')
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.agenda_calendar_selected_date = date.today()
        self.agenda_calendar_rows: list[DashboardActivityRow] = []
        self.current_dashboard = 'agenda'
        self.dashboard_nav_buttons: dict[str, QPushButton] = {}
        self._build_ui()
        self.reload()

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
        self.dashboard_stack.addWidget(self.agenda_dashboard)
        self.dashboard_stack.addWidget(self.orders_dashboard)
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
            card, value_label, note_label = self._build_kpi_card(title, tone, icon_name)
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
        self.today_link_btn = QPushButton('Ver toda la agenda')
        self.today_link_btn.setObjectName('dashboardPanelLinkButton')
        self.today_link_btn.clicked.connect(self._handle_secondary_action)
        today_panel.layout().addWidget(self.today_link_btn)
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

    def _build_kpi_card(self, title: str, tone: str, icon_name: str) -> tuple[QFrame, QLabel, QLabel]:
        card = QFrame()
        card.setObjectName('dashboardKpiCard')
        card.setProperty('tone', tone)
        card.setMinimumHeight(118)
        card.setMaximumHeight(118)
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
        note_label = QLabel('')
        note_label.setObjectName('dashboardKpiNote')
        note_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        text_layout.addWidget(title_label)
        text_layout.addSpacing(2)
        text_layout.addWidget(value_label)
        text_layout.addWidget(note_label)
        text_layout.addStretch(1)

        layout.addWidget(icon_wrap, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(text_layout, 1)
        return card, value_label, note_label

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
        heading.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(heading)
        container = QVBoxLayout()
        container.setContentsMargins(0, 0, 0, 0)
        container.setSpacing(8)
        empty = QLabel(empty_text)
        empty.setObjectName('dashboardEmptyLabel')
        empty.setWordWrap(True)
        empty.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        container.addWidget(empty)
        layout.addLayout(container)
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
        panel.setMinimumWidth(390)
        panel.setMinimumHeight(205)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        heading = QLabel('Agenda del mes')
        heading.setObjectName('dashboardPanelTitle')
        heading.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(heading)

        self.agenda_month_calendar = DashboardMonthCalendar(self, panel)
        self.agenda_month_calendar.setMinimumHeight(190)
        layout.addWidget(self.agenda_month_calendar)

        summary_row = QHBoxLayout()
        summary_row.setContentsMargins(0, 0, 0, 0)
        summary_row.setSpacing(8)
        self.pending_summary = self._build_summary_chip('Pendientes', 'blue')
        self.done_summary = self._build_summary_chip('Hechas', 'green')
        self.overdue_summary = self._build_summary_chip('Vencidas', 'red')
        summary_row.addWidget(self.pending_summary[0])
        summary_row.addWidget(self.done_summary[0])
        summary_row.addWidget(self.overdue_summary[0])
        layout.addLayout(summary_row)
        return panel

    def _build_summary_chip(self, title: str, tone: str) -> tuple[QFrame, QLabel]:
        frame = QFrame()
        frame.setObjectName('dashboardCalendarSummaryChip')
        frame.setProperty('tone', tone)
        inner = QHBoxLayout(frame)
        inner.setContentsMargins(10, 8, 10, 8)
        inner.setSpacing(8)
        title_label = QLabel(title)
        title_label.setObjectName('dashboardCalendarSummaryTitle')
        value_label = QLabel('0')
        value_label.setObjectName('dashboardCalendarSummaryValue')
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
        self.orders_kpi_notes: dict[str, QLabel] = {}
        for column, (key, title, tone, icon_name) in enumerate([
            ('total_orders', 'Pedidos', 'blue', 'shopping-cart.svg'),
            ('received_kg', 'Kg recibidos', 'green', 'package-check.svg'),
            ('pending_kg', 'Kg pendientes', 'orange', 'package-open.svg'),
            ('incident_orders', 'Incidencias', 'red', 'alert.svg'),
        ]):
            card, value_label, note_label = self._build_kpi_card(title, tone, icon_name)
            self.orders_kpi_labels[key] = value_label
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
        self.orders_recent_table.setHorizontalHeaderLabels(['Pedido', 'Almac?n', 'Fecha', 'Kg pedido', 'Kg recibido', 'Kg pend.', 'Estado'])
        self._configure_table(self.orders_recent_table)
        recent_header = self.orders_recent_table.horizontalHeader()
        recent_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        recent_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        recent_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        for col in (3, 4, 5, 6):
            recent_header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        recent_panel.layout().addWidget(self.orders_recent_table)
        upper_row.addWidget(recent_panel, 6)

        pending_panel = self._build_table_panel('M?s pendiente', 'dashboardOrdersPendingPanel')
        self.orders_pending_table = QTableWidget(0, 4)
        self.orders_pending_table.setObjectName('dashboardOrdersPendingTable')
        self.orders_pending_table.setHorizontalHeaderLabels(['Fecha', 'Pedido', 'Almac?n', 'Kg pend.'])
        self._configure_table(self.orders_pending_table)
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

        warehouse_panel = self._build_table_panel('M?s pendiente por almac?n', 'dashboardOrdersWarehousePanel')
        self.orders_warehouse_table = QTableWidget(0, 4)
        self.orders_warehouse_table.setObjectName('dashboardOrdersWarehouseTable')
        self.orders_warehouse_table.setHorizontalHeaderLabels(['Almac?n', 'Abiertos', 'Kg pend.', '?lt. recepci?n'])
        self._configure_table(self.orders_warehouse_table)
        warehouse_header = self.orders_warehouse_table.horizontalHeader()
        warehouse_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        warehouse_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        warehouse_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        warehouse_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        warehouse_panel.layout().addWidget(self.orders_warehouse_table)
        lower_row.addWidget(warehouse_panel, 5)

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

    def reload(self) -> None:
        if self.current_dashboard == 'pedidos':
            self._reload_orders_dashboard()
        else:
            self._reload_agenda_dashboard()

    def _reload_agenda_dashboard(self) -> None:
        snapshot = self.dashboard_service.load_snapshot()
        self.date_label.setText(self.format_date(date.today(), long=True))
        self.kpi_labels['pending_today'].setText(str(snapshot.pending_today))
        self.kpi_notes['pending_today'].setText('actividades')
        self.kpi_labels['overdue'].setText(str(snapshot.overdue))
        self.kpi_notes['overdue'].setText('actividades')
        self.kpi_labels['completed_today'].setText(str(snapshot.completed_today))
        self.kpi_notes['completed_today'].setText('actividades')
        self.kpi_labels['customers_without_follow_up'].setText(str(snapshot.customers_without_follow_up))
        self.kpi_notes['customers_without_follow_up'].setText('clientes')
        self._reload_today_panel(snapshot.today_items, self.agenda_calendar_selected_date)
        self._reload_reactivation_table(snapshot.reactivation_rows)
        self._reload_island_table(snapshot.island_rows)
        self._reload_agenda_calendar_panel(self.dashboard_service.list_all_activities(), today_value=date.today())
        self.footer_label.setText(
            f'Última actualización: {snapshot.generated_at.strftime("%d/%m/%Y %H:%M")} · {snapshot.reactivation_metric_label}'
        )

    def _reload_today_panel(self, rows: list[DashboardActivityRow], selected_day: date) -> None:
        while self.today_items_layout.count():
            item = self.today_items_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if selected_day == date.today():
            self.today_panel_title.setText('Agenda de hoy')
        else:
            self.today_panel_title.setText(f'Agenda del {self.format_date(selected_day)}')
        filtered = [row for row in rows if row.fecha_actividad == selected_day] if selected_day != date.today() else list(rows)
        if not filtered:
            empty = QLabel('No hay actividades para el día seleccionado.')
            empty.setObjectName('dashboardEmptyLabel')
            empty.setWordWrap(True)
            empty.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            self.today_items_layout.addWidget(empty)
            return
        for row in filtered:
            card = QFrame()
            card.setObjectName('dashboardActivityCard')
            layout = QVBoxLayout(card)
            layout.setContentsMargins(10, 10, 10, 10)
            layout.setSpacing(4)
            customer = QLabel(f'{row.cliente_codigo} · {row.cliente_nombre}')
            customer.setObjectName('dashboardActivityCustomer')
            summary = QLabel(row.resumen)
            summary.setObjectName('dashboardActivitySummary')
            detail = QLabel(f'{row.isla_nombre} · {row.estado}')
            detail.setObjectName('dashboardActivityDetail')
            layout.addWidget(customer)
            layout.addWidget(summary)
            layout.addWidget(detail)
            self.today_items_layout.addWidget(card)

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
        self.agenda_calendar_rows = rows
        selected = self.agenda_calendar_selected_date
        self.agenda_month_calendar.setSelectedDate(QDate(selected.year, selected.month, selected.day))
        pending = sum(1 for row in rows if row.fecha_actividad == selected and self._state_group(row.estado) not in {'completed', 'cancelled'})
        done = sum(1 for row in rows if row.fecha_actividad == selected and self._state_group(row.estado) == 'completed')
        overdue = sum(1 for row in rows if row.due_date == selected and row.due_date < today_value and self._state_group(row.estado) not in {'completed', 'cancelled'})
        self.pending_summary[1].setText(str(pending))
        self.done_summary[1].setText(str(done))
        self.overdue_summary[1].setText(str(overdue))

    def set_selected_date(self, selected_day: date) -> None:
        self.agenda_calendar_selected_date = selected_day
        self._reload_today_panel(self.dashboard_service.list_all_activities(), selected_day)
        self._reload_agenda_calendar_panel(self.dashboard_service.list_all_activities(), today_value=date.today())

    def _handle_primary_action(self) -> None:
        QMessageBox.information(self, 'Agenda', 'La creación de actividades se incorporará en el siguiente corte limpio.')

    def _handle_secondary_action(self) -> None:
        QMessageBox.information(self, 'Agenda', 'La vista completa de agenda se incorporará en el siguiente corte limpio.')


    def _set_dashboard_mode(self, mode: str, *, reload: bool = True) -> None:
        clean_mode = mode if mode in {'agenda', 'pedidos'} else 'agenda'
        self.current_dashboard = clean_mode
        for key, button in self.dashboard_nav_buttons.items():
            active = key == clean_mode
            button.setProperty('active', active)
            icon_name = 'calendar-days.svg' if key == 'agenda' else 'shopping-cart.svg'
            self._set_button_icon(button, icon_name, '#FFFFFF' if active else '#475569', 20)
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()
        self.dashboard_stack.setCurrentWidget(self.agenda_dashboard if clean_mode == 'agenda' else self.orders_dashboard)
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
            self._set_button_icon(self.full_agenda_btn, 'package-open.svg', '#2563EB', 18)
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
        self.orders_kpi_labels['received_kg'].setText(self._format_number_es(snapshot.received_kg, suffix=' kg'))
        self.orders_kpi_notes['received_kg'].setText('kg recibidos')
        self.orders_kpi_labels['pending_kg'].setText(self._format_number_es(snapshot.pending_kg, suffix=' kg'))
        self.orders_kpi_notes['pending_kg'].setText('kg pendientes')
        self.orders_kpi_labels['incident_orders'].setText(str(snapshot.incident_orders))
        self.orders_kpi_notes['incident_orders'].setText('pedido(s)')
        self._populate_order_recent_table(snapshot.recent_orders)
        self._populate_order_pending_table(snapshot.pending_orders)
        self._populate_order_warehouse_table(snapshot.warehouse_rows)
        self._populate_order_state_table(snapshot.state_rows)
        self.footer_label.setText(
            f'?ltima actualizaci?n: {snapshot.generated_at.strftime("%d/%m/%Y %H:%M")} ? Dashboard pedidos {snapshot.year}'
        )

    def _populate_order_recent_table(self, rows: list[DashboardOrderRow]) -> None:
        self.orders_recent_table.setRowCount(len(rows))
        for idx, row in enumerate(rows):
            values = [
                row.pedido_numero,
                row.almacen_nombre or row.almacen_id,
                self.format_date(row.pedido_fecha),
                self._format_number_es(row.ordered_kg, suffix=' kg'),
                self._format_number_es(row.received_kg, suffix=' kg'),
                self._format_number_es(row.pending_kg, suffix=' kg'),
                row.status.capitalize(),
            ]
            for col, value in enumerate(values):
                self.orders_recent_table.setItem(idx, col, QTableWidgetItem(value))

    def _populate_order_pending_table(self, rows: list[DashboardOrderRow]) -> None:
        self.orders_pending_table.setRowCount(len(rows))
        for idx, row in enumerate(rows):
            values = [
                self.format_date(row.pedido_fecha),
                row.pedido_numero,
                row.almacen_nombre or row.almacen_id,
                self._format_number_es(row.pending_kg, suffix=' kg'),
            ]
            for col, value in enumerate(values):
                self.orders_pending_table.setItem(idx, col, QTableWidgetItem(value))

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

    def _open_orders_page(self) -> None:
        window = self.window()
        page_names = getattr(window, 'page_names', None)
        setter = getattr(window, '_set_current_page', None)
        if isinstance(page_names, list) and callable(setter) and 'Pedidos' in page_names:
            setter(page_names.index('Pedidos'))
            return
        QMessageBox.information(self, 'Pedidos', 'La vista completa de pedidos no est? disponible desde este contexto.')

    def _agenda_rows_for_date(self, day_value: date) -> list[DashboardActivityRow]:
        return [row for row in self.agenda_calendar_rows if row.fecha_actividad == day_value]

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
    def format_date(value: date | None, *, long: bool = False) -> str:
        if value is None:
            return ''
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
            QWidget#dashboardContentHost, QWidget#dashboardContent, QWidget#dashboardAgendaView, QWidget#dashboardOrdersView, QStackedWidget#dashboardContentStack { background-color: transparent; }
            QFrame#dashboardHeader { background-color: transparent; }
            QLabel#dashboardTitle { font-size: 30px; font-weight: 700; color: #0F172A; }
            QLabel#dashboardDateLabel { font-size: 14px; color: #64748B; }
            QPushButton#dashboardNewActivityButton {
                background-color: #2563EB; color: #FFFFFF; border: 1px solid #2563EB;
                border-radius: 12px; padding: 11px 16px; font-size: 14px; font-weight: 700;
            }
            QPushButton#dashboardFullAgendaButton, QPushButton#dashboardPanelLinkButton {
                background-color: #FFFFFF; color: #1D4ED8; border: 1px solid #CBD5E1;
                border-radius: 12px; padding: 11px 16px; font-size: 14px; font-weight: 700;
            }
            QPushButton#dashboardNewActivityButton:hover { background-color: #1D4ED8; }
            QPushButton#dashboardFullAgendaButton:hover, QPushButton#dashboardPanelLinkButton:hover {
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
            QLabel#dashboardKpiNote, QLabel#dashboardFooterLabel, QLabel#dashboardEmptyLabel, QLabel#dashboardActivityDetail {
                color: #64748B; font-size: 13px;
            }
            QLabel#dashboardActivityCustomer { color: #0F172A; font-size: 14px; font-weight: 700; }
            QLabel#dashboardActivitySummary { color: #1E293B; font-size: 13px; }
            QFrame#dashboardActivityCard { background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 10px; }
            QCalendarWidget#dashboardMonthCalendar { background-color: #FFFFFF; border: none; }
            QCalendarWidget#dashboardMonthCalendar QWidget#qt_calendar_navigationbar { background-color: #2563EB; border-radius: 8px; }
            QCalendarWidget#dashboardMonthCalendar QToolButton {
                color: #FFFFFF; background-color: transparent; border: none; font-weight: 700; padding: 5px;
            }
            QCalendarWidget#dashboardMonthCalendar QAbstractItemView {
                background-color: #FFFFFF; color: #334155; selection-background-color: #2563EB;
                selection-color: #FFFFFF; outline: none;
            }
            QFrame#dashboardCalendarSummaryChip {
                background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 10px;
            }
            QFrame#dashboardCalendarSummaryChip[tone='blue'] { background-color: #EFF6FF; border-color: #BFDBFE; }
            QFrame#dashboardCalendarSummaryChip[tone='green'] { background-color: #F0FDF4; border-color: #BBF7D0; }
            QFrame#dashboardCalendarSummaryChip[tone='red'] { background-color: #FEF2F2; border-color: #FECACA; }
            QLabel#dashboardCalendarSummaryTitle { color: #475569; font-size: 12px; font-weight: 600; }
            QLabel#dashboardCalendarSummaryValue { color: #0F172A; font-size: 16px; font-weight: 800; }
            QTableWidget#dashboardReactivationTable, QTableWidget#dashboardIslandTable, QTableWidget#dashboardOrdersRecentTable, QTableWidget#dashboardOrdersPendingTable, QTableWidget#dashboardOrdersWarehouseTable, QTableWidget#dashboardOrdersStateTable {
                background-color: #FFFFFF; alternate-background-color: #F8FAFC; border: none; color: #334155;
            }
            QHeaderView::section {
                background-color: #F8FAFC; color: #475569; padding: 7px; border: none;
                border-bottom: 1px solid #E2E8F0; font-weight: 700;
            }
            """
        )
