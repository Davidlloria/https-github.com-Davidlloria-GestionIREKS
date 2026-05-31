import { useMemo, useState } from 'react'
import {
  getApiProviderSettings,
  getMaintenanceStatus,
  listImportWarehouses,
  runMaintenanceIntegrityCheck,
  saveApiProviderSettings,
} from '../api/settings'
import { QueryState } from '../components/QueryState'
import { StatCard } from '../components/StatCard'
import { useAsyncResource } from '../features/useAsyncResource'
import type { ApiSettingsPayload, MaintenanceResult } from '../types/api'

interface ProviderRow {
  provider: string
  status: 'ok' | 'error'
  enabled: boolean
  config: Record<string, unknown>
  error: string
}

const PROVIDERS = ['fdc', 'openai', 'fatsecret', 'orders_mail', 'warehouse'] as const

function formatBytes(value: number) {
  const bytes = Number(value)
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return '0 B'
  }
  const mb = bytes / (1024 * 1024)
  if (mb < 1) {
    return `${(bytes / 1024).toFixed(1)} KB`
  }
  return `${mb.toFixed(2)} MB`
}

export function SettingsPage() {
  const [integrityRun, setIntegrityRun] = useState<MaintenanceResult | null>(null)
  const [integrityLoading, setIntegrityLoading] = useState(false)
  const [integrityError, setIntegrityError] = useState('')
  const [warehouseThresholdInput, setWarehouseThresholdInput] = useState('')
  const [warehouseSaveLoading, setWarehouseSaveLoading] = useState(false)
  const [warehouseSaveMessage, setWarehouseSaveMessage] = useState('')
  const [warehouseSaveError, setWarehouseSaveError] = useState('')

  const maintenanceQuery = useAsyncResource(() => getMaintenanceStatus(), null, [])
  const providerQuery = useAsyncResource(async () => {
    const settled = await Promise.allSettled(PROVIDERS.map((provider) => getApiProviderSettings(provider)))
    return settled.map((result, index) => {
      const provider = PROVIDERS[index]
      if (result.status === 'fulfilled') {
        const value: ApiSettingsPayload = result.value
        return {
          provider,
          status: 'ok' as const,
          enabled: value.enabled,
          config: value.config,
          error: '',
        }
      }
      return {
        provider,
        status: 'error' as const,
        enabled: false,
        config: {},
        error: result.reason instanceof Error ? result.reason.message : 'Error de carga',
      }
    })
  }, [] as ProviderRow[], [])
  const importsQuery = useAsyncResource(() => listImportWarehouses(), [], [])

  const warehouseProvider = useMemo(
    () => providerQuery.data.find((row) => row.provider === 'warehouse' && row.status === 'ok') ?? null,
    [providerQuery.data],
  )

  const effectiveThresholdInput = useMemo(() => {
    if (warehouseThresholdInput) {
      return warehouseThresholdInput
    }
    const rawValue = warehouseProvider?.config?.low_stock_threshold_units
    if (rawValue === undefined || rawValue === null) {
      return ''
    }
    return String(rawValue)
  }, [warehouseProvider, warehouseThresholdInput])

  const totals = useMemo(() => {
    if (!maintenanceQuery.data) {
      return {
        dbSize: '0 B',
        tablesWithData: 0,
        rowsTracked: 0,
      }
    }
    const counts = Object.values(maintenanceQuery.data.counts)
    const tablesWithData = counts.filter((value) => Number(value) > 0).length
    const rowsTracked = counts.reduce((acc, value) => acc + Number(value || 0), 0)
    return {
      dbSize: formatBytes(maintenanceQuery.data.db_size_bytes),
      tablesWithData,
      rowsTracked,
    }
  }, [maintenanceQuery.data])

  const sortedCounts = useMemo(() => {
    if (!maintenanceQuery.data) {
      return [] as Array<{ table: string; count: number }>
    }
    return Object.entries(maintenanceQuery.data.counts)
      .map(([table, count]) => ({ table, count: Number(count || 0) }))
      .sort((a, b) => b.count - a.count || a.table.localeCompare(b.table))
  }, [maintenanceQuery.data])

  const runIntegrity = async () => {
    setIntegrityLoading(true)
    setIntegrityError('')
    try {
      const result = await runMaintenanceIntegrityCheck()
      setIntegrityRun(result)
      maintenanceQuery.reload()
    } catch (error: unknown) {
      setIntegrityError(error instanceof Error ? error.message : 'Error al ejecutar integridad')
    } finally {
      setIntegrityLoading(false)
    }
  }

  const saveWarehouseThreshold = async () => {
    if (warehouseSaveLoading) {
      return
    }
    const numeric = Number.parseFloat(effectiveThresholdInput.replace(',', '.'))
    if (!Number.isFinite(numeric) || numeric < 0) {
      setWarehouseSaveError('El umbral debe ser numerico y mayor o igual que 0.')
      setWarehouseSaveMessage('')
      return
    }
    setWarehouseSaveLoading(true)
    setWarehouseSaveError('')
    setWarehouseSaveMessage('')
    try {
      await saveApiProviderSettings('warehouse', { low_stock_threshold_units: numeric })
      await providerQuery.reload()
      setWarehouseThresholdInput(String(numeric))
      setWarehouseSaveMessage('Umbral de stock guardado.')
    } catch (error: unknown) {
      setWarehouseSaveError(error instanceof Error ? error.message : 'No se pudo guardar el umbral de stock.')
    } finally {
      setWarehouseSaveLoading(false)
    }
  }

  return (
    <section className="page-grid">
      <div className="cards">
        <StatCard label="Base de datos existe" value={maintenanceQuery.data?.db_exists ? 'Si' : 'No'} />
        <StatCard label="Tamano BD" value={totals.dbSize} />
        <StatCard label="Tablas con datos" value={totals.tablesWithData} />
        <StatCard label="Filas monitorizadas" value={totals.rowsTracked} />
      </div>

      <QueryState
        loading={maintenanceQuery.loading}
        error={maintenanceQuery.error}
        empty={!maintenanceQuery.data}
        emptyMessage="No se pudo cargar estado de mantenimiento."
      />

      {!!maintenanceQuery.data && (
        <div className="split-panel">
          <div className="detail-panel">
            <dl className="detail-list">
              <div>
                <dt>Ruta DB</dt>
                <dd>{maintenanceQuery.data.db_path}</dd>
              </div>
              <div>
                <dt>Ruta DB legacy</dt>
                <dd>{maintenanceQuery.data.legacy_db_path}</dd>
              </div>
              <div>
                <dt>Legacy existe</dt>
                <dd>{maintenanceQuery.data.legacy_exists ? 'Si' : 'No'}</dd>
              </div>
              <div>
                <dt>Enlaces huerfanos contacto-cliente</dt>
                <dd>{maintenanceQuery.data.orphan_contact_links}</dd>
              </div>
            </dl>

            <div className="related-block">
              <h3>Integridad</h3>
              <button type="button" className="action-btn" onClick={runIntegrity} disabled={integrityLoading}>
                {integrityLoading ? 'Comprobando...' : 'Ejecutar integrity_check'}
              </button>
              {!!integrityError && <div className="state">Error: {integrityError}</div>}
              {!!integrityRun && (
                <div className="state">
                  {integrityRun.message} ({integrityRun.ok ? 'OK' : 'Con incidencias'})
                </div>
              )}
            </div>
          </div>

          <div className="detail-panel">
            <h3>Conteos por tabla</h3>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Tabla</th>
                    <th>Filas</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedCounts.slice(0, 20).map((row) => (
                    <tr key={row.table}>
                      <td>{row.table}</td>
                      <td>{row.count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      <div className="split-panel">
        <div className="detail-panel">
          <h3>Proveedores API</h3>
          <QueryState
            loading={providerQuery.loading}
            error={providerQuery.error}
            empty={!providerQuery.data.length}
            emptyMessage="No hay proveedores API para mostrar."
          />
          {!!providerQuery.data.length && (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Provider</th>
                    <th>Estado</th>
                    <th>Enabled</th>
                    <th>Keys config</th>
                  </tr>
                </thead>
                <tbody>
                  {providerQuery.data.map((row) => (
                    <tr key={row.provider}>
                      <td>{row.provider}</td>
                      <td>
                        <span className={`pill ${row.status === 'ok' ? 'ok' : 'off'}`}>
                          {row.status === 'ok' ? 'Cargado' : 'Error'}
                        </span>
                      </td>
                      <td>{row.enabled ? 'Si' : 'No'}</td>
                      <td>{Object.keys(row.config).join(', ') || row.error || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="related-block">
            <h3>Umbral de stock (warehouse)</h3>
            <div className="toolbar">
              <input
                className="input"
                value={effectiveThresholdInput}
                onChange={(event) => setWarehouseThresholdInput(event.target.value)}
                placeholder="Ej: 5"
                disabled={warehouseSaveLoading}
              />
              <button
                type="button"
                className="action-btn"
                onClick={saveWarehouseThreshold}
                disabled={warehouseSaveLoading}
              >
                {warehouseSaveLoading ? 'Guardando...' : 'Guardar umbral'}
              </button>
            </div>
            {!!warehouseSaveMessage && <div className="state">{warehouseSaveMessage}</div>}
            {!!warehouseSaveError && <div className="state">Error: {warehouseSaveError}</div>}
          </div>
        </div>

        <div className="detail-panel">
          <h3>Almacenes para importacion</h3>
          <QueryState
            loading={importsQuery.loading}
            error={importsQuery.error}
            empty={!importsQuery.data.length}
            emptyMessage="No hay almacenes disponibles para importacion."
          />
          {!!importsQuery.data.length && (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Almacen ID</th>
                    <th>Nombre</th>
                  </tr>
                </thead>
                <tbody>
                  {importsQuery.data.map((row) => (
                    <tr key={row.almacen_id}>
                      <td>{row.almacen_id}</td>
                      <td>{row.almacen_nombre || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
