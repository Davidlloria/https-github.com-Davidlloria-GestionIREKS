import { apiGet } from './http'
import type { PaginatedList, RecipeDetail, RecipeItemListResponse, RecipeListItem } from '../types/api'

export function listRecipes(search: string, limit?: number, offset?: number) {
  return apiGet<PaginatedList<RecipeListItem>>('/recipes', { q: search, limit, offset })
}

export function getRecipeDetail(recipeId: number) {
  return apiGet<RecipeDetail>(`/recipes/${recipeId}`)
}

export function listRecipeItems(recipeId: number) {
  return apiGet<RecipeItemListResponse>(`/recipes/${recipeId}/items`)
}
