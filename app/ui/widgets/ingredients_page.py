from datetime import date
from typing import Any
from pathlib import Path
import re

from PySide6.QtCore import QDate, QTimer, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QDateEdit,
    QLabel,
    QLineEdit,
    QInputDialog,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSplitter,
    QStyle,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from app.models import AlmacenMovimiento, Distribuidor, Envase, Fabricante, Familia, IngredienteIreks, IngredienteStd, Pedido, PedidoItem, Proveedor, ReferenciaDistribuidor, Subfamilia, TarifaPrecioIreks
from app.services.ingredient_fatsecret_nutrition_flow_service import IngredientFatSecretNutritionFlowService
from app.services.ingredient_fdc_nutrition_flow_service import IngredientFdcNutritionFlowService
from app.services.ingredient_chatgpt_nutrition_flow_service import IngredientChatGPTNutritionFlowService
from app.services.ingredient_entity_service import IngredientEntityService
from app.services.ingredient_ireks_service import IngredientIreksService
from app.services.ingredient_products_import_flow_service import IngredientProductsImportFlowService
from app.services.ingredient_nutrition_query_service import IngredientNutritionQueryService
from app.services.ingredient_std_service import IngredientStdService
from app.services.fatsecret_client import FatSecretApiError
from app.services.openai_nutrition_service import OpenAINutritionService
from app.services.monthly_orders_service import MonthlyOrdersService
from app.services.product_report_flow_service import ProductReportFlowService
from app.services.product_report_service import ProductReportResult
from app.services.report_export_service import ReportExportService
from app.ui.widgets.entity_page import EntityPage
from app.ui.widgets.ingredient_distributors_tab import IngredientDistributorsTab
from app.viewmodels import IngredientIreksViewModel, IngredientStdViewModel


class TarifaDistribuidorChart(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._points: list[tuple[int, float]] = []
        self.setMinimumWidth(280)
        self.setMinimumHeight(220)

    def set_points(self, points: list[tuple[int, float]]) -> None:
        # Expected sorted by year ascending.
        self._points = list(points)
        self.update()

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))

        if not self._points:
            painter.setPen(QColor("#7A869A"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin datos de tarifa")
            return

        left = 42
        top = 16
        right = 16
        bottom = 34
        plot_w = max(60, self.width() - left - right)
        plot_h = max(60, self.height() - top - bottom)

        prices = [float(price) for _, price in self._points]
        years = [int(year) for year, _ in self._points]
        min_p = min(prices)
        max_p = max(prices)
        if abs(max_p - min_p) < 1e-9:
            min_p -= 1.0
            max_p += 1.0

        axis_pen = QPen(QColor("#CFD7E6"))
        axis_pen.setWidth(1)
        painter.setPen(axis_pen)
        painter.drawLine(left, top + plot_h, left + plot_w, top + plot_h)  # X
        painter.drawLine(left, top, left, top + plot_h)  # Y

        def x_of(i: int) -> float:
            if len(self._points) == 1:
                return left + (plot_w / 2.0)
            return left + (plot_w * i / (len(self._points) - 1))

        def y_of(price: float) -> float:
            ratio = (price - min_p) / (max_p - min_p)
            return top + plot_h - (ratio * plot_h)

        # Y labels
        painter.setPen(QColor("#6B778C"))
        font_small = QFont()
        font_small.setPointSize(8)
        painter.setFont(font_small)
        painter.drawText(4, int(top + 8), f"{max_p:.2f} €")
        painter.drawText(4, int(top + plot_h + 2), f"{min_p:.2f} €")

        # Vertical bars
        bar_fill = QColor("#1E6FEA")
        bar_fill_light = QColor("#77A9F5")
        bar_pen = QPen(QColor("#1A5FCA"))
        bar_pen.setWidth(1)
        painter.setPen(bar_pen)
        bar_width = max(10.0, min(26.0, (plot_w / max(len(self._points), 1)) * 0.45))
        baseline_y = top + plot_h
        for i, price in enumerate(prices):
            cx = x_of(i)
            y = y_of(price)
            rect_x = cx - (bar_width / 2.0)
            rect_h = max(1.0, baseline_y - y)
            painter.fillRect(int(rect_x), int(y), int(bar_width), int(rect_h), bar_fill)
            # subtle highlight strip
            painter.fillRect(int(rect_x), int(y), max(2, int(bar_width * 0.22)), int(rect_h), bar_fill_light)
            painter.drawRect(int(rect_x), int(y), int(bar_width), int(rect_h))

        # X labels
        painter.setPen(QColor("#6B778C"))
        for i, year in enumerate(years):
            label = str(year)
            x = x_of(i)
            painter.drawText(int(x - 16), int(top + plot_h + 18), 40, 14, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, label)


class AddTarifaIreksDialog(QDialog):
    def __init__(
        self,
        total_kg: float,
        parent: QWidget | None = None,
        *,
        initial: dict[str, Any] | None = None,
        title: str = "Añadir tarifa",
    ) -> None:
        super().__init__(parent)
        self._total_kg = float(total_kg or 0.0)
        self._loading = False
        self.setWindowTitle(title)
        self.setFixedSize(430, 260)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        initial_values = initial or {}
        self.year_input = QLineEdit(str((initial or {}).get("tarifa_ano") or date.today().year))
        self.year_input.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.ireks_env_input = QLineEdit(self._float_text(initial_values.get("precio_fabricante", 0.0)))
        self.ireks_env_input.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.ireks_kg_input = QLineEdit()
        self.ireks_kg_input.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.discount_input = QLineEdit(self._float_text(initial_values.get("descuento_pct", 0.0)))
        self.discount_input.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.distribuidor_env_input = QLineEdit(self._float_text(initial_values.get("precio_distribuidor", 0.0)))
        self.distribuidor_env_input.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.distribuidor_kg_input = QLineEdit()
        self.distribuidor_kg_input.setAlignment(Qt.AlignmentFlag.AlignRight)
        form.addRow("Año", self.year_input)
        form.addRow("IREKS precio envase", self.ireks_env_input)
        form.addRow("IREKS €/kg", self.ireks_kg_input)
        form.addRow("Descuento %", self.discount_input)
        form.addRow("DISTRIBUIDOR precio envase", self.distribuidor_env_input)
        form.addRow("DISTRIBUIDOR €/kg", self.distribuidor_kg_input)
        layout.addLayout(form)

        self.ireks_env_input.textEdited.connect(self._on_env_edited)
        self.ireks_kg_input.textEdited.connect(self._on_kg_edited)
        self.distribuidor_env_input.textEdited.connect(self._on_distribuidor_env_edited)
        self.distribuidor_kg_input.textEdited.connect(self._on_distribuidor_kg_edited)
        self._set_kg_from_env(self.ireks_env_input, self.ireks_kg_input)
        self._set_kg_from_env(self.distribuidor_env_input, self.distribuidor_kg_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _to_float(value: str) -> float:
        text_value = str(value or "").strip()
        if not text_value:
            return 0.0
        if "," in text_value:
            text_value = text_value.replace(".", "").replace(",", ".")
        try:
            return float(text_value)
        except Exception:
            return 0.0

    @staticmethod
    def _float_text(value: Any) -> str:
        try:
            val = float(value or 0.0)
        except Exception:
            val = 0.0
        if abs(val) < 1e-12:
            return ""
        return f"{val:.2f}".replace(".", ",")

    def _on_env_edited(self, value: str) -> None:
        if self._loading:
            return
        self._loading = True
        self._set_kg_from_env(self.ireks_env_input, self.ireks_kg_input)
        self._loading = False

    def _on_kg_edited(self, value: str) -> None:
        if self._loading:
            return
        self._loading = True
        self._set_env_from_kg(self.ireks_kg_input, self.ireks_env_input)
        self._loading = False

    def _on_distribuidor_env_edited(self, value: str) -> None:
        if self._loading:
            return
        self._loading = True
        self._set_kg_from_env(self.distribuidor_env_input, self.distribuidor_kg_input)
        self._loading = False

    def _on_distribuidor_kg_edited(self, value: str) -> None:
        if self._loading:
            return
        self._loading = True
        self._set_env_from_kg(self.distribuidor_kg_input, self.distribuidor_env_input)
        self._loading = False

    def _set_kg_from_env(self, env_input: QLineEdit, kg_input: QLineEdit) -> None:
        env_price = self._to_float(env_input.text())
        kg_price = env_price / self._total_kg if self._total_kg > 0 and env_price > 0 else 0.0
        kg_input.setText(self._float_text(kg_price))

    def _set_env_from_kg(self, kg_input: QLineEdit, env_input: QLineEdit) -> None:
        kg_price = self._to_float(kg_input.text())
        env_price = kg_price * self._total_kg if self._total_kg > 0 and kg_price > 0 else 0.0
        env_input.setText(self._float_text(env_price))

    def _accept_if_valid(self) -> None:
        try:
            year = int(float(str(self.year_input.text() or "").strip().replace(",", ".")))
        except Exception:
            year = 0
        if year < 1900 or year > 2100:
            QMessageBox.warning(self, "Tarifa", "Año no válido.")
            return
        if self._total_kg <= 0:
            QMessageBox.warning(self, "Tarifa", "El producto no tiene peso de envase válido.")
            return
        self.accept()

    def payload(self) -> tuple[int, float, float, float]:
        year = int(float(str(self.year_input.text() or "").strip().replace(",", ".")))
        return (
            year,
            self._to_float(self.ireks_env_input.text()),
            self._to_float(self.distribuidor_env_input.text()),
            self._to_float(self.discount_input.text()),
        )


def ingredient_schema(include_referencia: bool) -> list[dict[str, Any]]:
    if include_referencia:
        return [
            {"name": "almacen_id", "label": "Almacen_ID"},
            {"name": "fabricante_id", "label": "Fabricante_ID"},
            {"name": "distribuidor_id", "label": "Distribuidor_ID"},
            {"name": "articulo_id", "label": "Articulo_ID"},
            {"name": "articulo_referencia", "label": "Articulo_Referencia"},
            {"name": "articulo_referencia_corta", "label": "Articulo_Referencia_Corta"},
            {"name": "articulo_descripcion", "label": "Articulo_Descripcion"},
            {"name": "articulo_envase_id", "label": "Articulo_Envase_ID"},
            {"name": "articulo_contenido_unidad", "label": "Articulo_Contenido_Unidad"},
            {"name": "articulo_envase_cantidad", "label": "Articulo_Envase_Cantidad", "type": "float"},
            {"name": "articulo_envase_peso", "label": "Articulo_Envase_Peso", "type": "float"},
            {"name": "articulo_envase_unidad_medida", "label": "Articulo_Envase_Unidad_Medida"},
            {"name": "articulo_envase_peso_total", "label": "Articulo_Envase_Peso_Total", "type": "float"},
            {"name": "transporte_pallet_tipo", "label": "Transporte_Pallet_Tipo"},
            {"name": "transporte_cajas_por_capa", "label": "Transporte_Cajas_Por_Capa", "type": "float"},
            {"name": "transporte_capas_por_pallet", "label": "Transporte_Capas_Por_Pallet", "type": "float"},
            {"name": "transporte_observaciones", "label": "Transporte_Observaciones"},
            {"name": "articulo_familia_id", "label": "Articulo_Familia_ID"},
            {"name": "articulo_grupo_id", "label": "Articulo_Grupo_ID"},
            {"name": "articulo_subfamilia_id", "label": "Articulo_Subfamilia_ID"},
            {"name": "articulo_status_activo", "label": "Articulo_Status_Activo", "type": "bool", "default": True},
            {"name": "articulo_status_en_lista", "label": "Articulo_Status_En_Lista", "type": "bool", "default": False},
        ]
    return [
        {"name": "articulo_id", "label": "Articulo_ID"},
        {"name": "articulo_referencia_distribuidor", "label": "Articulo_Referencia_Distribuidor"},
        {"name": "proveedor_id", "label": "Proveedor_ID"},
        {"name": "articulo_descripcion", "label": "Articulo_Descripcion"},
        {"name": "articulo_grupo_id", "label": "Articulo_Grupo_ID"},
        {"name": "articulo_familia_id", "label": "Articulo_Familia_ID"},
        {"name": "articulo_subfamilia_id", "label": "Articulo_Subfamilia_ID"},
        {"name": "categoria", "label": "Categoria"},
        {"name": "formato", "label": "Formato"},
        {"name": "formato_cantidad", "label": "Cantidad formato", "type": "float"},
        {"name": "formato_unidad", "label": "Unidad formato"},
        {"name": "pvp_formato", "label": "PVP formato", "type": "float"},
        {"name": "pvp_unidad_medida", "label": "PVP unidad medida", "type": "float"},
        {"name": "activo", "label": "Activo", "type": "bool", "default": True},
    ]


class _BaseIngredientsPage(EntityPage):
    def __init__(
        self,
        title: str,
        schema: list[dict],
        vm,
        include_referencia: bool,
        columns: list[tuple[str, str]],
        include_filters: bool,
        id_attr: str,
        required_fields: list[str],
    ) -> None:
        self.vm = vm
        self.include_referencia = include_referencia
        self.required_fields = required_fields
        self.ingredient_service = IngredientEntityService(
            vm,
            include_referencia=include_referencia,
            schema=schema,
            required_fields=required_fields,
        )
        super().__init__(
            title=title,
            columns=columns,
            schema=schema,
            list_fn=self._list,
            create_fn=self._create,
            update_fn=self._update,
            delete_fn=self._delete,
            include_filters=include_filters,
            import_fn=self._import,
            id_attr=id_attr,
        )

    def _list(self, term: str, familia: str = "", subfamilia: str = "") -> list:
        active_filter = getattr(self, "_active_filter_value", lambda: "all")()
        return self.ingredient_service.list(term, familia, subfamilia, active_filter=active_filter)

    def _create(self, payload: dict) -> None:
        self.ingredient_service.create(payload)

    def _update(self, entity_id, payload: dict) -> None:
        self.ingredient_service.update(entity_id, payload)

    def _delete(self, entity_id) -> bool:
        return self.ingredient_service.delete(entity_id)

    def _import(self, file_path: str) -> tuple[int, list[str]]:
        if self.include_referencia:
            aliases = {
                "almacen_id": ["almacen", "almacen_id"],
                "fabricante_id": ["fabricante", "fabricante_id", "marca_id"],
                "distribuidor_id": ["distribuidor", "distribuidor_id"],
                "articulo_id": ["articulo", "articulo_id", "id_articulo"],
                "articulo_referencia": ["referencia", "ref", "codigo"],
                "articulo_referencia_corta": ["referencia_corta", "ref_corta", "codigo_corto"],
                "articulo_descripcion": ["descripcion", "nombre", "articulo_descripcion"],
                "articulo_envase_id": ["envase", "envase_id", "articulo_envase_id"],
                "articulo_contenido_unidad": ["unidad_contenido", "contenido_unidad", "unidad_interior", "tipo_contenido"],
                "articulo_envase_cantidad": ["envase_cantidad", "cantidad_envase"],
                "articulo_envase_peso": ["envase_peso", "peso_envase"],
                "articulo_envase_unidad_medida": ["unidad_medida", "unidad", "um"],
                "articulo_envase_peso_total": ["peso_total", "envase_peso_total"],
                "transporte_pallet_tipo": ["pallet", "tipo_pallet", "transporte_pallet"],
                "transporte_cajas_por_capa": ["cajas_capa", "cajas_por_capa"],
                "transporte_capas_por_pallet": ["capas_pallet", "capas_por_pallet"],
                "transporte_observaciones": ["transporte_observaciones", "observaciones_transporte"],
                "articulo_familia_id": ["familia", "familia_id"],
                "articulo_grupo_id": ["grupo", "grupo_id"],
                "articulo_subfamilia_id": ["subfamilia", "subfamilia_id"],
                "articulo_status_activo": ["status_activo", "activo_status", "activo_producto", "estado", "habilitado"],
                "articulo_status_en_lista": ["status_en_lista", "en_lista", "lista"],
            }
        else:
            aliases = {
                "articulo_id": ["id", "articuloid"],
                "articulo_referencia_distribuidor": ["referencia", "ref", "codigo", "cod"],
                "proveedor_id": ["proveedor", "proveedor_id", "supplier_id", "distribuidor", "distribuidor_id"],
                "articulo_descripcion": ["descripcion", "nombre", "articulo", "producto"],
                "articulo_grupo_id": ["grupo", "grupo_id"],
                "articulo_familia_id": ["familia", "familia_id"],
                "articulo_subfamilia_id": ["subfamilia", "subfamilia_id"],
                "categoria": ["categoria", "tipo"],
                "formato": ["formato", "envase"],
                "formato_cantidad": ["cantidad", "cantidad_formato", "peso_formato"],
                "formato_unidad": ["unidad", "unidad_formato"],
                "pvp_formato": ["pvp_formato", "precio_formato"],
                "pvp_unidad_medida": ["pvp_unidad", "pvp_unidad_medida", "precio_unidad"],
                "activo": ["estado", "habilitado"],
            }

        return self.ingredient_service.import_file(file_path, aliases)

class IngredientsIreksPage(QWidget):
    def __init__(
        self,
        *,
        show_header: bool = True,
        show_actions_ribbon: bool = True,
        compact_mode: bool = False,
        vm: Any | None = None,
    ) -> None:
        QWidget.__init__(self)
        self.show_header = show_header
        self.show_actions_ribbon = show_actions_ribbon
        self.compact_mode = compact_mode
        self.vm = vm or IngredientIreksViewModel()
        self.ireks_service = IngredientIreksService(self.vm)
        self.monthly_orders_service = MonthlyOrdersService()
        self.product_report_flow_service = ProductReportFlowService()
        self.report_export_service = ReportExportService()
        self.nutrition_query_service = IngredientNutritionQueryService()
        self.fdc_nutrition_flow_service = IngredientFdcNutritionFlowService(
            nutrition_query_service=self.nutrition_query_service,
        )
        self.fatsecret_nutrition_flow_service = IngredientFatSecretNutritionFlowService(
            nutrition_query_service=self.nutrition_query_service,
        )
        self.chatgpt_nutrition_flow_service = IngredientChatGPTNutritionFlowService(
            openai_service=OpenAINutritionService(),
        )
        self.external_distributor_filter_id = ""
        self.ingredient_products_import_flow_service = IngredientProductsImportFlowService(self.ireks_service)
        self.rows: list[IngredienteIreks] = []
        self._distribuidores: list[Distribuidor] = []
        self._fabricantes: list[Fabricante] = []
        self._familias: list[Familia] = []
        self._subfamilias: list[Subfamilia] = []
        self._envases: list[Envase] = []
        self._loading = False
        self._loading_nutricion = False
        self._current_entradas_articulo_id = ""
        self._current_tarifa_articulo_id = ""
        self._left_sort_col = 0
        self._left_sort_order = Qt.SortOrder.AscendingOrder
        self._selected_product_ids: set[int] = set()
        self._last_product_report: ProductReportResult | None = None
        self._product_reports_dialog: QDialog | None = None
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self.reload)
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.timeout.connect(self._autosave_selected)
        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        if self.show_header:
            header = QLabel("Productos IREKS")
            header.setProperty("role", "pageTitle")
            layout.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, 1)

        left_panel = QWidget()
        left_panel.setObjectName("sidePanel")
        left_width = 420
        left_panel.setFixedWidth(left_width)
        left_layout = QVBoxLayout(left_panel)

        fabricante_row = QHBoxLayout()
        fabricante_row.setSpacing(5)
        self.fabricante_filter = QComboBox()
        self.fabricante_filter.addItem("Fabricante (todos)", "")
        self.fabricante_filter.currentIndexChanged.connect(self._on_fabricante_filter_changed)
        self.fabricante_filter.setFixedWidth(280)
        fabricante_row.addWidget(self.fabricante_filter)
        self.activity_filter = QComboBox()
        self.activity_filter.addItem("Todos", "all")
        self.activity_filter.addItem("Activos", "active")
        self.activity_filter.addItem("Inactivos", "inactive")
        self.activity_filter.setFixedWidth(120)
        self.activity_filter.currentIndexChanged.connect(self.reload)
        fabricante_row.addWidget(self.activity_filter)
        left_layout.addLayout(fabricante_row)

        filters_row = QHBoxLayout()
        filters_row.setSpacing(5)
        self.familia_filter = QComboBox()
        self.familia_filter.addItem("Familia (todas)", "")
        self.familia_filter.currentIndexChanged.connect(self._on_familia_filter_changed)
        taxonomy_width = 200
        self.familia_filter.setFixedWidth(taxonomy_width)
        self.subfamilia_filter = QComboBox()
        self.subfamilia_filter.addItem("Subfamilia (todas)", "")
        self.subfamilia_filter.currentIndexChanged.connect(self.reload)
        self.subfamilia_filter.setFixedWidth(taxonomy_width)
        filters_row.addWidget(self.familia_filter, 1)
        filters_row.addWidget(self.subfamilia_filter, 1)
        filters_row.addStretch(2)
        left_layout.addLayout(filters_row)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar productos...")
        self.search_input.textChanged.connect(lambda *_: self._search_timer.start(200))
        self.search_input.setFixedWidth(left_width - 15)
        left_layout.addWidget(self.search_input)

        self.table = QTableWidget(0, 3)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setStyleSheet("QTableWidget::item:focus { border: none; outline: 0; }")
        table_header = self.table.horizontalHeader()
        table_header.setSectionsClickable(True)
        table_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        table_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 90)
        self.table.setColumnWidth(2, 55)
        self.table.setHorizontalHeaderLabels(["Ref", "Nombre", "Sel."])
        self.table.setSortingEnabled(False)
        table_header.setSortIndicatorShown(True)
        table_header.setSortIndicator(self._left_sort_col, self._left_sort_order)
        table_header.sectionClicked.connect(self._on_left_header_clicked)
        self.table.itemSelectionChanged.connect(self._show_selected_details)
        left_layout.addWidget(self.table, 1)
        splitter.addWidget(left_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        if self.show_actions_ribbon:
            ribbon = QFrame()
            ribbon.setObjectName("topRibbon")
            ribbon.setFrameShape(QFrame.Shape.StyledPanel)
            ribbon_layout = QHBoxLayout(ribbon)
            ribbon_layout.setContentsMargins(8, 6, 8, 6)
            ribbon_layout.setSpacing(6)
            for text, role, handler in [
                ("Nuevo", "success", self._new_product),
                ("Eliminar", "danger", self._delete_product),
                ("ID", "secondary", self._show_product_id_dialog),
                ("Importar Excel/CSV", "secondary", self._import_products),
                ("Listados", "primary", self._open_product_reports_dialog),
                ("Refrescar", "secondary", self.reload),
            ]:
                btn = QPushButton(text)
                btn.setProperty("btnRole", role)
                btn.clicked.connect(handler)
                ribbon_layout.addWidget(btn)
            ribbon_layout.addStretch(1)
            right_layout.addWidget(ribbon)

        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_layout.addWidget(right_splitter, 1)

        detail_panel = QWidget()
        detail_panel.setObjectName("detailPanel")
        if self.compact_mode:
            detail_panel.setFixedHeight(82)
        else:
            detail_panel.setFixedHeight(168)

        # Malla fija (coordenadas absolutas) para el bloque de detalle.
        detail_title = QLabel("Detalle del producto", detail_panel)
        detail_title.setProperty("role", "sectionTitle")
        detail_title.setGeometry(14, 8, 260, 24)

        QLabel("Ref.", detail_panel).setGeometry(14, 50, 30, 24)
        self.detail_referencia = QLineEdit()
        self.detail_referencia.setParent(detail_panel)
        self.detail_referencia.setGeometry(45, 46, 92 if self.compact_mode else 100, 24)
        QLabel("Ref. corta", detail_panel).setGeometry(150, 50, 82, 24)
        self.detail_ref_corta = QLineEdit()
        self.detail_ref_corta.setParent(detail_panel)
        self.detail_ref_corta.setGeometry(210, 46, 95 if self.compact_mode else 100, 24)
        QLabel("Descripcion", detail_panel).setGeometry(333 if self.compact_mode else 350, 50, 82, 24)
        self.detail_descripcion = QLineEdit()
        self.detail_descripcion.setParent(detail_panel)
        self.detail_descripcion.setGeometry(415 if self.compact_mode else 432, 46, 385, 24)

        self.detail_data_top_separator = QFrame(detail_panel)
        self.detail_data_top_separator.setFrameShape(QFrame.Shape.HLine)
        self.detail_data_top_separator.setFrameShadow(QFrame.Shadow.Sunken)
        self.detail_data_top_separator.setGeometry(14, 82, 810 if self.compact_mode else 850, 2)

        self.lbl_detail_envase = QLabel("Envase", detail_panel)
        self.lbl_detail_envase.setGeometry(14, 92, 45, 24)
        self.detail_envase_id = QComboBox(detail_panel)
        self.detail_envase_id.setGeometry(60, 88, 155 if self.compact_mode else 170, 24)

        self.lbl_detail_envase_cantidad = QLabel("Cantidad", detail_panel)
        self.lbl_detail_envase_cantidad.setGeometry(240, 92, 56, 24)
        self.detail_envase_cantidad = QLineEdit(detail_panel)
        self.detail_envase_cantidad.setGeometry(296, 88, 66 if self.compact_mode else 70, 24)
        self.detail_envase_cantidad.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.lbl_detail_envase_peso = QLabel("Peso", detail_panel)
        self.lbl_detail_envase_peso.setGeometry(376, 92, 34, 24)
        self.detail_envase_peso = QLineEdit(detail_panel)
        self.detail_envase_peso.setGeometry(410, 88, 66 if self.compact_mode else 70, 24)
        self.detail_envase_peso.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.lbl_detail_envase_unidad = QLabel("Unidad", detail_panel)
        self.lbl_detail_envase_unidad.setGeometry(490, 92, 44, 24)
        self.detail_envase_unidad = QComboBox(detail_panel)
        self.detail_envase_unidad.setGeometry(534, 88, 80 if self.compact_mode else 90, 24)
        self.detail_envase_unidad.addItems(["", "kg", "g", "L", "Unidades"])

        self.lbl_detail_envase_total = QLabel("Total", detail_panel)
        self.lbl_detail_envase_total.setGeometry(634, 92, 34, 24)
        self.detail_envase_total = QLineEdit(detail_panel)
        self.detail_envase_total.setGeometry(668, 88, 100 if self.compact_mode else 120, 24)
        self.detail_envase_total.setReadOnly(True)
        self.detail_envase_total.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.lbl_detail_fabricante = QLabel("Fabricante", detail_panel)
        self.lbl_detail_fabricante.setGeometry(14, 138, 70, 24)
        self.detail_fabricante_id = QComboBox(detail_panel)
        self.detail_fabricante_id.setGeometry(86, 134, 110 if self.compact_mode else 150, 24)
        self.detail_fabricante_id.addItem("", "")

        self.lbl_detail_familia = QLabel("Familia", detail_panel)
        self.lbl_detail_familia.setGeometry(210, 138, 46, 24)
        self.detail_familia_id = QComboBox(detail_panel)
        self.detail_familia_id.setGeometry(263, 134, 210 if self.compact_mode else 210, 24)
        self.detail_familia_id.addItem("", "")

        self.lbl_detail_subfamilia = QLabel("Subfamilia", detail_panel)
        self.lbl_detail_subfamilia.setGeometry(480, 138, 62, 24)
        self.detail_subfamilia_id = QComboBox(detail_panel)
        self.detail_subfamilia_id.setGeometry(555, 134, 260 if self.compact_mode else 210, 24)
        self.detail_subfamilia_id.addItem("", "")

        self.detail_data_row_separator = QFrame(detail_panel)
        self.detail_data_row_separator.setFrameShape(QFrame.Shape.HLine)
        self.detail_data_row_separator.setFrameShadow(QFrame.Shadow.Sunken)
        self.detail_data_row_separator.setGeometry(14, 128, 810 if self.compact_mode else 850, 2)

        QLabel("Distribuidor", detail_panel).setGeometry(14, 94, 70, 24)
        self.detail_distribuidor_id = QComboBox(detail_panel)
        self.detail_distribuidor_id.setGeometry(86, 90, 180 if self.compact_mode else 210, 24)
        self.detail_distribuidor_id.addItem("", "")

        QLabel("Referencia", detail_panel).setGeometry(280 if self.compact_mode else 305, 94, 64, 24)
        self.detail_referencia_distribuidor = QLineEdit(detail_panel)
        self.detail_referencia_distribuidor.setGeometry(
            345 if self.compact_mode else 375,
            90,
            60 if self.compact_mode else 95,
            24,
        )

        QLabel("Descripcion", detail_panel).setGeometry(480 if self.compact_mode else 485, 94, 68, 24)
        self.detail_descripcion_distribuidor = QLineEdit(detail_panel)
        self.detail_descripcion_distribuidor.setGeometry(
            550 if self.compact_mode else 555,
            90,
            260 if self.compact_mode else 270,
            24,
        )

        row_separator_3 = QFrame(detail_panel)
        row_separator_3.setFrameShape(QFrame.Shape.HLine)
        row_separator_3.setFrameShadow(QFrame.Shadow.Sunken)
        row_separator_3.setGeometry(14, 82, 810 if self.compact_mode else 850, 2)

        row_separator_4 = QFrame(detail_panel)
        row_separator_4.setFrameShape(QFrame.Shape.HLine)
        row_separator_4.setFrameShadow(QFrame.Shadow.Sunken)
        row_separator_4.setGeometry(14, 124, 810 if self.compact_mode else 850, 2)

        QLabel("Status activo", detail_panel).setGeometry(14, 132, 88, 24)
        self.detail_status_activo_si = QRadioButton("Si", detail_panel)
        self.detail_status_activo_si.setGeometry(106, 132, 50, 24)
        self.detail_status_activo_no = QRadioButton("No", detail_panel)
        self.detail_status_activo_no.setGeometry(160, 132, 50, 24)
        self.detail_status_activo_group = QButtonGroup(detail_panel)
        self.detail_status_activo_group.setExclusive(True)
        self.detail_status_activo_group.addButton(self.detail_status_activo_si)
        self.detail_status_activo_group.addButton(self.detail_status_activo_no)
        self.detail_status_activo_si.setChecked(True)

        QLabel("Status en lista", detail_panel).setGeometry(220, 132, 92, 24)
        self.detail_status_en_lista_si = QRadioButton("Si", detail_panel)
        self.detail_status_en_lista_si.setGeometry(316, 132, 50, 24)
        self.detail_status_en_lista_no = QRadioButton("No", detail_panel)
        self.detail_status_en_lista_no.setGeometry(370, 132, 50, 24)
        self.detail_status_en_lista_group = QButtonGroup(detail_panel)
        self.detail_status_en_lista_group.setExclusive(True)
        self.detail_status_en_lista_group.addButton(self.detail_status_en_lista_si)
        self.detail_status_en_lista_group.addButton(self.detail_status_en_lista_no)
        self.detail_status_en_lista_no.setChecked(True)

        QLabel("Categoria", detail_panel).setGeometry(440, 132, 70, 24)
        self.detail_categoria_harina = QRadioButton("Harina", detail_panel)
        self.detail_categoria_harina.setGeometry(512, 132, 70, 24)
        self.detail_categoria_liquido = QRadioButton("Líquido", detail_panel)
        self.detail_categoria_liquido.setGeometry(590, 132, 80, 24)
        self.detail_categoria_group = QButtonGroup(detail_panel)
        self.detail_categoria_group.setExclusive(True)
        self.detail_categoria_group.addButton(self.detail_categoria_harina)
        self.detail_categoria_group.addButton(self.detail_categoria_liquido)
        self._set_ireks_category("")

        for field in (
            self.detail_ref_corta,
            self.detail_descripcion,
            self.detail_referencia,
            self.detail_referencia_distribuidor,
            self.detail_descripcion_distribuidor,
            self.detail_envase_cantidad,
            self.detail_envase_peso,
        ):
            field.textEdited.connect(lambda *_: self._schedule_autosave())
        self.detail_envase_id.currentIndexChanged.connect(self._schedule_autosave)
        self.detail_envase_unidad.currentIndexChanged.connect(self._schedule_autosave)
        self.detail_envase_unidad.currentIndexChanged.connect(lambda *_: self._update_envase_total_preview())
        self.detail_envase_id.currentIndexChanged.connect(lambda *_: self._update_transport_label_texts())
        self.detail_envase_cantidad.textEdited.connect(lambda *_: self._update_envase_total_preview())
        self.detail_envase_peso.textEdited.connect(lambda *_: self._update_envase_total_preview())
        self.detail_fabricante_id.currentIndexChanged.connect(self._on_detail_fabricante_changed)
        self.detail_familia_id.currentIndexChanged.connect(self._on_detail_familia_changed)
        self.detail_subfamilia_id.currentIndexChanged.connect(self._on_detail_subfamilia_changed)
        self.detail_distribuidor_id.currentIndexChanged.connect(self._on_detail_distribuidor_changed)
        self.detail_status_activo_si.toggled.connect(self._on_status_toggled)
        self.detail_status_activo_no.toggled.connect(self._on_status_toggled)
        self.detail_status_en_lista_si.toggled.connect(self._on_status_toggled)
        self.detail_status_en_lista_no.toggled.connect(self._on_status_toggled)
        self.detail_categoria_harina.toggled.connect(self._on_status_toggled)
        self.detail_categoria_liquido.toggled.connect(self._on_status_toggled)

        right_splitter.addWidget(detail_panel)

        tabs_host = QWidget()
        tabs_layout = QVBoxLayout(tabs_host)
        tabs_layout.setContentsMargins(0, 4, 0, 0)
        tabs = QTabWidget()
        self.detail_tabs = tabs
        tabs.setDocumentMode(False)
        tabs.tabBar().setDrawBase(False)
        tabs.setStyleSheet(
            "QTabWidget { background: #FFFFFF; }"
            "QTabWidget::pane { border: 0; margin-top: 1px; background: #FFFFFF; }"
            "QTabBar { background: #FFFFFF; }"
            "QTabBar::tab { margin-bottom: 0px; }"
        )

        datos_tab = self._build_ireks_data_tab()
        tabs.addTab(datos_tab, "Datos")

        entradas_tab = QWidget()
        entradas_tab.setObjectName("entradasTab")
        entradas_tab.setStyleSheet(
            """
            QWidget#entradasTab {
                background: #F5F7FB;
            }
            QFrame#entradasCard {
                background: #FFFFFF;
                border: 1px solid #E5EAF1;
                border-radius: 10px;
            }
            QWidget#entradasTab QLabel {
                color: #5E6C84;
                font-weight: 500;
            }
            QDateEdit#entradasDateFrom, QDateEdit#entradasDateTo {
                min-height: 30px;
                padding: 2px 8px;
                border: 1px solid #D5DDEA;
                border-radius: 6px;
                background: #FFFFFF;
            }
            QPushButton#entradasResetBtn {
                min-height: 30px;
                padding: 0 10px;
                border: 1px solid #D5DDEA;
                border-radius: 6px;
                background: #F7F9FC;
                color: #1B2A42;
            }
            QPushButton#entradasResetBtn:hover {
                background: #EDF2FA;
            }
            QTableWidget#entradasTable {
                border: 1px solid #E5EAF1;
                border-radius: 8px;
                gridline-color: #ECF0F6;
                alternate-background-color: #FBFCFE;
                background: #FFFFFF;
                selection-background-color: #E6F0FF;
                selection-color: #0F2D5C;
            }
            QTableWidget#entradasTable::item {
                padding: 4px 6px;
            }
            QTableWidget#entradasTable::item:hover {
                background: #F1F6FF;
            }
            QHeaderView::section {
                background: #F7F9FC;
                color: #1B2A42;
                font-weight: 600;
                border: 1px solid #E5EAF1;
                padding: 6px 8px;
            }
            QTableWidget#entradasTotalsTable {
                border: 1px solid #E5EAF1;
                border-top: 0;
                border-radius: 0 0 8px 8px;
                background: #F7F9FC;
                gridline-color: #E5EAF1;
            }
            """
        )
        entradas_layout = QVBoxLayout(entradas_tab)
        entradas_layout.setContentsMargins(8, 8, 8, 8)
        entradas_layout.setSpacing(6)
        entradas_card = QFrame()
        entradas_card.setObjectName("entradasCard")
        entradas_card_layout = QVBoxLayout(entradas_card)
        entradas_card_layout.setContentsMargins(10, 10, 10, 10)
        entradas_card_layout.setSpacing(8)
        entradas_filters_row = QHBoxLayout()
        entradas_filters_row.setObjectName("entradasToolbar")
        entradas_filters_row.addWidget(QLabel("Desde"))
        self.entradas_date_from = QDateEdit()
        self.entradas_date_from.setObjectName("entradasDateFrom")
        self.entradas_date_from.setCalendarPopup(True)
        self.entradas_date_from.setDisplayFormat("dd/MM/yyyy")
        self.entradas_date_from.setDate(QDate(2000, 1, 1))
        self.entradas_date_from.dateChanged.connect(lambda _d: self._reload_entradas_table(self._current_entradas_articulo_id))
        entradas_filters_row.addWidget(self.entradas_date_from)
        entradas_filters_row.addWidget(QLabel("Hasta"))
        self.entradas_date_to = QDateEdit()
        self.entradas_date_to.setObjectName("entradasDateTo")
        self.entradas_date_to.setCalendarPopup(True)
        self.entradas_date_to.setDisplayFormat("dd/MM/yyyy")
        self.entradas_date_to.setDate(QDate(2100, 12, 31))
        self.entradas_date_to.dateChanged.connect(lambda _d: self._reload_entradas_table(self._current_entradas_articulo_id))
        entradas_filters_row.addWidget(self.entradas_date_to)
        clear_dates_btn = QPushButton("Todo")
        clear_dates_btn.setObjectName("entradasResetBtn")
        clear_dates_btn.setProperty("btnRole", "secondary")
        clear_dates_btn.clicked.connect(self._reset_entradas_date_filters)
        entradas_filters_row.addWidget(clear_dates_btn)
        entradas_filters_row.addStretch(1)
        entradas_card_layout.addLayout(entradas_filters_row)
        self.entradas_table = QTableWidget(0, 7)
        self.entradas_table.setObjectName("entradasTable")
        self.entradas_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.entradas_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.entradas_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.entradas_table.verticalHeader().setVisible(False)
        self.entradas_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.entradas_table.setAlternatingRowColors(True)
        self.entradas_table.setStyleSheet("QTableWidget::item:focus { border: none; outline: 0; }")
        entradas_header = self.entradas_table.horizontalHeader()
        entradas_header.setSectionsClickable(True)
        entradas_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        entradas_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        entradas_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        entradas_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        entradas_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        entradas_header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        entradas_header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.entradas_table.setHorizontalHeaderLabels(["Fecha", "Pedido Nº", "Albarán", "Uds", "Kg", "Lote", "Caduca"])
        self.entradas_table.setColumnWidth(0, 110)
        self.entradas_table.setColumnWidth(1, 130)
        self.entradas_table.setColumnWidth(2, 150)
        self.entradas_table.setColumnWidth(3, 85)
        self.entradas_table.setColumnWidth(4, 105)
        self.entradas_table.setColumnWidth(6, 110)
        entradas_card_layout.addWidget(self.entradas_table, 1)
        self.entradas_totals_table = QTableWidget(1, 7)
        self.entradas_totals_table.setObjectName("entradasTotalsTable")
        self.entradas_totals_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.entradas_totals_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.entradas_totals_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.entradas_totals_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.entradas_totals_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.entradas_totals_table.verticalHeader().setVisible(False)
        self.entradas_totals_table.horizontalHeader().setVisible(False)
        entradas_totals_header = self.entradas_totals_table.horizontalHeader()
        entradas_totals_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        entradas_totals_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        entradas_totals_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        entradas_totals_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        entradas_totals_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        entradas_totals_header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        entradas_totals_header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.entradas_totals_table.setFixedHeight(30)
        self.entradas_totals_table.setColumnWidth(0, 110)
        self.entradas_totals_table.setColumnWidth(1, 130)
        self.entradas_totals_table.setColumnWidth(2, 150)
        self.entradas_totals_table.setColumnWidth(3, 85)
        self.entradas_totals_table.setColumnWidth(4, 105)
        self.entradas_totals_table.setColumnWidth(6, 110)
        entradas_card_layout.addWidget(self.entradas_totals_table)
        entradas_layout.addWidget(entradas_card, 1)
        self._entradas_tab_index = tabs.addTab(entradas_tab, "Entradas")

        salidas_tab = QWidget()
        salidas_layout = QVBoxLayout(salidas_tab)
        salidas_layout.setContentsMargins(8, 8, 8, 8)
        salidas_layout.setSpacing(6)
        salidas_filters_row = QHBoxLayout()
        salidas_filters_row.addWidget(QLabel("Desde"))
        self.salidas_date_from = QDateEdit()
        self.salidas_date_from.setCalendarPopup(True)
        self.salidas_date_from.setDisplayFormat("dd/MM/yyyy")
        self.salidas_date_from.setDate(QDate(2000, 1, 1))
        self.salidas_date_from.dateChanged.connect(lambda _d: self._reload_salidas_table(self._current_entradas_articulo_id))
        salidas_filters_row.addWidget(self.salidas_date_from)
        salidas_filters_row.addWidget(QLabel("Hasta"))
        self.salidas_date_to = QDateEdit()
        self.salidas_date_to.setCalendarPopup(True)
        self.salidas_date_to.setDisplayFormat("dd/MM/yyyy")
        self.salidas_date_to.setDate(QDate(2100, 12, 31))
        self.salidas_date_to.dateChanged.connect(lambda _d: self._reload_salidas_table(self._current_entradas_articulo_id))
        salidas_filters_row.addWidget(self.salidas_date_to)
        salidas_clear_dates_btn = QPushButton("Todo")
        salidas_clear_dates_btn.setProperty("btnRole", "secondary")
        salidas_clear_dates_btn.clicked.connect(self._reset_salidas_date_filters)
        salidas_filters_row.addWidget(salidas_clear_dates_btn)
        salidas_filters_row.addStretch(1)
        salidas_layout.addLayout(salidas_filters_row)
        self.salidas_table = QTableWidget(0, 7)
        self.salidas_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.salidas_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.salidas_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.salidas_table.verticalHeader().setVisible(False)
        self.salidas_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.salidas_table.setAlternatingRowColors(True)
        self.salidas_table.setStyleSheet("QTableWidget::item:focus { border: none; outline: 0; }")
        salidas_header = self.salidas_table.horizontalHeader()
        salidas_header.setSectionsClickable(True)
        salidas_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        salidas_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        salidas_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        salidas_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        salidas_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        salidas_header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        salidas_header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.salidas_table.setHorizontalHeaderLabels(["Fecha", "Pedido Nº", "Albarán", "Uds", "Kg", "Lote", "Caduca"])
        self.salidas_table.setColumnWidth(0, 110)
        self.salidas_table.setColumnWidth(1, 130)
        self.salidas_table.setColumnWidth(2, 150)
        self.salidas_table.setColumnWidth(3, 85)
        self.salidas_table.setColumnWidth(4, 105)
        self.salidas_table.setColumnWidth(6, 110)
        salidas_layout.addWidget(self.salidas_table, 1)
        self.salidas_totals_table = QTableWidget(1, 7)
        self.salidas_totals_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.salidas_totals_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.salidas_totals_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.salidas_totals_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.salidas_totals_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.salidas_totals_table.verticalHeader().setVisible(False)
        self.salidas_totals_table.horizontalHeader().setVisible(False)
        salidas_totals_header = self.salidas_totals_table.horizontalHeader()
        salidas_totals_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        salidas_totals_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        salidas_totals_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        salidas_totals_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        salidas_totals_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        salidas_totals_header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        salidas_totals_header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.salidas_totals_table.setFixedHeight(30)
        self.salidas_totals_table.setColumnWidth(0, 110)
        self.salidas_totals_table.setColumnWidth(1, 130)
        self.salidas_totals_table.setColumnWidth(2, 150)
        self.salidas_totals_table.setColumnWidth(3, 85)
        self.salidas_totals_table.setColumnWidth(4, 105)
        self.salidas_totals_table.setColumnWidth(6, 110)
        salidas_layout.addWidget(self.salidas_totals_table)
        self._salidas_tab_index = tabs.addTab(salidas_tab, "Salidas")

        stock_tab = QWidget()
        stock_layout = QVBoxLayout(stock_tab)
        stock_layout.setContentsMargins(8, 8, 8, 8)
        stock_layout.setSpacing(6)
        stock_filters_row = QHBoxLayout()
        stock_filters_row.addWidget(QLabel("Desde"))
        self.stock_date_from = QDateEdit()
        self.stock_date_from.setCalendarPopup(True)
        self.stock_date_from.setDisplayFormat("dd/MM/yyyy")
        self.stock_date_from.setDate(QDate(2000, 1, 1))
        self.stock_date_from.dateChanged.connect(lambda _d: self._reload_stock_table(self._current_entradas_articulo_id))
        stock_filters_row.addWidget(self.stock_date_from)
        stock_filters_row.addWidget(QLabel("Hasta"))
        self.stock_date_to = QDateEdit()
        self.stock_date_to.setCalendarPopup(True)
        self.stock_date_to.setDisplayFormat("dd/MM/yyyy")
        self.stock_date_to.setDate(QDate(2100, 12, 31))
        self.stock_date_to.dateChanged.connect(lambda _d: self._reload_stock_table(self._current_entradas_articulo_id))
        stock_filters_row.addWidget(self.stock_date_to)
        stock_clear_dates_btn = QPushButton("Todo")
        stock_clear_dates_btn.setProperty("btnRole", "secondary")
        stock_clear_dates_btn.clicked.connect(self._reset_stock_date_filters)
        stock_filters_row.addWidget(stock_clear_dates_btn)
        stock_filters_row.addStretch(1)
        stock_layout.addLayout(stock_filters_row)
        self.stock_table = QTableWidget(0, 8)
        self.stock_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.stock_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.stock_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.stock_table.verticalHeader().setVisible(False)
        self.stock_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.stock_table.setAlternatingRowColors(True)
        self.stock_table.setStyleSheet("QTableWidget::item:focus { border: none; outline: 0; }")
        stock_header = self.stock_table.horizontalHeader()
        stock_header.setSectionsClickable(True)
        stock_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        stock_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        stock_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        stock_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        stock_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        stock_header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        stock_header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        stock_header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        self.stock_table.setHorizontalHeaderLabels(["Fecha", "Tipo", "Pedido Nº", "Albarán", "Uds", "Kg", "Lote", "Caduca"])
        self.stock_table.setColumnWidth(0, 110)
        self.stock_table.setColumnWidth(1, 95)
        self.stock_table.setColumnWidth(2, 130)
        self.stock_table.setColumnWidth(3, 150)
        self.stock_table.setColumnWidth(4, 85)
        self.stock_table.setColumnWidth(5, 105)
        self.stock_table.setColumnWidth(7, 110)
        stock_layout.addWidget(self.stock_table, 1)
        self.stock_totals_table = QTableWidget(1, 8)
        self.stock_totals_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.stock_totals_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.stock_totals_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.stock_totals_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.stock_totals_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.stock_totals_table.verticalHeader().setVisible(False)
        self.stock_totals_table.horizontalHeader().setVisible(False)
        stock_totals_header = self.stock_totals_table.horizontalHeader()
        stock_totals_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        stock_totals_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        stock_totals_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        stock_totals_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        stock_totals_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        stock_totals_header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        stock_totals_header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        stock_totals_header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        self.stock_totals_table.setFixedHeight(30)
        self.stock_totals_table.setColumnWidth(0, 110)
        self.stock_totals_table.setColumnWidth(1, 95)
        self.stock_totals_table.setColumnWidth(2, 130)
        self.stock_totals_table.setColumnWidth(3, 150)
        self.stock_totals_table.setColumnWidth(4, 85)
        self.stock_totals_table.setColumnWidth(5, 105)
        self.stock_totals_table.setColumnWidth(7, 110)
        stock_layout.addWidget(self.stock_totals_table)
        tabs.addTab(stock_tab, "Stock")

        mensual_tab = QWidget()
        mensual_layout = QVBoxLayout(mensual_tab)
        mensual_layout.setContentsMargins(8, 8, 8, 8)
        mensual_layout.setSpacing(6)
        mensual_filters = QHBoxLayout()
        mensual_filters.addWidget(QLabel("Desde"))
        self.monthly_orders_date_from = QDateEdit()
        self.monthly_orders_date_from.setCalendarPopup(True)
        self.monthly_orders_date_from.setDisplayFormat("dd/MM/yyyy")
        self.monthly_orders_date_from.setDate(QDate(2000, 1, 1))
        self.monthly_orders_date_from.dateChanged.connect(
            lambda _d: self._reload_monthly_orders_table(self._current_entradas_articulo_id)
        )
        mensual_filters.addWidget(self.monthly_orders_date_from)
        mensual_filters.addWidget(QLabel("Hasta"))
        self.monthly_orders_date_to = QDateEdit()
        self.monthly_orders_date_to.setCalendarPopup(True)
        self.monthly_orders_date_to.setDisplayFormat("dd/MM/yyyy")
        self.monthly_orders_date_to.setDate(QDate(2100, 12, 31))
        self.monthly_orders_date_to.dateChanged.connect(
            lambda _d: self._reload_monthly_orders_table(self._current_entradas_articulo_id)
        )
        mensual_filters.addWidget(self.monthly_orders_date_to)
        monthly_reset_btn = QPushButton("Limpiar")
        monthly_reset_btn.clicked.connect(self._reset_monthly_orders_date_filters)
        mensual_filters.addWidget(monthly_reset_btn)
        mensual_filters.addStretch(1)
        mensual_layout.addLayout(mensual_filters)
        self.monthly_orders_table = QTableWidget(0, 7)
        self.monthly_orders_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.monthly_orders_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.monthly_orders_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.monthly_orders_table.verticalHeader().setVisible(False)
        self.monthly_orders_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.monthly_orders_table.setAlternatingRowColors(True)
        self.monthly_orders_table.setStyleSheet("QTableWidget::item:focus { border: none; outline: 0; }")
        monthly_header = self.monthly_orders_table.horizontalHeader()
        monthly_header.setSectionsClickable(True)
        monthly_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        monthly_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        monthly_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        monthly_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        monthly_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        monthly_header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        monthly_header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.monthly_orders_table.setHorizontalHeaderLabels(
            ["Mes", "Pedidos", "Cantidad", "Kg", "Media", "Ult. fecha", "Ult. pedido"]
        )
        self.monthly_orders_table.setColumnWidth(0, 95)
        self.monthly_orders_table.setColumnWidth(1, 75)
        self.monthly_orders_table.setColumnWidth(2, 95)
        self.monthly_orders_table.setColumnWidth(3, 95)
        self.monthly_orders_table.setColumnWidth(4, 95)
        self.monthly_orders_table.setColumnWidth(5, 105)
        mensual_layout.addWidget(self.monthly_orders_table, 1)
        tabs.addTab(mensual_tab, "Mensual")

        pedidos_tab = QWidget()
        pedidos_layout = QVBoxLayout(pedidos_tab)
        pedidos_layout.setContentsMargins(8, 8, 8, 8)
        pedidos_layout.setSpacing(6)
        pedidos_filters = QHBoxLayout()
        pedidos_filters.addWidget(QLabel("Desde"))
        self.pedidos_date_from = QDateEdit()
        self.pedidos_date_from.setCalendarPopup(True)
        self.pedidos_date_from.setDisplayFormat("dd/MM/yyyy")
        self.pedidos_date_from.setDate(QDate(2000, 1, 1))
        self.pedidos_date_from.dateChanged.connect(lambda _d: self._reload_pedidos_table(self._current_entradas_articulo_id))
        pedidos_filters.addWidget(self.pedidos_date_from)
        pedidos_filters.addWidget(QLabel("Hasta"))
        self.pedidos_date_to = QDateEdit()
        self.pedidos_date_to.setCalendarPopup(True)
        self.pedidos_date_to.setDisplayFormat("dd/MM/yyyy")
        self.pedidos_date_to.setDate(QDate(2100, 12, 31))
        self.pedidos_date_to.dateChanged.connect(lambda _d: self._reload_pedidos_table(self._current_entradas_articulo_id))
        pedidos_filters.addWidget(self.pedidos_date_to)
        self.pedidos_reset_btn = QPushButton("Limpiar")
        self.pedidos_reset_btn.clicked.connect(self._reset_pedidos_date_filters)
        pedidos_filters.addWidget(self.pedidos_reset_btn)
        pedidos_filters.addStretch(1)
        pedidos_layout.addLayout(pedidos_filters)
        self.pedidos_table = QTableWidget(0, 6)
        self.pedidos_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.pedidos_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.pedidos_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.pedidos_table.verticalHeader().setVisible(False)
        self.pedidos_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.pedidos_table.setAlternatingRowColors(True)
        self.pedidos_table.setStyleSheet("QTableWidget::item:focus { border: none; outline: 0; }")
        pedidos_header = self.pedidos_table.horizontalHeader()
        pedidos_header.setSectionsClickable(True)
        pedidos_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        pedidos_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        pedidos_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        pedidos_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        pedidos_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        pedidos_header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.pedidos_table.setHorizontalHeaderLabels(["Fecha", "Pedido Nº", "Albarán", "Cantidad", "Lote", "Caducidad"])
        self.pedidos_table.setColumnWidth(0, 110)
        self.pedidos_table.setColumnWidth(1, 130)
        self.pedidos_table.setColumnWidth(2, 150)
        self.pedidos_table.setColumnWidth(3, 95)
        self.pedidos_table.setColumnWidth(5, 110)
        pedidos_layout.addWidget(self.pedidos_table, 1)
        tabs.addTab(pedidos_tab, "Pedidos")

        tarifa_tab = QWidget()
        tarifa_layout = QVBoxLayout(tarifa_tab)
        tarifa_layout.setContentsMargins(8, 8, 8, 8)
        tarifa_layout.setSpacing(6)
        tarifa_filters = QHBoxLayout()
        tarifa_filters.addWidget(QLabel("Año"))
        self.tarifa_year_filter = QComboBox()
        self.tarifa_year_filter.addItem("Todos", "")
        self.tarifa_year_filter.currentIndexChanged.connect(lambda _idx: self._reload_tarifas_table())
        tarifa_filters.addWidget(self.tarifa_year_filter)
        tarifa_button_h = self.tarifa_year_filter.sizeHint().height()
        tarifa_add_style = (
            "QPushButton { min-height: 0px; padding: 0 10px; border: 1px solid #1E7E34; "
            "border-radius: 3px; background: #2E7D32; color: #FFFFFF; font-weight: 600; }"
            "QPushButton:hover { background: #256D2A; }"
            "QPushButton:disabled { color: #E8EDF3; background: #9DB8A1; border-color: #9DB8A1; }"
        )
        tarifa_edit_style = (
            "QPushButton { min-height: 0px; padding: 0 10px; border: 1px solid #1F5FBF; "
            "border-radius: 3px; background: #1565C0; color: #FFFFFF; font-weight: 600; }"
            "QPushButton:hover { background: #0F55A4; }"
            "QPushButton:disabled { color: #E8EDF3; background: #9BB7DA; border-color: #9BB7DA; }"
        )
        tarifa_delete_style = (
            "QPushButton { min-height: 0px; padding: 0 10px; border: 1px solid #A12D2A; "
            "border-radius: 3px; background: #C62828; color: #FFFFFF; font-weight: 600; }"
            "QPushButton:hover { background: #A92222; }"
            "QPushButton:disabled { color: #F5E8E8; background: #D9A0A0; border-color: #D9A0A0; }"
        )
        self.add_tarifa_btn = QPushButton("Añadir tarifa")
        self.add_tarifa_btn.setFixedHeight(tarifa_button_h)
        self.add_tarifa_btn.setStyleSheet(tarifa_add_style)
        self.add_tarifa_btn.clicked.connect(self._add_tarifa_row)
        tarifa_filters.addWidget(self.add_tarifa_btn)
        self.edit_tarifa_btn = QPushButton("Editar")
        self.edit_tarifa_btn.setFixedHeight(tarifa_button_h)
        self.edit_tarifa_btn.setStyleSheet(tarifa_edit_style)
        self.edit_tarifa_btn.clicked.connect(self._edit_tarifa_row)
        tarifa_filters.addWidget(self.edit_tarifa_btn)
        self.delete_tarifa_btn = QPushButton("Eliminar")
        self.delete_tarifa_btn.setFixedHeight(tarifa_button_h)
        self.delete_tarifa_btn.setStyleSheet(tarifa_delete_style)
        self.delete_tarifa_btn.clicked.connect(self._delete_tarifa_row)
        tarifa_filters.addWidget(self.delete_tarifa_btn)
        tarifa_filters.addStretch(1)
        tarifa_layout.addLayout(tarifa_filters)
        tarifa_content = QHBoxLayout()
        tarifa_content.setSpacing(10)
        tarifa_table_wrap = QWidget()
        tarifa_table_layout = QVBoxLayout(tarifa_table_wrap)
        tarifa_table_layout.setContentsMargins(0, 0, 0, 0)
        tarifa_table_layout.setSpacing(0)
        self.tarifa_header_table = QTableWidget(2, 10)
        self.tarifa_header_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.tarifa_header_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tarifa_header_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tarifa_header_table.verticalHeader().setVisible(False)
        self.tarifa_header_table.horizontalHeader().setVisible(False)
        self.tarifa_header_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tarifa_header_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tarifa_header_table.setShowGrid(True)
        self.tarifa_header_table.setFixedHeight(62)
        self.tarifa_header_table.setSpan(0, 0, 2, 1)
        self.tarifa_header_table.setSpan(0, 1, 1, 3)
        self.tarifa_header_table.setSpan(0, 4, 2, 1)
        self.tarifa_header_table.setSpan(0, 5, 1, 5)
        tarifa_header_labels = {
            (0, 0): "Año",
            (0, 1): "IREKS",
            (1, 1): "€/Env.",
            (1, 2): "€/kg",
            (1, 3): "Delta",
            (0, 4): "Dto %",
            (0, 5): "DISTRIBUIDOR",
            (1, 5): "Costo",
            (1, 6): "€/Env.",
            (1, 7): "€/kg",
            (1, 8): "Delta",
            (1, 9): "Margen",
        }
        for (row_idx, col_idx), label in tarifa_header_labels.items():
            cell = QTableWidgetItem(label)
            cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            font = cell.font()
            font.setBold(True)
            cell.setFont(font)
            cell.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.tarifa_header_table.setItem(row_idx, col_idx, cell)
        self.tarifa_header_table.setStyleSheet(
            "QTableWidget { background: #F3F6FA; color: #0B2545; gridline-color: #D8E0EC; }"
            "QTableWidget::item { padding: 2px; }"
        )
        tarifa_table_layout.addWidget(self.tarifa_header_table)
        self.tarifa_table = QTableWidget(0, 10)
        self.tarifa_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tarifa_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tarifa_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tarifa_table.verticalHeader().setVisible(False)
        self.tarifa_table.horizontalHeader().setVisible(False)
        self.tarifa_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tarifa_table.setStyleSheet("QTableWidget::item:focus { border: none; outline: 0; }")
        tarifa_header = self.tarifa_table.horizontalHeader()
        tarifa_header.setSectionsClickable(True)
        tarifa_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        tarifa_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        tarifa_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        tarifa_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        tarifa_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        tarifa_header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        tarifa_header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        tarifa_header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        tarifa_header.setSectionResizeMode(8, QHeaderView.ResizeMode.Fixed)
        tarifa_header.setSectionResizeMode(9, QHeaderView.ResizeMode.Fixed)
        self.tarifa_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        tarifa_column_widths = [58, 86, 86, 92, 82, 86, 86, 86, 92, 88]
        for col_idx, width in enumerate(tarifa_column_widths):
            self.tarifa_table.setColumnWidth(col_idx, width)
        self.tarifa_table.setHorizontalHeaderLabels(
            [
                "Año",
                "IREKS",
                "IREKS",
                "IREKS",
                "Dto",
                "DISTRIBUIDOR",
                "DISTRIBUIDOR",
                "DISTRIBUIDOR",
                "DISTRIBUIDOR",
                "DISTRIBUIDOR",
            ]
        )
        self._adjust_tarifa_table_width()
        tarifa_table_layout.addWidget(self.tarifa_table, 1)
        tarifa_content.addWidget(tarifa_table_wrap, 0)
        tarifa_layout.addLayout(tarifa_content, 1)
        tabs.insertTab(1, tarifa_tab, "Tarifa")

        nutricion_tab = QWidget()
        nutricion_layout = QVBoxLayout(nutricion_tab)
        nutricion_layout.setContentsMargins(8, 8, 8, 8)
        nutricion_layout.setSpacing(6)
        self.nutricion_table = QTableWidget(9, 2)
        self.nutricion_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.nutricion_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        self.nutricion_table.verticalHeader().setVisible(False)
        self.nutricion_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.nutricion_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.nutricion_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.nutricion_table.setColumnWidth(1, 140)
        self.nutricion_table.setHorizontalHeaderLabels(["Nutriente", "Por 100 g"])
        nutrientes = [
            ("Energia (kJ)", "energia_kj"),
            ("Energia (kcal)", "energia_kcal"),
            ("Grasas (g)", "grasas_g"),
            ("Saturadas (g)", "saturadas_g"),
            ("Hidratos (g)", "hidratos_g"),
            ("Azucares (g)", "azucares_g"),
            ("Fibra (g)", "fibra_g"),
            ("Proteinas (g)", "proteinas_g"),
            ("Sal (g)", "sal_g"),
        ]
        self._nutrient_keys = [key for _label, key in nutrientes]
        for row_idx, (label, _key) in enumerate(nutrientes):
            name_item = QTableWidgetItem(label)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            value_item = QTableWidgetItem("0.00")
            value_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.nutricion_table.setItem(row_idx, 0, name_item)
            self.nutricion_table.setItem(row_idx, 1, value_item)
        self.nutricion_table.itemChanged.connect(self._on_nutricion_item_changed)
        nutricion_layout.addWidget(self.nutricion_table, 1)
        tabs.addTab(nutricion_tab, "Nutición")

        clientes_tab = QWidget()
        clientes_layout = QVBoxLayout(clientes_tab)
        clientes_info = QLabel("Pestaña Clientes pendiente de implementar.")
        clientes_info.setWordWrap(True)
        clientes_layout.addWidget(clientes_info, 1)
        tabs.addTab(clientes_tab, "Clientes")
        tabs_layout.addWidget(tabs)
        right_splitter.addWidget(tabs_host)
        right_splitter.setStretchFactor(0, 1)
        right_splitter.setStretchFactor(1, 9)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(0)
        splitter.handle(1).setEnabled(False)

    def _build_product_reports_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.product_report_prompt = QPlainTextEdit()
        self.product_report_prompt.setObjectName("productReportPrompt")
        self.product_report_prompt.setFixedHeight(58)
        self.product_report_prompt.setPlaceholderText(
            "Ej.: productos activos de la familia mejorantes, muestra ref corta, descripcion, presentacion, total presentacion y precio fabricante"
        )
        layout.addWidget(self.product_report_prompt)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)
        self.product_report_generate_btn = QPushButton("Generar")
        self.product_report_generate_btn.setProperty("btnRole", "primary")
        self.product_report_excel_btn = QPushButton("Excel")
        self.product_report_excel_btn.setProperty("btnRole", "success")
        self.product_report_pdf_btn = QPushButton("PDF")
        self.product_report_pdf_btn.setProperty("btnRole", "secondary")
        self.product_report_print_btn = QPushButton("Imprimir")
        self.product_report_print_btn.setProperty("btnRole", "secondary")
        self.product_report_generate_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.product_report_excel_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self.product_report_pdf_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        self.product_report_print_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        self.product_report_generate_btn.clicked.connect(self._generate_product_report)
        self.product_report_excel_btn.clicked.connect(self._export_product_report_excel)
        self.product_report_pdf_btn.clicked.connect(self._export_product_report_pdf)
        self.product_report_print_btn.clicked.connect(self._print_product_report)
        actions.addWidget(self.product_report_generate_btn)
        actions.addWidget(self.product_report_excel_btn)
        actions.addWidget(self.product_report_pdf_btn)
        actions.addWidget(self.product_report_print_btn)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.product_report_status_label = QLabel("Sin listado generado.")
        self.product_report_status_label.setObjectName("productReportStatus")
        layout.addWidget(self.product_report_status_label)

        self.product_report_table = QTableWidget(0, 0)
        self.product_report_table.setObjectName("productReportTable")
        self.product_report_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.product_report_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.product_report_table.setAlternatingRowColors(True)
        self.product_report_table.verticalHeader().setVisible(False)
        self.product_report_table.horizontalHeader().setVisible(True)
        self.product_report_table.horizontalHeader().setSectionsClickable(True)
        self.product_report_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.product_report_table, 1)
        self._set_product_report_actions_enabled(False)
        return panel

    def _open_product_reports_dialog(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Listados de productos IREKS")
        dialog.setModal(False)
        dialog.resize(1080, 640)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._build_product_reports_panel())
        dialog.show()
        self._product_reports_dialog = dialog

    def _set_product_report_actions_enabled(self, enabled: bool) -> None:
        for attr in ("product_report_excel_btn", "product_report_pdf_btn", "product_report_print_btn"):
            button = getattr(self, attr, None)
            if button is not None:
                button.setEnabled(enabled)

    def _build_ireks_data_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("ireksDataTab")
        tab.setStyleSheet(
            """
            QWidget#ireksDataTab {
                background: #FFFFFF;
            }
            QWidget#ireksDataTab QLabel {
                color: #486081;
                font-weight: 500;
            }
            QWidget#ireksDataTab QComboBox,
            QWidget#ireksDataTab QLineEdit {
                min-height: 28px;
            }
            """
        )
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 10, 8, 8)
        layout.setSpacing(8)

        for widget in (self.detail_data_top_separator, self.detail_data_row_separator):
            widget.hide()

        self.lbl_detail_envase.setText("Presentación")
        self.lbl_detail_envase_cantidad.setText("Contenido")
        self.lbl_detail_envase_peso.setText("Peso unidad")
        self.lbl_detail_envase_unidad.setText("Unidad peso")
        self.lbl_detail_envase_total.setText("Total presentación")
        self.lbl_detail_contenido_unidad = QLabel("Unidad contenido", tab)
        self.detail_contenido_unidad = QComboBox(tab)
        self.detail_contenido_unidad.setEditable(True)
        self.detail_contenido_unidad.addItems(["", "BOLSA", "BOTELLA", "SACO", "LATA", "CUBO", "UNIDAD"])
        self.detail_contenido_unidad.setMinimumWidth(120)
        self.detail_contenido_unidad.setMaximumWidth(150)

        row_presentacion_1 = QHBoxLayout()
        row_presentacion_1.setContentsMargins(0, 0, 0, 0)
        row_presentacion_1.setSpacing(8)
        row_presentacion_1.addWidget(self._reparent_detail_widget(self.lbl_detail_envase, tab))
        row_presentacion_1.addWidget(self._reparent_detail_widget(self.detail_envase_id, tab), 2)
        row_presentacion_1.addWidget(self._reparent_detail_widget(self.lbl_detail_envase_cantidad, tab))
        row_presentacion_1.addWidget(self._reparent_detail_widget(self.detail_envase_cantidad, tab), 1)
        row_presentacion_1.addWidget(self.lbl_detail_contenido_unidad)
        row_presentacion_1.addWidget(self.detail_contenido_unidad, 1)
        row_presentacion_1.addStretch(1)

        row_presentacion_2 = QHBoxLayout()
        row_presentacion_2.setContentsMargins(0, 0, 0, 0)
        row_presentacion_2.setSpacing(8)
        row_presentacion_2.addWidget(self._reparent_detail_widget(self.lbl_detail_envase_peso, tab))
        row_presentacion_2.addWidget(self._reparent_detail_widget(self.detail_envase_peso, tab), 1)
        row_presentacion_2.addWidget(self._reparent_detail_widget(self.lbl_detail_envase_unidad, tab))
        row_presentacion_2.addWidget(self._reparent_detail_widget(self.detail_envase_unidad, tab), 1)
        row_presentacion_2.addWidget(self._reparent_detail_widget(self.lbl_detail_envase_total, tab))
        row_presentacion_2.addWidget(self._reparent_detail_widget(self.detail_envase_total, tab), 1)
        row_presentacion_2.addStretch(1)

        row_transporte_1 = QHBoxLayout()
        row_transporte_1.setContentsMargins(0, 0, 0, 0)
        row_transporte_1.setSpacing(8)
        row_transporte_2 = QHBoxLayout()
        row_transporte_2.setContentsMargins(0, 0, 0, 0)
        row_transporte_2.setSpacing(8)
        row_transporte_obs = QHBoxLayout()
        row_transporte_obs.setContentsMargins(0, 0, 0, 0)
        row_transporte_obs.setSpacing(8)
        self.lbl_transporte_pallet = QLabel("Pallet", tab)
        self.transporte_pallet_tipo = QComboBox(tab)
        self.transporte_pallet_tipo.addItems(["", "EUR", "Americano", "Medio pallet", "Otro"])
        self.lbl_transporte_cajas_capa = QLabel("Presentaciones/capa", tab)
        self.transporte_cajas_por_capa = QLineEdit(tab)
        self.transporte_cajas_por_capa.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.lbl_transporte_capas = QLabel("Capas", tab)
        self.transporte_capas_por_pallet = QLineEdit(tab)
        self.transporte_capas_por_pallet.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.lbl_transporte_cajas_pallet = QLabel("Presentaciones/pallet", tab)
        self.transporte_cajas_por_pallet = QLineEdit(tab)
        self.transporte_cajas_por_pallet.setReadOnly(True)
        self.transporte_cajas_por_pallet.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.lbl_transporte_unidades = QLabel("Uds/pallet", tab)
        self.transporte_unidades_por_pallet = QLineEdit(tab)
        self.transporte_unidades_por_pallet.setReadOnly(True)
        self.transporte_unidades_por_pallet.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.lbl_transporte_kg = QLabel("Total pallet", tab)
        self.transporte_kg_por_pallet = QLineEdit(tab)
        self.transporte_kg_por_pallet.setReadOnly(True)
        self.transporte_kg_por_pallet.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.lbl_transporte_obs = QLabel("Obs.", tab)
        self.transporte_observaciones = QLineEdit(tab)
        for widget in (
            self.transporte_cajas_por_capa,
            self.transporte_capas_por_pallet,
            self.transporte_cajas_por_pallet,
            self.transporte_unidades_por_pallet,
            self.transporte_kg_por_pallet,
        ):
            widget.setMinimumWidth(76)
            widget.setMaximumWidth(90)
        self.transporte_pallet_tipo.setMinimumWidth(105)
        self.transporte_pallet_tipo.setMaximumWidth(130)
        self.transporte_observaciones.setMinimumWidth(260)
        row_transporte_1.addWidget(self.lbl_transporte_pallet)
        row_transporte_1.addWidget(self.transporte_pallet_tipo)
        row_transporte_1.addWidget(self.lbl_transporte_cajas_capa)
        row_transporte_1.addWidget(self.transporte_cajas_por_capa)
        row_transporte_1.addWidget(self.lbl_transporte_capas)
        row_transporte_1.addWidget(self.transporte_capas_por_pallet)
        row_transporte_1.addStretch(1)
        row_transporte_2.addWidget(self.lbl_transporte_cajas_pallet)
        row_transporte_2.addWidget(self.transporte_cajas_por_pallet)
        row_transporte_2.addWidget(self.lbl_transporte_unidades)
        row_transporte_2.addWidget(self.transporte_unidades_por_pallet)
        row_transporte_2.addWidget(self.lbl_transporte_kg)
        row_transporte_2.addWidget(self.transporte_kg_por_pallet)
        row_transporte_2.addStretch(1)
        row_transporte_obs.addWidget(self.lbl_transporte_obs)
        row_transporte_obs.addWidget(self.transporte_observaciones, 1)

        row_taxonomy = QHBoxLayout()
        row_taxonomy.setContentsMargins(0, 0, 0, 0)
        row_taxonomy.setSpacing(8)
        row_taxonomy.addWidget(self._reparent_detail_widget(self.lbl_detail_fabricante, tab))
        row_taxonomy.addWidget(self._reparent_detail_widget(self.detail_fabricante_id, tab), 2)
        row_taxonomy.addWidget(self._reparent_detail_widget(self.lbl_detail_familia, tab))
        row_taxonomy.addWidget(self._reparent_detail_widget(self.detail_familia_id, tab), 3)
        row_taxonomy.addWidget(self._reparent_detail_widget(self.lbl_detail_subfamilia, tab))
        row_taxonomy.addWidget(self._reparent_detail_widget(self.detail_subfamilia_id, tab), 3)
        row_taxonomy.addStretch(1)

        layout.addLayout(row_taxonomy)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)
        layout.addLayout(row_presentacion_1)
        layout.addLayout(row_presentacion_2)
        line_2 = QFrame()
        line_2.setFrameShape(QFrame.Shape.HLine)
        line_2.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line_2)
        layout.addLayout(row_transporte_1)
        layout.addLayout(row_transporte_2)
        layout.addLayout(row_transporte_obs)
        layout.addStretch(1)

        self.transporte_pallet_tipo.currentIndexChanged.connect(self._schedule_autosave)
        self.detail_contenido_unidad.currentTextChanged.connect(self._schedule_autosave)
        self.transporte_cajas_por_capa.textEdited.connect(lambda *_: self._update_transport_total_preview())
        self.transporte_capas_por_pallet.textEdited.connect(lambda *_: self._update_transport_total_preview())
        self.transporte_cajas_por_capa.textEdited.connect(lambda *_: self._schedule_autosave())
        self.transporte_capas_por_pallet.textEdited.connect(lambda *_: self._schedule_autosave())
        self.transporte_observaciones.textEdited.connect(lambda *_: self._schedule_autosave())
        self._update_transport_label_texts()
        return tab

    def _reparent_detail_widget(self, widget: QWidget, parent: QWidget) -> QWidget:
        widget.setParent(parent)
        widget.setMinimumHeight(28)
        widget.setMaximumHeight(30)
        if isinstance(widget, QLineEdit):
            widget.setMinimumWidth(70)
        elif isinstance(widget, QComboBox):
            widget.setMinimumWidth(120)
        return widget

    def _schedule_autosave(self) -> None:
        if self._loading:
            return
        self._autosave_timer.start(350)

    def reload(self) -> None:
        selected_id = self._selected_id()
        payload = self.ireks_service.list_payload(
            search=self.search_input.text().strip(),
            familia_id=self._current_filter_value(self.familia_filter),
            subfamilia_id=self._current_filter_value(self.subfamilia_filter),
            fabricante_id=self._current_filter_value(self.fabricante_filter),
            activity_filter=str(self.activity_filter.currentData() or "all"),
            distributor_filter_id=self.external_distributor_filter_id,
        )
        self._apply_catalog_values(payload.catalogs)
        self._reload_filter_values()
        self._reload_envase_values()
        self._reload_distribuidor_values()
        self._sync_detail_taxonomy_combos(
            self._current_filter_value(self.detail_fabricante_id),
            self._current_filter_value(self.detail_familia_id),
            self._current_filter_value(self.detail_subfamilia_id),
        )
        self.rows = payload.rows
        self.table.setRowCount(len(self.rows))
        for row_idx, row in enumerate(self.rows):
            ref_item = QTableWidgetItem(str(row.articulo_referencia_corta or ""))
            ref_item.setData(Qt.ItemDataRole.UserRole, row.id)
            ref_item.setData(Qt.ItemDataRole.UserRole + 1, str(row.articulo_id or "").strip())
            self.table.setItem(row_idx, 0, ref_item)
            self.table.setItem(row_idx, 1, QTableWidgetItem(str(row.articulo_descripcion or "")))
            item_id = int(row.id or 0)
            self._set_selection_widget(row_idx, item_id in self._selected_product_ids, item_id)
        if self.table.rowCount() > 0:
            self.table.sortItems(self._left_sort_col, self._left_sort_order)
            self.table.horizontalHeader().setSortIndicator(self._left_sort_col, self._left_sort_order)
        self._select_by_id(selected_id)
        if self.table.rowCount() > 0 and not self.table.selectionModel().selectedRows():
            self.table.selectRow(0)
        if self.table.rowCount() > 0:
            self._show_selected_details()
        else:
            self._clear_details()

    def _current_filter_value(self, combo: QComboBox | None) -> str:
        if combo is None:
            return ""
        return str(combo.currentData() or "")

    def set_external_distributor_filter(self, distribuidor_id: str) -> None:
        self.external_distributor_filter_id = str(distribuidor_id or "").strip()
        self.reload()

    def focus_article_and_open_salidas(self, articulo_id: str) -> None:
        target = str(articulo_id or "").strip()
        if not target:
            return
        if not self._select_by_articulo_id(target):
            return
        self._show_selected_details()
        tab_widget = getattr(self, "detail_tabs", None)
        salidas_index = int(getattr(self, "_salidas_tab_index", -1) or -1)
        if tab_widget is not None and salidas_index >= 0:
            tab_widget.setCurrentIndex(salidas_index)

    def focus_article_and_open_entradas(self, articulo_id: str) -> None:
        target = str(articulo_id or "").strip()
        if not target:
            return
        if not self._select_by_articulo_id(target):
            return
        self._show_selected_details()
        tab_widget = getattr(self, "detail_tabs", None)
        entradas_index = int(getattr(self, "_entradas_tab_index", -1) or -1)
        if tab_widget is not None and entradas_index >= 0:
            tab_widget.setCurrentIndex(entradas_index)

    def _select_by_articulo_id(self, articulo_id: str) -> bool:
        target = str(articulo_id or "").strip()
        if not target:
            return False
        for i in range(self.table.rowCount()):
            ref_item = self.table.item(i, 0)
            current_articulo_id = str(ref_item.data(Qt.ItemDataRole.UserRole + 1) or "").strip() if ref_item else ""
            if current_articulo_id == target:
                self.table.selectRow(i)
                return True
        return False

    def _apply_catalog_values(self, catalogs) -> None:
        self._distribuidores = catalogs.distribuidores
        self._fabricantes = catalogs.fabricantes
        self._familias = catalogs.familias
        self._subfamilias = catalogs.subfamilias
        self._envases = catalogs.envases

    def _reload_filter_values(self) -> None:
        current_fabricante = self._current_filter_value(self.fabricante_filter)
        current_familia = self._current_filter_value(self.familia_filter)
        current_subfamilia = self._current_filter_value(self.subfamilia_filter)

        fabricantes = [x for x in self._fabricantes if str(x.fabricante_id or "").strip()]
        familias = [
            x
            for x in self._familias
            if str(x.articulo_familia_id or "").strip()
            and (not current_fabricante or str(x.fabricante_id or "").strip() == current_fabricante)
        ]
        familia_ids = {str(x.articulo_familia_id or "").strip() for x in familias}
        subfamilias = [
            x
            for x in self._subfamilias
            if str(x.articulo_subfamilia_id or "").strip()
            and (not current_familia or str(x.articulo_familia_id or "").strip() == current_familia)
            and (not current_fabricante or str(x.articulo_familia_id or "").strip() in familia_ids)
        ]

        self.fabricante_filter.blockSignals(True)
        self.familia_filter.blockSignals(True)
        self.subfamilia_filter.blockSignals(True)

        self.fabricante_filter.clear()
        self.fabricante_filter.addItem("Fabricante (todos)", "")
        for value in fabricantes:
            fabricante_id = str(value.fabricante_id or "").strip()
            label = str(value.fabricante_nombre or "").strip() or fabricante_id
            self.fabricante_filter.addItem(label, fabricante_id)
        idx = self.fabricante_filter.findData(current_fabricante)
        self.fabricante_filter.setCurrentIndex(idx if idx >= 0 else 0)

        if current_familia and current_familia not in {str(x.articulo_familia_id or "").strip() for x in familias}:
            current_familia = ""
        self.familia_filter.clear()
        self.familia_filter.addItem("Familia (todas)", "")
        for value in familias:
            familia_id = str(value.articulo_familia_id or "").strip()
            nombre = str(value.articulo_familia_nombre or "").strip()
            label = nombre or familia_id
            self.familia_filter.addItem(label, familia_id)
        idx = self.familia_filter.findData(current_familia)
        self.familia_filter.setCurrentIndex(idx if idx >= 0 else 0)

        if current_subfamilia and current_subfamilia not in {str(x.articulo_subfamilia_id or "").strip() for x in subfamilias}:
            current_subfamilia = ""
        self.subfamilia_filter.clear()
        self.subfamilia_filter.addItem("Subfamilia (todas)", "")
        for value in subfamilias:
            subfamilia_id = str(value.articulo_subfamilia_id or "").strip()
            nombre = str(value.articulo_subfamilia_nombre or "").strip()
            label = nombre or subfamilia_id
            self.subfamilia_filter.addItem(label, subfamilia_id)
        idx = self.subfamilia_filter.findData(current_subfamilia)
        self.subfamilia_filter.setCurrentIndex(idx if idx >= 0 else 0)

        self.fabricante_filter.blockSignals(False)
        self.familia_filter.blockSignals(False)
        self.subfamilia_filter.blockSignals(False)

    def _reload_envase_values(self) -> None:
        current = str(self.detail_envase_id.currentData() or "")
        self.detail_envase_id.blockSignals(True)
        self.detail_envase_id.clear()
        self.detail_envase_id.addItem("", "")
        for value in self._envases:
            envase_id = str(value.envase_id or "").strip()
            if not envase_id:
                continue
            nombre = str(value.envase_nombre or "").strip()
            label = nombre
            self.detail_envase_id.addItem(label, envase_id)
        idx = self.detail_envase_id.findData(current)
        self.detail_envase_id.setCurrentIndex(idx if idx >= 0 else 0)
        self.detail_envase_id.blockSignals(False)

    def _reload_distribuidor_values(self) -> None:
        current = str(self.detail_distribuidor_id.currentData() or "")
        self.detail_distribuidor_id.blockSignals(True)
        self.detail_distribuidor_id.clear()
        self.detail_distribuidor_id.addItem("", "")
        for value in self._distribuidores:
            distribuidor_id = str(value.distribuidor_id or "").strip()
            if not distribuidor_id:
                continue
            label = str(value.distribuidor_nombre_comercial or "").strip() or str(value.distribuidor_razon_social or "").strip()
            self.detail_distribuidor_id.addItem(label or distribuidor_id, distribuidor_id)
        idx = self.detail_distribuidor_id.findData(current)
        self.detail_distribuidor_id.setCurrentIndex(idx if idx >= 0 else 0)
        self.detail_distribuidor_id.blockSignals(False)

    def _sync_detail_taxonomy_combos(
        self,
        fabricante_id: str = "",
        familia_id: str = "",
        subfamilia_id: str = "",
    ) -> None:
        self.detail_fabricante_id.blockSignals(True)
        self.detail_fabricante_id.clear()
        self.detail_fabricante_id.addItem("", "")
        for value in self._fabricantes:
            row_id = str(value.fabricante_id or "").strip()
            if not row_id:
                continue
            label = str(value.fabricante_nombre or "").strip() or row_id
            self.detail_fabricante_id.addItem(label, row_id)
        idx = self.detail_fabricante_id.findData(fabricante_id)
        self.detail_fabricante_id.setCurrentIndex(idx if idx >= 0 else 0)
        self.detail_fabricante_id.blockSignals(False)

        familias = [
            x
            for x in self._familias
            if str(x.articulo_familia_id or "").strip()
            and (not fabricante_id or str(x.fabricante_id or "").strip() == fabricante_id)
        ]
        if familia_id and familia_id not in {str(x.articulo_familia_id or "").strip() for x in familias}:
            familia_id = ""
        self.detail_familia_id.blockSignals(True)
        self.detail_familia_id.clear()
        self.detail_familia_id.addItem("", "")
        for value in familias:
            row_id = str(value.articulo_familia_id or "").strip()
            label = str(value.articulo_familia_nombre or "").strip() or row_id
            self.detail_familia_id.addItem(label, row_id)
        idx = self.detail_familia_id.findData(familia_id)
        self.detail_familia_id.setCurrentIndex(idx if idx >= 0 else 0)
        self.detail_familia_id.blockSignals(False)

        subfamilias = [
            x
            for x in self._subfamilias
            if str(x.articulo_subfamilia_id or "").strip()
            and (not familia_id or str(x.articulo_familia_id or "").strip() == familia_id)
        ]
        if subfamilia_id and subfamilia_id not in {str(x.articulo_subfamilia_id or "").strip() for x in subfamilias}:
            subfamilia_id = ""
        self.detail_subfamilia_id.blockSignals(True)
        self.detail_subfamilia_id.clear()
        self.detail_subfamilia_id.addItem("", "")
        for value in subfamilias:
            row_id = str(value.articulo_subfamilia_id or "").strip()
            label = str(value.articulo_subfamilia_nombre or "").strip() or row_id
            self.detail_subfamilia_id.addItem(label, row_id)
        idx = self.detail_subfamilia_id.findData(subfamilia_id)
        self.detail_subfamilia_id.setCurrentIndex(idx if idx >= 0 else 0)
        self.detail_subfamilia_id.blockSignals(False)

    def _on_fabricante_filter_changed(self, *_args) -> None:
        self.reload()

    def _on_familia_filter_changed(self, *_args) -> None:
        self.reload()

    def _on_detail_fabricante_changed(self, *_args) -> None:
        fabricante_id = self._current_filter_value(self.detail_fabricante_id)
        self._sync_detail_taxonomy_combos(fabricante_id, "", "")
        self._schedule_autosave()

    def _on_detail_familia_changed(self, *_args) -> None:
        fabricante_id = self._current_filter_value(self.detail_fabricante_id)
        familia_id = self._current_filter_value(self.detail_familia_id)
        self._sync_detail_taxonomy_combos(fabricante_id, familia_id, "")
        self._schedule_autosave()

    def _on_detail_subfamilia_changed(self, *_args) -> None:
        self._schedule_autosave()

    def _on_detail_distribuidor_changed(self, *_args) -> None:
        self._load_distributor_reference_for_selected()
        self._schedule_autosave()

    def _on_status_toggled(self, _checked: bool) -> None:
        self._schedule_autosave()

    def _load_distributor_reference_for_selected(self) -> None:
        row = self._selected_row()
        if not row:
            self.detail_referencia_distribuidor.clear()
            self.detail_descripcion_distribuidor.clear()
            return
        distribuidor_id = str(self.detail_distribuidor_id.currentData() or "").strip()
        if not distribuidor_id:
            self.detail_referencia_distribuidor.clear()
            self.detail_descripcion_distribuidor.clear()
            return
        articulo_id = str(row.articulo_id or "").strip()
        ref_row = self.ireks_service.distributor_reference(articulo_id, distribuidor_id)
        prev = self._loading
        self._loading = True
        self.detail_referencia_distribuidor.setText(str(getattr(ref_row, "articulo_referencia_distribuidor", "") or ""))
        self.detail_descripcion_distribuidor.setText(str(getattr(ref_row, "articulo_descripcion_distribuidor", "") or ""))
        self._loading = prev

    def _to_float_text(self, value: str) -> float:
        text = str(value or "").strip().replace(",", ".")
        if not text:
            return 0.0
        try:
            return float(text)
        except Exception:
            return 0.0

    def _update_envase_total_preview(self) -> None:
        cantidad = self._to_float_text(self.detail_envase_cantidad.text())
        peso = self._to_float_text(self.detail_envase_peso.text())
        total = cantidad * peso
        total_txt = f"{total:.4f}".rstrip("0").rstrip(".")
        unidad = self.detail_envase_unidad.currentText().strip()
        if not total_txt:
            self.detail_envase_total.clear()
        else:
            self.detail_envase_total.setText(f"{total_txt} {unidad}".strip())
        self._update_transport_total_preview()

    def _update_transport_total_preview(self) -> None:
        if not hasattr(self, "transporte_cajas_por_pallet"):
            return
        cajas_capa = self._to_float_text(self.transporte_cajas_por_capa.text())
        capas = self._to_float_text(self.transporte_capas_por_pallet.text())
        envase_cantidad = self._to_float_text(self.detail_envase_cantidad.text())
        envase_peso = self._to_float_text(self.detail_envase_peso.text())
        cajas_pallet = cajas_capa * capas
        unidades_pallet = cajas_pallet * envase_cantidad
        kg_pallet = unidades_pallet * envase_peso
        self.transporte_cajas_por_pallet.setText(self._format_float(cajas_pallet))
        self.transporte_unidades_por_pallet.setText(self._format_float(unidades_pallet))
        self.transporte_kg_por_pallet.setText(self._format_float(kg_pallet))

    def _update_transport_label_texts(self) -> None:
        if not hasattr(self, "lbl_transporte_cajas_capa"):
            return
        self.lbl_transporte_cajas_capa.setText("Presentaciones/capa")
        self.lbl_transporte_cajas_pallet.setText("Presentaciones/pallet")

    def _current_envase_name(self) -> str:
        text = str(self.detail_envase_id.currentText() or "").strip()
        if not text:
            return ""
        return text.split(" (", 1)[0].strip()

    def _pluralize_envase_label(self, singular: str) -> str:
        text = str(singular or "Envase").strip()
        if not text:
            return "Envases"
        lower = text.lower()
        if lower.endswith("s"):
            return text
        if lower.endswith(("a", "e", "i", "o", "u")):
            return f"{text}s"
        return f"{text}es"

    def _format_float(self, value: float) -> str:
        if abs(float(value or 0.0)) < 0.000001:
            return ""
        return f"{float(value):.4f}".rstrip("0").rstrip(".")

    def _set_selection_widget(self, row_idx: int, selected: bool, item_id: int) -> None:
        box = QWidget()
        box.setStyleSheet("background: transparent; border: none;")
        box_layout = QHBoxLayout(box)
        box_layout.setContentsMargins(0, 0, 0, 0)
        box_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        check = QCheckBox()
        check.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        check.setChecked(selected)
        check.setStyleSheet(
            """
            QCheckBox { background: transparent; }
            QCheckBox::indicator {
                width: 15px;
                height: 15px;
                border: 1px solid #BFC9D8;
                border-radius: 4px;
                background: transparent;
            }
            QCheckBox::indicator:checked {
                border: 1px solid #BFC9D8;
                background: transparent;
                image: url(assets/icons/checkmark_green.svg);
            }
            """
        )
        check.stateChanged.connect(
            lambda state, rid=item_id: self._toggle_product_selection(rid, state == Qt.CheckState.Checked.value)
        )
        box_layout.addWidget(check)
        self.table.setCellWidget(row_idx, 2, box)

    def _set_list_selected_checkbox(self, row_idx: int, selected: bool) -> None:
        cell = self.table.cellWidget(row_idx, 2)
        if cell is None:
            return
        check = cell.findChild(QCheckBox)
        if check is None:
            return
        prev_loading = self._loading
        self._loading = True
        check.setChecked(selected)
        self._loading = prev_loading

    def _toggle_product_selection(self, item_id: int, selected: bool) -> None:
        if self._loading or not item_id:
            return
        if selected:
            self._selected_product_ids.add(int(item_id))
        else:
            self._selected_product_ids.discard(int(item_id))

    def _visible_product_ids(self) -> list[int]:
        ids: list[int] = []
        for row_idx in range(self.table.rowCount()):
            id_item = self.table.item(row_idx, 0)
            item_id = int(id_item.data(Qt.ItemDataRole.UserRole) or 0) if id_item else 0
            if item_id:
                ids.append(item_id)
        return ids

    def _toggle_all_visible_products_selection(self) -> None:
        ids = self._visible_product_ids()
        if not ids:
            return
        select_all = any(item_id not in self._selected_product_ids for item_id in ids)
        if select_all:
            self._selected_product_ids.update(ids)
        else:
            for item_id in ids:
                self._selected_product_ids.discard(item_id)
        prev_loading = self._loading
        self._loading = True
        for row_idx in range(self.table.rowCount()):
            id_item = self.table.item(row_idx, 0)
            item_id = int(id_item.data(Qt.ItemDataRole.UserRole) or 0) if id_item else 0
            self._set_list_selected_checkbox(row_idx, item_id in self._selected_product_ids)
        self._loading = prev_loading

    def _on_left_header_clicked(self, section: int) -> None:
        if section == 2:
            self._toggle_all_visible_products_selection()
            self.table.horizontalHeader().setSortIndicator(self._left_sort_col, self._left_sort_order)
            return
        if section == self._left_sort_col:
            self._left_sort_order = (
                Qt.SortOrder.DescendingOrder
                if self._left_sort_order == Qt.SortOrder.AscendingOrder
                else Qt.SortOrder.AscendingOrder
            )
        else:
            self._left_sort_col = section
            self._left_sort_order = Qt.SortOrder.AscendingOrder
        self.table.sortItems(self._left_sort_col, self._left_sort_order)
        self.table.horizontalHeader().setSortIndicator(self._left_sort_col, self._left_sort_order)

    def _selected_row(self) -> IngredienteIreks | None:
        selected = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not selected:
            return None
        row_idx = selected[0].row()
        id_item = self.table.item(row_idx, 0)
        item_id = int(id_item.data(Qt.ItemDataRole.UserRole) or 0) if id_item else 0
        if not item_id:
            return None
        return next((row for row in self.rows if int(row.id or 0) == item_id), None)

    def _selected_id(self) -> int | None:
        row = self._selected_row()
        return None if not row else row.id

    def _select_by_id(self, item_id: int | None) -> None:
        if item_id is None:
            return
        for i in range(self.table.rowCount()):
            id_item = self.table.item(i, 0)
            current_id = int(id_item.data(Qt.ItemDataRole.UserRole) or 0) if id_item else 0
            if current_id == int(item_id):
                self.table.selectRow(i)
                return

    def _show_selected_details(self) -> None:
        row = self._selected_row()
        self._loading = True
        if not row:
            self._clear_details()
            self._loading = False
            return
        fabricante_id = str(row.fabricante_id or "").strip()
        familia_id = str(row.articulo_familia_id or "").strip()
        subfamilia_id = str(row.articulo_subfamilia_id or "").strip()
        self._sync_detail_taxonomy_combos(fabricante_id, familia_id, subfamilia_id)
        if fabricante_id and self.detail_fabricante_id.findData(fabricante_id) < 0:
            self.detail_fabricante_id.addItem(f"{fabricante_id} (sin catalogar)", fabricante_id)
            self.detail_fabricante_id.setCurrentIndex(self.detail_fabricante_id.findData(fabricante_id))
        if familia_id and self.detail_familia_id.findData(familia_id) < 0:
            self.detail_familia_id.addItem(f"{familia_id} (sin catalogar)", familia_id)
            self.detail_familia_id.setCurrentIndex(self.detail_familia_id.findData(familia_id))
        if subfamilia_id and self.detail_subfamilia_id.findData(subfamilia_id) < 0:
            self.detail_subfamilia_id.addItem(f"{subfamilia_id} (sin catalogar)", subfamilia_id)
            self.detail_subfamilia_id.setCurrentIndex(self.detail_subfamilia_id.findData(subfamilia_id))
        self.detail_ref_corta.setText(str(row.articulo_referencia_corta or ""))
        self.detail_descripcion.setText(str(row.articulo_descripcion or ""))
        self.detail_referencia.setText(str(row.articulo_referencia or ""))
        envase_id = str(row.articulo_envase_id or "")
        idx = self.detail_envase_id.findData(envase_id)
        if idx < 0 and envase_id:
            self.detail_envase_id.addItem(f"{envase_id} (sin catalogar)", envase_id)
            idx = self.detail_envase_id.findData(envase_id)
        self.detail_envase_id.setCurrentIndex(idx if idx >= 0 else 0)
        contenido_unidad = str(getattr(row, "articulo_contenido_unidad", "") or "")
        cidx = self.detail_contenido_unidad.findText(contenido_unidad)
        if cidx < 0 and contenido_unidad:
            self.detail_contenido_unidad.addItem(contenido_unidad)
            cidx = self.detail_contenido_unidad.findText(contenido_unidad)
        self.detail_contenido_unidad.setCurrentIndex(cidx if cidx >= 0 else 0)
        self.detail_envase_cantidad.setText(
            f"{float(row.articulo_envase_cantidad or 0.0):.4f}".rstrip("0").rstrip(".")
        )
        self.detail_envase_peso.setText(f"{float(row.articulo_envase_peso or 0.0):.4f}".rstrip("0").rstrip("."))
        unidad = str(row.articulo_envase_unidad_medida or "")
        uidx = self.detail_envase_unidad.findText(unidad)
        self.detail_envase_unidad.setCurrentIndex(uidx if uidx >= 0 else 0)
        pallet_tipo = str(getattr(row, "transporte_pallet_tipo", "") or "")
        pidx = self.transporte_pallet_tipo.findText(pallet_tipo)
        if pidx < 0 and pallet_tipo:
            self.transporte_pallet_tipo.addItem(pallet_tipo)
            pidx = self.transporte_pallet_tipo.findText(pallet_tipo)
        self.transporte_pallet_tipo.setCurrentIndex(pidx if pidx >= 0 else 0)
        self.transporte_cajas_por_capa.setText(self._format_float(float(getattr(row, "transporte_cajas_por_capa", 0.0) or 0.0)))
        self.transporte_capas_por_pallet.setText(
            self._format_float(float(getattr(row, "transporte_capas_por_pallet", 0.0) or 0.0))
        )
        self.transporte_observaciones.setText(str(getattr(row, "transporte_observaciones", "") or ""))
        distribuidor_id = str(row.distribuidor_id or "")
        didx = self.detail_distribuidor_id.findData(distribuidor_id)
        if didx < 0 and distribuidor_id:
            self.detail_distribuidor_id.addItem(f"{distribuidor_id} (sin catalogar)", distribuidor_id)
            didx = self.detail_distribuidor_id.findData(distribuidor_id)
        self.detail_distribuidor_id.setCurrentIndex(didx if didx >= 0 else 0)
        ref_row = self.ireks_service.distributor_reference(str(row.articulo_id or "").strip(), distribuidor_id)
        self.detail_referencia_distribuidor.setText(
            str(getattr(ref_row, "articulo_referencia_distribuidor", "") or "")
        )
        self.detail_descripcion_distribuidor.setText(
            str(getattr(ref_row, "articulo_descripcion_distribuidor", "") or "")
        )
        status_activo = bool(getattr(row, "articulo_status_activo", True))
        status_en_lista = bool(getattr(row, "articulo_status_en_lista", False))
        categoria = str(getattr(row, "categoria", "") or "").strip().lower()
        self.detail_status_activo_si.setChecked(status_activo)
        self.detail_status_activo_no.setChecked(not status_activo)
        self.detail_status_en_lista_si.setChecked(status_en_lista)
        self.detail_status_en_lista_no.setChecked(not status_en_lista)
        self._set_ireks_category(categoria)
        selected_articulo_id = str(row.articulo_id or "").strip()
        self._reload_entradas_table(selected_articulo_id)
        self._reload_salidas_table(selected_articulo_id)
        self._reload_stock_table(selected_articulo_id)
        self._reload_monthly_orders_table(selected_articulo_id)
        self._reload_pedidos_table(selected_articulo_id)
        self._reload_tarifas_table(selected_articulo_id)
        self._reload_nutricion_table(selected_articulo_id)
        self._update_envase_total_preview()
        self._update_transport_label_texts()
        self._update_transport_total_preview()
        self._loading = False

    def _clear_details(self) -> None:
        for field in (
            self.detail_ref_corta,
            self.detail_descripcion,
            self.detail_referencia,
            self.detail_referencia_distribuidor,
            self.detail_descripcion_distribuidor,
            self.detail_envase_cantidad,
            self.detail_envase_peso,
            self.detail_envase_total,
            self.transporte_cajas_por_capa,
            self.transporte_capas_por_pallet,
            self.transporte_cajas_por_pallet,
            self.transporte_unidades_por_pallet,
            self.transporte_kg_por_pallet,
            self.transporte_observaciones,
        ):
            field.clear()
        self.detail_envase_id.setCurrentIndex(0)
        if hasattr(self, "detail_contenido_unidad"):
            self.detail_contenido_unidad.setCurrentIndex(0)
        self.transporte_pallet_tipo.setCurrentIndex(0)
        self._update_transport_label_texts()
        self.detail_distribuidor_id.setCurrentIndex(0)
        self.detail_envase_unidad.setCurrentIndex(0)
        self.detail_fabricante_id.setCurrentIndex(0)
        self.detail_familia_id.setCurrentIndex(0)
        self.detail_subfamilia_id.setCurrentIndex(0)
        self.detail_status_activo_si.setChecked(True)
        self.detail_status_en_lista_no.setChecked(True)
        self._set_ireks_category("")
        self._current_entradas_articulo_id = ""
        self._reload_entradas_table("")
        self._reload_salidas_table("")
        self._reload_stock_table("")
        self._reload_monthly_orders_table("")
        self._reload_pedidos_table("")
        self._reload_tarifas_table("")
        self._reload_nutricion_table("")

    def _reset_entradas_date_filters(self) -> None:
        self.entradas_date_from.blockSignals(True)
        self.entradas_date_to.blockSignals(True)
        self.entradas_date_from.setDate(QDate(2000, 1, 1))
        self.entradas_date_to.setDate(QDate(2100, 12, 31))
        self.entradas_date_from.blockSignals(False)
        self.entradas_date_to.blockSignals(False)
        self._reload_entradas_table(self._current_entradas_articulo_id)

    def _reset_salidas_date_filters(self) -> None:
        self.salidas_date_from.blockSignals(True)
        self.salidas_date_to.blockSignals(True)
        self.salidas_date_from.setDate(QDate(2000, 1, 1))
        self.salidas_date_to.setDate(QDate(2100, 12, 31))
        self.salidas_date_from.blockSignals(False)
        self.salidas_date_to.blockSignals(False)
        self._reload_salidas_table(self._current_entradas_articulo_id)

    def _reset_stock_date_filters(self) -> None:
        self.stock_date_from.blockSignals(True)
        self.stock_date_to.blockSignals(True)
        self.stock_date_from.setDate(QDate(2000, 1, 1))
        self.stock_date_to.setDate(QDate(2100, 12, 31))
        self.stock_date_from.blockSignals(False)
        self.stock_date_to.blockSignals(False)
        self._reload_stock_table(self._current_entradas_articulo_id)

    def _reset_pedidos_date_filters(self) -> None:
        self.pedidos_date_from.blockSignals(True)
        self.pedidos_date_to.blockSignals(True)
        self.pedidos_date_from.setDate(QDate(2000, 1, 1))
        self.pedidos_date_to.setDate(QDate(2100, 12, 31))
        self.pedidos_date_from.blockSignals(False)
        self.pedidos_date_to.blockSignals(False)
        self._reload_pedidos_table(self._current_entradas_articulo_id)

    def _reset_monthly_orders_date_filters(self) -> None:
        self.monthly_orders_date_from.blockSignals(True)
        self.monthly_orders_date_to.blockSignals(True)
        self.monthly_orders_date_from.setDate(QDate(2000, 1, 1))
        self.monthly_orders_date_to.setDate(QDate(2100, 12, 31))
        self.monthly_orders_date_from.blockSignals(False)
        self.monthly_orders_date_to.blockSignals(False)
        self._reload_monthly_orders_table(self._current_entradas_articulo_id)

    def _set_entradas_totals(self, total_unidades: float, total_kg: float) -> None:
        vals = [
            "TOTAL",
            "",
            "",
            f"{total_unidades:.2f}",
            f"{total_kg:.2f} kg",
            "",
            "",
        ]
        for col, value in enumerate(vals):
            item = QTableWidgetItem(value)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            if col in (3, 4):
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            self.entradas_totals_table.setItem(0, col, item)

    def _set_salidas_totals(self, total_unidades: float, total_kg: float) -> None:
        vals = [
            "TOTAL",
            "",
            "",
            f"{total_unidades:.2f}",
            f"{total_kg:.2f} kg",
            "",
            "",
        ]
        for col, value in enumerate(vals):
            item = QTableWidgetItem(value)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            if col in (3, 4):
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            self.salidas_totals_table.setItem(0, col, item)

    def _set_stock_totals(self, total_unidades: float, total_kg: float) -> None:
        vals = [
            "TOTAL NETO",
            "",
            "",
            "",
            f"{total_unidades:.2f}",
            f"{total_kg:.2f} kg",
            "",
            "",
        ]
        for col, value in enumerate(vals):
            item = QTableWidgetItem(value)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            if col in (4, 5):
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            self.stock_totals_table.setItem(0, col, item)

    def _reload_entradas_table(self, articulo_id: str) -> None:
        if not hasattr(self, "entradas_table"):
            return
        self.entradas_table.setRowCount(0)
        articulo_id = str(articulo_id or "").strip()
        self._current_entradas_articulo_id = articulo_id
        if not articulo_id:
            self._set_entradas_totals(0.0, 0.0)
            return
        moves, items = self.ireks_service.movement_payload(articulo_id)
        q_from = self.entradas_date_from.date()
        q_to = self.entradas_date_to.date()
        from_date: date = date(q_from.year(), q_from.month(), q_from.day())
        to_date: date = date(q_to.year(), q_to.month(), q_to.day())
        if from_date > to_date:
            from_date, to_date = to_date, from_date
        filtered_moves = [
            mov
            for mov in moves
            if mov.fecha_pedido is not None and from_date <= mov.fecha_pedido <= to_date and float(mov.cantidad or 0.0) > 0
        ]
        peso_total = float(items[0].articulo_envase_peso_total or 0.0) if items else 0.0
        self.entradas_table.setRowCount(len(filtered_moves))
        total_unidades = 0.0
        total_kg = 0.0
        today = date.today()
        for i, mov in enumerate(filtered_moves):
            fecha = mov.fecha_pedido.strftime("%d/%m/%Y") if mov.fecha_pedido else ""
            cantidad = float(mov.cantidad or 0.0)
            kg = cantidad * peso_total
            total_unidades += cantidad
            total_kg += kg
            caduca = mov.articulo_caducidad.strftime("%d/%m/%Y") if mov.articulo_caducidad else ""
            is_expiring = bool(mov.articulo_caducidad and (mov.articulo_caducidad - today).days <= 30)
            vals = [
                fecha,
                str(mov.pedido_numero or "").strip(),
                str(mov.pedido_albaran_numero or "").strip(),
                f"{cantidad:.2f}",
                f"{kg:.2f} kg",
                str(mov.articulo_lote or "").strip(),
                caduca,
            ]
            for col, value in enumerate(vals):
                item = QTableWidgetItem(value)
                if col in (3, 4):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if is_expiring and col == 6:
                    item.setForeground(QBrush(QColor("#B42318")))
                    item.setBackground(QBrush(QColor("#FEE4E2")))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                self.entradas_table.setItem(i, col, item)
        self._set_entradas_totals(total_unidades, total_kg)

    def _reload_salidas_table(self, articulo_id: str) -> None:
        if not hasattr(self, "salidas_table"):
            return
        self.salidas_table.setRowCount(0)
        articulo_id = str(articulo_id or "").strip()
        if not articulo_id:
            self._set_salidas_totals(0.0, 0.0)
            return
        moves, items = self.ireks_service.movement_payload(articulo_id)
        q_from = self.salidas_date_from.date()
        q_to = self.salidas_date_to.date()
        from_date: date = date(q_from.year(), q_from.month(), q_from.day())
        to_date: date = date(q_to.year(), q_to.month(), q_to.day())
        if from_date > to_date:
            from_date, to_date = to_date, from_date
        filtered_moves = [
            mov
            for mov in moves
            if mov.fecha_pedido is not None and from_date <= mov.fecha_pedido <= to_date and float(mov.cantidad or 0.0) < 0
        ]
        peso_total = float(items[0].articulo_envase_peso_total or 0.0) if items else 0.0
        self.salidas_table.setRowCount(len(filtered_moves))
        total_unidades = 0.0
        total_kg = 0.0
        today = date.today()
        for i, mov in enumerate(filtered_moves):
            fecha = mov.fecha_pedido.strftime("%d/%m/%Y") if mov.fecha_pedido else ""
            cantidad = abs(float(mov.cantidad or 0.0))
            kg = cantidad * peso_total
            total_unidades += cantidad
            total_kg += kg
            caduca = mov.articulo_caducidad.strftime("%d/%m/%Y") if mov.articulo_caducidad else ""
            is_expiring = bool(mov.articulo_caducidad and (mov.articulo_caducidad - today).days <= 30)
            vals = [
                fecha,
                str(mov.pedido_numero or "").strip(),
                str(mov.pedido_albaran_numero or "").strip(),
                f"{cantidad:.2f}",
                f"{kg:.2f} kg",
                str(mov.articulo_lote or "").strip(),
                caduca,
            ]
            for col, value in enumerate(vals):
                item = QTableWidgetItem(value)
                if col in (3, 4):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if is_expiring and col == 6:
                    item.setForeground(QBrush(QColor("#B42318")))
                    item.setBackground(QBrush(QColor("#FEE4E2")))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                self.salidas_table.setItem(i, col, item)
        self._set_salidas_totals(total_unidades, total_kg)

    def _reload_stock_table(self, articulo_id: str) -> None:
        if not hasattr(self, "stock_table"):
            return
        self.stock_table.setRowCount(0)
        articulo_id = str(articulo_id or "").strip()
        if not articulo_id:
            self._set_stock_totals(0.0, 0.0)
            return
        moves, items = self.ireks_service.movement_payload(articulo_id)
        q_from = self.stock_date_from.date()
        q_to = self.stock_date_to.date()
        from_date: date = date(q_from.year(), q_from.month(), q_from.day())
        to_date: date = date(q_to.year(), q_to.month(), q_to.day())
        if from_date > to_date:
            from_date, to_date = to_date, from_date
        filtered_moves = [
            mov
            for mov in moves
            if mov.fecha_pedido is not None and from_date <= mov.fecha_pedido <= to_date
        ]
        peso_total = float(items[0].articulo_envase_peso_total or 0.0) if items else 0.0
        self.stock_table.setRowCount(len(filtered_moves))
        total_unidades = 0.0
        total_kg = 0.0
        today = date.today()
        for i, mov in enumerate(filtered_moves):
            fecha = mov.fecha_pedido.strftime("%d/%m/%Y") if mov.fecha_pedido else ""
            cantidad_signed = float(mov.cantidad or 0.0)
            kg_signed = cantidad_signed * peso_total
            total_unidades += cantidad_signed
            total_kg += kg_signed
            caduca = mov.articulo_caducidad.strftime("%d/%m/%Y") if mov.articulo_caducidad else ""
            is_expiring = bool(mov.articulo_caducidad and (mov.articulo_caducidad - today).days <= 30)
            tipo = "Entrada" if cantidad_signed >= 0 else "Salida"
            vals = [
                fecha,
                tipo,
                str(mov.pedido_numero or "").strip(),
                str(mov.pedido_albaran_numero or "").strip(),
                f"{cantidad_signed:.2f}",
                f"{kg_signed:.2f} kg",
                str(mov.articulo_lote or "").strip(),
                caduca,
            ]
            for col, value in enumerate(vals):
                item = QTableWidgetItem(value)
                if col in (4, 5):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if col in (4, 5) and cantidad_signed < 0:
                    item.setForeground(QBrush(QColor("#B42318")))
                if is_expiring and col == 7:
                    item.setForeground(QBrush(QColor("#B42318")))
                    item.setBackground(QBrush(QColor("#FEE4E2")))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                self.stock_table.setItem(i, col, item)
        self._set_stock_totals(total_unidades, total_kg)

    def _reload_pedidos_table(self, articulo_id: str) -> None:
        if not hasattr(self, "pedidos_table"):
            return
        self.pedidos_table.setRowCount(0)
        articulo_id = str(articulo_id or "").strip()
        if not articulo_id:
            return
        item_rows = self.ireks_service.pedido_items(articulo_id)
        q_from = self.pedidos_date_from.date()
        q_to = self.pedidos_date_to.date()
        from_date: date = date(q_from.year(), q_from.month(), q_from.day())
        to_date: date = date(q_to.year(), q_to.month(), q_to.day())
        if from_date > to_date:
            from_date, to_date = to_date, from_date
        filtered_rows = [
            row
            for row in item_rows
            if row.pedido_item_fecha is not None and from_date <= row.pedido_item_fecha <= to_date
        ]
        self.pedidos_table.setRowCount(len(filtered_rows))
        for i, row in enumerate(filtered_rows):
            values = [
                row.pedido_item_fecha.strftime("%d/%m/%Y") if row.pedido_item_fecha else "",
                str(getattr(row, "pedido_numero", "") or "").strip(),
                str(getattr(row, "pedido_albaran_numero", "") or "").strip(),
                f"{float(getattr(row, 'articulo_cantidad', 0.0) or 0.0):.2f}",
                str(getattr(row, "articulo_lote", "") or "").strip(),
                row.articulo_caducidad.strftime("%d/%m/%Y") if getattr(row, "articulo_caducidad", None) else "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 3:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.pedidos_table.setItem(i, col, item)

    def _reload_monthly_orders_table(self, articulo_id: str) -> None:
        if not hasattr(self, "monthly_orders_table"):
            return
        self.monthly_orders_table.setRowCount(0)
        articulo_id = str(articulo_id or "").strip()
        if not articulo_id:
            return
        q_from = self.monthly_orders_date_from.date()
        q_to = self.monthly_orders_date_to.date()
        from_date: date = date(q_from.year(), q_from.month(), q_from.day())
        to_date: date = date(q_to.year(), q_to.month(), q_to.day())
        if from_date > to_date:
            from_date, to_date = to_date, from_date
        month_names = [
            "Ene",
            "Feb",
            "Mar",
            "Abr",
            "May",
            "Jun",
            "Jul",
            "Ago",
            "Sep",
            "Oct",
            "Nov",
            "Dic",
        ]
        rows = self.monthly_orders_service.product_monthly_rows_for(
            articulo_id=articulo_id,
            almacen_id=self.external_distributor_filter_id,
            date_from=from_date,
            date_to=to_date,
        )
        self.monthly_orders_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            average = row.quantity / row.order_count if row.order_count > 0 else 0.0
            values = [
                f"{month_names[row.month - 1]} {row.year}",
                str(row.order_count),
                f"{row.quantity:.2f}",
                f"{row.kg:.2f} kg",
                f"{average:.2f}",
                row.last_order_date.strftime("%d/%m/%Y") if row.last_order_date else "",
                row.last_order_number,
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col in (1, 2, 3, 4):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if col in (2, 3):
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                self.monthly_orders_table.setItem(i, col, item)

    def _reload_nutricion_table(self, articulo_id: str) -> None:
        if not hasattr(self, "nutricion_table"):
            return
        aid = str(articulo_id or "").strip()
        nutrition = None
        if aid:
            nutrition = self.ireks_service.nutrition(aid)
        self._loading_nutricion = True
        try:
            for row_idx, key in enumerate(getattr(self, "_nutrient_keys", [])):
                value = 0.0
                if nutrition is not None:
                    value = float(getattr(nutrition, key, 0.0) or 0.0)
                item = self.nutricion_table.item(row_idx, 1)
                if item is None:
                    item = QTableWidgetItem()
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    self.nutricion_table.setItem(row_idx, 1, item)
                item.setText(f"{value:.2f}")
        finally:
            self._loading_nutricion = False

    def _on_nutricion_item_changed(self, item: QTableWidgetItem) -> None:
        if self._loading_nutricion or self._loading:
            return
        if item.column() != 1:
            return
        row = self._selected_row()
        articulo_id = str(getattr(row, "articulo_id", "") or "").strip() if row else ""
        if not articulo_id:
            return
        values: dict[str, float] = {}
        for row_idx, key in enumerate(getattr(self, "_nutrient_keys", [])):
            cell = self.nutricion_table.item(row_idx, 1)
            raw = str(cell.text() if cell else "").strip().replace(",", ".")
            try:
                value = float(raw) if raw else 0.0
            except Exception:
                value = 0.0
            values[key] = value
        try:
            self.ireks_service.save_nutrition(articulo_id, values)
        except Exception:
            return
        self._loading_nutricion = True
        try:
            item.setText(f"{values.get(self._nutrient_keys[item.row()], 0.0):.2f}")
        finally:
            self._loading_nutricion = False

    def _reload_tarifas_table(self, articulo_id: str | int | None = None) -> None:
        if not hasattr(self, "tarifa_table") or not hasattr(self, "tarifa_year_filter"):
            return

        # When called by QComboBox.currentIndexChanged, Qt passes the index (int).
        if isinstance(articulo_id, int):
            articulo_id = None

        if articulo_id is None:
            row = self._selected_row()
            if row:
                articulo_id = str(getattr(row, "articulo_id", "") or "").strip()
            else:
                articulo_id = str(self._current_tarifa_articulo_id or "").strip()
        else:
            articulo_id = str(articulo_id or "").strip()
        self._current_tarifa_articulo_id = articulo_id

        self.tarifa_table.setRowCount(0)
        self.tarifa_year_filter.blockSignals(True)
        current_year_filter = str(self.tarifa_year_filter.currentData() or "").strip()
        self.tarifa_year_filter.clear()
        self.tarifa_year_filter.addItem("Todos", "")
        self.tarifa_year_filter.blockSignals(False)

        if not articulo_id:
            return

        rows = self.ireks_service.tarifas(articulo_id)
        years = sorted({int(getattr(item, "tarifa_ano", 0) or 0) for item in rows if int(getattr(item, "tarifa_ano", 0) or 0) > 0}, reverse=True)
        self.tarifa_year_filter.blockSignals(True)
        for year in years:
            self.tarifa_year_filter.addItem(str(year), str(year))
        idx = self.tarifa_year_filter.findData(current_year_filter)
        self.tarifa_year_filter.setCurrentIndex(idx if idx >= 0 else 0)
        self.tarifa_year_filter.blockSignals(False)

        selected_year = str(self.tarifa_year_filter.currentData() or "").strip()
        filtered_rows = rows
        if selected_year:
            filtered_rows = [item for item in rows if str(getattr(item, "tarifa_ano", "") or "") == selected_year]

        previous_price_by_id: dict[int, float] = {}
        previous_distributor_price_by_id: dict[int, float] = {}
        sorted_by_year = sorted(
            rows,
            key=lambda item: (int(getattr(item, "tarifa_ano", 0) or 0), int(getattr(item, "id", 0) or 0)),
        )
        previous_by_year: dict[int, float] = {}
        previous_distributor_by_year: dict[int, float] = {}
        for item in sorted_by_year:
            tarifa_id = int(getattr(item, "id", 0) or 0)
            year = int(getattr(item, "tarifa_ano", 0) or 0)
            previous_years = [known_year for known_year in previous_by_year if known_year < year]
            if previous_years:
                previous_year = max(previous_years)
                previous_price_by_id[tarifa_id] = previous_by_year[previous_year]
                previous_distributor_price_by_id[tarifa_id] = previous_distributor_by_year.get(previous_year, 0.0)
            previous_by_year[year] = float(getattr(item, "precio_fabricante", 0.0) or 0.0)
            previous_distributor_by_year[year] = float(getattr(item, "precio_distribuidor", 0.0) or 0.0)

        selected_row = self._selected_row()
        total_kg = 0.0
        if selected_row:
            total_kg = float(getattr(selected_row, "articulo_envase_peso_total", 0.0) or 0.0)
            if total_kg <= 0:
                cantidad = float(getattr(selected_row, "articulo_envase_cantidad", 0.0) or 0.0)
                peso = float(getattr(selected_row, "articulo_envase_peso", 0.0) or 0.0)
                total_kg = cantidad * peso

        self.tarifa_table.setRowCount(len(filtered_rows))
        for row_idx, item in enumerate(filtered_rows):
            year_item = QTableWidgetItem(str(int(getattr(item, "tarifa_ano", 0) or 0)))
            tarifa_id = int(getattr(item, "id", 0) or 0)
            pf = float(getattr(item, "precio_fabricante", 0.0) or 0.0)
            pd = float(getattr(item, "precio_distribuidor", 0.0) or 0.0)
            dto = float(getattr(item, "descuento_pct", 0.0) or 0.0)
            costo = pf * max(0.0, 1.0 - (dto / 100.0))
            margen = ((pd - costo) / pd * 100.0) if pd > 0 else 0.0
            previous_pf = previous_price_by_id.get(tarifa_id, 0.0)
            delta = ((pf - previous_pf) / previous_pf * 100.0) if previous_pf > 0 else 0.0
            previous_pd = previous_distributor_price_by_id.get(tarifa_id, 0.0)
            delta_distribuidor = ((pd - previous_pd) / previous_pd * 100.0) if previous_pd > 0 else 0.0
            pf_kg = (pf / total_kg) if total_kg > 0 else 0.0
            pd_kg = (pd / total_kg) if total_kg > 0 else 0.0
            pf_item = QTableWidgetItem(f"{pf:.2f} €")
            pf_kg_item = QTableWidgetItem(f"{pf_kg:.2f} €")
            delta_item = QTableWidgetItem(f"{delta:.2f} %" if previous_pf > 0 else "")
            dto_item = QTableWidgetItem(f"{dto:.2f} %")
            costo_item = QTableWidgetItem(f"{costo:.2f} €")
            pd_item = QTableWidgetItem(f"{pd:.2f} €")
            pd_kg_item = QTableWidgetItem(f"{pd_kg:.2f} €")
            delta_distribuidor_item = QTableWidgetItem(f"{delta_distribuidor:.2f} %" if previous_pd > 0 else "")
            margen_item = QTableWidgetItem(f"{margen:.2f} %")
            year_item.setData(Qt.ItemDataRole.UserRole, tarifa_id)
            year_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            pf_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            pf_kg_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            delta_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            dto_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            costo_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            pd_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            pd_kg_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            delta_distribuidor_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            margen_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tarifa_table.setItem(row_idx, 0, year_item)
            self.tarifa_table.setItem(row_idx, 1, pf_item)
            self.tarifa_table.setItem(row_idx, 2, pf_kg_item)
            self.tarifa_table.setItem(row_idx, 3, delta_item)
            self.tarifa_table.setItem(row_idx, 4, dto_item)
            self.tarifa_table.setItem(row_idx, 5, costo_item)
            self.tarifa_table.setItem(row_idx, 6, pd_item)
            self.tarifa_table.setItem(row_idx, 7, pd_kg_item)
            self.tarifa_table.setItem(row_idx, 8, delta_distribuidor_item)
            self.tarifa_table.setItem(row_idx, 9, margen_item)

    def _selected_tarifa_id(self) -> int:
        selected = self.tarifa_table.selectionModel().selectedRows() if self.tarifa_table.selectionModel() else []
        if not selected:
            return 0
        row_idx = selected[0].row()
        item = self.tarifa_table.item(row_idx, 0)
        return int(item.data(Qt.ItemDataRole.UserRole) or 0) if item is not None else 0

    def _selected_tarifa_total_kg(self) -> float:
        row = self._selected_row()
        if not row:
            return 0.0
        total_kg = float(getattr(row, "articulo_envase_peso_total", 0.0) or 0.0)
        if total_kg <= 0:
            cantidad = float(getattr(row, "articulo_envase_cantidad", 0.0) or 0.0)
            peso = float(getattr(row, "articulo_envase_peso", 0.0) or 0.0)
            total_kg = cantidad * peso
        return total_kg

    def _add_tarifa_row(self) -> None:
        row = self._selected_row()
        articulo_id = str(getattr(row, "articulo_id", "") or "").strip() if row else ""
        if not articulo_id:
            QMessageBox.warning(self, "Tarifa", "Selecciona un producto IREKS.")
            return
        dialog = AddTarifaIreksDialog(self._selected_tarifa_total_kg(), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        tarifa_ano, precio_ireks, precio_distribuidor, descuento_pct = dialog.payload()
        self.ireks_service.upsert_tarifa(
            articulo_id=articulo_id,
            tarifa_ano=tarifa_ano,
            precio_fabricante=precio_ireks,
            precio_distribuidor=precio_distribuidor,
            descuento_pct=descuento_pct,
        )
        self._reload_tarifas_table(articulo_id)

    def _edit_tarifa_row(self) -> None:
        tarifa_id = self._selected_tarifa_id()
        if not tarifa_id:
            QMessageBox.warning(self, "Tarifa", "Selecciona una tarifa.")
            return
        row = self._selected_row()
        articulo_id = str(getattr(row, "articulo_id", "") or "").strip() if row else ""
        tarifa = self.ireks_service.get_tarifa(tarifa_id)
        if tarifa is None:
            QMessageBox.warning(self, "Tarifa", "Tarifa no encontrada.")
            return
        initial = {
            "tarifa_ano": int(getattr(tarifa, "tarifa_ano", 0) or 0),
            "precio_fabricante": float(getattr(tarifa, "precio_fabricante", 0.0) or 0.0),
            "precio_distribuidor": float(getattr(tarifa, "precio_distribuidor", 0.0) or 0.0),
            "descuento_pct": float(getattr(tarifa, "descuento_pct", 0.0) or 0.0),
        }
        dialog = AddTarifaIreksDialog(self._selected_tarifa_total_kg(), self, initial=initial, title="Editar tarifa")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        tarifa_ano, precio_ireks, precio_distribuidor, descuento_pct = dialog.payload()
        if not self.ireks_service.update_tarifa(
            tarifa_id=tarifa_id,
            tarifa_ano=tarifa_ano,
            precio_fabricante=precio_ireks,
            precio_distribuidor=precio_distribuidor,
            descuento_pct=descuento_pct,
        ):
            QMessageBox.warning(self, "Tarifa", "Tarifa no encontrada.")
            return
        self._reload_tarifas_table(articulo_id)

    def _delete_tarifa_row(self) -> None:
        tarifa_id = self._selected_tarifa_id()
        if not tarifa_id:
            QMessageBox.warning(self, "Tarifa", "Selecciona una tarifa.")
            return
        answer = QMessageBox.question(self, "Eliminar tarifa", "Eliminar la tarifa seleccionada?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        row = self._selected_row()
        articulo_id = str(getattr(row, "articulo_id", "") or "").strip() if row else ""
        self.ireks_service.delete_tarifa(tarifa_id)
        self._reload_tarifas_table(articulo_id)

    def _adjust_tarifa_table_width(self) -> None:
        if not hasattr(self, "tarifa_table"):
            return
        table = self.tarifa_table
        header_table = getattr(self, "tarifa_header_table", None)
        if header_table is not None:
            for idx in range(table.columnCount()):
                header_table.setColumnWidth(idx, table.columnWidth(idx))
            header_table.setRowHeight(0, 34)
            header_table.setRowHeight(1, 28)
        total_cols = sum(table.columnWidth(idx) for idx in range(table.columnCount()))
        total_width = total_cols + (2 * table.frameWidth()) + 2
        table.setMinimumWidth(total_width)
        table.setMaximumWidth(total_width)
        if header_table is not None:
            header_table.setMinimumWidth(total_width)
            header_table.setMaximumWidth(total_width)

    def _autosave_selected(self) -> None:
        row = self._selected_row()
        if not row:
            return
        payload = {
            "articulo_referencia_corta": self.detail_ref_corta.text().strip(),
            "articulo_descripcion": self.detail_descripcion.text().strip(),
            "articulo_referencia": self.detail_referencia.text().strip(),
            "fabricante_id": self._current_filter_value(self.detail_fabricante_id),
            "articulo_familia_id": self._current_filter_value(self.detail_familia_id),
            "articulo_subfamilia_id": self._current_filter_value(self.detail_subfamilia_id),
            "distribuidor_id": self._current_filter_value(self.detail_distribuidor_id),
            "articulo_envase_id": str(self.detail_envase_id.currentData() or "").strip(),
            "articulo_contenido_unidad": self.detail_contenido_unidad.currentText().strip(),
            "articulo_envase_cantidad": self._to_float_text(self.detail_envase_cantidad.text()),
            "articulo_envase_peso": self._to_float_text(self.detail_envase_peso.text()),
            "articulo_envase_unidad_medida": self.detail_envase_unidad.currentText().strip(),
            "transporte_pallet_tipo": self.transporte_pallet_tipo.currentText().strip(),
            "transporte_cajas_por_capa": self._to_float_text(self.transporte_cajas_por_capa.text()),
            "transporte_capas_por_pallet": self._to_float_text(self.transporte_capas_por_pallet.text()),
            "transporte_observaciones": self.transporte_observaciones.text().strip(),
            "articulo_status_activo": bool(self.detail_status_activo_si.isChecked()),
            "articulo_status_en_lista": bool(self.detail_status_en_lista_si.isChecked()),
            "categoria": self._selected_ireks_category(),
        }
        try:
            row_id = row.id
            if row_id is None:
                return
            self.ireks_service.update_product(int(row_id), payload)
            row.articulo_referencia_corta = str(payload["articulo_referencia_corta"] or "")
            row.articulo_descripcion = str(payload["articulo_descripcion"] or "")
            row.articulo_referencia = str(payload["articulo_referencia"] or "")
            row.fabricante_id = str(payload["fabricante_id"] or "")
            row.articulo_familia_id = str(payload["articulo_familia_id"] or "")
            row.articulo_subfamilia_id = str(payload["articulo_subfamilia_id"] or "")
            row.distribuidor_id = str(payload["distribuidor_id"] or "")
            row.articulo_envase_id = str(payload["articulo_envase_id"] or "")
            row.articulo_contenido_unidad = str(payload["articulo_contenido_unidad"] or "")
            row.articulo_envase_cantidad = float(payload["articulo_envase_cantidad"] or 0.0)
            row.articulo_envase_peso = float(payload["articulo_envase_peso"] or 0.0)
            row.articulo_envase_unidad_medida = str(payload["articulo_envase_unidad_medida"] or "")
            row.transporte_pallet_tipo = str(payload["transporte_pallet_tipo"] or "")
            row.transporte_cajas_por_capa = float(payload["transporte_cajas_por_capa"] or 0.0)
            row.transporte_capas_por_pallet = float(payload["transporte_capas_por_pallet"] or 0.0)
            row.transporte_cajas_por_pallet = row.transporte_cajas_por_capa * row.transporte_capas_por_pallet
            row.transporte_unidades_por_pallet = row.transporte_cajas_por_pallet * row.articulo_envase_cantidad
            row.transporte_kg_por_pallet = row.transporte_unidades_por_pallet * row.articulo_envase_peso
            row.transporte_observaciones = str(payload["transporte_observaciones"] or "")
            row.articulo_status_activo = bool(payload["articulo_status_activo"])
            row.articulo_status_en_lista = bool(payload["articulo_status_en_lista"])
            row.categoria = str(payload["categoria"] or "")
            ref_key_articulo_id = str(row.articulo_id or "").strip()
            ref_key_distribuidor_id = str(payload["distribuidor_id"] or "").strip()
            self.ireks_service.upsert_distributor_reference(
                articulo_id=ref_key_articulo_id,
                distribuidor_id=ref_key_distribuidor_id,
                referencia=self.detail_referencia_distribuidor.text(),
                descripcion=self.detail_descripcion_distribuidor.text(),
            )
            self._update_envase_total_preview()
            selected = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
            if selected:
                i = selected[0].row()
                item_ref = self.table.item(i, 0)
                item_name = self.table.item(i, 1)
                if item_ref:
                    item_ref.setText(payload["articulo_referencia_corta"])
                if item_name:
                    item_name.setText(payload["articulo_descripcion"])
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Productos IREKS", f"No se pudo guardar.\n{exc}")

    def _selected_ireks_category(self) -> str:
        if self.detail_categoria_harina.isChecked():
            return "harina"
        if self.detail_categoria_liquido.isChecked():
            return "liquido"
        return ""

    def _set_ireks_category(self, value: str) -> None:
        category = (value or "").strip().lower()
        prev_harina = self.detail_categoria_harina.blockSignals(True)
        prev_liquido = self.detail_categoria_liquido.blockSignals(True)
        self.detail_categoria_group.setExclusive(False)
        self.detail_categoria_harina.setChecked(False)
        self.detail_categoria_liquido.setChecked(False)
        if category == "harina":
            self.detail_categoria_harina.setChecked(True)
        elif category == "liquido":
            self.detail_categoria_liquido.setChecked(True)
        self.detail_categoria_group.setExclusive(True)
        self.detail_categoria_harina.blockSignals(prev_harina)
        self.detail_categoria_liquido.blockSignals(prev_liquido)

    def _generate_product_report(self) -> None:
        prompt = self.product_report_prompt.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "Listados", "Escribe que listado necesitas.")
            return
        self.product_report_status_label.setText("Generando listado...")
        QApplication.processEvents()
        result = self.product_report_flow_service.generate_report(
            prompt,
            selected_product_ids=self._selected_product_ids,
        )
        if result.status == "empty_prompt":
            QMessageBox.warning(self, "Listados", result.message)
            return
        if result.status == "parse_error":
            QMessageBox.warning(self, "Listados", result.message)
            return
        if result.status == "no_selection":
            QMessageBox.warning(self, "Listados", result.message)
            self.product_report_status_label.setText("Sin listado generado.")
            return
        if result.status == "error":
            QMessageBox.warning(self, "Listados", result.message)
            return
        if result.status != "ready" or result.report is None:
            QMessageBox.warning(self, "Listados", "No se pudo generar el listado.")
            return
        report = result.report
        self._last_product_report = report
        self._render_product_report(report)
        source = "ChatGPT" if result.used_ai else "interprete local"
        self.product_report_status_label.setText(f"{report.title} · {len(report.rows)} fila(s) · {source}")
        self.product_report_status_label.setToolTip(result.message or "")

    def _render_product_report(self, report: ProductReportResult) -> None:
        self.product_report_table.clear()
        self.product_report_table.setColumnCount(len(report.headers))
        self.product_report_table.setHorizontalHeaderLabels(report.headers)
        self.product_report_table.setRowCount(len(report.rows))
        for row_idx, row in enumerate(report.rows):
            for col_idx, value in enumerate(row):
                self.product_report_table.setItem(row_idx, col_idx, QTableWidgetItem(str(value)))
        self.product_report_table.resizeColumnsToContents()
        if report.headers:
            self.product_report_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        for col_idx in range(1, len(report.headers)):
            self.product_report_table.horizontalHeader().setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Stretch)
        self._set_product_report_actions_enabled(bool(report.rows))

    def _export_product_report_excel(self) -> None:
        report = self._last_product_report
        if report is None:
            QMessageBox.warning(self, "Listados", "Genera primero un listado.")
            return
        default = str(self.report_export_service.default_path(report.title, "xlsx", "listados_productos_ireks"))
        path, _ = QFileDialog.getSaveFileName(self, "Exportar listado a Excel", default, "Excel (*.xlsx)")
        if not path:
            return
        out = self.report_export_service.export_excel(path, report.title, report.headers, report.rows, "Listado productos")
        QMessageBox.information(self, "Listados", f"Excel exportado:\n{out}")

    def _export_product_report_pdf(self) -> None:
        report = self._last_product_report
        if report is None:
            QMessageBox.warning(self, "Listados", "Genera primero un listado.")
            return
        default = str(self.report_export_service.default_path(report.title, "pdf", "listados_productos_ireks"))
        path, _ = QFileDialog.getSaveFileName(self, "Exportar listado a PDF", default, "PDF (*.pdf)")
        if not path:
            return
        out = self.report_export_service.export_pdf(path, report.title, report.headers, report.rows)
        QMessageBox.information(self, "Listados", f"PDF exportado:\n{out}")

    def _print_product_report(self) -> None:
        report = self._last_product_report
        if report is None:
            QMessageBox.warning(self, "Listados", "Genera primero un listado.")
            return
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageOrientation(QPrinter.Orientation.Landscape)
        dialog = QPrintDialog(printer, self)
        if dialog.exec() != QPrintDialog.DialogCode.Accepted:
            return
        document = QTextDocument()
        document.setHtml(self._product_report_to_html(report))
        document.print_(printer)

    def _product_report_to_html(self, report: ProductReportResult) -> str:
        def esc(value: object) -> str:
            return (
                str(value)
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
            )

        header_html = "".join(f"<th>{esc(header)}</th>" for header in report.headers)
        rows_html = ""
        for row in report.rows:
            rows_html += "<tr>" + "".join(f"<td>{esc(value)}</td>" for value in row) + "</tr>"
        return f"""
        <html>
        <body>
        <h2>{esc(report.title)}</h2>
        <table border="1" cellspacing="0" cellpadding="4" width="100%">
        <thead><tr>{header_html}</tr></thead>
        <tbody>{rows_html}</tbody>
        </table>
        </body>
        </html>
        """

    def _new_product(self) -> None:
        try:
            row_id = self.ireks_service.create_product()
            self.reload()
            self._select_by_id(row_id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Productos IREKS", f"No se pudo crear.\n{exc}")

    def _delete_product(self) -> None:
        row = self._selected_row()
        if not row:
            QMessageBox.warning(self, "Productos IREKS", "Selecciona un producto.")
            return
        if QMessageBox.question(self, "Eliminar", "Eliminar producto seleccionado?") != QMessageBox.StandardButton.Yes:
            return
        row_id = row.id
        if row_id is None:
            return
        self.ireks_service.delete_product(int(row_id))
        self.reload()

    def _import_products(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar archivo",
            "",
            "Archivos de datos (*.xlsx *.xlsm *.csv)",
        )
        if not file_path:
            return
        result = self.ingredient_products_import_flow_service.import_products(file_path)
        self.reload()
        if result.errors:
            QMessageBox.warning(
                self,
                "Importacion completada con incidencias",
                f"Registros importados: {result.imported}\nErrores: {len(result.errors)}\n\n{result.preview}",
            )
            return
        QMessageBox.information(self, "Importacion completada", f"Registros importados: {result.imported}")

    def _show_product_id_dialog(self) -> None:
        row = self._selected_row()
        if not row:
            QMessageBox.warning(self, "Productos IREKS", "Selecciona un producto.")
            return
        product_id = str(row.articulo_id or "").strip()
        if not product_id:
            QMessageBox.warning(self, "Productos IREKS", "El producto no tiene ID.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("ID del producto")
        dialog.setModal(True)
        layout = QVBoxLayout(dialog)

        label = QLabel("ID del producto")
        id_field = QLineEdit(product_id)
        id_field.setReadOnly(True)
        id_field.setCursorPosition(0)
        id_field.setSelection(0, 0)

        buttons = QHBoxLayout()
        copy_btn = QPushButton("Copiar")
        close_btn = QPushButton("Cerrar")
        copy_btn.setProperty("btnRole", "secondary")
        close_btn.setProperty("btnRole", "secondary")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(product_id))
        close_btn.clicked.connect(dialog.accept)
        buttons.addWidget(copy_btn)
        buttons.addStretch(1)
        buttons.addWidget(close_btn)

        layout.addWidget(label)
        layout.addWidget(id_field)
        layout.addLayout(buttons)
        dialog.resize(460, 130)
        dialog.exec()


class IngredientStdArticleDialog(QDialog):
    FORMATOS = ["", "saco", "bolsa", "caja", "botella", "garrafa", "bidon", "lata", "paquete", "bote"]
    UNIDADES = ["g", "kg", "l", "ml", "unidad"]
    NUTRIENT_FIELDS = [
        ("energia_kj", "Energia (kJ)"),
        ("energia_kcal", "Energia (kcal)"),
        ("grasas_g", "Grasas (g)"),
        ("saturadas_g", "Saturadas (g)"),
        ("hidratos_g", "Hidratos (g)"),
        ("azucares_g", "Azucares (g)"),
        ("fibra_g", "Fibra (g)"),
        ("proteinas_g", "Proteinas (g)"),
        ("sal_g", "Sal (g)"),
    ]
    DAILY_REFERENCE = {
        "energia_kcal": 2000.0,
        "grasas_g": 70.0,
        "saturadas_g": 20.0,
        "hidratos_g": 260.0,
        "azucares_g": 90.0,
        "proteinas_g": 50.0,
        "sal_g": 6.0,
    }
    NUTRIENT_UNITS = {
        "energia_kj": "kJ",
        "energia_kcal": "kcal",
        "grasas_g": "g",
        "saturadas_g": "g",
        "hidratos_g": "g",
        "azucares_g": "g",
        "fibra_g": "g",
        "proteinas_g": "g",
        "sal_g": "g",
    }

    def __init__(self, title: str, initial: dict[str, Any] | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.initial = initial or {}
        self.articulo_id = str(self.initial.get("articulo_id") or "").strip()
        self.distributors: list[Proveedor] = []
        self.std_service = IngredientStdService(IngredientStdViewModel())
        self._load_catalogs()
        self._build_ui()
        self._apply_initial()

    def _load_catalogs(self) -> None:
        self.distributors = self.std_service.providers()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        main_panel = QGroupBox("Datos generales")
        main_panel.setFixedWidth(660)
        main_panel.setFixedHeight(218)
        main_panel_layout = QVBoxLayout(main_panel)
        main_panel_layout.setContentsMargins(8, 4, 8, 4)
        form_canvas = QWidget(main_panel)
        form_canvas.setFixedHeight(182)
        form_canvas.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        form_canvas.setStyleSheet("background-color: transparent; border: none;")

        self.reference_input = QLineEdit()
        self.name_input = QLineEdit()
        self.distributor_combo = QComboBox()
        self.distributor_combo.addItem("", "")
        for row in self.distributors:
            label = str(row.distribuidor_nombre_comercial or "").strip() or str(row.distribuidor_razon_social or "").strip()
            self.distributor_combo.addItem(label or str(row.distribuidor_id or ""), str(row.distribuidor_id or ""))

        self.category_combo = QComboBox()
        self.category_combo.addItems(["", "harina", "liquido"])

        self.format_combo = self._editable_combo(self.FORMATOS)
        self.format_qty_input = QLineEdit()
        self.format_qty_input.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.format_unit_combo = QComboBox()
        self.format_unit_combo.addItems(self.UNIDADES)
        self.pvp_format_input = QLineEdit()
        self.pvp_format_input.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.pvp_unit_input = QLineEdit()
        self.pvp_unit_input.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.pvp_unit_input.setReadOnly(True)
        self.price_date_input = QDateEdit()
        self.price_date_input.setCalendarPopup(True)
        self.price_date_input.setDate(QDate.currentDate())
        field_style = (
            "QLineEdit, QComboBox, QDateEdit {"
            " border: 1px solid #AEB9C8;"
            " border-radius: 6px;"
            " background: #FFFFFF;"
            " padding: 2px 8px;"
            " min-height: 26px;"
            "}"
        )
        for w in (
            self.reference_input,
            self.name_input,
            self.distributor_combo,
            self.category_combo,
            self.format_combo,
            self.format_qty_input,
            self.format_unit_combo,
            self.pvp_format_input,
            self.pvp_unit_input,
            self.price_date_input,
        ):
            w.setStyleSheet(field_style)
        for w in (self.reference_input, self.category_combo, self.format_combo, self.pvp_format_input):
            w.setFixedWidth(140)

        self.category_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.category_combo.setMinimumWidth(0)

        # Layout fijo por coordenadas (x, y, w, h)
        self._place_labeled_field(form_canvas, "Referencia", self.reference_input, 10, 10, 270, gap=2)
        self._place_labeled_field(form_canvas, "Nombre", self.name_input, 250, 10, 370, gap=2)

        self._place_labeled_field(form_canvas, "Categoria", self.category_combo, 10, 54, 270, gap=2)
        self._place_labeled_field(form_canvas, "Distribuidor", self.distributor_combo, 250, 54, 370, gap=2)

        self._place_labeled_field(form_canvas, "Formato", self.format_combo, 10, 100, 270, gap=2)
        self._place_labeled_field(form_canvas, "Cantidad", self.format_qty_input, 250, 100, 20, gap=2)
        self._place_labeled_field(form_canvas, "Unidad", self.format_unit_combo, 454, 100, 20, gap=0)

        self._place_labeled_field(form_canvas, "PVP", self.pvp_format_input, 10, 150, 20, gap=2, label_w=40)
        self._place_labeled_field(form_canvas, "PVP Unitario", self.pvp_unit_input, 220, 150, 20, gap=2)
        self._place_labeled_field(form_canvas, "Fecha precio", self.price_date_input, 423, 150, 200, gap=2)

        self.pvp_format_input.textChanged.connect(self._recalculate_unit_price)
        self.format_qty_input.textChanged.connect(self._recalculate_unit_price)
        self.format_unit_combo.currentIndexChanged.connect(self._recalculate_unit_price)
        self.format_unit_combo.currentIndexChanged.connect(lambda *_: self._load_price_history())
        self.format_unit_combo.currentTextChanged.connect(lambda *_: self._load_price_history())

        main_panel_layout.addWidget(form_canvas)
        layout.addWidget(main_panel)

        section_row = QHBoxLayout()
        section_row.setSpacing(6)
        section_row.setContentsMargins(0, 0, 0, 0)
        history_panel = QGroupBox("Historico de precios")
        history_panel.setFixedWidth(255)
        history_panel.setFixedHeight(360)
        nutrition_panel = QGroupBox("Valores nutricionales")
        nutrition_panel.setFixedWidth(400)
        nutrition_panel.setFixedHeight(360)
        left_box = QVBoxLayout(history_panel)
        right_box = QVBoxLayout(nutrition_panel)
        left_box.setContentsMargins(8, 6, 8, 8)
        right_box.setContentsMargins(8, 0, 8, 8)
        left_box.setSpacing(6)
        right_box.setSpacing(4)
        right_box.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.price_history_table = QTableWidget(0, 2)
        self.price_history_table.setHorizontalHeaderLabels(["Fecha", "PVP"])
        self.price_history_table.verticalHeader().setVisible(False)
        self.price_history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.price_history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.price_history_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.price_history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.price_history_table.setColumnWidth(0, 95)
        self.price_history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.price_history_table.setColumnWidth(1, 110)
        header_w = self.price_history_table.verticalHeader().width()
        frame_w = self.price_history_table.frameWidth() * 2
        table_w = self.price_history_table.columnWidth(0) + self.price_history_table.columnWidth(1) + header_w + frame_w
        self.price_history_table.setFixedWidth(table_w)
        self.price_history_table.setMaximumHeight(240)
        left_box.addWidget(self.price_history_table)
        history_actions = QHBoxLayout()
        self.add_price_btn = QPushButton("Registrar")
        self.add_price_btn.setProperty("btnRole", "secondary")
        self.add_price_btn.clicked.connect(self._register_price_for_selected_date)
        self.delete_price_btn = QPushButton("Eliminar")
        self.delete_price_btn.setProperty("btnRole", "danger")
        self.delete_price_btn.clicked.connect(self._delete_selected_price_row)
        self.add_price_btn.setFixedWidth(95)
        self.delete_price_btn.setFixedWidth(95)
        history_actions.addWidget(self.add_price_btn)
        history_actions.addWidget(self.delete_price_btn)
        left_box.addLayout(history_actions)

        portion_header = QHBoxLayout()
        portion_header.setContentsMargins(0, 0, 0, 0)
        portion_header.setSpacing(4)
        portion_header.addWidget(QLabel("Tamaño de la porción"))
        self.portion_size_label = QLabel("100 g")
        self.portion_size_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        portion_header.addWidget(self.portion_size_label, 1)
        right_box.addLayout(portion_header)

        self.nutrition_table = QTableWidget(len(self.NUTRIENT_FIELDS), 3)
        self.nutrition_table.setHorizontalHeaderLabels(["Campo", "Por porción", "% IR*"])
        self.nutrition_table.verticalHeader().setVisible(False)
        self.nutrition_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.nutrition_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.nutrition_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.nutrition_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.nutrition_table.setColumnWidth(1, 98)
        self.nutrition_table.setColumnWidth(2, 62)
        self.nutrition_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nutrition_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nutrition_table.setMinimumWidth(360)
        self.nutrition_table.setStyleSheet(
            "QTableWidget {"
            " font-size: 12px;"
            " border: 1px solid #D5DDEA;"
            " border-radius: 6px;"
            " gridline-color: #D5DDEA;"
            " background: #FFFFFF;"
            "}"
            "QHeaderView::section {"
            " font-size: 11px;"
            " font-weight: 600;"
            " padding: 2px 6px;"
            " min-height: 18px;"
            " background: #E9EDF4;"
            " border: 1px solid #D5DDEA;"
            "}"
            "QTableWidget::item {"
            " padding: 1px 6px;"
            " border: 1px solid #E2E7EF;"
            "}"
        )
        self.nutrition_table.horizontalHeader().setFixedHeight(20)
        self.nutrition_table.verticalHeader().setDefaultSectionSize(20)
        self.nutrition_table.verticalHeader().setMinimumSectionSize(20)
        for i, (_key, label) in enumerate(self.NUTRIENT_FIELDS):
            item_key = QTableWidgetItem(label)
            item_key.setFlags(item_key.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.nutrition_table.setItem(i, 0, item_key)
            value_item = QTableWidgetItem("")
            value_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.nutrition_table.setItem(i, 1, value_item)
            ir_item = QTableWidgetItem("")
            ir_item.setFlags(ir_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            ir_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.nutrition_table.setItem(i, 2, ir_item)
        nutrition_table_height = self.nutrition_table.horizontalHeader().height() + (
            self.nutrition_table.verticalHeader().defaultSectionSize() * self.nutrition_table.rowCount()
        ) + 4
        self.nutrition_table.setFixedHeight(nutrition_table_height)
        right_box.addWidget(self.nutrition_table)
        nutrition_actions = QHBoxLayout()
        nutrition_actions.addStretch(1)
        self.load_chatgpt_btn = QPushButton("Cargar ChatGPT")
        self.load_chatgpt_btn.setProperty("btnRole", "secondary")
        self.load_chatgpt_btn.clicked.connect(self._load_nutrition_from_chatgpt)
        self.load_fatsecret_btn = QPushButton("Cargar FatSecret")
        self.load_fatsecret_btn.setProperty("btnRole", "secondary")
        self.load_fatsecret_btn.clicked.connect(self._load_nutrition_from_fatsecret)
        self.load_fdc_btn = QPushButton("Cargar FDC")
        self.load_fdc_btn.setProperty("btnRole", "secondary")
        self.load_fdc_btn.clicked.connect(self._load_nutrition_from_fdc)
        nutrition_actions.addWidget(self.load_chatgpt_btn)
        nutrition_actions.addWidget(self.load_fatsecret_btn)
        nutrition_actions.addWidget(self.load_fdc_btn)
        right_box.addLayout(nutrition_actions)

        section_row.addWidget(history_panel, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        section_row.addWidget(nutrition_panel, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        section_row.addStretch(1)
        layout.addLayout(section_row)
        self._load_price_history()
        self._load_nutrition_values()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        save_btn = buttons.button(QDialogButtonBox.StandardButton.Save)
        if save_btn is not None:
            save_btn.setText("Guardar")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setFixedSize(700, 660)

    def _editable_combo(self, values: list[str]) -> QComboBox:
        combo = QComboBox()
        combo.setEditable(True)
        combo.addItems(values)
        return combo

    def _place_labeled_field(
        self,
        parent: QWidget,
        label_text: str,
        field: QWidget,
        x: int,
        y: int,
        total_w: int,
        gap: int = 5,
        label_w: int = 85,
    ) -> None:
        field_w = max(80, total_w - label_w - gap)
        h = 30
        label = QLabel(label_text, parent)
        label.setGeometry(x, y, label_w, h)
        field.setParent(parent)
        field.setGeometry(x + label_w + gap, y, field_w, h)

    def _apply_initial(self) -> None:
        self.reference_input.setText(str(self.initial.get("articulo_referencia_distribuidor") or ""))
        self.name_input.setText(str(self.initial.get("articulo_descripcion") or ""))
        self._set_combo_data(self.distributor_combo, str(self.initial.get("distribuidor_id") or ""))
        self.category_combo.setCurrentText(str(self.initial.get("categoria") or ""))
        self.format_combo.setCurrentText(str(self.initial.get("formato") or ""))
        self.format_qty_input.setText(self._float_text(self.initial.get("formato_cantidad")))
        self.format_unit_combo.setCurrentText(str(self.initial.get("formato_unidad") or "kg"))
        self.pvp_format_input.setText(self._float_text(self.initial.get("pvp_formato")))
        self.pvp_unit_input.setText(self._float_text(self.initial.get("pvp_unidad_medida")))
        self._recalculate_unit_price()

    def _set_combo_data(self, combo: QComboBox, value: str) -> None:
        idx = combo.findData(value)
        combo.setCurrentIndex(idx if idx >= 0 else 0)

    def _load_price_history(self) -> None:
        if not self.articulo_id:
            self.price_history_table.setRowCount(0)
            return
        rows = self.std_service.price_history(self.articulo_id)
        self.price_history_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            fecha_txt = str(getattr(row, "fecha_precio", "") or "")
            precio_txt = self._float_text(getattr(row, "costo_neto", 0.0))
            fecha_item = QTableWidgetItem(fecha_txt)
            fecha_item.setData(Qt.ItemDataRole.UserRole, int(getattr(row, "id", 0) or 0))
            unidad = (self.format_unit_combo.currentText() or "").strip() or "ud"
            precio_item = QTableWidgetItem(f"{precio_txt} €/ {unidad}" if precio_txt else "")
            precio_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.price_history_table.setItem(i, 0, fecha_item)
            self.price_history_table.setItem(i, 1, precio_item)

    def _load_nutrition_values(self) -> None:
        if not self.articulo_id:
            return
        row = self.std_service.nutrition(self.articulo_id)
        if row is None:
            return
        values = {key: float(getattr(row, key, 0.0) or 0.0) for key, _label in self.NUTRIENT_FIELDS}
        self._apply_nutrition_values(values)

    def _load_nutrition_from_fdc(self) -> None:
        query = (
            self.name_input.text().strip()
            or self.reference_input.text().strip()
            or str(self.articulo_id or "").strip()
        )
        query_result = self.fdc_nutrition_flow_service.build_query_options(query)
        if query_result.status == "no_query":
            return
        chosen_query = self._choose_fdc_query(query_result.query_options)
        if not chosen_query:
            return
        candidates_result = self.fdc_nutrition_flow_service.fetch_candidates(chosen_query, limit=10)
        if candidates_result.status == "error":
            QMessageBox.warning(self, "FoodData Central", candidates_result.message)
            return
        if candidates_result.status == "no_results":
            QMessageBox.information(self, "FoodData Central", candidates_result.message)
            return
        labels = candidates_result.labels
        selected_label, ok = QInputDialog.getItem(
            self,
            "Seleccionar alimento FDC",
            "Coincidencias encontradas:",
            labels,
            0,
            False,
        )
        if not ok or not selected_label:
            return
        selected = self.fdc_nutrition_flow_service.resolve_selected_candidate(candidates_result, selected_label)
        if selected.selected_candidate is None:
            return
        self._apply_nutrition_values(selected.selected_candidate.values)
        QMessageBox.information(self, "FoodData Central", "Valores nutricionales cargados desde FDC.")

    def _load_nutrition_from_fatsecret(self) -> None:
        mode, ok = QInputDialog.getItem(
            self,
            "FatSecret",
            "Modo de búsqueda:",
            ["Buscar por texto", "Buscar por código de barras"],
            0,
            False,
        )
        if not ok or not mode:
            return

        try:
            if str(mode).startswith("Buscar por código"):
                barcode, ok_barcode = QInputDialog.getText(
                    self,
                    "FatSecret barcode",
                    "Código de barras (GTIN):",
                )
                barcode = str(barcode or "").strip()
                if not ok_barcode or not barcode:
                    return
                barcode_result = self.fatsecret_nutrition_flow_service.load_barcode(barcode, region="ES")
                if barcode_result.status == "barcode_cancelled":
                    return
                if barcode_result.status == "search_error":
                    QMessageBox.warning(self, "FatSecret", barcode_result.message)
                    return
                if barcode_result.status == "no_servings":
                    QMessageBox.information(self, "FatSecret", barcode_result.message)
                    return
                if barcode_result.status == "ready_to_apply" and barcode_result.values:
                    values = barcode_result.values
                elif barcode_result.status == "servings_available":
                    servings = list(barcode_result.servings or [])
                    if not servings:
                        QMessageBox.information(self, "FatSecret", "El alimento no tiene raciones con datos nutricionales.")
                        return
                    serving = servings[0]
                    if len(servings) > 1:
                        chosen, ok_serving = QInputDialog.getItem(
                            self,
                            "Seleccionar ración",
                            "Raciones disponibles:",
                            barcode_result.serving_labels,
                            0,
                            False,
                        )
                        if not ok_serving or not chosen:
                            return
                        selected_serving = self.fatsecret_nutrition_flow_service.resolve_selected_serving(barcode_result, chosen)
                        if selected_serving.selected_serving is None:
                            return
                        serving = selected_serving.selected_serving
                    values = self.fatsecret_nutrition_flow_service.build_values_from_serving(serving)
                else:
                    return
                self._apply_nutrition_values(values)
                QMessageBox.information(self, "FatSecret", "Valores nutricionales cargados desde FatSecret.")
                return

            query = (
                self.name_input.text().strip()
                or self.reference_input.text().strip()
                or str(self.articulo_id or "").strip()
            )
            if not query:
                QMessageBox.warning(self, "FatSecret", "Introduce nombre o referencia para buscar.")
                return
            chosen_query = self._choose_fatsecret_query(query)
            if not chosen_query:
                return
            search_result = self.fatsecret_nutrition_flow_service.search_food(
                chosen_query,
                page=0,
                max_results=20,
                region="ES",
            )
            if search_result.status == "search_error":
                QMessageBox.warning(self, "FatSecret", search_result.message)
                return
            if search_result.status == "no_results":
                QMessageBox.information(self, "FatSecret", search_result.message)
                return
            if search_result.status != "foods_available":
                return
            selected_label, ok_food = QInputDialog.getItem(
                self,
                "Seleccionar alimento FatSecret",
                "Coincidencias encontradas:",
                search_result.food_labels,
                0,
                False,
            )
            if not ok_food or not selected_label:
                return
            food_result = self.fatsecret_nutrition_flow_service.load_selected_food(
                search_result,
                selected_label,
                region="ES",
                language="es",
            )
            if food_result.status == "no_food_id":
                QMessageBox.warning(self, "FatSecret", food_result.message)
                return
            if food_result.status == "no_servings":
                QMessageBox.information(self, "FatSecret", food_result.message)
                return
            if food_result.status != "servings_available":
                return
            servings = list(food_result.servings or [])
            if not servings:
                QMessageBox.information(self, "FatSecret", "El alimento no tiene raciones con datos nutricionales.")
                return
            serving = servings[0]
            if len(servings) > 1:
                chosen, ok_serving = QInputDialog.getItem(
                    self,
                    "Seleccionar ración",
                    "Raciones disponibles:",
                    food_result.serving_labels,
                    0,
                    False,
                )
                if not ok_serving or not chosen:
                    return
                selected_serving = self.fatsecret_nutrition_flow_service.resolve_selected_serving(food_result, chosen)
                if selected_serving.selected_serving is None:
                    return
                serving = selected_serving.selected_serving
            values = self.fatsecret_nutrition_flow_service.build_values_from_serving(serving)
            self._apply_nutrition_values(values)
            QMessageBox.information(self, "FatSecret", "Valores nutricionales cargados desde FatSecret.")
            return
        except FatSecretApiError as exc:
            QMessageBox.warning(self, "FatSecret", str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "FatSecret", f"No se pudo consultar FatSecret.\n{exc}")
            return

    def _load_nutrition_from_chatgpt(self) -> None:
        query = (
            self.name_input.text().strip()
            or self.reference_input.text().strip()
            or str(self.articulo_id or "").strip()
        )
        if not query:
            QMessageBox.warning(self, "ChatGPT", "Introduce nombre o referencia para buscar.")
            return
        manual_query, ok = QInputDialog.getText(
            self,
            "ChatGPT",
            "Consulta para buscar nutrición (por 100 g):",
            text=query,
        )
        if not ok:
            return
        q = str(manual_query or "").strip()
        if not q:
            return
        result = self.chatgpt_nutrition_flow_service.load_nutrition(q)
        if result.status == "no_query":
            QMessageBox.warning(self, "ChatGPT", result.message)
            return
        if result.status == "service_error":
            QMessageBox.warning(self, "ChatGPT", result.message)
            return
        if result.status == "error":
            QMessageBox.warning(self, "ChatGPT", result.message or "No se pudo consultar OpenAI.")
            return
        if result.status != "ready_to_apply":
            return
        self._apply_nutrition_values(result.values)
        QMessageBox.information(self, "ChatGPT", "Valores nutricionales cargados desde ChatGPT.")

    def _choose_fatsecret_query(self, source_query: str) -> str:
        options_result = self.fatsecret_nutrition_flow_service.build_query_options(source_query)
        options = options_result.query_options
        if not options:
            return ""
        selected, ok = QInputDialog.getItem(
            self,
            "Seleccionar traducción FatSecret",
            "Selecciona la traducción/query para buscar en FatSecret:",
            options,
            0,
            False,
        )
        if not ok or not selected:
            return ""
        return str(selected).strip()

    def _choose_fdc_query(self, options: list[str]) -> str:
        if not options:
            return ""
        selected, ok = QInputDialog.getItem(
            self,
            "Seleccionar traduccion",
            "Selecciona la traduccion/query para buscar en FDC:",
            options,
            0,
            False,
        )
        if not ok or not selected:
            return ""
        return str(selected).strip()

    def nutrition_payload(self) -> dict[str, float]:
        data: dict[str, float] = {}
        for i, (key, _label) in enumerate(self.NUTRIENT_FIELDS):
            cell = self.nutrition_table.item(i, 1)
            data[key] = self._extract_numeric_value(cell.text() if cell else "")
        return data

    def _apply_nutrition_values(self, values: dict[str, Any]) -> None:
        for i, (key, _label) in enumerate(self.NUTRIENT_FIELDS):
            val = float(values.get(key, 0.0) or 0.0)
            unit = self.NUTRIENT_UNITS.get(key, "")
            text = "" if abs(val) < 1e-12 else f"{self._float_text_2(val)} {unit}".strip()
            value_item = QTableWidgetItem(text)
            value_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value_item.setData(Qt.ItemDataRole.UserRole, float(val))
            self.nutrition_table.setItem(i, 1, value_item)
            ir_item = self.nutrition_table.item(i, 2)
            if ir_item is None:
                ir_item = QTableWidgetItem("")
                ir_item.setFlags(ir_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                ir_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.nutrition_table.setItem(i, 2, ir_item)
            ir_item.setText(self._compute_ir_text(key, float(val)))

    def _compute_ir_text(self, key: str, nutrient_value: float) -> str:
        if float(nutrient_value or 0.0) <= 0:
            return ""
        ref = float(self.DAILY_REFERENCE.get(key, 0.0) or 0.0)
        if ref <= 0:
            return ""
        pct = (float(nutrient_value or 0.0) / ref) * 100.0
        if pct < 1.0:
            return "<1%"
        return f"{int(round(pct))}%"

    def _extract_numeric_value(self, text: str) -> float:
        raw = str(text or "").strip().replace(",", ".")
        if not raw:
            return 0.0
        match = re.search(r"[-+]?\d*\.?\d+", raw)
        if not match:
            return 0.0
        try:
            return float(match.group(0))
        except Exception:
            return 0.0

    def _float_text(self, value: Any) -> str:
        try:
            return f"{float(value or 0):.4f}".rstrip("0").rstrip(".")
        except Exception:
            return ""

    def _float_text_2(self, value: Any) -> str:
        try:
            return f"{float(value or 0):.2f}"
        except Exception:
            return "0.00"

    def _to_float(self, value: str) -> float:
        try:
            return float(str(value or "").strip().replace(",", ".") or 0)
        except Exception:
            return 0.0

    def _recalculate_unit_price(self) -> None:
        precio_formato = self._to_float(self.pvp_format_input.text())
        cantidad = self._to_float(self.format_qty_input.text())
        unidad = (self.format_unit_combo.currentText() or "").strip().lower()
        if precio_formato <= 0 or cantidad <= 0:
            self.pvp_unit_input.clear()
            return

        # pvp_unidad_medida se guarda como precio por kg/l para materias primas.
        if unidad in {"kg", "l"}:
            precio_unidad = precio_formato / cantidad
        elif unidad in {"g", "ml"}:
            precio_unidad = precio_formato * 1000.0 / cantidad
        else:
            precio_unidad = precio_formato / cantidad

        self.pvp_unit_input.setText(self._float_text(precio_unidad))

    def _register_price_for_selected_date(self) -> None:
        if not self.articulo_id:
            QMessageBox.information(self, "Precios", "Guarda primero el articulo para registrar historico.")
            return
        precio = self._to_float(self.pvp_format_input.text())
        if precio <= 0:
            QMessageBox.information(self, "Precios", "Introduce un PVP formato mayor que 0.")
            return
        q_fecha = self.price_date_input.date()
        fecha: date = date(q_fecha.year(), q_fecha.month(), q_fecha.day())
        self.std_service.upsert_price(self.articulo_id, precio, fecha)
        self._load_price_history()

    def _delete_selected_price_row(self) -> None:
        if not self.articulo_id:
            return
        selected = self.price_history_table.selectionModel().selectedRows() if self.price_history_table.selectionModel() else []
        if not selected:
            QMessageBox.information(self, "Precios", "Selecciona una fila del historico.")
            return
        row_idx = selected[0].row()
        id_item = self.price_history_table.item(row_idx, 0)
        price_id = int(id_item.data(Qt.ItemDataRole.UserRole) or 0) if id_item else 0
        if price_id <= 0:
            QMessageBox.warning(self, "Precios", "No se pudo identificar la fila seleccionada.")
            return
        answer = QMessageBox.question(self, "Eliminar precio", "Eliminar el registro de precio seleccionado?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.std_service.delete_price(price_id)
        self._load_price_history()

    def get_payload(self) -> dict[str, Any]:
        return {
            "articulo_referencia_distribuidor": self.reference_input.text().strip(),
            "articulo_descripcion": self.name_input.text().strip(),
            "distribuidor_id": str(self.distributor_combo.currentData() or "").strip(),
            "categoria": self.category_combo.currentText().strip(),
            "formato": self.format_combo.currentText().strip(),
            "formato_cantidad": self._to_float(self.format_qty_input.text()),
            "formato_unidad": self.format_unit_combo.currentText().strip(),
            "pvp_formato": self._to_float(self.pvp_format_input.text()),
            "pvp_unidad_medida": self._to_float(self.pvp_unit_input.text()),
            "price_date": self.price_date_input.date().toPython(),
        }


class IngredientsStdArticlesTab(_BaseIngredientsPage):
    def __init__(self) -> None:
        self._loading_active_checks = False
        self.active_filter: QComboBox | None = None
        self.std_service = IngredientStdService(IngredientStdViewModel())
        self._sort_col = 1
        self._sort_order = Qt.SortOrder.AscendingOrder
        self._cache_rows: list[Any] | None = None
        self._cache_active_filter = "all"
        self._typing_timer = QTimer()
        self._typing_timer.setSingleShot(True)
        self._typing_timer.setInterval(120)
        super().__init__(
            title="Articulos",
            schema=ingredient_schema(include_referencia=False),
            vm=IngredientStdViewModel(),
            include_referencia=False,
            columns=[
                ("activo", "Activo"),
                ("articulo_referencia_distribuidor", "Referencia"),
                ("articulo_descripcion", "Nombre"),
                ("distribuidor_nombre", "Proveedor"),
                ("categoria", "Categoria"),
                ("formato", "Formato"),
                ("formato_cantidad", "Cantidad"),
                ("pvp_formato", "PVP formato"),
                ("pvp_unidad_medida", "PVP unidad"),
            ],
            include_filters=False,
            id_attr="articulo_id",
            required_fields=["articulo_descripcion"],
        )
        self._typing_timer.setParent(self)
        self._typing_timer.timeout.connect(self.reload)
        try:
            self.search_input.textChanged.disconnect()
        except Exception:
            pass
        self.search_input.textChanged.connect(lambda *_: self._typing_timer.start())
        root_layout = self.layout()
        toolbar_layout: QHBoxLayout | None = None
        if isinstance(root_layout, QVBoxLayout) and root_layout.count() > 1:
            toolbar_item = root_layout.itemAt(1)
            if toolbar_item is not None:
                maybe_layout = toolbar_item.layout()
                if isinstance(maybe_layout, QHBoxLayout):
                    toolbar_layout = maybe_layout
        self.active_filter = QComboBox()
        self.active_filter.addItem("Todos", "all")
        self.active_filter.addItem("Activos", "active")
        self.active_filter.addItem("Inactivos", "inactive")
        self.active_filter.setFixedWidth(130)
        self.active_filter.currentIndexChanged.connect(lambda *_: self.reload())
        if isinstance(toolbar_layout, QHBoxLayout):
            toolbar_layout.insertWidget(1, self.active_filter)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        for idx in range(self.table.columnCount()):
            header.setSectionResizeMode(idx, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 90)
        self.table.setColumnWidth(1, 130)
        self.table.setColumnWidth(2, 300)
        self.table.setColumnWidth(3, 190)
        self.table.setColumnWidth(4, 90)
        self.table.setColumnWidth(5, 90)
        self.table.setColumnWidth(6, 130)
        self.table.setColumnWidth(7, 110)
        self.table.setColumnWidth(8, 110)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setStyleSheet("QTableWidget::item:focus { border: none; outline: 0; }")
        self.table.setSortingEnabled(False)
        header = self.table.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        header.setSortIndicator(self._sort_col, self._sort_order)
        header.sectionClicked.connect(self._on_header_clicked)
        self.reload()

    def _active_filter_value(self) -> str:
        if not self.active_filter:
            return "all"
        return str(self.active_filter.currentData() or "all")

    def _invalidate_cache(self) -> None:
        self._cache_rows = None

    def _term_matches(self, row: Any, term: str) -> bool:
        haystack = " ".join(
            [
                str(row.articulo_referencia_distribuidor or ""),
                str(row.articulo_descripcion or ""),
                str(row.distribuidor_id or ""),
                str(row.distribuidor_nombre or ""),
                str(row.articulo_grupo_id or ""),
                str(row.articulo_familia_id or ""),
                str(row.articulo_subfamilia_id or ""),
                str(row.categoria or ""),
                str(row.formato or ""),
                str(row.formato_unidad or ""),
            ]
        ).lower()
        return term in haystack

    def reload(self) -> None:
        term = self.search_input.text().strip().lower()
        active_filter = self._active_filter_value()

        # Pull from DB only when cache is empty or the active scope changed.
        if self._cache_rows is None or self._cache_active_filter != active_filter:
            self._cache_rows = self.list_fn("", "", "")
            self._cache_active_filter = active_filter

        if term:
            self.rows = [row for row in self._cache_rows if self._term_matches(row, term)]
        else:
            self.rows = list(self._cache_rows)

        self._render_table()

    def _render_table(self) -> None:
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        self._loading_active_checks = True
        self.table.setRowCount(len(self.rows))
        for row_idx, item in enumerate(self.rows):
            articulo_id = str(getattr(item, self.id_attr, None) or "")
            active_box = QWidget()
            active_box.setStyleSheet("background: transparent; border: none;")
            active_layout = QHBoxLayout(active_box)
            active_layout.setContentsMargins(0, 0, 0, 0)
            active_layout.setSpacing(0)
            active_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            active_check = QCheckBox()
            active_check.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            active_check.setChecked(bool(getattr(item, "activo", False)))
            active_check.setStyleSheet(
                """
                QCheckBox { background: transparent; }
                QCheckBox::indicator {
                    width: 15px;
                    height: 15px;
                    border: 1px solid #BFC9D8;
                    border-radius: 4px;
                    background: transparent;
                }
                QCheckBox::indicator:checked {
                    border: 1px solid #5BBE6A;
                    background: #5BBE6A;
                    image: url(assets/icons/checkmark_white.svg);
                }
                QCheckBox::indicator:focus,
                QCheckBox::indicator:hover,
                QCheckBox::indicator:pressed {
                    border: 1px solid #BFC9D8;
                }
                QCheckBox::indicator:checked:focus,
                QCheckBox::indicator:checked:hover,
                QCheckBox::indicator:checked:pressed {
                    border: 1px solid #5BBE6A;
                    background: #5BBE6A;
                }
                """
            )
            active_check.stateChanged.connect(
                lambda state, aid=articulo_id: self._on_active_checkbox_changed(
                    aid, state == Qt.CheckState.Checked.value
                )
            )
            active_layout.addWidget(active_check)
            self.table.setCellWidget(row_idx, 0, active_box)

            ref_item = QTableWidgetItem(str(getattr(item, "articulo_referencia_distribuidor", "") or ""))
            ref_item.setData(Qt.ItemDataRole.UserRole, getattr(item, self.id_attr, None))
            self.table.setItem(row_idx, 1, ref_item)
            self.table.setItem(row_idx, 2, QTableWidgetItem(str(getattr(item, "articulo_descripcion", "") or "")))
            self.table.setItem(row_idx, 3, QTableWidgetItem(str(getattr(item, "distribuidor_nombre", "") or "")))
            self.table.setItem(row_idx, 4, QTableWidgetItem(str(getattr(item, "categoria", "") or "")))
            self.table.setItem(row_idx, 5, QTableWidgetItem(str(getattr(item, "formato", "") or "")))
            qty_txt = self._float_text(getattr(item, "formato_cantidad", 0.0))
            unit_txt = str(getattr(item, "formato_unidad", "") or "").strip()
            cantidad_display = f"{qty_txt} {unit_txt}".strip() if qty_txt else ""
            cantidad_item = QTableWidgetItem(cantidad_display)
            cantidad_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row_idx, 6, cantidad_item)

            pvp_formato_val = float(getattr(item, "pvp_formato", 0.0) or 0.0)
            pvp_formato_item = QTableWidgetItem("" if abs(pvp_formato_val) < 1e-12 else self._euro_text(pvp_formato_val))
            pvp_formato_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row_idx, 7, pvp_formato_item)

            pvp_unidad_val = float(getattr(item, "pvp_unidad_medida", 0.0) or 0.0)
            pvp_unidad_item = QTableWidgetItem("" if abs(pvp_unidad_val) < 1e-12 else self._euro_text(pvp_unidad_val))
            pvp_unidad_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row_idx, 8, pvp_unidad_item)
        self._loading_active_checks = False
        self.table.blockSignals(False)
        self.table.setUpdatesEnabled(True)

    def _float_text(self, value: Any) -> str:
        try:
            return f"{float(value or 0):.4f}".rstrip("0").rstrip(".")
        except Exception:
            return ""

    def _euro_text(self, value: Any) -> str:
        try:
            return f"{float(value or 0):.4f}".rstrip("0").rstrip(".") + " €"
        except Exception:
            return "0 €"

    def _new_entity(self) -> None:
        dialog = IngredientStdArticleDialog("Nuevo: Articulos", parent=self)
        if dialog.exec():
            payload = dialog.get_payload()
            price_date = payload.pop("price_date", None)
            nutrition = dialog.nutrition_payload()
            self.std_service.create_article(payload, price_date=price_date, nutrition=nutrition)
            self._invalidate_cache()
            self.reload()

    def _edit_entity(self) -> None:
        row = self._selected_row()
        if not row:
            QMessageBox.warning(self, "Atencion", "Selecciona un registro.")
            return
        initial = {field["name"]: getattr(row, field["name"], None) for field in self.schema}
        initial["articulo_id"] = str(getattr(row, "articulo_id", "") or "")
        dialog = IngredientStdArticleDialog("Editar: Articulos", initial=initial, parent=self)
        if dialog.exec():
            payload = dialog.get_payload()
            price_date = payload.pop("price_date", None)
            nutrition = dialog.nutrition_payload()
            self.std_service.update_article(
                str(getattr(row, "articulo_id", "") or ""),
                payload,
                price_date=price_date,
                nutrition=nutrition,
            )
            self._invalidate_cache()
            self.reload()

    def _delete_entity(self) -> None:
        self._invalidate_cache()
        super()._delete_entity()

    def _import_entities(self) -> None:
        self._invalidate_cache()
        super()._import_entities()

    def _on_active_checkbox_changed(self, articulo_id: str, activo: bool) -> None:
        if self._loading_active_checks:
            return
        if not articulo_id:
            return
        try:
            self.std_service.update_active(articulo_id, activo)
            self._invalidate_cache()
            if self._active_filter_value() != "all":
                self.reload()
        except Exception:
            pass

    def _on_header_clicked(self, section: int) -> None:
        if section == 0:
            header = self.table.horizontalHeader()
            header.setSortIndicator(self._sort_col, self._sort_order)
            return
        if section == self._sort_col:
            self._sort_order = (
                Qt.SortOrder.DescendingOrder
                if self._sort_order == Qt.SortOrder.AscendingOrder
                else Qt.SortOrder.AscendingOrder
            )
        else:
            self._sort_col = section
            self._sort_order = Qt.SortOrder.AscendingOrder
        self.table.sortItems(self._sort_col, self._sort_order)
        self.table.horizontalHeader().setSortIndicator(self._sort_col, self._sort_order)


class IngredientsStdPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)

        header = QLabel("Materias primas")
        header.setProperty("role", "pageTitle")
        layout.addWidget(header)

        tabs = QTabWidget()
        self.articles_tab = IngredientsStdArticlesTab()
        self.distributors_tab = IngredientDistributorsTab()
        tabs.addTab(self.articles_tab, "Articulo")
        tabs.addTab(self.distributors_tab, "Proveedores")
        layout.addWidget(tabs, 1)
