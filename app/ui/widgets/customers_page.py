from pathlib import Path
import unicodedata

from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtGui import QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QRadioButton,
    QMessageBox,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStyle,
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

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._main_splitter = splitter
        layout.addWidget(splitter, 1)

        left_panel = QWidget()
        left_panel.setObjectName("crmCard")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(14, 14, 14, 14)
        left_layout.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar cliente...")
        self.search_input.setFixedWidth(352)
        self.search_input.textChanged.connect(self._schedule_reload)
        self.search_input.textChanged.connect(self._update_search_clear_button)
        self.search_input.setFixedHeight(34)
        self.clear_search_btn = QPushButton()
        self.clear_search_btn.setObjectName("customerSearchClearButton")
        self.clear_search_btn.setFixedSize(34, 34)
        self.clear_search_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton))
        self.clear_search_btn.setIconSize(QSize(14, 14))
        self.clear_search_btn.setToolTip("Vaciar filtro")
        self.clear_search_btn.setEnabled(False)
        self.clear_search_btn.clicked.connect(self._clear_search_filter)
        self.island_filter = QComboBox()
        self.island_filter.setFixedWidth(390)
        self.island_filter.currentIndexChanged.connect(self.reload)
        search_row = QHBoxLayout()
        search_row.setContentsMargins(0, 0, 0, 0)
        search_row.setSpacing(8)
        search_row.addWidget(self.search_input)
        search_row.addWidget(self.clear_search_btn)
        left_layout.addWidget(self.island_filter)
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
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        ribbon = QFrame()
        ribbon.setObjectName("crmCard")
        ribbon.setFrameShape(QFrame.Shape.StyledPanel)
        ribbon_layout = QHBoxLayout(ribbon)
        ribbon_layout.setContentsMargins(12, 10, 12, 10)
        ribbon_layout.setSpacing(8)

        self.new_btn = QPushButton("Nuevo")
        self.new_btn.setProperty("btnRole", "success")
        self.edit_btn = QPushButton("Editar")
        self.edit_btn.setProperty("btnRole", "warning")
        self.del_btn = QPushButton("Eliminar")
        self.del_btn.setProperty("btnRole", "danger")
        self.id_btn = QPushButton("ID")
        self.id_btn.setProperty("btnRole", "secondary")
        self.import_btn = QPushButton("Importar Excel/CSV")
        self.import_btn.setProperty("btnRole", "secondary")
        self.reports_btn = QPushButton("Listados")
        self.reports_btn.setProperty("btnRole", "primary")
        self.refresh_btn = QPushButton("Refrescar")
        self.refresh_btn.setProperty("btnRole", "secondary")
        self.new_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
        self.edit_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        self.del_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        self.id_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogInfoView))
        self.import_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp))
        self.reports_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogListView))
        self.refresh_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))

        self.new_btn.clicked.connect(self._new_entity)
        self.edit_btn.clicked.connect(self._edit_entity)
        self.del_btn.clicked.connect(self._delete_entity)
        self.id_btn.clicked.connect(self._show_customer_id_dialog)
        self.import_btn.clicked.connect(self._import_entities)
        self.reports_btn.clicked.connect(self._open_customer_reports_dialog)
        self.refresh_btn.clicked.connect(self.reload)

        ribbon_layout.addWidget(self.new_btn)
        ribbon_layout.addSpacing(10)
        ribbon_layout.addWidget(self.edit_btn)
        ribbon_layout.addWidget(self.del_btn)
        ribbon_layout.addSpacing(10)
        ribbon_layout.addWidget(self.id_btn)
        ribbon_layout.addWidget(self.import_btn)
        ribbon_layout.addWidget(self.reports_btn)
        ribbon_layout.addStretch(1)
        ribbon_layout.addWidget(self.refresh_btn)
        right_layout.addWidget(ribbon)

        right_splitter = QSplitter(Qt.Orientation.Vertical)
        self._detail_splitter = right_splitter
        right_layout.addWidget(right_splitter, 1)

        detail_panel = QWidget()
        detail_panel.setObjectName("detailTopArea")
        detail_panel.setFixedHeight(300)
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(10)

        detail_title = QLabel("Detalle de cliente", detail_panel)
        detail_title.setProperty("role", "sectionTitle")
        self.detail_title = detail_title
        self.detail_title.setGeometry(5, 0, 300, 24)
        self.detail_tipo_header = QLabel("Clasificación del cliente", detail_panel)
        self.detail_tipo_header.setProperty("role", "sectionTitle")
        self.detail_tipo_header.setGeometry(550, 0, 300, 24)

        self.detail_panel = detail_panel

        left_card = QFrame(detail_panel)
        left_card.setObjectName("crmCard")
        self.left_card = left_card
        left_card_layout = QVBoxLayout(left_card)
        left_card_layout.setContentsMargins(2, 2, 2, 2)
        left_card_layout.setSpacing(0)
        left_detail_panel = self._build_upper_left_detail_panel()
        left_card_layout.addWidget(left_detail_panel, 1)

        right_card = QFrame(detail_panel)
        right_card.setObjectName("crmCard")
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
        self.customer_tabs.addTab(self._build_tab_placeholder("Agenda y proxima actividad."), "Agenda")
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
        # Coordenadas fijas dentro del detail_panel.
        left_card.setGeometry(5, 25, 540, 270)
        right_card.setGeometry(550, 25, 290, 270)

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
        self.setStyleSheet(
            """
            QWidget {
                font-family: 'Segoe UI', 'Inter';
            }
            QWidget#CustomersPageRoot {
                background: #F5F7FA;
            }
            QFrame#crmCard, QWidget#crmCard {
                background: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
            }
            QWidget#detailSubPanel {
                background: transparent;
                border: 0;
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
            QPushButton {
                min-height: 30px;
                border-radius: 8px;
                padding: 5px 12px;
            }
            QPushButton[btnRole="success"] {
                background: #22C55E;
                color: white;
                border: 1px solid #16A34A;
                font-weight: 600;
            }
            QPushButton[btnRole="warning"] {
                background: #F59E0B;
                color: #111827;
                border: 1px solid #D97706;
                font-weight: 600;
            }
            QPushButton[btnRole="danger"] {
                background: #EF4444;
                color: white;
                border: 1px solid #DC2626;
                font-weight: 600;
            }
            QPushButton[btnRole="secondary"] {
                background: #FFFFFF;
                color: #334155;
                border: 1px solid #CBD5E1;
                font-weight: 500;
            }
            QPushButton[btnRole="primary"] {
                background: #3B82F6;
                color: #FFFFFF;
                border: 1px solid #2563EB;
                font-weight: 600;
            }
            QPushButton#customerSearchClearButton {
                min-width: 34px;
                max-width: 34px;
                min-height: 34px;
                max-height: 34px;
                padding: 0;
                margin: 0;
                border-radius: 8px;
                background: #FEE2E2;
                color: #991B1B;
                border: 1px solid #FCA5A5;
                icon-size: 14px;
            }
            QPushButton#customerSearchClearButton:hover {
                background: #FECACA;
                border: 1px solid #F87171;
            }
            QPushButton#customerSearchClearButton:pressed {
                background: #FCA5A5;
                border: 1px solid #EF4444;
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
        )

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
