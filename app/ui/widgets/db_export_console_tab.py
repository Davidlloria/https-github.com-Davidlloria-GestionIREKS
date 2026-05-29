from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.config import DATA_DIR
from app.services.db_export_service import DbExportService


class DbExportConsoleTab(QWidget):
    def __init__(
        self,
        *,
        title: str = "Consola de exportacion",
        allowed_table_names: list[str] | None = None,
    ) -> None:
        super().__init__()
        self._service = DbExportService()
        self._title = str(title or "Consola de exportacion")
        self._allowed_table_names = [str(name or "").strip() for name in (allowed_table_names or []) if str(name or "").strip()]
        self._build_ui()
        self._reload_schema()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(8)

        title = QLabel(self._title)
        title.setProperty("role", "sectionTitle")
        card_layout.addWidget(title)

        self.table_combo = QComboBox()
        self.table_combo.currentIndexChanged.connect(self._on_table_changed)
        self.refresh_tables_btn = QPushButton("Actualizar")
        self.refresh_tables_btn.setProperty("btnRole", "secondary")
        self.refresh_tables_btn.clicked.connect(self._reload_schema)
        self.refresh_tables_btn.setMinimumWidth(96)

        self.row_count_label = QLabel("Registros: 0")
        self.selected_cols_label = QLabel("Campos seleccionados: 0")

        self.field_filter = QLineEdit()
        self.field_filter.setPlaceholderText("Filtrar campos...")
        self.field_filter.textChanged.connect(self._filter_fields)

        body = QHBoxLayout()
        body.setSpacing(10)

        left_panel = QFrame()
        left_panel.setObjectName("card")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(8)

        selector_row = QHBoxLayout()
        self.select_all_btn = QPushButton("Seleccionar todo")
        self.select_all_btn.setProperty("btnRole", "secondary")
        self.select_all_btn.clicked.connect(self._select_all_fields)
        self.clear_all_btn = QPushButton("Limpiar")
        self.clear_all_btn.setProperty("btnRole", "secondary")
        self.clear_all_btn.clicked.connect(self._clear_all_fields)
        selector_row.addWidget(self.select_all_btn)
        selector_row.addWidget(self.clear_all_btn)
        selector_row.addStretch(1)
        left_layout.addLayout(selector_row)

        self.fields_list = QListWidget()
        self.fields_list.itemChanged.connect(self._update_selected_count)
        self.fields_list.setMinimumHeight(280)
        self.fields_list.setStyleSheet(
            """
            QListWidget::item:selected {
                color: #0f172a;
                background: #dbeafe;
            }
            QListWidget::item:selected:active {
                color: #0f172a;
                background: #bfdbfe;
            }
            QListWidget::item:selected:!active {
                color: #0f172a;
                background: #dbeafe;
            }
            """
        )
        left_layout.addWidget(self.fields_list, 1)

        right_panel = QFrame()
        right_panel.setObjectName("card")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(8)

        table_line = QHBoxLayout()
        table_label = QLabel("Tabla")
        table_label.setMinimumWidth(86)
        table_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        table_line.addWidget(table_label)
        table_line.addWidget(self.table_combo, 1)
        table_line.addWidget(self.refresh_tables_btn, 0)
        right_layout.addLayout(table_line)

        metrics_line = QHBoxLayout()
        metrics_line.addWidget(self.row_count_label)
        metrics_line.addSpacing(20)
        metrics_line.addWidget(self.selected_cols_label)
        metrics_line.addStretch(1)
        right_layout.addLayout(metrics_line)

        filter_line = QHBoxLayout()
        filter_label = QLabel("Buscar campo")
        filter_label.setMinimumWidth(86)
        filter_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        filter_line.addWidget(filter_label)
        filter_line.addWidget(self.field_filter, 1)
        right_layout.addLayout(filter_line)

        self.format_combo = QComboBox()
        self.format_combo.addItem("CSV", "csv")
        self.format_combo.addItem("Excel (.xlsx)", "xlsx")
        self.format_combo.addItem("JSON", "json")
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        format_line = QHBoxLayout()
        format_label = QLabel("Formato")
        format_label.setMinimumWidth(90)
        format_line.addWidget(format_label)
        format_line.addWidget(self.format_combo, 1)
        right_layout.addLayout(format_line)

        self.output_path_input = QLineEdit()
        self.output_path_input.setPlaceholderText("Ruta de salida")
        output_line = QHBoxLayout()
        output_label = QLabel("Archivo salida")
        output_label.setMinimumWidth(90)
        output_line.addWidget(output_label)
        output_line.addWidget(self.output_path_input, 1)
        self.browse_btn = QPushButton("Seleccionar...")
        self.browse_btn.setProperty("btnRole", "secondary")
        self.browse_btn.clicked.connect(self._pick_output_file)
        self.browse_btn.setMinimumWidth(120)
        output_line.addWidget(self.browse_btn, 0)
        right_layout.addLayout(output_line)

        actions = QHBoxLayout()
        self.export_btn = QPushButton("Exportar")
        self.export_btn.setProperty("btnRole", "success")
        self.export_btn.clicked.connect(self._export)
        actions.addWidget(self.export_btn)
        actions.addStretch(1)
        right_layout.addLayout(actions)
        right_layout.addStretch(1)

        body.addWidget(right_panel, 3)
        body.addWidget(left_panel, 2)
        card_layout.addLayout(body, 1)
        layout.addWidget(card, 1)

    def _reload_schema(self) -> None:
        tables = self._service.list_tables()
        if self._allowed_table_names:
            allowed = set(self._allowed_table_names)
            tables = [name for name in tables if name in allowed]
        self.table_combo.blockSignals(True)
        current = str(self.table_combo.currentData() or "").strip()
        self.table_combo.clear()
        for table_name in tables:
            self.table_combo.addItem(table_name, table_name)
        self.table_combo.blockSignals(False)
        if current:
            idx = self.table_combo.findData(current)
            if idx >= 0:
                self.table_combo.setCurrentIndex(idx)
                self._on_table_changed()
                return
        if tables:
            self.table_combo.setCurrentIndex(0)
        self._on_table_changed()

    def _on_table_changed(self) -> None:
        table_name = str(self.table_combo.currentData() or "").strip()
        self.fields_list.blockSignals(True)
        self.fields_list.clear()
        self.field_filter.clear()
        if not table_name:
            self.fields_list.blockSignals(False)
            self.row_count_label.setText("Registros: 0")
            self.selected_cols_label.setText("Campos seleccionados: 0")
            self.output_path_input.clear()
            return

        columns = self._service.list_columns(table_name)
        for name in columns:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.fields_list.addItem(item)
        self.fields_list.blockSignals(False)

        count = self._service.count_rows(table_name)
        self.row_count_label.setText(f"Registros: {count}")
        self._update_selected_count()
        self._sync_default_path(force=True)

    def _on_format_changed(self, _index: int) -> None:
        fmt = str(self.format_combo.currentData() or "csv").strip().lower()
        current = str(self.output_path_input.text() or "").strip()
        if not current:
            self._sync_default_path(force=True)
            return
        try:
            updated = str(Path(current).with_suffix(f".{fmt}"))
            self.output_path_input.setText(updated)
        except Exception:  # noqa: BLE001
            self._sync_default_path(force=True)

    def _filter_fields(self) -> None:
        term = str(self.field_filter.text() or "").strip().lower()
        for idx in range(self.fields_list.count()):
            item = self.fields_list.item(idx)
            visible = term in str(item.text() or "").lower()
            item.setHidden(not visible)

    def _select_all_fields(self) -> None:
        self.fields_list.blockSignals(True)
        for idx in range(self.fields_list.count()):
            self.fields_list.item(idx).setCheckState(Qt.CheckState.Checked)
        self.fields_list.blockSignals(False)
        self._update_selected_count()

    def _clear_all_fields(self) -> None:
        self.fields_list.blockSignals(True)
        for idx in range(self.fields_list.count()):
            self.fields_list.item(idx).setCheckState(Qt.CheckState.Unchecked)
        self.fields_list.blockSignals(False)
        self._update_selected_count()

    def _update_selected_count(self) -> None:
        selected = 0
        for idx in range(self.fields_list.count()):
            if self.fields_list.item(idx).checkState() == Qt.CheckState.Checked:
                selected += 1
        self.selected_cols_label.setText(f"Campos seleccionados: {selected}")

    def _sync_default_path(self, *, force: bool = False) -> None:
        table_name = str(self.table_combo.currentData() or "").strip()
        if not table_name:
            return
        extension = str(self.format_combo.currentData() or "csv")
        current = str(self.output_path_input.text() or "").strip()
        if current and not force:
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_dir = DATA_DIR / "exports"
        default_path = default_dir / f"{table_name}_{stamp}.{extension}"
        self.output_path_input.setText(str(default_path))

    def _pick_output_file(self) -> None:
        table_name = str(self.table_combo.currentData() or "").strip() or "export"
        fmt = str(self.format_combo.currentData() or "csv")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_dir = DATA_DIR / "exports"
        default_path = default_dir / f"{table_name}_{stamp}.{fmt}"

        filters = {
            "csv": "CSV (*.csv)",
            "xlsx": "Excel (*.xlsx)",
            "json": "JSON (*.json)",
        }
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar exportacion",
            str(default_path),
            filters.get(fmt, "Todos (*.*)"),
        )
        if file_path:
            self.output_path_input.setText(file_path)

    def _selected_columns(self) -> list[str]:
        columns: list[str] = []
        for idx in range(self.fields_list.count()):
            item = self.fields_list.item(idx)
            if item.checkState() == Qt.CheckState.Checked:
                columns.append(str(item.text() or "").strip())
        return columns

    def _export(self) -> None:
        table_name = str(self.table_combo.currentData() or "").strip()
        if not table_name:
            QMessageBox.warning(self, "Exportacion", "Selecciona una tabla.")
            return
        columns = self._selected_columns()
        if not columns:
            QMessageBox.warning(self, "Exportacion", "Selecciona al menos un campo.")
            return
        fmt = str(self.format_combo.currentData() or "csv")
        output_path = str(self.output_path_input.text() or "").strip()
        if not output_path:
            self._sync_default_path(force=True)
            output_path = str(self.output_path_input.text() or "").strip()
        if not output_path:
            QMessageBox.warning(self, "Exportacion", "Indica una ruta de salida.")
            return

        destination = Path(output_path)
        confirm = QMessageBox.question(
            self,
            "Confirmar exportacion",
            (
                f"Tabla: {table_name}\n"
                f"Campos: {len(columns)}\n"
                f"Formato: {fmt}\n"
                f"Salida: {destination}\n\n"
                "Continuar?"
            ),
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            result = self._service.export_data(
                table_name=table_name,
                columns=columns,
                destination=destination,
                output_format=fmt,
            )
            QMessageBox.information(
                self,
                "Exportacion completada",
                (
                    f"Tabla: {result['table']}\n"
                    f"Filas exportadas: {result['rows_exported']}\n"
                    f"Archivo: {result['path']}"
                ),
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Exportacion", f"No se pudo completar la exportacion:\n{exc}")
