export interface RecipeListItem {
  id: number | null
  cliente_id: string
  nombre: string
  codigo_receta: string
  version: string
  es_base: boolean
  receta_base_id: number | null
  masa_final_deseada_g: number
  peso_pieza_g: number
  numero_piezas: number
  observaciones: string
  proceso: string
  estado: string
  created_at: string | null
  updated_at: string | null
}

export interface RecipeListResponse {
  total: number
  limit: number
  offset: number
  items: RecipeListItem[]
}

export type RecipeDetail = RecipeListItem

export interface RecipeItem {
  id: number | null
  ingrediente_id: number | null
  nombre_mostrado: string
  codigo_ingrediente: string
  tipo_origen: string
  cantidad_base_g: number
  cantidad_calculada_g: number
  orden: number
  notas: string
}

export interface RecipeItemListResponse {
  total: number
  items: RecipeItem[]
}
