import { apiGet } from './http'
import type { DistributorDetail, DistributorListItem, PaginatedList } from '../types/api'

export async function listDistributors(search = '', limit?: number, offset?: number): Promise<PaginatedList<DistributorListItem>> {
  return apiGet<PaginatedList<DistributorListItem>>('/distributors', { q: search, limit, offset })
}

export async function getDistributorDetail(distributorId: string): Promise<DistributorDetail> {
  return apiGet<DistributorDetail>(`/distributors/${distributorId}`)
}
