from __future__ import annotations

from datetime import date, datetime
import json
import os
from pathlib import Path
import re
import tempfile
import traceback
from typing import Any, cast

from PySide6.QtCore import QEvent, QSize, QTimer, Qt
from PySide6.QtGui import QAction, QBrush, QColor, QFont, QIcon, QKeySequence, QPainter, QPen, QPixmap, QShortcut, QTextCharFormat
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QMenu,
    QPushButton,
    QPlainTextEdit,
    QRadioButton,
    QTextEdit,
    QSpinBox,
    QSizePolicy,
    QSplitter,
    QStyledItemDelegate,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from app.models import Receta, RecetaLinea
from app.services.openai_process_service import OpenAIProcessService
from app.services import PdfService
from app.services.recipe_active_flow_service import RecipeActiveFlowService, RecipeActivePayload
from app.services.recipe_document_import_service import RecipeDocumentDraft, RecipeDocumentImportService
from app.services.recipe_image_storage_service import resolve_recipe_image_path, store_recipe_image
from app.services.recipe_service import RecipeService
from app.ui.widgets.action_ribbon import create_standard_ribbon_button, create_standard_top_ribbon
from app.ui.widgets.nutrition_card import NutritionCard, NutritionRowData
from app.ui.widgets.recipe_document_import_dialog import RecipeDocumentImportDialog
from app.viewmodels import IngredientChoice


def _process_add_icon() -> QIcon:
    pixmap = QPixmap(48, 48)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#14532D"), 2))
    painter.drawLine(5, 12, 19, 12)
    painter.drawLine(12, 5, 12, 19)
    painter.end()
    return QIcon(pixmap)


def _normalize_process_name(value: str | None) -> str:
    text = str(value or "").strip()
    return text if text else "Masa final"


def _piece_count_from_mass(final_mass_g: float, piece_weight_g: float) -> float:
    mass = max(float(final_mass_g or 0.0), 0.0)
    piece_weight = max(float(piece_weight_g or 0.0), 0.0)
    return mass / piece_weight if piece_weight > 0 else 0.0


def _recipe_process_totals(lineas: list[RecetaLinea], process_name: str) -> tuple[float, float]:
    target_process = _normalize_process_name(process_name)
    total_qty_g = 0.0
    total_pct = 0.0
    for line in lineas:
        if _normalize_process_name(line.proceso_nombre) != target_process:
            continue
        if not (line.nombre_mostrado or line.notas or line.cantidad_base_g):
            continue
        total_qty_g += float(line.cantidad_base_g or 0.0)
        total_pct += float(line.porcentaje_panadero or 0.0)
    return total_qty_g, total_pct


def _default_recipe_pdf_filename(recipe_name: str, customer_name: str, saved_at: datetime | None = None) -> str:
    timestamp = saved_at or datetime.now()
    recipe_label = str(recipe_name or "").strip() or "receta"
    customer_label = str(customer_name or "").strip() or "sin cliente"
    base_name = f"{recipe_label}-{customer_label}[{timestamp:%Y-%m-%d}]"
    safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", base_name).strip(". ")
    return f"{safe_name or 'receta'}.pdf"


def _customer_display_name(customer: Any) -> str:
    return str(
        getattr(customer, "cliente_nombre_comercial", "")
        or getattr(customer, "cliente_nombre_fiscal", "")
        or getattr(customer, "cliente_nombre_interno", "")
        or getattr(customer, "cliente_id", "")
        or ""
    ).strip()


def _white_icon_from_svg(svg_path: Path) -> QIcon:
    source = QPixmap(str(svg_path))
    white = QPixmap(source.size())
    white.fill(Qt.GlobalColor.transparent)
    painter = QPainter(white)
    painter.drawPixmap(0, 0, source)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(white.rect(), QColor("#FFFFFF"))
    painter.end()
    return QIcon(white)


def _unique_process_names(values: list[str]) -> list[str]:
    names: list[str] = []
    for value in values:
        name = _normalize_process_name(value)
        if name not in names:
            names.append(name)
    if not names:
        names.append("Masa final")
    return names


def _collect_recipe_image_gallery(items: list[tuple[str, bool]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for idx, (path, is_main) in enumerate(items):
        clean_path = str(path or "").strip()
        if not clean_path:
            continue
        rows.append({"path": clean_path, "is_main": bool(is_main), "order": idx})
    return rows


def _load_recipe_image_gallery(raw_value: object) -> list[dict[str, object]]:
    if isinstance(raw_value, list):
        data = raw_value
    else:
        text = str(raw_value or "").strip()
        if not text:
            return []
        try:
            data = json.loads(text)
        except Exception:
            return []
    if not isinstance(data, list):
        return []
    ordered_rows = sorted(
        [row for row in data if isinstance(row, dict)],
        key=lambda row: int(row.get("order", 0) or 0),
    )
    result: list[dict[str, object]] = []
    for row in ordered_rows:
        path = str(row.get("path") or "").strip()
        if not path:
            continue
        result.append({"path": path, "is_main": bool(row.get("is_main", False))})
    return result


def _recipe_image_gallery_from_payload(payload: dict[str, object]) -> list[dict[str, object]]:
    if "images_gallery" in payload:
        return _load_recipe_image_gallery(payload.get("images_gallery"))
    return _load_recipe_image_gallery(payload.get("__images_gallery_json"))


def _json_to_string_dict(raw_value: str) -> dict[str, str]:
    text = (raw_value or "").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {
        str(key): (
            json.dumps(value, ensure_ascii=False)
            if str(key) == "images_gallery" and isinstance(value, list)
            else str(value)
        )
        for key, value in payload.items()
    }


class IngredientSearchDialog(QDialog):
    def __init__(self, service: RecipeService, source_processes: list[str] | None = None, parent=None) -> None:
        super().__init__(parent)
        self.service = service
        self.source_processes = [str(x or "").strip() for x in (source_processes or []) if str(x or "").strip()]
        self.selected: IngredientChoice | None = None
        self.selected_process_name: str = ""
        self.selected_process_qty: float = 0.0
        self.setWindowTitle("Buscar ingrediente")
        self.resize(900, 450)
        self._build_ui()
        self._search()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.mode_combo: QComboBox | None = None
        if self.source_processes:
            mode_row = QHBoxLayout()
            mode_row.addWidget(QLabel("Tipo"))
            self.mode_combo = QComboBox()
            self.mode_combo.addItem("Ingrediente", "ingredient")
            self.mode_combo.addItem("Proceso", "process")
            self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
            mode_row.addWidget(self.mode_combo)
            mode_row.addStretch(1)
            layout.addLayout(mode_row)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por codigo, nombre, familia...")
        self.search_input.textChanged.connect(self._search)
        self.search_input.returnPressed.connect(self._search)
        layout.addWidget(self.search_input)

        self.table = QTableWidget(0, 2)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setHorizontalHeaderLabels(["Codigo", "Nombre"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.doubleClicked.connect(self._accept_selected)
        layout.addWidget(self.table, 1)

        self.process_box = QWidget()
        process_form = QFormLayout(self.process_box)
        process_form.setContentsMargins(0, 0, 0, 0)
        self.process_combo = QComboBox()
        self.process_combo.addItems(self.source_processes)
        self.process_qty = QDoubleSpinBox()
        self.process_qty.setDecimals(2)
        self.process_qty.setRange(0.01, 1_000_000_000.0)
        self.process_qty.setSingleStep(100.0)
        self.process_qty.setSuffix(" g")
        process_form.addRow("Proceso origen", self.process_combo)
        process_form.addRow("Cantidad usada", self.process_qty)
        self.process_box.setVisible(False)
        layout.addWidget(self.process_box)

        actions = QHBoxLayout()
        actions.addStretch()
        use_btn = QPushButton("Usar seleccionado")
        use_btn.setProperty("btnRole", "success")
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setProperty("btnRole", "secondary")
        use_btn.clicked.connect(self._accept_selected)
        cancel_btn.clicked.connect(self.reject)
        actions.addWidget(use_btn)
        actions.addWidget(cancel_btn)
        layout.addLayout(actions)
        self._on_mode_changed()

    def _mode(self) -> str:
        if self.mode_combo is None:
            return "ingredient"
        return str(self.mode_combo.currentData() or "ingredient")

    def _on_mode_changed(self) -> None:
        is_process = self._mode() == "process"
        self.search_input.setVisible(not is_process)
        self.table.setVisible(not is_process)
        self.process_box.setVisible(is_process)

    def _search(self) -> None:
        if self._mode() == "process":
            return
        term = self.search_input.text().strip()
        items = self.service.search_ingredients(term)
        self.table.setRowCount(len(items))
        for row, item in enumerate(items):
            values = [
                item.codigo,
                item.nombre,
            ]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if col == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, item)
                self.table.setItem(row, col, cell)

    def _accept_selected(self) -> None:
        if self._mode() == "process":
            process_name = str(self.process_combo.currentText() or "").strip()
            qty = float(self.process_qty.value() or 0.0)
            if not process_name:
                QMessageBox.warning(self, "Atencion", "Selecciona un proceso.")
                return
            if qty <= 0:
                QMessageBox.warning(self, "Atencion", "La cantidad debe ser mayor que 0.")
                return
            self.selected_process_name = process_name
            self.selected_process_qty = qty
            self.selected = None
            self.accept()
            return
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            QMessageBox.warning(self, "Atencion", "Selecciona un ingrediente.")
            return
        item_cell = self.table.item(selected[0].row(), 0)
        self.selected = item_cell.data(Qt.ItemDataRole.UserRole) if item_cell is not None else None
        self.selected_process_name = ""
        self.selected_process_qty = 0.0
        self.accept()


class BaseRecipeSearchDialog(QDialog):
    def __init__(self, service: RecipeService, parent=None) -> None:
        super().__init__(parent)
        self.service = service
        self.selected_recipe_id: int | None = None
        self.setWindowTitle("Cargar receta base")
        self.resize(760, 460)
        self._build_ui()
        self._search()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filtrar por ocurrencia...")
        self.search_input.textChanged.connect(self._search)
        layout.addWidget(self.search_input)

        self.table = QTableWidget(0, 2)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setHorizontalHeaderLabels(["Nº", "Nombre receta"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 72)
        self.table.doubleClicked.connect(self._accept_selected)
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        actions.addStretch()
        use_btn = QPushButton("Cargar")
        use_btn.setProperty("btnRole", "primary")
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setProperty("btnRole", "secondary")
        use_btn.clicked.connect(self._accept_selected)
        cancel_btn.clicked.connect(self.reject)
        actions.addWidget(use_btn)
        actions.addWidget(cancel_btn)
        layout.addLayout(actions)

    def _search(self) -> None:
        term = self.search_input.text().strip()
        recipes = self.service.list_recipes(term=term, es_base=True)
        self.table.setRowCount(len(recipes))
        for row, recipe in enumerate(recipes):
            values = [str(recipe.id or ""), recipe.nombre]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if col == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, recipe.id)
                self.table.setItem(row, col, cell)

    def _accept_selected(self) -> None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            QMessageBox.warning(self, "Recetas", "Selecciona una receta base.")
            return
        item = self.table.item(selected[0].row(), 0)
        if not item:
            return
        recipe_id = item.data(Qt.ItemDataRole.UserRole)
        if recipe_id is None:
            return
        self.selected_recipe_id = int(recipe_id)
        self.accept()


class CustomerRecipeSelectionDialog(QDialog):
    def __init__(self, service: RecipeService, parent=None) -> None:
        super().__init__(parent)
        self.service = service
        self.selected_customer_id = ""
        self.selected_customer_label = ""
        self.setWindowTitle("Nueva receta de cliente")
        self.resize(620, 420)
        self._build_ui()
        self._search()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filtrar clientes...")
        self.search_input.textChanged.connect(self._search)
        layout.addWidget(self.search_input)

        self.table = QTableWidget(0, 2)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setHorizontalHeaderLabels(["Código", "Cliente"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._accept_selected)
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        actions.addStretch()
        select_btn = QPushButton("Seleccionar")
        select_btn.setProperty("btnRole", "primary")
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setProperty("btnRole", "secondary")
        select_btn.clicked.connect(self._accept_selected)
        cancel_btn.clicked.connect(self.reject)
        actions.addWidget(select_btn)
        actions.addWidget(cancel_btn)
        layout.addLayout(actions)

    def _search(self) -> None:
        customers = self.service.search_customers(self.search_input.text().strip())
        self.table.setRowCount(len(customers))
        for row, customer in enumerate(customers):
            customer_id = str(getattr(customer, "cliente_id", "") or "").strip()
            code_item = QTableWidgetItem(str(getattr(customer, "cliente_codigo", "") or ""))
            code_item.setData(Qt.ItemDataRole.UserRole, customer_id)
            self.table.setItem(row, 0, code_item)
            label = _customer_display_name(customer) or customer_id
            self.table.setItem(row, 1, QTableWidgetItem(label))

    def _accept_selected(self) -> None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            QMessageBox.warning(self, "Recetas", "Selecciona un cliente.")
            return
        item = self.table.item(selected[0].row(), 0)
        customer_id = str(item.data(Qt.ItemDataRole.UserRole) or "").strip() if item else ""
        if not customer_id:
            return
        self.selected_customer_id = customer_id
        self.selected_customer_label = (self.table.item(selected[0].row(), 1).text() if self.table.item(selected[0].row(), 1) else "")
        self.accept()


class PromotionEditorDialog(QDialog):
    def __init__(self, service: RecipeService, promotion_row: Any | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Promoción cliente-producto")
        self.setMinimumWidth(520)
        self._promotion_id = getattr(getattr(promotion_row, "promotion", None), "id", None)
        promotion = getattr(promotion_row, "promotion", None)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.product_combo = QComboBox()
        self.product_combo.setEditable(True)
        self.product_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        for item in service.search_ingredients(""):
            if item.tipo_origen == "ireks" and item.ingrediente_id:
                self.product_combo.addItem(f"{item.codigo} · {item.nombre}", item.ingrediente_id)
        self.product_combo.setCurrentIndex(-1)
        self.buy_spin = QSpinBox()
        self.buy_spin.setRange(1, 1_000_000)
        self.buy_spin.setValue(10)
        self.free_spin = QSpinBox()
        self.free_spin.setRange(1, 1_000_000)
        self.free_spin.setValue(1)
        self.from_input = QLineEdit()
        self.from_input.setPlaceholderText("AAAA-MM-DD (opcional)")
        self.until_input = QLineEdit()
        self.until_input.setPlaceholderText("AAAA-MM-DD (opcional)")
        self.active_check = QCheckBox("Promoción activa")
        self.active_check.setChecked(True)
        self.notes_input = QLineEdit()
        form.addRow("Producto IREKS", self.product_combo)
        form.addRow("Unidades compradas", self.buy_spin)
        form.addRow("Unidades sin cargo", self.free_spin)
        form.addRow("Vigente desde", self.from_input)
        form.addRow("Vigente hasta", self.until_input)
        form.addRow("Estado", self.active_check)
        form.addRow("Observaciones", self.notes_input)
        layout.addLayout(form)

        if promotion is not None:
            self.product_combo.setCurrentIndex(self.product_combo.findData(int(promotion.producto_ireks_id)))
            self.buy_spin.setValue(int(promotion.unidades_compra or 1))
            self.free_spin.setValue(int(promotion.unidades_sin_cargo or 1))
            self.from_input.setText(promotion.fecha_desde.isoformat() if promotion.fecha_desde else "")
            self.until_input.setText(promotion.fecha_hasta.isoformat() if promotion.fecha_hasta else "")
            self.active_check.setChecked(bool(promotion.activa))
            self.notes_input.setText(str(promotion.observaciones or ""))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Guardar")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _parse_date(value: str) -> date | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            return date.fromisoformat(text)
        except ValueError as exc:
            raise ValueError("Las fechas deben tener formato AAAA-MM-DD.") from exc

    def payload(self) -> dict[str, Any]:
        product_id = self.product_combo.currentData()
        if not product_id:
            raise ValueError("Selecciona un producto IREKS de la lista.")
        return {
            "promotion_id": self._promotion_id,
            "producto_ireks_id": int(product_id),
            "unidades_compra": self.buy_spin.value(),
            "unidades_sin_cargo": self.free_spin.value(),
            "fecha_desde": self._parse_date(self.from_input.text()),
            "fecha_hasta": self._parse_date(self.until_input.text()),
            "activa": self.active_check.isChecked(),
            "observaciones": self.notes_input.text().strip(),
        }


class CustomerPromotionsDialog(QDialog):
    def __init__(self, service: RecipeService, customer_id: str, customer_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.customer_id = str(customer_id or "").strip()
        self.setWindowTitle(f"Promociones · {customer_name or self.customer_id}")
        self.resize(920, 420)
        self._rows: list[Any] = []

        layout = QVBoxLayout(self)
        help_label = QLabel("El escandallo prorratea cada promoción como precio medio efectivo.")
        layout.addWidget(help_label)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Producto", "Compra", "S/C", "Desde", "Hasta", "Activa", "Observaciones"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.table.doubleClicked.connect(self._edit)
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        add_button = QPushButton("Añadir")
        edit_button = QPushButton("Editar")
        delete_button = QPushButton("Eliminar")
        close_button = QPushButton("Cerrar")
        add_button.clicked.connect(self._add)
        edit_button.clicked.connect(self._edit)
        delete_button.clicked.connect(self._delete)
        close_button.clicked.connect(self.accept)
        actions.addWidget(add_button)
        actions.addWidget(edit_button)
        actions.addWidget(delete_button)
        actions.addStretch(1)
        actions.addWidget(close_button)
        layout.addLayout(actions)
        self._reload()

    def _reload(self) -> None:
        self._rows = self.service.list_customer_promotions(self.customer_id)
        self.table.setRowCount(len(self._rows))
        for row_index, row in enumerate(self._rows):
            promotion = row.promotion
            product = row.product
            values = [
                f"{product.articulo_referencia} · {product.articulo_descripcion}",
                str(promotion.unidades_compra),
                str(promotion.unidades_sin_cargo),
                promotion.fecha_desde.isoformat() if promotion.fecha_desde else "",
                promotion.fecha_hasta.isoformat() if promotion.fecha_hasta else "",
                "Sí" if promotion.activa else "No",
                promotion.observaciones,
            ]
            for column, value in enumerate(values):
                self.table.setItem(row_index, column, QTableWidgetItem(str(value or "")))

    def _selected_row(self) -> Any | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        index = selected[0].row()
        return self._rows[index] if 0 <= index < len(self._rows) else None

    def _add(self) -> None:
        self._open_editor(None)

    def _edit(self, *_args: Any) -> None:
        row = self._selected_row()
        if row is not None:
            self._open_editor(row)

    def _open_editor(self, row: Any | None) -> None:
        dialog = PromotionEditorDialog(self.service, row, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            payload = dialog.payload()
            self.service.save_customer_promotion(cliente_id=self.customer_id, **payload)
        except ValueError as exc:
            QMessageBox.warning(self, "Promociones", str(exc))
            return
        self._reload()

    def _delete(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        answer = QMessageBox.question(
            self,
            "Eliminar promoción",
            "¿Eliminar la promoción seleccionada?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.service.delete_customer_promotion(int(row.promotion.id or 0))
            self._reload()


class RecipeScaleDialog(QDialog):
    def __init__(self, current_flour_g: float, current_total_g: float, current_pieces: float, parent=None) -> None:
        super().__init__(parent)
        self.current_flour_g = float(current_flour_g or 0.0)
        self.current_total_g = float(current_total_g or 0.0)
        self.current_pieces = float(current_pieces or 0.0)
        self.setWindowTitle("Escalar receta")
        self.setFixedWidth(430)
        self._build_ui()
        self._on_mode_changed()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Por cantidad de harina (g)", "flour")
        self.mode_combo.addItem("Por masa total (g)", "dough")
        self.mode_combo.addItem("Por numero de piezas (uds)", "pieces")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        self.current_value_lbl = QLabel("-")

        self.target_spin = QDoubleSpinBox()
        self.target_spin.setDecimals(2)
        self.target_spin.setRange(0.01, 1_000_000_000.0)
        self.target_spin.setSingleStep(100.0)

        form.addRow("Modo", self.mode_combo)
        form.addRow("Valor actual", self.current_value_lbl)
        form.addRow("Objetivo", self.target_spin)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=self)
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_button is not None:
            ok_button.setText("Aplicar")
        if cancel_button is not None:
            cancel_button.setText("Cancelar")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_mode_changed(self) -> None:
        mode = self.mode()
        if mode == "flour":
            current = self.current_flour_g
            self.current_value_lbl.setText(f"{self._fmt(current)} g")
            self.target_spin.setDecimals(2)
            self.target_spin.setSingleStep(100.0)
            self.target_spin.setRange(0.01, 1_000_000_000.0)
        elif mode == "dough":
            current = self.current_total_g
            self.current_value_lbl.setText(f"{self._fmt(current)} g")
            self.target_spin.setDecimals(2)
            self.target_spin.setSingleStep(100.0)
            self.target_spin.setRange(0.01, 1_000_000_000.0)
        else:
            current = self.current_pieces
            self.current_value_lbl.setText(f"{self._fmt(current, 0)} uds")
            self.target_spin.setDecimals(0)
            self.target_spin.setSingleStep(1.0)
            self.target_spin.setRange(1.0, 1_000_000_000.0)
        minimum = 1.0 if mode == "pieces" else 0.01
        self.target_spin.setValue(max(current, minimum))

    def mode(self) -> str:
        return str(self.mode_combo.currentData() or "dough")

    def target_value_g(self) -> float:
        return float(self.target_spin.value() or 0.0)

    @staticmethod
    def _fmt(value: float, decimals: int = 2) -> str:
        text = f"{float(value or 0):,.{decimals}f}"
        return text.replace(",", "_").replace(".", ",").replace("_", ".")


class ProcessSourceDialog(QDialog):
    def __init__(self, source_processes: list[str], parent=None) -> None:
        super().__init__(parent)
        self._source_processes = [str(x or "").strip() for x in source_processes if str(x or "").strip()]
        self._selected_process = ""
        self._selected_qty = 0.0
        self.setWindowTitle("Añadir desde proceso")
        self.setFixedWidth(430)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.process_combo = QComboBox()
        self.process_combo.addItems(self._source_processes)
        self.qty_spin = QDoubleSpinBox()
        self.qty_spin.setDecimals(2)
        self.qty_spin.setRange(0.01, 1_000_000_000.0)
        self.qty_spin.setSingleStep(100.0)
        self.qty_spin.setSuffix(" g")

        form.addRow("Proceso origen", self.process_combo)
        form.addRow("Cantidad usada", self.qty_spin)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=self)
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_button is not None:
            ok_button.setText("Añadir")
        if cancel_button is not None:
            cancel_button.setText("Cancelar")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        process_name = str(self.process_combo.currentText() or "").strip()
        qty = float(self.qty_spin.value() or 0.0)
        if not process_name:
            QMessageBox.warning(self, "Recetas", "Selecciona un proceso origen.")
            return
        if qty <= 0:
            QMessageBox.warning(self, "Recetas", "La cantidad debe ser mayor que 0.")
            return
        self._selected_process = process_name
        self._selected_qty = qty
        self.accept()

    def selected(self) -> tuple[str, float]:
        return self._selected_process, self._selected_qty


class RecipePdfExportDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Exportar receta a PDF")
        self.setMinimumWidth(390)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        format_group = QGroupBox("Tipo de impresión", self)
        format_layout = QVBoxLayout(format_group)
        self.minimal_radio = QRadioButton("Mínimo", format_group)
        self.simple_radio = QRadioButton("Simple", format_group)
        self.extended_radio = QRadioButton("Extendido", format_group)
        self.minimal_radio.setChecked(True)
        self.format_buttons = QButtonGroup(self)
        for button in (self.minimal_radio, self.simple_radio, self.extended_radio):
            self.format_buttons.addButton(button)
            format_layout.addWidget(button)
        layout.addWidget(format_group)

        self.minimal_options_group = QGroupBox("Opciones del formato mínimo", self)
        options_layout = QGridLayout(self.minimal_options_group)
        options_layout.addWidget(QLabel("Incluir escandallo:"), 0, 0)
        self.escandallo_si = QRadioButton("Sí")
        self.escandallo_no = QRadioButton("No")
        self.escandallo_no.setChecked(True)
        self.escandallo_group = QButtonGroup(self)
        self.escandallo_group.addButton(self.escandallo_si)
        self.escandallo_group.addButton(self.escandallo_no)
        options_layout.addWidget(self.escandallo_si, 0, 1)
        options_layout.addWidget(self.escandallo_no, 0, 2)
        options_layout.addWidget(QLabel("Incluir valores nutricionales:"), 1, 0)
        self.nutrition_si = QRadioButton("Sí")
        self.nutrition_no = QRadioButton("No")
        self.nutrition_no.setChecked(True)
        self.nutrition_group = QButtonGroup(self)
        self.nutrition_group.addButton(self.nutrition_si)
        self.nutrition_group.addButton(self.nutrition_no)
        options_layout.addWidget(self.nutrition_si, 1, 1)
        options_layout.addWidget(self.nutrition_no, 1, 2)
        options_layout.addWidget(QLabel("Incluir % panadero:"), 2, 0)
        self.baker_percentage_si = QRadioButton("Sí")
        self.baker_percentage_no = QRadioButton("No")
        self.baker_percentage_si.setChecked(True)
        self.baker_percentage_group = QButtonGroup(self)
        self.baker_percentage_group.addButton(self.baker_percentage_si)
        self.baker_percentage_group.addButton(self.baker_percentage_no)
        options_layout.addWidget(self.baker_percentage_si, 2, 1)
        options_layout.addWidget(self.baker_percentage_no, 2, 2)
        options_layout.addWidget(QLabel("Incluir imágenes:"), 3, 0)
        self.images_si = QRadioButton("Sí")
        self.images_no = QRadioButton("No")
        self.images_no.setChecked(True)
        self.images_group = QButtonGroup(self)
        self.images_group.addButton(self.images_si)
        self.images_group.addButton(self.images_no)
        options_layout.addWidget(self.images_si, 3, 1)
        options_layout.addWidget(self.images_no, 3, 2)
        layout.addWidget(self.minimal_options_group)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Exportar")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.minimal_radio.toggled.connect(self.minimal_options_group.setVisible)
        self.minimal_options_group.setVisible(True)

    def layout_mode(self) -> str:
        if self.simple_radio.isChecked():
            return "simple"
        if self.minimal_radio.isChecked():
            return "minimal"
        return "extended"

    def include_escandallo(self) -> bool:
        return self.escandallo_si.isChecked()

    def include_nutrition(self) -> bool:
        return self.nutrition_si.isChecked()

    def include_baker_percentage(self) -> bool:
        return self.baker_percentage_si.isChecked()

    def include_images(self) -> bool:
        return self.images_si.isChecked()


class MinimalRecipePdfPreviewDialog(QDialog):
    def __init__(
        self,
        pdf_service: PdfService,
        recipe_id: int,
        include_escandallo: bool,
        include_nutrition: bool,
        include_baker_percentage: bool,
        include_images: bool,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._preview_path: Path | None = None
        self.setWindowTitle("PDF mínimo - Vista previa")
        self.resize(920, 720)

        layout = QVBoxLayout(self)

        self.pdf_view = QPdfView(self)
        self.pdf_document = QPdfDocument(self.pdf_view)
        self.pdf_view.setDocument(self.pdf_document)
        self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        layout.addWidget(self.pdf_view, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Guardar PDF")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        handle = tempfile.NamedTemporaryFile(prefix="gestionireks_minimo_", suffix=".pdf", delete=False)
        handle.close()
        self._preview_path = Path(handle.name)
        try:
            pdf_service.export_recipe_to_pdf(
                recipe_id,
                self._preview_path,
                layout_mode="minimal",
                include_escandallo=include_escandallo,
                include_nutrition=include_nutrition,
                include_baker_percentage=include_baker_percentage,
                include_images=include_images,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Vista previa PDF", f"No se pudo generar la vista previa:\n{exc}")
            return
        load_error = self.pdf_document.load(str(self._preview_path))
        if load_error != QPdfDocument.Error.None_:
            QMessageBox.critical(self, "Vista previa PDF", "No se pudo cargar la vista previa generada.")

    def cleanup_preview(self) -> None:
        self.pdf_view.setDocument(None)
        self.pdf_document.close()
        if self._preview_path is not None:
            try:
                os.unlink(self._preview_path)
            except (FileNotFoundError, PermissionError):
                # En Windows QPdfDocument puede liberar el descriptor después de
                # cerrar el diálogo. No bloqueamos el guardado por un temporal.
                pass
            self._preview_path = None


class CompactQuantityDelegate(QStyledItemDelegate):
    def __init__(self, on_commit=None, parent=None) -> None:
        super().__init__(parent)
        self.on_commit = on_commit

    def createEditor(self, parent, option, index):  # type: ignore[override]
        editor = QLineEdit(parent)
        editor.setFrame(False)
        editor.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        editor.setStyleSheet(
            "QLineEdit {"
            "padding: 0 6px;"
            "margin: 0;"
            "border: none;"
            "outline: 0;"
            "background: #FFFFFF;"
            "color: #16325C;"
            "selection-background-color: #DDEBFF;"
            "selection-color: #16325C;"
            "}"
            "QLineEdit:focus { border: none; outline: 0; }"
        )
        return editor

    def updateEditorGeometry(self, editor, option, index) -> None:  # type: ignore[override]
        editor.setGeometry(option.rect)

    def setEditorData(self, editor, index) -> None:  # type: ignore[override]
        if isinstance(editor, QLineEdit):
            editor.setText(str(index.data(Qt.ItemDataRole.DisplayRole) or "").replace("g", "").strip())
            editor.selectAll()
            return
        super().setEditorData(editor, index)

    def setModelData(self, editor, model, index) -> None:  # type: ignore[override]
        if isinstance(editor, QLineEdit):
            raw_value = editor.text().replace("g", "").strip()
            normalized = raw_value.replace(".", "").replace(",", ".")
            try:
                value = float(normalized) if normalized else 0.0
            except ValueError:
                value = 0.0
            text = f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
            model.setData(index, f"{text} g" if raw_value else "", Qt.ItemDataRole.EditRole)
        else:
            super().setModelData(editor, model, index)
        if callable(self.on_commit):
            self.on_commit()


class UnitComboDelegate(QStyledItemDelegate):
    def __init__(self, on_commit=None, parent=None) -> None:
        super().__init__(parent)
        self.on_commit = on_commit

    def createEditor(self, parent, option, index):  # type: ignore[override]
        editor = QComboBox(parent)
        editor.addItems(["g", "kg", "l", "ml"])
        editor.setEditable(True)
        line_edit = editor.lineEdit()
        if line_edit is not None:
            line_edit.setReadOnly(True)
            line_edit.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            line_edit.setFrame(False)
        editor.setFrame(False)
        editor.setFixedHeight(22)
        editor.setStyleSheet(
            "QComboBox {"
            "background: transparent;"
            "border: none;"
            "padding: 0 2px;"
            "margin: 0;"
            "color: #FFFFFF;"
            "selection-color: #FFFFFF;"
            "}"
            "QComboBox QLineEdit {"
            "background: transparent;"
            "border: none;"
            "padding: 0;"
            "margin: 0;"
            "color: #FFFFFF;"
            "selection-color: #FFFFFF;"
            "selection-background-color: transparent;"
            "}"
            "QComboBox::drop-down {"
            "border: none;"
            "width: 0px;"
            "}"
            "QComboBox::down-arrow {"
            "image: none;"
            "width: 0px;"
            "height: 0px;"
            "}"
            "QComboBox QAbstractItemView {"
            "background-color: #FFFFFF;"
            "border: 1px solid #CAD3DF;"
            "selection-background-color: #2F80ED;"
            "selection-color: #FFFFFF;"
            "}"
        )
        return editor

    def setEditorData(self, editor, index) -> None:  # type: ignore[override]
        if isinstance(editor, QComboBox):
            value = str(index.data(Qt.ItemDataRole.EditRole) or index.data(Qt.ItemDataRole.DisplayRole) or "g").strip().lower() or "g"
            idx = editor.findText(value)
            editor.setCurrentIndex(idx if idx >= 0 else 0)
            QTimer.singleShot(0, editor.showPopup)

    def setModelData(self, editor, model, index) -> None:  # type: ignore[override]
        if isinstance(editor, QComboBox):
            model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)
            if callable(self.on_commit):
                self.on_commit()
            return
        super().setModelData(editor, model, index)

    def updateEditorGeometry(self, editor, option, index) -> None:  # type: ignore[override]
        editor.setGeometry(option.rect.adjusted(2, 3, -2, -3))


class ProcessComboDelegate(QStyledItemDelegate):
    def __init__(self, options_getter=None, on_commit=None, parent=None) -> None:
        super().__init__(parent)
        self.options_getter = options_getter
        self.on_commit = on_commit

    def createEditor(self, parent, option, index):  # type: ignore[override]
        editor = QComboBox(parent)
        editor.setEditable(True)
        line_edit = editor.lineEdit()
        if line_edit is not None:
            line_edit.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        editor.setStyleSheet(
            "QComboBox {"
            "background: #FFFFFF;"
            "border: none;"
            "padding: 0 4px;"
            "margin: 0;"
            "color: #16325C;"
            "}"
            "QComboBox QLineEdit {"
            "background: #FFFFFF;"
            "border: none;"
            "padding: 0;"
            "margin: 0;"
            "color: #16325C;"
            "}"
            "QComboBox QAbstractItemView {"
            "background-color: #FFFFFF;"
            "border: 1px solid #CAD3DF;"
            "selection-background-color: #2F80ED;"
            "selection-color: #FFFFFF;"
            "}"
        )
        return editor

    def setEditorData(self, editor, index) -> None:  # type: ignore[override]
        if not isinstance(editor, QComboBox):
            return
        current = str(index.data(Qt.ItemDataRole.EditRole) or index.data(Qt.ItemDataRole.DisplayRole) or "").strip()
        options = []
        if callable(self.options_getter):
            try:
                raw_options = self.options_getter()
                if isinstance(raw_options, (list, tuple, set)):
                    options = [str(x or "").strip() for x in raw_options]
                else:
                    options = []
            except Exception:
                options = []
        cleaned = []
        for opt in options:
            if opt and opt not in cleaned:
                cleaned.append(opt)
        if "Masa final" not in cleaned:
            cleaned.insert(0, "Masa final")
        editor.blockSignals(True)
        editor.clear()
        editor.addItems(cleaned)
        editor.blockSignals(False)
        if current:
            idx = editor.findText(current)
            if idx >= 0:
                editor.setCurrentIndex(idx)
            else:
                editor.setEditText(current)
        elif cleaned:
            editor.setCurrentIndex(0)

    def setModelData(self, editor, model, index) -> None:  # type: ignore[override]
        if isinstance(editor, QComboBox):
            model.setData(index, editor.currentText().strip(), Qt.ItemDataRole.EditRole)
            if callable(self.on_commit):
                self.on_commit()
            return
        super().setModelData(editor, model, index)

    def updateEditorGeometry(self, editor, option, index) -> None:  # type: ignore[override]
        editor.setGeometry(option.rect.adjusted(2, 3, -2, -3))


class CompactTextDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):  # type: ignore[override]
        editor = QLineEdit(parent)
        editor.setFrame(False)
        editor.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        editor.setStyleSheet(
            "QLineEdit {"
            "padding: 0 6px;"
            "margin: 0;"
            "border: none;"
            "outline: 0;"
            "background: #FFFFFF;"
            "color: #16325C;"
            "selection-background-color: #DDEBFF;"
            "selection-color: #16325C;"
            "}"
            "QLineEdit:focus { border: none; outline: 0; }"
        )
        return editor

    def updateEditorGeometry(self, editor, option, index) -> None:  # type: ignore[override]
        editor.setGeometry(option.rect)


class ExpandablePlainTextEdit(QPlainTextEdit):
    def __init__(self, on_expand=None, parent=None) -> None:
        super().__init__(parent)
        self._on_expand = on_expand

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        if callable(self._on_expand):
            self._on_expand()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event) -> None:  # type: ignore[override]
        menu = self.createStandardContextMenu()
        menu.addSeparator()
        expand_action = menu.addAction("Abrir editor ampliado")
        if not callable(self._on_expand):
            expand_action.setEnabled(False)
        else:
            expand_action.triggered.connect(self._on_expand)
        menu.exec(event.globalPos())


class RichProcessTextEdit(QTextEdit):
    def contextMenuEvent(self, event) -> None:  # type: ignore[override]
        menu = self.createStandardContextMenu()
        menu.addSeparator()

        bold_action = menu.addAction("Negrita")
        bold_action.triggered.connect(self._toggle_bold_selection)

        size_action = menu.addAction("Cambiar tamaño de fuente")
        size_action.triggered.connect(self._change_selection_font_size)

        menu.exec(event.globalPos())

    def _toggle_bold_selection(self) -> None:
        cursor = self.textCursor()
        if not cursor.hasSelection():
            return
        fmt = QTextCharFormat()
        current_weight = cursor.charFormat().fontWeight()
        fmt.setFontWeight(QFont.Weight.Normal if current_weight >= QFont.Weight.Bold else QFont.Weight.Bold)
        cursor.mergeCharFormat(fmt)
        self.mergeCurrentCharFormat(fmt)

    def _change_selection_font_size(self) -> None:
        cursor = self.textCursor()
        if not cursor.hasSelection():
            return
        default_size = self.font().pointSizeF()
        current_size = cursor.charFormat().fontPointSize() or default_size or 11.0
        new_size, ok = QInputDialog.getInt(
            self,
            "Tamaño de fuente",
            "Nuevo tamaño (pt):",
            int(round(current_size)),
            6,
            72,
            1,
        )
        if not ok:
            return
        fmt = QTextCharFormat()
        fmt.setFontPointSize(float(new_size))
        cursor.mergeCharFormat(fmt)
        self.mergeCurrentCharFormat(fmt)


class RecipesPage(QWidget):
    COL_INGREDIENTE = 0
    COL_NOTA = 1
    COL_CANTIDAD = 2
    COL_PCT = 3
    COL_PROCESO = 4
    ESC_COL_INGREDIENTE = 0
    ESC_COL_CANTIDAD = 1
    ESC_COL_PCT = 2
    ESC_COL_EUR_KG = 3
    ESC_COL_PROMOCION = 4
    ESC_COL_EUR_KG_EFECTIVO = 5
    ESC_COL_EUR_LINEA = 6
    ESC_TOTALS_OFFSET = 1
    LINES_TOTALS_OFFSET = 1
    MIN_LINE_ROWS = 10
    PROCESO_RICH_HTML_KEY = "__proceso_rich_html"

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("RecipesPageRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.recipe_service = RecipeService()
        self.recipe_active_flow_service = RecipeActiveFlowService(recipe_service=self.recipe_service)
        self.pdf_service = PdfService()
        self.current_recipe_id: int | None = None
        self.current_base_recipe_id: int | None = None
        self.current_recipe_is_ireks = False
        self.customer_filter_selected_id: str = ""
        self.recipe_escandallo_data: dict[str, str] = {}
        self.recipe_elaboracion_data: dict[str, str] = {}
        self._proceso_rich_html: str = ""
        self.recipe_process_names: list[str] = ["Masa final"]
        self._is_loading_recipe = False
        self._document_import_pending = False
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(450)
        self._autosave_timer.timeout.connect(self._perform_autosave)
        self.current_issues: list[str] = []
        self._build_ui()
        self._load_customers()
        self._reload_recipe_list()
        self._new_recipe()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 11, 14, 14)
        root.setSpacing(10)

        ribbon, ribbon_layout = create_standard_top_ribbon()
        self.new_recipe_btn = create_standard_ribbon_button("Nueva", role="success", icon_name="plus.svg")
        self.save_recipe_btn = create_standard_ribbon_button("Guardar", role="primary", icon_name="save.svg")
        self.save_version_btn = create_standard_ribbon_button("Versión", role="warning", icon_name="history.svg")
        self.duplicate_recipe_btn = create_standard_ribbon_button("Duplicar", role="secondary", icon_name="file-text.svg")
        self.delete_recipe_btn = create_standard_ribbon_button("Eliminar", role="danger", icon_name="trash.svg")
        self.recalculate_recipe_btn = create_standard_ribbon_button("Recalcular", role="info", icon_name="refresh-cw.svg")
        self.promotions_btn = create_standard_ribbon_button("Promociones", role="warning", icon_name="badge-euro.svg")
        self.print_recipe_btn = create_standard_ribbon_button("Imprimir", role="secondary", icon_name="printer.svg")
        self.export_pdf_btn = create_standard_ribbon_button("PDF", role="secondary", icon_name="file-text.svg")
        self.export_excel_btn = create_standard_ribbon_button("Excel", role="secondary", icon_name="sheet.svg")

        self.new_recipe_btn.clicked.connect(self._start_new_recipe)
        self.save_recipe_btn.clicked.connect(self._save_recipe)
        self.save_version_btn.clicked.connect(self._save_version)
        self.duplicate_recipe_btn.clicked.connect(self._duplicate_recipe)
        self.delete_recipe_btn.clicked.connect(self._delete_recipe)
        self.recalculate_recipe_btn.clicked.connect(self._recalculate)
        self.promotions_btn.clicked.connect(self._open_customer_promotions)
        self.print_recipe_btn.clicked.connect(self._print_recipe)
        self.export_pdf_btn.clicked.connect(self._export_pdf)
        self.export_excel_btn.clicked.connect(self._export_excel)

        for button in (
            self.new_recipe_btn,
            self.save_recipe_btn,
            self.save_version_btn,
            self.duplicate_recipe_btn,
            self.delete_recipe_btn,
            self.recalculate_recipe_btn,
            self.promotions_btn,
            self.print_recipe_btn,
            self.export_pdf_btn,
            self.export_excel_btn,
        ):
            ribbon_layout.addWidget(button)
        ribbon_layout.addStretch(1)
        root.addWidget(ribbon)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("recipesMainSplitter")
        root.addWidget(splitter, 1)

        left_panel = QWidget()
        left_panel.setObjectName("recipesSidePanel")
        left_panel.setFixedWidth(332)
        left_layout = QVBoxLayout(left_panel)

        self.recipe_tabs = QTabWidget()
        self.recipe_tabs.setObjectName("recipeTabs")
        self.recipe_tabs.currentChanged.connect(self._on_recipe_tab_changed)
        left_layout.addWidget(self.recipe_tabs, 1)

        ireks_tab = QWidget()
        ireks_tab.setObjectName("recipeTabPage")
        ireks_tab.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        ireks_layout = QVBoxLayout(ireks_tab)
        ireks_search_row = QHBoxLayout()
        ireks_search_row.setContentsMargins(0, 0, 0, 0)
        ireks_search_row.setSpacing(6)
        self.ireks_recipe_search = QLineEdit()
        self.ireks_recipe_search.setPlaceholderText("Buscar por ocurrencia, receta, producto IREKS...")
        self.ireks_recipe_search.textChanged.connect(self._reload_recipe_list)
        ireks_search_row.addWidget(self.ireks_recipe_search, 1)
        self.document_recipe_search_btn = QPushButton("Documentación")
        self.document_recipe_search_btn.setObjectName("recipeDocumentSearchOpenButton")
        self.document_recipe_search_btn.setProperty("btnRole", "primary")
        self.document_recipe_search_btn.setToolTip("Buscar e importar una fórmula desde la biblioteca documental")
        self.document_recipe_search_btn.setIcon(QIcon(str(Path(__file__).resolve().parents[3] / "assets" / "icons" / "file-text.svg")))
        self.document_recipe_search_btn.setIconSize(QSize(16, 16))
        self.document_recipe_search_btn.setStyleSheet(
            "QPushButton { min-height: 32px; max-height: 32px; padding: 0 8px; "
            "background: #D9F0F2; color: #0B2F5B; border: 1px solid #8EBBC6; border-radius: 6px; }"
            "QPushButton:hover { background: #BFE4E8; border-color: #087E9C; }"
            "QPushButton:pressed { background: #A8D8DF; }"
        )
        self.ireks_recipe_search.setStyleSheet("min-height: 32px; max-height: 32px; padding-top: 0; padding-bottom: 0;")
        self.document_recipe_search_btn.clicked.connect(self._open_document_recipe_search)
        ireks_search_row.addWidget(self.document_recipe_search_btn)
        ireks_layout.addLayout(ireks_search_row)
        self.ireks_recipe_table = self._create_recipe_table()
        ireks_layout.addWidget(self.ireks_recipe_table, 1)
        self.recipe_tabs.addTab(ireks_tab, "IREKS")

        customer_tab = QWidget()
        customer_tab.setObjectName("recipeTabPage")
        customer_tab.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        customer_layout = QVBoxLayout(customer_tab)
        customer_filter_row = QHBoxLayout()
        customer_filter_row.setContentsMargins(0, 0, 0, 0)
        customer_filter_row.setSpacing(6)
        self.customer_filter_input = QLineEdit()
        self.customer_filter_input.setObjectName("customerRecipeFilterInput")
        self.customer_filter_input.setPlaceholderText("Filtrar clientes...")
        self.customer_filter_input.setFixedHeight(34)
        self.customer_filter_input.installEventFilter(self)
        self.customer_filter_input.textChanged.connect(self._on_customer_filter_text_changed)
        self.customer_filter_input.returnPressed.connect(self._select_first_customer_filter_result)
        customer_filter_row.addWidget(self.customer_filter_input, 1)
        self.customer_filter_clear_btn = QPushButton()
        self.customer_filter_clear_btn.setObjectName("customerRecipeFilterClearButton")
        self.customer_filter_clear_btn.setProperty("btnRole", "danger")
        self.customer_filter_clear_btn.setIcon(
            _white_icon_from_svg(Path(__file__).resolve().parents[3] / "assets" / "icons" / "eraser.svg")
        )
        self.customer_filter_clear_btn.setIconSize(QSize(18, 18))
        self.customer_filter_clear_btn.setFixedSize(34, 34)
        self.customer_filter_clear_btn.setToolTip("Limpiar filtro de clientes")
        self.customer_filter_clear_btn.setEnabled(False)
        self.customer_filter_clear_btn.clicked.connect(self._clear_customer_filter)
        customer_filter_row.addWidget(self.customer_filter_clear_btn)
        customer_layout.addLayout(customer_filter_row)

        self.customer_filter_results = QTableWidget(0, 2)
        self.customer_filter_results.setObjectName("customerRecipeFilterResults")
        self.customer_filter_results.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.customer_filter_results.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.customer_filter_results.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.customer_filter_results.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.customer_filter_results.setHorizontalHeaderLabels(["Código", "Cliente"])
        results_header = self.customer_filter_results.horizontalHeader()
        results_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        results_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.customer_filter_results.verticalHeader().setVisible(False)
        self.customer_filter_results.setMaximumHeight(180)
        self.customer_filter_results.setVisible(False)
        self.customer_filter_results.cellClicked.connect(self._select_customer_filter_result)
        customer_layout.addWidget(self.customer_filter_results)
        self.customer_recipe_table = self._create_recipe_table()
        customer_layout.addWidget(self.customer_recipe_table, 1)
        self.recipe_tabs.addTab(customer_tab, "Clientes")

        splitter.addWidget(left_panel)

        right_panel = QWidget()
        right_panel.setObjectName("recipesContentPanel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(1, 1)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(5)
        splitter.setSizes([332, 930])

        self.header_row = QWidget()
        self.header_row.setObjectName("recipesHeaderRow")
        self.header_row.setFixedHeight(68)

        self.recipe_header_box = QGroupBox("Receta")
        self.recipe_header_box.setObjectName("recipeHeaderBox")
        self.recipe_header_box.setFixedHeight(62)
        self.cliente_combo = QComboBox()
        self.cliente_combo.currentIndexChanged.connect(self._update_inline_customer_name)
        self.nombre_input = QLineEdit()
        self.nombre_input.setParent(self.recipe_header_box)
        self.nombre_input.setFixedHeight(24)
        self.nombre_input.textChanged.connect(self._schedule_autosave)
        self.nombre_input.returnPressed.connect(self._flush_autosave)
        self.nombre_input.editingFinished.connect(self._flush_autosave)
        self.codigo_input = QLineEdit()
        self.version_input = QLineEdit("1.0")
        self.estado_input = QLineEdit("borrador")
        self.masa_spin = self._double_spin(0, 1_000_000, 2)
        self.peso_spin = self._double_spin(0, 100_000, 2)
        self.piezas_spin = QSpinBox()
        self.piezas_spin.setRange(0, 1_000_000)
        self.piezas_spin.setValue(1)
        self.peso_spin.valueChanged.connect(self._refresh_escandallo_table)
        self.piezas_spin.valueChanged.connect(self._refresh_escandallo_table)
        self.merma_spin = self._double_spin(0, 100, 2)
        self.merma_spin.valueChanged.connect(self._refresh_escandallo_table)

        self.customer_header_box = QGroupBox("Cliente")
        self.customer_header_box.setObjectName("customerHeaderBox")
        self.customer_header_box.setFixedHeight(64)
        self.customer_name_value = QLabel("")
        self.customer_name_value.setObjectName("customerNameValue")
        self.customer_name_value.setParent(self.customer_header_box)
        self.customer_name_value.setFixedHeight(34)
        self.customer_name_value.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.customer_name_value.setStyleSheet("color: #16325C;")
        self.change_customer_btn = QPushButton()
        self.change_customer_btn.setObjectName("changeRecipeCustomerButton")
        self.change_customer_btn.setProperty("btnRole", "primary")
        self.change_customer_btn.setIcon(
            _white_icon_from_svg(Path(__file__).resolve().parents[3] / "assets" / "icons" / "user-round-pen.svg")
        )
        self.change_customer_btn.setIconSize(QSize(18, 18))
        self.change_customer_btn.setFixedSize(34, 34)
        self.change_customer_btn.setToolTip("Cambiar cliente de la receta")
        self.change_customer_btn.setEnabled(False)
        self.change_customer_btn.clicked.connect(self._change_recipe_customer)
        self.change_customer_btn.setParent(self.customer_header_box)

        self.recipe_header_box.setParent(self.header_row)
        self.customer_header_box.setParent(self.header_row)
        self.header_separator = QFrame(self.header_row)
        self.header_separator.setObjectName("recipesHeaderSeparator")
        self.header_separator.setFrameShape(QFrame.Shape.VLine)
        self.header_separator.setFrameShadow(QFrame.Shadow.Plain)
        self.header_row.installEventFilter(self)
        right_layout.addWidget(self.header_row)
        self._layout_header_boxes_abs()
        self._layout_header_fields_abs()

        recipe_ribbon, recipe_ribbon_layout = create_standard_top_ribbon()
        recipe_ribbon.setObjectName("recipeRibbon")
        self.scale_btn = create_standard_ribbon_button("Escalar", role="primary", icon_name="scale.svg")
        self.load_base_btn = create_standard_ribbon_button("Cargar", role="success", icon_name="download.svg")
        self.recipe_pdf_btn = create_standard_ribbon_button("Pdf", role="danger", icon_name="file-text.svg")
        self.recipe_excel_btn = create_standard_ribbon_button("Excel", role="success", icon_name="sheet.svg")
        self.scale_btn.clicked.connect(self._scale_recipe)
        self.load_base_btn.clicked.connect(self._load_base_recipe_template)
        self.recipe_pdf_btn.clicked.connect(self._export_pdf)
        self.recipe_excel_btn.clicked.connect(self._export_excel)
        recipe_ribbon_layout.addWidget(self.scale_btn)
        recipe_ribbon_layout.addWidget(self.load_base_btn)
        recipe_ribbon_layout.addWidget(self.recipe_pdf_btn)
        recipe_ribbon_layout.addWidget(self.recipe_excel_btn)
        self.load_base_btn.setVisible(False)
        recipe_ribbon_layout.addStretch()

        self.recipe_process_row = QWidget()
        recipe_process_layout = QHBoxLayout(self.recipe_process_row)
        recipe_process_layout.setContentsMargins(8, 0, 8, 0)
        recipe_process_layout.setSpacing(6)
        recipe_process_layout.addWidget(QLabel("Proceso"))
        self.active_process_combo = QComboBox()
        self.active_process_combo.setEditable(False)
        self.active_process_combo.setFixedWidth(160)
        self.active_process_combo.setFixedHeight(30)
        self.active_process_combo.setStyleSheet(
            "QComboBox { min-width: 142px; max-width: 142px; min-height: 28px; max-height: 28px; padding: 0 8px; border: 1px solid #CBD5E1; }"
        )
        self.active_process_combo.currentTextChanged.connect(self._on_active_process_changed)
        recipe_process_layout.addWidget(self.active_process_combo)
        self.add_process_btn = QPushButton()
        self.add_process_btn.setIcon(_process_add_icon())
        self.add_process_btn.setIconSize(QSize(24, 24))
        self.add_process_btn.setObjectName("addRecipeProcessButton")
        self.add_process_btn.setFixedSize(34, 30)
        self.add_process_btn.setToolTip("Añadir proceso")
        self.add_process_btn.setAccessibleName("Añadir proceso")
        self.add_process_btn.setStyleSheet(
            "QPushButton { min-width: 32px; max-width: 32px; min-height: 28px; max-height: 28px; padding: 0px; font-family: 'Segoe UI'; font-size: 24px; font-weight: 700; background-color: #DCFCE7; color: #14532D; border: 1px solid #86EFAC; border-radius: 7px; }"
            "QPushButton:hover { background-color: #BBF7D0; color: #14532D; border-color: #4ADE80; }"
            "QPushButton:pressed { background-color: #86EFAC; color: #14532D; }"
        )
        self.add_process_btn.clicked.connect(self._add_process)
        recipe_process_layout.addWidget(self.add_process_btn)
        self.delete_process_btn = QPushButton()
        self.delete_process_btn.setObjectName("deleteRecipeProcessButton")
        self.delete_process_btn.setFixedSize(34, 30)
        self.delete_process_btn.setIcon(QIcon(str(Path(__file__).resolve().parents[3] / "assets" / "icons" / "trash.svg")))
        self.delete_process_btn.setIconSize(QSize(20, 20))
        self.delete_process_btn.setToolTip("Eliminar proceso y sus ingredientes")
        self.delete_process_btn.setAccessibleName("Eliminar proceso y sus ingredientes")
        self.delete_process_btn.setStyleSheet(
            "QPushButton { min-width: 32px; max-width: 32px; min-height: 28px; max-height: 28px; padding: 0px; background-color: #FEE2E2; border: 1px solid #FCA5A5; border-radius: 7px; }"
            "QPushButton:hover { background-color: #FECACA; }"
            "QPushButton:pressed { background-color: #FCA5A5; }"
        )
        self.delete_process_btn.clicked.connect(self._delete_process_with_ingredients)
        recipe_process_layout.addWidget(self.delete_process_btn)
        for text, tooltip, callback in (
            ("Renombrar", "Cambiar el nombre del proceso", self._rename_process),
            ("↑", "Mover el proceso antes", lambda: self._reorder_process(-1)),
            ("↓", "Mover el proceso después", lambda: self._reorder_process(1)),
        ):
            button = QPushButton(text)
            button.setToolTip(tooltip)
            button.setStyleSheet("min-height: 28px; max-height: 28px; padding: 0 8px;")
            button.clicked.connect(callback)
            recipe_process_layout.addWidget(button)
        recipe_process_layout.addStretch()

        lines_group = QGroupBox()
        lines_group.setObjectName("recipeLinesGroup")
        lines_layout = QVBoxLayout(lines_group)
        lines_layout.setContentsMargins(6, 2, 6, 6)
        lines_layout.setSpacing(5)
        lines_title = QLabel("Líneas de receta")
        lines_title.setStyleSheet("background: transparent; border: none;")
        lines_layout.addWidget(lines_title)

        self.lines_table = QTableWidget(0, 5)
        self.lines_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.lines_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.lines_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lines_table.setStyleSheet(
            "QTableWidget::item:selected { color: #FFFFFF; }"
            "QTableWidget::item:focus { border: none; outline: 0; }"
        )
        self.lines_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.lines_table.setHorizontalHeaderLabels(["Ingrediente", "", "Cantidad", "%", "Proceso"])
        lines_header = self.lines_table.horizontalHeader()
        lines_header.setSectionResizeMode(self.COL_INGREDIENTE, QHeaderView.ResizeMode.Stretch)
        lines_header.setSectionResizeMode(self.COL_NOTA, QHeaderView.ResizeMode.Fixed)
        lines_header.setSectionResizeMode(self.COL_CANTIDAD, QHeaderView.ResizeMode.Fixed)
        lines_header.setSectionResizeMode(self.COL_PCT, QHeaderView.ResizeMode.Fixed)
        lines_header.setSectionResizeMode(self.COL_PROCESO, QHeaderView.ResizeMode.Fixed)
        lines_header.setFixedHeight(26)
        self.lines_table.setColumnWidth(self.COL_NOTA, 80)
        self.lines_table.setColumnWidth(self.COL_CANTIDAD, 116)
        self.lines_table.setColumnWidth(self.COL_PCT, 96)
        self.lines_table.setColumnWidth(self.COL_PROCESO, 190)
        self.lines_table.setItemDelegateForColumn(
            self.COL_NOTA,
            CompactTextDelegate(self.lines_table),
        )
        self.lines_table.setItemDelegateForColumn(
            self.COL_CANTIDAD,
            CompactQuantityDelegate(self._on_lines_changed, self.lines_table),
        )
        self.lines_table.setItemDelegateForColumn(
            self.COL_PROCESO,
            ProcessComboDelegate(self._available_process_names, self._on_lines_changed, self.lines_table),
        )
        self.lines_table.verticalHeader().setDefaultSectionSize(30)
        self.lines_table.verticalHeader().setMinimumSectionSize(30)
        lines_table_height = (
            self.lines_table.horizontalHeader().height()
            + self.lines_table.verticalHeader().defaultSectionSize() * self.MIN_LINE_ROWS
            + 8
        )
        self.lines_table.setMinimumHeight(lines_table_height)
        self.lines_table.itemDoubleClicked.connect(self._on_line_double_click)
        self.lines_table.itemChanged.connect(self._on_line_item_changed)
        self.lines_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.lines_table.customContextMenuRequested.connect(self._show_lines_context_menu)
        lines_layout.addWidget(self.lines_table, 1)
        self.lines_totals_frame = QFrame()
        self.lines_totals_frame.setObjectName("recipeLinesTotalsFrame")
        lines_totals_layout = QVBoxLayout(self.lines_totals_frame)
        lines_totals_layout.setContentsMargins(0, 0, 0, 0)
        self.lines_totals_table = QTableWidget(1, 6)
        self.lines_totals_table.horizontalHeader().setVisible(False)
        self.lines_totals_table.verticalHeader().setVisible(False)
        self.lines_totals_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.lines_totals_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.lines_totals_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lines_totals_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.lines_totals_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.lines_totals_table.setFixedHeight(34)
        self.lines_totals_table.setShowGrid(False)
        self.lines_totals_table.setFrameShape(QFrame.Shape.NoFrame)
        self.lines_totals_table.setStyleSheet(
            "QTableWidget { background-color: transparent; border: none; }"
            "QTableWidget::item { background-color: transparent; color: #FFFFFF; border: none; padding: 0 8px; }"
        )
        lines_totals_layout.addWidget(self.lines_totals_table)
        lines_layout.addWidget(self.lines_totals_frame)
        lines_header.sectionResized.connect(lambda *_args: self._refresh_recipe_lines_totals())
        lines_header.geometriesChanged.connect(self._refresh_recipe_lines_totals)
        self._refresh_process_controls(["Masa final"], preserve_active=False)

        summary_group = QGroupBox("Resumen tecnico")
        summary_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        summary_root_layout = QVBoxLayout(summary_group)
        summary_root_layout.setContentsMargins(8, 8, 8, 8)
        summary_root_layout.setSpacing(8)
        summary_top_layout = QHBoxLayout()
        summary_top_layout.setContentsMargins(0, 0, 0, 0)
        summary_top_layout.setSpacing(8)
        self.total_harinas_lbl = QLabel("0.00 g")
        self.total_liquidos_lbl = QLabel("0.00 g")
        self.hidratacion_lbl = QLabel("0.00 %")
        self.total_panadero_lbl = QLabel("0.00 %")
        self.masa_total_lbl = QLabel("0.00 g")
        for value_lbl in (
            self.masa_total_lbl,
            self.total_harinas_lbl,
            self.total_liquidos_lbl,
            self.hidratacion_lbl,
            self.total_panadero_lbl,
        ):
            value_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        summary_pill_style = (
            "QFrame[summaryPill='true'] {"
            "background-color: #F8FAFD;"
            "border: 1px solid #CAD3DF;"
            "border-radius: 14px;"
            "}"
            "QLabel[summaryIcon='true'] {"
            "background-color: #FFFFFF;"
            "border: 1px solid #D7DEE8;"
            "border-radius: 14px;"
            "color: #16325C;"
            "font-weight: 800;"
            "}"
            "QLabel[summaryLabel='true'] { color: #51627A; font-size: 11px; }"
            "QLabel[summaryValue='true'] { color: #16325C; font-size: 12px; font-weight: 800; }"
        )

        summary_icon_dir = Path(__file__).resolve().parents[3] / "assets" / "icons"

        def summary_pill(icon_path: Path, label_text: str, value_lbl: QLabel) -> QFrame:
            pill = QFrame()
            pill.setProperty("summaryPill", True)
            pill.setStyleSheet(summary_pill_style)
            pill.setFixedSize(150, 48)
            pill.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            pill_layout = QHBoxLayout(pill)
            pill_layout.setContentsMargins(7, 4, 8, 4)
            pill_layout.setSpacing(6)
            icon_lbl = QLabel()
            icon_lbl.setProperty("summaryIcon", True)
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_lbl.setFixedSize(28, 28)
            icon_pixmap = QPixmap(str(icon_path))
            if not icon_pixmap.isNull():
                icon_lbl.setPixmap(
                    icon_pixmap.scaled(21, 21, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                )
            label_lbl = QLabel(label_text)
            label_lbl.setProperty("summaryLabel", True)
            label_lbl.setFixedHeight(18)
            label_lbl.setFixedWidth(96)
            value_lbl.setProperty("summaryValue", True)
            value_lbl.setStyleSheet("QLabel[summaryValue='true'] { color: #16325C; font-size: 12px; font-weight: 800; }")
            value_lbl.setFixedHeight(20)
            value_lbl.setFixedWidth(96)
            text_layout = QVBoxLayout()
            text_layout.setContentsMargins(0, 0, 0, 0)
            text_layout.setSpacing(0)
            text_layout.addWidget(label_lbl)
            text_layout.addWidget(value_lbl)
            pill_layout.addWidget(icon_lbl)
            pill_layout.addLayout(text_layout, 1)
            return pill

        fields = [
            (summary_icon_dir / "icon_masa.png", "Masa total", self.masa_total_lbl),
            (summary_icon_dir / "icon_trigo.png", "Total harinas", self.total_harinas_lbl),
            (summary_icon_dir / "icon_bol.png", "Total liquidos", self.total_liquidos_lbl),
            (summary_icon_dir / "icon_gota.png", "Hidratacion", self.hidratacion_lbl),
        ]
        for icon_path, label, value in fields:
            summary_top_layout.addWidget(summary_pill(icon_path, label, value))
        summary_top_layout.addStretch(1)

        nutrition_panel = QWidget()
        nutrition_panel.setObjectName("nutritionPanel")
        nutrition_panel.setMinimumWidth(272)
        nutrition_panel.setMaximumWidth(272)
        nutrition_panel.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        nutrition_layout = QVBoxLayout(nutrition_panel)
        nutrition_layout.setContentsMargins(0, 0, 0, 0)
        nutrition_layout.setSpacing(0)
        self.nutrition_card = NutritionCard(parent=nutrition_panel)
        nutrition_layout.addWidget(self.nutrition_card, 0, Qt.AlignmentFlag.AlignTop)

        summary_root_layout.addLayout(summary_top_layout)

        process_group = QGroupBox("Proceso")
        process_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        process_layout = QVBoxLayout(process_group)
        process_layout.setContentsMargins(8, 8, 8, 8)
        process_layout.setSpacing(4)
        notes_group = QGroupBox("Observaciones")
        notes_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        notes_layout = QVBoxLayout(notes_group)
        self.observaciones_input = QPlainTextEdit()
        self.observaciones_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.observaciones_input.setPlaceholderText("Observaciones...")
        self.proceso_input = ExpandablePlainTextEdit(self._open_process_editor_dialog)
        self.proceso_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.proceso_input.setPlaceholderText("Proceso...")
        self.proceso_input.setToolTip("Doble clic para abrir editor ampliado")
        text_panel_style = (
            "QPlainTextEdit {"
            "background-color: #F8FAFD;"
            "border: 1px solid #CAD3DF;"
            "border-radius: 6px;"
            "padding: 6px 8px;"
            "}"
            "QPlainTextEdit:focus {"
            "background-color: #F8FAFD;"
            "border: 1px solid #CAD3DF;"
            "}"
        )
        self.proceso_input.setStyleSheet(text_panel_style)
        self.proceso_input.textChanged.connect(self._on_proceso_plain_text_changed)
        self.observaciones_input.setStyleSheet(text_panel_style)
        process_layout.addWidget(self.proceso_input, 1)
        self.expand_process_shortcut = QShortcut(QKeySequence("Ctrl+Shift+P"), self)
        self.expand_process_shortcut.activated.connect(self._open_process_editor_dialog)
        notes_layout.addWidget(self.observaciones_input, 1)
        self.editor_tabs = QTabWidget()
        self.editor_tabs.setObjectName("recipeEditorTabs")
        receta_tab = QWidget()
        receta_tab.setObjectName("recipeEditorTabPage")
        receta_tab.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        receta_tab_layout = QVBoxLayout(receta_tab)
        receta_tab_layout.setContentsMargins(0, 0, 0, 0)
        receta_tab_layout.setSpacing(4)

        self.recipe_process_row.setObjectName("recipeProcessRow")
        recipe_top_row = QWidget()
        recipe_top_row.setObjectName("recipeTopRow")
        recipe_top_row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        recipe_top_layout = QVBoxLayout(recipe_top_row)
        recipe_top_layout.setContentsMargins(0, 0, 0, 0)
        recipe_top_layout.setSpacing(8)
        recipe_top_layout.addWidget(self.recipe_process_row)
        recipe_top_layout.addWidget(recipe_ribbon)
        recipe_content_row = QWidget()
        recipe_content_row.setObjectName("recipeContentRow")
        recipe_content_row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        recipe_content_row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        recipe_content_layout = QHBoxLayout(recipe_content_row)
        recipe_content_layout.setContentsMargins(0, 0, 0, 0)
        recipe_content_layout.setSpacing(8)
        receta_left_panel = QWidget()
        receta_left_panel.setObjectName("recipeEditorTabPage")
        receta_left_panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        receta_left_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        receta_left_layout = QVBoxLayout(receta_left_panel)
        receta_left_layout.setContentsMargins(0, 0, 0, 0)
        receta_left_layout.setSpacing(8)
        receta_left_layout.addWidget(lines_group, 1)
        recipe_content_layout.addWidget(receta_left_panel, 1)
        recipe_content_layout.addWidget(nutrition_panel)
        receta_tab_layout.addWidget(recipe_content_row, 1)
        receta_tab_layout.addWidget(summary_group)
        self.editor_tabs.addTab(receta_tab, "Receta")

        escandallo_tab = QWidget()
        escandallo_tab.setObjectName("recipeEditorTabPage")
        escandallo_tab.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        escandallo_layout = QVBoxLayout(escandallo_tab)
        escandallo_layout.setContentsMargins(0, 0, 0, 0)
        escandallo_layout.setSpacing(4)

        escandallo_filter_row = QHBoxLayout()
        escandallo_filter_row.setContentsMargins(0, 0, 0, 4)
        escandallo_filter_row.addWidget(QLabel("Escandallo del proceso"))
        self.escandallo_process_combo = QComboBox()
        self.escandallo_process_combo.setMinimumWidth(180)
        self.escandallo_process_combo.addItems(self.recipe_process_names)
        self.escandallo_process_combo.currentTextChanged.connect(self._on_escandallo_process_changed)
        escandallo_filter_row.addWidget(self.escandallo_process_combo)
        escandallo_filter_row.addStretch(1)
        escandallo_layout.addLayout(escandallo_filter_row)

        escandallo_group = QGroupBox()
        escandallo_group.setObjectName("escandalloGroup")
        escandallo_group_layout = QVBoxLayout(escandallo_group)
        escandallo_group_layout.setContentsMargins(8, 8, 8, 8)
        escandallo_group_layout.setSpacing(6)
        self.escandallo_table = QTableWidget(0, 7)
        self.escandallo_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.escandallo_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.escandallo_table.setHorizontalHeaderLabels(
            ["Ingrediente", "Cant.", "%", "€/kg", "Promo", "€/kg neto", "Importe"]
        )
        escandallo_header = self.escandallo_table.horizontalHeader()
        escandallo_header.setSectionResizeMode(self.ESC_COL_INGREDIENTE, QHeaderView.ResizeMode.Stretch)
        for column, width in (
            (self.ESC_COL_CANTIDAD, 92),
            (self.ESC_COL_PCT, 58),
            (self.ESC_COL_EUR_KG, 68),
            (self.ESC_COL_PROMOCION, 78),
            (self.ESC_COL_EUR_KG_EFECTIVO, 78),
            (self.ESC_COL_EUR_LINEA, 78),
        ):
            escandallo_header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            self.escandallo_table.setColumnWidth(column, width)
        self.escandallo_table.setColumnHidden(self.ESC_COL_PCT, True)
        self.escandallo_table.itemChanged.connect(self._on_escandallo_item_changed)
        escandallo_header.sectionResized.connect(lambda *_args: self._refresh_escandallo_table())
        escandallo_header.geometriesChanged.connect(self._refresh_escandallo_table)
        escandallo_group_layout.addWidget(self.escandallo_table, 1)
        self.escandallo_totals_frame = QFrame()
        self.escandallo_totals_frame.setObjectName("escandalloTotalsFrame")
        escandallo_totals_layout = QVBoxLayout(self.escandallo_totals_frame)
        escandallo_totals_layout.setContentsMargins(0, 0, 0, 0)
        self.escandallo_totals_table = QTableWidget(1, 8)
        self.escandallo_totals_table.horizontalHeader().setVisible(False)
        self.escandallo_totals_table.verticalHeader().setVisible(False)
        self.escandallo_totals_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.escandallo_totals_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.escandallo_totals_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.escandallo_totals_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.escandallo_totals_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.escandallo_totals_table.setFixedHeight(34)
        self.escandallo_totals_table.setColumnHidden(self.ESC_COL_PCT + self.ESC_TOTALS_OFFSET, True)
        self.escandallo_totals_table.setShowGrid(False)
        self.escandallo_totals_table.setFrameShape(QFrame.Shape.NoFrame)
        self.escandallo_totals_table.setStyleSheet(
            "QTableWidget { background-color: transparent; border: none; }"
            "QTableWidget::item { background-color: transparent; color: #FFFFFF; border: none; padding: 0 8px; }"
        )
        escandallo_totals_layout.addWidget(self.escandallo_totals_table)
        escandallo_group_layout.addWidget(self.escandallo_totals_frame)
        escandallo_content_row = QHBoxLayout()
        escandallo_content_row.setContentsMargins(0, 0, 0, 0)
        escandallo_content_row.setSpacing(8)
        escandallo_content_row.addWidget(escandallo_group, 1)
        self.total_panel = QFrame()
        self.total_panel.setObjectName("totalPanel")
        self.total_panel.setFixedWidth(300)
        self.total_panel.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        total_panel_layout = QVBoxLayout(self.total_panel)
        total_panel_layout.setContentsMargins(12, 12, 12, 12)
        total_panel_layout.setSpacing(10)

        def total_panel_pill(label_text: str, value_widget: QWidget, background: str, height: int = 72) -> QFrame:
            pill = QFrame()
            pill.setStyleSheet(
                "QFrame {"
                f"background-color: {background};"
                "border: none; border-radius: 12px;"
                "}"
                "QLabel { background: transparent; border: none; color: #16325C; }"
                "QLineEdit { background: transparent; border: none; color: #16325C; font-weight: 800; }"
            )
            pill.setFixedHeight(height)
            pill_layout = QVBoxLayout(pill)
            pill_layout.setContentsMargins(12, 7, 12, 7)
            pill_layout.setSpacing(0)
            label = QLabel(label_text)
            label.setStyleSheet("font-size: 16px; color: #51627A;")
            pill_layout.addWidget(label)
            pill_layout.addWidget(value_widget)
            return pill

        self.total_panel_total_masa_lbl = QLabel("0,00 g")
        self.total_panel_total_masa_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.total_panel_total_masa_lbl.setStyleSheet("font-size: 18px; font-weight: 800;")
        self.total_panel_peso_pieza_input = QLineEdit()
        self.total_panel_peso_pieza_input.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.total_panel_peso_pieza_input.setStyleSheet(
            "font-size: 18px; font-weight: 800; background-color: #FFFFFF; border: 1px solid #86EFAC; border-radius: 6px;"
        )
        self.total_panel_peso_pieza_input.editingFinished.connect(self._on_total_panel_peso_pieza_changed)
        self.total_panel_merma_input = QLineEdit()
        self.total_panel_merma_input.setFixedWidth(76)
        self.total_panel_merma_input.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.total_panel_merma_input.setStyleSheet(
            "font-size: 14px; font-weight: 700; background-color: #FFFFFF; border: 1px solid #FDA4AF; border-radius: 6px;"
        )
        self.total_panel_merma_input.editingFinished.connect(self._on_total_panel_merma_changed)
        self.total_panel_peso_terminado_lbl = QLabel("0,00 g")
        self.total_panel_peso_terminado_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.total_panel_peso_terminado_lbl.setStyleSheet("font-size: 18px; font-weight: 800;")
        peso_terminado_values = QWidget()
        peso_terminado_values.setStyleSheet("background: transparent; border: none;")
        peso_terminado_layout = QHBoxLayout(peso_terminado_values)
        peso_terminado_layout.setContentsMargins(0, 0, 0, 0)
        peso_terminado_layout.setSpacing(6)
        peso_terminado_layout.addWidget(QLabel("Merma"))
        peso_terminado_layout.addWidget(self.total_panel_merma_input)
        peso_terminado_layout.addWidget(self.total_panel_peso_terminado_lbl, 1)
        self.total_panel_total_piezas_lbl = QLabel("0 Uds")
        self.total_panel_total_piezas_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.total_panel_total_piezas_lbl.setStyleSheet("font-size: 18px; font-weight: 800;")
        self.total_panel_coste_unitario_lbl = QLabel("0,00 €")
        self.total_panel_coste_unitario_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.total_panel_coste_unitario_lbl.setStyleSheet("font-size: 18px; font-weight: 800;")
        total_panel_layout.addWidget(total_panel_pill("Total masa", self.total_panel_total_masa_lbl, "#DBEAFE"))
        total_panel_layout.addWidget(total_panel_pill("Peso por pieza en masa", self.total_panel_peso_pieza_input, "#DCFCE7"))
        total_panel_layout.addWidget(total_panel_pill("Peso por pieza terminada", peso_terminado_values, "#FFE4E6", height=82))
        total_panel_layout.addWidget(total_panel_pill("Total piezas", self.total_panel_total_piezas_lbl, "#FEF3C7"))
        total_panel_layout.addWidget(total_panel_pill("Coste unitario", self.total_panel_coste_unitario_lbl, "#F3E8FF"))
        total_panel_layout.addStretch(1)
        escandallo_content_row.addWidget(self.total_panel)
        escandallo_layout.addLayout(escandallo_content_row, 1)

        self.escandallo_summary_group = QGroupBox()
        self.escandallo_summary_group.setObjectName("escandalloSummaryGroup")
        escandallo_summary_layout = QHBoxLayout(self.escandallo_summary_group)
        escandallo_summary_layout.setContentsMargins(8, 8, 8, 8)
        escandallo_summary_layout.setSpacing(8)
        escandallo_summary_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.escandallo_total_masa_lbl = QLabel("0,00 g")
        self.escandallo_peso_pieza_lbl = QLabel("0,00 g")
        self.escandallo_total_piezas_lbl = QLabel("0")
        self.escandallo_coste_unitario_lbl = QLabel("0,00 €")
        for label in (
            self.escandallo_total_masa_lbl,
            self.escandallo_peso_pieza_lbl,
            self.escandallo_total_piezas_lbl,
            self.escandallo_coste_unitario_lbl,
        ):
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        def escandallo_pill(label_text: str, value_label: QLabel, background: str) -> QFrame:
            pill = QFrame()
            pill.setStyleSheet(
                "QFrame {"
                f"background-color: {background};"
                "border: none; border-radius: 14px;"
                "}"
                "QLabel { background: transparent; border: none; }"
                "QLabel[pillLabel='true'] { color: #51627A; font-size: 13px; }"
                "QLabel[pillValue='true'] { color: #16325C; font-size: 12px; font-weight: 800; }"
            )
            pill.setFixedSize(150, 48)
            pill_layout = QVBoxLayout(pill)
            pill_layout.setContentsMargins(10, 5, 10, 5)
            pill_layout.setSpacing(0)
            label = QLabel(label_text)
            label.setProperty("pillLabel", True)
            value_label.setProperty("pillValue", True)
            pill_layout.addWidget(label)
            pill_layout.addWidget(value_label)
            return pill

        for label_text, value_label, background in (
            ("Total masa", self.escandallo_total_masa_lbl, "#DBEAFE"),
            ("Peso por pieza", self.escandallo_peso_pieza_lbl, "#DCFCE7"),
            ("Total piezas", self.escandallo_total_piezas_lbl, "#FEF3C7"),
            ("Coste unitario", self.escandallo_coste_unitario_lbl, "#F3E8FF"),
        ):
            escandallo_summary_layout.addWidget(
                escandallo_pill(label_text, value_label, background),
                0,
                Qt.AlignmentFlag.AlignVCenter,
            )
        escandallo_summary_layout.addStretch(1)
        escandallo_layout.addWidget(self.escandallo_summary_group)
        self.editor_tabs.addTab(escandallo_tab, "Escandallo")

        proceso_tab = QWidget()
        proceso_tab.setObjectName("recipeEditorTabPage")
        proceso_tab.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        proceso_tab_layout = QVBoxLayout(proceso_tab)
        proceso_tab_layout.setContentsMargins(0, 0, 0, 0)
        proceso_tab_layout.setSpacing(0)
        proceso_tab_layout.addWidget(process_group, 1)
        self.editor_tabs.addTab(proceso_tab, "Proceso")

        observaciones_tab = QWidget()
        observaciones_tab.setObjectName("recipeEditorTabPage")
        observaciones_tab.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        observaciones_tab_layout = QVBoxLayout(observaciones_tab)
        observaciones_tab_layout.setContentsMargins(0, 0, 0, 0)
        observaciones_tab_layout.setSpacing(0)
        observaciones_tab_layout.addWidget(notes_group, 1)
        self.editor_tabs.addTab(observaciones_tab, "Observaciones")

        imagenes_tab = QWidget()
        imagenes_tab.setObjectName("recipeEditorTabPage")
        imagenes_tab.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.images_ribbon = QWidget(imagenes_tab)
        self.images_ribbon.setObjectName("recipesImagesRibbon")
        self.images_ribbon.setGeometry(0, 0, 928, 56)
        self.images_list = QListWidget()
        self.images_list.setParent(imagenes_tab)
        self.images_list.setGeometry(0, 68, 928, 360)
        self.images_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.images_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.images_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.images_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.images_list.setMovement(QListWidget.Movement.Snap)
        self.images_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.images_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.images_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.images_list.setSpacing(10)
        self.images_list.setIconSize(QSize(132, 98))
        self.images_list.setGridSize(QSize(154, 140))
        self.images_list.setFrameShape(QFrame.Shape.NoFrame)
        self.images_list.setStyleSheet(
            """
            QListWidget {
                background: transparent;
                border: none;
            }
            QListWidget::item {
                border: 1px solid #CAD3DF;
                border-radius: 10px;
                padding: 8px;
                margin: 2px;
                background: #F8FAFD;
            }
            QListWidget::item:selected {
                border: 1px solid #3B82F6;
                background: #EAF2FF;
                color: #16325C;
            }
            """
        )
        self.images_list.itemDoubleClicked.connect(self._preview_recipe_image)
        self.images_list.customContextMenuRequested.connect(self._show_images_context_menu)
        self.images_list.model().rowsMoved.connect(lambda *_args: self._schedule_autosave())
        self.add_image_btn = QPushButton("Añadir imagen", self.images_ribbon)
        self.add_image_btn.setProperty("btnRole", "secondary")
        self.add_image_btn.setGeometry(10, 8, 120, 28)
        self.add_image_btn.setFixedHeight(28)
        self.add_image_btn.setStyleSheet(
            "QPushButton { min-height: 28px; max-height: 28px; padding: 0 8px; font-size: 12px; "
            "background-color: #2FA84F; color: white; border: none; border-radius: 6px; }"
            "QPushButton:hover { background-color: #279344; }"
            "QPushButton:pressed { background-color: #1F7D38; }"
        )
        self.remove_image_btn = QPushButton("Quitar", self.images_ribbon)
        self.remove_image_btn.setProperty("btnRole", "danger")
        self.remove_image_btn.setGeometry(138, 8, 90, 28)
        self.remove_image_btn.setFixedHeight(28)
        self.remove_image_btn.setStyleSheet(
            "QPushButton { min-height: 28px; max-height: 28px; padding: 0 8px; font-size: 12px; }"
        )
        self.set_main_image_btn = QPushButton("Marcar principal", self.images_ribbon)
        self.set_main_image_btn.setProperty("btnRole", "primary")
        self.set_main_image_btn.setGeometry(236, 8, 140, 28)
        self.set_main_image_btn.setFixedHeight(28)
        self.set_main_image_btn.setStyleSheet(
            "QPushButton { min-height: 28px; max-height: 28px; padding: 0 8px; font-size: 12px; }"
        )
        self.add_image_btn.clicked.connect(self._add_recipe_image)
        self.remove_image_btn.clicked.connect(self._remove_recipe_images)
        self.set_main_image_btn.clicked.connect(self._mark_main_recipe_image)
        separator = QFrame(imagenes_tab)
        separator.setGeometry(0, 56, 928, 1)
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Plain)
        separator.setStyleSheet("color: #D7DEE8;")
        self.editor_tabs.addTab(imagenes_tab, "Imagenes")
        self.editor_tabs.currentChanged.connect(self._on_editor_tab_changed)

        editor_container = QWidget()
        editor_container.setObjectName("recipeEditorContainer")
        editor_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        editor_container_layout = QVBoxLayout(editor_container)
        editor_container_layout.setContentsMargins(0, 4, 0, 0)
        editor_container_layout.setSpacing(4)
        editor_container_layout.addWidget(recipe_top_row)
        editor_container_layout.addWidget(self.editor_tabs, 1)
        right_layout.addWidget(editor_container, 1)
        self._on_editor_tab_changed(self.editor_tabs.currentIndex())

        self.issues_label = None

    def _add_recipe_image(self) -> None:
        if not hasattr(self, "images_list"):
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar imagen de elaboración",
            "",
            "Imágenes (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if not file_path:
            return
        if QPixmap(file_path).isNull():
            QMessageBox.warning(self, "Imágenes", "No se pudo cargar la imagen seleccionada.")
            return
        try:
            stored_path = store_recipe_image(Path(file_path))
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Imágenes", str(exc))
            return
        self._add_recipe_image_item(stored_path)
        self._schedule_autosave()

    def _remove_recipe_images(self) -> None:
        if not hasattr(self, "images_list"):
            return
        selected_rows = sorted({idx.row() for idx in self.images_list.selectedIndexes()}, reverse=True)
        if not selected_rows:
            return
        for row in selected_rows:
            self.images_list.takeItem(row)
        self._schedule_autosave()

    def _mark_main_recipe_image(self) -> None:
        if not hasattr(self, "images_list"):
            return
        row = self.images_list.currentRow()
        if row < 0:
            return
        for i in range(self.images_list.count()):
            item = self.images_list.item(i)
            item.setData(Qt.ItemDataRole.UserRole + 1, False)
            item.setBackground(QBrush())
        current = self.images_list.item(row)
        current.setData(Qt.ItemDataRole.UserRole + 1, True)
        current.setBackground(QBrush(QColor("#D6F5DD")))
        self._schedule_autosave()

    def _add_recipe_image_item(self, file_path: str) -> None:
        path = str(file_path or "").strip()
        if not path:
            return
        resolved_path = resolve_recipe_image_path(path)
        pix = QPixmap(str(resolved_path))
        if pix.isNull():
            QMessageBox.warning(self, "Imágenes", "No se pudo cargar la imagen seleccionada.")
            return
        thumb = pix.scaled(132, 98, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        item = QListWidgetItem()
        item.setIcon(QIcon(thumb))
        item.setText(Path(path).name)
        item.setToolTip(str(resolved_path))
        item.setData(Qt.ItemDataRole.UserRole, path)
        item.setData(Qt.ItemDataRole.UserRole + 1, False)
        self.images_list.addItem(item)

    def _preview_recipe_image(self, item: QListWidgetItem) -> None:
        path = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
        if not path:
            return
        pix = QPixmap(str(resolve_recipe_image_path(path)))
        if pix.isNull():
            QMessageBox.warning(self, "Imágenes", "No se pudo abrir la imagen.")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(Path(path).name)
        dialog.resize(960, 680)
        root = QVBoxLayout(dialog)
        lbl = QLabel()
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scaled = pix.scaled(920, 620, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        lbl.setPixmap(scaled)
        root.addWidget(lbl, 1)
        dialog.exec()

    def _show_images_context_menu(self, pos) -> None:
        if not hasattr(self, "images_list"):
            return
        item = self.images_list.itemAt(pos)
        if item is None:
            return
        selected = self.images_list.selectedItems()
        if item not in selected:
            self.images_list.setCurrentItem(item)
            item.setSelected(True)

        menu = QMenu(self)
        open_action = menu.addAction("Abrir")
        replace_action = menu.addAction("Reemplazar")
        delete_action = menu.addAction("Eliminar")
        chosen = menu.exec(self.images_list.mapToGlobal(pos))
        if chosen is open_action:
            self._preview_recipe_image(item)
            return
        if chosen is replace_action:
            self._replace_recipe_image(item)
            return
        if chosen is delete_action:
            self._remove_recipe_images()

    def _replace_recipe_image(self, item: QListWidgetItem) -> None:
        old_path = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Reemplazar imagen",
            str(resolve_recipe_image_path(old_path).parent) if old_path else "",
            "Imágenes (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if not file_path:
            return
        source_pix = QPixmap(file_path)
        if source_pix.isNull():
            QMessageBox.warning(self, "Imágenes", "No se pudo cargar la imagen seleccionada.")
            return
        try:
            stored_path = store_recipe_image(Path(file_path))
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Imágenes", str(exc))
            return
        resolved_path = resolve_recipe_image_path(stored_path)
        thumb = source_pix.scaled(132, 98, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        was_main = bool(item.data(Qt.ItemDataRole.UserRole + 1))
        item.setIcon(QIcon(thumb))
        item.setText(Path(stored_path).name)
        item.setToolTip(str(resolved_path))
        item.setData(Qt.ItemDataRole.UserRole, stored_path)
        item.setData(Qt.ItemDataRole.UserRole + 1, was_main)
        if was_main:
            item.setBackground(QBrush(QColor("#D6F5DD")))
        else:
            item.setBackground(QBrush())
        self._schedule_autosave()

    def _collect_images_gallery(self) -> list[dict[str, object]]:
        if not hasattr(self, "images_list"):
            return []
        payload: list[tuple[str, bool]] = []
        for idx in range(self.images_list.count()):
            item = self.images_list.item(idx)
            path = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
            if not path:
                continue
            payload.append((path, bool(item.data(Qt.ItemDataRole.UserRole + 1))))
        return _collect_recipe_image_gallery(payload)

    def _load_images_gallery(self, payload: dict[str, str]) -> bool:
        if not hasattr(self, "images_list"):
            return False
        self.images_list.clear()
        migrated = False
        rows = _recipe_image_gallery_from_payload(payload)
        for row in rows:
            path = str(row.get("path") or "").strip()
            if Path(path).is_absolute():
                try:
                    managed_path = store_recipe_image(Path(path))
                except (OSError, ValueError):
                    managed_path = path
                migrated = migrated or managed_path != path
                path = managed_path
            self._add_recipe_image_item(path)
            if self.images_list.count() > 0:
                item = self.images_list.item(self.images_list.count() - 1)
                is_main = bool(row.get("is_main", False))
                item.setData(Qt.ItemDataRole.UserRole + 1, is_main)
                if is_main:
                    item.setBackground(QBrush(QColor("#D6F5DD")))
        return migrated

    def _open_process_editor_dialog(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Editar proceso")
        dialog.setModal(True)
        dialog.resize(920, 640)

        layout = QVBoxLayout(dialog)
        editor = RichProcessTextEdit(dialog)
        if self._proceso_rich_html.strip():
            editor.setHtml(self._proceso_rich_html)
        else:
            editor.setPlainText(self.proceso_input.toPlainText())
        editor.setPlaceholderText("Proceso...")
        editor.setStyleSheet(self.proceso_input.styleSheet())
        editor.setAcceptRichText(True)
        layout.addWidget(editor, 1)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(8)
        generate_btn = QPushButton("Generar con ChatGPT")
        generate_btn.clicked.connect(lambda: self._generate_process_with_chatgpt(editor))
        action_row.addWidget(generate_btn)
        action_row.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, parent=dialog)
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if save_button:
            save_button.setText("Guardar")
        if cancel_button:
            cancel_button.setText("Cancelar")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        action_row.addWidget(buttons)
        layout.addLayout(action_row)

        dialog.setStyleSheet(
            "QPushButton {"
            "border: none;"
            "border-radius: 8px;"
            "padding: 7px 12px;"
            "font-weight: 600;"
            "}"
            "QPushButton:hover {"
            "opacity: 0.95;"
            "}"
        )
        if save_button:
            save_button.setStyleSheet("QPushButton { background-color: #1C8D4A; color: white; }")
        if cancel_button:
            cancel_button.setStyleSheet("QPushButton { background-color: #6B7280; color: white; }")
        generate_btn.setStyleSheet("QPushButton { background-color: #0E6FD1; color: white; }")

        save_shortcut = QShortcut(QKeySequence("Ctrl+Return"), dialog)
        save_shortcut.activated.connect(dialog.accept)
        save_shortcut2 = QShortcut(QKeySequence("Ctrl+Enter"), dialog)
        save_shortcut2.activated.connect(dialog.accept)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self._proceso_rich_html = editor.toHtml().strip()
        self.proceso_input.blockSignals(True)
        self.proceso_input.setPlainText(editor.toPlainText())
        self.proceso_input.blockSignals(False)
        self._schedule_autosave()

    def _build_chatgpt_process_prompt(self) -> str:
        def widget_text(attr_name: str) -> str:
            widget = getattr(self, attr_name, None)
            if widget is None:
                return ""
            if hasattr(widget, "text"):
                try:
                    return str(widget.text() or "").strip()
                except Exception:
                    return ""
            return ""

        def data_val(key: str) -> str:
            process = self._current_active_process() if hasattr(self, "_current_active_process") else "Masa final"
            process_key = f"proceso::{process}::{key}"
            if hasattr(self, "recipe_elaboracion_data"):
                value = str(getattr(self, "recipe_elaboracion_data", {}).get(process_key, "") or "").strip()
                if value:
                    return value
                value = str(getattr(self, "recipe_elaboracion_data", {}).get(key, "") or "").strip()
                if value:
                    return value
            if hasattr(self, "recipe_escandallo_data"):
                value = str(getattr(self, "recipe_escandallo_data", {}).get(process_key, "") or "").strip()
                if value:
                    return value
                value = str(getattr(self, "recipe_escandallo_data", {}).get(key, "") or "").strip()
                if value:
                    return value
            return ""

        def pick(attr_name: str, key: str, default: str = "") -> str:
            return widget_text(attr_name) or data_val(key) or default

        receta_nombre = str(self.nombre_input.text() if hasattr(self, "nombre_input") else "").strip() or "Receta sin nombre"
        process_name = self._current_active_process() if hasattr(self, "_current_active_process") else "Masa final"
        masa_total = ""
        if hasattr(self, "masa_spin"):
            try:
                masa_total = self._fmt_number(float(self.masa_spin.value() or 0.0), 2)
            except Exception:
                masa_total = ""
        peso_pieza = ""
        if hasattr(self, "peso_spin"):
            try:
                peso_pieza = self._fmt_number(float(self.peso_spin.value() or 0.0), 2)
            except Exception:
                peso_pieza = ""
        total_piezas = ""
        if hasattr(self, "piezas_spin"):
            try:
                total_piezas = str(int(self.piezas_spin.value() or 0))
            except Exception:
                total_piezas = ""
        return (
            "Tu única función es generar el PROCESO DE ELABORACIÓN del producto a partir de los datos que te proporcione.\n\n"
            "Debes responder SIEMPRE únicamente con el proceso, sin análisis, sin explicaciones y sin teoría.\n\n"
            "Estructura obligatoria de la respuesta:\n\n"
            "PROCESO DE ELABORACIÓN\n\n"
            "Amasado\n"
            "Tipo de amasado (corto, intensivo, etc.)\n"
            "Tiempo aproximado\n"
            "Objetivo del amasado\n"
            "Temperatura de masa\n"
            "Temperatura final objetivo\n"
            "Reposo / Fermentación en bloque\n"
            "Tiempo\n"
            "Condiciones (temperatura si aplica)\n"
            "División y formado\n"
            "Peso de piezas\n"
            "Tipo de formado\n"
            "Fermentación final\n"
            "Tiempo\n"
            "Condiciones\n"
            "Horneado\n"
            "Temperatura\n"
            "Vapor (sí/no y cantidad orientativa)\n"
            "Tiempo de cocción\n\n"
            "Normas obligatorias:\n\n"
            "Sé directo y práctico (formato obrador)\n"
            "No añadas explicaciones\n"
            "No justifiques nada\n"
            "No des alternativas salvo que se pidan\n"
            "Si faltan datos, asume valores estándar profesionales\n\n"
            "Datos de la app:\n"
            f"Receta: {receta_nombre}\n"
            f"Proceso activo: {process_name}\n\n"
            "Parametros:\n"
            f"- Total masa: {pick('el_total_masa', 'masa_total', masa_total)} g\n"
            f"- Peso por pieza: {pick('el_peso_pieza', 'peso_pieza', peso_pieza)} g\n"
            f"- Total piezas: {pick('el_rendimiento', 'rendimiento', total_piezas)} uds\n"
            f"- 1º amasado (lenta): {pick('am1_lenta', 'am1_lenta')} min\n"
            f"- 1º amasado (rapida): {pick('am1_rapida', 'am1_rapida')} min\n"
            f"- Temp. masa: {pick('am1_temp', 'am1_temp')} C\n"
            f"- Reposo en bloque: {pick('rep_bloque_1', 'rep_bloque_1')} min\n"
            f"- Reposo en pieza: {pick('rep_bloque_2', 'rep_bloque_2')} min\n"
            f"- Fermentacion temperatura: {pick('fermentacion_temp', 'fermentacion_temp')} C\n"
            f"- Fermentacion tiempo: {pick('rep_fermentacion', 'rep_fermentacion')} min\n"
            f"- Fermentacion humedad: {pick('fermentacion_humedad', 'fermentacion_humedad')} %\n"
            f"- Precoccion temp. inicial: {pick('precalentamiento_pre', 'precalentamiento_pre')} C\n"
            f"- Precoccion temp. coccion: {pick('temp_coccion_pre', 'temp_coccion_pre')} C\n"
            f"- Precoccion tiempo coccion: {pick('tiempo_coccion_pre', 'tiempo_coccion_pre')} min\n"
            f"- Precoccion vapor: {pick('vapor_pre', 'vapor_pre')}\n"
            f"- Coccion temp. inicial: {pick('precalentamiento_coc', 'precalentamiento_coc')} C\n"
            f"- Coccion temp. coccion: {pick('temp_coccion_coc', 'temp_coccion_coc')} C\n"
            f"- Coccion tiempo coccion: {pick('tiempo_coccion_coc', 'tiempo_coccion_coc')} min\n"
            f"- Coccion vapor: {pick('vapor_coc', 'vapor_coc')}\n"
        )

    def _generate_process_with_chatgpt(self, editor: QTextEdit) -> None:
        prompt = self._build_chatgpt_process_prompt().strip()
        if not prompt:
            QMessageBox.warning(self, "Proceso", "No hay datos para generar el proceso.")
            return
        self.setCursor(Qt.CursorShape.WaitCursor)
        try:
            result = OpenAIProcessService().generate_process(prompt)
        finally:
            self.unsetCursor()
        if not result.ok:
            QMessageBox.warning(self, "Proceso", result.message or "No se pudo generar el proceso.")
            return
        editor.setPlainText(result.text.strip())

    def _on_proceso_plain_text_changed(self) -> None:
        if self._is_loading_recipe:
            return
        # If user edits outside rich editor, keep data coherent with plain text state.
        self._proceso_rich_html = ""
        self._schedule_autosave()

    def _create_recipe_table(self) -> QTableWidget:
        table = QTableWidget(0, 2)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setStyleSheet("QTableWidget::item:focus { border: none; outline: 0; }")
        table.setHorizontalHeaderLabels(["Nº", "Nombre receta"])
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.setColumnWidth(0, 52)
        table.setSortingEnabled(True)
        table.cellClicked.connect(self._on_recipe_selected)
        return table

    def _double_spin(self, min_value: float, max_value: float, decimals: int) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(min_value, max_value)
        spin.setDecimals(decimals)
        return spin

    def eventFilter(self, watched, event) -> bool:  # type: ignore[override]
        customer_filter_input = getattr(self, "customer_filter_input", None)
        header_row = getattr(self, "header_row", None)
        if watched is customer_filter_input and event.type() == QEvent.Type.FocusIn:
            QTimer.singleShot(0, customer_filter_input.selectAll)
        if watched is header_row and event.type() == QEvent.Type.Resize:
            self._layout_header_boxes_abs()
            self._layout_header_fields_abs()
        return super().eventFilter(watched, event)

    def _load_customers(self) -> None:
        customers = self.recipe_service.list_customers()
        self.cliente_combo.clear()
        for customer in customers:
            self.cliente_combo.addItem(_customer_display_name(customer), str(customer.cliente_id))
        self.cliente_combo.setCurrentIndex(-1)
        self._update_inline_customer_name()
        self._reload_customer_filter(customers)

    def _reload_customer_filter(self, customers: list[Any] | None = None) -> None:
        if not hasattr(self, "customer_filter_input"):
            return
        if customers is None:
            customers = self.recipe_service.list_customers()
        self._customer_filter_items: list[tuple[str, str]] = [("", "Todos los clientes")]
        for customer in customers:
            self._customer_filter_items.append((str(customer.cliente_id), _customer_display_name(customer)))
        valid_ids = {item[0] for item in self._customer_filter_items}
        if self.customer_filter_selected_id not in valid_ids:
            self.customer_filter_selected_id = ""
        self._refresh_customer_filter_input()
        self._reload_recipe_list()

    @staticmethod
    def _customer_filter_label(customer: Any) -> str:
        return _customer_display_name(customer)

    def _on_customer_filter_text_changed(self, text: str) -> None:
        if self._is_loading_recipe:
            return
        term = str(text or "").strip()
        self.customer_filter_clear_btn.setEnabled(bool(term))
        if not term:
            if self.customer_filter_selected_id:
                self.customer_filter_selected_id = ""
                self._reload_recipe_list()
            self.customer_filter_results.setRowCount(0)
            self.customer_filter_results.setVisible(False)
            return

        customers = self.recipe_service.search_customers(term)
        self.customer_filter_results.setRowCount(len(customers))
        for row, customer in enumerate(customers):
            customer_id = str(getattr(customer, "cliente_id", "") or "").strip()
            code = str(getattr(customer, "cliente_codigo", "") or "")
            code_item = QTableWidgetItem(code)
            code_item.setData(Qt.ItemDataRole.UserRole, customer_id)
            self.customer_filter_results.setItem(row, 0, code_item)
            self.customer_filter_results.setItem(row, 1, QTableWidgetItem(self._customer_filter_label(customer)))
        self.customer_filter_results.setVisible(bool(customers))

    def _clear_customer_filter(self) -> None:
        self.customer_filter_input.clear()

    def _select_first_customer_filter_result(self) -> None:
        if self.customer_filter_results.rowCount() > 0:
            self._select_customer_filter_result(0, 0)

    def _select_customer_filter_result(self, row: int, _column: int) -> None:
        code_item = self.customer_filter_results.item(row, 0)
        label_item = self.customer_filter_results.item(row, 1)
        if code_item is None or label_item is None:
            return
        customer_id = str(code_item.data(Qt.ItemDataRole.UserRole) or "").strip()
        if not customer_id:
            return
        self.customer_filter_selected_id = customer_id
        self._refresh_customer_filter_input(label_item.text())
        self.customer_filter_results.setVisible(False)
        self._reload_recipe_list()

    def _reload_recipe_list(self) -> None:
        if not hasattr(self, "recipe_tabs"):
            return
        active_table = self._active_recipe_table()
        is_ireks_tab = self.recipe_tabs.currentIndex() == 0
        term = self.ireks_recipe_search.text().strip() if is_ireks_tab else ""
        cliente_id = None if is_ireks_tab else (self.customer_filter_selected_id or None)
        recipes = self.recipe_service.list_recipes(term=term, cliente_id=cliente_id, es_base=is_ireks_tab)
        active_table.setSortingEnabled(False)
        active_table.setRowCount(len(recipes))
        for row, recipe in enumerate(recipes):
            values = [str(recipe.id or ""), recipe.nombre]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if col == 0:
                    recipe_id = int(recipe.id or 0)
                    cell.setData(Qt.ItemDataRole.DisplayRole, recipe_id)
                    cell.setData(Qt.ItemDataRole.UserRole, recipe_id)
                active_table.setItem(row, col, cell)
        active_table.setSortingEnabled(True)

    def _select_recipe_in_active_table(self, recipe_id: int | None) -> None:
        if not recipe_id:
            return
        table = self._active_recipe_table()
        for row in range(table.rowCount()):
            item = table.item(row, 0)
            if item and int(item.data(Qt.ItemDataRole.UserRole) or 0) == recipe_id:
                table.selectRow(row)
                return

    def _active_recipe_table(self) -> QTableWidget:
        if self.recipe_tabs.currentIndex() == 0:
            return self.ireks_recipe_table
        return self.customer_recipe_table

    def _on_recipe_tab_changed(self) -> None:
        if not hasattr(self, "nombre_input"):
            return
        if hasattr(self, "editor_tabs"):
            self._on_editor_tab_changed(self.editor_tabs.currentIndex())
        self._flush_autosave()
        self.current_recipe_is_ireks = self.recipe_tabs.currentIndex() == 0
        self._new_recipe()
        self._reload_recipe_list()
        self._update_inline_customer_name()

    def _on_editor_tab_changed(self, index: int) -> None:
        if not hasattr(self, "recipe_process_row"):
            return
        is_recipe_or_escandallo = index in (0, 1)
        process_enabled = index in (0, 1, 2)
        exports_enabled = index in (0, 1, 4)
        customer_tab_active = hasattr(self, "recipe_tabs") and self.recipe_tabs.currentIndex() == 1

        self.recipe_process_row.setEnabled(process_enabled)
        self.scale_btn.setEnabled(is_recipe_or_escandallo)
        self.recipe_pdf_btn.setEnabled(exports_enabled)
        self.recipe_excel_btn.setEnabled(exports_enabled)
        self.load_base_btn.setVisible(customer_tab_active)
        self.load_base_btn.setEnabled(customer_tab_active and is_recipe_or_escandallo)

    def _available_process_names(self) -> list[str]:
        return _unique_process_names(self.recipe_process_names)

    def _current_active_process(self) -> str:
        return _normalize_process_name(self.active_process_combo.currentText() if hasattr(self, "active_process_combo") else "")

    def _current_escandallo_process(self) -> str:
        if hasattr(self, "escandallo_process_combo"):
            return _normalize_process_name(self.escandallo_process_combo.currentText())
        return self._current_active_process()

    def _refresh_process_controls(self, process_names: list[str] | None = None, preserve_active: bool = True) -> None:
        if process_names is None:
            process_names = self.recipe_process_names
        cleaned = _unique_process_names(process_names)
        self.recipe_process_names = cleaned
        if not hasattr(self, "active_process_combo"):
            return
        current = self._current_active_process() if preserve_active else "Masa final"
        self.active_process_combo.blockSignals(True)
        self.active_process_combo.clear()
        self.active_process_combo.addItems(self.recipe_process_names)
        idx = self.active_process_combo.findText(current)
        self.active_process_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.active_process_combo.blockSignals(False)
        if hasattr(self, "escandallo_process_combo"):
            escandallo_current = self._current_escandallo_process() if preserve_active else "Masa final"
            self.escandallo_process_combo.blockSignals(True)
            self.escandallo_process_combo.clear()
            self.escandallo_process_combo.addItems(self.recipe_process_names)
            escandallo_idx = self.escandallo_process_combo.findText(escandallo_current)
            self.escandallo_process_combo.setCurrentIndex(escandallo_idx if escandallo_idx >= 0 else 0)
            self.escandallo_process_combo.blockSignals(False)
        self._apply_process_filter()

    def _on_active_process_changed(self) -> None:
        self._apply_process_filter()

    def _on_escandallo_process_changed(self) -> None:
        self._refresh_escandallo_table()

    def _apply_process_filter(self) -> None:
        if not hasattr(self, "lines_table"):
            return
        active = self._current_active_process()
        for row in range(self.lines_table.rowCount()):
            line = self._line_from_row(row)
            has_content = bool(line.nombre_mostrado or line.notas or line.cantidad_base_g)
            if not has_content:
                self.lines_table.setRowHidden(row, False)
                continue
            proc = _normalize_process_name(getattr(line, "proceso_nombre", ""))
            self.lines_table.setRowHidden(row, proc != active)
        self._refresh_recipe_lines_totals()

    def _add_process(self) -> None:
        raw, ok = QInputDialog.getText(self, "Nuevo proceso", "Nombre del proceso")
        if not ok:
            return
        name = _normalize_process_name(raw)
        if name in self.recipe_process_names:
            self.active_process_combo.setCurrentText(name)
            return
        self.recipe_process_names.append(name)
        self._refresh_process_controls(self.recipe_process_names)
        self.active_process_combo.setCurrentText(name)
        self._schedule_autosave()

    def _rename_process(self) -> None:
        old = self._current_active_process()
        name, accepted = QInputDialog.getText(self, "Renombrar proceso", "Nombre", text=old)
        name = name.strip()
        if not accepted or not name or name == old:
            return
        if name.casefold() in {value.casefold() for value in self.recipe_process_names}:
            QMessageBox.warning(self, "Procesos", "Ya existe un proceso con ese nombre.")
            return
        lines = self._build_lines()
        if old == self.recipe_elaboracion_data.get("recipe_primary_process", "Masa final"):
            self.recipe_elaboracion_data["recipe_primary_process"] = name
        for line in lines:
            if line.proceso_nombre == old:
                line.proceso_nombre = name
            if line.proceso_origen_nombre == old:
                line.proceso_origen_nombre = name
                line.nombre_mostrado = f"Proceso: {name}"
                line.codigo_ingrediente = f"PROC:{name}"
        for data in (self.recipe_escandallo_data, self.recipe_elaboracion_data):
            for key in list(data):
                if key.startswith(f"proceso::{old}::"):
                    data[f"proceso::{name}::" + key[len(f"proceso::{old}::"):]] = data.pop(key)
        self.recipe_process_names = [name if value == old else value for value in self.recipe_process_names]
        self._replace_process_lines(lines, name)

    def _reorder_process(self, offset: int) -> None:
        active = self._current_active_process()
        index = self.recipe_process_names.index(active)
        target = index + offset
        if 0 <= target < len(self.recipe_process_names):
            names = list(self.recipe_process_names)
            names[index], names[target] = names[target], names[index]
            self._refresh_process_controls(names)
            self._schedule_autosave()

    def _replace_process_lines(self, lines: list[RecetaLinea], active: str) -> None:
        previous = self._is_loading_recipe
        self._is_loading_recipe = True
        self.lines_table.blockSignals(True)
        try:
            self._render_lines(lines)
            self.active_process_combo.setCurrentText(active)
        finally:
            self.lines_table.blockSignals(False)
            self._is_loading_recipe = previous
        self._on_lines_changed()

    def _move_ingredient_to_process(self, row: int, target: str) -> None:
        line = self._line_from_row(row)
        if line.tipo_linea == "proceso" or not line.nombre_mostrado:
            return
        line.proceso_nombre = target
        previous = self.lines_table.blockSignals(True)
        self._set_line_row(row, line)
        self.lines_table.blockSignals(previous)
        self._apply_process_filter()
        self._on_lines_changed()

    def _delete_process_with_ingredients(self) -> None:
        target = self._current_active_process()
        primary = self.recipe_elaboracion_data.get("recipe_primary_process", "Masa final")
        if target == primary or len(self.recipe_process_names) == 1:
            QMessageBox.information(self, "Recetas", "El proceso principal no se puede eliminar.")
            return
        if target not in self.recipe_process_names:
            return
        answer = QMessageBox.warning(
            self,
            "Eliminar proceso e ingredientes",
            f"¿Eliminar el proceso '{target}' y todos sus ingredientes de esta fórmula?\n\n"
            "También se eliminarán las líneas que hacen referencia a este proceso desde otros procesos.\n"
            "Los demás ingredientes se conservarán. Esta acción no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        lines = [
            line for line in self._build_lines()
            if _normalize_process_name(line.proceso_nombre) != target
            and not (line.tipo_linea == "proceso" and line.proceso_origen_nombre == target)
        ]
        self.recipe_process_names = [name for name in self.recipe_process_names if name != target]
        for data in (self.recipe_escandallo_data, self.recipe_elaboracion_data):
            for key in list(data):
                if key.startswith(f"proceso::{target}::"):
                    del data[key]
        active = primary if primary in self.recipe_process_names else self.recipe_process_names[0]
        self._replace_process_lines(lines, active)

    def _start_new_recipe(self) -> None:
        if self.recipe_tabs.currentIndex() == 0:
            self._new_recipe()
            return
        dialog = CustomerRecipeSelectionDialog(self.recipe_service, self)
        if not dialog.exec() or not dialog.selected_customer_id:
            return
        self._load_customers()
        self._new_recipe(cliente_id=dialog.selected_customer_id)

    def _open_document_recipe_search(self) -> None:
        if self.recipe_tabs.currentIndex() != 0:
            self.recipe_tabs.setCurrentIndex(0)
        service = RecipeDocumentImportService(
            ingredient_search=self.recipe_service.search_ingredients,
        )
        dialog = RecipeDocumentImportDialog(service, self)
        if not dialog.exec() or dialog.selected_draft is None:
            return
        self._load_document_recipe_draft(dialog.selected_draft)

    def _load_document_recipe_draft(self, draft: RecipeDocumentDraft) -> None:
        self._new_recipe()
        self._is_loading_recipe = True
        try:
            self.current_recipe_is_ireks = True
            self.nombre_input.setText(draft.recipe_name)
            self.codigo_input.clear()
            self.version_input.setText("1.0")
            self.estado_input.setText("borrador")
            self.piezas_spin.setValue(max(1, int(draft.number_of_pieces or 1)))
            self.proceso_input.setPlainText(draft.process_text)
            self.observaciones_input.setPlainText(
                "Importada desde documentación IREKS: "
                f"{draft.relative_path} (página {draft.page_number}).\n"
                "Revisar ingredientes, cantidades y procesos antes de guardar."
            )
            self.recipe_elaboracion_data = {
                "recipe_primary_process": draft.primary_process,
                "document_source_id": draft.document_id,
                "document_source_path": draft.relative_path,
                "document_source_page": str(draft.page_number),
            }
            lines: list[RecetaLinea] = []
            for index, source_line in enumerate(draft.lines, start=1):
                matched = source_line.matched_ingredient
                line = RecetaLinea(
                    receta_id=0,
                    orden=index,
                    tipo_origen=matched.tipo_origen if matched is not None else "std",
                    ingrediente_id=matched.ingrediente_id if matched is not None else None,
                    nombre_mostrado=matched.nombre if matched is not None else source_line.source_name,
                    codigo_ingrediente=matched.codigo if matched is not None else "",
                    familia=matched.familia if matched is not None else "",
                    subfamilia=matched.subfamilia if matched is not None else "",
                    es_harina=matched.es_harina if matched is not None else False,
                    es_liquido=matched.es_liquido if matched is not None else False,
                    cantidad_base_g=float(source_line.quantity_g or 0.0),
                    cantidad_calculada_g=float(source_line.quantity_g or 0.0),
                    precio_kg_snapshot=float(matched.precio_kg or 0.0) if matched is not None else 0.0,
                    proceso_nombre=_normalize_process_name(source_line.process_name),
                    notas=source_line.notes,
                )
                if source_line.source_process:
                    line.tipo_linea = "proceso"
                    line.tipo_origen = "process"
                    line.proceso_origen_nombre = source_line.source_process
                    line.cantidad_origen_g = line.cantidad_base_g
                    line.nombre_mostrado = f"Proceso: {source_line.source_process}"
                    line.codigo_ingrediente = f"PROC:{source_line.source_process}"
                    line.familia = "Proceso"
                lines.append(line)
            self._refresh_process_controls(
                [line.proceso_nombre for line in lines] or ["Masa final"],
                preserve_active=False,
            )
            self._render_lines(lines)
            calculated = self.recipe_service.calculate(
                self._build_recipe_model(),
                lines,
                sync_categories=True,
            )
            self._render_lines(calculated.lineas)
            self._update_summary(calculated.receta, calculated.lineas)
            self.current_issues = [f"[{issue.level.upper()}] {issue.message}" for issue in calculated.issues]
            self._set_issues_text("\n".join(self.current_issues))
        finally:
            self._is_loading_recipe = False
        self._document_import_pending = True
        QMessageBox.information(
            self,
            "Fórmula cargada",
            "La fórmula se ha cargado como borrador sin guardar. "
            "Revisa las líneas marcadas y pulsa «Guardar» cuando esté correcta.",
        )

    def _new_recipe(self, cliente_id: str = "") -> None:
        self._autosave_timer.stop()
        self._document_import_pending = False
        self._is_loading_recipe = True
        try:
            self.current_recipe_id = None
            self.current_base_recipe_id = None
            self.current_recipe_is_ireks = self.recipe_tabs.currentIndex() == 0 if hasattr(self, "recipe_tabs") else False
            self._set_combo_by_data(self.cliente_combo, cliente_id)
            if not cliente_id:
                self.cliente_combo.setCurrentIndex(-1)
            self.nombre_input.clear()
            self.codigo_input.clear()
            self.version_input.setText("1.0")
            self.estado_input.setText("borrador")
            self.masa_spin.setValue(0)
            self.peso_spin.setValue(0)
            self.piezas_spin.setValue(1)
            self.merma_spin.setValue(0)
            self.observaciones_input.clear()
            self.proceso_input.clear()
            self.recipe_escandallo_data = {}
            self.recipe_elaboracion_data = {}
            if hasattr(self, "images_list"):
                self.images_list.clear()
            self._proceso_rich_html = ""
            self._refresh_process_controls(["Masa final"], preserve_active=False)
            self._render_lines([])
            self._update_summary(Receta(cliente_id=self._selected_cliente_id(), nombre="", codigo_receta=""))
            self._set_issues_text("")
            self._update_inline_customer_name()
        finally:
            self._is_loading_recipe = False

    def _selected_cliente_id(self) -> str:
        value = self.cliente_combo.currentData()
        return str(value).strip() if value is not None else ""

    def _on_recipe_selected(self, row: int, _col: int) -> None:
        table = self.sender() if isinstance(self.sender(), QTableWidget) else self._active_recipe_table()
        if not isinstance(table, QTableWidget):
            return
        item = table.item(row, 0)
        if not item:
            return
        recipe_id = int(item.data(Qt.ItemDataRole.UserRole) or 0)
        if not recipe_id:
            return
        self._flush_autosave()
        self._select_recipe_in_active_table(recipe_id)
        self._load_recipe(recipe_id)

    def _load_recipe(self, recipe_id: int) -> None:
        aggregate = self.recipe_service.get_recipe(recipe_id, sync_categories=True)
        if not aggregate:
            return
        self._is_loading_recipe = True
        self._document_import_pending = False
        images_migrated = False
        try:
            receta = aggregate.receta
            self.current_recipe_id = receta.id
            self.current_base_recipe_id = receta.receta_base_id
            self.current_recipe_is_ireks = receta.es_base
            self._set_combo_by_data(self.cliente_combo, receta.cliente_id)
            self.nombre_input.setText(receta.nombre)
            self.codigo_input.setText(receta.codigo_receta)
            self.version_input.setText(receta.version)
            self.estado_input.setText(receta.estado)
            self.masa_spin.setValue(receta.masa_final_deseada_g)
            self.piezas_spin.setValue(receta.numero_piezas)
            self.merma_spin.setValue(receta.merma_pct)
            self.observaciones_input.setPlainText(receta.observaciones)
            self.proceso_input.setPlainText(receta.proceso)
            self.recipe_escandallo_data = _json_to_string_dict(receta.escandallo_detalle_json)
            self.recipe_elaboracion_data = _json_to_string_dict(receta.parametros_elaboracion_json)
            images_migrated = self._load_images_gallery(self.recipe_elaboracion_data)
            self._proceso_rich_html = str(self.recipe_elaboracion_data.get(self.PROCESO_RICH_HTML_KEY, "") or "").strip()
            line_processes = [_normalize_process_name(getattr(line, "proceso_nombre", "") or "Masa final") for line in aggregate.lineas]
            try:
                saved_processes = json.loads(self.recipe_elaboracion_data.get("recipe_process_order", "[]"))
            except (ValueError, TypeError):
                saved_processes = []
            if not isinstance(saved_processes, list):
                saved_processes = []
            self._refresh_process_controls([name for name in saved_processes if isinstance(name, str)] + line_processes,
                                           preserve_active=False)
            self.peso_spin.setValue(self._technical_peso_pieza(float(receta.peso_pieza_g or 0.0)))
            self._render_lines(aggregate.lineas)
            self._update_summary(receta, aggregate.lineas)
            self._set_issues_text("")
            self._update_inline_customer_name()
        finally:
            self._is_loading_recipe = False
        if images_migrated:
            self._schedule_autosave()

    def _set_combo_by_data(self, combo: QComboBox, value: str) -> bool:
        idx = combo.findData(str(value or ""))
        combo.setCurrentIndex(idx)
        self._update_inline_customer_name()
        return idx >= 0

    def _update_inline_customer_name(self) -> None:
        if not hasattr(self, "customer_header_box") or not hasattr(self, "recipe_tabs"):
            return
        is_customer_tab = self.recipe_tabs.currentIndex() == 1
        self.customer_header_box.setVisible(is_customer_tab)
        self.change_customer_btn.setEnabled(is_customer_tab and bool(self.current_recipe_id) and not self.current_recipe_is_ireks)
        if hasattr(self, "promotions_btn"):
            self.promotions_btn.setEnabled(is_customer_tab and bool(self._selected_cliente_id()))
        if not is_customer_tab:
            self.customer_name_value.clear()
            return
        customer_name = (self.cliente_combo.currentText() or "").strip()
        self.customer_name_value.setText(customer_name)

    def _open_customer_promotions(self) -> None:
        customer_id = self._selected_cliente_id()
        if not customer_id:
            QMessageBox.information(self, "Promociones", "Selecciona primero una receta de cliente.")
            return
        dialog = CustomerPromotionsDialog(self.recipe_service, customer_id, self.cliente_combo.currentText(), self)
        dialog.exec()
        self._recalculate()
        self._refresh_escandallo_table()
        if self.current_recipe_id:
            self._perform_autosave()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._layout_header_boxes_abs()
        self._layout_header_fields_abs()

    def _layout_header_boxes_abs(self) -> None:
        if not hasattr(self, "header_row") or not hasattr(self, "recipe_header_box") or not hasattr(self, "customer_header_box"):
            return
        self.recipe_header_box.setGeometry(0, 4, 460, 58)
        customer_width = max(500, self.header_row.width() - 468)
        self.customer_header_box.setGeometry(468, 4, customer_width, 58)
        self.header_separator.setGeometry(464, 8, 1, 48)

    def _layout_header_fields_abs(self) -> None:
        if not hasattr(self, "recipe_header_box") or not hasattr(self, "customer_header_box"):
            return
        self.nombre_input.setGeometry(10, 21, 440, 24)
        customer_field_width = max(0, self.customer_header_box.width() - 60)
        self.customer_name_value.setGeometry(10, 21, customer_field_width, 34)
        self.change_customer_btn.setGeometry(16 + customer_field_width, 21, 34, 34)

    def _change_recipe_customer(self) -> None:
        if self.recipe_tabs.currentIndex() != 1 or not self.current_recipe_id or self.current_recipe_is_ireks:
            return
        dialog = CustomerRecipeSelectionDialog(self.recipe_service, self)
        if not dialog.exec() or not dialog.selected_customer_id:
            return
        if dialog.selected_customer_id == self._selected_cliente_id():
            return
        answer = QMessageBox.question(
            self,
            "Cambiar cliente",
            f"¿Asignar esta receta a '{dialog.selected_customer_label}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._autosave_timer.stop()
        try:
            updated = self.recipe_service.update_recipe_customer(self.current_recipe_id, dialog.selected_customer_id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Recetas", f"No se pudo cambiar el cliente.\n{exc}")
            return
        if not updated:
            QMessageBox.warning(self, "Recetas", "No se encontró la receta para cambiar el cliente.")
            return
        self._set_combo_by_data(self.cliente_combo, dialog.selected_customer_id)
        self.customer_filter_selected_id = dialog.selected_customer_id
        self._refresh_customer_filter_input(dialog.selected_customer_label)
        self._reload_recipe_list()
        self._select_recipe_in_active_table(self.current_recipe_id)
        self._load_recipe(self.current_recipe_id)
        QMessageBox.information(self, "Recetas", "Cliente de la receta actualizado.")

    def _add_ingredient(self) -> None:
        target_process = self._current_active_process()
        source_processes = [name for name in self._available_process_names() if name != target_process]
        dialog = IngredientSearchDialog(self.recipe_service, source_processes=source_processes, parent=self)
        if not dialog.exec():
            return
        if dialog.selected_process_name and dialog.selected_process_qty > 0:
            self._insert_process_line(dialog.selected_process_name, dialog.selected_process_qty)
            return
        if not dialog.selected:
            return
        row = self._first_empty_line_row()
        self._set_ingredient_row(row, dialog.selected)
        self._apply_process_filter()

    def _insert_process_line(self, source_name: str, qty_g: float, row: int | None = None) -> None:
        target_process = self._current_active_process()
        if row is None:
            row = self._first_empty_line_row()
        linea = self._line_from_row(row)
        linea.tipo_linea = "proceso"
        linea.tipo_origen = "process"
        linea.ingrediente_id = None
        linea.nombre_mostrado = f"Proceso: {source_name}"
        linea.codigo_ingrediente = f"PROC:{source_name}"
        linea.familia = "Proceso"
        linea.subfamilia = ""
        linea.es_harina = False
        linea.es_liquido = False
        linea.precio_kg_snapshot = 0.0
        linea.proceso_nombre = target_process
        linea.proceso_origen_nombre = str(source_name or "").strip()
        linea.cantidad_origen_g = float(qty_g or 0.0)
        linea.cantidad_base_g = float(qty_g or 0.0)
        linea.notas = (linea.notas or "").strip() or "Usado desde proceso"
        self._set_line_row(row, linea)
        self._ensure_trailing_empty_line()
        self._on_lines_changed()
        self._apply_process_filter()

    def _remove_line(self) -> None:
        selected = self.lines_table.selectionModel().selectedRows()
        if not selected:
            return
        self.lines_table.removeRow(selected[0].row())
        self._ensure_min_line_rows()
        self._on_lines_changed()

    def _show_lines_context_menu(self, position) -> None:
        index = self.lines_table.indexAt(position)
        if index.isValid():
            self.lines_table.selectRow(index.row())

        menu = QMenu(self.lines_table)
        add_action = menu.addAction("Añadir fila")
        remove_action = menu.addAction("Eliminar fila")
        remove_action.setEnabled(index.isValid())
        move_actions = {}
        if index.isValid():
            line = self._line_from_row(index.row())
            if line.tipo_linea != "proceso" and line.nombre_mostrado:
                submenu = menu.addMenu("Traspasar ingrediente a proceso")
                for name in self._available_process_names():
                    if name != line.proceso_nombre:
                        move_actions[submenu.addAction(name)] = name
                submenu.setEnabled(bool(move_actions))
        action = menu.exec(self.lines_table.viewport().mapToGlobal(position))
        if action in move_actions:
            self._move_ingredient_to_process(index.row(), move_actions[action])
            return
        if action is add_action:
            self._add_ingredient()
        elif action is remove_action:
            self._remove_line()

    def _scale_recipe(self) -> None:
        lineas = self._build_lines()
        if not lineas:
            QMessageBox.warning(self, "Escalar receta", "No hay lineas para escalar.")
            return

        receta = self._build_recipe_model()
        lineas = self.recipe_service.sync_line_categories(lineas)

        current_flour_g = sum(float(linea.cantidad_base_g or 0.0) for linea in lineas if linea.es_harina)
        current_total_g = sum(float(linea.cantidad_base_g or 0.0) for linea in lineas)
        if receta.peso_pieza_g > 0 and current_total_g > 0:
            current_pieces = current_total_g / float(receta.peso_pieza_g)
        else:
            current_pieces = float(receta.numero_piezas or 0.0)

        dialog = RecipeScaleDialog(current_flour_g, current_total_g, current_pieces, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            scaled = self.recipe_service.scale_recipe(receta, lineas, cast(Any, dialog.mode()), dialog.target_value_g())
            result = self.recipe_service.calculate(scaled.receta, scaled.lineas)
        except ValueError as exc:
            QMessageBox.warning(self, "Escalar receta", str(exc))
            return
        except Exception as exc:
            QMessageBox.warning(self, "Escalar receta", f"No se pudo escalar la receta.\n{exc}")
            return

        self._is_loading_recipe = True
        try:
            self.masa_spin.setValue(result.receta.masa_final_deseada_g)
            self.piezas_spin.setValue(max(int(result.receta.numero_piezas or 1), 1))
            self._render_lines(result.lineas)
            self._update_summary(result.receta)
            self.current_issues = [f"[{i.level.upper()}] {i.message}" for i in result.issues]
            self._set_issues_text("\n".join(self.current_issues))
        finally:
            self._is_loading_recipe = False

        self._autosave_timer.stop()
        self._perform_autosave()

    def _on_line_double_click(self, item: QTableWidgetItem) -> None:
        if item.column() == self.COL_INGREDIENTE:
            self._pick_ingredient_for_selected()

    def _pick_ingredient_for_selected(self) -> None:
        selected = self.lines_table.selectionModel().selectedRows()
        if not selected:
            QMessageBox.warning(self, "Atencion", "Selecciona una linea.")
            return
        row = selected[0].row()
        target_process = self._current_active_process()
        source_processes = [name for name in self._available_process_names() if name != target_process]
        dialog = IngredientSearchDialog(self.recipe_service, source_processes=source_processes, parent=self)
        if not dialog.exec():
            return
        if dialog.selected_process_name and dialog.selected_process_qty > 0:
            self._insert_process_line(dialog.selected_process_name, dialog.selected_process_qty, row=row)
            return
        if not dialog.selected:
            return
        self._set_ingredient_row(row, dialog.selected)

    def _first_empty_line_row(self) -> int:
        for row in range(self.lines_table.rowCount()):
            line = self._line_from_row(row)
            if not line.nombre_mostrado and not line.notas and not line.cantidad_base_g:
                return row
        row = self.lines_table.rowCount()
        self.lines_table.insertRow(row)
        self._set_line_row(row, RecetaLinea(receta_id=0, orden=row + 1))
        return row

    def _set_ingredient_row(self, row: int, ingredient: IngredientChoice) -> None:
        linea = self._line_from_row(row)
        linea.tipo_linea = "ingrediente"
        linea.tipo_origen = ingredient.tipo_origen
        linea.ingrediente_id = ingredient.ingrediente_id
        linea.codigo_ingrediente = ingredient.codigo
        linea.nombre_mostrado = ingredient.nombre
        linea.familia = ingredient.familia
        linea.subfamilia = ingredient.subfamilia
        linea.es_harina = ingredient.es_harina
        linea.es_liquido = ingredient.es_liquido
        linea.precio_kg_snapshot = ingredient.precio_kg
        linea.proceso_nombre = self._current_active_process()
        linea.proceso_origen_nombre = ""
        linea.cantidad_origen_g = 0.0
        self._set_line_row(row, linea)
        self._ensure_trailing_empty_line()
        self._on_lines_changed()

    def _ensure_trailing_empty_line(self) -> None:
        """Mantiene una fila libre al final para que la tabla pueda crecer sin límite."""
        if self.lines_table.rowCount() <= 0:
            return
        last_row = self.lines_table.rowCount() - 1
        last_line = self._line_from_row(last_row)
        if not (last_line.nombre_mostrado or last_line.notas or last_line.cantidad_base_g):
            return
        row = self.lines_table.rowCount()
        self.lines_table.insertRow(row)
        self._set_line_row(row, RecetaLinea(receta_id=0, orden=row + 1))

    def _set_line_row(self, row: int, linea: RecetaLinea) -> None:
        has_ingredient = bool((linea.nombre_mostrado or "").strip())
        has_content = has_ingredient or bool((linea.notas or "").strip()) or float(linea.cantidad_base_g or 0.0) > 0
        process_text = _normalize_process_name(getattr(linea, "proceso_nombre", "") or self._current_active_process())
        values = [
            linea.nombre_mostrado or "",
            linea.notas or "",
            f"{self._format_number(linea.cantidad_base_g)} g" if has_content else "",
            f"{self._format_number(linea.porcentaje_panadero, 2)} %" if has_content else "",
            process_text if has_content else "",
        ]
        for col, value in enumerate(values):
            cell = QTableWidgetItem(value)
            if col == self.COL_INGREDIENTE:
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if col == self.COL_NOTA:
                cell.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            if col == self.COL_CANTIDAD:
                cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if col == self.COL_PCT:
                cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if col == self.COL_PROCESO and not has_content:
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.lines_table.setItem(row, col, cell)
        ingredient_cell = self.lines_table.item(row, self.COL_INGREDIENTE)
        if ingredient_cell is not None:
            ingredient_cell.setData(Qt.ItemDataRole.UserRole, linea.model_dump())

    def _line_from_row(self, row: int) -> RecetaLinea:
        item = self.lines_table.item(row, self.COL_INGREDIENTE)
        existing = item.data(Qt.ItemDataRole.UserRole) if item else None
        if isinstance(existing, dict):
            linea = RecetaLinea(**existing)
        elif isinstance(existing, RecetaLinea):
            linea = RecetaLinea(**existing.model_dump())
        else:
            linea = RecetaLinea(receta_id=0, orden=row + 1)
        linea.orden = row + 1
        tipo_linea = str(getattr(linea, "tipo_linea", "") or "").strip().lower()
        linea.tipo_linea = tipo_linea if tipo_linea in {"ingrediente", "proceso"} else "ingrediente"
        linea.nombre_mostrado = self._cell_text(row, self.COL_INGREDIENTE)
        linea.notas = self._cell_text(row, self.COL_NOTA)
        linea.cantidad_base_g = self._quantity_as_grams(row)
        linea.proceso_nombre = _normalize_process_name(self._cell_text(row, self.COL_PROCESO) or self._current_active_process())
        linea.proceso_origen_nombre = str(getattr(linea, "proceso_origen_nombre", "") or "").strip()
        if linea.tipo_linea == "proceso":
            linea.cantidad_origen_g = float(linea.cantidad_base_g or 0.0)
        else:
            linea.proceso_origen_nombre = ""
            linea.cantidad_origen_g = 0.0
        return linea

    def _cell_text(self, row: int, col: int) -> str:
        item = self.lines_table.item(row, col)
        return item.text().strip() if item else ""

    def _cell_float(self, row: int, col: int) -> float:
        text = self._cell_text(row, col).replace("g", "").replace(".", "").replace(",", ".")
        try:
            return float(text) if text else 0.0
        except ValueError:
            return 0.0

    def _format_number(self, value: float, decimals: int = 2) -> str:
        text = f"{float(value or 0):,.{decimals}f}"
        return text.replace(",", "_").replace(".", ",").replace("_", ".")

    def _quantity_as_grams(self, row: int) -> float:
        return self._cell_float(row, self.COL_CANTIDAD)

    def _build_recipe_payload(self) -> RecipeActivePayload:
        elaboracion_payload = dict(self.recipe_elaboracion_data)
        elaboracion_payload["recipe_process_order"] = json.dumps(self.recipe_process_names, ensure_ascii=False)
        images_gallery = self._collect_images_gallery()
        return RecipeActivePayload(
            recipe_id=self.current_recipe_id,
            cliente_id=self._selected_cliente_id(),
            nombre=self.nombre_input.text().strip(),
            codigo_receta=self.codigo_input.text().strip(),
            version=self.version_input.text().strip(),
            es_base=self.current_recipe_is_ireks,
            receta_base_id=self.current_base_recipe_id,
            masa_final_deseada_g=self.masa_spin.value(),
            peso_pieza_g=self.peso_spin.value(),
            numero_piezas=self.piezas_spin.value(),
            merma_pct=self.merma_spin.value(),
            observaciones=self.observaciones_input.toPlainText().strip(),
            proceso=self.proceso_input.toPlainText().strip(),
            escandallo_data=dict(self.recipe_escandallo_data),
            elaboracion_data=elaboracion_payload,
            proceso_rich_html=self._proceso_rich_html.strip(),
            images_gallery=images_gallery,
            estado=self.estado_input.text().strip(),
        )

    def _build_recipe_model(self) -> Receta:
        return self.recipe_active_flow_service.build_recipe_model(self._build_recipe_payload())

    def _build_lines(self) -> list[RecetaLinea]:
        lines: list[RecetaLinea] = []
        for row in range(self.lines_table.rowCount()):
            line = self._line_from_row(row)
            if line.nombre_mostrado or line.notas or line.cantidad_base_g:
                line.proceso_nombre = _normalize_process_name(line.proceso_nombre)
                lines.append(line)
        line_processes = [line.proceso_nombre for line in lines]
        self._refresh_process_controls(self.recipe_process_names + line_processes)
        return lines

    def _recalculate(self) -> None:
        receta = self._build_recipe_model()
        lineas = self._build_lines()
        result = self.recipe_service.calculate(receta, lineas, sync_categories=True)
        self._render_lines(result.lineas)
        self._update_summary(result.receta, result.lineas)
        self.current_issues = [f"[{i.level.upper()}] {i.message}" for i in result.issues]
        self._set_issues_text("\n".join(self.current_issues))

    def _on_lines_changed(self) -> None:
        self._auto_recalculate_summary()
        self._refresh_escandallo_table()
        self._schedule_autosave()

    def _refresh_recipe_lines_totals(self) -> None:
        if not hasattr(self, "lines_totals_table"):
            return
        lineas = [self._line_from_row(row) for row in range(self.lines_table.rowCount())]
        total_qty_g, total_pct = _recipe_process_totals(lineas, self._current_active_process())
        values = [
            "",
            "",
            "",
            f"{self._format_number(total_qty_g, 2)} g",
            f"{self._format_number(total_pct, 2)} %",
            "",
        ]
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.lines_totals_table.setItem(0, column, item)
        self.lines_totals_table.setColumnWidth(0, self.lines_table.verticalHeader().width())
        for column in range(self.COL_INGREDIENTE, self.COL_PROCESO + 1):
            self.lines_totals_table.setColumnWidth(
                column + self.LINES_TOTALS_OFFSET,
                self.lines_table.columnWidth(column),
            )

    def _refresh_escandallo_table(self) -> None:
        if not hasattr(self, "escandallo_table"):
            return
        price_by_code = self.recipe_service.std_prices_by_code()
        table = self.escandallo_table
        table.blockSignals(True)
        recipe_lines = self._build_lines()
        cost_sheet = self.recipe_service.build_process_cost_sheet(recipe_lines, self._current_escandallo_process())
        rows = [(max(int(line.orden or 1) - 1, 0), line) for line in cost_sheet]
        table.setRowCount(len(rows))
        total_qty_g = 0.0
        total_pct = 0.0
        total_cost = 0.0
        for row, (source_row, line) in enumerate(rows):
            base_eur_kg = float(line.precio_kg_snapshot or 0.0)
            if base_eur_kg <= 0 and (line.tipo_origen or "").strip().lower() == "std":
                base_eur_kg = float(price_by_code.get((line.codigo_ingrediente or "").strip().lower()) or 0.0)
            effective_eur_kg = float(line.precio_kg_efectivo_snapshot or 0.0) or base_eur_kg
            cost = (float(line.cantidad_base_g or 0.0) / 1000.0) * effective_eur_kg
            promotion_text = ""
            if line.promocion_compra_snapshot > 0 and line.promocion_sin_cargo_snapshot > 0:
                promotion_text = f"{line.promocion_compra_snapshot} + {line.promocion_sin_cargo_snapshot} S/C"
            ingredient = (line.nombre_mostrado or "").strip()
            if line.notas:
                ingredient = f"{ingredient} ({line.notas})"
            values = [
                ingredient,
                f"{self._format_number(line.cantidad_base_g)} g",
                f"{self._format_number(line.porcentaje_panadero, 2)} %",
                f"{self._format_number(base_eur_kg, 2)} €" if base_eur_kg > 0 else "",
                promotion_text,
                f"{self._format_number(effective_eur_kg, 2)} €" if effective_eur_kg > 0 else "",
                f"{self._format_number(cost, 2)} €" if effective_eur_kg > 0 else "",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, source_row)
                is_process = str(getattr(line, "tipo_linea", "") or "").strip().lower() == "proceso"
                if column != self.ESC_COL_EUR_KG or is_process:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if column in {
                    self.ESC_COL_CANTIDAD,
                    self.ESC_COL_PCT,
                    self.ESC_COL_EUR_KG,
                    self.ESC_COL_EUR_KG_EFECTIVO,
                    self.ESC_COL_EUR_LINEA,
                }:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if promotion_text:
                    saving = (float(line.cantidad_base_g or 0.0) / 1000.0) * max(base_eur_kg - effective_eur_kg, 0.0)
                    item.setToolTip(f"Ahorro promocional en esta cantidad: {self._format_number(saving, 2)} €")
                table.setItem(row, column, item)
            total_qty_g += float(line.cantidad_base_g or 0.0)
            total_pct += float(line.porcentaje_panadero or 0.0)
            total_cost += cost
        process_names = {_normalize_process_name(line.proceso_nombre) for line in recipe_lines}
        primary = self.recipe_elaboracion_data.get("recipe_primary_process", "Masa final")
        final_process = primary if primary in process_names else self._current_escandallo_process()
        if final_process == self._current_escandallo_process():
            final_mass_g = total_qty_g
        else:
            final_mass_g = sum(
                float(line.cantidad_base_g or 0.0)
                for line in self.recipe_service.build_process_cost_sheet(recipe_lines, final_process)
            )
        table.blockSignals(False)
        self._refresh_recipe_lines_totals()
        self._refresh_escandallo_totals(total_qty_g, total_pct, total_cost, final_mass_g)

    def _refresh_escandallo_totals(
        self,
        total_qty_g: float,
        total_pct: float,
        total_cost: float,
        final_mass_g: float,
    ) -> None:
        if not hasattr(self, "escandallo_totals_table"):
            return
        values = [
            "",
            "",
            f"{self._format_number(total_qty_g, 2)} g",
            f"{self._format_number(total_pct, 2)} %",
            "",
            "",
            "",
            f"{self._format_number(total_cost, 2)} €",
        ]
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.escandallo_totals_table.setItem(0, column, item)
        self.escandallo_totals_table.setColumnWidth(0, self.escandallo_table.verticalHeader().width())
        for column in range(self.ESC_COL_INGREDIENTE, self.ESC_COL_EUR_LINEA + 1):
            self.escandallo_totals_table.setColumnWidth(
                column + self.ESC_TOTALS_OFFSET,
                self.escandallo_table.columnWidth(column),
            )
        if hasattr(self, "escandallo_summary_group"):
            peso_pieza = float(self.peso_spin.value() or 0.0)
            total_piezas = _piece_count_from_mass(final_mass_g, peso_pieza)
            coste_unitario = total_cost / total_piezas if total_piezas > 0 else 0.0
            self.escandallo_total_masa_lbl.setText(f"{self._format_number(total_qty_g)} g")
            self.escandallo_peso_pieza_lbl.setText(f"{self._format_number(peso_pieza)} g")
            self.escandallo_total_piezas_lbl.setText(self._format_number(total_piezas, 0))
            self.escandallo_coste_unitario_lbl.setText(f"{self._format_number(coste_unitario, 2)} €")
        if hasattr(self, "total_panel"):
            peso_pieza = float(self.peso_spin.value() or 0.0)
            merma_pct = float(self.merma_spin.value() or 0.0)
            total_piezas = _piece_count_from_mass(final_mass_g, peso_pieza)
            peso_terminado = peso_pieza * (1 - (merma_pct / 100.0))
            costes_adicionales = sum(
                self._parse_decimal(self._technical_escandallo_value(key))
                for key in ("costes_fijos", "costes_variables", "otros_costes")
            )
            coste_unitario = (total_cost + costes_adicionales) / total_piezas if total_piezas > 0 else 0.0
            self.total_panel_total_masa_lbl.setText(f"{self._format_number(total_qty_g)} g")
            self.total_panel_peso_pieza_input.blockSignals(True)
            self.total_panel_peso_pieza_input.setText(f"{self._format_number(peso_pieza)} g" if peso_pieza > 0 else "")
            self.total_panel_peso_pieza_input.blockSignals(False)
            self.total_panel_merma_input.blockSignals(True)
            self.total_panel_merma_input.setText(f"{self._format_number(merma_pct, 2)} %")
            self.total_panel_merma_input.blockSignals(False)
            self.total_panel_peso_terminado_lbl.setText(f"{self._format_number(peso_terminado)} g")
            self.total_panel_total_piezas_lbl.setText(f"{self._format_number(total_piezas, 0)} Uds")
            self.total_panel_coste_unitario_lbl.setText(f"{self._format_number(coste_unitario, 2)} €")

    def _on_total_panel_peso_pieza_changed(self) -> None:
        peso_pieza = self._parse_decimal(self.total_panel_peso_pieza_input.text())
        self.peso_spin.setValue(peso_pieza)
        peso_pieza_text = self._format_number(peso_pieza, 2) if peso_pieza > 0 else ""
        self.recipe_escandallo_data["peso_pieza"] = peso_pieza_text
        self.recipe_escandallo_data[f"proceso::{self._current_escandallo_process()}::peso_pieza"] = peso_pieza_text
        self._refresh_escandallo_table()
        self._schedule_autosave()

    def _on_total_panel_merma_changed(self) -> None:
        merma_pct = max(0.0, min(100.0, self._parse_decimal(self.total_panel_merma_input.text())))
        self.merma_spin.setValue(merma_pct)
        self._refresh_escandallo_table()
        self._schedule_autosave()

    def _on_escandallo_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != self.ESC_COL_EUR_KG or self._is_loading_recipe:
            return
        source_row = int(item.data(Qt.ItemDataRole.UserRole) or -1)
        if source_row < 0:
            return
        line = self._line_from_row(source_row)
        price = self._parse_decimal(item.text())
        line.precio_kg_snapshot = price
        ingredient_item = self.lines_table.item(source_row, self.COL_INGREDIENTE)
        if ingredient_item is not None:
            ingredient_item.setData(Qt.ItemDataRole.UserRole, line.model_dump())
        self._auto_recalculate_summary()
        self._refresh_escandallo_table()
        self._schedule_autosave()

    @staticmethod
    def _parse_decimal(value: str) -> float:
        normalized = str(value or "")
        for suffix in ("€", "%", "g", "G", "uds", "Uds"):
            normalized = normalized.replace(suffix, "")
        normalized = normalized.replace(".", "").replace(",", ".").strip()
        try:
            return float(normalized) if normalized else 0.0
        except ValueError:
            return 0.0

    def _technical_peso_pieza(self, fallback: float = 0.0) -> float:
        peso_pieza = self._parse_decimal(self._technical_escandallo_value("peso_pieza"))
        return peso_pieza if peso_pieza > 0 else fallback

    def _technical_escandallo_value(self, key: str) -> str:
        process_key = f"proceso::{self._current_escandallo_process()}::{key}"
        return self.recipe_escandallo_data.get(process_key) or self.recipe_escandallo_data.get(key, "")

    def _on_line_item_changed(self, item: QTableWidgetItem) -> None:
        if self._is_loading_recipe:
            return
        if item.column() not in {self.COL_INGREDIENTE, self.COL_NOTA, self.COL_CANTIDAD, self.COL_PROCESO}:
            return
        self._on_lines_changed()

    def _auto_recalculate_summary(self) -> None:
        receta = self._build_recipe_model()
        lineas = self._build_lines()
        result = self.recipe_service.calculate(receta, lineas, sync_categories=True)
        self._refresh_line_baker_percentages(result.lineas)
        self._update_summary(result.receta, result.lineas)
        self.current_issues = [f"[{i.level.upper()}] {i.message}" for i in result.issues]

    def _refresh_line_baker_percentages(self, lineas: list[RecetaLinea]) -> None:
        self.lines_table.blockSignals(True)
        try:
            for linea in lineas:
                row = int(linea.orden or 0) - 1
                if row < 0 or row >= self.lines_table.rowCount():
                    continue
                pct_item = self.lines_table.item(row, self.COL_PCT)
                if pct_item is not None:
                    pct_item.setText(f"{self._format_number(linea.porcentaje_panadero, 2)} %")
                ingredient_item = self.lines_table.item(row, self.COL_INGREDIENTE)
                if ingredient_item is not None:
                    ingredient_item.setData(Qt.ItemDataRole.UserRole, linea.model_dump())
        finally:
            self.lines_table.blockSignals(False)

    def _schedule_autosave(self) -> None:
        if self._is_loading_recipe or self._document_import_pending:
            return
        self._autosave_timer.start()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        # Extra safety: persist any pending recipe changes when this view closes.
        self._flush_autosave()
        super().closeEvent(event)

    def hideEvent(self, event) -> None:  # type: ignore[override]
        # Persist when navigating away to another main window section.
        self._flush_autosave()
        super().hideEvent(event)

    def _flush_autosave(self) -> None:
        if self._is_loading_recipe or self._document_import_pending:
            return
        self._autosave_timer.stop()
        self._perform_autosave()

    def _perform_autosave(self) -> None:
        if self._is_loading_recipe or self._document_import_pending:
            return
        try:
            result = self.recipe_active_flow_service.autosave_recipe(
                self._build_recipe_payload(),
                self._build_lines(),
                selected_cliente_id=self._selected_cliente_id(),
                recipe_tab_index=self.recipe_tabs.currentIndex(),
            )
            if result.status != "saved":
                if result.status == "error":
                    print(f"[AUTOSAVE] Error guardando receta: {result.message}")
                return
            self.current_recipe_id = result.saved_recipe_id
            self._reload_recipe_list()
            self._select_recipe_in_active_table(self.current_recipe_id)
        except Exception as exc:
            print(f"[AUTOSAVE] Error guardando receta: {exc}")
            traceback.print_exc()

    def _render_lines(self, lineas: list[RecetaLinea]) -> None:
        line_processes = [_normalize_process_name(getattr(linea, "proceso_nombre", "") or "Masa final") for linea in lineas]
        self._refresh_process_controls(self.recipe_process_names + line_processes)
        self.lines_table.setRowCount(0)
        for idx, linea in enumerate(lineas):
            self.lines_table.insertRow(idx)
            self._set_line_row(idx, linea)
        self._ensure_min_line_rows()
        self._apply_process_filter()
        self._refresh_escandallo_table()

    def _ensure_min_line_rows(self) -> None:
        while self.lines_table.rowCount() < self.MIN_LINE_ROWS:
            row = self.lines_table.rowCount()
            self.lines_table.insertRow(row)
            self._set_line_row(row, RecetaLinea(receta_id=0, orden=row + 1))

    def _update_summary(self, receta: Receta, lineas: list[RecetaLinea] | None = None) -> None:
        if lineas:
            process_names = [_normalize_process_name(getattr(linea, "proceso_nombre", "")) for linea in lineas]
            primary = self.recipe_elaboracion_data.get("recipe_primary_process", "Masa final")
            principal = primary if primary in process_names else (process_names[0] if process_names else primary)
            principal_lines = [
                linea for linea in lineas if _normalize_process_name(getattr(linea, "proceso_nombre", "")) == principal
            ]
            total_harinas = sum(float(getattr(l, "cantidad_base_g", 0.0) or 0.0) for l in principal_lines if bool(getattr(l, "es_harina", False)))
            total_liquidos = sum(float(getattr(l, "cantidad_base_g", 0.0) or 0.0) for l in principal_lines if bool(getattr(l, "es_liquido", False)))
            masa_total = sum(float(getattr(l, "cantidad_base_g", 0.0) or 0.0) for l in principal_lines)
            hidratacion = (total_liquidos / total_harinas * 100.0) if total_harinas > 0 else 0.0
            self.total_harinas_lbl.setText(f"{self._format_number(total_harinas)} g")
            self.total_liquidos_lbl.setText(f"{self._format_number(total_liquidos)} g")
            self.hidratacion_lbl.setText(f"{self._format_number(hidratacion)} %")
            self.total_panadero_lbl.setText(f"{self._format_number(0)} %")
            self.masa_total_lbl.setText(f"{self._format_number(masa_total)} g")
            self._update_nutrition_summary(principal_lines, masa_total)
            return
        self.total_harinas_lbl.setText(f"{self._format_number(receta.total_harinas_g)} g")
        self.total_liquidos_lbl.setText(f"{self._format_number(receta.total_liquidos_g)} g")
        self.hidratacion_lbl.setText(f"{self._format_number(receta.hidratacion_pct)} %")
        self.total_panadero_lbl.setText(f"{self._format_number(receta.total_porcentaje_panadero)} %")
        self.masa_total_lbl.setText(f"{self._format_number(receta.masa_total_g)} g")
        self._update_nutrition_summary([], float(receta.masa_total_g or 0.0))

    def _update_nutrition_summary(self, lineas: list[RecetaLinea], masa_total_g: float) -> None:
        nutrientes = {
            "energia_kj": 0.0,
            "energia_kcal": 0.0,
            "grasas_g": 0.0,
            "saturadas_g": 0.0,
            "hidratos_g": 0.0,
            "azucares_g": 0.0,
            "fibra_g": 0.0,
            "proteinas_g": 0.0,
            "sal_g": 0.0,
        }
        if masa_total_g <= 0:
            self._render_nutrition_table_values(nutrientes)
            return

        valid_lines: list[RecetaLinea] = []
        ireks_codes: set[str] = set()
        std_codes: set[str] = set()
        unknown_codes: set[str] = set()
        ireks_names: set[str] = set()
        std_names: set[str] = set()
        for line in lineas:
            if str(getattr(line, "tipo_linea", "ingrediente") or "ingrediente").strip().lower() != "ingrediente":
                continue
            cantidad = float(getattr(line, "cantidad_base_g", 0.0) or 0.0)
            if cantidad <= 0:
                continue
            code = str(getattr(line, "codigo_ingrediente", "") or "").strip()
            source = str(getattr(line, "tipo_origen", "") or "").strip().lower()
            name = str(getattr(line, "nombre_mostrado", "") or "").strip()
            if not code and not name:
                continue
            valid_lines.append(line)
            if source == "ireks":
                if code:
                    ireks_codes.add(code)
                if name:
                    ireks_names.add(name)
            elif source == "std":
                if code:
                    std_codes.add(code)
                if name:
                    std_names.add(name)
            else:
                if code:
                    unknown_codes.add(code)

        if not valid_lines:
            self._render_nutrition_table_values(nutrientes)
            return

        ireks_by_code, std_by_code, nutrition_by_articulo = self.recipe_service.nutrition_lookup(
            ireks_codes,
            std_codes,
            unknown_codes,
            ireks_names,
            std_names,
        )

        for line in valid_lines:
            source = str(getattr(line, "tipo_origen", "") or "").strip().lower()
            code = str(getattr(line, "codigo_ingrediente", "") or "").strip().lower()
            name = str(getattr(line, "nombre_mostrado", "") or "").strip().lower()
            aid = ""
            if source == "ireks":
                aid = ireks_by_code.get(code, "") or ireks_by_code.get(name, "")
            elif source == "std":
                aid = std_by_code.get(code, "") or std_by_code.get(name, "")
            else:
                aid = (
                    ireks_by_code.get(code, "")
                    or std_by_code.get(code, "")
                    or ireks_by_code.get(name, "")
                    or std_by_code.get(name, "")
                )
            if not aid:
                continue
            nutrition = nutrition_by_articulo.get(aid)
            if nutrition is None:
                continue
            cantidad_g = float(getattr(line, "cantidad_base_g", 0.0) or 0.0)
            factor = cantidad_g / 100.0
            nutrientes["energia_kj"] += float(getattr(nutrition, "energia_kj", 0.0) or 0.0) * factor
            nutrientes["energia_kcal"] += float(getattr(nutrition, "energia_kcal", 0.0) or 0.0) * factor
            nutrientes["grasas_g"] += float(getattr(nutrition, "grasas_g", 0.0) or 0.0) * factor
            nutrientes["saturadas_g"] += float(getattr(nutrition, "saturadas_g", 0.0) or 0.0) * factor
            nutrientes["hidratos_g"] += float(getattr(nutrition, "hidratos_g", 0.0) or 0.0) * factor
            nutrientes["azucares_g"] += float(getattr(nutrition, "azucares_g", 0.0) or 0.0) * factor
            nutrientes["fibra_g"] += float(getattr(nutrition, "fibra_g", 0.0) or 0.0) * factor
            nutrientes["proteinas_g"] += float(getattr(nutrition, "proteinas_g", 0.0) or 0.0) * factor
            nutrientes["sal_g"] += float(getattr(nutrition, "sal_g", 0.0) or 0.0) * factor

        per_100 = {key: (value * 100.0 / masa_total_g) for key, value in nutrientes.items()}
        self._render_nutrition_table_values(per_100)

    def _render_nutrition_table_values(self, values_per_100: dict[str, float]) -> None:
        energia_kj = float(values_per_100.get("energia_kj", 0.0) or 0.0)
        energia_kcal = float(values_per_100.get("energia_kcal", 0.0) or 0.0)
        grasas = float(values_per_100.get("grasas_g", 0.0) or 0.0)
        saturadas = float(values_per_100.get("saturadas_g", 0.0) or 0.0)
        hidratos = float(values_per_100.get("hidratos_g", 0.0) or 0.0)
        azucares = float(values_per_100.get("azucares_g", 0.0) or 0.0)
        fibra = float(values_per_100.get("fibra_g", 0.0) or 0.0)
        proteinas = float(values_per_100.get("proteinas_g", 0.0) or 0.0)
        sal = float(values_per_100.get("sal_g", 0.0) or 0.0)

        if not hasattr(self, "nutrition_card"):
            return
        self.nutrition_card.set_rows(
            [
                NutritionRowData(
                    key="energia",
                    label="Energía (kJ/kcal)",
                    value=f"{self._format_number(energia_kj)} kJ\n{self._format_number(energia_kcal)} kcal",
                    icon="energy",
                ),
                NutritionRowData("grasas", "Grasas", f"{self._format_number(grasas)} g", icon="fat"),
                NutritionRowData(
                    "saturadas",
                    "de las cuales saturadas",
                    f"{self._format_number(saturadas)} g",
                    icon="fat",
                    secondary=True,
                ),
                NutritionRowData(
                    "hidratos",
                    "Hidratos de carbono",
                    f"{self._format_number(hidratos)} g",
                    icon="carbohydrate",
                ),
                NutritionRowData(
                    "azucares",
                    "de los cuales azúcares",
                    f"{self._format_number(azucares)} g",
                    icon="sugar",
                    secondary=True,
                ),
                NutritionRowData("fibra", "Fibra", f"{self._format_number(fibra)} g", icon="fiber"),
                NutritionRowData("proteinas", "Proteínas", f"{self._format_number(proteinas)} g", icon="protein"),
                NutritionRowData("sal", "Sal", f"{self._format_number(sal)} g", icon="salt"),
            ]
        )

    def _set_issues_text(self, text: str) -> None:
        self.current_issues = text.splitlines() if text else []

    def _save_recipe(self) -> None:
        self._autosave_timer.stop()
        if self.current_recipe_id is None:
            self.current_recipe_is_ireks = self.recipe_tabs.currentIndex() == 0
        result = self.recipe_active_flow_service.save_recipe(
            self._build_recipe_payload(),
            self._build_lines(),
            selected_cliente_id=self._selected_cliente_id(),
            recipe_tab_index=self.recipe_tabs.currentIndex(),
        )
        if result.status == "missing_name":
            QMessageBox.warning(self, "Validacion", result.message)
            return
        if result.status == "missing_customer":
            QMessageBox.warning(self, "Recetas", result.message)
            return
        if result.status == "error":
            QMessageBox.warning(self, "Recetas", f"No se pudo guardar.\n{result.message}")
            return
        if result.receta is None:
            return
        self._render_lines(result.lineas)
        self._update_summary(result.receta, result.lineas)
        self.current_issues = [f"[{i.level.upper()}] {i.message}" for i in result.issues]
        self._set_issues_text("\n".join(self.current_issues))
        self.current_recipe_id = result.saved_recipe_id
        self._document_import_pending = False
        self._reload_recipe_list()
        QMessageBox.information(self, "Recetas", "Receta guardada.")

    def _save_version(self) -> None:
        if not self.current_recipe_id:
            QMessageBox.warning(self, "Recetas", "Guarda la receta antes de crear una version.")
            return
        comentario, ok = QInputDialog.getText(self, "Guardar version", "Comentario:")
        if not ok:
            return
        result = self.recipe_active_flow_service.save_version(
            self._build_recipe_payload(),
            self._build_lines(),
            comentario.strip(),
            selected_cliente_id=self._selected_cliente_id(),
            recipe_tab_index=self.recipe_tabs.currentIndex(),
        )
        if result.status == "missing_name":
            QMessageBox.warning(self, "Validacion", result.message)
            return
        if result.status == "missing_customer":
            QMessageBox.warning(self, "Recetas", result.message)
            return
        if result.status == "error":
            QMessageBox.warning(self, "Recetas", f"No se pudo guardar la version.\n{result.message}")
            return
        QMessageBox.information(self, "Recetas", "Version guardada.")

    def _duplicate_recipe(self) -> None:
        if not self.current_recipe_id:
            QMessageBox.warning(self, "Recetas", "Selecciona una receta para duplicar.")
            return
        cloned = self.recipe_service.duplicate_recipe(self.current_recipe_id, self._selected_cliente_id())
        self._reload_recipe_list()
        self._load_recipe(cloned.receta.id or 0)
        QMessageBox.information(self, "Recetas", "Receta duplicada.")

    def _delete_recipe(self) -> None:
        if not self.current_recipe_id:
            return
        confirm = QMessageBox.question(self, "Recetas", "Eliminar receta seleccionada?")
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self.recipe_service.delete_recipe(self.current_recipe_id)
        self._reload_recipe_list()
        self._new_recipe()

    def _print_recipe(self) -> None:
        QMessageBox.information(self, "Recetas", "Impresion se implementa en Fase 3.")

    def _export_pdf(self) -> None:
        if not self.current_recipe_id:
            QMessageBox.warning(self, "Recetas", "Selecciona y guarda una receta antes de exportar.")
            return

        export_dialog = RecipePdfExportDialog(self)
        if not export_dialog.exec():
            return
        layout_mode = export_dialog.layout_mode()
        include_escandallo = layout_mode == "minimal" and export_dialog.include_escandallo()
        include_nutrition = layout_mode == "minimal" and export_dialog.include_nutrition()
        include_baker_percentage = layout_mode == "minimal" and export_dialog.include_baker_percentage()
        include_images = layout_mode == "minimal" and export_dialog.include_images()
        if layout_mode == "minimal":
            preview_dialog = MinimalRecipePdfPreviewDialog(
                self.pdf_service,
                self.current_recipe_id,
                include_escandallo,
                include_nutrition,
                include_baker_percentage,
                include_images,
                self,
            )
            try:
                if not preview_dialog.exec():
                    return
            finally:
                preview_dialog.cleanup_preview()

        default_name = _default_recipe_pdf_filename(
            self.nombre_input.text().strip() or f"receta_{self.current_recipe_id}",
            self.cliente_combo.currentText().strip(),
        )
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar receta a PDF",
            default_name,
            "PDF (*.pdf)",
        )
        if not output_path:
            return

        try:
            self.pdf_service.export_recipe_to_pdf(
                self.current_recipe_id,
                Path(output_path),
                layout_mode=layout_mode,
                include_escandallo=include_escandallo,
                include_nutrition=include_nutrition,
                include_baker_percentage=include_baker_percentage,
                include_images=include_images,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Recetas", f"No se pudo exportar el PDF:\n{exc}")
            return
        QMessageBox.information(self, "Recetas", "PDF generado correctamente.")

    def _export_excel(self) -> None:
        QMessageBox.information(self, "Recetas", "Exportacion Excel se implementa en Fase 3.")

    def _refresh_customer_filter_input(self, label: str | None = None) -> None:
        if not hasattr(self, "customer_filter_input"):
            return
        if label is None:
            label = ""
            for customer_id, customer_label in getattr(self, "_customer_filter_items", []):
                if customer_id == self.customer_filter_selected_id:
                    label = customer_label
                    break
        self.customer_filter_input.blockSignals(True)
        self.customer_filter_input.setText(label)
        self.customer_filter_input.blockSignals(False)
        self.customer_filter_clear_btn.setEnabled(bool(str(label or "").strip()))
        self.customer_filter_results.setRowCount(0)
        self.customer_filter_results.setVisible(False)

    def _refresh_customer_filter_button(self) -> None:
        self._refresh_customer_filter_input()

    def _load_base_recipe_template(self) -> None:
        if self.recipe_tabs.currentIndex() != 1:
            return
        dialog = BaseRecipeSearchDialog(self.recipe_service, self)
        if not dialog.exec() or not dialog.selected_recipe_id:
            return
        recipe_id = dialog.selected_recipe_id
        aggregate = self.recipe_service.get_recipe(recipe_id)
        if not aggregate:
            return

        base = aggregate.receta
        self.current_recipe_id = None
        self.current_recipe_is_ireks = False
        self.current_base_recipe_id = base.id
        self.nombre_input.setText(base.nombre)
        self.codigo_input.clear()
        self.version_input.setText("1.0")
        self.estado_input.setText("borrador")
        self.masa_spin.setValue(base.masa_final_deseada_g)
        self.peso_spin.setValue(base.peso_pieza_g)
        self.piezas_spin.setValue(base.numero_piezas)
        self.merma_spin.setValue(base.merma_pct)
        self.proceso_input.setPlainText(base.proceso)
        self.observaciones_input.setPlainText(base.observaciones)

        cloned_lines = [
            RecetaLinea(
                receta_id=0,
                orden=line.orden,
                tipo_origen=line.tipo_origen,
                ingrediente_id=line.ingrediente_id,
                nombre_mostrado=line.nombre_mostrado,
                codigo_ingrediente=line.codigo_ingrediente,
                familia=line.familia,
                subfamilia=line.subfamilia,
                es_harina=line.es_harina,
                es_liquido=line.es_liquido,
                cantidad_base_g=line.cantidad_base_g,
                porcentaje_panadero=line.porcentaje_panadero,
                cantidad_calculada_g=line.cantidad_calculada_g,
                precio_kg_snapshot=line.precio_kg_snapshot,
                coste_linea=line.coste_linea,
                tipo_linea=line.tipo_linea,
                proceso_nombre=line.proceso_nombre,
                proceso_origen_nombre=line.proceso_origen_nombre,
                cantidad_origen_g=line.cantidad_origen_g,
                es_subreceta=line.es_subreceta,
                subreceta_id=line.subreceta_id,
                notas=line.notas,
            )
            for line in aggregate.lineas
        ]
        self._render_lines(cloned_lines)
        self._auto_recalculate_summary()




