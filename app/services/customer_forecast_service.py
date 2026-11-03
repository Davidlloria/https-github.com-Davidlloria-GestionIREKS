"""Read-only catalogue and monetary calculations for customer supply forecasts."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from sqlmodel import Session, select

from app.core.database import engine
from app.models import AlmacenCatalogo, AlmacenMovimiento, Cliente, IngredienteIreks, TarifaPrecioIreks
from app.services.warehouse_inventory_service import compute_current_stock_rows


@dataclass(frozen=True)
class ForecastProduct:
    label: str
    price: Decimal | None
    article_id: str = ""


@dataclass(frozen=True)
class ForecastLot:
    warehouse_id: str
    warehouse_name: str
    lot: str
    expiry: date | None
    available: Decimal


class CustomerForecastService:
    def __init__(self, db_engine=None):
        self.engine = db_engine if db_engine is not None else engine

    def catalog(self, customer_id: str, year: int) -> tuple[str, list[ForecastProduct]]:
        with Session(self.engine) as session:
            customer = session.get(Cliente, customer_id)
            if customer is None:
                raise ValueError("No se encuentra el cliente.")
            direct = (customer.cliente_tipo or "").strip().casefold() == "directo"
            price_field = "precio_fabricante" if direct else "precio_distribuidor"
            products = session.exec(select(IngredienteIreks).where(
                IngredienteIreks.articulo_status_activo == True,  # noqa: E712
            ).order_by(IngredienteIreks.articulo_descripcion)).all()
            rates = session.exec(select(TarifaPrecioIreks).where(
                TarifaPrecioIreks.tarifa_ano == year,
            ).order_by(TarifaPrecioIreks.id)).all()
            prices = {rate.articulo_id: Decimal(str(getattr(rate, price_field))) for rate in rates}
            result = []
            for product in products:
                price = prices.get(product.articulo_id)
                if price is not None and (not price.is_finite() or price <= 0):
                    price = None
                label = f"{product.articulo_referencia} · {product.articulo_descripcion}"
                result.append(ForecastProduct(label, price, product.articulo_id))
            return "IREKS" if direct else "IGSA", result

    def lots(self, article_id: str) -> list[ForecastLot]:
        if not article_id:
            return []
        with Session(self.engine) as session:
            moves = session.exec(select(AlmacenMovimiento).where(
                AlmacenMovimiento.articulo_id == article_id,
            )).all()
            warehouses = {w.almacen_id: w.almacen_nombre for w in session.exec(select(AlmacenCatalogo))}
        by_warehouse = {}
        for move in moves:
            by_warehouse.setdefault(move.almacen_id, []).append(move)
        result = []
        for warehouse_id, warehouse_moves in by_warehouse.items():
            for row in compute_current_stock_rows(warehouse_moves):
                result.append(ForecastLot(
                    warehouse_id, warehouses.get(warehouse_id) or warehouse_id or "Sin almacén",
                    row["lote"], row["caducidad"], Decimal(str(row["cantidad"])),
                ))
        return sorted(result, key=lambda lot: (lot.expiry or date.max, lot.warehouse_name, lot.lot))

    @staticmethod
    def amount(quantity: int, price: Decimal | None) -> Decimal | None:
        if quantity <= 0:
            raise ValueError("La cantidad debe ser positiva.")
        if price is None:
            return None
        if not price.is_finite() or price <= 0:
            raise ValueError("El precio de tarifa debe ser positivo y finito.")
        return (Decimal(quantity) * price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
