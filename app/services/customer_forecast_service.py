"""Read-only catalogue and monetary calculations for customer supply forecasts."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from sqlmodel import Session, select

from app.core.database import engine
from app.models import Cliente, Distribuidor, IngredienteIreks, TarifaPrecioIreks


@dataclass(frozen=True)
class ForecastProduct:
    label: str
    price: Decimal | None


class CustomerForecastService:
    def __init__(self, db_engine=None):
        self.engine = db_engine if db_engine is not None else engine

    def catalog(self, customer_id: str, year: int) -> tuple[str, list[ForecastProduct]]:
        with Session(self.engine) as session:
            customer = session.get(Cliente, customer_id)
            if customer is None or not customer.distribuidor_id:
                raise ValueError("El cliente no tiene un distribuidor asignado.")
            distributor = session.get(Distribuidor, customer.distribuidor_id)
            if distributor is None:
                raise ValueError("No se encuentra el distribuidor del cliente.")
            products = session.exec(select(IngredienteIreks).where(
                IngredienteIreks.distribuidor_id == customer.distribuidor_id,
                IngredienteIreks.articulo_status_activo == True,  # noqa: E712
            ).order_by(IngredienteIreks.articulo_descripcion)).all()
            rates = session.exec(select(TarifaPrecioIreks).where(
                TarifaPrecioIreks.tarifa_ano == year,
            ).order_by(TarifaPrecioIreks.id)).all()
            prices = {rate.articulo_id: Decimal(str(rate.precio_distribuidor)) for rate in rates}
            result = []
            for product in products:
                price = prices.get(product.articulo_id)
                if price is not None and (not price.is_finite() or price <= 0):
                    price = None
                label = f"{product.articulo_referencia} · {product.articulo_descripcion}"
                result.append(ForecastProduct(label, price))
            name = distributor.distribuidor_nombre_comercial or distributor.distribuidor_razon_social
            return name, result

    @staticmethod
    def amount(quantity: int, price: Decimal | None) -> Decimal | None:
        if quantity <= 0:
            raise ValueError("La cantidad debe ser positiva.")
        if price is None:
            return None
        if not price.is_finite() or price <= 0:
            raise ValueError("El precio de tarifa debe ser positivo y finito.")
        return (Decimal(quantity) * price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
