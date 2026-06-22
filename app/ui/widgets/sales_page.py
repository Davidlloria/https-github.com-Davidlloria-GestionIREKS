from __future__ import annotations

from datetime import date

from PySide6.QtCore import QTimer, Qt, QSize, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QStyle,
    QToolButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QToolTip,
    QWidget,
)
try:
    import pyqtgraph as pg
except ModuleNotFoundError:  # pragma: no cover - dependency guard
    pg = None

from app.services.sales_annual_comparison_service import SalesAnnualComparisonService, SalesComparisonRow, SalesMonthlyComparisonPoint
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


class MonthlySalesBarSeriesItem(pg.GraphicsObject if pg is not None else object):
    def __init__(
        self,
        points: list[SalesMonthlyComparisonPoint],
        *,
        prev_color: str,
        prev_edge: str,
        curr_color: str,
        curr_edge: str,
        hover_tooltip,
    ) -> None:
        super().__init__()
        self._points = list(points)
        self._prev_brush = QColor(prev_color)
        self._prev_pen = QPen(QColor(prev_edge))
        self._curr_brush = QColor(curr_color)
        self._curr_pen = QPen(QColor(curr_edge))
        self._hover_tooltip = hover_tooltip
        self._bars: list[dict[str, object]] = []
        self._bounds = QRectF(0.5, 0.0, 12.0, 1.0)
        if pg is not None:
            self.setAcceptHoverEvents(True)
        self._rebuild_geometry()

    def _rebuild_geometry(self) -> None:
        self.prepareGeometryChange()
        self._bars = []
        max_value = max(
            [float(point.kilos_prev or 0.0) for point in self._points] + [float(point.kilos_curr or 0.0) for point in self._points] + [0.0]
        )
        if max_value <= 0:
            max_value = 1.0
        top_padding = max_value * 0.18
        self._bounds = QRectF(0.5, 0.0, 12.0, max_value + top_padding)
        for point in self._points:
            month = int(point.month or 0)
            prev_value = float(point.kilos_prev or 0.0)
            curr_value = float(point.kilos_curr or 0.0)
            prev_rect = QRectF(month - 0.36, 0.0, 0.28, prev_value)
            curr_rect = QRectF(month + 0.08, 0.0, 0.28, curr_value)
            self._bars.append(
                {
                    "month": month,
                    "prev_value": prev_value,
                    "curr_value": curr_value,
                    "prev_rect": prev_rect,
                    "curr_rect": curr_rect,
                }
            )

    def boundingRect(self) -> QRectF:  # type: ignore[override]
        return self._bounds

    def paint(self, painter: QPainter, _option, _widget=None) -> None:  # type: ignore[override]
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        for bar in self._bars:
            prev_rect = bar["prev_rect"]
            curr_rect = bar["curr_rect"]
            prev_value = float(bar["prev_value"])
            curr_value = float(bar["curr_value"])

            if prev_value > 0:
                painter.fillRect(prev_rect, self._prev_brush)
                painter.setPen(self._prev_pen)
                painter.drawRect(prev_rect)
            if curr_value > 0:
                painter.fillRect(curr_rect, self._curr_brush)
                painter.setPen(self._curr_pen)
                painter.drawRect(curr_rect)

    def hoverEvent(self, event) -> None:  # type: ignore[override]
        if pg is None:
            return
        if event.isExit():
            QToolTip.hideText()
            event.accept()
            return
        pos = event.pos()
        for bar in self._bars:
            month = int(bar["month"])
            prev_rect: QRectF = bar["prev_rect"]
            curr_rect: QRectF = bar["curr_rect"]
            prev_value = float(bar["prev_value"])
            curr_value = float(bar["curr_value"])
            if prev_rect.contains(pos) or curr_rect.contains(pos):
                screen_pos = event.screenPos().toPoint()
                text = self._hover_tooltip(month, prev_value, curr_value)
                QToolTip.showText(screen_pos, text)
                event.accept()
                return
        QToolTip.hideText()
        event.ignore()


class MonthlySalesChartWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._title = "Ventas mensuales"
        self._subtitle = ""
        self._points: list[SalesMonthlyComparisonPoint] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        if pg is None:
            placeholder = QLabel("pyqtgraph no esta instalado")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setMinimumSize(760, 360)
            placeholder.setStyleSheet("color: #6B7280; background: #FFFFFF;")
            layout.addWidget(placeholder)
            self._plot = None
        else:
            self._plot = pg.PlotWidget(parent=self)
            self._plot.setBackground("#FFFFFF")
            self._plot.showGrid(x=False, y=True, alpha=0.22)
            self._plot.setMenuEnabled(False)
            self._plot.setMouseEnabled(x=False, y=False)
            self._plot.setAntialiasing(True)
            self._plot.hideButtons()
            plot_item = self._plot.getPlotItem()
            plot_item.layout.setContentsMargins(4, 4, 4, 4)
            plot_item.getAxis("left").setWidth(46)
            plot_item.getAxis("bottom").setHeight(28)
            self._plot.setMinimumSize(640, 300)
            layout.addWidget(self._plot)

    def set_series(self, title: str, subtitle: str, points: list[SalesMonthlyComparisonPoint]) -> None:
        self._title = str(title or "Ventas mensuales").strip() or "Ventas mensuales"
        self._subtitle = str(subtitle or "").strip()
        self._points = list(points or [])
        if self._plot is None:
            return
        self._plot.clear()
        plot_item = self._plot.getPlotItem()
        plot_item.setTitle(f"<span style='font-size:12pt;font-weight:600;color:#111827'>{self._title}</span>")
        plot_item.setLabel("top", "")

        if not self._points:
            plot_item.setLabel("left", "")
            plot_item.showGrid(x=False, y=False)
            text = pg.TextItem("Sin datos mensuales", color="#6B7280", anchor=(0.5, 0.5))
            text.setPos(5.5, 0.0)
            self._plot.addItem(text)
            return

        values = [float(point.kilos_prev or 0.0) for point in self._points] + [float(point.kilos_curr or 0.0) for point in self._points]
        max_value = max(values) if values else 0.0
        if max_value <= 0:
            plot_item.setLabel("left", "")
            plot_item.showGrid(x=False, y=False)
            text = pg.TextItem("Sin ventas mensuales", color="#6B7280", anchor=(0.5, 0.5))
            text.setPos(5.5, 0.0)
            self._plot.addItem(text)
            return

        plot_item.setLabel("left", "<span style='color:#4B5563'>Kg</span>")
        plot_item.showGrid(x=False, y=True, alpha=0.18)
        plot_item.setMenuEnabled(False)

        self._plot.addItem(
            MonthlySalesBarSeriesItem(
                self._points,
                prev_color="#A7B3C5",
                prev_edge="#8B95A7",
                curr_color="#1E6FEA",
                curr_edge="#1A5FCA",
                hover_tooltip=self._build_tooltip,
            )
        )

        value_font = QFont()
        value_font.setPointSize(8)
        for point in self._points:
            if float(point.kilos_prev or 0.0) > 0:
                prev_label = pg.TextItem(f"{float(point.kilos_prev or 0.0):.1f}".replace(".", ","), color="#4B5563", anchor=(0.5, 1.0))
                prev_label.setFont(value_font)
                prev_label.setPos(point.month - 0.22, float(point.kilos_prev or 0.0) + max_value * 0.03)
                self._plot.addItem(prev_label)
            if float(point.kilos_curr or 0.0) > 0:
                curr_label = pg.TextItem(f"{float(point.kilos_curr or 0.0):.1f}".replace(".", ","), color="#4B5563", anchor=(0.5, 1.0))
                curr_label.setFont(value_font)
                curr_label.setPos(point.month + 0.22, float(point.kilos_curr or 0.0) + max_value * 0.03)
                self._plot.addItem(curr_label)

        axis = self._plot.getAxis("bottom")
        axis.setTicks([[(point.month, MONTH_NAMES[point.month - 1][:3]) for point in self._points]])
        axis.setStyle(tickTextOffset=6)
        axis.setPen("#D5DCE8")
        self._plot.getAxis("left").setPen("#D5DCE8")
        y_max = self._nice_step(max_value) * 5
        self._plot.setYRange(0, y_max, padding=0.04)
        self._plot.setXRange(0.5, 12.5, padding=0.02)
        self._plot.showGrid(x=False, y=True, alpha=0.2)

        legend = pg.LegendItem(offset=(16, 16))
        legend.setParentItem(plot_item.vb)
        legend.addItem(pg.PlotDataItem([], [], pen=pg.mkPen("#8B95A7"), symbolBrush="#A7B3C5", symbolSize=8), "Año anterior")
        legend.addItem(pg.PlotDataItem([], [], pen=pg.mkPen("#1A5FCA"), symbolBrush="#1E6FEA", symbolSize=8), "Año actual")

    @staticmethod
    def _build_tooltip(month: int, prev_value: float, curr_value: float) -> str:
        label = MONTH_NAMES[month - 1] if 1 <= month <= 12 else str(month)
        prev_text = f"{prev_value:.1f}".replace(".", ",")
        curr_text = f"{curr_value:.1f}".replace(".", ",")
        return f"{label}\nAño anterior: {prev_text} kg\nAño actual: {curr_text} kg"

    @staticmethod
    def _nice_step(max_value: float) -> float:
        raw = max(float(max_value or 0.0) / 5.0, 1.0)
        for step in (1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0, 200.0, 500.0, 1000.0):
            if raw <= step:
                return step
        return 1000.0


class MonthlySalesDialog(QDialog):
    def __init__(
        self,
        *,
        title: str,
        subtitle: str,
        points: list[SalesMonthlyComparisonPoint],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            self.resize(min(920, max(700, available.width() - 80)), min(520, max(380, available.height() - 120)))
            self.setMinimumSize(min(760, max(640, available.width() - 160)), min(380, max(320, available.height() - 200)))
        else:
            self.resize(820, 420)
            self.setMinimumSize(680, 360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header = QVBoxLayout()
        title_label = QLabel(title)
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #111827;")
        header.addWidget(title_label)
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_font = QFont()
            subtitle_font.setPointSize(9)
            subtitle_label.setFont(subtitle_font)
            subtitle_label.setStyleSheet("color: #6B7280;")
            header.addWidget(subtitle_label)
        layout.addLayout(header)

        chart = MonthlySalesChartWidget(self)
        chart.set_series(title, subtitle, points)
        layout.addWidget(chart, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


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
        self.sales_chart_btn = QToolButton()
        self.sales_chart_btn.setToolTip("Ver gráfico mensual")
        self.sales_chart_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogInfoView))
        self.sales_chart_btn.setIconSize(QSize(14, 14))
        self.sales_chart_btn.setAutoRaise(True)
        self.sales_chart_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sales_chart_btn.setFixedSize(28, 28)
        self.sales_chart_btn.setEnabled(False)
        self.sales_chart_btn.clicked.connect(self._open_selected_monthly_sales_dialog)
        filters_bottom.addWidget(self.sales_chart_btn)
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
        self.sales_table.itemSelectionChanged.connect(self._update_sales_chart_button_state)
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
                    if col == 0:
                        item.setData(Qt.ItemDataRole.UserRole, row.articulo_id)
                    elif col == 1:
                        item.setData(Qt.ItemDataRole.UserRole, row.nombre)
                self.sales_table.setItem(idx, col, item)

        self.sales_table.setSortingEnabled(True)
        self._fill_totals_row(total_prev_kg, total_prev_sc, total_prev_sales, total_curr_kg, total_curr_sc, total_curr_sales)
        self._update_sales_chart_button_state()

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
        self._update_sales_chart_button_state()

    def _selected_sales_row(self) -> tuple[str, str, str] | None:
        row_idx = self.sales_table.currentRow()
        if row_idx < 0:
            return None
        code_item = self.sales_table.item(row_idx, 0)
        name_item = self.sales_table.item(row_idx, 1)
        if code_item is None:
            return None
        articulo_id = str(code_item.data(Qt.ItemDataRole.UserRole) or "").strip()
        if not articulo_id:
            return None
        codigo = str(code_item.text() or "").strip()
        nombre = str((name_item.text() if name_item is not None else "") or "").strip()
        return articulo_id, codigo, nombre

    def _update_sales_chart_button_state(self) -> None:
        self.sales_chart_btn.setEnabled(self._selected_sales_row() is not None and self._current_year() > 0)

    def _open_selected_monthly_sales_dialog(self) -> None:
        row = self._selected_sales_row()
        year = self._current_year()
        if row is None or year <= 0:
            return
        articulo_id, codigo, nombre = row
        points = self.sales_summary_service.listar_ventas_mensuales_ireks_comparativa(
            year=year,
            articulo_id=articulo_id,
            cliente_id=self._current_client_id(),
        )
        subtitle_parts = [part for part in [codigo, nombre, self._current_client_id(), f"{year - 1} vs {year}"] if part]
        dialog = MonthlySalesDialog(
            title=f"Ventas mensuales {year - 1} / {year}",
            subtitle=" | ".join(subtitle_parts),
            points=points,
            parent=self,
        )
        dialog.exec()

    def _fmt_num(self, value) -> str:
        number = float(value or 0.0)
        return f"{number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def _fmt_money(self, value) -> str:
        return f"{self._fmt_num(value)} €"

    def _fmt_pct(self, value) -> str:
        return f"{self._fmt_num(value)} %"

