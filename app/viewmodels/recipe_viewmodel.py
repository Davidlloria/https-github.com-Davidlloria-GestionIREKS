from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session

from app.models import Cliente, IngredienteIreks, IngredienteStd, Receta, RecetaLinea
from app.repositories import CustomerRepository, IngredientIreksRepository, IngredientStdRepository, RecipeRepository
from app.repositories.recipe_repository import RecipeAggregate
from app.services import CalculationResult, RecipeCalculationService


@dataclass
class IngredientChoice:
    tipo_origen: str
    ingrediente_id: int
    codigo: str
    nombre: str
    familia: str
    subfamilia: str
    precio_kg: float
    es_harina: bool
    es_liquido: bool


class RecipeViewModel:
    def __init__(
        self,
        recipe_repo: RecipeRepository | None = None,
        customer_repo: CustomerRepository | None = None,
        ireks_repo: IngredientIreksRepository | None = None,
        std_repo: IngredientStdRepository | None = None,
        calc_service: RecipeCalculationService | None = None,
    ) -> None:
        self.recipe_repo = recipe_repo or RecipeRepository()
        self.customer_repo = customer_repo or CustomerRepository()
        self.ireks_repo = ireks_repo or IngredientIreksRepository()
        self.std_repo = std_repo or IngredientStdRepository()
        self.calc_service = calc_service or RecipeCalculationService()

    def list_recipes(self, session: Session, term: str = "", cliente_id: int | None = None) -> list[Receta]:
        return self.recipe_repo.list(session, term, cliente_id)

    def get_recipe(self, session: Session, recipe_id: int) -> RecipeAggregate | None:
        return self.recipe_repo.get(session, recipe_id)

    def list_customers(self, session: Session) -> list[Cliente]:
        return self.customer_repo.list_all(session)

    def search_ingredients(self, session: Session, term: str = "") -> list[IngredientChoice]:
        ireks = self.ireks_repo.search(session, term)
        std = self.std_repo.search(session, term)
        results: list[IngredientChoice] = []
        for item in ireks:
            if not item.activo:
                continue
            results.append(
                IngredientChoice(
                    tipo_origen="ireks",
                    ingrediente_id=item.id or 0,
                    codigo=item.codigo,
                    nombre=item.nombre,
                    familia=item.familia,
                    subfamilia=item.subfamilia,
                    precio_kg=item.precio_kg,
                    es_harina=item.es_harina,
                    es_liquido=item.es_liquido,
                )
            )
        for item in std:
            if not item.activo:
                continue
            results.append(
                IngredientChoice(
                    tipo_origen="std",
                    ingrediente_id=item.id or 0,
                    codigo=item.codigo,
                    nombre=item.nombre,
                    familia=item.familia,
                    subfamilia=item.subfamilia,
                    precio_kg=item.precio_kg,
                    es_harina=item.es_harina,
                    es_liquido=item.es_liquido,
                )
            )
        return sorted(results, key=lambda x: (x.tipo_origen, x.nombre.lower()))

    def calculate(self, receta: Receta, lineas: list[RecetaLinea]) -> CalculationResult:
        return self.calc_service.calculate(receta, lineas)

    def save_recipe(self, session: Session, receta: Receta, lineas: list[RecetaLinea]) -> RecipeAggregate:
        return self.recipe_repo.save(session, receta, lineas)

    def delete_recipe(self, session: Session, recipe_id: int) -> bool:
        return self.recipe_repo.delete(session, recipe_id)

    def duplicate_recipe(self, session: Session, recipe_id: int, target_cliente_id: int | None = None) -> RecipeAggregate:
        aggregate = self.recipe_repo.get(session, recipe_id)
        if not aggregate:
            raise ValueError("Receta no encontrada")

        base = aggregate.receta
        cloned = Receta(
            cliente_id=target_cliente_id or base.cliente_id,
            nombre=f"{base.nombre} (Copia)",
            codigo_receta=f"{base.codigo_receta}-COPY",
            version="1.0",
            es_base=base.es_base,
            receta_base_id=base.receta_base_id,
            masa_final_deseada_g=base.masa_final_deseada_g,
            peso_pieza_g=base.peso_pieza_g,
            numero_piezas=base.numero_piezas,
            merma_pct=base.merma_pct,
            observaciones=base.observaciones,
            proceso=base.proceso,
            estado="borrador",
        )
        lines = []
        for line in aggregate.lineas:
            lines.append(
                RecetaLinea(
                    receta_id=0,
                    orden=line.orden,
                    tipo_origen=line.tipo_origen,
                    ingrediente_id=line.ingrediente_id,
                    nombre_mostrado=line.nombre_mostrado,
                    codigo_ingrediente=line.codigo_ingrediente,
                    familia=line.familia,
                    subfamilia=line.subfamilia,
                    es_harina=line.es_harina,
                    es_liquido=line.es_liquido,
                    cantidad_base_g=line.cantidad_base_g,
                    porcentaje_panadero=line.porcentaje_panadero,
                    cantidad_calculada_g=line.cantidad_calculada_g,
                    precio_kg_snapshot=line.precio_kg_snapshot,
                    coste_linea=line.coste_linea,
                    es_subreceta=line.es_subreceta,
                    subreceta_id=line.subreceta_id,
                    notas=line.notas,
                )
            )
        calc = self.calculate(cloned, lines)
        return self.recipe_repo.save(session, calc.receta, calc.lineas)

    def save_version(self, session: Session, receta: Receta, lineas: list[RecetaLinea], comentario: str = "") -> None:
        if not receta.id:
            raise ValueError("Debes guardar la receta antes de versionar")
        self.recipe_repo.save_version(session, receta, lineas, comentario)

