from dataclasses import dataclass, field

from app.models import Receta, RecetaLinea


@dataclass
class ValidationIssue:
    level: str
    message: str


@dataclass
class CalculationResult:
    receta: Receta
    lineas: list[RecetaLinea]
    issues: list[ValidationIssue] = field(default_factory=list)


class RecipeCalculationService:
    def calculate(self, receta: Receta, lineas: list[RecetaLinea]) -> CalculationResult:
        issues: list[ValidationIssue] = []

        total_harinas = sum(linea.cantidad_base_g for linea in lineas if linea.es_harina)
        total_liquidos = sum(linea.cantidad_base_g for linea in lineas if linea.es_liquido)

        if total_harinas <= 0:
            issues.append(ValidationIssue(level="error", message="La receta debe tener al menos una harina."))

        if receta.numero_piezas <= 0:
            issues.append(ValidationIssue(level="error", message="El numero de piezas debe ser mayor que 0."))

        for linea in lineas:
            if linea.ingrediente_id is None and not linea.nombre_mostrado:
                issues.append(ValidationIssue(level="warning", message=f"Linea {linea.orden}: sin ingrediente asignado."))

            if linea.precio_kg_snapshot <= 0:
                issues.append(ValidationIssue(level="warning", message=f"Linea {linea.orden}: ingrediente sin precio."))

            linea.porcentaje_panadero = (
                (linea.cantidad_base_g / total_harinas) * 100 if total_harinas > 0 else 0
            )

        total_panadero = sum(linea.porcentaje_panadero for linea in lineas)
        if total_panadero <= 0:
            issues.append(ValidationIssue(level="error", message="El total de porcentaje panadero no puede ser 0."))

        masa_objetivo = receta.masa_final_deseada_g if receta.masa_final_deseada_g > 0 else sum(
            linea.cantidad_base_g for linea in lineas
        )

        for linea in lineas:
            linea.cantidad_calculada_g = (
                masa_objetivo * linea.porcentaje_panadero / total_panadero if total_panadero > 0 else 0
            )
            linea.coste_linea = (linea.cantidad_calculada_g * linea.precio_kg_snapshot) / 1000

        coste_total = sum(linea.coste_linea for linea in lineas)
        masa_total = sum(linea.cantidad_calculada_g for linea in lineas)
        hidratacion = (total_liquidos / total_harinas * 100) if total_harinas > 0 else 0

        if hidratacion < 45 or hidratacion > 95:
            issues.append(
                ValidationIssue(level="warning", message=f"Hidratacion anomala detectada: {hidratacion:.2f}%")
            )

        receta.total_harinas_g = total_harinas
        receta.total_liquidos_g = total_liquidos
        receta.hidratacion_pct = hidratacion
        receta.total_porcentaje_panadero = total_panadero
        receta.masa_total_g = masa_total
        receta.coste_total = coste_total
        receta.coste_kg = coste_total / (masa_total / 1000) if masa_total > 0 else 0
        receta.coste_pieza = coste_total / receta.numero_piezas if receta.numero_piezas > 0 else 0

        return CalculationResult(receta=receta, lineas=lineas, issues=issues)

