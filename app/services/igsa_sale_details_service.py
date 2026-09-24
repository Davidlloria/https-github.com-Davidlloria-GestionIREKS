"""Read-only access to the individual records behind the IGSA summary."""
import json

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
        by_id = {p.articulo_id: p for p in products}
        by_code = {}
        for p in products:
            for code in (p.articulo_referencia, p.articulo_referencia_corta):
                if code:
                    by_code[str(code).strip().upper()] = p
        result = []
        for row in rows:
            try:
                payload = json.loads(row.payload_json or "{}")
            except (ValueError, TypeError):
                payload = {}
            if not isinstance(payload, dict):
                payload = {}
            product = by_id.get(row.articulo_id) or by_code.get(str(row.articulo_codigo_origen).strip().upper())
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
                issues.append("Importe pendiente: hay kilos vendidos, pero el importe guardado es cero. Revise la tarifa del producto y recalcule las ventas. No se trata de una salida sin cargo.")
            if any(term in observations.casefold() for term in ("diferencia entre", "no coincide", "no encontrado", "no reconocido")):
                issues.append("Incidencia anotada en el documento importado: " + observations)
            result.append(dict(
                articulo_id=article_id, codigo=code, periodo=row.periodo, tipo=kind,
                cantidad=quantity, peso=weight, kilos=kilos, precio=price, euros=euros,
                lote=str(payload.get("lote") or ""), caducidad=str(payload.get("caducidad") or payload.get("cons_pref") or ""),
                observaciones=observations, incidencias=issues, fuente=row.fuente,
            ))
        return sorted(result, key=lambda r: (r["periodo"], str(r["codigo"]), r["tipo"], r["lote"]))
