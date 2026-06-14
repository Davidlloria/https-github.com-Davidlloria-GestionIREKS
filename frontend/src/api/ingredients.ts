import { apiGet } from './http'
import type {
  IngredientDetail,
  IngredientIreksListPayload,
  IngredientIreksRead,
  IngredientStdRead,
  MateriaPrimaPrecioRead,
  IngredientListResponse,
} from '../types/api'

export type IngredientStdListResponse = {
  items: IngredientStdRead[]
  total: number
  limit: number
  offset: number
}

export function listIngredients(search: string, limit?: number, offset?: number) {
  return apiGet<IngredientListResponse>('/ingredients', {
    q: search,
    limit,
    offset,
  })
}

export function getIngredientDetail(ingredientId: string) {
  return apiGet<IngredientDetail>(`/ingredients/${ingredientId}`)
}

export function listIreksIngredients(search: string, limit?: number, offset?: number) {
  return apiGet<IngredientIreksListPayload>('/ingredients/ireks', {
    q: search,
    limit,
    offset,
  })
}

export function getIreksIngredientDetail(rowId: number) {
  return apiGet<IngredientIreksRead>(`/ingredients/ireks/${rowId}`)
}

export function listStdIngredients(search: string, limit?: number, offset?: number, activityFilter?: 'all' | 'active' | 'inactive') {
  return apiGet<IngredientStdListResponse>('/ingredients/std', {
    q: search,
    limit,
    offset,
    activity_filter: activityFilter,
  })
}

export function getStdIngredient(articuloId: string) {
  return apiGet<IngredientStdRead>(`/ingredients/std/${articuloId}`)
}

export function listStdIngredientPrices(articuloId: string) {
  return apiGet<MateriaPrimaPrecioRead[]>(`/ingredients/std/${articuloId}/prices`)
}
