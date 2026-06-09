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
