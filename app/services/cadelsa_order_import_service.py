from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from math import isclose
from pathlib import Path
import re
from uuid import uuid4

import fitz
from sqlmodel import Session, select

from app.core.database import engine
from app.models import Cliente, Distribuidor, IngredienteIreks, Pedido, ReferenciaDistribuidor
from app.services.order_service import OrderLineInput, OrderService


@dataclass(frozen=True)
class CadelsaLine:
    code: str
    description: str
    units: float
    weight_kg: float


@dataclass(frozen=True)
class CadelsaResolvedLine:
    source: CadelsaLine
    article_id: str
    reference: str
    name: str
    issue: str = ""


@dataclass(frozen=True)
class CadelsaPreview:
    client_id: str
    source_ref: str
    lines: tuple[CadelsaResolvedLine, ...]


class CadelsaOrderImportService:
    """Importación del formato de pedido CADELSA, sin OCR ni efectos en la vista previa."""

    @staticmethod
    def is_cadelsa_client(client: Cliente | None) -> bool:
        return bool(
            client
            and client.activo
            and client.cliente_nombre_comercial.strip().upper() == "CADELSA LZA"
            and client.cliente_tipo.strip().lower() in {"directo", "cliente directo", "cliente_directo"}
        )

    @staticmethod
    def _code(value: str) -> str:
        clean = value.strip().upper()
        return (clean.lstrip("0") or "0") if clean.isdigit() else clean

    @staticmethod
    def parse_text(text: str) -> tuple[CadelsaLine, ...]:
        upper = text.upper()
        if not all(marker in upper for marker in ("CADELSA", "LANZAROTE", "CANTIDAD FMT", "CANTIDAD U.B.")):
            raise ValueError("El PDF no tiene el formato de pedido CADELSA Lanzarote.")
        body = upper.split("CANTIDAD U.B.", 1)[1].split("PIE PEDIDO", 1)[0]
        # Una referencia abre cada registro; el texto PDF puede separar las columnas en líneas.
        starts = list(re.finditer(r"(?m)^\s*(\d{8})\b", body))
        if not starts:
            raise ValueError("No se encontraron artículos en el PDF. Se requiere un PDF con texto.")
        prefix = body[:starts[0].start()]
        if prefix.strip("- \r\n\t"):
            raise ValueError("Hay contenido no reconocido antes de los artículos.")
        lines: list[CadelsaLine] = []
        number = r"\d+(?:\.\d{3})*(?:,\d+)?"
        pattern = re.compile(rf"(\d{{8}})\s+(.+?)\s+({number})\s+UNI\s+({number})")
        for index, start in enumerate(starts):
            end = starts[index + 1].start() if index + 1 < len(starts) else len(body)
            block = " ".join(body[start.start():end].split())
            match = pattern.fullmatch(block)
            if match is None or len(re.findall(r"\bUNI\b", block)) != 1:
                raise ValueError(f"Línea no reconocida: {start.group(1)}. No se ha importado nada.")
            code, description, qty, base_qty = match.groups()
            units = float(qty.replace(".", "").replace(",", "."))
            base_units = float(base_qty.replace(".", "").replace(",", "."))
            weight = re.search(r"(\d+(?:[,.]\d+)?)\s*(KG|K|G)\s*$", description)
            if units <= 0 or units != base_units or weight is None:
                raise ValueError(f"Cantidad o formato no válido en {code}.")
            kg = float(weight.group(1).replace(",", ".")) / (1000 if weight.group(2) == "G" else 1)
            if kg <= 0:
                raise ValueError(f"Peso no válido en {code}.")
            lines.append(CadelsaLine(code, description, units, kg))
        return tuple(lines)

    def _resolve(self, session: Session, lines: tuple[CadelsaLine, ...]) -> tuple[CadelsaResolvedLine, ...]:
        distributors = list(session.exec(select(Distribuidor)))
        igsa_ids = {d.distribuidor_id for d in distributors if d.distribuidor_nombre_comercial.strip().upper() == "IGSA"}
        if len(igsa_ids) != 1:
            raise ValueError("Debe existir un único distribuidor IGSA para resolver las referencias.")
        refs = list(session.exec(select(ReferenciaDistribuidor).where(ReferenciaDistribuidor.distribuidor_id.in_(igsa_ids))))
        products = list(session.exec(select(IngredienteIreks)))
        resolved: list[CadelsaResolvedLine] = []
        for line in lines:
            ids = {r.articulo_id for r in refs if self._code(r.articulo_referencia_distribuidor) == self._code(line.code)}
            matches = [p for p in products if p.articulo_id in ids]
            if len(ids) != 1 or len(matches) != 1:
                resolved.append(CadelsaResolvedLine(line, "", "", "", "Equivalencia IGSA inexistente o ambigua"))
                continue
            product = matches[0]
            issue = ""
            if not product.articulo_status_activo:
                issue = "Producto inactivo"
            elif not isclose(float(product.articulo_envase_peso_total or 0), line.weight_kg, abs_tol=0.0001):
                issue = f"Envase distinto: ficha {product.articulo_envase_peso_total:g} kg / PDF {line.weight_kg:g} kg"
            resolved.append(CadelsaResolvedLine(line, product.articulo_id, product.articulo_referencia, product.articulo_descripcion, issue))
        return tuple(resolved)

    def preview(self, path: Path, client_id: str) -> CadelsaPreview:
        if path.suffix.lower() != ".pdf":
            raise ValueError("Selecciona un archivo PDF.")
        data = path.read_bytes()
        with fitz.open(stream=data, filetype="pdf") as document:
            # Procesar cada página evita mezclar cabeceras repetidas con las líneas.
            lines = tuple(line for page in document for line in self.parse_text(page.get_text()))
        source_ref = "CADELSA-PDF:" + sha256(data).hexdigest()
        with Session(engine) as session:
            if not self.is_cadelsa_client(session.get(Cliente, client_id)):
                raise ValueError("Selecciona el cliente directo CADELSA LZA.")
            if session.exec(select(Pedido).where(Pedido.almacen_id == client_id, Pedido.pedido_ref == source_ref)).first():
                raise ValueError("Este PDF ya se ha importado para CADELSA LZA.")
            return CadelsaPreview(client_id, source_ref, self._resolve(session, lines))

    def save(self, preview: CadelsaPreview, order_date: date) -> str:
        with Session(engine) as session:
            if not self.is_cadelsa_client(session.get(Cliente, preview.client_id)):
                raise ValueError("Selecciona el cliente directo CADELSA LZA.")
            current = self._resolve(session, tuple(row.source for row in preview.lines))
            if not current or any(row.issue for row in current) or current != preview.lines:
                raise ValueError("Hay incidencias o cambios en los productos. Vuelve a abrir la vista previa.")
        totals: dict[str, float] = {}
        for row in current:
            totals[row.article_id] = totals.get(row.article_id, 0) + row.source.units
        return OrderService().create_order(
            almacen_id=preview.client_id,
            pedido_fecha=order_date,
            pedido_numero="CAD-" + uuid4().hex.upper(),
            lines=[OrderLineInput(article_id, units) for article_id, units in totals.items()],
            pedido_ref=preview.source_ref,
        )
