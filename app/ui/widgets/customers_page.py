from pathlib import Path
from datetime import date, datetime
import unicodedata

from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap, QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QCalendarWidget,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QFormLayout,
    QHeaderView,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QRadioButton,
    QMessageBox,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStyle,
    QStyledItemDelegate,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.exc import IntegrityError

from app.models import CodigoPostal, Cliente, Contacto, Isla, Localidad, Municipio, Provincia, Receta
from app.services.customer_report_document_helper import build_customer_report_html
from app.services.customer_report_flow_service import CustomerReportFlowResult, CustomerReportFlowService
from app.services.customer_service import CustomerService
from app.services.customer_report_service import CustomerReportIntentService, CustomerReportResult, CustomerReportService
from app.services.report_export_service import ReportExportService
from app.ui.widgets.entity_dialog import EntityDialog

BASE_DIR = Path(__file__).resolve().parents[3]


class AgendaIconDelegate(QStyledItemDelegate):
    def __init__(self, page: "CustomersPage", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._page = page

    def paint(self, painter: QPainter, option, index) -> None:
        activity_type = str(index.data(Qt.ItemDataRole.UserRole + 1) or "")
        rect = option.rect
        bubble_size = 24
        icon_size = 14
        bubble_x = rect.x() + (rect.width() - bubble_size) // 2
        bubble_y = rect.y() + (rect.height() - bubble_size) // 2

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self._page._agenda_type_color(activity_type)))
        painter.drawEllipse(bubble_x, bubble_y, bubble_size, bubble_size)

        pixmap = QIcon(str(self._page._agenda_type_icon_path(activity_type))).pixmap(icon_size, icon_size)
        tinted = self._page._recolor_pixmap_white(
            pixmap, QColor(self._page._agenda_type_accent_color(activity_type))
        )
        icon_x = rect.x() + (rect.width() - icon_size) // 2
        icon_y = rect.y() + (rect.height() - icon_size) // 2
        painter.drawPixmap(icon_x, icon_y, tinted)
        painter.restore()

    def sizeHint(self, option, index):
        return QSize(50, 32)


class CustomersPage(QWidget):
    UNLINKED_CLIENT_ID = "00000000-0000-0000-0000-000000000000"

    def __init__(self) -> None:
        super().__init__()
        self.customer_service = CustomerService()
        self.report_intent_service = CustomerReportIntentService()
        self.customer_report_service = CustomerReportService()
        self.customer_report_flow_service = CustomerReportFlowService(
            intent_service=self.report_intent_service,
            report_service=self.customer_report_service,
        )
        self.report_export_service = ReportExportService()
        self.schema = [
            {"name": "cliente_nombre_comercial", "label": "Nombre comercial"},
            {"name": "cliente_nombre_fiscal", "label": "Nombre fiscal"},
            {"name": "cliente_nombre_interno", "label": "Nombre interno"},
            {"name": "cliente_abreviatura", "label": "Abreviatura pedido"},
            {"name": "cliente_cif", "label": "CIF"},
            {"name": "cliente_telefono", "label": "Telefono"},
            {"name": "cliente_email", "label": "Email"},
            {"name": "cliente_direccion", "label": "Direccion", "type": "multiline"},
            {"name": "cliente_direccion_cp", "label": "CP"},
            {"name": "cliente_direccion_localidad_id", "label": "Localidad_ID"},
            {"name": "cliente_direccion_municipio_id", "label": "Municipio_ID"},
            {"name": "cliente_direccion_provincia_id", "label": "Provincia_ID"},
            {"name": "cliente_direccion_isla_id", "label": "Isla_ID"},
            {"name": "cliente_tipo", "label": "Tipo", "default": "indirecto"},
            {"name": "cliente_actividad", "label": "Actividad"},
            {"name": "cliente_prospeccion", "label": "Prospección", "type": "bool", "default": False},
            {"name": "distribuidor_id", "label": "Distribuidor_ID"},
            {"name": "activo", "label": "Activo", "type": "bool", "default": True},
        ]
        self.edit_schema = list(self.schema)
        self.import_schema = [
            {"name": "cliente_id", "label": "Cliente_ID"},
            *self.edit_schema,
        ]
        self.rows: list = []
        self.provincias: list[Provincia] = []
        self.islas: list[Isla] = []
        self.municipios: list[Municipio] = []
        self.codigos_postales: list[CodigoPostal] = []
        self.localidades: list[Localidad] = []
        self.provincia_name_by_id: dict[str, str] = {}
        self.isla_name_by_id: dict[str, str] = {}
        self.isla_initials_by_id: dict[str, str] = {}
        self.municipio_name_by_id: dict[str, str] = {}
        self.localidad_name_by_id: dict[str, str] = {}
        self._is_loading_details = False
        self._related_context_menu_open = False
        self._loading_related_contacts = False
        self._loading_agenda = False
        self._agenda_filter_type: QComboBox | None = None
        self._agenda_filter_state: QComboBox | None = None
        self._agenda_filter_from: QDateEdit | None = None
        self._agenda_filter_to: QDateEdit | None = None
        self._agenda_filter_refresh_btn: QPushButton | None = None
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self.reload)
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.timeout.connect(self._autosave_selected_customer)
        self._main_splitter: QSplitter | None = None
        self._detail_splitter: QSplitter | None = None
        self._last_selected_customer_id: str = ""
        self._last_customer_report: CustomerReportResult | None = None
        self._last_customer_report_flow_result: CustomerReportFlowResult = CustomerReportFlowResult(status="idle")

        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        self.setObjectName("CustomersPageRoot")
        self._apply_modern_styles()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header = QLabel("👥  Clientes")
        header.setProperty("role", "pageTitle")
        layout.addWidget(header)
        header.hide()

        ribbon = QFrame()
        ribbon.setObjectName("topRibbon")
        ribbon.setProperty("pageType", "contacts")
        ribbon.setFrameShape(QFrame.Shape.StyledPanel)
        ribbon_layout = QHBoxLayout(ribbon)
        ribbon_layout.setContentsMargins(8, 6, 8, 6)
        ribbon_layout.setSpacing(6)

        self.new_btn = QPushButton("Nuevo")
        self.new_btn.setProperty("btnRole", "success")
        self.new_btn.setFixedHeight(26)
        self.new_btn.setIcon(QIcon(str(BASE_DIR / "assets" / "icons" / "file-text.svg")))
        self.new_btn.setIconSize(QSize(14, 14))
        self.edit_btn = QPushButton("Editar")
        self.edit_btn.setProperty("btnRole", "warning")
        self.edit_btn.setFixedHeight(26)
        self.edit_btn.setIcon(QIcon(str(BASE_DIR / "assets" / "icons" / "file-pen.svg")))
        self.edit_btn.setIconSize(QSize(14, 14))
        self.del_btn = QPushButton("Eliminar")
        self.del_btn.setProperty("btnRole", "danger")
        self.del_btn.setFixedHeight(26)
        self.del_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        self.del_btn.setIconSize(QSize(14, 14))
        self.print_btn = QPushButton("Imprimir")
        self.print_btn.setProperty("btnRole", "secondary")
        self.print_btn.setFixedHeight(26)
        self.print_btn.setIcon(QIcon(str(BASE_DIR / "assets" / "icons" / "printer.svg")))
        self.print_btn.setIconSize(QSize(14, 14))
        self.export_btn = QPushButton("Exportar")
        self.export_btn.setProperty("btnRole", "primary")
        self.export_btn.setFixedHeight(26)
        self.export_btn.setIcon(QIcon(str(BASE_DIR / "assets" / "icons" / "export.svg")))
        self.export_btn.setIconSize(QSize(14, 14))
        self.refresh_btn = QPushButton("Actualizar")
        self.refresh_btn.setProperty("btnRole", "info")
        self.refresh_btn.setFixedHeight(26)
        self.refresh_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.refresh_btn.setIconSize(QSize(14, 14))

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar cliente...")
        self.search_input.setFixedWidth(352)
        self.search_input.setFixedHeight(30)
        self.search_input.textChanged.connect(self._schedule_reload)
        self.search_input.textChanged.connect(self._update_search_clear_button)
        self.clear_search_btn = QPushButton()
        self.clear_search_btn.setObjectName("customerSearchClearButton")
        self.clear_search_btn.setFixedSize(30, 30)
        self.clear_search_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.clear_search_btn.setIcon(QIcon(str(BASE_DIR / "assets" / "icons" / "close-white.svg")))
        self.clear_search_btn.setIconSize(QSize(14, 14))
        self.clear_search_btn.setToolTip("Vaciar filtro")
        self.clear_search_btn.setEnabled(False)
        self.clear_search_btn.clicked.connect(self._clear_search_filter)
        self.help_btn = QPushButton("Ayuda")
        self.help_btn.setProperty("btnRole", "secondary")
        self.help_btn.setFixedHeight(26)
        self.help_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxQuestion))
        self.help_btn.setIconSize(QSize(14, 14))
        self.help_btn.clicked.connect(self._show_customer_help)

        export_menu = QMenu(self)
        export_listados_action = export_menu.addAction("Listados")
        export_import_action = export_menu.addAction("Importar Excel/CSV")
        export_id_action = export_menu.addAction("ID")
        export_listados_action.triggered.connect(self._open_customer_reports_dialog)
        export_import_action.triggered.connect(self._import_entities)
        export_id_action.triggered.connect(self._show_customer_id_dialog)
        self.export_btn.setMenu(export_menu)

        self.new_btn.clicked.connect(self._new_entity)
        self.edit_btn.clicked.connect(self._edit_entity)
        self.del_btn.clicked.connect(self._delete_entity)
        self.print_btn.clicked.connect(self._print_customer_report)
        self.refresh_btn.clicked.connect(self.reload)

        ribbon_layout.addWidget(self.new_btn)
        ribbon_layout.addWidget(self.edit_btn)
        ribbon_layout.addWidget(self.del_btn)
        ribbon_layout.addWidget(self.print_btn)
        ribbon_layout.addWidget(self.export_btn)
        ribbon_layout.addWidget(self.refresh_btn)
        ribbon_layout.addStretch(1)
        ribbon_layout.addWidget(self.help_btn)
        layout.addWidget(ribbon)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("customersMainSplitter")
        self._main_splitter = splitter
        layout.addWidget(splitter, 1)

        left_panel = QWidget()
        left_panel.setObjectName("crmCard")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(14, 14, 14, 14)
        left_layout.setSpacing(10)

        self.island_filter = QComboBox()
        self.island_filter.setFixedWidth(390)
        self.island_filter.currentIndexChanged.connect(self.reload)
        left_layout.addWidget(self.island_filter)

        search_row = QHBoxLayout()
        search_row.setContentsMargins(0, 0, 0, 0)
        search_row.setSpacing(8)
        search_row.addWidget(self.search_input)
        search_row.addWidget(self.clear_search_btn)
        left_layout.addLayout(search_row)

        self.table = QTableWidget(0, 3)
        self.table.setObjectName("customersListTable")
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionsClickable(True)
        header.setMinimumSectionSize(40)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setHorizontalHeaderLabels(["Cod.", "Nombre", "Isla"])
        self.table.setColumnWidth(0, 60)
        self.table.setColumnWidth(1, 268)
        self.table.setColumnWidth(2, 48)
        self.table.setFixedWidth(390)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.table.itemSelectionChanged.connect(self._show_selected_details)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_customers_context_menu)
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.setAlternatingRowColors(True)
        left_layout.addWidget(self.table, 1)
        splitter.addWidget(left_panel)

        right_panel = QWidget()
        right_panel.setObjectName("customersRightPanel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)
        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_splitter.setObjectName("customersDetailSplitter")
        self._detail_splitter = right_splitter
        right_layout.addWidget(right_splitter)
        right_panel_stretch = QWidget()
        right_panel_stretch.setObjectName("customersRightPanelStretch")
        right_panel_stretch.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Expanding,
        )
        self.right_panel_stretch = right_panel_stretch
        right_layout.addWidget(right_panel_stretch, 1)

        detail_panel = QWidget()
        detail_panel.setObjectName("detailTopArea")
        detail_panel.setFixedHeight(300)
        detail_panel.setFixedWidth(932)
        detail_panel.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(10)

        detail_title = QLabel("Detalle de cliente", detail_panel)
        detail_title.setProperty("role", "sectionTitle")
        self.detail_title = detail_title
        self.detail_title.setGeometry(5, 0, 300, 24)
        self.detail_tipo_header = QLabel("Clasificación del cliente", detail_panel)
        self.detail_tipo_header.setProperty("role", "sectionTitle")
        self.detail_tipo_header.setGeometry(0, 0, 300, 24)

        self.detail_panel = detail_panel

        left_card = QFrame(detail_panel)
        left_card.setObjectName("detailLeftCard")
        self.left_card = left_card
        left_card_layout = QVBoxLayout(left_card)
        left_card_layout.setContentsMargins(2, 2, 2, 2)
        left_card_layout.setSpacing(0)
        left_detail_panel = self._build_upper_left_detail_panel()
        left_card_layout.addWidget(left_detail_panel, 1)

        right_card = QFrame(detail_panel)
        right_card.setObjectName("detailRightCard")
        self.right_card = right_card
        right_card_layout = QVBoxLayout(right_card)
        right_card_layout.setContentsMargins(2, 2, 2, 2)
        right_card_layout.setSpacing(0)
        right_detail_panel = self._build_upper_right_detail_panel()
        right_card_layout.addWidget(right_detail_panel, 1)
        self._layout_detail_cards_abs()
        right_splitter.addWidget(detail_panel)

        tabs_panel = QWidget()
        tabs_panel.setObjectName("crmCard")
        tabs_panel.setFixedHeight(300)
        tabs_layout = QVBoxLayout(tabs_panel)
        tabs_layout.setContentsMargins(12, 12, 12, 12)
        tabs_layout.setSpacing(8)

        self.customer_tabs = QTabWidget()
        self.customer_tabs.setObjectName("customerTabs")
        self.customer_tabs.addTab(self._build_contacts_tab(), "Contactos")
        self.customer_tabs.addTab(self._build_tab_placeholder("Historial y resumen de ventas."), "Ventas")
        self.customer_tabs.addTab(self._build_recipes_tab(), "Recetas")
        self.customer_tabs.addTab(self._build_agenda_tab(), "Agenda")
        self.customer_tabs.setTabIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView))
        self.customer_tabs.setTabIcon(1, self.style().standardIcon(QStyle.StandardPixmap.SP_DriveHDIcon))
        self.customer_tabs.setTabIcon(2, self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        self.customer_tabs.setTabIcon(3, self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        tabs_layout.addWidget(self.customer_tabs)
        right_splitter.addWidget(tabs_panel)
        right_splitter.setStretchFactor(0, 1)
        right_splitter.setStretchFactor(1, 9)
        right_splitter.setChildrenCollapsible(False)
        right_splitter.setHandleWidth(0)
        right_splitter.handle(1).setEnabled(False)
        self._apply_fixed_detail_split()

        splitter.addWidget(right_panel)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(0)
        splitter.handle(1).setEnabled(False)
        self._apply_fixed_split_ratio()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._apply_fixed_split_ratio()
        self._apply_fixed_detail_split()
        self._layout_detail_cards_abs()
        self._layout_left_detail_abs()
        self._layout_right_detail_abs()

    def _apply_fixed_split_ratio(self) -> None:
        splitter = self._main_splitter
        if splitter is None:
            return
        total = splitter.size().width()
        if total <= 0:
            return
        left = min(400, max(220, total - 220))
        right = max(1, total - left)
        splitter.setSizes([left, right])

    def _apply_fixed_detail_split(self) -> None:
        splitter = self._detail_splitter
        if splitter is None:
            return
        # Coordenadas fijas efectivas en el splitter vertical:
        # panel superior y=0,h=300 / panel inferior y=300,h=300
        top_px = 300
        bottom_px = 300
        splitter.setSizes([top_px, bottom_px])

    def _layout_detail_cards_abs(self) -> None:
        panel = getattr(self, "detail_panel", None)
        left_card = getattr(self, "left_card", None)
        right_card = getattr(self, "right_card", None)
        if panel is None or left_card is None or right_card is None:
            return
        panel.setFixedWidth(932)
        # Coordenadas fijas dentro del detail_panel.
        left_x = 5
        top_y = 25
        left_width = 620
        gap = 5
        right_width = 290
        right_x = left_x + left_width + gap
        left_card.setGeometry(left_x, top_y, left_width, 270)
        right_card.setGeometry(right_x, top_y, right_width, 270)
        if hasattr(self, "detail_tipo_header"):
            self.detail_tipo_header.setGeometry(right_x, 0, right_width, 24)

    def _build_tab_placeholder(self, text: str) -> QWidget:
        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        label.setWordWrap(True)
        panel_layout.addWidget(label, 1)
        return panel

    def _build_contacts_tab(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("relatedContactsPanel")
        panel.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        panel.customContextMenuRequested.connect(self._show_related_contacts_context_menu)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        self.related_contacts_table = QTableWidget(0, 5)
        self.related_contacts_table.setObjectName("relatedContactsTable")
        self.related_contacts_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.related_contacts_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.related_contacts_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        self.related_contacts_table.verticalHeader().setVisible(False)
        header = self.related_contacts_table.horizontalHeader()
        header.setSectionsClickable(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.related_contacts_table.setHorizontalHeaderLabels(["Avatar", "Nombre", "Cargo", "📞 Teléfono", "✉ Email"])
        self.related_contacts_table.setColumnWidth(0, 70)
        self.related_contacts_table.setColumnWidth(2, 150)
        self.related_contacts_table.setColumnWidth(3, 170)
        self.related_contacts_table.verticalHeader().setDefaultSectionSize(36)
        self.related_contacts_table.cellDoubleClicked.connect(self._open_related_contact)
        self.related_contacts_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.related_contacts_table.customContextMenuRequested.connect(self._show_related_contacts_context_menu)
        self.related_contacts_table.itemChanged.connect(self._on_related_contact_item_changed)
        layout.addWidget(self.related_contacts_table, 1)
        self.related_contacts_empty = QLabel("No hay contactos asociados.\nPulsa clic derecho para a?adir el primero.")
        self.related_contacts_empty.setObjectName("relatedContactsEmpty")
        self.related_contacts_empty.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        self.related_contacts_empty.setWordWrap(True)
        self.related_contacts_empty.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.related_contacts_empty.customContextMenuRequested.connect(self._show_related_contacts_context_menu)
        self.related_contacts_empty.setVisible(False)
        layout.addWidget(self.related_contacts_empty)
        return panel

    def _build_recipes_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        self.related_recipes_table = QTableWidget(0, 3)
        self.related_recipes_table.setObjectName("relatedRecipesTable")
        self.related_recipes_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.related_recipes_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.related_recipes_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.related_recipes_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.related_recipes_table.verticalHeader().setVisible(False)
        header = self.related_recipes_table.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.related_recipes_table.setHorizontalHeaderLabels(["Nº", "Receta", "Versión"])
        self.related_recipes_table.setColumnWidth(0, 70)
        self.related_recipes_table.setColumnWidth(2, 90)
        self.related_recipes_table.verticalHeader().setDefaultSectionSize(36)
        self.related_recipes_table.cellDoubleClicked.connect(self._open_related_recipe)
        layout.addWidget(self.related_recipes_table, 1)

        self.related_recipes_empty = QLabel("No hay recetas asociadas a este cliente.")
        self.related_recipes_empty.setObjectName("relatedRecipesEmpty")
        self.related_recipes_empty.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        self.related_recipes_empty.setWordWrap(True)
        self.related_recipes_empty.setVisible(False)
        layout.addWidget(self.related_recipes_empty)
        return panel

    def _build_agenda_tab(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("customerAgendaPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        title = QLabel("Historial de actividades")
        title.setObjectName("customerAgendaTitle")
        layout.addWidget(title)

        filter_bar = QHBoxLayout()
        filter_bar.setContentsMargins(0, 0, 0, 0)
        filter_bar.setSpacing(10)

        self._agenda_filter_type = QComboBox()
        self._agenda_filter_type.setObjectName("customerAgendaFilter")
        self._agenda_filter_type.setFixedWidth(156)
        self._agenda_filter_type.setFixedHeight(28)
        self._agenda_filter_type.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._agenda_filter_type.addItem("Todos los tipos", "")
        for key, label in self._agenda_type_options():
            self._agenda_filter_type.addItem(label, key)

        self._agenda_filter_state = QComboBox()
        self._agenda_filter_state.setObjectName("customerAgendaFilter")
        self._agenda_filter_state.setFixedWidth(156)
        self._agenda_filter_state.setFixedHeight(28)
        self._agenda_filter_state.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._agenda_filter_state.addItem("Todos los estados", "")
        for key, label in self._agenda_state_options():
            self._agenda_filter_state.addItem(label, key)

        current_year = date.today().year
        self._agenda_filter_from = QDateEdit()
        self._agenda_filter_from.setObjectName("customerAgendaFilterDate")
        self._agenda_filter_from.setCalendarPopup(True)
        self._agenda_filter_from.setDisplayFormat("dd/MM/yyyy")
        self._agenda_filter_from.setFixedWidth(144)
        self._agenda_filter_from.setFixedHeight(28)
        self._agenda_filter_from.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._agenda_filter_from.setDate(self._agenda_qdate(date(current_year, 1, 1), fallback_today=False))

        self._agenda_filter_to = QDateEdit()
        self._agenda_filter_to.setObjectName("customerAgendaFilterDate")
        self._agenda_filter_to.setCalendarPopup(True)
        self._agenda_filter_to.setDisplayFormat("dd/MM/yyyy")
        self._agenda_filter_to.setFixedWidth(144)
        self._agenda_filter_to.setFixedHeight(28)
        self._agenda_filter_to.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._agenda_filter_to.setDate(self._agenda_qdate(date(current_year, 12, 31), fallback_today=False))
        for calendar_edit in (self._agenda_filter_from, self._agenda_filter_to):
            calendar_widget = calendar_edit.calendarWidget()
            if calendar_widget is not None:
                calendar_widget.setMinimumSize(340, 272)
                calendar_widget.setGridVisible(False)
                calendar_widget.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
                calendar_widget.setObjectName("customerAgendaPopupCalendar")

        range_sep = QLabel(" - ")
        range_sep.setObjectName("customerAgendaRangeSep")

        self._agenda_filter_refresh_btn = QPushButton("Actualizar")
        self._agenda_filter_refresh_btn.setObjectName("customerAgendaRefreshButton")
        self._agenda_filter_refresh_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self._agenda_filter_refresh_btn.setFixedWidth(112)
        self._agenda_filter_refresh_btn.setFixedHeight(28)
        self._agenda_filter_refresh_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._agenda_filter_refresh_btn.setIconSize(QSize(14, 14))

        filter_bar.addWidget(self._agenda_filter_type)
        filter_bar.addWidget(self._agenda_filter_state)
        filter_bar.addWidget(self._agenda_filter_from)
        filter_bar.addWidget(range_sep)
        filter_bar.addWidget(self._agenda_filter_to)
        filter_bar.addWidget(self._agenda_filter_refresh_btn)
        filter_bar.addStretch(1)
        layout.addLayout(filter_bar)

        self.agenda_table = QTableWidget(0, 6)
        self.agenda_table.setObjectName("customerAgendaTable")
        self.agenda_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.agenda_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.agenda_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.agenda_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.agenda_table.verticalHeader().setVisible(False)
        self.agenda_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.agenda_table.setAlternatingRowColors(True)
        self.agenda_table.setShowGrid(False)
        self.agenda_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.agenda_table.setHorizontalHeaderLabels(["", "Fecha", "Tipo", "Estado", "Resumen", "Seguimiento"])
        header = self.agenda_table.horizontalHeader()
        header.setSectionsClickable(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.agenda_table.setColumnWidth(0, 50)
        self.agenda_table.setColumnWidth(1, 112)
        self.agenda_table.setColumnWidth(2, 132)
        self.agenda_table.setColumnWidth(3, 104)
        self.agenda_table.setColumnWidth(5, 106)
        self.agenda_table.verticalHeader().setDefaultSectionSize(32)
        self.agenda_table.setItemDelegateForColumn(0, AgendaIconDelegate(self, self.agenda_table))
        self.agenda_table.cellDoubleClicked.connect(self._open_agenda_activity_from_row)
        self.agenda_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.agenda_table.customContextMenuRequested.connect(self._show_agenda_context_menu)
        layout.addWidget(self.agenda_table, 1)

        self.agenda_empty = QLabel("No hay actividades registradas para este cliente.")
        self.agenda_empty.setObjectName("customerAgendaEmpty")
        self.agenda_empty.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        self.agenda_empty.setWordWrap(True)
        self.agenda_empty.setVisible(False)
        layout.addWidget(self.agenda_empty)

        if self._agenda_filter_type is not None:
            self._agenda_filter_type.currentIndexChanged.connect(self._refresh_agenda_view)
        if self._agenda_filter_state is not None:
            self._agenda_filter_state.currentIndexChanged.connect(self._refresh_agenda_view)
        if self._agenda_filter_from is not None:
            self._agenda_filter_from.dateChanged.connect(self._refresh_agenda_view)
        if self._agenda_filter_to is not None:
            self._agenda_filter_to.dateChanged.connect(self._refresh_agenda_view)
        if self._agenda_filter_refresh_btn is not None:
            self._agenda_filter_refresh_btn.clicked.connect(self._refresh_agenda_view)
        return panel

    def _render_customer_agenda(self, cliente_id: str) -> None:
        if not hasattr(self, "agenda_table"):
            return
        entries = self.customer_service.related_agenda(cliente_id)
        filtered_entries = [item for item in entries if self._agenda_matches_filters(item)]
        self._loading_agenda = True
        self.agenda_table.blockSignals(True)
        try:
            self.agenda_table.setRowCount(len(filtered_entries))
            for row_idx, item in enumerate(filtered_entries):
                agenda_id = str(getattr(item, "agenda_id", "") or "")
                fecha = self._format_agenda_date(getattr(item, "fecha_actividad", None))
                tipo = self._agenda_type_label(str(getattr(item, "tipo", "") or ""))
                estado = self._agenda_state_label(str(getattr(item, "estado", "") or ""))
                resumen = str(getattr(item, "resumen", "") or "").strip()
                seguimiento = self._format_agenda_date(getattr(item, "fecha_seguimiento", None), allow_blank=True)

                icon_item = QTableWidgetItem("")
                fecha_item = QTableWidgetItem(fecha)
                tipo_item = QTableWidgetItem(tipo)
                resumen_item = QTableWidgetItem(resumen)
                seguimiento_item = QTableWidgetItem(seguimiento)
                state_cell = self._make_agenda_state_pill_widget(str(getattr(item, "estado", "") or ""))
                icon_item.setData(Qt.ItemDataRole.UserRole, agenda_id)
                icon_item.setData(Qt.ItemDataRole.UserRole + 1, str(getattr(item, "tipo", "") or ""))
                fecha_item.setData(Qt.ItemDataRole.UserRole, agenda_id)
                tipo_item.setData(Qt.ItemDataRole.UserRole, agenda_id)
                resumen_item.setData(Qt.ItemDataRole.UserRole, agenda_id)
                seguimiento_item.setData(Qt.ItemDataRole.UserRole, agenda_id)
                for item_widget in (icon_item, fecha_item, tipo_item, resumen_item, seguimiento_item):
                    item_widget.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    item_widget.setToolTip(item_widget.text())
                    item_widget.setForeground(QColor("#14213D"))
                icon_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                fecha_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter)
                tipo_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter)
                resumen_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                seguimiento_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter)
                self.agenda_table.setItem(row_idx, 0, icon_item)
                self.agenda_table.setItem(row_idx, 1, fecha_item)
                self.agenda_table.setItem(row_idx, 2, tipo_item)
                self.agenda_table.setCellWidget(row_idx, 3, state_cell)
                self.agenda_table.setItem(row_idx, 4, resumen_item)
                self.agenda_table.setItem(row_idx, 5, seguimiento_item)
                self.agenda_table.setRowHeight(row_idx, self.agenda_table.verticalHeader().defaultSectionSize())
        finally:
            self.agenda_table.blockSignals(False)
            self._loading_agenda = False
        if hasattr(self, "agenda_empty"):
            self.agenda_empty.setVisible(len(filtered_entries) == 0)

    def _refresh_agenda_view(self, *_args) -> None:
        selected = self._selected_row()
        if selected is None:
            if hasattr(self, "agenda_table"):
                self.agenda_table.setRowCount(0)
            if hasattr(self, "agenda_empty"):
                self.agenda_empty.setVisible(True)
            return
        self._render_customer_agenda(str(getattr(selected, "cliente_id", "") or ""))

    def _agenda_matches_filters(self, item) -> bool:
        tipo_filter = ""
        estado_filter = ""
        date_from = None
        date_to = None
        if self._agenda_filter_type is not None:
            tipo_filter = str(self._agenda_filter_type.currentData() or "").strip().lower()
        if self._agenda_filter_state is not None:
            estado_filter = str(self._agenda_filter_state.currentData() or "").strip().lower()
        if self._agenda_filter_from is not None:
            date_from = self._agenda_filter_from.date().toPython()
        if self._agenda_filter_to is not None:
            date_to = self._agenda_filter_to.date().toPython()

        tipo = str(getattr(item, "tipo", "") or "").strip().lower()
        estado = str(getattr(item, "estado", "") or "").strip().lower()
        actividad_fecha = self._agenda_entry_date(getattr(item, "fecha_actividad", None))

        if tipo_filter and tipo != tipo_filter:
            return False
        if estado_filter and estado != estado_filter:
            return False
        if actividad_fecha is None:
            return True
        if date_from is not None and actividad_fecha < date_from:
            return False
        if date_to is not None and actividad_fecha > date_to:
            return False
        return True

    @staticmethod
    def _agenda_entry_date(value: object) -> date | None:
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        text = str(value or "").strip()
        if not text:
            return None
        try:
            return date.fromisoformat(text)
        except ValueError:
            try:
                return datetime.fromisoformat(text).date()
            except ValueError:
                return None

    def _agenda_type_icon_path(self, value: str) -> Path:
        normalized = str(value or "").strip().lower()
        icon_map = {
            "visita_realizada": "user-check.svg",
            "visita_prevista": "calendar-check.svg",
            "llamada": "phone-call.svg",
            "seguimiento": "history.svg",
            "desarrollo_futuro": "lightbulb.svg",
            "incidencia": "triangle-alert.svg",
            "nota": "file-pen.svg",
        }
        icon_name = icon_map.get(normalized, "history.svg")
        return BASE_DIR / "assets" / "icons" / icon_name

    def _agenda_type_color(self, value: str) -> str:
        normalized = str(value or "").strip().lower()
        palette = {
            "visita_realizada": "#DCEBFF",
            "visita_prevista": "#EDE3FF",
            "llamada": "#DCF7EA",
            "seguimiento": "#DDF6F1",
            "desarrollo_futuro": "#FEF1D8",
            "incidencia": "#FDE3E2",
            "nota": "#EEF2F7",
        }
        return palette.get(normalized, "#EEF2F7")

    def _agenda_type_accent_color(self, value: str) -> str:
        normalized = str(value or "").strip().lower()
        palette = {
            "visita_realizada": "#2563EB",
            "visita_prevista": "#7C3AED",
            "llamada": "#059669",
            "seguimiento": "#0F766E",
            "desarrollo_futuro": "#D97706",
            "incidencia": "#DC2626",
            "nota": "#475467",
        }
        return palette.get(normalized, "#475467")

    def _agenda_state_palette(self, value: str) -> tuple[str, str]:
        normalized = str(value or "").strip().lower()
        palette = {
            "pendiente": ("#A15C00", "#FFF0C2"),
            "hecho": ("#0B7A4D", "#ECF9F0"),
            "aplazado": ("#1D63C9", "#ECF3FF"),
            "cancelado": ("#A63A2A", "#FEF0EE"),
        }
        return palette.get(normalized, ("#475467", "#EEF2F6"))

    def _recolor_pixmap_white(self, pixmap: QPixmap, color: QColor | str = "#FFFFFF") -> QPixmap:
        if pixmap.isNull():
            return pixmap
        out = QPixmap(pixmap.size())
        out.fill(Qt.GlobalColor.transparent)
        painter = QPainter(out)
        painter.drawPixmap(0, 0, pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(out.rect(), QColor(color))
        painter.end()
        return out

    def _make_agenda_icon_widget(self, activity_type: str) -> QWidget:
        wrapper = QWidget()
        wrapper.setAutoFillBackground(False)
        wrapper.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        wrapper.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        wrapper_layout = QHBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        bubble = QLabel()
        bubble.setObjectName("customerAgendaIconBubble")
        bubble.setFixedSize(24, 24)
        bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bubble.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        bubble.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        bubble.setStyleSheet(
            f"QLabel#customerAgendaIconBubble {{ background: {self._agenda_type_color(activity_type)}; "
            "border-radius: 12px; border: none; }}"
        )
        pixmap = QIcon(str(self._agenda_type_icon_path(activity_type))).pixmap(14, 14)
        bubble.setPixmap(self._recolor_pixmap_white(pixmap, QColor(self._agenda_type_accent_color(activity_type))))
        wrapper_layout.addWidget(bubble, 0, Qt.AlignmentFlag.AlignCenter)
        return wrapper

    def _make_agenda_state_pill_widget(self, state: str) -> QWidget:
        fg_color, bg_color = self._agenda_state_palette(state)
        wrapper = QFrame()
        wrapper.setObjectName("customerAgendaStatePill")
        wrapper.setAutoFillBackground(False)
        wrapper.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        wrapper.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        wrapper.setStyleSheet(
            f"QFrame#customerAgendaStatePill {{ background: transparent; border: none; }}"
        )
        wrapper_layout = QHBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label = QLabel(self._agenda_state_label(state))
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFixedSize(82, 18)
        label.setStyleSheet(
            f"background: {bg_color}; color: {fg_color}; border: 1px solid rgba(0,0,0,0.03); "
            "border-radius: 9px; font-size: 9px; font-weight: 700; padding: 0 6px;"
        )
        wrapper_layout.addWidget(label)
        return wrapper

    def _show_agenda_context_menu(self, pos) -> None:
        customer = self._selected_row()
        if customer is None:
            return
        index = self.agenda_table.indexAt(pos)
        agenda_id = ""
        row_idx = index.row() if index.isValid() else None
        global_pos = self.agenda_table.viewport().mapToGlobal(pos)
        if row_idx is not None:
            self.agenda_table.selectRow(row_idx)
            agenda_id = self._get_agenda_activity_id(row_idx)

        menu = QMenu(self)
        action_new = menu.addAction("Nueva actividad")
        action_edit = menu.addAction("Editar")
        action_delete = menu.addAction("Eliminar")
        if not agenda_id:
            action_edit.setEnabled(False)
            action_delete.setEnabled(False)
        chosen = menu.exec(global_pos)
        if chosen == action_new:
            self._open_agenda_activity_dialog()
            return
        if chosen == action_edit:
            self._open_agenda_activity_dialog(agenda_id)
            return
        if chosen == action_delete:
            self._delete_agenda_activity(agenda_id)

    def _open_agenda_activity_from_row(self, row_idx: int, _column: int) -> None:
        agenda_id = self._get_agenda_activity_id(row_idx)
        if not agenda_id:
            return
        self._open_agenda_activity_dialog(agenda_id)

    def _open_agenda_activity_dialog(self, agenda_id: str = "") -> None:
        selected_customer = self._selected_row()
        if selected_customer is None:
            QMessageBox.warning(self, "Agenda", "Selecciona un cliente.")
            return
        customer_id = str(getattr(selected_customer, "cliente_id", "") or "").strip()
        activity = self.customer_service.get_agenda_activity(agenda_id) if agenda_id else None
        if activity is not None and str(getattr(activity, "cliente_id", "") or "").strip() != customer_id:
            activity = None
        editing = activity is not None

        dialog = QDialog(self)
        dialog.setWindowTitle("Editar actividad" if editing else "Nueva actividad")
        dialog.setModal(True)
        dialog.setFixedSize(620, 520)

        form_layout = QVBoxLayout(dialog)
        form_layout.setContentsMargins(16, 16, 16, 16)
        form_layout.setSpacing(10)

        title = QLabel("Editar actividad" if editing else "Nueva actividad")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #14213D;")
        form_layout.addWidget(title)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setVerticalSpacing(10)
        form.setHorizontalSpacing(12)

        tipo_combo = QComboBox()
        for key, label in self._agenda_type_options():
            tipo_combo.addItem(label, key)

        estado_combo = QComboBox()
        for key, label in self._agenda_state_options():
            estado_combo.addItem(label, key)

        fecha_edit = QDateEdit()
        fecha_edit.setCalendarPopup(True)
        fecha_edit.setDisplayFormat("dd/MM/yyyy")
        fecha_edit.setDate(self._agenda_qdate(getattr(activity, "fecha_actividad", None)))

        resumen_edit = QLineEdit()
        resumen_edit.setPlaceholderText("Resumen de la actividad")

        detalle_edit = QPlainTextEdit()
        detalle_edit.setPlaceholderText("Detalle, acuerdos, próximos pasos...")
        detalle_edit.setFixedHeight(110)

        seguimiento_check = QCheckBox("Tiene seguimiento")
        seguimiento_edit = QDateEdit()
        seguimiento_edit.setCalendarPopup(True)
        seguimiento_edit.setDisplayFormat("dd/MM/yyyy")
        seguimiento_edit.setDate(self._agenda_qdate(getattr(activity, "fecha_seguimiento", None), fallback_today=True))
        seguimiento_edit.setEnabled(False)
        seguimiento_check.toggled.connect(seguimiento_edit.setEnabled)

        if activity is not None:
            tipo_combo.setCurrentIndex(max(0, tipo_combo.findData(str(getattr(activity, "tipo", "") or "nota"))))
            estado_combo.setCurrentIndex(max(0, estado_combo.findData(str(getattr(activity, "estado", "") or "pendiente"))))
            resumen_edit.setText(str(getattr(activity, "resumen", "") or ""))
            detalle_edit.setPlainText(str(getattr(activity, "detalle", "") or ""))
            if getattr(activity, "fecha_seguimiento", None):
                seguimiento_check.setChecked(True)
                seguimiento_edit.setEnabled(True)
                seguimiento_edit.setDate(self._agenda_qdate(getattr(activity, "fecha_seguimiento", None)))
        else:
            tipo_combo.setCurrentIndex(max(0, tipo_combo.findData("nota")))
            estado_combo.setCurrentIndex(max(0, estado_combo.findData("pendiente")))
            seguimiento_check.setChecked(False)

        form.addRow("Tipo", tipo_combo)
        form.addRow("Fecha", fecha_edit)
        form.addRow("Estado", estado_combo)
        form.addRow("Resumen", resumen_edit)
        form.addRow("Detalle", detalle_edit)
        form.addRow("Seguimiento", seguimiento_check)
        form.addRow("Fecha seguimiento", seguimiento_edit)
        form_layout.addLayout(form)

        buttons = QDialogButtonBox()
        save_btn = buttons.addButton("Guardar", QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_btn = buttons.addButton("Cancelar", QDialogButtonBox.ButtonRole.RejectRole)
        delete_btn = None
        delete_requested = {"value": False}
        if editing:
            delete_btn = buttons.addButton("Eliminar", QDialogButtonBox.ButtonRole.DestructiveRole)
        save_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        if delete_btn is not None:
            delete_btn.clicked.connect(lambda: delete_requested.__setitem__("value", True))
            delete_btn.clicked.connect(dialog.reject)
        form_layout.addWidget(buttons)

        result = dialog.exec()
        if result != QDialog.DialogCode.Accepted:
            if delete_requested["value"] and delete_btn is not None:
                self._delete_agenda_activity(str(getattr(activity, "agenda_id", "") or ""))
            return

        payload = {
            "cliente_id": customer_id,
            "fecha_actividad": fecha_edit.date().toString("yyyy-MM-dd"),
            "tipo": str(tipo_combo.currentData() or "nota"),
            "estado": str(estado_combo.currentData() or "pendiente"),
            "resumen": resumen_edit.text().strip(),
            "detalle": detalle_edit.toPlainText().strip(),
            "fecha_seguimiento": seguimiento_edit.date().toString("yyyy-MM-dd") if seguimiento_check.isChecked() else "",
            "prioridad": "normal",
            "responsable": "",
        }
        if not payload["resumen"] and not payload["detalle"]:
            QMessageBox.warning(self, "Agenda", "El resumen o el detalle no pueden quedar vacíos.")
            return
        try:
            self.customer_service.upsert_agenda_activity(str(getattr(activity, "agenda_id", "") or ""), payload)
        except Exception as exc:
            QMessageBox.warning(self, "Agenda", f"No se pudo guardar la actividad: {exc}")
            return
        self._render_customer_agenda(customer_id)

    def _delete_agenda_activity(self, agenda_id: str) -> None:
        clean_id = str(agenda_id or "").strip()
        if not clean_id:
            return
        answer = QMessageBox.question(
            self,
            "Confirmar eliminación",
            "La actividad se eliminará de la agenda.\n\n¿Continuar?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            deleted = self.customer_service.delete_agenda_activity(clean_id)
        except Exception as exc:
            QMessageBox.warning(self, "Agenda", f"No se pudo eliminar la actividad: {exc}")
            return
        if deleted:
            selected = self._selected_row()
            self._render_customer_agenda(str(getattr(selected, "cliente_id", "") or "") if selected else "")

    def _get_agenda_activity_id(self, row_idx: int | None = None) -> str:
        if row_idx is None:
            selected = self.agenda_table.selectionModel().selectedRows()
            if not selected:
                return ""
            row_idx = selected[0].row()
        id_item = self.agenda_table.item(row_idx, 1)
        if id_item is None:
            return ""
        return str(id_item.data(Qt.ItemDataRole.UserRole) or "").strip()

    def _agenda_qdate(self, value: object, *, fallback_today: bool = True):
        from PySide6.QtCore import QDate

        if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
            return QDate(int(value.year), int(value.month), int(value.day))
        if fallback_today:
            return QDate.currentDate()
        return QDate()

    def _format_agenda_date(self, value: object, *, allow_blank: bool = False) -> str:
        text = str(value or "").strip()
        if not text:
            return "" if allow_blank else "-"
        try:
            parsed = datetime.fromisoformat(text)
            return parsed.strftime("%d/%m/%Y")
        except ValueError:
            try:
                parsed_date = date.fromisoformat(text)
                return parsed_date.strftime("%d/%m/%Y")
            except ValueError:
                return text

    def _agenda_type_options(self) -> list[tuple[str, str]]:
        return [
            ("visita_realizada", "Visita realizada"),
            ("visita_prevista", "Visita prevista"),
            ("llamada", "Llamada"),
            ("seguimiento", "Seguimiento"),
            ("desarrollo_futuro", "Desarrollo futuro"),
            ("incidencia", "Incidencia"),
            ("nota", "Nota"),
        ]

    def _agenda_state_options(self) -> list[tuple[str, str]]:
        return [
            ("pendiente", "Pendiente"),
            ("hecho", "Completada"),
            ("aplazado", "Aplazado"),
            ("cancelado", "Cancelado"),
        ]

    def _agenda_type_label(self, value: str) -> str:
        options = dict(self._agenda_type_options())
        return options.get(str(value or "").strip(), str(value or "").replace("_", " ").title())

    def _agenda_state_label(self, value: str) -> str:
        options = dict(self._agenda_state_options())
        return options.get(str(value or "").strip(), str(value or "").replace("_", " ").title())

    def _agenda_style_state_item(self, item: QTableWidgetItem, state: str) -> None:
        normalized = str(state or "").strip().lower()
        if normalized == "hecho":
            item.setForeground(QColor("#067647"))
        elif normalized == "aplazado":
            item.setForeground(QColor("#B54708"))
        elif normalized == "cancelado":
            item.setForeground(QColor("#B42318"))
        else:
            item.setForeground(QColor("#475467"))

    def _build_reports_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.report_prompt = QPlainTextEdit()
        self.report_prompt.setObjectName("customerReportPrompt")
        self.report_prompt.setFixedHeight(58)
        self.report_prompt.setPlaceholderText(
            "Ej.: clientes indirectos activos de Tenerife con contactos y telefono"
        )
        layout.addWidget(self.report_prompt)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)
        self.report_generate_btn = QPushButton("Generar")
        self.report_generate_btn.setProperty("btnRole", "primary")
        self.report_excel_btn = QPushButton("Excel")
        self.report_excel_btn.setProperty("btnRole", "success")
        self.report_pdf_btn = QPushButton("PDF")
        self.report_pdf_btn.setProperty("btnRole", "secondary")
        self.report_print_btn = QPushButton("Imprimir")
        self.report_print_btn.setProperty("btnRole", "secondary")
        self.report_generate_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.report_excel_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self.report_pdf_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        self.report_print_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        self.report_generate_btn.clicked.connect(self._generate_customer_report)
        self.report_excel_btn.clicked.connect(self._export_customer_report_excel)
        self.report_pdf_btn.clicked.connect(self._export_customer_report_pdf)
        self.report_print_btn.clicked.connect(self._print_customer_report)
        actions.addWidget(self.report_generate_btn)
        actions.addWidget(self.report_excel_btn)
        actions.addWidget(self.report_pdf_btn)
        actions.addWidget(self.report_print_btn)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.report_status_label = QLabel("Sin listado generado.")
        self.report_status_label.setObjectName("customerReportStatus")
        layout.addWidget(self.report_status_label)

        self.report_table = QTableWidget(0, 0)
        self.report_table.setObjectName("customerReportTable")
        self.report_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.report_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.report_table.setAlternatingRowColors(True)
        self.report_table.verticalHeader().setVisible(False)
        self.report_table.horizontalHeader().setVisible(True)
        self.report_table.horizontalHeader().setSectionsClickable(True)
        self.report_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.report_table, 1)
        self._set_report_actions_enabled(False)
        return panel

    def _open_customer_reports_dialog(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Listados de clientes")
        dialog.setModal(False)
        dialog.resize(980, 620)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._build_reports_panel())
        dialog.show()
        self._reports_dialog = dialog

    def _build_upper_left_detail_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("detailSubPanel")
        self.left_detail_panel = panel
        self.lbl_cod = QLabel("Cod.", panel)
        self.detail_codigo = QLineEdit(panel)
        self.detail_codigo.setReadOnly(True)
        self.lbl_nombre_comercial = QLabel("Nombre Comercial", panel)
        self.detail_nombre_comercial = QLineEdit(panel)
        self.detail_nombre_comercial.setFixedHeight(28)
        self.lbl_telefono = QLabel("Telef.", panel)
        self.detail_telefono = QLineEdit(panel)
        self.lbl_cif = QLabel("C.I.F.", panel)
        self.detail_cif = QLineEdit(panel)
        self.detail_cif.setReadOnly(True)
        self.lbl_nombre_fiscal = QLabel("Nombre Fiscal", panel)
        self.detail_nombre_fiscal = QLineEdit(panel)
        self.lbl_provincia = QLabel("Provincia", panel)
        self.detail_provincia = QComboBox(panel)
        self.lbl_isla = QLabel("Isla", panel)
        self.detail_isla = QComboBox(panel)
        self.lbl_municipio = QLabel("Municipio", panel)
        self.detail_municipio = QComboBox(panel)
        self.lbl_calle = QLabel("Calle", panel)
        self.detail_direccion = QLineEdit(panel)
        self.lbl_cp = QLabel("C.P.", panel)
        self.detail_cp = QComboBox(panel)
        self.lbl_localidad = QLabel("Localidad", panel)
        self.detail_localidad = QComboBox(panel)
        self._layout_left_detail_abs()

        self.detail_provincia.currentIndexChanged.connect(self._on_provincia_changed)
        self.detail_isla.currentIndexChanged.connect(self._on_isla_changed)
        self.detail_municipio.currentIndexChanged.connect(self._on_municipio_changed)
        self.detail_cp.currentIndexChanged.connect(self._on_cp_changed)
        self.detail_localidad.currentIndexChanged.connect(self._schedule_autosave)
        self.detail_telefono.editingFinished.connect(self._format_customer_phone_field)

        return panel

    def _layout_left_detail_abs(self) -> None:
        panel = getattr(self, "left_detail_panel", None)
        if panel is None:
            return
        y = 6
        label_h = 20
        field_h = 34
        row_gap = 14
        col_gap = 10
        w = max(10, panel.width() - 8)
        col1 = 120
        col2 = max(180, w - col1 - col_gap)

        self.lbl_cod.setGeometry(5, 2, 80, 20)
        self.lbl_nombre_comercial.setGeometry(95, 2, 430, 20)
        y += label_h + 4
        self.detail_codigo.setGeometry(5, 26, 80, 28)
        self.detail_nombre_comercial.setGeometry(95, 26, 430, 28)

        y += field_h + row_gap
        c1 = (w - 2 * col_gap) // 3
        c2 = c1
        c3 = w - c1 - c2 - 2 * col_gap
        self.lbl_telefono.setGeometry(5, 64, 120, 20)
        self.lbl_cif.setGeometry(135, 64, 100, 20)
        self.lbl_nombre_fiscal.setGeometry(245, 64, 280, 20)
        y += label_h + 4
        self.detail_telefono.setGeometry(5, 86, 120, 28)
        self.detail_cif.setGeometry(135, 86, 100, 28)
        self.detail_nombre_fiscal.setGeometry(245, 86, 280, 28)

        y += field_h + row_gap
        self.lbl_provincia.setGeometry(5, 126, 165, 20)
        self.lbl_isla.setGeometry(175, 126, 100, 20)
        self.lbl_municipio.setGeometry(285, 126, 235, 20)
        y += label_h + 4
        self.detail_provincia.setGeometry(5, 150, 165, 28)
        self.detail_isla.setGeometry(175, 150, 100, 28)
        self.detail_municipio.setGeometry(285, 150, 235, 28)

        y += field_h + row_gap
        c1b = int(w * 0.52)
        c2b = int(w * 0.22)
        c3b = w - c1b - c2b - 2 * col_gap
        self.lbl_calle.setGeometry(5, 190, 270, 20)
        self.lbl_cp.setGeometry(285, 190, 80, 20)
        self.lbl_localidad.setGeometry(375, 190, 150, 20)
        y += label_h + 4
        self.detail_direccion.setGeometry(5, 214, 270, 28)
        self.detail_cp.setGeometry(285, 214, 80, 28)
        self.detail_localidad.setGeometry(375, 214, 150, 28)

    def _build_upper_right_detail_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("detailSubPanel")
        self.right_detail_panel = panel

        self.sectors_box = QFrame(panel)
        sectors_box = self.sectors_box
        sectors_box.setObjectName("plainGroup")
        sectors_box.setFrameShape(QFrame.Shape.Box)
        sectors_box.setFixedHeight(128)
        self.tipo_checks: dict[str, QCheckBox] = {}
        labels = [
            ("PANADERIA", "🥖"),
            ("PASTELERIA", "🧁"),
            ("HELADERIA", "🍦"),
            ("CAFETERIA", "☕"),
            ("RESTAURANTE", "🍽"),
            ("HOTEL", "🏨"),
        ]
        pill_name_by_label = {
            "PANADERIA": "sectorChipPillPanaderia",
            "PASTELERIA": "sectorChipPillPasteleria",
            "HELADERIA": "sectorChipPillHeladeria",
            "CAFETERIA": "sectorChipPillCafeteria",
            "RESTAURANTE": "sectorChipPillRestaurante",
            "HOTEL": "sectorChipPillHotel",
        }
        for idx, (label, icon) in enumerate(labels):
            checkbox = QCheckBox(f"{icon} {label}", sectors_box)
            checkbox.setObjectName(pill_name_by_label[label])
            checkbox.setMinimumHeight(28)
            self.tipo_checks[label] = checkbox

        self.section_info = QLabel("Tipo", panel)
        self.section_info.setProperty("role", "blockTitle")

        self.detail_tipo = QComboBox(panel)
        self.detail_tipo.addItems(["", "directo", "indirecto", "distribuidor"])

        self.lbl_abrev = QLabel("Abrev. pedido", panel)
        self.detail_abreviatura = QLineEdit(panel)
        self.detail_abreviatura.setMaxLength(20)

        self.status_box = QFrame(panel)
        status_box = self.status_box
        status_box.setObjectName("plainGroup")
        status_box.setFrameShape(QFrame.Shape.Box)
        self.status_group = QButtonGroup(self)
        self.detail_activo = QPushButton("ACTIVO", status_box)
        self.detail_inactivo = QPushButton("INACTIVO", status_box)
        self.detail_activo.setCheckable(True)
        self.detail_inactivo.setCheckable(True)
        self.detail_activo.setObjectName("stateChipActive")
        self.detail_inactivo.setObjectName("stateChipInactive")
        self.status_group.addButton(self.detail_activo)
        self.status_group.addButton(self.detail_inactivo)
        self.lbl_prospeccion = QLabel("Prospección", status_box)
        self.prospeccion_group = QButtonGroup(self)
        self.detail_prospeccion_si = QRadioButton("Sí", status_box)
        self.detail_prospeccion_no = QRadioButton("No", status_box)
        self.detail_prospeccion_no.setChecked(True)
        self.prospeccion_group.addButton(self.detail_prospeccion_si)
        self.prospeccion_group.addButton(self.detail_prospeccion_no)
        self._layout_right_detail_abs()

        for line_edit in (
            self.detail_codigo,
            self.detail_nombre_comercial,
            self.detail_telefono,
            self.detail_nombre_fiscal,
            self.detail_direccion,
            self.detail_abreviatura,
        ):
            line_edit.textEdited.connect(self._schedule_autosave)
        for checkbox in self.tipo_checks.values():
            checkbox.toggled.connect(self._schedule_autosave)
        self.detail_tipo.currentTextChanged.connect(self._schedule_autosave)
        self.detail_activo.toggled.connect(self._schedule_autosave)
        self.detail_inactivo.toggled.connect(self._schedule_autosave)
        self.detail_prospeccion_si.toggled.connect(self._schedule_autosave)
        self.detail_prospeccion_no.toggled.connect(self._schedule_autosave)

        return panel

    def _layout_right_detail_abs(self) -> None:
        panel = getattr(self, "right_detail_panel", None)
        if panel is None:
            return
        self.sectors_box.setGeometry(0, 6, 274, 128)
        self.section_info.setGeometry(5, 125, 120, 24)
        self.detail_tipo.setGeometry(5, 153, 120, 28)
        self.lbl_abrev.setGeometry(145, 125, 120, 24)
        self.detail_abreviatura.setGeometry(145, 153, 120, 28)
        self.status_box.setGeometry(0, 190, 274, 76)
        self.detail_activo.setGeometry(8, 10, 124, 28)
        self.detail_inactivo.setGeometry(140, 10, 124, 28)
        self.lbl_prospeccion.setGeometry(8, 45, 110, 24)
        self.detail_prospeccion_si.setGeometry(130, 45, 50, 24)
        self.detail_prospeccion_no.setGeometry(190, 45, 60, 24)
        self.tipo_checks["PANADERIA"].setGeometry(8, 10, 125, 24)
        self.tipo_checks["PASTELERIA"].setGeometry(141, 10, 125, 24)
        self.tipo_checks["HELADERIA"].setGeometry(8, 48, 125, 24)
        self.tipo_checks["CAFETERIA"].setGeometry(141, 48, 125, 24)
        self.tipo_checks["RESTAURANTE"].setGeometry(8, 86, 125, 24)
        self.tipo_checks["HOTEL"].setGeometry(141, 86, 125, 24)

    def _load_address_catalogs(self) -> None:
        catalogs = self.customer_service.address_catalogs()
        self.provincias = catalogs.provincias
        self.islas = catalogs.islas
        self.municipios = catalogs.municipios
        self.codigos_postales = catalogs.codigos_postales
        self.localidades = catalogs.localidades

        self.provincia_name_by_id = {str(x.provincia_id or ""): str(x.provincia_nombre or "") for x in self.provincias}
        self.isla_name_by_id = {str(x.isla_id or ""): str(x.isla_nombre or "") for x in self.islas}
        self.isla_initials_by_id = {str(x.isla_id or ""): str(getattr(x, "isla_iniciales", "") or "").strip().upper() for x in self.islas}
        self.municipio_name_by_id = {str(x.municipio_id or ""): str(x.municipio_nombre or "") for x in self.municipios}
        self.localidad_name_by_id = {str(x.localidad_id or ""): str(x.localidad_nombre or "") for x in self.localidades}

    def _fill_combo(self, combo: QComboBox, items: list[tuple[str, str]], selected_value: str = "") -> None:
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("", "")
        for label, value in items:
            combo.addItem(label, value)
        if selected_value:
            idx = combo.findData(selected_value)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
        else:
            combo.setCurrentIndex(0)
        combo.blockSignals(False)

    def _populate_provincias(self, selected_id: str = "") -> None:
        items = [(str(p.provincia_nombre or ""), str(p.provincia_id or "")) for p in self.provincias if p.provincia_nombre]
        self._fill_combo(self.detail_provincia, items, selected_id)

    def _populate_islas(self, provincia_id: str, selected_id: str = "") -> None:
        items = [
            (str(i.isla_nombre or ""), str(i.isla_id or ""))
            for i in self.islas
            if str(i.provincia_id or "") == str(provincia_id or "") and i.isla_nombre
        ]
        self._fill_combo(self.detail_isla, items, selected_id)

    def _populate_municipios(self, isla_id: str, selected_id: str = "") -> None:
        items = [
            (str(m.municipio_nombre or ""), str(m.municipio_id or ""))
            for m in self.municipios
            if str(m.isla_id or "") == str(isla_id or "") and m.municipio_nombre
        ]
        self._fill_combo(self.detail_municipio, items, selected_id)

    def _populate_cps(self, municipio_id: str, selected_cp: str = "") -> None:
        items = [
            (str(cp.codigo_postal or ""), str(cp.codigo_postal or ""))
            for cp in self.codigos_postales
            if str(cp.municipio_id or "") == str(municipio_id or "") and str(cp.codigo_postal or "").strip()
        ]
        unique_items: list[tuple[str, str]] = []
        seen: set[str] = set()
        for label, value in items:
            if value in seen:
                continue
            seen.add(value)
            unique_items.append((label, value))
        self._fill_combo(self.detail_cp, unique_items, selected_cp)

    def _populate_localidades(self, codigo_postal: str, selected_localidad_id: str = "") -> None:
        cp = str(codigo_postal or "").strip()
        if not cp:
            items: list[tuple[str, str]] = []
        else:
            items = [
                (str(loc.localidad_nombre or ""), str(loc.localidad_id or ""))
                for loc in self.localidades
                if str(loc.codigo_postal or "").strip() == cp and loc.localidad_nombre
            ]
        self._fill_combo(self.detail_localidad, items, selected_localidad_id)

    def _on_provincia_changed(self, _idx: int) -> None:
        if self._is_loading_details:
            return
        provincia_id = str(self.detail_provincia.currentData() or "")
        self._populate_islas(provincia_id, "")
        self._populate_municipios("", "")
        self._populate_cps("", "")
        self._populate_localidades("", "")
        self._schedule_autosave()

    def _on_isla_changed(self, _idx: int) -> None:
        if self._is_loading_details:
            return
        isla_id = str(self.detail_isla.currentData() or "")
        self._populate_municipios(isla_id, "")
        self._populate_cps("", "")
        self._populate_localidades("", "")
        self._schedule_autosave()

    def _on_municipio_changed(self, _idx: int) -> None:
        if self._is_loading_details:
            return
        municipio_id = str(self.detail_municipio.currentData() or "")
        self._populate_cps(municipio_id, "")
        self._populate_localidades("", "")
        self._schedule_autosave()

    def _on_cp_changed(self, _idx: int) -> None:
        if self._is_loading_details:
            return
        codigo_postal = str(self.detail_cp.currentData() or "")
        self._populate_localidades(codigo_postal, "")
        self._schedule_autosave()

    def _normalize_customer_phone(self, raw: str) -> str:
        digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
        if digits.startswith("34") and len(digits) == 11:
            digits = digits[2:]
        if len(digits) == 9:
            return f"+34 {digits[:3]} {digits[3:6]} {digits[6:]}"
        return str(raw or "").strip()

    def _format_customer_phone_field(self) -> None:
        formatted = self._normalize_customer_phone(self.detail_telefono.text())
        self.detail_telefono.setText(formatted)
        self._schedule_autosave()

    def _update_search_clear_button(self) -> None:
        if hasattr(self, "clear_search_btn"):
            self.clear_search_btn.setEnabled(bool(self.search_input.text().strip()))

    def _clear_search_filter(self) -> None:
        self.search_input.clear()
        self.search_input.setFocus()

    def _list(self, term: str) -> list:
        return self.customer_service.list(term)

    def _create(self, payload: dict) -> None:
        self.customer_service.create(payload)

    def _update(self, entity_id: str, payload: dict) -> None:
        self.customer_service.update(entity_id, payload)

    def _delete(self, entity_id: str) -> bool:
        return self.customer_service.delete(entity_id)

    def _customer_delete_blockers(self, customer_id: str) -> list[str]:
        return self.customer_service.delete_blockers(customer_id)

    def _import(self, file_path: str) -> tuple[int, list[str]]:
        return self.customer_service.import_file(Path(file_path), self.import_schema)

    def reload(self) -> None:
        selected_before = self._selected_row()
        preferred_customer_id = (
            str(getattr(selected_before, "cliente_id", "") or "").strip()
            if selected_before
            else self._last_selected_customer_id
        )
        self._load_address_catalogs()
        self._populate_island_filter()
        term = self.search_input.text().strip()
        self.rows = self._list(term)
        selected_isla_id = str(self.island_filter.currentData() or "").strip() if hasattr(self, "island_filter") else ""
        if selected_isla_id:
            self.rows = [
                row
                for row in self.rows
                if str(getattr(row, "cliente_direccion_isla_id", "") or "").strip() == selected_isla_id
            ]
        self._render_table()
        if not self._restore_customer_selection(preferred_customer_id):
            self._restore_customer_selection(self._last_selected_customer_id)
        if self.table.rowCount() > 0 and not self.table.selectionModel().selectedRows():
            self.table.selectRow(0)
        self._show_selected_details()

    def _populate_island_filter(self) -> None:
        if not hasattr(self, "island_filter"):
            return
        current = str(self.island_filter.currentData() or "").strip()
        self.island_filter.blockSignals(True)
        self.island_filter.clear()
        self.island_filter.addItem("Todas las islas", "")
        for isla in self.islas:
            isla_id = str(getattr(isla, "isla_id", "") or "").strip()
            isla_name = str(getattr(isla, "isla_nombre", "") or "").strip()
            if not isla_id or not isla_name:
                continue
            self.island_filter.addItem(isla_name, isla_id)
        idx = self.island_filter.findData(current)
        self.island_filter.setCurrentIndex(idx if idx >= 0 else 0)
        self.island_filter.blockSignals(False)

    def _render_table(self) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.rows))
        for row_idx, item in enumerate(self.rows):
            code_item = QTableWidgetItem()
            raw_code = getattr(item, "cliente_codigo", 0) or 0
            try:
                code_value = int(raw_code)
            except (TypeError, ValueError):
                code_value = 0
            code_item.setData(Qt.ItemDataRole.DisplayRole, code_value if code_value > 0 else "")
            name = str(item.cliente_nombre_comercial or item.cliente_nombre_fiscal or "")
            icon = self._customer_icon(item)
            label = f"{icon} {name}".strip() if icon else name
            name_item = QTableWidgetItem(label)
            island_item = QTableWidgetItem(self._island_initials(item))
            island_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            code_item.setData(Qt.ItemDataRole.UserRole, getattr(item, "cliente_id", None))
            self.table.setItem(row_idx, 0, code_item)
            self.table.setItem(row_idx, 1, name_item)
            self.table.setItem(row_idx, 2, island_item)
            self.table.setRowHeight(row_idx, 36)
        name_w = 268
        isla_w = 48
        self.table.setColumnWidth(0, 60)
        self.table.setColumnWidth(1, name_w)
        self.table.setColumnWidth(2, isla_w)
        self.table.setSortingEnabled(True)

    def _customer_icon(self, item: Cliente) -> str:
        text = ",".join(
            [
                str(getattr(item, "cliente_actividad", "") or ""),
                str(getattr(item, "cliente_tipo", "") or ""),
                str(getattr(item, "cliente_nombre_comercial", "") or ""),
            ]
        ).upper()
        if self._activity_matches(text, "PANADERIA"):
            return "🍞"
        if self._activity_matches(text, "PASTELERIA"):
            return "🧁"
        if self._activity_matches(text, "HELADERIA"):
            return "🍦"
        if self._activity_matches(text, "CAFETERIA"):
            return "☕"
        if self._activity_matches(text, "RESTAURANTE"):
            return "🍽"
        if self._activity_matches(text, "HOTEL"):
            return "🏨"
        return "•"

    def _activity_matches(self, text: str, activity: str) -> bool:
        normalized_text = unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("ascii").upper()
        normalized_activity = unicodedata.normalize("NFD", activity).encode("ascii", "ignore").decode("ascii").upper()
        return normalized_activity in normalized_text

    def _customer_subtext(self, item: Cliente) -> str:
        localidad_id = str(getattr(item, "cliente_direccion_localidad_id", "") or "").strip()
        localidad = self.localidad_name_by_id.get(localidad_id, "").strip()
        tipo = str(getattr(item, "cliente_tipo", "") or "").strip()
        return localidad or tipo

    def _island_initials(self, item: Cliente) -> str:
        isla_id = str(getattr(item, "cliente_direccion_isla_id", "") or "").strip()
        return str(self.isla_initials_by_id.get(isla_id, "") or "").strip().upper()

    def _selected_row(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        row_index = selected[0].row()
        id_item = self.table.item(row_index, 0)
        if id_item is None:
            return None
        customer_id = id_item.data(Qt.ItemDataRole.UserRole)
        if not customer_id:
            return None
        for row in self.rows:
            if getattr(row, "cliente_id", None) == customer_id:
                return row
        return None

    def _show_selected_details(self) -> None:
        row = self._selected_row()
        self._is_loading_details = True
        if not row:
            self._last_selected_customer_id = ""
            self.detail_codigo.clear()
            self.detail_nombre_comercial.clear()
            self.detail_telefono.clear()
            self.detail_cif.clear()
            self.detail_nombre_fiscal.clear()
            self.detail_direccion.clear()
            self.detail_abreviatura.clear()
            self._populate_provincias("")
            self._populate_islas("", "")
            self._populate_municipios("", "")
            self._populate_cps("", "")
            self._populate_localidades("", "")
            self.detail_tipo.setCurrentIndex(0)
            for checkbox in self.tipo_checks.values():
                checkbox.setChecked(False)
            self.detail_inactivo.setChecked(False)
            self.detail_activo.setChecked(False)
            self.detail_prospeccion_no.setChecked(True)
            self._render_related_contacts("")
            self._render_related_recipes("")
            self._render_customer_agenda("")
            self._is_loading_details = False
            return
        self._last_selected_customer_id = str(getattr(row, "cliente_id", "") or "").strip()
        self.detail_codigo.setText(str(row.cliente_codigo or ""))
        self.detail_nombre_comercial.setText(str(row.cliente_nombre_comercial or ""))
        self.detail_telefono.setText(self._normalize_customer_phone(str(row.cliente_telefono or "")))
        self.detail_cif.setText(str(row.cliente_cif or ""))
        self.detail_nombre_fiscal.setText(str(row.cliente_nombre_fiscal or ""))
        self.detail_direccion.setText(str(row.cliente_direccion or ""))
        self.detail_abreviatura.setText(str(getattr(row, "cliente_abreviatura", "") or ""))
        provincia_id = str(row.cliente_direccion_provincia_id or "")
        isla_id = str(row.cliente_direccion_isla_id or "")
        municipio_id = str(row.cliente_direccion_municipio_id or "")
        codigo_postal = str(row.cliente_direccion_cp or "")
        localidad_id = str(row.cliente_direccion_localidad_id or "")
        self._populate_provincias(provincia_id)
        self._populate_islas(provincia_id, isla_id)
        self._populate_municipios(isla_id, municipio_id)
        self._populate_cps(municipio_id, codigo_postal)
        self._populate_localidades(codigo_postal, localidad_id)
        self.detail_tipo.setCurrentIndex(0)

        grupos = (getattr(row, "cliente_actividad", "") or "").upper()
        for label, checkbox in self.tipo_checks.items():
            checkbox.setChecked(label in grupos)

        tipo = (getattr(row, "cliente_tipo", "") or "").strip().lower()
        idx_tipo = self.detail_tipo.findText(tipo)
        self.detail_tipo.setCurrentIndex(idx_tipo if idx_tipo >= 0 else 0)

        if bool(getattr(row, "activo", False)):
            self.detail_activo.setChecked(True)
        else:
            self.detail_inactivo.setChecked(True)
        if bool(getattr(row, "cliente_prospeccion", False)):
            self.detail_prospeccion_si.setChecked(True)
        else:
            self.detail_prospeccion_no.setChecked(True)
        self._render_related_contacts(str(getattr(row, "cliente_id", "") or ""))
        self._render_related_recipes(str(getattr(row, "cliente_id", "") or ""))
        self._render_customer_agenda(str(getattr(row, "cliente_id", "") or ""))
        self._is_loading_details = False

    def _restore_customer_selection(self, customer_id: str) -> bool:
        clean_id = str(customer_id or "").strip()
        if not clean_id:
            return False
        for row_idx in range(self.table.rowCount()):
            id_item = self.table.item(row_idx, 0)
            row_customer_id = str(id_item.data(Qt.ItemDataRole.UserRole) or "").strip() if id_item else ""
            if row_customer_id == clean_id:
                self.table.selectRow(row_idx)
                return True
        return False

    def _render_related_contacts(self, cliente_id: str) -> None:
        if not hasattr(self, "related_contacts_table"):
            return
        contacts = self.customer_service.related_contacts(cliente_id)

        self._loading_related_contacts = True
        self.related_contacts_table.blockSignals(True)
        try:
            self.related_contacts_table.setRowCount(len(contacts) + 1)
            for row_idx, item in enumerate(contacts):
                full_name = f"{(item.nombre or '').strip()} {(item.apellidos or '').strip()}".strip()
                initials = self._contact_initials(full_name)
                avatar_item = QTableWidgetItem(initials)
                avatar_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                avatar_item.setData(Qt.ItemDataRole.UserRole, str(getattr(item, "contacto_id", "") or ""))
                name_item = QTableWidgetItem(full_name)
                name_item.setData(Qt.ItemDataRole.UserRole, str(getattr(item, "contacto_id", "") or ""))
                self.related_contacts_table.setItem(row_idx, 0, avatar_item)
                self.related_contacts_table.setItem(row_idx, 1, name_item)
                self.related_contacts_table.setItem(row_idx, 2, QTableWidgetItem(str(item.cargo or "")))
                self.related_contacts_table.setItem(
                    row_idx, 3, QTableWidgetItem(f"📞 {self._format_phone_display(str(item.telefono or ''))}".strip())
                )
                self.related_contacts_table.setItem(row_idx, 4, QTableWidgetItem(f"✉ {str(item.email or '').strip()}".strip()))

            # Empty input row to allow inline creation of a new linked contact.
            new_row = len(contacts)
            placeholder = QTableWidgetItem("")
            placeholder.setData(Qt.ItemDataRole.UserRole, "")
            self.related_contacts_table.setItem(new_row, 0, placeholder)
            self.related_contacts_table.setItem(new_row, 1, QTableWidgetItem(""))
            self.related_contacts_table.setItem(new_row, 2, QTableWidgetItem(""))
            self.related_contacts_table.setItem(new_row, 3, QTableWidgetItem(""))
            self.related_contacts_table.setItem(new_row, 4, QTableWidgetItem(""))
        finally:
            self.related_contacts_table.blockSignals(False)
            self._loading_related_contacts = False
            has_contacts = len(contacts) > 0
            self.related_contacts_table.setVisible(has_contacts)
            if hasattr(self, "related_contacts_empty"):
                self.related_contacts_empty.setVisible(not has_contacts)

    def _render_related_recipes(self, cliente_id: str) -> None:
        if not hasattr(self, "related_recipes_table"):
            return
        recipes = self.customer_service.related_recipes(cliente_id)

        self.related_recipes_table.setRowCount(len(recipes))
        for row_idx, item in enumerate(recipes):
            recipe_id = int(getattr(item, "id", 0) or 0)
            recipe_number = str(recipe_id or "")
            recipe_name = str(getattr(item, "nombre", "") or "").strip()
            version = str(getattr(item, "version", "") or "").strip()
            code_item = QTableWidgetItem(recipe_number)
            code_item.setData(Qt.ItemDataRole.UserRole, recipe_id)
            name_item = QTableWidgetItem(recipe_name)
            name_item.setData(Qt.ItemDataRole.UserRole, recipe_id)
            version_item = QTableWidgetItem(version)
            self.related_recipes_table.setItem(row_idx, 0, code_item)
            self.related_recipes_table.setItem(row_idx, 1, name_item)
            self.related_recipes_table.setItem(row_idx, 2, version_item)

        has_recipes = len(recipes) > 0
        self.related_recipes_table.setVisible(has_recipes)
        if hasattr(self, "related_recipes_empty"):
            self.related_recipes_empty.setVisible(not has_recipes)

    def _open_related_recipe(self, row_idx: int, _column: int) -> None:
        if not hasattr(self, "related_recipes_table"):
            return
        id_item = self.related_recipes_table.item(row_idx, 0)
        if id_item is None:
            return
        recipe_id = int(id_item.data(Qt.ItemDataRole.UserRole) or 0)
        if recipe_id <= 0:
            return
        customer_id = self.customer_service.recipe_customer_id(recipe_id)
        if not customer_id:
            selected_customer = self._selected_row()
            customer_id = str(getattr(selected_customer, "cliente_id", "") or "")
        self._focus_recipe_in_formulas_page(recipe_id, customer_id)

    def _focus_recipe_in_formulas_page(self, recipe_id: int, customer_id: str = "") -> None:
        main_window = self.window()
        pages = getattr(main_window, "pages", None)
        if pages is None:
            return
        recipes_page = None
        for idx in range(pages.count()):
            widget = pages.widget(idx)
            if widget.__class__.__name__ == "RecipesPage":
                recipes_page = widget
                set_current_page = getattr(main_window, "_set_current_page", None)
                if callable(set_current_page):
                    set_current_page(idx)
                else:
                    pages.setCurrentIndex(idx)
                break
        if recipes_page is None:
            return
        # Ensure target tab is "Clientes" and filtered by the selected customer.
        if hasattr(recipes_page, "recipe_tabs"):
            recipes_page.recipe_tabs.setCurrentIndex(1)
        if customer_id:
            if hasattr(recipes_page, "customer_filter_selected_id"):
                recipes_page.customer_filter_selected_id = customer_id
            if hasattr(recipes_page, "_refresh_customer_filter_button"):
                recipes_page._refresh_customer_filter_button()
            if hasattr(recipes_page, "_set_combo_by_data") and hasattr(recipes_page, "cliente_combo"):
                recipes_page._set_combo_by_data(recipes_page.cliente_combo, customer_id)
        if hasattr(recipes_page, "_reload_recipe_list"):
            recipes_page._reload_recipe_list()
        if hasattr(recipes_page, "_load_recipe"):
            recipes_page._load_recipe(recipe_id)

    def _split_full_name(self, full_name: str) -> tuple[str, str]:
        text = (full_name or "").strip()
        if not text:
            return "", ""
        parts = text.split(None, 1)
        if len(parts) == 1:
            return parts[0], ""
        return parts[0], parts[1]

    def _clean_phone_input(self, value: str) -> str:
        text = (value or "").strip()
        if not text:
            return ""
        digits = "".join(ch for ch in text if ch.isdigit())
        if digits.startswith("34") and len(digits) == 11:
            digits = digits[2:]
        return digits if len(digits) == 9 else text

    def _on_related_contact_item_changed(self, item: QTableWidgetItem) -> None:
        if self._loading_related_contacts or self._related_context_menu_open:
            return
        row_idx = item.row()
        contacto_id = self._get_related_contact_id(row_idx)
        selected_customer = self._selected_row()
        if not selected_customer:
            return

        name_cell = self.related_contacts_table.item(row_idx, 0)
        if self.related_contacts_table.columnCount() >= 5:
            name_cell = self.related_contacts_table.item(row_idx, 1)
            cargo_cell = self.related_contacts_table.item(row_idx, 2)
            telefono_cell = self.related_contacts_table.item(row_idx, 3)
            email_cell = self.related_contacts_table.item(row_idx, 4)
        else:
            cargo_cell = self.related_contacts_table.item(row_idx, 1)
            telefono_cell = self.related_contacts_table.item(row_idx, 2)
            email_cell = self.related_contacts_table.item(row_idx, 3)
        full_name = str(name_cell.text() if name_cell else "").strip()
        cargo = str(cargo_cell.text() if cargo_cell else "").strip()
        telefono = str(telefono_cell.text() if telefono_cell else "").strip().replace("📞", "").strip()
        email = str(email_cell.text() if email_cell else "").strip().replace("✉", "").strip()

        if not any([full_name, cargo, telefono, email]):
            return
        nombre, apellidos = self._split_full_name(full_name)
        if not nombre:
            return

        payload = {
            "nombre": nombre,
            "apellidos": apellidos,
            "cargo": cargo,
            "telefono": self._clean_phone_input(telefono),
            "email": email,
            "cliente_id": str(getattr(selected_customer, "cliente_id", "") or ""),
        }

        try:
            contacto_id = self.customer_service.upsert_contact(contacto_id, payload)
            self._render_related_contacts(payload["cliente_id"])
            if contacto_id:
                for r in range(self.related_contacts_table.rowCount()):
                    existing_id = self._get_related_contact_id(r)
                    if existing_id == contacto_id:
                        self.related_contacts_table.selectRow(r)
                        break
        except Exception as exc:
            QMessageBox.warning(self, "Contactos", f"No se pudo guardar el contacto: {exc}")

    def _format_phone_display(self, raw_phone: str) -> str:
        text = (raw_phone or "").strip()
        if not text:
            return ""
        digits = "".join(ch for ch in text if ch.isdigit())
        if digits.startswith("34") and len(digits) == 11:
            digits = digits[2:]
        if len(digits) == 9:
            return f"+34 {digits[:3]} {digits[3:6]} {digits[6:]}"
        return text

    def _get_related_contact_id(self, row_idx: int | None = None) -> str:
        if row_idx is None:
            selected = self.related_contacts_table.selectionModel().selectedRows()
            if not selected:
                return ""
            row_idx = selected[0].row()
        avatar_item = self.related_contacts_table.item(row_idx, 0)
        if avatar_item is not None:
            cid = str(avatar_item.data(Qt.ItemDataRole.UserRole) or "")
            if cid:
                return cid
        name_item = self.related_contacts_table.item(row_idx, 1)
        if name_item is None:
            return ""
        return str(name_item.data(Qt.ItemDataRole.UserRole) or "")

    def _contact_initials(self, full_name: str) -> str:
        parts = [p for p in str(full_name or "").strip().split() if p]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return f"{parts[0][:1]}{parts[1][:1]}".upper()

    def _add_related_contact(self) -> None:
        selected_customer = self._selected_row()
        if not selected_customer:
            QMessageBox.warning(self, "Contactos", "Selecciona un cliente.")
            return
        schema = [
            {"name": "nombre", "label": "Nombre"},
            {"name": "apellidos", "label": "Apellidos"},
            {"name": "cargo", "label": "Cargo"},
            {"name": "telefono", "label": "Telefono"},
            {"name": "email", "label": "Email"},
        ]
        dialog = EntityDialog("Nuevo: Contacto", schema, parent=self)
        if not dialog.exec():
            return
        payload = dialog.get_payload()
        nombre = str(payload.get("nombre") or "").strip()
        if not nombre:
            QMessageBox.warning(self, "Contactos", "Nombre es obligatorio.")
            return
        create_payload = {
            "nombre": nombre,
            "apellidos": str(payload.get("apellidos") or "").strip(),
            "cargo": str(payload.get("cargo") or "").strip(),
            "telefono": self._clean_phone_input(str(payload.get("telefono") or "").strip()),
            "email": str(payload.get("email") or "").strip(),
            "cliente_id": str(getattr(selected_customer, "cliente_id", "") or ""),
        }
        self.customer_service.create_contact(create_payload)
        self._render_related_contacts(create_payload["cliente_id"])

    def _open_related_contact(self, row_idx: int, _column: int) -> None:
        if self._related_context_menu_open:
            return
        contacto_id = self._get_related_contact_id(row_idx)
        if not contacto_id:
            return
        self._focus_contact_in_contacts_page(contacto_id)

    def _focus_contact_in_contacts_page(self, contacto_id: str) -> None:
        main_window = self.window()
        pages = getattr(main_window, "pages", None)
        if pages is None:
            return
        contacts_page = None
        for idx in range(pages.count()):
            widget = pages.widget(idx)
            if widget.__class__.__name__ == "ContactsPage":
                contacts_page = widget
                set_current_page = getattr(main_window, "_set_current_page", None)
                if callable(set_current_page):
                    set_current_page(idx)
                else:
                    pages.setCurrentIndex(idx)
                break
        if contacts_page is None:
            return
        contacts_page.reload()
        if hasattr(contacts_page, "_select_row_by_id"):
            contacts_page._select_row_by_id(contacto_id)

    def _apply_modern_styles(self) -> None:
        agenda_arrow_icon = (BASE_DIR / "assets" / "icons" / "arrow-down.svg").as_posix()
        style = """
            QWidget {
                font-family: 'Segoe UI', 'Inter';
            }
            QWidget#CustomersPageRoot {
                background: transparent;
                border: none;
            }
            QFrame#crmCard, QWidget#crmCard {
                background: transparent;
                border: none;
                border-radius: 0;
            }
            QWidget#detailSubPanel {
                background: transparent;
                border: 0;
            }
            QWidget#detailTopArea {
                background: #EAF3FF;
                border: none;
            }
            QWidget#customersRightPanel {
                background: transparent;
                border: none;
            }
            QWidget#customersRightPanelStretch {
                background: #FDECEC;
                border: none;
            }
            QFrame#detailLeftCard {
                background: #FFFFFF;
                border: 1px solid #D7DEE8;
                border-radius: 8px;
            }
            QFrame#detailRightCard {
                background: #FFFFFF;
                border: 1px solid #D7DEE8;
                border-radius: 8px;
            }
            QSplitter#customersMainSplitter,
            QSplitter#customersDetailSplitter {
                background: transparent;
                border: none;
            }
            QSplitter#customersDetailSplitter {
                background: #EAF8EA;
            }
            QSplitter#customersMainSplitter::handle,
            QSplitter#customersDetailSplitter::handle {
                background: transparent;
                border: none;
            }
            QSplitter#detailInnerSplitter {
                background: transparent;
                border: 0;
            }
            QSplitter#detailInnerSplitter::handle {
                background: transparent;
                border: 0;
                width: 0px;
                height: 0px;
            }
            QFrame#plainGroup {
                background: transparent;
                border: 0;
            }
            QLabel[role="pageTitle"] {
                font-size: 18px;
                font-weight: 700;
                color: #0F172A;
                margin-bottom: 0px;
            }
            QLabel[role="pageSubtitle"] {
                font-size: 13px;
                color: #64748B;
                margin-bottom: 4px;
            }
            QLabel[role="sectionTitle"] {
                font-size: 14px;
                font-weight: 600;
                color: #111827;
            }
            QLabel[role="blockTitle"] {
                font-size: 13px;
                font-weight: 600;
                color: #0F172A;
                margin-top: 2px;
            }
            QLineEdit, QComboBox {
                min-height: 26px;
                padding: 2px 8px;
                border: 1px solid #D1D5DB;
                border-radius: 8px;
                background: #FFFFFF;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #3B82F6;
            }
            QPushButton#customerSearchClearButton {
                min-width: 30px;
                max-width: 30px;
                min-height: 30px;
                max-height: 30px;
                padding: 0;
                margin: 0;
                border-radius: 6px;
                background: #EF4444;
                color: #FFFFFF;
                border: 1px solid #DC2626;
                icon-size: 14px;
            }
            QPushButton#customerSearchClearButton:hover {
                background: #DC2626;
                border: 1px solid #B91C1C;
            }
            QPushButton#customerSearchClearButton:pressed {
                background: #B91C1C;
                border: 1px solid #991B1B;
            }
            QPushButton#customerSearchClearButton:disabled {
                background: #F8FAFC;
                color: #94A3B8;
                border: 1px solid #CBD5E1;
            }
            QPushButton#relatedAddContactBtn {
                background: #3E78D8;
                color: #FFFFFF;
                border: 1px solid #2F6BD1;
                border-radius: 12px;
                min-height: 34px;
                padding: 7px 18px;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton#relatedAddContactBtn:hover {
                background: #336CCB;
                border: 1px solid #2A5FBE;
            }
            QPushButton:hover {
                opacity: 0.95;
            }
            QTabWidget#customerTabs::pane {
                border: 0;
                background: transparent;
                margin-top: 0px;
            }
            QTabWidget#customerTabs QTabBar {
                background: transparent;
            }
            QTabWidget#customerTabs::tab-bar {
                background: transparent;
                left: 0px;
            }
            QTabWidget#customerTabs QTabBar::tab {
                background: #FFFFFF;
                color: #64748B;
                padding: 8px 14px;
                border: 1px solid #E2E8F0;
                border-bottom: 2px solid transparent;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 6px;
                margin-bottom: 0px;
                font-weight: 600;
            }
            QTabWidget#customerTabs QTabBar::tab:selected {
                color: #3B82F6;
                background: #FFFFFF;
                border-bottom: 2px solid #3B82F6;
            }
            QTabWidget#customerTabs QTabBar::tab:!selected {
                background: #F8FAFC;
            }
            QTableWidget {
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                background: #FFFFFF;
                alternate-background-color: #FAFBFF;
                selection-background-color: #3A78CF;
                gridline-color: #EEF2F7;
            }
            QTableWidget::item {
                padding: 7px;
            }
            QTableWidget::item:selected {
                color: #FFFFFF;
            }
            QTableWidget::item:focus {
                border: none;
                outline: 0;
            }
            QTableWidget#customersListTable::item:selected {
                background: #3A78CF;
                color: #FFFFFF;
            }
            QTableWidget#relatedContactsTable {
                border: 1px solid #DCE4EF;
                border-radius: 10px;
                background: #FFFFFF;
                gridline-color: #E8EDF5;
            }
            QTableWidget#relatedContactsTable::item {
                padding: 8px 10px;
            }
            QTableWidget#relatedContactsTable::item:selected {
                background: #3A78CF;
                color: #FFFFFF;
            }
            QTableWidget#relatedContactsTable QHeaderView::section {
                background: #F7F9FC;
                color: #2F3E55;
                border: 0;
                border-right: 1px solid #E7ECF3;
                border-bottom: 1px solid #DEE6F1;
                padding: 6px 8px;
                min-height: 30px;
                font-weight: 600;
            }
            QLabel#relatedContactsEmpty {
                color: #6E7E96;
                font-size: 14px;
                font-weight: 500;
                padding: 24px 16px;
                background: #F8FAFD;
                border: 1px dashed #D6E0EE;
                border-radius: 10px;
            }
            QTableWidget#customerAgendaTable {
                border: 1px solid #DCE4EF;
                border-radius: 10px;
                background: #FFFFFF;
                gridline-color: #E8EDF5;
            }
            QTableWidget#customerAgendaTable::item {
                padding: 4px 10px;
            }
            QTableWidget#customerAgendaTable::item:selected {
                background: #3A78CF;
                color: #FFFFFF;
            }
            QTableWidget#customerAgendaTable QHeaderView::section {
                background: #F7F9FC;
                color: #2F3E55;
                border: 0;
                border-right: 1px solid #E7ECF3;
                border-bottom: 1px solid #DEE6F1;
                padding: 1px 8px;
                min-height: 16px;
                font-weight: 600;
            }
            QLabel#customerAgendaTitle {
                color: #14213D;
                font-size: 17px;
                font-weight: 800;
                padding: 0 2px 0 2px;
            }
            QComboBox#customerAgendaFilter, QDateEdit#customerAgendaFilterDate {
                min-height: 24px;
                max-height: 24px;
                padding: 0px 6px;
                border: 1px solid #C9D5E6;
                border-radius: 8px;
                background: #FFFFFF;
                color: #334155;
                font-weight: 600;
                font-size: 10px;
            }
            QComboBox#customerAgendaFilter::drop-down, QDateEdit#customerAgendaFilterDate::drop-down {
                border: none;
                width: 16px;
                subcontrol-origin: padding;
                subcontrol-position: top right;
            }
            QComboBox#customerAgendaFilter::down-arrow, QDateEdit#customerAgendaFilterDate::down-arrow {
                width: 8px;
                height: 8px;
                image: url("__AGENDA_ARROW_ICON__");
            }
            QComboBox#customerAgendaFilter, QDateEdit#customerAgendaFilterDate {
                padding-right: 16px;
            }
            QLabel#customerAgendaRangeSep {
                color: #64748B;
                font-weight: 700;
                padding: 0 2px;
            }
            QWidget#customerAgendaStatePill {
                background: transparent;
            }
            QPushButton#customerAgendaRefreshButton {
                min-width: 112px;
                max-width: 112px;
                min-height: 24px;
                max-height: 24px;
                padding: 0 8px;
                border-radius: 8px;
                background: #FFFFFF;
                color: #334155;
                border: 1px solid #CBD5E1;
                font-size: 10px;
                font-weight: 600;
            }
            QPushButton#customerAgendaRefreshButton:hover {
                background: #F8FAFC;
                border: 1px solid #94A3B8;
            }
            QPushButton#customerAgendaRefreshButton:pressed {
                background: #E2E8F0;
                border: 1px solid #94A3B8;
            }
            QPushButton#customerAgendaRefreshButton::menu-indicator {
                image: none;
            }
            QPushButton#customerAgendaRefreshButton::icon {
                width: 14px;
                height: 14px;
            }
            QCalendarWidget {
                background: #FFFFFF;
                color: #0F172A;
            }
            QCalendarWidget#customerAgendaPopupCalendar QWidget#qt_calendar_navigationbar {
                min-height: 30px;
                max-height: 30px;
                background: #FFFFFF;
                padding: 2px 6px;
            }
            QCalendarWidget QToolButton {
                min-width: 20px;
                max-width: 20px;
                min-height: 20px;
                max-height: 20px;
                padding: 0;
                margin: 0;
                border: none;
                background: transparent;
                icon-size: 12px;
            }
            QCalendarWidget QToolButton::menu-indicator {
                image: none;
            }
            QCalendarWidget#customerAgendaPopupCalendar QToolButton#qt_calendar_prevmonth,
            QCalendarWidget#customerAgendaPopupCalendar QToolButton#qt_calendar_nextmonth,
            QCalendarWidget#customerAgendaPopupCalendar QToolButton#qt_calendar_monthbutton,
            QCalendarWidget#customerAgendaPopupCalendar QToolButton#qt_calendar_yearbutton {
                min-height: 24px;
                max-height: 24px;
                padding: 0 8px;
                margin: 0 3px;
                border: none;
                background: transparent;
                font-size: 10px;
            }
            QCalendarWidget QComboBox {
                min-height: 22px;
                max-height: 22px;
                min-width: 74px;
                max-width: 74px;
                padding: 0 4px;
                margin: 0;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                background: #FFFFFF;
                color: #334155;
                font-size: 10px;
            }
            QCalendarWidget QAbstractSpinBox {
                min-height: 22px;
                max-height: 22px;
                min-width: 64px;
                max-width: 64px;
                padding: 0 4px;
                margin: 0;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                background: #FFFFFF;
                color: #334155;
                font-size: 10px;
            }
            QCalendarWidget QAbstractSpinBox::up-button,
            QCalendarWidget QAbstractSpinBox::down-button {
                width: 14px;
                border: none;
                background: transparent;
            }
            QCalendarWidget QAbstractSpinBox::up-arrow,
            QCalendarWidget QAbstractSpinBox::down-arrow {
                width: 7px;
                height: 7px;
            }
            QCalendarWidget QComboBox::drop-down {
                border: none;
                width: 14px;
            }
            QCalendarWidget QComboBox::down-arrow {
                width: 7px;
                height: 7px;
                image: url("__AGENDA_ARROW_ICON__");
            }
            QCalendarWidget QAbstractItemView {
                selection-background-color: #3A78CF;
                selection-color: #FFFFFF;
            }
            QCalendarWidget#customerAgendaPopupCalendar QComboBox {
                min-height: 22px;
                max-height: 22px;
                min-width: 82px;
                max-width: 82px;
                padding: 0 4px;
                font-size: 10px;
            }
            QCalendarWidget#customerAgendaPopupCalendar QToolButton#qt_calendar_monthbutton {
                min-width: 88px;
                max-width: 88px;
            }
            QCalendarWidget#customerAgendaPopupCalendar QToolButton#qt_calendar_yearbutton {
                min-width: 66px;
                max-width: 66px;
            }
            QCalendarWidget#customerAgendaPopupCalendar QAbstractSpinBox {
                min-width: 66px;
                max-width: 66px;
            }
            QLabel#customerAgendaEmpty {
                color: #6E7E96;
                font-size: 14px;
                font-weight: 500;
                padding: 18px 16px;
                background: #F8FAFD;
                border: 1px dashed #D6E0EE;
                border-radius: 10px;
            }
            QHeaderView::section {
                background: #F8FAFC;
                color: #334155;
                border: 0;
                border-bottom: 1px solid #E2E8F0;
                padding: 6px 8px;
            }
            QCheckBox#sectorChip {
                spacing: 6px;
                min-height: 26px;
                padding: 2px 4px;
                color: #334155;
                font-weight: 600;
                background: transparent;
                border: none;
            }
            QCheckBox#sectorChip::indicator {
                width: 14px;
                height: 14px;
                border-radius: 3px;
                border: 1px solid #94A3B8;
                background: #FFFFFF;
            }
            QCheckBox#sectorChip::indicator:checked {
                border-color: #3B82F6;
                background: #3B82F6;
            }
            QCheckBox#sectorChip:checked {
                color: #1E40AF;
            }
            QCheckBox#sectorChipPillPanaderia, QCheckBox#sectorChipPillPasteleria,
            QCheckBox#sectorChipPillHeladeria, QCheckBox#sectorChipPillCafeteria,
            QCheckBox#sectorChipPillRestaurante, QCheckBox#sectorChipPillHotel {
                spacing: 6px;
                min-height: 22px;
                padding: 1px 9px;
                font-size: 11px;
                color: #0F172A;
                font-weight: 600;
                border-radius: 18px;
            }
            QCheckBox#sectorChipPillPanaderia::indicator,
            QCheckBox#sectorChipPillPasteleria::indicator,
            QCheckBox#sectorChipPillHeladeria::indicator,
            QCheckBox#sectorChipPillCafeteria::indicator,
            QCheckBox#sectorChipPillRestaurante::indicator,
            QCheckBox#sectorChipPillHotel::indicator {
                width: 11px;
                height: 11px;
            }
            QCheckBox#sectorChipPillPanaderia {
                background: #FEF3C7;
                border: 1px solid #F59E0B;
            }
            QCheckBox#sectorChipPillPasteleria {
                background: #FCE7F3;
                border: 1px solid #EC4899;
            }
            QCheckBox#sectorChipPillHeladeria {
                background: #DBEAFE;
                border: 1px solid #3B82F6;
            }
            QCheckBox#sectorChipPillCafeteria {
                background: #EDE9FE;
                border: 1px solid #8B5CF6;
            }
            QCheckBox#sectorChipPillRestaurante {
                background: #DCFCE7;
                border: 1px solid #22C55E;
            }
            QCheckBox#sectorChipPillHotel {
                background: #FFE4E6;
                border: 1px solid #F43F5E;
            }
            QPushButton#stateChipActive, QPushButton#stateChipInactive {
                spacing: 0;
                border-radius: 12px;
                min-height: 26px;
                padding: 0px;
                font-size: 10px;
                font-weight: 600;
                text-align: center;
                background: #E5E7EB;
                border: 1px solid #9CA3AF;
                color: #1F2937;
            }
            QPushButton#stateChipActive {
            }
            QPushButton#stateChipInactive {
            }
            QPushButton#stateChipActive:checked {
                background: #DCFCE7;
                border: 1px solid #22C55E;
                color: #166534;
            }
            QPushButton#stateChipInactive:checked {
                background: #FEE2E2;
                border: 1px solid #EF4444;
                color: #991B1B;
            }
            """
        self.setStyleSheet(style.replace("__AGENDA_ARROW_ICON__", agenda_arrow_icon))

    def _show_related_contacts_context_menu(self, pos) -> None:
        source = self.sender()
        source_widget = source if isinstance(source, QWidget) else self.related_contacts_table
        global_pos = source_widget.mapToGlobal(pos)
        row_idx = None
        if source is self.related_contacts_table:
            index = self.related_contacts_table.indexAt(pos)
            row_idx = index.row() if index.isValid() else None
            global_pos = self.related_contacts_table.viewport().mapToGlobal(pos)
        contacto_id = ""
        if row_idx is not None:
            self.related_contacts_table.selectRow(row_idx)
            contacto_id = self._get_related_contact_id(row_idx)

        menu = QMenu(self)
        action_add = menu.addAction("Añadir")
        action_edit = menu.addAction("Editar")
        action_unlink = menu.addAction("Eliminar")
        action_add.setEnabled(self._selected_row() is not None)
        if not contacto_id:
            action_edit.setEnabled(False)
            action_unlink.setEnabled(False)
        self._related_context_menu_open = True
        try:
            chosen = menu.exec(global_pos)
        finally:
            self._related_context_menu_open = False
        if chosen == action_add:
            self._add_related_contact()
            return
        if chosen == action_edit:
            self._edit_related_contact(contacto_id)
            return
        if chosen == action_unlink:
            self._unlink_related_contact(contacto_id)

    def _edit_related_contact(self, contacto_id: str) -> None:
        contact = self.customer_service.get_contact(contacto_id)
        if not contact:
            QMessageBox.warning(self, "Atencion", "Contacto no encontrado.")
            return
        schema = [
            {"name": "nombre", "label": "Nombre"},
            {"name": "apellidos", "label": "Apellidos"},
            {"name": "cargo", "label": "Cargo"},
            {"name": "nif", "label": "NIF"},
            {"name": "telefono", "label": "Telefono"},
            {"name": "email", "label": "Email"},
        ]
        initial = {field["name"]: getattr(contact, field["name"], "") for field in schema}
        dialog = EntityDialog("Editar: Contacto", schema, initial=initial, parent=self)
        if not dialog.exec():
            return
        payload = dialog.get_payload()
        if not (payload.get("nombre") or "").strip():
            QMessageBox.warning(self, "Atencion", "Nombre es obligatorio.")
            return
        self.customer_service.update_contact(
            contacto_id,
            {
                "nombre": (payload.get("nombre") or "").strip(),
                "apellidos": (payload.get("apellidos") or "").strip(),
                "cargo": (payload.get("cargo") or "").strip(),
                "nif": (payload.get("nif") or "").strip(),
                "telefono": (payload.get("telefono") or "").strip(),
                "email": (payload.get("email") or "").strip(),
            },
        )
        selected = self._selected_row()
        self._render_related_contacts(str(getattr(selected, "cliente_id", "") or ""))

    def _unlink_related_contact(self, contacto_id: str) -> None:
        selected_customer = self._selected_row()
        if not selected_customer:
            return
        answer = QMessageBox.question(
            self,
            "Confirmar",
            "Se quitara la relacion del contacto con este cliente. El contacto no se eliminara.\n\nContinuar?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            self.customer_service.unlink_contact(contacto_id, self.UNLINKED_CLIENT_ID)
        except Exception as exc:
            QMessageBox.warning(self, "Atencion", str(exc))
            return

        self._render_related_contacts(str(getattr(selected_customer, "cliente_id", "") or ""))

    def _schedule_autosave(self, *_args) -> None:
        if self._is_loading_details or not self._selected_row():
            return
        self._autosave_timer.start(350)

    def _schedule_reload(self) -> None:
        self._search_timer.start(250)

    def _autosave_selected_customer(self) -> None:
        row = self._selected_row()
        if not row:
            return

        telefono = self._normalize_customer_phone(self.detail_telefono.text().strip())
        self.detail_telefono.setText(telefono)
        provincia_id = str(self.detail_provincia.currentData() or "").strip()
        isla_id = str(self.detail_isla.currentData() or "").strip()
        municipio_id = str(self.detail_municipio.currentData() or "").strip()
        codigo_postal = str(self.detail_cp.currentData() or "").strip()
        localidad_id = str(self.detail_localidad.currentData() or "").strip()

        payload = {
            "cliente_nombre_comercial": self.detail_nombre_comercial.text().strip(),
            "cliente_telefono": telefono,
            "cliente_nombre_fiscal": self.detail_nombre_fiscal.text().strip(),
            "cliente_direccion": self.detail_direccion.text().strip(),
            "cliente_abreviatura": self.detail_abreviatura.text().strip().upper(),
            "cliente_cif": self.detail_cif.text().strip(),
            "cliente_direccion_cp": codigo_postal,
            "cliente_direccion_provincia_id": provincia_id,
            "cliente_direccion_isla_id": isla_id,
            "cliente_direccion_municipio_id": municipio_id,
            "cliente_direccion_localidad_id": localidad_id,
            "cliente_tipo": (self.detail_tipo.currentText() or "").strip().lower(),
            "cliente_actividad": ",".join(
                [label for label, checkbox in self.tipo_checks.items() if checkbox.isChecked()]
            ),
            "cliente_prospeccion": self.detail_prospeccion_si.isChecked(),
            "activo": self.detail_activo.isChecked(),
        }

        selected_id = row.cliente_id
        try:
            self._update(row.cliente_id, payload)
        except Exception as exc:
            QMessageBox.warning(self, "Guardado automatico", f"No se pudo guardar el cambio: {exc}")
        finally:
            self.reload()
            self._select_row_by_id(selected_id)

    def _select_row_by_id(self, customer_id: str) -> None:
        for row in range(self.table.rowCount()):
            cell = self.table.item(row, 0)
            if cell and cell.data(Qt.ItemDataRole.UserRole) == customer_id:
                self.table.selectRow(row)
                break

    def _show_customers_context_menu(self, pos) -> None:
        index = self.table.indexAt(pos)
        if index.isValid():
            self.table.selectRow(index.row())

        row = self._selected_row()
        has_row = row is not None
        menu = QMenu(self)
        action_new = menu.addAction("Nuevo cliente")
        menu.addSeparator()
        action_edit = menu.addAction("Editar")
        action_delete = menu.addAction("Eliminar")
        menu.addSeparator()
        action_copy_id = menu.addAction("Copiar ID")
        action_copy_name = menu.addAction("Copiar nombre")
        action_show_id = menu.addAction("Ver ID")
        menu.addSeparator()
        action_clear_filter = menu.addAction("Vaciar filtro")
        action_refresh = menu.addAction("Refrescar")

        for action in (action_edit, action_delete, action_copy_id, action_copy_name, action_show_id):
            action.setEnabled(has_row)
        action_clear_filter.setEnabled(bool(self.search_input.text().strip()))

        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen == action_new:
            self._new_entity()
            return
        if chosen == action_edit:
            self._edit_entity()
            return
        if chosen == action_delete:
            self._delete_entity()
            return
        if chosen == action_copy_id and row is not None:
            QApplication.clipboard().setText(str(getattr(row, "cliente_id", "") or ""))
            return
        if chosen == action_copy_name and row is not None:
            QApplication.clipboard().setText(str(getattr(row, "cliente_nombre_comercial", "") or ""))
            return
        if chosen == action_show_id:
            self._show_customer_id_dialog()
            return
        if chosen == action_clear_filter:
            self._clear_search_filter()
            return
        if chosen == action_refresh:
            self.reload()

    def _set_report_actions_enabled(self, enabled: bool) -> None:
        for attr in ("report_excel_btn", "report_pdf_btn", "report_print_btn"):
            button = getattr(self, attr, None)
            if button is not None:
                button.setEnabled(enabled)

    def _generate_customer_report(self) -> None:
        self.report_status_label.setText("Generando listado...")
        QApplication.processEvents()
        result = self.customer_report_flow_service.generate_report(self.report_prompt.toPlainText())
        self._last_customer_report_flow_result = result
        report = result.report
        self._last_customer_report = report
        if result.status == "empty" and report is None:
            QMessageBox.warning(self, "Listados", result.message)
            return
        if result.status == "error":
            QMessageBox.warning(self, "Listados", result.message)
            return
        if report is None:
            QMessageBox.warning(self, "Listados", "No se pudo generar el listado.")
            return
        self._render_customer_report(report)
        self.report_status_label.setText(f"{report.title} · {len(report.rows)} fila(s) · {result.source}")
        if result.message and not result.used_ai:
            self.report_status_label.setToolTip(result.message)

    def _render_customer_report(self, report: CustomerReportResult) -> None:
        self.report_table.clear()
        self.report_table.setColumnCount(len(report.headers))
        self.report_table.setHorizontalHeaderLabels(report.headers)
        self.report_table.setRowCount(len(report.rows))
        for row_idx, row in enumerate(report.rows):
            for col_idx, value in enumerate(row):
                self.report_table.setItem(row_idx, col_idx, QTableWidgetItem(str(value)))
        self.report_table.resizeColumnsToContents()
        if report.headers:
            self.report_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        for col_idx in range(1, len(report.headers)):
            self.report_table.horizontalHeader().setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Stretch)
        self._set_report_actions_enabled(bool(report.rows))

    def _export_customer_report_excel(self) -> None:
        report = self.customer_report_flow_service.last_report
        if report is None:
            QMessageBox.warning(self, "Listados", "Genera primero un listado.")
            return
        default = str(self.report_export_service.default_path(report.title, "xlsx"))
        path, _ = QFileDialog.getSaveFileName(self, "Exportar listado a Excel", default, "Excel (*.xlsx)")
        if not path:
            return
        out = self.report_export_service.export_excel(path, report.title, report.headers, report.rows)
        QMessageBox.information(self, "Listados", f"Excel exportado:\n{out}")

    def _export_customer_report_pdf(self) -> None:
        report = self.customer_report_flow_service.last_report
        if report is None:
            QMessageBox.warning(self, "Listados", "Genera primero un listado.")
            return
        default = str(self.report_export_service.default_path(report.title, "pdf"))
        path, _ = QFileDialog.getSaveFileName(self, "Exportar listado a PDF", default, "PDF (*.pdf)")
        if not path:
            return
        out = self.report_export_service.export_pdf(path, report.title, report.headers, report.rows)
        QMessageBox.information(self, "Listados", f"PDF exportado:\n{out}")

    def _print_customer_report(self) -> None:
        report = self.customer_report_flow_service.last_report
        if report is None:
            QMessageBox.warning(self, "Listados", "Genera primero un listado.")
            return
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageOrientation(QPrinter.Orientation.Landscape)
        dialog = QPrintDialog(printer, self)
        if dialog.exec() != QPrintDialog.DialogCode.Accepted:
            return
        document = QTextDocument()
        document.setHtml(build_customer_report_html(report))
        document.print_(printer)

    def _new_entity(self) -> None:
        dialog = EntityDialog("Nuevo: Clientes", self.edit_schema, parent=self)
        if dialog.exec():
            payload = dialog.get_payload()
            self._create(payload)
            self.reload()

    def _edit_entity(self) -> None:
        row = self._selected_row()
        if not row:
            QMessageBox.warning(self, "Atencion", "Selecciona un cliente.")
            return
        initial = {field["name"]: getattr(row, field["name"], None) for field in self.edit_schema}
        dialog = EntityDialog("Editar: Clientes", self.edit_schema, initial=initial, parent=self)
        if dialog.exec():
            payload = dialog.get_payload()
            self._update(row.cliente_id, payload)
            self.reload()

    def _delete_entity(self) -> None:
        row = self._selected_row()
        if not row:
            QMessageBox.warning(self, "Atencion", "Selecciona un cliente.")
            return
        answer = QMessageBox.question(
            self,
            "Confirmar",
            f"Eliminar cliente {getattr(row, 'cliente_nombre_comercial', row.cliente_id)}?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            blockers = self._customer_delete_blockers(row.cliente_id)
            if blockers:
                QMessageBox.warning(
                    self,
                    "No se puede eliminar",
                    "Este cliente tiene datos relacionados:\n\n"
                    + "\n".join(f"- {item}" for item in blockers)
                    + "\n\nQuita o reasigna esos datos antes de eliminar el cliente.",
                )
                return
            try:
                self._delete(row.cliente_id)
            except IntegrityError:
                QMessageBox.warning(
                    self,
                    "No se puede eliminar",
                    "SQLite ha bloqueado el borrado porque el cliente esta referenciado por otros datos.",
                )
                return
            self.reload()

    def _show_customer_id_dialog(self) -> None:
        row = self._selected_row()
        if not row:
            QMessageBox.warning(self, "Clientes", "Selecciona un cliente.")
            return
        cliente_id = str(getattr(row, "cliente_id", "") or "").strip()
        if not cliente_id:
            QMessageBox.warning(self, "Clientes", "El cliente no tiene ID.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("ID del cliente")
        dialog.setModal(True)
        layout = QVBoxLayout(dialog)

        label = QLabel("ID del cliente")
        id_field = QLineEdit(cliente_id)
        id_field.setReadOnly(True)
        id_field.setCursorPosition(0)
        id_field.setSelection(0, 0)

        buttons = QHBoxLayout()
        copy_btn = QPushButton("Copiar")
        close_btn = QPushButton("Cerrar")
        copy_btn.setProperty("btnRole", "secondary")
        close_btn.setProperty("btnRole", "secondary")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(cliente_id))
        close_btn.clicked.connect(dialog.accept)
        buttons.addWidget(copy_btn)
        buttons.addStretch(1)
        buttons.addWidget(close_btn)

        layout.addWidget(label)
        layout.addWidget(id_field)
        layout.addLayout(buttons)
        dialog.resize(460, 130)
        dialog.exec()

    def _show_customer_help(self) -> None:
        QMessageBox.information(
            self,
            "Ayuda de clientes",
            "Usa la barra superior para crear, editar, eliminar, imprimir o exportar clientes.\n"
            "La búsqueda filtra la lista por nombre y el botón de refresco recarga los datos.",
        )

    def _import_entities(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar archivo",
            "",
            "Archivos de datos (*.xlsx *.xlsm *.csv)",
        )
        if not file_path:
            return
        imported, errors = self._import(file_path)
        self.reload()
        if errors:
            preview = "\n".join(errors[:8])
            extra = "" if len(errors) <= 8 else f"\n... y {len(errors) - 8} errores mas."
            QMessageBox.warning(
                self,
                "Importacion completada con incidencias",
                f"Registros importados: {imported}\nErrores: {len(errors)}\n\n{preview}{extra}",
            )
            return
        QMessageBox.information(self, "Importacion completada", f"Registros importados: {imported}")
