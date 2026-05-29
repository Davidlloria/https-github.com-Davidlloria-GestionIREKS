from __future__ import annotations

from typing import Any, cast

from sqlmodel import Session, select

from app.core.database import engine
from app.models import IngredienteIreks, IngredienteStd, MateriaPrimaPrecio, MateriaPrimaValorNutricional, Receta, RecetaLinea
from app.repositories.recipe_repository import RecipeAggregate
from app.services.recipe_calculation_service import CalculationResult
from app.services.recipe_scaling_service import ScaleMode, ScalingResult
from app.viewmodels import IngredientChoice, RecipeViewModel


class RecipeService:
    def __init__(self) -> None:
        self.vm = RecipeViewModel()

    def search_ingredients(self, term: str = "") -> list[IngredientChoice]:
        with Session(engine) as session:
            return self.vm.search_ingredients(session, term)

    def list_recipes(self, term: str = "", cliente_id: str | None = None, es_base: bool | None = None) -> list[Receta]:
        with Session(engine) as session:
            return self.vm.list_recipes(session, term=term, cliente_id=cliente_id, es_base=es_base)

    def list_customers(self) -> list[Any]:
        with Session(engine) as session:
            return self.vm.list_customers(session)

    def search_customers(self, term: str = "") -> list[Any]:
        with Session(engine) as session:
            return self.vm.search_customers(session, term)

    def get_recipe(self, recipe_id: int, *, sync_categories: bool = False) -> RecipeAggregate | None:
        with Session(engine) as session:
            aggregate = self.vm.get_recipe(session, recipe_id)
            if aggregate and sync_categories:
                aggregate.lineas = self.vm.sync_line_categories(session, aggregate.lineas)
        return aggregate

    def sync_line_categories(self, lineas: list[RecetaLinea]) -> list[RecetaLinea]:
        with Session(engine) as session:
            return self.vm.sync_line_categories(session, lineas)

    def calculate(self, receta: Receta, lineas: list[RecetaLinea], *, sync_categories: bool = False) -> CalculationResult:
        if sync_categories:
            lineas = self.sync_line_categories(lineas)
        return self.vm.calculate(receta, lineas)

    def scale_recipe(
        self,
        receta: Receta,
        lineas: list[RecetaLinea],
        mode: ScaleMode,
        target_value_g: float,
        *,
        sync_categories: bool = False,
    ) -> ScalingResult:
        if sync_categories:
            lineas = self.sync_line_categories(lineas)
        return self.vm.scale_recipe(receta, lineas, mode, target_value_g)

    def save_recipe(self, receta: Receta, lineas: list[RecetaLinea], *, sync_categories: bool = False) -> RecipeAggregate:
        if sync_categories:
            lineas = self.sync_line_categories(lineas)
        result = self.vm.calculate(receta, lineas)
        with Session(engine) as session:
            return self.vm.save_recipe(session, result.receta, result.lineas)

    def save_version(self, receta: Receta, lineas: list[RecetaLinea], comentario: str = "") -> None:
        with Session(engine) as session:
            self.vm.save_version(session, receta, lineas, comentario)

    def duplicate_recipe(self, recipe_id: int, target_cliente_id: str | None = None) -> RecipeAggregate:
        with Session(engine) as session:
            return self.vm.duplicate_recipe(session, recipe_id, target_cliente_id)

    def delete_recipe(self, recipe_id: int) -> bool:
        with Session(engine) as session:
            return self.vm.delete_recipe(session, recipe_id)

    def std_prices_by_code(self) -> dict[str, float]:
        with Session(engine) as session:
            std_items = list(session.exec(select(IngredienteStd)))
            articulo_ids = [str(item.articulo_id or "").strip() for item in std_items if str(item.articulo_id or "").strip()]
            latest_price_by_articulo: dict[str, float] = {}
            if articulo_ids:
                price_rows = list(
                    session.exec(
                        select(MateriaPrimaPrecio)
                        .where(cast(Any, MateriaPrimaPrecio.articulo_id).in_(articulo_ids))
                        .order_by(
                            MateriaPrimaPrecio.articulo_id,
                            cast(Any, MateriaPrimaPrecio.fecha_precio).desc(),
                            cast(Any, MateriaPrimaPrecio.id).desc(),
                        )
                    )
                )
                for row in price_rows:
                    aid = str(getattr(row, "articulo_id", "") or "").strip()
                    if aid and aid not in latest_price_by_articulo:
                        latest_price_by_articulo[aid] = float(getattr(row, "costo_neto", 0.0) or 0.0)

        prices: dict[str, float] = {}
        for item in std_items:
            code = (item.codigo or "").strip().lower()
            if not code:
                continue
            articulo_id = str(item.articulo_id or "").strip()
            precio_formato = float(latest_price_by_articulo.get(articulo_id, 0.0) or 0.0)
            cantidad = float(getattr(item, "formato_cantidad", 0.0) or 0.0)
            if precio_formato > 0 and cantidad > 0:
                prices[code] = precio_formato / cantidad
            else:
                prices[code] = float(getattr(item, "precio_kg", 0.0) or 0.0)
        return prices

    def nutrition_lookup(
        self,
        ireks_codes: set[str],
        std_codes: set[str],
        unknown_codes: set[str],
    ) -> tuple[dict[str, str], dict[str, str], dict[str, MateriaPrimaValorNutricional]]:
        ireks_by_code: dict[str, str] = {}
        std_by_code: dict[str, str] = {}
        nutrition_by_articulo: dict[str, MateriaPrimaValorNutricional] = {}
        with Session(engine) as session:
            all_ireks_codes = set(ireks_codes) | set(unknown_codes)
            if all_ireks_codes:
                rows = list(
                    session.exec(
                        select(IngredienteIreks).where(cast(Any, IngredienteIreks.articulo_referencia).in_(all_ireks_codes))
                    )
                )
                ireks_by_code = {
                    str(getattr(row, "articulo_referencia", "") or "").strip(): str(getattr(row, "articulo_id", "") or "").strip()
                    for row in rows
                    if str(getattr(row, "articulo_referencia", "") or "").strip()
                    and str(getattr(row, "articulo_id", "") or "").strip()
                }
            all_std_codes = set(std_codes) | set(unknown_codes)
            if all_std_codes:
                rows = list(
                    session.exec(
                        select(IngredienteStd).where(cast(Any, IngredienteStd.articulo_referencia_distribuidor).in_(all_std_codes))
                    )
                )
                std_by_code = {
                    str(getattr(row, "articulo_referencia_distribuidor", "") or "").strip(): str(getattr(row, "articulo_id", "") or "").strip()
                    for row in rows
                    if str(getattr(row, "articulo_referencia_distribuidor", "") or "").strip()
                    and str(getattr(row, "articulo_id", "") or "").strip()
                }

            articulo_ids = set(ireks_by_code.values()) | set(std_by_code.values())
            if articulo_ids:
                nutrition_rows = list(
                    session.exec(
                        select(MateriaPrimaValorNutricional).where(cast(Any, MateriaPrimaValorNutricional.articulo_id).in_(articulo_ids))
                    )
                )
                nutrition_by_articulo = {
                    str(getattr(row, "articulo_id", "") or "").strip(): row
                    for row in nutrition_rows
                    if str(getattr(row, "articulo_id", "") or "").strip()
                }
        return ireks_by_code, std_by_code, nutrition_by_articulo
