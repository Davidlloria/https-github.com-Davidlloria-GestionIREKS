from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class OrderDocumentFacturaSidecarService:
    def load_rows(
        self,
        pdf_path: str | Path,
        factura_numero: str,
        header: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        file_path = Path(pdf_path)
        factura_numero = str(factura_numero or "").strip()
        header = dict(header or {})
        if not factura_numero:
            return []

        rows: list[dict[str, Any]] = []
        for json_path in sorted(file_path.parent.glob("*.json")):
            if factura_numero not in json_path.name:
                continue
            try:
                payload = json.loads(json_path.read_text(encoding="utf-8-sig"))
            except Exception:
                continue
            if not isinstance(payload, list):
                continue
            for entry in payload:
                if not isinstance(entry, dict):
                    continue
                entry_factura = str(self._factura_sidecar_value(entry, ["Factura", "factura_numero"]) or "").strip()
                if entry_factura and entry_factura != factura_numero:
                    continue
                codigo = str(self._factura_sidecar_value(entry, ["CÃ³digo", "Codigo", "CÃƒÂ³digo", "articulo_codigo"]) or "").strip()
                lote = str(self._factura_sidecar_value(entry, ["Lote", "articulo_lote"]) or "").strip()
                if not codigo or not lote:
                    continue
                rows.append(
                    {
                        "factura_numero": factura_numero,
                        "factura_fecha": str(
                            self._factura_sidecar_value(entry, ["Fecha", "factura_fecha"]) or header.get("factura_fecha") or ""
                        ).strip(),
                        "albaran_numero": str(
                            self._factura_sidecar_value(entry, ["AlbarÃ¡n", "Albaran", "AlbarÃƒÂ¡n", "albaran_numero"])
                            or header.get("albaran_numero")
                            or ""
                        ).strip(),
                        "factura_referencia": str(header.get("factura_referencia") or "").strip(),
                        "articulo_codigo": codigo,
                        "articulo_descripcion": str(
                            self._factura_sidecar_value(entry, ["DescripciÃ³n", "Descripcion", "DescripciÃƒÂ³n", "articulo_descripcion"])
                            or codigo
                        ).strip(),
                        "articulo_cantidad": str(
                            self._factura_sidecar_value(entry, ["Unidades", "Uds", "articulo_cantidad"]) or ""
                        ).strip(),
                        "articulo_envase": "",
                        "articulo_kilos": "",
                        "articulo_lote": lote,
                        "articulo_caducidad": str(
                            self._factura_sidecar_value(entry, ["Caducidad", "articulo_caducidad"]) or ""
                        ).strip(),
                        "precio_unitario": str(
                            self._factura_sidecar_value(entry, ["Precio", "precio_unitario"]) or ""
                        ).strip(),
                        "dto_pct": str(self._factura_sidecar_value(entry, ["Descuento", "Dto", "dto_pct"]) or "20").strip(),
                        "iva_pct": "",
                        "total_linea": "",
                    }
                )
            if rows:
                return rows
        return rows

    @staticmethod
    def _factura_sidecar_value(payload: dict[str, Any], names: list[str]) -> Any:
        normalized = {re.sub(r"[^a-z0-9]", "", str(key).lower()): value for key, value in payload.items()}
        for name in names:
            key = re.sub(r"[^a-z0-9]", "", name.lower())
            if key in normalized:
                return normalized[key]
        return ""
