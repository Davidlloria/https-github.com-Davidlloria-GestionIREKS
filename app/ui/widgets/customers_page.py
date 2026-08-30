from pathlib import Path
from datetime import date, datetime
import threading
import unicodedata
from uuid import uuid4

from PySide6.QtCore import QObject, QSize, QTimer, Qt, Signal, QStringListModel
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap, QTextCharFormat, QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QCompleter,
    QCalendarWidget,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QFormLayout,
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
    QSizePolicy,
    QSplitter,
    QStyle,
    QStyledItemDelegate,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolTip,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.exc import IntegrityError

try:
    import pyqtgraph as pg
except ModuleNotFoundError:  # pragma: no cover - dependency guard
    pg = None

from app.models import CodigoPostal, Cliente, Contacto, Isla, Localidad, Municipio, Provincia, Receta
from app.services.customer_report_document_helper import build_customer_report_html
from app.services.customer_ai_summary_service import CustomerAISummaryResult, CustomerAISummaryService
from app.services.customer_report_flow_service import CustomerReportFlowResult, CustomerReportFlowService
from app.services.customer_query_service import CustomerQueryService
from app.services.customer_service import CustomerService
from app.ui.widgets.customer_queries_dialog import CustomerQueriesDialog
from app.ui.widgets.customer_ai_summary_dialog import CustomerAISummaryDialog
from app.services.customer_report_service import CustomerReportIntentService, CustomerReportResult, CustomerReportService
from app.services.report_export_service import ReportExportService
from app.ui.widgets.action_ribbon import create_standard_ribbon_button, create_standard_top_ribbon
from app.ui.widgets.entity_dialog import EntityDialog

BASE_DIR = Path(__file__).resolve().parents[3]


class _CustomerAISummaryRunner(QObject):
    result_ready = Signal(str, object)
    failed = Signal(str, str)

    def start(self, token: str, service: CustomerAISummaryService, customer: object) -> None:
        threading.Thread(
            target=self._run,
            args=(token, service, customer),
            name="customer-ai-summary",
            daemon=True,
        ).start()

    def _run(self, token: str, service: CustomerAISummaryService, customer: object) -> None:
        try:
            self.result_ready.emit(token, service.summarize(customer))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(token, f"No se pudo generar el resumen.\n{exc}")


def _has_current_sales_activity(item: object) -> bool:
    """Return whether a comparison row has activity in the selected period."""
    return any(
        abs(float(getattr(item, field, 0.0) or 0.0)) > 1e-9
        for field in ("unidades_curr", "kg_curr", "euros_curr")
    )


class _NumericTableWidgetItem(QTableWidgetItem):
    """Table item that displays formatted text while sorting by its numeric value."""

    _SORT_ROLE = Qt.ItemDataRole.UserRole + 10

    def __init__(self, text: str, value: float) -> None:
        super().__init__(text)
        self.setData(self._SORT_ROLE, float(value))

    def __lt__(self, other: QTableWidgetItem) -> bool:
        if isinstance(other, _NumericTableWidgetItem):
            return float(self.data(self._SORT_ROLE) or 0.0) < float(other.data(self._SORT_ROLE) or 0.0)
        return super().__lt__(other)


class CustomerSalesComparisonChartDialog(QDialog):
    def __init__(self, *, rows: list, year: int, customer_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows = list(rows or [])
        self._year = int(year)
        self._hover_regions: list[dict[str, float | int]] = []
        self._tooltip_text = ""
        self._tooltip_global_position = None
        self._tooltip_refresh_timer = QTimer(self)
        self._tooltip_refresh_timer.setInterval(250)
        self._tooltip_refresh_timer.timeout.connect(self._refresh_tooltip)
        self.setWindowTitle("Gráfico comparativo de ventas")
        self.resize(980, 560)
        self.setMinimumSize(720, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        title = QLabel(f"Comparativa de ventas en kg · {customer_name}")
        title.setProperty("role", "sectionTitle")
        layout.addWidget(title)
        subtitle = QLabel(f"Productos · {self._year - 1} vs {self._year}")
        subtitle.setStyleSheet("color: #667085;")
        layout.addWidget(subtitle)

        if pg is None:
            unavailable = QLabel("No se puede mostrar el gráfico porque pyqtgraph no está instalado.")
            unavailable.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(unavailable, 1)
        else:
            self._plot = pg.PlotWidget(parent=self)
            self._configure_plot()
            layout.addWidget(self._plot, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _configure_plot(self) -> None:
        self._plot.setBackground("#FFFFFF")
        self._plot.setMenuEnabled(False)
        self._plot.setMouseEnabled(x=False, y=False)
        self._plot.setAntialiasing(True)
        self._plot.hideButtons()
        self._plot.showGrid(x=False, y=True, alpha=0.18)
        plot_item = self._plot.getPlotItem()
        plot_item.setLabel("left", "Kg")
        plot_item.setLabel("bottom", "Producto")
        plot_item.hideAxis("top")
        plot_item.hideAxis("right")

        positions = list(range(len(self._rows)))
        prev_values = [float(getattr(row, "kg_prev", 0.0) or 0.0) for row in self._rows]
        curr_values = [float(getattr(row, "kg_curr", 0.0) or 0.0) for row in self._rows]
        width = 0.34
        self._plot.addItem(
            pg.BarGraphItem(
                x=[position - 0.2 for position in positions],
                height=prev_values,
                width=width,
                brush=QColor("#98A2B3"),
                pen=QColor("#667085"),
            )
        )
        self._plot.addItem(
            pg.BarGraphItem(
                x=[position + 0.2 for position in positions],
                height=curr_values,
                width=width,
                brush=QColor("#0F766E"),
                pen=QColor("#0B5F59"),
            )
        )

        ticks = []
        for position, row, prev_value, curr_value in zip(positions, self._rows, prev_values, curr_values):
            label = str(getattr(row, "codigo", "") or getattr(row, "nombre", "") or position + 1).strip()
            ticks.append((position, label[:16]))
            self._hover_regions.extend(
                [
                    {"index": position, "x1": position - 0.2 - width / 2, "x2": position - 0.2 + width / 2, "value": prev_value},
                    {"index": position, "x1": position + 0.2 - width / 2, "x2": position + 0.2 + width / 2, "value": curr_value},
                ]
            )

        self._plot.getAxis("bottom").setTicks([ticks])
        self._plot.setXRange(-0.7, max(len(self._rows) - 0.3, 0.7), padding=0)
        legend = self._plot.addLegend(offset=(10, 10))
        legend.setBrush(QColor(255, 255, 255, 225))
        legend.setPen(QColor("#D0D5DD"))
        legend.addItem(pg.BarGraphItem(x=[0], height=[1], width=1, brush=QColor("#98A2B3")), str(self._year - 1))
        legend.addItem(pg.BarGraphItem(x=[0], height=[1], width=1, brush=QColor("#0F766E")), str(self._year))
        self._plot.scene().sigMouseMoved.connect(self._show_tooltip)

    def _show_tooltip(self, scene_pos) -> None:
        view_box = self._plot.getPlotItem().vb
        view_rect = view_box.sceneBoundingRect()
        if not view_rect.left() <= scene_pos.x() <= view_rect.right():
            self._clear_tooltip()
            return
        point = view_box.mapSceneToView(scene_pos)
        x_value = float(point.x())
        y_value = float(point.y())
        for region in self._hover_regions:
            height = float(region["value"])
            if float(region["x1"]) <= x_value <= float(region["x2"]) and 0 <= y_value <= height:
                row = self._rows[int(region["index"])]
                name = str(getattr(row, "nombre", "") or getattr(row, "codigo", "") or "Producto").strip()
                prev_text = self._format_kg(getattr(row, "kg_prev", 0.0))
                curr_text = self._format_kg(getattr(row, "kg_curr", 0.0))
                text = f"{name}\n{self._year - 1}: {prev_text} kg\n{self._year}: {curr_text} kg"
                self._display_tooltip(scene_pos, text)
                return
        product_index = self._product_index_at_x(x_value)
        if product_index is not None:
            row = self._rows[product_index]
            name = str(getattr(row, "nombre", "") or getattr(row, "codigo", "") or "Producto").strip()
            self._display_tooltip(scene_pos, name)
            return
        self._clear_tooltip()

    def _display_tooltip(self, scene_pos, text: str) -> None:
        self._tooltip_text = str(text or "")
        self._tooltip_global_position = self._tooltip_global_pos(scene_pos)
        QToolTip.showText(self._tooltip_global_position, self._tooltip_text, self._plot)
        self._tooltip_refresh_timer.start()

    def _refresh_tooltip(self) -> None:
        if not self._tooltip_text or self._tooltip_global_position is None:
            return
        QToolTip.showText(self._tooltip_global_position, self._tooltip_text, self._plot)

    def _clear_tooltip(self) -> None:
        self._tooltip_refresh_timer.stop()
        self._tooltip_text = ""
        self._tooltip_global_position = None
        QToolTip.hideText()

    def _tooltip_global_pos(self, scene_pos):
        local_pos = self._plot.mapFromScene(scene_pos)
        if hasattr(local_pos, "toPoint"):
            local_pos = local_pos.toPoint()
        return self._plot.mapToGlobal(local_pos)

    def _product_index_at_x(self, x_value: float) -> int | None:
        index = int(round(float(x_value)))
        if 0 <= index < len(self._rows) and abs(float(x_value) - index) <= 0.45:
            return index
        return None

    @staticmethod
    def _format_kg(value: float | int | None) -> str:
        number = float(value or 0.0)
        return f"{number:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")

    def leaveEvent(self, event) -> None:
        self._clear_tooltip()
        super().leaveEvent(event)


class NumericSortableTableWidgetItem(QTableWidgetItem):
    def __init__(self, text: str, numeric_value: float) -> None:
        super().__init__(text)
        self._numeric_value = float(numeric_value)

    def __lt__(self, other) -> bool:
        if isinstance(other, NumericSortableTableWidgetItem):
            return self._numeric_value < other._numeric_value
        return super().__lt__(other)


class CustomersCatalogSelectionDelegate(QStyledItemDelegate):
    """Paint the catalog selection accent without changing customer selection state."""

    def paint(self, painter: QPainter, option, index) -> None:  # type: ignore[override]
        super().paint(painter, option, index)
        if index.column() == 0 and option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect.x(), option.rect.y(), 3, option.rect.height(), QColor("#087E9C"))


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


class AgendaCalendarDelegate(QStyledItemDelegate):
    """Paint calendar headers and dates without losing Qt's text formats to QSS."""

    def paint(self, painter: QPainter, option, index) -> None:
        display = index.data(Qt.ItemDataRole.DisplayRole)
        if display is None:
            return

        is_header = index.row() == 0 or index.column() == 0
        is_selected = bool(option.state & QStyle.StateFlag.State_Selected) and not is_header
        background = index.data(Qt.ItemDataRole.BackgroundRole)
        foreground = index.data(Qt.ItemDataRole.ForegroundRole)
        if hasattr(background, "color"):
            background = background.color()
        if hasattr(foreground, "color"):
            foreground = foreground.color()
        if not isinstance(background, QColor) or not background.isValid():
            background = QColor("#FFFFFF")
        if not isinstance(foreground, QColor) or not foreground.isValid():
            foreground = QColor("#0F172A")

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        if is_header:
            painter.setBrush(background)
            painter.drawRoundedRect(option.rect.adjusted(2, 2, -2, -2), 4, 4)
        elif is_selected:
            painter.setBrush(QColor("#5B8DEF"))
            painter.drawRoundedRect(option.rect.adjusted(3, 2, -3, -2), 4, 4)
            foreground = QColor("#FFFFFF")
        else:
            painter.fillRect(option.rect, background)

        font = option.font
        font.setBold(is_header)
        painter.setFont(font)
        painter.setPen(foreground)
        painter.drawText(option.rect, Qt.AlignmentFlag.AlignCenter, str(display))
        painter.restore()


class CustomerEditorDialog(QDialog):
    _SECTOR_OPTIONS = [
        ("PANADERIA", "sectorChipPillPanaderia"),
        ("PASTELERIA", "sectorChipPillPasteleria"),
        ("HELADERIA", "sectorChipPillHeladeria"),
        ("CAFETERIA", "sectorChipPillCafeteria"),
        ("RESTAURANTE", "sectorChipPillRestaurante"),
        ("HOTEL", "sectorChipPillHotel"),
    ]

    def __init__(
        self,
        *,
        title: str,
        provincias: list[Provincia],
        islas: list[Isla],
        municipios: list[Municipio],
        codigos_postales: list[CodigoPostal],
        localidades: list[Localidad],
        initial: dict | None = None,
        style_sheet: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("customerEditorDialog")
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(958, 418)
        self._title = title
        self._initial = dict(initial or {})
        self._preserved_payload = {
            key: self._initial.get(key)
            for key in ("cliente_email", "cliente_nombre_interno", "distribuidor_id")
            if key in self._initial
        }
        self._provincias = list(provincias or [])
        self._islas = list(islas or [])
        self._municipios = list(municipios or [])
        self._codigos_postales = list(codigos_postales or [])
        self._localidades = list(localidades or [])
        self._is_loading = False
        self._base_style_sheet = style_sheet or ""

        self._build_ui()
        self._load_initial()

    def _build_ui(self) -> None:
        extra_style = """
            QDialog#customerEditorDialog {
                background: #EEF3F8;
            }
        """
        if self._base_style_sheet:
            self.setStyleSheet(self._base_style_sheet + "\n" + extra_style)
        else:
            self.setStyleSheet(extra_style)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel(self._title)
        title.setProperty("role", "pageTitle")
        layout.addWidget(title)

        cards_row = QHBoxLayout()
        cards_row.setContentsMargins(0, 0, 0, 0)
        cards_row.setSpacing(10)

        self.left_card = QFrame()
        self.left_card.setObjectName("detailLeftCard")
        self.left_card.setFixedSize(590, 300)
        left_layout = QVBoxLayout(self.left_card)
        left_layout.setContentsMargins(12, 10, 12, 12)
        left_layout.setSpacing(8)
        left_title = QLabel("Detalle de cliente")
        left_title.setProperty("role", "sectionTitle")
        left_layout.addWidget(left_title, 0)
        self.left_panel = self._build_left_panel()
        left_layout.addWidget(self.left_panel, 0)

        self.right_card = QFrame()
        self.right_card.setObjectName("detailRightCard")
        self.right_card.setFixedSize(300, 300)
        right_layout = QVBoxLayout(self.right_card)
        right_layout.setContentsMargins(12, 6, 12, 10)
        right_layout.setSpacing(2)
        right_title = QLabel("Clasificacion del cliente")
        right_title.setProperty("role", "sectionTitle")
        right_layout.addWidget(right_title, 0)
        self.right_panel = self._build_right_panel()
        right_layout.addWidget(self.right_panel, 0)

        cards_row.addStretch(1)
        cards_row.addWidget(self.left_card, 0)
        cards_row.addWidget(self.right_card, 0)
        cards_row.addStretch(1)
        layout.addLayout(cards_row)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(8)
        buttons.addStretch(1)

        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.setProperty("btnRole", "secondary")
        self.cancel_btn.setFixedWidth(120)
        self.cancel_btn.setAutoDefault(False)
        self.cancel_btn.setDefault(False)
        self.cancel_btn.clicked.connect(self.reject)

        self.save_btn = QPushButton("Guardar")
        self.save_btn.setProperty("btnRole", "primary")
        self.save_btn.setFixedWidth(120)
        self.save_btn.setAutoDefault(False)
        self.save_btn.setDefault(False)
        self.save_btn.clicked.connect(self.accept)

        buttons.addWidget(self.cancel_btn)
        buttons.addWidget(self.save_btn)
        layout.addLayout(buttons)

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("detailSubPanel")
        panel.setFixedSize(554, 246)

        self.lbl_cod = QLabel("Cod.", panel)
        self.codigo_edit = QLineEdit(panel)
        self.codigo_edit.setReadOnly(True)

        self.lbl_nombre_comercial = QLabel("Nombre Comercial", panel)
        self.nombre_comercial_edit = QLineEdit(panel)
        self.nombre_comercial_edit.setFixedHeight(28)

        self.lbl_telefono = QLabel("Telef.", panel)
        self.telefono_edit = QLineEdit(panel)
        self.telefono_edit.editingFinished.connect(self._format_phone_field)

        self.lbl_cif = QLabel("C.I.F.", panel)
        self.cif_edit = QLineEdit(panel)

        self.lbl_nombre_fiscal = QLabel("Nombre Fiscal", panel)
        self.nombre_fiscal_edit = QLineEdit(panel)

        self.lbl_provincia = QLabel("Provincia", panel)
        self.provincia_combo = QComboBox(panel)
        self.lbl_isla = QLabel("Isla", panel)
        self.isla_combo = QComboBox(panel)
        self.lbl_municipio = QLabel("Municipio", panel)
        self.municipio_edit = QLineEdit(panel)
        self.municipio_edit.setPlaceholderText("Escribe o selecciona un municipio")

        self.lbl_calle = QLabel("Calle", panel)
        self.direccion_edit = QLineEdit(panel)
        self.lbl_cp = QLabel("C.P.", panel)
        self.cp_edit = QLineEdit(panel)
        self.cp_edit.setPlaceholderText("C.P.")
        self.lbl_localidad = QLabel("Localidad", panel)
        self.localidad_combo = QComboBox(panel)

        self._layout_left_panel()

        self.provincia_combo.currentIndexChanged.connect(self._on_provincia_changed)
        self.isla_combo.currentIndexChanged.connect(self._on_isla_changed)
        self._municipio_options: dict[str, str] = {}
        self._cp_options: set[str] = set()
        self._selected_municipio_id = ""
        self._selected_cp = ""
        self._municipio_completer = self._build_lookup_completer(self.municipio_edit)
        self._cp_completer = self._build_lookup_completer(self.cp_edit)
        self.municipio_edit.editingFinished.connect(self._on_municipio_editing_finished)
        self.cp_edit.editingFinished.connect(self._on_cp_editing_finished)
        self._municipio_completer.activated.connect(self._on_municipio_editing_finished)
        self._cp_completer.activated.connect(self._on_cp_editing_finished)
        return panel

    def _layout_left_panel(self) -> None:
        self.lbl_cod.setGeometry(5, 2, 80, 20)
        self.lbl_nombre_comercial.setGeometry(95, 2, 455, 20)
        self.codigo_edit.setGeometry(5, 26, 80, 28)
        self.nombre_comercial_edit.setGeometry(95, 26, 455, 28)

        self.lbl_telefono.setGeometry(5, 64, 120, 20)
        self.lbl_cif.setGeometry(135, 64, 100, 20)
        self.lbl_nombre_fiscal.setGeometry(245, 64, 305, 20)
        self.telefono_edit.setGeometry(5, 86, 120, 28)
        self.cif_edit.setGeometry(135, 86, 100, 28)
        self.nombre_fiscal_edit.setGeometry(245, 86, 305, 28)

        self.lbl_provincia.setGeometry(5, 126, 165, 20)
        self.lbl_isla.setGeometry(175, 126, 100, 20)
        self.lbl_municipio.setGeometry(285, 126, 260, 20)
        self.provincia_combo.setGeometry(5, 150, 165, 28)
        self.isla_combo.setGeometry(175, 150, 100, 28)
        self.municipio_edit.setGeometry(285, 150, 260, 28)

        self.lbl_calle.setGeometry(5, 190, 270, 20)
        self.lbl_cp.setGeometry(285, 190, 80, 20)
        self.lbl_localidad.setGeometry(375, 190, 175, 20)
        self.direccion_edit.setGeometry(5, 214, 270, 28)
        self.cp_edit.setGeometry(285, 214, 80, 28)
        self.localidad_combo.setGeometry(375, 214, 175, 28)

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("detailSubPanel")
        panel.setFixedSize(274, 258)

        self.sectors_box = QFrame(panel)
        self.sectors_box.setObjectName("plainGroup")
        self.sectors_box.setFixedHeight(128)
        self.tipo_checks: dict[str, QCheckBox] = {}
        for label, object_name in self._SECTOR_OPTIONS:
            checkbox = QCheckBox(label, self.sectors_box)
            checkbox.setObjectName(object_name)
            checkbox.setMinimumHeight(28)
            self.tipo_checks[label] = checkbox

        self.section_info = QLabel("Tipo", panel)
        self.section_info.setProperty("role", "blockTitle")
        self.tipo_combo = QComboBox(panel)
        self.tipo_combo.addItems(["", "directo", "indirecto", "distribuidor"])

        self.lbl_abrev = QLabel("Abrev. pedido", panel)
        self.abreviatura_edit = QLineEdit(panel)
        self.abreviatura_edit.setMaxLength(20)

        self.status_box = QFrame(panel)
        self.status_box.setObjectName("plainGroup")
        self.status_group = QButtonGroup(self)
        self.activo_btn = QPushButton("ACTIVO", self.status_box)
        self.inactivo_btn = QPushButton("INACTIVO", self.status_box)
        self.activo_btn.setCheckable(True)
        self.inactivo_btn.setCheckable(True)
        self.activo_btn.setObjectName("stateChipActive")
        self.inactivo_btn.setObjectName("stateChipInactive")
        self.status_group.addButton(self.activo_btn)
        self.status_group.addButton(self.inactivo_btn)

        self.lbl_prospeccion = QLabel("Prospeccion", self.status_box)
        self.prospeccion_group = QButtonGroup(self)
        self.prospeccion_si = QRadioButton("Si", self.status_box)
        self.prospeccion_no = QRadioButton("No", self.status_box)
        self.prospeccion_group.addButton(self.prospeccion_si)
        self.prospeccion_group.addButton(self.prospeccion_no)

        self._layout_right_panel()
        return panel

    def _layout_right_panel(self) -> None:
        self.sectors_box.setGeometry(0, 0, 274, 128)
        self.section_info.setGeometry(5, 119, 120, 24)
        self.tipo_combo.setGeometry(5, 145, 120, 28)
        self.lbl_abrev.setGeometry(145, 119, 120, 24)
        self.abreviatura_edit.setGeometry(145, 145, 120, 28)
        self.status_box.setGeometry(0, 182, 274, 76)
        self.activo_btn.setGeometry(8, 10, 124, 28)
        self.inactivo_btn.setGeometry(140, 10, 124, 28)
        self.lbl_prospeccion.setGeometry(8, 45, 110, 24)
        self.prospeccion_si.setGeometry(130, 45, 50, 24)
        self.prospeccion_no.setGeometry(190, 45, 60, 24)

        self.tipo_checks["PANADERIA"].setGeometry(8, 10, 125, 24)
        self.tipo_checks["PASTELERIA"].setGeometry(141, 10, 125, 24)
        self.tipo_checks["HELADERIA"].setGeometry(8, 48, 125, 24)
        self.tipo_checks["CAFETERIA"].setGeometry(141, 48, 125, 24)
        self.tipo_checks["RESTAURANTE"].setGeometry(8, 86, 125, 24)
        self.tipo_checks["HOTEL"].setGeometry(141, 86, 125, 24)

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

    def _build_lookup_completer(self, field: QLineEdit) -> QCompleter:
        model = QStringListModel(self)
        completer = QCompleter(model, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        field.setCompleter(completer)
        return completer

    @staticmethod
    def _lookup_value_for_id(options: dict[str, str], selected_id: str) -> str:
        for label, value in options.items():
            if value == selected_id:
                return label
        return ""

    def _set_municipio_options(self, items: list[tuple[str, str]], selected_id: str = "") -> None:
        self._municipio_options = {label: value for label, value in items}
        self._municipio_completer.model().setStringList(list(self._municipio_options))
        self._selected_municipio_id = selected_id if selected_id in self._municipio_options.values() else ""
        self.municipio_edit.setText(self._lookup_value_for_id(self._municipio_options, self._selected_municipio_id))

    def _set_cp_options(self, items: list[tuple[str, str]], selected_cp: str = "") -> None:
        self._cp_options = {value for _label, value in items}
        self._cp_completer.model().setStringList(sorted(self._cp_options))
        self._selected_cp = selected_cp if selected_cp in self._cp_options else ""
        self.cp_edit.setText(self._selected_cp)

    def _populate_provincias(self, selected_id: str = "") -> None:
        items = [(str(p.provincia_nombre or ""), str(p.provincia_id or "")) for p in self._provincias if p.provincia_nombre]
        self._fill_combo(self.provincia_combo, items, selected_id)

    def _populate_islas(self, provincia_id: str, selected_id: str = "") -> None:
        items = [
            (str(i.isla_nombre or ""), str(i.isla_id or ""))
            for i in self._islas
            if str(i.provincia_id or "") == str(provincia_id or "") and i.isla_nombre
        ]
        self._fill_combo(self.isla_combo, items, selected_id)

    def _populate_municipios(self, isla_id: str, selected_id: str = "", codigo_postal: str = "") -> None:
        cp = str(codigo_postal or "").strip()
        municipality_ids_for_cp = {
            str(item.municipio_id or "")
            for item in self._codigos_postales
            if str(item.codigo_postal or "").strip() == cp
        }
        items = [
            (str(m.municipio_nombre or ""), str(m.municipio_id or ""))
            for m in self._municipios
            if (
                str(m.isla_id or "") == str(isla_id or "")
                and m.municipio_nombre
                and (not cp or str(m.municipio_id or "") in municipality_ids_for_cp)
            )
        ]
        self._set_municipio_options(items, selected_id)

    def _populate_cps(self, isla_id: str, selected_cp: str = "", municipio_id: str = "") -> None:
        items = [
            (str(cp.codigo_postal or ""), str(cp.codigo_postal or ""))
            for cp in self._codigos_postales
            if (
                str(cp.codigo_postal or "").strip()
                and (not municipio_id or str(cp.municipio_id or "") == str(municipio_id or ""))
                and any(
                    str(m.municipio_id or "") == str(cp.municipio_id or "")
                    and str(m.isla_id or "") == str(isla_id or "")
                    for m in self._municipios
                )
            )
        ]
        unique_items: list[tuple[str, str]] = []
        seen: set[str] = set()
        for label, value in items:
            if value in seen:
                continue
            seen.add(value)
            unique_items.append((label, value))
        self._set_cp_options(unique_items, selected_cp)

    def _populate_localidades(
        self,
        municipio_id: str,
        codigo_postal: str,
        selected_localidad_id: str = "",
    ) -> None:
        cp = str(codigo_postal or "").strip()
        municipality_id = str(municipio_id or "").strip()
        if not cp or not municipality_id:
            items: list[tuple[str, str]] = []
        else:
            items = [
                (str(loc.localidad_nombre or ""), str(loc.localidad_id or ""))
                for loc in self._localidades
                if (
                    str(loc.municipio_id or "") == municipality_id
                    and str(loc.codigo_postal or "").strip() == cp
                    and loc.localidad_nombre
                )
            ]
        self._fill_combo(self.localidad_combo, items, selected_localidad_id)

    def _on_provincia_changed(self, _idx: int) -> None:
        if self._is_loading:
            return
        provincia_id = str(self.provincia_combo.currentData() or "")
        self._populate_islas(provincia_id, "")
        self._populate_municipios("", "")
        self._populate_cps("", "")
        self._populate_localidades("", "", "")

    def _on_isla_changed(self, _idx: int) -> None:
        if self._is_loading:
            return
        isla_id = str(self.isla_combo.currentData() or "")
        self._populate_municipios(isla_id, "")
        self._populate_cps(isla_id, "")
        self._populate_localidades("", "", "")

    def _on_municipio_editing_finished(self, *_args) -> None:
        if self._is_loading:
            return
        entered_name = self.municipio_edit.text().strip()
        self._selected_municipio_id = self._municipio_options.get(entered_name, "")
        if not self._selected_municipio_id:
            self.municipio_edit.clear()
        isla_id = str(self.isla_combo.currentData() or "")
        self._populate_cps(isla_id, self._selected_cp, self._selected_municipio_id)
        self._populate_localidades(self._selected_municipio_id, self._selected_cp, "")

    def _on_cp_editing_finished(self, *_args) -> None:
        if self._is_loading:
            return
        entered_cp = self.cp_edit.text().strip()
        self._selected_cp = entered_cp if entered_cp in self._cp_options else ""
        if not self._selected_cp:
            self.cp_edit.clear()
        isla_id = str(self.isla_combo.currentData() or "")
        self._populate_municipios(isla_id, self._selected_municipio_id, self._selected_cp)
        self._populate_localidades(self._selected_municipio_id, self._selected_cp, "")

    def _normalize_phone(self, raw: str) -> str:
        digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
        if digits.startswith("34") and len(digits) == 11:
            digits = digits[2:]
        if len(digits) == 9:
            return f"+34 {digits[:3]} {digits[3:6]} {digits[6:]}"
        return str(raw or "").strip()

    def _format_phone_field(self) -> None:
        self.telefono_edit.setText(self._normalize_phone(self.telefono_edit.text()))

    def _load_initial(self) -> None:
        self._is_loading = True
        self.codigo_edit.setText(str(self._initial.get("cliente_codigo", "") or ""))
        self.nombre_comercial_edit.setText(str(self._initial.get("cliente_nombre_comercial", "") or ""))
        self.telefono_edit.setText(self._normalize_phone(str(self._initial.get("cliente_telefono", "") or "")))
        self.cif_edit.setText(str(self._initial.get("cliente_cif", "") or ""))
        self.nombre_fiscal_edit.setText(str(self._initial.get("cliente_nombre_fiscal", "") or ""))
        self.direccion_edit.setText(str(self._initial.get("cliente_direccion", "") or ""))
        self.abreviatura_edit.setText(str(self._initial.get("cliente_abreviatura", "") or ""))

        provincia_id = str(self._initial.get("cliente_direccion_provincia_id", "") or "")
        isla_id = str(self._initial.get("cliente_direccion_isla_id", "") or "")
        municipio_id = str(self._initial.get("cliente_direccion_municipio_id", "") or "")
        codigo_postal = str(self._initial.get("cliente_direccion_cp", "") or "")
        localidad_id = str(self._initial.get("cliente_direccion_localidad_id", "") or "")
        self._populate_provincias(provincia_id)
        self._populate_islas(provincia_id, isla_id)
        self._populate_municipios(isla_id, municipio_id)
        self._populate_cps(isla_id, codigo_postal, municipio_id)
        self._populate_localidades(municipio_id, codigo_postal, localidad_id)

        grupos = (str(self._initial.get("cliente_actividad", "") or "")).upper()
        for label, checkbox in self.tipo_checks.items():
            checkbox.setChecked(label in grupos)

        tipo = (str(self._initial.get("cliente_tipo", "") or "")).strip().lower()
        idx_tipo = self.tipo_combo.findText(tipo)
        self.tipo_combo.setCurrentIndex(idx_tipo if idx_tipo >= 0 else 0)

        if bool(self._initial.get("activo", True)):
            self.activo_btn.setChecked(True)
        else:
            self.inactivo_btn.setChecked(True)
        if bool(self._initial.get("cliente_prospeccion", False)):
            self.prospeccion_si.setChecked(True)
        else:
            self.prospeccion_no.setChecked(True)
        self._is_loading = False

    def accept(self) -> None:  # type: ignore[override]
        self._format_phone_field()
        super().accept()

    def get_payload(self) -> dict:
        payload = dict(self._preserved_payload)
        payload.update(
            {
                "cliente_nombre_comercial": self.nombre_comercial_edit.text().strip(),
                "cliente_telefono": self.telefono_edit.text().strip(),
                "cliente_nombre_fiscal": self.nombre_fiscal_edit.text().strip(),
                "cliente_direccion": self.direccion_edit.text().strip(),
                "cliente_abreviatura": self.abreviatura_edit.text().strip().upper(),
                "cliente_cif": self.cif_edit.text().strip(),
                "cliente_direccion_cp": self._selected_cp,
                "cliente_direccion_provincia_id": str(self.provincia_combo.currentData() or "").strip(),
                "cliente_direccion_isla_id": str(self.isla_combo.currentData() or "").strip(),
                "cliente_direccion_municipio_id": self._selected_municipio_id,
                "cliente_direccion_localidad_id": str(self.localidad_combo.currentData() or "").strip(),
                "cliente_tipo": (self.tipo_combo.currentText() or "").strip().lower(),
                "cliente_actividad": ",".join(
                    [label for label, checkbox in self.tipo_checks.items() if checkbox.isChecked()]
                ),
                "cliente_prospeccion": self.prospeccion_si.isChecked(),
                "activo": self.activo_btn.isChecked(),
            }
        )
        return payload


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
        self.customer_query_service = CustomerQueryService(
            report_flow_service=self.customer_report_flow_service
        )
        self.customer_ai_summary_service = CustomerAISummaryService(customer_service=self.customer_service)
        self._customer_ai_summary_runner = _CustomerAISummaryRunner(self)
        self._customer_ai_summary_runner.result_ready.connect(self._handle_customer_ai_summary_result)
        self._customer_ai_summary_runner.failed.connect(self._handle_customer_ai_summary_failure)
        self._customer_ai_summary_request_token = ""
        self._customer_ai_summary_dialog: CustomerAISummaryDialog | None = None
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
        self._loading_related_sales = False
        self._loading_agenda = False
        self._agenda_filter_type: QComboBox | None = None
        self._agenda_filter_state: QComboBox | None = None
        self._agenda_filter_from: QDateEdit | None = None
        self._agenda_filter_to: QDateEdit | None = None
        self._agenda_filter_refresh_btn: QPushButton | None = None
        self._related_sales_year_filter: QComboBox | None = None
        self._related_sales_month_from_filter: QComboBox | None = None
        self._related_sales_month_to_filter: QComboBox | None = None
        self._related_sales_compare_btn: QPushButton | None = None
        self._related_sales_rows: list = []
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
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._apply_modern_styles()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 11, 14, 14)
        layout.setSpacing(10)

        ribbon, ribbon_layout = create_standard_top_ribbon()

        self.new_btn = create_standard_ribbon_button("Nuevo", role="success", icon_name="user-round-plus.svg")
        self.edit_btn = create_standard_ribbon_button("Editar", role="warning", icon_name="file-pen.svg")
        self.del_btn = create_standard_ribbon_button("Eliminar", role="danger", icon_name="trash.svg")
        self.print_btn = create_standard_ribbon_button("Listados", role="secondary", icon_name="list.svg")
        self.refresh_btn = create_standard_ribbon_button("Actualizar", role="info", icon_name="refresh-cw.svg")
        self.queries_btn = create_standard_ribbon_button(
            "Consultas",
            role="primary",
            icon_name="brain.svg",
            object_name="customerQueriesButton",
            tooltip="Abrir consultas de clientes",
        )
        self.ai_summary_btn = create_standard_ribbon_button(
            "Resumen IA",
            role="primary",
            icon_name="brain.svg",
            object_name="customerAISummaryButton",
            tooltip="Generar un resumen comercial del cliente seleccionado",
        )
        self.ai_summary_btn.setEnabled(False)
        self.help_btn = create_standard_ribbon_button(
            "Ayuda",
            role="secondary",
            icon_name="circle-question-mark.svg",
        )
        self.help_btn.clicked.connect(self._show_customer_help)

        self.new_btn.clicked.connect(self._new_entity)
        self.edit_btn.clicked.connect(self._edit_entity)
        self.del_btn.clicked.connect(self._delete_entity)
        self.print_btn.clicked.connect(self._open_customer_reports_dialog)
        self.queries_btn.clicked.connect(self._open_customer_queries_dialog)
        self.ai_summary_btn.clicked.connect(self._open_customer_ai_summary)
        self.refresh_btn.clicked.connect(self.reload)

        ribbon_layout.addWidget(self.new_btn)
        ribbon_layout.addWidget(self.edit_btn)
        ribbon_layout.addWidget(self.del_btn)
        ribbon_layout.addWidget(self.print_btn)
        ribbon_layout.addWidget(self.refresh_btn)
        ribbon_layout.addWidget(self.queries_btn)
        ribbon_layout.addWidget(self.ai_summary_btn)
        ribbon_layout.addStretch(1)
        ribbon_layout.addWidget(self.help_btn)
        layout.addWidget(ribbon)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("customersMainSplitter")
        self._main_splitter = splitter
        layout.addWidget(splitter, 1)

        left_panel = QWidget()
        left_panel.setObjectName("customersLeftPanel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        customers_catalog_header = QFrame(left_panel)
        customers_catalog_header.setObjectName("customersCatalogHeader")
        customers_catalog_header.setProperty("uiRole", "detailHeader")
        customers_catalog_header.setFixedHeight(38)
        customers_catalog_header_layout = QHBoxLayout(customers_catalog_header)
        customers_catalog_header_layout.setContentsMargins(14, 0, 14, 0)
        customers_catalog_header_layout.setSpacing(9)
        customers_catalog_icon = QLabel(customers_catalog_header)
        customers_catalog_icon.setObjectName("customersCatalogHeaderIcon")
        customers_catalog_icon.setProperty("uiRole", "detailHeaderIcon")
        catalog_icon_pixmap = QIcon(str(BASE_DIR / "assets" / "icons" / "users.svg")).pixmap(21, 21)
        catalog_icon_image = catalog_icon_pixmap.toImage()
        for x in range(catalog_icon_image.width()):
            for y in range(catalog_icon_image.height()):
                color = catalog_icon_image.pixelColor(x, y)
                if color.alpha():
                    catalog_icon_image.setPixelColor(x, y, QColor(255, 255, 255, color.alpha()))
        customers_catalog_icon.setPixmap(QPixmap.fromImage(catalog_icon_image))
        customers_catalog_icon.setFixedSize(22, 22)
        customers_catalog_header_layout.addWidget(customers_catalog_icon)
        customers_catalog_title = QLabel("CLIENTES", customers_catalog_header)
        customers_catalog_title.setObjectName("customersCatalogHeaderTitle")
        customers_catalog_title.setProperty("uiRole", "detailHeaderTitle")
        customers_catalog_header_layout.addWidget(customers_catalog_title)
        customers_catalog_header_layout.addStretch(1)
        left_layout.addWidget(customers_catalog_header)

        customers_catalog_body = QWidget(left_panel)
        customers_catalog_body.setObjectName("customersCatalogBody")
        customers_catalog_body_layout = QVBoxLayout(customers_catalog_body)
        customers_catalog_body_layout.setContentsMargins(14, 10, 14, 14)
        customers_catalog_body_layout.setSpacing(10)

        self.island_filter = QComboBox()
        self.island_filter.setObjectName("customerIslandFilter")
        self.island_filter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.island_filter.currentIndexChanged.connect(self.reload)
        self.classification_filter = QComboBox()
        self.classification_filter.setObjectName("customerClassificationFilter")
        self.classification_filter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.classification_filter.currentIndexChanged.connect(self.reload)
        filters_row = QHBoxLayout()
        filters_row.setContentsMargins(0, 0, 0, 0)
        filters_row.setSpacing(8)
        filters_row.addWidget(self.island_filter, 1)
        filters_row.addWidget(self.classification_filter, 1)
        customers_catalog_body_layout.addLayout(filters_row)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar cliente o código distribuidor...")
        self.search_input.setFixedWidth(220)
        self.search_input.setFixedHeight(30)
        self.search_input.textChanged.connect(self._schedule_reload)
        self.search_input.textChanged.connect(self._update_search_clear_button)

        self.search_counter_label = QLabel("0/0")
        self.search_counter_label.setObjectName("customerSearchCounterLabel")
        self.search_counter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.search_counter_label.setFixedHeight(30)
        self.search_counter_label.setToolTip("Registros encontrados / registros totales")

        self.clear_search_btn = QPushButton()
        self.clear_search_btn.setObjectName("customerSearchClearButton")
        self.clear_search_btn.setFixedSize(30, 30)
        self.clear_search_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.clear_search_btn.setIcon(QIcon(str(BASE_DIR / "assets" / "icons" / "close-white.svg")))
        self.clear_search_btn.setIconSize(QSize(14, 14))
        self.clear_search_btn.setToolTip("Vaciar filtro")
        self.clear_search_btn.setEnabled(False)
        self.clear_search_btn.clicked.connect(self._clear_search_filter)

        search_row = QHBoxLayout()
        search_row.setContentsMargins(0, 0, 0, 0)
        search_row.setSpacing(8)
        search_row.addWidget(self.search_input)
        search_row.addWidget(self.clear_search_btn)
        search_row.addWidget(self.search_counter_label, 1)
        customers_catalog_body_layout.addLayout(search_row)

        self.table = QTableWidget(0, 3)
        self.table.setObjectName("customersListTable")
        self.table.setProperty("tableVariant", "standard")
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setItemDelegate(CustomersCatalogSelectionDelegate(self.table))
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
        customers_catalog_body_layout.addWidget(self.table, 1)
        left_layout.addWidget(customers_catalog_body, 1)
        splitter.addWidget(left_panel)

        right_panel = QWidget()
        right_panel.setObjectName("customersRightPanel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_splitter.setObjectName("customersDetailSplitter")
        self._detail_splitter = right_splitter
        right_layout.addWidget(right_splitter, 1)

        detail_panel = QWidget()
        detail_panel.setObjectName("detailTopArea")
        detail_panel.setFixedHeight(300)
        detail_panel.setFixedWidth(932)
        detail_panel.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(10)

        self.detail_panel = detail_panel

        left_card = QFrame(detail_panel)
        left_card.setObjectName("detailLeftCard")
        self.left_card = left_card
        left_card_layout = QVBoxLayout(left_card)
        left_card_layout.setContentsMargins(0, 0, 0, 0)
        left_card_layout.setSpacing(0)
        customer_detail_header = QFrame(left_card)
        customer_detail_header.setObjectName("customerDetailHeader")
        customer_detail_header.setProperty("uiRole", "detailHeader")
        customer_detail_header.setFixedHeight(38)
        customer_detail_header_layout = QHBoxLayout(customer_detail_header)
        customer_detail_header_layout.setContentsMargins(14, 0, 14, 0)
        customer_detail_header_layout.setSpacing(9)
        customer_detail_icon = QLabel(customer_detail_header)
        customer_detail_icon.setObjectName("customerDetailHeaderIcon")
        customer_detail_icon.setProperty("uiRole", "detailHeaderIcon")
        detail_icon_pixmap = QIcon(str(BASE_DIR / "assets" / "icons" / "users.svg")).pixmap(21, 21)
        detail_icon_image = detail_icon_pixmap.toImage()
        for x in range(detail_icon_image.width()):
            for y in range(detail_icon_image.height()):
                color = detail_icon_image.pixelColor(x, y)
                if color.alpha():
                    detail_icon_image.setPixelColor(x, y, QColor(255, 255, 255, color.alpha()))
        customer_detail_icon.setPixmap(QPixmap.fromImage(detail_icon_image))
        customer_detail_icon.setFixedSize(22, 22)
        customer_detail_header_layout.addWidget(customer_detail_icon)
        self.detail_title = QLabel("DETALLE DEL CLIENTE", customer_detail_header)
        self.detail_title.setObjectName("customerDetailHeaderTitle")
        self.detail_title.setProperty("uiRole", "detailHeaderTitle")
        customer_detail_header_layout.addWidget(self.detail_title)
        customer_detail_header_layout.addStretch(1)
        left_card_layout.addWidget(customer_detail_header)
        customer_detail_body = QWidget(left_card)
        customer_detail_body.setObjectName("customerDetailBody")
        customer_detail_body_layout = QVBoxLayout(customer_detail_body)
        customer_detail_body_layout.setContentsMargins(4, 4, 4, 4)
        customer_detail_body_layout.setSpacing(0)
        left_detail_panel = self._build_upper_left_detail_panel()
        customer_detail_body_layout.addWidget(left_detail_panel, 1)
        left_card_layout.addWidget(customer_detail_body, 1)

        right_card = QFrame(detail_panel)
        right_card.setObjectName("detailRightCard")
        self.right_card = right_card
        right_card_layout = QVBoxLayout(right_card)
        right_card_layout.setContentsMargins(0, 0, 0, 0)
        right_card_layout.setSpacing(0)
        customer_classification_header = QFrame(right_card)
        customer_classification_header.setObjectName("customerClassificationHeader")
        customer_classification_header.setProperty("uiRole", "detailHeader")
        customer_classification_header.setFixedHeight(38)
        customer_classification_header_layout = QHBoxLayout(customer_classification_header)
        customer_classification_header_layout.setContentsMargins(14, 0, 14, 0)
        customer_classification_header_layout.setSpacing(9)
        customer_classification_icon = QLabel(customer_classification_header)
        customer_classification_icon.setObjectName("customerClassificationHeaderIcon")
        customer_classification_icon.setProperty("uiRole", "detailHeaderIcon")
        classification_icon_pixmap = QIcon(str(BASE_DIR / "assets" / "icons" / "briefcase.svg")).pixmap(21, 21)
        classification_icon_image = classification_icon_pixmap.toImage()
        for x in range(classification_icon_image.width()):
            for y in range(classification_icon_image.height()):
                color = classification_icon_image.pixelColor(x, y)
                if color.alpha():
                    classification_icon_image.setPixelColor(x, y, QColor(255, 255, 255, color.alpha()))
        customer_classification_icon.setPixmap(QPixmap.fromImage(classification_icon_image))
        customer_classification_icon.setFixedSize(22, 22)
        customer_classification_header_layout.addWidget(customer_classification_icon)
        self.detail_tipo_header = QLabel("CLASIFICACIÓN DEL CLIENTE", customer_classification_header)
        self.detail_tipo_header.setObjectName("customerClassificationHeaderTitle")
        self.detail_tipo_header.setProperty("uiRole", "detailHeaderTitle")
        customer_classification_header_layout.addWidget(self.detail_tipo_header)
        customer_classification_header_layout.addStretch(1)
        right_card_layout.addWidget(customer_classification_header)
        customer_classification_body = QWidget(right_card)
        customer_classification_body.setObjectName("customerClassificationBody")
        customer_classification_body_layout = QVBoxLayout(customer_classification_body)
        customer_classification_body_layout.setContentsMargins(12, 2, 12, 2)
        customer_classification_body_layout.setSpacing(0)
        right_detail_panel = self._build_upper_right_detail_panel()
        customer_classification_body_layout.addWidget(right_detail_panel, 1)
        right_card_layout.addWidget(customer_classification_body, 1)
        self._layout_detail_cards_abs()
        right_splitter.addWidget(detail_panel)

        tabs_panel = QWidget()
        tabs_panel.setObjectName("crmCard")
        tabs_panel.setMinimumHeight(300)
        tabs_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        tabs_layout = QVBoxLayout(tabs_panel)
        tabs_layout.setContentsMargins(5, 5, 5, 5)
        tabs_layout.setSpacing(8)

        self.customer_tabs = QTabWidget()
        self.customer_tabs.setObjectName("customerTabs")
        self.customer_tabs.addTab(self._build_sales_tab(), "Compras")
        self.customer_tabs.addTab(self._build_contacts_tab(), "Contactos")
        self.customer_tabs.addTab(self._build_recipes_tab(), "Recetas")
        self.customer_tabs.addTab(self._build_agenda_tab(), "Agenda")
        self._customer_sales_tab_index = 0
        self.customer_tabs.currentChanged.connect(self._handle_customer_tab_changed)
        self.customer_tabs.setTabIcon(0, QIcon(str(BASE_DIR / "assets" / "icons" / "badge-euro.svg")))
        self.customer_tabs.setTabIcon(1, QIcon(str(BASE_DIR / "assets" / "icons" / "contact.svg")))
        self.customer_tabs.setTabIcon(2, QIcon(str(BASE_DIR / "assets" / "icons" / "cooking-pot.svg")))
        self.customer_tabs.setTabIcon(3, QIcon(str(BASE_DIR / "assets" / "icons" / "calendar-days.svg")))
        tabs_layout.addWidget(self.customer_tabs)
        right_splitter.addWidget(tabs_panel)
        right_splitter.setStretchFactor(0, 0)
        right_splitter.setStretchFactor(1, 1)
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
        QTimer.singleShot(0, self._layout_left_detail_abs)

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
        # El detalle superior permanece fijo y la zona de pesta?as ocupa el resto.
        top_px = 300
        bottom_px = max(300, splitter.height() - top_px)
        splitter.setSizes([top_px, bottom_px])

    def _layout_detail_cards_abs(self) -> None:
        panel = getattr(self, "detail_panel", None)
        left_card = getattr(self, "left_card", None)
        right_card = getattr(self, "right_card", None)
        if panel is None or left_card is None or right_card is None:
            return
        panel.setFixedWidth(932)
        # Coordenadas fijas dentro del detail_panel.
        left_card.setGeometry(5, 0, 590, 300)
        right_card.setGeometry(600, 0, 300, 300)

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
        self.related_contacts_table.setProperty("tableVariant", "standard")
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

    def _build_sales_tab(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("customerSalesPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)

        self._related_sales_year_filter = QComboBox()
        self._related_sales_year_filter.setObjectName("customerSalesYearFilter")
        self._related_sales_year_filter.setFixedWidth(110)
        self._related_sales_year_filter.currentIndexChanged.connect(self._refresh_related_sales)

        self._related_sales_month_from_filter = QComboBox()
        self._related_sales_month_from_filter.setObjectName("customerSalesMonthFromFilter")
        self._related_sales_month_from_filter.setFixedWidth(125)
        self._populate_month_filter(self._related_sales_month_from_filter, 1)
        self._related_sales_month_from_filter.currentIndexChanged.connect(self._refresh_related_sales)

        self._related_sales_month_to_filter = QComboBox()
        self._related_sales_month_to_filter.setObjectName("customerSalesMonthToFilter")
        self._related_sales_month_to_filter.setFixedWidth(125)
        self._populate_month_filter(self._related_sales_month_to_filter, 12)
        self._related_sales_month_to_filter.currentIndexChanged.connect(self._refresh_related_sales)

        self._related_sales_compare_btn = QPushButton("Comparar")
        self._related_sales_compare_btn.setObjectName("customerSalesCompareButton")
        self._related_sales_compare_btn.setIcon(QIcon(str(BASE_DIR / "assets" / "icons" / "scale.svg")))
        self._related_sales_compare_btn.setIconSize(QSize(16, 16))
        self._related_sales_compare_btn.setProperty("btnRole", "info")
        self._related_sales_compare_btn.setEnabled(False)
        self._related_sales_compare_btn.clicked.connect(self._open_related_sales_comparison)

        actions.addWidget(self._related_sales_year_filter)
        actions.addWidget(self._related_sales_month_from_filter)
        actions.addWidget(self._related_sales_month_to_filter)
        actions.addWidget(self._related_sales_compare_btn)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.related_sales_table = QTableWidget(0, 5)
        self.related_sales_table.setObjectName("customerSalesTable")
        self.related_sales_table.setProperty("tableVariant", "standard")
        self.related_sales_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.related_sales_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.related_sales_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.related_sales_table.setAlternatingRowColors(True)
        self.related_sales_table.setSortingEnabled(True)
        self.related_sales_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.related_sales_table.customContextMenuRequested.connect(self._show_related_sales_context_menu)
        self.related_sales_table.verticalHeader().setVisible(False)
        self.related_sales_table.setHorizontalHeaderLabels(["Referencia", "Descripción", "Unid.", "Kg", "€"])
        sales_header = self.related_sales_table.horizontalHeader()
        sales_header.setSectionsClickable(True)
        sales_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        sales_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        sales_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        sales_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        sales_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.related_sales_table.setColumnWidth(0, 110)
        self.related_sales_table.setColumnWidth(2, 96)
        self.related_sales_table.setColumnWidth(3, 108)
        self.related_sales_table.setColumnWidth(4, 118)
        self.related_sales_table.verticalHeader().setDefaultSectionSize(34)
        layout.addWidget(self.related_sales_table, 1)

        self.related_sales_totals = QTableWidget(1, 5)
        self.related_sales_totals.setObjectName("customerSalesTotals")
        self.related_sales_totals.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.related_sales_totals.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.related_sales_totals.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.related_sales_totals.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.related_sales_totals.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.related_sales_totals.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.related_sales_totals.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.related_sales_totals.setShowGrid(True)
        self.related_sales_totals.verticalHeader().setVisible(False)
        self.related_sales_totals.horizontalHeader().setVisible(False)
        totals_header = self.related_sales_totals.horizontalHeader()
        totals_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        totals_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        totals_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        totals_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        totals_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.related_sales_totals.verticalHeader().setDefaultSectionSize(30)
        self.related_sales_totals.setFixedHeight(34)
        layout.addWidget(self.related_sales_totals)

        sales_header.sectionResized.connect(self._sync_related_sales_totals)
        self.related_sales_table.verticalScrollBar().rangeChanged.connect(self._sync_related_sales_totals)

        self.related_sales_empty = QLabel("No hay ventas asociadas a este cliente para el año seleccionado.")
        self.related_sales_empty.setObjectName("customerSalesEmpty")
        self.related_sales_empty.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        self.related_sales_empty.setWordWrap(True)
        self.related_sales_empty.setVisible(False)
        layout.addWidget(self.related_sales_empty)

        self._reload_related_sales_years()
        self._render_related_sales("")
        return panel

    def _reload_related_sales_years(self) -> None:
        combo = self._related_sales_year_filter
        if combo is None:
            return
        current_value = str(combo.currentData() or combo.currentText() or "").strip()
        years = [int(year) for year in self.customer_service.related_sales_years() if int(year or 0) > 0]
        years = sorted(set(years), reverse=True)
        preferred_year = str(date.today().year)
        combo.blockSignals(True)
        combo.clear()
        for year in years:
            combo.addItem(str(year), year)
        if years:
            preferred_index = combo.findData(int(preferred_year))
            if preferred_index < 0 and current_value.isdigit():
                preferred_index = combo.findData(int(current_value))
            if preferred_index < 0:
                preferred_index = 0
            combo.setCurrentIndex(preferred_index)
        combo.blockSignals(False)

    def _populate_month_filter(self, combo: QComboBox, selected_month: int) -> None:
        months = [
            (1, "Enero"),
            (2, "Febrero"),
            (3, "Marzo"),
            (4, "Abril"),
            (5, "Mayo"),
            (6, "Junio"),
            (7, "Julio"),
            (8, "Agosto"),
            (9, "Septiembre"),
            (10, "Octubre"),
            (11, "Noviembre"),
            (12, "Diciembre"),
        ]
        combo.blockSignals(True)
        combo.clear()
        for value, label in months:
            combo.addItem(label, value)
        idx = combo.findData(int(selected_month or 0))
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

    def _related_sales_month_range(self) -> tuple[int, int]:
        month_from = 1
        month_to = 12
        if self._related_sales_month_from_filter is not None:
            month_from = int(self._related_sales_month_from_filter.currentData() or 1)
        if self._related_sales_month_to_filter is not None:
            month_to = int(self._related_sales_month_to_filter.currentData() or 12)
        month_from = max(1, min(month_from, 12))
        month_to = max(1, min(month_to, 12))
        if month_from > month_to:
            month_from, month_to = month_to, month_from
        return month_from, month_to

    def _refresh_related_sales(self) -> None:
        selected = self._selected_row()
        self._render_related_sales(str(getattr(selected, "cliente_id", "") or "") if selected else "")

    def _render_related_sales(self, cliente_id: str) -> None:
        if not hasattr(self, "related_sales_table"):
            return
        year_filter = self._related_sales_year_filter
        year = int(year_filter.currentData() or 0) if year_filter is not None else 0
        if not str(cliente_id or "").strip() or year <= 0:
            rows = []
        else:
            month_from, month_to = self._related_sales_month_range()
            rows = self.customer_service.related_sales(
                str(cliente_id or "").strip(),
                year,
                month_from=month_from,
                month_to=month_to,
            )

        # The summary service also returns previous-period-only articles for the
        # comparison dialog. Keep those records in the service result, but do
        # not show them as current sales in this main table.
        self._related_sales_rows = [item for item in (rows or []) if _has_current_sales_activity(item)]
        self._loading_related_sales = True
        self.related_sales_table.setSortingEnabled(False)
        try:
            self.related_sales_table.setRowCount(len(self._related_sales_rows))
            total_units = 0.0
            total_kg = 0.0
            total_euros = 0.0
            for row_idx, item in enumerate(self._related_sales_rows):
                units = float(getattr(item, "unidades_curr", 0.0) or 0.0)
                kg = float(getattr(item, "kg_curr", 0.0) or 0.0)
                euros = float(getattr(item, "euros_curr", 0.0) or 0.0)
                total_units += units
                total_kg += kg
                total_euros += euros

                code_item = QTableWidgetItem(str(getattr(item, "codigo", "") or ""))
                name_item = QTableWidgetItem(str(getattr(item, "nombre", "") or ""))
                units_item = _NumericTableWidgetItem(self._format_sales_number(units), units)
                kg_item = _NumericTableWidgetItem(self._format_sales_number(kg, suffix=" kg"), kg)
                euros_item = _NumericTableWidgetItem(self._format_sales_number(euros, suffix=" €"), euros)

                code_item.setData(Qt.ItemDataRole.UserRole, str(getattr(item, "articulo_id", "") or ""))
                units_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                kg_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                euros_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                units_item.setData(Qt.ItemDataRole.UserRole, units)
                kg_item.setData(Qt.ItemDataRole.UserRole, kg)
                euros_item.setData(Qt.ItemDataRole.UserRole, euros)

                self.related_sales_table.setItem(row_idx, 0, code_item)
                self.related_sales_table.setItem(row_idx, 1, name_item)
                self.related_sales_table.setItem(row_idx, 2, units_item)
                self.related_sales_table.setItem(row_idx, 3, kg_item)
                self.related_sales_table.setItem(row_idx, 4, euros_item)

            total_label = QTableWidgetItem("TOTALES")
            total_label.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            total_units_item = QTableWidgetItem(self._format_sales_number(total_units))
            total_kg_item = QTableWidgetItem(self._format_sales_number(total_kg, suffix=" kg"))
            total_euros_item = QTableWidgetItem(self._format_sales_number(total_euros, suffix=" €"))
            total_units_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            total_kg_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            total_euros_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.related_sales_totals.clearSpans()
            self.related_sales_totals.setSpan(0, 0, 1, 2)
            self.related_sales_totals.setItem(0, 0, total_label)
            self.related_sales_totals.setItem(0, 1, QTableWidgetItem(""))
            self.related_sales_totals.setItem(0, 2, total_units_item)
            self.related_sales_totals.setItem(0, 3, total_kg_item)
            self.related_sales_totals.setItem(0, 4, total_euros_item)
            self._sync_related_sales_totals()
        finally:
            self._loading_related_sales = False
            self.related_sales_table.setSortingEnabled(True)

        has_rows = bool(self._related_sales_rows)
        self.related_sales_table.setVisible(True)
        self.related_sales_totals.setVisible(True)
        self.related_sales_empty.setVisible(False)
        if self._related_sales_compare_btn is not None:
            self._related_sales_compare_btn.setEnabled(bool(cliente_id) and year > 0 and has_rows)
        QTimer.singleShot(0, self._sync_related_sales_totals)

    def _handle_customer_tab_changed(self, index: int) -> None:
        if index == getattr(self, "_customer_sales_tab_index", -1):
            self._reload_related_sales_years()
            self._refresh_related_sales()
            QTimer.singleShot(0, self._sync_related_sales_totals)

    def _sync_related_sales_totals(self, *args) -> None:
        if not hasattr(self, "related_sales_table") or not hasattr(self, "related_sales_totals"):
            return
        for column in range(self.related_sales_table.columnCount()):
            self.related_sales_totals.setColumnWidth(column, self.related_sales_table.columnWidth(column))

        total_item = self.related_sales_totals.item(0, 0)
        if total_item is not None:
            total_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    @staticmethod
    def _format_sales_number(value: float | int | None, suffix: str = "") -> str:
        number = float(value or 0.0)
        formatted = f"{number:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
        return f"{formatted}{suffix}"

    def _open_related_sales_comparison(self) -> None:
        selected = self._selected_row()
        year_filter = self._related_sales_year_filter
        year = int(year_filter.currentData() or 0) if year_filter is not None else 0
        cliente_id = str(getattr(selected, "cliente_id", "") or "").strip() if selected else ""
        customer_name = str(getattr(selected, "cliente_nombre_comercial", "") or "").strip() if selected else ""
        if not cliente_id or year <= 0:
            return
        month_from, month_to = self._related_sales_month_range()
        rows = self.customer_service.related_sales(cliente_id, year, month_from=month_from, month_to=month_to)
        dialog = self._build_related_sales_comparison_dialog(rows=rows, year=year, customer_name=customer_name)
        self._related_sales_comparison_dialog = dialog
        dialog.exec()

    def _show_related_sales_context_menu(self, pos) -> None:
        index = self.related_sales_table.indexAt(pos)
        if not index.isValid():
            return
        self.related_sales_table.selectRow(index.row())
        code_item = self.related_sales_table.item(index.row(), 0)
        if code_item is None:
            return
        menu = QMenu(self)
        detail_action = menu.addAction("Ver detalle mensual")
        detail_action.setEnabled(bool(str(code_item.text() or "").strip()))
        if menu.exec(self.related_sales_table.viewport().mapToGlobal(pos)) == detail_action:
            self._open_related_sales_monthly_detail(index.row())

    def _open_related_sales_monthly_detail(self, row_idx: int) -> None:
        selected = self._selected_row()
        year_filter = self._related_sales_year_filter
        year = int(year_filter.currentData() or 0) if year_filter is not None else 0
        if selected is None or year <= 0:
            return
        code_item = self.related_sales_table.item(row_idx, 0)
        name_item = self.related_sales_table.item(row_idx, 1)
        if code_item is None:
            return
        cliente_id = str(getattr(selected, "cliente_id", "") or "").strip()
        articulo_id = str(code_item.data(Qt.ItemDataRole.UserRole) or "").strip()
        articulo_codigo = str(code_item.text() or "").strip()
        if not cliente_id or not articulo_codigo:
            return
        rows = self.customer_service.related_sales_monthly_product(
            cliente_id,
            year,
            articulo_id=articulo_id,
            articulo_codigo=articulo_codigo,
        )
        product_name = str(name_item.text() or "").strip() if name_item is not None else ""
        dialog = self._build_related_sales_monthly_detail_dialog(
            rows=rows,
            year=year,
            articulo_codigo=articulo_codigo,
            product_name=product_name,
        )
        dialog.exec()

    def _build_related_sales_monthly_detail_dialog(
        self,
        *,
        rows: list,
        year: int,
        articulo_codigo: str,
        product_name: str,
    ) -> QDialog:
        dialog = QDialog(self)
        dialog.setObjectName("customerSalesMonthlyDetailDialog")
        dialog.setWindowTitle(f"Detalle mensual · {product_name or articulo_codigo}")
        dialog.setFixedWidth(680)
        dialog.resize(680, 580)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel(f"{articulo_codigo} · {product_name}".strip(" ·"))
        title.setProperty("role", "sectionTitle")
        layout.addWidget(title)
        subtitle = QLabel(f"Detalle mensual · {year}")
        subtitle.setProperty("role", "muted")
        layout.addWidget(subtitle)

        table = QTableWidget(0, 4)
        table.setObjectName("customerSalesMonthlyDetailTable")
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setAlternatingRowColors(True)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.verticalHeader().setVisible(False)
        table.setHorizontalHeaderLabels(["Mes", "Unid.", "Kg", "€"])
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 4):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(1, 125)
        table.setColumnWidth(2, 140)
        table.setColumnWidth(3, 140)
        month_names = (
            "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
        )
        table.setRowCount(len(month_names))
        total_units = total_kg = total_euros = 0.0
        for index, month_name in enumerate(month_names):
            item = rows[index] if index < len(rows) else None
            units = float(getattr(item, "unidades", 0.0) or 0.0)
            kg = float(getattr(item, "kg", 0.0) or 0.0)
            euros = float(getattr(item, "euros", 0.0) or 0.0)
            total_units += units
            total_kg += kg
            total_euros += euros
            table.setItem(index, 0, QTableWidgetItem(month_name))
            for column, value, suffix in ((1, units, ""), (2, kg, " kg"), (3, euros, " €")):
                cell = QTableWidgetItem(self._format_sales_number(value, suffix=suffix))
                cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                table.setItem(index, column, cell)
        layout.addWidget(table, 1)

        totals = QTableWidget(1, 4)
        totals.setObjectName("customerSalesMonthlyDetailTotals")
        totals.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        totals.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        totals.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        totals.verticalHeader().setVisible(False)
        totals.horizontalHeader().setVisible(False)
        totals.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        totals.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        totals.setFixedHeight(34)
        totals_header = totals.horizontalHeader()
        for column in range(4):
            totals_header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
        total_label = QTableWidgetItem("TOTALES")
        total_label.setForeground(QColor("#FFFFFF"))
        total_label.setBackground(QColor("#2F80ED"))
        totals.setItem(0, 0, total_label)
        for column, value, suffix in ((1, total_units, ""), (2, total_kg, " kg"), (3, total_euros, " €")):
            cell = QTableWidgetItem(self._format_sales_number(value, suffix=suffix))
            cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            cell.setForeground(QColor("#FFFFFF"))
            cell.setBackground(QColor("#2F80ED"))
            totals.setItem(0, column, cell)
        totals.setStyleSheet("QTableWidget { background: #2F80ED; border: 0; gridline-color: #2F80ED; }")

        def sync_totals() -> None:
            for column in range(table.columnCount()):
                totals.setColumnWidth(column, table.columnWidth(column))

        header.sectionResized.connect(lambda *_: sync_totals())
        QTimer.singleShot(0, sync_totals)
        layout.addWidget(totals)

        footer = QHBoxLayout()
        footer.addStretch(1)
        close_button = QPushButton("Cerrar")
        close_button.setProperty("btnRole", "danger")
        close_button.clicked.connect(dialog.accept)
        footer.addWidget(close_button)
        layout.addLayout(footer)
        return dialog

    def _build_related_sales_comparison_dialog(self, *, rows: list, year: int, customer_name: str) -> QDialog:
        dialog = QDialog(self)
        dialog.setWindowTitle("Comparativa de ventas")
        dialog.resize(1360, 720)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel(f"{customer_name or 'Cliente'} - Comparativa {year - 1} vs {year}")
        title.setProperty("role", "sectionTitle")
        layout.addWidget(title)

        groups_bar = QWidget()
        groups_bar.setObjectName("customerSalesComparisonGroupsBar")
        groups_bar_layout = QHBoxLayout(groups_bar)
        groups_bar_layout.setContentsMargins(0, 0, 0, 0)
        groups_bar_layout.setSpacing(0)
        groups_spacer = QWidget()
        groups_spacer.setObjectName("customerSalesComparisonGroupsSpacer")
        groups_prev = QLabel(str(year - 1))
        groups_prev.setObjectName("customerSalesComparisonGroupPrev")
        groups_prev.setAlignment(Qt.AlignmentFlag.AlignCenter)
        groups_curr = QLabel(str(year))
        groups_curr.setObjectName("customerSalesComparisonGroupCurr")
        groups_curr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        groups_delta = QLabel("Diferencia")
        groups_delta.setObjectName("customerSalesComparisonGroupDelta")
        groups_delta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        groups_bar_layout.addWidget(groups_spacer)
        groups_bar_layout.addWidget(groups_prev)
        groups_bar_layout.addWidget(groups_curr)
        groups_bar_layout.addWidget(groups_delta)
        layout.addWidget(groups_bar)

        table = QTableWidget(0, 11)
        table.setObjectName("customerSalesComparisonTable")
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(False)
        table.verticalHeader().setVisible(False)
        table.setHorizontalHeaderLabels([
            "Referencia", "Descripción",
            "Unid.", "Kg", "€",
            "Unid.", "Kg", "€",
            "Δ Unid.", "Δ Kg", "Δ €",
        ])
        header = table.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for column in range(2, 11):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(0, 110)
        table.setColumnWidth(2, 90)
        table.setColumnWidth(3, 100)
        table.setColumnWidth(4, 112)
        table.setColumnWidth(5, 90)
        table.setColumnWidth(6, 100)
        table.setColumnWidth(7, 112)
        table.setColumnWidth(8, 100)
        table.setColumnWidth(9, 110)
        table.setColumnWidth(10, 118)
        table.verticalHeader().setDefaultSectionSize(34)
        layout.addWidget(table, 1)

        totals_table = QTableWidget(1, 11)
        totals_table.setObjectName("customerSalesComparisonTotals")
        totals_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        totals_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        totals_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        totals_table.setShowGrid(True)
        totals_table.verticalHeader().setVisible(False)
        totals_table.horizontalHeader().setVisible(False)
        totals_table.setFixedHeight(34)
        totals_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        totals_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        totals_table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        totals_table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        totals_header = totals_table.horizontalHeader()
        for column in range(11):
            totals_header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
        totals_table.verticalHeader().setDefaultSectionSize(30)
        layout.addWidget(totals_table)

        header.sectionResized.connect(lambda *_: self._sync_related_sales_comparison_layout(table=table, totals_table=totals_table, groups_spacer=groups_spacer, groups_prev=groups_prev, groups_curr=groups_curr, groups_delta=groups_delta))
        table.verticalScrollBar().rangeChanged.connect(lambda *_: self._sync_related_sales_comparison_layout(table=table, totals_table=totals_table, groups_spacer=groups_spacer, groups_prev=groups_prev, groups_curr=groups_curr, groups_delta=groups_delta))

        empty = QLabel("No hay datos de comparativa para este cliente.")
        empty.setObjectName("customerSalesEmpty")
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.setVisible(False)
        layout.addWidget(empty)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(8)
        chart_btn = QPushButton("Graf.")
        chart_btn.setObjectName("customerSalesComparisonChartButton")
        chart_btn.setProperty("btnRole", "info")
        chart_btn.setIcon(QIcon(str(BASE_DIR / "assets" / "icons" / "chart-no-axes-combined.svg")))
        chart_btn.clicked.connect(lambda: self._open_related_sales_chart(rows=rows, year=year, customer_name=customer_name, parent=dialog))
        excel_btn = QPushButton("Excel")
        excel_btn.setObjectName("customerSalesComparisonExcelButton")
        excel_btn.setProperty("btnRole", "success")
        excel_btn.setIcon(QIcon(str(BASE_DIR / "assets" / "icons" / "sheet.svg")))
        excel_btn.clicked.connect(lambda: self._export_related_sales_comparison_excel(rows=rows, year=year, customer_name=customer_name, parent=dialog))
        pdf_btn = QPushButton("Pdf")
        pdf_btn.setObjectName("customerSalesComparisonPdfButton")
        pdf_btn.setProperty("btnRole", "primary")
        pdf_btn.setIcon(QIcon(str(BASE_DIR / "assets" / "icons" / "file-text.svg")))
        pdf_btn.clicked.connect(lambda: self._export_related_sales_comparison_pdf(rows=rows, year=year, customer_name=customer_name, parent=dialog))
        close_btn = QPushButton("Cerrar")
        close_btn.setObjectName("customerSalesComparisonCloseButton")
        close_btn.setProperty("btnRole", "danger")
        close_btn.clicked.connect(dialog.accept)
        comparison_footer_width = max(button.sizeHint().width() for button in (chart_btn, excel_btn, pdf_btn, close_btn))
        for button in (chart_btn, excel_btn, pdf_btn, close_btn):
            button.setFixedWidth(comparison_footer_width)
        footer.addWidget(chart_btn)
        footer.addWidget(excel_btn)
        footer.addWidget(pdf_btn)
        footer.addStretch(1)
        footer.addWidget(close_btn)
        layout.addLayout(footer)

        self._populate_related_sales_comparison_table(table=table, totals_table=totals_table, empty_label=empty, rows=rows)
        QTimer.singleShot(0, lambda: self._sync_related_sales_comparison_layout(table=table, totals_table=totals_table, groups_spacer=groups_spacer, groups_prev=groups_prev, groups_curr=groups_curr, groups_delta=groups_delta))
        return dialog

    def _populate_related_sales_comparison_table(self, *, table: QTableWidget, totals_table: QTableWidget, empty_label: QLabel, rows: list) -> None:
        table.setRowCount(len(rows))
        totals = [0.0] * 9
        for row_idx, item in enumerate(rows):
            values = [
                float(getattr(item, "unidades_prev", 0.0) or 0.0),
                float(getattr(item, "kg_prev", 0.0) or 0.0),
                float(getattr(item, "euros_prev", 0.0) or 0.0),
                float(getattr(item, "unidades_curr", 0.0) or 0.0),
                float(getattr(item, "kg_curr", 0.0) or 0.0),
                float(getattr(item, "euros_curr", 0.0) or 0.0),
                float(getattr(item, "delta_unidades", 0.0) or 0.0),
                float(getattr(item, "delta_kg", 0.0) or 0.0),
                float(getattr(item, "delta_euros", 0.0) or 0.0),
            ]
            totals = [total + value for total, value in zip(totals, values)]
            base_items = [
                QTableWidgetItem(str(getattr(item, "codigo", "") or "")),
                QTableWidgetItem(str(getattr(item, "nombre", "") or "")),
            ]
            for col_idx, base_item in enumerate(base_items):
                base_item.setData(Qt.ItemDataRole.UserRole, row_idx)
                table.setItem(row_idx, col_idx, base_item)
            for offset, value in enumerate(values, start=2):
                suffix = " kg" if offset in (3, 6, 9) else " €" if offset in (4, 7, 10) else ""
                number_item = NumericSortableTableWidgetItem(self._format_sales_number(value, suffix=suffix), value)
                number_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                number_item.setData(Qt.ItemDataRole.UserRole, value)
                if offset >= 8:
                    if value > 0:
                        number_item.setForeground(QColor("#067647"))
                    elif value < 0:
                        number_item.setForeground(QColor("#B42318"))
                table.setItem(row_idx, offset, number_item)

        totals_label = QTableWidgetItem("TOTALES")
        totals_label.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        totals_table.clearSpans()
        totals_table.setSpan(0, 0, 1, 2)
        totals_table.setItem(0, 0, totals_label)
        totals_table.setItem(0, 1, QTableWidgetItem(""))
        for idx, value in enumerate(totals, start=2):
            suffix = " kg" if idx in (3, 6, 9) else " €" if idx in (4, 7, 10) else ""
            item = QTableWidgetItem(self._format_sales_number(value, suffix=suffix))
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if idx >= 8:
                if value > 0:
                    item.setForeground(QColor("#067647"))
                elif value < 0:
                    item.setForeground(QColor("#B42318"))
            totals_table.setItem(0, idx, item)
        self._sync_related_sales_comparison_layout(table=table, totals_table=totals_table, groups_spacer=None, groups_prev=None, groups_curr=None, groups_delta=None)

        has_rows = bool(rows)
        table.setVisible(has_rows)
        totals_table.setVisible(has_rows)
        empty_label.setVisible(not has_rows)
        table.setSortingEnabled(True)

    def _sync_related_sales_comparison_layout(self, *, table: QTableWidget, totals_table: QTableWidget, groups_spacer: QWidget | None, groups_prev: QLabel | None, groups_curr: QLabel | None, groups_delta: QLabel | None) -> None:
        for column in range(table.columnCount()):
            totals_table.setColumnWidth(column, table.columnWidth(column))

        total_item = totals_table.item(0, 0)
        if total_item is not None:
            total_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        if groups_spacer is None or groups_prev is None or groups_curr is None or groups_delta is None:
            return

        left_width = table.columnWidth(0) + table.columnWidth(1)
        prev_width = sum(table.columnWidth(column) for column in range(2, 5))
        curr_width = sum(table.columnWidth(column) for column in range(5, 8))
        delta_width = sum(table.columnWidth(column) for column in range(8, 11))

        groups_spacer.setFixedWidth(max(0, left_width))
        groups_prev.setFixedWidth(max(0, prev_width))
        groups_curr.setFixedWidth(max(0, curr_width))
        groups_delta.setFixedWidth(max(0, delta_width))

    def _open_related_sales_chart(self, *, rows: list, year: int, customer_name: str, parent: QWidget | None = None) -> None:
        if not rows:
            return
        dialog = CustomerSalesComparisonChartDialog(rows=rows, year=year, customer_name=customer_name, parent=parent or self)
        dialog.exec()

    @staticmethod
    def _sales_comparison_pdf_filename(year: int, customer_name: str) -> str:
        safe_customer_name = str(customer_name or "").strip() or "Cliente"
        return f"Comparativa - {int(year) - 1} vs {int(year)} - {safe_customer_name}.pdf"

    @staticmethod
    def _sales_comparison_rows_in_table_order(table: QTableWidget, rows: list) -> list:
        ordered_rows: list = []
        for table_row in range(table.rowCount()):
            item = table.item(table_row, 0)
            source_row = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
            if isinstance(source_row, int) and 0 <= source_row < len(rows):
                ordered_rows.append(rows[source_row])
        return ordered_rows or list(rows)

    def _export_related_sales_comparison_excel(self, *, rows: list, year: int, customer_name: str, parent: QWidget | None = None) -> None:
        if not rows:
            return
        safe_customer_name = customer_name.strip() or "Cliente"
        default_name = f"Comparativa - {year - 1} vs {year} - {safe_customer_name}"
        default = str(self.report_export_service.default_path(default_name, "xlsx"))
        path, _ = QFileDialog.getSaveFileName(parent or self, "Guardar comparativa Excel", default, "Excel (*.xlsx)")
        if not path:
            return
        headers = [
            "Referencia", "Descripción",
            f"Unid. {year - 1}", f"Kg {year - 1}", f"€ {year - 1}",
            f"Unid. {year}", f"Kg {year}", f"€ {year}",
            "Δ Unid.", "Δ Kg", "Δ €",
        ]
        export_rows = []
        for row in rows:
            export_rows.append([
                str(getattr(row, "codigo", "") or "").strip(),
                str(getattr(row, "nombre", "") or "").strip(),
                self._format_sales_number(getattr(row, "unidades_prev", 0.0) or 0.0),
                self._format_sales_number(getattr(row, "kg_prev", 0.0) or 0.0, suffix=" kg"),
                self._format_sales_number(getattr(row, "euros_prev", 0.0) or 0.0, suffix=" €"),
                self._format_sales_number(getattr(row, "unidades_curr", 0.0) or 0.0),
                self._format_sales_number(getattr(row, "kg_curr", 0.0) or 0.0, suffix=" kg"),
                self._format_sales_number(getattr(row, "euros_curr", 0.0) or 0.0, suffix=" €"),
                self._format_sales_number(getattr(row, "delta_unidades", 0.0) or 0.0),
                self._format_sales_number(getattr(row, "delta_kg", 0.0) or 0.0, suffix=" kg"),
                self._format_sales_number(getattr(row, "delta_euros", 0.0) or 0.0, suffix=" €"),
            ])
        try:
            out = self.report_export_service.export_excel(path, default_name, headers, export_rows, sheet_title="Comparativa ventas")
        except Exception as exc:
            QMessageBox.warning(parent or self, "Comparativa Excel", f"No se pudo exportar el Excel.\n\n{exc}")
            return
        QMessageBox.information(parent or self, "Comparativa Excel", f"Excel generado correctamente.\n\n{out}")

    def _export_related_sales_comparison_pdf(self, *, rows: list, year: int, customer_name: str, parent: QWidget | None = None) -> None:
        if not rows:
            return
        safe_customer_name = customer_name.strip() or "Cliente"
        filename = self._sales_comparison_pdf_filename(year, safe_customer_name)
        default = str(self.report_export_service.default_path(Path(filename).stem, "pdf"))
        path, _ = QFileDialog.getSaveFileName(parent or self, "Guardar comparativa PDF", default, "PDF (*.pdf)")
        if not path:
            return
        try:
            out = self.report_export_service.export_customer_sales_comparison_pdf(
                path,
                customer_name=safe_customer_name,
                year=year,
                rows=rows,
            )
        except Exception as exc:
            QMessageBox.warning(parent or self, "Comparativa PDF", f"No se pudo exportar el PDF.\n\n{exc}")
            return
        QMessageBox.information(parent or self, "Comparativa PDF", f"PDF generado correctamente.\n\n{out}")

    def _build_recipes_tab(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("customerRecipesPanel")
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
            self._configure_agenda_calendar(calendar_edit)
            if calendar_edit.lineEdit() is not None:
                calendar_edit.lineEdit().setAlignment(Qt.AlignmentFlag.AlignCenter)

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

    def _refresh_agenda_view(self, *_args) -> None:
        selected = self._selected_row()
        if selected is None:
            if hasattr(self, "agenda_table"):
                self.agenda_table.setRowCount(0)
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

        tipo = self._normalize_agenda_type(getattr(item, "tipo", ""))
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
        normalized = self._normalize_agenda_type(value)
        icon_map = {
            "visita": "calendar-check.svg",
            "demo": "calendar.svg",
            "llamada": "phone-call.svg",
            "seguimiento": "history.svg",
            "desarrollo_futuro": "lightbulb.svg",
            "incidencia": "triangle-alert.svg",
            "nota": "file-pen.svg",
        }
        icon_name = icon_map.get(normalized, "history.svg")
        return BASE_DIR / "assets" / "icons" / icon_name

    def _agenda_type_color(self, value: str) -> str:
        normalized = self._normalize_agenda_type(value)
        palette = {
            "visita": "#DCEBFF",
            "demo": "#E0F2FE",
            "llamada": "#DCF7EA",
            "seguimiento": "#DDF6F1",
            "desarrollo_futuro": "#FEF1D8",
            "incidencia": "#FDE3E2",
            "nota": "#EEF2F7",
        }
        return palette.get(normalized, "#EEF2F7")

    def _agenda_type_accent_color(self, value: str) -> str:
        normalized = self._normalize_agenda_type(value)
        palette = {
            "visita": "#2563EB",
            "demo": "#0369A1",
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
        for calendar_edit in (fecha_edit, seguimiento_edit):
            self._configure_agenda_calendar(calendar_edit)

        if activity is not None:
            activity_type = self._normalize_agenda_type(getattr(activity, "tipo", "") or "nota")
            tipo_combo.setCurrentIndex(max(0, tipo_combo.findData(activity_type)))
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

    @staticmethod
    def _configure_agenda_calendar(date_edit: QDateEdit) -> None:
        calendar_widget = date_edit.calendarWidget()
        if calendar_widget is None:
            return
        calendar_widget.setMinimumSize(340, 272)
        calendar_widget.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
        calendar_widget.setGridVisible(True)
        calendar_widget.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.ShortDayNames)
        calendar_widget.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.ISOWeekNumbers)

        header_format = QTextCharFormat()
        header_format.setBackground(QColor("#5B8DEF"))
        header_format.setForeground(QColor("#FFFFFF"))
        calendar_widget.setHeaderTextFormat(header_format)

        weekend_format = QTextCharFormat()
        weekend_format.setForeground(QColor("#D94C5C"))
        calendar_widget.setWeekdayTextFormat(Qt.DayOfWeek.Saturday, weekend_format)
        calendar_widget.setWeekdayTextFormat(Qt.DayOfWeek.Sunday, weekend_format)
        calendar_widget.setObjectName("customerAgendaPopupCalendar")
        calendar_view = calendar_widget.findChild(QAbstractItemView, "qt_calendar_calendarview")
        if calendar_view is not None:
            calendar_view.setItemDelegate(AgendaCalendarDelegate(calendar_view))

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
            ("visita", "Visita"),
            ("demo", "Demo"),
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
        normalized = self._normalize_agenda_type(value)
        return options.get(normalized, normalized.replace("_", " ").title())

    @staticmethod
    def _normalize_agenda_type(value: object) -> str:
        normalized = str(value or "").strip().lower()
        if normalized in {"visita_realizada", "visita_prevista"}:
            return "visita"
        return normalized

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

    def _open_customer_queries_dialog(self) -> None:
        dialog = CustomerQueriesDialog(service=self.customer_query_service, parent=self)
        self._customer_queries_dialog = dialog
        dialog.exec()

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
        self.detail_municipio = QLineEdit(panel)
        self.detail_municipio.setPlaceholderText("Escribe o selecciona un municipio")
        self.lbl_calle = QLabel("Calle", panel)
        self.detail_direccion = QLineEdit(panel)
        self.lbl_cp = QLabel("C.P.", panel)
        self.detail_cp = QLineEdit(panel)
        self.detail_cp.setPlaceholderText("C.P.")
        self.lbl_localidad = QLabel("Localidad", panel)
        self.detail_localidad = QComboBox(panel)
        self._layout_left_detail_abs()

        self.detail_provincia.currentIndexChanged.connect(self._on_provincia_changed)
        self.detail_isla.currentIndexChanged.connect(self._on_isla_changed)
        self.detail_municipio_options: dict[str, str] = {}
        self.detail_cp_options: set[str] = set()
        self.detail_selected_municipio_id = ""
        self.detail_selected_cp = ""
        self.detail_municipio_completer = self._build_detail_lookup_completer(self.detail_municipio)
        self.detail_cp_completer = self._build_detail_lookup_completer(self.detail_cp)
        self.detail_municipio.editingFinished.connect(self._on_detail_municipio_editing_finished)
        self.detail_cp.editingFinished.connect(self._on_detail_cp_editing_finished)
        self.detail_municipio_completer.activated.connect(self._on_detail_municipio_editing_finished)
        self.detail_cp_completer.activated.connect(self._on_detail_cp_editing_finished)
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
        right_edge = max(5, panel.width() - 4)
        col1 = 120
        col2 = max(180, w - col1 - col_gap)

        self.lbl_cod.setGeometry(5, 2, 80, 20)
        self.lbl_nombre_comercial.setGeometry(95, 2, max(0, right_edge - 95), 20)
        y += label_h + 4
        self.detail_codigo.setGeometry(5, 26, 80, 28)
        self.detail_nombre_comercial.setGeometry(95, 26, max(0, right_edge - 95), 28)

        y += field_h + row_gap
        c1 = (w - 2 * col_gap) // 3
        c2 = c1
        c3 = w - c1 - c2 - 2 * col_gap
        self.lbl_telefono.setGeometry(5, 64, 120, 20)
        self.lbl_cif.setGeometry(135, 64, 100, 20)
        self.lbl_nombre_fiscal.setGeometry(245, 64, max(0, right_edge - 245), 20)
        y += label_h + 4
        self.detail_telefono.setGeometry(5, 86, 120, 28)
        self.detail_cif.setGeometry(135, 86, 100, 28)
        self.detail_nombre_fiscal.setGeometry(245, 86, max(0, right_edge - 245), 28)

        y += field_h + row_gap
        self.lbl_provincia.setGeometry(5, 126, 165, 20)
        self.lbl_isla.setGeometry(175, 126, 100, 20)
        self.lbl_municipio.setGeometry(285, 126, max(0, right_edge - 285), 20)
        y += label_h + 4
        self.detail_provincia.setGeometry(5, 150, 165, 28)
        self.detail_isla.setGeometry(175, 150, 100, 28)
        self.detail_municipio.setGeometry(285, 150, max(0, right_edge - 285), 28)

        y += field_h + row_gap
        c1b = int(w * 0.52)
        c2b = int(w * 0.22)
        c3b = w - c1b - c2b - 2 * col_gap
        self.lbl_calle.setGeometry(5, 190, 270, 20)
        self.lbl_cp.setGeometry(285, 190, 80, 20)
        self.lbl_localidad.setGeometry(375, 190, max(0, right_edge - 375), 20)
        y += label_h + 4
        self.detail_direccion.setGeometry(5, 214, 270, 28)
        self.detail_cp.setGeometry(285, 214, 80, 28)
        self.detail_localidad.setGeometry(375, 214, max(0, right_edge - 375), 28)

    def _build_upper_right_detail_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("detailSubPanel")
        self.right_detail_panel = panel

        self.sectors_box = QFrame(panel)
        sectors_box = self.sectors_box
        sectors_box.setObjectName("plainGroup")
        sectors_box.setFrameShape(QFrame.Shape.NoFrame)
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
            checkbox.setMinimumHeight(32)
            self.tipo_checks[label] = checkbox

        self.otros_placeholder = QCheckBox("Otros", sectors_box)
        self.otros_placeholder.setObjectName("otros_placeholder")
        self.otros_placeholder.setMinimumHeight(32)
        self.tipo_checks["OTROS"] = self.otros_placeholder

        sectors_layout = QGridLayout(sectors_box)
        sectors_layout.setContentsMargins(0, 0, 0, 0)
        sectors_layout.setHorizontalSpacing(8)
        sectors_layout.setVerticalSpacing(8)
        for idx, (label, _icon) in enumerate(labels):
            sectors_layout.addWidget(self.tipo_checks[label], idx // 2, idx % 2)
        sectors_layout.addWidget(self.otros_placeholder, 3, 0, 1, 2)

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
        status_box.setFrameShape(QFrame.Shape.NoFrame)
        self.status_group = QButtonGroup(self)
        self.detail_activo = QPushButton("Activo", status_box)
        self.detail_inactivo = QPushButton("Inactivo", status_box)
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
        self.lbl_prospeccion.setVisible(False)
        self.detail_prospeccion_si.setVisible(False)
        self.detail_prospeccion_no.setVisible(False)

        status_layout = QHBoxLayout(status_box)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(0)
        status_layout.addWidget(self.detail_activo)
        status_layout.addWidget(self.detail_inactivo)

        fields_layout = QGridLayout()
        fields_layout.setContentsMargins(0, 0, 0, 0)
        fields_layout.setHorizontalSpacing(10)
        fields_layout.setVerticalSpacing(3)
        fields_layout.addWidget(self.section_info, 0, 0)
        fields_layout.addWidget(self.lbl_abrev, 0, 1)
        fields_layout.addWidget(self.detail_tipo, 1, 0)
        fields_layout.addWidget(self.detail_abreviatura, 1, 1)
        fields_layout.setColumnStretch(0, 1)
        fields_layout.setColumnStretch(1, 1)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(sectors_box)
        layout.addLayout(fields_layout)
        layout.addWidget(status_box)

        for line_edit in (
            self.detail_codigo,
            self.detail_nombre_comercial,
            self.detail_telefono,
            self.detail_nombre_fiscal,
            self.detail_direccion,
            self.detail_abreviatura,
        ):
            line_edit.editingFinished.connect(self._schedule_autosave)
        for label, checkbox in self.tipo_checks.items():
            checkbox.toggled.connect(
                lambda checked, activity_label=label: self._enforce_activity_exclusivity(activity_label, checked)
            )
            checkbox.toggled.connect(self._schedule_autosave)
        self.detail_tipo.currentTextChanged.connect(self._schedule_autosave)
        self.detail_activo.toggled.connect(self._schedule_autosave)
        self.detail_inactivo.toggled.connect(self._schedule_autosave)
        self.detail_prospeccion_si.toggled.connect(self._schedule_autosave)
        self.detail_prospeccion_no.toggled.connect(self._schedule_autosave)

        return panel

    def _enforce_activity_exclusivity(self, selected_label: str, checked: bool) -> None:
        """Keep the visual 'Otros' category mutually exclusive without changing persistence."""
        if not checked or getattr(self, "_syncing_activity_selection", False):
            return
        self._syncing_activity_selection = True
        try:
            if selected_label == "OTROS":
                for label, checkbox in self.tipo_checks.items():
                    if label != "OTROS":
                        checkbox.setChecked(False)
            elif self.otros_placeholder.isChecked():
                self.otros_placeholder.setChecked(False)
        finally:
            self._syncing_activity_selection = False

    def _layout_right_detail_abs(self) -> None:
        # Kept as a compatibility hook for callers that also lay out the detail cards.
        # The classification panel itself uses layouts so its controls remain responsive.
        return

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

    def _build_detail_lookup_completer(self, field: QLineEdit) -> QCompleter:
        model = QStringListModel(self)
        completer = QCompleter(model, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        field.setCompleter(completer)
        return completer

    @staticmethod
    def _detail_lookup_value_for_id(options: dict[str, str], selected_id: str) -> str:
        return next((label for label, value in options.items() if value == selected_id), "")

    def _set_detail_municipio_options(self, items: list[tuple[str, str]], selected_id: str = "") -> None:
        self.detail_municipio_options = {label: value for label, value in items}
        self.detail_municipio_completer.model().setStringList(list(self.detail_municipio_options))
        self.detail_selected_municipio_id = selected_id if selected_id in self.detail_municipio_options.values() else ""
        self.detail_municipio.setText(
            self._detail_lookup_value_for_id(self.detail_municipio_options, self.detail_selected_municipio_id)
        )

    def _set_detail_cp_options(self, items: list[tuple[str, str]], selected_cp: str = "") -> None:
        self.detail_cp_options = {value for _label, value in items}
        self.detail_cp_completer.model().setStringList(sorted(self.detail_cp_options))
        self.detail_selected_cp = selected_cp if selected_cp in self.detail_cp_options else ""
        self.detail_cp.setText(self.detail_selected_cp)

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

    def _populate_municipios(self, isla_id: str, selected_id: str = "", codigo_postal: str = "") -> None:
        cp = str(codigo_postal or "").strip()
        municipality_ids_for_cp = {
            str(item.municipio_id or "")
            for item in self.codigos_postales
            if str(item.codigo_postal or "").strip() == cp
        }
        items = [
            (str(m.municipio_nombre or ""), str(m.municipio_id or ""))
            for m in self.municipios
            if (
                str(m.isla_id or "") == str(isla_id or "")
                and m.municipio_nombre
                and (not cp or str(m.municipio_id or "") in municipality_ids_for_cp)
            )
        ]
        self._set_detail_municipio_options(items, selected_id)

    def _populate_cps(self, isla_id: str, selected_cp: str = "", municipio_id: str = "") -> None:
        items = [
            (str(cp.codigo_postal or ""), str(cp.codigo_postal or ""))
            for cp in self.codigos_postales
            if (
                str(cp.codigo_postal or "").strip()
                and (not municipio_id or str(cp.municipio_id or "") == str(municipio_id or ""))
                and any(
                    str(m.municipio_id or "") == str(cp.municipio_id or "")
                    and str(m.isla_id or "") == str(isla_id or "")
                    for m in self.municipios
                )
            )
        ]
        unique_items: list[tuple[str, str]] = []
        seen: set[str] = set()
        for label, value in items:
            if value in seen:
                continue
            seen.add(value)
            unique_items.append((label, value))
        self._set_detail_cp_options(unique_items, selected_cp)

    def _populate_localidades(
        self,
        municipio_id: str,
        codigo_postal: str,
        selected_localidad_id: str = "",
    ) -> None:
        cp = str(codigo_postal or "").strip()
        municipality_id = str(municipio_id or "").strip()
        if not cp or not municipality_id:
            items: list[tuple[str, str]] = []
        else:
            items = [
                (str(loc.localidad_nombre or ""), str(loc.localidad_id or ""))
                for loc in self.localidades
                if (
                    str(loc.municipio_id or "") == municipality_id
                    and str(loc.codigo_postal or "").strip() == cp
                    and loc.localidad_nombre
                )
            ]
        self._fill_combo(self.detail_localidad, items, selected_localidad_id)

    def _on_provincia_changed(self, _idx: int) -> None:
        if self._is_loading_details:
            return
        provincia_id = str(self.detail_provincia.currentData() or "")
        self._populate_islas(provincia_id, "")
        self._populate_municipios("", "")
        self._populate_cps("", "")
        self._populate_localidades("", "", "")
        self._schedule_autosave()

    def _on_isla_changed(self, _idx: int) -> None:
        if self._is_loading_details:
            return
        isla_id = str(self.detail_isla.currentData() or "")
        self._populate_municipios(isla_id, "")
        self._populate_cps(isla_id, "")
        self._populate_localidades("", "", "")
        self._schedule_autosave()

    def _on_detail_municipio_editing_finished(self, *_args) -> None:
        if self._is_loading_details:
            return
        entered_name = self.detail_municipio.text().strip()
        self.detail_selected_municipio_id = self.detail_municipio_options.get(entered_name, "")
        if not self.detail_selected_municipio_id:
            self.detail_municipio.clear()
        isla_id = str(self.detail_isla.currentData() or "")
        self._populate_cps(isla_id, self.detail_selected_cp, self.detail_selected_municipio_id)
        self._populate_localidades(self.detail_selected_municipio_id, self.detail_selected_cp, "")
        self._schedule_autosave()

    def _on_detail_cp_editing_finished(self, *_args) -> None:
        if self._is_loading_details:
            return
        entered_cp = self.detail_cp.text().strip()
        self.detail_selected_cp = entered_cp if entered_cp in self.detail_cp_options else ""
        if not self.detail_selected_cp:
            self.detail_cp.clear()
        isla_id = str(self.detail_isla.currentData() or "")
        self._populate_municipios(isla_id, self.detail_selected_municipio_id, self.detail_selected_cp)
        self._populate_localidades(self.detail_selected_municipio_id, self.detail_selected_cp, "")
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

    def _update_search_counter(self, found: int, total: int) -> None:
        if hasattr(self, "search_counter_label"):
            self.search_counter_label.setText(f"{max(0, int(found))}/{max(0, int(total))}")

    def _list(self, term: str) -> list:
        return self.customer_service.list(term)

    def _create(self, payload: dict):
        return self.customer_service.create(payload)

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
        self._populate_classification_filter()
        term = self.search_input.text().strip()
        all_rows = self._list("")
        self.rows = self._list(term) if term else list(all_rows)
        selected_isla_id = str(self.island_filter.currentData() or "").strip() if hasattr(self, "island_filter") else ""
        if selected_isla_id:
            self.rows = [
                row
                for row in self.rows
                if str(getattr(row, "cliente_direccion_isla_id", "") or "").strip() == selected_isla_id
            ]
        selected_classification = (
            str(self.classification_filter.currentData() or "").strip()
            if hasattr(self, "classification_filter")
            else ""
        )
        if selected_classification:
            self.rows = [
                row
                for row in self.rows
                if self._matches_customer_classification(row, selected_classification)
            ]
        self._update_search_counter(len(self.rows), len(all_rows))
        self._render_table()
        self._reload_related_sales_years()
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

    def _populate_classification_filter(self) -> None:
        if not hasattr(self, "classification_filter"):
            return
        current = str(self.classification_filter.currentData() or "").strip()
        classifications = [
            ("Todas las clasificaciones", ""),
            ("Panadería", "PANADERIA"),
            ("Pastelería", "PASTELERIA"),
            ("Heladería", "HELADERIA"),
            ("Cafetería", "CAFETERIA"),
            ("Restaurante", "RESTAURANTE"),
            ("Hotel", "HOTEL"),
            ("Otros", "OTROS"),
        ]
        self.classification_filter.blockSignals(True)
        self.classification_filter.clear()
        for label, value in classifications:
            self.classification_filter.addItem(label, value)
        index = self.classification_filter.findData(current)
        self.classification_filter.setCurrentIndex(index if index >= 0 else 0)
        self.classification_filter.blockSignals(False)

    def _matches_customer_classification(self, row: Cliente, classification: str) -> bool:
        activity = str(getattr(row, "cliente_actividad", "") or "")
        return self._activity_matches(activity, classification)

    def _render_table(self) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.rows))
        for row_idx, item in enumerate(self.rows):
            code_item = QTableWidgetItem()
            distributor_code = str(getattr(item, "cliente_codigo_distribuidor", "") or "").strip()
            code_item.setData(Qt.ItemDataRole.DisplayRole, distributor_code)
            name = str(item.cliente_nombre_comercial or item.cliente_nombre_fiscal or "")
            icon = self._customer_icon(item)
            label = f"{icon} {name}".strip() if icon else name
            name_item = QTableWidgetItem(label)
            list_icon = self._customer_list_icon(item)
            if not list_icon.isNull():
                name_item.setIcon(list_icon)
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
        activity = str(getattr(item, "cliente_actividad", "") or "")
        if self._activity_matches(activity, "OTROS"):
            return ""
        text = ",".join(
            [
                activity,
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

    def _customer_list_icon(self, item: Cliente) -> QIcon:
        activity = str(getattr(item, "cliente_actividad", "") or "")
        if self._activity_matches(activity, "OTROS"):
            return QIcon(str(BASE_DIR / "assets" / "icons" / "circle-question-mark.svg"))
        return QIcon()

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
        if hasattr(self, "ai_summary_btn"):
            self.ai_summary_btn.setEnabled(row is not None)
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
            self._populate_localidades("", "", "")
            self.detail_tipo.setCurrentIndex(0)
            for checkbox in self.tipo_checks.values():
                checkbox.setChecked(False)
            self.detail_inactivo.setChecked(False)
            self.detail_activo.setChecked(False)
            self.detail_prospeccion_no.setChecked(True)
            self._render_related_contacts("")
            self._render_related_sales("")
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
        self._populate_cps(isla_id, codigo_postal, municipio_id)
        self._populate_localidades(municipio_id, codigo_postal, localidad_id)
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
        self._render_related_sales(str(getattr(row, "cliente_id", "") or ""))
        self._render_related_recipes(str(getattr(row, "cliente_id", "") or ""))
        self._render_customer_agenda(str(getattr(row, "cliente_id", "") or ""))
        self._is_loading_details = False

    def _open_customer_ai_summary(self) -> None:
        customer = self._selected_row()
        if customer is None:
            QMessageBox.information(self, "Resumen IA", "Selecciona un cliente para generar el resumen.")
            return

        customer_name = str(
            getattr(customer, "cliente_nombre_comercial", "")
            or getattr(customer, "cliente_nombre_fiscal", "")
            or "Cliente"
        ).strip()
        if self._customer_ai_summary_dialog is not None:
            self._customer_ai_summary_dialog.close()
        dialog = CustomerAISummaryDialog(customer_name=customer_name, parent=self)
        self._customer_ai_summary_dialog = dialog
        dialog.retry_requested.connect(lambda: self._start_customer_ai_summary(customer, dialog))
        dialog.show()
        self._start_customer_ai_summary(customer, dialog)

    def _start_customer_ai_summary(self, customer: object, dialog: CustomerAISummaryDialog) -> None:
        token = uuid4().hex
        self._customer_ai_summary_request_token = token
        dialog.set_loading()
        self.ai_summary_btn.setEnabled(False)
        self._customer_ai_summary_runner.start(token, self.customer_ai_summary_service, customer)

    def _handle_customer_ai_summary_result(self, token: str, result: CustomerAISummaryResult) -> None:
        if token != self._customer_ai_summary_request_token:
            return
        self.ai_summary_btn.setEnabled(self._selected_row() is not None)
        dialog = self._customer_ai_summary_dialog
        if dialog is not None:
            dialog.set_result(result)

    def _handle_customer_ai_summary_failure(self, token: str, message: str) -> None:
        if token != self._customer_ai_summary_request_token:
            return
        self.ai_summary_btn.setEnabled(self._selected_row() is not None)
        dialog = self._customer_ai_summary_dialog
        if dialog is not None:
            dialog.set_result(CustomerAISummaryResult(False, "", message))

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
        checkmark_white_icon = (BASE_DIR / "assets" / "icons" / "checkmark_white.svg").as_posix()
        style = """
            QWidget {
                font-family: 'Segoe UI', 'Inter';
            }
            QWidget#CustomersPageRoot {
                background: #EEF3F8;
                border: 0;
            }
            QSplitter#customersMainSplitter {
                background: transparent;
                border: 0;
            }
            QSplitter#customersMainSplitter::handle {
                background: transparent;
                border: 0;
                width: 0px;
            }
            QWidget#customersLeftPanel {
                background: #FFFFFF;
                border: 1px solid #D7DEE8;
                border-radius: 8px;
            }
            QWidget#customersCatalogBody {
                background: #FFFFFF;
                border: 1px solid #D7DEE8;
                border-bottom-left-radius: 7px;
                border-bottom-right-radius: 7px;
            }
            QWidget#customerDetailBody {
                background: #FFFFFF;
                border: none;
                border-bottom-left-radius: 7px;
                border-bottom-right-radius: 7px;
            }
            QWidget#customerClassificationBody {
                background: #FFFFFF;
                border: none;
                border-bottom-left-radius: 7px;
                border-bottom-right-radius: 7px;
            }
            QWidget#customersRightPanel {
                background: transparent;
                border: 0;
                border-radius: 8px;
            }
            QSplitter#customersDetailSplitter {
                background: transparent;
                border: 0;
            }
            QSplitter#customersDetailSplitter::handle {
                background: transparent;
                border: 0;
                width: 0px;
                height: 0px;
            }
            QWidget#detailTopArea {
                background: transparent;
                border: 0;
            }
            QFrame#crmCard, QWidget#crmCard {
                background: transparent;
                border: 0;
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
                min-height: 26px;
                border-radius: 8px;
                padding: 4px 10px;
            }
            QPushButton[btnRole="success"] {
                background: #DCFCE7;
                color: #166534;
                border: 1px solid #86EFAC;
                font-weight: 600;
            }
            QPushButton[btnRole="warning"] {
                background: #FEF3C7;
                color: #92400E;
                border: 1px solid #FCD34D;
                font-weight: 600;
            }
            QPushButton[btnRole="danger"] {
                background: #FEE2E2;
                color: #B91C1C;
                border: 1px solid #FCA5A5;
                font-weight: 600;
            }
            QPushButton[btnRole="secondary"] {
                background: #E2E8F0;
                color: #334155;
                border: 1px solid #CBD5E1;
                font-weight: 500;
            }
            QPushButton[btnRole="primary"] {
                background: #DBEAFE;
                color: #1D4ED8;
                border: 1px solid #93C5FD;
                font-weight: 600;
            }
            QPushButton[btnRole="info"] {
                background: #F3E8FF;
                color: #6B21A8;
                border: 1px solid #D8B4FE;
                font-weight: 600;
            }
            QPushButton#customerSearchClearButton {
                min-width: 30px;
                max-width: 30px;
                min-height: 30px;
                max-height: 30px;
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
            QLabel#customerSearchCounterLabel {
                min-height: 30px;
                max-height: 30px;
                padding: 0 8px;
                border: 1px solid #D1D5DB;
                border-radius: 8px;
                background: #F8FAFC;
                color: #334155;
                font-size: 12px;
                font-weight: 700;
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
            QTableWidget[tableVariant="standard"] {
                border: 1px solid #DCE4EF;
                border-radius: 8px;
                background: #FFFFFF;
                alternate-background-color: #FAFBFF;
                selection-background-color: #3083FF;
                gridline-color: #EEF2F7;
            }
            QTableWidget[tableVariant="standard"]::item {
                padding: 7px;
            }
            QTableWidget[tableVariant="standard"]::item:selected {
                color: #FFFFFF;
            }
            QTableWidget[tableVariant="standard"]::item:focus {
                border: none;
                outline: 0;
            }
            QTableWidget[tableVariant="standard"] QHeaderView::section {
                background: #D1D1D1;
                color: #000000;
                border: 0;
                border-right: 1px solid #A3A3A3;
                border-bottom: 1px solid #D1D1D1;
                padding: 6px 8px;
                border-radius: 0;
            }
            QTableWidget[tableVariant="standard"] QHeaderView::section:first {
                border-top-left-radius: 8px;
            }
            QTableWidget[tableVariant="standard"] QHeaderView::section:last {
                border-right: 0;
            }
            QTableWidget#customersListTable {
                background: #FFFFFF;
                color: #0B2F5B;
                border: 1px solid #D6E0EA;
                border-radius: 8px;
                gridline-color: #E1E8F0;
                alternate-background-color: #F8FAFD;
                selection-background-color: #E5F7F4;
                selection-color: #0B2F5B;
            }
            QTableWidget#customersListTable::item {
                padding: 4px 7px;
            }
            QTableWidget#customersListTable::item:selected {
                background: #E5F7F4;
                color: #0B2F5B;
            }
            QTableWidget#customersListTable QHeaderView::section {
                background: #EEF3F8;
                color: #0B2F5B;
                border: 0;
                border-right: 1px solid #D6E0EA;
                border-bottom: 1px solid #D6E0EA;
                padding: 7px 6px;
                font-weight: 700;
            }
            QTableWidget#customersListTable QScrollBar:vertical {
                width: 8px;
                background: transparent;
                margin: 3px 1px;
            }
            QTableWidget#customersListTable QScrollBar::handle:vertical {
                min-height: 24px;
                background: #B8C7D8;
                border-radius: 4px;
            }
            QTableWidget#customersListTable QScrollBar::add-line:vertical,
            QTableWidget#customersListTable QScrollBar::sub-line:vertical {
                height: 0;
            }
            QWidget#relatedContactsPanel,
            QWidget#customerSalesPanel,
            QWidget#customerAgendaPanel,
            QWidget#customerRecipesPanel {
                background: #FFFFFF;
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
            QWidget#customerSalesComparisonGroupsBar {
                background: transparent;
            }
            QWidget#customerSalesComparisonGroupsSpacer {
                background: transparent;
                border: none;
            }
            QLabel#customerSalesComparisonGroupPrev,
            QLabel#customerSalesComparisonGroupCurr,
            QLabel#customerSalesComparisonGroupDelta {
                min-height: 28px;
                max-height: 28px;
                padding: 0 10px;
                border-radius: 8px;
                font-weight: 700;
                color: #1F2A44;
                border: 1px solid transparent;
            }
            QLabel#customerSalesComparisonGroupPrev {
                background: #E8F0FE;
                border-color: #BFDBFE;
                color: #1D4ED8;
            }
            QLabel#customerSalesComparisonGroupCurr {
                background: #DCFCE7;
                border-color: #BBF7D0;
                color: #15803D;
            }
            QLabel#customerSalesComparisonGroupDelta {
                background: #F3E8FF;
                border-color: #DDD6FE;
                color: #7C3AED;
            }
            QTableWidget#customerSalesComparisonTotals {
                border: 1px solid #D8E3F2;
                border-radius: 8px;
                background: #EEF4FF;
                gridline-color: #D8E3F2;
            }
            QTableWidget#customerSalesComparisonTotals::item {
                padding: 4px 8px;
                background: #EEF4FF;
                border: 0;
            }
            QTableWidget#customerSalesComparisonTotals::item:selected {
                background: #EEF4FF;
            }
            QTableWidget#customerSalesTotals {
                border: 1px solid #D8E3F2;
                border-radius: 8px;
                background: #EEF4FF;
                gridline-color: #D8E3F2;
            }
            QTableWidget#customerSalesTotals::item {
                padding: 4px 8px;
                background: #EEF4FF;
                color: #1F2A44;
                border: 0;
            }
            QTableWidget#customerSalesTotals::item:selected {
                background: #EEF4FF;
                color: #1F2A44;
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
            QComboBox#customerAgendaFilter, QDateEdit#customerAgendaFilterDate {
                min-height: 24px;
                max-height: 24px;
                padding: 0px 6px;
                border: 1px solid #C9D5E6;
                border-radius: 8px;
                background: #FFFFFF;
                color: #334155;
                font-weight: 600;
                font-size: 11px;
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
                min-height: 26px;
                max-height: 26px;
                background: #1769AA;
                padding: 1px 5px;
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
            QCalendarWidget#customerAgendaPopupCalendar QToolButton#qt_calendar_nextmonth {
                min-width: 20px;
                max-width: 20px;
                min-height: 20px;
                max-height: 20px;
                padding: 0;
                margin: 0 2px;
                border: none;
                border-radius: 10px;
                background: #4D9B31;
            }
            QCalendarWidget#customerAgendaPopupCalendar QToolButton#qt_calendar_prevmonth:hover,
            QCalendarWidget#customerAgendaPopupCalendar QToolButton#qt_calendar_nextmonth:hover {
                background: #3F8128;
            }
            QCalendarWidget#customerAgendaPopupCalendar QToolButton#qt_calendar_monthbutton,
            QCalendarWidget#customerAgendaPopupCalendar QToolButton#qt_calendar_yearbutton {
                min-height: 24px;
                max-height: 24px;
                padding: 0 3px;
                margin: 0;
                border: none;
                background: transparent;
                color: #FFFFFF;
                font-weight: 700;
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
                outline: none;
                selection-background-color: #5B8DEF;
                selection-color: #FFFFFF;
            }
            QCalendarWidget#customerAgendaPopupCalendar QAbstractItemView::item {
                padding: 0;
                border: none;
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
                min-width: 72px;
                max-width: 72px;
            }
            QCalendarWidget#customerAgendaPopupCalendar QToolButton#qt_calendar_yearbutton {
                min-width: 44px;
                max-width: 44px;
            }
            QCalendarWidget#customerAgendaPopupCalendar QAbstractSpinBox {
                min-width: 66px;
                max-width: 66px;
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
                min-height: 30px;
                padding: 0px 10px;
                font-size: 11px;
                color: #0F172A;
                font-weight: 600;
                background: #FFFFFF;
                border: 1px solid #D7DEE8;
                border-radius: 10px;
            }
            QCheckBox#sectorChipPillPanaderia::indicator,
            QCheckBox#sectorChipPillPasteleria::indicator,
            QCheckBox#sectorChipPillHeladeria::indicator,
            QCheckBox#sectorChipPillCafeteria::indicator,
            QCheckBox#sectorChipPillRestaurante::indicator,
            QCheckBox#sectorChipPillHotel::indicator {
                width: 13px;
                height: 13px;
                border-radius: 3px;
                border: 1px solid #94A3B8;
                background: #FFFFFF;
            }
            QCheckBox#sectorChipPillPanaderia::indicator:checked,
            QCheckBox#sectorChipPillPasteleria::indicator:checked,
            QCheckBox#sectorChipPillHeladeria::indicator:checked,
            QCheckBox#sectorChipPillCafeteria::indicator:checked,
            QCheckBox#sectorChipPillRestaurante::indicator:checked,
            QCheckBox#sectorChipPillHotel::indicator:checked {
                border-color: #2563EB;
                background: #2563EB;
                image: url("__CHECKMARK_WHITE_ICON__");
            }
            QCheckBox#sectorChipPillPanaderia:checked,
            QCheckBox#sectorChipPillPasteleria:checked,
            QCheckBox#sectorChipPillHeladeria:checked,
            QCheckBox#sectorChipPillCafeteria:checked,
            QCheckBox#sectorChipPillRestaurante:checked,
            QCheckBox#sectorChipPillHotel:checked {
                background: #EFF6FF;
                border: 1px solid #2563EB;
                color: #0B2F5B;
            }
            QCheckBox#otros_placeholder {
                spacing: 6px;
                min-height: 30px;
                padding: 0px 10px;
                font-size: 11px;
                font-weight: 600;
                color: #94A3B8;
                background: #F8FAFC;
                border: 1px solid #D7DEE8;
                border-radius: 10px;
            }
            QCheckBox#otros_placeholder::indicator {
                width: 13px;
                height: 13px;
                border-radius: 3px;
                border: 1px solid #CBD5E1;
                background: #FFFFFF;
            }
            QCheckBox#otros_placeholder::indicator:checked {
                border-color: #2563EB;
                background: #2563EB;
                image: url("__CHECKMARK_WHITE_ICON__");
            }
            QCheckBox#otros_placeholder:checked {
                background: #EFF6FF;
                border: 1px solid #2563EB;
                color: #0B2F5B;
            }
            QPushButton#stateChipActive, QPushButton#stateChipInactive {
                spacing: 0;
                border-radius: 0px;
                min-height: 26px;
                padding: 0px;
                font-size: 10px;
                font-weight: 600;
                text-align: center;
                background: #FFFFFF;
                border: 1px solid #D7DEE8;
                color: #334155;
            }
            QPushButton#stateChipActive {
                border-top-left-radius: 8px;
                border-bottom-left-radius: 8px;
            }
            QPushButton#stateChipInactive {
                border-left: 0px;
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
            }
            QPushButton#stateChipActive:checked {
                background: #2563EB;
                border: 1px solid #2563EB;
                color: #FFFFFF;
            }
            QPushButton#stateChipInactive:checked {
                background: #2563EB;
                border: 1px solid #2563EB;
                color: #FFFFFF;
            }
            """
        self.setStyleSheet(
            style.replace("__AGENDA_ARROW_ICON__", agenda_arrow_icon).replace(
                "__CHECKMARK_WHITE_ICON__", checkmark_white_icon
            )
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
        municipio_id = str(self.detail_selected_municipio_id or "").strip()
        codigo_postal = str(self.detail_selected_cp or "").strip()
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

    def _customer_merge_summary_text(self, preview) -> str:
        labels = {
            "contactos": "Contactos",
            "recetas": "Recetas",
            "agenda": "Agenda",
            "asistentes": "Asistentes",
            "ventas_clientes": "Ventas clientes",
        }
        lines = [
            f"Origen: {preview.source_label}",
            f"Destino: {preview.target_label}",
            "",
            "Datos relacionados detectados:",
        ]
        counts = getattr(preview, "counts", {}) or {}
        for key, label in labels.items():
            lines.append(f"- {label}: {int(counts.get(key, 0) or 0)}")
        lines.append("")
        lines.append("Al confirmar se eliminara el cliente origen.")
        return "\n".join(lines)

    def _merge_selected_customer(self) -> None:
        source = self._selected_row()
        if not source:
            QMessageBox.warning(self, "Clientes", "Selecciona un cliente origen.")
            return
        source_id = str(getattr(source, "cliente_id", "") or "").strip()
        if not source_id:
            QMessageBox.warning(self, "Clientes", "El cliente origen no tiene ID.")
            return

        candidates = [
            row
            for row in self._list("")
            if str(getattr(row, "cliente_id", "") or "").strip() and str(getattr(row, "cliente_id", "") or "").strip() != source_id
        ]
        if not candidates:
            QMessageBox.warning(self, "Clientes", "No hay clientes destino disponibles.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Fusionar cliente")
        dialog.setModal(True)
        dialog.setObjectName("customerMergeDialog")
        layout = QVBoxLayout(dialog)
        layout.setSpacing(10)

        source_label = QLabel(f"Cliente origen: {self._customer_merge_row_label(source)}")
        source_label.setObjectName("customerMergeSourceLabel")
        layout.addWidget(source_label)

        target_filter = QLineEdit()
        target_filter.setObjectName("customerMergeTargetFilter")
        target_filter.setPlaceholderText("Filtrar destino por codigo o nombre...")
        layout.addWidget(QLabel("Filtro destino"))
        layout.addWidget(target_filter)

        target_combo = QComboBox()
        target_combo.setObjectName("customerMergeTargetCombo")
        layout.addWidget(QLabel("Cliente destino"))
        layout.addWidget(target_combo)

        summary = QLabel()
        summary.setObjectName("customerMergeSummary")
        summary.setWordWrap(True)
        layout.addWidget(summary)

        buttons = QDialogButtonBox()
        merge_btn = buttons.addButton("Fusionar", QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_btn = buttons.addButton("Cancelar", QDialogButtonBox.ButtonRole.RejectRole)
        merge_btn.setProperty("btnRole", "danger")
        cancel_btn.setProperty("btnRole", "secondary")
        layout.addWidget(buttons)

        state = {"preview": None}

        def refill_targets() -> None:
            term = self._normalize_filter_text(target_filter.text())
            current_id = str(target_combo.currentData() or "").strip()
            target_combo.blockSignals(True)
            target_combo.clear()
            for item in candidates:
                label = self._customer_merge_row_label(item)
                if term and term not in self._normalize_filter_text(label):
                    continue
                target_combo.addItem(label, str(getattr(item, "cliente_id", "") or "").strip())
            idx = target_combo.findData(current_id)
            target_combo.setCurrentIndex(idx if idx >= 0 else (0 if target_combo.count() else -1))
            target_combo.blockSignals(False)
            update_preview()

        def update_preview() -> None:
            target_id = str(target_combo.currentData() or "").strip()
            if not target_id:
                state["preview"] = None
                summary.setText("No hay clientes destino que coincidan con el filtro.")
                merge_btn.setEnabled(False)
                return
            try:
                preview = self.customer_service.preview_merge(source_id, target_id)
            except Exception as exc:  # noqa: BLE001
                state["preview"] = None
                summary.setText(f"No se pudo preparar la fusion: {exc}")
                merge_btn.setEnabled(False)
                return
            state["preview"] = preview
            summary.setText(self._customer_merge_summary_text(preview))
            merge_btn.setEnabled(True)

        target_filter.textChanged.connect(refill_targets)
        target_combo.currentIndexChanged.connect(update_preview)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        refill_targets()
        if not dialog.exec():
            return

        preview = state.get("preview")
        target_id = str(target_combo.currentData() or "").strip()
        if preview is None or not target_id:
            QMessageBox.warning(self, "Clientes", "No se pudo preparar la fusion.")
            return
        answer = QMessageBox.question(
            self,
            "Confirmar fusion",
            self._customer_merge_summary_text(preview),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            result = self.customer_service.merge_customers(source_id, target_id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Clientes", f"No se pudo fusionar el cliente:\n{exc}")
            return
        QMessageBox.information(
            self,
            "Clientes",
            "Fusion completada.\n\n" + self._customer_merge_summary_text(result),
        )
        self.reload()
        self._select_row_by_id(target_id)

    def _customer_merge_row_label(self, row) -> str:
        code = str(getattr(row, "cliente_codigo", "") or "").strip()
        name = str(getattr(row, "cliente_nombre_comercial", "") or getattr(row, "cliente_nombre_fiscal", "") or "").strip()
        return f"{code} - {name}".strip(" -")

    def _normalize_filter_text(self, value: str) -> str:
        text = str(value or "").strip().lower()
        decomposed = unicodedata.normalize("NFKD", text)
        return "".join(char for char in decomposed if not unicodedata.combining(char))

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
        action_duplicate = menu.addAction("Duplicar cliente")
        action_merge = menu.addAction("Fusionar cliente")
        menu.addSeparator()
        action_copy_id = menu.addAction("Copiar ID")
        action_copy_name = menu.addAction("Copiar nombre")
        action_show_distributor_code = menu.addAction("Ver codigo cliente distribuidor")
        action_edit_distributor_code = menu.addAction("Editar codigo cliente distribuidor")
        action_show_id = menu.addAction("Ver ID")
        menu.addSeparator()
        action_clear_filter = menu.addAction("Vaciar filtro")
        action_refresh = menu.addAction("Refrescar")

        for action in (
            action_edit,
            action_delete,
            action_duplicate,
            action_merge,
            action_copy_id,
            action_copy_name,
            action_show_distributor_code,
            action_edit_distributor_code,
            action_show_id,
        ):
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
        if chosen == action_duplicate:
            self._duplicate_selected_customer()
            return
        if chosen == action_merge:
            self._merge_selected_customer()
            return
        if chosen == action_copy_id and row is not None:
            QApplication.clipboard().setText(str(getattr(row, "cliente_id", "") or ""))
            return
        if chosen == action_copy_name and row is not None:
            QApplication.clipboard().setText(str(getattr(row, "cliente_nombre_comercial", "") or ""))
            return
        if chosen == action_show_distributor_code:
            self._show_customer_distributor_code_dialog()
            return
        if chosen == action_edit_distributor_code:
            self._edit_customer_distributor_code_dialog()
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

    def _show_customer_help(self) -> None:
        QMessageBox.information(
            self,
            "Ayuda",
            "Usa el listado de la izquierda para seleccionar un cliente y revisa sus datos, contactos, ventas, recetas y agenda en el panel derecho.",
        )

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
        self._load_address_catalogs()
        dialog = CustomerEditorDialog(
            title="Nuevo cliente",
            provincias=self.provincias,
            islas=self.islas,
            municipios=self.municipios,
            codigos_postales=self.codigos_postales,
            localidades=self.localidades,
            style_sheet=self.styleSheet(),
            parent=self,
        )
        if dialog.exec():
            payload = dialog.get_payload()
            self._create(payload)
            self.reload()

    def _edit_entity(self) -> None:
        row = self._selected_row()
        if not row:
            QMessageBox.warning(self, "Atencion", "Selecciona un cliente.")
            return
        self._load_address_catalogs()
        initial = {field["name"]: getattr(row, field["name"], None) for field in self.edit_schema}
        initial["cliente_codigo"] = getattr(row, "cliente_codigo", "")
        dialog = CustomerEditorDialog(
            title="Editar cliente",
            provincias=self.provincias,
            islas=self.islas,
            municipios=self.municipios,
            codigos_postales=self.codigos_postales,
            localidades=self.localidades,
            initial=initial,
            style_sheet=self.styleSheet(),
            parent=self,
        )
        if dialog.exec():
            payload = dialog.get_payload()
            self._update(row.cliente_id, payload)
            self.reload()

    def _duplicate_selected_customer(self) -> None:
        row = self._selected_row()
        if not row:
            QMessageBox.warning(self, "Atencion", "Selecciona un cliente.")
            return

        source_label = self._customer_merge_row_label(row)
        answer = QMessageBox.question(
            self,
            "Duplicar cliente",
            (
                f"Duplicar cliente {source_label}?\n\n"
                "Se copiara solo el detalle del cliente.\n"
                "No se copiaran contactos, ventas, recetas ni agenda.\n"
                "El duplicado tendra UUID y codigo de cliente nuevos."
            ),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        detail_fields = (
            "cliente_codigo_distribuidor",
            "cliente_nombre_comercial",
            "cliente_nombre_fiscal",
            "cliente_nombre_interno",
            "cliente_abreviatura",
            "cliente_cif",
            "cliente_telefono",
            "cliente_email",
            "cliente_direccion",
            "cliente_direccion_cp",
            "cliente_direccion_localidad_id",
            "cliente_direccion_municipio_id",
            "cliente_direccion_provincia_id",
            "cliente_direccion_isla_id",
            "cliente_tipo",
            "cliente_actividad",
            "cliente_prospeccion",
            "distribuidor_id",
            "distribuidor_comercial_id",
            "activo",
        )
        payload = {field: getattr(row, field, None) for field in detail_fields}

        try:
            created = self._create(payload)
        except Exception as exc:
            QMessageBox.warning(self, "Clientes", f"No se pudo duplicar el cliente:\n{exc}")
            return

        created_id = str(getattr(created, "cliente_id", "") or "").strip()
        self.reload()
        if created_id:
            self._select_row_by_id(created_id)

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

    def _show_customer_distributor_code_dialog(self) -> None:
        row = self._selected_row()
        if not row:
            QMessageBox.warning(self, "Clientes", "Selecciona un cliente.")
            return

        distributor_code = str(getattr(row, "cliente_codigo_distribuidor", "") or "").strip()
        display_value = distributor_code or "No informado"

        dialog = QDialog(self)
        dialog.setWindowTitle("Codigo cliente distribuidor")
        dialog.setModal(True)
        layout = QVBoxLayout(dialog)

        label = QLabel("Codigo cliente distribuidor")
        code_field = QLineEdit(display_value)
        code_field.setReadOnly(True)
        code_field.setCursorPosition(0)
        code_field.setSelection(0, 0)

        buttons = QHBoxLayout()
        copy_btn = QPushButton("Copiar")
        close_btn = QPushButton("Cerrar")
        copy_btn.setProperty("btnRole", "secondary")
        close_btn.setProperty("btnRole", "secondary")
        copy_btn.setEnabled(bool(distributor_code))
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(distributor_code))
        close_btn.clicked.connect(dialog.accept)
        buttons.addWidget(copy_btn)
        buttons.addStretch(1)
        buttons.addWidget(close_btn)

        layout.addWidget(label)
        layout.addWidget(code_field)
        layout.addLayout(buttons)
        dialog.resize(460, 130)
        dialog.exec()

    def _find_customer_by_distributor_code(self, distributor_code: str, current_customer_id: str) -> object | None:
        normalized_code = str(distributor_code or "").strip().casefold()
        if not normalized_code:
            return None

        candidates = list(getattr(self, "_all_rows", []) or []) + list(getattr(self, "rows", []) or [])
        seen_ids: set[str] = set()
        for candidate in candidates:
            candidate_id = str(getattr(candidate, "cliente_id", "") or "").strip()
            if not candidate_id or candidate_id in seen_ids or candidate_id == current_customer_id:
                continue
            seen_ids.add(candidate_id)
            candidate_code = str(getattr(candidate, "cliente_codigo_distribuidor", "") or "").strip().casefold()
            if candidate_code == normalized_code:
                return candidate
        return None

    def _edit_customer_distributor_code_dialog(self) -> None:
        row = self._selected_row()
        if not row:
            QMessageBox.warning(self, "Clientes", "Selecciona un cliente.")
            return

        customer_id = str(getattr(row, "cliente_id", "") or "").strip()
        if not customer_id:
            QMessageBox.warning(self, "Clientes", "El cliente no tiene ID.")
            return

        current_code = str(getattr(row, "cliente_codigo_distribuidor", "") or "").strip()

        dialog = QDialog(self)
        dialog.setWindowTitle("Editar codigo cliente distribuidor")
        dialog.setModal(True)
        layout = QVBoxLayout(dialog)

        label = QLabel("Codigo cliente distribuidor")
        code_field = QLineEdit(current_code)
        code_field.setPlaceholderText("Codigo asignado por el distribuidor")
        code_field.setCursorPosition(0)
        code_field.selectAll()

        buttons = QHBoxLayout()
        save_btn = QPushButton("Guardar")
        cancel_btn = QPushButton("Cancelar")
        save_btn.setProperty("btnRole", "primary")
        cancel_btn.setProperty("btnRole", "secondary")
        buttons.addStretch(1)
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)

        layout.addWidget(label)
        layout.addWidget(code_field)
        layout.addLayout(buttons)
        dialog.resize(460, 130)

        def save() -> None:
            new_code = code_field.text().strip()
            duplicate = self._find_customer_by_distributor_code(new_code, customer_id)
            if duplicate is not None:
                duplicate_label = self._customer_merge_row_label(duplicate)
                QMessageBox.warning(
                    dialog,
                    "Clientes",
                    f"El codigo cliente distribuidor ya esta asignado a:\n{duplicate_label}",
                )
                return

            if new_code == current_code:
                dialog.accept()
                return

            try:
                self._update(customer_id, {"cliente_codigo_distribuidor": new_code})
            except Exception as exc:
                QMessageBox.warning(dialog, "Clientes", f"No se pudo guardar el codigo:\n{exc}")
                return

            dialog.accept()
            self.reload()
            self._select_row_by_id(customer_id)

        save_btn.clicked.connect(save)
        cancel_btn.clicked.connect(dialog.reject)
        code_field.returnPressed.connect(save)
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
