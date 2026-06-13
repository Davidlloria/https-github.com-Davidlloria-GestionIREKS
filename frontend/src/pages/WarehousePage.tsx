import { useMemo, useState } from 'react'
import { getInventoryDetail, listInventoryHistory, listMovements, listStock } from '../api/warehouse'
import { EmptyState, ErrorState, LoadingState, QueryState } from '../components/QueryState'
import { useAsyncResource } from '../features/useAsyncResource'
import type { InventoryDetailRead, InventoryHeaderRead, PaginatedList, WarehouseMovementRead, WarehouseStockRead } from '../types/api'

const PAGE_SIZE = 12

const MAIN_TABS = [
  'Artículos',
  'Entradas',
  'Salidas',
  'Stock',
  'Pedidos mensual',
  'Inventarios',
  'Caducidad',
  'Fabricantes',
  'Otras ref.',
  'Familias',
  'Subfamilias',
  'Envases',
] as const

const DETAIL_TABS = ['Datos', 'Tarifa', 'Entradas', 'Salidas', 'Stock', 'Mensual', 'Pedidos', 'Nutrición', 'Clientes'] as const

type WarehouseMainTab = (typeof MAIN_TABS)[number]
type WarehouseDetailTab = (typeof DETAIL_TABS)[number]

interface WarehousePayload {
  stock: PaginatedList<WarehouseStockRead>
  movements: PaginatedList<WarehouseMovementRead>
  history: PaginatedList<InventoryHeaderRead>
}

const EMPTY_PAYLOAD: WarehousePayload = {
  stock: { items: [], total: 0, limit: PAGE_SIZE, offset: 0 },
  movements: { items: [], total: 0, limit: PAGE_SIZE, offset: 0 },
  history: { items: [], total: 0, limit: PAGE_SIZE, offset: 0 },
}

const EMPTY_DETAIL: InventoryDetailRead[] = []

function safeNumber(value: unknown) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : 0
}

function formatNumber(value: unknown) {
  return new Intl.NumberFormat('es-ES', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(safeNumber(value))
}

function formatMaybeText(value: string | number | boolean | null | undefined) {
  if (value === null || value === undefined) {
    return '-'
  }
  if (typeof value === 'boolean') {
    return value ? 'Si' : 'No'
  }
  const text = String(value).trim()
  return text || '-'
}

function compactText(value: string | number | null | undefined, maxLength = 18) {
  const text = formatMaybeText(value)
  if (text === '-' || text.length <= maxLength) {
    return text
  }
  return `${text.slice(0, Math.max(6, maxLength - 5))}…${text.slice(-4)}`
}

function limitLabel(total: number, visible: number) {
  if (total <= visible) {
    return 'Registros cargados'
  }
  return `Primeros ${visible} registros`
}

function stockRowKey(row: WarehouseStockRead) {
  return `${row.almacen_id}::${row.articulo_id}`
}

function SectionHead({
  title,
  description,
  countLabel,
}: {
  title: string
  description: string
  countLabel?: string
}) {
  return (
    <div className="section-heading warehouse-section-head">
      <div>
        <h3>{title}</h3>
        <p>{description}</p>
      </div>
      {!!countLabel && <span className="surface-chip">{countLabel}</span>}
    </div>
  )
}

function TabButton({
  label,
  active,
  onClick,
  className = '',
}: {
  label: string
  active: boolean
  onClick: () => void
  className?: string
}) {
  return (
    <button
      type="button"
      className={`${className} ${active ? `${className}-active` : ''}`.trim()}
      aria-pressed={active}
      onClick={onClick}
    >
      {label}
    </button>
  )
}

function ReadonlyField({
  label,
  value,
  className = '',
  kind = 'text',
}: {
  label: string
  value: string | number | boolean | null | undefined
  className?: string
  kind?: 'text' | 'number'
}) {
  const displayValue =
    kind === 'number' ? formatNumber(typeof value === 'number' ? value : Number(value)) : formatMaybeText(value)

  return (
    <label className={`warehouse-field ${className}`.trim()}>
      <span>{label}</span>
      <input className="input warehouse-field-input" value={displayValue} readOnly />
    </label>
  )
}

function PlaceholderPanel({ title, description, note }: { title: string; description: string; note: string }) {
  return (
    <section className="panel-section warehouse-panel warehouse-placeholder-panel">
      <SectionHead title={title} description={description} />
      <div className="state state-empty warehouse-placeholder-state">
        <strong>{note}</strong>
        <span>Vista read-only pendiente de migración visual.</span>
      </div>
    </section>
  )
}

function DetailPlaceholder({ tab }: { tab: WarehouseDetailTab }) {
  const message = detailTabPlaceholder(tab)
  return <div className="warehouse-tab-empty">{message}</div>
}

function detailTabPlaceholder(tab: WarehouseDetailTab) {
  switch (tab) {
    case 'Tarifa':
      return 'Tarifa pendiente de migración read-only'
    case 'Entradas':
      return 'Entradas pendientes de migración read-only'
    case 'Salidas':
      return 'Salidas pendientes de migración read-only'
    case 'Stock':
      return 'Stock pendiente de migración read-only'
    case 'Mensual':
      return 'Mensual pendiente de migración read-only'
    case 'Pedidos':
      return 'Pedidos pendientes de migración read-only'
    case 'Nutrición':
      return 'Nutrición pendiente de migración read-only'
    case 'Clientes':
      return 'Clientes pendientes de migración read-only'
    case 'Datos':
    default:
      return 'Datos del producto read-only'
  }
}

function mainTabPlaceholder(tab: WarehouseMainTab) {
  switch (tab) {
    case 'Entradas':
      return 'Entradas read-only pendientes de migración'
    case 'Salidas':
      return 'Salidas read-only pendientes de migración'
    case 'Pedidos mensual':
      return 'Pedidos mensual read-only pendiente de migración'
    case 'Caducidad':
      return 'Caducidad read-only pendiente de migración'
    case 'Fabricantes':
      return 'Fabricantes read-only pendientes de migración'
    case 'Otras ref.':
      return 'Otras referencias read-only pendientes de migración'
    case 'Familias':
      return 'Familias read-only pendientes de migración'
    case 'Subfamilias':
      return 'Subfamilias read-only pendientes de migración'
    case 'Envases':
      return 'Envases read-only pendientes de migración'
    case 'Artículos':
    case 'Stock':
    case 'Inventarios':
    default:
      return 'Vista read-only'
  }
}

export function WarehousePage() {
  const almacenId = ''
  const [search, setSearch] = useState('')
  const [selectedStockCandidateKey, setSelectedStockCandidateKey] = useState('')
  const [selectedHistoryCandidateId, setSelectedHistoryCandidateId] = useState('')
  const [refreshTick, setRefreshTick] = useState(0)
  const [activeMainTab, setActiveMainTab] = useState<WarehouseMainTab>('Artículos')
  const [activeDetailTab, setActiveDetailTab] = useState<WarehouseDetailTab>('Datos')

  const fetchPayload = async () => {
    const [stock, movements, history] = await Promise.all([
      listStock(almacenId, PAGE_SIZE, 0),
      listMovements(almacenId, PAGE_SIZE, 0),
      listInventoryHistory(almacenId, PAGE_SIZE, 0),
    ])
    return { stock, movements, history }
  }

  const query = useAsyncResource(fetchPayload, EMPTY_PAYLOAD, [almacenId, refreshTick])
  const historyRows = query.data.history.items

  const filteredStockRows = useMemo(() => {
    const normalized = search.trim().toLowerCase()
    if (!normalized) {
      return query.data.stock.items
    }
    return query.data.stock.items.filter((row) => {
      const haystack = `${row.almacen_id} ${row.articulo_id}`.toLowerCase()
      return haystack.includes(normalized)
    })
  }, [query.data.stock.items, search])

  const selectedStockRow = useMemo(() => {
    if (!filteredStockRows.length) {
      return null
    }
    if (selectedStockCandidateKey && filteredStockRows.some((row) => stockRowKey(row) === selectedStockCandidateKey)) {
      return filteredStockRows.find((row) => stockRowKey(row) === selectedStockCandidateKey) ?? null
    }
    return filteredStockRows[0] ?? null
  }, [filteredStockRows, selectedStockCandidateKey])

  const selectedHistory = useMemo(() => {
    if (!historyRows.length) {
      return null
    }
    if (selectedHistoryCandidateId && historyRows.some((row) => row.inventario_id === selectedHistoryCandidateId)) {
      return historyRows.find((row) => row.inventario_id === selectedHistoryCandidateId) ?? null
    }
    return historyRows[0] ?? null
  }, [historyRows, selectedHistoryCandidateId])

  const detailQuery = useAsyncResource(
    () => (selectedHistory ? getInventoryDetail(selectedHistory.inventario_id) : Promise.resolve(EMPTY_DETAIL)),
    EMPTY_DETAIL,
    [selectedHistory?.inventario_id],
  )

  const stockVisibleLabel = useMemo(
    () => (query.data.stock.total > query.data.stock.items.length ? limitLabel(query.data.stock.total, query.data.stock.items.length) : 'Registros cargados'),
    [query.data.stock.items.length, query.data.stock.total],
  )

  const historyVisibleLabel = useMemo(
    () =>
      query.data.history.total > query.data.history.items.length
        ? limitLabel(query.data.history.total, query.data.history.items.length)
        : 'Registros cargados',
    [query.data.history.items.length, query.data.history.total],
  )

  const selectedArticleName = selectedStockRow ? 'Artículo sin nombre disponible' : '-'
  const selectedArticleRef = selectedStockRow ? compactText(selectedStockRow.articulo_id, 20) : '-'

  const articleDataTab = selectedStockRow ? (
    <div className="warehouse-detail-grid">
      <ReadonlyField label="Ref." value={selectedArticleRef} />
      <ReadonlyField label="Almacén" value={selectedStockRow.almacen_id} />
      <ReadonlyField label="Nombre" value={selectedArticleName} />
      <ReadonlyField label="Cantidad total" value={selectedStockRow.cantidad_total} kind="number" />
      <ReadonlyField label="Estado" value="Read-only" />
      <ReadonlyField label="Notas" value="Contrato actual limitado a stock agregado." />
    </div>
  ) : (
    <div className="warehouse-tab-empty">Selecciona un artículo para ver el detalle read-only.</div>
  )

  const renderArticleTab = () => (
    <div className="warehouse-articles-workspace">
      <section className="panel-section warehouse-panel warehouse-list-panel">
        <SectionHead
          title="Artículos"
          description="Listado read-only de referencias cargadas en stock."
          countLabel={`${filteredStockRows.length} visibles`}
        />

        <div className="warehouse-list-filters">
          <label className="warehouse-filter">
            <span>Fabricante</span>
            <select className="select" disabled defaultValue="">
              <option value="">Todos</option>
            </select>
          </label>
          <label className="warehouse-filter">
            <span>Familia</span>
            <select className="select" disabled defaultValue="">
              <option value="">Todas</option>
            </select>
          </label>
          <label className="warehouse-filter">
            <span>Subfamilia</span>
            <select className="select" disabled defaultValue="">
              <option value="">Todas</option>
            </select>
          </label>
        </div>

        <div className="toolbar warehouse-search-toolbar">
          <input
            className="input warehouse-search-input"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value)
              setSelectedStockCandidateKey('')
            }}
            placeholder="Buscar por referencia o identificador"
          />
          <span className="surface-chip">{stockVisibleLabel}</span>
        </div>

        {query.loading ? (
          <LoadingState className="state state-loading warehouse-inline-state" />
        ) : query.error ? (
          <ErrorState className="state state-error warehouse-inline-state">{query.error}</ErrorState>
        ) : filteredStockRows.length ? (
          <div className="warehouse-list-scroll">
            <div className="table-wrap warehouse-table-wrap warehouse-list-table-wrap">
              <table className="warehouse-table warehouse-list-table">
                <thead>
                  <tr>
                    <th>Ref</th>
                    <th>Nombre</th>
                    <th>Sel.</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredStockRows.map((row) => {
                    const isSelected = stockRowKey(row) === stockRowKey(selectedStockRow ?? row)
                    return (
                      <tr
                        key={stockRowKey(row)}
                        className={isSelected ? 'row-selected' : ''}
                        onClick={() => setSelectedStockCandidateKey(stockRowKey(row))}
                      >
                        <td>{compactText(row.articulo_id, 18)}</td>
                        <td>Artículo sin nombre disponible</td>
                        <td>{isSelected ? 'Si' : 'No'}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <EmptyState className="state state-empty warehouse-inline-state">
            Sin artículos cargados para el filtro actual.
          </EmptyState>
        )}
      </section>

      <div className="warehouse-detail-stack">
        <section className="panel-section warehouse-panel warehouse-article-detail-panel">
          <SectionHead
            title="Detalle del producto"
            description="Ficha compacta read-only de la referencia seleccionada."
            countLabel={selectedStockRow ? compactText(selectedStockRow.articulo_id, 20) : 'Sin selección'}
          />

          {selectedStockRow ? (
            <div className="warehouse-article-detail-grid">
              <ReadonlyField label="Ref." value={selectedStockRow.articulo_id} />
              <ReadonlyField label="Almacén" value={selectedStockRow.almacen_id} />
              <ReadonlyField label="Nombre" value={selectedArticleName} />
              <ReadonlyField label="Cantidad total" value={selectedStockRow.cantidad_total} kind="number" />
              <ReadonlyField label="Observaciones" value="Consulta read-only sin mutaciones." className="warehouse-field-wide" />
            </div>
          ) : (
            <div className="warehouse-tab-empty">Selecciona una fila para ver el detalle del producto.</div>
          )}
        </section>

        <section className="panel-section warehouse-panel warehouse-detail-tabs-panel">
          <SectionHead
            title="Información del producto"
            description="Tabs read-only de la referencia seleccionada."
            countLabel={activeDetailTab}
          />

          <div className="warehouse-detail-tabs">
            {DETAIL_TABS.map((tab) => (
              <TabButton
                key={tab}
                label={tab}
                active={activeDetailTab === tab}
                onClick={() => setActiveDetailTab(tab)}
                className="warehouse-detail-tab"
              />
            ))}
          </div>

          <div className="warehouse-detail-tab-body">
            {activeDetailTab === 'Datos' ? (
              articleDataTab
            ) : (
              <DetailPlaceholder tab={activeDetailTab} />
            )}
          </div>
        </section>
      </div>
    </div>
  )

  const renderStockTab = () => (
    <section className="panel-section warehouse-panel warehouse-main-panel">
      <SectionHead
        title="Stock"
        description="Consulta read-only del stock agregado disponible."
        countLabel={stockVisibleLabel}
      />
      {query.loading ? (
        <LoadingState className="state state-loading warehouse-inline-state" />
      ) : query.error ? (
        <ErrorState className="state state-error warehouse-inline-state">{query.error}</ErrorState>
      ) : query.data.stock.items.length ? (
        <div className="warehouse-list-scroll">
          <div className="table-wrap warehouse-table-wrap">
            <table className="warehouse-table">
              <thead>
                <tr>
                  <th>Almacén</th>
                  <th>Artículo</th>
                  <th>Cantidad total</th>
                </tr>
              </thead>
              <tbody>
                {query.data.stock.items.map((row) => (
                  <tr key={stockRowKey(row)}>
                    <td>{row.almacen_id}</td>
                    <td>{compactText(row.articulo_id, 24)}</td>
                    <td>{formatNumber(row.cantidad_total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <EmptyState className="state state-empty warehouse-inline-state">Sin filas de stock para el filtro actual.</EmptyState>
      )}
    </section>
  )

  const renderInventoryTab = () => (
    <div className="warehouse-inventory-workspace">
      <section className="panel-section warehouse-panel warehouse-history-panel">
        <SectionHead
          title="Inventarios"
          description="Histórico read-only de inventarios y ajustes."
          countLabel={historyVisibleLabel}
        />

        {query.loading ? (
          <LoadingState className="state state-loading warehouse-inline-state" />
        ) : query.error ? (
          <ErrorState className="state state-error warehouse-inline-state">{query.error}</ErrorState>
        ) : historyRows.length ? (
          <div className="warehouse-list-scroll">
            <div className="table-wrap warehouse-table-wrap">
              <table className="warehouse-table warehouse-history-table">
                <thead>
                  <tr>
                    <th>Inventario ID</th>
                    <th>Almacén</th>
                    <th>Fecha</th>
                    <th>Estado</th>
                    <th>Líneas</th>
                    <th>Ajustes</th>
                  </tr>
                </thead>
                <tbody>
                  {historyRows.map((row) => (
                    <tr
                      key={row.inventario_id}
                      className={row.inventario_id === selectedHistory?.inventario_id ? 'row-selected' : ''}
                      onClick={() => setSelectedHistoryCandidateId(row.inventario_id)}
                    >
                      <td>{compactText(row.inventario_id, 20)}</td>
                      <td>{formatMaybeText(row.almacen_id)}</td>
                      <td>{formatMaybeText(row.fecha)}</td>
                      <td>{formatMaybeText(row.estado)}</td>
                      <td>{row.lineas}</td>
                      <td>{row.ajustes}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <EmptyState className="state state-empty warehouse-inline-state">Sin inventarios para el filtro actual.</EmptyState>
        )}
      </section>

      <section className="panel-section warehouse-panel warehouse-inventory-detail-panel">
        <SectionHead
          title="Detalle de inventario"
          description="Cabecera e líneas de ajuste del inventario seleccionado."
          countLabel={selectedHistory ? compactText(selectedHistory.inventario_id, 20) : 'Sin selección'}
        />

        {selectedHistory ? (
          <div className="warehouse-detail-scroll">
            <dl className="detail-list warehouse-detail-summary">
              <div>
                <dt>Inventario ID</dt>
                <dd>{compactText(selectedHistory.inventario_id, 20)}</dd>
              </div>
              <div>
                <dt>Almacén</dt>
                <dd>{formatMaybeText(selectedHistory.almacen_id)}</dd>
              </div>
              <div>
                <dt>Fecha</dt>
                <dd>{formatMaybeText(selectedHistory.fecha)}</dd>
              </div>
              <div>
                <dt>Estado</dt>
                <dd>{formatMaybeText(selectedHistory.estado)}</dd>
              </div>
              <div>
                <dt>Líneas</dt>
                <dd>{selectedHistory.lineas}</dd>
              </div>
              <div>
                <dt>Ajustes</dt>
                <dd>{selectedHistory.ajustes}</dd>
              </div>
            </dl>

            <QueryState
              loading={detailQuery.loading}
              error={detailQuery.error}
              empty={!detailQuery.loading && !detailQuery.error && !detailQuery.data.length}
              emptyMessage="No hay líneas para el inventario seleccionado."
            />

            {!detailQuery.loading && !detailQuery.error && !!detailQuery.data.length && (
              <div className="table-wrap warehouse-table-wrap">
                <table className="warehouse-table warehouse-detail-table">
                  <thead>
                    <tr>
                      <th>Artículo</th>
                      <th>Lote</th>
                      <th>Caducidad</th>
                      <th>Teórico</th>
                      <th>Conteo</th>
                      <th>Diferencia</th>
                      <th>KG ajuste</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detailQuery.data.map((row) => (
                      <tr key={`${row.id ?? row.articulo_id}-${row.articulo_lote}`}>
                        <td>{formatMaybeText(row.articulo_id)}</td>
                        <td>{formatMaybeText(row.articulo_lote)}</td>
                        <td>{formatMaybeText(row.articulo_caducidad)}</td>
                        <td>{formatNumber(row.teorico_uds)}</td>
                        <td>{formatNumber(row.conteo_uds)}</td>
                        <td>{formatNumber(row.diferencia_uds)}</td>
                        <td>{formatNumber(row.kg_ajuste)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ) : (
          <div className="warehouse-tab-empty">Selecciona un inventario histórico para ver el detalle.</div>
        )}
      </section>
    </div>
  )

  const activeMainPanel = (() => {
    switch (activeMainTab) {
      case 'Artículos':
        return renderArticleTab()
      case 'Stock':
        return renderStockTab()
      case 'Inventarios':
        return renderInventoryTab()
      default:
        return (
          <PlaceholderPanel
            title={activeMainTab}
            description={`Sección read-only de ${activeMainTab.toLowerCase()}.`}
            note={mainTabPlaceholder(activeMainTab)}
          />
        )
    }
  })()

  return (
    <section className="page-grid warehouse-page">
      <header className="warehouse-header">
        <div className="warehouse-header-copy">
          <p className="warehouse-kicker">Almacén</p>
          <h2>Almacén</h2>
          <p className="warehouse-subtitle">Ventana operativa read-only alineada con la estructura real de la desktop app.</p>
        </div>

        <div className="warehouse-header-meta">
          <div className="warehouse-header-filter">
            <span>Cliente/Distribuidor</span>
            <select className="select" disabled defaultValue="">
              <option value="">Todos</option>
            </select>
          </div>
          <button
            type="button"
            className="action-btn warehouse-refresh-btn"
            onClick={() => setRefreshTick((prev) => prev + 1)}
          >
            Refrescar
          </button>
          <span className="surface-chip">Vista read-only</span>
        </div>
      </header>

      <div className="warehouse-main-tabs">
        {MAIN_TABS.map((tab) => (
          <TabButton
            key={tab}
            label={tab}
            active={activeMainTab === tab}
            onClick={() => setActiveMainTab(tab)}
            className="warehouse-main-tab"
          />
        ))}
      </div>

      <div className="warehouse-main-content">{activeMainPanel}</div>
    </section>
  )
}
