import { apiDelete, apiGet, apiPatch, apiPost } from './http'
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

export function createIreksIngredient(payload: {
  almacen_id: string
  fabricante_id?: string
  distribuidor_id?: string
  articulo_id?: string
  articulo_referencia?: string
  articulo_referencia_corta?: string
  articulo_descripcion: string
  articulo_envase_id?: string
  articulo_contenido_unidad?: string
  articulo_envase_cantidad?: number
  articulo_envase_peso?: number
  articulo_envase_unidad_medida?: string
  transporte_pallet_tipo?: string
  transporte_cajas_por_capa?: number
  transporte_capas_por_pallet?: number
  transporte_observaciones?: string
  articulo_familia_id?: string
  articulo_grupo_id?: string
  articulo_subfamilia_id?: string
  categoria?: string
  articulo_status_activo?: boolean
  articulo_status_en_lista?: boolean
}) {
  return apiPost<IngredientIreksRead>('/ingredients/ireks', payload)
}

export function updateIreksIngredient(
  rowId: number,
  payload: {
    articulo_status_activo?: boolean
    articulo_status_en_lista?: boolean
    articulo_referencia?: string
    articulo_referencia_corta?: string
    articulo_descripcion?: string
    categoria?: string
  },
) {
  return apiPatch<IngredientIreksRead>(`/ingredients/ireks/${rowId}`, payload)
}

export function deleteIreksIngredient(rowId: number) {
  return apiDelete(`/ingredients/ireks/${rowId}`)
}

export function getIreksNutrition(articuloId: string) {
  return apiGet<NutritionValues | null>(`/ingredients/ireks/${articuloId}/nutrition`)
}

export function listIreksTarifas(articuloId: string) {
  return apiGet<TarifaPrecioIreksRead[]>(`/ingredients/ireks/${articuloId}/tarifas`)
}

export function createIreksTarifa(payload: {
  articulo_id: string
  tarifa_ano: number
  precio_fabricante: number
  precio_distribuidor: number
  descuento_pct: number
}) {
  return apiPost<TarifaPrecioIreksRead>('/ingredients/ireks/tarifas', payload)
}

export function updateIreksTarifa(
  tarifaId: number,
  payload: {
    tarifa_ano: number
    precio_fabricante: number
    precio_distribuidor: number
    descuento_pct: number
  },
) {
  return apiPatch<TarifaPrecioIreksRead>(`/ingredients/ireks/tarifas/${tarifaId}`, payload)
}

export function deleteIreksTarifa(tarifaId: number) {
  return apiDelete(`/ingredients/ireks/tarifas/${tarifaId}`)
}

export function listStdIngredients(search: string, activityFilter: string) {
  return apiGet<IngredientStdRead[]>('/ingredients/std', {
    q: search,
    activity_filter: activityFilter,
  })
}

export function createStdIngredient(payload: {
  articulo_id?: string
  articulo_referencia_distribuidor: string
  proveedor_id: string
  distribuidor_id?: string
  articulo_descripcion: string
  articulo_grupo_id?: string
  articulo_familia_id?: string
  articulo_subfamilia_id?: string
  categoria?: string
  formato?: string
  formato_cantidad?: number
  formato_unidad?: string
  pvp_formato?: number
  pvp_unidad_medida?: number
  activo?: boolean
}) {
  return apiPost<IngredientStdRead>('/ingredients/std', payload)
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

export function updateStdIngredient(
  articuloId: string,
  payload: {
    articulo_descripcion?: string
    pvp_formato?: number
    pvp_unidad_medida?: number
  },
) {
  return apiPatch<IngredientStdRead>(`/ingredients/std/${articuloId}`, payload)
}

export function deleteStdIngredient(articuloId: string) {
  return apiDelete(`/ingredients/std/${articuloId}`)
}
