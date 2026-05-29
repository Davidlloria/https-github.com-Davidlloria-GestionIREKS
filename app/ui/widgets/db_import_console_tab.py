from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.config import DATA_DIR
from app.services.db_maintenance_import_service import DbMaintenanceImportService


class DbImportConsoleTab(QWidget):
    def __init__(
        self,
        on_import_completed: Callable[[], None] | None = None,
        *,
        allowed_profile_keys: list[str] | None = None,
        title: str = "Consola central de importacion",
    ) -> None:
        super().__init__()
        self._on_import_completed = on_import_completed
        self._service = DbMaintenanceImportService()
        self._allowed_profile_keys = {str(x or "").strip() for x in (allowed_profile_keys or []) if str(x or "").strip()}
        self._title = str(title or "").strip() or "Consola central de importacion"
        self._build_ui()
        self._load_profiles()
        self._refresh_jobs()

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

        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        card_layout.addWidget(self.description_label)

        form = QFormLayout()
        self.profile_combo = QComboBox()
        self.profile_combo.currentIndexChanged.connect(self._on_profile_changed)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Upsert (insertar o actualizar)", "upsert")
        self.mode_combo.addItem("Solo insertar", "insert_only")
        self.mode_combo.addItem("Solo actualizar", "update_only")

        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText("Selecciona archivo CSV/XLSX/JSON")
        browse_row = QHBoxLayout()
        browse_row.addWidget(self.file_input, 1)
        self.browse_btn = QPushButton("Seleccionar...")
        self.browse_btn.setProperty("btnRole", "secondary")
        self.browse_btn.clicked.connect(self._pick_file)
        browse_row.addWidget(self.browse_btn)

        self.dry_run_checkbox = QCheckBox("Ejecutar en modo simulacion (dry-run)")
        self.dry_run_checkbox.setChecked(True)

        form.addRow("Perfil", self.profile_combo)
        form.addRow("Modo", self.mode_combo)
        form.addRow("Archivo", self._wrap_layout_widget(browse_row))
        form.addRow("", self.dry_run_checkbox)
        card_layout.addLayout(form)

        actions = QHBoxLayout()
        self.preview_btn = QPushButton("Previsualizar")
        self.preview_btn.setProperty("btnRole", "warning")
        self.preview_btn.clicked.connect(self._preview)
        self.template_btn = QPushButton("Plantilla Excel")
        self.template_btn.setProperty("btnRole", "secondary")
        self.template_btn.clicked.connect(self._generate_template)
        self.run_btn = QPushButton("Ejecutar importacion")
        self.run_btn.setProperty("btnRole", "success")
        self.run_btn.clicked.connect(self._run_import)
        actions.addWidget(self.preview_btn)
        actions.addWidget(self.template_btn)
        actions.addWidget(self.run_btn)
        actions.addStretch(1)
        card_layout.addLayout(actions)

        self.preview_summary = QLabel("Sin previsualizacion.")
        self.preview_summary.setWordWrap(True)
        card_layout.addWidget(self.preview_summary)

        self.preview_errors = QTextEdit()
        self.preview_errors.setReadOnly(True)
        self.preview_errors.setPlaceholderText("Aqui se mostraran errores de validacion de la previsualizacion.")
        self.preview_errors.setMaximumHeight(160)
        card_layout.addWidget(self.preview_errors)

        layout.addWidget(card)

        history_title = QLabel("Historial de importaciones")
        history_title.setProperty("role", "sectionTitle")
        layout.addWidget(history_title)

        self.jobs_table = QTableWidget(0, 8)
        self.jobs_table.setHorizontalHeaderLabels(
            ["Fecha", "Perfil", "Modo", "Dry-run", "Insert", "Update", "Skip", "Errores"]
        )
        self.jobs_table.verticalHeader().setVisible(False)
        self.jobs_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.jobs_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.jobs_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.jobs_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.jobs_table, 1)

    def _wrap_layout_widget(self, row_layout: QHBoxLayout) -> QWidget:
        container = QWidget()
        container.setLayout(row_layout)
        return container

    def _load_profiles(self) -> None:
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        for profile in self._service.list_profiles():
            if self._allowed_profile_keys and profile.key not in self._allowed_profile_keys:
                continue
            self.profile_combo.addItem(profile.label, profile.key)
        self.profile_combo.blockSignals(False)
        self._on_profile_changed()

    def _on_profile_changed(self) -> None:
        profile_key = str(self.profile_combo.currentData() or "").strip()
        if not profile_key:
            self.description_label.setText("")
            return
        profile = self._service.get_profile(profile_key)
        required = ", ".join(profile.required_fields) if profile.required_fields else "ninguno"
        self.description_label.setText(
            f"{profile.description}\nCampos obligatorios: {required}."
        )

    def _pick_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar archivo",
            "",
            "Archivos de datos (*.xlsx *.xlsm *.csv *.json)",
        )
        if file_path:
            self.file_input.setText(file_path)

    def _generate_template(self) -> None:
        profile_key = str(self.profile_combo.currentData() or "").strip()
        if not profile_key:
            QMessageBox.warning(self, "Plantilla", "Selecciona un perfil de importacion.")
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_path = DATA_DIR / "templates" / f"{profile_key}_template_{stamp}.xlsx"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar plantilla Excel",
            str(default_path),
            "Excel (*.xlsx)",
        )
        if not file_path:
            return
        try:
            saved = self._service.create_excel_template(profile_key=profile_key, destination=Path(file_path))
            QMessageBox.information(self, "Plantilla", f"Plantilla generada:\n{saved}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Plantilla", f"No se pudo generar la plantilla:\n{exc}")

    def _preview(self) -> None:
        profile_key, path = self._resolve_inputs()
        if not profile_key or path is None:
            return

        try:
            preview = self._service.preview(profile_key=profile_key, file_path=path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Previsualizacion", f"No se pudo previsualizar: {exc}")
            return

        self.preview_summary.setText(
            (
                f"Filas archivo: {preview.total_rows} | "
                f"Validas: {preview.valid_rows} | "
                f"Invalidas: {preview.invalid_rows} | "
                f"Inserciones estimadas: {preview.estimated_inserts} | "
                f"Actualizaciones estimadas: {preview.estimated_updates}"
            )
        )
        if preview.errors:
            self.preview_errors.setPlainText("\n".join(preview.errors[:50]))
        else:
            self.preview_errors.setPlainText("Sin errores de validacion.")

    def _run_import(self) -> None:
        profile_key, path = self._resolve_inputs()
        if not profile_key or path is None:
            return

        mode = str(self.mode_combo.currentData() or "upsert")
        dry_run = bool(self.dry_run_checkbox.isChecked())
        confirm = QMessageBox.question(
            self,
            "Confirmar importacion",
            (
                "Se ejecutara una importacion centralizada de mantenimiento.\n"
                f"Perfil: {self.profile_combo.currentText()}\n"
                f"Modo: {self.mode_combo.currentText()}\n"
                f"Dry-run: {'si' if dry_run else 'no'}\n\n"
                "Continuar?"
            ),
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            result = self._service.execute(
                profile_key=profile_key,
                file_path=path,
                mode=mode,
                dry_run=dry_run,
                actor="settings_console",
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Importacion", f"No se pudo completar la importacion: {exc}")
            return

        self._refresh_jobs()
        if self._on_import_completed is not None:
            self._on_import_completed()

        summary = (
            f"Lote: {result.job_id}\n"
            f"Filas procesadas: {result.total_rows}\n"
            f"Insertadas: {result.inserted}\n"
            f"Actualizadas: {result.updated}\n"
            f"Omitidas: {result.skipped}\n"
            f"Errores: {len(result.errors)}"
        )
        if result.errors:
            details = "\n".join(result.errors[:12])
            extra = "" if len(result.errors) <= 12 else f"\n... y {len(result.errors) - 12} errores mas."
            QMessageBox.warning(self, "Importacion completada con incidencias", f"{summary}\n\n{details}{extra}")
            return
        QMessageBox.information(self, "Importacion completada", summary)

    def _resolve_inputs(self) -> tuple[str | None, Path | None]:
        profile_key = str(self.profile_combo.currentData() or "").strip()
        file_path = str(self.file_input.text() or "").strip()
        if not profile_key:
            QMessageBox.warning(self, "Importacion", "Selecciona un perfil de importacion.")
            return None, None
        if not file_path:
            QMessageBox.warning(self, "Importacion", "Selecciona un archivo de entrada.")
            return None, None
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            QMessageBox.warning(self, "Importacion", "El archivo seleccionado no existe o no es valido.")
            return None, None
        return profile_key, path

    def _refresh_jobs(self) -> None:
        jobs = self._service.list_recent_jobs(limit=40)
        self.jobs_table.setRowCount(len(jobs))
        for row_idx, item in enumerate(jobs):
            profile_key = str(item.get("profile_key", ""))
            profile_label = profile_key
            try:
                profile_label = self._service.get_profile(profile_key).label
            except Exception:
                profile_label = profile_key
            values = [
                item.get("created_at", ""),
                profile_label,
                item.get("mode", ""),
                "si" if item.get("dry_run", False) else "no",
                str(item.get("inserted", 0)),
                str(item.get("updated", 0)),
                str(item.get("skipped", 0)),
                str(item.get("errors", 0)),
            ]
            for col_idx, value in enumerate(values):
                table_item = QTableWidgetItem(value)
                table_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter if col_idx >= 3 else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self.jobs_table.setItem(row_idx, col_idx, table_item)
