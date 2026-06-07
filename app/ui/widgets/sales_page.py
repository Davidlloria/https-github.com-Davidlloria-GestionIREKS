from __future__ import annotations

from datetime import date

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.services.sales_annual_comparison_service import SalesAnnualComparisonService, SalesComparisonRow
from app.services.sales_reconciliation_service import SalesReconciliationService


MONTH_NAMES = [
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
]


class NumericTableWidgetItem(QTableWidgetItem):
    def __init__(self, text: str, value: float) -> None:
        super().__init__(text)
        self.value = float(value or 0.0)

    def __lt__(self, other) -> bool:
        if isinstance(other, NumericTableWidgetItem):
            return self.value < other.value
        return super().__lt__(other)


class CodeTableWidgetItem(QTableWidgetItem):
    def __init__(self, text: str) -> None:
        super().__init__(text)
        raw = str(text or "").strip().upper()
        digits = "".join(ch for ch in raw if ch.isdigit())
        prefix = "".join(ch for ch in raw if ch.isalpha())
        if digits:
            sort_key = (0, int(digits), prefix, raw)
        else:
            sort_key = (1, 0, prefix, raw)
        self.setData(Qt.ItemDataRole.UserRole, sort_key)

    def __lt__(self, other) -> bool:
        left = self.data(Qt.ItemDataRole.UserRole)
        right = other.data(Qt.ItemDataRole.UserRole) if other is not None else None
        if isinstance(left, tuple) and isinstance(right, tuple):
            return left < right
        return super().__lt__(other)


class SalesPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.sales_service = SalesReconciliationService()
        self.sales_summary_service = SalesAnnualComparisonService()
        self._building = False
        self._building_igsa = False
        self._product_filter_timer = QTimer(self)
        self._product_filter_timer.setSingleShot(True)
        self._product_filter_timer.timeout.connect(self.reload)
        self._product_filter_timer_igsa = QTimer(self)
        self._product_filter_timer_igsa.setSingleShot(True)
        self._product_filter_timer_igsa.timeout.connect(self.reload_igsa)
        self._build_ui()
        self.reload()
        self.reload_igsa()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setSpacing(4)

        title = QLabel("Ventas")
        title.setProperty("role", "pageTitle")
        root_layout.addWidget(title)

        tabs = QTabWidget()
        root_layout.addWidget(tabs)

        ireks_tab = QWidget()
        tabs.addTab(ireks_tab, "IREKS")
        igsa_tab = QWidget()
        tabs.addTab(igsa_tab, "IGSA")

        igsa_layout = QVBoxLayout(igsa_tab)
        igsa_filters_top = QHBoxLayout()
        igsa_filters_top.addWidget(QLabel("Año"))
        self.year_filter_igsa = QComboBox()
        self.year_filter_igsa.currentIndexChanged.connect(self.reload_igsa)
        self.year_filter_igsa.setMinimumWidth(90)
        igsa_filters_top.addWidget(self.year_filter_igsa)

        igsa_filters_top.addWidget(QLabel("Mes"))
        self.month_filter_igsa = QComboBox()
        self.month_filter_igsa.currentIndexChanged.connect(self.reload_igsa)
        self.month_filter_igsa.setMinimumWidth(125)
        igsa_filters_top.addWidget(self.month_filter_igsa)

        self.acumulado_check_igsa = QCheckBox()
        self.acumulado_check_igsa.toggled.connect(self.reload_igsa)
        igsa_filters_top.addWidget(self.acumulado_check_igsa)
        igsa_filters_top.addWidget(QLabel("Acumulado"))

        igsa_filters_top.addWidget(QLabel("Fabricante"))
        self.manufacturer_filter_igsa = QComboBox()
        self.manufacturer_filter_igsa.currentIndexChanged.connect(self._on_manufacturer_changed_igsa)
        self.manufacturer_filter_igsa.setMinimumWidth(190)
        igsa_filters_top.addWidget(self.manufacturer_filter_igsa)

        igsa_filters_top.addWidget(QLabel("Familia"))
        self.family_filter_igsa = QComboBox()
        self.family_filter_igsa.currentIndexChanged.connect(self._on_family_changed_igsa)
        self.family_filter_igsa.setMinimumWidth(190)
        igsa_filters_top.addWidget(self.family_filter_igsa)

        igsa_filters_top.addWidget(QLabel("Subfamilia"))
        self.subfamily_filter_igsa = QComboBox()
        self.subfamily_filter_igsa.currentIndexChanged.connect(self.reload_igsa)
        self.subfamily_filter_igsa.setMinimumWidth(190)
        igsa_filters_top.addWidget(self.subfamily_filter_igsa)
        igsa_layout.addLayout(igsa_filters_top)

        igsa_filters_bottom = QHBoxLayout()
        igsa_filters_bottom.addWidget(QLabel("Producto"))
        self.product_filter_igsa = QLineEdit()
        self.product_filter_igsa.setPlaceholderText("Buscar por código o descripción...")
        self.product_filter_igsa.textChanged.connect(self._schedule_product_reload_igsa)
        self.product_filter_igsa.setMinimumWidth(300)
        igsa_filters_bottom.addWidget(self.product_filter_igsa, 1)
        igsa_layout.addLayout(igsa_filters_bottom)

        group_header_style = """
            QTableWidget#salesGroupHeader {
                border: none;
                background: transparent;
                selection-background-color: transparent;
            }
            QTableWidget#salesGroupHeader::item,
            QTableWidget#salesGroupHeader::item:hover,
            QTableWidget#salesGroupHeader::item:selected,
            QTableWidget#salesGroupHeader::item:focus {
                border: none;
                background: transparent;
                outline: none;
            }
            """

        totals_table_style = """
            QTableWidget#salesTotalsTableIgsa {
                border: 1px solid #C9D1DC;
                border-radius: 0;
                background: #FFFFFF;
                gridline-color: #C9D1DC;
                selection-background-color: transparent;
            }
            QTableWidget#salesTotalsTableIgsa::viewport {
                border: none;
                border-radius: 0;
                background: #FFFFFF;
            }
            QTableWidget#salesTotalsTableIgsa::item,
            QTableWidget#salesTotalsTableIgsa::item:hover,
            QTableWidget#salesTotalsTableIgsa::item:selected,
            QTableWidget#salesTotalsTableIgsa::item:focus {
                border: none;
                background: #FFFFFF;
                outline: none;
                padding: 2px 6px;
            }
            QTableWidget#salesTotalsTableIgsa::item:selected:!active {
                background: #FFFFFF;
            }
            """

        self.group_header_igsa = QTableWidget(1, 12)
        self.group_header_igsa.setObjectName("salesGroupHeaderIgsa")
        self.group_header_igsa.setFixedHeight(36)
        self.group_header_igsa.horizontalHeader().setVisible(False)
        self.group_header_igsa.verticalHeader().setVisible(False)
        self.group_header_igsa.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.group_header_igsa.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.group_header_igsa.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.group_header_igsa.setShowGrid(False)
        self.group_header_igsa.verticalHeader().setDefaultSectionSize(34)
        self.group_header_igsa.setRowHeight(0, 34)
        self.group_header_igsa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.group_header_igsa.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.group_header_igsa.viewport().setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.group_header_igsa.setStyleSheet(group_header_style)
        igsa_layout.addWidget(self.group_header_igsa)

        self.sales_table_igsa = QTableWidget(0, 12)
        self.sales_table_igsa.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.sales_table_igsa.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.sales_table_igsa.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.sales_table_igsa.verticalHeader().setVisible(False)
        self.sales_table_igsa.setSortingEnabled(True)
        self.sales_table_igsa.setHorizontalHeaderLabels(
            [
                "Cod.",
                "Producto",
                "Kilos",
                "S/C",
                "Ventas",
                "Kilos",
                "S/C",
                "Ventas",
                "Δ kg",
                "Δ kg %",
                "Δ €",
                "Δ € %",
            ]
        )
        header_igsa = self.sales_table_igsa.horizontalHeader()
        header_igsa.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header_igsa.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for idx in range(2, 12):
            header_igsa.setSectionResizeMode(idx, QHeaderView.ResizeMode.Fixed)
        header_igsa.sectionResized.connect(self._sync_aux_column_width_igsa)
        igsa_layout.addWidget(self.sales_table_igsa, 1)

        self.totals_table_igsa = QTableWidget(1, 12)
        self.totals_table_igsa.setObjectName("salesTotalsTableIgsa")
        self.totals_table_igsa.horizontalHeader().setVisible(False)
        self.totals_table_igsa.verticalHeader().setVisible(False)
        self.totals_table_igsa.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.totals_table_igsa.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.totals_table_igsa.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.totals_table_igsa.setFrameShape(QTableWidget.Shape.NoFrame)
        self.totals_table_igsa.setFixedHeight(36)
        self.totals_table_igsa.verticalHeader().setDefaultSectionSize(36)
        self.totals_table_igsa.setRowHeight(0, 36)
        self.totals_table_igsa.setShowGrid(True)
        self.totals_table_igsa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.totals_table_igsa.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.totals_table_igsa.setStyleSheet(totals_table_style)
        self.totals_table_igsa.viewport().setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        igsa_layout.addWidget(self.totals_table_igsa)

        layout = QVBoxLayout(ireks_tab)
        layout.setSpacing(4)

        filters_top = QHBoxLayout()
        filters_top.addWidget(QLabel("Año"))
        self.year_filter = QComboBox()
        self.year_filter.currentIndexChanged.connect(self.reload)
        self.year_filter.setMinimumWidth(90)
        filters_top.addWidget(self.year_filter)

        filters_top.addWidget(QLabel("Mes"))
        self.month_filter = QComboBox()
        self.month_filter.currentIndexChanged.connect(self.reload)
        self.month_filter.setMinimumWidth(125)
        filters_top.addWidget(self.month_filter)
        self.acumulado_check = QCheckBox()
        self.acumulado_check.toggled.connect(self.reload)
        filters_top.addWidget(self.acumulado_check)
        filters_top.addWidget(QLabel("Acumulado"))

        filters_top.addWidget(QLabel("Cliente"))
        self.client_filter = QComboBox()
        self.client_filter.currentIndexChanged.connect(self.reload)
        self.client_filter.setMinimumWidth(260)
        filters_top.addWidget(self.client_filter, 1)

        layout.addLayout(filters_top)

        filters_bottom = QHBoxLayout()
        filters_bottom.addWidget(QLabel("Fabricante"))
        self.manufacturer_filter = QComboBox()
        self.manufacturer_filter.currentIndexChanged.connect(self._on_manufacturer_changed)
        self.manufacturer_filter.setMinimumWidth(190)
        filters_bottom.addWidget(self.manufacturer_filter)

        filters_bottom.addWidget(QLabel("Familia"))
        self.family_filter = QComboBox()
        self.family_filter.currentIndexChanged.connect(self._on_family_changed)
        self.family_filter.setMinimumWidth(190)
        filters_bottom.addWidget(self.family_filter)

        filters_bottom.addWidget(QLabel("Subfamilia"))
        self.subfamily_filter = QComboBox()
        self.subfamily_filter.currentIndexChanged.connect(self.reload)
        self.subfamily_filter.setMinimumWidth(190)
        filters_bottom.addWidget(self.subfamily_filter)

        filters_bottom.addWidget(QLabel("Producto"))
        self.product_filter = QLineEdit()
        self.product_filter.setPlaceholderText("Buscar por código o descripción...")
        self.product_filter.textChanged.connect(self._schedule_product_reload)
        self.product_filter.setMinimumWidth(300)
        filters_bottom.addWidget(self.product_filter, 1)
        layout.addLayout(filters_bottom)

        self.group_header = QTableWidget(1, 12)
        self.group_header.setObjectName("salesGroupHeader")
        self.group_header.setFixedHeight(36)
        self.group_header.horizontalHeader().setVisible(False)
        self.group_header.verticalHeader().setVisible(False)
        self.group_header.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.group_header.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.group_header.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.group_header.setShowGrid(False)
        self.group_header.verticalHeader().setDefaultSectionSize(34)
        self.group_header.setRowHeight(0, 34)
        self.group_header.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.group_header.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.group_header.viewport().setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.group_header.setStyleSheet(
            """
            QTableWidget#salesGroupHeader {
                border: none;
                background: transparent;
                selection-background-color: transparent;
            }
            QTableWidget#salesGroupHeader::item,
            QTableWidget#salesGroupHeader::item:hover,
            QTableWidget#salesGroupHeader::item:selected,
            QTableWidget#salesGroupHeader::item:focus {
                border: none;
                background: transparent;
                outline: none;
            }
            """
        )
        layout.addWidget(self.group_header)

        self.sales_table = QTableWidget(0, 12)
        self.sales_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.sales_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.sales_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.sales_table.verticalHeader().setVisible(False)
        self.sales_table.setSortingEnabled(True)
        self.sales_table.setHorizontalHeaderLabels(
            [
                "Cod.",
                "Producto",
                "Kilos",
                "S/C",
                "Ventas",
                "Kilos",
                "S/C",
                "Ventas",
                "Δ kg",
                "Δ kg %",
                "Δ €",
                "Δ € %",
            ]
        )
        header = self.sales_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for idx in range(2, 12):
            header.setSectionResizeMode(idx, QHeaderView.ResizeMode.Fixed)
        header.sectionResized.connect(self._sync_aux_column_width)
        layout.addWidget(self.sales_table, 1)

        self.totals_table = QTableWidget(1, 12)
        self.totals_table.setObjectName("salesTotalsTable")
        self.totals_table.horizontalHeader().setVisible(False)
        self.totals_table.verticalHeader().setVisible(False)
        self.totals_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.totals_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.totals_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.totals_table.setFrameShape(QTableWidget.Shape.NoFrame)
        self.totals_table.setFixedHeight(36)
        self.totals_table.verticalHeader().setDefaultSectionSize(36)
        self.totals_table.setRowHeight(0, 36)
        self.totals_table.setShowGrid(True)
        self.totals_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.totals_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.totals_table.setStyleSheet(
            """
            QTableWidget#salesTotalsTable {
                border: 1px solid #C9D1DC;
                border-radius: 0;
                background: #FFFFFF;
                gridline-color: #C9D1DC;
                selection-background-color: transparent;
            }
            QTableWidget#salesTotalsTable::viewport {
                border: none;
                border-radius: 0;
                background: #FFFFFF;
            }
            QTableWidget#salesTotalsTable::item,
            QTableWidget#salesTotalsTable::item:hover,
            QTableWidget#salesTotalsTable::item:selected,
            QTableWidget#salesTotalsTable::item:focus {
                border: none;
                background: #FFFFFF;
                outline: none;
                padding: 2px 6px;
            }
            QTableWidget#salesTotalsTable::item:selected:!active {
                background: #FFFFFF;
            }
            """
        )
        self.totals_table.viewport().setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.totals_table)
        self._apply_column_widths()

        self.sales_table.horizontalScrollBar().valueChanged.connect(self.group_header.horizontalScrollBar().setValue)
        self.sales_table.horizontalScrollBar().valueChanged.connect(self.totals_table.horizontalScrollBar().setValue)
        self.sales_table_igsa.horizontalScrollBar().valueChanged.connect(self.group_header_igsa.horizontalScrollBar().setValue)
        self.sales_table_igsa.horizontalScrollBar().valueChanged.connect(self.totals_table_igsa.horizontalScrollBar().setValue)
        self._apply_column_widths_igsa()

    def _current_year(self) -> int:
        return int(self.year_filter.currentData() or 0)

    def _current_month(self) -> int:
        return int(self.month_filter.currentData() or 0)

    def _current_client_id(self) -> str:
        return str(self.client_filter.currentData() or "").strip()

    def _current_product_text(self) -> str:
        return str(self.product_filter.text() or "").strip()

    def _current_manufacturer_id(self) -> str:
        return str(self.manufacturer_filter.currentData() or "").strip()

    def _current_family_id(self) -> str:
        return str(self.family_filter.currentData() or "").strip()

    def _current_subfamily_id(self) -> str:
        return str(self.subfamily_filter.currentData() or "").strip()

    def _on_manufacturer_changed(self) -> None:
        if self._building:
            return
        self.family_filter.blockSignals(True)
        self.family_filter.setCurrentIndex(0 if self.family_filter.count() else -1)
        self.family_filter.blockSignals(False)
        self.subfamily_filter.blockSignals(True)
        self.subfamily_filter.setCurrentIndex(0 if self.subfamily_filter.count() else -1)
        self.subfamily_filter.blockSignals(False)
        self.product_filter.blockSignals(True)
        self.product_filter.clear()
        self.product_filter.blockSignals(False)
        self.reload()

    def _on_family_changed(self) -> None:
        if self._building:
            return
        self.subfamily_filter.blockSignals(True)
        self.subfamily_filter.setCurrentIndex(0 if self.subfamily_filter.count() else -1)
        self.subfamily_filter.blockSignals(False)
        self.product_filter.blockSignals(True)
        self.product_filter.clear()
        self.product_filter.blockSignals(False)
        self.reload()

    def reload(self) -> None:
        if self._building:
            return
        self._building = True
        try:
            self._reload_filters()
            year = self._current_year()
            if year <= 0:
                self.sales_table.setRowCount(0)
                self._fill_group_headers(date.today().year)
                self._fill_totals_row(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
                return
            rows = self.sales_summary_service.listar_resumen_anual(
                year=year,
                month=self._current_month(),
                acumulado=bool(self.acumulado_check.isChecked()),
                cliente_id=self._current_client_id(),
                producto_texto=self._current_product_text(),
                fabricante_id=self._current_manufacturer_id(),
                familia_id=self._current_family_id(),
                subfamilia_id=self._current_subfamily_id(),
            )
            self._fill_sales(rows, year)
        finally:
            self._building = False

    def _reload_filters(self) -> None:
        current_year = self._current_year()
        current_month = self._current_month()
        current_client_id = self._current_client_id()
        current_manufacturer_id = self._current_manufacturer_id()
        current_family_id = self._current_family_id()
        current_subfamily_id = self._current_subfamily_id()

        years = self.sales_summary_service.list_years()
        if not years:
            years = [date.today().year]
        clients = self.sales_summary_service.list_filter_clients()
        manufacturers = self.sales_summary_service.list_filter_manufacturers()
        families = self.sales_summary_service.list_filter_families(current_manufacturer_id)
        family_ids = {str(getattr(row, "articulo_familia_id", "") or "").strip() for row in families}
        effective_family_id = current_family_id if current_family_id in family_ids else ""
        subfamilies = self.sales_summary_service.list_filter_subfamilies(effective_family_id)
        subfamily_ids = {str(getattr(row, "articulo_subfamilia_id", "") or "").strip() for row in subfamilies}
        effective_subfamily_id = current_subfamily_id if current_subfamily_id in subfamily_ids else ""

        self.year_filter.blockSignals(True)
        self.year_filter.clear()
        for year in years:
            self.year_filter.addItem(str(year), int(year))
        idx = self.year_filter.findData(current_year if current_year else years[0])
        self.year_filter.setCurrentIndex(idx if idx >= 0 else 0)
        self.year_filter.blockSignals(False)

        self.month_filter.blockSignals(True)
        self.month_filter.clear()
        self.month_filter.addItem("Todos", 0)
        for month, label in enumerate(MONTH_NAMES, start=1):
            self.month_filter.addItem(label, month)
        m_idx = self.month_filter.findData(current_month)
        self.month_filter.setCurrentIndex(m_idx if m_idx >= 0 else 0)
        self.month_filter.blockSignals(False)

        self.client_filter.blockSignals(True)
        self.client_filter.clear()
        self.client_filter.addItem("Todos", "")
        for client in clients:
            cliente_id = str(getattr(client, "cliente_id", "") or "").strip()
            if not cliente_id:
                continue
            label = str(getattr(client, "cliente_nombre_comercial", "") or "").strip() or str(
                getattr(client, "cliente_nombre_fiscal", "") or ""
            ).strip()
            tipo = str(getattr(client, "cliente_tipo", "") or "").strip()
            display = f"{label or cliente_id} ({tipo})" if tipo else label or cliente_id
            self.client_filter.addItem(display, cliente_id)
        c_idx = self.client_filter.findData(current_client_id)
        self.client_filter.setCurrentIndex(c_idx if c_idx >= 0 else 0)
        self.client_filter.blockSignals(False)

        self.manufacturer_filter.blockSignals(True)
        self.manufacturer_filter.clear()
        self.manufacturer_filter.addItem("Todos", "")
        for manufacturer in manufacturers:
            manufacturer_id = str(getattr(manufacturer, "fabricante_id", "") or "").strip()
            if not manufacturer_id:
                continue
            label = str(getattr(manufacturer, "fabricante_nombre", "") or "").strip() or manufacturer_id
            self.manufacturer_filter.addItem(label, manufacturer_id)
        mfg_idx = self.manufacturer_filter.findData(current_manufacturer_id)
        self.manufacturer_filter.setCurrentIndex(mfg_idx if mfg_idx >= 0 else 0)
        self.manufacturer_filter.blockSignals(False)

        self.family_filter.blockSignals(True)
        self.family_filter.clear()
        self.family_filter.addItem("Todas", "")
        for family in families:
            family_id = str(getattr(family, "articulo_familia_id", "") or "").strip()
            if not family_id:
                continue
            label = str(getattr(family, "articulo_familia_nombre", "") or "").strip() or family_id
            self.family_filter.addItem(label, family_id)
        f_idx = self.family_filter.findData(effective_family_id)
        self.family_filter.setCurrentIndex(f_idx if f_idx >= 0 else 0)
        self.family_filter.blockSignals(False)

        self.subfamily_filter.blockSignals(True)
        self.subfamily_filter.clear()
        self.subfamily_filter.addItem("Todas", "")
        for subfamily in subfamilies:
            subfamily_id = str(getattr(subfamily, "articulo_subfamilia_id", "") or "").strip()
            if not subfamily_id:
                continue
            label = str(getattr(subfamily, "articulo_subfamilia_nombre", "") or "").strip() or subfamily_id
            self.subfamily_filter.addItem(label, subfamily_id)
        s_idx = self.subfamily_filter.findData(effective_subfamily_id)
        self.subfamily_filter.setCurrentIndex(s_idx if s_idx >= 0 else 0)
        self.subfamily_filter.blockSignals(False)

    def _schedule_product_reload(self) -> None:
        if self._building:
            return
        self._product_filter_timer.start(250)

    def _current_year_igsa(self) -> int:
        return int(self.year_filter_igsa.currentData() or 0)

    def _current_month_igsa(self) -> int:
        return int(self.month_filter_igsa.currentData() or 0)

    def _current_product_text_igsa(self) -> str:
        return str(self.product_filter_igsa.text() or "").strip()

    def _current_manufacturer_id_igsa(self) -> str:
        return str(self.manufacturer_filter_igsa.currentData() or "").strip()

    def _current_family_id_igsa(self) -> str:
        return str(self.family_filter_igsa.currentData() or "").strip()

    def _current_subfamily_id_igsa(self) -> str:
        return str(self.subfamily_filter_igsa.currentData() or "").strip()

    def _on_manufacturer_changed_igsa(self) -> None:
        if self._building_igsa:
            return
        self.family_filter_igsa.blockSignals(True)
        self.family_filter_igsa.setCurrentIndex(0 if self.family_filter_igsa.count() else -1)
        self.family_filter_igsa.blockSignals(False)
        self.subfamily_filter_igsa.blockSignals(True)
        self.subfamily_filter_igsa.setCurrentIndex(0 if self.subfamily_filter_igsa.count() else -1)
        self.subfamily_filter_igsa.blockSignals(False)
        self.product_filter_igsa.blockSignals(True)
        self.product_filter_igsa.clear()
        self.product_filter_igsa.blockSignals(False)
        self.reload_igsa()

    def _on_family_changed_igsa(self) -> None:
        if self._building_igsa:
            return
        self.subfamily_filter_igsa.blockSignals(True)
        self.subfamily_filter_igsa.setCurrentIndex(0 if self.subfamily_filter_igsa.count() else -1)
        self.subfamily_filter_igsa.blockSignals(False)
        self.product_filter_igsa.blockSignals(True)
        self.product_filter_igsa.clear()
        self.product_filter_igsa.blockSignals(False)
        self.reload_igsa()

    def _schedule_product_reload_igsa(self) -> None:
        if self._building_igsa:
            return
        self._product_filter_timer_igsa.start(250)

    def reload_igsa(self) -> None:
        if self._building_igsa:
            return
        self._building_igsa = True
        try:
            self._reload_filters_igsa()
            year = self._current_year_igsa()
            if year <= 0:
                self.sales_table_igsa.setRowCount(0)
                self._fill_group_headers_igsa(date.today().year)
                self._fill_totals_row_igsa(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
                return
            rows = self.sales_summary_service.listar_resumen_anual_igsa(
                year=year,
                month=self._current_month_igsa(),
                acumulado=bool(self.acumulado_check_igsa.isChecked()),
                producto_texto=self._current_product_text_igsa(),
                fabricante_id=self._current_manufacturer_id_igsa(),
                familia_id=self._current_family_id_igsa(),
                subfamilia_id=self._current_subfamily_id_igsa(),
            )
            self._fill_sales_igsa(rows, year)
        finally:
            self._building_igsa = False

    def _reload_filters_igsa(self) -> None:
        current_year = self._current_year_igsa()
        current_month = self._current_month_igsa()
        current_manufacturer_id = self._current_manufacturer_id_igsa()
        current_family_id = self._current_family_id_igsa()
        current_subfamily_id = self._current_subfamily_id_igsa()

        years = self.sales_summary_service.list_years_igsa()
        if not years:
            years = [date.today().year]
        manufacturers = self.sales_summary_service.list_filter_manufacturers_igsa()
        families = self.sales_summary_service.list_filter_families_igsa(current_manufacturer_id)
        family_ids = {str(getattr(row, "articulo_familia_id", "") or "").strip() for row in families}
        effective_family_id = current_family_id if current_family_id in family_ids else ""
        subfamilies = self.sales_summary_service.list_filter_subfamilies_igsa(effective_family_id)
        subfamily_ids = {str(getattr(row, "articulo_subfamilia_id", "") or "").strip() for row in subfamilies}
        effective_subfamily_id = current_subfamily_id if current_subfamily_id in subfamily_ids else ""

        self.year_filter_igsa.blockSignals(True)
        self.year_filter_igsa.clear()
        for year in years:
            self.year_filter_igsa.addItem(str(year), int(year))
        idx = self.year_filter_igsa.findData(current_year if current_year else years[0])
        self.year_filter_igsa.setCurrentIndex(idx if idx >= 0 else 0)
        self.year_filter_igsa.blockSignals(False)

        self.month_filter_igsa.blockSignals(True)
        self.month_filter_igsa.clear()
        self.month_filter_igsa.addItem("Todos", 0)
        for month, label in enumerate(MONTH_NAMES, start=1):
            self.month_filter_igsa.addItem(label, month)
        m_idx = self.month_filter_igsa.findData(current_month)
        self.month_filter_igsa.setCurrentIndex(m_idx if m_idx >= 0 else 0)
        self.month_filter_igsa.blockSignals(False)

        self.manufacturer_filter_igsa.blockSignals(True)
        self.manufacturer_filter_igsa.clear()
        self.manufacturer_filter_igsa.addItem("Todos", "")
        for manufacturer in manufacturers:
            manufacturer_id = str(getattr(manufacturer, "fabricante_id", "") or "").strip()
            if not manufacturer_id:
                continue
            label = str(getattr(manufacturer, "fabricante_nombre", "") or "").strip() or manufacturer_id
            self.manufacturer_filter_igsa.addItem(label, manufacturer_id)
        mfg_idx = self.manufacturer_filter_igsa.findData(current_manufacturer_id)
        self.manufacturer_filter_igsa.setCurrentIndex(mfg_idx if mfg_idx >= 0 else 0)
        self.manufacturer_filter_igsa.blockSignals(False)

        self.family_filter_igsa.blockSignals(True)
        self.family_filter_igsa.clear()
        self.family_filter_igsa.addItem("Todas", "")
        for family in families:
            family_id = str(getattr(family, "articulo_familia_id", "") or "").strip()
            if not family_id:
                continue
            label = str(getattr(family, "articulo_familia_nombre", "") or "").strip() or family_id
            self.family_filter_igsa.addItem(label, family_id)
        f_idx = self.family_filter_igsa.findData(effective_family_id)
        self.family_filter_igsa.setCurrentIndex(f_idx if f_idx >= 0 else 0)
        self.family_filter_igsa.blockSignals(False)

        self.subfamily_filter_igsa.blockSignals(True)
        self.subfamily_filter_igsa.clear()
        self.subfamily_filter_igsa.addItem("Todas", "")
        for subfamily in subfamilies:
            subfamily_id = str(getattr(subfamily, "articulo_subfamilia_id", "") or "").strip()
            if not subfamily_id:
                continue
            label = str(getattr(subfamily, "articulo_subfamilia_nombre", "") or "").strip() or subfamily_id
            self.subfamily_filter_igsa.addItem(label, subfamily_id)
        s_idx = self.subfamily_filter_igsa.findData(effective_subfamily_id)
        self.subfamily_filter_igsa.setCurrentIndex(s_idx if s_idx >= 0 else 0)
        self.subfamily_filter_igsa.blockSignals(False)

    def _apply_column_widths_igsa(self) -> None:
        widths = {
            0: 84,
            2: 95,
            3: 78,
            4: 118,
            5: 95,
            6: 78,
            7: 118,
            8: 95,
            9: 88,
            10: 118,
            11: 84,
        }
        for col, width in widths.items():
            self.sales_table_igsa.setColumnWidth(col, width)
            self.group_header_igsa.setColumnWidth(col, width)
            self.totals_table_igsa.setColumnWidth(col, width)

    def _sync_aux_column_width_igsa(self, logical_index: int, _old_size: int, new_size: int) -> None:
        self.group_header_igsa.setColumnWidth(logical_index, new_size)
        self.totals_table_igsa.setColumnWidth(logical_index, new_size)

    def _set_group_item_igsa(self, column: int, text: str, color: str, span: int = 1) -> None:
        if span > 1:
            self.group_header_igsa.setSpan(0, column, 1, span)
        self.group_header_igsa.setCellWidget(0, column, self._make_band_label(text, color))

    def _fill_group_headers_igsa(self, year: int) -> None:
        self.group_header_igsa.clearSpans()
        self.group_header_igsa.clearContents()
        for col in range(12):
            self.group_header_igsa.removeCellWidget(0, col)
            label = QLabel("")
            label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            if col in {0, 1}:
                label.setStyleSheet("background-color: transparent; border: none; padding: 0;")
            else:
                label.setStyleSheet("background-color: #F3F6FA; border: 1px solid #000000; border-radius: 0; padding: 0;")
            self.group_header_igsa.setCellWidget(0, col, label)
        self._set_group_item_igsa(2, str(year - 1), "#3E5064", 3)
        self._set_group_item_igsa(5, str(year), "#0F766E", 3)
        self._set_group_item_igsa(8, "Diferencias", "#111827", 4)

    def _fill_sales_igsa(self, rows: list[SalesComparisonRow], year: int) -> None:
        self._fill_group_headers_igsa(year)
        self.sales_table_igsa.setSortingEnabled(False)
        self.sales_table_igsa.setRowCount(len(rows))
        total_prev_kg = 0.0
        total_prev_sc = 0.0
        total_curr_kg = 0.0
        total_curr_sc = 0.0
        total_prev_sales = 0.0
        total_curr_sales = 0.0

        for idx, row in enumerate(rows):
            total_prev_kg += row.kilos_prev
            total_prev_sc += row.sc_prev
            total_curr_kg += row.kilos_curr
            total_curr_sc += row.sc_curr
            total_prev_sales += row.ventas_prev
            total_curr_sales += row.ventas_curr
            values = [
                row.codigo,
                row.nombre,
                (self._fmt_num(row.kilos_prev), row.kilos_prev),
                (self._fmt_num(row.sc_prev), row.sc_prev),
                (self._fmt_money(row.ventas_prev), row.ventas_prev),
                (self._fmt_num(row.kilos_curr), row.kilos_curr),
                (self._fmt_num(row.sc_curr), row.sc_curr),
                (self._fmt_money(row.ventas_curr), row.ventas_curr),
                (self._fmt_num(row.delta_kg), row.delta_kg),
                (self._fmt_pct(row.delta_kg_pct), row.delta_kg_pct),
                (self._fmt_money(row.delta_ventas), row.delta_ventas),
                (self._fmt_pct(row.delta_ventas_pct), row.delta_ventas_pct),
            ]
            for col, value in enumerate(values):
                if isinstance(value, tuple):
                    item = NumericTableWidgetItem(value[0], value[1])
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    item.setToolTip(value[0])
                    if col in {8, 9, 10, 11}:
                        if value[1] > 0:
                            item.setForeground(QColor("#067647"))
                        elif value[1] < 0:
                            item.setForeground(QColor("#B42318"))
                else:
                    if col == 0:
                        item = CodeTableWidgetItem(str(value or ""))
                    else:
                        item = QTableWidgetItem(str(value or ""))
                    item.setToolTip(str(value or ""))
                self.sales_table_igsa.setItem(idx, col, item)
        self.sales_table_igsa.setSortingEnabled(True)
        self._fill_totals_row_igsa(total_prev_kg, total_prev_sc, total_prev_sales, total_curr_kg, total_curr_sc, total_curr_sales)

    def _fill_totals_row_igsa(
        self,
        prev_kg: float,
        prev_sc: float,
        prev_sales: float,
        curr_kg: float,
        curr_sc: float,
        curr_sales: float,
    ) -> None:
        self.totals_table_igsa.clearSpans()
        self.totals_table_igsa.clearContents()
        for col in range(12):
            self.totals_table_igsa.removeCellWidget(0, col)

        prev_total_kg = prev_kg + prev_sc
        curr_total_kg = curr_kg + curr_sc
        delta_kg = curr_total_kg - prev_total_kg
        delta_sales = curr_sales - prev_sales
        delta_kg_pct = 0.0 if abs(prev_total_kg) <= 1e-9 else delta_kg / prev_total_kg * 100.0
        delta_sales_pct = 0.0 if abs(prev_sales) <= 1e-9 else delta_sales / prev_sales * 100.0
        self.totals_table_igsa.setSpan(0, 0, 1, 2)
        values = {
            2: (self._fmt_num(prev_kg), float(prev_kg or 0.0)),
            3: (self._fmt_num(prev_sc), float(prev_sc or 0.0)),
            4: (self._fmt_money(prev_sales), float(prev_sales or 0.0)),
            5: (self._fmt_num(curr_kg), float(curr_kg or 0.0)),
            6: (self._fmt_num(curr_sc), float(curr_sc or 0.0)),
            7: (self._fmt_money(curr_sales), float(curr_sales or 0.0)),
            8: (self._fmt_num(delta_kg), float(delta_kg or 0.0)),
            9: (self._fmt_pct(delta_kg_pct), float(delta_kg_pct or 0.0)),
            10: (self._fmt_money(delta_sales), float(delta_sales or 0.0)),
            11: (self._fmt_pct(delta_sales_pct), float(delta_sales_pct or 0.0)),
        }
        total_label = QLabel("TOTAL")
        total_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        total_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        total_font = QFont()
        total_font.setBold(True)
        total_font.setPointSize(12)
        total_font.setFamilies(["Arial Narrow", "Bahnschrift Condensed", "Roboto Condensed", "Segoe UI", "Arial"])
        total_font.setStretch(QFont.Stretch.Condensed)
        total_label.setFont(total_font)
        total_label.setStyleSheet(
            "background-color: #FFFFFF; color: #111827; border: none; border-radius: 0; padding: 2px 6px;"
        )
        self.totals_table_igsa.setCellWidget(0, 0, total_label)
        self.totals_table_igsa.setCurrentCell(-1, -1)
        self.totals_table_igsa.clearSelection()
        self.totals_table_igsa.clearFocus()
        self.totals_table_igsa.viewport().clearFocus()

        for col, (value_text, numeric_value) in values.items():
            item = QTableWidgetItem(value_text)
            item.setBackground(QColor("#FFFFFF"))
            metric = float(numeric_value or 0.0)
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item.setToolTip(value_text)
            if col in {8, 9, 10, 11}:
                if metric > 0:
                    item.setForeground(QColor("#067647"))
                elif metric < 0:
                    item.setForeground(QColor("#B42318"))
                else:
                    item.setForeground(QColor("#111827"))
            else:
                item.setForeground(QColor("#111827"))
            font = item.font()
            font.setBold(True)
            font.setPointSize(12)
            font.setFamilies(["Arial Narrow", "Bahnschrift Condensed", "Roboto Condensed", "Segoe UI", "Arial"])
            font.setStretch(QFont.Stretch.Condensed)
            item.setFont(font)
            self.totals_table_igsa.setItem(0, col, item)

    def _apply_column_widths(self) -> None:
        widths = {
            0: 84,
            2: 95,
            3: 78,
            4: 118,
            5: 95,
            6: 78,
            7: 118,
            8: 95,
            9: 88,
            10: 118,
            11: 84,
        }
        for col, width in widths.items():
            self.sales_table.setColumnWidth(col, width)
            self.group_header.setColumnWidth(col, width)
            self.totals_table.setColumnWidth(col, width)

    def _sync_aux_column_width(self, logical_index: int, _old_size: int, new_size: int) -> None:
        if not hasattr(self, "group_header") or not hasattr(self, "totals_table"):
            return
        self.group_header.setColumnWidth(logical_index, new_size)
        self.totals_table.setColumnWidth(logical_index, new_size)

    def _make_band_label(
        self,
        text: str,
        color: str,
        align: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignCenter,
        bold: bool = True,
        border_color: str = "#000000",
    ) -> QLabel:
        label = QLabel(text)
        label.setAlignment(align)
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        font = QFont()
        font.setBold(bold)
        label.setFont(font)
        label.setStyleSheet(
            f"background-color: {color}; color: #FFFFFF; border: 1px solid {border_color}; border-radius: 0; padding: 0;"
        )
        return label

    def _set_group_item(self, column: int, text: str, color: str, span: int = 1) -> None:
        if span > 1:
            self.group_header.setSpan(0, column, 1, span)
        self.group_header.setCellWidget(0, column, self._make_band_label(text, color))

    def _fill_group_headers(self, year: int) -> None:
        self.group_header.clearSpans()
        self.group_header.clearContents()
        for col in range(12):
            self.group_header.removeCellWidget(0, col)
            label = QLabel("")
            label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            if col in {0, 1}:
                label.setStyleSheet("background-color: transparent; border: none; padding: 0;")
            else:
                label.setStyleSheet("background-color: #F3F6FA; border: 1px solid #000000; border-radius: 0; padding: 0;")
            self.group_header.setCellWidget(0, col, label)
        self._set_group_item(2, str(year - 1), "#3E5064", 3)
        self._set_group_item(5, str(year), "#0F766E", 3)
        self._set_group_item(8, "Diferencias", "#111827", 4)

    def _fill_sales(self, rows: list[SalesComparisonRow], year: int) -> None:
        self._fill_group_headers(year)
        self.sales_table.setSortingEnabled(False)
        self.sales_table.setRowCount(len(rows))
        total_prev_kg = 0.0
        total_prev_sc = 0.0
        total_curr_kg = 0.0
        total_curr_sc = 0.0
        total_prev_sales = 0.0
        total_curr_sales = 0.0

        for idx, row in enumerate(rows):
            total_prev_kg += row.kilos_prev
            total_prev_sc += row.sc_prev
            total_curr_kg += row.kilos_curr
            total_curr_sc += row.sc_curr
            total_prev_sales += row.ventas_prev
            total_curr_sales += row.ventas_curr

            values = [
                row.codigo,
                row.nombre,
                (self._fmt_num(row.kilos_prev), row.kilos_prev),
                (self._fmt_num(row.sc_prev), row.sc_prev),
                (self._fmt_money(row.ventas_prev), row.ventas_prev),
                (self._fmt_num(row.kilos_curr), row.kilos_curr),
                (self._fmt_num(row.sc_curr), row.sc_curr),
                (self._fmt_money(row.ventas_curr), row.ventas_curr),
                (self._fmt_num(row.delta_kg), row.delta_kg),
                (self._fmt_pct(row.delta_kg_pct), row.delta_kg_pct),
                (self._fmt_money(row.delta_ventas), row.delta_ventas),
                (self._fmt_pct(row.delta_ventas_pct), row.delta_ventas_pct),
            ]
            for col, value in enumerate(values):
                if isinstance(value, tuple):
                    item = NumericTableWidgetItem(value[0], value[1])
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    item.setToolTip(value[0])
                    if col in {8, 9, 10, 11}:
                        if value[1] > 0:
                            item.setForeground(QColor("#067647"))
                        elif value[1] < 0:
                            item.setForeground(QColor("#B42318"))
                else:
                    item = QTableWidgetItem(str(value or ""))
                    item.setToolTip(str(value or ""))
                self.sales_table.setItem(idx, col, item)

        self.sales_table.setSortingEnabled(True)
        self._fill_totals_row(total_prev_kg, total_prev_sc, total_prev_sales, total_curr_kg, total_curr_sc, total_curr_sales)

    def _fill_totals_row(
        self,
        prev_kg: float,
        prev_sc: float,
        prev_sales: float,
        curr_kg: float,
        curr_sc: float,
        curr_sales: float,
    ) -> None:
        self.totals_table.clearSpans()
        self.totals_table.clearContents()
        for col in range(12):
            self.totals_table.removeCellWidget(0, col)

        prev_total_kg = prev_kg + prev_sc
        curr_total_kg = curr_kg + curr_sc
        delta_kg = curr_total_kg - prev_total_kg
        delta_sales = curr_sales - prev_sales
        delta_kg_pct = 0.0 if abs(prev_total_kg) <= 1e-9 else delta_kg / prev_total_kg * 100.0
        delta_sales_pct = 0.0 if abs(prev_sales) <= 1e-9 else delta_sales / prev_sales * 100.0
        self.totals_table.setSpan(0, 0, 1, 2)
        self.totals_table.setCellWidget(
            0,
            0,
            self._make_band_label(
                "TOTAL",
                "#FFFFFF",
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                True,
                "#C9D1DC",
            ),
        )
        values = {
            2: (self._fmt_num(prev_kg), float(prev_kg or 0.0)),
            3: (self._fmt_num(prev_sc), float(prev_sc or 0.0)),
            4: (self._fmt_money(prev_sales), float(prev_sales or 0.0)),
            5: (self._fmt_num(curr_kg), float(curr_kg or 0.0)),
            6: (self._fmt_num(curr_sc), float(curr_sc or 0.0)),
            7: (self._fmt_money(curr_sales), float(curr_sales or 0.0)),
            8: (self._fmt_num(delta_kg), float(delta_kg or 0.0)),
            9: (self._fmt_pct(delta_kg_pct), float(delta_kg_pct or 0.0)),
            10: (self._fmt_money(delta_sales), float(delta_sales or 0.0)),
            11: (self._fmt_pct(delta_sales_pct), float(delta_sales_pct or 0.0)),
        }
        total_label = QLabel("TOTAL")
        total_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        total_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        total_font = QFont()
        total_font.setBold(True)
        total_font.setPointSize(12)
        total_font.setFamilies(["Arial Narrow", "Bahnschrift Condensed", "Roboto Condensed", "Segoe UI", "Arial"])
        total_font.setStretch(QFont.Stretch.Condensed)
        total_label.setFont(total_font)
        total_label.setStyleSheet(
            "background-color: #FFFFFF; color: #111827; border: none; border-radius: 0; padding: 2px 6px;"
        )
        self.totals_table.setCellWidget(0, 0, total_label)
        self.totals_table.setCurrentCell(-1, -1)
        self.totals_table.clearSelection()
        self.totals_table.clearFocus()
        self.totals_table.viewport().clearFocus()

        for col, (value_text, numeric_value) in values.items():
            item = QTableWidgetItem(value_text)
            item.setBackground(QColor("#FFFFFF"))
            metric = float(numeric_value or 0.0)
            if col in {8, 9, 10, 11}:
                if metric > 0:
                    item.setForeground(QColor("#067647"))
                elif metric < 0:
                    item.setForeground(QColor("#B42318"))
                else:
                    item.setForeground(QColor("#111827"))
            else:
                item.setForeground(QColor("#111827"))
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item.setToolTip(value_text)
            font = item.font()
            font.setBold(True)
            font.setPointSize(12)
            font.setFamilies(["Arial Narrow", "Bahnschrift Condensed", "Roboto Condensed", "Segoe UI", "Arial"])
            font.setStretch(QFont.Stretch.Condensed)
            item.setFont(font)
            self.totals_table.setItem(0, col, item)

    def _fmt_num(self, value) -> str:
        number = float(value or 0.0)
        return f"{number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def _fmt_money(self, value) -> str:
        return f"{self._fmt_num(value)} €"

    def _fmt_pct(self, value) -> str:
        return f"{self._fmt_num(value)} %"

