from __future__ import annotations

from app.services.document_catalog_refresh_service import DocumentCatalogRefreshService
from app.services.document_library_service import DocumentLibraryScanResult
from app.services.document_product_link_service import DocumentProductLinkSyncResult


class _LibraryService:
    def __init__(self, result: DocumentLibraryScanResult) -> None:
        self.result = result
        self.calls = 0

    def refresh_catalog(self) -> DocumentLibraryScanResult:
        self.calls += 1
        return self.result


class _ProductLinkService:
    def __init__(
        self,
        result: DocumentProductLinkSyncResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result or DocumentProductLinkSyncResult()
        self.error = error
        self.calls = 0

    def sync_technical_sheets(self) -> DocumentProductLinkSyncResult:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.result


def test_complete_catalog_refresh_synchronizes_product_links() -> None:
    catalog = _LibraryService(
        DocumentLibraryScanResult(available=True, scan_complete=True, added=2)
    )
    expected_links = DocumentProductLinkSyncResult(
        technical_documents=10,
        linked=8,
        created=3,
        unchanged=5,
        unmatched=2,
    )
    product_links = _ProductLinkService(expected_links)

    result = DocumentCatalogRefreshService(catalog, product_links).refresh_catalog()

    assert catalog.calls == product_links.calls == 1
    assert result.added == 2
    assert result.product_links == expected_links
    assert result.product_link_error == ""


def test_unavailable_or_incomplete_catalog_does_not_synchronize_product_links() -> None:
    product_links = _ProductLinkService()
    unavailable = _LibraryService(
        DocumentLibraryScanResult(available=False, scan_complete=False)
    )
    incomplete = _LibraryService(
        DocumentLibraryScanResult(
            available=True,
            scan_complete=False,
            errors=("sin acceso",),
        )
    )

    unavailable_result = DocumentCatalogRefreshService(
        unavailable, product_links
    ).refresh_catalog()
    incomplete_result = DocumentCatalogRefreshService(
        incomplete, product_links
    ).refresh_catalog()

    assert product_links.calls == 0
    assert unavailable_result.product_links is None
    assert incomplete_result.product_links is None
    assert incomplete_result.errors == ("sin acceso",)


def test_product_link_error_preserves_successful_catalog_result() -> None:
    catalog = _LibraryService(
        DocumentLibraryScanResult(available=True, scan_complete=True, updated=4)
    )
    product_links = _ProductLinkService(error=RuntimeError("productos no disponibles"))

    result = DocumentCatalogRefreshService(catalog, product_links).refresh_catalog()

    assert result.updated == 4
    assert result.product_links is None
    assert result.product_link_error == "productos no disponibles"
    assert product_links.calls == 1
