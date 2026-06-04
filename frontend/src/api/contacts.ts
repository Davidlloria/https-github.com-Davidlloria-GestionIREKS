import { apiDelete, apiGet, apiPatch, apiPost } from './http'
import type { ContactCompanyOption, ContactDetail, ContactListItem, PaginatedList } from '../types/api'

export async function listContacts(search = '', companyId = '', limit?: number, offset?: number): Promise<PaginatedList<ContactListItem>> {
  return apiGet<PaginatedList<ContactListItem>>('/contacts', { q: search, cliente_id: companyId, limit, offset })
}

export async function listContactCompanies(): Promise<ContactCompanyOption[]> {
  return apiGet<ContactCompanyOption[]>('/contacts/companies')
}

export async function getContactDetail(contactId: string): Promise<ContactDetail> {
  return apiGet<ContactDetail>(`/contacts/${contactId}`)
}

export async function createContact(payload: {
  cliente_id: string
  nombre: string
  apellidos: string
  cargo: string
  nif: string
  telefono: string
  email: string
}): Promise<ContactDetail> {
  return apiPost<ContactDetail>('/contacts', payload)
}

export async function updateContact(
  contactId: string,
  payload: {
    cliente_id?: string
    nombre?: string
    apellidos?: string
    cargo?: string
    nif?: string
    telefono?: string
    email?: string
  },
): Promise<ContactDetail> {
  return apiPatch<ContactDetail>(`/contacts/${contactId}`, payload)
}

export async function deleteContact(contactId: string): Promise<void> {
  return apiDelete(`/contacts/${contactId}`)
}
