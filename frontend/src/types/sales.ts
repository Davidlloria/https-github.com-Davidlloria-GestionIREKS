export interface SalesYearOption {
  year: number
  label: string
}

export interface SalesYearOptionsResponse {
  items: SalesYearOption[]
}

export interface SalesFilterOption {
  id: string
  name: string
  code: string
  parent_id: string
}

export interface SalesFilterOptionsResponse {
  items: SalesFilterOption[]
}

export interface SalesAnnualSummaryRow {
  articulo_id: string
  fabricante_id: string
  familia_id: string
  subfamilia_id: string
  codigo: string
  nombre: string
  kilos_prev: number
  sc_prev: number
  ventas_prev: number
  kilos_curr: number
  sc_curr: number
  ventas_curr: number
  delta_kg: number
  delta_kg_pct: number
  delta_ventas: number
  delta_ventas_pct: number
}

export interface SalesAnnualSummaryResponse {
  source: 'ireks' | 'igsa'
  year: number
  month: number
  acumulado: boolean
  total: number
  items: SalesAnnualSummaryRow[]
}
