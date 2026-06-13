import { apiGet } from './http'
import type { IngredientDetail, IngredientIreksListPayload, IngredientIreksRead, IngredientListResponse } from '../types/api'

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
