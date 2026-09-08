from __future__ import annotations

import os
from datetime import date
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTableWidget

from app.ui.widgets.courses_page import CoursesPage


def test_courses_reload_sorts_dates_chronologically_and_preserves_row_identity() -> None:
    app = QApplication.instance() or QApplication([])
    table = QTableWidget(0, 2)
    dates = [date(2026, 1, 2), date(2025, 12, 31), date(2026, 2, 1), date(2026, 1, 15)]
    rows = [SimpleNamespace(curso_fecha=value, curso_id=value.isoformat(),
                            curso_nombre=f"Curso {value.isoformat()}") for value in dates]
    empty_filter = SimpleNamespace(currentData=lambda: None)
    page = SimpleNamespace(
        year_filter=empty_filter, month_start_filter=empty_filter,
        month_end_filter=empty_filter, search_input=SimpleNamespace(text=lambda: ""),
        service=SimpleNamespace(list_courses=lambda **kwargs: rows), table=table,
        _show_selected_details=lambda: None,
    )
    try:
        for order, reverse in ((Qt.SortOrder.AscendingOrder, False),
                               (Qt.SortOrder.DescendingOrder, True)):
            table.sortItems(0, order)
            CoursesPage.reload(page)
            for index, value in enumerate(sorted(dates, reverse=reverse)):
                cell = table.item(index, 0)
                assert cell.text() == value.strftime("%d/%m/%Y")
                assert cell.data(Qt.ItemDataRole.UserRole) == value.isoformat()
                assert table.item(index, 1).text() == f"Curso {value.isoformat()}"
    finally:
        table.close()
        table.deleteLater()
        app.processEvents()


def test_attendee_context_actions_use_clicked_row_and_show_island(monkeypatch) -> None:
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QMenu
    from app.viewmodels.course_viewmodel import AsistenteListadoItem

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(CoursesPage, "reload", lambda self: None)
    page = CoursesPage()
    rows = [AsistenteListadoItem("course", contact, "company", "", name, "", "Empresa", False, island)
            for contact, name, island in (("z", "Zoe", "GC"), ("a", "Ana", ""))]
    monkeypatch.setattr(page.service, "list_attendees", lambda course: rows)
    calls = []
    monkeypatch.setattr(page, "_delete_attendee", lambda: calls.append(("delete", page._selected_attendee().contacto_id)))
    monkeypatch.setattr(page, "_focus_contact_in_contacts_page", lambda contact: calls.append(("edit", contact)))
    monkeypatch.setattr(page, "_edit_attendee_observaciones", lambda contact: calls.append(("notes", contact)))
    try:
        page._render_attendees("course")
        assert page.attendees_table.horizontalHeaderItem(4).text() == "Isla"
        assert page.attendees_table.item(0, 4).text() == ""
        assert page.attendees_table.item(1, 4).text() == "GC"
        assert page.attendees_table.cellWidget(1, 4) is None
        for index, expected in enumerate(("delete", "edit", "notes")):
            def choose(menu, pos):
                assert [action.text() for action in menu.actions()] == ["Eliminar", "Editar", "Observaciones"]
                return menu.actions()[index]
            from app.ui.widgets import courses_page
            class TestMenu(QMenu):
                def exec(self, pos):
                    return choose(self, pos)
            monkeypatch.setattr(courses_page, "QMenu", TestMenu)
            page.attendees_table.selectRow(0)
            pos = page.attendees_table.visualItemRect(page.attendees_table.item(1, 1)).center()
            page._show_attendees_context_menu(pos)
            assert calls[-1] == (expected, "z")
        page._show_attendees_context_menu(QPoint(-1, -1))
        assert len(calls) == 3
    finally:
        page.close()
        page.deleteLater()
        app.processEvents()


def test_consent_document_selection_scope_and_actions(monkeypatch) -> None:
    from app.ui.widgets import courses_page
    from app.ui.widgets.courses_page import ConsentimientosDialog

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(CoursesPage, "reload", lambda self: None)
    page = CoursesPage()
    calls = []
    monkeypatch.setattr(page, "_preview_signature_sheets", lambda scope, template: calls.append(("preview", scope, template)))
    monkeypatch.setattr(page, "_print_signature_sheets", lambda scope, template: calls.append(("print", scope, template)))

    monkeypatch.setattr(page, "_export_signature_sheets", lambda scope, template: calls.append(("export", scope, template)))

    class TestDialog(ConsentimientosDialog):
        def exec(self):
            assert self.selected_templates() == ["imagenes"]
            assert self.selected_scope() == "all"
            self.template_buttons["datos"].click()
            assert self.selected_templates() == ["imagenes", "datos"]
            self.scope_buttons["confirmed"].click()
            self.scope_buttons["selected"].click()
            assert self.selected_scope() == "selected"
            assert sum(button.isChecked() for button in self.scope_buttons.values()) == 1
            assert self.selected_templates() == ["imagenes", "datos"]
            self.preview_btn.click()
            self.print_btn.click()
            self.export_btn.click()
            for button, role in ((self.preview_btn, "primary"), (self.print_btn, "success"), (self.close_btn, "danger")):
                assert button.property("btnRole") == role
                assert not button.icon().isNull()
            self.template_buttons["imagenes"].click()
            self.template_buttons["datos"].click()
            assert not self.preview_btn.isEnabled()
            assert not self.print_btn.isEnabled()
            assert not self.export_btn.isEnabled()
            self.preview_btn.click()
            self.template_buttons["datos"].click()
            assert self.print_btn.isEnabled()
            self.close_btn.click()
            return self.result()

    monkeypatch.setattr(courses_page, "ConsentimientosDialog", TestDialog)
    try:
        page._open_consentimientos_manager()
        assert calls == [(action, "selected", template) for action in ("preview", "print", "export") for template in ("imagenes", "datos")]
    finally:
        page.close()
        page.deleteLater()
        app.processEvents()


def test_certificate_scope_is_exclusive_and_icons_are_white() -> None:
    from app.ui.widgets.courses_page import CertificadosDialog

    app = QApplication.instance() or QApplication([])
    dialog = CertificadosDialog()
    try:
        assert dialog.selected_scope() == "all"
        for scope in ("confirmed", "selected", "all"):
            dialog.scope_buttons[scope].click()
            assert dialog.selected_scope() == scope
            assert sum(button.isChecked() for button in dialog.scope_buttons.values()) == 1
        for button in (dialog.preview_btn, dialog.print_btn, dialog.export_btn, dialog.close_btn):
            pixels = button.icon().pixmap(18, 18).toImage()
            colors = [pixels.pixelColor(x, y) for x in range(pixels.width()) for y in range(pixels.height()) if pixels.pixelColor(x, y).alpha() > 0]
            assert colors
            assert all(color.red() == color.green() == color.blue() == 255 for color in colors)
        dialog.close_btn.click()
        assert dialog.result() == dialog.DialogCode.Accepted
    finally:
        dialog.deleteLater()
        app.processEvents()


def test_pdf_printing_stops_on_cancellation_or_failed_page_and_closes_pdf(monkeypatch) -> None:
    from app.ui.widgets import courses_page
    from PySide6.QtCore import QSizeF
    from PySide6.QtWidgets import QDialog

    for accepted, active, next_page, expected_pages, expected_end in (
        (False, True, True, 0, 0),
        (True, False, True, 0, 0),
        (True, True, False, 1, 1),
        (True, True, True, 3, 1),
    ):
        calls = []
        pdf = SimpleNamespace(
            load=lambda path: courses_page.QPdfDocument.Error.None_,
            pageCount=lambda: 3,
            render=lambda index, size: calls.append(("render", index)),
            close=lambda: calls.append(("close",)),
        )
        printer = SimpleNamespace(
            pageRect=lambda unit: SimpleNamespace(size=lambda: QSizeF(100, 200)),
            newPage=lambda: calls.append(("newPage",)) or next_page,
        )
        painter = SimpleNamespace(
            isActive=lambda: active,
            drawImage=lambda *args: calls.append(("draw",)),
            end=lambda: calls.append(("end",)),
        )
        pdf_error = courses_page.QPdfDocument.Error
        printer_mode = courses_page.QPrinter.PrinterMode
        printer_unit = courses_page.QPrinter.Unit
        # Factory classes keep the Qt enum attributes used by the printing helper.
        class PdfFactory:
            Error = pdf_error
            def __new__(cls):
                return pdf
        class PrinterFactory:
            PrinterMode = printer_mode
            Unit = printer_unit
            def __new__(cls, mode):
                return printer
        monkeypatch.setattr(courses_page, "QPdfDocument", PdfFactory)
        monkeypatch.setattr(courses_page, "QPrinter", PrinterFactory)
        monkeypatch.setattr(courses_page, "QPrintDialog", lambda *args: SimpleNamespace(exec=lambda: QDialog.DialogCode.Accepted if accepted else QDialog.DialogCode.Rejected))
        monkeypatch.setattr(courses_page, "QPainter", lambda device: calls.append(("begin",)) or painter)
        CoursesPage._print_pdf_file(SimpleNamespace(), "test.pdf")
        assert sum(call[0] == "render" for call in calls) == expected_pages
        assert sum(call[0] == "draw" for call in calls) == expected_pages
        assert sum(call[0] == "end" for call in calls) == expected_end
        assert sum(call[0] == "begin" for call in calls) == int(accepted)
        assert sum(call[0] == "newPage" for call in calls) == (0 if expected_pages == 0 else min(expected_pages, 2))
        assert calls[-1] == ("close",)


def test_certificate_print_uses_actual_pdf_dimensions(monkeypatch) -> None:
    from app.ui.widgets import courses_page
    from PySide6.QtCore import QSizeF
    from PySide6.QtWidgets import QDialog

    calls = []
    pdf = SimpleNamespace(
        load=lambda path: 0, pageCount=lambda: 1,
        pagePointSize=lambda index: QSizeF(595.32, 842.04),
        render=lambda index, size: calls.append(("render", size.width(), size.height())),
        close=lambda: calls.append(("close",)),
    )
    printer = SimpleNamespace(
        setPageSize=lambda size: calls.append(("paper", size.id())),
        setFullPage=lambda full: calls.append(("full", full)),
        resolution=lambda: 300,
        pageRect=lambda unit: SimpleNamespace(size=lambda: QSizeF(2200, 3200)),
    )
    painter = SimpleNamespace(isActive=lambda: True, drawImage=lambda *args: None, end=lambda: None)
    class PdfFactory:
        Error = SimpleNamespace(None_=0)
        def __new__(cls):
            return pdf
    class PrinterFactory:
        PrinterMode = courses_page.QPrinter.PrinterMode
        Unit = courses_page.QPrinter.Unit
        def __new__(cls, mode):
            return printer
    monkeypatch.setattr(courses_page, "QPdfDocument", PdfFactory)
    monkeypatch.setattr(courses_page, "QPrinter", PrinterFactory)
    monkeypatch.setattr(courses_page, "QPainter", lambda device: painter)
    monkeypatch.setattr(courses_page, "QPrintDialog", lambda *args: SimpleNamespace(exec=lambda: QDialog.DialogCode.Accepted))
    CoursesPage._print_pdf_file(SimpleNamespace(), "certificate.pdf", actual_size=True)
    assert ("full", True) in calls
    assert ("paper", courses_page.QPageSize.PageSizeId.A4) in calls
    assert ("render", 2481, 3508) in calls
    assert calls[-1] == ("close",)


def test_certificate_actions_use_assigned_technicians_and_actual_size() -> None:
    technicians = [SimpleNamespace(nombre_completo="Ana Pérez")]
    payloads = []
    page = SimpleNamespace(
        _selected_course=lambda: SimpleNamespace(curso_id="course"),
        _sorted_attendee_rows=lambda: [], _selected_attendee=lambda: None,
        service=SimpleNamespace(list_course_technicians=lambda course_id: technicians),
        course_document_generation_service=SimpleNamespace(
            generate_certificates_pdf=lambda *args, **kwargs: payloads.append(kwargs) or "certificate.pdf"),
    )
    assert CoursesPage._generate_certificates_pdf(page, "all") == "certificate.pdf"
    assert payloads[0]["technicians"] == technicians
    page._generate_certificates_pdf = lambda scope: "certificate.pdf"
    page._print_pdf_file = lambda path, **kwargs: payloads.append(kwargs)
    CoursesPage._print_certificates(page, "all")
    assert payloads[-1] == {"dialog_title": "Certificados", "actual_size": True}


def test_pdf_export_saves_selected_file_and_cancel_does_not_generate(monkeypatch, tmp_path) -> None:
    from app.ui.widgets import courses_page
    from PySide6.QtWidgets import QDialog

    source = tmp_path / "generated.pdf"
    source.write_bytes(b"%PDF-1.4\nexample")
    destination = tmp_path / "chosen.pdf"
    calls = []
    accepted = False
    class SaveDialog:
        AcceptMode = courses_page.QFileDialog.AcceptMode
        def __init__(self, *args):
            pass
        def setAcceptMode(self, mode):
            assert mode == self.AcceptMode.AcceptSave
        def setNameFilter(self, value):
            assert "*.pdf" in value
        def setDefaultSuffix(self, value):
            assert value == "pdf"
        def selectFile(self, value):
            assert value == "suggested.pdf"
        def exec(self):
            return QDialog.DialogCode.Accepted if accepted else QDialog.DialogCode.Rejected
        def selectedFiles(self):
            return [str(destination)]
    monkeypatch.setattr(courses_page, "QFileDialog", SaveDialog)
    monkeypatch.setattr(courses_page.QMessageBox, "information", lambda *args: calls.append("saved"))
    monkeypatch.setattr(courses_page.QMessageBox, "warning", lambda *args: calls.append("error"))
    def generate():
        calls.append("generated")
        return source
    CoursesPage._export_course_pdf(SimpleNamespace(), generate, "suggested.pdf")
    assert calls == []
    assert not destination.exists()
    accepted = True
    CoursesPage._export_course_pdf(SimpleNamespace(), generate, "suggested.pdf")
    assert destination.read_bytes() == source.read_bytes()
    assert calls == ["generated", "saved"]
    destination = source
    CoursesPage._export_course_pdf(SimpleNamespace(), generate, "suggested.pdf")
    assert calls[-1] == "saved"
    def fail():
        raise ValueError("No hay asistentes")
    CoursesPage._export_course_pdf(SimpleNamespace(), fail, "suggested.pdf")
    assert calls[-1] == "error"


def test_certificate_export_button_uses_selected_scope(monkeypatch) -> None:
    from app.ui.widgets import courses_page
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(CoursesPage, "reload", lambda self: None)
    page = CoursesPage()
    calls = []
    monkeypatch.setattr(page, "_export_certificates", lambda scope: calls.append(scope))
    class TestDialog(courses_page.CertificadosDialog):
        def exec(self):
            self.scope_buttons["confirmed"].click()
            self.export_btn.click()
            return self.DialogCode.Accepted
    monkeypatch.setattr(courses_page, "CertificadosDialog", TestDialog)
    try:
        page._open_certificados_manager()
        assert calls == ["confirmed"]
    finally:
        page.deleteLater()
        app.processEvents()
