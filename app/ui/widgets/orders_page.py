from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import re
import tempfile
from typing import Any, Callable, cast

from PySide6.QtCore import QDate, QTimer, Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QApplication,
    QProgressBar,
    QProgressDialog,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from app.models import (
    Albaran,
    AlbaranItem,
    Factura,
    FacturaItem,
    Fabricante,
    Familia,
    IngredienteIreks,
    Pedido,
    PedidoItem,
    PedidoPendiente,
    Subfamilia,
)
from app.services.order_document_import_service import OrderDocumentImportService
from app.services.order_document_parser import OrderDocumentParser
from app.services.order_export_service import OrderExportService
from app.services.orders_documents_import_ui_service import OrdersDocumentsImportUiService
from app.services.order_query_service import OrderQueryService
from app.services.order_service import OrderLineInput, OrderService
from app.services.orders_mail_settings_service import OrdersMailSettingsService

MONTHS = [
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

@dataclass
class PedidoListRow:
    pedido_id: str
    almacen_id: str
    almacen_nombre: str
    pedido_fecha: date
    pedido_numero: str
    pedido_albaran_numero: str
    pedido_factura_numero: str
    pedido_ref: str
    pedido_estado: str
    semana: int
    total_kg: float


class NumericTableWidgetItem(QTableWidgetItem):
    def __init__(self, text: str, sort_value: float) -> None:
        super().__init__(text)
        self.setData(Qt.ItemDataRole.UserRole, float(sort_value))

    def __lt__(self, other: QTableWidgetItem) -> bool:
        left = self.data(Qt.ItemDataRole.UserRole)
        right = other.data(Qt.ItemDataRole.UserRole) if other is not None else None
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            return float(left) < float(right)
        return super().__lt__(other)


class AlbaranPreviewDialog(QDialog):
    def __init__(self, header: dict[str, str], items: list[dict[str, Any]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Previsualización de albarán")
        self.resize(980, 620)

        layout = QVBoxLayout(self)
        info = QLabel(
            "Revisa los datos extraídos antes de importar.\n"
            f"Número: {header.get('albaran_numero', '')} | Fecha: {header.get('albaran_fecha', '')} | "
            f"Fecha pedido: {header.get('fecha_pedido', '')} | Nº Pedido: {header.get('pedido_numero', '')}"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        table = QTableWidget(len(items), 6)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.verticalHeader().setVisible(False)
        table.setHorizontalHeaderLabels(["Código", "Descripción", "Kilos", "Envases", "Lote", "Cons.Pref."])
        header_widget = table.horizontalHeader()
        header_widget.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header_widget.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header_widget.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header_widget.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header_widget.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header_widget.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(0, 110)
        table.setColumnWidth(2, 110)
        table.setColumnWidth(3, 90)
        table.setColumnWidth(4, 120)
        table.setColumnWidth(5, 120)
        for idx, item in enumerate(items):
            table.setItem(idx, 0, QTableWidgetItem(str(item.get("articulo_codigo") or "")))
            table.setItem(idx, 1, QTableWidgetItem(str(item.get("articulo_descripcion") or "")))
            table.setItem(idx, 2, QTableWidgetItem(str(item.get("articulo_kilos") or "")))
            table.setItem(idx, 3, QTableWidgetItem(str(item.get("articulo_cantidad") or "")))
            table.setItem(idx, 4, QTableWidgetItem(str(item.get("articulo_lote") or "")))
            table.setItem(idx, 5, QTableWidgetItem(str(item.get("articulo_caducidad") or "")))
        layout.addWidget(table, 1)

        buttons = QDialogButtonBox()
        import_btn = buttons.addButton("Importar", QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_btn = buttons.addButton("Cancelar", QDialogButtonBox.ButtonRole.RejectRole)
        import_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(buttons)


class FacturaPreviewDialog(QDialog):
    def __init__(self, header: dict[str, str], items: list[dict[str, Any]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Previsualización de factura")
        self.resize(1120, 680)

        layout = QVBoxLayout(self)
        info = QLabel(
            "Revisa los datos extraídos antes de importar.\n"
            f"Factura: {header.get('factura_numero', '')} | Fecha: {header.get('factura_fecha', '')} | "
            f"Albarán: {header.get('albaran_numero', '')} | Referencia: {header.get('factura_referencia', '')} | "
            f"Total kg: {header.get('total_kilos', '')} | Total: {header.get('total_factura', '')}"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        table = QTableWidget(len(items), 11)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.verticalHeader().setVisible(False)
        table.setHorizontalHeaderLabels(
            ["Código", "Descripción", "Uds.", "Env.", "Kg/Lit.", "Lote", "Caducidad", "Precio", "Dto", "IVA", "Total"]
        )
        header_widget = table.horizontalHeader()
        header_widget.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header_widget.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col_idx in range(2, 11):
            header_widget.setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(0, 110)
        table.setColumnWidth(2, 75)
        table.setColumnWidth(3, 75)
        table.setColumnWidth(4, 90)
        table.setColumnWidth(5, 105)
        table.setColumnWidth(6, 105)
        table.setColumnWidth(7, 80)
        table.setColumnWidth(8, 65)
        table.setColumnWidth(9, 65)
        table.setColumnWidth(10, 90)
        for idx, item in enumerate(items):
            price_discrepancy = bool(item.get("precio_discrepancia"))
            values = [
                item.get("articulo_codigo"),
                item.get("articulo_descripcion"),
                item.get("articulo_cantidad"),
                item.get("articulo_envase"),
                item.get("articulo_kilos"),
                item.get("articulo_lote"),
                item.get("articulo_caducidad"),
                item.get("precio_unitario"),
                item.get("dto_pct"),
                item.get("iva_pct"),
                item.get("total_linea"),
            ]
            for col_idx, value in enumerate(values):
                cell = QTableWidgetItem(str(value or ""))
                if col_idx == 7 and price_discrepancy:
                    cell.setForeground(QBrush(QColor("#c62828")))
                table.setItem(idx, col_idx, cell)
        layout.addWidget(table, 1)

        buttons = QDialogButtonBox()
        import_btn = buttons.addButton("Importar", QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_btn = buttons.addButton("Cancelar", QDialogButtonBox.ButtonRole.RejectRole)
        import_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(buttons)


class FacturaItemEditDialog(QDialog):
    def __init__(self, item: FacturaItem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar línea de factura")
        self.resize(940, 280)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        self.fields: dict[str, QLineEdit] = {}

        def make_field(name: str, label: str, value: Any, *, width: int | None = None) -> QWidget:
            wrap = QWidget()
            wrap_layout = QVBoxLayout(wrap)
            wrap_layout.setContentsMargins(0, 0, 0, 0)
            wrap_layout.setSpacing(3)
            lbl = QLabel(label)
            edit = QLineEdit(str(value or ""))
            if width:
                edit.setFixedWidth(width)
            else:
                edit.setMinimumWidth(420)
            self.fields[name] = edit
            wrap_layout.addWidget(lbl)
            wrap_layout.addWidget(edit)
            return wrap

        def add_row(items: list[QWidget]) -> None:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(10)
            for widget in items:
                row.addWidget(widget)
            row.addStretch(1)
            layout.addLayout(row)

        factura_fecha = getattr(item, "factura_fecha", None)
        caducidad = getattr(item, "articulo_caducidad", None)

        add_row(
            [
                make_field("factura_numero", "Factura número", getattr(item, "factura_numero", ""), width=150),
                make_field("factura_fecha", "Factura fecha", factura_fecha.strftime("%d/%m/%Y") if factura_fecha else "", width=140),
                make_field("albaran_numero", "Albarán número", getattr(item, "albaran_numero", ""), width=160),
            ]
        )
        add_row(
            [
                make_field("articulo_codigo", "Código artículo", getattr(item, "articulo_codigo", ""), width=150),
                make_field("articulo_descripcion", "Descripción", getattr(item, "articulo_descripcion", "")),
            ]
        )
        add_row(
            [
                make_field("articulo_cantidad", "Uds.", self._fmt(getattr(item, "articulo_cantidad", 0.0)), width=90),
                make_field("articulo_envase", "Env.", self._fmt(getattr(item, "articulo_envase", 0.0)), width=90),
                make_field("articulo_kilos", "Kg/Lit.", self._fmt(getattr(item, "articulo_kilos", 0.0)), width=100),
                make_field("precio_unitario", "Precio", self._fmt(getattr(item, "precio_unitario", 0.0)), width=100),
                make_field("dto_pct", "Dto %", self._fmt(getattr(item, "dto_pct", 20.0)), width=90),
                make_field("total_linea", "Total", self._fmt(getattr(item, "total_linea", 0.0)), width=120),
            ]
        )
        add_row(
            [
                make_field("articulo_lote", "Lote", getattr(item, "articulo_lote", ""), width=180),
                make_field("articulo_caducidad", "Caducidad", caducidad.strftime("%d/%m/%Y") if caducidad else "", width=140),
            ]
        )

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _fmt(value: Any) -> str:
        try:
            return f"{float(value or 0.0):.2f}".replace(".", ",")
        except Exception:
            return "0,00"

    @staticmethod
    def _to_float(value: str) -> float:
        text = str(value or "").strip()
        if not text:
            return 0.0
        if "," not in text and "." in text:
            parts = text.split(".")
            if len(parts) == 2 and 1 <= len(parts[1]) <= 2:
                return float(text)
        return float(text.replace(".", "").replace(",", "."))

    @staticmethod
    def _to_date(value: str, *, required: bool) -> date | None:
        text = str(value or "").strip()
        if not text:
            if required:
                raise ValueError("fecha obligatoria")
            return None
        for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
            try:
                return datetime.strptime(text, fmt).date()
            except Exception:
                pass
        raise ValueError(f"fecha no válida: {text}")

    def _accept_if_valid(self) -> None:
        try:
            self.payload()
        except Exception as exc:
            QMessageBox.warning(self, "Factura", f"No se puede guardar.\n{exc}")
            return
        self.accept()

    def payload(self) -> dict[str, Any]:
        return {
            "factura_numero": self.fields["factura_numero"].text().strip(),
            "factura_fecha": self._to_date(self.fields["factura_fecha"].text(), required=True),
            "albaran_numero": self.fields["albaran_numero"].text().strip(),
            "articulo_codigo": self.fields["articulo_codigo"].text().strip(),
            "articulo_descripcion": self.fields["articulo_descripcion"].text().strip(),
            "articulo_cantidad": self._to_float(self.fields["articulo_cantidad"].text()),
            "articulo_envase": self._to_float(self.fields["articulo_envase"].text()),
            "articulo_kilos": self._to_float(self.fields["articulo_kilos"].text()),
            "articulo_lote": self.fields["articulo_lote"].text().strip(),
            "articulo_caducidad": self._to_date(self.fields["articulo_caducidad"].text(), required=False),
            "precio_unitario": self._to_float(self.fields["precio_unitario"].text()),
            "dto_pct": self._to_float(self.fields["dto_pct"].text()),
            "total_linea": self._to_float(self.fields["total_linea"].text()),
        }


class AddPedidoLineDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Añadir línea de pedido")
        self.resize(760, 520)
        self._all_rows: list[IngredienteIreks] = []
        self._build_ui()
        self._load_rows()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filtro"))
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Buscar por código o nombre...")
        self.filter_edit.textChanged.connect(self._render_rows)
        filter_row.addWidget(self.filter_edit, 1)
        layout.addLayout(filter_row)

        self.table = QTableWidget(0, 2)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setHorizontalHeaderLabels(["Cod.", "Nombre"])
        self.table.setColumnWidth(0, 140)
        self.table.itemDoubleClicked.connect(lambda _item: self.accept())
        layout.addWidget(self.table, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_rows(self) -> None:
        self._all_rows = OrderQueryService().list_active_ingredients()
        self._render_rows()

    def _render_rows(self) -> None:
        pattern = str(self.filter_edit.text() or "").strip().lower()
        rows: list[IngredienteIreks] = []
        if not pattern:
            rows = list(self._all_rows)
        else:
            for row in self._all_rows:
                cod = str(getattr(row, "articulo_referencia_corta", "") or "").strip()
                if not cod:
                    cod = str(getattr(row, "articulo_referencia", "") or "").strip()
                name = str(getattr(row, "articulo_descripcion", "") or "").strip()
                haystack = f"{cod} {name}".lower()
                if pattern in haystack:
                    rows.append(row)
        self.table.setRowCount(len(rows))
        for idx, row in enumerate(rows):
            articulo_id = str(getattr(row, "articulo_id", "") or "").strip()
            cod = str(getattr(row, "articulo_referencia_corta", "") or "").strip()
            if not cod:
                cod = str(getattr(row, "articulo_referencia", "") or "").strip()
            name = str(getattr(row, "articulo_descripcion", "") or "").strip()
            cod_item = QTableWidgetItem(cod or articulo_id)
            cod_item.setData(Qt.ItemDataRole.UserRole, articulo_id)
            name_item = QTableWidgetItem(name or (cod or articulo_id))
            self.table.setItem(idx, 0, cod_item)
            self.table.setItem(idx, 1, name_item)
        if self.table.rowCount() > 0:
            self.table.selectRow(0)

    def selected_article(self) -> tuple[str, str, str] | None:
        selected = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not selected:
            return None
        row_idx = selected[0].row()
        cod_item = self.table.item(row_idx, 0)
        name_item = self.table.item(row_idx, 1)
        articulo_id = str(cod_item.data(Qt.ItemDataRole.UserRole) or "").strip() if cod_item else ""
        if not articulo_id:
            return None
        cod = str(cod_item.text() or "").strip() if cod_item else ""
        nombre = str(name_item.text() or "").strip() if name_item else ""
        return articulo_id, cod, nombre


class EditPedidoLineDialog(QDialog):
    def __init__(
        self,
        articulo_id: str,
        cantidad: float,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._articulo_id = str(articulo_id or "").strip()
        self._cantidad = float(cantidad or 0.0)
        self._all_rows: list[IngredienteIreks] = []
        self._row_by_articulo: dict[str, IngredienteIreks] = {}
        self._search_rows: list[IngredienteIreks] = []
        self._selected_nombre = ""
        self._selected_peso = 0.0
        self.setWindowTitle("Editar línea de pedido")
        self.setFixedSize(900, 360)
        self._build_ui()
        self._load_rows()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filtro"), 0)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Buscar por referencia o nombre...")
        self.filter_edit.setStyleSheet("background-color: #FFF4CC; border: 1px solid #E2A81E;")
        self.filter_edit.textChanged.connect(self._render_search_rows)
        filter_row.addWidget(self.filter_edit, 1)
        layout.addLayout(filter_row)

        self.search_table = QTableWidget(0, 2)
        self.search_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.search_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.search_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.search_table.verticalHeader().setVisible(False)
        self.search_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.search_table.setStyleSheet("QTableWidget::item:focus { border: none; outline: 0; }")
        search_header = self.search_table.horizontalHeader()
        search_header.setSectionsClickable(False)
        search_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        search_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.search_table.setHorizontalHeaderLabels(["Referencia", "Nombre"])
        self.search_table.setColumnWidth(0, 150)
        self.search_table.itemSelectionChanged.connect(self._on_search_selected)
        layout.addWidget(self.search_table, 1)

        data_box = QFrame()
        data_box.setStyleSheet("QFrame { background-color: #FFFFFF; border: none; }")
        data_box_layout = QVBoxLayout(data_box)
        data_box_layout.setContentsMargins(10, 10, 10, 10)
        data_box_layout.setSpacing(6)

        data_row = QHBoxLayout()
        ref_col = QVBoxLayout()
        ref_col.setSpacing(2)
        ref_col.addWidget(QLabel("Referencia"))
        self.ref_edit = QLineEdit()
        self.ref_edit.setReadOnly(True)
        self.ref_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.ref_edit.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.ref_edit.setMinimumWidth(95)
        self.ref_edit.setMaximumWidth(120)
        ref_col.addWidget(self.ref_edit)
        data_row.addLayout(ref_col, 0)

        nombre_col = QVBoxLayout()
        nombre_col.setSpacing(2)
        nombre_col.addWidget(QLabel("Nombre"))
        self.nombre_edit = QLineEdit()
        self.nombre_edit.setReadOnly(True)
        self.nombre_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.nombre_edit.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.nombre_edit.setMinimumWidth(360)
        nombre_col.addWidget(self.nombre_edit)
        data_row.addLayout(nombre_col, 1)

        peso_col = QVBoxLayout()
        peso_col.setSpacing(2)
        peso_col.addWidget(QLabel("Peso"))
        self.peso_edit = QLineEdit()
        self.peso_edit.setReadOnly(True)
        self.peso_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.peso_edit.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.peso_edit.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.peso_edit.setMinimumWidth(70)
        self.peso_edit.setMaximumWidth(90)
        peso_col.addWidget(self.peso_edit)
        data_row.addLayout(peso_col, 0)

        cantidad_col = QVBoxLayout()
        cantidad_col.setSpacing(2)
        cantidad_col.addWidget(QLabel("Cantidad"))
        self.cantidad_edit = QLineEdit()
        self.cantidad_edit.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.cantidad_edit.setStyleSheet("background-color: #FFF4CC; border: 1px solid #E2A81E;")
        self.cantidad_edit.setText(f"{self._cantidad:.2f}".replace(".", ","))
        self.cantidad_edit.textChanged.connect(self._update_total_field)
        self.cantidad_edit.setMinimumWidth(80)
        self.cantidad_edit.setMaximumWidth(95)
        cantidad_col.addWidget(self.cantidad_edit)
        data_row.addLayout(cantidad_col, 0)

        total_col = QVBoxLayout()
        total_col.setSpacing(2)
        total_col.addWidget(QLabel("Peso total"))
        self.total_edit = QLineEdit()
        self.total_edit.setReadOnly(True)
        self.total_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.total_edit.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.total_edit.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.total_edit.setMinimumWidth(85)
        self.total_edit.setMaximumWidth(100)
        total_col.addWidget(self.total_edit)
        data_row.addLayout(total_col, 0)
        data_box_layout.addLayout(data_row)
        layout.addWidget(data_box)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_rows(self) -> None:
        self._all_rows = OrderQueryService().list_active_ingredients()
        self._row_by_articulo = {
            str(getattr(row, "articulo_id", "") or "").strip(): row
            for row in self._all_rows
            if str(getattr(row, "articulo_id", "") or "").strip()
        }
        if self._articulo_id not in self._row_by_articulo and self._all_rows:
            self._articulo_id = str(getattr(self._all_rows[0], "articulo_id", "") or "").strip()
        self._render_search_rows(str(self.filter_edit.text() or ""))
        self._set_selected_article(self._articulo_id)

    def _article_ref(self, row: IngredienteIreks | None) -> str:
        if row is None:
            return ""
        return str(getattr(row, "articulo_referencia_corta", "") or "").strip() or str(
            getattr(row, "articulo_referencia", "") or ""
        ).strip()

    def _article_name(self, row: IngredienteIreks | None) -> str:
        return str(getattr(row, "articulo_descripcion", "") or "").strip() if row is not None else ""

    def _article_weight(self, row: IngredienteIreks | None) -> float:
        return float(getattr(row, "articulo_envase_peso_total", 0.0) or 0.0) if row is not None else 0.0

    def _render_search_rows(self, filter_text: str) -> None:
        pattern = str(filter_text or "").strip().lower()
        rows: list[IngredienteIreks] = []
        for row in self._all_rows:
            articulo_id = str(getattr(row, "articulo_id", "") or "").strip()
            if not articulo_id:
                continue
            ref = self._article_ref(row)
            name = self._article_name(row)
            haystack = f"{ref} {name}".lower()
            if pattern and pattern not in haystack:
                continue
            rows.append(row)
        self._search_rows = rows
        self.search_table.blockSignals(True)
        self.search_table.setRowCount(len(rows))
        for idx, row in enumerate(rows):
            articulo_id = str(getattr(row, "articulo_id", "") or "").strip()
            ref = self._article_ref(row) or articulo_id
            name = self._article_name(row) or ref
            ref_item = QTableWidgetItem(ref)
            ref_item.setData(Qt.ItemDataRole.UserRole, articulo_id)
            name_item = QTableWidgetItem(name)
            self.search_table.setItem(idx, 0, ref_item)
            self.search_table.setItem(idx, 1, name_item)
        self.search_table.blockSignals(False)
        self._select_search_row_by_article(self._articulo_id)

    def _select_search_row_by_article(self, articulo_id: str) -> None:
        clean_id = str(articulo_id or "").strip()
        if self.search_table.rowCount() <= 0:
            return
        target_idx = -1
        for idx in range(self.search_table.rowCount()):
            ref_item = self.search_table.item(idx, 0)
            row_id = str(ref_item.data(Qt.ItemDataRole.UserRole) or "").strip() if ref_item else ""
            if row_id == clean_id:
                target_idx = idx
                break
        if target_idx < 0:
            target_idx = 0
        self.search_table.selectRow(target_idx)

    def _on_search_selected(self) -> None:
        selected = self.search_table.selectionModel().selectedRows() if self.search_table.selectionModel() else []
        if not selected:
            return
        row_idx = selected[0].row()
        ref_item = self.search_table.item(row_idx, 0)
        articulo_id = str(ref_item.data(Qt.ItemDataRole.UserRole) or "").strip() if ref_item else ""
        if not articulo_id:
            return
        self._set_selected_article(articulo_id)

    def _set_selected_article(self, articulo_id: str) -> None:
        self._articulo_id = articulo_id
        row = self._row_by_articulo.get(articulo_id)
        self.ref_edit.setText(self._article_ref(row) or articulo_id)
        self._selected_nombre = self._article_name(row)
        self._selected_peso = self._article_weight(row)
        self.nombre_edit.setText(self._selected_nombre)
        self.peso_edit.setText(f"{self._selected_peso:.2f}".replace(".", ","))
        self._update_total_field()

    def _update_total_field(self) -> None:
        qty = self._parse_qty()
        total = 0.0 if qty is None else qty * float(self._selected_peso)
        self.total_edit.setText(f"{total:.2f}".replace(".", ","))

    def _parse_qty(self) -> float | None:
        text = str(self.cantidad_edit.text() or "").strip()
        if not text:
            return None
        try:
            value = float(text.replace(",", "."))
        except Exception:
            return None
        if value < 0:
            return None
        return value

    def _on_accept(self) -> None:
        if not self._articulo_id:
            QMessageBox.warning(self, "Pedidos", "Selecciona un artículo.")
            return
        qty = self._parse_qty()
        if qty is None:
            QMessageBox.warning(self, "Pedidos", "Cantidad no válida.")
            return
        self._cantidad = qty
        self.accept()

    def payload(self) -> tuple[str, float]:
        return self._articulo_id, float(self._cantidad)


@dataclass
class NewPedidoLine:
    articulo_id: str
    referencia: str
    nombre: str
    peso: float
    uds: float
    total_kg: float


class NewPedidoDialog(QDialog):
    def __init__(
        self,
        almacen_id: str,
        parent: QWidget | None = None,
        *,
        title: str = "Nuevo pedido",
        pedido_fecha: date | None = None,
        pedido_numero: str = "",
        initial_qty_by_articulo: dict[str, float] | None = None,
        preload_history: bool = True,
        confirm_label: str = "Consignar",
        allow_pending: bool = True,
    ) -> None:
        super().__init__(parent)
        self.almacen_id = str(almacen_id or "").strip()
        self._pedido_fecha = pedido_fecha or date.today()
        self._pedido_numero = str(pedido_numero or "").strip()
        self._initial_qty_by_articulo = dict(initial_qty_by_articulo or {})
        self._preload_history = bool(preload_history)
        self._confirm_label = str(confirm_label or "Consignar").strip() or "Consignar"
        self._allow_pending = bool(allow_pending)
        self._submit_mode = "consignar"
        self.setWindowTitle(title)
        self.setFixedSize(980, 620)
        self._all_rows: list[IngredienteIreks] = []
        self._row_by_articulo: dict[str, IngredienteIreks] = {}
        self._qty_by_articulo: dict[str, float] = {}
        self._prev_qty_by_articulo: dict[str, float] = {}
        self._pending_qty_by_articulo: dict[str, float] = {}
        self._loading_table = False
        self._build_ui()
        self._load_rows()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Fecha pedido"))
        self.fecha_edit = QDateEdit()
        self.fecha_edit.setCalendarPopup(True)
        self.fecha_edit.setDisplayFormat("dd/MM/yyyy")
        self.fecha_edit.setDate(QDate(self._pedido_fecha.year, self._pedido_fecha.month, self._pedido_fecha.day))
        self.fecha_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_row.addWidget(self.fecha_edit)
        top_row.addWidget(QLabel("Número"))
        self.numero_edit = QLineEdit()
        self.numero_edit.setPlaceholderText("Opcional")
        self.numero_edit.setMaximumWidth(180)
        self.numero_edit.setText(self._pedido_numero)
        top_row.addWidget(self.numero_edit)
        top_row.addStretch(1)
        layout.addLayout(top_row)

        filters_row = QHBoxLayout()
        filters_row.addWidget(QLabel("Fabricante"))
        self.fabricante_filter = QComboBox()
        self.fabricante_filter.currentIndexChanged.connect(self._render_rows)
        filters_row.addWidget(self.fabricante_filter)
        filters_row.addWidget(QLabel("Familia"))
        self.familia_filter = QComboBox()
        self.familia_filter.currentIndexChanged.connect(self._render_rows)
        filters_row.addWidget(self.familia_filter)
        filters_row.addWidget(QLabel("Subfamilia"))
        self.subfamilia_filter = QComboBox()
        self.subfamilia_filter.currentIndexChanged.connect(self._render_rows)
        filters_row.addWidget(self.subfamilia_filter)
        filters_row.addStretch(1)
        layout.addLayout(filters_row)

        occurrence_row = QHBoxLayout()
        occurrence_row.addWidget(QLabel("Buscar ocurrencia"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Ref. o nombre...")
        self.search_edit.textChanged.connect(self._render_rows)
        occurrence_row.addWidget(self.search_edit, 1)
        self.only_nonzero_check = QCheckBox("Solo Uds <> 0")
        self.only_nonzero_check.toggled.connect(self._render_rows)
        occurrence_row.addWidget(self.only_nonzero_check, 0)
        layout.addLayout(occurrence_row)

        self.table = QTableWidget(0, 7)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed | QAbstractItemView.EditTrigger.SelectedClicked)
        self.table.verticalHeader().setVisible(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setStyleSheet("QTableWidget::item:focus { border: none; outline: 0; }")
        header = self.table.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.table.setHorizontalHeaderLabels(["Ref.", "Nombre", "Peso", "Uds.", "Total kg", "Pedido ant.", "Pendiente"])
        self.table.setColumnWidth(0, 120)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 90)
        self.table.setColumnWidth(4, 110)
        self.table.setColumnWidth(5, 95)
        self.table.setColumnWidth(6, 95)
        self.table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.table, 1)

        self.totals_lbl = QLabel("Total Uds.: 0,00    Total kg: 0,00")
        self.move_up_btn = QPushButton("↑")
        self.move_up_btn.setToolTip("Subir selección")
        self.move_up_btn.setFixedSize(86, 42)
        self.move_up_btn.setProperty("btnRole", "secondary")
        self.move_up_btn.clicked.connect(self._move_selection_up)
        self.move_down_btn = QPushButton("↓")
        self.move_down_btn.setToolTip("Bajar selección")
        self.move_down_btn.setFixedSize(86, 42)
        self.move_down_btn.setProperty("btnRole", "secondary")
        self.move_down_btn.clicked.connect(self._move_selection_down)
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setProperty("btnRole", "secondary")
        cancel_btn.clicked.connect(self.reject)
        consignar_btn = QPushButton(self._confirm_label)
        consignar_btn.setProperty("btnRole", "success")
        consignar_btn.clicked.connect(self._consignar)
        self.pending_btn = QPushButton("Pendiente")
        self.pending_btn.setProperty("btnRole", "warning")
        self.pending_btn.clicked.connect(self._save_pending)
        self.pending_btn.setVisible(self._allow_pending)

        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(8)

        left_box = QHBoxLayout()
        left_box.setContentsMargins(0, 0, 0, 0)
        left_box.setSpacing(8)
        left_box.addWidget(self.totals_lbl, 0, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        center_box = QHBoxLayout()
        center_box.setContentsMargins(0, 0, 0, 0)
        center_box.setSpacing(10)
        center_box.addWidget(self.move_up_btn)
        center_box.addWidget(self.move_down_btn)

        right_box = QHBoxLayout()
        right_box.setContentsMargins(0, 0, 0, 0)
        right_box.setSpacing(8)
        right_box.addWidget(self.pending_btn)
        right_box.addWidget(cancel_btn)
        right_box.addWidget(consignar_btn)

        bottom_row.addLayout(left_box, 1)
        bottom_row.addLayout(center_box, 1)
        bottom_row.addLayout(right_box, 1)
        layout.addLayout(bottom_row)

    def _load_rows(self) -> None:
        (
            self._all_rows,
            fabricantes,
            familias,
            subfamilias,
            self._prev_qty_by_articulo,
            self._pending_qty_by_articulo,
        ) = OrderQueryService().order_dialog_catalogs(self.almacen_id, self._preload_history)
        self._row_by_articulo = {
            str(getattr(row, "articulo_id", "") or "").strip(): row for row in self._all_rows if str(getattr(row, "articulo_id", "") or "").strip()
        }
        for articulo_id, qty in self._initial_qty_by_articulo.items():
            key = str(articulo_id or "").strip()
            if not key or key not in self._row_by_articulo:
                continue
            parsed_qty = float(qty or 0.0)
            if parsed_qty > 0:
                self._qty_by_articulo[key] = parsed_qty

        self.fabricante_filter.blockSignals(True)
        self.familia_filter.blockSignals(True)
        self.subfamilia_filter.blockSignals(True)
        self.fabricante_filter.clear()
        self.fabricante_filter.addItem("Fabricante (todos)", "")
        for row in fabricantes:
            fid = str(getattr(row, "fabricante_id", "") or "").strip()
            if fid:
                self.fabricante_filter.addItem(str(getattr(row, "fabricante_nombre", "") or "").strip() or fid, fid)
        self.familia_filter.clear()
        self.familia_filter.addItem("Familia (todas)", "")
        for row in familias:
            fid = str(getattr(row, "articulo_familia_id", "") or "").strip()
            if fid:
                self.familia_filter.addItem(str(getattr(row, "articulo_familia_nombre", "") or "").strip() or fid, fid)
        self.subfamilia_filter.clear()
        self.subfamilia_filter.addItem("Subfamilia (todas)", "")
        for row in subfamilias:
            sid = str(getattr(row, "articulo_subfamilia_id", "") or "").strip()
            if sid:
                self.subfamilia_filter.addItem(str(getattr(row, "articulo_subfamilia_nombre", "") or "").strip() or sid, sid)
        self.fabricante_filter.blockSignals(False)
        self.familia_filter.blockSignals(False)
        self.subfamilia_filter.blockSignals(False)
        self._render_rows()

    def _to_float(self, value: str) -> float:
        txt = str(value or "").strip()
        if not txt:
            return 0.0
        try:
            return float(txt.replace(",", "."))
        except Exception:
            return 0.0

    def _fmt(self, value: float, suffix: str = "") -> str:
        return f"{float(value):.2f}{suffix}"

    def _render_rows(self) -> None:
        fabricante_id = str(self.fabricante_filter.currentData() or "").strip()
        familia_id = str(self.familia_filter.currentData() or "").strip()
        subfamilia_id = str(self.subfamilia_filter.currentData() or "").strip()
        term = str(self.search_edit.text() or "").strip().lower()
        only_nonzero = bool(self.only_nonzero_check.isChecked())

        filtered: list[IngredienteIreks] = []
        for row in self._all_rows:
            rid = str(getattr(row, "articulo_id", "") or "").strip()
            if not rid:
                continue
            if fabricante_id and str(getattr(row, "fabricante_id", "") or "").strip() != fabricante_id:
                continue
            if familia_id and str(getattr(row, "articulo_familia_id", "") or "").strip() != familia_id:
                continue
            if subfamilia_id and str(getattr(row, "articulo_subfamilia_id", "") or "").strip() != subfamilia_id:
                continue
            ref = str(getattr(row, "articulo_referencia_corta", "") or "").strip() or str(getattr(row, "articulo_referencia", "") or "").strip()
            nombre = str(getattr(row, "articulo_descripcion", "") or "").strip()
            if term and term not in f"{ref} {nombre}".lower():
                continue
            uds = float(self._qty_by_articulo.get(rid, 0.0) or 0.0)
            if only_nonzero and uds == 0:
                continue
            filtered.append(row)

        self._loading_table = True
        self.table.setRowCount(len(filtered))
        for i, row in enumerate(filtered):
            articulo_id = str(getattr(row, "articulo_id", "") or "").strip()
            ref = str(getattr(row, "articulo_referencia_corta", "") or "").strip() or str(getattr(row, "articulo_referencia", "") or "").strip() or articulo_id
            nombre = str(getattr(row, "articulo_descripcion", "") or "").strip() or ref
            peso = float(getattr(row, "articulo_envase_peso_total", 0.0) or 0.0)
            prev_qty = float(self._prev_qty_by_articulo.get(articulo_id, 0.0) or 0.0)
            pending_qty = float(self._pending_qty_by_articulo.get(articulo_id, 0.0) or 0.0)
            uds = float(self._qty_by_articulo.get(articulo_id, 0.0) or 0.0)
            total_kg = peso * uds

            ref_item = QTableWidgetItem(ref)
            ref_item.setData(Qt.ItemDataRole.UserRole, articulo_id)
            nombre_item = QTableWidgetItem(nombre)
            peso_item = NumericTableWidgetItem(self._fmt(peso), peso)
            prev_item = NumericTableWidgetItem("" if prev_qty == 0 else self._fmt(prev_qty), prev_qty)
            pending_item = NumericTableWidgetItem("" if pending_qty == 0 else self._fmt(pending_qty), pending_qty)
            uds_item = NumericTableWidgetItem("" if uds == 0 else self._fmt(uds), uds)
            total_item = NumericTableWidgetItem(self._fmt(total_kg, " kg"), total_kg)

            peso_item.setFlags(peso_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            prev_item.setFlags(prev_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            pending_item.setFlags(pending_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            total_item.setFlags(total_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            ref_item.setFlags(ref_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            nombre_item.setFlags(nombre_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            peso_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            prev_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            pending_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            uds_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            total_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            prev_item.setBackground(QBrush(QColor("#E1E6EF")))
            pending_item.setBackground(QBrush(QColor("#E1E6EF")))
            if prev_qty != 0:
                prev_item.setForeground(QBrush(QColor("#1565C0")))
            if pending_qty != 0:
                pending_item.setForeground(QBrush(QColor("#C62828")))
            uds_item.setForeground(QBrush(QColor("#2E7D32")))
            total_item.setForeground(QBrush(QColor("#2E7D32")))

            self.table.setItem(i, 0, ref_item)
            self.table.setItem(i, 1, nombre_item)
            self.table.setItem(i, 2, peso_item)
            self.table.setItem(i, 3, uds_item)
            self.table.setItem(i, 4, total_item)
            self.table.setItem(i, 5, prev_item)
            self.table.setItem(i, 6, pending_item)
        self._loading_table = False
        self._update_totals_label()

    def _update_totals_label(self) -> None:
        total_uds = 0.0
        total_kg = 0.0
        for articulo_id, qty in self._qty_by_articulo.items():
            if qty <= 0:
                continue
            row = self._row_by_articulo.get(articulo_id)
            peso = float(getattr(row, "articulo_envase_peso_total", 0.0) or 0.0) if row else 0.0
            total_uds += qty
            total_kg += qty * peso
        self.totals_lbl.setText(f"Total Uds.: {self._fmt(total_uds)}    Total kg: {self._fmt(total_kg)}")

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._loading_table or item is None or item.column() != 3:
            return
        row_idx = item.row()
        ref_item = self.table.item(row_idx, 0)
        peso_item = self.table.item(row_idx, 2)
        total_item = self.table.item(row_idx, 4)
        articulo_id = str(ref_item.data(Qt.ItemDataRole.UserRole) or "").strip() if ref_item else ""
        if not articulo_id:
            return
        uds = self._to_float(item.text())
        if uds < 0:
            uds = 0.0
        peso = self._to_float(peso_item.text()) if peso_item else 0.0
        total_kg = uds * peso
        self._qty_by_articulo[articulo_id] = uds

        self._loading_table = True
        item.setText(self._fmt(uds))
        if total_item is not None:
            total_item.setText(self._fmt(total_kg, " kg"))
            total_item.setData(Qt.ItemDataRole.UserRole, total_kg)
        item.setData(Qt.ItemDataRole.UserRole, uds)
        self._loading_table = False
        self._update_totals_label()

    def _move_selection(self, step: int) -> None:
        rows = self.table.rowCount()
        if rows <= 0:
            return
        current_row = self.table.currentRow()
        if current_row < 0:
            target_row = 0 if step > 0 else rows - 1
        else:
            target_row = max(0, min(rows - 1, current_row + step))
        self.table.selectRow(target_row)
        self.table.setCurrentCell(target_row, 3)

    def _move_selection_up(self) -> None:
        self._move_selection(-1)

    def _move_selection_down(self) -> None:
        self._move_selection(1)

    def selected_lines(self) -> list[NewPedidoLine]:
        lines: list[NewPedidoLine] = []
        for articulo_id, qty in self._qty_by_articulo.items():
            uds = float(qty or 0.0)
            if uds <= 0:
                continue
            row = self._row_by_articulo.get(articulo_id)
            if row is None:
                continue
            ref = str(getattr(row, "articulo_referencia_corta", "") or "").strip() or str(getattr(row, "articulo_referencia", "") or "").strip() or articulo_id
            nombre = str(getattr(row, "articulo_descripcion", "") or "").strip() or ref
            peso = float(getattr(row, "articulo_envase_peso_total", 0.0) or 0.0)
            lines.append(
                NewPedidoLine(
                    articulo_id=articulo_id,
                    referencia=ref,
                    nombre=nombre,
                    peso=peso,
                    uds=uds,
                    total_kg=uds * peso,
                )
            )
        return sorted(lines, key=lambda x: (x.referencia, x.nombre))

    def pedido_fecha(self) -> date:
        value = self.fecha_edit.date().toPython()
        return value if isinstance(value, date) else date.today()

    def pedido_numero(self) -> str:
        return str(self.numero_edit.text() or "").strip()

    def _consignar(self) -> None:
        if not self.selected_lines():
            QMessageBox.warning(self, "Pedidos", "No hay líneas para consignar. Introduce Uds. > 0.")
            return
        self._submit_mode = "consignar"
        self.accept()

    def _save_pending(self) -> None:
        if not self.selected_lines():
            QMessageBox.warning(self, "Pedidos", "No hay líneas para guardar en pendiente. Introduce Uds. > 0.")
            return
        self._submit_mode = "pendiente"
        self.accept()

    def submit_mode(self) -> str:
        mode = str(self._submit_mode or "").strip().lower()
        return mode if mode in {"consignar", "pendiente"} else "consignar"


class OrdersPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.order_document_import_service = OrderDocumentImportService()
        self.order_export_service = OrderExportService()
        self.order_query_service = OrderQueryService()
        self.order_service = OrderService()
        self.orders_documents_import_ui_service = OrdersDocumentsImportUiService(
            order_document_import_service=self.order_document_import_service,
        )
        self.orders_mail_settings = OrdersMailSettingsService()
        self.rows: list[PedidoListRow] = []
        self._is_loading_details = False
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self.reload)
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.timeout.connect(self._autosave_selected_order)
        self._loading_pedido_items_table = False
        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        header = QLabel("Pedidos")
        header.setProperty("role", "pageTitle")
        layout.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, 1)

        left_panel = QWidget()
        left_panel.setObjectName("sidePanel")
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMinimumWidth(560)
        left_panel.setMaximumWidth(620)

        filters_row = QHBoxLayout()
        self.year_filter = QComboBox()
        self.year_filter.currentIndexChanged.connect(self.reload)
        self.month_from_filter = QComboBox()
        self.month_from_filter.currentIndexChanged.connect(self.reload)
        self.month_to_filter = QComboBox()
        self.month_to_filter.currentIndexChanged.connect(self.reload)
        self.almacen_filter = QComboBox()
        self.almacen_filter.currentIndexChanged.connect(self.reload)

        self.year_filter.setMinimumWidth(90)
        self.month_from_filter.setMinimumWidth(120)
        self.month_to_filter.setMinimumWidth(120)
        self.almacen_filter.setMinimumWidth(210)

        filters_row.addWidget(QLabel("Año"))
        filters_row.addWidget(self.year_filter)
        filters_row.addWidget(QLabel("Mes inicial"))
        filters_row.addWidget(self.month_from_filter)
        filters_row.addWidget(QLabel("Mes final"))
        filters_row.addWidget(self.month_to_filter)
        left_layout.addLayout(filters_row)

        almacen_row = QHBoxLayout()
        almacen_row.addWidget(QLabel("Cliente/Distribuidor"))
        almacen_row.addWidget(self.almacen_filter, 1)
        left_layout.addLayout(almacen_row)

        self.new_btn = QPushButton("Nuevo pedido")
        self.new_btn.setProperty("btnRole", "success")
        self.edit_btn = QPushButton("Editar")
        self.edit_btn.setProperty("btnRole", "warning")
        self.del_btn = QPushButton("Eliminar")
        self.del_btn.setProperty("btnRole", "danger")
        self.export_btn = QPushButton("Exportar")
        self.export_btn.setProperty("btnRole", "secondary")
        self.send_mail_btn = QPushButton("Enviar Outlook")
        self.send_mail_btn.setProperty("btnRole", "secondary")
        self.print_btn = QPushButton("Imprimir")
        self.print_btn.setProperty("btnRole", "secondary")

        self.new_btn.clicked.connect(self._new_order)
        self.edit_btn.clicked.connect(self._edit_order)
        self.del_btn.clicked.connect(self._delete_order)
        self.export_btn.clicked.connect(self._export_selected_order_to_excel)
        self.send_mail_btn.clicked.connect(self._send_selected_order_by_outlook)
        self.print_btn.clicked.connect(self._print_selected_order)

        left_ribbon = QFrame()
        left_ribbon.setObjectName("topRibbon")
        left_ribbon.setFrameShape(QFrame.Shape.StyledPanel)
        left_ribbon_layout = QHBoxLayout(left_ribbon)
        left_ribbon_layout.setContentsMargins(8, 6, 8, 6)
        left_ribbon_layout.setSpacing(6)
        left_ribbon_layout.addWidget(self.new_btn)
        left_ribbon_layout.addWidget(self.edit_btn)
        left_ribbon_layout.addWidget(self.del_btn)
        left_ribbon_layout.addWidget(self.export_btn)
        left_ribbon_layout.addWidget(self.send_mail_btn)
        left_ribbon_layout.addWidget(self.print_btn)
        left_ribbon_layout.addStretch(1)
        left_layout.addWidget(left_ribbon)

        self.table = QTableWidget(0, 6)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setStyleSheet("QTableWidget::item:focus { border: none; outline: 0; }")
        header_widget = self.table.horizontalHeader()
        header_widget.setSectionsClickable(True)
        header_widget.setMinimumSectionSize(40)
        header_widget.setStretchLastSection(False)
        header_widget.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        header_widget.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setHorizontalHeaderLabels(["Almacen", "Nº", "Fecha", "Semana", "Total Kg", "Estado"])
        estado_header_item = self.table.horizontalHeaderItem(5)
        if estado_header_item is not None:
            estado_header_item.setTextAlignment(int(Qt.AlignmentFlag.AlignCenter))
        self.table.setColumnWidth(0, 180)
        self.table.setColumnWidth(1, 60)
        self.table.setColumnWidth(2, 108)
        self.table.setColumnWidth(3, 60)
        self.table.setColumnWidth(4, 100)
        self.table.setColumnWidth(5, 55)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setSortingEnabled(True)
        self.table.itemSelectionChanged.connect(self._show_selected_details)
        left_layout.addWidget(self.table, 1)

        self.table_totals = QTableWidget(1, 6)
        self.table_totals.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table_totals.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_totals.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table_totals.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table_totals.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table_totals.verticalHeader().setVisible(False)
        self.table_totals.horizontalHeader().setVisible(False)
        self.table_totals.setFixedHeight(30)
        self.table_totals.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table_totals.setShowGrid(False)
        left_layout.addWidget(self.table_totals)

        splitter.addWidget(left_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        self.import_albaran_btn = QPushButton("Imp. Albarán")
        self.import_albaran_btn.setProperty("btnRole", "warning")
        self.import_albaran_btn.setFixedHeight(24)
        self.import_albaran_btn.setEnabled(False)
        self.import_albaran_btn.clicked.connect(self._import_albaran_for_selected_order)
        self.import_factura_btn = QPushButton("Imp. Factura")
        self.import_factura_btn.setProperty("btnRole", "warning")
        self.import_factura_btn.setFixedHeight(24)
        self.import_factura_btn.setEnabled(False)
        self.import_factura_btn.clicked.connect(self._import_factura_for_selected_order)
        self.delete_factura_btn = QPushButton("Eliminar Factura")
        self.delete_factura_btn.setProperty("btnRole", "danger")
        self.delete_factura_btn.setFixedHeight(24)
        self.delete_factura_btn.setEnabled(False)
        self.delete_factura_btn.clicked.connect(self._delete_selected_factura)
        self.edit_factura_line_btn = QPushButton("Editar línea")
        self.edit_factura_line_btn.setProperty("btnRole", "primary")
        self.edit_factura_line_btn.setFixedHeight(24)
        self.edit_factura_line_btn.setEnabled(False)
        self.edit_factura_line_btn.clicked.connect(self._edit_factura_line)
        self.add_line_btn = QPushButton("Añadir")
        self.add_line_btn.setProperty("btnRole", "success")
        self.add_line_btn.setFixedHeight(24)
        self.add_line_btn.clicked.connect(self._add_order_line)
        self.edit_line_btn = QPushButton("Editar")
        self.edit_line_btn.setProperty("btnRole", "warning")
        self.edit_line_btn.setFixedHeight(24)
        self.edit_line_btn.clicked.connect(self._edit_order_line)
        self.del_line_btn = QPushButton("Eliminar")
        self.del_line_btn.setProperty("btnRole", "danger")
        self.del_line_btn.setFixedHeight(24)
        self.del_line_btn.clicked.connect(self._delete_order_line)
        self.edit_order_btn = QPushButton("Editar pedido")
        self.edit_order_btn.setProperty("btnRole", "warning")
        self.edit_order_btn.setFixedHeight(24)
        self.edit_order_btn.clicked.connect(self._edit_order)

        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_layout.addWidget(right_splitter, 1)

        detail_panel = QWidget()
        detail_panel.setObjectName("detailPanel")
        detail_panel.setMaximumHeight(170)
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(14, 14, 14, 14)
        detail_layout.setSpacing(8)

        detail_title = QLabel("Detalle del pedido")
        detail_title.setProperty("role", "sectionTitle")
        detail_layout.addWidget(detail_title)

        row_1 = QHBoxLayout()
        row_1.addWidget(QLabel("Semana"))
        self.detail_semana = QLineEdit()
        self.detail_semana.setReadOnly(True)
        self.detail_semana.setMinimumWidth(50)
        self.detail_semana.setMaximumWidth(50)
        row_1.addWidget(self.detail_semana)

        row_1.addWidget(QLabel("Fecha"))
        self.detail_fecha = QDateEdit()
        self.detail_fecha.setCalendarPopup(True)
        self.detail_fecha.setDisplayFormat("dd/MM/yyyy")
        self.detail_fecha.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_fecha.setMinimumWidth(130)
        row_1.addWidget(self.detail_fecha)

        row_1.addWidget(QLabel("Numero"))
        self.detail_pedido_numero = QLineEdit()
        self.detail_pedido_numero.setMinimumWidth(100)
        self.detail_pedido_numero.setMaximumWidth(100)
        row_1.addWidget(self.detail_pedido_numero)

        row_1.addStretch(1)
        detail_layout.addLayout(row_1)
        self.detail_fecha.dateChanged.connect(lambda _d: self._schedule_autosave())
        self.detail_pedido_numero.textEdited.connect(self._schedule_autosave)
        right_splitter.addWidget(detail_panel)

        tabs_panel = QWidget()
        tabs_layout = QVBoxLayout(tabs_panel)
        tabs_layout.setContentsMargins(0, 0, 0, 0)
        tabs_layout.setSpacing(0)
        tabs = QTabWidget()

        pedido_tab = QWidget()
        pedido_tab_layout = QVBoxLayout(pedido_tab)
        pedido_tab_layout.setContentsMargins(8, 8, 8, 8)
        pedido_tab_layout.setSpacing(6)
        pedido_actions_ribbon = QFrame()
        pedido_actions_ribbon.setObjectName("topRibbon")
        pedido_actions_ribbon.setFrameShape(QFrame.Shape.StyledPanel)
        pedido_actions_layout = QHBoxLayout(pedido_actions_ribbon)
        pedido_actions_layout.setContentsMargins(8, 6, 8, 6)
        pedido_actions_layout.setSpacing(6)
        pedido_actions_layout.addWidget(self.add_line_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        pedido_actions_layout.addWidget(self.edit_line_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        pedido_actions_layout.addWidget(self.del_line_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        pedido_actions_layout.addWidget(self.edit_order_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        pedido_actions_layout.addStretch(1)
        pedido_tab_layout.addWidget(pedido_actions_ribbon)
        self.pedido_items_table = QTableWidget(0, 4)
        self.pedido_items_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.pedido_items_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.pedido_items_table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed | QAbstractItemView.EditTrigger.SelectedClicked)
        self.pedido_items_table.verticalHeader().setVisible(False)
        self.pedido_items_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.pedido_items_table.setStyleSheet("QTableWidget::item:focus { border: none; outline: 0; }")
        self.pedido_items_table.itemChanged.connect(self._on_pedido_item_cell_changed)
        items_header = self.pedido_items_table.horizontalHeader()
        items_header.setSectionsClickable(True)
        items_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        items_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        items_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        items_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.pedido_items_table.setHorizontalHeaderLabels(["Cod.", "Nombre", "Cantidad", "Kg"])
        self.pedido_items_table.setColumnWidth(0, 95)
        self.pedido_items_table.setColumnWidth(2, 90)
        self.pedido_items_table.setColumnWidth(3, 100)
        self.pedido_items_table.setSortingEnabled(True)
        pedido_tab_layout.addWidget(self.pedido_items_table, 1)
        self.pedido_items_totals_table = QTableWidget(1, 4)
        self.pedido_items_totals_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.pedido_items_totals_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.pedido_items_totals_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.pedido_items_totals_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.pedido_items_totals_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.pedido_items_totals_table.verticalHeader().setVisible(False)
        self.pedido_items_totals_table.horizontalHeader().setVisible(False)
        pedido_totals_header = self.pedido_items_totals_table.horizontalHeader()
        pedido_totals_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        pedido_totals_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        pedido_totals_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        pedido_totals_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.pedido_items_totals_table.setFixedHeight(30)
        self.pedido_items_totals_table.setColumnWidth(0, 95)
        self.pedido_items_totals_table.setColumnWidth(2, 90)
        self.pedido_items_totals_table.setColumnWidth(3, 100)
        pedido_tab_layout.addWidget(self.pedido_items_totals_table)
        tabs.addTab(pedido_tab, "Pedido")

        albaran_tab = QWidget()
        albaran_tab_layout = QVBoxLayout(albaran_tab)
        albaran_tab_layout.setContentsMargins(8, 8, 8, 8)
        albaran_tab_layout.setSpacing(6)
        albaran_actions_ribbon = QFrame()
        albaran_actions_ribbon.setObjectName("topRibbon")
        albaran_actions_ribbon.setFrameShape(QFrame.Shape.StyledPanel)
        albaran_actions_layout = QHBoxLayout(albaran_actions_ribbon)
        albaran_actions_layout.setContentsMargins(8, 6, 8, 6)
        albaran_actions_layout.setSpacing(6)
        albaran_actions_layout.addWidget(self.import_albaran_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        albaran_actions_layout.addStretch(1)
        albaran_tab_layout.addWidget(albaran_actions_ribbon)
        albaran_filter_row = QHBoxLayout()
        albaran_filter_row.addWidget(QLabel("Albaran"))
        self.albaran_selector = QComboBox()
        self.albaran_selector.currentIndexChanged.connect(self._on_albaran_selector_changed)
        albaran_filter_row.addWidget(self.albaran_selector, 1)
        albaran_tab_layout.addLayout(albaran_filter_row)

        self.albaran_items_table = QTableWidget(0, 5)
        self.albaran_items_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.albaran_items_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.albaran_items_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.albaran_items_table.verticalHeader().setVisible(False)
        self.albaran_items_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.albaran_items_table.setStyleSheet("QTableWidget::item:focus { border: none; outline: 0; }")
        self.albaran_items_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.albaran_items_table.customContextMenuRequested.connect(self._show_albaran_items_context_menu)
        albaran_items_header = self.albaran_items_table.horizontalHeader()
        albaran_items_header.setSectionsClickable(True)
        albaran_items_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        albaran_items_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        albaran_items_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        albaran_items_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        albaran_items_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.albaran_items_table.setHorizontalHeaderLabels(["Cod.", "Nº albarán", "Nombre", "Cantidad", "Kg"])
        self.albaran_items_table.setColumnWidth(0, 95)
        self.albaran_items_table.setColumnWidth(1, 120)
        self.albaran_items_table.setColumnWidth(3, 90)
        self.albaran_items_table.setColumnWidth(4, 100)
        self.albaran_items_table.setSortingEnabled(True)
        albaran_tab_layout.addWidget(self.albaran_items_table, 1)
        self.albaran_items_totals_table = QTableWidget(1, 5)
        self.albaran_items_totals_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.albaran_items_totals_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.albaran_items_totals_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.albaran_items_totals_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.albaran_items_totals_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.albaran_items_totals_table.verticalHeader().setVisible(False)
        self.albaran_items_totals_table.horizontalHeader().setVisible(False)
        albaran_totals_header = self.albaran_items_totals_table.horizontalHeader()
        albaran_totals_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        albaran_totals_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        albaran_totals_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        albaran_totals_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        albaran_totals_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.albaran_items_totals_table.setFixedHeight(30)
        self.albaran_items_totals_table.setColumnWidth(0, 95)
        self.albaran_items_totals_table.setColumnWidth(1, 120)
        self.albaran_items_totals_table.setColumnWidth(3, 90)
        self.albaran_items_totals_table.setColumnWidth(4, 100)
        albaran_tab_layout.addWidget(self.albaran_items_totals_table)
        tabs.addTab(albaran_tab, "Albarán")

        factura_tab = QWidget()
        factura_tab_layout = QVBoxLayout(factura_tab)
        factura_tab_layout.setContentsMargins(8, 8, 8, 8)
        factura_tab_layout.setSpacing(6)
        factura_actions_ribbon = QFrame()
        factura_actions_ribbon.setObjectName("topRibbon")
        factura_actions_ribbon.setFrameShape(QFrame.Shape.StyledPanel)
        factura_actions_layout = QHBoxLayout(factura_actions_ribbon)
        factura_actions_layout.setContentsMargins(8, 6, 8, 6)
        factura_actions_layout.setSpacing(6)
        factura_actions_layout.addWidget(self.import_factura_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        factura_actions_layout.addWidget(self.edit_factura_line_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        factura_actions_layout.addWidget(self.delete_factura_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        factura_actions_layout.addStretch(1)
        factura_tab_layout.addWidget(factura_actions_ribbon)
        factura_content = QSplitter(Qt.Orientation.Horizontal)
        factura_content.setChildrenCollapsible(False)

        self.facturas_table = QTableWidget(0, 1)
        self.facturas_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.facturas_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.facturas_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.facturas_table.verticalHeader().setVisible(False)
        self.facturas_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.facturas_table.setStyleSheet("QTableWidget::item:focus { border: none; outline: 0; }")
        facturas_header = self.facturas_table.horizontalHeader()
        facturas_header.setSectionsClickable(True)
        facturas_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.facturas_table.setHorizontalHeaderLabels(["Factura"])
        self.facturas_table.setFixedWidth(120)
        self.facturas_table.setSortingEnabled(True)
        self.facturas_table.itemSelectionChanged.connect(self._on_factura_selection_changed)
        factura_content.addWidget(self.facturas_table)

        factura_items_panel = QWidget()
        factura_items_layout = QVBoxLayout(factura_items_panel)
        factura_items_layout.setContentsMargins(0, 0, 0, 0)
        factura_items_layout.setSpacing(0)

        self.factura_items_table = QTableWidget(0, 5)
        self.factura_items_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.factura_items_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.factura_items_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.factura_items_table.verticalHeader().setVisible(False)
        self.factura_items_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.factura_items_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.factura_items_table.setStyleSheet("QTableWidget::item:focus { border: none; outline: 0; }")
        factura_items_header = self.factura_items_table.horizontalHeader()
        factura_items_header.setSectionsClickable(True)
        factura_items_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        factura_items_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        factura_items_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        factura_items_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        factura_items_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.factura_items_table.setHorizontalHeaderLabels(["Cod.", "Nombre", "Uds.", "Kg/Lit.", "Precio"])
        self.factura_items_table.setColumnWidth(0, 86)
        self.factura_items_table.setColumnWidth(2, 60)
        self.factura_items_table.setColumnWidth(3, 78)
        self.factura_items_table.setColumnWidth(4, 82)
        self.factura_items_table.setSortingEnabled(True)
        self.factura_items_table.itemSelectionChanged.connect(
            lambda: self.edit_factura_line_btn.setEnabled(bool(self._selected_factura_item_id()))
        )
        self.factura_items_table.itemDoubleClicked.connect(lambda _item: self._edit_factura_line())
        factura_items_layout.addWidget(self.factura_items_table, 1)
        self.factura_items_totals_table = QTableWidget(1, 5)
        self.factura_items_totals_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.factura_items_totals_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.factura_items_totals_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.factura_items_totals_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.factura_items_totals_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.factura_items_totals_table.verticalHeader().setVisible(False)
        self.factura_items_totals_table.horizontalHeader().setVisible(False)
        factura_totals_header = self.factura_items_totals_table.horizontalHeader()
        factura_totals_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        factura_totals_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        factura_totals_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        factura_totals_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        factura_totals_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.factura_items_totals_table.setFixedHeight(30)
        self.factura_items_totals_table.setColumnWidth(0, 86)
        self.factura_items_totals_table.setColumnWidth(2, 60)
        self.factura_items_totals_table.setColumnWidth(3, 78)
        self.factura_items_totals_table.setColumnWidth(4, 82)
        factura_items_layout.addWidget(self.factura_items_totals_table)
        factura_content.addWidget(factura_items_panel)
        factura_content.setStretchFactor(0, 0)
        factura_content.setStretchFactor(1, 1)
        factura_content.setSizes([120, 920])
        factura_content.setHandleWidth(0)
        factura_content.handle(1).setEnabled(False)
        factura_tab_layout.addWidget(factura_content, 1)
        tabs.addTab(factura_tab, "Factura")

        pendientes_tab = QWidget()
        pendientes_tab_layout = QVBoxLayout(pendientes_tab)
        pendientes_tab_layout.setContentsMargins(8, 8, 8, 8)
        pendientes_tab_layout.setSpacing(6)
        self.pendientes_table = QTableWidget(0, 6)
        self.pendientes_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.pendientes_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.pendientes_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.pendientes_table.verticalHeader().setVisible(False)
        self.pendientes_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.pendientes_table.setStyleSheet("QTableWidget::item:focus { border: none; outline: 0; }")
        pendientes_header = self.pendientes_table.horizontalHeader()
        pendientes_header.setSectionsClickable(True)
        pendientes_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        pendientes_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        pendientes_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        pendientes_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        pendientes_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        pendientes_header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.pendientes_table.setHorizontalHeaderLabels(["Cod.", "Nombre", "Pedida", "Recibida", "Pendiente", "Estado"])
        self.pendientes_table.setColumnWidth(0, 95)
        self.pendientes_table.setColumnWidth(2, 90)
        self.pendientes_table.setColumnWidth(3, 90)
        self.pendientes_table.setColumnWidth(4, 100)
        self.pendientes_table.setColumnWidth(5, 90)
        pendientes_tab_layout.addWidget(self.pendientes_table, 1)
        tabs.addTab(pendientes_tab, "Pendientes")
        tabs_layout.addWidget(tabs)
        right_splitter.addWidget(tabs_panel)
        right_splitter.setStretchFactor(0, 0)
        right_splitter.setStretchFactor(1, 10)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([580, 660])
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(0)
        splitter.handle(1).setEnabled(False)

    def _try_parse_date(self, value) -> date | None:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value

        if value is not None:
            as_text = str(value).strip()
            if re.fullmatch(r"\d+([.,]\d+)?", as_text):
                try:
                    serial = float(as_text.replace(",", "."))
                    if serial > 0:
                        # Serie Excel (base 1899-12-30)
                        return datetime.fromordinal(date(1899, 12, 30).toordinal() + int(serial)).date()
                except Exception:
                    pass

            # Objetos tipo pandas/openpyxl con conversor a datetime.
            to_py = getattr(value, "to_pydatetime", None)
            if callable(to_py):
                try:
                    dt = to_py()
                    if isinstance(dt, datetime):
                        return dt.date()
                except Exception:
                    pass

        text_value = str(value or "").strip()
        for fmt in (
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%Y/%m/%d",
            "%d.%m.%Y",
            "%d/%m/%y",
            "%d-%m-%y",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
        ):
            try:
                return datetime.strptime(text_value, fmt).date()
            except Exception:
                continue
        return None

    def _parse_date(self, value) -> date:
        parsed = self._try_parse_date(value)
        if parsed is not None:
            return parsed
        return date.today()

    def _load_almacen_filter(self, _session: Any | None = None) -> None:
        current = str(self.almacen_filter.currentData() or "")
        options = self.order_query_service.warehouse_filter_options()
        self.almacen_filter.blockSignals(True)
        self.almacen_filter.clear()
        for option in options:
            self.almacen_filter.addItem(option.label, option.value)
        idx = self.almacen_filter.findData(current)
        self.almacen_filter.setCurrentIndex(idx if idx >= 0 else 0)
        self.almacen_filter.blockSignals(False)

    def _load_period_filters(self, pedidos: list[Pedido]) -> None:
        current_year = str(self.year_filter.currentData() or "")
        current_from = int(self.month_from_filter.currentData() or 0)
        current_to = int(self.month_to_filter.currentData() or 0)
        default_year = str(date.today().year)
        default_from = 1
        default_to = 12

        years = sorted({int(self._parse_date(row.pedido_fecha).year) for row in pedidos}, reverse=True)
        if default_year not in {str(y) for y in years}:
            years = sorted({*years, int(default_year)}, reverse=True)
        self.year_filter.blockSignals(True)
        self.year_filter.clear()
        self.year_filter.addItem("Todos", "")
        for year in years:
            self.year_filter.addItem(str(year), str(year))
        selected_year = current_year or default_year
        idx = self.year_filter.findData(selected_year)
        self.year_filter.setCurrentIndex(idx if idx >= 0 else 0)
        self.year_filter.blockSignals(False)

        self.month_from_filter.blockSignals(True)
        self.month_to_filter.blockSignals(True)
        self.month_from_filter.clear()
        self.month_to_filter.clear()
        self.month_from_filter.addItem("Todos", 0)
        self.month_to_filter.addItem("Todos", 0)
        for month_num, month_name in MONTHS:
            self.month_from_filter.addItem(month_name, month_num)
            self.month_to_filter.addItem(month_name, month_num)
        selected_from = current_from if current_from != 0 else default_from
        selected_to = current_to if current_to != 0 else default_to
        idx = self.month_from_filter.findData(selected_from)
        self.month_from_filter.setCurrentIndex(idx if idx >= 0 else 0)
        idx = self.month_to_filter.findData(selected_to)
        self.month_to_filter.setCurrentIndex(idx if idx >= 0 else 0)
        self.month_from_filter.blockSignals(False)
        self.month_to_filter.blockSignals(False)

    def _reload_pedido_items_table(self, pedido_id: str | None) -> None:
        self._loading_pedido_items_table = True
        header = self.pedido_items_table.horizontalHeader()
        sort_col = header.sortIndicatorSection()
        sort_order = header.sortIndicatorOrder()
        was_sorting = self.pedido_items_table.isSortingEnabled()
        self.pedido_items_table.setSortingEnabled(False)
        self.pedido_items_table.setRowCount(0)
        if not pedido_id:
            self.pedido_items_table.setSortingEnabled(was_sorting)
            self._set_pedido_items_totals(0.0, 0.0)
            self._loading_pedido_items_table = False
            return
        rows, pending_article_ids = self.order_query_service.list_order_items(pedido_id)
        self.pedido_items_table.setRowCount(len(rows))
        total_cantidad = 0.0
        total_kg = 0.0
        for row_idx, (item, article) in enumerate(rows):
            cantidad = float(getattr(item, "articulo_cantidad", 0.0) or 0.0)
            peso_total = float(getattr(article, "articulo_envase_peso_total", 0.0) or 0.0) if article else 0.0
            kg = cantidad * peso_total
            total_cantidad += cantidad
            total_kg += kg
            cod = str(getattr(article, "articulo_referencia_corta", "") or "").strip() if article else ""
            nombre = str(getattr(article, "articulo_descripcion", "") or "").strip() if article else ""
            if not cod:
                cod = str(getattr(item, "articulo_id", "") or "").strip()
            if not nombre:
                nombre = cod
            values = [
                cod,
                nombre,
                self._format_number_es(cantidad, 2),
                self._format_number_es(kg, 2, " kg"),
            ]
            for col_idx, value in enumerate(values):
                if col_idx == 2:
                    cell = NumericTableWidgetItem(value, cantidad)
                elif col_idx == 3:
                    cell = NumericTableWidgetItem(value, kg)
                else:
                    cell = QTableWidgetItem(value)
                if col_idx == 0 and not isinstance(cell, NumericTableWidgetItem):
                    cell.setData(Qt.ItemDataRole.UserRole, str(getattr(item, "item_id", "") or "").strip())
                if col_idx == 0 and self._is_article_pending(article):
                    cell.setForeground(QBrush(QColor("#c62828")))
                if str(getattr(item, "articulo_id", "") or "").strip() in pending_article_ids:
                    cell.setForeground(QBrush(QColor("#c62828")))
                if col_idx in (2, 3):
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if col_idx == 2:
                    cell.setFlags(cell.flags() | Qt.ItemFlag.ItemIsEditable)
                else:
                    cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.pedido_items_table.setItem(row_idx, col_idx, cell)
        self.pedido_items_table.setSortingEnabled(was_sorting)
        if was_sorting:
            self.pedido_items_table.sortItems(sort_col if sort_col >= 0 else 0, sort_order if sort_col >= 0 else Qt.SortOrder.AscendingOrder)
        self._set_pedido_items_totals(total_cantidad, total_kg)
        self._loading_pedido_items_table = False

    def _on_pedido_item_cell_changed(self, item: QTableWidgetItem) -> None:
        if self._loading_pedido_items_table:
            return
        if item is None or item.column() != 2:
            return
        row_idx = item.row()
        id_cell = self.pedido_items_table.item(row_idx, 0)
        item_id = str(id_cell.data(Qt.ItemDataRole.UserRole) or "").strip() if id_cell else ""
        if not item_id:
            return
        qty_text = str(item.text() or "").strip()
        qty = self._parse_float(qty_text, default=-1.0)
        if qty < 0:
            QMessageBox.warning(self, "Pedidos", "Cantidad no válida.")
            self.reload()
            return
        self.order_service.update_order_line_quantity(item_id, qty)
        self.reload()

    def _add_order_line(self) -> None:
        selected = self._selected_row()
        if selected is None:
            QMessageBox.warning(self, "Pedidos", "Selecciona un pedido.")
            return
        dialog = AddPedidoLineDialog(parent=self)
        if not dialog.exec():
            return
        chosen = dialog.selected_article()
        if not chosen:
            QMessageBox.warning(self, "Pedidos", "Selecciona un producto.")
            return
        articulo_id, _cod, _nombre = chosen
        try:
            self.order_service.add_order_line(selected.pedido_id, articulo_id)
        except Exception as exc:
            QMessageBox.warning(self, "Pedidos", str(exc))
            return
        self.reload()
        self._select_by_id(selected.pedido_id)
        self._show_selected_details()

    def _edit_order_line(self) -> None:
        selected_order = self._selected_row()
        if selected_order is None:
            QMessageBox.warning(self, "Pedidos", "Selecciona un pedido.")
            return
        selected_rows = self.pedido_items_table.selectionModel().selectedRows() if self.pedido_items_table.selectionModel() else []
        if not selected_rows:
            QMessageBox.warning(self, "Pedidos", "Selecciona una línea para editar.")
            return
        row_idx = selected_rows[0].row()
        id_cell = self.pedido_items_table.item(row_idx, 0)
        item_id = str(id_cell.data(Qt.ItemDataRole.UserRole) or "").strip() if id_cell else ""
        if not item_id:
            QMessageBox.warning(self, "Pedidos", "No se pudo editar la línea seleccionada.")
            return
        try:
            current_articulo_id, current_qty = self.order_service.get_order_line_payload(item_id)
        except Exception as exc:
            QMessageBox.warning(self, "Pedidos", str(exc))
            return

        dialog = EditPedidoLineDialog(
            articulo_id=current_articulo_id,
            cantidad=current_qty,
            parent=self,
        )
        if not dialog.exec():
            return
        new_articulo_id, new_qty = dialog.payload()
        try:
            self.order_service.update_order_line(item_id, new_articulo_id, new_qty)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Pedidos", f"No se pudo editar la línea.\n{exc}")
            return
        self.reload()
        self._select_by_id(selected_order.pedido_id)
        self._show_selected_details()

    def _delete_order_line(self) -> None:
        selected_order = self._selected_row()
        if selected_order is None:
            QMessageBox.warning(self, "Pedidos", "Selecciona un pedido.")
            return
        selected_rows = self.pedido_items_table.selectionModel().selectedRows() if self.pedido_items_table.selectionModel() else []
        if not selected_rows:
            QMessageBox.warning(self, "Pedidos", "Selecciona una línea para eliminar.")
            return
        row_idx = selected_rows[0].row()
        id_cell = self.pedido_items_table.item(row_idx, 0)
        item_id = str(id_cell.data(Qt.ItemDataRole.UserRole) or "").strip() if id_cell else ""
        if not item_id:
            QMessageBox.warning(self, "Pedidos", "No se pudo identificar la línea seleccionada.")
            return
        answer = QMessageBox.question(self, "Confirmar", "Eliminar línea seleccionada?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.order_service.delete_order_line(item_id)
        self.reload()
        self._select_by_id(selected_order.pedido_id)
        self._show_selected_details()

    def _load_albaran_selector(self, pedido_id: str | None) -> None:
        self.albaran_selector.blockSignals(True)
        self.albaran_selector.clear()
        self.albaran_selector.addItem("Todos", "")
        if pedido_id:
            rows = self.order_query_service.list_albaranes(pedido_id)
            for row in rows:
                albaran_id = str(getattr(row, "albaran_id", "") or "").strip()
                if not albaran_id:
                    continue
                numero = str(getattr(row, "albaran_numero", "") or "").strip()
                fecha = self._parse_date(getattr(row, "albaran_fecha", None))
                label = f"{numero} ({fecha.strftime('%d/%m/%Y')})" if numero else fecha.strftime("%d/%m/%Y")
                self.albaran_selector.addItem(label, albaran_id)
        self.albaran_selector.setCurrentIndex(0)
        self.albaran_selector.blockSignals(False)

    def _reload_albaran_items_table(self, pedido_id: str | None, albaran_id: str | None = None) -> None:
        header = self.albaran_items_table.horizontalHeader()
        sort_col = header.sortIndicatorSection()
        sort_order = header.sortIndicatorOrder()
        was_sorting = self.albaran_items_table.isSortingEnabled()
        self.albaran_items_table.setSortingEnabled(False)
        self.albaran_items_table.setRowCount(0)
        if not pedido_id:
            self._set_albaran_items_totals(0.0, 0.0)
            self.albaran_items_table.setSortingEnabled(was_sorting)
            return
        clean_albaran_id = str(albaran_id or "").strip()
        self.order_document_import_service.repair_albaran_item_mappings_for_order(pedido_id, clean_albaran_id)
        rows, excess_article_ids = self.order_query_service.list_albaran_items(pedido_id, clean_albaran_id)
        self.albaran_items_table.setRowCount(len(rows))
        total_cantidad = 0.0
        total_kg = 0.0
        for row_idx, (item, article) in enumerate(rows):
            cantidad = float(getattr(item, "articulo_cantidad", 0.0) or 0.0)
            peso_total = float(getattr(article, "articulo_envase_peso_total", 0.0) or 0.0) if article else 0.0
            kg = cantidad * peso_total
            total_cantidad += cantidad
            total_kg += kg
            cod = str(getattr(article, "articulo_referencia_corta", "") or "").strip() if article else ""
            nombre = str(getattr(article, "articulo_descripcion", "") or "").strip() if article else ""
            if not cod:
                cod = str(getattr(item, "articulo_codigo", "") or "").strip()
            if not cod:
                cod = str(getattr(item, "articulo_id", "") or "").strip()
            if not nombre:
                nombre = cod
            values = [
                cod,
                str(getattr(item, "albaran_numero", "") or "").strip(),
                nombre,
                self._format_number_es(cantidad, 2),
                self._format_number_es(kg, 2, " kg"),
            ]
            for col_idx, value in enumerate(values):
                if col_idx == 3:
                    cell = NumericTableWidgetItem(value, cantidad)
                elif col_idx == 4:
                    cell = NumericTableWidgetItem(value, kg)
                else:
                    cell = QTableWidgetItem(value)
                if col_idx == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, str(getattr(item, "item_id", "") or "").strip())
                if col_idx == 0 and self._is_article_pending(article):
                    cell.setForeground(QBrush(QColor("#c62828")))
                if str(getattr(item, "articulo_id", "") or "").strip() in excess_article_ids:
                    cell.setForeground(QBrush(QColor("#2e7d32")))
                if col_idx in (3, 4):
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.albaran_items_table.setItem(row_idx, col_idx, cell)
        self.albaran_items_table.setSortingEnabled(was_sorting)
        if was_sorting:
            self.albaran_items_table.sortItems(
                sort_col if sort_col >= 0 else 1,
                sort_order if sort_col >= 0 else Qt.SortOrder.DescendingOrder,
            )
        self._set_albaran_items_totals(total_cantidad, total_kg)

    def _on_albaran_selector_changed(self, _index: int) -> None:
        selected = self._selected_row()
        pedido_id = str(getattr(selected, "pedido_id", "") or "").strip() if selected else ""
        albaran_id = str(self.albaran_selector.currentData() or "").strip()
        self._reload_albaran_items_table(pedido_id, albaran_id)

    def _load_factura_selector(self, pedido_id: str | None) -> None:
        header = self.facturas_table.horizontalHeader()
        sort_col = header.sortIndicatorSection()
        sort_order = header.sortIndicatorOrder()
        was_sorting = self.facturas_table.isSortingEnabled()
        self.facturas_table.blockSignals(True)
        self.facturas_table.setSortingEnabled(False)
        self.facturas_table.setRowCount(0)
        rows: list[Factura] = []
        if pedido_id:
            rows = self.order_document_import_service.list_facturas(pedido_id)
        self.facturas_table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            factura_id = str(getattr(row, "factura_id", "") or "").strip()
            numero = str(getattr(row, "factura_numero", "") or "").strip()
            cell = QTableWidgetItem(numero or factura_id)
            cell.setData(Qt.ItemDataRole.UserRole, factura_id)
            self.facturas_table.setItem(row_idx, 0, cell)
        self.facturas_table.setSortingEnabled(was_sorting)
        if was_sorting and rows:
            self.facturas_table.sortItems(
                sort_col if sort_col >= 0 else 1,
                sort_order if sort_col >= 0 else Qt.SortOrder.DescendingOrder,
            )
        if rows:
            self.facturas_table.selectRow(0)
        self.facturas_table.blockSignals(False)
        self.delete_factura_btn.setEnabled(bool(self._selected_factura_id()))
        self.edit_factura_line_btn.setEnabled(False)

    def _selected_factura_id(self) -> str:
        if not hasattr(self, "facturas_table") or self.facturas_table.selectionModel() is None:
            return ""
        selected = self.facturas_table.selectionModel().selectedRows()
        if not selected:
            return ""
        id_item = self.facturas_table.item(selected[0].row(), 0)
        return str(id_item.data(Qt.ItemDataRole.UserRole) or "").strip() if id_item else ""

    def _selected_factura_item_id(self) -> str:
        if not hasattr(self, "factura_items_table") or self.factura_items_table.selectionModel() is None:
            return ""
        selected = self.factura_items_table.selectionModel().selectedRows()
        if not selected:
            return ""
        id_item = self.factura_items_table.item(selected[0].row(), 0)
        return str(id_item.data(Qt.ItemDataRole.UserRole) or "").strip() if id_item else ""

    def _reload_factura_items_table(self, pedido_id: str | None, factura_id: str | None = None) -> None:
        header = self.factura_items_table.horizontalHeader()
        sort_col = header.sortIndicatorSection()
        sort_order = header.sortIndicatorOrder()
        was_sorting = self.factura_items_table.isSortingEnabled()
        self.factura_items_table.setSortingEnabled(False)
        self.factura_items_table.setRowCount(0)
        self.edit_factura_line_btn.setEnabled(False)
        if not pedido_id:
            self._set_factura_items_totals(0.0, 0.0, 0.0)
            self.factura_items_table.setSortingEnabled(was_sorting)
            return
        rows, price_discrepancy_by_item = self.order_document_import_service.list_factura_items(
            pedido_id,
            str(factura_id or "").strip(),
        )
        self.factura_items_table.setRowCount(len(rows))
        total_cantidad = 0.0
        total_kg = 0.0
        total_importe = 0.0
        for row_idx, (item, article) in enumerate(rows):
            cantidad = float(getattr(item, "articulo_cantidad", 0.0) or 0.0)
            kg = float(getattr(item, "articulo_kilos", 0.0) or 0.0)
            precio = float(getattr(item, "precio_unitario", 0.0) or 0.0)
            dto = float(getattr(item, "dto_pct", 20.0) or 0.0)
            total_linea = float(getattr(item, "total_linea", 0.0) or 0.0)
            total_cantidad += cantidad
            total_kg += kg
            total_importe += total_linea
            item_id = str(getattr(item, "item_id", "") or "").strip()
            cod = str(getattr(article, "articulo_referencia_corta", "") or "").strip() if article else ""
            nombre = str(getattr(article, "articulo_descripcion", "") or "").strip() if article else ""
            if not cod:
                cod = str(getattr(item, "articulo_codigo", "") or "").strip()
            if not cod:
                cod = str(getattr(item, "articulo_id", "") or "").strip()
            if not nombre:
                nombre = str(getattr(item, "articulo_descripcion", "") or "").strip() or cod
            values = [
                cod,
                nombre,
                self._format_number_es(cantidad, 2),
                self._format_number_es(kg, 2),
                self._format_number_es(precio, 2),
            ]
            for col_idx, value in enumerate(values):
                if col_idx == 2:
                    cell = NumericTableWidgetItem(value, cantidad)
                elif col_idx == 3:
                    cell = NumericTableWidgetItem(value, kg)
                elif col_idx == 4:
                    cell = NumericTableWidgetItem(value, precio)
                else:
                    cell = QTableWidgetItem(value)
                if col_idx == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, item_id)
                if col_idx == 0 and self._is_article_pending(article):
                    cell.setForeground(QBrush(QColor("#c62828")))
                if col_idx == 4 and price_discrepancy_by_item.get(item_id, False):
                    cell.setForeground(QBrush(QColor("#c62828")))
                if col_idx in (2, 3, 4):
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.factura_items_table.setItem(row_idx, col_idx, cell)
        self.factura_items_table.setSortingEnabled(was_sorting)
        if was_sorting:
            self.factura_items_table.sortItems(
                sort_col if sort_col >= 0 else 1,
                sort_order if sort_col >= 0 else Qt.SortOrder.DescendingOrder,
            )
        self._set_factura_items_totals(total_cantidad, total_kg, total_importe)

    def _on_factura_selection_changed(self) -> None:
        selected = self._selected_row()
        pedido_id = str(getattr(selected, "pedido_id", "") or "").strip() if selected else ""
        factura_id = self._selected_factura_id()
        self._reload_factura_items_table(pedido_id, factura_id)
        self.delete_factura_btn.setEnabled(bool(factura_id))
        self.edit_factura_line_btn.setEnabled(False)

    def _edit_factura_line(self) -> None:
        item_id = self._selected_factura_item_id()
        if not item_id:
            QMessageBox.warning(self, "Factura", "Selecciona una línea de factura.")
            return
        item = self.order_document_import_service.get_factura_item(item_id)
        if item is None:
            QMessageBox.warning(self, "Factura", "Línea de factura no encontrada.")
            return
        dialog = FacturaItemEditDialog(item, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.order_document_import_service.update_factura_item(item_id, dialog.payload())
        except Exception as exc:
            QMessageBox.warning(self, "Factura", str(exc))
            return
        selected = self._selected_row()
        pedido_id = str(getattr(selected, "pedido_id", "") or "").strip() if selected else ""
        self._load_factura_selector(pedido_id)
        self._reload_factura_items_table(pedido_id, self._selected_factura_id())

    def _delete_selected_factura(self) -> None:
        selected = self._selected_row()
        factura_id = self._selected_factura_id()
        if selected is None or not factura_id:
            QMessageBox.warning(self, "Factura", "Selecciona una factura concreta para eliminar.")
            return
        factura_numero = ""
        current_row = self.facturas_table.currentRow()
        if current_row >= 0 and self.facturas_table.item(current_row, 0) is not None:
            factura_numero = str(self.facturas_table.item(current_row, 0).text() or "").strip()
        answer = QMessageBox.question(
            self,
            "Eliminar factura",
            f"Eliminar la factura {factura_numero or factura_id} y sus líneas? Esta acción permite reimportarla después.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.order_document_import_service.delete_factura(selected.pedido_id, factura_id)
        except Exception as exc:
            QMessageBox.warning(self, "Factura", str(exc))
            return
        self.reload()

    def _show_albaran_items_context_menu(self, pos) -> None:
        item = self.albaran_items_table.itemAt(pos)
        if item is None:
            return
        row_idx = item.row()
        id_cell = self.albaran_items_table.item(row_idx, 0)
        albaran_item_id = str(id_cell.data(Qt.ItemDataRole.UserRole) or "").strip() if id_cell else ""
        if not albaran_item_id:
            return
        if not self.order_document_import_service.is_albaran_item_pending(albaran_item_id):
            return
        menu = QMenu(self)
        refresh_action = menu.addAction("Refrescar")
        chosen = menu.exec(self.albaran_items_table.viewport().mapToGlobal(pos))
        if chosen == refresh_action:
            self._refresh_albaran_item_mapping(albaran_item_id)

    def _refresh_albaran_item_mapping(self, albaran_item_id: str) -> None:
        try:
            self.order_document_import_service.refresh_albaran_item_mapping(albaran_item_id)
        except Exception as exc:
            QMessageBox.warning(self, "Albaran", str(exc))
            return
        self.reload()

    def _reload_pendientes_table(self, pedido_id: str | None) -> None:
        self.pendientes_table.setRowCount(0)
        if not pedido_id:
            return
        rows, articles = self.order_query_service.list_pendientes(pedido_id)
        name_by_article = {str(a.articulo_id or ""): str(a.articulo_descripcion or "").strip() for a in articles}
        ref_by_article = {str(a.articulo_id or ""): str(a.articulo_referencia_corta or "").strip() for a in articles}
        article_by_id = {str(a.articulo_id or ""): a for a in articles}

        self.pendientes_table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            articulo_id = str(getattr(row, "articulo_id", "") or "").strip()
            cod = ref_by_article.get(articulo_id, "") or articulo_id
            nombre = name_by_article.get(articulo_id, "") or articulo_id
            pendiente_raw = float(getattr(row, "cantidad_pendiente", 0.0) or 0.0)
            pendiente_display = -pendiente_raw
            values = [
                cod,
                nombre,
                self._format_number_es(float(getattr(row, "cantidad_pedida", 0.0) or 0.0), 2),
                self._format_number_es(float(getattr(row, "cantidad_recibida", 0.0) or 0.0), 2),
                self._format_number_es(pendiente_display, 2),
                str(getattr(row, "estado", "") or "").strip(),
            ]
            for col_idx, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if col_idx == 0 and self._is_article_pending(article_by_id.get(articulo_id)):
                    cell.setForeground(QBrush(QColor("#c62828")))
                if col_idx == 4:
                    if pendiente_display > 0:
                        cell.setForeground(QBrush(QColor("#2e7d32")))
                    elif pendiente_display < 0:
                        cell.setForeground(QBrush(QColor("#c62828")))
                if col_idx in (2, 3, 4):
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.pendientes_table.setItem(row_idx, col_idx, cell)

    def reload(self) -> None:
        selected_id = self._selected_id()
        pedidos = self.order_query_service.list_raw_orders()
        self._load_almacen_filter()
        self._load_period_filters(pedidos)

        year_filter = str(self.year_filter.currentData() or "")
        month_from = int(self.month_from_filter.currentData() or 0)
        month_to = int(self.month_to_filter.currentData() or 0)
        almacen_filter = str(self.almacen_filter.currentData() or "")
        self.rows = [
                PedidoListRow(
                    pedido_id=row.pedido_id,
                    almacen_id=row.almacen_id,
                    almacen_nombre=row.almacen_nombre,
                    pedido_fecha=row.pedido_fecha,
                    pedido_numero=row.pedido_numero,
                    pedido_albaran_numero=row.pedido_albaran_numero,
                    pedido_factura_numero=row.pedido_factura_numero,
                    pedido_ref=row.pedido_ref,
                    pedido_estado=row.pedido_estado,
                    semana=row.semana,
                    total_kg=row.total_kg,
                )
                for row in self.order_query_service.list_order_rows(
                    year_filter=year_filter,
                    month_from=month_from,
                    month_to=month_to,
                    almacen_filter=almacen_filter,
                )
        ]
        self._render_table()
        self._select_by_id(selected_id)
        if self.table.rowCount() > 0 and not self.table.selectionModel().selectedRows():
            self.table.selectRow(0)
        if self.table.rowCount() > 0:
            self._show_selected_details()
        else:
            self._clear_details()

    def _render_table(self) -> None:
        header = self.table.horizontalHeader()
        sort_col = header.sortIndicatorSection()
        sort_order = header.sortIndicatorOrder()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.rows))
        for row_idx, row in enumerate(self.rows):
            values = [
                row.almacen_nombre,
                row.pedido_numero,
                row.pedido_fecha.strftime("%d/%m/%Y"),
                str(row.semana),
                self._format_number_es(row.total_kg, 2),
                row.pedido_estado,
            ]
            for col_idx, value in enumerate(values):
                if col_idx == 3:
                    item = NumericTableWidgetItem(value, float(row.semana))
                elif col_idx == 4:
                    item = NumericTableWidgetItem(value, row.total_kg)
                else:
                    item = QTableWidgetItem(value)
                if col_idx == 0:
                    item.setData(Qt.ItemDataRole.UserRole, row.pedido_id)
                if col_idx == 5:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    state = str(value or "").strip().upper()
                    if state == "E":
                        item.setForeground(QBrush(QColor("#1565C0")))
                    elif state == "P":
                        item.setForeground(QBrush(QColor("#EF6C00")))
                    elif state == "M":
                        item.setForeground(QBrush(QColor("#C62828")))
                elif col_idx == 3:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                elif col_idx == 4:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row_idx, col_idx, item)
        self.table.setSortingEnabled(True)
        self.table.sortItems(sort_col if sort_col >= 0 else 3, sort_order if sort_col >= 0 else Qt.SortOrder.DescendingOrder)
        self._set_left_totals(sum(row.total_kg for row in self.rows))

    def _set_left_totals(self, total_kg: float) -> None:
        # Mantener anchos de la fila de totales sincronizados con la tabla principal.
        for col_idx in range(self.table.columnCount()):
            self.table_totals.setColumnWidth(col_idx, self.table.columnWidth(col_idx))
        values = ["TOTAL", "", "", "", self._format_number_es(total_kg, 2), ""]
        for col_idx, value in enumerate(values):
            if col_idx == 4:
                cell = NumericTableWidgetItem(value, total_kg)
            else:
                cell = QTableWidgetItem(value)
            cell.setFlags(Qt.ItemFlag.ItemIsEnabled)
            if col_idx == 4:
                cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            elif col_idx in (3, 5):
                cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            font = cell.font()
            font.setBold(True)
            cell.setFont(font)
            self.table_totals.setItem(0, col_idx, cell)

    def _set_pedido_items_totals(self, total_cantidad: float, total_kg: float) -> None:
        values = [
            "TOTAL",
            "",
            self._format_number_es(total_cantidad, 2),
            self._format_number_es(total_kg, 2, " kg"),
        ]
        for col_idx, value in enumerate(values):
            if col_idx == 2:
                cell = NumericTableWidgetItem(value, total_cantidad)
            elif col_idx == 3:
                cell = NumericTableWidgetItem(value, total_kg)
            else:
                cell = QTableWidgetItem(value)
            cell.setFlags(Qt.ItemFlag.ItemIsEnabled)
            if col_idx in (2, 3):
                cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            font = cell.font()
            font.setBold(True)
            cell.setFont(font)
            self.pedido_items_totals_table.setItem(0, col_idx, cell)

    def _set_albaran_items_totals(self, total_cantidad: float, total_kg: float) -> None:
        values = [
            "TOTAL",
            "",
            "",
            self._format_number_es(total_cantidad, 2),
            self._format_number_es(total_kg, 2, " kg"),
        ]
        for col_idx, value in enumerate(values):
            if col_idx == 3:
                cell = NumericTableWidgetItem(value, total_cantidad)
            elif col_idx == 4:
                cell = NumericTableWidgetItem(value, total_kg)
            else:
                cell = QTableWidgetItem(value)
            cell.setFlags(Qt.ItemFlag.ItemIsEnabled)
            if col_idx in (3, 4):
                cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            font = cell.font()
            font.setBold(True)
            cell.setFont(font)
            self.albaran_items_totals_table.setItem(0, col_idx, cell)

    def _set_factura_items_totals(self, total_cantidad: float, total_kg: float, total_importe: float) -> None:
        values = [
            "TOTAL",
            "",
            self._format_number_es(total_cantidad, 2),
            self._format_number_es(total_kg, 2),
            self._format_number_es(total_importe, 2),
        ]
        for col_idx, value in enumerate(values):
            if col_idx == 2:
                cell = NumericTableWidgetItem(value, total_cantidad)
            elif col_idx == 3:
                cell = NumericTableWidgetItem(value, total_kg)
            elif col_idx == 4:
                cell = NumericTableWidgetItem(value, total_importe)
            else:
                cell = QTableWidgetItem(value)
            cell.setFlags(Qt.ItemFlag.ItemIsEnabled)
            if col_idx in (2, 3, 4):
                cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            font = cell.font()
            font.setBold(True)
            cell.setFont(font)
            self.factura_items_totals_table.setItem(0, col_idx, cell)

    def _selected_row(self) -> PedidoListRow | None:
        selected = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not selected:
            return None
        row_idx = selected[0].row()
        id_item = self.table.item(row_idx, 0)
        pedido_id = str(id_item.data(Qt.ItemDataRole.UserRole) or "") if id_item else ""
        if not pedido_id:
            return None
        return next((row for row in self.rows if row.pedido_id == pedido_id), None)

    def _selected_id(self) -> str | None:
        row = self._selected_row()
        return None if row is None else row.pedido_id

    def _select_by_id(self, pedido_id: str | None) -> None:
        if not pedido_id:
            return
        for i, row in enumerate(self.rows):
            if row.pedido_id == pedido_id:
                self.table.selectRow(i)
                return

    def _show_selected_details(self) -> None:
        row = self._selected_row()
        self._is_loading_details = True
        if row is None:
            self._clear_details()
            self._is_loading_details = False
            return
        self.detail_semana.setText(str(row.semana))
        self.detail_fecha.setDate(QDate(row.pedido_fecha.year, row.pedido_fecha.month, row.pedido_fecha.day))
        self.detail_pedido_numero.setText(row.pedido_numero)
        self._load_albaran_selector(row.pedido_id)
        self._load_factura_selector(row.pedido_id)
        self._reload_pedido_items_table(row.pedido_id)
        self._reload_albaran_items_table(row.pedido_id, str(self.albaran_selector.currentData() or "").strip())
        self._reload_factura_items_table(row.pedido_id, self._selected_factura_id())
        self._reload_pendientes_table(row.pedido_id)
        self.import_albaran_btn.setEnabled(True)
        self.import_factura_btn.setEnabled(True)
        self.delete_factura_btn.setEnabled(bool(self._selected_factura_id()))
        self.edit_factura_line_btn.setEnabled(bool(self._selected_factura_item_id()))
        self._is_loading_details = False

    def _clear_details(self) -> None:
        self.detail_semana.clear()
        today = date.today()
        self.detail_fecha.setDate(QDate(today.year, today.month, today.day))
        self.detail_pedido_numero.clear()
        self._load_albaran_selector(None)
        self._load_factura_selector(None)
        self._reload_pedido_items_table(None)
        self._reload_albaran_items_table(None)
        self._reload_factura_items_table(None)
        self._reload_pendientes_table(None)
        self.import_albaran_btn.setEnabled(False)
        self.import_factura_btn.setEnabled(False)
        self.delete_factura_btn.setEnabled(False)
        self.edit_factura_line_btn.setEnabled(False)

    def _schedule_autosave(self) -> None:
        if self._is_loading_details:
            return
        self._autosave_timer.start(350)

    def _autosave_selected_order(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        try:
            parsed_date = self.detail_fecha.date().toPython()
            payload = {
                "pedido_fecha": parsed_date,
                "pedido_numero": self.detail_pedido_numero.text().strip(),
            }
            self.order_service.update_order_header(row.pedido_id, payload["pedido_fecha"], payload["pedido_numero"])
            self.reload()
            self._select_by_id(row.pedido_id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Pedidos", f"No se pudo guardar.\n{exc}")

    def _new_order(self) -> None:
        almacen_id = str(self.almacen_filter.currentData() or "").strip()
        if not almacen_id:
            QMessageBox.warning(self, "Pedidos", "Selecciona un Cliente/Distribuidor para crear el pedido.")
            return

        dialog = NewPedidoDialog(almacen_id=almacen_id, parent=self, preload_history=False)
        if not dialog.exec():
            return
        lines = dialog.selected_lines()
        if not lines:
            QMessageBox.warning(self, "Pedidos", "No hay líneas para consignar.")
            return
        submit_mode = dialog.submit_mode()
        is_pending = submit_mode == "pendiente"
        pedido_numero = dialog.pedido_numero()
        pedido_fecha = dialog.pedido_fecha()
        try:
            pedido_id = self.order_service.create_order(
                almacen_id=almacen_id,
                pedido_fecha=pedido_fecha,
                pedido_numero=pedido_numero,
                lines=[OrderLineInput(line.articulo_id, float(line.uds)) for line in lines],
                is_pending=is_pending,
            )
            self.reload()
            self._select_by_id(pedido_id)
            self._show_selected_details()
            if not is_pending:
                answer = QMessageBox.question(self, "Pedido creado", "Pedido consignado. ¿Deseas exportarlo a Excel?")
                if answer == QMessageBox.StandardButton.Yes:
                    self._export_order_to_excel(pedido_id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Pedidos", f"No se pudo crear.\n{exc}")

    def _edit_order(self) -> None:
        selected = self._selected_row()
        if selected is None:
            QMessageBox.warning(self, "Pedidos", "Selecciona un pedido para editar.")
            return
        try:
            pedido, qty_by_articulo = self.order_query_service.get_order_edit_payload(selected.pedido_id)

            dialog = NewPedidoDialog(
                almacen_id=str(pedido.almacen_id or "").strip(),
                parent=self,
                title="Editar pedido",
                pedido_fecha=self._parse_date(getattr(pedido, "pedido_fecha", None)),
                pedido_numero=str(getattr(pedido, "pedido_numero", "") or "").strip(),
                initial_qty_by_articulo=qty_by_articulo,
                confirm_label="Guardar" if selected.pedido_estado == "E" else "Consignar",
                allow_pending=(selected.pedido_estado != "E"),
            )
            if not dialog.exec():
                return
            lines = dialog.selected_lines()
            if not lines:
                QMessageBox.warning(self, "Pedidos", "No hay líneas para consignar.")
                return
            submit_mode = dialog.submit_mode()
            pedido_fecha = dialog.pedido_fecha()
            pedido_numero = dialog.pedido_numero()

            self.order_service.update_order(
                pedido_id=selected.pedido_id,
                pedido_fecha=pedido_fecha,
                pedido_numero=pedido_numero,
                lines=[OrderLineInput(line.articulo_id, float(line.uds)) for line in lines],
                submit_mode=submit_mode,
            )
            self.reload()
            self._select_by_id(selected.pedido_id)
            self._show_selected_details()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Pedidos", f"No se pudo editar.\n{exc}")

    def _export_selected_order_to_excel(self) -> None:
        selected = self._selected_row()
        if selected is None:
            QMessageBox.warning(self, "Pedidos", "Selecciona un pedido para exportar.")
            return
        self._export_order_to_excel(selected.pedido_id)

    def _export_order_to_excel(self, pedido_id: str) -> None:
        try:
            wb, default_base_name = self.order_export_service.build_order_workbook(pedido_id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Pedidos", f"No se pudo preparar la exportación.\n{exc}")
            return
        default_name = f"{default_base_name}.xlsx"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar pedido a Excel",
            default_name,
            "Excel (*.xlsx)",
        )
        if not file_path:
            return
        if not file_path.lower().endswith(".xlsx"):
            file_path = f"{file_path}.xlsx"
        wb.save(file_path)
        history_path = self.order_export_service.save_order_excel_history(pedido_id, wb, default_base_name)
        self.order_export_service.mark_order_exported(pedido_id)
        self.reload()
        self._select_by_id(pedido_id)
        QMessageBox.information(self, "Pedidos", f"Pedido exportado.\n{file_path}\n\nHistórico:\n{history_path}")

    def _send_selected_order_by_outlook(self) -> None:
        selected = self._selected_row()
        if selected is None:
            QMessageBox.warning(self, "Pedidos", "Selecciona un pedido para enviar.")
            return
        mail_cfg = self.orders_mail_settings.load()
        destino_email = str(mail_cfg.get("destino_email") or "").strip()
        if not destino_email:
            QMessageBox.warning(
                self,
                "Pedidos",
                "Configura el email destino fijo en Configuracion > API > Pedidos por Outlook.",
            )
            return
        mode_dialog = QMessageBox(self)
        mode_dialog.setIcon(QMessageBox.Icon.Question)
        mode_dialog.setWindowTitle("Enviar pedido")
        mode_dialog.setText("Selecciona modo de envío para Outlook:")
        draft_btn = mode_dialog.addButton("Preparar borrador", QMessageBox.ButtonRole.AcceptRole)
        send_btn = mode_dialog.addButton("Enviar directo", QMessageBox.ButtonRole.ActionRole)
        cancel_btn = mode_dialog.addButton(QMessageBox.StandardButton.Cancel)
        mode_dialog.setDefaultButton(draft_btn)
        mode_dialog.exec()
        clicked = mode_dialog.clickedButton()
        if clicked == cancel_btn:
            return
        send_direct = clicked == send_btn
        try:
            wb, default_base_name = self.order_export_service.build_order_workbook(selected.pedido_id)
            excel_path = self.order_export_service.save_order_excel_history(selected.pedido_id, wb, default_base_name)
            preview = self.order_export_service.build_order_mail_preview(
                pedido_id=selected.pedido_id,
                pedido_numero=selected.pedido_numero,
                destino_email=destino_email,
            )
            edited = self._show_mail_preview_dialog(
                to_email=str(preview.get("to_email") or ""),
                subject=str(preview.get("subject") or ""),
                body=str(preview.get("body") or ""),
                attachment_path=excel_path,
                send_direct=send_direct,
            )
            if edited is None:
                return
            outcome = self.order_export_service.open_outlook_mail_with_attachment(
                pedido_id=selected.pedido_id,
                pedido_numero=selected.pedido_numero,
                attachment_path=excel_path,
                destino_email=str(edited.get("to_email") or "").strip(),
                send_direct=send_direct,
                subject=str(edited.get("subject") or "").strip(),
                body=str(edited.get("body") or ""),
            )
            self.order_export_service.log_order_mail_event(
                pedido_id=selected.pedido_id,
                pedido_numero=selected.pedido_numero,
                destino_email=str(edited.get("to_email") or "").strip(),
                asunto=str(outcome.get("subject") or "").strip(),
                adjunto_path=str(excel_path),
                modo_envio="send" if send_direct else "draft",
                estado="ENVIADO" if send_direct else "BORRADOR",
                error_detalle="",
            )
        except Exception as exc:  # noqa: BLE001
            self.order_export_service.log_order_mail_event(
                pedido_id=selected.pedido_id,
                pedido_numero=selected.pedido_numero,
                destino_email=locals().get("edited", {}).get("to_email", destino_email),
                asunto="",
                adjunto_path=str(locals().get("excel_path", "")),
                modo_envio="send" if locals().get("send_direct", False) else "draft",
                estado="ERROR",
                error_detalle=str(exc),
            )
            QMessageBox.warning(self, "Pedidos", f"No se pudo preparar el email.\n{exc}")
            return
        if send_direct:
            QMessageBox.information(self, "Pedidos", f"Correo enviado desde Outlook.\nAdjunto: {excel_path}")
        else:
            QMessageBox.information(self, "Pedidos", f"Borrador de Outlook preparado.\nAdjunto: {excel_path}")

    def _print_selected_order(self) -> None:
        selected = self._selected_row()
        if selected is None:
            QMessageBox.warning(self, "Pedidos", "Selecciona un pedido para imprimir.")
            return
        try:
            wb, base_name = self.order_export_service.build_order_workbook(selected.pedido_id)
            safe_name = "".join(ch for ch in base_name if ch not in '<>:"/\\|?*').strip() or "pedido"
            tmp_path = Path(tempfile.gettempdir()) / f"{safe_name}.xlsx"
            wb.save(tmp_path)
            if hasattr(os, "startfile"):
                os.startfile(str(tmp_path), "print")
            else:
                raise RuntimeError("La impresión directa solo está disponible en Windows.")
            QMessageBox.information(self, "Pedidos", f"Enviado a impresión.\n{tmp_path}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Pedidos", f"No se pudo imprimir.\n{exc}")

    def _show_mail_preview_dialog(
        self,
        *,
        to_email: str,
        subject: str,
        body: str,
        attachment_path: Path,
        send_direct: bool,
    ) -> dict[str, str] | None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Previsualización correo")
        dialog.resize(780, 480)
        layout = QVBoxLayout(dialog)

        form = QFormLayout()
        to_input = QLineEdit(str(to_email or "").strip())
        subject_input = QLineEdit(str(subject or "").strip())
        form.addRow("Para", to_input)
        form.addRow("Asunto", subject_input)
        layout.addLayout(form)

        attachment_label = QLabel(f"Adjunto: {attachment_path}")
        attachment_label.setWordWrap(True)
        layout.addWidget(attachment_label)

        body_input = QTextEdit()
        body_input.setPlainText(str(body or ""))
        layout.addWidget(body_input, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        preview_btn = buttons.addButton("Ver pedido", QDialogButtonBox.ButtonRole.ActionRole)
        preview_btn.setProperty("btnRole", "warning")
        confirm_text = "Enviar directo" if send_direct else "Preparar borrador"
        confirm_btn = buttons.addButton(confirm_text, QDialogButtonBox.ButtonRole.AcceptRole)
        confirm_btn.setProperty("btnRole", "success" if send_direct else "secondary")

        def _open_order_preview() -> None:
            try:
                if hasattr(os, "startfile"):
                    os.startfile(str(attachment_path))
                else:
                    raise RuntimeError("La previsualización directa solo está disponible en Windows.")
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, "Pedidos", f"No se pudo abrir la previsualización del pedido.\n{exc}")

        preview_btn.clicked.connect(_open_order_preview)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return None
        to_value = str(to_input.text() or "").strip()
        if not to_value:
            QMessageBox.warning(self, "Pedidos", "El destinatario no puede estar vacío.")
            return None
        return {
            "to_email": to_value,
            "subject": str(subject_input.text() or "").strip(),
            "body": body_input.toPlainText(),
        }

    def _delete_order(self) -> None:
        row = self._selected_row()
        if row is None:
            QMessageBox.warning(self, "Pedidos", "Selecciona un pedido.")
            return
        answer = QMessageBox.question(self, "Confirmar", "Eliminar pedido seleccionado?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.order_service.delete_order(row.pedido_id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Pedidos", f"No se pudo eliminar.\n{exc}")
        self.reload()

    def _confirm_albaran_preview(self, header: dict[str, str], rows: list[dict[str, Any]]) -> bool:
        dialog = AlbaranPreviewDialog(header=header, items=rows, parent=self)
        return dialog.exec() == QDialog.DialogCode.Accepted

    def _confirm_factura_preview(self, header: dict[str, str], rows: list[dict[str, Any]]) -> bool:
        dialog = FacturaPreviewDialog(header=header, items=rows, parent=self)
        return dialog.exec() == QDialog.DialogCode.Accepted

    def _read_factura_pdf_with_progress(self, file_path: Path) -> tuple[dict[str, str], list[dict[str, Any]]]:
        dialog = QProgressDialog("Analizando factura", "", 0, 0, self)
        dialog.setWindowTitle("Analizando factura")
        dialog.setFixedWidth(420)
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        dialog.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        dialog.setCancelButton(None)
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.setValue(0)
        dialog.setMinimumWidth(420)
        progress_bar = QProgressBar(dialog)
        progress_bar.setRange(0, 0)
        progress_bar.setTextVisible(False)
        progress_bar.setMinimumWidth(380)
        dialog.setBar(progress_bar)

        result: dict[str, Any] = {"header": None, "rows": None, "error": None}
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(OrderDocumentParser.parse_factura_pdf, file_path)
        poll_timer = QTimer(dialog)

        def poll_result() -> None:
            if not future.done():
                return
            poll_timer.stop()
            try:
                header, rows = future.result()
            except Exception as exc:
                result["error"] = str(exc)
                dialog.reject()
                return
            result["header"] = header
            result["rows"] = rows
            dialog.accept()

        poll_timer.setInterval(100)
        poll_timer.timeout.connect(poll_result)

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            poll_timer.start()
            dialog.exec()
        finally:
            poll_timer.stop()
            executor.shutdown(wait=False)
            QApplication.restoreOverrideCursor()

        if result["error"]:
            raise ValueError(str(result["error"]))
        header = result.get("header")
        rows = result.get("rows")
        if not isinstance(header, dict) or not isinstance(rows, list):
            raise ValueError("No se pudo leer la factura.")
        return header, rows

    def _parse_float(self, value, default: float = 0.0) -> float:
        text_value = str(value or "").strip()
        if not text_value:
            return default
        try:
            return float(text_value.replace(",", "."))
        except Exception:
            return default

    @staticmethod
    def _format_number_es_static(value: float, decimals: int = 2, suffix: str = "") -> str:
        return OrderDocumentParser.format_number_es(value, decimals, suffix)

    def _format_number_es(self, value: float, decimals: int = 2, suffix: str = "") -> str:
        return OrdersPage._format_number_es_static(value, decimals, suffix)

    def _is_article_pending(self, article: IngredienteIreks | None) -> bool:
        if article is None:
            return True
        descripcion = str(getattr(article, "articulo_descripcion", "") or "").strip().lower()
        if not descripcion or descripcion.startswith("pendiente"):
            return True
        for field_name in ("fabricante_id", "articulo_envase_id", "articulo_familia_id", "articulo_subfamilia_id"):
            if not str(getattr(article, field_name, "") or "").strip():
                return True
        return False

    def _import_albaran_for_selected_order(self) -> None:
        self._import_document_for_selected_order(
            dialog_title="Seleccionar albaran",
            warning_prefix="albaran",
            preview_loader=lambda source: self.orders_documents_import_ui_service.prepare_albaran_preview(
                source,
                parse_pdf=OrderDocumentParser.parse_albaran_pdf,
            ),
            importer=lambda pedido_id, header, rows: self.orders_documents_import_ui_service.import_albaran(
                pedido_id=pedido_id,
                header=header,
                rows=rows,
            ),
            confirm_preview=self._confirm_albaran_preview,
        )

    def _import_factura_for_selected_order(self) -> None:
        self._import_document_for_selected_order(
            dialog_title="Seleccionar factura",
            warning_prefix="factura",
            preview_loader=lambda source: self.orders_documents_import_ui_service.prepare_factura_preview(
                source,
                parse_pdf=self._read_factura_pdf_with_progress,
            ),
            importer=lambda pedido_id, header, rows: self.orders_documents_import_ui_service.import_factura(
                pedido_id=pedido_id,
                header=header,
                rows=rows,
            ),
            confirm_preview=self._confirm_factura_preview,
        )

    def _import_document_for_selected_order(
        self,
        *,
        dialog_title: str,
        warning_prefix: str,
        preview_loader: Callable[[Path], OrdersDocumentPreviewData],
        importer: Callable[[str, dict[str, str], list[dict[str, Any]]], OrdersDocumentImportOutcome],
        confirm_preview: Callable[[dict[str, str], list[dict[str, Any]]], bool],
    ) -> None:
        row = self._selected_row()
        if row is None:
            QMessageBox.warning(self, "Pedidos", f"Selecciona un pedido para importar su {warning_prefix}.")
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            dialog_title,
            "",
            "Archivos de datos (*.pdf *.json *.xlsx *.xlsm *.csv)",
        )
        if not file_path:
            return

        try:
            preview = preview_loader(Path(file_path))
        except Exception as exc:
            QMessageBox.warning(self, "Pedidos", f"No se pudo leer la {warning_prefix}: {exc}")
            return

        if not confirm_preview(preview.header, preview.rows):
            return

        try:
            outcome = importer(row.pedido_id, preview.header, preview.rows)
        except Exception as exc:
            QMessageBox.warning(self, "Pedidos", str(exc))
            return
        self.reload()
        if outcome.ok:
            QMessageBox.information(self, outcome.title, outcome.message)
            return
        QMessageBox.warning(self, outcome.title, outcome.message)
