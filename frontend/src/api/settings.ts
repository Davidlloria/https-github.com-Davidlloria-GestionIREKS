import { apiGet, apiPost, apiPut } from './http'
import type { ApiSettingsPayload, MaintenanceResult, MaintenanceStatus, WarehouseOption } from '../types/api'

export function getMaintenanceStatus() {
  return apiGet<MaintenanceStatus>('/settings/maintenance/status')
}

export function runMaintenanceIntegrityCheck() {
  return apiPost<MaintenanceResult>('/settings/maintenance/integrity-check')
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
