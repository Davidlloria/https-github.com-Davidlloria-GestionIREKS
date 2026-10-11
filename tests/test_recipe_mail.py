from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QDialogButtonBox, QLineEdit, QWidget
from reportlab.pdfgen.canvas import Canvas

from app.services.recipe_mail_service import RecipeMailService, normalize_recipients
from app.ui.widgets import recipes_page, recipe_mail_dialog
from app.ui.widgets.recipe_mail_dialog import RecipeMailDialog
from app.ui.widgets.recipes_page import RecipePdfExportDialog, RecipePdfPreviewDialog, RecipesPage


def test_recipients_deduplicate_and_validate():
    assert normalize_recipients([" A@example.com; b@example.com ", "a@example.com"]) == ["A@example.com", "b@example.com"]
    with pytest.raises(ValueError):
        normalize_recipients(["not-an-email"])
    with pytest.raises(ValueError):
        normalize_recipients(["a@example.com\r\nBcc: hidden@example.com"])


@pytest.mark.parametrize("failure", [None, "attach", "save", "display", "connect"])
def test_outlook_embeds_exact_pdf_and_never_sends(tmp_path, monkeypatch, failure):
    import tempfile
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    calls, paths = [], []
    content = b"%PDF-exact-preview-bytes"
    class Mail:
        def __init__(self):
            self.Attachments = SimpleNamespace(Add=self.attach)
        def attach(self, path, attachment_type):
            assert attachment_type == 1
            paths.append(Path(path))
            assert paths[0].read_bytes() == content
            calls.append("attach")
            if failure == "attach":
                raise RuntimeError("Attachment error")
        def Save(self):
            assert paths[0].exists()
            calls.append("save")
            if failure == "save":
                raise RuntimeError("Save error")
        def Display(self):
            assert calls == ["attach", "save"]
            calls.append("display")
            if failure == "display":
                raise RuntimeError("Display error")
        def Send(self):
            pytest.fail("Automatic sending is forbidden")
    mail = Mail()
    def dispatch(name):
        assert name == "Outlook.Application"
        if failure == "connect":
            raise RuntimeError("Unavailable")
        return SimpleNamespace(CreateItem=lambda kind: mail if kind == 0 else pytest.fail("Wrong item"))
    service = RecipeMailService(dispatch)
    args = dict(pdf_content=content, recipe_name='Pan / malta', recipients=["one@example.com", "ONE@example.com"], subject="Receta: Pan", body="Texto editable")
    if failure:
        with pytest.raises(RuntimeError):
            service.open_draft(**args)
    else:
        service.open_draft(**args)
        assert calls == ["attach", "save", "display"]
        assert mail.To == "one@example.com" and mail.Subject == args["subject"] and mail.Body == args["body"]
        assert paths[0].name == "Receta-Pan _ malta.pdf"
    assert all(not path.exists() for path in paths)


def test_no_recipient_does_not_start_outlook():
    service = RecipeMailService(lambda _: pytest.fail("Must not start Outlook"))
    with pytest.raises(ValueError):
        service.open_draft(pdf_content=b"pdf", recipe_name="Pan", recipients=[], subject="", body="")


@pytest.fixture(scope="module")
def application():
    app = QApplication.instance() or QApplication([])
    yield app


def test_contacts_are_unselected_missing_email_disabled_and_manual_deduplicated(application):
    requested = []
    def related(customer_id):
        requested.append(customer_id)
        return [SimpleNamespace(nombre="Ana", apellidos="Uno", email="ana@example.com"),
                SimpleNamespace(nombre="Luis", apellidos="Dos", email="")]
    dialog = RecipeMailDialog(customer_id="customer-A", recipe_name="Pan", contact_service=SimpleNamespace(related_contacts=related))
    assert requested == ["customer-A"]
    assert dialog.contacts_table.item(0, 0).checkState() == Qt.CheckState.Unchecked
    assert not dialog.contacts_table.item(1, 0).flags() & Qt.ItemFlag.ItemIsEnabled
    dialog.contacts_table.item(0, 0).setCheckState(Qt.CheckState.Checked)
    dialog.manual_recipients.setText("ANA@example.com; other@example.com")
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.recipients == ["ANA@example.com", "other@example.com"]
    assert dialog.subject.text() == "Receta: Pan"


@pytest.mark.parametrize("case", ["no_customer", "empty", "unavailable", "invalid"])
def test_manual_fallback_and_recipient_validation(application, monkeypatch, case):
    warnings = []
    monkeypatch.setattr(recipe_mail_dialog.QMessageBox, "warning", lambda *args: warnings.append(args[-1]))
    def related(_):
        if case == "no_customer":
            pytest.fail("No customer query expected")
        if case == "unavailable":
            raise OSError("Unavailable")
        if case == "invalid":
            return [SimpleNamespace(nombre="Ana", apellidos="", email="incorrecto")]
        return []
    dialog = RecipeMailDialog(customer_id="" if case == "no_customer" else "A", recipe_name="Pan", contact_service=SimpleNamespace(related_contacts=related))
    dialog.accept()
    assert warnings and dialog.result() == QDialog.DialogCode.Rejected
    dialog.manual_recipients.setText("manual@example.com")
    dialog.accept()
    assert dialog.recipients == ["manual@example.com"]
    assert dialog.result() == QDialog.DialogCode.Accepted


def make_pdf(path, text="Receta"):
    canvas = Canvas(str(path))
    canvas.drawString(50, 750, text)
    canvas.save()


@pytest.mark.parametrize("cancel,fail", [(True, False), (False, False), (False, True)])
def test_preview_mail_uses_loaded_combined_pdf_without_closing_preview(application, tmp_path, monkeypatch, cancel, fail):
    sheet = tmp_path / "sheet.pdf"
    make_pdf(sheet, "Ficha")
    service = SimpleNamespace(export_recipe_to_pdf=lambda _id, path, **_: make_pdf(path))
    dialog = RecipePdfPreviewDialog(service, 1, False, False, False, False, technical_sheets=[sheet], customer_id="customer-A", recipe_name="Pan")
    assert dialog.pdf_document.pageCount() == 2 and dialog.outlook_button.isEnabled()
    original = bytes(dialog._preview_buffer.data())
    requested, drafts, warnings = [], [], []
    def mail_dialog(parent, **kwargs):
        requested.append(kwargs)
        return SimpleNamespace(exec=lambda: not cancel, recipients=["ana@example.com"], subject=QLineEdit("Asunto editado"), body=SimpleNamespace(toPlainText=lambda: "Texto editado"))
    def draft(**kwargs):
        drafts.append(kwargs)
        if fail:
            raise RuntimeError("Outlook no disponible")
    monkeypatch.setattr(recipes_page, "RecipeMailDialog", mail_dialog)
    monkeypatch.setattr(recipes_page, "RecipeMailService", lambda: SimpleNamespace(open_draft=draft))
    monkeypatch.setattr(recipes_page.QMessageBox, "warning", lambda *args: warnings.append(args[-1]))
    dialog._preview_path.write_bytes(b"changed after preview")
    dialog.outlook_button.click()
    assert requested == [{"customer_id": "customer-A", "recipe_name": "Pan"}]
    assert len(drafts) == (0 if cancel else 1)
    if not cancel:
        assert drafts[0]["pdf_content"] == original
        assert drafts[0]["subject"] == "Asunto editado"
    assert bool(warnings) == fail
    assert dialog.outlook_button.isEnabled()
    assert dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Save).isEnabled()
    dialog.cleanup_preview()


@pytest.mark.parametrize("mode", ["minimal", "original", "simple", "extended"])
def test_export_passes_saved_customer_to_mail_preview_in_all_formats(application, tmp_path, monkeypatch, mode):
    page = QWidget()
    page.current_recipe_id = 7
    page.recipe_service = SimpleNamespace(get_recipe=lambda _: SimpleNamespace(receta=SimpleNamespace(cliente_id="saved-customer", parametros_elaboracion_json="{}")))
    page.pdf_service = SimpleNamespace(export_recipe_to_pdf=lambda _id, path, **_: make_pdf(path))
    page.nombre_input = QLineEdit("Pan")
    page.cliente_combo = QComboBox()
    def options(dialog):
        getattr(dialog, f"{mode}_radio").setChecked(True)
        return QDialog.DialogCode.Accepted
    previews = []
    def preview(dialog):
        previews.append(dialog._preview_path)
        assert dialog._mail_customer_id == "saved-customer"
        assert dialog._mail_recipe_name == "Pan"
        assert dialog.outlook_button.isEnabled()
        return QDialog.DialogCode.Rejected
    monkeypatch.setattr(RecipePdfExportDialog, "exec", options)
    monkeypatch.setattr(RecipePdfPreviewDialog, "exec", preview)
    RecipesPage._export_pdf(page)
    assert len(previews) == 1 and not previews[0].exists()


def test_failed_pdf_disables_email(application, monkeypatch):
    monkeypatch.setattr(recipes_page.QMessageBox, "critical", lambda *_: None)
    def export(*_, **__):
        raise ValueError("PDF failed")
    dialog = RecipePdfPreviewDialog(SimpleNamespace(export_recipe_to_pdf=export), 1, False, False, False, False)
    assert not dialog.outlook_button.isEnabled()
    dialog.cleanup_preview()
