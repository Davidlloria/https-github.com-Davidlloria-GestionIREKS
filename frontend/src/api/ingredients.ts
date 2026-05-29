import { apiGet } from './http'
import type { IngredientIreksListPayload } from '../types/api'

export function listIreksIngredients(search: string, activityFilter: string) {
  return apiGet<IngredientIreksListPayload>('/ingredients/ireks', {
    q: search,
    activity_filter: activityFilter,
  })
}
