export interface CustomerListItem {
  cliente_id: string
  cliente_codigo: number
  cliente_nombre_comercial: string
  cliente_nombre_fiscal: string
  cliente_cif: string
  cliente_grupo: string
  cliente_tipo: string
  cliente_direccion_isla_id?: string
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
