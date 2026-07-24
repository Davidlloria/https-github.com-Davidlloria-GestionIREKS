from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, QRectF, QSize, Qt
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
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.customer_service = customer_service or CustomerService()
        self.dashboard_service = dashboard_service or CustomerDashboardService()
        self.setObjectName("dashboardPageRoot")
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
        self.content_layout.setContentsMargins(16, 14, 16, 14)
        self.content_layout.setSpacing(14)
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
        self._set_button_icon(self.new_activity_btn, "plus.svg", color="#FFFFFF", size=24)
        self.new_activity_btn.clicked.connect(self._open_new_activity)
        header_layout.addWidget(self.new_activity_btn)

        self.full_agenda_btn = QPushButton("Ver agenda completa")
        self.full_agenda_btn.setObjectName("dashboardFullAgendaButton")
        self.full_agenda_btn.setProperty("btnRole", "secondary")
        self._set_button_icon(self.full_agenda_btn, "calendar.svg", color="#1D4ED8", size=24)
        self.full_agenda_btn.clicked.connect(self._open_full_agenda)
        header_layout.addWidget(self.full_agenda_btn)

        self.content_layout.addWidget(header)

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
        self.content_layout.addLayout(kpi_row)

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
        self.content_layout.addLayout(middle_row)

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
        self.content_layout.addLayout(lower_row)

        self.footer_label = QLabel("")
        self.footer_label.setObjectName("dashboardFooterLabel")
        self.content_layout.addWidget(self.footer_label)

        self._apply_styles()

    def reload(self) -> None:
        snapshot = self.dashboard_service.load_snapshot()
        self.date_label.setText(self.format_header_date(date.today()))
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
        self._populate_upcoming_group(
            self.upcoming_tomorrow_layout,
            snapshot.upcoming_tomorrow,
            empty_text="Sin vencimientos para mañana.",
        )
        self._populate_upcoming_group(
            self.upcoming_next_three_layout,
            snapshot.upcoming_next_three_days,
            empty_text="Sin vencimientos en los próximos 3 días.",
        )
        self._populate_upcoming_group(
            self.upcoming_week_layout,
            snapshot.upcoming_week,
            empty_text="Sin vencimientos en la próxima semana.",
        )
        self._populate_reactivation_table(snapshot.reactivation_rows)
        self._populate_island_table(snapshot)
        self.footer_label.setText(f"Última actualización: {snapshot.generated_at.strftime('%d/%m/%Y %H:%M')} · {snapshot.reactivation_metric_label}")

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
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
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
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        heading = QLabel("Próximos vencimientos")
        heading.setObjectName("dashboardPanelTitle")
        layout.addWidget(heading)

        tomorrow_section, self.upcoming_tomorrow_layout = self._build_upcoming_section("Mañana")
        next_three_section, self.upcoming_next_three_layout = self._build_upcoming_section("Próximos 3 días")
        week_section, self.upcoming_week_layout = self._build_upcoming_section("Semana")
        layout.addWidget(tomorrow_section)
        layout.addWidget(next_three_section)
        layout.addWidget(week_section)
        layout.addStretch(1)
        return panel

    def _build_upcoming_section(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setObjectName("dashboardUpcomingSection")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        heading = QLabel(title)
        heading.setObjectName("dashboardUpcomingSectionTitle")
        layout.addWidget(heading)
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(6)
        layout.addWidget(container)
        return frame, container_layout

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

    def _populate_upcoming_group(self, layout: QVBoxLayout, rows: list[DashboardActivityRow], *, empty_text: str) -> None:
        self._clear_layout(layout)
        if not rows:
            layout.addWidget(self._empty_label(empty_text))
            return
        for row in rows:
            layout.addWidget(self._build_upcoming_row(row))

    def _build_upcoming_row(self, row: DashboardActivityRow) -> QFrame:
        frame = QFrame()
        frame.setObjectName("dashboardUpcomingRow")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)
        date_label = QLabel(self.format_date(row.due_date))
        date_label.setObjectName("dashboardUpcomingDate")
        layout.addWidget(date_label)
        text = QLabel(f"{self.customer_label(row.cliente_codigo, row.cliente_nombre)} · {self.agenda_type_label(row.tipo)}")
        text.setObjectName("dashboardUpcomingText")
        text.setWordWrap(True)
        layout.addWidget(text, 1)
        state = QLabel(self.agenda_state_label(row.estado))
        state.setObjectName("dashboardUpcomingState")
        fg_color, bg_color = self._state_palette(row.estado)
        state.setStyleSheet(
            "QLabel#dashboardUpcomingState {"
            f"background: {bg_color}; color: {fg_color}; padding: 2px 8px; border-radius: 999px;"
            "font-weight: 600;"
            "}"
        )
        layout.addWidget(state)
        return frame

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

        brand_icon = self._icon_path("layout-dashboard.svg").as_posix()
        brand = QLabel(
            (
                "<table cellspacing='0' cellpadding='0'><tr>"
                f"<td width='30'><img src='{brand_icon}' width='22' height='22'/></td>"
                "<td><span>IREKS</span><br/><span>Dashboard</span></td>"
                "</tr></table>"
            )
        )
        brand.setObjectName("dashboardSidebarBrand")
        brand.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(brand)

        agenda_btn = QPushButton("Agenda")
        agenda_btn.setObjectName("dashboardSidebarButton")
        agenda_btn.setProperty("active", True)
        self._set_button_icon(agenda_btn, "calendar-days.svg", color="#FFFFFF", size=28)
        layout.addWidget(agenda_btn)

        for label, icon_name in [("Almacen", "box.svg"), ("Pedidos", "shopping-cart.svg"), ("Ventas", "bar-chart-3.svg")]:
            button = QPushButton(label)
            button.setObjectName("dashboardSidebarButton")
            self._set_button_icon(button, icon_name, color="#475569", size=28)
            button.clicked.connect(lambda _checked=False, name=label: self._show_placeholder_dashboard(name))
            layout.addWidget(button)

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
                background: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 16px;
                padding: 14px;
                font-size: 18px;
                font-weight: 700;
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
            QWidget#dashboardContent {
                background: transparent;
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
                font-size: 18px;
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
            QLabel#dashboardUpcomingDate {
                color: #1D4ED8;
                font-weight: 700;
                min-width: 86px;
            }
            QLabel#dashboardUpcomingText {
                color: #1E293B;
                font-size: 12px;
            }
            QLabel#dashboardUpcomingSectionTitle {
                color: #334155;
                font-size: 13px;
                font-weight: 700;
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
            QTableWidget#dashboardAgendaOverviewTable {
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
