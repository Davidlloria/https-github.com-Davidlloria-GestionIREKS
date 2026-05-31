import { apiGet, apiPost, apiPut } from './http'
import type {
  ApiSettingsPayload,
  MaintenanceResult,
  MaintenanceStatus,
  OrderJsonImportResponse,
  WarehouseOption,
} from '../types/api'

export function getMaintenanceStatus() {
  return apiGet<MaintenanceStatus>('/settings/maintenance/status')
}

export function runMaintenanceIntegrityCheck() {
  return apiPost<MaintenanceResult>('/settings/maintenance/integrity-check')
}

export function runMaintenanceRepairContactLinks() {
  return apiPost<MaintenanceResult>('/settings/maintenance/repair-contact-links')
}

export function runMaintenanceCreateMissingContactClients() {
  return apiPost<MaintenanceResult>('/settings/maintenance/create-missing-contact-clients')
}

export function runMaintenanceOptimize() {
  return apiPost<MaintenanceResult>('/settings/maintenance/optimize')
}

export function runMaintenanceBackup(destinationPath: string) {
  return apiPost<MaintenanceResult>('/settings/maintenance/backup', {
    destination_path: destinationPath,
  })
}

export function getApiProviderSettings(provider: string) {
  return apiGet<ApiSettingsPayload>(`/settings/api/${provider}`)
}

export function saveApiProviderSettings(provider: string, config: Record<string, unknown>) {
  return apiPut<ApiSettingsPayload>(`/settings/api/${provider}`, {
    provider,
    enabled: true,
    config,
  })
}

export function listImportWarehouses() {
  return apiGet<WarehouseOption[]>('/settings/imports/warehouses')
}

export function importOrdersJsonFromSettings(payload: { almacen_id: string; file_path: string }) {
  return apiPost<OrderJsonImportResponse>('/settings/imports/orders-json', payload)
}
