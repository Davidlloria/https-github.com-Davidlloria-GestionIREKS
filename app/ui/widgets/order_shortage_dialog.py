from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QDate, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog,
    QFormLayout, QLabel, QLineEdit, QListWidget, QMessageBox, QPushButton, QTextEdit, QVBoxLayout,
)

from app.services.order_incident_service import OrderIncidentService, ReceivedArticleOption
from app.services.order_shortage_service import OrderShortageService, SHORTAGE_STATES


class NewOrderShortageDialog(QDialog):
    def __init__(self, articles: list[ReceivedArticleOption], selected_item: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Registrar faltante de recepción")
        self.resize(670, 520)
        self.articles = {a.item_id: a for a in articles}
        self.paths: list[Path] = []
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.article = QComboBox()
        self.article.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.article.setMinimumContentsLength(35)
        for a in articles:
            self.article.addItem(a.label, a.item_id)
        form.addRow("Línea y lote", self.article)
        self.documented = QLabel()
        form.addRow("Unidades del albarán", self.documented)
        self.received = QDoubleSpinBox()
        self.received.setDecimals(3)
        self.received.setSuffix(" uds.")
        form.addRow("Recuento del almacén", self.received)
        self.missing = QLabel()
        form.addRow("Faltante", self.missing)
        self.incident_date = QDateEdit(QDate.currentDate())
        self.incident_date.setCalendarPopup(True)
        self.incident_date.setDisplayFormat("dd/MM/yyyy")
        form.addRow("Fecha del recuento", self.incident_date)
        self.observations = QTextEdit()
        self.observations.setPlaceholderText("Describe la diferencia y cómo se ha comprobado.")
        form.addRow("Observaciones", self.observations)
        layout.addLayout(form)
        self.files = QListWidget()
        layout.addWidget(QLabel("Justificantes"))
        layout.addWidget(self.files)
        attach = QPushButton("Adjuntar justificante PDF o imagen")
        attach.clicked.connect(self._attach)
        layout.addWidget(attach)
        hint = QLabel("Se guardará pendiente de comprobar. La recepción y el stock se corrigen al confirmar.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Guardar")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.article.currentIndexChanged.connect(self._update_article)
        self.received.valueChanged.connect(self._update_missing)
        if selected_item:
            self.article.setCurrentIndex(self.article.findData(selected_item))
        self._update_article()

    def _update_article(self):
        article = self.articles.get(self.article.currentData())
        quantity = article.unidades if article else 0
        self.documented.setText(f"{quantity:g}")
        self.received.setRange(0, quantity)
        self.received.setValue(quantity)
        self._update_missing()

    def _update_missing(self):
        article = self.articles.get(self.article.currentData())
        self.missing.setText(f"{(article.unidades if article else 0) - self.received.value():g} uds.")

    def _attach(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Justificante del almacén", "", "PDF e imágenes (*.pdf *.jpg *.jpeg *.png *.webp)")
        for raw in paths:
            path = Path(raw)
            if path not in self.paths:
                self.paths.append(path)
                self.files.addItem(path.name)

    def _validate(self):
        article = self.articles.get(self.article.currentData())
        missing = article.unidades - self.received.value() if article else 0
        if missing <= 0 or not float(missing).is_integer() or not self.observations.toPlainText().strip():
            QMessageBox.warning(self, "Faltante", "Indica un faltante entero mayor que cero y describe el recuento.")
            return
        if any(not p.is_file() or p.stat().st_size > 10 * 1024 * 1024 for p in self.paths):
            QMessageBox.warning(self, "Justificante", "Comprueba los archivos: deben existir y no superar 10 MB cada uno.")
            return
        self.accept()


class OrderShortageFollowupDialog(QDialog):
    def __init__(self, *, shortage, article: ReceivedArticleOption, observations: str,
                 service: OrderShortageService, attachments: OrderIncidentService, parent=None):
        super().__init__(parent)
        self.shortage = shortage
        self.service = service
        self.attachments = attachments
        self.setWindowTitle("Seguimiento del faltante")
        self.resize(700, 650)
        layout = QVBoxLayout(self)
        for text in (article.label, SHORTAGE_STATES[shortage.estado],
                     f"Albarán: {shortage.cantidad_documentada:g} uds. · Recuento registrado: {shortage.cantidad_recibida:g} uds. · "
                     f"Faltante registrado: {shortage.cantidad_documentada - shortage.cantidad_recibida:g} uds.", observations):
            label = QLabel(text)
            label.setWordWrap(True)
            layout.addWidget(label)
        if shortage.resolucion == "error_recuento":
            layout.addWidget(QLabel(f"Recepción final: {shortage.cantidad_documentada:g} uds. No existía faltante."))
        self.files = QListWidget()
        self._paths: list[Path] = []
        self.files.itemDoubleClicked.connect(self._open)
        layout.addWidget(QLabel("Justificantes · doble clic para abrir"))
        layout.addWidget(self.files)
        attach = QPushButton("Añadir justificante PDF o imagen")
        attach.clicked.connect(self._attach)
        layout.addWidget(attach)
        self._reload_files()
        history = QTextEdit()
        layout.addWidget(QLabel("Historial"))
        history.setReadOnly(True)
        history.setPlainText("\n\n".join(f"{e['fecha']} · {e['accion']}\n{e['detalle']}" for e in json.loads(shortage.historial)))
        layout.addWidget(history)
        self.reference = QLineEdit()
        self.reference.setPlaceholderText("Referencia y detalle de la reclamación, abono o comprobación")
        layout.addWidget(self.reference)
        if shortage.estado == "pendiente":
            self.corrected_count = QDoubleSpinBox()
            self.corrected_count.setDecimals(3)
            self.corrected_count.setRange(0, shortage.cantidad_documentada)
            self.corrected_count.setValue(shortage.cantidad_recibida)
            self.corrected_count.setSuffix(" uds. contadas")
            layout.addWidget(self.corrected_count)
            correct = QPushButton("Corregir recuento pendiente")
            correct.clicked.connect(lambda: self._run(lambda: service.update_count(shortage.incidencia_id,
                self.corrected_count.value(), self.reference.text())))
            layout.addWidget(correct)
            confirm = QPushButton("Confirmar recepción y corregir stock")
            confirm.clicked.connect(self._confirm)
            layout.addWidget(confirm)
        if shortage.estado == "confirmado":
            claim = QPushButton("Marcar como reclamada")
            claim.clicked.connect(lambda: self._run(lambda: service.mark_claimed(shortage.incidencia_id, self.reference.text())))
            layout.addWidget(claim)
        self.resolution = QComboBox()
        if shortage.confirmado:
            self.resolution.addItem("Reposición recibida", "reposicion")
            self.resolution.addItem("Abono y cancelación del faltante", "abono")
        self.resolution.addItem("Error de recuento: no existía faltante", "error_recuento")
        self.replacement = QComboBox()
        self.replacement.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.replacement.setMinimumContentsLength(35)
        self.replacement.addItem("Selecciona la recepción de reposición...", "")
        if shortage.confirmado and shortage.estado != "resuelta":
            for item in service.replacement_options(shortage.incidencia_id):
                self.replacement.addItem(f"Albarán {item.albaran_numero} · {item.albaran_fecha:%d/%m/%Y} · "
                    f"Lote {item.articulo_lote} · {item.cantidad_operativa:g} uds.", item.item_id)
        self.resolution.currentIndexChanged.connect(lambda: self.replacement.setVisible(self.resolution.currentData() == "reposicion"))
        layout.addWidget(self.resolution)
        layout.addWidget(self.replacement)
        self.replacement.setVisible(self.resolution.currentData() == "reposicion")
        resolve = QPushButton("Resolver incidencia")
        resolve.clicked.connect(self._resolve)
        layout.addWidget(resolve)
        if shortage.estado == "resuelta":
            self.reference.hide()
            self.resolution.hide()
            self.replacement.hide()
            resolve.hide()
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.button(QDialogButtonBox.StandardButton.Close).setText("Cerrar")
        close.rejected.connect(self.reject)
        layout.addWidget(close)

    def _reload_files(self):
        self.files.clear()
        self._paths = []
        for attachment in self.attachments.list_images(self.shortage.incidencia_id):
            self.files.addItem(attachment.nombre_original)
            self._paths.append(self.attachments.resolve_image_path(attachment.ruta_relativa))

    def _open(self, item):
        path = self._paths[self.files.row(item)]
        if path.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _attach(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Justificante", "", "PDF e imágenes (*.pdf *.jpg *.jpeg *.png *.webp)")
        try:
            for path in paths:
                self.attachments.add_attachment(self.shortage.incidencia_id, Path(path))
        except Exception as exc:
            QMessageBox.warning(self, "Justificante", str(exc))
        self._reload_files()

    def _run(self, action):
        try:
            action()
        except Exception as exc:
            QMessageBox.warning(self, "Faltante", str(exc))
            return
        self.accept()

    def _confirm(self):
        missing = self.shortage.cantidad_documentada - self.shortage.cantidad_recibida
        message = (f"La línea pasará de {self.shortage.cantidad_documentada:g} a {self.shortage.cantidad_recibida:g} unidades recibidas.\n"
                   f"Se registrará un ajuste de stock de −{missing:g} unidades y se recalcularán los pendientes.\n"
                   "El albarán original se conserva. ¿Confirmar el recuento?")
        if QMessageBox.question(self, "Confirmar recepción", message) == QMessageBox.StandardButton.Yes:
            self._run(lambda: self.service.confirm(self.shortage.incidencia_id, expected_received=self.shortage.cantidad_recibida))

    def _resolve(self):
        resolution = self.resolution.currentData()
        effects = {"reposicion": "Se vinculará una recepción existente; no se añadirá stock otra vez.",
            "abono": "Se cancelarán las unidades faltantes pendientes, conservando la recepción real y el stock.",
            "error_recuento": "Se cerrará el faltante y se revertirá su corrección de recepción y stock si estaba confirmada."}
        if QMessageBox.question(self, "Resolver faltante", effects[resolution] + "\n¿Continuar?") == QMessageBox.StandardButton.Yes:
            self._run(lambda: self.service.resolve(self.shortage.incidencia_id, resolution,
                self.reference.text(), str(self.replacement.currentData() or "")))
