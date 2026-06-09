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

export interface WarehouseManualMovementCreate {
  almacen_id: string
  articulo_id: string
  cantidad: number
  mode: 'in' | 'out'
  fecha_pedido: string
  articulo_lote: string
  pedido_albaran_numero: string
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

export interface InventoryAdjustmentInput {
  articulo_id: string
  articulo_lote: string
  articulo_caducidad: string | null
  teorico_uds: number
  conteo_uds: number
  diferencia_uds: number
  kg_ajuste: number
}

export interface InventoryAdjustmentPayload {
  almacen_id: string
  contador: string
  aprobador: string
  adjustments: InventoryAdjustmentInput[]
}

export interface WarehouseOption {
  almacen_id: string
  almacen_nombre: string
}
