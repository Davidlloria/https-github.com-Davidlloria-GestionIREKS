import { apiGet } from './http'
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
