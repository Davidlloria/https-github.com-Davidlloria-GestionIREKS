import { apiGet } from './http'
import type { CustomerListItem } from '../types/api'

export function listCustomers(search: string) {
  return apiGet<CustomerListItem[]>('/customers', { q: search })
}
