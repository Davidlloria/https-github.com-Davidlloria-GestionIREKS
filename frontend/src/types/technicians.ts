export interface TechnicianListItem {
  tecnico_id: string
  tecnico_codigo: number
  nombre: string
  apellidos: string
  movil: string
  interno: string
  email: string
}

export interface TechnicianDetail extends TechnicianListItem {
  created_at: string | null
  updated_at: string | null
}
