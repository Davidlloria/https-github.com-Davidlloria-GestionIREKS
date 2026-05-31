from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from app.services.import_service import ImportService
from app.services.order_document_import_service import OrderDocumentImportService


@dataclass
class OrdersDocumentPreviewData:
    header: dict[str, str]
    rows: list[dict[str, Any]]


@dataclass
class OrdersDocumentImportOutcome:
    ok: bool
    title: str
    message: str
    imported: int = 0
    errors_count: int = 0
    already_imported: bool = False


class OrdersDocumentsImportUiService:
    def __init__(
        self,
        import_service: ImportService | None = None,
        order_document_import_service: OrderDocumentImportService | None = None,
    ) -> None:
        self.import_service = import_service or ImportService()
        self.order_document_import_service = order_document_import_service or OrderDocumentImportService()

    def prepare_albaran_preview(
        self,
        source: Path,
        *,
        parse_pdf: Callable[[Path], tuple[dict[str, str], list[dict[str, Any]]]],
    ) -> OrdersDocumentPreviewData:
        clean_source = self._validate_source(source)
        if clean_source.suffix.lower() == ".pdf":
            header, rows = parse_pdf(clean_source)
        else:
            rows = self.import_service.map_rows(
                file_path=clean_source,
                schema=self._albaran_items_schema(),
                aliases=self._albaran_aliases(),
            )
            first = rows[0] if rows else {}
            header = {
                "albaran_numero": str(first.get("albaran_numero") or "").strip(),
                "albaran_fecha": str(first.get("albaran_fecha") or "").strip(),
                "fecha_pedido": "",
                "pedido_numero": str(first.get("pedido_numero") or "").strip(),
            }
        if not rows:
            raise ValueError("El archivo no contiene lineas para importar.")
        return OrdersDocumentPreviewData(header=header, rows=rows)

    def prepare_factura_preview(
        self,
        source: Path,
        *,
        parse_pdf: Callable[[Path], tuple[dict[str, str], list[dict[str, Any]]]],
    ) -> OrdersDocumentPreviewData:
        clean_source = self._validate_source(source)
        if clean_source.suffix.lower() == ".pdf":
            header, rows = parse_pdf(clean_source)
        else:
            rows = self.import_service.map_rows(
                file_path=clean_source,
                schema=self._factura_items_schema(),
                aliases=self._factura_aliases(),
            )
            first = rows[0] if rows else {}
            header = {
                "factura_numero": str(first.get("factura_numero") or "").strip(),
                "factura_fecha": str(first.get("factura_fecha") or "").strip(),
                "albaran_numero": str(first.get("albaran_numero") or "").strip(),
                "factura_referencia": str(first.get("factura_referencia") or "").strip(),
                "total_kilos": "",
                "importe_neto": "",
                "total_factura": "",
            }
        if not rows:
            raise ValueError("El archivo no contiene lineas para importar.")
        enriched_rows = self.order_document_import_service.enrich_factura_rows_from_tarifa(rows)
        return OrdersDocumentPreviewData(header=header, rows=enriched_rows)

    def import_albaran(
        self,
        *,
        pedido_id: str,
        header: dict[str, str],
        rows: list[dict[str, Any]],
    ) -> OrdersDocumentImportOutcome:
        result = self.order_document_import_service.import_albaran(pedido_id, header, rows)
        return self._to_outcome(
            result=result,
            already_title="Albaran ya importado",
            success_message_template="Lineas de albaran importadas: {imported}",
        )

    def import_factura(
        self,
        *,
        pedido_id: str,
        header: dict[str, str],
        rows: list[dict[str, Any]],
    ) -> OrdersDocumentImportOutcome:
        result = self.order_document_import_service.import_factura(pedido_id, header, rows)
        return self._to_outcome(
            result=result,
            already_title="Factura ya importada",
            success_message_template="Lineas de factura importadas: {imported}",
        )

    def _validate_source(self, source: Path) -> Path:
        clean_source = Path(source)
        if not clean_source.exists() or not clean_source.is_file():
            raise ValueError("El archivo seleccionado no existe.")
        if clean_source.suffix.lower() not in {".pdf", ".json", ".xlsx", ".xlsm", ".csv"}:
            raise ValueError("El archivo seleccionado debe ser .pdf, .json, .xlsx, .xlsm o .csv.")
        return clean_source

    def _to_outcome(
        self,
        *,
        result: Any,
        already_title: str,
        success_message_template: str,
    ) -> OrdersDocumentImportOutcome:
        imported = int(getattr(result, "imported", 0) or 0)
        errors = list(getattr(result, "errors", []) or [])
        already_imported = bool(getattr(result, "already_imported", False))
        message = str(getattr(result, "message", "") or "")
        if already_imported:
            return OrdersDocumentImportOutcome(
                ok=True,
                title=already_title,
                message=message,
                imported=imported,
                errors_count=len(errors),
                already_imported=True,
            )
        if errors:
            preview = "\n".join(errors[:8])
            extra = "" if len(errors) <= 8 else f"\n... y {len(errors) - 8} errores mas."
            return OrdersDocumentImportOutcome(
                ok=False,
                title="Importacion completada con incidencias",
                message=f"Registros importados: {imported}\nErrores: {len(errors)}\n\n{preview}{extra}",
                imported=imported,
                errors_count=len(errors),
                already_imported=False,
            )
        return OrdersDocumentImportOutcome(
            ok=True,
            title="Importacion completada",
            message=success_message_template.format(imported=imported),
            imported=imported,
            errors_count=0,
            already_imported=False,
        )

    @staticmethod
    def _albaran_items_schema() -> list[dict[str, str]]:
        return [
            {"name": "albaran_numero", "label": "Albaran_Numero"},
            {"name": "albaran_fecha", "label": "Albaran_Fecha"},
            {"name": "pedido_numero", "label": "Pedido_Numero"},
            {"name": "articulo_codigo", "label": "Codigo_Articulo"},
            {"name": "articulo_cantidad", "label": "Articulo_Cantidad"},
            {"name": "articulo_kilos", "label": "Kilos"},
            {"name": "articulo_lote", "label": "Articulo_Lote"},
            {"name": "articulo_caducidad", "label": "Articulo_Caducidad"},
        ]

    @staticmethod
    def _factura_items_schema() -> list[dict[str, str]]:
        return [
            {"name": "factura_numero", "label": "Factura_Numero"},
            {"name": "factura_fecha", "label": "Factura_Fecha"},
            {"name": "albaran_numero", "label": "Albaran_Numero"},
            {"name": "factura_referencia", "label": "Factura_Referencia"},
            {"name": "articulo_codigo", "label": "Codigo_Articulo"},
            {"name": "articulo_descripcion", "label": "Articulo_Descripcion"},
            {"name": "articulo_cantidad", "label": "Articulo_Cantidad"},
            {"name": "articulo_envase", "label": "Articulo_Envase"},
            {"name": "articulo_kilos", "label": "Kilos"},
            {"name": "articulo_lote", "label": "Articulo_Lote"},
            {"name": "articulo_caducidad", "label": "Articulo_Caducidad"},
            {"name": "precio_unitario", "label": "Precio_Unitario"},
            {"name": "dto_pct", "label": "Dto"},
            {"name": "iva_pct", "label": "IVA"},
            {"name": "total_linea", "label": "Total"},
        ]

    @staticmethod
    def _albaran_aliases() -> dict[str, list[str]]:
        return {
            "albaran_numero": ["numero", "albaran", "numero_albaran", "pedido_albaran_numero"],
            "albaran_fecha": ["fecha_packing", "fecha", "fecha_albaran", "pedido_fecha", "fecha_pedido"],
            "pedido_numero": ["nº_pedido", "n_pedido", "numero_pedido", "pedido_numero"],
            "articulo_codigo": ["codigo_articulo", "articuloid", "id_articulo", "articulo_id", "cod", "codigo"],
            "articulo_cantidad": ["envases", "cantidad", "uds", "unidades", "qty", "articulo_cantidad"],
            "articulo_kilos": ["kilos", "kg"],
            "articulo_lote": ["lote", "articulo_lote"],
            "articulo_caducidad": ["caduca", "caducidad", "articulo_caducidad", "fecha_caducidad"],
        }

    @staticmethod
    def _factura_aliases() -> dict[str, list[str]]:
        return {
            "factura_numero": ["numero", "factura", "numero_factura", "pedido_factura_numero"],
            "factura_fecha": ["fecha", "fecha_factura", "pedido_fecha", "fecha_pedido"],
            "albaran_numero": ["albaran", "numero_albaran", "pedido_albaran_numero"],
            "factura_referencia": ["referencia", "ref"],
            "articulo_codigo": ["codigo_articulo", "articuloid", "id_articulo", "articulo_id", "cod", "codigo"],
            "articulo_descripcion": ["descripcion", "nombre", "articulo_descripcion"],
            "articulo_cantidad": ["uds", "cantidad", "unidades", "qty", "articulo_cantidad"],
            "articulo_envase": ["env", "envase", "articulo_envase"],
            "articulo_kilos": ["kilos", "kg", "kg_lit", "articulo_kilos"],
            "articulo_lote": ["lote", "articulo_lote"],
            "articulo_caducidad": ["caduca", "caducidad", "articulo_caducidad", "fecha_caducidad"],
            "precio_unitario": ["precio", "precio_unitario"],
            "dto_pct": ["dto", "descuento", "descuento_pct"],
            "iva_pct": ["iva", "iva_pct"],
            "total_linea": ["total", "importe", "total_linea"],
        }
