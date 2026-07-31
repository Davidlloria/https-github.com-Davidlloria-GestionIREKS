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
    Subfamilia,
    VentaClientesRaw,
    VentaMensualRaw,
)


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
        return sorted({int(year or 0) for year in years if int(year or 0) > 0}, reverse=True)

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
        result: list[Cliente] = []
        for row in rows:
            tipo = str(getattr(row, "cliente_tipo", "") or "").strip().lower()
            if tipo not in SALES_CLIENT_TYPES:
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

    def listar_ventas_anuales_clientes(
        self,
        year: int,
        cliente_tipo: str = "",
        isla: str = "",
        direction: str = "asc",
        zero_consumption: bool = False,
    ) -> list[SalesCustomerAnnualSalesRow]:
        current_year = int(year or 0)
        if current_year <= 0:
            return []
        with Session(self._engine) as session:
            raw_rows = list(session.exec(select(VentaClientesRaw).where(col(VentaClientesRaw.anio) == current_year)))
            clients = list(session.exec(select(Cliente)))
            islands = list(session.exec(select(Isla)))
        return self._build_annual_customer_sales(
            raw_rows,
            clients,
            islands,
            cliente_tipo,
            isla,
            direction,
            zero_consumption,
        )

    def listar_ranking_anual_clientes(
        self,
        year: int,
        limit: int = 10,
        direction: str = "asc",
    ) -> list[SalesCustomerAnnualComparisonRow]:
        current_year = int(year or 0)
        if current_year <= 0:
            return []
        previous_year = current_year - 1
        safe_limit = min(max(int(limit or 10), 1), 500)
        with Session(self._engine) as session:
            raw_rows = list(
                session.exec(
                    select(VentaClientesRaw).where(col(VentaClientesRaw.anio).in_([previous_year, current_year]))
                )
            )
            clients = list(session.exec(select(Cliente)))
            distributors = list(session.exec(select(Distribuidor)))
        party_by_id, _party_search_by_id = self._build_sales_party_lookup(clients, distributors)
        return self._build_annual_customer_ranking(raw_rows, party_by_id, current_year, safe_limit, direction)

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
                stmt = stmt.where(col(VentaMensualRaw.cliente_id) == clean_cliente_id)
            raw_rows = list(session.exec(stmt))
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
                stmt = stmt.where(col(VentaMensualRaw.cliente_id) == clean_cliente_id)
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
                stmt = stmt.where(col(VentaMensualRaw.cliente_id) == clean_cliente_id)
            prev_rows = list(session.exec(stmt))

            stmt = select(VentaMensualRaw).where(
                col(VentaMensualRaw.fuente) == "ireks",
                col(VentaMensualRaw.articulo_id) == clean_articulo_id,
                col(VentaMensualRaw.periodo).like(f"{current_year:04d}-%"),
            )
            if clean_cliente_id:
                stmt = stmt.where(col(VentaMensualRaw.cliente_id) == clean_cliente_id)
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
                prev_stmt = prev_stmt.where(col(VentaMensualRaw.cliente_id) == clean_cliente_id)
            prev_rows = list(session.exec(prev_stmt))

            curr_stmt = select(VentaMensualRaw).where(
                col(VentaMensualRaw.fuente) == "ireks",
                col(VentaMensualRaw.periodo).like(f"{current_year:04d}-%"),
            )
            if clean_cliente_id:
                curr_stmt = curr_stmt.where(col(VentaMensualRaw.cliente_id) == clean_cliente_id)
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

    def _build_annual_customer_sales(
        self,
        raw_rows,
        clients,
        islands,
        cliente_tipo: str,
        isla: str,
        direction: str,
        zero_consumption: bool = False,
    ) -> list[SalesCustomerAnnualSalesRow]:
        client_by_id = {str(row.cliente_id or "").strip(): row for row in clients}
        island_by_id = {str(row.isla_id or "").strip(): str(row.isla_nombre or "") for row in islands}
        clean_type = str(cliente_tipo or "").strip().lower()
        clean_island = self._normalize_search_text(isla)
        eligible_clients: dict[str, Cliente] = {}

        for cliente_id, client in client_by_id.items():
            row_type = str(getattr(client, "cliente_tipo", "") or "").strip()
            if clean_type and row_type.lower() != clean_type:
                continue
            island_id = str(getattr(client, "cliente_direccion_isla_id", "") or "").strip()
            island_name = island_by_id.get(island_id, "")
            if clean_island and self._normalize_search_text(island_name) != clean_island:
                continue
            eligible_clients[cliente_id] = client

        totals: dict[str, float] = defaultdict(float)
        for raw_row in raw_rows:
            cliente_id = str(getattr(raw_row, "cliente_id", "") or "").strip()
            if cliente_id not in eligible_clients:
                continue
            totals[cliente_id] += float(getattr(raw_row, "kg", 0.0) or 0.0)

        result: list[SalesCustomerAnnualSalesRow] = []
        candidates = (
            eligible_clients.items()
            if zero_consumption
            else ((cliente_id, eligible_clients[cliente_id]) for cliente_id in totals)
        )
        for cliente_id, client in candidates:
            kg = float(totals.get(cliente_id, 0.0) or 0.0)
            if zero_consumption and abs(kg) > 1e-9:
                continue
            island_id = str(getattr(client, "cliente_direccion_isla_id", "") or "").strip()
            result.append(
                SalesCustomerAnnualSalesRow(
                    cliente_id=cliente_id,
                    isla=island_by_id.get(island_id, ""),
                    cliente_codigo=str(getattr(client, "cliente_codigo", "") or ""),
                    cliente_nombre=str(
                        getattr(client, "cliente_nombre_comercial", "")
                        or getattr(client, "cliente_nombre_fiscal", "")
                        or cliente_id
                    ),
                    cliente_tipo=str(getattr(client, "cliente_tipo", "") or ""),
                    kg=kg,
                )
            )
        kg_factor = -1.0 if str(direction or "asc").strip().lower() == "desc" else 1.0
        result.sort(
            key=lambda row: (
                not bool(row.isla.strip()),
                row.isla.lower(),
                kg_factor * row.kg,
                row.cliente_nombre.lower(),
            )
        )
        return result

    def _build_annual_customer_ranking(
        self,
        raw_rows,
        party_by_id: dict[str, tuple[str, str]],
        current_year: int,
        safe_limit: int,
        direction: str,
    ) -> list[SalesCustomerAnnualComparisonRow]:
        totals = defaultdict(lambda: {"kg_prev": 0.0, "kg_curr": 0.0})
        for raw_row in raw_rows:
            cliente_id = str(getattr(raw_row, "cliente_id", "") or "").strip()
            if not cliente_id:
                continue
            key = "kg_curr" if int(getattr(raw_row, "anio", 0) or 0) == current_year else "kg_prev"
            totals[cliente_id][key] += float(getattr(raw_row, "kg", 0.0) or 0.0)

        result: list[SalesCustomerAnnualComparisonRow] = []
        for cliente_id, values in totals.items():
            code, name = party_by_id.get(cliente_id, ("", cliente_id))
            kg_prev = float(values["kg_prev"] or 0.0)
            kg_curr = float(values["kg_curr"] or 0.0)
            delta_kg = kg_curr - kg_prev
            result.append(
                SalesCustomerAnnualComparisonRow(
                    cliente_id=cliente_id,
                    cliente_codigo=str(code or ""),
                    cliente_nombre=str(name or cliente_id),
                    kg_prev=kg_prev,
                    kg_curr=kg_curr,
                    delta_kg=delta_kg,
                    delta_kg_pct=self._pct(delta_kg, kg_prev),
                )
            )
        reverse = str(direction or "asc").strip().lower() == "desc"
        result.sort(
            key=lambda row: (row.delta_kg, row.cliente_nombre.lower(), row.cliente_codigo.lower()),
            reverse=reverse,
        )
        return result[:safe_limit]

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
                getattr(distributor, "distribuidor_nombre_comercial", "")
                or getattr(distributor, "distribuidor_razon_social", "")
                or did
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

    def _pct(self, delta: float, base: float) -> float:
        if abs(base) <= 1e-9:
            return 0.0
        return (float(delta or 0.0) / float(base)) * 100.0

    def _normalize_search_text(self, value) -> str:
        text = str(value or "").strip().lower()
        normalized = unicodedata.normalize("NFD", text)
        normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
        return re.sub(r"\s+", " ", normalized)

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
