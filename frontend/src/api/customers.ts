import { apiDelete, apiGet, apiPatch, apiPost } from './http'
import type { CustomerDetail, CustomerListItem } from '../types/api'

export function listCustomers(search: string) {
  return apiGet<CustomerListItem[]>('/customers', { q: search })
}

export function getCustomerDetail(customerId: string) {
  return apiGet<CustomerDetail>(`/customers/${customerId}`)
}

export function updateCustomerActive(customerId: string, active: boolean) {
  return apiPatch<CustomerDetail>(`/customers/${customerId}`, { activo: active })
}

export function deleteCustomer(customerId: string) {
  return apiDelete(`/customers/${customerId}`)
}

export function createCustomer(payload: {
  cliente_id?: string
  cliente_nombre_comercial: string
  cliente_nombre_fiscal: string
  cliente_cif: string
  cliente_email: string
  cliente_telefono: string
  cliente_tipo: string
  cliente_grupo: string
  cliente_prospeccion: boolean
  activo: boolean
}) {
  return apiPost<CustomerDetail>('/customers', payload)
}

export function updateCustomer(
  customerId: string,
  payload: {
    cliente_nombre_comercial?: string
    cliente_nombre_fiscal?: string
    cliente_cif?: string
    cliente_email?: string
    cliente_telefono?: string
    cliente_tipo?: string
    cliente_grupo?: string
    cliente_prospeccion?: boolean
    activo?: boolean
  },
) {
  return apiPatch<CustomerDetail>(`/customers/${customerId}`, payload)
}
