from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QFrame, QHBoxLayout, QHeaderView, QInputDialog,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QProgressBar,
    QPushButton, QScrollArea, QTableWidget, QTableWidgetItem, QTabWidget,
    QVBoxLayout, QWidget,
)

from app.services.objectives_service import BLOCKS, MONTHS, Objective, ObjectivesService, fmt, number
from app.ui.widgets.product_consumers_dialog import _SelectionDelegate


STATUS = {"active": "Activo", "pending": "Pendiente todo el año", "unmarketed": "No comercializado"}
DIMENSIONS = {"all": "Todos los productos", "family": "Familias", "subfamily": "Subfamilias", "manufacturer": "Fabricantes", "products": "Productos concretos"}
RULES = {"growth": "Enteros · regla del informe", "quarter": "Cuartos de punto · volumen", "no_charge": "Reducir género sin cargo", "manual": "Valoración manual"}


class SortItem(QTableWidgetItem):
    def __init__(self, text, value=None):
        super().__init__(text)
        self.value = value if value is not None else text.casefold()

    def __lt__(self, other):
        if isinstance(self.value, (int, float)) and isinstance(other.value, (int, float)):
            return self.value < other.value
        return str(self.value) < str(other.value)


def table(headers):
    widget = QTableWidget(0, len(headers))
    widget.setHorizontalHeaderLabels(headers)
    widget.verticalHeader().hide()
    widget.verticalHeader().setDefaultSectionSize(38)
    widget.setAlternatingRowColors(True)
    widget.setWordWrap(False)
    widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    widget.setItemDelegate(_SelectionDelegate(widget))
    widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    return widget


class SelectionDialog(QDialog):
    def __init__(self, title, options, selected, parent):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(680, 580)
        layout = QVBoxLayout(self)
        search = QLineEdit()
        search.setPlaceholderText("Buscar…")
        layout.addWidget(search)
        self.list = QListWidget()
        for key, name in sorted(options.items(), key=lambda p: p[1].casefold()):
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if key in selected else Qt.CheckState.Unchecked)
            self.list.addItem(item)
        layout.addWidget(self.list)
        search.textChanged.connect(lambda text: [self.list.item(i).setHidden(text.casefold() not in self.list.item(i).text().casefold()) for i in range(self.list.count())])
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected(self):
        return [self.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list.count()) if self.list.item(i).checkState() == Qt.CheckState.Checked]


class ObjectiveEditor(QDialog):
    def __init__(self, raw, catalog, parent):
        super().__init__(parent)
        self.raw = deepcopy(raw)
        self.catalog = catalog
        self.members = raw["members"][:]
        self.setWindowTitle("Configurar objetivo")
        self.resize(640, 550)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(raw["name"])
        form.addRow("Nombre", self.name)
        self.kind = QComboBox()
        self.kind.addItem("Incremento porcentual (%)", "percent")
        self.kind.addItem("Meta anual fija (kg)", "kg")
        self.kind.setCurrentIndex(self.kind.findData(raw["target_type"]))
        form.addRow("Objetivo", self.kind)
        self.target = QDoubleSpinBox()
        self.target.setRange(0, 100000000)
        self.target.setDecimals(3)
        self.target.setValue(raw["target"])
        form.addRow("Valor objetivo", self.target)
        self.maximum = QDoubleSpinBox()
        self.maximum.setRange(0, 100)
        self.maximum.setValue(raw["maximum"])
        form.addRow("Puntos máximos", self.maximum)
        self.status = QComboBox()
        for key, name in STATUS.items():
            self.status.addItem(name, key)
        self.status.setCurrentIndex(self.status.findData(raw["status"]))
        form.addRow("Estado", self.status)
        self.dimension = QComboBox()
        for key, label in DIMENSIONS.items():
            self.dimension.addItem(label, key)
        self.dimension.setCurrentIndex(self.dimension.findData(raw["dimension"]))
        self.dimension.currentIndexChanged.connect(self._dimension_changed)
        form.addRow("Agrupar por", self.dimension)
        self.member_button = QPushButton()
        self._member_caption()
        self.member_button.clicked.connect(self._choose_members)
        form.addRow("Selección", self.member_button)
        self.scope = QComboBox()
        for key, name in (("all", "Canarias · cuatro orígenes"), ("distributors", "IGSA + Cadelsa"), ("hermanos", "Hermanos Rodríguez"), ("baker", "Baker Las Arenas Sin Gluten")):
            self.scope.addItem(name, key)
        self.scope.setCurrentIndex(self.scope.findData(raw["scope"]))
        form.addRow("Ventas incluidas", self.scope)
        form.addRow("Cálculo de puntos", QLabel(RULES[raw["rule"]]))
        note = QLabel("Las cantidades se obtienen de ventas IREKS: kilos vendidos + sin cargo.\nPara metas fijas sin ventas previas se aplica la regla por mes del informe.")
        note.setWordWrap(True)
        layout.addLayout(form)
        layout.addWidget(note)
        if raw["rule"] in {"manual", "no_charge"}:
            for w in (self.kind, self.target, self.dimension, self.member_button, self.scope, self.status):
                w.setEnabled(False)
        if raw["unit"] == "eur":
            self.kind.setEnabled(False)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _member_caption(self):
        self.member_button.setText(f"Seleccionar ({len(self.members)})…")

    def _dimension_changed(self):
        self.members = []
        self._member_caption()

    def _choose_members(self):
        kind = self.dimension.currentData()
        options = self.catalog.get(kind, {})
        if kind == "products":
            options = {key: f'{p["code"]} · {p["name"]}' for key, p in options.items()}
        if kind == "all":
            return
        dialog = SelectionDialog("Seleccionar productos o grupos", options, self.members, self)
        if dialog.exec():
            self.members = dialog.selected()
            self._member_caption()

    def _accept(self):
        if not self.name.text().strip():
            QMessageBox.warning(self, "Objetivo", "Introduce un nombre.")
            return
        if self.status.currentData() == "active" and self.dimension.currentData() != "all" and not self.members:
            QMessageBox.warning(self, "Objetivo", "Selecciona los productos o grupos de este objetivo.")
            return
        self.raw.update(name=self.name.text().strip(), target=self.target.value(), maximum=self.maximum.value(),
            target_type=self.kind.currentData(), status=self.status.currentData(), dimension=self.dimension.currentData(),
            members=self.members, scope=self.scope.currentData())
        self.accept()


class ObjectivesPage(QWidget):
    def __init__(self, parent=None, service=None):
        super().__init__(parent)
        self.service = service or ObjectivesService()
        self.campaign = None
        self.snapshot = None
        self.setObjectName("objectivesPage")
        self.setStyleSheet("""
            QWidget#objectivesPage { background: #F4F7FA; }
            QFrame#objectiveCard { background: white; border: 1px solid #D6E1EB; border-radius: 8px; }
            QTableWidget { background: white; alternate-background-color: #F3F6F9; color: #173653;
                selection-background-color: #DBF3F2; selection-color: #173653; gridline-color: #DBE3EB; }
            QHeaderView::section { background: #173653; color: white; padding: 9px; border: 1px solid #50667A; font-weight: bold; }
            QProgressBar { border: none; background: #E4EBF1; border-radius: 4px; max-height: 12px; }
            QProgressBar::chunk { background: #14999A; border-radius: 4px; }
            QTabBar::tab:selected { color: #173653; border-bottom: 3px solid #14999A; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        controls = QHBoxLayout()
        self.year = QComboBox()
        self.month = QComboBox()
        for i, name in enumerate(MONTHS, 1):
            self.month.addItem(name, i)
        controls.addWidget(QLabel("Campaña"))
        controls.addWidget(self.year)
        controls.addWidget(QLabel("Acumulado hasta"))
        controls.addWidget(self.month)
        new = QPushButton("Nueva campaña")
        new.clicked.connect(self._new_campaign)
        controls.addWidget(new)
        refresh = QPushButton("Actualizar")
        refresh.clicked.connect(self._refresh)
        controls.addWidget(refresh)
        controls.addStretch()
        icons = Path(__file__).resolve().parents[3] / "assets/icons"
        for label, suffix, icon, color in (("Pdf", "pdf", "file-text.svg", "#C62D40"), ("Excel", "xlsx", "sheet.svg", "#087A43")):
            button = QPushButton(label)
            button.setIcon(QIcon(str(icons / icon)))
            button.setIconSize(QSize(20, 20))
            button.setStyleSheet(f"color: {color}; font-weight: bold; padding: 8px 14px;")
            button.clicked.connect(lambda checked=False, kind=suffix: self._export(kind))
            controls.addWidget(button)
        layout.addLayout(controls)
        self.note = QLabel("Ventas de IREKS · kg vendidos + sin cargo · comparativa del mismo periodo")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        self.summary = QWidget()
        self.summary_layout = QVBoxLayout(self.summary)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.summary)
        self.tabs.addTab(scroll, "Resumen")
        detail_page = QWidget()
        detail_layout = QVBoxLayout(detail_page)
        self.filter = QComboBox()
        self.filter.addItem("Todos los apartados", -1)
        for i, name in enumerate(BLOCKS):
            self.filter.addItem(name, i)
        self.filter.currentIndexChanged.connect(self._fill_detail)
        detail_layout.addWidget(self.filter)
        self.detail = table(["Objetivo", "Meta anual", "Año anterior", "Año actual", "Δ cantidad", "Δ %", "Puntos", "Estado"])
        self.detail.setColumnWidth(0, 320)
        for i in range(1, 8):
            self.detail.setColumnWidth(i, 125 if i < 5 else 110)
        self.detail.setColumnWidth(7, 180)
        self.detail.horizontalHeader().setStretchLastSection(True)
        self.detail.horizontalHeader().setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        self.detail.cellDoubleClicked.connect(self._open_detail)
        self.detail.itemSelectionChanged.connect(self._selected_objective)
        detail_layout.addWidget(self.detail, 1)
        open_detail = QPushButton("Ver productos del objetivo seleccionado")
        open_detail.clicked.connect(lambda: self._open_detail(self.detail.currentRow(), 0))
        detail_layout.addWidget(open_detail)
        self.rule_note = QLabel("Selecciona un objetivo para ver su meta y desviación.")
        self.rule_note.setWordWrap(True)
        self.rule_note.setStyleSheet("color: #173653; background: #E8F3F5; padding: 10px;")
        detail_layout.addWidget(self.rule_note)
        self.detail_total = QLabel()
        detail_layout.addWidget(self.detail_total)
        self.tabs.addTab(detail_page, "Detalle")
        settings = QWidget()
        settings_layout = QVBoxLayout(settings)
        info = QLabel("Configura metas, puntos y lanzamientos por año. Las ventas nunca se modifican desde esta sección. Los cambios se guardan al aceptar cada edición.")
        info.setWordWrap(True)
        settings_layout.addWidget(info)
        self.config_table = table(["Apartado", "Objetivo", "Meta", "Puntos máximos", "Estado", "Productos / grupos"])
        self.config_table.setColumnWidth(0, 185)
        self.config_table.setColumnWidth(1, 320)
        self.config_table.setColumnWidth(2, 140)
        self.config_table.setColumnWidth(3, 145)
        self.config_table.setColumnWidth(4, 190)
        self.config_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.config_table.cellDoubleClicked.connect(lambda row, col: self._edit())
        settings_layout.addWidget(self.config_table, 1)
        buttons = QHBoxLayout()
        for label, callback in (("Editar objetivo", self._edit), ("Añadir lanzamiento", self._add_launch), ("Retirar lanzamiento", self._remove_launch), ("Orígenes de ventas", self._edit_sources), ("Valoración extra", self._manual)):
            button = QPushButton(label)
            button.clicked.connect(callback)
            buttons.addWidget(button)
        settings_layout.addLayout(buttons)
        self.tabs.addTab(settings, "Configuración")
        self.year.currentIndexChanged.connect(self._change_year)
        self.month.currentIndexChanged.connect(self._refresh)

    def reload(self):
        try:
            selected = self.year.currentData()
            years = self.service.years()
            self.year.blockSignals(True)
            self.year.clear()
            for year in years:
                self.year.addItem(str(year), year)
            self.year.setCurrentIndex(max(0, self.year.findData(selected)))
            self.year.blockSignals(False)
            self._change_year()
        except Exception as exc:
            self.note.setText(f"No se pudieron cargar los objetivos: {exc}")

    def _change_year(self):
        if self.year.currentData() is None:
            return
        try:
            self.campaign = self.service.campaign(self.year.currentData())
            latest = self.service.latest_month(self.campaign)
            self.month.blockSignals(True)
            self.month.setCurrentIndex(max(0, latest-1))
            self.month.blockSignals(False)
            self._refresh()
        except Exception as exc:
            self.campaign = None
            self._clear_snapshot()
            self.note.setText(f"No se pudo cargar la campaña: {exc}")

    def _clear_snapshot(self):
        self.snapshot = None
        self.detail.setRowCount(0)
        self.detail_total.clear()
        self.rule_note.clear()
        while self.summary_layout.count():
            item = self.summary_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _refresh(self):
        if self.campaign is None:
            return
        try:
            self.snapshot = self.service.calculate(self.campaign, self.month.currentData())
            self.note.setText("Ventas de IREKS · kg vendidos + sin cargo · " + ("Resultado provisional: revisa los avisos de datos." if self.snapshot["provisional"] else "Comparación del mismo periodo en ambos años."))
            self._fill_summary()
            self._fill_detail()
            self._fill_config()
        except Exception as exc:
            self._clear_snapshot()
            self.note.setText(f"No se pudo calcular el seguimiento: {exc}")

    def _fill_summary(self):
        while self.summary_layout.count():
            item = self.summary_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        s = self.snapshot
        cards = QFrame()
        cards.setObjectName("objectiveCard")
        row = QHBoxLayout(cards)
        volume = next((r for r in s["results"] if r.objective.key == "total"), None)
        pending = sum(r.objective.status == "pending" for r in s["results"])
        for title, value, subtitle in (("Puntuación calculada", fmt(s["total"]), f'Base {fmt(s["base"])} / {fmt(s["base_max"])} · extra {fmt(s["extra"])}'),
            ("Volumen acumulado", fmt(volume.current if volume else None, " kg"), "IGSA + Cadelsa + clientes directos"),
            ("Apartados pendientes", str(pending), "Se conservan dentro de los puntos máximos")):
            box = QVBoxLayout()
            box.addWidget(QLabel(title))
            big = QLabel(value)
            big.setStyleSheet("font-size: 27px; color: #173653; font-weight: 700;")
            box.addWidget(big)
            small = QLabel(subtitle)
            small.setWordWrap(True)
            box.addWidget(small)
            row.addLayout(box, 1)
        self.summary_layout.addWidget(cards)
        blocks = QFrame()
        blocks.setObjectName("objectiveCard")
        blocks_layout = QVBoxLayout(blocks)
        title = QLabel("Puntuación por apartado")
        title.setStyleSheet("font-size: 19px; font-weight: 700; color: #173653;")
        blocks_layout.addWidget(title)
        for block, name in enumerate(BLOCKS):
            points = sum(float(r.points or 0) for r in s["results"] if r.objective.block == block)
            maximum = sum(r.objective.maximum for r in s["results"] if r.objective.block == block)
            block_row = QHBoxLayout()
            block_row.addWidget(QLabel(name))
            block_row.addStretch()
            block_row.addWidget(QLabel(f"{fmt(points)} / {fmt(maximum)} puntos"))
            blocks_layout.addLayout(block_row)
            bar = QProgressBar()
            bar.setRange(0, 1000)
            bar.setValue(round(points/maximum*1000) if maximum else 0)
            bar.setTextVisible(False)
            blocks_layout.addWidget(bar)
        self.summary_layout.addWidget(blocks)
        sc = next((r for r in s["results"] if r.objective.rule == "no_charge"), None)
        if sc and sc.current is not None and volume and volume.current is not None:
            ratios = [fmt(amount / total * 100, " %") if total and amount is not None else "—" for amount, total in ((sc.previous, volume.previous), (sc.current, volume.current))]
            label = QLabel(f"Género sin cargo sin lanzamientos: {fmt(sc.current, ' kg')} · {ratios[1]} del volumen actual (año anterior: {ratios[0]}).\nLos puntos se calculan por reducción de kilos, no por esta proporción.")
            label.setWordWrap(True)
            self.summary_layout.addWidget(label)
        extra = QLabel("Extra: valoración manual. Solo se aplica con una base de al menos el 45 % y menor del 100 %. Sin avisos por valoraciones a cero.")
        extra.setWordWrap(True)
        self.summary_layout.addWidget(extra)
        if s["issues"]:
            issue = QLabel("Datos a revisar\n" + "\n".join(s["issues"]))
            issue.setWordWrap(True)
            issue.setStyleSheet("background: #FFF4DE; color: #724C16; padding: 12px;")
            self.summary_layout.addWidget(issue)
        self.summary_layout.addStretch()

    def _fill_detail(self):
        if not self.snapshot:
            return
        s = self.snapshot
        self.detail.setSortingEnabled(False)
        results = [r for r in s["results"] if self.filter.currentData() in (-1, r.objective.block)]
        self.detail.setRowCount(len(results))
        self.detail.setHorizontalHeaderLabels(["Objetivo", "Meta anual", f'Ene–{MONTHS[s["month"]-1][:3]} {s["year"]-1}', f'Ene–{MONTHS[s["month"]-1][:3]} {s["year"]}', "Δ cantidad", "Δ %", "Puntos", "Estado"])
        for row, r in enumerate(results):
            unit = " €" if r.objective.unit == "eur" else " kg"
            values = [r.objective.name, fmt(r.annual_target, unit), fmt(r.previous, unit), fmt(r.current, unit), fmt(r.delta, unit), fmt(r.growth, " %"), f"{fmt(r.points)} / {fmt(r.objective.maximum)}", r.status]
            keys = [r.objective.name, r.annual_target, r.previous, r.current, r.delta, r.growth, r.points, r.status]
            for col, value in enumerate(values):
                key = keys[col]
                item = SortItem(value, float(key) if key is not None and col in range(1, 7) else key)
                item.setData(Qt.ItemDataRole.UserRole, r.objective.key)
                item.setToolTip(value)
                if col in range(1, 7):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if col in (4, 5) and key:
                    item.setForeground(QColor("#087A43" if key > 0 else "#BE2940"))
                self.detail.setItem(row, col, item)
        self.detail.setSortingEnabled(True)
        self.detail_total.setText(f'Puntuación total: {fmt(s["total"])} · Base: {fmt(s["base"])} / {fmt(s["base_max"])} · Extra aplicado: {fmt(s["extra"])}. Las cantidades de los apartados se solapan y no se suman.')
        self.detail_total.setWordWrap(True)

    def _selected_objective(self):
        row = self.detail.currentRow()
        item = self.detail.item(row, 0) if row >= 0 else None
        if not self.snapshot or item is None or not hasattr(self, "rule_note"):
            return
        r = next((r for r in self.snapshot["results"] if r.objective.key == item.data(Qt.ItemDataRole.UserRole)), None)
        if r is None:
            return
        o = r.objective
        if o.status != "active" or o.rule == "manual":
            self.rule_note.setText(f"{o.name} · {r.status}. Puntos máximos conservados: {fmt(o.maximum)}.")
            return
        target = fmt(o.target, " %" if o.target_type == "percent" else " kg")
        text = f"{o.name} · Meta: {target} · {RULES[o.rule]}."
        if o.target_type == "percent" and r.growth is not None:
            text += f" Crecimiento acumulado: {fmt(r.growth, ' %')} · Desviación: {fmt(r.growth - number(o.target), ' puntos porcentuales')}."
        if r.annual_target is not None and r.current is not None:
            unit = " €" if o.unit == "eur" else " kg"
            text += f" Diferencia hasta la meta anual: {fmt(r.annual_target - r.current, unit)}."
        if o.unit == "sc":
            text = f"{o.name}: 2 años comparados hasta el mismo mes, excluyendo los lanzamientos. Se puntúa una reducción estricta de kg sin cargo; igualdad o aumento puntúan cero."
        self.rule_note.setText(text)

    def _fill_config(self):
        self.config_table.setRowCount(len(self.campaign["objectives"]))
        c = self.snapshot["catalog"]
        for row, raw in enumerate(self.campaign["objectives"]):
            labels = c.get(raw["dimension"], {})
            selected = [labels.get(i, "Referencia no disponible") for i in raw["members"]]
            if raw["dimension"] == "products":
                selected = [c["products"].get(i, {}).get("name", "Referencia no disponible") for i in raw["members"]]
            values = [BLOCKS[raw["block"]], raw["name"], fmt(raw["target"], " %" if raw["target_type"] == "percent" else " kg"), fmt(raw["maximum"]), STATUS[raw["status"]], ", ".join(selected) or DIMENSIONS[raw["dimension"]]]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.config_table.setItem(row, col, item)

    def _open_detail(self, row, col):
        if row < 0 or not self.snapshot:
            return
        key = self.detail.item(row, 0).data(Qt.ItemDataRole.UserRole)
        r = next(r for r in self.snapshot["results"] if r.objective.key == key)
        dialog = QDialog(self)
        dialog.setWindowTitle(r.objective.name)
        dialog.resize(950, 580)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(f"{r.status} · {RULES[r.objective.rule]} · Fuente: ventas IREKS"))
        t = table(["Código", "Producto", "Acumulado anterior", "Acumulado actual", "Δ cantidad"])
        t.setColumnWidth(0, 100)
        t.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col in (2, 3, 4):
            t.setColumnWidth(col, 155)
        t.setRowCount(len(r.details))
        for row, item in enumerate(r.details):
            values = [item["code"], item["name"], item["previous"], item["current"], item["current"]-item["previous"]]
            for col, value in enumerate(values):
                cell = SortItem(str(value) if col < 2 else fmt(value), str(value) if col < 2 else float(value))
                if col >= 2:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                t.setItem(row, col, cell)
        t.setSortingEnabled(True)
        layout.addWidget(t)
        dialog.exec()

    def _save(self, campaign):
        try:
            self.service.save(campaign)
            self.campaign = campaign
            self._refresh()
            return True
        except Exception as exc:
            QMessageBox.warning(self, "Objetivos", f"No se guardaron los cambios:\n{exc}")
            return False

    def _edit(self):
        row = self.config_table.currentRow()
        if row < 0 or not self.snapshot:
            return
        dialog = ObjectiveEditor(self.campaign["objectives"][row], self.snapshot["catalog"], self)
        if dialog.exec():
            campaign = deepcopy(self.campaign)
            campaign["objectives"][row] = dialog.raw
            self._save(campaign)

    def _add_launch(self):
        if not self.snapshot:
            return
        raw = asdict(Objective(str(uuid4()), "Nuevo lanzamiento", 1, 0, 4, target_type="kg", dimension="products"))
        dialog = ObjectiveEditor(raw, self.snapshot["catalog"], self)
        if dialog.exec():
            campaign = deepcopy(self.campaign)
            campaign["objectives"].append(dialog.raw)
            self._save(campaign)

    def _remove_launch(self):
        row = self.config_table.currentRow()
        if row < 0 or self.campaign["objectives"][row]["block"] != 1:
            QMessageBox.information(self, "Lanzamientos", "Selecciona un lanzamiento para retirarlo de esta campaña.")
            return
        name = self.campaign["objectives"][row]["name"]
        if QMessageBox.question(self, "Retirar lanzamiento", f"¿Retirar {name} de esta campaña? Sus puntos dejarán de contar en el máximo. Puedes marcarlo como no comercializado para conservarlos.") != QMessageBox.StandardButton.Yes:
            return
        campaign = deepcopy(self.campaign)
        del campaign["objectives"][row]
        self._save(campaign)

    def _edit_sources(self):
        if not self.snapshot:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Orígenes de ventas de IREKS")
        layout = QVBoxLayout(dialog)
        label = QLabel("Incluye las referencias históricas de cada origen. La unión evita contar dos veces una referencia seleccionada en varios grupos.")
        label.setWordWrap(True)
        layout.addWidget(label)
        campaign = deepcopy(self.campaign)
        for key, name in (("igsa", "IGSA"), ("cadelsa", "Cadelsa"), ("hermanos", "Hermanos Rodríguez"), ("baker", "Baker Las Arenas Sin Gluten")):
            button = QPushButton(f"{name} · {len(campaign['scopes'][key])} referencias")
            def choose(checked=False, key=key, name=name, button=button):
                picker = SelectionDialog(name, self.snapshot["catalog"]["parties"], campaign["scopes"][key], dialog)
                if picker.exec():
                    campaign["scopes"][key] = picker.selected()
                    button.setText(f"{name} · {len(picker.selected())} referencias")
            button.clicked.connect(choose)
            layout.addWidget(button)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec():
            self._save(campaign)

    def _manual(self):
        if not self.campaign:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Valoración extra · {self.month.currentText()}")
        layout = QFormLayout(dialog)
        fields = {}
        month = str(self.month.currentData())
        for raw in self.campaign["objectives"]:
            if raw["rule"] == "manual":
                spin = QDoubleSpinBox()
                spin.setRange(0, raw["maximum"])
                spin.setValue(self.campaign.get("manual", {}).get(month, {}).get(raw["key"], 0))
                layout.addRow(raw["name"], spin)
                fields[raw["key"]] = spin
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        if dialog.exec():
            campaign = deepcopy(self.campaign)
            campaign.setdefault("manual", {})[month] = {key: spin.value() for key, spin in fields.items()}
            self._save(campaign)

    def _new_campaign(self):
        if not self.campaign:
            return
        year, ok = QInputDialog.getInt(self, "Nueva campaña", "Año de la nueva campaña (copia metas y lanzamientos; revisa su configuración)", self.campaign["year"]+1, 2000, 2200)
        if ok:
            try:
                campaign = self.service.copy_campaign(self.campaign["year"], year)
                self.service.save(campaign)
                self.reload()
                self.year.setCurrentIndex(self.year.findData(year))
            except Exception as exc:
                QMessageBox.warning(self, "Campaña", str(exc))

    def _export(self, suffix):
        if not self.snapshot:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar objetivos", f'Objetivos_{self.campaign["year"]}_{self.month.currentData():02d}.{suffix}', "PDF (*.pdf)" if suffix == "pdf" else "Excel (*.xlsx)")
        if not path:
            return
        if not path.lower().endswith("." + suffix):
            path += "." + suffix
        try:
            from app.services.objectives_export import export_objectives
            export_objectives(path, self.snapshot)
            QMessageBox.information(self, "Objetivos", f"Archivo guardado:\n{path}")
        except Exception as exc:
            QMessageBox.warning(self, "Exportación", f"No se pudo guardar el archivo:\n{exc}")
