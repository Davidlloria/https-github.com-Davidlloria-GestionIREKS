export interface CustomerListItem {
  cliente_id: string
  cliente_codigo: number
  cliente_nombre_comercial: string
  cliente_tipo: string
  cliente_email: string
  cliente_telefono: string
  cliente_prospeccion: boolean
  activo: boolean
}

export interface IngredientIreksRead {
  id: number | null
  articulo_id: string
  articulo_referencia: string
  articulo_descripcion: string
  articulo_envase_peso_total: number
  categoria: string
  articulo_status_activo: boolean
  articulo_status_en_lista: boolean
}

export interface IngredientIreksListPayload {
  rows: IngredientIreksRead[]
  catalogs: {
    distribuidores: Array<{ id: string; name: string }>
    fabricantes: Array<{ id: string; name: string }>
    familias: Array<{ id: string; name: string }>
    subfamilias: Array<{ id: string; name: string }>
    envases: Array<{ id: string; name: string }>
  }
}

export interface WarehouseStockRead {
  almacen_id: string
  articulo_id: string
  cantidad_total: number
}

export interface WarehouseMovementRead {
  id: number | null
  almacen_id: string
  articulo_id: string
  pedido_numero: string
  pedido_albaran_numero: string
  cantidad: number
  articulo_lote: string
  fecha_pedido: string
  albaran_item_id: string
}

export interface InventoryHeaderRead {
  inventario_id: string
  almacen_id: string
  fecha: string
  contador: string
  aprobador: string
  estado: string
  lineas: number
  ajustes: number
}
