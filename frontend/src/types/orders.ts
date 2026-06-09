export interface OrderRead {
  pedido_id: string
  almacen_id: string
  pedido_fecha: string
  pedido_numero: string
  pedido_albaran_numero: string
  pedido_factura_numero: string
  pedido_ref: string
  pedido_estado: string
}

export interface OrderListItem extends OrderRead {
  almacen_nombre: string
  semana: number
  total_kg: number
}

export interface OrderItemRead {
  item_id: string
  pedido_id: string
  pedido_numero: string
  pedido_albaran_numero: string
  pedido_item_fecha: string
  articulo_id: string
  articulo_cantidad: number
}

export interface OrderPendingRead {
  pendiente_id: string
  pedido_id: string
  albaran_id: string
  articulo_id: string
  cantidad_pedida: number
  cantidad_recibida: number
  cantidad_pendiente: number
  estado: string
  fecha_registro: string | null
}

export interface OrderJsonImportResponse {
  pedido_id: string
  imported_items: number
  skipped_unknown: string[]
  skipped_invalid: number
}

export interface OrderDocumentImportResponse {
  imported: number
  errors: string[]
  already_imported: boolean
  message: string
}
