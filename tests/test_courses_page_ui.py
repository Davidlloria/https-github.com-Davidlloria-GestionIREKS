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
            for button, role in ((self.preview_btn, "primary"), (self.print_btn, "success"), (self.close_btn, "danger")):
                assert button.property("btnRole") == role
                assert not button.icon().isNull()
            self.template_buttons["imagenes"].click()
            self.template_buttons["datos"].click()
            assert not self.preview_btn.isEnabled()
            assert not self.print_btn.isEnabled()
            self.preview_btn.click()
            self.template_buttons["datos"].click()
            assert self.print_btn.isEnabled()
            self.close_btn.click()
            return self.result()

    monkeypatch.setattr(courses_page, "ConsentimientosDialog", TestDialog)
    try:
        page._open_consentimientos_manager()
        assert calls == [(action, "selected", template) for action in ("preview", "print") for template in ("imagenes", "datos")]
    finally:
        page.close()
        page.deleteLater()
        app.processEvents()
