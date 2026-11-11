from email.parser import BytesParser
from email.policy import default
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog

from app.services.recipe_mail_service import RecipeMailService
from app.services.technical_sheet_mail_service import TechnicalSheetMailService
from app.ui.widgets.technical_sheet_mail_dialog import TechnicalSheetMailDialog


def test_multiple_sheets_are_attached_once_and_missing_file_blocks_draft(tmp_path):
    first, second = tmp_path / "uno.pdf", tmp_path / "dos.pdf"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    paths = {"one": first, "two": second}
    calls = []
    mail = RecipeMailService(launcher=lambda *a, **kw: calls.append(a),
                             executable_resolver=lambda: tmp_path / "olk.exe",
                             draft_dir=tmp_path, signature_path=tmp_path / "none")
    service = TechnicalSheetMailService(SimpleNamespace(resolve_document=lambda key: paths[key]), mail)
    args = dict(document_ids=["one", "two", "one"], recipients=["a@example.com"],
                subject="Fichas", body="Hola", include_signature=False)
    draft = service.open_draft(**args)
    message = BytesParser(policy=default).parsebytes(draft.read_bytes())
    assert [(part.get_filename(), part.get_payload(decode=True)) for part in message.iter_attachments()] == [
        ("uno.pdf", b"first"), ("dos.pdf", b"second")]
    assert len(calls) == 1
    second.unlink()
    with pytest.raises(OSError):
        service.open_draft(**args)
    assert len(calls) == 1


def test_dialog_selects_customer_contacts_and_removes_documents(monkeypatch):
    app = QApplication.instance() or QApplication([])
    customers = SimpleNamespace(list=lambda: [SimpleNamespace(cliente_id="a", cliente_codigo=1,
        cliente_nombre_comercial="Cliente", cliente_nombre_fiscal="", cliente_email="cliente@example.com")])
    contacts = SimpleNamespace(related_contacts=lambda _: [SimpleNamespace(nombre="Ana", apellidos="", email="ana@example.com")])
    distributors = SimpleNamespace(list=lambda: [SimpleNamespace(distribuidor_id="d", distribuidor_codigo=1, distribuidor_nombre_comercial="Panadería Norte", distribuidor_razon_social="Distribuciones Norte")])
    dialog = TechnicalSheetMailDialog({"one": "Ficha uno", "two": "Ficha dos"}, customer_service=customers, contact_service=contacts, distributor_service=distributors)
    dialog.search.setText("NORTE")
    assert dialog.customers.count() == 2 and "Distribuidor" in dialog.customers.itemText(1)
    dialog.customers.setCurrentIndex(1)
    assert "manualmente" in dialog.status.text()
    dialog.search.setText("ien")
    assert dialog.customers.count() == 2 and "Cliente" in dialog.customers.itemText(1)
    dialog.documents.setCurrentRow(0)
    dialog._remove_document()
    dialog.customers.setCurrentIndex(1)
    dialog.contacts.item(1).setCheckState(Qt.CheckState.Checked)
    dialog.manual_recipients.setText("ANA@example.com; distribuidor@example.com")
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.selected_document_ids() == ["two"]
    assert dialog.recipients == ["ANA@example.com", "distribuidor@example.com"]
    dialog.close()
    app.processEvents()


def test_dialog_rejects_invalid_recipient(monkeypatch):
    from app.ui.widgets import technical_sheet_mail_dialog as module
    app = QApplication.instance() or QApplication([])
    warnings = []
    monkeypatch.setattr(module.QMessageBox, "warning", lambda *args: warnings.append(args[-1]))
    dialog = TechnicalSheetMailDialog({"one": "Ficha"}, customer_service=SimpleNamespace(list=lambda: []), distributor_service=SimpleNamespace(list=lambda: []))
    dialog.manual_recipients.setText("correo incorrecto")
    dialog.accept()
    assert warnings and dialog.result() == QDialog.DialogCode.Rejected
    dialog.close()
    app.processEvents()


def test_without_recipient_opens_draft_with_attachment(tmp_path):
    app = QApplication.instance() or QApplication([])
    dialog = TechnicalSheetMailDialog({"one": "Producto"}, customer_service=SimpleNamespace(list=lambda: []), distributor_service=SimpleNamespace(list=lambda: []))
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.recipients == []
    sheet = tmp_path / "ficha.pdf"
    sheet.write_bytes(b"ficha")
    calls = []
    mail = RecipeMailService(launcher=lambda *args, **kwargs: calls.append(args),
                             executable_resolver=lambda: tmp_path / "olk.exe", draft_dir=tmp_path,
                             signature_path=tmp_path / "none")
    service = TechnicalSheetMailService(SimpleNamespace(resolve_document=lambda _: sheet), mail)
    draft = service.open_draft(document_ids=dialog.selected_document_ids(), recipients=dialog.recipients,
                               subject="Fichas", body="Hola", include_signature=False)
    message = BytesParser(policy=default).parsebytes(draft.read_bytes())
    assert not message.get("To")
    assert [part.get_payload(decode=True) for part in message.iter_attachments()] == [b"ficha"]
    assert len(calls) == 1
    dialog.close()
    app.processEvents()


def test_selection_persists_across_products(monkeypatch, tmp_path):
    from dataclasses import replace
    from tests.test_ingredients_product_documents_ui import _application, _document, _page

    app = _application()
    page, links, _, _ = _page(monkeypatch, tmp_path)
    page._reload_product_documents("product-1")
    page._add_product_document_to_mail()
    links.documents = [replace(_document(), document_id="document-2", name="Otra.pdf")]
    page._reload_product_documents("product-2")
    page._add_product_document_to_mail()
    assert list(page._mail_technical_sheets) == ["document-1", "document-2"]
    assert page.product_document_mail_button.text() == "Email"
    assert "2 fichas" in page.product_document_mail_button.toolTip()
    page._remove_mail_technical_sheet("document-1")
    assert list(page._mail_technical_sheets) == ["document-2"]
    page.close()
    app.processEvents()
