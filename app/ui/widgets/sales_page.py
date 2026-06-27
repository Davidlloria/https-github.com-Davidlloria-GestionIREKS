from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
import math
from pathlib import Path
import unicodedata

from PySide6.QtCore import QTimer, Qt, QSize
from PySide6.QtGui import QColor, QCursor, QFont, QIcon, QTextDocument, QBrush
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QFormLayout,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QLineEdit,
    QPlainTextEdit,
    QFrame,
    QSizePolicy,
    QPushButton,
    QToolButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QToolTip,
    QWidget,
)
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
try:
    import pyqtgraph as pg
except ModuleNotFoundError:  # pragma: no cover - dependency guard
    pg = None

from app.services.sales_ai_assistant_service import SalesQueryAssistantService
from app.services.sales_annual_comparison_service import (
    SalesAnnualComparisonService,
    SalesComparisonRow,
    SalesDetailRow,
    SalesMonthlyComparisonPoint,
)
from app.services.db_export_service import DbExportService
from app.services.report_export_service import ReportExportService
from app.services.sales_reconciliation_service import SalesReconciliationService
from app.services.settings_sales_import_service import SettingsSalesImportService
from app.core.config import DATA_DIR
from app.core.database import engine


BASE_DIR = Path(__file__).resolve().parents[3]
ALERT_ICON_PATH = BASE_DIR / "assets" / "icons" / "alert.svg"
ARROW_DOWN_ICON_PATH = BASE_DIR / "assets" / "icons" / "arrow-down.svg"
ARROW_UP_ICON_PATH = BASE_DIR / "assets" / "icons" / "arrow-up.svg"
CHART_COLUMN_ICON_PATH = BASE_DIR / "assets" / "icons" / "chart-column.svg"
FILTER_ICON_PATH = BASE_DIR / "assets" / "icons" / "filtro.svg"
SALES_IREKS_ICON_PATH = BASE_DIR / "assets" / "icons" / "chart-no-axes-combined.svg"
CHECK_ICON_PATH = BASE_DIR / "assets" / "icons" / "check.svg"
ERROR_ICON_PATH = BASE_DIR / "assets" / "icons" / "error.svg"
EXPORT_ICON_PATH = BASE_DIR / "assets" / "icons" / "export.svg"
IMPORT_ICON_PATH = BASE_DIR / "assets" / "icons" / "import.svg"
HISTORY_ICON_PATH = BASE_DIR / "assets" / "icons" / "history.svg"
CHART_LINE_ICON_PATH = BASE_DIR / "assets" / "icons" / "chart-line.svg"
PRINTER_ICON_PATH = BASE_DIR / "assets" / "icons" / "printer.svg"
FILE_TEXT_ICON_PATH = BASE_DIR / "assets" / "icons" / "file-text.svg"
SHEET_ICON_PATH = BASE_DIR / "assets" / "icons" / "sheet.svg"
TOOLBOX_ICON_PATH = BASE_DIR / "assets" / "icons" / "toolbox.svg"

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


@dataclass
class SalesExportRow:
    cliente_id: str
    cliente_nombre: str
    articulo_id: str
    codigo: str
    nombre: str
    fabricante_id: str
    familia_id: str
    subfamilia_id: str
    kilos_prev: float
    sc_prev: float
    ventas_prev: float
    kilos_curr: float
    sc_curr: float
    ventas_curr: float
    delta_kg: float
    delta_kg_pct: float
    delta_ventas: float
    delta_ventas_pct: float


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


class MonthlySalesChartWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._title = "Ventas mensuales"
        self._subtitle = ""
        self._points: list[SalesMonthlyComparisonPoint] = []
        self._hover_regions: list[dict[str, float | int | str]] = []
        self._active_bar_key: tuple[int, str] | None = None
        self._tooltip_text = ""
        self._tooltip_global_pos = None
        self._hover_y_margin = 5.0
        self._chart_mode = "bar"
        self._hover_refresh_timer = QTimer(self)
        self._hover_refresh_timer.setInterval(250)
        self._hover_refresh_timer.timeout.connect(self._refresh_hover_tooltip)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        if pg is None:
            placeholder = QLabel("pyqtgraph no esta instalado")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setMinimumSize(520, 260)
            placeholder.setStyleSheet("color: #6B7280; background: #FFFFFF;")
            layout.addWidget(placeholder)
            self._plot = None
        else:
            self._plot = pg.PlotWidget(parent=self)
            self._plot.setBackground("#FFFFFF")
            self._plot.showGrid(x=False, y=True, alpha=0.18)
            self._plot.setMenuEnabled(False)
            self._plot.setMouseEnabled(x=False, y=False)
            self._plot.setAntialiasing(True)
            self._plot.hideButtons()
            self._plot.hideAxis("top")
            self._plot.hideAxis("right")
            plot_item = self._plot.getPlotItem()
            plot_item.layout.setContentsMargins(2, 2, 2, 2)
            plot_item.getAxis("left").setWidth(42)
            plot_item.getAxis("bottom").setHeight(24)
            plot_item.getAxis("left").setStyle(tickTextOffset=4)
            plot_item.getAxis("bottom").setStyle(tickTextOffset=4)
            self._plot.setMinimumSize(560, 260)
            self._plot.scene().sigMouseMoved.connect(self._on_scene_mouse_moved)
            layout.addWidget(self._plot)

    def set_series(self, title: str, subtitle: str, points: list[SalesMonthlyComparisonPoint]) -> None:
        self._title = str(title or "Ventas mensuales").strip() or "Ventas mensuales"
        self._subtitle = str(subtitle or "").strip()
        self._points = list(points or [])
        self._hover_regions = []
        self._active_bar_key = None
        self._tooltip_text = ""
        self._tooltip_global_pos = None
        self._hover_refresh_timer.stop()
        if self._plot is None:
            return
        self._plot.clear()
        plot_item = self._plot.getPlotItem()
        plot_item.setTitle("")
        plot_item.showAxis("top", False)
        plot_item.showAxis("right", False)

        if not self._points:
            plot_item.setLabel("left", "")
            plot_item.setLabel("bottom", "")
            plot_item.showGrid(x=False, y=False)
            text = pg.TextItem("Sin datos mensuales", color="#6B7280", anchor=(0.5, 0.5))
            text.setPos(5.5, 0.0)
            self._plot.addItem(text)
            return

        values = [float(point.kilos_prev or 0.0) for point in self._points] + [float(point.kilos_curr or 0.0) for point in self._points]
        max_value = max(values) if values else 0.0
        self._hover_y_margin = max(max_value * 0.035, 5.0)
        if max_value <= 0:
            plot_item.setLabel("left", "")
            plot_item.setLabel("bottom", "")
            plot_item.showGrid(x=False, y=False)
            text = pg.TextItem("Sin ventas mensuales", color="#6B7280", anchor=(0.5, 0.5))
            text.setPos(5.5, 0.0)
            self._plot.addItem(text)
            return

        plot_item.setLabel("left", "<span style='color:#4B5563'>Kg</span>")
        plot_item.setLabel("bottom", "")
        plot_item.showGrid(x=False, y=True, alpha=0.18)
        plot_item.setMenuEnabled(False)

        value_font = QFont()
        value_font.setPointSize(8)
        if self._chart_mode == "line":
            prev_x = [int(point.month or 0) for point in self._points]
            prev_y = [float(point.kilos_prev or 0.0) for point in self._points]
            curr_x = [int(point.month or 0) for point in self._points]
            curr_y = [float(point.kilos_curr or 0.0) for point in self._points]
            self._plot.addItem(
                pg.PlotDataItem(
                    prev_x,
                    prev_y,
                    pen=pg.mkPen("#8B95A7", width=2.4),
                    symbol="o",
                    symbolBrush="#A7B3C5",
                    symbolPen="#7B8794",
                    symbolSize=8,
                )
            )
            self._plot.addItem(
                pg.PlotDataItem(
                    curr_x,
                    curr_y,
                    pen=pg.mkPen("#1A5FCA", width=2.4),
                    symbol="o",
                    symbolBrush="#1E6FEA",
                    symbolPen="#1A5FCA",
                    symbolSize=8,
                )
            )
            for point in self._points:
                month = int(point.month or 0)
                prev_value = float(point.kilos_prev or 0.0)
                curr_value = float(point.kilos_curr or 0.0)
                self._hover_regions.append(
                    {
                        "month": month,
                        "series": "prev",
                        "x1": month - 0.16,
                        "x2": month + 0.16,
                        "y1": prev_value - self._hover_y_margin,
                        "y2": prev_value + self._hover_y_margin,
                        "value": prev_value,
                    }
                )
                self._hover_regions.append(
                    {
                        "month": month,
                        "series": "curr",
                        "x1": month - 0.16,
                        "x2": month + 0.16,
                        "y1": curr_value - self._hover_y_margin,
                        "y2": curr_value + self._hover_y_margin,
                        "value": curr_value,
                    }
                )
                if prev_value > 0:
                    prev_label = pg.TextItem(f"{prev_value:.1f}".replace(".", ","), color="#4B5563", anchor=(0.5, 1.0))
                    prev_label.setFont(value_font)
                    prev_label.setPos(month, prev_value + max_value * 0.04)
                    self._plot.addItem(prev_label)
                if curr_value > 0:
                    curr_label = pg.TextItem(f"{curr_value:.1f}".replace(".", ","), color="#4B5563", anchor=(0.5, 1.0))
                    curr_label.setFont(value_font)
                    curr_label.setPos(month, curr_value + max_value * 0.04)
                    self._plot.addItem(curr_label)
        else:
            prev_x = []
            prev_h = []
            curr_x = []
            curr_h = []
            bar_width = 0.28
            prev_offset = -0.18
            curr_offset = 0.18
            for point in self._points:
                month = int(point.month or 0)
                prev_value = float(point.kilos_prev or 0.0)
                curr_value = float(point.kilos_curr or 0.0)
                if prev_value > 0:
                    prev_x.append(month + prev_offset)
                    prev_h.append(prev_value)
                    self._hover_regions.append(
                        {
                            "month": month,
                            "series": "prev",
                            "x1": month + prev_offset - bar_width / 2.0,
                            "x2": month + prev_offset + bar_width / 2.0,
                            "y1": 0.0,
                            "y2": prev_value,
                            "value": prev_value,
                        }
                    )
                if curr_value > 0:
                    curr_x.append(month + curr_offset)
                    curr_h.append(curr_value)
                    self._hover_regions.append(
                        {
                            "month": month,
                            "series": "curr",
                            "x1": month + curr_offset - bar_width / 2.0,
                            "x2": month + curr_offset + bar_width / 2.0,
                            "y1": 0.0,
                            "y2": curr_value,
                            "value": curr_value,
                        }
                    )

            if prev_x:
                self._plot.addItem(
                    pg.BarGraphItem(
                        x=prev_x,
                        height=prev_h,
                        width=bar_width,
                        brush=QColor("#A7B3C5"),
                        pen=QColor("#8B95A7"),
                    )
                )
            if curr_x:
                self._plot.addItem(
                    pg.BarGraphItem(
                        x=curr_x,
                        height=curr_h,
                        width=bar_width,
                        brush=QColor("#1E6FEA"),
                        pen=QColor("#1A5FCA"),
                    )
                )

            for point in self._points:
                if float(point.kilos_prev or 0.0) > 0:
                    prev_label = pg.TextItem(f"{float(point.kilos_prev or 0.0):.1f}".replace(".", ","), color="#4B5563", anchor=(0.5, 1.0))
                    prev_label.setFont(value_font)
                    prev_label.setPos(point.month + prev_offset, float(point.kilos_prev or 0.0) + max_value * 0.04)
                    self._plot.addItem(prev_label)
                if float(point.kilos_curr or 0.0) > 0:
                    curr_label = pg.TextItem(f"{float(point.kilos_curr or 0.0):.1f}".replace(".", ","), color="#4B5563", anchor=(0.5, 1.0))
                    curr_label.setFont(value_font)
                    curr_label.setPos(point.month + curr_offset, float(point.kilos_curr or 0.0) + max_value * 0.04)
                    self._plot.addItem(curr_label)

        axis = self._plot.getAxis("bottom")
        axis.setTicks([[(point.month, MONTH_NAMES[point.month - 1][:3]) for point in self._points]])
        axis.setStyle(tickTextOffset=6)
        axis.setPen("#D5DCE8")
        self._plot.getAxis("left").setPen("#D5DCE8")
        y_max = self._nice_step(max_value) * 5
        self._plot.setYRange(0, y_max, padding=0.08)
        self._plot.setXRange(0.5, 12.5, padding=0.03)
        self._plot.showGrid(x=False, y=True, alpha=0.18)

        legend = pg.LegendItem(offset=(16, 16))
        legend.setParentItem(plot_item.vb)
        legend.setLabelTextColor("#4B5563")
        legend.setBrush(QColor(255, 255, 255, 220))
        legend.setPen(QColor("#D5DCE8"))
        legend.addItem(
            pg.PlotDataItem(
                [],
                [],
                pen=pg.mkPen("#475569", width=3),
                symbol="o",
                symbolBrush="#475569",
                symbolPen="#475569",
                symbolSize=10,
            ),
            "Año anterior",
        )
        legend.addItem(
            pg.PlotDataItem(
                [],
                [],
                pen=pg.mkPen("#2563EB", width=3),
                symbol="o",
                symbolBrush="#2563EB",
                symbolPen="#2563EB",
                symbolSize=10,
            ),
            "Año actual",
        )

    @staticmethod
    def _build_tooltip(month: int, prev_value: float, curr_value: float) -> str:
        label = MONTH_NAMES[month - 1] if 1 <= month <= 12 else str(month)
        prev_text = f"{prev_value:.1f}".replace(".", ",")
        curr_text = f"{curr_value:.1f}".replace(".", ",")
        return f"{label}\nAño anterior: {prev_text} kg\nAño actual: {curr_text} kg"

    def _on_scene_mouse_moved(self, pos) -> None:
        if self._plot is None or not self._hover_regions:
            self._clear_hover_tooltip()
            return
        view_box = self._plot.getPlotItem().vb
        if view_box.sceneBoundingRect().contains(pos):
            mouse_point = view_box.mapSceneToView(pos)
            x_pos = float(mouse_point.x())
            y_pos = float(mouse_point.y())
            bar = self._find_bar_at_pos(x_pos, y_pos)
            if bar is None and self._active_bar_key is not None:
                bar = self._find_bar_at_pos(x_pos, y_pos, key=self._active_bar_key, expanded=True)
            if bar is not None:
                self._show_bar_tooltip(bar, pos)
                return
        self._clear_hover_tooltip()

    def _find_bar_at_pos(self, x_pos: float, y_pos: float, key: tuple[int, str] | None = None, expanded: bool = False):
        x_margin = 0.12 if expanded else 0.02
        y_margin = self._hover_y_margin if expanded else 0.0
        for bar in self._hover_regions:
            month = int(bar["month"])
            series = str(bar["series"])
            bar_key = (month, series)
            if key is not None and bar_key != key:
                continue
            x1 = float(bar["x1"]) - x_margin
            x2 = float(bar["x2"]) + x_margin
            y1 = float(bar["y1"]) - y_margin
            y2 = float(bar["y2"]) + y_margin
            if x1 <= x_pos <= x2 and y1 <= y_pos <= y2:
                return bar
        return None

    def _show_bar_tooltip(self, bar, pos) -> None:
        month = int(bar["month"])
        series = str(bar["series"])
        value = float(bar["value"])
        prev_value = value if series == "prev" else self._value_for_month(month, "prev")
        curr_value = value if series == "curr" else self._value_for_month(month, "curr")
        self._active_bar_key = (month, series)
        self._tooltip_text = self._build_tooltip(month, prev_value, curr_value)
        scene_pos = self._plot.mapFromScene(pos)
        if hasattr(scene_pos, "toPoint"):
            scene_pos = scene_pos.toPoint()
        self._tooltip_global_pos = self._plot.mapToGlobal(scene_pos)
        self._hover_refresh_timer.start()
        QToolTip.showText(
            self._tooltip_global_pos,
            self._tooltip_text,
            self._plot,
            self._plot.rect(),
            10000,
        )

    def _refresh_hover_tooltip(self) -> None:
        if self._plot is None or self._active_bar_key is None:
            return
        if not self._tooltip_text or self._tooltip_global_pos is None:
            return
        QToolTip.showText(
            self._tooltip_global_pos,
            self._tooltip_text,
            self._plot,
            self._plot.rect(),
            10000,
        )

    def _clear_hover_tooltip(self) -> None:
        self._active_bar_key = None
        self._tooltip_text = ""
        self._tooltip_global_pos = None
        self._hover_refresh_timer.stop()
        QToolTip.hideText()

    def set_chart_mode(self, chart_mode: str) -> None:
        normalized = str(chart_mode or "").strip().lower()
        if normalized not in {"bar", "line"}:
            normalized = "bar"
        if normalized == self._chart_mode:
            return
        self._chart_mode = normalized
        if self._points:
            self.set_series(self._title, self._subtitle, self._points)

    def chart_mode(self) -> str:
        return self._chart_mode

    def _value_for_month(self, month: int, series: str) -> float:
        for point in self._points:
            if int(point.month or 0) != month:
                continue
            if series == "prev":
                return float(point.kilos_prev or 0.0)
            return float(point.kilos_curr or 0.0)
        return 0.0

    @staticmethod
    def _nice_step(max_value: float) -> float:
        raw = max(float(max_value or 0.0) / 5.0, 1.0)
        magnitude = 10.0 ** max(0, int(math.floor(math.log10(raw))))
        for factor in (1.0, 2.0, 2.5, 5.0, 10.0):
            step = magnitude * factor
            if raw <= step:
                return step
        return magnitude * 10.0


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
        self._chart_mode = "bar"
        self.setWindowTitle(title)
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            self.resize(min(880, max(680, available.width() - 64)), min(500, max(360, available.height() - 96)))
            self.setMinimumSize(min(700, max(600, available.width() - 180)), min(340, max(300, available.height() - 220)))
        else:
            self.resize(780, 420)
            self.setMinimumSize(640, 320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

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

        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(8)

        self.chart_mode_btn = QToolButton()
        self.chart_mode_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chart_mode_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.chart_mode_btn.setIconSize(QSize(18, 18))
        self.chart_mode_btn.setFixedSize(40, 36)
        self.chart_mode_btn.setStyleSheet(
            "QToolButton {"
            "background-color: #FDE68A;"
            "border: 1px solid #F59E0B;"
            "border-radius: 8px;"
            "}"
            "QToolButton:hover { background-color: #FCD34D; }"
            "QToolButton:pressed { background-color: #FBBF24; }"
        )
        self.chart_mode_btn.clicked.connect(lambda: self._toggle_chart_mode(chart))
        bottom_row.addWidget(self.chart_mode_btn)

        bottom_row.addStretch(1)

        close_btn = QPushButton("Close")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFixedSize(88, 36)
        close_btn.clicked.connect(self.reject)
        bottom_row.addWidget(close_btn)
        layout.addLayout(bottom_row)
        self._sync_chart_mode_button(chart)

    def _sync_chart_mode_button(self, chart: MonthlySalesChartWidget) -> None:
        is_bar = chart.chart_mode() == "bar"
        self.chart_mode_btn.setIcon(QIcon(str(CHART_COLUMN_ICON_PATH if is_bar else CHART_LINE_ICON_PATH)))
        self.chart_mode_btn.setToolTip("Cambiar a gráfico de líneas" if is_bar else "Cambiar a gráfico de barras")

    def _toggle_chart_mode(self, chart: MonthlySalesChartWidget) -> None:
        next_mode = "line" if chart.chart_mode() == "bar" else "bar"
        chart.set_chart_mode(next_mode)
        self._sync_chart_mode_button(chart)


class SalesAnalysisDialog(QDialog):
    def __init__(
        self,
        *,
        title: str,
        defaults: dict[str, object],
        sales_service: SalesAnnualComparisonService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._defaults = dict(defaults or {})
        self._assistant = SalesQueryAssistantService(sales_service=sales_service)
        self._report_export_service = ReportExportService()
        self.setWindowTitle(title)
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            self.resize(min(920, max(760, available.width() - 120)), min(700, max(520, available.height() - 140)))
            self.setMinimumSize(min(780, max(680, available.width() - 220)), min(560, max(420, available.height() - 260)))
        else:
            self.resize(860, 620)
            self.setMinimumSize(720, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title_label = QLabel("Análisis de ventas con ChatGPT")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #111827;")
        layout.addWidget(title_label)

        context_label = QLabel("Escribe la consulta y pulsa Consultar. La respuesta aparecerá debajo.")
        context_label.setWordWrap(True)
        context_label.setStyleSheet("color: #6B7280;")
        layout.addWidget(context_label)

        question_label = QLabel("Consulta")
        question_label.setStyleSheet("color: #374151; font-weight: 600;")
        layout.addWidget(question_label)

        self.question_edit = QPlainTextEdit()
        self.question_edit.setPlaceholderText("Ejemplo: resume los productos con mayor crecimiento y detecta caídas relevantes.")
        self.question_edit.setFixedHeight(120)
        layout.addWidget(self.question_edit)

        response_label = QLabel("Respuesta")
        response_label.setStyleSheet("color: #374151; font-weight: 600;")
        layout.addWidget(response_label)

        self.response_edit = QPlainTextEdit()
        self.response_edit.setReadOnly(True)
        self.response_edit.setPlaceholderText("La respuesta de ChatGPT aparecerá aquí.")
        layout.addWidget(self.response_edit, 1)

        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(8)

        self.consult_btn = QPushButton("Consultar")
        self.consult_btn.setProperty("btnRole", "warning")
        self.consult_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.consult_btn.clicked.connect(self._consult)
        bottom_row.addWidget(self.consult_btn)

        bottom_row.addStretch(1)

        center_actions = QWidget()
        center_actions_layout = QHBoxLayout(center_actions)
        center_actions_layout.setContentsMargins(0, 0, 0, 0)
        center_actions_layout.setSpacing(8)

        self.print_btn = QPushButton("Imprimir")
        self.print_btn.setProperty("btnRole", "secondary")
        self.print_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.print_btn.clicked.connect(self._print_response)
        center_actions_layout.addWidget(self.print_btn)

        self.export_excel_btn = QPushButton("Excel")
        self.export_excel_btn.setProperty("btnRole", "secondary")
        self.export_excel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_excel_btn.clicked.connect(self._export_response_excel)
        center_actions_layout.addWidget(self.export_excel_btn)

        self.export_pdf_btn = QPushButton("PDF")
        self.export_pdf_btn.setProperty("btnRole", "secondary")
        self.export_pdf_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_pdf_btn.clicked.connect(self._export_response_pdf)
        center_actions_layout.addWidget(self.export_pdf_btn)

        bottom_row.addWidget(center_actions)

        bottom_row.addStretch(1)

        close_btn = QPushButton("Cerrar")
        close_btn.setProperty("btnRole", "danger")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        bottom_row.addWidget(close_btn)
        layout.addLayout(bottom_row)

    def _consult(self) -> None:
        question = str(self.question_edit.toPlainText() or "").strip()
        if not question:
            QMessageBox.warning(self, "Análisis de ventas", "Escribe una consulta antes de consultar a ChatGPT.")
            return
        self.consult_btn.setEnabled(False)
        self.response_edit.setPlainText("Consultando ChatGPT...")
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            # The analysis query must not inherit the visible sales-page filters.
            result = self._assistant.answer(question, {})
        finally:
            QApplication.restoreOverrideCursor()
            self.consult_btn.setEnabled(True)
        output = result.text.strip() if result.ok else result.message.strip()
        if not output:
            output = "Sin respuesta."
        self.response_edit.setPlainText(output)

    def _response_text(self) -> str:
        return str(self.response_edit.toPlainText() or "").strip()

    def _response_lines(self) -> list[str]:
        text = self._response_text()
        if not text:
            return []
        return [line.rstrip() for line in text.splitlines() if line.strip()]

    def _export_response_excel(self) -> None:
        lines = self._response_lines()
        if not lines:
            QMessageBox.warning(self, "Análisis de ventas", "No hay respuesta para exportar.")
            return
        default = str(self._report_export_service.default_path(self.windowTitle(), "xlsx", folder="sales_analysis"))
        path, _ = QFileDialog.getSaveFileName(self, "Exportar respuesta a Excel", default, "Excel (*.xlsx)")
        if not path:
            return
        out = self._report_export_service.export_excel(path, self.windowTitle(), ["Respuesta"], [[line] for line in lines], sheet_title="Analisis ventas")
        QMessageBox.information(self, "Análisis de ventas", f"Excel exportado:\n{out}")

    def _export_response_pdf(self) -> None:
        lines = self._response_lines()
        if not lines:
            QMessageBox.warning(self, "Análisis de ventas", "No hay respuesta para exportar.")
            return
        default = str(self._report_export_service.default_path(self.windowTitle(), "pdf", folder="sales_analysis"))
        path, _ = QFileDialog.getSaveFileName(self, "Exportar respuesta a PDF", default, "PDF (*.pdf)")
        if not path:
            return
        out = self._report_export_service.export_pdf(path, self.windowTitle(), ["Respuesta"], [[line] for line in lines])
        QMessageBox.information(self, "Análisis de ventas", f"PDF exportado:\n{out}")

    def _print_response(self) -> None:
        text = self._response_text()
        if not text:
            QMessageBox.warning(self, "Análisis de ventas", "No hay respuesta para imprimir.")
            return
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageOrientation(QPrinter.Orientation.Portrait)
        dialog = QPrintDialog(printer, self)
        if dialog.exec() != QPrintDialog.DialogCode.Accepted:
            return
        document = QTextDocument()
        document.setPlainText(text)
        document.print_(printer)


class SalesExcelExportDialog(QDialog):
    def __init__(self, source_label: str, *, client_groupable: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Exportar ventas a Excel - {source_label}")
        self.setModal(True)
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("Configurar exportación")
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        group_box = QWidget()
        group_layout = QVBoxLayout(group_box)
        group_layout.setContentsMargins(0, 0, 0, 0)
        group_layout.setSpacing(8)

        group_hint = QLabel("Selecciona una o varias agrupaciones. Se aplican en cascada, no se sustituyen.")
        group_hint.setWordWrap(True)
        group_hint.setStyleSheet("color: #6B7280;")
        group_layout.addWidget(group_hint)

        self.group_checks: list[tuple[str, QCheckBox]] = []

        def add_group_check(label: str, key: str, checked: bool = False, enabled: bool = True, tooltip: str = "") -> None:
            check = QCheckBox(label)
            check.setChecked(checked)
            check.setEnabled(enabled)
            if tooltip:
                check.setToolTip(tooltip)
            self.group_checks.append((key, check))
            group_layout.addWidget(check)

        add_group_check("Mes", "month", checked=True)
        add_group_check(
            "Cliente",
            "client",
            checked=False,
            enabled=client_groupable,
            tooltip="Solo disponible cuando el filtro Cliente está en Todos.",
        )
        add_group_check("Fabricante", "manufacturer", checked=False)
        add_group_check("Familia", "family", checked=False)
        add_group_check("Subfamilia", "subfamily", checked=False)

        layout.addWidget(group_box)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Código", "codigo")
        self.sort_combo.addItem("Producto", "nombre")
        self.sort_combo.addItem("Kilos anterior", "kilos_prev")
        self.sort_combo.addItem("S/C anterior", "sc_prev")
        self.sort_combo.addItem("Ventas anterior", "ventas_prev")
        self.sort_combo.addItem("Kilos actual", "kilos_curr")
        self.sort_combo.addItem("S/C actual", "sc_curr")
        self.sort_combo.addItem("Ventas actual", "ventas_curr")
        self.sort_combo.addItem("Delta kg", "delta_kg")
        self.sort_combo.addItem("Delta kg %", "delta_kg_pct")
        self.sort_combo.addItem("Delta €", "delta_ventas")
        self.sort_combo.addItem("Delta € %", "delta_ventas_pct")
        self.sort_combo.setCurrentIndex(self.sort_combo.findData("ventas_curr"))
        form.addRow("Ordenar por", self.sort_combo)

        self.direction_combo = QComboBox()
        self.direction_combo.addItem("Ascendente", "asc")
        self.direction_combo.addItem("Descendente", "desc")
        self.direction_combo.setCurrentIndex(self.direction_combo.findData("desc"))
        form.addRow("Dirección", self.direction_combo)

        self.subtotals_check = QCheckBox("Incluir subtotales por grupo")
        self.subtotals_check.setChecked(True)
        form.addRow("", self.subtotals_check)

        layout.addLayout(form)

        hint = QLabel(
            "Si eliges Mes, se exportan los meses hasta el filtro seleccionado. "
            "Con Acumulado activado, cada mes usa el acumulado correspondiente."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #6B7280;")
        layout.addWidget(hint)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setDefault(True)
            ok_button.setAutoDefault(True)
        layout.addWidget(buttons)

        note = QLabel("Cliente solo aparece si el filtro Cliente está en Todos.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #6B7280;")
        layout.addWidget(note)

    def export_options(self) -> dict[str, object]:
        return {
            "group_levels": [key for key, check in self.group_checks if check.isEnabled() and check.isChecked()],
            "sort_by": str(self.sort_combo.currentData() or "ventas_curr"),
            "direction": str(self.direction_combo.currentData() or "desc"),
            "subtotals": bool(self.subtotals_check.isChecked()),
        }


@dataclass(frozen=True)
class SalesClientSelectionRow:
    cliente_id: str
    cliente_nombre: str
    cliente_tipo: str
    search_text: str


class SalesClientSelectDialog(QDialog):
    def __init__(
        self,
        clients: list[SalesClientSelectionRow],
        *,
        selected_client_id: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Seleccionar cliente")
        self.setModal(True)
        self.resize(760, 560)
        self.setMinimumSize(680, 480)
        self._clients = clients
        self._selected_client_id = str(selected_client_id or "").strip()
        self._selected_client_name = ""
        self._build_ui()
        self._refresh_table()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("Seleccionar cliente")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        hint = QLabel("Escribe una ocurrencia para filtrar la lista. Haz doble clic sobre un cliente para seleccionarlo.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #6B7280;")
        layout.addWidget(hint)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filtrar por nombre, código o fiscal...")
        self.search_edit.textChanged.connect(self._refresh_table)
        layout.addWidget(self.search_edit)

        self.clients_table = QTableWidget(0, 1)
        self.clients_table.setHorizontalHeaderLabels(["Cliente"])
        self.clients_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.clients_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.clients_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.clients_table.verticalHeader().setVisible(False)
        self.clients_table.setAlternatingRowColors(True)
        self.clients_table.setSortingEnabled(False)
        self.clients_table.cellDoubleClicked.connect(self._accept_row)
        header = self.clients_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.clients_table, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Seleccionar")
        buttons.accepted.connect(self._accept_selected)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _normalize(self, text: str) -> str:
        cleaned = unicodedata.normalize("NFKD", str(text or ""))
        return "".join(ch for ch in cleaned if not unicodedata.combining(ch)).casefold().strip()

    def _refresh_table(self) -> None:
        needle = self._normalize(self.search_edit.text())
        filtered: list[SalesClientSelectionRow] = []
        for client in self._clients:
            if not needle or needle in client.search_text:
                filtered.append(client)

        self.clients_table.setRowCount(len(filtered))
        match_row = -1
        for row_idx, client in enumerate(filtered):
            name_item = QTableWidgetItem(client.cliente_nombre)
            name_item.setToolTip(client.cliente_nombre)
            name_item.setData(Qt.ItemDataRole.UserRole, client.cliente_id)
            name_item.setData(Qt.ItemDataRole.UserRole + 1, client.cliente_nombre)
            name_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.clients_table.setItem(row_idx, 0, name_item)
            if client.cliente_id == self._selected_client_id:
                match_row = row_idx

        if match_row >= 0:
            self.clients_table.selectRow(match_row)
            self.clients_table.scrollToItem(self.clients_table.item(match_row, 0))
        self.clients_table.resizeRowsToContents()

    def _accept_row(self, row: int, _column: int) -> None:
        item = self.clients_table.item(row, 0)
        if item is None:
            return
        self._selected_client_id = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
        self._selected_client_name = str(item.data(Qt.ItemDataRole.UserRole + 1) or item.text() or "").strip()
        if not self._selected_client_id:
            return
        self.accept()

    def _accept_selected(self) -> None:
        current_row = self.clients_table.currentRow()
        if current_row < 0:
            selected_rows = self.clients_table.selectionModel().selectedRows() if self.clients_table.selectionModel() else []
            if not selected_rows:
                return
            current_row = int(selected_rows[0].row())
        self._accept_row(current_row, 0)

    def selected_client(self) -> tuple[str, str]:
        return self._selected_client_id, self._selected_client_name


@dataclass(frozen=True)
class SalesToolsHistoryRow:
    created_at: str
    action: str
    detail: str
    status: str
    message: str


class SalesToolsDialog(QDialog):
    def __init__(
        self,
        *,
        mode: str = "ireks",
        on_import_completed=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._mode = mode if mode in {"ireks", "clientes"} else "ireks"
        self.setWindowTitle(self._dialog_title())
        self.setModal(True)
        self.resize(980, 620)
        self.setMinimumSize(900, 560)
        self._on_import_completed = on_import_completed
        self._export_service = DbExportService()
        self._import_service = SettingsSalesImportService()
        self._sales_reconciliation_service = SalesReconciliationService()
        self._history_limit = 40
        self._build_ui()
        self._refresh_history()

    def _dialog_title(self) -> str:
        if self._mode == "clientes":
            return "Herramienta de ventas - clientes"
        return "Herramientas de ventas - IREKS"

    def _subtitle_text(self) -> str:
        if self._mode == "clientes":
            return "Acceso rápido a importación e histórico de ventas clientes."
        return "Acceso rápido a exportación, importación e histórico de IREKS."

    def _export_card_title(self) -> str:
        if self._mode == "clientes":
            return "Ventas clientes"
        return "Ventas IREKS"

    def _export_card_description(self) -> str:
        if self._mode == "clientes":
            return "Gestión de ventas clientes."
        return "Gestiona exportación e importación de ventas IREKS."

    def _history_title(self) -> str:
        if self._mode == "clientes":
            return "Histórico clientes"
        return "Histórico IREKS"

    def _history_description(self) -> str:
        if self._mode == "clientes":
            return "Últimas operaciones de importación de ventas clientes."
        return "Últimas operaciones de exportación e importación."

    def _build_ui(self) -> None:
        self.setObjectName("salesToolsDialog")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        title = QLabel(self._dialog_title())
        title.setProperty("role", "pageTitle")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #14213D;")
        layout.addWidget(title)

        subtitle = QLabel(self._subtitle_text())
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #4B5F7A; font-size: 12px;")
        layout.addWidget(subtitle)

        export_card = QFrame()
        export_card.setObjectName("salesToolsCard")
        export_layout = QHBoxLayout(export_card)
        export_layout.setContentsMargins(14, 14, 14, 14)
        export_layout.setSpacing(14)

        export_left = QHBoxLayout()
        export_left.setSpacing(12)
        export_icon = self._make_icon_label(SALES_IREKS_ICON_PATH, "#EAF2FF")
        export_left.addWidget(export_icon, 0, Qt.AlignmentFlag.AlignTop)

        export_text = QVBoxLayout()
        export_text.setSpacing(4)
        export_title = QLabel(self._export_card_title())
        export_title.setStyleSheet("font-size: 22px; font-weight: 700; color: #14213D;")
        export_text.addWidget(export_title)
        export_desc = QLabel(self._export_card_description())
        export_desc.setWordWrap(True)
        export_desc.setStyleSheet("font-size: 13px; color: #4B5F7A;")
        export_text.addWidget(export_desc)
        export_text.addStretch(1)
        export_left.addLayout(export_text, 1)
        export_layout.addLayout(export_left, 1)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        self.export_btn = self._make_action_button(
            "Exportar",
            EXPORT_ICON_PATH,
            background="#E5EEFF",
            border="#AFC8F7",
            foreground="#214EAA",
        )
        if self._mode == "ireks":
            self.export_btn.clicked.connect(self._export_ireks_sales)
        else:
            self.export_btn.setEnabled(False)
            self.export_btn.setToolTip("Exportación pendiente.")
        button_row.addWidget(self.export_btn)

        self.import_btn = self._make_action_button(
            "Importar",
            IMPORT_ICON_PATH,
            background="#E6F7E9",
            border="#AAD9B4",
            foreground="#1D7D4D",
        )
        self.import_btn.clicked.connect(self._import_ireks_sales)
        button_row.addWidget(self.import_btn)
        export_layout.addLayout(button_row)
        layout.addWidget(export_card)

        history_card = QFrame()
        history_card.setObjectName("salesToolsCard")
        history_layout = QVBoxLayout(history_card)
        history_layout.setContentsMargins(14, 14, 14, 14)
        history_layout.setSpacing(10)

        history_header = QHBoxLayout()
        history_header.setSpacing(10)
        history_icon = self._make_icon_label(HISTORY_ICON_PATH, "#EFE9FF")
        history_header.addWidget(history_icon, 0, Qt.AlignmentFlag.AlignTop)

        header_text = QVBoxLayout()
        header_text.setSpacing(3)
        header_title = QLabel(self._history_title())
        header_title.setStyleSheet("font-size: 20px; font-weight: 700; color: #14213D;")
        header_text.addWidget(header_title)
        header_desc = QLabel(self._history_description())
        header_desc.setWordWrap(True)
        header_desc.setStyleSheet("font-size: 12px; color: #5E708A;")
        header_text.addWidget(header_desc)
        history_header.addLayout(header_text, 1)

        history_filter_panel = QHBoxLayout()
        history_filter_panel.setSpacing(6)
        filter_icon = self._make_small_icon_label(FILTER_ICON_PATH, "#EEF2FF")
        history_filter_panel.addWidget(filter_icon)
        self.history_filter_combo = QComboBox()
        self.history_filter_combo.addItem("Todos", "all")
        self.history_filter_combo.addItem("Exportaciones", "export")
        self.history_filter_combo.addItem("Importaciones", "import")
        self.history_filter_combo.currentIndexChanged.connect(lambda *_: self._refresh_history())
        self.history_filter_combo.setMinimumWidth(190)
        self.history_filter_combo.setStyleSheet(
            """
            QComboBox {
                background: #FFFFFF;
                border: 1px solid #D7E0EC;
                border-radius: 10px;
                padding: 8px 12px;
                color: #14213D;
                min-height: 36px;
            }
            QComboBox::drop-down {
                border: none;
                width: 26px;
            }
            """
        )
        history_filter_panel.addWidget(self.history_filter_combo)
        history_header.addLayout(history_filter_panel, 0)
        history_layout.addLayout(history_header)

        self.history_table = QTableWidget(0, 4)
        self.history_table.setObjectName("salesToolsHistoryTable")
        self.history_table.setHorizontalHeaderLabels(["Fecha", "Acción", "Detalle", "Estado"])
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setShowGrid(False)
        self.history_table.setWordWrap(False)
        self.history_table.setFrameShape(QFrame.Shape.NoFrame)
        self.history_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.history_table.setStyleSheet(
            """
            QTableWidget#salesToolsHistoryTable {
                background: #FFFFFF;
                border: 1px solid #D7E0EC;
                border-radius: 12px;
                gridline-color: #E5ECF5;
            }
            QTableWidget#salesToolsHistoryTable::item {
                padding: 6px 10px;
                border: none;
            }
            QTableWidget#salesToolsHistoryTable::item:selected {
                background: #F6FAFF;
                color: #14213D;
            }
            """
        )
        header = self.history_table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.history_table.setColumnWidth(0, 160)
        self.history_table.setColumnWidth(1, 150)
        self.history_table.setColumnWidth(3, 160)
        self.history_table.verticalHeader().setDefaultSectionSize(36)
        history_layout.addWidget(self.history_table, 1)

        self.history_empty_label = QLabel("Sin operaciones registradas todavía.")
        self.history_empty_label.setStyleSheet("color: #6B7280; font-style: italic; padding: 2px 2px 0 2px;")
        history_layout.addWidget(self.history_empty_label)

        layout.addWidget(history_card, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        close_btn = QPushButton("Cerrar")
        close_btn.setMinimumWidth(138)
        close_btn.setMinimumHeight(42)
        close_btn.setStyleSheet(
            """
            QPushButton {
                background: #FFFFFF;
                color: #14213D;
                border: 1px solid #C9D6E5;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 600;
                padding: 0 18px;
            }
            QPushButton:hover {
                background: #F6FAFF;
            }
            """
        )
        close_btn.clicked.connect(self.reject)
        footer.addWidget(close_btn)
        layout.addLayout(footer)

        self.setStyleSheet(
            """
            QDialog#salesToolsDialog {
                background: #F8FBFF;
            }
            QFrame#salesToolsCard {
                background: #FFFFFF;
                border: 1px solid #D7E0EC;
                border-radius: 14px;
            }
            """
        )

    def _make_icon_label(self, icon_path: Path, background: str) -> QLabel:
        label = QLabel()
        label.setFixedSize(54, 54)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(f"background: {background}; border-radius: 27px;")
        pixmap = QIcon(str(icon_path)).pixmap(28, 28)
        label.setPixmap(pixmap)
        return label

    def _make_small_icon_label(self, icon_path: Path, background: str) -> QLabel:
        label = QLabel()
        label.setFixedSize(32, 32)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(f"background: {background}; border-radius: 16px;")
        pixmap = QIcon(str(icon_path)).pixmap(16, 16)
        label.setPixmap(pixmap)
        return label

    def _make_action_button(
        self,
        text: str,
        icon_path: Path,
        *,
        background: str,
        border: str,
        foreground: str,
    ) -> QToolButton:
        button = QToolButton()
        button.setIcon(QIcon(str(icon_path)))
        button.setIconSize(QSize(22, 22))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumSize(194, 104)
        button.setStyleSheet(
            f"""
            QToolButton {{
                background: {background};
                border: 1px solid {border};
                border-radius: 12px;
                color: {foreground};
                font-size: 17px;
                font-weight: 700;
                padding: 10px 14px 12px;
            }}
            QToolButton:hover {{
                background: {'#DCE9FF' if background == '#E5EEFF' else '#DDF3E4'};
            }}
            QToolButton:pressed {{
                background: {'#CBDDFA' if background == '#E5EEFF' else '#C8E8D1'};
            }}
            """
        )
        button.setText(text)
        return button

    def _history_status_def(self, status: str) -> tuple[str, Path, str, str]:
        clean = str(status or "").strip().lower()
        if clean == "error":
            return "Error", ERROR_ICON_PATH, "#B42318", "#FEF3F2"
        if clean == "warning":
            return "Con advertencias", ALERT_ICON_PATH, "#B54708", "#FFFAEB"
        return "Completado", CHECK_ICON_PATH, "#067647", "#ECFDF3"

    def _action_label(self, action: str) -> tuple[str, Path]:
        clean = str(action or "").strip().lower()
        if clean == "export":
            return "Exportación", EXPORT_ICON_PATH
        return "Importación", IMPORT_ICON_PATH

    def _ensure_history_table(self) -> None:
        with engine.begin() as conn:
            conn.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS sales_tools_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    action TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.exec_driver_sql(
                """
                CREATE INDEX IF NOT EXISTS idx_sales_tools_history_created_at
                ON sales_tools_history (created_at DESC, id DESC)
                """
            )

    def _record_history(self, *, action: str, detail: str, status: str, message: str) -> None:
        self._ensure_history_table()
        created_at = datetime.now().isoformat(timespec="seconds")
        with engine.begin() as conn:
            conn.exec_driver_sql(
                """
                INSERT INTO sales_tools_history (created_at, action, detail, status, message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (created_at, action, detail, status, message),
            )

    def _load_history_rows(self, limit: int | None = None) -> list[SalesToolsHistoryRow]:
        self._ensure_history_table()
        safe_limit = self._history_limit if limit is None else max(1, min(int(limit), 200))
        action_filter = str(self.history_filter_combo.currentData() or "all").strip().lower()
        where_clause = ""
        params: list[object] = [safe_limit]
        if action_filter in {"export", "import"}:
            where_clause = "WHERE action = ?"
            params = [action_filter, safe_limit]
        query = f"""
            SELECT created_at, action, detail, status, message
            FROM sales_tools_history
            {where_clause}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
        """
        with engine.begin() as conn:
            rows = conn.exec_driver_sql(query, tuple(params)).fetchall()
        return [
            SalesToolsHistoryRow(
                created_at=str(row[0] or ""),
                action=str(row[1] or ""),
                detail=str(row[2] or ""),
                status=str(row[3] or ""),
                message=str(row[4] or ""),
            )
            for row in rows
        ]

    def _refresh_history(self) -> None:
        rows = self._load_history_rows()
        self.history_table.setRowCount(len(rows))
        self.history_empty_label.setVisible(not rows)

        for row_idx, row in enumerate(rows):
            created_at = row.created_at.replace("T", " ")
            try:
                created_at = datetime.fromisoformat(row.created_at).strftime("%d/%m/%Y %H:%M")
            except Exception:  # noqa: BLE001
                pass

            action_label, action_icon = self._action_label(row.action)
            status_label, status_icon, status_color, status_bg = self._history_status_def(row.status)
            detail_text = row.detail or "-"
            detail_note = row.message or ""

            created_item = QTableWidgetItem(created_at)
            action_item = QTableWidgetItem(action_label)
            action_item.setIcon(QIcon(str(action_icon)))
            detail_item = QTableWidgetItem(detail_text)
            status_item = QTableWidgetItem(status_label)
            status_item.setIcon(QIcon(str(status_icon)))

            for item in (created_item, action_item, detail_item, status_item):
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                item.setForeground(QBrush(QColor("#14213D")))

            detail_item.setToolTip(detail_note or detail_text)
            status_item.setForeground(QBrush(QColor(status_color)))
            status_item.setBackground(QBrush(QColor(status_bg)))
            action_item.setForeground(QBrush(QColor("#214EAA" if row.action == "export" else "#1D7D4D")))

            self.history_table.setItem(row_idx, 0, created_item)
            self.history_table.setItem(row_idx, 1, action_item)
            self.history_table.setItem(row_idx, 2, detail_item)
            self.history_table.setItem(row_idx, 3, status_item)

        self.history_table.resizeRowsToContents()

    def _export_ireks_sales(self) -> None:
        default_name = f"ventas_ireks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        default_path = DATA_DIR / "exports" / "sales" / default_name
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar ventas IREKS",
            str(default_path),
            "Excel (*.xlsx)",
        )
        if not file_path:
            return
        destination = Path(file_path)
        if destination.suffix.lower() != ".xlsx":
            destination = destination.with_suffix(".xlsx")
        try:
            rows_exported, tables = self._write_ireks_sales_workbook(destination)
        except Exception as exc:  # noqa: BLE001
            self._record_history(
                action="export",
                detail=destination.name,
                status="error",
                message=str(exc),
            )
            self._refresh_history()
            QMessageBox.warning(self, "Exportación IREKS", f"No se pudo exportar las ventas IREKS:\n{exc}")
            return

        status = "warning" if rows_exported == 0 else "ok"
        self._record_history(
            action="export",
            detail=f"{destination.name} | {', '.join(tables)}",
            status=status,
            message=f"{rows_exported} filas exportadas | Tablas: {', '.join(tables)}",
        )
        self._refresh_history()
        QMessageBox.information(
            self,
            "Exportación IREKS",
            f"Ventas IREKS exportadas:\n{destination}\n\nFilas exportadas: {rows_exported}",
        )

    def _import_ireks_sales(self) -> None:
        if self._mode == "clientes":
            self._import_clientes_sales()
            return
        view = self._import_service.build_import_view()
        file_path, _ = QFileDialog.getOpenFileName(self, view.ireks_json_title, "", view.ireks_json_filter)
        if not file_path:
            return
        source = Path(file_path)
        try:
            outcome = self._import_service.import_ireks_json(source)
        except Exception as exc:  # noqa: BLE001
            self._record_history(
                action="import",
                detail=source.name,
                status="error",
                message=str(exc),
            )
            self._refresh_history()
            QMessageBox.warning(self, "Importación IREKS", f"No se pudo importar el JSON IREKS:\n{exc}")
            return

        status = "warning" if int(outcome.incidencias or 0) > 0 else "ok"
        if not outcome.ok:
            status = "error"
        self._record_history(
            action="import",
            detail=f"{source.name} | JSON IREKS",
            status=status,
            message=outcome.message.replace("\n", " | "),
        )
        self._refresh_history()
        if outcome.ok and self._on_import_completed is not None:
            self._on_import_completed()

        if outcome.ok and status == "ok":
            QMessageBox.information(self, outcome.title, outcome.message)
        else:
            QMessageBox.warning(self, outcome.title, outcome.message)

    def _import_clientes_sales(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar Excel ventas clientes",
            "",
            "Excel (*.xlsx *.xlsm *.xls)",
        )
        if not file_path:
            return
        source = Path(file_path)
        try:
            preview = self._sales_reconciliation_service.preview_clientes_excel(source)
        except Exception as exc:  # noqa: BLE001
            self._record_history(
                action="import",
                detail=source.name,
                status="error",
                message=str(exc),
            )
            self._refresh_history()
            QMessageBox.warning(self, "Previsualización clientes", f"No se pudo previsualizar el Excel de ventas clientes:\n{exc}")
            return
        self._show_clientes_sales_preview_dialog(source, preview)

    def _execute_clientes_sales_import(self, source: Path, *, close_dialog: QDialog | None = None) -> None:
        try:
            result = self._sales_reconciliation_service.import_clientes_excel(source)
        except Exception as exc:  # noqa: BLE001
            self._record_history(
                action="import",
                detail=source.name,
                status="error",
                message=str(exc),
            )
            self._refresh_history()
            QMessageBox.warning(self, "Importación clientes", f"No se pudo importar el Excel de ventas clientes:\n{exc}")
            return

        status = "ok" if bool(getattr(result, "ok", False)) else "error"
        if int(getattr(result, "incidencias", 0) or 0) > 0:
            status = "warning" if status == "ok" else status
        self._record_history(
            action="import",
            detail=f"{source.name} | Excel clientes",
            status=status,
            message=str(getattr(result, "message", "") or "").replace("\n", " | "),
        )
        self._refresh_history()
        if bool(getattr(result, "ok", False)) and self._on_import_completed is not None:
            self._on_import_completed()

        if bool(getattr(result, "ok", False)) and status == "ok":
            QMessageBox.information(self, "Importación clientes", str(getattr(result, "message", "") or ""))
        else:
            QMessageBox.warning(self, "Importación clientes", str(getattr(result, "message", "") or ""))
        if bool(getattr(result, "ok", False)) and close_dialog is not None:
            close_dialog.accept()

    def _show_clientes_sales_preview_dialog(self, source: Path, preview) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Previsualización - {source.name}")
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        dialog.resize(1220, 760)
        root = QVBoxLayout(dialog)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        title = QLabel("Previsualización de ventas clientes")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #14213D;")
        root.addWidget(title)

        summary = QLabel(
            f"Filas detectadas: {int(getattr(preview, 'total_rows', 0) or 0)}"
            f" | Válidas: {int(getattr(preview, 'valid_rows', 0) or 0)}"
            f" | Con incidencias: {len(getattr(preview, 'issues', []) or [])}"
        )
        summary.setWordWrap(True)
        summary.setStyleSheet("color: #4B5F7A;")
        root.addWidget(summary)

        if getattr(preview, "issues", None):
            issues = QPlainTextEdit()
            issues.setReadOnly(True)
            issues.setMaximumHeight(160)
            issues.setPlainText("\n".join(str(item) for item in list(preview.issues)[:120]))
            root.addWidget(issues)

        table = QTableWidget(0, 12)
        table.setHorizontalHeaderLabels(
            [
                "Fila",
                "Cliente",
                "Codigo",
                "Articulo distribuidor",
                "Producto IREKS",
                "Estado",
                "Incidencia",
                "Envase",
                "Unidades",
                "Kg",
                "Precio/kg",
                "Euros",
            ]
        )
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.setWordWrap(False)
        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(10, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(11, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(0, 70)
        table.setColumnWidth(2, 110)
        table.setColumnWidth(3, 150)
        table.setColumnWidth(5, 84)
        table.setColumnWidth(7, 80)
        table.setColumnWidth(8, 90)
        table.setColumnWidth(9, 90)
        table.setColumnWidth(10, 100)
        table.setColumnWidth(11, 110)
        table.verticalHeader().setDefaultSectionSize(34)

        for row_idx, row in enumerate(list(getattr(preview, "preview_rows", []) or [])):
            table.insertRow(row_idx)
            values = [
                str(row.get("source_row") or ""),
                str(row.get("cliente_nombre") or ""),
                str(row.get("cliente_codigo") or ""),
                str(row.get("articulo_codigo") or ""),
                str(row.get("articulo_descripcion") or ""),
                str(row.get("status") or ""),
                str(row.get("issue_text") or ""),
                f"{float(row.get('envase') or 0.0):.3f}",
                f"{float(row.get('unidades') or 0.0):.3f}",
                f"{float(row.get('kg') or 0.0):.3f}",
                f"{float(row.get('precio_kg') or 0.0):.4f}",
                f"{float(row.get('euros') or 0.0):.2f}",
            ]
            for col_idx, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col_idx in {0, 7, 8, 9, 10, 11}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                status = str(row.get("status") or "").lower()
                if status == "error":
                    item.setBackground(QColor("#FDECEC"))
                elif status == "warning":
                    item.setBackground(QColor("#FFF6D8"))
                table.setItem(row_idx, col_idx, item)
        root.addWidget(table, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        import_btn = QPushButton("Importar")
        import_btn.setProperty("btnRole", "success")
        import_btn.setEnabled(bool(getattr(preview, "valid_rows", 0) or 0))
        import_btn.clicked.connect(lambda: self._execute_clientes_sales_import(source, close_dialog=dialog))
        actions.addWidget(import_btn)
        close_btn = QPushButton("Cerrar")
        close_btn.setProperty("btnRole", "secondary")
        close_btn.clicked.connect(dialog.reject)
        actions.addWidget(close_btn)
        root.addLayout(actions)

        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        dialog.exec()

    def _write_ireks_sales_workbook(self, destination: Path) -> tuple[int, list[str]]:
        tables = [
            ("ventas_import_lotes", "Ventas import lotes"),
            ("ventas_mensuales_raw", "Ventas mensuales raw"),
        ]
        workbook = Workbook()
        total_rows = 0
        used_tables: list[str] = []
        first_sheet = True
        for table_name, sheet_title in tables:
            columns = self._export_service.list_columns(table_name)
            if not columns:
                continue
            ws = workbook.active if first_sheet else workbook.create_sheet()
            first_sheet = False
            ws.title = sheet_title[:31]
            used_tables.append(table_name)
            ws.append(columns)
            header_row = ws.max_row
            for col_idx, header in enumerate(columns, start=1):
                cell = ws.cell(row=header_row, column=col_idx)
                cell.font = Font(bold=True, color="FF14213D")
                cell.fill = PatternFill("solid", fgColor="E8EEF7")
                cell.alignment = Alignment(horizontal="left", vertical="center")
            query = self._build_export_query(table_name, columns)
            with engine.begin() as conn:
                result = conn.exec_driver_sql(query)
                for row in result:
                    ws.append([self._normalize_export_value(value) for value in row])
                    total_rows += 1
            ws.freeze_panes = "A2"
            self._fit_export_sheet(ws)
        if not used_tables:
            raise ValueError("No se encontraron tablas de ventas IREKS para exportar.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        workbook.save(destination)
        return total_rows, used_tables

    def _build_export_query(self, table_name: str, columns: list[str]) -> str:
        quoted_cols = ", ".join(self._quote_identifier(col) for col in columns)
        return f"SELECT {quoted_cols} FROM {self._quote_identifier(table_name)}"

    def _quote_identifier(self, value: str) -> str:
        return '"' + str(value).replace('"', '""') + '"'

    def _normalize_export_value(self, value):
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                return str(value)
        return value

    def _fit_export_sheet(self, ws) -> None:
        for col_idx, column_cells in enumerate(ws.iter_cols(1, ws.max_column), start=1):
            values = [str(cell.value or "") for cell in column_cells]
            width = max([len(str(cell.value or "")) for cell in column_cells] + [10])
            ws.column_dimensions[get_column_letter(col_idx)].width = min(width + 2, 42)


class SalesPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.sales_service = SalesReconciliationService()
        self.sales_summary_service = SalesAnnualComparisonService()
        self._report_export_service = ReportExportService()
        self._building = False
        self._building_igsa = False
        self._building_clientes = False
        self._clientes_selected_client_id = ""
        self._clientes_selected_client_name = "Todos los clientes"
        self._product_filter_timer = QTimer(self)
        self._product_filter_timer.setSingleShot(True)
        self._product_filter_timer.timeout.connect(self.reload)
        self._product_filter_timer_igsa = QTimer(self)
        self._product_filter_timer_igsa.setSingleShot(True)
        self._product_filter_timer_igsa.timeout.connect(self.reload_igsa)
        self._product_filter_timer_clientes = QTimer(self)
        self._product_filter_timer_clientes.setSingleShot(True)
        self._product_filter_timer_clientes.timeout.connect(self.reload_clientes)
        self._build_ui()
        self.reload()
        self.reload_igsa()
        self.reload_clientes()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setSpacing(4)

        self.sales_tabs = QTabWidget()
        root_layout.addWidget(self.sales_tabs)

        ireks_tab = QWidget()
        self.sales_tabs.addTab(ireks_tab, "VENTAS IREKS")
        igsa_tab = QWidget()
        self.sales_tabs.addTab(igsa_tab, "VENTAS IGSA")

        igsa_layout = QVBoxLayout(igsa_tab)
        igsa_filters_top = QHBoxLayout()
        igsa_filters_top.setContentsMargins(0, 0, 0, 0)
        igsa_filters_top.setSpacing(18)

        def create_igsa_filter_group(label_text: str, combo: QComboBox) -> QWidget:
            group = QWidget()
            group_layout = QHBoxLayout(group)
            group_layout.setContentsMargins(0, 0, 0, 0)
            group_layout.setSpacing(4)
            group_label = QLabel(label_text)
            group_label.setStyleSheet("padding-right: 2px;")
            group_layout.addWidget(group_label)
            group_layout.addWidget(combo)
            group.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            return group

        igsa_year_group = QWidget()
        igsa_year_layout = QHBoxLayout(igsa_year_group)
        igsa_year_layout.setContentsMargins(0, 0, 0, 0)
        igsa_year_layout.setSpacing(4)
        igsa_year_label = QLabel("Año")
        igsa_year_label.setStyleSheet("padding-right: 2px;")
        igsa_year_layout.addWidget(igsa_year_label)
        self.year_filter_igsa = QComboBox()
        self.year_filter_igsa.currentIndexChanged.connect(self.reload_igsa)
        self.year_filter_igsa.setMinimumWidth(90)
        igsa_year_layout.addWidget(self.year_filter_igsa)
        igsa_year_group.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        igsa_filters_top.addWidget(igsa_year_group)

        igsa_month_group = QWidget()
        igsa_month_layout = QHBoxLayout(igsa_month_group)
        igsa_month_layout.setContentsMargins(0, 0, 0, 0)
        igsa_month_layout.setSpacing(4)
        igsa_month_label = QLabel("Mes")
        igsa_month_label.setStyleSheet("padding-right: 2px;")
        igsa_month_layout.addWidget(igsa_month_label)
        self.month_filter_igsa = QComboBox()
        self.month_filter_igsa.currentIndexChanged.connect(self.reload_igsa)
        self.month_filter_igsa.setMinimumWidth(125)
        igsa_month_layout.addWidget(self.month_filter_igsa)
        igsa_month_group.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        igsa_filters_top.addWidget(igsa_month_group)

        igsa_acumulado_group = QWidget()
        igsa_acumulado_layout = QHBoxLayout(igsa_acumulado_group)
        igsa_acumulado_layout.setContentsMargins(0, 0, 0, 0)
        igsa_acumulado_layout.setSpacing(4)
        igsa_acumulado_label = QLabel("Acumulado")
        igsa_acumulado_label.setStyleSheet("padding-right: 2px;")
        igsa_acumulado_layout.addWidget(igsa_acumulado_label)
        self.acumulado_check_igsa = QCheckBox()
        self.acumulado_check_igsa.toggled.connect(self.reload_igsa)
        igsa_acumulado_layout.addWidget(self.acumulado_check_igsa)
        igsa_acumulado_group.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        igsa_filters_top.addWidget(igsa_acumulado_group)

        self.manufacturer_filter_igsa = QComboBox()
        self.manufacturer_filter_igsa.currentIndexChanged.connect(self._on_manufacturer_changed_igsa)
        self.manufacturer_filter_igsa.setMinimumWidth(190)
        igsa_filters_top.addWidget(create_igsa_filter_group("Fabricante", self.manufacturer_filter_igsa))

        self.family_filter_igsa = QComboBox()
        self.family_filter_igsa.currentIndexChanged.connect(self._on_family_changed_igsa)
        self.family_filter_igsa.setMinimumWidth(190)
        igsa_filters_top.addWidget(create_igsa_filter_group("Familia", self.family_filter_igsa))

        self.subfamily_filter_igsa = QComboBox()
        self.subfamily_filter_igsa.currentIndexChanged.connect(self.reload_igsa)
        self.subfamily_filter_igsa.setMinimumWidth(190)
        igsa_filters_top.addWidget(create_igsa_filter_group("Subfamilia", self.subfamily_filter_igsa))
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

        clientes_tab = QWidget()
        self.sales_tabs.addTab(clientes_tab, "VENTAS CLIENTES")

        clientes_layout = QVBoxLayout(clientes_tab)
        clientes_layout.setSpacing(4)

        clientes_filters_top = QHBoxLayout()
        clientes_filters_top.setContentsMargins(0, 0, 0, 0)
        clientes_filters_top.setSpacing(18)

        def create_clientes_filter_group(label_text: str, combo: QComboBox) -> QWidget:
            group = QWidget()
            group_layout = QHBoxLayout(group)
            group_layout.setContentsMargins(0, 0, 0, 0)
            group_layout.setSpacing(4)
            group_label = QLabel(label_text)
            group_label.setStyleSheet("padding-right: 2px;")
            group_layout.addWidget(group_label)
            group_layout.addWidget(combo)
            group.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            return group

        clientes_year_group = QWidget()
        clientes_year_layout = QHBoxLayout(clientes_year_group)
        clientes_year_layout.setContentsMargins(0, 0, 0, 0)
        clientes_year_layout.setSpacing(4)
        clientes_year_label = QLabel("Año")
        clientes_year_label.setStyleSheet("padding-right: 2px;")
        clientes_year_layout.addWidget(clientes_year_label)
        self.year_filter_clientes = QComboBox()
        self.year_filter_clientes.currentIndexChanged.connect(self.reload_clientes)
        self.year_filter_clientes.setMinimumWidth(90)
        clientes_year_layout.addWidget(self.year_filter_clientes)
        clientes_year_group.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        clientes_filters_top.addWidget(clientes_year_group)

        clientes_month_group = QWidget()
        clientes_month_layout = QHBoxLayout(clientes_month_group)
        clientes_month_layout.setContentsMargins(0, 0, 0, 0)
        clientes_month_layout.setSpacing(4)
        clientes_month_label = QLabel("Mes")
        clientes_month_label.setStyleSheet("padding-right: 2px;")
        clientes_month_layout.addWidget(clientes_month_label)
        self.month_filter_clientes = QComboBox()
        self.month_filter_clientes.setEnabled(False)
        self.month_filter_clientes.setMinimumWidth(125)
        clientes_month_layout.addWidget(self.month_filter_clientes)
        clientes_month_group.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        clientes_filters_top.addWidget(clientes_month_group)

        clientes_acumulado_group = QWidget()
        clientes_acumulado_layout = QHBoxLayout(clientes_acumulado_group)
        clientes_acumulado_layout.setContentsMargins(0, 0, 0, 0)
        clientes_acumulado_layout.setSpacing(4)
        clientes_acumulado_label = QLabel("Acumulado")
        clientes_acumulado_label.setStyleSheet("padding-right: 2px;")
        clientes_acumulado_layout.addWidget(clientes_acumulado_label)
        self.acumulado_check_clientes = QCheckBox()
        self.acumulado_check_clientes.toggled.connect(self.reload_clientes)
        clientes_acumulado_layout.addWidget(self.acumulado_check_clientes)
        clientes_acumulado_group.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        clientes_filters_top.addWidget(clientes_acumulado_group)

        self.manufacturer_filter_clientes = QComboBox()
        self.manufacturer_filter_clientes.currentIndexChanged.connect(self._on_manufacturer_changed_clientes)
        self.manufacturer_filter_clientes.setMinimumWidth(190)
        clientes_filters_top.addWidget(create_clientes_filter_group("Fabricante", self.manufacturer_filter_clientes))

        self.family_filter_clientes = QComboBox()
        self.family_filter_clientes.currentIndexChanged.connect(self._on_family_changed_clientes)
        self.family_filter_clientes.setMinimumWidth(190)
        clientes_filters_top.addWidget(create_clientes_filter_group("Familia", self.family_filter_clientes))

        self.subfamily_filter_clientes = QComboBox()
        self.subfamily_filter_clientes.currentIndexChanged.connect(self.reload_clientes)
        self.subfamily_filter_clientes.setMinimumWidth(190)
        clientes_filters_top.addWidget(create_clientes_filter_group("Subfamilia", self.subfamily_filter_clientes))
        clientes_layout.addLayout(clientes_filters_top)

        clientes_filters_bottom = QHBoxLayout()
        clientes_filters_bottom.addWidget(QLabel("Cliente"))
        client_selector_widget = QWidget()
        client_selector_layout = QHBoxLayout(client_selector_widget)
        client_selector_layout.setContentsMargins(0, 0, 0, 0)
        client_selector_layout.setSpacing(6)
        self.client_filter_clientes_btn = QPushButton()
        self.client_filter_clientes_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.client_filter_clientes_btn.setMinimumWidth(348)
        self.client_filter_clientes_btn.setToolTip("Seleccionar cliente")
        self.client_filter_clientes_btn.clicked.connect(self._open_clientes_client_dialog)
        self.client_filter_clientes_btn.setText("Todos los clientes")
        client_selector_layout.addWidget(self.client_filter_clientes_btn, 1)
        self.client_filter_clientes_clear_btn = QPushButton("Todos")
        self.client_filter_clientes_clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.client_filter_clientes_clear_btn.setFixedWidth(72)
        self.client_filter_clientes_clear_btn.setToolTip("Limpiar cliente seleccionado")
        self.client_filter_clientes_clear_btn.clicked.connect(self._clear_clientes_client_selection)
        self.client_filter_clientes_clear_btn.setEnabled(False)
        client_selector_layout.addWidget(self.client_filter_clientes_clear_btn)
        self.client_selector_widget_clientes = client_selector_widget
        clientes_filters_bottom.addWidget(client_selector_widget, 1)

        clientes_filters_bottom.addWidget(QLabel("Producto"))
        self.product_filter_clientes = QLineEdit()
        self.product_filter_clientes.setPlaceholderText("Buscar por código o descripción...")
        self.product_filter_clientes.textChanged.connect(self._schedule_product_reload_clientes)
        self.product_filter_clientes.setMinimumWidth(250)
        clientes_filters_bottom.addWidget(self.product_filter_clientes, 1)
        self.client_filter_clientes_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #FFFFFF;
                color: #253041;
                border: 1px solid #CCD6E2;
                border-radius: 6px;
                padding: 0 12px;
                min-height: 33px;
                max-height: 33px;
            }
            QPushButton:hover {
                background-color: #F7FAFD;
                border-color: #BFD0E0;
            }
            QPushButton:pressed {
                background-color: #EEF4F9;
            }
            QPushButton:disabled {
                background-color: #F5F7FA;
                color: #A7B1BD;
                border-color: #E1E7EE;
            }
            """
        )
        self.client_filter_clientes_clear_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #FDECEC;
                color: #B42318;
                border: 1px solid #F5B5B1;
                border-radius: 6px;
                padding: 0 12px;
                min-height: 33px;
                max-height: 33px;
            }
            QPushButton:hover {
                background-color: #FAD8D5;
                border-color: #EAA4A0;
            }
            QPushButton:pressed {
                background-color: #F6C7C2;
            }
            QPushButton:disabled {
                background-color: #F7F1F0;
                color: #D08A84;
                border-color: #E8D8D6;
            }
            """
        )
        button_height = 35
        self.client_filter_clientes_clear_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.client_filter_clientes_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.client_filter_clientes_clear_btn.setFixedHeight(button_height)
        self.client_filter_clientes_btn.setFixedHeight(button_height)
        self.client_selector_widget_clientes.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.client_selector_widget_clientes.setFixedHeight(button_height)

        clientes_action_button_width = 110
        clientes_action_button_height = 36

        def make_clientes_action_button(
            *,
            text: str,
            tooltip: str,
            icon_path: Path,
            background: str,
            border: str,
            hover_background: str,
            pressed_background: str,
            foreground: str = "#1F2937",
        ) -> QToolButton:
            button = QToolButton()
            button.setToolTip(tooltip)
            button.setIcon(QIcon(str(icon_path)))
            button.setIconSize(QSize(16, 16))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFixedSize(clientes_action_button_width, clientes_action_button_height)
            button.setText(text)
            button.setStyleSheet(
                f"""
                QToolButton {{
                    background-color: {background};
                    border: 1px solid {border};
                    border-radius: 8px;
                    color: {foreground};
                    padding: 0 8px;
                    font-size: 12px;
                    font-weight: 600;
                }}
                QToolButton:hover {{
                    background-color: {hover_background};
                }}
                QToolButton:pressed {{
                    background-color: {pressed_background};
                }}
                QToolButton:disabled {{
                    background-color: {background};
                    border-color: {border};
                    color: #6B7280;
                }}
                """
            )
            return button

        self.sales_chart_btn_clientes = QToolButton()
        self.sales_chart_btn_clientes.setToolTip("Ver gráfico del producto")
        self.sales_chart_btn_clientes.setIcon(QIcon(str(CHART_LINE_ICON_PATH)))
        self.sales_chart_btn_clientes.setIconSize(QSize(16, 16))
        self.sales_chart_btn_clientes.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.sales_chart_btn_clientes.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sales_chart_btn_clientes.setFixedSize(clientes_action_button_width, clientes_action_button_height)
        self.sales_chart_btn_clientes.setEnabled(False)
        self.sales_chart_btn_clientes.setText("Producto")
        self.sales_chart_btn_clientes.setStyleSheet(
            """
            QToolButton {
                background-color: #9CC9F5;
                border: 1px solid #7AAEE3;
                border-radius: 8px;
                color: #1F2937;
                padding: 0 8px;
                font-size: 12px;
                font-weight: 600;
            }
            QToolButton:hover {
                background-color: #B0D4F8;
            }
            QToolButton:pressed {
                background-color: #8AB8E6;
            }
            QToolButton:disabled {
                background-color: #C7DFF5;
                border-color: #B1CBE5;
                color: #6B7280;
            }
            """
        )

        self.sales_total_chart_btn_clientes = QToolButton()
        self.sales_total_chart_btn_clientes.setToolTip("Ver gráfico total")
        self.sales_total_chart_btn_clientes.setIcon(QIcon(str(CHART_LINE_ICON_PATH)))
        self.sales_total_chart_btn_clientes.setIconSize(QSize(16, 16))
        self.sales_total_chart_btn_clientes.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.sales_total_chart_btn_clientes.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sales_total_chart_btn_clientes.setFixedSize(clientes_action_button_width, clientes_action_button_height)
        self.sales_total_chart_btn_clientes.setEnabled(False)
        self.sales_total_chart_btn_clientes.setText("Total")
        self.sales_total_chart_btn_clientes.setStyleSheet(
            """
            QToolButton {
                background-color: #A7E3D1;
                border: 1px solid #83CBB5;
                border-radius: 8px;
                color: #1F2937;
                padding: 0 8px;
                font-size: 12px;
                font-weight: 600;
            }
            QToolButton:hover {
                background-color: #B8E8DA;
            }
            QToolButton:pressed {
                background-color: #91D2BE;
            }
            QToolButton:disabled {
                background-color: #CDEFE4;
                border-color: #B8DCCD;
                color: #6B7280;
            }
            """
        )

        self.sales_analysis_btn_clientes = QToolButton()
        self.sales_analysis_btn_clientes.setToolTip("Análisis")
        self.sales_analysis_btn_clientes.setIcon(QIcon(str(BASE_DIR / "assets" / "icons" / "brain.svg")))
        self.sales_analysis_btn_clientes.setIconSize(QSize(16, 16))
        self.sales_analysis_btn_clientes.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.sales_analysis_btn_clientes.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sales_analysis_btn_clientes.setFixedSize(clientes_action_button_width, clientes_action_button_height)
        self.sales_analysis_btn_clientes.setEnabled(False)
        self.sales_analysis_btn_clientes.setText("Análisis")
        self.sales_analysis_btn_clientes.setStyleSheet(
            """
            QToolButton {
                background-color: #F6E3A1;
                border: 1px solid #E3C56D;
                border-radius: 8px;
                color: #111827;
                padding: 0 8px;
                font-size: 12px;
                font-weight: 600;
            }
            QToolButton:hover {
                background-color: #F8E8B6;
            }
            QToolButton:pressed {
                background-color: #EED88B;
            }
            QToolButton:disabled {
                background-color: #FAEDC5;
                border-color: #E8D79C;
                color: #6B7280;
            }
            """
        )

        self.sales_print_btn_clientes = make_clientes_action_button(
            text="Imprimir",
            tooltip="Imprimir",
            icon_path=PRINTER_ICON_PATH,
            background="#D6D0C8",
            border="#B8B1A8",
            hover_background="#E2DDD6",
            pressed_background="#C8C1B7",
        )
        self.sales_print_btn_clientes.setEnabled(False)

        self.sales_pdf_btn_clientes = make_clientes_action_button(
            text="PDF",
            tooltip="Exportar a PDF",
            icon_path=FILE_TEXT_ICON_PATH,
            background="#F4B2A8",
            border="#D98E83",
            hover_background="#F7C0B8",
            pressed_background="#E89A8F",
        )
        self.sales_pdf_btn_clientes.setEnabled(False)

        self.sales_excel_btn_clientes = make_clientes_action_button(
            text="Excel",
            tooltip="Exportar a Excel",
            icon_path=SHEET_ICON_PATH,
            background="#CBEA8B",
            border="#AFD268",
            hover_background="#D7F09D",
            pressed_background="#B9DE72",
        )
        self.sales_excel_btn_clientes.clicked.connect(self._export_sales_excel)

        self.sales_tools_btn_clientes = make_clientes_action_button(
            text="Tools",
            tooltip="Herramientas",
            icon_path=TOOLBOX_ICON_PATH,
            background="#D9C3F3",
            border="#BA9EE7",
            hover_background="#E3D2F7",
            pressed_background="#CBB2ED",
        )
        self.sales_tools_btn_clientes.clicked.connect(self._open_clientes_sales_tools_dialog)

        clientes_chart_actions_widget = QWidget()
        clientes_chart_band = QHBoxLayout(clientes_chart_actions_widget)
        clientes_chart_band.setContentsMargins(0, 0, 0, 0)
        clientes_chart_band.setSpacing(4)
        clientes_chart_band.addWidget(self.sales_chart_btn_clientes)
        clientes_chart_band.addWidget(self.sales_total_chart_btn_clientes)
        clientes_chart_band.addWidget(self.sales_analysis_btn_clientes)
        clientes_chart_band.addWidget(self.sales_print_btn_clientes)
        clientes_chart_band.addWidget(self.sales_pdf_btn_clientes)
        clientes_chart_band.addWidget(self.sales_excel_btn_clientes)
        clientes_chart_band.addWidget(self.sales_tools_btn_clientes)

        clientes_layout.addLayout(clientes_filters_bottom)

        clientes_actions_band = QHBoxLayout()
        clientes_actions_band.setContentsMargins(0, 0, 0, 0)
        clientes_actions_band.setSpacing(8)
        clientes_actions_band.addWidget(clientes_chart_actions_widget)
        clientes_actions_band.addStretch(1)
        clientes_layout.addLayout(clientes_actions_band)

        clientes_separator_line = QFrame()
        clientes_separator_line.setFrameShape(QFrame.Shape.HLine)
        clientes_separator_line.setFrameShadow(QFrame.Shadow.Plain)
        clientes_separator_line.setStyleSheet("color: #D8E0EC; background: #D8E0EC;")
        clientes_separator_line.setFixedHeight(1)
        clientes_layout.addWidget(clientes_separator_line)

        self.group_header_clientes = QTableWidget(1, 12)
        self.group_header_clientes.setObjectName("salesGroupHeaderClientes")
        self.group_header_clientes.setFixedHeight(36)
        self.group_header_clientes.horizontalHeader().setVisible(False)
        self.group_header_clientes.verticalHeader().setVisible(False)
        self.group_header_clientes.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.group_header_clientes.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.group_header_clientes.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.group_header_clientes.setShowGrid(False)
        self.group_header_clientes.verticalHeader().setDefaultSectionSize(34)
        self.group_header_clientes.setRowHeight(0, 34)
        self.group_header_clientes.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.group_header_clientes.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.group_header_clientes.viewport().setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.group_header_clientes.setStyleSheet(
            """
            QTableWidget#salesGroupHeaderClientes {
                border: none;
                background: transparent;
                selection-background-color: transparent;
            }
            QTableWidget#salesGroupHeaderClientes::item,
            QTableWidget#salesGroupHeaderClientes::item:hover,
            QTableWidget#salesGroupHeaderClientes::item:selected,
            QTableWidget#salesGroupHeaderClientes::item:focus {
                border: none;
                background: transparent;
                outline: none;
            }
            """
        )

        clientes_layout.addWidget(self.group_header_clientes)

        self.sales_table_clientes = QTableWidget(0, 12)
        self.sales_table_clientes.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.sales_table_clientes.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.sales_table_clientes.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.sales_table_clientes.verticalHeader().setVisible(False)
        self.sales_table_clientes.setSortingEnabled(True)
        self.sales_table_clientes.setHorizontalHeaderLabels(
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
        clientes_header = self.sales_table_clientes.horizontalHeader()
        clientes_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        clientes_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for idx in range(2, 12):
            clientes_header.setSectionResizeMode(idx, QHeaderView.ResizeMode.Fixed)
        clientes_header.sectionResized.connect(self._sync_aux_column_width_clientes)
        clientes_layout.addWidget(self.sales_table_clientes, 1)

        self.totals_table_clientes = QTableWidget(1, 12)
        self.totals_table_clientes.setObjectName("salesTotalsTableClientes")
        self.totals_table_clientes.horizontalHeader().setVisible(False)
        self.totals_table_clientes.verticalHeader().setVisible(False)
        self.totals_table_clientes.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.totals_table_clientes.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.totals_table_clientes.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.totals_table_clientes.setFrameShape(QTableWidget.Shape.NoFrame)
        self.totals_table_clientes.setFixedHeight(36)
        self.totals_table_clientes.verticalHeader().setDefaultSectionSize(36)
        self.totals_table_clientes.setRowHeight(0, 36)
        self.totals_table_clientes.setShowGrid(True)
        self.totals_table_clientes.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.totals_table_clientes.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.totals_table_clientes.setStyleSheet(
            """
            QTableWidget#salesTotalsTableClientes {
                border: 1px solid #C9D1DC;
                border-radius: 0;
                background: #FFFFFF;
                gridline-color: #C9D1DC;
                selection-background-color: transparent;
            }
            QTableWidget#salesTotalsTableClientes::viewport {
                border: none;
                border-radius: 0;
                background: #FFFFFF;
            }
            QTableWidget#salesTotalsTableClientes::item,
            QTableWidget#salesTotalsTableClientes::item:hover,
            QTableWidget#salesTotalsTableClientes::item:selected,
            QTableWidget#salesTotalsTableClientes::item:focus {
                border: none;
                background: #FFFFFF;
                outline: none;
                padding: 2px 6px;
            }
            QTableWidget#salesTotalsTableClientes::item:selected:!active {
                background: #FFFFFF;
            }
            """
        )
        self.totals_table_clientes.viewport().setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        clientes_layout.addWidget(self.totals_table_clientes)

        layout = QVBoxLayout(ireks_tab)
        layout.setSpacing(4)

        filters_top = QHBoxLayout()
        filters_top.setContentsMargins(0, 0, 0, 0)
        filters_top.setSpacing(18)

        def create_filter_group(label_text: str, combo: QComboBox) -> QWidget:
            group = QWidget()
            group_layout = QHBoxLayout(group)
            group_layout.setContentsMargins(0, 0, 0, 0)
            group_layout.setSpacing(4)
            group_label = QLabel(label_text)
            group_label.setStyleSheet("padding-right: 2px;")
            group_layout.addWidget(group_label)
            group_layout.addWidget(combo)
            group.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            return group

        year_group = QWidget()
        year_layout = QHBoxLayout(year_group)
        year_layout.setContentsMargins(0, 0, 0, 0)
        year_layout.setSpacing(4)
        year_label = QLabel("Año")
        year_label.setStyleSheet("padding-right: 2px;")
        year_layout.addWidget(year_label)
        self.year_filter = QComboBox()
        self.year_filter.currentIndexChanged.connect(self.reload)
        self.year_filter.setMinimumWidth(90)
        year_layout.addWidget(self.year_filter)
        year_group.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        filters_top.addWidget(year_group)

        month_group = QWidget()
        month_layout = QHBoxLayout(month_group)
        month_layout.setContentsMargins(0, 0, 0, 0)
        month_layout.setSpacing(4)
        month_label = QLabel("Mes")
        month_label.setStyleSheet("padding-right: 2px;")
        month_layout.addWidget(month_label)
        self.month_filter = QComboBox()
        self.month_filter.currentIndexChanged.connect(self.reload)
        self.month_filter.setMinimumWidth(125)
        month_layout.addWidget(self.month_filter)
        month_group.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        filters_top.addWidget(month_group)

        acumulado_group = QWidget()
        acumulado_layout = QHBoxLayout(acumulado_group)
        acumulado_layout.setContentsMargins(0, 0, 0, 0)
        acumulado_layout.setSpacing(4)
        acumulado_label = QLabel("Acumulado")
        acumulado_label.setStyleSheet("padding-right: 2px;")
        acumulado_layout.addWidget(acumulado_label)
        self.acumulado_check = QCheckBox()
        self.acumulado_check.toggled.connect(self.reload)
        acumulado_layout.addWidget(self.acumulado_check)
        acumulado_group.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        filters_top.addWidget(acumulado_group)

        self.manufacturer_filter = QComboBox()
        self.manufacturer_filter.currentIndexChanged.connect(self._on_manufacturer_changed)
        self.manufacturer_filter.setMinimumWidth(190)
        filters_top.addWidget(create_filter_group("Fabricante", self.manufacturer_filter))

        self.family_filter = QComboBox()
        self.family_filter.currentIndexChanged.connect(self._on_family_changed)
        self.family_filter.setMinimumWidth(190)
        filters_top.addWidget(create_filter_group("Familia", self.family_filter))

        self.subfamily_filter = QComboBox()
        self.subfamily_filter.currentIndexChanged.connect(self.reload)
        self.subfamily_filter.setMinimumWidth(190)
        filters_top.addWidget(create_filter_group("Subfamilia", self.subfamily_filter))

        layout.addLayout(filters_top)

        filters_bottom = QHBoxLayout()
        filters_bottom.addWidget(QLabel("Cliente"))
        self.client_filter = QComboBox()
        self.client_filter.currentIndexChanged.connect(self.reload)
        self.client_filter.setMinimumWidth(260)
        filters_bottom.addWidget(self.client_filter, 1)

        filters_bottom.addWidget(QLabel("Producto"))
        self.product_filter = QLineEdit()
        self.product_filter.setPlaceholderText("Buscar por código o descripción...")
        self.product_filter.textChanged.connect(self._schedule_product_reload)
        self.product_filter.setMinimumWidth(300)
        filters_bottom.addWidget(self.product_filter, 1)

        action_button_width = 110
        action_button_height = 36

        def make_action_button(
            *,
            text: str,
            tooltip: str,
            icon_path: Path,
            background: str,
            border: str,
            hover_background: str,
            pressed_background: str,
            foreground: str = "#1F2937",
        ) -> QToolButton:
            button = QToolButton()
            button.setToolTip(tooltip)
            button.setIcon(QIcon(str(icon_path)))
            button.setIconSize(QSize(16, 16))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFixedSize(action_button_width, action_button_height)
            button.setText(text)
            button.setStyleSheet(
                f"""
                QToolButton {{
                    background-color: {background};
                    border: 1px solid {border};
                    border-radius: 8px;
                    color: {foreground};
                    padding: 0 8px;
                    font-size: 12px;
                    font-weight: 600;
                }}
                QToolButton:hover {{
                    background-color: {hover_background};
                }}
                QToolButton:pressed {{
                    background-color: {pressed_background};
                }}
                QToolButton:disabled {{
                    background-color: {background};
                    border-color: {border};
                    color: #6B7280;
                }}
                """
            )
            return button

        self.sales_chart_btn = QToolButton()
        self.sales_chart_btn.setToolTip("Ver gráfico del producto")
        self.sales_chart_btn.setIcon(QIcon(str(CHART_LINE_ICON_PATH)))
        self.sales_chart_btn.setIconSize(QSize(16, 16))
        self.sales_chart_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.sales_chart_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sales_chart_btn.setFixedSize(action_button_width, action_button_height)
        self.sales_chart_btn.setEnabled(False)
        self.sales_chart_btn.setText("Producto")
        self.sales_chart_btn.setStyleSheet(
            """
            QToolButton {
                background-color: #9CC9F5;
                border: 1px solid #7AAEE3;
                border-radius: 8px;
                color: #1F2937;
                padding: 0 8px;
                font-size: 12px;
                font-weight: 600;
            }
            QToolButton:hover {
                background-color: #B0D4F8;
            }
            QToolButton:pressed {
                background-color: #8AB8E6;
            }
            QToolButton:disabled {
                background-color: #C7DFF5;
                border-color: #B1CBE5;
                color: #6B7280;
            }
            """
        )
        self.sales_chart_btn.clicked.connect(self._open_selected_monthly_sales_dialog)

        self.sales_total_chart_btn = QToolButton()
        self.sales_total_chart_btn.setToolTip("Ver gráfico total")
        self.sales_total_chart_btn.setIcon(QIcon(str(CHART_LINE_ICON_PATH)))
        self.sales_total_chart_btn.setIconSize(QSize(16, 16))
        self.sales_total_chart_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.sales_total_chart_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sales_total_chart_btn.setFixedSize(action_button_width, action_button_height)
        self.sales_total_chart_btn.setEnabled(False)
        self.sales_total_chart_btn.setText("Total")
        self.sales_total_chart_btn.setStyleSheet(
            """
            QToolButton {
                background-color: #A7E3D1;
                border: 1px solid #83CBB5;
                border-radius: 8px;
                color: #1F2937;
                padding: 0 8px;
                font-size: 12px;
                font-weight: 600;
            }
            QToolButton:hover {
                background-color: #B8E8DA;
            }
            QToolButton:pressed {
                background-color: #91D2BE;
            }
            QToolButton:disabled {
                background-color: #CDEFE4;
                border-color: #B8DCCD;
                color: #6B7280;
            }
            """
        )
        self.sales_total_chart_btn.clicked.connect(self._open_total_monthly_sales_dialog)

        self.sales_analysis_btn = QToolButton()
        self.sales_analysis_btn.setToolTip("Análisis")
        self.sales_analysis_btn.setIcon(QIcon(str(BASE_DIR / "assets" / "icons" / "brain.svg")))
        self.sales_analysis_btn.setIconSize(QSize(16, 16))
        self.sales_analysis_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.sales_analysis_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sales_analysis_btn.setFixedSize(action_button_width, action_button_height)
        self.sales_analysis_btn.setEnabled(False)
        self.sales_analysis_btn.setText("Análisis")
        self.sales_analysis_btn.setStyleSheet(
            """
            QToolButton {
                background-color: #F6E3A1;
                border: 1px solid #E3C56D;
                border-radius: 8px;
                color: #111827;
                padding: 0 8px;
                font-size: 12px;
                font-weight: 600;
            }
            QToolButton:hover {
                background-color: #F8E8B6;
            }
            QToolButton:pressed {
                background-color: #EED88B;
            }
            QToolButton:disabled {
                background-color: #FAEDC5;
                border-color: #E8D79C;
                color: #6B7280;
            }
            """
        )
        self.sales_analysis_btn.clicked.connect(self._open_sales_analysis_dialog)

        self.sales_print_btn = make_action_button(
            text="Imprimir",
            tooltip="Imprimir",
            icon_path=PRINTER_ICON_PATH,
            background="#D6D0C8",
            border="#B8B1A8",
            hover_background="#E2DDD6",
            pressed_background="#C8C1B7",
        )

        self.sales_pdf_btn = make_action_button(
            text="PDF",
            tooltip="Exportar a PDF",
            icon_path=FILE_TEXT_ICON_PATH,
            background="#F4B2A8",
            border="#D98E83",
            hover_background="#F7C0B8",
            pressed_background="#E89A8F",
        )

        self.sales_excel_btn = make_action_button(
            text="Excel",
            tooltip="Exportar a Excel",
            icon_path=SHEET_ICON_PATH,
            background="#CBEA8B",
            border="#AFD268",
            hover_background="#D7F09D",
            pressed_background="#B9DE72",
        )

        self.sales_tools_btn = make_action_button(
            text="Tools",
            tooltip="Herramientas",
            icon_path=TOOLBOX_ICON_PATH,
            background="#D9C3F3",
            border="#BA9EE7",
            hover_background="#E3D2F7",
            pressed_background="#CBB2ED",
        )
        self.sales_tools_btn.clicked.connect(self._open_sales_tools_dialog)
        self.sales_excel_btn.clicked.connect(self._export_sales_excel)

        self.chart_actions_widget = QWidget()
        chart_band = QHBoxLayout(self.chart_actions_widget)
        chart_band.setContentsMargins(0, 0, 0, 0)
        chart_band.setSpacing(4)
        chart_band.addWidget(self.sales_chart_btn)
        chart_band.addWidget(self.sales_total_chart_btn)
        chart_band.addWidget(self.sales_analysis_btn)
        chart_band.addWidget(self.sales_print_btn)
        chart_band.addWidget(self.sales_pdf_btn)
        chart_band.addWidget(self.sales_excel_btn)
        chart_band.addWidget(self.sales_tools_btn)

        layout.addLayout(filters_bottom)

        actions_band = QHBoxLayout()
        actions_band.setContentsMargins(0, 0, 0, 0)
        actions_band.setSpacing(8)
        actions_band.addWidget(self.chart_actions_widget)
        actions_band.addStretch(1)
        layout.addLayout(actions_band)

        separator_line = QFrame()
        separator_line.setFrameShape(QFrame.Shape.HLine)
        separator_line.setFrameShadow(QFrame.Shadow.Plain)
        separator_line.setStyleSheet("color: #D8E0EC; background: #D8E0EC;")
        separator_line.setFixedHeight(1)
        layout.addWidget(separator_line)

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
        self.sales_table_clientes.horizontalScrollBar().valueChanged.connect(self.group_header_clientes.horizontalScrollBar().setValue)
        self.sales_table_clientes.horizontalScrollBar().valueChanged.connect(self.totals_table_clientes.horizontalScrollBar().setValue)
        self._apply_column_widths_igsa()
        self._apply_column_widths_clientes()

    def _export_sales_excel(self) -> None:
        state = self._sales_export_state()
        if state is None:
            QMessageBox.warning(self, "Ventas", "No hay datos disponibles para exportar a Excel.")
            return

        dialog = SalesExcelExportDialog(
            str(state["source_label"]),
            client_groupable=bool(state.get("customer_groupable", False)),
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        options = dialog.export_options()
        sections, grand_rows, grand_total_label = self._sales_export_sections_v2(state, options)
        if not sections or all(not rows for _title, rows in sections):
            QMessageBox.warning(self, "Ventas", "No hay datos para exportar con los filtros seleccionados.")
            return

        title = f"Ventas {state['source_label']} {state['year']}"
        subtitle = self._sales_export_subtitle_v2(state, options)
        default = str(self._report_export_service.default_path(title, "xlsx", folder="sales"))
        save_options = QFileDialog.Option.DontUseNativeDialog
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar ventas a Excel",
            default,
            "Excel (*.xlsx)",
            options=save_options,
        )
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path = f"{path}.xlsx"
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            try:
                out = self._write_sales_export_workbook_v2(
                    path=path,
                    title=title,
                    subtitle=subtitle,
                    sections=sections,
                    grand_rows=grand_rows,
                    grand_total_label=grand_total_label,
                    sort_by=str(options["sort_by"]),
                    direction=str(options["direction"]),
                    group_levels=list(options["group_levels"]),
                    include_subtotals=bool(options["subtotals"]),
                    state=state,
                )
            except Exception as exc:  # pragma: no cover - GUI safeguard
                QMessageBox.critical(self, "Ventas", f"No se pudo exportar a Excel:\n{exc}")
                return
        finally:
            QApplication.restoreOverrideCursor()
        QMessageBox.information(self, "Ventas", f"Excel exportado:\n{out}")

    def _open_sales_tools_dialog(self) -> None:
        dialog = SalesToolsDialog(on_import_completed=self.reload, parent=self)
        dialog.exec()

    def _open_clientes_sales_tools_dialog(self) -> None:
        dialog = SalesToolsDialog(mode="clientes", on_import_completed=self.reload_clientes, parent=self)
        dialog.exec()

    def _sales_export_state(self) -> dict[str, object] | None:
        if not hasattr(self, "sales_tabs"):
            return None
        tab_index = self.sales_tabs.currentIndex()
        if tab_index == 1:
            year = self._current_year_igsa()
            if year <= 0:
                return None
            return {
                "source_key": "igsa",
                "source_label": "IGSA",
                "year": year,
                "month": self._current_month_igsa(),
                "acumulado": bool(self.acumulado_check_igsa.isChecked()),
                "cliente_id": "",
                "cliente_texto": "",
                "producto_texto": self._current_product_text_igsa(),
                "fabricante_id": self._current_manufacturer_id_igsa(),
                "familia_id": self._current_family_id_igsa(),
                "subfamilia_id": self._current_subfamily_id_igsa(),
                "customer_groupable": False,
            }
        if tab_index == 2:
            year = self._current_year_clientes()
            if year <= 0:
                return None
            return {
                "source_key": "clientes",
                "source_label": "CLIENTES",
                "year": year,
                "month": self._current_month_clientes(),
                "acumulado": bool(self.acumulado_check_clientes.isChecked()),
                "cliente_id": self._current_client_id_clientes(),
                "cliente_texto": self._current_client_name_clientes() if self._current_client_id_clientes() else "",
                "producto_texto": self._current_product_text_clientes(),
                "fabricante_id": self._current_manufacturer_id_clientes(),
                "familia_id": self._current_family_id_clientes(),
                "subfamilia_id": self._current_subfamily_id_clientes(),
                "customer_groupable": False,
            }
        year = self._current_year()
        if year <= 0:
            return None
        return {
            "source_key": "ireks",
            "source_label": "IREKS",
            "year": year,
            "month": self._current_month(),
            "acumulado": bool(self.acumulado_check.isChecked()),
            "cliente_id": self._current_client_id(),
            "cliente_texto": self._current_client_name() if self._current_client_id() else "",
            "producto_texto": self._current_product_text(),
            "fabricante_id": self._current_manufacturer_id(),
            "familia_id": self._current_family_id(),
            "subfamilia_id": self._current_subfamily_id(),
            "customer_groupable": not bool(self._current_client_id()),
        }

    def _sales_export_subtitle_v2(self, state: dict[str, object], options: dict[str, object]) -> str:
        month_value = int(state["month"] or 0)
        if bool(state["acumulado"]):
            if 1 <= month_value <= 12:
                month_text = f"Enero a {self._sales_export_month_label(month_value)}"
            else:
                month_text = "Enero a Diciembre"
        else:
            month_text = self._sales_export_month_label(month_value)
        parts = [
            f"Año: {state['year']}",
            f"Mes: {month_text}",
            f"Acumulado: {'Sí' if bool(state['acumulado']) else 'No'}",
            f"Agrupar por: {self._sales_export_group_levels_label(list(options['group_levels']))}",
            f"Ordenar por: {self._sales_export_sort_label(str(options['sort_by']))}",
            f"Dirección: {'Descendente' if str(options['direction']) == 'desc' else 'Ascendente'}",
        ]
        if state["source_key"] in {"ireks", "clientes"}:
            cliente = str(state.get("cliente_texto") or "").strip()
            if cliente:
                parts.append(f"Cliente: {cliente}")
        producto = str(state.get("producto_texto") or "").strip()
        if producto:
            parts.append(f"Producto: {producto}")
        fabricante = str(state.get("fabricante_id") or "").strip()
        family = str(state.get("familia_id") or "").strip()
        subfamily = str(state.get("subfamilia_id") or "").strip()
        if fabricante:
            parts.append(f"Fabricante ID: {fabricante}")
        if family:
            parts.append(f"Familia ID: {family}")
        if subfamily:
            parts.append(f"Subfamilia ID: {subfamily}")
        return " | ".join(parts)

    def _sales_export_month_label(self, month: int) -> str:
        if 1 <= month <= 12:
            return MONTH_NAMES[month - 1]
        return "Todos"

    def _sales_export_group_label(self, group_by: str) -> str:
        return {
            "none": "Sin agrupar",
            "month": "Mes",
            "manufacturer": "Fabricante",
            "family": "Familia",
            "subfamily": "Subfamilia",
        }.get(group_by, "Sin agrupar")

    def _sales_export_sort_label(self, sort_by: str) -> str:
        return {
            "codigo": "Código",
            "nombre": "Producto",
            "kilos_prev": "Kilos anterior",
            "sc_prev": "S/C anterior",
            "ventas_prev": "Ventas anterior",
            "kilos_curr": "Kilos actual",
            "sc_curr": "S/C actual",
            "ventas_curr": "Ventas actual",
            "delta_kg": "Delta kg",
            "delta_kg_pct": "Delta kg %",
            "delta_ventas": "Delta €",
            "delta_ventas_pct": "Delta € %",
        }.get(sort_by, "Ventas actual")

    def _sales_export_months(self, month: int, acumulado: bool) -> list[int]:
        clean_month = int(month or 0)
        if 1 <= clean_month <= 12:
            return list(range(1, clean_month + 1)) if acumulado else [clean_month]
        return list(range(1, 13))

    def _sales_export_load_rows(
        self,
        state: dict[str, object],
        *,
        month: int,
    ) -> list[SalesComparisonRow]:
        year = int(state["year"] or 0)
        acumulado = bool(state["acumulado"])
        source_key = str(state["source_key"] or "")
        if source_key == "igsa":
            return self.sales_summary_service.listar_resumen_anual_igsa(
                year=year,
                month=month,
                acumulado=acumulado,
                producto_texto=str(state["producto_texto"] or ""),
                fabricante_id=str(state["fabricante_id"] or ""),
                familia_id=str(state["familia_id"] or ""),
                subfamilia_id=str(state["subfamilia_id"] or ""),
            )
        if source_key == "clientes":
            return self.sales_summary_service.listar_resumen_anual_clientes(
                year=year,
                cliente_id=str(state["cliente_id"] or ""),
                producto_texto=str(state["producto_texto"] or ""),
                fabricante_id=str(state["fabricante_id"] or ""),
                familia_id=str(state["familia_id"] or ""),
                subfamilia_id=str(state["subfamilia_id"] or ""),
            )
        return self.sales_summary_service.listar_resumen_anual(
            year=year,
            month=month,
            acumulado=acumulado,
            cliente_id=str(state["cliente_id"] or ""),
            cliente_texto=str(state["cliente_texto"] or ""),
            articulo_id="",
            producto_texto=str(state["producto_texto"] or ""),
            fabricante_id=str(state["fabricante_id"] or ""),
            familia_id=str(state["familia_id"] or ""),
            subfamilia_id=str(state["subfamilia_id"] or ""),
        )

    def _sales_export_sort_rows(self, rows: list[SalesComparisonRow], sort_by: str, direction: str) -> None:
        reverse = direction == "desc"
        metric_map = {
            "codigo": lambda row: str(row.codigo or "").strip().lower(),
            "nombre": lambda row: str(row.nombre or "").strip().lower(),
            "kilos_prev": lambda row: float(row.kilos_prev or 0.0),
            "sc_prev": lambda row: float(row.sc_prev or 0.0),
            "ventas_prev": lambda row: float(row.ventas_prev or 0.0),
            "kilos_curr": lambda row: float(row.kilos_curr or 0.0),
            "sc_curr": lambda row: float(row.sc_curr or 0.0),
            "ventas_curr": lambda row: float(row.ventas_curr or 0.0),
            "delta_kg": lambda row: float(row.delta_kg or 0.0),
            "delta_kg_pct": lambda row: float(row.delta_kg_pct or 0.0),
            "delta_ventas": lambda row: float(row.delta_ventas or 0.0),
            "delta_ventas_pct": lambda row: float(row.delta_ventas_pct or 0.0),
        }
        primary = metric_map.get(sort_by, metric_map["ventas_curr"])
        rows.sort(
            key=lambda row: (
                primary(row),
                str(row.nombre or "").strip().lower(),
                str(row.codigo or "").strip().lower(),
            ),
            reverse=reverse,
        )

    def _sales_export_group_maps(self, source_key: str) -> dict[str, dict[str, str]]:
        if source_key == "igsa":
            manufacturers = self.sales_summary_service.list_filter_manufacturers_igsa()
            families = self.sales_summary_service.list_filter_families_igsa("")
            subfamilies = self.sales_summary_service.list_filter_subfamilies_igsa("")
            clients = []
        elif source_key == "clientes":
            manufacturers = self.sales_summary_service.list_filter_manufacturers()
            families = self.sales_summary_service.list_filter_families("")
            subfamilies = self.sales_summary_service.list_filter_subfamilies("")
            clients = self.sales_summary_service.list_filter_clients_indirect()
        else:
            manufacturers = self.sales_summary_service.list_filter_manufacturers()
            families = self.sales_summary_service.list_filter_families("")
            subfamilies = self.sales_summary_service.list_filter_subfamilies("")
            clients = self.sales_summary_service.list_filter_clients()

        def build_map(rows, id_attr: str, label_attr: str) -> dict[str, str]:
            result: dict[str, str] = {}
            for row in rows:
                key = str(getattr(row, id_attr, "") or "").strip()
                if not key:
                    continue
                label = str(getattr(row, label_attr, "") or "").strip() or key
                result[key] = label
            return result

        def build_client_map(rows) -> dict[str, str]:
            result: dict[str, str] = {}
            for row in rows:
                key = str(getattr(row, "cliente_id", "") or "").strip()
                if not key:
                    continue
                label = str(
                    getattr(row, "cliente_nombre_comercial", "") or getattr(row, "cliente_nombre_fiscal", "") or key
                ).strip()
                result[key] = label or key
            return result

        return {
            "client": build_client_map(clients),
            "manufacturer": build_map(manufacturers, "fabricante_id", "fabricante_nombre"),
            "family": build_map(families, "articulo_familia_id", "articulo_familia_nombre"),
            "subfamily": build_map(subfamilies, "articulo_subfamilia_id", "articulo_subfamilia_nombre"),
        }

    def _sales_export_group_section_title(self, group_by: str, label: str, month: int | None = None, acumulado: bool = False) -> str:
        if group_by == "month" and month is not None:
            month_label = self._sales_export_month_label(month)
            return f"{month_label} (acumulado)" if acumulado else month_label
        prefix = self._sales_export_group_label(group_by)
        return f"{prefix}: {label}" if label else prefix

    def _sales_export_sections(
        self,
        state: dict[str, object],
        options: dict[str, object],
    ) -> tuple[list[tuple[str, list[SalesComparisonRow]]], list[SalesComparisonRow], str]:
        group_by = str(options["group_by"] or "none")
        sort_by = str(options["sort_by"] or "ventas_curr")
        direction = str(options["direction"] or "desc")
        acumulado = bool(state["acumulado"])
        source_key = str(state["source_key"] or "")
        sections: list[tuple[str, list[SalesComparisonRow]]] = []
        grand_rows: list[SalesComparisonRow] = []
        grand_total_label = "TOTAL GENERAL"
        maps = self._sales_export_group_maps(source_key)

        if group_by == "month":
            months = self._sales_export_months(int(state["month"] or 0), acumulado)
            for month in months:
                rows = self._sales_export_load_rows(state, month=month)
                self._sales_export_sort_rows(rows, sort_by, direction)
                sections.append((self._sales_export_group_section_title("month", "", month, acumulado), rows))
            if months:
                if acumulado:
                    grand_rows = list(sections[-1][1])
                    grand_total_label = f"TOTAL HASTA {self._sales_export_month_label(months[-1]).upper()}"
                else:
                    for _section_title, rows in sections:
                        grand_rows.extend(rows)
                    grand_total_label = "TOTAL GENERAL"
            return sections, grand_rows, grand_total_label

        rows = self._sales_export_load_rows(state, month=int(state["month"] or 0))
        self._sales_export_sort_rows(rows, sort_by, direction)
        grand_rows = list(rows)

        if group_by in {"manufacturer", "family", "subfamily"}:
            grouped: dict[str, list[SalesComparisonRow]] = {}
            for row in rows:
                if group_by == "manufacturer":
                    raw_id = str(row.fabricante_id or "").strip()
                    label = maps["manufacturer"].get(raw_id, raw_id or "Sin fabricante")
                elif group_by == "family":
                    raw_id = str(row.familia_id or "").strip()
                    label = maps["family"].get(raw_id, raw_id or "Sin familia")
                else:
                    raw_id = str(row.subfamilia_id or "").strip()
                    label = maps["subfamily"].get(raw_id, raw_id or "Sin subfamilia")
                grouped.setdefault(label, []).append(row)

            def sort_label(label: str) -> tuple[int, str]:
                fallback = label.startswith("Sin ")
                return (1 if fallback else 0, label.casefold())

            for label in sorted(grouped.keys(), key=sort_label):
                group_rows = grouped[label]
                self._sales_export_sort_rows(group_rows, sort_by, direction)
                sections.append((self._sales_export_group_section_title(group_by, label), group_rows))
        else:
            sections.append(("Resultados", rows))

        return sections, grand_rows, grand_total_label

    def _sales_export_totals(self, rows: list[SalesComparisonRow]) -> dict[str, float]:
        totals = {
            "kilos_prev": 0.0,
            "sc_prev": 0.0,
            "ventas_prev": 0.0,
            "kilos_curr": 0.0,
            "sc_curr": 0.0,
            "ventas_curr": 0.0,
        }
        for row in rows:
            totals["kilos_prev"] += float(row.kilos_prev or 0.0)
            totals["sc_prev"] += float(row.sc_prev or 0.0)
            totals["ventas_prev"] += float(row.ventas_prev or 0.0)
            totals["kilos_curr"] += float(row.kilos_curr or 0.0)
            totals["sc_curr"] += float(row.sc_curr or 0.0)
            totals["ventas_curr"] += float(row.ventas_curr or 0.0)
        return totals

    def _write_sales_export_workbook(
        self,
        *,
        path: str,
        title: str,
        subtitle: str,
        sections: list[tuple[str, list[SalesComparisonRow]]],
        grand_rows: list[SalesComparisonRow],
        grand_total_label: str,
        group_by: str,
        sort_by: str,
        direction: str,
        include_subtotals: bool,
    ) -> Path:
        headers = [
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
        wb = Workbook()
        ws = wb.active
        ws.title = f"{self._sales_export_group_label(group_by)} {str(title.split()[-1]) if title.split() else ''}"[:31]
        ws.sheet_view.showGridLines = False

        title_fill = PatternFill("solid", fgColor="1F3A5F")
        section_fill = PatternFill("solid", fgColor="E8EEF7")
        header_fill = PatternFill("solid", fgColor="D9E5F4")
        subtotal_fill = PatternFill("solid", fgColor="F3F7FC")
        grand_fill = PatternFill("solid", fgColor="D7E3F4")
        border = Border(
            left=Side(style="thin", color="C9D1DC"),
            right=Side(style="thin", color="C9D1DC"),
            top=Side(style="thin", color="C9D1DC"),
            bottom=Side(style="thin", color="C9D1DC"),
        )

        text_widths = [len(header) for header in headers]

        def set_row_style(row_idx: int, *, fill: PatternFill | None = None, bold: bool = False, font_color: str = "FF111827") -> None:
            for col_idx in range(1, 13):
                cell = ws.cell(row=row_idx, column=col_idx)
                cell.border = border
                if fill is not None:
                    cell.fill = fill
                cell.font = Font(bold=bold, color=font_color)
                if col_idx >= 3:
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="center")

        def write_spanned_row(text: str, fill: PatternFill, bold: bool = True, font_color: str = "111827") -> None:
            row_idx = ws.max_row + 1
            ws.append([text] + [""] * 11)
            ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=12)
            cell = ws.cell(row=row_idx, column=1)
            cell.fill = fill
            cell.border = border
            cell.font = Font(bold=bold, color=font_color)
            cell.alignment = Alignment(horizontal="left", vertical="center")
            text_widths[0] = max(text_widths[0], len(text))

        def update_widths(values: list[str]) -> None:
            for idx, value in enumerate(values):
                text_widths[idx] = max(text_widths[idx], len(str(value or "")))

        def write_column_header() -> None:
            header_row = ws.max_row + 1
            ws.append(headers)
            update_widths(headers)
            for col_idx in range(1, 13):
                cell = ws.cell(row=header_row, column=col_idx)
                cell.border = border
                cell.fill = header_fill
                cell.font = Font(bold=True, color="FF111827")
                cell.alignment = Alignment(horizontal="left" if col_idx <= 2 else "right", vertical="center")

        def write_data_row(row: SalesComparisonRow) -> None:
            row_idx = ws.max_row + 1
            values = [
                str(row.codigo or ""),
                str(row.nombre or ""),
                float(row.kilos_prev or 0.0),
                float(row.sc_prev or 0.0),
                float(row.ventas_prev or 0.0),
                float(row.kilos_curr or 0.0),
                float(row.sc_curr or 0.0),
                float(row.ventas_curr or 0.0),
                float(row.delta_kg or 0.0),
                float(row.delta_kg_pct or 0.0),
                float(row.delta_ventas or 0.0),
                float(row.delta_ventas_pct or 0.0),
            ]
            display_values = [
                values[0],
                values[1],
                self._fmt_num(values[2]),
                self._fmt_num(values[3]),
                self._fmt_money(values[4]),
                self._fmt_num(values[5]),
                self._fmt_num(values[6]),
                self._fmt_money(values[7]),
                self._fmt_num(values[8]),
                self._fmt_pct(values[9]),
                self._fmt_money(values[10]),
                self._fmt_pct(values[11]),
            ]
            ws.append(values)
            update_widths(display_values)
            for col_idx, _display in enumerate(display_values, start=1):
                cell = ws.cell(row=row_idx, column=col_idx)
                cell.border = border
                if col_idx <= 2:
                    cell.alignment = Alignment(horizontal="left", vertical="center")
                else:
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                if col_idx == 9 and float(row.delta_kg or 0.0) != 0.0:
                    cell.font = Font(color="FF067647")
                elif col_idx == 10 and float(row.delta_kg_pct or 0.0) != 0.0:
                    cell.font = Font(color="FF067647" if float(row.delta_kg_pct or 0.0) > 0 else "FFB42318")
                elif col_idx == 11 and float(row.delta_ventas or 0.0) != 0.0:
                    cell.font = Font(color="FF067647" if float(row.delta_ventas or 0.0) > 0 else "FFB42318")
                elif col_idx == 12 and float(row.delta_ventas_pct or 0.0) != 0.0:
                    cell.font = Font(color="FF067647" if float(row.delta_ventas_pct or 0.0) > 0 else "FFB42318")
                else:
                    cell.font = Font(color="FF111827")
                if col_idx == 3:
                    cell.number_format = '#,##0.00'
                elif col_idx == 4:
                    cell.number_format = '#,##0.00'
                elif col_idx == 5:
                    cell.number_format = '#,##0.00 "€"'
                elif col_idx == 6:
                    cell.number_format = '#,##0.00'
                elif col_idx == 7:
                    cell.number_format = '#,##0.00'
                elif col_idx == 8:
                    cell.number_format = '#,##0.00 "€"'
                elif col_idx == 9:
                    cell.number_format = '#,##0.00'
                elif col_idx in {10, 12}:
                    cell.number_format = '0.00"%"'
                elif col_idx == 11:
                    cell.number_format = '#,##0.00 "€"'

        def write_totals_row(label: str, rows: list[SalesComparisonRow], fill: PatternFill) -> None:
            totals = self._sales_export_totals(rows)
            prev_total_kg = totals["kilos_prev"] + totals["sc_prev"]
            curr_total_kg = totals["kilos_curr"] + totals["sc_curr"]
            delta_kg = curr_total_kg - prev_total_kg
            delta_sales = totals["ventas_curr"] - totals["ventas_prev"]
            delta_kg_pct = 0.0 if abs(prev_total_kg) <= 1e-9 else delta_kg / prev_total_kg * 100.0
            delta_sales_pct = 0.0 if abs(totals["ventas_prev"]) <= 1e-9 else delta_sales / totals["ventas_prev"] * 100.0
            row_idx = ws.max_row + 1
            values = [
                label,
                "",
                totals["kilos_prev"],
                totals["sc_prev"],
                totals["ventas_prev"],
                totals["kilos_curr"],
                totals["sc_curr"],
                totals["ventas_curr"],
                delta_kg,
                delta_kg_pct,
                delta_sales,
                delta_sales_pct,
            ]
            display_values = [
                label,
                "",
                self._fmt_num(values[2]),
                self._fmt_num(values[3]),
                self._fmt_money(values[4]),
                self._fmt_num(values[5]),
                self._fmt_num(values[6]),
                self._fmt_money(values[7]),
                self._fmt_num(values[8]),
                self._fmt_pct(values[9]),
                self._fmt_money(values[10]),
                self._fmt_pct(values[11]),
            ]
            ws.append(values)
            update_widths(display_values)
            for col_idx in range(1, 13):
                cell = ws.cell(row=row_idx, column=col_idx)
                cell.border = border
                cell.fill = fill
                cell.font = Font(bold=True, color="FF111827")
                cell.alignment = Alignment(horizontal="right" if col_idx >= 3 else "left", vertical="center")
                if col_idx in {3, 4, 6, 7, 9}:
                    cell.number_format = '#,##0.00'
                elif col_idx in {5, 8, 11}:
                    cell.number_format = '#,##0.00 "€"'
                elif col_idx in {10, 12}:
                    cell.number_format = '0.00"%"'

        write_spanned_row(title, title_fill, True, "FFFFFFFF")
        write_spanned_row(subtitle, PatternFill("solid", fgColor="F8FAFC"), False, "FF4B5563")
        ws.append([""] * 12)

        for section_title, rows in sections:
            if not rows:
                continue
            write_spanned_row(section_title, section_fill, True, "FF111827")
            header_row = ws.max_row + 1
            ws.append(headers)
            update_widths(headers)
            set_row_style(header_row, fill=header_fill, bold=True, font_color="FF111827")
            for row in rows:
                write_data_row(row)
            if include_subtotals and group_by != "none":
                write_totals_row(f"TOTAL {section_title}", rows, subtotal_fill)
            ws.append([""] * 12)

        if grand_rows:
            write_totals_row(grand_total_label, grand_rows, grand_fill)

        for idx, width in enumerate(text_widths, start=1):
            ws.column_dimensions[get_column_letter(idx)].width = min(max(width + 2, 10), 42 if idx != 2 else 48)

        ws.freeze_panes = "A4"
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        wb.save(out)
        return out

    def _sales_export_group_level_label(self, key: str) -> str:
        return {
            "month": "Mes",
            "client": "Cliente",
            "manufacturer": "Fabricante",
            "family": "Familia",
            "subfamily": "Subfamilia",
        }.get(key, key)

    def _sales_export_group_levels_label(self, keys: list[str]) -> str:
        levels = [self._sales_export_group_level_label(key) for key in keys if str(key or "").strip()]
        return " > ".join(levels) if levels else "Sin agrupar"

    def _sales_export_group_value_label(
        self,
        level: str,
        row: SalesExportRow,
        group_maps: dict[str, dict[str, str]],
    ) -> str:
        if level == "client":
            raw = str(row.cliente_id or "").strip()
            label = str(row.cliente_nombre or "").strip() or group_maps.get("client", {}).get(raw, "")
            return str(label or raw or "Sin cliente").strip() or "Sin cliente"
        if level == "manufacturer":
            raw = str(row.fabricante_id or "").strip()
            return group_maps["manufacturer"].get(raw, raw or "Sin fabricante")
        if level == "family":
            raw = str(row.familia_id or "").strip()
            return group_maps["family"].get(raw, raw or "Sin familia")
        if level == "subfamily":
            raw = str(row.subfamilia_id or "").strip()
            return group_maps["subfamily"].get(raw, raw or "Sin subfamilia")
        return ""

    def _sales_export_selected_levels(self, state: dict[str, object], levels: list[str]) -> list[str]:
        allowed = {"month", "manufacturer", "family", "subfamily"}
        if bool(state.get("customer_groupable", False)):
            allowed.add("client")
        ordered = ["month", "client", "manufacturer", "family", "subfamily"]
        requested = {str(level or "").strip() for level in levels}
        return [level for level in ordered if level in requested and level in allowed]

    def _sales_export_rows_igsa_v2(self, state: dict[str, object], month: int) -> list[SalesExportRow]:
        rows = self.sales_summary_service.listar_resumen_anual_igsa(
            year=int(state["year"] or 0),
            month=month,
            acumulado=bool(state["acumulado"]),
            producto_texto=str(state["producto_texto"] or ""),
            fabricante_id=str(state["fabricante_id"] or ""),
            familia_id=str(state["familia_id"] or ""),
            subfamilia_id=str(state["subfamilia_id"] or ""),
        )
        result: list[SalesExportRow] = []
        for row in rows:
            result.append(
                SalesExportRow(
                    cliente_id="",
                    cliente_nombre="",
                    articulo_id=str(row.articulo_id or ""),
                    codigo=str(row.codigo or ""),
                    nombre=str(row.nombre or ""),
                    fabricante_id=str(row.fabricante_id or ""),
                    familia_id=str(row.familia_id or ""),
                    subfamilia_id=str(row.subfamilia_id or ""),
                    kilos_prev=float(row.kilos_prev or 0.0),
                    sc_prev=float(row.sc_prev or 0.0),
                    ventas_prev=float(row.ventas_prev or 0.0),
                    kilos_curr=float(row.kilos_curr or 0.0),
                    sc_curr=float(row.sc_curr or 0.0),
                    ventas_curr=float(row.ventas_curr or 0.0),
                    delta_kg=float(row.delta_kg or 0.0),
                    delta_kg_pct=float(row.delta_kg_pct or 0.0),
                    delta_ventas=float(row.delta_ventas or 0.0),
                    delta_ventas_pct=float(row.delta_ventas_pct or 0.0),
                )
            )
        return result

    def _sales_export_rows_ireks_v2(self, state: dict[str, object], month: int, selected_levels: list[str]) -> list[SalesExportRow]:
        year = int(state["year"] or 0)
        if year <= 0:
            return []
        include_client = "client" in selected_levels
        cliente_id = str(state["cliente_id"] or "")
        filters = {
            "cliente_id": cliente_id,
            "cliente_texto": "",
            "articulo_id": "",
            "producto_texto": str(state["producto_texto"] or ""),
            "fabricante_id": str(state["fabricante_id"] or ""),
            "familia_id": str(state["familia_id"] or ""),
            "subfamilia_id": str(state["subfamilia_id"] or ""),
        }
        prev_rows = self.sales_summary_service.listar_detalle_ventas(
            year=year - 1,
            month=month,
            acumulado=bool(state["acumulado"]),
            **filters,
        )
        curr_rows = self.sales_summary_service.listar_detalle_ventas(
            year=year,
            month=month,
            acumulado=bool(state["acumulado"]),
            **filters,
        )
        buckets: dict[tuple[str, str], dict[str, object]] = {}
        client_map = {
            str(client.cliente_id or "").strip(): str(
                client.cliente_nombre_comercial or client.cliente_nombre_fiscal or client.cliente_id or ""
            ).strip()
            for client in self.sales_summary_service.list_filter_clients()
            if str(client.cliente_id or "").strip()
        }

        def ensure_bucket(row: SalesDetailRow, suffix: str) -> dict[str, object]:
            client_id = str(row.cliente_id or "").strip() if include_client else ""
            product_id = str(row.articulo_id or "").strip() or str(row.codigo or "").strip() or str(row.nombre or "").strip()
            key = (client_id, product_id)
            bucket = buckets.setdefault(
                key,
                {
                    "cliente_id": client_id,
                    "cliente_nombre": str(row.cliente_nombre or client_map.get(client_id, "") or "").strip() if include_client else "",
                    "articulo_id": product_id,
                    "codigo": str(row.codigo or "").strip(),
                    "nombre": str(row.nombre or "").strip(),
                    "fabricante_id": str(row.fabricante_id or "").strip(),
                    "familia_id": str(row.familia_id or "").strip(),
                    "subfamilia_id": str(row.subfamilia_id or "").strip(),
                    "kilos_prev": 0.0,
                    "sc_prev": 0.0,
                    "ventas_prev": 0.0,
                    "kilos_curr": 0.0,
                    "sc_curr": 0.0,
                    "ventas_curr": 0.0,
                },
            )
            if include_client and not str(bucket["cliente_nombre"] or "").strip():
                bucket["cliente_nombre"] = str(row.cliente_nombre or client_map.get(client_id, "") or row.cliente_id or "").strip()
            if not str(bucket["codigo"] or "").strip():
                bucket["codigo"] = str(row.codigo or "").strip()
            if not str(bucket["nombre"] or "").strip():
                bucket["nombre"] = str(row.nombre or "").strip()
            if not str(bucket["fabricante_id"] or "").strip():
                bucket["fabricante_id"] = str(row.fabricante_id or "").strip()
            if not str(bucket["familia_id"] or "").strip():
                bucket["familia_id"] = str(row.familia_id or "").strip()
            if not str(bucket["subfamilia_id"] or "").strip():
                bucket["subfamilia_id"] = str(row.subfamilia_id or "").strip()
            return bucket

        for row in prev_rows:
            bucket = ensure_bucket(row, "prev")
            bucket["kilos_prev"] = float(bucket["kilos_prev"] or 0.0) + float(row.kilos or 0.0)
            bucket["sc_prev"] = float(bucket["sc_prev"] or 0.0) + float(row.sc or 0.0)
            bucket["ventas_prev"] = float(bucket["ventas_prev"] or 0.0) + float(row.ventas or 0.0)

        for row in curr_rows:
            bucket = ensure_bucket(row, "curr")
            bucket["kilos_curr"] = float(bucket["kilos_curr"] or 0.0) + float(row.kilos or 0.0)
            bucket["sc_curr"] = float(bucket["sc_curr"] or 0.0) + float(row.sc or 0.0)
            bucket["ventas_curr"] = float(bucket["ventas_curr"] or 0.0) + float(row.ventas or 0.0)

        result: list[SalesExportRow] = []
        client_map = {
            str(client.cliente_id or "").strip(): str(
                client.cliente_nombre_comercial or client.cliente_nombre_fiscal or client.cliente_id or ""
            ).strip()
            for client in self.sales_summary_service.list_filter_clients()
            if str(client.cliente_id or "").strip()
        }
        for values in buckets.values():
            kilos_prev = float(values["kilos_prev"] or 0.0)
            sc_prev = float(values["sc_prev"] or 0.0)
            ventas_prev = float(values["ventas_prev"] or 0.0)
            kilos_curr = float(values["kilos_curr"] or 0.0)
            sc_curr = float(values["sc_curr"] or 0.0)
            ventas_curr = float(values["ventas_curr"] or 0.0)
            total_prev = kilos_prev + sc_prev
            total_curr = kilos_curr + sc_curr
            delta_kg = total_curr - total_prev
            delta_ventas = ventas_curr - ventas_prev
            result.append(
                SalesExportRow(
                    cliente_id=str(values["cliente_id"] or ""),
                    cliente_nombre=str(client_map.get(str(values["cliente_id"] or "").strip(), "") or values["cliente_nombre"] or ""),
                    articulo_id=str(values["articulo_id"] or ""),
                    codigo=str(values["codigo"] or ""),
                    nombre=str(values["nombre"] or ""),
                    fabricante_id=str(values["fabricante_id"] or ""),
                    familia_id=str(values["familia_id"] or ""),
                    subfamilia_id=str(values["subfamilia_id"] or ""),
                    kilos_prev=kilos_prev,
                    sc_prev=sc_prev,
                    ventas_prev=ventas_prev,
                    kilos_curr=kilos_curr,
                    sc_curr=sc_curr,
                    ventas_curr=ventas_curr,
                    delta_kg=delta_kg,
                    delta_kg_pct=self._sales_export_pct(delta_kg, total_prev),
                    delta_ventas=delta_ventas,
                    delta_ventas_pct=self._sales_export_pct(delta_ventas, ventas_prev),
                )
            )

        result.sort(
            key=lambda row: (
                str(row.cliente_nombre or "").strip().lower(),
                str(row.nombre or "").strip().lower(),
                str(row.codigo or "").strip().lower(),
            )
        )
        return result

    def _sales_export_pct(self, delta: float, base: float) -> float:
        if abs(float(base or 0.0)) <= 1e-9:
            return 0.0
        return float(delta or 0.0) / float(base or 0.0) * 100.0

    def _sales_export_rows_v2(self, state: dict[str, object], month: int, selected_levels: list[str]) -> list[SalesExportRow]:
        if str(state["source_key"] or "") == "igsa":
            return self._sales_export_rows_igsa_v2(state, month)
        return self._sales_export_rows_ireks_v2(state, month, selected_levels)

    def _sales_export_sections_v2(
        self,
        state: dict[str, object],
        options: dict[str, object],
    ) -> tuple[list[tuple[str, list[SalesExportRow]]], list[SalesExportRow], str]:
        selected_levels = self._sales_export_selected_levels(state, list(options.get("group_levels") or []))
        group_levels = [level for level in selected_levels if level != "month"]
        sections: list[tuple[str, list[SalesExportRow]]] = []
        grand_rows: list[SalesExportRow] = []
        grand_total_label = "TOTAL GENERAL"
        if "month" in selected_levels:
            months = self._sales_export_months(int(state["month"] or 0), bool(state["acumulado"]))
            for month in months:
                rows = self._sales_export_rows_v2(state, month, group_levels)
                self._sales_export_sort_rows(rows, str(options["sort_by"] or "ventas_curr"), str(options["direction"] or "desc"))
                sections.append(
                    (f"Mes: {self._sales_export_month_label(month)}" + (" (acumulado)" if bool(state["acumulado"]) else ""), rows)
                )
            if months:
                if bool(state["acumulado"]):
                    grand_rows = list(sections[-1][1])
                    grand_total_label = f"TOTAL HASTA {self._sales_export_month_label(months[-1]).upper()}"
                else:
                    for _section_title, rows in sections:
                        grand_rows.extend(rows)
                    grand_total_label = "TOTAL GENERAL"
            return sections, grand_rows, grand_total_label

        rows = self._sales_export_rows_v2(state, int(state["month"] or 0), group_levels)
        self._sales_export_sort_rows(rows, str(options["sort_by"] or "ventas_curr"), str(options["direction"] or "desc"))
        sections.append(("Resultados", rows))
        grand_rows = list(rows)
        return sections, grand_rows, grand_total_label

    def _write_sales_export_workbook_v2(
        self,
        *,
        path: str,
        title: str,
        subtitle: str,
        sections: list[tuple[str, list[SalesExportRow]]],
        grand_rows: list[SalesExportRow],
        grand_total_label: str,
        sort_by: str,
        direction: str,
        group_levels: list[str],
        include_subtotals: bool,
        state: dict[str, object],
    ) -> Path:
        headers = [
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
        wb = Workbook()
        ws = wb.active
        ws.title = f"{state['source_label']} {state['year']}"[:31]
        ws.sheet_view.showGridLines = False

        title_fill = PatternFill("solid", fgColor="1F3A5F")
        section_fill = PatternFill("solid", fgColor="E8EEF7")
        header_fill = PatternFill("solid", fgColor="D9E5F4")
        subtotal_fill = PatternFill("solid", fgColor="F3F7FC")
        grand_fill = PatternFill("solid", fgColor="D7E3F4")
        border = Border(
            left=Side(style="thin", color="C9D1DC"),
            right=Side(style="thin", color="C9D1DC"),
            top=Side(style="thin", color="C9D1DC"),
            bottom=Side(style="thin", color="C9D1DC"),
        )

        text_widths = [len(header) for header in headers]
        group_maps = self._sales_export_group_maps(str(state["source_key"] or ""))
        level_titles = {
            "month": "Mes",
            "client": "Cliente",
            "manufacturer": "Fabricante",
            "family": "Familia",
            "subfamily": "Subfamilia",
        }
        level_fills = {
            "month": PatternFill("solid", fgColor="DDEEFF"),
            "client": PatternFill("solid", fgColor="E4F4E8"),
            "manufacturer": PatternFill("solid", fgColor="FDECD7"),
            "family": PatternFill("solid", fgColor="F1E3FA"),
            "subfamily": PatternFill("solid", fgColor="FFE5D8"),
        }
        level_subtotal_fills = {
            "month": PatternFill("solid", fgColor="CFE3FF"),
            "client": PatternFill("solid", fgColor="D4EFD9"),
            "manufacturer": PatternFill("solid", fgColor="FBDDBF"),
            "family": PatternFill("solid", fgColor="E9D6F6"),
            "subfamily": PatternFill("solid", fgColor="FFD6C4"),
        }

        def write_spanned_row(text: str, fill: PatternFill, bold: bool = True, font_color: str = "FF111827") -> None:
            row_idx = ws.max_row + 1
            ws.append([text] + [""] * 11)
            ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=12)
            cell = ws.cell(row=row_idx, column=1)
            cell.fill = fill
            cell.border = border
            cell.font = Font(bold=bold, color=font_color)
            cell.alignment = Alignment(horizontal="left", vertical="center")
            text_widths[0] = max(text_widths[0], len(str(text or "")))

        def update_widths(values: list[str]) -> None:
            for idx, value in enumerate(values):
                text_widths[idx] = max(text_widths[idx], len(str(value or "")))

        def write_data_row(row: SalesExportRow) -> None:
            row_idx = ws.max_row + 1
            values = [
                str(row.codigo or ""),
                str(row.nombre or ""),
                float(row.kilos_prev or 0.0),
                float(row.sc_prev or 0.0),
                float(row.ventas_prev or 0.0),
                float(row.kilos_curr or 0.0),
                float(row.sc_curr or 0.0),
                float(row.ventas_curr or 0.0),
                float(row.delta_kg or 0.0),
                float(row.delta_kg_pct or 0.0),
                float(row.delta_ventas or 0.0),
                float(row.delta_ventas_pct or 0.0),
            ]
            display_values = [
                values[0],
                values[1],
                self._fmt_num(values[2]),
                self._fmt_num(values[3]),
                self._fmt_money(values[4]),
                self._fmt_num(values[5]),
                self._fmt_num(values[6]),
                self._fmt_money(values[7]),
                self._fmt_num(values[8]),
                self._fmt_pct(values[9]),
                self._fmt_money(values[10]),
                self._fmt_pct(values[11]),
            ]
            ws.append(values)
            update_widths(display_values)
            for col_idx in range(1, 13):
                cell = ws.cell(row=row_idx, column=col_idx)
                cell.border = border
                cell.alignment = Alignment(horizontal="left" if col_idx <= 2 else "right", vertical="center")
                if col_idx == 9:
                    metric = float(row.delta_kg or 0.0)
                    cell.font = Font(color="FF067647" if metric > 0 else "FFB42318" if metric < 0 else "FF111827")
                elif col_idx == 10:
                    metric = float(row.delta_kg_pct or 0.0)
                    cell.font = Font(color="FF067647" if metric > 0 else "FFB42318" if metric < 0 else "FF111827")
                elif col_idx == 11:
                    metric = float(row.delta_ventas or 0.0)
                    cell.font = Font(color="FF067647" if metric > 0 else "FFB42318" if metric < 0 else "FF111827")
                elif col_idx == 12:
                    metric = float(row.delta_ventas_pct or 0.0)
                    cell.font = Font(color="FF067647" if metric > 0 else "FFB42318" if metric < 0 else "FF111827")
                else:
                    cell.font = Font(color="FF111827")
                if col_idx in {3, 4, 6, 7, 9}:
                    cell.number_format = '#,##0.00'
                elif col_idx in {5, 8, 11}:
                    cell.number_format = '#,##0.00 "€"'
                elif col_idx in {10, 12}:
                    cell.number_format = '0.00"%"'

        def write_totals_row(label: str, rows: list[SalesExportRow], fill: PatternFill) -> None:
            totals = self._sales_export_totals(rows)
            prev_total_kg = totals["kilos_prev"] + totals["sc_prev"]
            curr_total_kg = totals["kilos_curr"] + totals["sc_curr"]
            delta_kg = curr_total_kg - prev_total_kg
            delta_sales = totals["ventas_curr"] - totals["ventas_prev"]
            delta_kg_pct = 0.0 if abs(prev_total_kg) <= 1e-9 else delta_kg / prev_total_kg * 100.0
            delta_sales_pct = 0.0 if abs(totals["ventas_prev"]) <= 1e-9 else delta_sales / totals["ventas_prev"] * 100.0
            row_idx = ws.max_row + 1
            values = [
                label,
                "",
                totals["kilos_prev"],
                totals["sc_prev"],
                totals["ventas_prev"],
                totals["kilos_curr"],
                totals["sc_curr"],
                totals["ventas_curr"],
                delta_kg,
                delta_kg_pct,
                delta_sales,
                delta_sales_pct,
            ]
            display_values = [
                label,
                "",
                self._fmt_num(values[2]),
                self._fmt_num(values[3]),
                self._fmt_money(values[4]),
                self._fmt_num(values[5]),
                self._fmt_num(values[6]),
                self._fmt_money(values[7]),
                self._fmt_num(values[8]),
                self._fmt_pct(values[9]),
                self._fmt_money(values[10]),
                self._fmt_pct(values[11]),
            ]
            ws.append(values)
            update_widths(display_values)
            for col_idx in range(1, 13):
                cell = ws.cell(row=row_idx, column=col_idx)
                cell.border = border
                cell.fill = fill
                cell.font = Font(bold=True, color="FF111827")
                cell.alignment = Alignment(horizontal="left" if col_idx <= 2 else "right", vertical="center")
                if col_idx == 9:
                    metric = float(delta_kg or 0.0)
                    cell.font = Font(bold=True, color="FF067647" if metric > 0 else "FFB42318" if metric < 0 else "FF111827")
                elif col_idx == 10:
                    metric = float(delta_kg_pct or 0.0)
                    cell.font = Font(bold=True, color="FF067647" if metric > 0 else "FFB42318" if metric < 0 else "FF111827")
                elif col_idx == 11:
                    metric = float(delta_sales or 0.0)
                    cell.font = Font(bold=True, color="FF067647" if metric > 0 else "FFB42318" if metric < 0 else "FF111827")
                elif col_idx == 12:
                    metric = float(delta_sales_pct or 0.0)
                    cell.font = Font(bold=True, color="FF067647" if metric > 0 else "FFB42318" if metric < 0 else "FF111827")
                if col_idx in {3, 4, 6, 7, 9}:
                    cell.number_format = '#,##0.00'
                elif col_idx in {5, 8, 11}:
                    cell.number_format = '#,##0.00 "€"'
                elif col_idx in {10, 12}:
                    cell.number_format = '0.00"%"'

        def write_group_rows(rows: list[SalesExportRow], levels: list[str]) -> list[SalesExportRow]:
            while levels and levels[0] == "month":
                levels = levels[1:]
            if not levels:
                header_row = ws.max_row + 1
                ws.append(headers)
                update_widths(headers)
                for col_idx in range(1, 13):
                    cell = ws.cell(row=header_row, column=col_idx)
                    cell.border = border
                    cell.fill = header_fill
                    cell.font = Font(bold=True, color="FF111827")
                    cell.alignment = Alignment(horizontal="left" if col_idx <= 2 else "right", vertical="center")
                self._sales_export_sort_rows(rows, sort_by, direction)
                for row in rows:
                    write_data_row(row)
                return rows

            level = levels[0]
            grouped: dict[str, list[SalesExportRow]] = {}
            order: list[str] = []
            for row in rows:
                label = self._sales_export_group_value_label(level, row, group_maps)
                if label not in grouped:
                    grouped[label] = []
                    order.append(label)
                grouped[label].append(row)

            def sort_label(label: str) -> tuple[int, str]:
                return (1 if str(label or "").startswith("Sin ") else 0, str(label or "").casefold())

            total_rows: list[SalesExportRow] = []
            for label in sorted(order, key=sort_label):
                if not str(label or "").strip():
                    child_rows = write_group_rows(grouped[label], levels[1:])
                    total_rows.extend(child_rows)
                    continue
                level_fill = level_fills.get(level, section_fill)
                subtotal_level_fill = level_subtotal_fills.get(level, subtotal_fill)
                write_spanned_row(f"{level_titles.get(level, level.title())}: {label}", level_fill, True, "FF111827")
                child_rows = write_group_rows(grouped[label], levels[1:])
                total_rows.extend(child_rows)
                if include_subtotals:
                    write_totals_row(f"TOTAL {level_titles.get(level, level.title())}: {label}", child_rows, subtotal_level_fill)
            return total_rows

        write_spanned_row(title, title_fill, True, "FFFFFFFF")
        write_spanned_row(subtitle, PatternFill("solid", fgColor="F8FAFC"), False, "FF4B5563")
        ws.append([""] * 12)

        for section_title, rows in sections:
            if not rows:
                continue
            write_spanned_row(section_title, section_fill, True, "FF111827")
            section_leaf_rows = write_group_rows(rows, group_levels)
            if include_subtotals and group_levels:
                write_totals_row(f"TOTAL {section_title}", section_leaf_rows, subtotal_fill)
            ws.append([""] * 12)

        if grand_rows:
            write_totals_row(grand_total_label, grand_rows, grand_fill)

        for idx, width in enumerate(text_widths, start=1):
            ws.column_dimensions[get_column_letter(idx)].width = min(max(width + 2, 10), 42 if idx != 2 else 48)

        ws.freeze_panes = "A4"
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        wb.save(out)
        return out

    def _current_year(self) -> int:
        return int(self.year_filter.currentData() or 0)

    def _current_month(self) -> int:
        return int(self.month_filter.currentData() or 0)

    def _current_client_id(self) -> str:
        return str(self.client_filter.currentData() or "").strip()

    def _current_client_name(self) -> str:
        label = str(self.client_filter.currentText() or "").strip()
        if not label:
            return "Todos los clientes"
        if label.lower() == "todos":
            return "Todos los clientes"
        if label.endswith(")") and " (" in label:
            trimmed = label.rsplit(" (", 1)[0].strip()
            return trimmed or label
        return label

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
            if col in {0, 1}:
                self.group_header_igsa.setColumnWidth(col, self.sales_table_igsa.columnWidth(col))
            else:
                self.group_header_igsa.setColumnWidth(col, width)
            self.totals_table_igsa.setColumnWidth(col, width)
        self.group_header_igsa.setColumnWidth(0, self.sales_table_igsa.columnWidth(0))
        self.group_header_igsa.setColumnWidth(1, self.sales_table_igsa.columnWidth(1))
        self.totals_table_igsa.setColumnWidth(0, self.sales_table_igsa.columnWidth(0))
        self.totals_table_igsa.setColumnWidth(1, self.sales_table_igsa.columnWidth(1))

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

    def _current_year_clientes(self) -> int:
        return int(self.year_filter_clientes.currentData() or 0)

    def _current_month_clientes(self) -> int:
        return int(self.month_filter_clientes.currentData() or 0)

    def _current_client_id_clientes(self) -> str:
        return str(self._clientes_selected_client_id or "").strip()

    def _current_client_name_clientes(self) -> str:
        label = str(self._clientes_selected_client_name or "").strip()
        return label or "Todos los clientes"

    def _current_product_text_clientes(self) -> str:
        return str(self.product_filter_clientes.text() or "").strip()

    def _current_manufacturer_id_clientes(self) -> str:
        return str(self.manufacturer_filter_clientes.currentData() or "").strip()

    def _current_family_id_clientes(self) -> str:
        return str(self.family_filter_clientes.currentData() or "").strip()

    def _current_subfamily_id_clientes(self) -> str:
        return str(self.subfamily_filter_clientes.currentData() or "").strip()

    def _on_manufacturer_changed_clientes(self) -> None:
        if self._building_clientes:
            return
        self.family_filter_clientes.blockSignals(True)
        self.family_filter_clientes.setCurrentIndex(0 if self.family_filter_clientes.count() else -1)
        self.family_filter_clientes.blockSignals(False)
        self.subfamily_filter_clientes.blockSignals(True)
        self.subfamily_filter_clientes.setCurrentIndex(0 if self.subfamily_filter_clientes.count() else -1)
        self.subfamily_filter_clientes.blockSignals(False)
        self.product_filter_clientes.blockSignals(True)
        self.product_filter_clientes.clear()
        self.product_filter_clientes.blockSignals(False)
        self.reload_clientes()

    def _on_family_changed_clientes(self) -> None:
        if self._building_clientes:
            return
        self.subfamily_filter_clientes.blockSignals(True)
        self.subfamily_filter_clientes.setCurrentIndex(0 if self.subfamily_filter_clientes.count() else -1)
        self.subfamily_filter_clientes.blockSignals(False)
        self.product_filter_clientes.blockSignals(True)
        self.product_filter_clientes.clear()
        self.product_filter_clientes.blockSignals(False)
        self.reload_clientes()

    def _schedule_product_reload_clientes(self) -> None:
        if self._building_clientes:
            return
        self._product_filter_timer_clientes.start(250)

    def _set_clientes_client_selection(self, cliente_id: str, cliente_name: str, *, reload: bool = True) -> None:
        self._clientes_selected_client_id = str(cliente_id or "").strip()
        self._clientes_selected_client_name = str(cliente_name or "").strip() or "Todos los clientes"
        if hasattr(self, "client_filter_clientes_btn"):
            label = self._clientes_selected_client_name if self._clientes_selected_client_id else "Todos los clientes"
            self.client_filter_clientes_btn.setText(label)
            self.client_filter_clientes_btn.setToolTip(label)
        if hasattr(self, "client_filter_clientes_clear_btn"):
            self.client_filter_clientes_clear_btn.setEnabled(bool(self._clientes_selected_client_id))
        if reload and not self._building_clientes:
            self.reload_clientes()

    def _open_clientes_client_dialog(self) -> None:
        clients = self._build_clientes_selection_rows()
        dialog = SalesClientSelectDialog(
            clients,
            selected_client_id=self._current_client_id_clientes(),
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        cliente_id, cliente_name = dialog.selected_client()
        self._set_clientes_client_selection(cliente_id, cliente_name)

    def _clear_clientes_client_selection(self) -> None:
        self._set_clientes_client_selection("", "Todos los clientes")

    def _build_clientes_selection_rows(self) -> list[SalesClientSelectionRow]:
        clients = self.sales_summary_service.list_filter_clients_indirect()
        rows: list[SalesClientSelectionRow] = []
        for client in clients:
            cliente_id = str(getattr(client, "cliente_id", "") or "").strip()
            if not cliente_id:
                continue
            cliente_nombre = str(getattr(client, "cliente_nombre_comercial", "") or "").strip() or str(
                getattr(client, "cliente_nombre_fiscal", "") or ""
            ).strip()
            cliente_tipo = str(getattr(client, "cliente_tipo", "") or "").strip()
            search_text = self._normalize_clientes_search_text(
                " ".join(
                    [
                        cliente_id,
                        cliente_nombre,
                        cliente_tipo,
                        str(getattr(client, "cliente_nombre_fiscal", "") or ""),
                        str(getattr(client, "cliente_abreviatura", "") or ""),
                        str(getattr(client, "cliente_codigo", "") or ""),
                    ]
                )
            )
            rows.append(
                SalesClientSelectionRow(
                    cliente_id=cliente_id,
                    cliente_nombre=cliente_nombre or cliente_id,
                    cliente_tipo=cliente_tipo,
                    search_text=search_text,
                )
            )
        rows.sort(key=lambda row: (row.cliente_nombre.casefold(), row.cliente_id.casefold()))
        return rows

    def _normalize_clientes_search_text(self, text: str) -> str:
        cleaned = unicodedata.normalize("NFKD", str(text or ""))
        return "".join(ch for ch in cleaned if not unicodedata.combining(ch)).casefold().strip()

    def reload_clientes(self) -> None:
        if self._building_clientes:
            return
        self._building_clientes = True
        try:
            self._reload_filters_clientes()
            year = self._current_year_clientes()
            if year <= 0:
                self.sales_table_clientes.setRowCount(0)
                self._fill_group_headers_clientes(date.today().year)
                self._fill_totals_row_clientes(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
                return
            rows = self.sales_summary_service.listar_resumen_anual_clientes(
                year=year,
                cliente_id=self._current_client_id_clientes(),
                producto_texto=self._current_product_text_clientes(),
                fabricante_id=self._current_manufacturer_id_clientes(),
                familia_id=self._current_family_id_clientes(),
                subfamilia_id=self._current_subfamily_id_clientes(),
            )
            self._fill_sales_clientes(rows, year)
        finally:
            self._building_clientes = False

    def _reload_filters_clientes(self) -> None:
        current_year = self._current_year_clientes()
        current_client_id = self._current_client_id_clientes()
        current_manufacturer_id = self._current_manufacturer_id_clientes()
        current_family_id = self._current_family_id_clientes()
        current_subfamily_id = self._current_subfamily_id_clientes()

        years = self.sales_summary_service.list_years_clientes()
        if not years:
            years = [date.today().year]
        clients = self.sales_summary_service.list_filter_clients_indirect()
        client_ids = {
            str(getattr(client, "cliente_id", "") or "").strip()
            for client in clients
            if str(getattr(client, "cliente_id", "") or "").strip()
        }
        if current_client_id and current_client_id not in client_ids:
            current_client_id = ""
            self._set_clientes_client_selection("", "Todos los clientes", reload=False)
        manufacturers = self.sales_summary_service.list_filter_manufacturers()
        families = self.sales_summary_service.list_filter_families(current_manufacturer_id)
        family_ids = {str(getattr(row, "articulo_familia_id", "") or "").strip() for row in families}
        effective_family_id = current_family_id if current_family_id in family_ids else ""
        subfamilies = self.sales_summary_service.list_filter_subfamilies(effective_family_id)
        subfamily_ids = {str(getattr(row, "articulo_subfamilia_id", "") or "").strip() for row in subfamilies}
        effective_subfamily_id = current_subfamily_id if current_subfamily_id in subfamily_ids else ""

        self.year_filter_clientes.blockSignals(True)
        self.year_filter_clientes.clear()
        for year in years:
            self.year_filter_clientes.addItem(str(year), int(year))
        idx = self.year_filter_clientes.findData(current_year if current_year else years[0])
        self.year_filter_clientes.setCurrentIndex(idx if idx >= 0 else 0)
        self.year_filter_clientes.blockSignals(False)

        self.month_filter_clientes.blockSignals(True)
        self.month_filter_clientes.clear()
        self.month_filter_clientes.addItem("Todos", 0)
        for month, label in enumerate(MONTH_NAMES, start=1):
            self.month_filter_clientes.addItem(label, month)
        self.month_filter_clientes.setCurrentIndex(0)
        self.month_filter_clientes.blockSignals(False)

        self.manufacturer_filter_clientes.blockSignals(True)
        self.manufacturer_filter_clientes.clear()
        self.manufacturer_filter_clientes.addItem("Todos", "")
        for manufacturer in manufacturers:
            manufacturer_id = str(getattr(manufacturer, "fabricante_id", "") or "").strip()
            if not manufacturer_id:
                continue
            label = str(getattr(manufacturer, "fabricante_nombre", "") or "").strip() or manufacturer_id
            self.manufacturer_filter_clientes.addItem(label, manufacturer_id)
        mfg_idx = self.manufacturer_filter_clientes.findData(current_manufacturer_id)
        self.manufacturer_filter_clientes.setCurrentIndex(mfg_idx if mfg_idx >= 0 else 0)
        self.manufacturer_filter_clientes.blockSignals(False)

        self.family_filter_clientes.blockSignals(True)
        self.family_filter_clientes.clear()
        self.family_filter_clientes.addItem("Todas", "")
        for family in families:
            family_id = str(getattr(family, "articulo_familia_id", "") or "").strip()
            if not family_id:
                continue
            label = str(getattr(family, "articulo_familia_nombre", "") or "").strip() or family_id
            self.family_filter_clientes.addItem(label, family_id)
        f_idx = self.family_filter_clientes.findData(effective_family_id)
        self.family_filter_clientes.setCurrentIndex(f_idx if f_idx >= 0 else 0)
        self.family_filter_clientes.blockSignals(False)

        self.subfamily_filter_clientes.blockSignals(True)
        self.subfamily_filter_clientes.clear()
        self.subfamily_filter_clientes.addItem("Todas", "")
        for subfamily in subfamilies:
            subfamily_id = str(getattr(subfamily, "articulo_subfamilia_id", "") or "").strip()
            if not subfamily_id:
                continue
            label = str(getattr(subfamily, "articulo_subfamilia_nombre", "") or "").strip() or subfamily_id
            self.subfamily_filter_clientes.addItem(label, subfamily_id)
        s_idx = self.subfamily_filter_clientes.findData(effective_subfamily_id)
        self.subfamily_filter_clientes.setCurrentIndex(s_idx if s_idx >= 0 else 0)
        self.subfamily_filter_clientes.blockSignals(False)
        if hasattr(self, "client_filter_clientes_btn"):
            self.client_filter_clientes_btn.setText(self._current_client_name_clientes())
            self.client_filter_clientes_btn.setToolTip(self._current_client_name_clientes())
        if hasattr(self, "client_filter_clientes_clear_btn"):
            self.client_filter_clientes_clear_btn.setEnabled(bool(self._current_client_id_clientes()))

    def _sync_aux_column_width_clientes(self, logical_index: int, _old_size: int, new_size: int) -> None:
        self.group_header_clientes.setColumnWidth(logical_index, new_size)
        self.totals_table_clientes.setColumnWidth(logical_index, new_size)

    def _set_group_item_clientes(self, column: int, text: str, color: str, span: int = 1) -> None:
        if span > 1:
            self.group_header_clientes.setSpan(0, column, 1, span)
        self.group_header_clientes.setCellWidget(0, column, self._make_band_label(text, color))

    def _fill_group_headers_clientes(self, year: int) -> None:
        self.group_header_clientes.clearSpans()
        self.group_header_clientes.clearContents()
        for col in range(12):
            self.group_header_clientes.removeCellWidget(0, col)
            label = QLabel("")
            label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            if col in {0, 1}:
                label.setStyleSheet("background-color: transparent; border: none; padding: 0;")
            else:
                label.setStyleSheet("background-color: #F3F6FA; border: 1px solid #000000; border-radius: 0; padding: 0;")
            self.group_header_clientes.setCellWidget(0, col, label)
        self._set_group_item_clientes(2, str(year - 1), "#3E5064", 3)
        self._set_group_item_clientes(5, str(year), "#0F766E", 3)
        self._set_group_item_clientes(8, "Diferencias", "#111827", 4)

    def _fill_sales_clientes(self, rows: list[SalesComparisonRow], year: int) -> None:
        self._fill_group_headers_clientes(year)
        self.sales_table_clientes.setSortingEnabled(False)
        self.sales_table_clientes.setRowCount(len(rows))
        total_prev_kg = 0.0
        total_prev_sc = 0.0
        total_curr_kg = 0.0
        total_curr_sc = 0.0
        total_prev_sales = 0.0
        total_curr_sales = 0.0

        for idx, row in enumerate(rows):
            total_prev_kg += row.kg_prev
            total_curr_kg += row.kg_curr
            total_prev_sales += row.euros_prev
            total_curr_sales += row.euros_curr

            values = [
                row.codigo,
                row.nombre,
                (self._fmt_num(row.kg_prev), row.kg_prev),
                "",
                (self._fmt_money(row.euros_prev), row.euros_prev),
                (self._fmt_num(row.kg_curr), row.kg_curr),
                "",
                (self._fmt_money(row.euros_curr), row.euros_curr),
                (self._fmt_num(row.delta_kg), row.delta_kg),
                (self._fmt_pct(row.delta_kg_pct), row.delta_kg_pct),
                (self._fmt_money(row.delta_euros), row.delta_euros),
                (self._fmt_pct(row.delta_euros_pct), row.delta_euros_pct),
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
                self.sales_table_clientes.setItem(idx, col, item)

        self.sales_table_clientes.setSortingEnabled(True)
        self._fill_totals_row_clientes(total_prev_kg, total_prev_sc, total_prev_sales, total_curr_kg, total_curr_sc, total_curr_sales)

    def _fill_totals_row_clientes(
        self,
        prev_kg: float,
        prev_sc: float,
        prev_sales: float,
        curr_kg: float,
        curr_sc: float,
        curr_sales: float,
    ) -> None:
        self.totals_table_clientes.clearSpans()
        self.totals_table_clientes.clearContents()
        for col in range(12):
            self.totals_table_clientes.removeCellWidget(0, col)

        prev_total_kg = prev_kg + prev_sc
        curr_total_kg = curr_kg + curr_sc
        delta_kg = curr_total_kg - prev_total_kg
        delta_sales = curr_sales - prev_sales
        delta_kg_pct = 0.0 if abs(prev_total_kg) <= 1e-9 else delta_kg / prev_total_kg * 100.0
        delta_sales_pct = 0.0 if abs(prev_sales) <= 1e-9 else delta_sales / prev_sales * 100.0
        self.totals_table_clientes.setSpan(0, 0, 1, 2)
        values = {
            2: (self._fmt_num(prev_kg), float(prev_kg or 0.0)),
            3: ("", 0.0),
            4: (self._fmt_money(prev_sales), float(prev_sales or 0.0)),
            5: (self._fmt_num(curr_kg), float(curr_kg or 0.0)),
            6: ("", 0.0),
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
        self.totals_table_clientes.setCellWidget(0, 0, total_label)
        self.totals_table_clientes.setCurrentCell(-1, -1)
        self.totals_table_clientes.clearSelection()
        self.totals_table_clientes.clearFocus()
        self.totals_table_clientes.viewport().clearFocus()

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
            self.totals_table_clientes.setItem(0, col, item)

    def _apply_column_widths_clientes(self) -> None:
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
            self.sales_table_clientes.setColumnWidth(col, width)
            if col in {0, 1}:
                self.group_header_clientes.setColumnWidth(col, self.sales_table_clientes.columnWidth(col))
            else:
                self.group_header_clientes.setColumnWidth(col, width)
            self.totals_table_clientes.setColumnWidth(col, width)
        self.group_header_clientes.setColumnWidth(0, self.sales_table_clientes.columnWidth(0))
        self.group_header_clientes.setColumnWidth(1, self.sales_table_clientes.columnWidth(1))
        self.totals_table_clientes.setColumnWidth(0, self.sales_table_clientes.columnWidth(0))
        self.totals_table_clientes.setColumnWidth(1, self.sales_table_clientes.columnWidth(1))

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
            if col in {0, 1}:
                self.group_header.setColumnWidth(col, self.sales_table.columnWidth(col))
            else:
                self.group_header.setColumnWidth(col, width)
            self.totals_table.setColumnWidth(col, width)
        self.group_header.setColumnWidth(0, self.sales_table.columnWidth(0))
        self.group_header.setColumnWidth(1, self.sales_table.columnWidth(1))
        self.totals_table.setColumnWidth(0, self.sales_table.columnWidth(0))
        self.totals_table.setColumnWidth(1, self.sales_table.columnWidth(1))
        self._sync_chart_actions_width()
        QTimer.singleShot(0, self._sync_chart_actions_width)

    def _sync_aux_column_width(self, logical_index: int, _old_size: int, new_size: int) -> None:
        if not hasattr(self, "group_header") or not hasattr(self, "totals_table"):
            return
        self.group_header.setColumnWidth(logical_index, new_size)
        self.totals_table.setColumnWidth(logical_index, new_size)
        if logical_index in {0, 1}:
            self._sync_chart_actions_width()

    def _sync_chart_actions_width(self) -> None:
        if not hasattr(self, "chart_actions_widget") or not hasattr(self, "sales_table"):
            return
        left_width = self.sales_table.columnWidth(0) + self.sales_table.columnWidth(1)
        widget_width = self.chart_actions_widget.sizeHint().width()
        left_width = max(left_width, widget_width)
        self.chart_actions_widget.setFixedWidth(left_width)
        self.chart_actions_widget.updateGeometry()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._sync_chart_actions_width()
        QTimer.singleShot(0, self._sync_chart_actions_width)

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
        has_year = self._current_year() > 0
        self.sales_chart_btn.setEnabled(self._selected_sales_row() is not None and has_year)
        self.sales_total_chart_btn.setEnabled(has_year)
        self.sales_analysis_btn.setEnabled(has_year)

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
        client_name = self._current_client_name()
        subtitle_parts = [part for part in [codigo, nombre, f"{year - 1} vs {year}"] if part]
        dialog = MonthlySalesDialog(
            title=f"Ventas mensuales {year - 1} / {year} | {client_name}",
            subtitle=" | ".join(subtitle_parts),
            points=points,
            parent=self,
        )
        dialog.exec()

    def _open_total_monthly_sales_dialog(self) -> None:
        year = self._current_year()
        if year <= 0:
            return
        points = self.sales_summary_service.listar_ventas_mensuales_ireks_totales_comparativa(
            year=year,
            cliente_id=self._current_client_id(),
        )
        client_name = self._current_client_name()
        dialog = MonthlySalesDialog(
            title=f"Ventas totales mensuales {year - 1} / {year} | {client_name}",
            subtitle=f"Todos los productos | {year - 1} vs {year}",
            points=points,
            parent=self,
        )
        dialog.exec()

    def _open_sales_analysis_dialog(self) -> None:
        year = self._current_year()
        if year <= 0:
            return
        client_name = self._current_client_name() or "Todos los clientes"
        dialog = SalesAnalysisDialog(
            title=f"Análisis de ventas {year} | {client_name}",
            defaults=self._build_sales_analysis_defaults(),
            sales_service=self.sales_summary_service,
            parent=self,
        )
        dialog.exec()

    def _build_sales_analysis_defaults(self) -> dict[str, object]:
        selected = self._selected_sales_row()
        client_id = self._current_client_id()
        client_name = self._current_client_name()
        product_text = self._current_product_text()
        manufacturer_id = self._current_manufacturer_id()
        family_id = self._current_family_id()
        subfamily_id = self._current_subfamily_id()
        defaults: dict[str, object] = {
            "year": self._current_year(),
            "month": self._current_month(),
            "acumulado": bool(getattr(self, "acumulado_check", None) and self.acumulado_check.isChecked()),
            "cliente_id": client_id,
            "cliente_texto": client_name if client_id else "",
            "articulo_id": selected[0] if selected is not None else "",
            "producto_texto": product_text,
            "fabricante_id": manufacturer_id,
            "familia_id": family_id,
            "subfamilia_id": subfamily_id,
            "limit": 200,
        }
        if client_name == "Todos los clientes":
            defaults["cliente_texto"] = ""
        if not product_text:
            defaults["producto_texto"] = ""
        return defaults

    def _fmt_num(self, value) -> str:
        number = float(value or 0.0)
        return f"{number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def _fmt_money(self, value) -> str:
        return f"{self._fmt_num(value)} €"

    def _fmt_pct(self, value) -> str:
        return f"{self._fmt_num(value)} %"

