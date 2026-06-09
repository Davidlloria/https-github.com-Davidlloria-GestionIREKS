import { apiGet } from './http'
import type { IngredientDetail, IngredientListResponse } from '../types/api'

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
