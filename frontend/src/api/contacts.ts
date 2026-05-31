import { apiDelete, apiGet, apiPatch, apiPost } from './http'
import type { ContactCompanyOption, ContactDetail, ContactListItem } from '../types/api'

export async function listContacts(search = ''): Promise<ContactListItem[]> {
  return apiGet<ContactListItem[]>('/contacts', { q: search })
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
