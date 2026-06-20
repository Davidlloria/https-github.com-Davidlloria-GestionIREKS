export interface AddressOption {
  id: string
  label: string
  parent_id: string
  code: string
}

export interface CustomerAddressCatalogsPayload {
  provincias: AddressOption[]
  islas: AddressOption[]
  municipios: AddressOption[]
  codigos_postales: AddressOption[]
  localidades: AddressOption[]
}

export type CustomerListingCell = string | number | boolean | null

export interface CustomerListingRequest {
  prompt: string
}

export interface CustomerListingResponse {
  status: string
  message: string
  title: string
  headers: string[]
  rows: CustomerListingCell[][]
  source: string
  used_ai: boolean
}

export interface CustomerListItem {
  cliente_id: string
  cliente_codigo: number
  cliente_nombre_comercial: string
  cliente_nombre_fiscal: string
  cliente_cif: string
  cliente_actividad: string
  cliente_grupo?: string
  cliente_tipo: string
  cliente_direccion_isla_id?: string
  cliente_direccion_isla?: string
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
  cliente_grupo?: string
}
