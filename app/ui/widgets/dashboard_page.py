from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QPixmap
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
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(18, 18, 18, 18)
        sidebar_layout.setSpacing(16)

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
        self.content_layout.setContentsMargins(14, 6, 14, 6)
        self.content_layout.setSpacing(8)
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
        header_copy.addWidget(self.date_label)
        header_layout.addLayout(header_copy, 1)

        self.new_activity_btn = QPushButton('Nueva actividad')
        self.new_activity_btn.setObjectName('dashboardNewActivityButton')
        self.new_activity_btn.clicked.connect(self._handle_primary_action)
        header_layout.addWidget(self.new_activity_btn)

        self.full_agenda_btn = QPushButton('Ver agenda completa')
        self.full_agenda_btn.setObjectName('dashboardFullAgendaButton')
        self.full_agenda_btn.clicked.connect(self._handle_secondary_action)
        header_layout.addWidget(self.full_agenda_btn)

        self.content_layout.addWidget(header)
        self.agenda_dashboard = self._build_agenda_dashboard()
        self.content_layout.addWidget(self.agenda_dashboard, 1)

        self.footer_label = QLabel('')
        self.footer_label.setObjectName('dashboardFooterLabel')
        self.content_layout.addWidget(self.footer_label)
        self._apply_styles()

    def _build_agenda_dashboard(self) -> QWidget:
        widget = QWidget()
        widget.setObjectName('dashboardAgendaView')
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        kpi_row = QGridLayout()
        kpi_row.setHorizontalSpacing(12)
        kpi_row.setVerticalSpacing(12)
        self.kpi_labels: dict[str, QLabel] = {}
        self.kpi_notes: dict[str, QLabel] = {}
        for column, (key, title) in enumerate([
            ('pending_today', 'Pendientes hoy'),
            ('overdue', 'Vencidas'),
            ('completed_today', 'Completadas hoy'),
            ('customers_without_follow_up', 'Clientes sin seguimiento'),
        ]):
            card, value_label, note_label = self._build_kpi_card(title)
            self.kpi_labels[key] = value_label
            self.kpi_notes[key] = note_label
            kpi_row.addWidget(card, 0, column)
        layout.addLayout(kpi_row)

        middle_row = QHBoxLayout()
        middle_row.setContentsMargins(0, 0, 0, 0)
        middle_row.setSpacing(14)
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
        middle_row.addWidget(self.upcoming_panel, 2)
        middle_row.addWidget(today_panel, 5)
        layout.addLayout(middle_row)

        lower_row = QHBoxLayout()
        lower_row.setContentsMargins(0, 0, 0, 0)
        lower_row.setSpacing(14)

        reactivation_panel = self._build_table_panel('Clientes a reactivar', 'dashboardReactivationPanel')
        self.reactivation_table = QTableWidget(0, 5)
        self.reactivation_table.setObjectName('dashboardReactivationTable')
        self.reactivation_table.setHorizontalHeaderLabels(['Cliente', 'Isla', '?ltimo contacto', 'Variaci?n kg', 'Prioridad'])
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
        layout.addLayout(lower_row)
        return widget

    def _build_kpi_card(self, title: str) -> tuple[QFrame, QLabel, QLabel]:
        card = QFrame()
        card.setObjectName('dashboardKpiCard')
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)
        title_label = QLabel(title)
        title_label.setObjectName('dashboardKpiTitle')
        value_label = QLabel('0')
        value_label.setObjectName('dashboardKpiValue')
        note_label = QLabel('')
        note_label.setObjectName('dashboardKpiNote')
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addWidget(note_label)
        layout.addStretch(1)
        return card, value_label, note_label

    def _build_list_panel(self, title: str, object_name: str, *, empty_text: str) -> tuple[QFrame, QVBoxLayout, QLabel]:
        panel = QFrame()
        panel.setObjectName(object_name)
        panel.setProperty('dashboardPanel', True)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        heading = QLabel(title)
        heading.setObjectName('dashboardPanelTitle')
        layout.addWidget(heading)
        container = QVBoxLayout()
        container.setContentsMargins(0, 0, 0, 0)
        container.setSpacing(8)
        empty = QLabel(empty_text)
        empty.setObjectName('dashboardEmptyLabel')
        container.addWidget(empty)
        layout.addLayout(container)
        return panel, container, heading

    def _build_table_panel(self, title: str, object_name: str) -> QFrame:
        panel = QFrame()
        panel.setObjectName(object_name)
        panel.setProperty('dashboardPanel', True)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        heading = QLabel(title)
        heading.setObjectName('dashboardPanelTitle')
        layout.addWidget(heading)
        return panel

    def _build_upcoming_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName('dashboardUpcomingPanel')
        panel.setProperty('dashboardPanel', True)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        heading = QLabel('Agenda del mes')
        heading.setObjectName('dashboardPanelTitle')
        layout.addWidget(heading)

        self.agenda_month_calendar = DashboardMonthCalendar(self, panel)
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
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(False)

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
            f'?ltima actualizaci?n: {snapshot.generated_at.strftime("%d/%m/%Y %H:%M")} ? {snapshot.reactivation_metric_label}'
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
            empty = QLabel('No hay actividades para el d?a seleccionado.')
            empty.setObjectName('dashboardEmptyLabel')
            self.today_items_layout.addWidget(empty)
            return
        for row in filtered:
            card = QFrame()
            card.setObjectName('dashboardActivityCard')
            layout = QVBoxLayout(card)
            layout.setContentsMargins(10, 10, 10, 10)
            layout.setSpacing(4)
            customer = QLabel(f'{row.cliente_codigo} ? {row.cliente_nombre}')
            customer.setObjectName('dashboardActivityCustomer')
            summary = QLabel(row.resumen)
            summary.setObjectName('dashboardActivitySummary')
            detail = QLabel(f'{row.isla_nombre} ? {row.estado}')
            detail.setObjectName('dashboardActivityDetail')
            layout.addWidget(customer)
            layout.addWidget(summary)
            layout.addWidget(detail)
            self.today_items_layout.addWidget(card)

    def _reload_reactivation_table(self, rows: list[DashboardReactivationRow]) -> None:
        self.reactivation_table.setRowCount(len(rows))
        for idx, row in enumerate(rows):
            values = [
                f'{row.cliente_codigo} ? {row.cliente_nombre}',
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
        QMessageBox.information(self, 'Agenda', 'La creaci?n de actividades se incorporar? en el siguiente corte limpio.')

    def _handle_secondary_action(self) -> None:
        QMessageBox.information(self, 'Agenda', 'La vista completa de agenda se incorporar? en el siguiente corte limpio.')

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
            weekdays = ['lunes', 'martes', 'mi?rcoles', 'jueves', 'viernes', 's?bado', 'domingo']
            return f"{weekdays[value.weekday()]}, {value.day:02d} de {months[value.month - 1]} de {value.year}"
        return value.strftime('%d/%m/%Y')

    @staticmethod
    def _format_number_es(value: float, *, suffix: str = '', signed: bool = False) -> str:
        number = float(value or 0.0)
        fmt = f'{{:{"+" if signed else ""},.2f}}'.format(number)
        fmt = fmt.replace(',', '_').replace('.', ',').replace('_', '.')
        return f'{fmt}{suffix}'

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget#dashboardPageRoot { background: #EEF3F8; }
            QFrame#dashboardSidebar { background: #FFFFFF; border-right: 1px solid #DCE4EF; }
            QLabel#dashboardSidebarBrand { background: transparent; padding: 14px; border-radius: 18px; }
            QPushButton#dashboardSidebarButton { background: #2563EB; color: #FFFFFF; border: none; border-radius: 18px; padding: 18px 22px; font-size: 18px; font-weight: 600; }
            QWidget#dashboardContentHost, QWidget#dashboardContent, QWidget#dashboardAgendaView { background: transparent; }
            QFrame#dashboardHeader { background: transparent; }
            QLabel#dashboardTitle { font-size: 34px; font-weight: 700; color: #0F172A; }
            QLabel#dashboardDateLabel { font-size: 16px; color: #334155; }
            QPushButton#dashboardNewActivityButton { background: #2563EB; color: #FFFFFF; border: 1px solid #2563EB; border-radius: 14px; padding: 14px 18px; font-size: 16px; font-weight: 600; }
            QPushButton#dashboardFullAgendaButton, QPushButton#dashboardPanelLinkButton { background: #FFFFFF; color: #1D4ED8; border: 1px solid #CBD5E1; border-radius: 14px; padding: 14px 18px; font-size: 16px; font-weight: 600; }
            QFrame#dashboardKpiCard, QFrame[dashboardPanel='true'] { background: #FFFFFF; border: 1px solid #DCE4EF; border-radius: 18px; }
            QLabel#dashboardKpiTitle, QLabel#dashboardPanelTitle { color: #1E293B; font-size: 16px; font-weight: 700; }
            QLabel#dashboardKpiValue { color: #0F172A; font-size: 34px; font-weight: 800; }
            QLabel#dashboardKpiNote, QLabel#dashboardFooterLabel, QLabel#dashboardEmptyLabel, QLabel#dashboardActivityDetail { color: #64748B; font-size: 14px; }
            QLabel#dashboardActivityCustomer { color: #0F172A; font-size: 15px; font-weight: 700; }
            QLabel#dashboardActivitySummary { color: #1E293B; font-size: 14px; }
            QCalendarWidget#dashboardMonthCalendar { background: #FFFFFF; border: 1px solid #DCE4EF; border-radius: 16px; }
            QFrame#dashboardCalendarSummaryChip { background: #FFFFFF; border: 1px solid #DCE4EF; border-radius: 12px; }
            QLabel#dashboardCalendarSummaryTitle { color: #334155; font-size: 13px; font-weight: 600; }
            QLabel#dashboardCalendarSummaryValue { color: #0F172A; font-size: 18px; font-weight: 800; }
            QTableWidget#dashboardReactivationTable, QTableWidget#dashboardIslandTable { background: #FFFFFF; border: none; gridline-color: #E2E8F0; }
            QHeaderView::section { background: #F8FAFC; color: #334155; padding: 8px; border: none; border-bottom: 1px solid #E2E8F0; font-weight: 700; }
            """
        )
