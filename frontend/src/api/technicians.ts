import { apiGet } from './http'
import type { PaginatedList, TechnicianDetail, TechnicianListItem } from '../types/api'

export async function listTechnicians(search = '', limit?: number, offset?: number): Promise<PaginatedList<TechnicianListItem>> {
  return apiGet<PaginatedList<TechnicianListItem>>('/technicians', { q: search, limit, offset })
}

export async function getTechnicianDetail(technicianId: string): Promise<TechnicianDetail> {
  return apiGet<TechnicianDetail>(`/technicians/${technicianId}`)
}
