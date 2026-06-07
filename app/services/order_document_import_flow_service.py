from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(slots=True)
class OrderDocumentImportGateResult:
    status: str = "ready"
    message: str = ""
    existing_document_id: str = ""

    @property
    def already_imported(self) -> bool:
        return self.status == "already_imported"


class OrderDocumentImportFlowService:
    def resolve_albaran_gate(
        self,
        *,
        pedido_id: str,
        preview_header: dict[str, str],
        find_existing_albaran: Callable[[str, str], Any | None],
        repair_existing_albaran: Callable[[str], None],
    ) -> OrderDocumentImportGateResult:
        return self._resolve_duplicate_gate(
            pedido_id=pedido_id,
            document_number=self._clean_text(preview_header.get("albaran_numero")),
            find_existing_document=find_existing_albaran,
            get_existing_document_id=lambda existing: self._clean_text(getattr(existing, "albaran_id", "")),
            repair_existing_document=repair_existing_albaran,
            duplicate_message=lambda number: (
                f"El albaran {number} ya estaba importado para este pedido.\n"
                "No se han creado lineas duplicadas. Se han revisado las equivalencias y entradas de almacen existentes."
            ),
        )

    def resolve_factura_gate(
        self,
        *,
        pedido_id: str,
        preview_header: dict[str, str],
        find_existing_factura: Callable[[str, str], Any | None],
    ) -> OrderDocumentImportGateResult:
        return self._resolve_duplicate_gate(
            pedido_id=pedido_id,
            document_number=self._clean_text(preview_header.get("factura_numero")),
            find_existing_document=find_existing_factura,
            get_existing_document_id=lambda existing: self._clean_text(getattr(existing, "factura_id", "")),
            repair_existing_document=None,
            duplicate_message=lambda number: (
                f"La factura {number} ya estaba importada para este pedido. No se han creado líneas duplicadas."
            ),
        )

    def _resolve_duplicate_gate(
        self,
        *,
        pedido_id: str,
        document_number: str,
        find_existing_document: Callable[[str, str], Any | None],
        get_existing_document_id: Callable[[Any], str],
        duplicate_message: Callable[[str], str],
        repair_existing_document: Callable[[str], None] | None,
    ) -> OrderDocumentImportGateResult:
        clean_pedido_id = self._clean_text(pedido_id)
        clean_document_number = self._clean_text(document_number)
        if not clean_pedido_id or not clean_document_number:
            return OrderDocumentImportGateResult()

        existing_document = find_existing_document(clean_pedido_id, clean_document_number)
        if existing_document is None:
            return OrderDocumentImportGateResult()

        existing_document_id = self._clean_text(get_existing_document_id(existing_document))
        if repair_existing_document is not None:
            repair_existing_document(existing_document_id)

        return OrderDocumentImportGateResult(
            status="already_imported",
            message=duplicate_message(clean_document_number),
            existing_document_id=existing_document_id,
        )

    @staticmethod
    def _clean_text(value: object) -> str:
        return str(value or "").strip()
