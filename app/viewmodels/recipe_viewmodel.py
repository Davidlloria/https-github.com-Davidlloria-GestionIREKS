from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session
from sqlmodel import col, select

from app.models import Cliente, IngredienteIreks, IngredienteStd, MateriaPrimaPrecio, Receta, RecetaLinea, TarifaPrecioIreks
from app.repositories import CustomerRepository, IngredientIreksRepository, IngredientStdRepository, RecipeRepository
from app.repositories.recipe_repository import RecipeAggregate
from app.services import CalculationResult, RecipeCalculationService, RecipeScalingService, ScaleMode, ScalingResult


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
        scale_service: RecipeScalingService | None = None,
    ) -> None:
        self.recipe_repo = recipe_repo or RecipeRepository()
        self.customer_repo = customer_repo or CustomerRepository()
        self.ireks_repo = ireks_repo or IngredientIreksRepository()
        self.std_repo = std_repo or IngredientStdRepository()
        self.calc_service = calc_service or RecipeCalculationService()
        self.scale_service = scale_service or RecipeScalingService()

    def list_recipes(
        self,
        session: Session,
        term: str = "",
        cliente_id: str | None = None,
        es_base: bool | None = None,
    ) -> list[Receta]:
        return self.recipe_repo.list(session, term, cliente_id, es_base)

    def get_recipe(self, session: Session, recipe_id: int) -> RecipeAggregate | None:
        return self.recipe_repo.get(session, recipe_id)

    def list_customers(self, session: Session) -> list[Cliente]:
        return self.customer_repo.list_all(session)

    def search_customers(self, session: Session, term: str = "") -> list[Cliente]:
        return self.customer_repo.search(session, term)

    def search_ingredients(self, session: Session, term: str = "") -> list[IngredientChoice]:
        ireks = self.ireks_repo.search(session, term)
        std = self.std_repo.search(session, term)
        ireks_prices = self._build_ireks_tarifa_eur_kg_map(session, ireks)
        std_prices = self._build_std_price_map(session, std)
        results: list[IngredientChoice] = []
        for item in ireks:
            if not item.articulo_status_activo:
                continue
            eur_kg = float(ireks_prices.get(str(item.articulo_id or "").strip(), 0.0) or 0.0)
            results.append(
                IngredientChoice(
                    tipo_origen="ireks",
                    ingrediente_id=item.id or 0,
                    codigo=item.codigo,
                    nombre=item.nombre,
                    familia=item.familia,
                    subfamilia=item.subfamilia,
                    precio_kg=eur_kg,
                    es_harina=item.es_harina,
                    es_liquido=item.es_liquido,
                )
            )
        for item in std:
            if not item.activo:
                continue
            articulo_id = str(getattr(item, "articulo_id", "") or "").strip()
            results.append(
                IngredientChoice(
                    tipo_origen="std",
                    ingrediente_id=0,
                    codigo=item.codigo,
                    nombre=item.nombre,
                    familia=item.familia,
                    subfamilia=item.subfamilia,
                    precio_kg=float(std_prices.get(articulo_id, item.precio_kg) or 0.0),
                    es_harina=item.es_harina,
                    es_liquido=item.es_liquido,
                )
            )
        return sorted(results, key=lambda x: (x.tipo_origen, x.nombre.lower()))

    def _build_ireks_tarifa_eur_kg_map(
        self,
        session: Session,
        ireks_items: list[IngredienteIreks],
    ) -> dict[str, float]:
        articulo_ids = [str(item.articulo_id or "").strip() for item in ireks_items if str(item.articulo_id or "").strip()]
        if not articulo_ids:
            return {}

        tarifa_rows = list(
            session.exec(
                select(TarifaPrecioIreks)
                .where(col(TarifaPrecioIreks.articulo_id).in_(articulo_ids))
                .order_by(
                    col(TarifaPrecioIreks.articulo_id),
                    col(TarifaPrecioIreks.tarifa_ano).desc(),
                    col(TarifaPrecioIreks.id).desc(),
                )
            )
        )
        latest_tarifa_by_articulo: dict[str, TarifaPrecioIreks] = {}
        for row in tarifa_rows:
            articulo_id = str(getattr(row, "articulo_id", "") or "").strip()
            if articulo_id and articulo_id not in latest_tarifa_by_articulo:
                latest_tarifa_by_articulo[articulo_id] = row

        eur_kg_by_articulo: dict[str, float] = {}
        for item in ireks_items:
            articulo_id = str(item.articulo_id or "").strip()
            if not articulo_id:
                continue
            tarifa = latest_tarifa_by_articulo.get(articulo_id)
            if not tarifa:
                continue
            precio_distribuidor = float(getattr(tarifa, "precio_distribuidor", 0.0) or 0.0)
            total_kg = float(getattr(item, "articulo_envase_peso_total", 0.0) or 0.0)
            if total_kg <= 0:
                cantidad = float(getattr(item, "articulo_envase_cantidad", 0.0) or 0.0)
                peso = float(getattr(item, "articulo_envase_peso", 0.0) or 0.0)
                total_kg = cantidad * peso
            if total_kg > 0:
                eur_kg_by_articulo[articulo_id] = precio_distribuidor / total_kg
        return eur_kg_by_articulo

    def _build_std_price_map(
        self,
        session: Session,
        std_items: list[IngredienteStd],
    ) -> dict[str, float]:
        articulo_ids = [str(item.articulo_id or "").strip() for item in std_items if str(item.articulo_id or "").strip()]
        if not articulo_ids:
            return {}

        price_rows = list(
            session.exec(
                select(MateriaPrimaPrecio)
                .where(col(MateriaPrimaPrecio.articulo_id).in_(articulo_ids))
                .order_by(
                    col(MateriaPrimaPrecio.articulo_id),
                    col(MateriaPrimaPrecio.fecha_precio).desc(),
                    col(MateriaPrimaPrecio.id).desc(),
                )
            )
        )
        latest_price_by_articulo: dict[str, float] = {}
        for row in price_rows:
            aid = str(getattr(row, "articulo_id", "") or "").strip()
            if aid and aid not in latest_price_by_articulo:
                latest_price_by_articulo[aid] = float(getattr(row, "costo_neto", 0.0) or 0.0)

        eur_kg_by_articulo: dict[str, float] = {}
        for item in std_items:
            aid = str(item.articulo_id or "").strip()
            if not aid:
                continue
            precio_formato = float(latest_price_by_articulo.get(aid, 0.0) or 0.0)
            if precio_formato <= 0:
                continue
            cantidad = float(getattr(item, "formato_cantidad", 0.0) or 0.0)
            if cantidad > 0:
                eur_kg_by_articulo[aid] = precio_formato / cantidad
        return eur_kg_by_articulo

    def calculate(self, receta: Receta, lineas: list[RecetaLinea]) -> CalculationResult:
        return self.calc_service.calculate(receta, lineas)

    def scale_recipe(
        self,
        receta: Receta,
        lineas: list[RecetaLinea],
        mode: ScaleMode,
        target_value_g: float,
    ) -> ScalingResult:
        return self.scale_service.scale(receta, lineas, mode, target_value_g)

    def sync_line_categories(self, session: Session, lineas: list[RecetaLinea]) -> list[RecetaLinea]:
        try:
            ireks_map = {item.codigo.strip().lower(): item for item in self.ireks_repo.list_all(session) if item.codigo}
            std_map = {item.codigo.strip().lower(): item for item in self.std_repo.list_all(session) if item.codigo}
        except SQLAlchemyError as exc:
            # Si SQLite falla temporalmente (bloqueo, I/O, etc.), no detenemos el autosave.
            print(f"[RECETA] No se pudieron sincronizar categorías de líneas: {exc}")
            return lineas

        for linea in lineas:
            code = (linea.codigo_ingrediente or "").strip().lower()
            if not code:
                continue

            source = (linea.tipo_origen or "").strip().lower()
            matched = None
            if source == "ireks":
                matched = ireks_map.get(code)
            elif source == "std":
                matched = std_map.get(code)
            else:
                matched = ireks_map.get(code) or std_map.get(code)

            if not matched:
                continue

            linea.es_harina = bool(getattr(matched, "es_harina", False))
            linea.es_liquido = bool(getattr(matched, "es_liquido", False))

        return lineas

    def save_recipe(self, session: Session, receta: Receta, lineas: list[RecetaLinea]) -> RecipeAggregate:
        return self.recipe_repo.save(session, receta, lineas)

    def delete_recipe(self, session: Session, recipe_id: int) -> bool:
        return self.recipe_repo.delete(session, recipe_id)

    def duplicate_recipe(self, session: Session, recipe_id: int, target_cliente_id: str | None = None) -> RecipeAggregate:
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
            escandallo_detalle_json=base.escandallo_detalle_json,
            parametros_elaboracion_json=base.parametros_elaboracion_json,
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
                    tipo_linea=line.tipo_linea,
                    proceso_nombre=line.proceso_nombre,
                    proceso_origen_nombre=line.proceso_origen_nombre,
                    cantidad_origen_g=line.cantidad_origen_g,
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

