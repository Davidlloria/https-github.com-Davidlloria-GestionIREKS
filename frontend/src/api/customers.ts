import { apiDelete, apiGet, apiPatch } from './http'
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
