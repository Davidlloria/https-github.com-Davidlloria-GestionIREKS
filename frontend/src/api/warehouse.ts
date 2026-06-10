import { apiGet } from './http'
import type { InventoryDetailRead, InventoryHeaderRead, PaginatedList, WarehouseMovementRead, WarehouseStockRead } from '../types/api'

export function listStock(almacenId: string, limit?: number, offset?: number) {
  return apiGet<PaginatedList<WarehouseStockRead>>('/warehouse/stock', { almacen_id: almacenId, limit, offset })
}

export function listMovements(almacenId: string, limit?: number, offset?: number) {
  return apiGet<PaginatedList<WarehouseMovementRead>>('/warehouse/movements', { almacen_id: almacenId, limit, offset })
}

export function listInventoryHistory(almacenId: string, limit = 10, offset = 0) {
  return apiGet<PaginatedList<InventoryHeaderRead>>('/warehouse/inventory/history', {
    almacen_id: almacenId,
    limit,
    offset,
  })
}

export function getInventoryDetail(inventoryId: string) {
  return apiGet<InventoryDetailRead[]>(`/warehouse/inventory/${inventoryId}`)
}
