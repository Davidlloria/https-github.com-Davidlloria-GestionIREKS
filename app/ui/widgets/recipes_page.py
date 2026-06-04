from __future__ import annotations

import json
from pathlib import Path
import traceback
from typing import Any, cast

from PySide6.QtCore import QEvent, QSize, QTimer, Qt
from PySide6.QtGui import QAction, QBrush, QColor, QFont, QIcon, QKeySequence, QPixmap, QShortcut, QTextCharFormat
from PySide6.QtWidgets import (
    QAbstractItemView,
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
from app.services.recipe_service import RecipeService
from app.viewmodels import IngredientChoice


def _normalize_process_name(value: str | None) -> str:
    text = str(value or "").strip()
    return text if text else "Masa final"


def _unique_process_names(values: list[str]) -> list[str]:
    names: list[str] = []
    for value in values:
        name = _normalize_process_name(value)
        if name not in names:
            names.append(name)
    if "Masa final" not in names:
        names.insert(0, "Masa final")
    return names


def _collect_recipe_image_gallery(items: list[tuple[str, bool]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for idx, (path, is_main) in enumerate(items):
        clean_path = str(path or "").strip()
        if not clean_path:
            continue
        rows.append({"path": clean_path, "is_main": bool(is_main), "order": idx})
    return rows


def _load_recipe_image_gallery(raw_value: str) -> list[dict[str, object]]:
    text = (raw_value or "").strip()
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
    return {str(k): str(v) for k, v in payload.items()}


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


class CustomerSearchDialog(QDialog):
    def __init__(self, service: RecipeService, selected_id: str = "", parent=None) -> None:
        super().__init__(parent)
        self.service = service
        self.selected_id = selected_id
        self.selected_customer_id: str | None = None
        self.selected_customer_label: str = "Todos los clientes"
        self.setWindowTitle("Seleccionar cliente")
        self.resize(820, 480)
        self._build_ui()
        self._search()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filtrar por ocurrencia...")
        self.search_input.textChanged.connect(self._search)
        layout.addWidget(self.search_input)

        self.table = QTableWidget(0, 3)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setHorizontalHeaderLabels(["Codigo", "Cliente", "ID"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.doubleClicked.connect(self._accept_selected)
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        all_btn = QPushButton("Todos los clientes")
        all_btn.setProperty("btnRole", "secondary")
        all_btn.clicked.connect(self._accept_all)
        actions.addWidget(all_btn)
        actions.addStretch()
        use_btn = QPushButton("Seleccionar")
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
        customers = self.service.search_customers(term)
        self.table.setRowCount(len(customers))
        for row, customer in enumerate(customers):
            code = str(customer.cliente_codigo or "")
            label = customer.cliente_nombre_comercial or customer.cliente_nombre_fiscal or str(customer.cliente_id)
            customer_id = str(customer.cliente_id or "")
            values = [code, label, customer_id]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if col == 2:
                    cell.setData(Qt.ItemDataRole.UserRole, customer_id)
                self.table.setItem(row, col, cell)
            if customer_id == self.selected_id:
                self.table.selectRow(row)

    def _accept_all(self) -> None:
        self.selected_customer_id = ""
        self.selected_customer_label = "Todos los clientes"
        self.accept()

    def _accept_selected(self) -> None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            QMessageBox.warning(self, "Clientes", "Selecciona un cliente.")
            return
        row = selected[0].row()
        id_item = self.table.item(row, 2)
        label_item = self.table.item(row, 1)
        if not id_item or not label_item:
            return
        self.selected_customer_id = str(id_item.data(Qt.ItemDataRole.UserRole) or "").strip()
        self.selected_customer_label = label_item.text().strip()
        self.accept()


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


class RecipeTechnicalDialog(QDialog):
    COL_INGREDIENTE = 0
    COL_CANTIDAD = 1
    COL_PCT = 2
    COL_EUR_KG = 3
    COL_EUR_LINEA = 4
    TOTALS_OFFSET = 1

    def __init__(
        self,
        recipe_name: str,
        recipe_id: int | None,
        lines: list[tuple[RecetaLinea, str, str]],
        peso_pieza_g: float = 0.0,
        escandallo_data: dict[str, str] | None = None,
        elaboracion_data: dict[str, str] | None = None,
        initial_process: str = "Masa final",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Receta técnica")
        self.setFixedSize(1110, 760)
        self.recipe_name = str(recipe_name or "receta").strip() or "receta"
        self.recipe_id = recipe_id
        self.pdf_service = PdfService()
        self.all_lines = list(lines)
        self.lines: list[tuple[RecetaLinea, str, str]] = []
        self._display_indices: list[int] = []
        self.process_names = self._collect_process_names(self.all_lines)
        self.current_process = _normalize_process_name(initial_process)
        if self.current_process not in self.process_names:
            self.current_process = self.process_names[0] if self.process_names else "Masa final"
        self.peso_pieza_g = float(peso_pieza_g or 0.0)
        self.escandallo_data = {k: str(v) for k, v in (escandallo_data or {}).items()}
        self.elaboracion_data = {k: str(v) for k, v in (elaboracion_data or {}).items()}
        self.std_prices = self._load_std_prices()
        self._build_ui(recipe_name)
        self._apply_saved_panel_values()
        self._apply_process_filter()

    def _build_ui(self, recipe_name: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        title = QLabel(recipe_name)
        title.setStyleSheet("color: #000000; font-size: 18px; font-weight: 700;")
        layout.addWidget(title)

        process_row = QHBoxLayout()
        process_row.setContentsMargins(0, 0, 0, 0)
        process_row.setSpacing(8)
        process_row.addWidget(QLabel("Proceso"))
        self.process_combo = QComboBox()
        self.process_combo.setEditable(False)
        self.process_combo.addItems(self.process_names)
        self.process_combo.setMinimumWidth(180)
        self.process_combo.setMaximumWidth(260)
        idx = self.process_combo.findText(self.current_process)
        self.process_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.process_combo.currentTextChanged.connect(self._on_process_changed)
        process_row.addWidget(self.process_combo)
        self.edit_process_btn = QPushButton("Editar proceso")
        self.edit_process_btn.setProperty("btnRole", "primary")
        self.edit_process_btn.setFixedHeight(self.process_combo.sizeHint().height())
        self.edit_process_btn.clicked.connect(self._open_main_process_editor)
        process_row.addWidget(self.edit_process_btn)
        self.process_hint_lbl = QLabel("")
        self.process_hint_lbl.setStyleSheet("color: #51627A; font-size: 12px;")
        process_row.addWidget(self.process_hint_lbl)
        process_row.addStretch(1)
        layout.addLayout(process_row)

        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(12)

        left_panel = QWidget()
        left_panel.setFixedWidth(750)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        self.table = QTableWidget(0, 5)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setHorizontalHeaderLabels(
            [
                "Ingrediente",
                "Cantidad",
                "% panadero",
                "€/kg",
                "€/ingrediente",
            ]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(self.COL_INGREDIENTE, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self.COL_CANTIDAD, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(self.COL_PCT, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(self.COL_EUR_KG, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(self.COL_EUR_LINEA, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(self.COL_CANTIDAD, 96)
        self.table.setColumnWidth(self.COL_PCT, 92)
        self.table.setColumnWidth(self.COL_EUR_KG, 72)
        self.table.setColumnWidth(self.COL_EUR_LINEA, 108)
        left_layout.addWidget(self.table, 1)

        self.totals_table = QTableWidget(1, 6)
        self.totals_table.setHorizontalHeaderLabels(["", "", "", "", "", ""])
        self.totals_table.horizontalHeader().setVisible(False)
        self.totals_table.verticalHeader().setVisible(False)
        self.totals_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.totals_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.totals_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.totals_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.totals_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.totals_table.setFixedHeight(34)
        self.totals_table.setShowGrid(False)
        self.totals_table.setFrameShape(QFrame.Shape.NoFrame)
        self.totals_table.setFrameShadow(QFrame.Shadow.Plain)
        self.totals_table.setStyleSheet(
            "QTableWidget { background-color: #2F80ED; border: none; border-radius: 0; }"
            "QTableWidget::item { background-color: #2F80ED; color: #FFFFFF; border: none; border-radius: 0; padding: 0; }"
        )
        left_layout.addWidget(self.totals_table)

        self.table.horizontalHeader().sectionResized.connect(self._sync_totals_columns)
        self.table.verticalHeader().sectionResized.connect(self._sync_totals_columns)
        self._sync_totals_columns()
        QTimer.singleShot(0, self._sync_totals_columns)
        self.elaboration_panel = self._build_elaboration_panel()
        self.elaboration_panel.setFixedWidth(750)
        left_layout.addWidget(self.elaboration_panel)
        self.escandallo_panel = self._build_escandallo_panel()
        self.escandallo_panel.setFixedWidth(320)
        self.escandallo_panel.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        content_row.addWidget(left_panel)
        content_row.addWidget(self.escandallo_panel)
        layout.addLayout(content_row, 1)

        export_simple_btn = QPushButton("Exportar PDF simple")
        export_simple_btn.setProperty("btnRole", "primary")
        export_simple_btn.clicked.connect(self._export_pdf_simple)
        export_ext_btn = QPushButton("Exportar PDF extendida")
        export_ext_btn.setProperty("btnRole", "success")
        export_ext_btn.clicked.connect(self._export_pdf_extended)
        close_btn = QPushButton("Cerrar")
        close_btn.setProperty("btnRole", "secondary")
        close_btn.clicked.connect(self.accept)
        actions = QHBoxLayout()
        actions.addWidget(export_simple_btn)
        actions.addWidget(export_ext_btn)
        actions.addStretch()
        actions.addWidget(close_btn)
        layout.addLayout(actions)

        self.table.itemChanged.connect(self._on_item_changed)
        self._register_focus_clear_targets()

    def _normalize_process_name(self, value: str | None) -> str:
        text = str(value or "").strip()
        return text if text else "Masa final"

    def _collect_process_names(self, lines: list[tuple[RecetaLinea, str, str]]) -> list[str]:
        names: list[str] = []
        for line, _cantidad_text, _unidad_text in lines:
            name = _normalize_process_name(getattr(line, "proceso_nombre", ""))
            if name not in names:
                names.append(name)
        if "Masa final" in names:
            names = [x for x in names if x != "Masa final"] + ["Masa final"]
        if not names:
            names = ["Masa final"]
        return names

    def _on_process_changed(self) -> None:
        self._persist_current_process_panel_values()
        self._persist_visible_line_edits()
        self.current_process = _normalize_process_name(self.process_combo.currentText())
        self._load_process_panel_values()
        self._apply_process_filter()

    def _open_main_process_editor(self) -> None:
        host = self.parent()
        if host and hasattr(host, "_open_process_editor_dialog"):
            host._open_process_editor_dialog()

    def _apply_process_filter(self) -> None:
        self.lines = []
        self._display_indices = []
        for idx, (line, cantidad_text, unidad_text) in enumerate(self.all_lines):
            proc = _normalize_process_name(getattr(line, "proceso_nombre", ""))
            if proc != self.current_process:
                continue
            self._display_indices.append(idx)
            self.lines.append((line, cantidad_text, unidad_text))
        if hasattr(self, "process_hint_lbl"):
            self.process_hint_lbl.setText(f"Mostrando: {self.current_process}")
        self._populate()

    def _persist_visible_line_edits(self) -> None:
        if not self._display_indices:
            return
        for row, src_idx in enumerate(self._display_indices):
            if src_idx < 0 or src_idx >= len(self.all_lines):
                continue
            line, cantidad_text, unidad_text = self.all_lines[src_idx]
            eur_item = self.table.item(row, self.COL_EUR_KG)
            eur_kg = self._to_float(eur_item.text() if eur_item else "")
            line.precio_kg_snapshot = eur_kg
            line.coste_linea = (float(line.cantidad_base_g or 0.0) / 1000.0) * eur_kg
            self.all_lines[src_idx] = (line, cantidad_text, unidad_text)

    def _process_key(self, process_name: str, field: str) -> str:
        return f"proceso::{process_name}::{field}"

    def _persist_current_process_panel_values(self) -> None:
        process = _normalize_process_name(self.current_process)
        sc_values = {
            "peso_pieza": self.sc_peso_pieza.text().strip(),
            "costes_fijos": self.sc_costes_fijos.text().strip(),
            "costes_variables": self.sc_costes_variables.text().strip(),
            "otros_costes": self.sc_otros_costes.text().strip(),
            "margen_previsto": self.sc_margen_previsto.text().strip(),
            "precio_venta": self.sc_precio_venta.text().strip(),
            "igic": self.sc_igic.text().strip(),
        }
        for key, value in sc_values.items():
            self.escandallo_data[key] = value
            self.escandallo_data[self._process_key(process, key)] = value

        el_values = {
            "peso_pieza": self.el_peso_pieza.text().strip(),
            "am1_lenta": self.am1_lenta.text().strip(),
            "am1_rapida": self.am1_rapida.text().strip(),
            "am1_temp": self.am1_temp.text().strip(),
            "rep_bloque_1": self.rep_bloque_1.text().strip(),
            "rep_bloque_2": self.rep_bloque_2.text().strip(),
            "am2_lenta": self.rep_bloque_1.text().strip(),
            "am2_rapida": self.rep_bloque_2.text().strip(),
            "am2_temp": self.fermentacion_temp.text().strip(),
            "fermentacion_temp": self.fermentacion_temp.text().strip(),
            "rep_fermentacion": self.rep_fermentacion.text().strip(),
            "fermentacion_humedad": self.fermentacion_humedad.text().strip(),
            "precalentamiento_pre": self.precalentamiento_pre.text().strip(),
            "temp_coccion_pre": self.temp_coccion_pre.text().strip(),
            "tiempo_coccion_pre": self.tiempo_coccion_pre.text().strip(),
            "vapor_pre": self.vapor_pre.text().strip(),
            "precalentamiento_coc": self.precalentamiento_coc.text().strip(),
            "temp_coccion_coc": self.temp_coccion_coc.text().strip(),
            "tiempo_coccion_coc": self.tiempo_coccion_coc.text().strip(),
            "vapor_coc": self.vapor_coc.text().strip(),
        }
        for key, value in el_values.items():
            self.elaboracion_data[key] = value
            self.elaboracion_data[self._process_key(process, key)] = value

    def _load_process_panel_values(self) -> None:
        process = _normalize_process_name(self.current_process)

        def sc_val(key: str, default: str = "") -> str:
            return str(
                self.escandallo_data.get(self._process_key(process, key), self.escandallo_data.get(key, default)) or default
            ).strip()

        def el_val(key: str, default: str = "") -> str:
            return str(
                self.elaboracion_data.get(self._process_key(process, key), self.elaboracion_data.get(key, default)) or default
            ).strip()

        self.sc_peso_pieza.setText(sc_val("peso_pieza", self._fmt_number(self.peso_pieza_g, 2)))
        self.sc_costes_fijos.setText(sc_val("costes_fijos", ""))
        self.sc_costes_variables.setText(sc_val("costes_variables", ""))
        self.sc_otros_costes.setText(sc_val("otros_costes", ""))
        self.sc_margen_previsto.setText(sc_val("margen_previsto", "0"))
        self.sc_precio_venta.setText(sc_val("precio_venta", ""))
        self.sc_igic.setText(sc_val("igic", "3"))

        self.el_peso_pieza.setText(el_val("peso_pieza", self.sc_peso_pieza.text().strip()))
        self.am1_lenta.setText(el_val("am1_lenta", ""))
        self.am1_rapida.setText(el_val("am1_rapida", ""))
        self.am1_temp.setText(el_val("am1_temp", ""))
        self.rep_bloque_1.setText(el_val("rep_bloque_1", el_val("am2_lenta", "")))
        self.rep_bloque_2.setText(el_val("rep_bloque_2", el_val("am2_rapida", "")))
        self.fermentacion_temp.setText(el_val("fermentacion_temp", el_val("am2_temp", "")))
        self.rep_fermentacion.setText(el_val("rep_fermentacion", ""))
        self.fermentacion_humedad.setText(el_val("fermentacion_humedad", ""))
        self.precalentamiento_pre.setText(el_val("precalentamiento_pre", ""))
        self.temp_coccion_pre.setText(el_val("temp_coccion_pre", ""))
        self.tiempo_coccion_pre.setText(el_val("tiempo_coccion_pre", ""))
        self.vapor_pre.setText(el_val("vapor_pre", ""))
        self.precalentamiento_coc.setText(el_val("precalentamiento_coc", ""))
        self.temp_coccion_coc.setText(el_val("temp_coccion_coc", ""))
        self.tiempo_coccion_coc.setText(el_val("tiempo_coccion_coc", ""))
        self.vapor_coc.setText(el_val("vapor_coc", ""))
        self._recalculate_escandallo()

    def _load_std_prices(self) -> dict[str, float]:
        return self.recipe_service.std_prices_by_code()

    def _register_focus_clear_targets(self) -> None:
        self.installEventFilter(self)
        for widget in self.findChildren(QWidget):
            widget.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:  # type: ignore[override]
        if event.type() == QEvent.Type.MouseButtonPress:
            focused = self.focusWidget()
            watched_widget = watched if isinstance(watched, QWidget) else None
            if isinstance(focused, QLineEdit) and watched_widget is not None:
                clicked_inside_focused = watched_widget is focused or focused.isAncestorOf(watched_widget)
                if not clicked_inside_focused and not isinstance(watched_widget, QLineEdit):
                    focused.clearFocus()
        return super().eventFilter(watched, event)

    def _build_escandallo_panel(self) -> QWidget:
        panel = QGroupBox("ESCANDALLO")
        panel.setStyleSheet(
            "QGroupBox {"
            "font-weight: 800;"
            "font-size: 18px;"
            "color: #000000;"
            "border: 1px solid #BFC7D4;"
            "border-radius: 0px;"
            "margin-top: 14px;"
            "padding-top: 8px;"
            "}"
            "QGroupBox::title {"
            "subcontrol-origin: margin;"
            "left: 8px;"
            "padding: 1px 4px;"
            "background: #C5C8CC;"
            "}"
            "QLabel[rowLabel='true'] { color: #111111; font-size: 13px; }"
            "QLabel[value='true'] { background: #B8D1EA; color: #111111; padding: 2px 6px; }"
            "QLabel[valueSoft='true'] { background: #F4F4C8; color: #111111; padding: 2px 6px; }"
            "QLabel[valueStrong='true'] { background: #E51313; color: #FFFFFF; padding: 2px 6px; font-weight: 700; }"
            "QLabel[valueGood='true'] { background: #39A52E; color: #FFFFFF; padding: 2px 6px; font-weight: 700; }"
            "QLabel[section='true'] {"
            "background: #E9C5B1;"
            "color: #111111;"
            "font-weight: 800;"
            "padding: 2px 6px;"
            "}"
            "QLineEdit[esc='true'] {"
            "background: #F4F4C8;"
            "border: 1px solid #D2D6AF;"
            "padding: 1px 6px;"
            "}"
        )
        grid = QGridLayout(panel)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(3)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)

        row = 0

        def add_label(text: str) -> QLabel:
            nonlocal row
            lbl = QLabel(text)
            lbl.setProperty("rowLabel", True)
            grid.addWidget(lbl, row, 0)
            return lbl

        def add_value(value: QWidget, fixed_width: int = 112) -> None:
            nonlocal row
            value.setFixedWidth(fixed_width)
            if isinstance(value, QLabel):
                value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(value, row, 1)
            row += 1

        def add_section(text: str) -> None:
            nonlocal row
            section = QLabel(text)
            section.setProperty("section", True)
            section.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(section, row, 0, 1, 2)
            row += 1

        def add_input(default_text: str = "") -> QLineEdit:
            edit = QLineEdit(default_text)
            edit.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            edit.setProperty("esc", True)
            edit.editingFinished.connect(self._recalculate_escandallo)
            return edit

        add_section("PRODUCCION")
        self.sc_total_masa = QLabel("0,00 g")
        self.sc_total_masa.setProperty("value", True)
        add_label("Total masa")
        add_value(self.sc_total_masa)

        self.sc_peso_pieza = add_input("260")
        self.sc_peso_pieza.editingFinished.connect(self._on_sc_peso_pieza_changed)
        add_label("Peso por pieza (gr)")
        add_value(self.sc_peso_pieza)

        self.sc_rendimiento = QLabel("0 Uds")
        self.sc_rendimiento.setProperty("valueSoft", True)
        add_label("Rendimiento")
        add_value(self.sc_rendimiento)

        add_section("COSTES DE PRODUCCION")
        self.sc_coste_mp = QLabel("0,00 €")
        self.sc_coste_mp.setProperty("value", True)
        add_label("Coste materias primas")
        add_value(self.sc_coste_mp)

        self.sc_costes_fijos = add_input("")
        self.sc_costes_fijos.editingFinished.connect(lambda: self._format_field_with_suffix(self.sc_costes_fijos, "€"))
        add_label("Costes fijos")
        add_value(self.sc_costes_fijos)

        self.sc_costes_variables = add_input("")
        self.sc_costes_variables.editingFinished.connect(lambda: self._format_field_with_suffix(self.sc_costes_variables, "€"))
        add_label("Costes variables")
        add_value(self.sc_costes_variables)

        self.sc_otros_costes = add_input("")
        self.sc_otros_costes.editingFinished.connect(lambda: self._format_field_with_suffix(self.sc_otros_costes, "€"))
        add_label("Otros costes")
        add_value(self.sc_otros_costes)

        self.sc_total_costes = QLabel("0,00 €")
        self.sc_total_costes.setProperty("valueStrong", True)
        add_label("Total costes")
        add_value(self.sc_total_costes)

        add_section("UNIDADES PRODUCIDAS")
        self.sc_unidades_totales = QLabel("0 Uds")
        self.sc_unidades_totales.setProperty("valueSoft", True)
        add_label("Unidades totales")
        add_value(self.sc_unidades_totales)

        self.sc_coste_unitario = QLabel("0,00 €")
        self.sc_coste_unitario.setProperty("valueStrong", True)
        add_label("Coste unitario")
        add_value(self.sc_coste_unitario)

        add_section("PRECIO RECOMENDADO")
        self.sc_margen_previsto = add_input("0")
        self.sc_margen_previsto.editingFinished.connect(lambda: self._format_field_with_suffix(self.sc_margen_previsto, "%"))
        add_label("Margen previsto %")
        add_value(self.sc_margen_previsto)

        self.sc_precio_recomendado = QLabel("0,00 €")
        self.sc_precio_recomendado.setProperty("value", True)
        add_label("Precio recomendado")
        add_value(self.sc_precio_recomendado)

        add_section("CALCULO PVP")
        self.sc_precio_venta = add_input("")
        self.sc_precio_venta.editingFinished.connect(lambda: self._format_field_with_suffix(self.sc_precio_venta, "€"))
        add_label("Precio de venta")
        add_value(self.sc_precio_venta)

        self.sc_igic = add_input("3")
        self.sc_igic.editingFinished.connect(lambda: self._format_field_with_suffix(self.sc_igic, "%"))
        self.sc_igic.setFixedWidth(52)
        self.sc_calc_igic = QLabel("0,00 €")
        self.sc_calc_igic.setProperty("value", True)
        self.sc_calc_igic.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.sc_calc_igic.setFixedWidth(56)
        igic_row = QWidget()
        igic_row_layout = QHBoxLayout(igic_row)
        igic_row_layout.setContentsMargins(0, 0, 0, 0)
        igic_row_layout.setSpacing(4)
        igic_row_layout.addWidget(self.sc_igic)
        igic_row_layout.addWidget(self.sc_calc_igic)
        add_label("IGIC %")
        add_value(igic_row)

        self.sc_precio_neto = QLabel("0,00 €")
        self.sc_precio_neto.setProperty("value", True)
        add_label("Precio neto")
        add_value(self.sc_precio_neto)

        self.sc_pct_coste_mp = QLabel("0,00 %")
        self.sc_pct_coste_mp.setProperty("valueStrong", True)
        add_label("% Coste de Materia Primas")
        add_value(self.sc_pct_coste_mp)

        self.sc_pct_margen_pv = QLabel("0,00 %")
        self.sc_pct_margen_pv.setProperty("valueGood", True)
        add_label("% Margen sobre PV")
        add_value(self.sc_pct_margen_pv)

        return panel

    def _build_elaboration_panel(self) -> QWidget:
        panel = QFrame()
        panel.setStyleSheet(
            "QFrame[paramPanel='true'] { border: none; background: transparent; }"
            "QLabel[paramTitle='true'] { background: #BEBEBE; color: #111111; font-weight: 800; padding: 4px 8px; }"
            "QLabel[paramSection='true'] { background: #0070C0; color: #FFFFFF; font-weight: 700; padding: 4px 6px; }"
            "QLabel[paramLabel='true'] { background: #CFCFCF; color: #111111; padding: 1px 4px; }"
            "QLabel[paramUnit='true'] { background: #F0EDC6; color: #111111; padding: 1px 2px; }"
            "QLabel[paramAuto='true'] { background: #B8D7E8; color: #111111; padding: 1px 4px; }"
            "QLineEdit[paramEdit='true'] { background: #F0EDC6; border: 1px solid #D5D1A6; padding: 1px 4px; }"
        )
        panel.setProperty("paramPanel", True)
        root = QVBoxLayout(panel)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(2)

        title = QLabel("PARÁMETROS DE ELABORACIÓN")
        title.setProperty("paramTitle", True)
        root.addWidget(title)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(3)
        grid.setVerticalSpacing(2)
        for col in range(9):
            grid.setColumnStretch(col, 0)

        label_w = 118
        value_w = 70
        unit_w = 34

        def section(text: str, row: int, col: int) -> None:
            lbl = QLabel(text)
            lbl.setProperty("paramSection", True)
            if row > 0:
                grid.setRowMinimumHeight(row - 1, 8)
            grid.addWidget(lbl, row, col, 1, 3)

        def edit(default_text: str = "") -> QLineEdit:
            field = QLineEdit(default_text)
            field.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            field.setProperty("paramEdit", True)
            field.setFixedWidth(value_w)
            field.setMaxLength(5)
            return field

        def auto_value(default_text: str = "") -> QLabel:
            field = QLabel(default_text)
            field.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            field.setProperty("paramAuto", True)
            field.setFixedWidth(value_w)
            return field

        def row(label_text: str, value_widget: QWidget, unit_text: str, row_idx: int, col_idx: int) -> None:
            label = QLabel(label_text)
            label.setProperty("paramLabel", True)
            label.setFixedWidth(label_w)
            unit = QLabel(unit_text)
            unit.setProperty("paramUnit", True)
            unit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            unit.setFixedWidth(unit_w)
            grid.addWidget(label, row_idx, col_idx)
            grid.addWidget(value_widget, row_idx, col_idx + 1)
            grid.addWidget(unit, row_idx, col_idx + 2)

        section("Rendimiento (pesos en gramos)", 0, 0)
        section("1º Amasado", 0, 3)
        section("Reposos", 0, 6)

        self.el_total_masa = auto_value("0,00")
        self.el_peso_pieza = edit(self._fmt_number(self.peso_pieza_g, 2) if self.peso_pieza_g > 0 else "")
        self.el_peso_pieza.editingFinished.connect(self._on_el_peso_pieza_changed)
        self.el_rendimiento = auto_value("0")
        row("Total masa", self.el_total_masa, "gr", 1, 0)
        row("Peso por pieza", self.el_peso_pieza, "gr", 2, 0)
        row("Total piezas", self.el_rendimiento, "uds", 3, 0)

        self.am1_lenta = edit("")
        self.am1_rapida = edit("")
        self.am1_temp = edit("")
        row("Velocidad lenta", self.am1_lenta, "min", 1, 3)
        row("Velocidad rápida", self.am1_rapida, "min", 2, 3)
        row("Temp. de la masa", self.am1_temp, "°C", 3, 3)

        self.rep_bloque_1 = edit("")
        self.rep_bloque_2 = edit("")
        row("Reposo en bloque", self.rep_bloque_1, "min", 1, 6)
        row("Reposo en pieza", self.rep_bloque_2, "min", 2, 6)

        section("Fermentación", 4, 0)
        section("Precocción", 4, 3)
        section("Cocción", 4, 6)

        self.fermentacion_temp = edit("")
        self.rep_fermentacion = edit("")
        self.fermentacion_humedad = edit("")
        row("Temperatura", self.fermentacion_temp, "°C", 5, 0)
        row("Tiempo", self.rep_fermentacion, "min", 6, 0)
        row("Humedad", self.fermentacion_humedad, "%", 7, 0)

        self.precalentamiento_pre = edit("")
        self.temp_coccion_pre = edit("")
        self.tiempo_coccion_pre = edit("")
        self.vapor_pre = edit("")
        row("Temp. inicial", self.precalentamiento_pre, "°C", 5, 3)
        row("Temp de cocción", self.temp_coccion_pre, "°C", 6, 3)
        row("Tiempo de cocción", self.tiempo_coccion_pre, "min", 7, 3)
        row("Vapor", self.vapor_pre, "min", 8, 3)

        self.precalentamiento_coc = edit("")
        self.temp_coccion_coc = edit("")
        self.tiempo_coccion_coc = edit("")
        self.vapor_coc = edit("")
        row("Temp. inicial", self.precalentamiento_coc, "°C", 5, 6)
        row("Temp de cocción", self.temp_coccion_coc, "°C", 6, 6)
        row("Tiempo de cocción", self.tiempo_coccion_coc, "min", 7, 6)
        row("Vapor", self.vapor_coc, "min", 8, 6)

        root.addLayout(grid)
        return panel

    def _populate(self) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.lines))
        for row, (line, cantidad_text, unidad_text) in enumerate(self.lines):
            codigo = (line.codigo_ingrediente or "").strip().lower()
            eur_kg = float(line.precio_kg_snapshot or 0.0)
            if eur_kg <= 0 and (line.tipo_origen or "").strip().lower() == "std":
                eur_kg = float(self.std_prices.get(codigo) or 0.0)
            eur_kg_text = f"{self._fmt_number(eur_kg, 2)} €" if eur_kg and eur_kg > 0 else ""
            nota = (line.notas or "").strip()
            ingrediente = (line.nombre_mostrado or "").strip()
            ingrediente_text = f"{ingrediente} ({nota})" if nota else ingrediente
            cantidad_base = (cantidad_text or self._fmt_number(line.cantidad_base_g, 2)).strip()
            unidad_base = (unidad_text or "g").strip()
            cantidad_full = f"{cantidad_base} {unidad_base}".strip()

            values = [
                ingrediente_text,
                cantidad_full,
                f"{self._fmt_number(line.porcentaje_panadero, 2)} %",
                eur_kg_text,
                self._calc_line_cost_text(line.cantidad_base_g, eur_kg_text),
            ]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if col in {self.COL_INGREDIENTE, self.COL_CANTIDAD, self.COL_PCT, self.COL_EUR_LINEA}:
                    cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if col in {self.COL_CANTIDAD, self.COL_PCT, self.COL_EUR_KG, self.COL_EUR_LINEA}:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if col == self.COL_EUR_KG:
                    cell.setData(Qt.ItemDataRole.UserRole, float(line.cantidad_base_g or 0.0))
                self.table.setItem(row, col, cell)
        self._refresh_total_label()
        self.table.blockSignals(False)

    def _apply_saved_panel_values(self) -> None:
        self._load_process_panel_values()

    def _fmt_number(self, value: float | None, decimals: int = 2) -> str:
        text = f"{float(value or 0):,.{decimals}f}"
        return text.replace(",", "_").replace(".", ",").replace("_", ".")

    def _to_float(self, text: str) -> float:
        raw = (
            (text or "")
            .replace("€", "")
            .replace("%", "")
            .replace("g", "")
            .replace("Uds", "")
            .strip()
        )
        normalized = raw.replace(".", "").replace(",", ".")
        try:
            return float(normalized) if normalized else 0.0
        except ValueError:
            return 0.0

    def _format_field_with_suffix(self, field: QLineEdit, suffix: str) -> None:
        text = str(field.text() or "").strip()
        if not text:
            return
        value = self._to_float(text)
        normalized = self._fmt_number(value, 2).rstrip("0").rstrip(",")
        field.setText(f"{normalized} {suffix}")

    def _calc_line_cost_text(self, cantidad_g: float, eur_kg_text: str) -> str:
        eur_kg = self._to_float(eur_kg_text)
        if eur_kg <= 0:
            return ""
        line_cost = (float(cantidad_g or 0.0) / 1000.0) * eur_kg
        return f"{self._fmt_number(line_cost, 2)} €"

    def _sync_totals_columns(self, *_args) -> None:
        self.totals_table.setColumnWidth(0, self.table.verticalHeader().width())
        for col in range(5):
            self.totals_table.setColumnWidth(col + self.TOTALS_OFFSET, self.table.columnWidth(col))
        self.totals_table.viewport().update()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self._sync_totals_columns()
        QTimer.singleShot(0, self._sync_totals_columns)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._sync_totals_columns()

    def _refresh_total_label(self) -> None:
        total_value = 0.0
        total_qty_g = 0.0
        total_pct = 0.0
        for row in range(self.table.rowCount()):
            qty_item = self.table.item(row, self.COL_EUR_KG)
            if qty_item:
                total_qty_g += float(qty_item.data(Qt.ItemDataRole.UserRole) or 0.0)
            pct_item = self.table.item(row, self.COL_PCT)
            total_pct += self._to_float(pct_item.text() if pct_item else "")
            item = self.table.item(row, self.COL_EUR_LINEA)
            total_value += self._to_float(item.text() if item else "")

        values = [
            "",
            "",
            f"{self._fmt_number(total_qty_g, 2)} g",
            f"{self._fmt_number(total_pct, 2)} %",
            "",
            f"{self._fmt_number(total_value, 2)} €",
        ]
        for col, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.totals_table.setItem(0, col, item)
            lbl = QLabel(value)
            align = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter if col in {
                self.COL_CANTIDAD + self.TOTALS_OFFSET,
                self.COL_PCT + self.TOTALS_OFFSET,
                self.COL_EUR_KG + self.TOTALS_OFFSET,
                self.COL_EUR_LINEA + self.TOTALS_OFFSET,
            } else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            lbl.setAlignment(align)
            separator = "border-left: 1px solid #FFFFFF;" if col >= (self.COL_CANTIDAD + self.TOTALS_OFFSET) else "border-left: none;"
            lbl.setStyleSheet(
                "background-color: #2F80ED;"
                "color: #FFFFFF;"
                "border-radius: 0;"
                "border-top: none;"
                "border-right: none;"
                "border-bottom: none;"
                f"{separator}"
                "padding: 0 8px;"
            )
            self.totals_table.setCellWidget(0, col, lbl)
        self._recalculate_escandallo()

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != self.COL_EUR_KG:
            return
        row = item.row()
        eur_kg_text = (item.text() or "").strip()
        qty_item = self.table.item(row, self.COL_EUR_KG)
        cantidad_g = float(qty_item.data(Qt.ItemDataRole.UserRole) or 0.0) if qty_item else 0.0
        total_item = self.table.item(row, self.COL_EUR_LINEA)
        if total_item:
            total_item.setText(self._calc_line_cost_text(cantidad_g, eur_kg_text))
        self.table.blockSignals(True)
        self._refresh_total_label()
        self.table.blockSignals(False)

    def _recalculate_escandallo(self) -> None:
        total_masa = 0.0
        coste_mp = 0.0
        for row in range(self.table.rowCount()):
            eur_kg_item = self.table.item(row, self.COL_EUR_KG)
            if eur_kg_item:
                total_masa += float(eur_kg_item.data(Qt.ItemDataRole.UserRole) or 0.0)
            total_linea_item = self.table.item(row, self.COL_EUR_LINEA)
            if total_linea_item:
                coste_mp += self._to_float(total_linea_item.text() or "")

        peso_pieza_text = self.el_peso_pieza.text().strip()
        peso_pieza = self._to_float(peso_pieza_text) if peso_pieza_text else 0.0
        rendimiento = (total_masa / peso_pieza) if peso_pieza > 0 else 0.0
        unidades_totales = rendimiento

        costes_fijos = self._to_float(self.sc_costes_fijos.text())
        costes_variables = self._to_float(self.sc_costes_variables.text())
        otros_costes = self._to_float(self.sc_otros_costes.text())
        total_costes = coste_mp + costes_fijos + costes_variables + otros_costes

        coste_unitario = (total_costes / unidades_totales) if unidades_totales > 0 else 0.0
        margen_previsto = self._to_float(self.sc_margen_previsto.text())
        if 0 <= margen_previsto < 100:
            precio_recomendado = coste_unitario / (1 - (margen_previsto / 100.0))
        else:
            precio_recomendado = 0.0

        precio_venta = self._to_float(self.sc_precio_venta.text())
        igic_pct = self._to_float(self.sc_igic.text())
        calculo_igic = precio_venta * igic_pct / 100.0
        precio_neto = precio_venta + calculo_igic

        coste_mp_unitario = (coste_mp / unidades_totales) if unidades_totales > 0 else 0.0
        pct_coste_mp = (coste_mp_unitario / precio_venta * 100.0) if precio_venta > 0 else 0.0
        pct_margen_pv = ((precio_venta - coste_unitario) / precio_venta * 100.0) if precio_venta > 0 else 0.0

        self.sc_total_masa.setText(f"{self._fmt_number(total_masa, 2)} g")
        self.sc_peso_pieza.setText(self._fmt_number(peso_pieza, 2) if peso_pieza > 0 else "")
        self.sc_rendimiento.setText(f"{self._fmt_number(rendimiento, 0)} Uds")
        self.sc_coste_mp.setText(f"{self._fmt_number(coste_mp, 2)} €")
        self.sc_total_costes.setText(f"{self._fmt_number(total_costes, 2)} €")
        self.sc_unidades_totales.setText(f"{self._fmt_number(unidades_totales, 0)} Uds")
        self.sc_coste_unitario.setText(f"{self._fmt_number(coste_unitario, 2)} €")
        self.sc_precio_recomendado.setText(f"{self._fmt_number(precio_recomendado, 2)} €")
        self.sc_calc_igic.setText(f"{self._fmt_number(calculo_igic, 2)} €")
        self.sc_precio_neto.setText(f"{self._fmt_number(precio_neto, 2)} €")
        self.sc_pct_coste_mp.setText(f"{self._fmt_number(pct_coste_mp, 2)} %")
        self.sc_pct_margen_pv.setText(f"{self._fmt_number(pct_margen_pv, 2)} %")

        self.el_total_masa.setText(self._fmt_number(total_masa, 2))
        self.el_peso_pieza.setText(self._fmt_number(peso_pieza, 2) if peso_pieza > 0 else "")
        self.el_rendimiento.setText(self._fmt_number((total_masa / peso_pieza) if peso_pieza > 0 else 0.0, 0))
        self.peso_pieza_g = peso_pieza

    def _on_el_peso_pieza_changed(self) -> None:
        self._recalculate_escandallo()

    def _on_sc_peso_pieza_changed(self) -> None:
        self.el_peso_pieza.setText(self.sc_peso_pieza.text().strip())
        self._recalculate_escandallo()

    def _export_pdf_simple(self) -> None:
        self._export_pdf_layout("simple")

    def _export_pdf_extended(self) -> None:
        self._export_pdf_layout("extended")

    def _export_pdf_layout(self, layout_mode: str) -> None:
        if not self.recipe_id:
            QMessageBox.warning(self, "Receta técnica", "Guarda la receta antes de exportar.")
            return
        safe_name = self.recipe_name.replace("/", "-")
        suffix = "simple" if layout_mode == "simple" else "extendida"
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar receta técnica a PDF",
            f"{safe_name}_{suffix}.pdf",
            "PDF (*.pdf)",
        )
        if not output_path:
            return
        try:
            self.pdf_service.export_recipe_to_pdf(int(self.recipe_id), Path(output_path), layout_mode=layout_mode)
        except Exception as exc:
            QMessageBox.critical(self, "Receta técnica", f"No se pudo exportar el PDF:\n{exc}")
            return
        QMessageBox.information(self, "Receta técnica", "PDF generado correctamente.")

    def get_payload(self) -> tuple[list[RecetaLinea], dict[str, str], dict[str, str]]:
        self._persist_current_process_panel_values()
        self._persist_visible_line_edits()
        updated_lines: list[RecetaLinea] = []
        for line, _cantidad_text, _unidad_text in self.all_lines:
            clone = RecetaLinea(**line.model_dump())
            updated_lines.append(clone)

        return updated_lines, dict(self.escandallo_data), dict(self.elaboracion_data)


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

    def setModelData(self, editor, model, index) -> None:  # type: ignore[override]
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
    COL_UNIDAD = 3
    COL_PROCESO = 4
    MIN_LINE_ROWS = 10
    PROCESO_RICH_HTML_KEY = "__proceso_rich_html"
    IMAGES_GALLERY_KEY = "__images_gallery_json"

    def __init__(self) -> None:
        super().__init__()
        self.recipe_service = RecipeService()
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

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, 1)

        left_panel = QWidget()
        left_panel.setFixedWidth(332)
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("Recetas"))

        self.recipe_tabs = QTabWidget()
        self.recipe_tabs.currentChanged.connect(self._on_recipe_tab_changed)
        left_layout.addWidget(self.recipe_tabs, 1)

        ireks_tab = QWidget()
        ireks_layout = QVBoxLayout(ireks_tab)
        self.ireks_recipe_search = QLineEdit()
        self.ireks_recipe_search.setPlaceholderText("Buscar por ocurrencia, receta, producto IREKS...")
        self.ireks_recipe_search.textChanged.connect(self._reload_recipe_list)
        ireks_layout.addWidget(self.ireks_recipe_search)
        self.ireks_recipe_table = self._create_recipe_table()
        ireks_layout.addWidget(self.ireks_recipe_table, 1)
        self.recipe_tabs.addTab(ireks_tab, "IREKS")

        customer_tab = QWidget()
        customer_layout = QVBoxLayout(customer_tab)
        self.customer_filter_btn = QPushButton("Todos los clientes")
        self.customer_filter_btn.setProperty("btnRole", "secondary")
        self.customer_filter_btn.clicked.connect(self._pick_customer_filter)
        customer_layout.addWidget(self.customer_filter_btn)
        self.load_base_btn = QPushButton("Cargar receta base")
        self.load_base_btn.setProperty("btnRole", "success")
        self.load_base_btn.clicked.connect(self._load_base_recipe_template)
        customer_layout.addWidget(self.load_base_btn)
        self.customer_recipe_table = self._create_recipe_table()
        customer_layout.addWidget(self.customer_recipe_table, 1)
        self.recipe_tabs.addTab(customer_tab, "Clientes")

        splitter.addWidget(left_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(1, 1)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(0)
        splitter.setSizes([332, 930])

        actions = QHBoxLayout()
        for label, handler in [
            ("Nueva", self._new_recipe),
            ("Guardar", self._save_recipe),
            ("Guardar como version", self._save_version),
            ("Duplicar", self._duplicate_recipe),
            ("Eliminar", self._delete_recipe),
            ("Recalcular", self._recalculate),
            ("Imprimir", self._print_recipe),
            ("Exportar PDF", self._export_pdf),
            ("Exportar Excel", self._export_excel),
        ]:
            btn = QPushButton(label)
            if label == "Nueva":
                btn.setProperty("btnRole", "success")
            elif label in {"Guardar", "Recalcular"}:
                btn.setProperty("btnRole", "primary")
            elif label == "Guardar como version":
                btn.setProperty("btnRole", "warning")
            elif label == "Eliminar":
                btn.setProperty("btnRole", "danger")
            else:
                btn.setProperty("btnRole", "secondary")
            btn.clicked.connect(handler)
            actions.addWidget(btn)
        actions.addStretch()
        right_layout.addLayout(actions)

        self.header_row = QWidget()
        self.header_row.setFixedHeight(64)

        self.recipe_header_box = QGroupBox("Receta")
        self.recipe_header_box.setFixedHeight(64)
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
        self.merma_spin = self._double_spin(0, 100, 2)

        self.customer_header_box = QGroupBox("Cliente")
        self.customer_header_box.setFixedHeight(64)
        self.customer_name_value = QLabel("")
        self.customer_name_value.setParent(self.customer_header_box)
        self.customer_name_value.setFixedHeight(24)
        self.customer_name_value.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.customer_name_value.setStyleSheet("background: transparent; border: none; color: #16325C;")

        self.recipe_header_box.setParent(self.header_row)
        self.customer_header_box.setParent(self.header_row)
        right_layout.addWidget(self.header_row)
        self._layout_header_boxes_abs()
        self._layout_header_fields_abs()

        lines_group = QGroupBox("Lineas de receta")
        lines_layout = QVBoxLayout(lines_group)
        lines_layout.setSpacing(6)
        line_actions = QHBoxLayout()
        line_actions.setContentsMargins(0, 0, 0, 0)
        line_actions.setSpacing(6)
        add_line_btn = QPushButton("Añadir")
        add_line_btn.setProperty("btnRole", "success")
        del_line_btn = QPushButton("Eliminar")
        del_line_btn.setProperty("btnRole", "danger")
        scale_btn = QPushButton("Escalar")
        scale_btn.setProperty("btnRole", "primary")
        tech_recipe_btn = QPushButton("Técnica")
        tech_recipe_btn.setProperty("btnRole", "secondary")
        line_button_style = "min-height: 26px; max-height: 26px; padding: 0 8px;"
        for btn, min_width in (
            (add_line_btn, 74),
            (del_line_btn, 78),
            (scale_btn, 74),
            (tech_recipe_btn, 74),
        ):
            btn.setFixedHeight(26)
            btn.setMinimumWidth(min_width)
            btn.setStyleSheet(line_button_style)
        add_line_btn.clicked.connect(self._add_ingredient)
        del_line_btn.clicked.connect(self._remove_line)
        scale_btn.clicked.connect(self._scale_recipe)
        tech_recipe_btn.clicked.connect(self._open_recipe_technical)
        line_actions.addWidget(add_line_btn)
        line_actions.addWidget(del_line_btn)
        line_actions.addWidget(scale_btn)
        line_actions.addWidget(tech_recipe_btn)
        line_actions.addStretch()
        line_actions.addSpacing(10)
        line_actions.addWidget(QLabel("Proceso"))
        self.active_process_combo = QComboBox()
        self.active_process_combo.setEditable(True)
        self.active_process_combo.setMinimumWidth(130)
        self.active_process_combo.setMaximumWidth(170)
        self.active_process_combo.currentTextChanged.connect(self._on_active_process_changed)
        line_actions.addWidget(self.active_process_combo)
        add_process_btn = QPushButton("+")
        add_process_btn.setProperty("btnRole", "success")
        add_process_btn.setFixedHeight(26)
        add_process_btn.setMinimumWidth(34)
        add_process_btn.setStyleSheet(line_button_style)
        add_process_btn.setFont(QFont("Segoe UI", 14, QFont.Weight.DemiBold))
        add_process_btn.clicked.connect(self._add_process)
        del_process_btn = QPushButton("-")
        del_process_btn.setProperty("btnRole", "danger")
        del_process_btn.setFixedHeight(26)
        del_process_btn.setMinimumWidth(34)
        del_process_btn.setStyleSheet(line_button_style)
        del_process_btn.setFont(QFont("Segoe UI", 14, QFont.Weight.DemiBold))
        del_process_btn.clicked.connect(self._remove_process)
        line_actions.addWidget(add_process_btn)
        line_actions.addWidget(del_process_btn)
        lines_layout.addLayout(line_actions)

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
        self.lines_table.setHorizontalHeaderLabels(["Ingrediente", "", "Cantidad", "Und", "Proceso"])
        lines_header = self.lines_table.horizontalHeader()
        lines_header.setSectionResizeMode(self.COL_INGREDIENTE, QHeaderView.ResizeMode.Stretch)
        lines_header.setSectionResizeMode(self.COL_NOTA, QHeaderView.ResizeMode.Fixed)
        lines_header.setSectionResizeMode(self.COL_CANTIDAD, QHeaderView.ResizeMode.Fixed)
        lines_header.setSectionResizeMode(self.COL_UNIDAD, QHeaderView.ResizeMode.Fixed)
        lines_header.setSectionResizeMode(self.COL_PROCESO, QHeaderView.ResizeMode.Fixed)
        lines_header.setFixedHeight(26)
        self.lines_table.setColumnWidth(self.COL_NOTA, 108)
        self.lines_table.setColumnWidth(self.COL_CANTIDAD, 86)
        self.lines_table.setColumnWidth(self.COL_UNIDAD, 52)
        self.lines_table.setColumnWidth(self.COL_PROCESO, 94)
        self.lines_table.setItemDelegateForColumn(
            self.COL_NOTA,
            CompactTextDelegate(self.lines_table),
        )
        self.lines_table.setItemDelegateForColumn(
            self.COL_CANTIDAD,
            CompactQuantityDelegate(self._on_lines_changed, self.lines_table),
        )
        self.lines_table.setItemDelegateForColumn(
            self.COL_UNIDAD,
            UnitComboDelegate(self._on_lines_changed, self.lines_table),
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
        self.lines_table.setFixedHeight(lines_table_height)
        self.lines_table.itemDoubleClicked.connect(self._on_line_double_click)
        self.lines_table.itemChanged.connect(self._on_line_item_changed)
        lines_layout.addWidget(self.lines_table)
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

        nutrition_panel = QGroupBox("Valores nutricionales")
        nutrition_panel.setMinimumWidth(272)
        nutrition_panel.setMaximumWidth(272)
        nutrition_panel.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        nutrition_layout = QVBoxLayout(nutrition_panel)
        nutrition_layout.setContentsMargins(6, 6, 6, 6)
        nutrition_layout.setSpacing(4)
        self.nutrition_table = QTableWidget(8, 2)
        self.nutrition_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.nutrition_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.nutrition_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.nutrition_table.setHorizontalHeaderLabels(["Información nutricional", "Por 100 g"])
        self.nutrition_table.setStyleSheet(
            "QTableWidget { font-size: 11px; border: none; background: transparent; }"
            "QHeaderView { background: #E6EAF0; }"
            "QHeaderView::section {"
            "font-size: 10px; padding: 1px 4px; background: #E6EAF0;"
            "border: none; border-radius: 0px; margin: 0px;"
            "}"
            "QTableCornerButton::section { background: #E6EAF0; border: none; border-radius: 0px; }"
            "QTableWidget::item { padding: 1px 4px; border: none; }"
        )
        nutrition_header = self.nutrition_table.horizontalHeader()
        nutrition_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        nutrition_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        nutrition_header.setFixedHeight(22)
        self.nutrition_table.verticalHeader().setDefaultSectionSize(24)
        self.nutrition_table.verticalHeader().setMinimumSectionSize(22)
        self.nutrition_table.verticalHeader().setVisible(False)
        self.nutrition_table.setShowGrid(False)
        self.nutrition_table.setAlternatingRowColors(False)
        self.nutrition_table.setWordWrap(True)
        self.nutrition_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nutrition_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nutrition_rows = [
            ("Energía (kJ/kcal)", "1200 / 285"),
            ("Grasas", "12 g"),
            ("- de las cuales saturadas", "4 g"),
            ("Hidratos de carbono", "35 g"),
            ("- de los cuales azúcares", "8 g"),
            ("Fibra", "3 g"),
            ("Proteínas", "6 g"),
            ("Sal", "1,2 g"),
        ]
        for row, (name, per_100) in enumerate(nutrition_rows):
            name_item = QTableWidgetItem(name)
            per_100_item = QTableWidgetItem(per_100)
            per_100_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.nutrition_table.setItem(row, 0, name_item)
            self.nutrition_table.setItem(row, 1, per_100_item)
        self.nutrition_table.setColumnWidth(0, 146)
        self.nutrition_table.setColumnWidth(1, 88)
        self.nutrition_table.setRowHeight(0, 34)
        self.nutrition_table.resizeRowsToContents()
        nutrition_table_height = self.nutrition_table.horizontalHeader().height() + sum(
            self.nutrition_table.rowHeight(i) for i in range(self.nutrition_table.rowCount())
        ) + 2
        self.nutrition_table.setFixedHeight(nutrition_table_height)
        nutrition_layout.addWidget(self.nutrition_table)

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
        editor_tabs = QTabWidget()
        receta_tab = QWidget()
        receta_tab_layout = QHBoxLayout(receta_tab)
        receta_tab_layout.setContentsMargins(0, 0, 0, 0)
        receta_tab_layout.setSpacing(8)
        receta_left_panel = QWidget()
        receta_left_layout = QVBoxLayout(receta_left_panel)
        receta_left_layout.setContentsMargins(0, 0, 0, 0)
        receta_left_layout.setSpacing(8)
        receta_left_layout.addWidget(lines_group)
        receta_left_layout.addWidget(summary_group)
        receta_left_layout.addStretch(1)
        receta_tab_layout.addWidget(receta_left_panel, 1)
        receta_tab_layout.addWidget(nutrition_panel)
        editor_tabs.addTab(receta_tab, "Receta")

        proceso_tab = QWidget()
        proceso_tab_layout = QVBoxLayout(proceso_tab)
        proceso_tab_layout.setContentsMargins(0, 0, 0, 0)
        proceso_tab_layout.setSpacing(0)
        proceso_tab_layout.addWidget(process_group, 1)
        editor_tabs.addTab(proceso_tab, "Proceso")

        observaciones_tab = QWidget()
        observaciones_tab_layout = QVBoxLayout(observaciones_tab)
        observaciones_tab_layout.setContentsMargins(0, 0, 0, 0)
        observaciones_tab_layout.setSpacing(0)
        observaciones_tab_layout.addWidget(notes_group, 1)
        editor_tabs.addTab(observaciones_tab, "Observaciones")

        imagenes_tab = QWidget()
        self.images_ribbon = QWidget(imagenes_tab)
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
        editor_tabs.addTab(imagenes_tab, "Imagenes")

        body_layout = QHBoxLayout()
        body_layout.addWidget(editor_tabs, 1)
        right_layout.addLayout(body_layout, 1)

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
        self._add_recipe_image_item(file_path)
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
        pix = QPixmap(path)
        if pix.isNull():
            QMessageBox.warning(self, "Imágenes", "No se pudo cargar la imagen seleccionada.")
            return
        thumb = pix.scaled(132, 98, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        item = QListWidgetItem()
        item.setIcon(QIcon(thumb))
        item.setText(Path(path).name)
        item.setToolTip(path)
        item.setData(Qt.ItemDataRole.UserRole, path)
        item.setData(Qt.ItemDataRole.UserRole + 1, False)
        self.images_list.addItem(item)

    def _preview_recipe_image(self, item: QListWidgetItem) -> None:
        path = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
        if not path:
            return
        pix = QPixmap(path)
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
            str(Path(old_path).parent) if old_path else "",
            "Imágenes (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if not file_path:
            return
        pix = QPixmap(file_path)
        if pix.isNull():
            QMessageBox.warning(self, "Imágenes", "No se pudo cargar la imagen seleccionada.")
            return
        thumb = pix.scaled(132, 98, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        was_main = bool(item.data(Qt.ItemDataRole.UserRole + 1))
        item.setIcon(QIcon(thumb))
        item.setText(Path(file_path).name)
        item.setToolTip(file_path)
        item.setData(Qt.ItemDataRole.UserRole, file_path)
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

    def _load_images_gallery(self, payload: dict[str, str]) -> None:
        if not hasattr(self, "images_list"):
            return
        self.images_list.clear()
        rows = _load_recipe_image_gallery(str(payload.get(self.IMAGES_GALLERY_KEY, "") or ""))
        for row in rows:
            path = str(row.get("path") or "").strip()
            self._add_recipe_image_item(path)
            if self.images_list.count() > 0:
                item = self.images_list.item(self.images_list.count() - 1)
                is_main = bool(row.get("is_main", False))
                item.setData(Qt.ItemDataRole.UserRole + 1, is_main)
                if is_main:
                    item.setBackground(QBrush(QColor("#D6F5DD")))

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

    def _load_customers(self) -> None:
        customers = self.recipe_service.list_customers()
        self.cliente_combo.clear()
        for customer in customers:
            self.cliente_combo.addItem(f"{customer.cliente_nombre_comercial}", customer.cliente_id)
        self._update_inline_customer_name()
        self._reload_customer_filter(customers)

    def _reload_customer_filter(self, customers: list[Any] | None = None) -> None:
        if not hasattr(self, "customer_filter_btn"):
            return
        if customers is None:
            customers = self.recipe_service.list_customers()
        self._customer_filter_items: list[tuple[str, str]] = [("", "Todos los clientes")]
        for customer in customers:
            label = customer.cliente_nombre_comercial or customer.cliente_nombre_fiscal or customer.cliente_id
            self._customer_filter_items.append((str(customer.cliente_id), str(label)))
        valid_ids = {item[0] for item in self._customer_filter_items}
        if self.customer_filter_selected_id not in valid_ids:
            self.customer_filter_selected_id = ""
        self._refresh_customer_filter_button()
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
        self._flush_autosave()
        self.current_recipe_is_ireks = self.recipe_tabs.currentIndex() == 0
        self._new_recipe()
        self._reload_recipe_list()
        self._update_inline_customer_name()

    def _available_process_names(self) -> list[str]:
        return _unique_process_names(self.recipe_process_names)

    def _current_active_process(self) -> str:
        return _normalize_process_name(self.active_process_combo.currentText() if hasattr(self, "active_process_combo") else "")

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
        self._apply_process_filter()

    def _on_active_process_changed(self) -> None:
        self._apply_process_filter()

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

    def _remove_process(self) -> None:
        target = self._current_active_process()
        if target == "Masa final":
            QMessageBox.information(self, "Recetas", "El proceso 'Masa final' no se puede eliminar.")
            return
        if target not in self.recipe_process_names:
            return
        replacement = "Masa final"
        alternatives = [x for x in self.recipe_process_names if x != target]
        if alternatives:
            replacement, ok = QInputDialog.getItem(
                self,
                "Eliminar proceso",
                f"Reemplazar '{target}' por:",
                alternatives,
                0,
                False,
            )
            if not ok:
                return
            replacement = _normalize_process_name(replacement)
        self.recipe_process_names = [x for x in self.recipe_process_names if x != target]
        for row in range(self.lines_table.rowCount()):
            if self._cell_text(row, self.COL_PROCESO) == target:
                cell = self.lines_table.item(row, self.COL_PROCESO)
                if cell is not None:
                    cell.setText(replacement)
        self._refresh_process_controls(self.recipe_process_names, preserve_active=False)
        self._on_lines_changed()

    def _new_recipe(self) -> None:
        self._autosave_timer.stop()
        self._is_loading_recipe = True
        try:
            self.current_recipe_id = None
            self.current_base_recipe_id = None
            self.current_recipe_is_ireks = self.recipe_tabs.currentIndex() == 0 if hasattr(self, "recipe_tabs") else False
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
        self._flush_autosave()
        table = self.sender() if isinstance(self.sender(), QTableWidget) else self._active_recipe_table()
        if not isinstance(table, QTableWidget):
            return
        item = table.item(row, 0)
        if not item:
            return
        recipe_id = int(item.data(Qt.ItemDataRole.UserRole))
        self._load_recipe(recipe_id)

    def _load_recipe(self, recipe_id: int) -> None:
        aggregate = self.recipe_service.get_recipe(recipe_id, sync_categories=True)
        if not aggregate:
            return
        self._is_loading_recipe = True
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
            self.peso_spin.setValue(receta.peso_pieza_g)
            self.piezas_spin.setValue(receta.numero_piezas)
            self.merma_spin.setValue(receta.merma_pct)
            self.observaciones_input.setPlainText(receta.observaciones)
            self.proceso_input.setPlainText(receta.proceso)
            self.recipe_escandallo_data = _json_to_string_dict(receta.escandallo_detalle_json)
            self.recipe_elaboracion_data = _json_to_string_dict(receta.parametros_elaboracion_json)
            self._load_images_gallery(self.recipe_elaboracion_data)
            self._proceso_rich_html = str(self.recipe_elaboracion_data.get(self.PROCESO_RICH_HTML_KEY, "") or "").strip()
            line_processes = [_normalize_process_name(getattr(line, "proceso_nombre", "") or "Masa final") for line in aggregate.lineas]
            self._refresh_process_controls(line_processes or ["Masa final"], preserve_active=False)
            self._render_lines(aggregate.lineas)
            self._update_summary(receta, aggregate.lineas)
            self._set_issues_text("")
            self._update_inline_customer_name()
        finally:
            self._is_loading_recipe = False

    def _set_combo_by_data(self, combo: QComboBox, value: str) -> None:
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        self._update_inline_customer_name()

    def _update_inline_customer_name(self) -> None:
        if not hasattr(self, "customer_header_box") or not hasattr(self, "recipe_tabs"):
            return
        is_customer_tab = self.recipe_tabs.currentIndex() == 1
        self.customer_header_box.setVisible(is_customer_tab)
        if not is_customer_tab:
            self.customer_name_value.clear()
            return
        customer_name = (self.cliente_combo.currentText() or "").strip()
        self.customer_name_value.setText(customer_name)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._layout_header_boxes_abs()
        self._layout_header_fields_abs()

    def _layout_header_boxes_abs(self) -> None:
        if not hasattr(self, "header_row") or not hasattr(self, "recipe_header_box") or not hasattr(self, "customer_header_box"):
            return
        self.recipe_header_box.setGeometry(0, 0, 460, 64)
        self.customer_header_box.setGeometry(468, 0, 460, 64)

    def _layout_header_fields_abs(self) -> None:
        if not hasattr(self, "recipe_header_box") or not hasattr(self, "customer_header_box"):
            return
        self.nombre_input.setGeometry(10, 25, 440, 24)
        self.customer_name_value.setGeometry(10, 25, 440, 24)

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

    def _insert_process_line(self, source_name: str, qty_g: float) -> None:
        target_process = self._current_active_process()
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
        self._on_lines_changed()
        self._apply_process_filter()

    def _remove_line(self) -> None:
        selected = self.lines_table.selectionModel().selectedRows()
        if not selected:
            return
        self.lines_table.removeRow(selected[0].row())
        self._ensure_min_line_rows()
        self._on_lines_changed()

    def _open_recipe_technical(self) -> None:
        rows_data: list[tuple[RecetaLinea, str, str]] = []
        source_rows: list[int] = []
        for row in range(self.lines_table.rowCount()):
            line = self._line_from_row(row)
            if not (line.nombre_mostrado or line.notas or line.cantidad_base_g):
                continue
            cantidad_text = self._cell_text(row, self.COL_CANTIDAD)
            unidad_text = self._cell_text(row, self.COL_UNIDAD) or "g"
            rows_data.append((line, cantidad_text, unidad_text))
            source_rows.append(row)

        if not rows_data:
            QMessageBox.information(self, "Receta técnica", "No hay Líneas para mostrar.")
            return

        recipe = self._build_recipe_model()
        line_models = [row[0] for row in rows_data]
        result = self.recipe_service.calculate(recipe, line_models, sync_categories=True)

        final_rows = [(result.lineas[idx], rows_data[idx][1], rows_data[idx][2]) for idx in range(len(rows_data))]
        dialog = RecipeTechnicalDialog(
            self.nombre_input.text().strip() or "Sin nombre",
            self.current_recipe_id,
            final_rows,
            result.receta.peso_pieza_g,
            self.recipe_escandallo_data,
            self.recipe_elaboracion_data,
            initial_process=self._current_active_process(),
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        updated_lines, escandallo_payload, elaboracion_payload = dialog.get_payload()
        self.recipe_escandallo_data = escandallo_payload
        self.recipe_elaboracion_data = elaboracion_payload

        for idx, row in enumerate(source_rows):
            if idx >= len(updated_lines):
                break
            line = self._line_from_row(row)
            line.precio_kg_snapshot = float(updated_lines[idx].precio_kg_snapshot or 0.0)
            ingredient_item = self.lines_table.item(row, self.COL_INGREDIENTE)
            if ingredient_item:
                ingredient_item.setData(Qt.ItemDataRole.UserRole, line.model_dump())

        # Persist immediately after closing technical sheet so values survive app close/reopen.
        self._autosave_timer.stop()
        self._auto_recalculate_summary()
        self._perform_autosave()

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
        dialog = IngredientSearchDialog(self.recipe_service, parent=self)
        if not dialog.exec() or not dialog.selected:
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
        self._on_lines_changed()

    def _set_line_row(self, row: int, linea: RecetaLinea) -> None:
        has_ingredient = bool((linea.nombre_mostrado or "").strip())
        has_content = has_ingredient or bool((linea.notas or "").strip()) or float(linea.cantidad_base_g or 0.0) > 0
        prev_unit = self._cell_text(row, self.COL_UNIDAD).lower() if row < self.lines_table.rowCount() else ""
        unit_text = prev_unit if prev_unit in {"g", "kg", "l", "ml"} else "g"
        process_text = _normalize_process_name(getattr(linea, "proceso_nombre", "") or self._current_active_process())
        values = [
            linea.nombre_mostrado or "",
            linea.notas or "",
            self._format_number(linea.cantidad_base_g) if has_content else "",
            unit_text if has_content else "",
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
            if col == self.COL_UNIDAD:
                cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if not has_content:
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
            qty_origin = float(getattr(linea, "cantidad_origen_g", 0.0) or 0.0)
            if qty_origin <= 0:
                qty_origin = float(linea.cantidad_base_g or 0.0)
            linea.cantidad_origen_g = qty_origin
            linea.cantidad_base_g = qty_origin
        else:
            linea.proceso_origen_nombre = ""
            linea.cantidad_origen_g = 0.0
        return linea

    def _cell_text(self, row: int, col: int) -> str:
        item = self.lines_table.item(row, col)
        return item.text().strip() if item else ""

    def _cell_float(self, row: int, col: int) -> float:
        text = self._cell_text(row, col).replace(".", "").replace(",", ".")
        try:
            return float(text) if text else 0.0
        except ValueError:
            return 0.0

    def _format_number(self, value: float, decimals: int = 2) -> str:
        text = f"{float(value or 0):,.{decimals}f}"
        return text.replace(",", "_").replace(".", ",").replace("_", ".")

    def _unit_for_row(self, row: int) -> str:
        text = self._cell_text(row, self.COL_UNIDAD).lower()
        return text if text in {"g", "kg", "l", "ml"} else "g"

    def _quantity_as_grams(self, row: int) -> float:
        quantity = self._cell_float(row, self.COL_CANTIDAD)
        unit = self._unit_for_row(row)
        if unit in {"kg", "l"}:
            return quantity * 1000
        return quantity

    def _build_recipe_model(self) -> Receta:
        nombre = self.nombre_input.text().strip()
        codigo_receta = self.codigo_input.text().strip() or nombre
        elaboracion_payload = dict(self.recipe_elaboracion_data)
        if self._proceso_rich_html.strip():
            elaboracion_payload[self.PROCESO_RICH_HTML_KEY] = self._proceso_rich_html.strip()
        else:
            elaboracion_payload.pop(self.PROCESO_RICH_HTML_KEY, None)
        images_gallery = self._collect_images_gallery()
        if images_gallery:
            elaboracion_payload[self.IMAGES_GALLERY_KEY] = json.dumps(images_gallery, ensure_ascii=False)
        else:
            elaboracion_payload.pop(self.IMAGES_GALLERY_KEY, None)
        return Receta(
            id=self.current_recipe_id,
            cliente_id=self._selected_cliente_id(),
            nombre=nombre,
            codigo_receta=codigo_receta,
            version=self.version_input.text().strip() or "1.0",
            es_base=self.current_recipe_is_ireks,
            receta_base_id=self.current_base_recipe_id,
            masa_final_deseada_g=self.masa_spin.value(),
            peso_pieza_g=self.peso_spin.value(),
            numero_piezas=self.piezas_spin.value(),
            merma_pct=self.merma_spin.value(),
            observaciones=self.observaciones_input.toPlainText().strip(),
            proceso=self.proceso_input.toPlainText().strip(),
            escandallo_detalle_json=json.dumps(self.recipe_escandallo_data, ensure_ascii=False),
            parametros_elaboracion_json=json.dumps(elaboracion_payload, ensure_ascii=False),
            estado=self.estado_input.text().strip() or "borrador",
        )

    def _build_lines(self) -> list[RecetaLinea]:
        lines: list[RecetaLinea] = []
        for row in range(self.lines_table.rowCount()):
            line = self._line_from_row(row)
            if line.nombre_mostrado or line.notas or line.cantidad_base_g:
                line.proceso_nombre = _normalize_process_name(line.proceso_nombre)
                lines.append(line)
        line_processes = [line.proceso_nombre for line in lines]
        self._refresh_process_controls(line_processes or self.recipe_process_names)
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
        self._schedule_autosave()

    def _on_line_item_changed(self, item: QTableWidgetItem) -> None:
        if self._is_loading_recipe:
            return
        if item.column() not in {self.COL_INGREDIENTE, self.COL_NOTA, self.COL_CANTIDAD, self.COL_UNIDAD, self.COL_PROCESO}:
            return
        self._on_lines_changed()

    def _auto_recalculate_summary(self) -> None:
        receta = self._build_recipe_model()
        lineas = self._build_lines()
        result = self.recipe_service.calculate(receta, lineas, sync_categories=True)
        self._update_summary(result.receta, result.lineas)
        self.current_issues = [f"[{i.level.upper()}] {i.message}" for i in result.issues]

    def _schedule_autosave(self) -> None:
        if self._is_loading_recipe:
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
        if self._is_loading_recipe:
            return
        self._autosave_timer.stop()
        self._perform_autosave()

    def _perform_autosave(self) -> None:
        if self._is_loading_recipe:
            return
        try:
            receta = self._build_recipe_model()
            if not receta.nombre:
                return
            if self.recipe_tabs.currentIndex() == 1 and not receta.cliente_id:
                return
            lineas = self._build_lines()
            result = self.recipe_service.calculate(receta, lineas, sync_categories=True)
            saved = self.recipe_service.save_recipe(result.receta, result.lineas)
            self.current_recipe_id = saved.receta.id
            self._reload_recipe_list()
            self._select_recipe_in_active_table(self.current_recipe_id)
        except Exception as exc:
            print(f"[AUTOSAVE] Error guardando receta: {exc}")
            traceback.print_exc()

    def _render_lines(self, lineas: list[RecetaLinea]) -> None:
        line_processes = [_normalize_process_name(getattr(linea, "proceso_nombre", "") or "Masa final") for linea in lineas]
        self._refresh_process_controls(line_processes or self.recipe_process_names)
        self.lines_table.setRowCount(0)
        for idx, linea in enumerate(lineas):
            self.lines_table.insertRow(idx)
            self._set_line_row(idx, linea)
        self._ensure_min_line_rows()
        self._apply_process_filter()

    def _ensure_min_line_rows(self) -> None:
        while self.lines_table.rowCount() < self.MIN_LINE_ROWS:
            row = self.lines_table.rowCount()
            self.lines_table.insertRow(row)
            self._set_line_row(row, RecetaLinea(receta_id=0, orden=row + 1))

    def _update_summary(self, receta: Receta, lineas: list[RecetaLinea] | None = None) -> None:
        if lineas:
            process_names = [_normalize_process_name(getattr(linea, "proceso_nombre", "")) for linea in lineas]
            principal = "Masa final" if "Masa final" in process_names else (process_names[0] if process_names else "Masa final")
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
        for line in lineas:
            if str(getattr(line, "tipo_linea", "ingrediente") or "ingrediente").strip().lower() != "ingrediente":
                continue
            cantidad = float(getattr(line, "cantidad_base_g", 0.0) or 0.0)
            if cantidad <= 0:
                continue
            code = str(getattr(line, "codigo_ingrediente", "") or "").strip()
            if not code:
                continue
            valid_lines.append(line)
            source = str(getattr(line, "tipo_origen", "") or "").strip().lower()
            if source == "ireks":
                ireks_codes.add(code)
            elif source == "std":
                std_codes.add(code)
            else:
                unknown_codes.add(code)

        if not valid_lines:
            self._render_nutrition_table_values(nutrientes)
            return

        ireks_by_code, std_by_code, nutrition_by_articulo = self.recipe_service.nutrition_lookup(
            ireks_codes,
            std_codes,
            unknown_codes,
        )

        for line in valid_lines:
            source = str(getattr(line, "tipo_origen", "") or "").strip().lower()
            code = str(getattr(line, "codigo_ingrediente", "") or "").strip()
            aid = ""
            if source == "ireks":
                aid = ireks_by_code.get(code, "")
            elif source == "std":
                aid = std_by_code.get(code, "")
            else:
                aid = ireks_by_code.get(code, "") or std_by_code.get(code, "")
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

        rendered = [
            f"{self._format_number(energia_kj)} kJ\n{self._format_number(energia_kcal)} kcal",
            f"{self._format_number(grasas)} g",
            f"{self._format_number(saturadas)} g",
            f"{self._format_number(hidratos)} g",
            f"{self._format_number(azucares)} g",
            f"{self._format_number(fibra)} g",
            f"{self._format_number(proteinas)} g",
            f"{self._format_number(sal)} g",
        ]
        for row_idx, text in enumerate(rendered):
            item = self.nutrition_table.item(row_idx, 1)
            if item is None:
                item = QTableWidgetItem()
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.nutrition_table.setItem(row_idx, 1, item)
            item.setText(text)
        self.nutrition_table.resizeRowsToContents()

    def _set_issues_text(self, text: str) -> None:
        self.current_issues = text.splitlines() if text else []

    def _validate_recipe(self, receta: Receta) -> bool:
        if not receta.nombre:
            QMessageBox.warning(self, "Validacion", "El nombre de receta es obligatorio.")
            return False
        return True

    def _save_recipe(self) -> None:
        self._autosave_timer.stop()
        if self.current_recipe_id is None:
            self.current_recipe_is_ireks = self.recipe_tabs.currentIndex() == 0
        if self.recipe_tabs.currentIndex() == 1 and not self._selected_cliente_id():
            QMessageBox.warning(self, "Recetas", "Selecciona un cliente para guardar una receta de cliente.")
            return
        receta = self._build_recipe_model()
        if not self._validate_recipe(receta):
            return
        lineas = self._build_lines()
        result = self.recipe_service.calculate(receta, lineas, sync_categories=True)
        self._render_lines(result.lineas)
        self._update_summary(result.receta, result.lineas)
        self.current_issues = [f"[{i.level.upper()}] {i.message}" for i in result.issues]
        self._set_issues_text("\n".join(self.current_issues))
        saved = self.recipe_service.save_recipe(result.receta, result.lineas)
        self.current_recipe_id = saved.receta.id
        self._reload_recipe_list()
        QMessageBox.information(self, "Recetas", "Receta guardada.")

    def _save_version(self) -> None:
        if not self.current_recipe_id:
            QMessageBox.warning(self, "Recetas", "Guarda la receta antes de crear una version.")
            return
        comentario, ok = QInputDialog.getText(self, "Guardar version", "Comentario:")
        if not ok:
            return
        receta = self._build_recipe_model()
        lineas = self._build_lines()
        self.recipe_service.save_version(receta, lineas, comentario.strip())
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

        selector = QMessageBox(self)
        selector.setIcon(QMessageBox.Icon.Question)
        selector.setWindowTitle("Exportar receta a PDF")
        selector.setText("Selecciona el tipo de documento:")
        btn_simple = selector.addButton("Simple", QMessageBox.ButtonRole.AcceptRole)
        btn_ext = selector.addButton("Extendido", QMessageBox.ButtonRole.AcceptRole)
        btn_cancel = selector.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        selector.setDefaultButton(btn_ext)
        selector.exec()

        clicked = selector.clickedButton()
        if clicked == btn_cancel or clicked is None:
            return
        layout_mode = "simple" if clicked == btn_simple else "extended"

        default_name = (self.nombre_input.text().strip() or f"receta_{self.current_recipe_id}").replace("/", "-")
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar receta a PDF",
            f"{default_name}.pdf",
            "PDF (*.pdf)",
        )
        if not output_path:
            return

        try:
            self.pdf_service.export_recipe_to_pdf(self.current_recipe_id, Path(output_path), layout_mode=layout_mode)
        except Exception as exc:
            QMessageBox.critical(self, "Recetas", f"No se pudo exportar el PDF:\n{exc}")
            return
        QMessageBox.information(self, "Recetas", "PDF generado correctamente.")

    def _export_excel(self) -> None:
        QMessageBox.information(self, "Recetas", "Exportacion Excel se implementa en Fase 3.")

    def _refresh_customer_filter_button(self) -> None:
        if not hasattr(self, "customer_filter_btn"):
            return
        label = "Todos los clientes"
        for customer_id, customer_label in getattr(self, "_customer_filter_items", []):
            if customer_id == self.customer_filter_selected_id:
                label = customer_label
                break
        self.customer_filter_btn.setText(label)

    def _pick_customer_filter(self) -> None:
        dialog = CustomerSearchDialog(self.recipe_service, self.customer_filter_selected_id, self)
        if not dialog.exec() or dialog.selected_customer_id is None:
            return
        self.customer_filter_selected_id = dialog.selected_customer_id
        self._refresh_customer_filter_button()
        if self.customer_filter_selected_id:
            self._set_combo_by_data(self.cliente_combo, self.customer_filter_selected_id)
        self._update_inline_customer_name()
        self._reload_recipe_list()

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




