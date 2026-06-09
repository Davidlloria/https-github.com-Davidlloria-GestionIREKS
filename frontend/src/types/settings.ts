export interface MaintenanceStatus {
  db_path: string
  legacy_db_path: string
  db_exists: boolean
  legacy_exists: boolean
  db_size_bytes: number
  counts: Record<string, number>
  orphan_contact_links: number
}

export interface MaintenanceResult {
  ok: boolean
  message: string
  details: Record<string, unknown>
}

export interface ApiSettingsPayload {
  provider: string
  enabled: boolean
  config: Record<string, unknown>
}
