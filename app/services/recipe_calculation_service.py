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


@dataclass
class _ProcessStats:
    harina_g: float = 0.0
    liquido_g: float = 0.0
    masa_g: float = 0.0
    coste: float = 0.0


class RecipeCalculationService:
    def _normalize_process_name(self, value: str | None) -> str:
        text = str(value or "").strip()
        return text if text else "Masa final"

    def _line_type(self, linea: RecetaLinea) -> str:
        raw = str(getattr(linea, "tipo_linea", "") or "").strip().lower()
        return raw if raw in {"ingrediente", "proceso"} else "ingrediente"

    def _ordered_processes(self, lineas: list[RecetaLinea]) -> list[str]:
        names: list[str] = []
        for linea in lineas:
            name = self._normalize_process_name(getattr(linea, "proceso_nombre", ""))
            if name not in names:
                names.append(name)
        if "Masa final" not in names:
            names.append("Masa final")
        return names

    def _compute_process_stats(self, process_name: str, lineas: list[RecetaLinea], stats_by_process: dict[str, _ProcessStats]) -> _ProcessStats:
        stats = _ProcessStats()
        process_lines = [
            line
            for line in lineas
            if self._normalize_process_name(getattr(line, "proceso_nombre", "")) == process_name
        ]
        for linea in process_lines:
            qty = float(getattr(linea, "cantidad_base_g", 0.0) or 0.0)
            if qty < 0:
                qty = 0.0
            if self._line_type(linea) == "proceso":
                source = self._normalize_process_name(getattr(linea, "proceso_origen_nombre", ""))
                source_stats = stats_by_process.get(source)
                source_masa = float(getattr(source_stats, "masa_g", 0.0) or 0.0) if source_stats else 0.0
                if source_stats and source_masa > 0:
                    ratio = qty / source_masa
                    stats.harina_g += float(source_stats.harina_g or 0.0) * ratio
                    stats.liquido_g += float(source_stats.liquido_g or 0.0) * ratio
                    stats.coste += float(source_stats.coste or 0.0) * ratio
                    stats.masa_g += qty
                else:
                    stats.masa_g += qty
                continue

            if bool(getattr(linea, "es_harina", False)):
                stats.harina_g += qty
            if bool(getattr(linea, "es_liquido", False)):
                stats.liquido_g += qty
            eur_kg = float(getattr(linea, "precio_kg_snapshot", 0.0) or 0.0)
            if eur_kg > 0:
                stats.coste += (qty * eur_kg) / 1000.0
            stats.masa_g += qty
        return stats

    def calculate(self, receta: Receta, lineas: list[RecetaLinea]) -> CalculationResult:
        issues: list[ValidationIssue] = []
        process_order = self._ordered_processes(lineas)
        stats_by_process: dict[str, _ProcessStats] = {}
        for proc in process_order:
            stats_by_process[proc] = self._compute_process_stats(proc, lineas, stats_by_process)

        total_harinas = sum(float(x.harina_g or 0.0) for x in stats_by_process.values())
        total_liquidos = sum(float(x.liquido_g or 0.0) for x in stats_by_process.values())

        if total_harinas <= 0:
            issues.append(ValidationIssue(level="error", message="La receta debe tener al menos una harina."))

        if receta.numero_piezas <= 0:
            issues.append(ValidationIssue(level="error", message="El numero de piezas debe ser mayor que 0."))

        for linea in lineas:
            linea.proceso_nombre = self._normalize_process_name(getattr(linea, "proceso_nombre", ""))
            if self._line_type(linea) == "proceso":
                source = self._normalize_process_name(getattr(linea, "proceso_origen_nombre", ""))
                linea.proceso_origen_nombre = source
                if source == linea.proceso_nombre:
                    issues.append(
                        ValidationIssue(
                            level="error",
                            message=f"Linea {linea.orden}: un proceso no puede consumir su propio proceso origen.",
                        )
                    )
                qty_source = float(getattr(linea, "cantidad_origen_g", 0.0) or 0.0)
                if qty_source <= 0:
                    qty_source = float(getattr(linea, "cantidad_base_g", 0.0) or 0.0)
                linea.cantidad_origen_g = max(qty_source, 0.0)
                linea.cantidad_base_g = linea.cantidad_origen_g
                if source not in stats_by_process:
                    issues.append(
                        ValidationIssue(
                            level="warning",
                            message=f"Linea {linea.orden}: proceso origen '{source}' no encontrado.",
                        )
                    )
                source_stats = stats_by_process.get(source)
                source_masa = float(getattr(source_stats, "masa_g", 0.0) or 0.0) if source_stats else 0.0
                harina_equiv = 0.0
                if source_stats and source_masa > 0:
                    harina_equiv = float(source_stats.harina_g or 0.0) * (linea.cantidad_base_g / source_masa)
                linea.porcentaje_panadero = ((harina_equiv / total_harinas) * 100) if total_harinas > 0 else 0.0
                continue

            if linea.ingrediente_id is None and not linea.nombre_mostrado:
                issues.append(ValidationIssue(level="warning", message=f"Linea {linea.orden}: sin ingrediente asignado."))

            if linea.precio_kg_snapshot <= 0:
                issues.append(ValidationIssue(level="warning", message=f"Linea {linea.orden}: ingrediente sin precio."))

            # % panadero: cada ingrediente se expresa sobre el total de harinas.
            qty = float(linea.cantidad_base_g or 0.0)
            linea.porcentaje_panadero = ((qty / total_harinas) * 100) if total_harinas > 0 else 0.0

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
            if self._line_type(linea) == "proceso":
                source = self._normalize_process_name(getattr(linea, "proceso_origen_nombre", ""))
                source_stats = stats_by_process.get(source)
                source_masa = float(getattr(source_stats, "masa_g", 0.0) or 0.0) if source_stats else 0.0
                cost_per_g = (float(source_stats.coste or 0.0) / source_masa) if source_stats and source_masa > 0 else 0.0
                linea.coste_linea = float(linea.cantidad_calculada_g or 0.0) * cost_per_g
            else:
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
