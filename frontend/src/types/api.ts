export interface CustomerListItem {
  cliente_id: string
  cliente_codigo: number
  cliente_nombre_comercial: string
  cliente_nombre_fiscal: string
  cliente_cif: string
  cliente_grupo: string
  cliente_tipo: string
  cliente_email: string
  cliente_telefono: string
  cliente_prospeccion: boolean
  activo: boolean
}

export interface CustomerDetail extends CustomerListItem {
  cliente_nombre_interno: string
  cliente_abreviatura: string
  cliente_direccion: string
  cliente_direccion_cp: string
  cliente_direccion_localidad_id: string
  cliente_direccion_municipio_id: string
  cliente_direccion_provincia_id: string
  cliente_direccion_isla_id: string
  distribuidor_id: string
}

export interface ContactListItem {
  contacto_id: string
  contacto_codigo: number
  cliente_id: string
  cliente_nombre: string
  nombre: string
  apellidos: string
  cargo: string
  nif: string
  telefono: string
  email: string
}

export interface ContactDetail extends ContactListItem {
  created_at: string | null
  updated_at: string | null
}

export interface ContactCompanyOption {
  cliente_id: string
  nombre: string
}

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
  rows: IngredientIreksRead[]
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

export interface MaintenanceStatus {
  db_path: string
  legacy_db_path: string
  db_exists: boolean
  legacy_exists: boolean
  db_size_bytes: number
  counts: Record<string, number>
  orphan_contact_links: number
}

export interface MaintenanceResult {
  ok: boolean
  message: string
  details: Record<string, unknown>
}

export interface ApiSettingsPayload {
  provider: string
  enabled: boolean
  config: Record<string, unknown>
}

export interface WarehouseOption {
  almacen_id: string
  almacen_nombre: string
}
