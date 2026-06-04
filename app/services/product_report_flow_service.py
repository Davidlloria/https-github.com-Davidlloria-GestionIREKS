from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from app.services.product_report_service import (
    ProductReportIntent,
    ProductReportIntentService,
    ProductReportResult,
    ProductReportService,
)


@dataclass
class ProductReportFlowResult:
    status: str
    message: str = ""
    prompt: str = ""
    used_ai: bool = False
    intent: ProductReportIntent = field(default_factory=ProductReportIntent)
    report: ProductReportResult | None = None


class ProductReportFlowService:
    def __init__(
        self,
        *,
        intent_service: ProductReportIntentService | None = None,
        report_service: ProductReportService | None = None,
    ) -> None:
        self.intent_service = intent_service or ProductReportIntentService()
        self.report_service = report_service or ProductReportService()

    def generate_report(
        self,
        prompt: str,
        *,
        selected_product_ids: Iterable[int] | None = None,
    ) -> ProductReportFlowResult:
        text = str(prompt or "").strip()
        if not text:
            return ProductReportFlowResult(status="empty_prompt", message="Escribe que listado necesitas.")

        intent_result = self.intent_service.parse(text)
        if not intent_result.ok:
            return ProductReportFlowResult(
                status="parse_error",
                message=intent_result.message,
                prompt=text,
                used_ai=bool(intent_result.used_ai),
                intent=intent_result.intent,
            )

        intent = intent_result.intent
        if "seleccionad" in text.lower():
            selected_ids = self._clean_selected_ids(selected_product_ids or [])
            if not selected_ids:
                return ProductReportFlowResult(
                    status="no_selection",
                    message="No hay productos seleccionados en la lista.",
                    prompt=text,
                    used_ai=bool(intent_result.used_ai),
                    intent=intent,
                )
            intent.selected_ids = selected_ids

        try:
            report = self.report_service.run(intent)
        except Exception as exc:  # noqa: BLE001
            return ProductReportFlowResult(
                status="error",
                message=f"No se pudo generar el listado.\n{exc}",
                prompt=text,
                used_ai=bool(intent_result.used_ai),
                intent=intent,
            )

        return ProductReportFlowResult(
            status="ready",
            message=intent_result.message or "",
            prompt=text,
            used_ai=bool(intent_result.used_ai),
            intent=intent,
            report=report,
        )

    @staticmethod
    def _clean_selected_ids(selected_product_ids: Iterable[int]) -> list[int]:
        cleaned: list[int] = []
        seen: set[int] = set()
        for raw in selected_product_ids:
            try:
                item_id = int(raw or 0)
            except Exception:
                continue
            if item_id <= 0 or item_id in seen:
                continue
            seen.add(item_id)
            cleaned.append(item_id)
        return sorted(cleaned)
