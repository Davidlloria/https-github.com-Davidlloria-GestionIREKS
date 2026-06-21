import { apiDelete, apiGet, apiPatch, apiPost, apiPostBlob } from './http'
import type {
  CustomerAddressCatalogsPayload,
  CustomerDetail,
  CustomerListItem,
  CustomerListingRequest,
  CustomerListingResponse,
  PaginatedList,
} from '../types/api'

export interface CustomerSavePayload {
  cliente_id?: string
  cliente_codigo?: number | null
  cliente_nombre_comercial?: string
  cliente_nombre_fiscal?: string
  cliente_nombre_interno?: string
  cliente_abreviatura?: string
  cliente_cif?: string
  cliente_telefono?: string
  cliente_email?: string
  cliente_direccion?: string
  cliente_direccion_cp?: string
  cliente_direccion_localidad_id?: string
  cliente_direccion_municipio_id?: string
  cliente_direccion_provincia_id?: string
  cliente_direccion_isla_id?: string
  cliente_tipo?: string
  cliente_actividad?: string
  cliente_grupo?: string
  cliente_prospeccion?: boolean
  distribuidor_id?: string
  activo?: boolean
}

export function listCustomers(search: string, limit?: number, offset?: number) {
  return apiGet<PaginatedList<CustomerListItem>>('/customers', { q: search, limit, offset })
}

export function getCustomerDetail(customerId: string) {
  return apiGet<CustomerDetail>(`/customers/${customerId}`)
}

export function getCustomerAddressCatalogs() {
  return apiGet<CustomerAddressCatalogsPayload>('/customers/address-catalogs')
}

export function updateCustomerActive(customerId: string, active: boolean) {
  return apiPatch<CustomerDetail>(`/customers/${customerId}`, { activo: active })
}

export function deleteCustomer(customerId: string) {
  return apiDelete(`/customers/${customerId}`)
}

export function createCustomer(payload: CustomerSavePayload) {
  return apiPost<CustomerDetail>('/customers', payload)
}

export function updateCustomer(customerId: string, payload: CustomerSavePayload) {
  return apiPatch<CustomerDetail>(`/customers/${customerId}`, payload)
}

export function generateCustomerListing(prompt: string) {
  const payload: CustomerListingRequest = { prompt }
  return apiPost<CustomerListingResponse>('/customers/listings', payload)
}

export function exportCustomerListingPdf(payload: CustomerListingResponse) {
  return apiPostBlob('/customers/listings/pdf', payload)
}

export function exportCustomerListingXlsx(payload: CustomerListingResponse) {
  return apiPostBlob('/customers/listings/xlsx', payload)
}
