export interface PaginatedList<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}
