from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlmodel import Session

from app.core.database import engine
from app.models import Receta, RecetaLinea
from app.viewmodels import IngredientChoice, RecipeViewModel


class IngredientSearchDialog(QDialog):
    def __init__(self, vm: RecipeViewModel, parent=None) -> None:
        super().__init__(parent)
        self.vm = vm
        self.selected: IngredientChoice | None = None
        self.setWindowTitle("Buscar ingrediente")
        self.resize(900, 450)
        self._build_ui()
        self._search()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por codigo, nombre, familia...")
        btn = QPushButton("Buscar")
        btn.clicked.connect(self._search)
        self.search_input.returnPressed.connect(self._search)
        top.addWidget(self.search_input, 1)
        top.addWidget(btn)
        layout.addLayout(top)

        self.table = QTableWidget(0, 7)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setHorizontalHeaderLabels(
            ["Tipo", "ID", "Codigo", "Nombre", "Familia", "Subfamilia", "Precio/kg"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.doubleClicked.connect(self._accept_selected)
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        actions.addStretch()
        use_btn = QPushButton("Usar seleccionado")
        cancel_btn = QPushButton("Cancelar")
        use_btn.clicked.connect(self._accept_selected)
        cancel_btn.clicked.connect(self.reject)
        actions.addWidget(use_btn)
        actions.addWidget(cancel_btn)
        layout.addLayout(actions)

    def _search(self) -> None:
        term = self.search_input.text().strip()
        with Session(engine) as session:
            items = self.vm.search_ingredients(session, term)
        self.table.setRowCount(len(items))
        for row, item in enumerate(items):
            values = [
                item.tipo_origen.upper(),
                str(item.ingrediente_id),
                item.codigo,
                item.nombre,
                item.familia,
                item.subfamilia,
                f"{item.precio_kg:.4f}".rstrip("0").rstrip("."),
            ]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if col == 0:
                    cell.setData(Qt.UserRole, item)
                self.table.setItem(row, col, cell)

    def _accept_selected(self) -> None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            QMessageBox.warning(self, "Atencion", "Selecciona un ingrediente.")
            return
        item = self.table.item(selected[0].row(), 0).data(Qt.UserRole)
        self.selected = item
        self.accept()


class RecipesPage(QWidget):
    COL_ORDEN = 0
    COL_TIPO = 1
    COL_CODIGO = 2
    COL_INGREDIENTE = 3
    COL_FAMILIA = 4
    COL_HARINA = 5
    COL_LIQUIDO = 6
    COL_CANT_BASE = 7
    COL_PANADERO = 8
    COL_CANT_CALC = 9
    COL_PRECIO = 10
    COL_COSTE = 11
    COL_NOTAS = 12

    def __init__(self) -> None:
        super().__init__()
        self.vm = RecipeViewModel()
        self.current_recipe_id: int | None = None
        self.current_issues: list[str] = []
        self._build_ui()
        self._load_customers()
        self._reload_recipe_list()
        self._new_recipe()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("Recetas"))
        self.recipe_search = QLineEdit()
        self.recipe_search.setPlaceholderText("Buscar receta...")
        self.recipe_search.textChanged.connect(self._reload_recipe_list)
        left_layout.addWidget(self.recipe_search)
        self.recipe_table = QTableWidget(0, 4)
        self.recipe_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.recipe_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.recipe_table.setHorizontalHeaderLabels(["ID", "Codigo", "Nombre", "Cliente"])
        self.recipe_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.recipe_table.cellClicked.connect(self._on_recipe_selected)
        left_layout.addWidget(self.recipe_table, 1)
        splitter.addWidget(left_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(1, 1)

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
            btn.clicked.connect(handler)
            actions.addWidget(btn)
        actions.addStretch()
        right_layout.addLayout(actions)

        header_box = QGroupBox("Cabecera")
        form = QFormLayout(header_box)
        self.cliente_combo = QComboBox()
        self.nombre_input = QLineEdit()
        self.codigo_input = QLineEdit()
        self.version_input = QLineEdit("1.0")
        self.estado_input = QLineEdit("borrador")
        self.masa_spin = self._double_spin(0, 1_000_000, 2)
        self.peso_spin = self._double_spin(0, 100_000, 2)
        self.piezas_spin = QSpinBox()
        self.piezas_spin.setRange(0, 1_000_000)
        self.piezas_spin.setValue(1)
        self.merma_spin = self._double_spin(0, 100, 2)

        form.addRow("Cliente", self.cliente_combo)
        form.addRow("Nombre", self.nombre_input)
        form.addRow("Codigo receta", self.codigo_input)
        form.addRow("Version", self.version_input)
        form.addRow("Estado", self.estado_input)
        form.addRow("Masa final deseada (g)", self.masa_spin)
        form.addRow("Peso pieza (g)", self.peso_spin)
        form.addRow("Numero piezas", self.piezas_spin)
        form.addRow("Merma (%)", self.merma_spin)
        right_layout.addWidget(header_box)

        lines_group = QGroupBox("Lineas de receta")
        lines_layout = QVBoxLayout(lines_group)
        line_actions = QHBoxLayout()
        add_line_btn = QPushButton("Agregar linea")
        del_line_btn = QPushButton("Eliminar linea")
        pick_ingredient_btn = QPushButton("Buscar ingrediente")
        add_line_btn.clicked.connect(self._add_line)
        del_line_btn.clicked.connect(self._remove_line)
        pick_ingredient_btn.clicked.connect(self._pick_ingredient_for_selected)
        line_actions.addWidget(add_line_btn)
        line_actions.addWidget(del_line_btn)
        line_actions.addWidget(pick_ingredient_btn)
        line_actions.addStretch()
        lines_layout.addLayout(line_actions)

        self.lines_table = QTableWidget(0, 13)
        self.lines_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.lines_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.lines_table.setHorizontalHeaderLabels(
            [
                "Orden",
                "Tipo",
                "Codigo",
                "Ingrediente",
                "Familia",
                "Harina",
                "Liquido",
                "Cantidad base g",
                "% panadero",
                "Cantidad calculada g",
                "Precio €/kg",
                "Coste",
                "Notas",
            ]
        )
        self.lines_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.lines_table.itemDoubleClicked.connect(self._on_line_double_click)
        lines_layout.addWidget(self.lines_table)
        right_layout.addWidget(lines_group, 1)

        summary_group = QGroupBox("Resumen tecnico y economico")
        summary_layout = QGridLayout(summary_group)
        self.total_harinas_lbl = QLabel("0.00 g")
        self.total_liquidos_lbl = QLabel("0.00 g")
        self.hidratacion_lbl = QLabel("0.00 %")
        self.total_panadero_lbl = QLabel("0.00 %")
        self.masa_total_lbl = QLabel("0.00 g")
        self.coste_total_lbl = QLabel("0.00")
        self.coste_kg_lbl = QLabel("0.00")
        self.coste_pieza_lbl = QLabel("0.00")

        fields = [
            ("Total harinas", self.total_harinas_lbl),
            ("Total liquidos", self.total_liquidos_lbl),
            ("Hidratacion", self.hidratacion_lbl),
            ("Total % panadero", self.total_panadero_lbl),
            ("Masa total", self.masa_total_lbl),
            ("Coste total", self.coste_total_lbl),
            ("Coste/kg", self.coste_kg_lbl),
            ("Coste/pieza", self.coste_pieza_lbl),
        ]
        for i, (label, value) in enumerate(fields):
            summary_layout.addWidget(QLabel(label), i // 2, (i % 2) * 2)
            summary_layout.addWidget(value, i // 2, (i % 2) * 2 + 1)
        right_layout.addWidget(summary_group)

        notes_group = QGroupBox("Observaciones y proceso")
        notes_layout = QHBoxLayout(notes_group)
        self.observaciones_input = QPlainTextEdit()
        self.observaciones_input.setPlaceholderText("Observaciones...")
        self.proceso_input = QPlainTextEdit()
        self.proceso_input.setPlaceholderText("Proceso...")
        notes_layout.addWidget(self.observaciones_input, 1)
        notes_layout.addWidget(self.proceso_input, 1)
        right_layout.addWidget(notes_group)

        self.issues_label = QLabel("")
        self.issues_label.setWordWrap(True)
        right_layout.addWidget(self.issues_label)

    def _double_spin(self, min_value: float, max_value: float, decimals: int) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(min_value, max_value)
        spin.setDecimals(decimals)
        return spin

    def _load_customers(self) -> None:
        with Session(engine) as session:
            customers = self.vm.list_customers(session)
        self.cliente_combo.clear()
        for customer in customers:
            self.cliente_combo.addItem(f"{customer.codigo} - {customer.nombre_comercial}", customer.id)

    def _reload_recipe_list(self) -> None:
        term = self.recipe_search.text().strip()
        with Session(engine) as session:
            recipes = self.vm.list_recipes(session, term=term)
            customers = {c.id: c for c in self.vm.list_customers(session)}
        self.recipe_table.setRowCount(len(recipes))
        for row, recipe in enumerate(recipes):
            values = [
                str(recipe.id or ""),
                recipe.codigo_receta,
                recipe.nombre,
                customers.get(recipe.cliente_id).nombre_comercial if customers.get(recipe.cliente_id) else "",
            ]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if col == 0:
                    cell.setData(Qt.UserRole, recipe.id)
                self.recipe_table.setItem(row, col, cell)

    def _new_recipe(self) -> None:
        self.current_recipe_id = None
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
        self.lines_table.setRowCount(0)
        self._update_summary(Receta(cliente_id=self._selected_cliente_id(), nombre="", codigo_receta=""))
        self.issues_label.setText("")

    def _selected_cliente_id(self) -> int:
        value = self.cliente_combo.currentData()
        return int(value) if value is not None else 0

    def _on_recipe_selected(self, row: int, _col: int) -> None:
        item = self.recipe_table.item(row, 0)
        recipe_id = int(item.data(Qt.UserRole))
        self._load_recipe(recipe_id)

    def _load_recipe(self, recipe_id: int) -> None:
        with Session(engine) as session:
            aggregate = self.vm.get_recipe(session, recipe_id)
        if not aggregate:
            return
        receta = aggregate.receta
        self.current_recipe_id = receta.id
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
        self._render_lines(aggregate.lineas)
        self._update_summary(receta)
        self.issues_label.setText("")

    def _set_combo_by_data(self, combo: QComboBox, value: int) -> None:
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _add_line(self) -> None:
        row = self.lines_table.rowCount()
        self.lines_table.insertRow(row)
        self._set_line_row(row, RecetaLinea(receta_id=0, orden=row + 1))

    def _remove_line(self) -> None:
        selected = self.lines_table.selectionModel().selectedRows()
        if not selected:
            return
        self.lines_table.removeRow(selected[0].row())
        self._renumber_lines()

    def _renumber_lines(self) -> None:
        for row in range(self.lines_table.rowCount()):
            self.lines_table.setItem(row, self.COL_ORDEN, QTableWidgetItem(str(row + 1)))

    def _on_line_double_click(self, item: QTableWidgetItem) -> None:
        if item.column() == self.COL_INGREDIENTE:
            self._pick_ingredient_for_selected()

    def _pick_ingredient_for_selected(self) -> None:
        selected = self.lines_table.selectionModel().selectedRows()
        if not selected:
            QMessageBox.warning(self, "Atencion", "Selecciona una linea.")
            return
        row = selected[0].row()
        dialog = IngredientSearchDialog(self.vm, self)
        if not dialog.exec() or not dialog.selected:
            return
        ingredient = dialog.selected
        linea = self._line_from_row(row)
        linea.tipo_origen = ingredient.tipo_origen
        linea.ingrediente_id = ingredient.ingrediente_id
        linea.codigo_ingrediente = ingredient.codigo
        linea.nombre_mostrado = ingredient.nombre
        linea.familia = ingredient.familia
        linea.subfamilia = ingredient.subfamilia
        linea.es_harina = ingredient.es_harina
        linea.es_liquido = ingredient.es_liquido
        linea.precio_kg_snapshot = ingredient.precio_kg
        self._set_line_row(row, linea)

    def _set_line_row(self, row: int, linea: RecetaLinea) -> None:
        values = [
            str(row + 1),
            linea.tipo_origen.upper() if linea.tipo_origen else "",
            linea.codigo_ingrediente or "",
            linea.nombre_mostrado or "",
            linea.familia or "",
            "Si" if linea.es_harina else "No",
            "Si" if linea.es_liquido else "No",
            f"{linea.cantidad_base_g:.2f}",
            f"{linea.porcentaje_panadero:.2f}",
            f"{linea.cantidad_calculada_g:.2f}",
            f"{linea.precio_kg_snapshot:.4f}",
            f"{linea.coste_linea:.4f}",
            linea.notas or "",
        ]
        for col, value in enumerate(values):
            self.lines_table.setItem(row, col, QTableWidgetItem(value))
        self.lines_table.item(row, self.COL_INGREDIENTE).setData(Qt.UserRole, linea)

    def _line_from_row(self, row: int) -> RecetaLinea:
        item = self.lines_table.item(row, self.COL_INGREDIENTE)
        existing = item.data(Qt.UserRole) if item else None
        if isinstance(existing, RecetaLinea):
            linea = existing
        else:
            linea = RecetaLinea(receta_id=0, orden=row + 1)
        linea.orden = row + 1
        linea.tipo_origen = (self._cell_text(row, self.COL_TIPO) or linea.tipo_origen or "").lower() or "std"
        linea.codigo_ingrediente = self._cell_text(row, self.COL_CODIGO)
        linea.nombre_mostrado = self._cell_text(row, self.COL_INGREDIENTE)
        linea.familia = self._cell_text(row, self.COL_FAMILIA)
        linea.es_harina = self._cell_text(row, self.COL_HARINA).strip().lower() in {"si", "true", "1", "x"}
        linea.es_liquido = self._cell_text(row, self.COL_LIQUIDO).strip().lower() in {"si", "true", "1", "x"}
        linea.cantidad_base_g = self._cell_float(row, self.COL_CANT_BASE)
        linea.porcentaje_panadero = self._cell_float(row, self.COL_PANADERO)
        linea.cantidad_calculada_g = self._cell_float(row, self.COL_CANT_CALC)
        linea.precio_kg_snapshot = self._cell_float(row, self.COL_PRECIO)
        linea.coste_linea = self._cell_float(row, self.COL_COSTE)
        linea.notas = self._cell_text(row, self.COL_NOTAS)
        return linea

    def _cell_text(self, row: int, col: int) -> str:
        item = self.lines_table.item(row, col)
        return item.text().strip() if item else ""

    def _cell_float(self, row: int, col: int) -> float:
        text = self._cell_text(row, col).replace(",", ".")
        try:
            return float(text) if text else 0.0
        except ValueError:
            return 0.0

    def _build_recipe_model(self) -> Receta:
        return Receta(
            id=self.current_recipe_id,
            cliente_id=self._selected_cliente_id(),
            nombre=self.nombre_input.text().strip(),
            codigo_receta=self.codigo_input.text().strip(),
            version=self.version_input.text().strip() or "1.0",
            masa_final_deseada_g=self.masa_spin.value(),
            peso_pieza_g=self.peso_spin.value(),
            numero_piezas=self.piezas_spin.value(),
            merma_pct=self.merma_spin.value(),
            observaciones=self.observaciones_input.toPlainText().strip(),
            proceso=self.proceso_input.toPlainText().strip(),
            estado=self.estado_input.text().strip() or "borrador",
        )

    def _build_lines(self) -> list[RecetaLinea]:
        lines: list[RecetaLinea] = []
        for row in range(self.lines_table.rowCount()):
            line = self._line_from_row(row)
            lines.append(line)
        return lines

    def _recalculate(self) -> None:
        receta = self._build_recipe_model()
        lineas = self._build_lines()
        result = self.vm.calculate(receta, lineas)
        self._render_lines(result.lineas)
        self._update_summary(result.receta)
        self.current_issues = [f"[{i.level.upper()}] {i.message}" for i in result.issues]
        self.issues_label.setText("\n".join(self.current_issues))

    def _render_lines(self, lineas: list[RecetaLinea]) -> None:
        self.lines_table.setRowCount(0)
        for idx, linea in enumerate(lineas):
            self.lines_table.insertRow(idx)
            self._set_line_row(idx, linea)

    def _update_summary(self, receta: Receta) -> None:
        self.total_harinas_lbl.setText(f"{receta.total_harinas_g:.2f} g")
        self.total_liquidos_lbl.setText(f"{receta.total_liquidos_g:.2f} g")
        self.hidratacion_lbl.setText(f"{receta.hidratacion_pct:.2f} %")
        self.total_panadero_lbl.setText(f"{receta.total_porcentaje_panadero:.2f} %")
        self.masa_total_lbl.setText(f"{receta.masa_total_g:.2f} g")
        self.coste_total_lbl.setText(f"{receta.coste_total:.4f}")
        self.coste_kg_lbl.setText(f"{receta.coste_kg:.4f}")
        self.coste_pieza_lbl.setText(f"{receta.coste_pieza:.4f}")

    def _validate_recipe(self, receta: Receta) -> bool:
        if receta.cliente_id <= 0:
            QMessageBox.warning(self, "Validacion", "Debes seleccionar un cliente.")
            return False
        if not receta.nombre:
            QMessageBox.warning(self, "Validacion", "El nombre de receta es obligatorio.")
            return False
        if not receta.codigo_receta:
            QMessageBox.warning(self, "Validacion", "El codigo de receta es obligatorio.")
            return False
        return True

    def _save_recipe(self) -> None:
        receta = self._build_recipe_model()
        if not self._validate_recipe(receta):
            return
        lineas = self._build_lines()
        result = self.vm.calculate(receta, lineas)
        has_errors = any(issue.level == "error" for issue in result.issues)
        self._render_lines(result.lineas)
        self._update_summary(result.receta)
        self.current_issues = [f"[{i.level.upper()}] {i.message}" for i in result.issues]
        self.issues_label.setText("\n".join(self.current_issues))
        if has_errors:
            QMessageBox.warning(self, "Validacion", "Corrige los errores antes de guardar.\n" + self.issues_label.text())
            return
        with Session(engine) as session:
            saved = self.vm.save_recipe(session, result.receta, result.lineas)
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
        with Session(engine) as session:
            self.vm.save_version(session, receta, lineas, comentario.strip())
        QMessageBox.information(self, "Recetas", "Version guardada.")

    def _duplicate_recipe(self) -> None:
        if not self.current_recipe_id:
            QMessageBox.warning(self, "Recetas", "Selecciona una receta para duplicar.")
            return
        with Session(engine) as session:
            cloned = self.vm.duplicate_recipe(session, self.current_recipe_id, self._selected_cliente_id())
        self._reload_recipe_list()
        self._load_recipe(cloned.receta.id or 0)
        QMessageBox.information(self, "Recetas", "Receta duplicada.")

    def _delete_recipe(self) -> None:
        if not self.current_recipe_id:
            return
        confirm = QMessageBox.question(self, "Recetas", "Eliminar receta seleccionada?")
        if confirm != QMessageBox.Yes:
            return
        with Session(engine) as session:
            self.vm.delete_recipe(session, self.current_recipe_id)
        self._reload_recipe_list()
        self._new_recipe()

    def _print_recipe(self) -> None:
        QMessageBox.information(self, "Recetas", "Impresion se implementa en Fase 3.")

    def _export_pdf(self) -> None:
        QMessageBox.information(self, "Recetas", "Exportacion PDF se implementa en Fase 3.")

    def _export_excel(self) -> None:
        QMessageBox.information(self, "Recetas", "Exportacion Excel se implementa en Fase 3.")

