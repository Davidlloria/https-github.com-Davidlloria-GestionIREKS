import { apiGet } from './http'
import type {
  SalesAnnualSummaryResponse,
  SalesFilterOptionsResponse,
  SalesYearOptionsResponse,
} from '../types/api'

export type SalesSource = 'ireks' | 'igsa'

export interface SalesAnnualSummaryQuery {
  source?: SalesSource
  year: number
  month?: number
  acumulado?: boolean
  clienteId?: string
  articuloId?: string
  productoTexto?: string
  fabricanteId?: string
  familiaId?: string
  subfamiliaId?: string
}

function getSummaryPath(source: SalesSource) {
  return source === 'igsa' ? '/sales/annual-summary/igsa' : '/sales/annual-summary'
}

function getYearsPath(source: SalesSource) {
  return source === 'igsa' ? '/sales/annual-summary/igsa/years' : '/sales/annual-summary/years'
}

function getManufacturersPath(source: SalesSource) {
  return source === 'igsa'
    ? '/sales/annual-summary/igsa/filters/manufacturers'
    : '/sales/annual-summary/filters/manufacturers'
}

function getFamiliesPath(source: SalesSource) {
  return source === 'igsa'
    ? '/sales/annual-summary/igsa/filters/families'
    : '/sales/annual-summary/filters/families'
}

function getSubfamiliesPath(source: SalesSource) {
  return source === 'igsa'
    ? '/sales/annual-summary/igsa/filters/subfamilies'
    : '/sales/annual-summary/filters/subfamilies'
}

export function listSalesAnnualYears(source: SalesSource = 'ireks') {
  return apiGet<SalesYearOptionsResponse>(getYearsPath(source))
}

export function listSalesAnnualClients() {
  return apiGet<SalesFilterOptionsResponse>('/sales/annual-summary/filters/clients')
}

export function listSalesAnnualManufacturers(source: SalesSource = 'ireks') {
  return apiGet<SalesFilterOptionsResponse>(getManufacturersPath(source))
}

export function listSalesAnnualFamilies(source: SalesSource = 'ireks', fabricanteId?: string) {
  return apiGet<SalesFilterOptionsResponse>(getFamiliesPath(source), {
    fabricante_id: fabricanteId,
  })
}

export function listSalesAnnualSubfamilies(source: SalesSource = 'ireks', familiaId?: string) {
  return apiGet<SalesFilterOptionsResponse>(getSubfamiliesPath(source), {
    familia_id: familiaId,
  })
}

export function getSalesAnnualSummary(year: number, clienteId?: string): Promise<SalesAnnualSummaryResponse>
export function getSalesAnnualSummary(query: SalesAnnualSummaryQuery): Promise<SalesAnnualSummaryResponse>
export function getSalesAnnualSummary(
  arg1: number | SalesAnnualSummaryQuery,
  clienteId?: string,
): Promise<SalesAnnualSummaryResponse> {
  const query: SalesAnnualSummaryQuery =
    typeof arg1 === 'number'
      ? { year: arg1, clienteId }
      : arg1

  const source = query.source ?? 'ireks'

  return apiGet<SalesAnnualSummaryResponse>(getSummaryPath(source), {
    year: query.year,
    month: query.month,
    acumulado: query.acumulado ? 'true' : undefined,
    cliente_id: query.clienteId,
    articulo_id: query.articuloId,
    producto_texto: query.productoTexto,
    fabricante_id: query.fabricanteId,
    familia_id: query.familiaId,
    subfamilia_id: query.subfamiliaId,
  })
}
