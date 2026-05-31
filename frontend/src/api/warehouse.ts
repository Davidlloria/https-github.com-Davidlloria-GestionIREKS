import { apiGet, apiPost } from './http'
import type {
  InventoryHeaderRead,
  WarehouseManualMovementCreate,
  WarehouseMovementRead,
  WarehouseStockRead,
} from '../types/api'

export function listStock(almacenId: string) {
  return apiGet<WarehouseStockRead[]>('/warehouse/stock', { almacen_id: almacenId })
}

export function listMovements(almacenId: string) {
  return apiGet<WarehouseMovementRead[]>('/warehouse/movements', { almacen_id: almacenId })
}

export function listInventoryHistory(almacenId: string) {
  return apiGet<InventoryHeaderRead[]>('/warehouse/inventory/history', {
    almacen_id: almacenId,
    limit: 10,
  })
}

export function createManualMovement(payload: WarehouseManualMovementCreate) {
  return apiPost<WarehouseMovementRead>('/warehouse/movements', payload)
}
