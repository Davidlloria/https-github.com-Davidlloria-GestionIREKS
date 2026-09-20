"""Annual objectives fed exclusively by IREKS monthly sales.

Scoring follows the July 2026 workbook, including truncation and its special
calendar rule. Configuration is stored beside the external database; opening
the page never changes sales or creates a campaign on disk.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
import json
import math
import os
from pathlib import Path
import re
import tempfile
import unicodedata

from sqlmodel import Session, select

from app.core.config import DATA_DIR
from app.core.database import engine
from app.models import Cliente, Distribuidor, Fabricante, Familia, Subfamilia, IngredienteIreks, VentaMensualRaw


BLOCKS = ("Productos y familias", "Lanzamientos", "Evolución de la zona", "Volumen total", "Extra")
MONTHS = ("Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre")


def normalized(value):
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    return " ".join(re.sub(r"[^a-z0-9]+", " ", "".join(c for c in text if not unicodedata.combining(c))).split())


def number(value):
    return Decimal(str(value or 0))


def fmt(value, suffix=""):
    if value is None:
        return "—"
    rounded = number(value).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
    return f"{rounded:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".") + suffix


@dataclass
class Objective:
    key: str
    name: str
    block: int
    target: float
    maximum: float
    target_type: str = "percent"
    unit: str = "kg"
    scope: str = "all"
    dimension: str = "all"
    members: list[str] = field(default_factory=list)
    status: str = "active"
    rule: str = "growth"


@dataclass
class ObjectiveResult:
    objective: Objective
    previous_year: Decimal | None
    annual_target: Decimal | None
    previous: Decimal | None
    current: Decimal | None
    delta: Decimal | None
    growth: Decimal | None
    points: Decimal | None
    status: str
    details: list[dict] = field(default_factory=list)


def score(objective, previous, current, annual_previous, month):
    """Return points, never substituting a guessed rule for missing inputs."""
    maximum, target = number(objective.maximum), number(objective.target)
    previous, current, annual_previous = map(number, (previous, current, annual_previous))
    if objective.status != "active":
        return Decimal(0)
    if objective.rule == "manual":
        return Decimal(0)
    if current == previous:
        return Decimal(0)  # The workbook's blank K cell short-circuits scoring.
    if objective.rule == "no_charge":
        return maximum if previous > 0 and current < previous else Decimal(0)
    if objective.target_type == "kg" and previous == 0 and current > 0:
        return maximum * (number(month) / 12).quantize(Decimal(".1"), rounding=ROUND_HALF_UP)
    if objective.target_type == "kg":
        if annual_previous <= 0:
            return None
        target = (target - annual_previous) / annual_previous
    else:
        target /= 100
    growth = (current - previous) / previous if previous else (Decimal(1) if current > 0 else Decimal(0))
    if target == 0:
        return maximum if growth >= 0 else Decimal(0)
    if target < 0:
        return None
    step = Decimal(4) if objective.rule == "quarter" else Decimal(1)
    points = (maximum * growth / target * step).to_integral_value(rounding=ROUND_DOWN) / step
    return max(Decimal(0), min(maximum, points))


class ObjectivesService:
    def __init__(self, db_engine=None, config_path=None):
        self.engine = db_engine if db_engine is not None else engine
        self.config_path = Path(config_path) if config_path else DATA_DIR / "objetivos.json"

    def _read(self):
        if not self.config_path.exists():
            return {"version": 1, "campaigns": {}}
        data = json.loads(self.config_path.read_text(encoding="utf-8"))
        if data.get("version") != 1 or not isinstance(data.get("campaigns"), dict):
            raise ValueError("El archivo de objetivos tiene un formato no compatible.")
        return data

    def catalog(self):
        with Session(self.engine) as session:
            families = {r.articulo_familia_id: r.articulo_familia_nombre for r in session.exec(select(Familia))}
            subfamilies = {r.articulo_subfamilia_id: r.articulo_subfamilia_nombre for r in session.exec(select(Subfamilia))}
            manufacturers = {r.fabricante_id: r.fabricante_nombre for r in session.exec(select(Fabricante))}
            products = {}
            for r in session.exec(select(IngredienteIreks)):
                products[r.articulo_id] = {"id": r.articulo_id, "code": r.articulo_referencia_corta or r.articulo_referencia,
                    "reference": r.articulo_referencia, "name": r.articulo_descripcion,
                    "family": r.articulo_familia_id, "subfamily": r.articulo_subfamilia_id, "manufacturer": r.fabricante_id}
            parties = {r.cliente_id: f"{r.cliente_codigo} · {r.cliente_nombre_comercial or r.cliente_nombre_fiscal}" for r in session.exec(select(Cliente))}
            party_names = {r.cliente_id: r.cliente_nombre_comercial or r.cliente_nombre_fiscal for r in session.exec(select(Cliente))}
            for r in session.exec(select(Distribuidor)):
                parties[r.distribuidor_id] = f"Distribuidor · {r.distribuidor_nombre_comercial}"
                party_names[r.distribuidor_id] = r.distribuidor_nombre_comercial
        return {"family": families, "subfamily": subfamilies, "manufacturer": manufacturers,
                "products": products, "parties": parties, "party_names": party_names}

    def default_campaign(self, catalog=None):
        c = catalog or self.catalog()
        scopes = {key: [] for key in ("igsa", "cadelsa", "hermanos", "baker")}
        for key, name in c["party_names"].items():
            n = normalized(name)
            if n == "igsa":
                scopes["igsa"].append(key)
            elif n.startswith(("cadelsa", "cadelpsa")):
                scopes["cadelsa"].append(key)
            elif n in ("hermanos rodriguez", "panaderia hermanos rodriguez"):
                scopes["hermanos"].append(key)
            elif "las arenas" in n and "gluten" in n:
                scopes["baker"].append(key)
        objectives = []
        def add(key, name, block, target, maximum, dimension="all", labels=(), **options):
            members = [i for i, label in c.get(dimension, {}).items() if normalized(label) in {normalized(x) for x in labels}]
            if dimension == "products":
                members = [i for i, product in c["products"].items() if normalized(product["name"]) in {normalized(x) for x in labels}]
            objectives.append(asdict(Objective(key, name, block, target, maximum, dimension=dimension, members=members, **options)))
        for key, name, target, maximum, family in (
            ("mejorantes", "Mejorantes", 3, 6, "MEJORANTES"),
            ("panaderia", "Mixes panadería", 2, 7, "PANES ESPECIALES"),
            ("pasteleria", "Mixes pastelería", 2, 6, "MIXES PASTELERIA"),
            ("ingredientes", "Ingredientes", 1, 6, "INGREDIENTES"),
            ("aromas", "Aromas para horneado", 5, 5, "AROMAS PARA HORNEADO"),
            ("pastas", "Pastas para pastelería", 3, 5, "PASTAS PARA PASTELERIA"),
            ("bases", "Bases pastelería (incluye Fond Royal)", 0, 5, "BASES PARA PASTELERIA")):
            add(key, name, 0, target, maximum, "family", (family,))
        # The report's 33D group includes Gelatop kg: this reconciles the annual
        # 2025 base and both July accumulated periods with the source workbook.
        add("dreidoppel", "Aumento general familia 33D", 0, 4, 5, "manufacturer", ("DREIDOPPEL", "GELATOP"))
        add("gelatop", "Ventas Gelatop", 0, 5, 5, "manufacturer", ("GELATOP",), unit="eur")
        add("ten", "Ten Sprouts", 1, 750, 4, "products", ("TEN SPROUTS",), target_type="kg", status="unmarketed")
        add("konig", "König Ludwig Brot y Rex Dinkel", 1, 100, 4, "products", ("KÖNIG LUDWIG-BROT", "REX DINKEL"))
        add("carrot", "Mella Carrot y Mella Algarroba", 1, 1500, 4, "products", ("MELLA CARROT", "MELLA ALGARROBA"), target_type="kg")
        add("brioche", "Mella Brioche", 1, 9, 4, "products", ("MELLA BRIOCHE",))
        add("pastas_nuevas", "Pasta Sandía, Spekulatius y Fruta de la Pasión", 1, 100, 4, "products", ("PASTA SANDÍA", "SPEKULATIUS CLARO", "PASTA FRUTA DE LA PASIÓN"))
        add("igsa_cadelsa", "IGSA / Cadelsa", 2, 2, 11, scope="distributors")
        add("panesa", "Tenerife · Panesa y Panem", 2, 4, 3, status="pending")
        add("baker", "Baker Las Arenas Sin Gluten", 2, 10, 2, scope="baker")
        add("madera", "Gran Canaria · La Madera", 2, 15, 3, status="pending")
        add("hermanos", "Hermanos Rodríguez", 2, 17, 4, scope="hermanos")
        add("sc", "Control de género sin cargo", 2, 0, 2, unit="sc", rule="no_charge")
        add("total", "Volumen total Canarias", 3, 3, 5, rule="quarter")
        for key, label, maximum in (("administracion", "Administración", 3), ("marketing", "Marketing", 4), ("tecnica", "Área Técnica", 3)):
            add(key, label, 4, 0, maximum, rule="manual")
        return {"year": 2026, "scopes": scopes, "objectives": objectives, "manual": {}}

    def years(self):
        return sorted({2026, *map(int, self._read()["campaigns"])}, reverse=True)

    def campaign(self, year):
        stored = self._read()["campaigns"].get(str(year))
        if stored is not None:
            self.validate(stored)
            return deepcopy(stored)
        if year == 2026:
            return self.default_campaign()
        raise ValueError("Crea la campaña y revisa sus metas antes de calcularla.")

    @staticmethod
    def validate(campaign):
        if not 2000 <= int(campaign["year"]) <= 2200:
            raise ValueError("Año fuera de rango.")
        if set(campaign["scopes"]) != {"igsa", "cadelsa", "hermanos", "baker"}:
            raise ValueError("Faltan orígenes de ventas.")
        seen = set()
        for raw in campaign["objectives"]:
            o = Objective(**raw)
            if not o.name.strip() or o.key in seen or not o.key:
                raise ValueError("Los objetivos necesitan nombre e identificador único.")
            seen.add(o.key)
            if not 0 <= o.block < len(BLOCKS) or o.target_type not in {"kg", "percent"} or o.status not in {"active", "pending", "unmarketed"}:
                raise ValueError("Tipo o estado de objetivo no válido.")
            if o.scope not in {"all", "distributors", "hermanos", "baker"} or o.dimension not in {"all", "family", "subfamily", "manufacturer", "products"}:
                raise ValueError("Selección de ventas no válida.")
            if o.unit not in {"kg", "eur", "sc"} or o.rule not in {"growth", "quarter", "no_charge", "manual"}:
                raise ValueError("Regla de cálculo no válida.")
            if any(not math.isfinite(float(v)) or float(v) < 0 for v in (o.target, o.maximum)):
                raise ValueError("Metas y puntos deben ser números positivos o cero.")
            if o.target_type == "kg" and o.status == "active" and o.target <= 0:
                raise ValueError("Una meta fija activa debe ser mayor de cero.")
            if o.rule == "manual" and o.block != 4:
                raise ValueError("Las valoraciones manuales pertenecen al bloque extra.")
        for month, values in campaign.get("manual", {}).items():
            if not 1 <= int(month) <= 12:
                raise ValueError("Mes de valoración no válido.")
            for key, value in values.items():
                obj = next((o for o in campaign["objectives"] if o["key"] == key and o["rule"] == "manual"), None)
                if obj is None or not math.isfinite(float(value)) or not 0 <= float(value) <= obj["maximum"]:
                    raise ValueError("Puntuación manual fuera de los límites del objetivo.")

    def save(self, campaign):
        self.validate(campaign)
        data = self._read()
        data["campaigns"][str(campaign["year"])] = deepcopy(campaign)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        name = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.config_path.parent, delete=False) as f:
                name = f.name
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(name, self.config_path)
        finally:
            if name and os.path.exists(name):
                os.unlink(name)

    def copy_campaign(self, source_year, year):
        if year in self.years():
            raise ValueError("La campaña ya existe.")
        campaign = self.campaign(source_year)
        campaign.update(year=year, manual={})
        return campaign

    @staticmethod
    def party_ids(campaign, scope="all"):
        groups = ("igsa", "cadelsa", "hermanos", "baker") if scope == "all" else (("igsa", "cadelsa") if scope == "distributors" else (scope,))
        return {i for key in groups for i in campaign["scopes"].get(key, [])}

    def latest_month(self, campaign):
        ids = self.party_ids(campaign)
        with Session(self.engine) as session:
            periods = session.exec(select(VentaMensualRaw.periodo).where(VentaMensualRaw.fuente == "ireks", VentaMensualRaw.cliente_id.in_(ids), VentaMensualRaw.periodo.like(f'{campaign["year"]}-%'))).all()
        months = [int(p[5:7]) for p in periods if re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", p)]
        return max(months, default=0)

    def calculate(self, campaign, month):
        self.validate(campaign)
        if not 1 <= month <= 12:
            raise ValueError("Selecciona un mes de enero a diciembre.")
        year = campaign["year"]
        catalog = self.catalog()
        parties = self.party_ids(campaign)
        with Session(self.engine) as session:
            sales = session.exec(select(VentaMensualRaw).where(VentaMensualRaw.fuente == "ireks", VentaMensualRaw.cliente_id.in_(parties), VentaMensualRaw.periodo >= f"{year-1}-01", VentaMensualRaw.periodo <= f"{year}-{month:02d}")).all()
        products = catalog["products"]
        codes = {}
        for key, product in products.items():
            for code in (product["code"], product["reference"]):
                if code:
                    codes.setdefault(normalized(code).replace(" ", ""), set()).add(key)
        records, unknown = [], set()
        for row in sales:
            if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", row.periodo):
                continue
            product_id = row.articulo_id
            if product_id not in products:
                candidates = codes.get(normalized(row.articulo_codigo_origen).replace(" ", ""), set())
                if len(candidates) == 1:
                    product_id = next(iter(candidates))
                else:
                    unknown.add(row.articulo_codigo_origen or product_id or "Sin referencia")
            records.append((row, product_id, int(row.periodo[:4]), int(row.periodo[5:7])))
        launch_ids = {i for o in campaign["objectives"] if o["block"] == 1 for i in o["members"]}
        issues = []
        for group, ids in campaign["scopes"].items():
            if not ids:
                issues.append(f"Sin vincular: {group}.")
        if unknown:
            issues.append(f"{len(unknown)} referencias de ventas sin producto vinculado: " + ", ".join(sorted(unknown)[:5]))
        for yr, end_month in ((year-1, 12), (year, month)):
            present = {m for _, _, y, m in records if y == yr}
            missing = set(range(1, end_month+1)) - present
            if missing:
                issues.append(f"Sin registros IREKS en {yr}: " + ", ".join(MONTHS[m-1] for m in sorted(missing)))
        results = []
        for raw in campaign["objectives"]:
            o = Objective(**raw)
            if o.rule == "manual":
                value = number(campaign.get("manual", {}).get(str(month), {}).get(o.key, 0))
                results.append(ObjectiveResult(o, None, None, None, None, None, None, value, "Valoración manual"))
                continue
            if o.status != "active":
                state = "Pendiente" if o.status == "pending" else "No comercializado"
                results.append(ObjectiveResult(o, None, None, None, None, None, None, Decimal(0), state))
                continue
            if o.dimension != "all" and (not o.members or any(i not in catalog[o.dimension] for i in o.members)):
                results.append(ObjectiveResult(o, None, None, None, None, None, None, None, "Sin productos vinculados"))
                issues.append(f"{o.name}: falta seleccionar productos o familias.")
                continue
            allowed = self.party_ids(campaign, o.scope)
            totals = [Decimal(0), Decimal(0), Decimal(0)]
            detail = {}
            for r, product_id, yr, m in records:
                if r.cliente_id not in allowed:
                    continue
                product = products.get(product_id, {})
                if o.dimension == "products" and product_id not in o.members:
                    continue
                if o.dimension in {"family", "subfamily", "manufacturer"} and product.get(o.dimension) not in o.members:
                    continue
                if o.unit == "sc" and product_id in launch_ids:
                    continue
                value = number(r.venta_euros) if o.unit == "eur" else (number(r.venta_kilos_sc) if o.unit == "sc" else number(r.venta_kilos) + number(r.venta_kilos_sc))
                key = product_id or r.articulo_codigo_origen
                item = detail.setdefault(key, {"code": product.get("code", r.articulo_codigo_origen), "name": product.get("name", r.articulo_descripcion_origen), "previous": Decimal(0), "current": Decimal(0)})
                if yr == year - 1:
                    totals[0] += value
                    if m <= month:
                        totals[1] += value
                        item["previous"] += value
                elif yr == year:
                    totals[2] += value
                    item["current"] += value
            annual, previous, current = totals
            target = number(o.target) if o.target_type == "kg" else annual * (1 + number(o.target) / 100)
            growth = (current - previous) / previous * 100 if previous else None
            points = score(o, previous, current, annual, month)
            state = "Calculado" if points is not None else "Regla pendiente"
            delta = current - previous
            if not any(y == year and r.cliente_id in allowed for r, _, y, _ in records):
                points, state, current, delta, growth = None, "Sin datos del año", None, None, None
            if not any(y == year - 1 and m <= month and r.cliente_id in allowed for r, _, y, m in records):
                points, state, previous, delta, growth = None, "Sin datos comparables", None, None, None
            results.append(ObjectiveResult(o, annual, target, previous, current, delta, growth, points, state, list(detail.values())))
        base_max = sum((number(r.objective.maximum) for r in results if r.objective.block < 4), Decimal(0))
        base = sum((r.points or Decimal(0) for r in results if r.objective.block < 4), Decimal(0))
        eligible = (base_max > 0 and base_max * Decimal(".45") <= base < base_max
                    and all(r.points is not None for r in results if r.objective.block < 4))
        extra = sum((r.points or Decimal(0) for r in results if r.objective.block == 4), Decimal(0)) if eligible else Decimal(0)
        for r in results:
            if r.objective.rule == "manual" and not eligible:
                r.status = "Extra no aplicable"
                r.points = Decimal(0)
        return {"year": year, "month": month, "results": results, "base": base, "base_max": base_max,
                "extra": extra, "total": base+extra, "extra_eligible": eligible, "issues": issues,
                "provisional": bool(issues) or any(r.points is None for r in results), "catalog": catalog}
