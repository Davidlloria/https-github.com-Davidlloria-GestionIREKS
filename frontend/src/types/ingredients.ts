export interface IngredientIreksRead {
  id: number | null
  almacen_id: string
  fabricante_id: string
  distribuidor_id: string
  articulo_id: string
  articulo_referencia: string
  articulo_referencia_corta: string
  articulo_descripcion: string
  articulo_envase_id: string
  articulo_contenido_unidad: string
  articulo_envase_cantidad: number
  articulo_envase_peso: number
  articulo_envase_unidad_medida: string
  articulo_envase_peso_total: number
  transporte_pallet_tipo: string
  transporte_cajas_por_capa: number
  transporte_capas_por_pallet: number
  transporte_cajas_por_pallet: number
  transporte_unidades_por_pallet: number
  transporte_kg_por_pallet: number
  transporte_observaciones: string
  articulo_familia_id: string
  articulo_grupo_id: string
  articulo_subfamilia_id: string
  categoria: string
  articulo_status_activo: boolean
  articulo_status_en_lista: boolean
}

export interface IngredientIreksListPayload {
  items: IngredientIreksRead[]
  total: number
  limit: number
  offset: number
  catalogs: {
    distribuidores: Array<{ id: string; name: string }>
    fabricantes: Array<{ id: string; name: string }>
    familias: Array<{ id: string; name: string }>
    subfamilias: Array<{ id: string; name: string }>
    envases: Array<{ id: string; name: string }>
  }
}

export interface IngredientStdRead {
  articulo_id: string
  articulo_referencia_distribuidor: string
  proveedor_id: string
  distribuidor_id: string
  distribuidor_nombre: string
  articulo_descripcion: string
  articulo_grupo_id: string
  articulo_familia_id: string
  articulo_subfamilia_id: string
  categoria: string
  formato: string
  formato_cantidad: number
  formato_unidad: string
  pvp_formato: number
  pvp_unidad_medida: number
  activo: boolean
}

export interface NutritionValues {
  articulo_id: string
  energia_kj: number
  energia_kcal: number
  grasas_g: number
  saturadas_g: number
  hidratos_g: number
  azucares_g: number
  fibra_g: number
  proteinas_g: number
  sal_g: number
}

export interface TarifaPrecioIreksRead {
  id: number | null
  articulo_id: string
  tarifa_ano: number
  precio_fabricante: number
  precio_distribuidor: number
  descuento_pct: number
}

export interface MateriaPrimaPrecioRead {
  id: number | null
  articulo_id: string
  fecha_precio: string
  costo_neto: number
}
