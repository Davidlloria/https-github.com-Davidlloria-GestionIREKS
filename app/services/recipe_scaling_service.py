from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.models import Receta, RecetaLinea

ScaleMode = Literal["flour", "dough", "pieces"]


@dataclass
class ScalingResult:
    receta: Receta
    lineas: list[RecetaLinea]
    mode: ScaleMode
    factor: float
    source_value: float
    target_value: float


class RecipeScalingService:
    def scale(self, receta: Receta, lineas: list[RecetaLinea], mode: ScaleMode, target_value_g: float) -> ScalingResult:
        if target_value_g <= 0:
            raise ValueError("El valor objetivo debe ser mayor que 0.")
        if mode not in {"flour", "dough", "pieces"}:
            raise ValueError("Modo de escalado no valido.")

        scaled_receta = Receta(**receta.model_dump())
        scaled_lineas = [RecetaLinea(**linea.model_dump()) for linea in lineas]

        current_flour_g = sum(float(linea.cantidad_base_g or 0.0) for linea in scaled_lineas if linea.es_harina)
        current_total_g = sum(float(linea.cantidad_base_g or 0.0) for linea in scaled_lineas)

        if mode == "flour":
            if current_flour_g <= 0:
                raise ValueError("La receta no tiene lineas marcadas como harina.")
            source_value = current_flour_g
        elif mode == "dough":
            if current_total_g <= 0:
                raise ValueError("La receta no tiene masa para escalar.")
            source_value = current_total_g
        else:
            if scaled_receta.numero_piezas <= 0:
                raise ValueError("La receta no tiene un numero de piezas valido para escalar.")
            source_value = float(scaled_receta.numero_piezas)

        factor = float(target_value_g) / float(source_value)

        for linea in scaled_lineas:
            linea.cantidad_base_g = float(linea.cantidad_base_g or 0.0) * factor

        scaled_total_g = sum(float(linea.cantidad_base_g or 0.0) for linea in scaled_lineas)
        scaled_receta.masa_final_deseada_g = scaled_total_g

        if mode == "pieces":
            scaled_receta.numero_piezas = max(int(round(float(target_value_g))), 1)
        elif scaled_receta.peso_pieza_g > 0 and scaled_total_g > 0:
            pieces = int(round(scaled_total_g / float(scaled_receta.peso_pieza_g)))
            scaled_receta.numero_piezas = max(pieces, 1)

        return ScalingResult(
            receta=scaled_receta,
            lineas=scaled_lineas,
            mode=mode,
            factor=factor,
            source_value=source_value,
            target_value=float(target_value_g),
        )
