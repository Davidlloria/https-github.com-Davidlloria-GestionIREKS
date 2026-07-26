from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import QDate, QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
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


class DashboardPage(QWidget):
    def __init__(
        self,
        *,
        customer_service: CustomerService | None = None,
        dashboard_service: CustomerDashboardService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.customer_service = customer_service or CustomerService()
        self.dashboard_service = dashboard_service or CustomerDashboardService()
        self.setObjectName('dashboardPageRoot')
        self.agenda_calendar_selected_date = date.today()
        self.agenda_calendar_rows: list[DashboardActivityRow] = []
        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName('dashboardSidebar')
        sidebar.setFixedWidth(184)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 22, 16, 18)
        sidebar_layout.setSpacing(24)

        brand = QLabel()
        brand.setObjectName('dashboardSidebarBrand')
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_path = BASE_DIR / 'assets' / 'logos' / 'corporativos' / 'IREKS_Logo_transparente.png'
        if brand_path.exists():
            brand.setPixmap(QPixmap(str(brand_path)).scaledToWidth(140, Qt.TransformationMode.SmoothTransformation))
        sidebar_layout.addWidget(brand)

        agenda_btn = QPushButton('Agenda')
        agenda_btn.setObjectName('dashboardSidebarButton')
        agenda_btn.setProperty('active', True)
        agenda_btn.setEnabled(False)
        agenda_btn.setIcon(self._icon('calendar-days.svg'))
        agenda_btn.setIconSize(QSize(20, 20))
        agenda_btn.setMinimumHeight(52)
        sidebar_layout.addWidget(agenda_btn)
        sidebar_layout.addStretch(1)
        root_layout.addWidget(sidebar)

        content_host = QWidget()
        content_host.setObjectName('dashboardContentHost')
        content_host_layout = QVBoxLayout(content_host)
        content_host_layout.setContentsMargins(0, 0, 0, 0)
        content_host_layout.setSpacing(0)

        content = QWidget()
        content.setObjectName('dashboardContent')
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
        self.new_activity_btn.setIcon(self._icon('plus.svg'))
        self.new_activity_btn.setIconSize(QSize(18, 18))
        self.new_activity_btn.clicked.connect(self._handle_primary_action)
        header_layout.addWidget(self.new_activity_btn)

        self.full_agenda_btn = QPushButton('Ver agenda completa')
        self.full_agenda_btn.setObjectName('dashboardFullAgendaButton')
        self.full_agenda_btn.setIcon(self._icon('calendar.svg'))
        self.full_agenda_btn.setIconSize(QSize(18, 18))
        self.full_agenda_btn.clicked.connect(self._handle_secondary_action)
        header_layout.addWidget(self.full_agenda_btn)

        self.content_layout.addWidget(header)
        self.agenda_dashboard = self._build_agenda_dashboard()
        self.content_layout.addWidget(self.agenda_dashboard, 1)

        self.footer_label = QLabel('')
        self.footer_label.setObjectName('dashboardFooterLabel')
        self.footer_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.content_layout.addWidget(self.footer_label)
        self._apply_styles()

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
        for column, (key, title, icon_name) in enumerate([
            ('pending_today', 'Pendientes hoy', 'calendar.svg'),
            ('overdue', 'Vencidas', 'clock-3.svg'),
            ('completed_today', 'Completadas hoy', 'circle-check.svg'),
            ('customers_without_follow_up', 'Clientes sin seguimiento', 'users.svg'),
        ]):
            card, value_label, note_label = self._build_kpi_card(title, icon_name)
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

    def _build_kpi_card(self, title: str, icon_name: str) -> tuple[QFrame, QLabel, QLabel]:
        card = QFrame()
        card.setObjectName('dashboardKpiCard')
        card.setMinimumHeight(104)
        card.setMaximumHeight(118)
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout = QGridLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(3)
        icon_label = QLabel()
        icon_label.setObjectName('dashboardKpiIcon')
        icon_label.setPixmap(self._icon(icon_name).pixmap(QSize(22, 22)))
        icon_label.setFixedSize(38, 38)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label = QLabel(title)
        title_label.setObjectName('dashboardKpiTitle')
        title_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        value_label = QLabel('0')
        value_label.setObjectName('dashboardKpiValue')
        note_label = QLabel('')
        note_label.setObjectName('dashboardKpiNote')
        note_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(icon_label, 0, 0, 2, 1)
        layout.addWidget(title_label, 0, 1)
        layout.addWidget(value_label, 1, 1)
        layout.addWidget(note_label, 1, 2, Qt.AlignmentFlag.AlignBottom)
        layout.setColumnStretch(1, 1)
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
        self.pending_summary = self._build_summary_chip('Pendientes')
        self.done_summary = self._build_summary_chip('Hechas')
        self.overdue_summary = self._build_summary_chip('Vencidas')
        summary_row.addWidget(self.pending_summary[0])
        summary_row.addWidget(self.done_summary[0])
        summary_row.addWidget(self.overdue_summary[0])
        layout.addLayout(summary_row)
        return panel

    def _build_summary_chip(self, title: str) -> tuple[QFrame, QLabel]:
        frame = QFrame()
        frame.setObjectName('dashboardCalendarSummaryChip')
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

    def reload(self) -> None:
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
    def _icon(asset_name: str) -> QIcon:
        return QIcon(str(BASE_DIR / 'assets' / 'icons' / asset_name))

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget#dashboardPageRoot { background: #F1F5F9; font-family: "Segoe UI"; }
            QFrame#dashboardSidebar { background: #FFFFFF; border-right: 1px solid #DCE4EF; }
            QLabel#dashboardSidebarBrand { background: transparent; padding: 10px; }
            QPushButton#dashboardSidebarButton { background: #2563EB; color: #FFFFFF; border: none; border-radius: 14px; padding: 12px 18px; font-size: 16px; font-weight: 700; text-align: left; }
            QWidget#dashboardContentHost, QWidget#dashboardContent, QWidget#dashboardAgendaView { background: transparent; }
            QFrame#dashboardHeader { background: transparent; }
            QLabel#dashboardTitle { font-size: 30px; font-weight: 700; color: #0F172A; }
            QLabel#dashboardDateLabel { font-size: 14px; color: #64748B; }
            QPushButton#dashboardNewActivityButton { background: #2563EB; color: #FFFFFF; border: 1px solid #2563EB; border-radius: 12px; padding: 11px 16px; font-size: 14px; font-weight: 700; }
            QPushButton#dashboardFullAgendaButton, QPushButton#dashboardPanelLinkButton { background: #FFFFFF; color: #1D4ED8; border: 1px solid #CBD5E1; border-radius: 12px; padding: 11px 16px; font-size: 14px; font-weight: 700; }
            QPushButton#dashboardNewActivityButton:hover { background: #1D4ED8; }
            QPushButton#dashboardFullAgendaButton:hover, QPushButton#dashboardPanelLinkButton:hover { background: #EFF6FF; border-color: #93C5FD; }
            QFrame#dashboardKpiCard, QFrame[dashboardPanel='true'] { background: #FFFFFF; border: 1px solid #DCE4EF; border-radius: 16px; }
            QLabel#dashboardKpiIcon { background: #EFF6FF; border-radius: 10px; }
            QLabel#dashboardKpiTitle, QLabel#dashboardPanelTitle { color: #1E293B; font-size: 15px; font-weight: 700; }
            QLabel#dashboardKpiValue { color: #0F172A; font-size: 28px; font-weight: 800; }
            QLabel#dashboardKpiNote, QLabel#dashboardFooterLabel, QLabel#dashboardEmptyLabel, QLabel#dashboardActivityDetail { color: #64748B; font-size: 13px; }
            QLabel#dashboardActivityCustomer { color: #0F172A; font-size: 14px; font-weight: 700; }
            QLabel#dashboardActivitySummary { color: #1E293B; font-size: 13px; }
            QFrame#dashboardActivityCard { background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 10px; }
            QCalendarWidget#dashboardMonthCalendar { background: #FFFFFF; border: none; }
            QCalendarWidget#dashboardMonthCalendar QWidget#qt_calendar_navigationbar { background: #2563EB; border-radius: 8px; }
            QCalendarWidget#dashboardMonthCalendar QToolButton { color: #FFFFFF; background: transparent; border: none; font-weight: 700; padding: 5px; }
            QCalendarWidget#dashboardMonthCalendar QAbstractItemView { background: #FFFFFF; color: #334155; selection-background-color: #2563EB; selection-color: #FFFFFF; outline: none; }
            QFrame#dashboardCalendarSummaryChip { background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 10px; }
            QLabel#dashboardCalendarSummaryTitle { color: #475569; font-size: 12px; font-weight: 600; }
            QLabel#dashboardCalendarSummaryValue { color: #0F172A; font-size: 16px; font-weight: 800; }
            QTableWidget#dashboardReactivationTable, QTableWidget#dashboardIslandTable { background: #FFFFFF; alternate-background-color: #F8FAFC; border: none; color: #334155; }
            QHeaderView::section { background: #F8FAFC; color: #475569; padding: 7px; border: none; border-bottom: 1px solid #E2E8F0; font-weight: 700; }
            """
        )
