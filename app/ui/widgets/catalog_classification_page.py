from __future__ import annotations

from uuid import uuid4
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget, QMenu, QFileDialog,
)

from app.services.warehouse_catalog_service import WarehouseCatalogService
from app.ui.widgets.objectives_page import SortItem, table


# Singular service suffix, identity prefix, plural label.
LEVELS = (("fabricante", "fabricante", "Fabricantes"),
          ("familia", "articulo_familia", "Familias"),
          ("subfamilia", "articulo_subfamilia", "Subfamilias"))


class CatalogEditor(QDialog):
    def __init__(self, title, parent_label, code="", name="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(440, 210)
        layout = QVBoxLayout(self)
        if parent_label:
            layout.addWidget(QLabel(parent_label))
        form = QFormLayout()
        self.code = QLineEdit(str(code))
        self.name = QLineEdit(name)
        form.addRow("Código", self.code)
        form.addRow("Nombre", self.name)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self):
        if not self.name.text().strip():
            QMessageBox.warning(self, "Clasificación", "Introduce un nombre.")
            return
        self.accept()


class CatalogClassificationPage(QWidget):
    def __init__(self, parent=None, service=None):
        super().__init__(parent)
        self.service = service or WarehouseCatalogService()
        self.records = [[], [], []]
        self.selected = [None, None, None]
        self.cards, self.titles, self.searches, self.tables = [], [], [], []
        self.counts, self.new_buttons, self.edit_buttons, self.delete_buttons = [], [], [], []
        self.setObjectName("catalogClassification")
        self.setStyleSheet("""
            QWidget#catalogClassification { background: #F4F7FA; }
            QFrame#catalogCard { background: white; border: 1px solid #D6E1EB;
                border-top: 4px solid #14999A; border-radius: 8px; }
            QLabel { color: #173653; }
            QLabel#catalogTitle { font-size: 18px; font-weight: bold; }
            QLabel#catalogPath { background: white; padding: 12px; border: 1px solid #D6E1EB; border-radius: 6px; }
            QTableWidget { background: white; alternate-background-color: #F3F6F9;
                color: #173653; gridline-color: #E1E8EF; }
            QHeaderView::section { background: #EDF3F8; color: #173653;
                padding: 8px; border: none; font-weight: bold; }
            QPushButton { padding: 7px 10px; }
            QPushButton#catalogNew { background: #14999A; color: white; border-radius: 5px; }
            QPushButton#catalogNew:disabled { background: #DDE7EB; color: #607080; }
            QPushButton#catalogDelete { color: #B42332; }
        """)
        layout = QVBoxLayout(self)
        heading = QHBoxLayout()
        title = QLabel("Clasificación de productos")
        title.setObjectName("catalogTitle")
        heading.addWidget(title)
        heading.addStretch()
        imports = QPushButton("Importar")
        menu = QMenu(imports)
        for level, (_, _, label) in enumerate(LEVELS):
            menu.addAction(label).triggered.connect(lambda _, n=level: self._import(n))
        imports.setMenu(menu)
        heading.addWidget(imports)
        refresh = QPushButton("Actualizar")
        refresh.clicked.connect(self.reload)
        heading.addWidget(refresh)
        layout.addLayout(heading)
        self.path = QLabel()
        self.path.setObjectName("catalogPath")
        self.path.setWordWrap(True)
        layout.addWidget(self.path)
        cards = QHBoxLayout()
        cards.setSpacing(14)
        layout.addLayout(cards, 1)
        for level, (_, _, title) in enumerate(LEVELS):
            card = QFrame()
            card.setObjectName("catalogCard")
            body = QVBoxLayout(card)
            body.setContentsMargins(14, 18, 14, 12)
            label = QLabel(title)
            label.setObjectName("catalogTitle")
            label.setWordWrap(True)
            body.addWidget(label)
            search = QLineEdit()
            search.setPlaceholderText("Buscar código o nombre…")
            body.addWidget(search)
            new = QPushButton("Nuevo")
            new.setIcon(QIcon(str(Path(__file__).resolve().parents[3] / "assets" / "icons" / "plus.svg")))
            new.setObjectName("catalogNew")
            body.addWidget(new, alignment=Qt.AlignmentFlag.AlignRight)
            grid = table(["Código", "Nombre"], weights=(25, 75))
            grid.horizontalHeader().setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
            body.addWidget(grid, 1)
            count = QLabel()
            count.setWordWrap(True)
            body.addWidget(count)
            actions = QHBoxLayout()
            edit, delete = QPushButton("Editar"), QPushButton("Eliminar")
            icons = Path(__file__).resolve().parents[3] / "assets" / "icons"
            edit.setIcon(QIcon(str(icons / "movement-edit-navy.svg")))
            delete.setIcon(QIcon(str(icons / "trash.svg")))
            delete.setObjectName("catalogDelete")
            actions.addWidget(edit)
            actions.addWidget(delete)
            body.addLayout(actions)
            cards.addWidget(card, 1)
            self.cards.append(card)
            self.titles.append(label)
            self.searches.append(search)
            self.tables.append(grid)
            self.counts.append(count)
            self.new_buttons.append(new)
            self.edit_buttons.append(edit)
            self.delete_buttons.append(delete)
            search.textChanged.connect(lambda _, n=level: self._fill(n))
            grid.itemSelectionChanged.connect(lambda n=level: self._selection(n))
            grid.cellDoubleClicked.connect(lambda _r, _c, n=level: self._edit(n))
            new.clicked.connect(lambda _, n=level: self._edit(n, new=True))
            edit.clicked.connect(lambda _, n=level: self._edit(n))
            delete.clicked.connect(lambda _, n=level: self._delete(n))
        layout.addWidget(QLabel("Selecciona un fabricante y después una familia. Las nuevas altas se vinculan a la selección actual."))
        self.reload()

    def reload(self):
        try:
            records = [self.service.list_fabricantes(""), self.service.list_familias(""), self.service.list_subfamilias("")]
        except Exception as exc:
            QMessageBox.warning(self, "Clasificación", f"No se pudo cargar el catálogo:\n{exc}")
            return
        self.records = records
        self._fill(0)

    def _row(self, level):
        key = LEVELS[level][1] + "_id"
        return next((r for r in self.records[level] if getattr(r, key) == self.selected[level]
                     and (level != 2 or r.articulo_familia_id == self.selected[1])), None)

    def _fill(self, level):
        prefix = LEVELS[level][1]
        term = self.searches[level].text().strip().casefold()
        rows = self.records[level]
        if level:
            parent_key = LEVELS[level - 1][1] + "_id"
            rows = [r for r in rows if self.selected[level - 1] and getattr(r, parent_key) == self.selected[level - 1]]
        rows = [r for r in rows if term in f"{getattr(r, prefix + '_codigo')} {getattr(r, prefix + '_nombre')}".casefold()]
        grid = self.tables[level]
        grid.blockSignals(True)
        grid.setSortingEnabled(False)
        grid.setRowCount(len(rows))
        grid.clearSelection()
        selected_row = -1
        for i, record in enumerate(rows):
            identity = getattr(record, prefix + "_id")
            for col, field in enumerate(("_codigo", "_nombre")):
                value = getattr(record, prefix + field)
                cell = SortItem(str(value or ""), value if isinstance(value, int) else str(value or "").casefold())
                cell.setData(Qt.ItemDataRole.UserRole, identity)
                cell.setToolTip(cell.text())
                grid.setItem(i, col, cell)
            if identity == self.selected[level]:
                selected_row = i
        if selected_row >= 0:
            grid.selectRow(selected_row)
        grid.setSortingEnabled(True)
        grid.blockSignals(False)
        self.counts[level].setText(f"{len(rows)} registros" if rows else (
            "Selecciona primero " + ("un fabricante." if level == 1 else "una familia.")
            if level and not self.selected[level - 1] else "Sin registros para esta selección o búsqueda."))
        self._selection(level)

    def _selection(self, level):
        grid = self.tables[level]
        indexes = grid.selectionModel().selectedRows()
        identity = grid.item(indexes[0].row(), 0).data(Qt.ItemDataRole.UserRole) if indexes else None
        changed = identity != self.selected[level]
        self.selected[level] = identity
        self.edit_buttons[level].setEnabled(bool(identity))
        self.delete_buttons[level].setEnabled(bool(identity))
        self.new_buttons[level].setEnabled(level == 0 or bool(self.selected[level - 1]))
        if level < 2:
            if changed:
                self.selected[level + 1:] = [None] * (2 - level)
                for search in self.searches[level + 1:]:
                    search.blockSignals(True)
                    search.clear()
                    search.blockSignals(False)
            self._fill(level + 1)
        names = [getattr(row, LEVELS[i][1] + "_nombre") for i in range(3) if (row := self._row(i)) is not None]
        self.path.setText("  ›  ".join(names) or "Fabricante  ›  Familia  ›  Subfamilia")
        for i in (1, 2):
            parent = self._row(i - 1)
            self.titles[i].setText(LEVELS[i][2] + (" de " + getattr(parent, LEVELS[i - 1][1] + "_nombre") if parent else ""))

    def _edit(self, level, new=False):
        row = None if new else self._row(level)
        if (not new and row is None) or (level and not self.selected[level - 1]):
            return
        suffix, prefix, label = LEVELS[level]
        parent = self._row(level - 1) if level else None
        dialog = CatalogEditor("Nuevo registro" if new else "Editar registro",
            getattr(parent, LEVELS[level - 1][1] + "_nombre") if parent else "",
            getattr(row, prefix + "_codigo", ""), getattr(row, prefix + "_nombre", ""), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        code = dialog.code.text().strip()
        if level == 0 and code and not code.isdigit():
            QMessageBox.warning(self, "Clasificación", "El código del fabricante debe ser numérico.")
            return
        identity = str(uuid4()) if new else self.selected[level]
        payload = {prefix + "_nombre": dialog.name.text().strip(), prefix + "_codigo": int(code or 0) if level == 0 else code}
        if new:
            payload[prefix + "_id"] = identity
            if level:
                payload[LEVELS[level - 1][1] + "_id"] = self.selected[level - 1]
        try:
            if new:
                getattr(self.service, "create_" + suffix)(payload)
            elif level == 2:
                self.service.update_subfamilia(identity, payload, familia_id=self.selected[1])
            else:
                getattr(self.service, "update_" + suffix)(identity, payload)
        except Exception as exc:
            QMessageBox.warning(self, "Clasificación", f"No se pudo guardar:\n{exc}")
            return
        self.selected[level] = identity
        self.searches[level].blockSignals(True)
        self.searches[level].clear()
        self.searches[level].blockSignals(False)
        self.reload()

    def _delete(self, level):
        row = self._row(level)
        if row is None:
            return
        suffix, prefix, _ = LEVELS[level]
        name = getattr(row, prefix + "_nombre")
        if QMessageBox.question(self, "Eliminar registro", f"¿Eliminar «{name}»?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete_classification(suffix, self.selected[level], familia_id=self.selected[1] if level == 2 else None)
        except Exception as exc:
            QMessageBox.warning(self, "Clasificación", str(exc))
            return
        self.reload()

    def _import(self, level):
        path, _ = QFileDialog.getOpenFileName(self, "Importar " + LEVELS[level][2], "",
                                             "Archivos de datos (*.xlsx *.xlsm *.csv)")
        if not path:
            return
        try:
            count, errors = getattr(self.service, "import_" + LEVELS[level][2].lower())(path)
        except Exception as exc:
            QMessageBox.warning(self, "Importación", str(exc))
            return
        self.reload()
        message = f"Registros importados: {count}"
        if errors:
            QMessageBox.warning(self, "Importación", message + "\n" + "\n".join(errors[:8]))
        else:
            QMessageBox.information(self, "Importación", message)


def open_classification(parent):
    dialog = QDialog(parent)
    dialog.setWindowTitle("Clasificación de productos")
    dialog.resize(1250, 750)
    layout = QVBoxLayout(dialog)
    layout.addWidget(CatalogClassificationPage(dialog))
    dialog.exec()
