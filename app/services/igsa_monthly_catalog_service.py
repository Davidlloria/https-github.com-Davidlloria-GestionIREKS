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
        for ref in distributor_refs:
            code, product_id = _key(ref.articulo_referencia_distribuidor), _key(ref.articulo_id)
            if code and product_id:
                dist[code].add(product_id)
        self._dist = dist
        self._ireks = ireks

    def _resolve(self, index, code):
        candidates = index.get(_key(code), set())
        if not candidates:
            return None, "referencia_no_encontrada"
        if len(candidates) != 1:
            return None, "referencia_ambigua"
        product_id = next(iter(candidates))
        if product_id in self._conflicting_ids:
            return None, "referencia_ambigua"
        product = self.products.get(product_id)
        if product is None or not product.reference:
            return None, "producto_sin_referencia"
        return product, ""

    def distributor_product(self, reference):
        return self._resolve(self._dist, reference)

    def ireks_product(self, reference):
        return self._resolve(self._ireks, reference)


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
