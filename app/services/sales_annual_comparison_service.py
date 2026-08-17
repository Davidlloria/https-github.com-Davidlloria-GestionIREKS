from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import re
import unicodedata

from sqlmodel import Session, col, select

from app.core.database import engine
from app.models import (
    Cliente,
    Distribuidor,
    Fabricante,
    Familia,
    IngredienteIreks,
    Isla,
    ReferenciaDistribuidor,
    Subfamilia,
    VentaClientesRaw,
    VentaMensualRaw,
)
from app.services.sales_text_normalizer import normalize_search_text


SALES_CLIENT_TYPES = {"distribuidor", "directo", "cliente directo", "cliente_directo"}


@dataclass
class SalesComparisonRow:
    articulo_id: str
    fabricante_id: str
    familia_id: str
    subfamilia_id: str
    codigo: str
    nombre: str
    kilos_prev: float
    sc_prev: float
    ventas_prev: float
    kilos_curr: float
    sc_curr: float
    ventas_curr: float
    delta_kg: float
    delta_kg_pct: float
    delta_ventas: float
    delta_ventas_pct: float


@dataclass
class SalesMonthlyPoint:
    month: int
    kilos: float


@dataclass
class SalesMonthlyComparisonPoint:
    month: int
    kilos_prev: float
    kilos_curr: float


@dataclass
class SalesDetailRow:
    periodo: str
    cliente_id: str
    cliente_nombre: str
    articulo_id: str
    codigo: str
    nombre: str
    fabricante_id: str
    familia_id: str
    subfamilia_id: str
    kilos: float
    sc: float
    ventas: float


@dataclass
class SalesClientsComparisonRow:
    articulo_id: str
    fabricante_id: str
    familia_id: str
    subfamilia_id: str
    codigo: str
    nombre: str
    unidades_prev: float
    kg_prev: float
    euros_prev: float
    unidades_curr: float
    kg_curr: float
    euros_curr: float
    delta_unidades: float
    delta_unidades_pct: float
    delta_kg: float
    delta_kg_pct: float
    delta_euros: float
    delta_euros_pct: float


@dataclass
class SalesClientProductConsumerRow:
    cliente_id: str
    cliente_codigo: str
    cliente_nombre: str
    kg_prev: float
    euros_prev: float
    kg_curr: float
    euros_curr: float
    delta_kg: float
    delta_euros: float
    unidades_curr: float = 0.0
    ultimo_periodo: str = ""


@dataclass
class SalesCustomerAnnualComparisonRow:
    cliente_id: str
    cliente_codigo: str
    cliente_nombre: str
    kg_prev: float
    kg_curr: float
    delta_kg: float
    delta_kg_pct: float


@dataclass
class SalesCustomerAnnualSalesRow:
    cliente_id: str
    isla: str
    cliente_codigo: str
    cliente_nombre: str
    cliente_tipo: str
    kg: float


class SalesAnnualComparisonService:
    def __init__(self, db_engine=None) -> None:
        self._engine = db_engine if db_engine is not None else engine

    def _code_candidates(self, code: object) -> list[str]:
        base = self._normalize_code(code)
        clean = re.sub(r"\s+", "", str(base or "").upper())
        if not clean:
            return []
        out = [clean]
        if clean.startswith("D") and clean[1:].isdigit():
            out.append(clean[1:])
        elif clean.isdigit():
            out.append(f"D{clean}")
        return list(dict.fromkeys(out))

    def list_years(self) -> list[int]:
        with Session(self._engine) as session:
            periods = list(session.exec(select(VentaMensualRaw.periodo)))
        return sorted(
            {
                int(str(period or "").split("-")[0])
                for period in periods
                if str(period or "").count("-") == 1 and str(period or "").split("-")[0].isdigit()
            },
            reverse=True,
        )

    def list_years_igsa(self) -> list[int]:
        with Session(self._engine) as session:
            periods = list(
                session.exec(
                    select(VentaMensualRaw.periodo).where(col(VentaMensualRaw.fuente).in_(["igsa", "igsa_pdf", "igsa_book"]))
                )
            )
        return sorted(
            {
                int(str(period or "").split("-")[0])
                for period in periods
                if str(period or "").count("-") == 1 and str(period or "").split("-")[0].isdigit()
            },
            reverse=True,
        )

    def list_years_clientes(self) -> list[int]:
        with Session(self._engine) as session:
            years = list(session.exec(select(VentaClientesRaw.anio)))
        return sorted(
            {
                int(year or 0)
                for year in years
                if 1900 <= int(year or 0) <= 2100
            },
            reverse=True,
        )

    def list_filter_clients(self) -> list[Cliente]:
        with Session(self._engine) as session:
            rows = list(session.exec(select(Cliente).order_by(Cliente.cliente_nombre_comercial, Cliente.cliente_nombre_fiscal)))
        result: list[Cliente] = []
        for row in rows:
            tipo = str(getattr(row, "cliente_tipo", "") or "").strip().lower()
            if tipo in SALES_CLIENT_TYPES:
                result.append(row)
        return result

    def list_filter_clients_indirect(self) -> list[Cliente]:
        with Session(self._engine) as session:
            rows = list(session.exec(select(Cliente).order_by(Cliente.cliente_nombre_comercial, Cliente.cliente_nombre_fiscal)))
        excluded = SALES_CLIENT_TYPES
        result: list[Cliente] = []
        for row in rows:
            tipo = str(getattr(row, "cliente_tipo", "") or "").strip().lower()
            if tipo not in excluded:
                result.append(row)
        return result

    def list_filter_products(self) -> list[IngredienteIreks]:
        with Session(self._engine) as session:
            return list(
                session.exec(
                    select(IngredienteIreks).order_by(
                        IngredienteIreks.articulo_referencia_corta,
                        IngredienteIreks.articulo_descripcion,
                    )
                )
            )

    def list_filter_manufacturers(self) -> list[Fabricante]:
        with Session(self._engine) as session:
            return list(session.exec(select(Fabricante).order_by(Fabricante.fabricante_nombre)))

    def list_filter_manufacturers_igsa(self) -> list[Fabricante]:
        ids = self._igsa_related_family_tree()["manufacturer_ids"]
        with Session(self._engine) as session:
            if not ids:
                return []
            return list(session.exec(select(Fabricante).where(col(Fabricante.fabricante_id).in_(sorted(ids))).order_by(Fabricante.fabricante_nombre)))

    def list_filter_families(self, fabricante_id: str = "") -> list[Familia]:
        clean_fabricante = str(fabricante_id or "").strip()
        with Session(self._engine) as session:
            stmt = select(Familia).order_by(Familia.articulo_familia_nombre)
            if clean_fabricante:
                stmt = stmt.where(Familia.fabricante_id == clean_fabricante)
            return list(session.exec(stmt))

    def list_filter_families_igsa(self, fabricante_id: str = "") -> list[Familia]:
        tree = self._igsa_related_family_tree()
        clean_fabricante = str(fabricante_id or "").strip()
        valid_ids = tree["family_ids_by_manufacturer"].get(clean_fabricante) if clean_fabricante else tree["family_ids"]
        with Session(self._engine) as session:
            if not valid_ids:
                return []
            return list(
                session.exec(
                    select(Familia)
                    .where(col(Familia.articulo_familia_id).in_(sorted(valid_ids)))
                    .order_by(Familia.articulo_familia_nombre)
                )
            )

    def list_filter_subfamilies(self, familia_id: str = "") -> list[Subfamilia]:
        clean_familia = str(familia_id or "").strip()
        with Session(self._engine) as session:
            stmt = select(Subfamilia).order_by(Subfamilia.articulo_subfamilia_nombre)
            if clean_familia:
                stmt = stmt.where(Subfamilia.articulo_familia_id == clean_familia)
            return list(session.exec(stmt))

    def list_filter_subfamilies_igsa(self, familia_id: str = "") -> list[Subfamilia]:
        tree = self._igsa_related_family_tree()
        clean_familia = str(familia_id or "").strip()
        valid_ids = tree["subfamily_ids_by_family"].get(clean_familia) if clean_familia else tree["subfamily_ids"]
        with Session(self._engine) as session:
            if not valid_ids:
                return []
            return list(
                session.exec(
                    select(Subfamilia)
                    .where(col(Subfamilia.articulo_subfamilia_id).in_(sorted(valid_ids)))
                    .order_by(Subfamilia.articulo_subfamilia_nombre)
                )
            )

    def listar_resumen_anual_igsa(
        self,
        year: int,
        month: int = 0,
        acumulado: bool = False,
        producto_texto: str = "",
        fabricante_id: str = "",
        familia_id: str = "",
        subfamilia_id: str = "",
    ) -> list[SalesComparisonRow]:
        current_year = int(year or 0)
        if current_year <= 0:
            return []
        previous_year = current_year - 1
        clean_month = int(month or 0)
        if 1 <= clean_month <= 12:
            months = list(range(1, clean_month + 1)) if bool(acumulado) else [clean_month]
        else:
            months = list(range(1, 13))

        clean_producto_texto = self._normalize_search_text(producto_texto)
        clean_fabricante_id = str(fabricante_id or "").strip()
        clean_familia_id = str(familia_id or "").strip()
        clean_subfamilia_id = str(subfamilia_id or "").strip()

        periods = [f"{previous_year:04d}-{m:02d}" for m in months] + [f"{current_year:04d}-{m:02d}" for m in months]
        with Session(self._engine) as session:
            igsa_rows = list(
                session.exec(
                    select(VentaMensualRaw).where(
                        col(VentaMensualRaw.fuente).in_(["igsa", "igsa_pdf", "igsa_book"]),
                        col(VentaMensualRaw.periodo).in_(periods),
                    )
                )
            )
            products = list(session.exec(select(IngredienteIreks)))

        product_by_id: dict[str, tuple[str, str, str, str, str, str]] = {}
        product_by_code: dict[str, tuple[str, str, str, str, str, str]] = {}
        for product in products:
            aid = str(product.articulo_id or "").strip()
            short_ref = str(product.articulo_referencia_corta or "").strip()
            full_ref = str(product.articulo_referencia or "").strip()
            display_code = short_ref or full_ref
            display_name = str(product.articulo_descripcion or "").strip()
            fabricante = str(product.fabricante_id or "").strip()
            familia = str(product.articulo_familia_id or "").strip()
            subfamilia = str(product.articulo_subfamilia_id or "").strip()
            if aid:
                product_by_id[aid] = (aid, display_code, display_name, fabricante, familia, subfamilia)
            for norm in self._code_candidates(short_ref):
                if norm:
                    product_by_code[norm] = (aid, display_code or short_ref, display_name, fabricante, familia, subfamilia)
            for norm in self._code_candidates(full_ref):
                if norm and norm not in product_by_code:
                    product_by_code[norm] = (aid, display_code or full_ref, display_name, fabricante, familia, subfamilia)

        totals: dict[str, dict[str, float | str]] = defaultdict(
            lambda: {
                "codigo": "",
                "nombre": "",
                "articulo_id": "",
                "fabricante_id": "",
                "familia_id": "",
                "subfamilia_id": "",
                "kilos_prev": 0.0,
                "sc_prev": 0.0,
                "ventas_prev": 0.0,
                "kilos_curr": 0.0,
                "sc_curr": 0.0,
                "ventas_curr": 0.0,
            }
        )

        for row in igsa_rows:
            row_year = self._period_year(str(getattr(row, "periodo", "") or ""))
            if row_year not in {previous_year, current_year}:
                continue
            product = product_by_id.get(str(getattr(row, "articulo_id", "") or "").strip())
            if product is None:
                for cand in self._code_candidates(getattr(row, "articulo_codigo_origen", "")):
                    product = product_by_code.get(cand)
                    if product is not None:
                        break
            key = product[0] if product and product[0] else self._normalize_code(getattr(row, "articulo_codigo_origen", ""))
            if not key:
                continue
            product_articulo_id = product[0] if product else str(getattr(row, "articulo_id", "") or "").strip()
            product_fabricante_id = product[3] if product else ""
            product_familia_id = product[4] if product else ""
            product_subfamilia_id = product[5] if product else ""

            if clean_producto_texto:
                searchable = self._normalize_search_text(
                    " ".join(
                        [
                            product[1] if product else self._normalize_code(getattr(row, "articulo_codigo_origen", "")),
                            product[2] if product else str(getattr(row, "articulo_descripcion_origen", "") or ""),
                            str(getattr(row, "articulo_codigo_origen", "") or ""),
                            str(getattr(row, "articulo_descripcion_origen", "") or ""),
                        ]
                    )
                )
                if clean_producto_texto not in searchable:
                    continue
            if clean_fabricante_id and product_fabricante_id != clean_fabricante_id:
                continue
            if clean_familia_id and product_familia_id != clean_familia_id:
                continue
            if clean_subfamilia_id and product_subfamilia_id != clean_subfamilia_id:
                continue

            kilos_venta = float(getattr(row, "venta_kilos", 0.0) or 0.0)
            kilos_sc = float(getattr(row, "venta_kilos_sc", 0.0) or 0.0)

            bucket = totals[key]
            if not str(bucket["codigo"]):
                bucket["codigo"] = product[1] if product else self._normalize_code(getattr(row, "articulo_codigo_origen", ""))
            if not str(bucket["nombre"]):
                bucket["nombre"] = product[2] if product else str(getattr(row, "articulo_descripcion_origen", "") or "").strip()
            if not str(bucket["articulo_id"]):
                bucket["articulo_id"] = product_articulo_id
            if not str(bucket["fabricante_id"]):
                bucket["fabricante_id"] = product_fabricante_id
            if not str(bucket["familia_id"]):
                bucket["familia_id"] = product_familia_id
            if not str(bucket["subfamilia_id"]):
                bucket["subfamilia_id"] = product_subfamilia_id

            suffix = "curr" if row_year == current_year else "prev"
            bucket[f"kilos_{suffix}"] = float(bucket[f"kilos_{suffix}"] or 0.0) + kilos_venta
            bucket[f"sc_{suffix}"] = float(bucket[f"sc_{suffix}"] or 0.0) + kilos_sc

        return self._build_rows(totals)

    def listar_resumen_anual(
        self,
        year: int,
        month: int = 0,
        acumulado: bool = False,
        cliente_id: str = "",
        cliente_texto: str = "",
        articulo_id: str = "",
        producto_texto: str = "",
        fabricante_id: str = "",
        familia_id: str = "",
        subfamilia_id: str = "",
    ) -> list[SalesComparisonRow]:
        current_year = int(year or 0)
        if current_year <= 0:
            return []
        previous_year = current_year - 1
        clean_month = int(month or 0)
        if 1 <= clean_month <= 12:
            months = list(range(1, clean_month + 1)) if bool(acumulado) else [clean_month]
        else:
            months = list(range(1, 13))
        periods = [f"{previous_year:04d}-{m:02d}" for m in months] + [f"{current_year:04d}-{m:02d}" for m in months]
        clean_cliente_id = str(cliente_id or "").strip()
        clean_cliente_text = self._normalize_search_text(cliente_texto)
        clean_articulo_id = str(articulo_id or "").strip()
        clean_producto_texto = self._normalize_search_text(producto_texto)
        clean_fabricante_id = str(fabricante_id or "").strip()
        clean_familia_id = str(familia_id or "").strip()
        clean_subfamilia_id = str(subfamilia_id or "").strip()

        with Session(self._engine) as session:
            stmt = select(VentaMensualRaw).where(
                col(VentaMensualRaw.fuente) == "ireks",
                col(VentaMensualRaw.periodo).in_(periods),
            )
            if clean_cliente_id:
                resolved_cliente_ids = self._resolve_sales_party_ids(session, clean_cliente_id)
                stmt = stmt.where(col(VentaMensualRaw.cliente_id).in_(sorted(resolved_cliente_ids)))
            else:
                resolved_cliente_ids = set()
            raw_rows = list(session.exec(stmt))
            products = list(session.exec(select(IngredienteIreks)))
            clients = list(session.exec(select(Cliente)))
            distributors = list(session.exec(select(Distribuidor)))

        client_by_id, client_search_by_id = self._build_sales_party_lookup(clients, distributors)

        product_by_id: dict[str, tuple[str, str, str, str, str, str]] = {}
        product_by_code: dict[str, tuple[str, str, str, str, str, str]] = {}
        for product in products:
            aid = str(product.articulo_id or "").strip()
            short_ref = str(product.articulo_referencia_corta or "").strip()
            full_ref = str(product.articulo_referencia or "").strip()
            display_code = short_ref or full_ref
            display_name = str(product.articulo_descripcion or "").strip()
            fabricante = str(product.fabricante_id or "").strip()
            familia = str(product.articulo_familia_id or "").strip()
            subfamilia = str(product.articulo_subfamilia_id or "").strip()
            if aid:
                product_by_id[aid] = (aid, display_code, display_name, fabricante, familia, subfamilia)
            for candidate in (short_ref, full_ref):
                norm = self._normalize_code(candidate)
                if norm:
                    product_by_code[norm] = (aid, display_code or str(candidate or "").strip(), display_name, fabricante, familia, subfamilia)

        totals: dict[str, dict[str, float | str]] = defaultdict(
            lambda: {
                "codigo": "",
                "nombre": "",
                "articulo_id": "",
                "fabricante_id": "",
                "familia_id": "",
                "subfamilia_id": "",
                "kilos_prev": 0.0,
                "sc_prev": 0.0,
                "ventas_prev": 0.0,
                "kilos_curr": 0.0,
                "sc_curr": 0.0,
                "ventas_curr": 0.0,
            }
        )

        for row in raw_rows:
            row_year = self._period_year(row.periodo)
            if row_year not in {previous_year, current_year}:
                continue
            product = product_by_id.get(str(row.articulo_id or "").strip())
            if product is None:
                product = product_by_code.get(self._normalize_code(row.articulo_codigo_origen))
            key = product[0] if product and product[0] else self._normalize_code(row.articulo_codigo_origen)
            if not key:
                continue
            product_articulo_id = product[0] if product else str(row.articulo_id or "").strip()
            product_fabricante_id = product[3] if product else ""
            product_familia_id = product[4] if product else ""
            product_subfamilia_id = product[5] if product else ""
            if clean_articulo_id and product_articulo_id != clean_articulo_id:
                continue
            if clean_cliente_text:
                client_searchable = client_search_by_id.get(str(row.cliente_id or "").strip(), "")
                if clean_cliente_text not in client_searchable:
                    continue
            if clean_producto_texto:
                searchable = self._normalize_search_text(
                    " ".join(
                        [
                            product[1] if product else self._normalize_code(row.articulo_codigo_origen),
                            product[2] if product else str(row.articulo_descripcion_origen or ""),
                            str(row.articulo_codigo_origen or ""),
                            str(row.articulo_descripcion_origen or ""),
                        ]
                    )
                )
                if clean_producto_texto not in searchable:
                    continue
            if clean_fabricante_id and product_fabricante_id != clean_fabricante_id:
                continue
            if clean_familia_id and product_familia_id != clean_familia_id:
                continue
            if clean_subfamilia_id and product_subfamilia_id != clean_subfamilia_id:
                continue

            bucket = totals[key]
            if not str(bucket["codigo"]):
                bucket["codigo"] = product[1] if product else self._normalize_code(row.articulo_codigo_origen)
            if not str(bucket["nombre"]):
                bucket["nombre"] = product[2] if product else str(row.articulo_descripcion_origen or "").strip()
            if not str(bucket["articulo_id"]):
                bucket["articulo_id"] = product_articulo_id
            if not str(bucket["fabricante_id"]):
                bucket["fabricante_id"] = product_fabricante_id
            if not str(bucket["familia_id"]):
                bucket["familia_id"] = product_familia_id
            if not str(bucket["subfamilia_id"]):
                bucket["subfamilia_id"] = product_subfamilia_id

            suffix = "curr" if row_year == current_year else "prev"
            bucket[f"kilos_{suffix}"] = float(bucket[f"kilos_{suffix}"] or 0.0) + float(row.venta_kilos or 0.0)
            bucket[f"sc_{suffix}"] = float(bucket[f"sc_{suffix}"] or 0.0) + float(row.venta_kilos_sc or 0.0)
            bucket[f"ventas_{suffix}"] = float(bucket[f"ventas_{suffix}"] or 0.0) + float(row.venta_euros or 0.0)

        return self._build_rows(totals)

    def listar_resumen_anual_clientes(
        self,
        year: int,
        cliente_id: str = "",
        producto_texto: str = "",
        fabricante_id: str = "",
        familia_id: str = "",
        subfamilia_id: str = "",
        month_from: int = 1,
        month_to: int = 12,
    ) -> list[SalesClientsComparisonRow]:
        current_year = int(year or 0)
        if current_year <= 0:
            return []
        previous_year = current_year - 1
        clean_month_from = max(1, min(int(month_from or 1), 12))
        clean_month_to = max(1, min(int(month_to or 12), 12))
        if clean_month_from > clean_month_to:
            clean_month_from, clean_month_to = clean_month_to, clean_month_from
        clean_cliente_id = str(cliente_id or "").strip()
        clean_producto_texto = self._normalize_search_text(producto_texto)
        clean_fabricante_id = str(fabricante_id or "").strip()
        clean_familia_id = str(familia_id or "").strip()
        clean_subfamilia_id = str(subfamilia_id or "").strip()

        with Session(self._engine) as session:
            stmt = select(VentaClientesRaw).where(col(VentaClientesRaw.anio).in_([previous_year, current_year]))
            stmt = stmt.where(col(VentaClientesRaw.mes) >= clean_month_from, col(VentaClientesRaw.mes) <= clean_month_to)
            if clean_cliente_id:
                resolved_cliente_ids = self._resolve_sales_party_ids(session, clean_cliente_id)
                stmt = stmt.where(col(VentaClientesRaw.cliente_id).in_(sorted(resolved_cliente_ids)))
            else:
                resolved_cliente_ids = set()
            raw_rows = list(session.exec(stmt))
            products = list(session.exec(select(IngredienteIreks)))
            clients = list(session.exec(select(Cliente)))
            distributors = list(session.exec(select(Distribuidor)))

        client_by_id, client_search_by_id = self._build_sales_party_lookup(clients, distributors)

        product_by_id: dict[str, tuple[str, str, str, str, str, str, str]] = {}
        product_by_code: dict[str, tuple[str, str, str, str, str, str, str]] = {}
        for product in products:
            aid = str(product.articulo_id or "").strip()
            short_ref = str(product.articulo_referencia_corta or "").strip()
            full_ref = str(product.articulo_referencia or "").strip()
            display_code = short_ref or full_ref
            display_name = str(product.articulo_descripcion or "").strip()
            fabricante = str(product.fabricante_id or "").strip()
            family = str(product.articulo_familia_id or "").strip()
            subfamily = str(product.articulo_subfamilia_id or "").strip()
            searchable = self._normalize_search_text(" ".join([display_code, display_name, short_ref, full_ref]))
            if aid:
                product_by_id[aid] = (aid, display_code, display_name, fabricante, family, subfamily, searchable)
            for candidate in (short_ref, full_ref):
                norm = self._normalize_code(candidate)
                if norm:
                    product_by_code[norm] = (
                        aid,
                        display_code or str(candidate or "").strip(),
                        display_name,
                        fabricante,
                        family,
                        subfamily,
                        searchable,
                    )

        totals: dict[str, dict[str, float | str]] = defaultdict(
            lambda: {
                "codigo": "",
                "nombre": "",
                "articulo_id": "",
                "fabricante_id": "",
                "familia_id": "",
                "subfamilia_id": "",
                "unidades_prev": 0.0,
                "kg_prev": 0.0,
                "euros_prev": 0.0,
                "unidades_curr": 0.0,
                "kg_curr": 0.0,
                "euros_curr": 0.0,
            }
        )

        for row in raw_rows:
            row_year = int(getattr(row, "anio", 0) or 0)
            if row_year not in {previous_year, current_year}:
                continue
            product = product_by_id.get(str(getattr(row, "articulo_id", "") or "").strip())
            if product is None:
                for cand in self._code_candidates(getattr(row, "articulo_codigo_origen", "")):
                    product = product_by_code.get(cand)
                    if product is not None:
                        break
            key = product[0] if product and product[0] else self._normalize_code(getattr(row, "articulo_codigo_origen", ""))
            if not key:
                continue
            product_articulo_id = product[0] if product else str(getattr(row, "articulo_id", "") or "").strip()
            product_fabricante_id = product[3] if product else ""
            product_familia_id = product[4] if product else ""
            product_subfamilia_id = product[5] if product else ""

            if clean_producto_texto:
                searchable = self._normalize_search_text(
                    " ".join(
                        [
                            product[1] if product else self._normalize_code(getattr(row, "articulo_codigo_origen", "")),
                            product[2] if product else str(getattr(row, "articulo_descripcion_origen", "") or ""),
                            str(getattr(row, "articulo_codigo_origen", "") or ""),
                            str(getattr(row, "articulo_descripcion_origen", "") or ""),
                        ]
                    )
                )
                if clean_producto_texto not in searchable:
                    continue
            if clean_fabricante_id and product_fabricante_id != clean_fabricante_id:
                continue
            if clean_familia_id and product_familia_id != clean_familia_id:
                continue
            if clean_subfamilia_id and product_subfamilia_id != clean_subfamilia_id:
                continue

            bucket = totals[key]
            if not str(bucket["codigo"]):
                bucket["codigo"] = product[1] if product else self._normalize_code(getattr(row, "articulo_codigo_origen", ""))
            if not str(bucket["nombre"]):
                bucket["nombre"] = product[2] if product else str(getattr(row, "articulo_descripcion_origen", "") or "").strip()
            if not str(bucket["articulo_id"]):
                bucket["articulo_id"] = product_articulo_id
            if not str(bucket["fabricante_id"]):
                bucket["fabricante_id"] = product_fabricante_id
            if not str(bucket["familia_id"]):
                bucket["familia_id"] = product_familia_id
            if not str(bucket["subfamilia_id"]):
                bucket["subfamilia_id"] = product_subfamilia_id

            suffix = "curr" if row_year == current_year else "prev"
            bucket[f"unidades_{suffix}"] = float(bucket[f"unidades_{suffix}"] or 0.0) + float(getattr(row, "unidades", 0.0) or 0.0)
            bucket[f"kg_{suffix}"] = float(bucket[f"kg_{suffix}"] or 0.0) + float(getattr(row, "kg", 0.0) or 0.0)
            bucket[f"euros_{suffix}"] = float(bucket[f"euros_{suffix}"] or 0.0) + float(getattr(row, "euros", 0.0) or 0.0)

        return self._build_client_rows(totals)

    def listar_ventas_anuales_clientes(
        self,
        year: int,
        cliente_tipo: str = '',
        isla: str = '',
        direction: str = 'asc',
        zero_consumption: bool = False,
        sort_by_island: bool = True,
    ):
        current_year = int(year or 0)
        if current_year <= 0:
            return []
        with Session(self._engine) as session:
            raw_rows = list(
                session.exec(
                    select(VentaClientesRaw).where(col(VentaClientesRaw.anio) == current_year)
                )
            )
            clients = list(session.exec(select(Cliente)))
            islands = list(session.exec(select(Isla)))
        return self._build_annual_customer_sales(
            raw_rows, clients, islands, cliente_tipo, isla, direction, zero_consumption, sort_by_island
        )

    def listar_ranking_anual_clientes(self, year: int, limit: int = 10, direction: str = 'asc'):
        current_year = int(year or 0)
        if current_year <= 0:
            return []
        previous_year = current_year - 1
        safe_limit = min(max(int(limit or 10), 1), 500)
        with Session(self._engine) as session:
            raw_rows = list(
                session.exec(
                    select(VentaClientesRaw).where(
                        col(VentaClientesRaw.anio).in_([previous_year, current_year])
                    )
                )
            )
            clients = list(session.exec(select(Cliente)))
            distributors = list(session.exec(select(Distribuidor)))
        party_by_id, _search_by_id = self._build_sales_party_lookup(clients, distributors)
        return self._build_annual_customer_ranking(
            raw_rows, party_by_id, current_year, safe_limit, direction
        )

    def listar_comparativa_anual_clientes(
        self,
        year: int,
        compare_year: int,
        limit: int = 10,
        direction: str = 'desc',
        sort_metric: str = 'kg_curr',
        cliente_tipo: str = '',
        isla: str = '',
    ) -> list[SalesCustomerAnnualComparisonRow]:
        current_year = int(year or 0)
        previous_year = int(compare_year or 0)
        if current_year <= 0 or previous_year <= 0 or current_year == previous_year:
            return []
        safe_limit = min(max(int(limit or 10), 1), 500)
        with Session(self._engine) as session:
            raw_rows = list(
                session.exec(
                    select(VentaClientesRaw).where(
                        col(VentaClientesRaw.anio).in_([previous_year, current_year])
                    )
                )
            )
            clients = list(session.exec(select(Cliente)))
            islands = list(session.exec(select(Isla)))
        return self._build_customer_year_comparison(
            raw_rows,
            clients,
            islands,
            current_year,
            previous_year,
            safe_limit,
            direction,
            sort_metric,
            cliente_tipo,
            isla,
        )

    def _build_annual_customer_sales(
        self,
        raw_rows,
        clients,
        islands,
        cliente_tipo: str,
        isla: str,
        direction: str,
        zero_consumption: bool = False,
        sort_by_island: bool = True,
    ):
        client_by_id = {str(row.cliente_id or '').strip(): row for row in clients}
        island_by_id = {str(row.isla_id or '').strip(): str(row.isla_nombre or '') for row in islands}
        clean_type = str(cliente_tipo or '').strip().lower()
        clean_island = self._normalize_search_text(isla)
        eligible_clients = {}
        for cliente_id, client in client_by_id.items():
            row_type = str(getattr(client, 'cliente_tipo', '') or '').strip()
            if clean_type and row_type.lower() != clean_type:
                continue
            island_id = str(getattr(client, 'cliente_direccion_isla_id', '') or '').strip()
            island_name = island_by_id.get(island_id, '')
            if clean_island and self._normalize_search_text(island_name) != clean_island:
                continue
            eligible_clients[cliente_id] = client

        totals = defaultdict(float)
        for raw_row in raw_rows:
            cliente_id = str(getattr(raw_row, 'cliente_id', '') or '').strip()
            if cliente_id not in eligible_clients:
                continue
            totals[cliente_id] += float(getattr(raw_row, 'kg', 0.0) or 0.0)

        result = []
        candidates = eligible_clients.items() if zero_consumption else (
            (cliente_id, eligible_clients[cliente_id])
            for cliente_id in totals
        )
        for cliente_id, client in candidates:
            kg = float(totals.get(cliente_id, 0.0) or 0.0)
            if zero_consumption and abs(kg) > 1e-9:
                continue
            island_id = str(getattr(client, 'cliente_direccion_isla_id', '') or '').strip()
            result.append(
                SalesCustomerAnnualSalesRow(
                    cliente_id=cliente_id,
                    isla=island_by_id.get(island_id, ''),
                    cliente_codigo=str(getattr(client, 'cliente_codigo', '') or ''),
                    cliente_nombre=str(
                        getattr(client, 'cliente_nombre_comercial', '')
                        or getattr(client, 'cliente_nombre_fiscal', '')
                        or cliente_id
                    ),
                    cliente_tipo=str(getattr(client, 'cliente_tipo', '') or ''),
                    kg=float(kg or 0.0),
                )
            )
        kg_factor = -1.0 if str(direction or 'asc').strip().lower() == 'desc' else 1.0
        if sort_by_island:
            result.sort(
                key=lambda row: (
                    not bool(row.isla.strip()),
                    row.isla.lower(),
                    kg_factor * row.kg,
                    row.cliente_nombre.lower(),
                )
            )
        else:
            result.sort(
                key=lambda row: (
                    kg_factor * row.kg,
                    row.cliente_nombre.lower(),
                    row.cliente_codigo.lower(),
                )
            )
        return result

    def _build_annual_customer_ranking(
        self, raw_rows, party_by_id, current_year: int, safe_limit: int, direction: str
    ):
        totals = defaultdict(lambda: {'kg_prev': 0.0, 'kg_curr': 0.0})
        for raw_row in raw_rows:
            cliente_id = str(getattr(raw_row, 'cliente_id', '') or '').strip()
            if not cliente_id:
                continue
            key = 'kg_curr' if int(getattr(raw_row, 'anio', 0) or 0) == current_year else 'kg_prev'
            totals[cliente_id][key] += float(getattr(raw_row, 'kg', 0.0) or 0.0)
        result = []
        for cliente_id, values in totals.items():
            code, name = party_by_id.get(cliente_id, ('', cliente_id))
            kg_prev = float(values['kg_prev'] or 0.0)
            kg_curr = float(values['kg_curr'] or 0.0)
            delta_kg = kg_curr - kg_prev
            result.append(
                SalesCustomerAnnualComparisonRow(
                    cliente_id=cliente_id,
                    cliente_codigo=str(code or ''),
                    cliente_nombre=str(name or cliente_id),
                    kg_prev=kg_prev,
                    kg_curr=kg_curr,
                    delta_kg=delta_kg,
                    delta_kg_pct=self._pct(delta_kg, kg_prev),
                )
            )
        reverse = str(direction or 'asc').strip().lower() == 'desc'
        result.sort(
            key=lambda row: (row.delta_kg, row.cliente_nombre.lower(), row.cliente_codigo.lower()),
            reverse=reverse,
        )
        return result[:safe_limit]

    def _build_customer_year_comparison(
        self,
        raw_rows,
        clients,
        islands,
        current_year: int,
        previous_year: int,
        safe_limit: int,
        direction: str,
        sort_metric: str,
        cliente_tipo: str,
        isla: str,
    ) -> list[SalesCustomerAnnualComparisonRow]:
        island_by_id = {str(row.isla_id or '').strip(): str(row.isla_nombre or '') for row in islands}
        clean_type = str(cliente_tipo or '').strip().lower()
        clean_island = self._normalize_search_text(isla)
        eligible_clients = {}
        for client in clients:
            cliente_id = str(getattr(client, 'cliente_id', '') or '').strip()
            if not cliente_id:
                continue
            row_type = str(getattr(client, 'cliente_tipo', '') or '').strip().lower()
            if clean_type and row_type != clean_type:
                continue
            island_id = str(getattr(client, 'cliente_direccion_isla_id', '') or '').strip()
            island_name = island_by_id.get(island_id, '')
            if clean_island and self._normalize_search_text(island_name) != clean_island:
                continue
            eligible_clients[cliente_id] = client

        totals = defaultdict(lambda: {'kg_prev': 0.0, 'kg_curr': 0.0})
        for raw_row in raw_rows:
            cliente_id = str(getattr(raw_row, 'cliente_id', '') or '').strip()
            if cliente_id not in eligible_clients:
                continue
            row_year = int(getattr(raw_row, 'anio', 0) or 0)
            if row_year == current_year:
                totals[cliente_id]['kg_curr'] += float(getattr(raw_row, 'kg', 0.0) or 0.0)
            elif row_year == previous_year:
                totals[cliente_id]['kg_prev'] += float(getattr(raw_row, 'kg', 0.0) or 0.0)

        result = []
        for cliente_id, values in totals.items():
            client = eligible_clients.get(cliente_id)
            if client is None:
                continue
            kg_prev = float(values['kg_prev'] or 0.0)
            kg_curr = float(values['kg_curr'] or 0.0)
            delta_kg = kg_curr - kg_prev
            result.append(
                SalesCustomerAnnualComparisonRow(
                    cliente_id=cliente_id,
                    cliente_codigo=str(getattr(client, 'cliente_codigo', '') or ''),
                    cliente_nombre=str(
                        getattr(client, 'cliente_nombre_comercial', '')
                        or getattr(client, 'cliente_nombre_fiscal', '')
                        or cliente_id
                    ),
                    kg_prev=kg_prev,
                    kg_curr=kg_curr,
                    delta_kg=delta_kg,
                    delta_kg_pct=self._pct(delta_kg, kg_prev),
                )
            )

        clean_sort = str(sort_metric or 'kg_curr').strip().lower()
        reverse = str(direction or 'desc').strip().lower() == 'desc'
        if clean_sort == 'delta_kg':
            sort_value = lambda row: row.delta_kg
        elif clean_sort == 'kg_prev':
            sort_value = lambda row: row.kg_prev
        else:
            sort_value = lambda row: row.kg_curr
        result.sort(
            key=lambda row: (
                sort_value(row),
                row.cliente_nombre.lower(),
                row.cliente_codigo.lower(),
            ),
            reverse=reverse,
        )
        return result[:safe_limit]

    def listar_ranking_anual(
        self,
        year: int,
        month: int = 0,
        acumulado: bool = False,
        cliente_id: str = "",
        cliente_texto: str = "",
        articulo_id: str = "",
        producto_texto: str = "",
        fabricante_id: str = "",
        familia_id: str = "",
        subfamilia_id: str = "",
        limit: int = 20,
    ) -> list[SalesComparisonRow]:
        rows = self.listar_resumen_anual(
            year=year,
            month=month,
            acumulado=acumulado,
            cliente_id=cliente_id,
            cliente_texto=cliente_texto,
            articulo_id=articulo_id,
            producto_texto=producto_texto,
            fabricante_id=fabricante_id,
            familia_id=familia_id,
            subfamilia_id=subfamilia_id,
        )
        rows.sort(
            key=lambda row: (
                -(float(row.kilos_curr or 0.0) + float(row.sc_curr or 0.0)),
                -(float(row.ventas_curr or 0.0)),
                row.nombre.lower(),
                row.codigo.lower(),
            )
        )
        clean_limit = max(int(limit or 0), 0)
        if clean_limit > 0:
            return rows[:clean_limit]
        return rows

    def listar_diferenciales_negativos_anual(
        self,
        year: int,
        month: int = 0,
        acumulado: bool = False,
        cliente_id: str = "",
        cliente_texto: str = "",
        articulo_id: str = "",
        producto_texto: str = "",
        fabricante_id: str = "",
        familia_id: str = "",
        subfamilia_id: str = "",
        limit: int = 20,
    ) -> list[SalesComparisonRow]:
        rows = self.listar_resumen_anual(
            year=year,
            month=month,
            acumulado=acumulado,
            cliente_id=cliente_id,
            cliente_texto=cliente_texto,
            articulo_id=articulo_id,
            producto_texto=producto_texto,
            fabricante_id=fabricante_id,
            familia_id=familia_id,
            subfamilia_id=subfamilia_id,
        )
        rows = [row for row in rows if float(row.delta_kg or 0.0) < 0.0]
        rows.sort(
            key=lambda row: (
                float(row.delta_kg or 0.0),
                float(row.delta_kg_pct or 0.0),
                row.nombre.lower(),
                row.codigo.lower(),
            )
        )
        clean_limit = max(int(limit or 0), 0)
        if clean_limit > 0:
            return rows[:clean_limit]
        return rows

    def listar_detalle_ventas(
        self,
        year: int,
        month: int = 0,
        acumulado: bool = False,
        cliente_id: str = "",
        cliente_texto: str = "",
        articulo_id: str = "",
        producto_texto: str = "",
        fabricante_id: str = "",
        familia_id: str = "",
        subfamilia_id: str = "",
        limit: int = 200,
    ) -> list[SalesDetailRow]:
        current_year = int(year or 0)
        if current_year <= 0:
            return []
        clean_month = int(month or 0)
        if 1 <= clean_month <= 12:
            months = list(range(1, clean_month + 1)) if bool(acumulado) else [clean_month]
        else:
            months = list(range(1, 13))
        periods = [f"{current_year:04d}-{m:02d}" for m in months]
        clean_cliente_id = str(cliente_id or "").strip()
        clean_cliente_text = self._normalize_search_text(cliente_texto)
        clean_articulo_id = str(articulo_id or "").strip()
        clean_producto_text = self._normalize_search_text(producto_texto)
        clean_fabricante_id = str(fabricante_id or "").strip()
        clean_familia_id = str(familia_id or "").strip()
        clean_subfamilia_id = str(subfamilia_id or "").strip()
        clean_limit = max(int(limit or 0), 0)

        with Session(self._engine) as session:
            stmt = select(VentaMensualRaw).where(
                col(VentaMensualRaw.fuente) == "ireks",
                col(VentaMensualRaw.periodo).in_(periods),
            )
            if clean_cliente_id:
                resolved_cliente_ids = self._resolve_sales_party_ids(session, clean_cliente_id)
                stmt = stmt.where(col(VentaMensualRaw.cliente_id).in_(sorted(resolved_cliente_ids)))
            raw_rows = list(session.exec(stmt))
            products = list(session.exec(select(IngredienteIreks)))
            clients = list(session.exec(select(Cliente)))
            distributors = list(session.exec(select(Distribuidor)))

        client_by_id, client_search_by_id = self._build_sales_party_lookup(clients, distributors)

        product_by_id: dict[str, tuple[str, str, str, str, str, str, str]] = {}
        product_by_code: dict[str, tuple[str, str, str, str, str, str, str]] = {}
        for product in products:
            aid = str(product.articulo_id or "").strip()
            short_ref = str(product.articulo_referencia_corta or "").strip()
            full_ref = str(product.articulo_referencia or "").strip()
            display_code = short_ref or full_ref
            display_name = str(product.articulo_descripcion or "").strip()
            fabricante = str(product.fabricante_id or "").strip()
            familia = str(product.articulo_familia_id or "").strip()
            subfamilia = str(product.articulo_subfamilia_id or "").strip()
            searchable = self._normalize_search_text(" ".join([display_code, display_name, short_ref, full_ref]))
            if aid:
                product_by_id[aid] = (aid, display_code, display_name, fabricante, familia, subfamilia, searchable)
            for candidate in (short_ref, full_ref):
                norm = self._normalize_code(candidate)
                if norm:
                    product_by_code[norm] = (
                        aid,
                        display_code or str(candidate or "").strip(),
                        display_name,
                        fabricante,
                        familia,
                        subfamilia,
                        searchable,
                    )

        grouped: dict[tuple[str, str, str], dict[str, str | float]] = defaultdict(
            lambda: {
                "periodo": "",
                "cliente_id": "",
                "cliente_nombre": "",
                "articulo_id": "",
                "codigo": "",
                "nombre": "",
                "fabricante_id": "",
                "familia_id": "",
                "subfamilia_id": "",
                "kilos": 0.0,
                "sc": 0.0,
                "ventas": 0.0,
            }
        )

        for row in raw_rows:
            row_periodo = str(getattr(row, "periodo", "") or "").strip()
            row_cliente_id = str(getattr(row, "cliente_id", "") or "").strip()
            row_articulo_id = str(getattr(row, "articulo_id", "") or "").strip()
            row_code = self._normalize_code(getattr(row, "articulo_codigo_origen", ""))
            product = product_by_id.get(row_articulo_id) if row_articulo_id else None
            if product is None and row_code:
                product = product_by_code.get(row_code)
            product_id = str(product[0] if product else row_articulo_id).strip()
            product_code = str(product[1] if product else row_code).strip()
            product_name = str(product[2] if product else getattr(row, "articulo_descripcion_origen", "") or "").strip()
            product_fabricante_id = str(product[3] if product else "").strip()
            product_familia_id = str(product[4] if product else "").strip()
            product_subfamilia_id = str(product[5] if product else "").strip()
            product_searchable = str(product[6] if product else self._normalize_search_text(product_name)).strip()

            client = client_by_id.get(row_cliente_id)
            client_name = str(client[1] if client else row_cliente_id).strip()
            client_searchable = client_search_by_id.get(row_cliente_id, "")

            if clean_cliente_id and row_cliente_id != clean_cliente_id:
                continue
            if clean_cliente_text and clean_cliente_text not in client_searchable:
                continue
            if clean_articulo_id and product_id != clean_articulo_id:
                continue
            if clean_producto_text and clean_producto_text not in product_searchable:
                continue
            if clean_fabricante_id and product_fabricante_id != clean_fabricante_id:
                continue
            if clean_familia_id and product_familia_id != clean_familia_id:
                continue
            if clean_subfamilia_id and product_subfamilia_id != clean_subfamilia_id:
                continue

            key = (row_periodo, row_cliente_id or client_name, product_id or product_code or product_name)
            bucket = grouped[key]
            bucket["periodo"] = row_periodo
            bucket["cliente_id"] = row_cliente_id
            bucket["cliente_nombre"] = client_name
            bucket["articulo_id"] = product_id
            bucket["codigo"] = product_code
            bucket["nombre"] = product_name
            bucket["fabricante_id"] = product_fabricante_id
            bucket["familia_id"] = product_familia_id
            bucket["subfamilia_id"] = product_subfamilia_id
            bucket["kilos"] = float(bucket["kilos"] or 0.0) + float(getattr(row, "venta_kilos", 0.0) or 0.0)
            bucket["sc"] = float(bucket["sc"] or 0.0) + float(getattr(row, "venta_kilos_sc", 0.0) or 0.0)
            bucket["ventas"] = float(bucket["ventas"] or 0.0) + float(getattr(row, "venta_euros", 0.0) or 0.0)

        rows = [
            SalesDetailRow(
                periodo=str(values["periodo"] or ""),
                cliente_id=str(values["cliente_id"] or ""),
                cliente_nombre=str(values["cliente_nombre"] or ""),
                articulo_id=str(values["articulo_id"] or ""),
                codigo=str(values["codigo"] or ""),
                nombre=str(values["nombre"] or ""),
                fabricante_id=str(values["fabricante_id"] or ""),
                familia_id=str(values["familia_id"] or ""),
                subfamilia_id=str(values["subfamilia_id"] or ""),
                kilos=float(values["kilos"] or 0.0),
                sc=float(values["sc"] or 0.0),
                ventas=float(values["ventas"] or 0.0),
            )
            for values in grouped.values()
        ]
        rows.sort(key=lambda row: (row.periodo, row.cliente_nombre.lower(), row.nombre.lower(), row.codigo.lower()))
        if clean_limit > 0:
            return rows[:clean_limit]
        return rows

    def listar_ventas_mensuales_ireks(self, year: int, articulo_id: str, cliente_id: str = "") -> list[SalesMonthlyPoint]:
        current_year = int(year or 0)
        if current_year <= 0:
            return [SalesMonthlyPoint(month=month, kilos=0.0) for month in range(1, 13)]

        clean_articulo_id = str(articulo_id or "").strip()
        if not clean_articulo_id:
            return [SalesMonthlyPoint(month=month, kilos=0.0) for month in range(1, 13)]

        clean_cliente_id = str(cliente_id or "").strip()
        with Session(self._engine) as session:
            stmt = select(VentaMensualRaw).where(
                col(VentaMensualRaw.fuente) == "ireks",
                col(VentaMensualRaw.articulo_id) == clean_articulo_id,
                col(VentaMensualRaw.periodo).like(f"{current_year:04d}-%"),
            )
            if clean_cliente_id:
                resolved_cliente_ids = self._resolve_sales_party_ids(session, clean_cliente_id)
                stmt = stmt.where(col(VentaMensualRaw.cliente_id).in_(sorted(resolved_cliente_ids)))
            rows = list(session.exec(stmt))

        totals_by_month = {month: 0.0 for month in range(1, 13)}
        for row in rows:
            month = self._period_month(str(getattr(row, "periodo", "") or ""))
            if month < 1 or month > 12:
                continue
            totals_by_month[month] += float(getattr(row, "venta_kilos", 0.0) or 0.0) + float(
                getattr(row, "venta_kilos_sc", 0.0) or 0.0
            )
        return [SalesMonthlyPoint(month=month, kilos=totals_by_month[month]) for month in range(1, 13)]

    def listar_ventas_mensuales_ireks_comparativa(
        self,
        year: int,
        articulo_id: str,
        cliente_id: str = "",
    ) -> list[SalesMonthlyComparisonPoint]:
        current_year = int(year or 0)
        if current_year <= 0:
            return [SalesMonthlyComparisonPoint(month=month, kilos_prev=0.0, kilos_curr=0.0) for month in range(1, 13)]

        clean_articulo_id = str(articulo_id or "").strip()
        if not clean_articulo_id:
            return [SalesMonthlyComparisonPoint(month=month, kilos_prev=0.0, kilos_curr=0.0) for month in range(1, 13)]

        clean_cliente_id = str(cliente_id or "").strip()
        previous_year = current_year - 1
        with Session(self._engine) as session:
            stmt = select(VentaMensualRaw).where(
                col(VentaMensualRaw.fuente) == "ireks",
                col(VentaMensualRaw.articulo_id) == clean_articulo_id,
                col(VentaMensualRaw.periodo).like(f"{previous_year:04d}-%"),
            )
            if clean_cliente_id:
                resolved_cliente_ids = self._resolve_sales_party_ids(session, clean_cliente_id)
                stmt = stmt.where(col(VentaMensualRaw.cliente_id).in_(sorted(resolved_cliente_ids)))
            prev_rows = list(session.exec(stmt))

            stmt = select(VentaMensualRaw).where(
                col(VentaMensualRaw.fuente) == "ireks",
                col(VentaMensualRaw.articulo_id) == clean_articulo_id,
                col(VentaMensualRaw.periodo).like(f"{current_year:04d}-%"),
            )
            if clean_cliente_id:
                resolved_cliente_ids = self._resolve_sales_party_ids(session, clean_cliente_id)
                stmt = stmt.where(col(VentaMensualRaw.cliente_id).in_(sorted(resolved_cliente_ids)))
            curr_rows = list(session.exec(stmt))

        prev_totals = {month: 0.0 for month in range(1, 13)}
        curr_totals = {month: 0.0 for month in range(1, 13)}
        for row in prev_rows:
            month = self._period_month(str(getattr(row, "periodo", "") or ""))
            if 1 <= month <= 12:
                prev_totals[month] += float(getattr(row, "venta_kilos", 0.0) or 0.0) + float(
                    getattr(row, "venta_kilos_sc", 0.0) or 0.0
                )
        for row in curr_rows:
            month = self._period_month(str(getattr(row, "periodo", "") or ""))
            if 1 <= month <= 12:
                curr_totals[month] += float(getattr(row, "venta_kilos", 0.0) or 0.0) + float(
                    getattr(row, "venta_kilos_sc", 0.0) or 0.0
                )
        return [
            SalesMonthlyComparisonPoint(month=month, kilos_prev=prev_totals[month], kilos_curr=curr_totals[month])
            for month in range(1, 13)
        ]

    def listar_ventas_mensuales_ireks_totales_comparativa(
        self,
        year: int,
        cliente_id: str = "",
    ) -> list[SalesMonthlyComparisonPoint]:
        current_year = int(year or 0)
        if current_year <= 0:
            return [SalesMonthlyComparisonPoint(month=month, kilos_prev=0.0, kilos_curr=0.0) for month in range(1, 13)]

        clean_cliente_id = str(cliente_id or "").strip()
        previous_year = current_year - 1
        with Session(self._engine) as session:
            prev_stmt = select(VentaMensualRaw).where(
                col(VentaMensualRaw.fuente) == "ireks",
                col(VentaMensualRaw.periodo).like(f"{previous_year:04d}-%"),
            )
            if clean_cliente_id:
                resolved_cliente_ids = self._resolve_sales_party_ids(session, clean_cliente_id)
                prev_stmt = prev_stmt.where(col(VentaMensualRaw.cliente_id).in_(sorted(resolved_cliente_ids)))
            prev_rows = list(session.exec(prev_stmt))

            curr_stmt = select(VentaMensualRaw).where(
                col(VentaMensualRaw.fuente) == "ireks",
                col(VentaMensualRaw.periodo).like(f"{current_year:04d}-%"),
            )
            if clean_cliente_id:
                resolved_cliente_ids = self._resolve_sales_party_ids(session, clean_cliente_id)
                curr_stmt = curr_stmt.where(col(VentaMensualRaw.cliente_id).in_(sorted(resolved_cliente_ids)))
            curr_rows = list(session.exec(curr_stmt))

        prev_totals = {month: 0.0 for month in range(1, 13)}
        curr_totals = {month: 0.0 for month in range(1, 13)}
        for row in prev_rows:
            month = self._period_month(str(getattr(row, "periodo", "") or ""))
            if 1 <= month <= 12:
                prev_totals[month] += float(getattr(row, "venta_kilos", 0.0) or 0.0) + float(
                    getattr(row, "venta_kilos_sc", 0.0) or 0.0
                )
        for row in curr_rows:
            month = self._period_month(str(getattr(row, "periodo", "") or ""))
            if 1 <= month <= 12:
                curr_totals[month] += float(getattr(row, "venta_kilos", 0.0) or 0.0) + float(
                    getattr(row, "venta_kilos_sc", 0.0) or 0.0
                )
        return [
            SalesMonthlyComparisonPoint(month=month, kilos_prev=prev_totals[month], kilos_curr=curr_totals[month])
            for month in range(1, 13)
        ]

    def _build_rows(self, totals: dict[str, dict[str, float | str]]) -> list[SalesComparisonRow]:
        result: list[SalesComparisonRow] = []
        for values in totals.values():
            kilos_prev = float(values["kilos_prev"] or 0.0)
            sc_prev = float(values["sc_prev"] or 0.0)
            ventas_prev = float(values["ventas_prev"] or 0.0)
            kilos_curr = float(values["kilos_curr"] or 0.0)
            sc_curr = float(values["sc_curr"] or 0.0)
            ventas_curr = float(values["ventas_curr"] or 0.0)
            total_prev = kilos_prev + sc_prev
            total_curr = kilos_curr + sc_curr
            delta_kg = total_curr - total_prev
            delta_ventas = ventas_curr - ventas_prev
            result.append(
                SalesComparisonRow(
                    articulo_id=str(values["articulo_id"] or ""),
                    fabricante_id=str(values["fabricante_id"] or ""),
                    familia_id=str(values["familia_id"] or ""),
                    subfamilia_id=str(values["subfamilia_id"] or ""),
                    codigo=str(values["codigo"] or ""),
                    nombre=str(values["nombre"] or ""),
                    kilos_prev=kilos_prev,
                    sc_prev=sc_prev,
                    ventas_prev=ventas_prev,
                    kilos_curr=kilos_curr,
                    sc_curr=sc_curr,
                    ventas_curr=ventas_curr,
                    delta_kg=delta_kg,
                    delta_kg_pct=self._pct(delta_kg, total_prev),
                    delta_ventas=delta_ventas,
                    delta_ventas_pct=self._pct(delta_ventas, ventas_prev),
                )
            )
        result.sort(key=lambda x: (x.nombre.lower(), x.codigo.lower()))
        return result

    def listar_clientes_consumidores_producto(
        self,
        year: int,
        articulo_id: str,
        articulo_codigo: str = "",
        articulo_nombre: str = "",
        cliente_texto: str = "",
    ) -> list[SalesClientProductConsumerRow]:
        current_year = int(year or 0)
        clean_articulo_id = str(articulo_id or "").strip()
        clean_articulo_codigo = self._normalize_code(articulo_codigo)
        clean_articulo_nombre = self._normalize_search_text(articulo_nombre)
        clean_cliente_text = self._normalize_search_text(cliente_texto)
        if not clean_articulo_id and not clean_articulo_codigo and not clean_articulo_nombre:
            return []
        all_years = current_year <= 0
        years = {current_year} if not all_years else set()
        if current_year > 1:
            years.add(current_year - 1)

        with Session(self._engine) as session:
            stmt = select(VentaClientesRaw)
            if years:
                stmt = stmt.where(col(VentaClientesRaw.anio).in_(years))
            raw_rows = list(session.exec(stmt))
            clients = list(session.exec(select(Cliente)))
            distributors = list(session.exec(select(Distribuidor)))
            products = list(session.exec(select(IngredienteIreks)))
            product_reference_lookup = self._build_clientes_product_reference_lookup(session)

        client_by_id, client_search_by_id = self._build_sales_party_lookup(clients, distributors)

        product_by_id: dict[str, tuple[str, str, str, str, str, str, str]] = {}
        product_by_code: dict[str, tuple[str, str, str, str, str, str, str]] = {}
        for product in products:
            aid = str(product.articulo_id or "").strip()
            short_ref = str(product.articulo_referencia_corta or "").strip()
            full_ref = str(product.articulo_referencia or "").strip()
            display_code = short_ref or full_ref
            display_name = str(product.articulo_descripcion or "").strip()
            fabricante = str(product.fabricante_id or "").strip()
            familia = str(product.articulo_familia_id or "").strip()
            subfamilia = str(product.articulo_subfamilia_id or "").strip()
            searchable = self._normalize_search_text(" ".join([display_code, display_name, short_ref, full_ref]))
            if aid:
                product_by_id[aid] = (aid, display_code, display_name, fabricante, familia, subfamilia, searchable)
            for candidate in (short_ref, full_ref):
                norm = self._normalize_code(candidate)
                if norm:
                    product_by_code[norm] = (
                        aid,
                        display_code or str(candidate or "").strip(),
                        display_name,
                        fabricante,
                        familia,
                        subfamilia,
                        searchable,
                    )

        def resolve_product(row_articulo_id: str, row_code: str, row_name: str):
            product = product_by_id.get(row_articulo_id) if row_articulo_id else None
            if product is None and row_code:
                product = product_by_code.get(row_code)
            if product is None and row_code:
                resolved_id = product_reference_lookup.get(row_code, "")
                if resolved_id:
                    product = product_by_id.get(resolved_id)
            if product is None and row_name:
                searchable_name = self._normalize_search_text(row_name)
                if searchable_name:
                    for candidate in product_by_id.values():
                        if searchable_name in candidate[6]:
                            product = candidate
                            break
                    if product is None:
                        for candidate in product_by_code.values():
                            if searchable_name in candidate[6]:
                                product = candidate
                                break
            return product

        totals: dict[str, dict[str, float | str]] = defaultdict(
            lambda: {
                "cliente_id": "",
                "cliente_codigo": "",
                "cliente_nombre": "",
                "kg_prev": 0.0,
                "euros_prev": 0.0,
                "kg_curr": 0.0,
                "euros_curr": 0.0,
                "unidades_curr": 0.0,
                "ultimo_periodo": "",
            }
        )
        for row in raw_rows:
            row_year = int(getattr(row, "anio", 0) or 0)
            if years and row_year not in years:
                continue
            cliente_id_raw = str(getattr(row, "cliente_id", "") or "").strip()
            client_info = client_by_id.get(cliente_id_raw)
            row_code = self._normalize_code(getattr(row, "articulo_codigo_origen", ""))
            row_name = str(getattr(row, "articulo_descripcion_origen", "") or "").strip()
            row_product = resolve_product(str(getattr(row, "articulo_id", "") or "").strip(), row_code, row_name)
            row_product_id = str(row_product[0] if row_product else str(getattr(row, "articulo_id", "") or "").strip()).strip()
            row_product_code = str(row_product[1] if row_product else row_code).strip()
            row_product_code_norm = self._normalize_code(row_product_code)
            row_product_name = str(row_product[2] if row_product else row_name).strip()
            row_searchable = self._normalize_search_text(" ".join([row_product_code, row_product_name, row_code]))

            if clean_articulo_id or clean_articulo_codigo or clean_articulo_nombre:
                matches_id = bool(clean_articulo_id and row_product_id == clean_articulo_id)
                matches_code = bool(
                    clean_articulo_codigo
                    and (row_product_code_norm == clean_articulo_codigo or row_code == clean_articulo_codigo)
                )
                matches_name = bool(clean_articulo_nombre and clean_articulo_nombre in row_searchable)
                if not matches_id and not matches_code and not matches_name:
                    continue

            if clean_cliente_text:
                searchable = client_search_by_id.get(cliente_id_raw, "")
                if clean_cliente_text not in searchable:
                    continue
            cliente_codigo = str(client_info[0] if client_info else "").strip()
            cliente_nombre = str(client_info[1] if client_info else cliente_id_raw).strip()
            bucket = totals[cliente_id_raw or cliente_nombre]
            bucket["cliente_id"] = cliente_id_raw
            if not str(bucket["cliente_codigo"]):
                bucket["cliente_codigo"] = cliente_codigo
            if not str(bucket["cliente_nombre"]):
                bucket["cliente_nombre"] = cliente_nombre
            if not all_years and row_year == current_year - 1:
                bucket["kg_prev"] = float(bucket["kg_prev"] or 0.0) + float(getattr(row, "kg", 0.0) or 0.0)
                bucket["euros_prev"] = float(bucket["euros_prev"] or 0.0) + float(getattr(row, "euros", 0.0) or 0.0)
            elif all_years or row_year == current_year:
                bucket["kg_curr"] = float(bucket["kg_curr"] or 0.0) + float(getattr(row, "kg", 0.0) or 0.0)
                bucket["euros_curr"] = float(bucket["euros_curr"] or 0.0) + float(getattr(row, "euros", 0.0) or 0.0)
                bucket["unidades_curr"] = float(bucket["unidades_curr"] or 0.0) + float(getattr(row, "unidades", 0.0) or 0.0)
            row_month = int(getattr(row, "mes", 0) or 0)
            period = f"{row_year:04d}-{row_month:02d}" if row_year > 0 and 1 <= row_month <= 12 else str(row_year or "")
            if period > str(bucket["ultimo_periodo"] or ""):
                bucket["ultimo_periodo"] = period

        result = [
            SalesClientProductConsumerRow(
                cliente_id=str(values["cliente_id"] or ""),
                cliente_codigo=str(values["cliente_codigo"] or ""),
                cliente_nombre=str(values["cliente_nombre"] or ""),
                kg_prev=float(values["kg_prev"] or 0.0),
                euros_prev=float(values["euros_prev"] or 0.0),
                kg_curr=float(values["kg_curr"] or 0.0),
                euros_curr=float(values["euros_curr"] or 0.0),
                delta_kg=float(values["kg_curr"] or 0.0) - float(values["kg_prev"] or 0.0),
                delta_euros=float(values["euros_curr"] or 0.0) - float(values["euros_prev"] or 0.0),
                unidades_curr=float(values["unidades_curr"] or 0.0),
                ultimo_periodo=str(values["ultimo_periodo"] or ""),
            )
            for values in totals.values()
            if float(values["kg_prev"] or 0.0) > 0
            or float(values["euros_prev"] or 0.0) > 0
            or float(values["kg_curr"] or 0.0) > 0
            or float(values["euros_curr"] or 0.0) > 0
        ]
        result.sort(
            key=lambda row: (
                -row.euros_curr,
                -row.kg_curr,
                -row.euros_prev,
                -row.kg_prev,
                row.cliente_nombre.lower(),
                row.cliente_codigo.lower(),
            )
        )
        return result

    def _build_clientes_product_reference_lookup(self, session: Session) -> dict[str, str]:
        lookup: dict[str, str] = {}
        rows = list(session.exec(select(ReferenciaDistribuidor)))
        for row in rows:
            articulo_id = str(getattr(row, "articulo_id", "") or "").strip()
            reference = str(getattr(row, "articulo_referencia_distribuidor", "") or "").strip()
            if not articulo_id or not reference:
                continue
            for candidate in self._code_candidates(reference):
                lookup[candidate] = articulo_id
        return lookup

    def _build_sales_party_lookup(
        self,
        clients: list[Cliente],
        distributors: list[Distribuidor],
    ) -> tuple[dict[str, tuple[str, str]], dict[str, str]]:
        party_by_id: dict[str, tuple[str, str]] = {}
        party_search_by_id: dict[str, str] = {}
        for client in clients:
            cid = str(client.cliente_id or "").strip()
            if not cid:
                continue
            codigo = str(getattr(client, "cliente_codigo", "") or "").strip()
            nombre = str(client.cliente_nombre_comercial or client.cliente_nombre_fiscal or cid).strip()
            searchable = self._normalize_search_text(
                " ".join(
                    [
                        codigo,
                        str(client.cliente_nombre_comercial or ""),
                        str(client.cliente_nombre_fiscal or ""),
                        str(client.cliente_abreviatura or ""),
                    ]
                )
            )
            party_by_id[cid] = (codigo, nombre or cid)
            party_search_by_id[cid] = searchable
        for distributor in distributors:
            did = str(getattr(distributor, "distribuidor_id", "") or "").strip()
            if not did or did in party_by_id:
                continue
            codigo = str(getattr(distributor, "distribuidor_codigo", "") or "").strip()
            nombre = str(
                getattr(distributor, "distribuidor_nombre_comercial", "") or getattr(distributor, "distribuidor_razon_social", "") or did
            ).strip()
            searchable = self._normalize_search_text(
                " ".join(
                    [
                        codigo,
                        str(getattr(distributor, "distribuidor_nombre_comercial", "") or ""),
                        str(getattr(distributor, "distribuidor_razon_social", "") or ""),
                    ]
                )
            )
            party_by_id[did] = (codigo, nombre or did)
            party_search_by_id[did] = searchable
        return party_by_id, party_search_by_id

    def _resolve_sales_party_ids(self, session: Session, party_id: str) -> set[str]:
        clean_party_id = str(party_id or "").strip()
        if not clean_party_id:
            return set()
        ids: set[str] = {clean_party_id}
        client = session.get(Cliente, clean_party_id)
        distributor = session.get(Distribuidor, clean_party_id)
        search_terms: set[str] = set()
        if client is not None:
            linked_distributor_id = str(getattr(client, "distribuidor_id", "") or "").strip()
            if linked_distributor_id:
                ids.add(linked_distributor_id)
                distributor = distributor or session.get(Distribuidor, linked_distributor_id)
            search_terms.update(
                {
                    self._normalize_search_text(getattr(client, "cliente_nombre_comercial", "")),
                    self._normalize_search_text(getattr(client, "cliente_nombre_fiscal", "")),
                    self._normalize_search_text(getattr(client, "cliente_abreviatura", "")),
                }
            )
        if distributor is not None:
            search_terms.update(
                {
                    self._normalize_search_text(getattr(distributor, "distribuidor_nombre_comercial", "")),
                    self._normalize_search_text(getattr(distributor, "distribuidor_razon_social", "")),
                }
            )

        search_terms = {term for term in search_terms if term}
        if not search_terms:
            return ids

        for row in session.exec(select(Cliente)):
            row_id = str(getattr(row, "cliente_id", "") or "").strip()
            if not row_id:
                continue
            searchable = self._normalize_search_text(
                " ".join(
                    [
                        str(getattr(row, "cliente_codigo", "") or ""),
                        str(getattr(row, "cliente_nombre_comercial", "") or ""),
                        str(getattr(row, "cliente_nombre_fiscal", "") or ""),
                        str(getattr(row, "cliente_abreviatura", "") or ""),
                    ]
                )
            )
            if any(term in searchable or searchable in term for term in search_terms):
                ids.add(row_id)
                linked_distributor_id = str(getattr(row, "distribuidor_id", "") or "").strip()
                if linked_distributor_id:
                    ids.add(linked_distributor_id)
        for row in session.exec(select(Distribuidor)):
            row_id = str(getattr(row, "distribuidor_id", "") or "").strip()
            if not row_id:
                continue
            searchable = self._normalize_search_text(
                " ".join(
                    [
                        str(getattr(row, "distribuidor_codigo", "") or ""),
                        str(getattr(row, "distribuidor_nombre_comercial", "") or ""),
                        str(getattr(row, "distribuidor_razon_social", "") or ""),
                    ]
                )
            )
            if any(term in searchable or searchable in term for term in search_terms):
                ids.add(row_id)
        return ids

    def _build_client_rows(self, totals: dict[str, dict[str, float | str]]) -> list[SalesClientsComparisonRow]:
        result: list[SalesClientsComparisonRow] = []
        for values in totals.values():
            unidades_prev = float(values["unidades_prev"] or 0.0)
            kg_prev = float(values["kg_prev"] or 0.0)
            euros_prev = float(values["euros_prev"] or 0.0)
            unidades_curr = float(values["unidades_curr"] or 0.0)
            kg_curr = float(values["kg_curr"] or 0.0)
            euros_curr = float(values["euros_curr"] or 0.0)
            delta_unidades = unidades_curr - unidades_prev
            delta_kg = kg_curr - kg_prev
            delta_euros = euros_curr - euros_prev
            result.append(
                SalesClientsComparisonRow(
                    articulo_id=str(values["articulo_id"] or ""),
                    fabricante_id=str(values["fabricante_id"] or ""),
                    familia_id=str(values["familia_id"] or ""),
                    subfamilia_id=str(values["subfamilia_id"] or ""),
                    codigo=str(values["codigo"] or ""),
                    nombre=str(values["nombre"] or ""),
                    unidades_prev=unidades_prev,
                    kg_prev=kg_prev,
                    euros_prev=euros_prev,
                    unidades_curr=unidades_curr,
                    kg_curr=kg_curr,
                    euros_curr=euros_curr,
                    delta_unidades=delta_unidades,
                    delta_unidades_pct=self._pct(delta_unidades, unidades_prev),
                    delta_kg=delta_kg,
                    delta_kg_pct=self._pct(delta_kg, kg_prev),
                    delta_euros=delta_euros,
                    delta_euros_pct=self._pct(delta_euros, euros_prev),
                )
            )
        result.sort(key=lambda x: (x.nombre.lower(), x.codigo.lower()))
        return result

    def _period_year(self, periodo: str) -> int:
        text = str(periodo or "").strip()
        if text.count("-") != 1:
            return 0
        year = text.split("-")[0]
        return int(year) if year.isdigit() else 0

    def _period_month(self, periodo: str) -> int:
        text = str(periodo or "").strip()
        if text.count("-") != 1:
            return 0
        month = text.split("-")[1]
        return int(month) if month.isdigit() else 0

    def _pct(self, delta: float, base: float) -> float:
        if abs(base) <= 1e-9:
            return 0.0
        return (float(delta or 0.0) / float(base)) * 100.0

    def _normalize_search_text(self, value) -> str:
        return normalize_search_text(value)

    def _normalize_code(self, value) -> str:
        text = str(value or "").strip().upper()
        if not text:
            return ""
        if re.fullmatch(r"\d+(\.0+)?", text):
            return str(int(float(text)))
        return text

    def _igsa_related_family_tree(self) -> dict[str, object]:
        with Session(self._engine) as session:
            raw_rows = list(
                session.exec(
                    select(VentaMensualRaw.articulo_id, VentaMensualRaw.articulo_codigo_origen).where(
                        col(VentaMensualRaw.fuente).in_(["igsa", "igsa_pdf", "igsa_book"])
                    )
                )
            )
        product_ids = {str(aid or "").strip() for aid, _code in raw_rows if str(aid or "").strip()}
        product_refs = {self._normalize_code(code) for _aid, code in raw_rows if self._normalize_code(code)}
        with Session(self._engine) as session:
            products = list(session.exec(select(IngredienteIreks)))

        manufacturer_ids: set[str] = set()
        family_ids: set[str] = set()
        subfamily_ids: set[str] = set()
        family_ids_by_manufacturer: dict[str, set[str]] = defaultdict(set)
        subfamily_ids_by_family: dict[str, set[str]] = defaultdict(set)

        for product in products:
            aid = str(product.articulo_id or "").strip()
            ref_short = self._normalize_code(product.articulo_referencia_corta)
            ref_full = self._normalize_code(product.articulo_referencia)
            if aid not in product_ids and ref_short not in product_refs and ref_full not in product_refs:
                continue
            manufacturer_id = str(product.fabricante_id or "").strip()
            family_id = str(product.articulo_familia_id or "").strip()
            subfamily_id = str(product.articulo_subfamilia_id or "").strip()
            if manufacturer_id:
                manufacturer_ids.add(manufacturer_id)
            if family_id:
                family_ids.add(family_id)
            if subfamily_id:
                subfamily_ids.add(subfamily_id)
            if manufacturer_id and family_id:
                family_ids_by_manufacturer[manufacturer_id].add(family_id)
            if family_id and subfamily_id:
                subfamily_ids_by_family[family_id].add(subfamily_id)

        return {
            "manufacturer_ids": manufacturer_ids,
            "family_ids": family_ids,
            "subfamily_ids": subfamily_ids,
            "family_ids_by_manufacturer": family_ids_by_manufacturer,
            "subfamily_ids_by_family": subfamily_ids_by_family,
        }
