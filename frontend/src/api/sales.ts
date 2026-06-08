import { apiGet } from './http'
import type {
  SalesAnnualSummaryResponse,
  SalesFilterOptionsResponse,
  SalesYearOptionsResponse,
} from '../types/api'

export function listSalesAnnualYears() {
  return apiGet<SalesYearOptionsResponse>('/sales/annual-summary/years')
}

export function listSalesAnnualClients() {
  return apiGet<SalesFilterOptionsResponse>('/sales/annual-summary/filters/clients')
}

export function getSalesAnnualSummary(year: number, clienteId?: string) {
  return apiGet<SalesAnnualSummaryResponse>('/sales/annual-summary', {
    year,
    cliente_id: clienteId,
  })
}
