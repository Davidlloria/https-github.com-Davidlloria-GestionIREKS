"""Read-only product/reference snapshot for the IGSA monthly review."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import re

from sqlmodel import Session, select

from app.core.database import engine
from app.models import Distribuidor, IngredienteIreks, ReferenciaDistribuidor


def _key(value: object) -> str:
    return str(value if value is not None else "").strip().upper()


def historical_reference(reference: str, period: str) -> str:
    """Select the manufacturer's reference in force for an IGSA month."""
    code = _key(reference)
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", period):
        return code
    if code in {"275021", "27553", "127502E", "127553E"}:
        return "275021" if period < "2026-08" else "27553"
    if code in {"D1415185", "D1415178"}:
        return "D1415185" if period < "2026-05" else "D1415178"
    return code


@dataclass(frozen=True)
class ReviewProduct:
    product_id: str
    reference: str
    description: str


class IgsaMonthlyCatalog:
    def __init__(self, distributor_refs, products):
        self.products = {}
        self._conflicting_ids = set()
        dist = defaultdict(set)
        ireks = defaultdict(set)
        ireks_numeric = defaultdict(set)
        for product in products:
            product_id = _key(product.articulo_id)
            if not product_id:
                continue
            short = _key(product.articulo_referencia_corta)
            full = _key(product.articulo_referencia)
            candidate = ReviewProduct(product_id, short or full, str(product.articulo_descripcion or ""))
            if product_id in self.products and self.products[product_id] != candidate:
                self._conflicting_ids.add(product_id)
            self.products[product_id] = candidate
            for code in {short, full} - {""}:
                ireks[code].add(product_id)
                if code.isascii() and code.isdigit():
                    ireks_numeric[code.lstrip("0") or "0"].add(product_id)
        for ref in distributor_refs:
            code, product_id = _key(ref.articulo_referencia_distribuidor), _key(ref.articulo_id)
            if code and product_id:
                dist[code].add(product_id)
        by_reference = defaultdict(set)
        for product_id, product in self.products.items():
            if product.reference:
                by_reference[product.reference].add(product_id)
        self._shared_references = {}
        for reference, ids in by_reference.items():
            if len(ids) > 1 and not ids.intersection(self._conflicting_ids):
                shared = ReviewProduct(f"REFERENCIA:{reference}", reference, "")
                self.products[shared.product_id] = shared
                self._shared_references[reference] = shared
        self._dist = dist
        self._ireks = ireks
        self._ireks_numeric = ireks_numeric

    def _resolve(self, index, code):
        candidates = index.get(_key(code), set())
        if not candidates:
            return None, "referencia_no_encontrada"
        if len(candidates) != 1:
            references = {self.products[pid].reference for pid in candidates if pid in self.products}
            if len(references) == 1 and len(candidates) == sum(pid in self.products for pid in candidates):
                shared = self._shared_references.get(next(iter(references)))
                if shared is not None:
                    return shared, "referencia_compartida"
            return None, "referencia_ambigua"
        product_id = next(iter(candidates))
        if product_id in self._conflicting_ids:
            return None, "referencia_ambigua"
        product = self.products.get(product_id)
        if product is None or not product.reference:
            return None, "producto_sin_referencia"
        shared = self._shared_references.get(product.reference)
        if shared is not None:
            return shared, "referencia_compartida"
        return product, ""

    def distributor_product(self, reference, period=""):
        candidates = self._dist.get(_key(reference), set())
        if candidates and all(pid in self.products and pid not in self._conflicting_ids for pid in candidates):
            references = {self.products[pid].reference for pid in candidates}
            targets = {historical_reference(ref, period) for ref in references}
            if len(targets) == 1 and (len(references) > 1 or next(iter(targets)) not in references):
                return self.ireks_product(next(iter(targets)))
        return self._resolve(self._dist, reference)

    def ireks_product(self, reference):
        code = _key(reference)
        if code in self._ireks:
            return self._resolve(self._ireks, code)
        if code.isascii() and code.isdigit():
            return self._resolve(self._ireks_numeric, code.lstrip("0") or "0")
        return None, "referencia_no_encontrada"

    def is_ireks_zero_normalized(self, reference):
        code = _key(reference)
        return code not in self._ireks and code.isascii() and code.isdigit()


def load_igsa_monthly_catalog(db_engine=None) -> IgsaMonthlyCatalog:
    """Read a unique IGSA distributor and its product references; never write."""
    selected_engine = db_engine if db_engine is not None else engine
    database = selected_engine.url.database
    if selected_engine.url.get_backend_name() == "sqlite" and database not in (None, "", ":memory:") and not Path(database).is_file():
        raise ValueError("No existe la base de datos de GestionIREKS; no se puede consultar el catálogo.")
    with Session(selected_engine) as session:
        distributors = list(session.exec(select(Distribuidor)))
        matches = [d for d in distributors if any(
            re.search(r"(?<!\w)IGSA(?!\w)", _key(name)) for name in (d.distribuidor_nombre_comercial, d.distribuidor_razon_social)
        )]
        if len(matches) != 1:
            raise ValueError("No se ha identificado un único distribuidor IGSA en el catálogo.")
        refs = list(session.exec(select(ReferenciaDistribuidor).where(
            ReferenciaDistribuidor.distribuidor_id == matches[0].distribuidor_id
        )))
        products = list(session.exec(select(IngredienteIreks)))
        return IgsaMonthlyCatalog(refs, products)
