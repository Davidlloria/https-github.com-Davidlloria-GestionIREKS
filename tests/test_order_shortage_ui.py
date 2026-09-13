from datetime import date
import os
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
from PySide6.QtGui import QFontDatabase, QFont

from app.models import PedidoFaltante
from app.services.order_incident_service import ReceivedArticleOption
from app.ui.widgets.order_shortage_dialog import NewOrderShortageDialog, OrderShortageFollowupDialog

_APP = QApplication.instance() or QApplication([])


def preview(dialog, path):
    # Qt offscreen on Windows does not automatically discover the system fonts.
    font_path = Path("C:/Windows/Fonts/segoeui.ttf")
    if font_path.exists():
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            dialog.setFont(QFont(families[0], 10))
    dialog.show()
    _APP.processEvents()
    dialog.grab().save(str(path))


def article():
    return ReceivedArticleOption("line", "D1203041", "PASTA LIMON", "60690267", date(2027, 12, 16), 24, "2026090117", date(2026, 8, 27))


def test_new_shortage_calculates_difference_and_validates_without_writing(monkeypatch, tmp_path):
    dialog = NewOrderShortageDialog([article()], "line")
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]))
    dialog._validate()
    assert warnings
    assert dialog.result() == QDialog.DialogCode.Rejected
    dialog.received.setValue(18)
    dialog.observations.setPlainText("Tres cajas de seis unidades en el almacén")
    assert dialog.missing.text() == "6 uds."
    preview(dialog, tmp_path / "new-shortage.png")
    dialog._validate()
    assert dialog.result() == QDialog.DialogCode.Accepted
    dialog.close()


def test_followup_confirmation_is_explicit_and_has_no_implicit_stock_write(monkeypatch, tmp_path):
    shortage = PedidoFaltante(incidencia_id="i", albaran_item_id="line", cantidad_documentada=24,
        cantidad_recibida=18, huella="fingerprint")
    calls = []
    service = SimpleNamespace(confirm=lambda key, **kwargs: calls.append(key))
    dialog = OrderShortageFollowupDialog(shortage=shortage, article=article(), observations="Recuento",
        service=service, attachments=SimpleNamespace(list_images=lambda key: []))
    assert calls == []
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.No)
    dialog._confirm()
    assert calls == []
    preview(dialog, tmp_path / "followup-shortage.png")
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    dialog._confirm()
    assert calls == ["i"]
    assert dialog.result() == QDialog.DialogCode.Accepted
    dialog.close()


def test_service_error_keeps_followup_open(monkeypatch):
    def fail(_, **kwargs):
        raise ValueError("Revisa la asignación")
    shortage = PedidoFaltante(incidencia_id="i", albaran_item_id="line", cantidad_documentada=24,
        cantidad_recibida=18, huella="fingerprint")
    dialog = OrderShortageFollowupDialog(shortage=shortage, article=article(), observations="Recuento",
        service=SimpleNamespace(confirm=fail), attachments=SimpleNamespace(list_images=lambda key: []))
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]))
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    dialog._confirm()
    assert warnings == ["Revisa la asignación"]
    assert dialog.result() == QDialog.DialogCode.Rejected
    dialog.close()
