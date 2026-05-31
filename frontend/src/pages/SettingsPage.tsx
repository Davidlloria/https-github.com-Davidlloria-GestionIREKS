import { useMemo, useState } from 'react'
import {
  getApiProviderSettings,
  getMaintenanceStatus,
  importOrdersJsonFromSettings,
  listImportWarehouses,
  runMaintenanceBackup,
  runMaintenanceCreateMissingContactClients,
  runMaintenanceIntegrityCheck,
  runMaintenanceOptimize,
  runMaintenanceRepairContactLinks,
  saveApiProviderSettings,
} from '../api/settings'
import { QueryState } from '../components/QueryState'
import { StatCard } from '../components/StatCard'
import { useAsyncResource } from '../features/useAsyncResource'
import type { ApiSettingsPayload, MaintenanceResult, OrderJsonImportResponse } from '../types/api'

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
  const [ordersMailDestinoInput, setOrdersMailDestinoInput] = useState('')
  const [ordersMailHistoricoInput, setOrdersMailHistoricoInput] = useState('')
  const [ordersMailSaveLoading, setOrdersMailSaveLoading] = useState(false)
  const [ordersMailSaveMessage, setOrdersMailSaveMessage] = useState('')
  const [ordersMailSaveError, setOrdersMailSaveError] = useState('')
  const [maintenanceActionLoading, setMaintenanceActionLoading] = useState(false)
  const [maintenanceActionMessage, setMaintenanceActionMessage] = useState('')
  const [maintenanceActionError, setMaintenanceActionError] = useState('')
  const [backupDestinationPath, setBackupDestinationPath] = useState('')
  const [importWarehouseId, setImportWarehouseId] = useState('')
  const [importFilePath, setImportFilePath] = useState('')
  const [importOrdersLoading, setImportOrdersLoading] = useState(false)
  const [importOrdersMessage, setImportOrdersMessage] = useState('')
  const [importOrdersError, setImportOrdersError] = useState('')
  const [importOrdersResult, setImportOrdersResult] = useState<OrderJsonImportResponse | null>(null)
  const [providerEditName, setProviderEditName] = useState<string>('fdc')
  const [providerEditDraft, setProviderEditDraft] = useState('')
  const [providerEditDirty, setProviderEditDirty] = useState(false)
  const [providerEditLoading, setProviderEditLoading] = useState(false)
  const [providerEditMessage, setProviderEditMessage] = useState('')
  const [providerEditError, setProviderEditError] = useState('')

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
  const ordersMailProvider = useMemo(
    () => providerQuery.data.find((row) => row.provider === 'orders_mail' && row.status === 'ok') ?? null,
    [providerQuery.data],
  )
  const providerEditRow = useMemo(
    () => providerQuery.data.find((row) => row.provider === providerEditName) ?? null,
    [providerEditName, providerQuery.data],
  )
  const providerEditText = useMemo(() => {
    if (providerEditDirty) {
      return providerEditDraft
    }
    if (!providerEditRow || providerEditRow.status !== 'ok') {
      return '{}'
    }
    return JSON.stringify(providerEditRow.config ?? {}, null, 2)
  }, [providerEditDirty, providerEditDraft, providerEditRow])

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

  const effectiveOrdersMailDestinoInput = useMemo(() => {
    if (ordersMailDestinoInput) {
      return ordersMailDestinoInput
    }
    const rawValue = ordersMailProvider?.config?.destino_email
    if (rawValue === undefined || rawValue === null) {
      return ''
    }
    return String(rawValue)
  }, [ordersMailDestinoInput, ordersMailProvider])

  const effectiveOrdersMailHistoricoInput = useMemo(() => {
    if (ordersMailHistoricoInput) {
      return ordersMailHistoricoInput
    }
    const rawValue = ordersMailProvider?.config?.historico_dir
    if (rawValue === undefined || rawValue === null) {
      return ''
    }
    return String(rawValue)
  }, [ordersMailHistoricoInput, ordersMailProvider])

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

  const runMaintenanceAction = async (action: () => Promise<MaintenanceResult>, successPrefix: string) => {
    if (maintenanceActionLoading) {
      return
    }
    setMaintenanceActionLoading(true)
    setMaintenanceActionError('')
    setMaintenanceActionMessage('')
    try {
      const result = await action()
      await maintenanceQuery.reload()
      setMaintenanceActionMessage(`${successPrefix}: ${result.message || 'OK'}`)
    } catch (error: unknown) {
      setMaintenanceActionError(error instanceof Error ? error.message : 'Error ejecutando accion de mantenimiento.')
    } finally {
      setMaintenanceActionLoading(false)
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

  const saveOrdersMailSettings = async () => {
    if (ordersMailSaveLoading) {
      return
    }
    const destino = effectiveOrdersMailDestinoInput.trim()
    const historicoDir = effectiveOrdersMailHistoricoInput.trim()
    if (destino && !destino.includes('@')) {
      setOrdersMailSaveError('El email destino no tiene un formato valido.')
      setOrdersMailSaveMessage('')
      return
    }
    setOrdersMailSaveLoading(true)
    setOrdersMailSaveError('')
    setOrdersMailSaveMessage('')
    try {
      await saveApiProviderSettings('orders_mail', {
        destino_email: destino,
        historico_dir: historicoDir,
      })
      await providerQuery.reload()
      setOrdersMailDestinoInput(destino)
      setOrdersMailHistoricoInput(historicoDir)
      setOrdersMailSaveMessage('Configuracion de pedidos por email guardada.')
    } catch (error: unknown) {
      setOrdersMailSaveError(error instanceof Error ? error.message : 'No se pudo guardar la configuracion de pedidos por email.')
    } finally {
      setOrdersMailSaveLoading(false)
    }
  }

  const runBackup = async () => {
    const destination = backupDestinationPath.trim()
    if (!destination) {
      setMaintenanceActionError('Debes indicar destination_path para el backup.')
      setMaintenanceActionMessage('')
      return
    }
    await runMaintenanceAction(
      () => runMaintenanceBackup(destination),
      'Backup completado',
    )
  }

  const effectiveImportWarehouseId = useMemo(() => {
    if (importWarehouseId) {
      return importWarehouseId
    }
    return importsQuery.data[0]?.almacen_id ?? ''
  }, [importWarehouseId, importsQuery.data])

  const runOrdersJsonImport = async () => {
    if (importOrdersLoading) {
      return
    }
    const almacenId = effectiveImportWarehouseId.trim()
    const filePath = importFilePath.trim()
    if (!almacenId) {
      setImportOrdersError('Debes seleccionar un almacen.')
      setImportOrdersMessage('')
      return
    }
    if (!filePath) {
      setImportOrdersError('Debes indicar file_path del JSON de pedido.')
      setImportOrdersMessage('')
      return
    }
    if (!filePath.toLowerCase().endsWith('.json')) {
      setImportOrdersError('El fichero debe tener extension .json')
      setImportOrdersMessage('')
      return
    }
    setImportOrdersLoading(true)
    setImportOrdersError('')
    setImportOrdersMessage('')
    setImportOrdersResult(null)
    try {
      const result = await importOrdersJsonFromSettings({
        almacen_id: almacenId,
        file_path: filePath,
      })
      setImportOrdersResult(result)
      setImportOrdersMessage(`Importacion JSON completada para ${almacenId}.`)
    } catch (error: unknown) {
      setImportOrdersError(error instanceof Error ? error.message : 'No se pudo importar el JSON de pedidos.')
    } finally {
      setImportOrdersLoading(false)
    }
  }

  const saveProviderJsonConfig = async () => {
    if (providerEditLoading) {
      return
    }
    if (!providerEditRow || providerEditRow.status !== 'ok') {
      setProviderEditError('Selecciona un proveedor cargado correctamente.')
      setProviderEditMessage('')
      return
    }
    let parsed: unknown
    try {
      parsed = JSON.parse(providerEditText || '{}')
    } catch {
      setProviderEditError('El JSON no es valido.')
      setProviderEditMessage('')
      return
    }
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      setProviderEditError('La configuracion debe ser un objeto JSON.')
      setProviderEditMessage('')
      return
    }
    setProviderEditLoading(true)
    setProviderEditError('')
    setProviderEditMessage('')
    try {
      await saveApiProviderSettings(providerEditRow.provider, parsed as Record<string, unknown>)
      await providerQuery.reload()
      setProviderEditDirty(false)
      setProviderEditDraft(JSON.stringify(parsed, null, 2))
      setProviderEditMessage(`Configuracion guardada para ${providerEditRow.provider}.`)
    } catch (error: unknown) {
      setProviderEditError(error instanceof Error ? error.message : 'No se pudo guardar la configuracion del proveedor.')
    } finally {
      setProviderEditLoading(false)
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

            <div className="related-block">
              <h3>Mantenimiento</h3>
              <div className="toolbar">
                <button
                  type="button"
                  className="action-btn"
                  onClick={() => runMaintenanceAction(runMaintenanceRepairContactLinks, 'Revision de enlaces')}
                  disabled={maintenanceActionLoading}
                >
                  {maintenanceActionLoading ? 'Ejecutando...' : 'Reparar enlaces'}
                </button>
                <button
                  type="button"
                  className="action-btn"
                  onClick={() =>
                    runMaintenanceAction(
                      runMaintenanceCreateMissingContactClients,
                      'Creacion de clientes faltantes',
                    )
                  }
                  disabled={maintenanceActionLoading}
                >
                  {maintenanceActionLoading ? 'Ejecutando...' : 'Crear clientes faltantes'}
                </button>
                <button
                  type="button"
                  className="action-btn"
                  onClick={() => runMaintenanceAction(runMaintenanceOptimize, 'Optimizacion')}
                  disabled={maintenanceActionLoading}
                >
                  {maintenanceActionLoading ? 'Ejecutando...' : 'Optimizar BD'}
                </button>
              </div>
              <div className="form-grid">
                <label>
                  Ruta backup (.db)
                  <input
                    className="input"
                    value={backupDestinationPath}
                    onChange={(event) => setBackupDestinationPath(event.target.value)}
                    placeholder="E:\\IREKS\\APP\\GestionIREKS\\data\\backups\\backup_manual.db"
                    disabled={maintenanceActionLoading}
                  />
                </label>
              </div>
              <div className="toolbar">
                <button
                  type="button"
                  className="action-btn"
                  onClick={runBackup}
                  disabled={maintenanceActionLoading}
                >
                  {maintenanceActionLoading ? 'Ejecutando...' : 'Crear backup'}
                </button>
              </div>
              {!!maintenanceActionMessage && <div className="state">{maintenanceActionMessage}</div>}
              {!!maintenanceActionError && <div className="state">Error: {maintenanceActionError}</div>}
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
            <h3>Configuracion JSON de proveedor</h3>
            <div className="form-grid">
              <label>
                Proveedor
                <select
                  className="select"
                  value={providerEditName}
                  onChange={(event) => {
                    setProviderEditName(event.target.value)
                    setProviderEditDraft('')
                    setProviderEditDirty(false)
                    setProviderEditMessage('')
                    setProviderEditError('')
                  }}
                  disabled={providerEditLoading}
                >
                  {providerQuery.data.map((row) => (
                    <option key={row.provider} value={row.provider}>
                      {row.provider}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Config (JSON)
                <textarea
                  className="input"
                  value={providerEditText}
                  onChange={(event) => {
                    setProviderEditDraft(event.target.value)
                    setProviderEditDirty(true)
                  }}
                  disabled={providerEditLoading}
                  rows={10}
                  style={{ minWidth: '100%', fontFamily: 'Consolas, monospace' }}
                />
              </label>
            </div>
            <div className="toolbar">
              <button
                type="button"
                className="action-btn"
                onClick={saveProviderJsonConfig}
                disabled={providerEditLoading}
              >
                {providerEditLoading ? 'Guardando...' : 'Guardar JSON proveedor'}
              </button>
            </div>
            {!!providerEditMessage && <div className="state">{providerEditMessage}</div>}
            {!!providerEditError && <div className="state">Error: {providerEditError}</div>}
          </div>

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

          <div className="related-block">
            <h3>Pedidos por email (orders_mail)</h3>
            <div className="form-grid">
              <label>
                Email destino
                <input
                  className="input"
                  value={effectiveOrdersMailDestinoInput}
                  onChange={(event) => setOrdersMailDestinoInput(event.target.value)}
                  placeholder="destino@empresa.com"
                  disabled={ordersMailSaveLoading}
                />
              </label>
              <label>
                Directorio historico
                <input
                  className="input"
                  value={effectiveOrdersMailHistoricoInput}
                  onChange={(event) => setOrdersMailHistoricoInput(event.target.value)}
                  placeholder="E:\\pedidos\\historico"
                  disabled={ordersMailSaveLoading}
                />
              </label>
            </div>
            <div className="toolbar">
              <button
                type="button"
                className="action-btn"
                onClick={saveOrdersMailSettings}
                disabled={ordersMailSaveLoading}
              >
                {ordersMailSaveLoading ? 'Guardando...' : 'Guardar orders_mail'}
              </button>
            </div>
            {!!ordersMailSaveMessage && <div className="state">{ordersMailSaveMessage}</div>}
            {!!ordersMailSaveError && <div className="state">Error: {ordersMailSaveError}</div>}
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
            <>
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
              <div className="related-block">
                <h3>Importar pedidos JSON (settings)</h3>
                <div className="form-grid">
                  <label>
                    Almacen
                    <select
                      className="select"
                      value={effectiveImportWarehouseId}
                      onChange={(event) => setImportWarehouseId(event.target.value)}
                      disabled={importOrdersLoading}
                    >
                      {importsQuery.data.map((row) => (
                        <option key={row.almacen_id} value={row.almacen_id}>
                          {row.almacen_id} - {row.almacen_nombre || 'Sin nombre'}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Ruta JSON (file_path)
                    <input
                      className="input"
                      value={importFilePath}
                      onChange={(event) => setImportFilePath(event.target.value)}
                      placeholder="E:\\ruta\\pedido.json"
                      disabled={importOrdersLoading}
                    />
                  </label>
                </div>
                <div className="toolbar">
                  <button
                    type="button"
                    className="action-btn"
                    onClick={runOrdersJsonImport}
                    disabled={importOrdersLoading}
                  >
                    {importOrdersLoading ? 'Importando...' : 'Importar JSON'}
                  </button>
                </div>
                {!!importOrdersMessage && <div className="state">{importOrdersMessage}</div>}
                {!!importOrdersError && <div className="state">Error: {importOrdersError}</div>}
                {!!importOrdersResult && (
                  <div className="state">
                    Importados: {importOrdersResult.imported_items} | Omitidos invalidos: {importOrdersResult.skipped_invalid} | Desconocidos:{' '}
                    {(importOrdersResult.skipped_unknown || []).join(', ') || '-'}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </section>
  )
}
