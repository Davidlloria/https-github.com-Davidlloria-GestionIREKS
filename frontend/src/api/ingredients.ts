import { apiGet, apiPatch } from './http'
import type {
  IngredientIreksListPayload,
  IngredientIreksRead,
  IngredientStdRead,
  MateriaPrimaPrecioRead,
  NutritionValues,
  TarifaPrecioIreksRead,
} from '../types/api'

export function listIreksIngredients(search: string, activityFilter: string) {
  return apiGet<IngredientIreksListPayload>('/ingredients/ireks', {
    q: search,
    activity_filter: activityFilter,
  })
}

export function getIreksIngredientDetail(rowId: number) {
  return apiGet<IngredientIreksRead>(`/ingredients/ireks/${rowId}`)
}

export function getIreksNutrition(articuloId: string) {
  return apiGet<NutritionValues | null>(`/ingredients/ireks/${articuloId}/nutrition`)
}

export function listIreksTarifas(articuloId: string) {
  return apiGet<TarifaPrecioIreksRead[]>(`/ingredients/ireks/${articuloId}/tarifas`)
}

export function listStdIngredients(search: string, activityFilter: string) {
  return apiGet<IngredientStdRead[]>('/ingredients/std', {
    q: search,
    activity_filter: activityFilter,
  })
}

export function getStdIngredientDetail(articuloId: string) {
  return apiGet<IngredientStdRead>(`/ingredients/std/${articuloId}`)
}

export function getStdNutrition(articuloId: string) {
  return apiGet<NutritionValues | null>(`/ingredients/std/${articuloId}/nutrition`)
}

export function listStdPrices(articuloId: string) {
  return apiGet<MateriaPrimaPrecioRead[]>(`/ingredients/std/${articuloId}/prices`)
}

export function updateStdActive(articuloId: string, activo: boolean) {
  return apiPatch<IngredientStdRead>(`/ingredients/std/${articuloId}/active`, { activo })
}
