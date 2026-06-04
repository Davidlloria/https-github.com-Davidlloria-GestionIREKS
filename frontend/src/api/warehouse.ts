import { apiGet, apiPost } from './http'
import type {
  InventoryAdjustmentPayload,
  InventoryHeaderRead,
  PaginatedList,
  WarehouseManualMovementCreate,
  WarehouseMovementRead,
  WarehouseStockRead,
} from '../types/api'

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

export function createManualMovement(payload: WarehouseManualMovementCreate) {
  return apiPost<WarehouseMovementRead>('/warehouse/movements', payload)
}

export function applyInventoryAdjustments(payload: InventoryAdjustmentPayload) {
  return apiPost<InventoryHeaderRead>('/warehouse/inventory/adjustments', payload)
}
