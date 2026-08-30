from __future__ import annotations

from dataclasses import replace

from app.services.document_library_service import (
    DocumentLibraryScanResult,
    DocumentLibraryService,
)
from app.services.document_product_link_service import DocumentProductLinkService


class DocumentCatalogRefreshService:
    """Refresh the catalog and then synchronize its derived product links."""

    def __init__(
        self,
        library_service: DocumentLibraryService | None = None,
        product_link_service: DocumentProductLinkService | None = None,
    ) -> None:
        self.library_service = library_service or DocumentLibraryService()
        self.product_link_service = product_link_service or DocumentProductLinkService(
            document_database_path=self.library_service.database_path
        )

    def refresh_catalog(self) -> DocumentLibraryScanResult:
        result = self.library_service.refresh_catalog()
        if not result.available or not result.scan_complete:
            return result
        try:
            product_links = self.product_link_service.sync_technical_sheets()
        except Exception as exc:  # noqa: BLE001
            return replace(
                result,
                product_link_error=(
                    str(exc) or "Error desconocido al relacionar documentos y productos."
                ),
            )
        return replace(result, product_links=product_links)
