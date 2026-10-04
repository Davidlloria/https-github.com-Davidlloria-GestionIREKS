"""IGSA detail, audited manual corrections and monthly reconciliation."""
import json
import math
from datetime import datetime, timezone
from sqlalchemy import text, inspect, update
from app.services.sales_annual_comparison_service import SalesAnnualComparisonService

from sqlmodel import Session, col, select

from app.core.database import engine
from app.models import IngredienteIreks, VentaMensualRaw


class IgsaSaleDetailsService:
    def __init__(self, db_engine=None):
        self.engine = db_engine if db_engine is not None else engine

    def list_lines(self, year: int, month: int = 0, acumulado: bool = False) -> list[dict]:
        months = range(1, month + 1) if acumulado and month else [month] if month else range(1, 13)
        periods = [f"{y:04d}-{m:02d}" for y in (year - 1, year) for m in months]
        with Session(self.engine) as session:
            rows = list(session.exec(select(VentaMensualRaw).where(
                col(VentaMensualRaw.fuente).in_(["igsa", "igsa_pdf", "igsa_book"]),
                col(VentaMensualRaw.periodo).in_(periods),
            )))
            products = list(session.exec(select(IngredienteIreks)))
        matching = SalesAnnualComparisonService(self.engine)
        by_id = {p.articulo_id: p for p in products}
        by_code = {}
        for p in products:
            for code in (p.articulo_referencia, p.articulo_referencia_corta):
                for candidate in matching._code_candidates(code):
                    by_code.setdefault(candidate, p)
        result = []
        for row in rows:
            try:
                payload = json.loads(row.payload_json or "{}")
            except (ValueError, TypeError):
                payload = {}
            if not isinstance(payload, dict):
                payload = {}
            product = by_id.get(row.articulo_id) or next((by_code[c] for c in matching._code_candidates(row.articulo_codigo_origen) if c in by_code), None)
            article_id = product.articulo_id if product else row.articulo_id
            code = (product.articulo_referencia_corta or product.articulo_referencia) if product else row.articulo_codigo_origen
            kilos = float(row.venta_kilos or 0) + float(row.venta_kilos_sc or 0)
            euros = float(row.venta_euros or 0)
            quantity = payload.get("cantidad", payload.get("cantidad_lote", payload.get("envases")))
            weight = payload.get("envase_peso", payload.get("peso_envase"))
            price = payload.get("precio_kg_snapshot")
            if price is None and row.venta_kilos and euros:
                price = euros / row.venta_kilos
            kind = str(payload.get("tipo") or ("venta" if row.venta_kilos else "s/c")).strip().lower()
            kind = {"venta": "Venta", "muestra": "Muestra", "muestras": "Muestra", "promocion": "Promoción", "promociones": "Promoción", "s/c": "S/C"}.get(kind, kind)
            observations = str(payload.get("observaciones") or "").strip()
            issues = []
            if row.venta_kilos and not euros:
                issues.append("Importe pendiente: hay kilos vendidos, pero el importe guardado es cero. Revise la tarifa y corrija manualmente el importe si procede. No se trata de una salida sin cargo.")
            if not payload.get("incidencia_resuelta") and any(term in observations.casefold() for term in ("diferencia entre", "no coincide", "no encontrado", "no reconocido")):
                issues.append("Incidencia anotada en el documento importado: " + observations)
            result.append(dict(
                raw_id=row.raw_id, snapshot=self.snapshot(row),
                historial=payload.get("correcciones", []), resuelta=payload.get("incidencia_resuelta", False),
                articulo_id=article_id, codigo=code, periodo=row.periodo, tipo=kind,
                cantidad=quantity, peso=weight, kilos=kilos, precio=price, euros=euros,
                lote=str(payload.get("lote") or ""), caducidad=str(payload.get("caducidad") or payload.get("cons_pref") or ""),
                observaciones=observations, incidencias=issues, fuente=row.fuente,
            ))
        return sorted(result, key=lambda r: (r["periodo"], str(r["codigo"]), r["tipo"], r["lote"]))


    @staticmethod
    def snapshot(row):
        return {key: getattr(row, key) for key in (
            "articulo_id", "articulo_codigo_origen", "articulo_descripcion_origen",
            "venta_kilos", "venta_kilos_sc", "venta_euros", "payload_json",
            "periodo", "fuente", "cliente_id", "lote_id")}

    def products(self):
        with Session(self.engine) as session:
            return list(session.exec(select(IngredienteIreks).order_by(IngredienteIreks.articulo_descripcion)))

    def parties(self):
        return SalesAnnualComparisonService(self.engine).list_filter_clients()

    def correct(self, raw_id, expected, *, reason, values=None, resolved=False):
        if not reason.strip():
            raise ValueError("Indique el motivo de la corrección o revisión.")
        with Session(self.engine) as session:
            row = session.get(VentaMensualRaw, raw_id)
            if row is None or row.fuente not in {"igsa", "igsa_pdf", "igsa_book"}:
                raise ValueError("La línea IGSA ya no está disponible.")
            before = self.snapshot(row)
            if before != expected:
                raise ValueError("La línea ha cambiado. Cierre y vuelva a abrir el detalle.")
            try:
                payload = json.loads(row.payload_json or "{}")
            except ValueError as exc:
                raise ValueError("Los datos originales no son válidos; no se sobrescribirán.") from exc
            if not isinstance(payload, dict):
                raise ValueError("Los datos originales no son válidos.")
            if values is not None:
                if row.venta_kilos and row.venta_kilos_sc:
                    raise ValueError("Esta línea mezcla venta y sin cargo. Puede registrar su revisión, pero no sustituir ambos datos por una sola cantidad.")
                product = session.exec(select(IngredienteIreks).where(IngredienteIreks.articulo_id == values["articulo_id"])).first()
                if product is None:
                    raise ValueError("Seleccione un producto válido.")
                kind = values["tipo"]
                if kind not in {"venta", "muestra", "promocion", "s/c"}:
                    raise ValueError("Tipo de salida no válido.")
                quantity, weight, euros = (float(values[k]) for k in ("cantidad", "peso", "euros"))
                if not all(math.isfinite(n) for n in (quantity, weight, euros)) or weight <= 0:
                    raise ValueError("Los valores deben ser finitos y el peso mayor que cero.")
                if kind != "venta" and euros != 0:
                    raise ValueError("Una salida sin cargo debe tener importe cero.")
                kilos = quantity * weight
                if kilos == 0 and euros != 0:
                    raise ValueError("No puede asignar un importe a una venta de cero kilos.")
                if not math.isfinite(kilos):
                    raise ValueError("Cantidad fuera de rango.")
                row.articulo_id = product.articulo_id
                row.articulo_codigo_origen = product.articulo_referencia_corta or product.articulo_referencia
                row.articulo_descripcion_origen = product.articulo_descripcion
                row.venta_kilos = kilos if kind == "venta" else 0
                row.venta_kilos_sc = kilos if kind != "venta" else 0
                row.venta_euros = euros
                payload.update(cantidad=quantity, envase_peso=weight, tipo=kind,
                               precio_kg_snapshot=euros / kilos if kind == "venta" and kilos else 0)
            payload["incidencia_resuelta"] = bool(resolved)
            entry = dict(fecha=datetime.now(timezone.utc).isoformat(), motivo=reason.strip(),
                         resuelta=bool(resolved), anterior=before)
            # The original import payload and every revision remain available.
            history = list(payload.get("correcciones", []))
            history.append({k: v for k, v in entry.items() if k != "anterior"})
            payload["correcciones"] = history
            row.payload_json = json.dumps(payload, ensure_ascii=False)
            after = self.snapshot(row)
            session.expunge(row)
            statement = update(VentaMensualRaw).where(VentaMensualRaw.raw_id == raw_id)
            for key, value in before.items():
                statement = statement.where(getattr(VentaMensualRaw, key) == value)
            if session.execute(statement.values(**after)).rowcount != 1:
                raise ValueError("La línea ha cambiado. Vuelva a abrir el detalle.")
            session.execute(text("""CREATE TABLE IF NOT EXISTS igsa_manual_corrections (
                id INTEGER PRIMARY KEY AUTOINCREMENT, raw_id TEXT NOT NULL,
                fecha TEXT NOT NULL, motivo TEXT NOT NULL, anterior TEXT NOT NULL, posterior TEXT NOT NULL
            )"""))
            session.execute(text("""INSERT INTO igsa_manual_corrections
                (raw_id, fecha, motivo, anterior, posterior) VALUES (:raw, :date, :reason, :before, :after)"""),
                dict(raw=raw_id, date=entry["fecha"], reason=reason.strip(),
                     before=json.dumps(before, ensure_ascii=False), after=json.dumps(self.snapshot(row), ensure_ascii=False)))
            session.commit()

    def history(self, raw_id=None):
        if not inspect(self.engine).has_table("igsa_manual_corrections"):
            return []
        with self.engine.connect() as conn:
            return [dict(r._mapping) for r in conn.execute(text(
                "SELECT * FROM igsa_manual_corrections WHERE (:raw IS NULL OR raw_id=:raw) ORDER BY id"), dict(raw=raw_id))]

    def compare(self, year, month=0, acumulado=False, *, cliente_id):
        if not cliente_id:
            return []
        service = SalesAnnualComparisonService(self.engine)
        months = range(1, month + 1) if acumulado and month else [month] if month else range(1, 13)
        result = []
        periods = {f"{y}-{m:02d}" for y in (year - 1, year) for m in months}
        with Session(self.engine) as session:
            ids = service._resolve_sales_party_ids(session, cliente_id)
            raw = list(session.exec(select(VentaMensualRaw).where(col(VentaMensualRaw.periodo).in_(periods))))
            products = list(session.exec(select(IngredienteIreks)))
        by_id = {p.articulo_id: p.articulo_id for p in products}
        by_code = {service._normalize_code(code): p.articulo_id for p in products
                   for code in (p.articulo_referencia, p.articulo_referencia_corta) if code}
        igsa_codes = {}
        for product in products:
            for code in (product.articulo_referencia_corta, product.articulo_referencia):
                for candidate in service._code_candidates(code):
                    igsa_codes.setdefault(candidate, product.articulo_id)
        present_keys = set()
        for row in raw:
            source = "igsa" if row.fuente in {"igsa", "igsa_pdf", "igsa_book"} else "ireks" if row.fuente == "ireks" and row.cliente_id in ids else ""
            if source:
                code_match = next((igsa_codes[c] for c in service._code_candidates(row.articulo_codigo_origen) if c in igsa_codes), None) if source == "igsa" else by_code.get(service._normalize_code(row.articulo_codigo_origen))
                product_key = by_id.get(row.articulo_id) or code_match or "code:" + service._normalize_code(row.articulo_codigo_origen)
                present_keys.add((source, row.periodo, product_key))
        for m in months:
            igsa = service.listar_resumen_anual_igsa(year=year, month=m)
            ireks = service.listar_resumen_anual(year=year, month=m, cliente_id=cliente_id)
            left = {(r.articulo_id or "code:" + service._normalize_code(r.codigo)): r for r in igsa}
            right = {(r.articulo_id or "code:" + service._normalize_code(r.codigo)): r for r in ireks}
            for key in sorted(left.keys() | right.keys()):
                a, b = left.get(key), right.get(key)
                product = a or b
                for y, suffix in ((year - 1, "prev"), (year, "curr")):
                    # Existence is checked separately: an absent record is not zero.
                    period = f"{y}-{m:02d}"
                    has_a = ("igsa", period, key) in present_keys
                    has_b = ("ireks", period, key) in present_keys
                    if not has_a and not has_b:
                        continue
                    for field, label in (("kilos", "Kg vendidos"), ("sc", "Kg sin cargo")):
                        av = getattr(a, f"{field}_{suffix}") if a and has_a else None
                        bv = getattr(b, f"{field}_{suffix}") if b and has_b else None
                        delta = av - bv if av is not None and bv is not None else None
                        state = "Sin correspondencia" if not product.articulo_id else "Sin datos para comparar" if delta is None else "Diferencia" if abs(delta) > 0.001 else "Coincide"
                        result.append(dict(articulo_id=product.articulo_id, codigo=product.codigo,
                            nombre=product.nombre, periodo=f"{y}-{m:02d}", dato=label,
                            igsa=av, ireks=bv, diferencia=delta, estado=state))
        return result
