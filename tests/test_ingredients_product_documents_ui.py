from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication, QDialog

import app.ui.widgets.ingredients_page as page_module
from app.services.document_product_link_service import ProductDocumentItem
from app.ui.widgets.ingredients_page import IngredientsIreksPage


def _application() -> QApplication:
    return QApplication.instance() or QApplication([])


def _document() -> ProductDocumentItem:
    return ProductDocumentItem(
        document_id="document-1",
        name="IREKS Ficha 14715.pdf",
        relative_path="FICHAS TECNICAS/IREKS/IREKS Ficha 14715.pdf",
        area="FICHAS TECNICAS",
        category="IREKS",
        extension=".pdf",
        modified_at="2026-08-29T11:30:00+00:00",
        relation_type="technical_sheet",
        origin="automatic_filename",
    )


class _FakeLinkService:
    def __init__(self, documents: list[ProductDocumentItem]) -> None:
        self.documents = documents
        self.product_ids: list[str] = []

    def list_product_documents(self, product_articulo_id: str):
        self.product_ids.append(product_articulo_id)
        return self.documents


class _FakeLibraryService:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.resolved_ids: list[str] = []

    def resolve_document(self, document_id: str) -> Path:
        self.resolved_ids.append(document_id)
        return self.path


class _FakeWhatsAppService:
    def __init__(self) -> None:
        self.urls: list[tuple[str, str]] = []
        self.revealed: list[Path] = []

    def build_chat_url(self, phone: str, message: str) -> str:
        self.urls.append((phone, message))
        return "https://wa.me/34600123456?text=ficha"

    def reveal_file(self, path: Path) -> bool:
        self.revealed.append(path)
        return True


def _page(monkeypatch, tmp_path: Path, documents=None):
    monkeypatch.setattr(IngredientsIreksPage, "reload", lambda self: None)
    links = _FakeLinkService(documents if documents is not None else [_document()])
    library = _FakeLibraryService(tmp_path / "IREKS Ficha 14715.pdf")
    whatsapp = _FakeWhatsAppService()
    page = IngredientsIreksPage(
        document_product_link_service=links,  # type: ignore[arg-type]
        document_library_service=library,  # type: ignore[arg-type]
        whatsapp_share_service=whatsapp,  # type: ignore[arg-type]
    )
    return page, links, library, whatsapp


def test_product_documents_tab_lists_and_opens_related_sheet(
    monkeypatch,
    tmp_path: Path,
) -> None:
    app = _application()
    page, links, library, _whatsapp = _page(monkeypatch, tmp_path)
    opened_urls: list[QUrl] = []
    monkeypatch.setattr(
        page_module.QDesktopServices,
        "openUrl",
        lambda url: opened_urls.append(url) or True,
    )

    page._reload_product_documents("product-1")
    app.processEvents()

    assert links.product_ids == ["product-1"]
    assert page.detail_tabs.tabText(page._documents_tab_index) == "Documentos"
    assert page.product_documents_table.rowCount() == 1
    assert page.product_documents_table.item(0, 0).text() == _document().name
    assert page.product_documents_table.item(0, 1).text() == "Ficha técnica"
    assert page.product_documents_table.item(0, 2).text() == "IREKS"
    assert page.product_document_open_button.isEnabled()

    page.product_document_open_button.click()

    assert library.resolved_ids == ["document-1"]
    assert [Path(url.toLocalFile()) for url in opened_urls] == [library.path]
    page.close()


def test_product_document_whatsapp_prepares_selected_sheet(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _application()
    page, _links, library, whatsapp = _page(monkeypatch, tmp_path)

    class _AcceptedDialog:
        def __init__(self, document_name, service, parent) -> None:
            assert document_name == _document().name
            assert service is whatsapp
            assert parent is page
            self.normalized_phone = "34600123456"
            self.message = "Te envío la ficha técnica."

        def exec(self):
            return QDialog.DialogCode.Accepted

    opened_urls: list[QUrl] = []
    monkeypatch.setattr(page_module, "WhatsAppShareDialog", _AcceptedDialog)
    monkeypatch.setattr(
        page_module.QDesktopServices,
        "openUrl",
        lambda url: opened_urls.append(url) or True,
    )
    page._reload_product_documents("product-1")

    assert page.product_document_whatsapp_button.text() == "WhatsApp"
    assert page.product_document_whatsapp_button.isEnabled()
    page.product_document_whatsapp_button.click()

    assert library.resolved_ids == ["document-1"]
    assert whatsapp.revealed == [library.path]
    assert whatsapp.urls == [("34600123456", "Te envío la ficha técnica.")]
    assert [url.toString() for url in opened_urls] == [
        "https://wa.me/34600123456?text=ficha"
    ]
    assert "Arrastra el documento" in page.product_documents_status.text()
    page.close()


def test_product_documents_tab_has_a_clear_empty_state(monkeypatch, tmp_path: Path) -> None:
    _application()
    page, links, _library, _whatsapp = _page(monkeypatch, tmp_path, documents=[])

    page._reload_product_documents("product-without-sheet")

    assert links.product_ids == ["product-without-sheet"]
    assert page.product_documents_table.rowCount() == 0
    assert "No hay fichas técnicas" in page.product_documents_empty.text()
    assert not page.product_document_open_button.isEnabled()
    assert not page.product_document_whatsapp_button.isEnabled()
    page.close()
