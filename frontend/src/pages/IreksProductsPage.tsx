import { useMemo, useState } from 'react'
import { getIreksIngredientDetail, listIreksIngredients } from '../api/ingredients'
import { AppButton } from '../components/AppButton'
import { AppDataTable } from '../components/AppDataTable'
import { AppSectionHeader } from '../components/AppSectionHeader'
import { QueryState } from '../components/QueryState'
import { List, Plus, Trash2, X } from 'lucide-react'
import { useAsyncResource } from '../features/useAsyncResource'
import type { IngredientIreksListPayload, IngredientIreksRead } from '../types/api'

const PAGE_SIZE = 100

type IreksTab = 'Datos' | 'Tarifa' | 'Entradas' | 'Salidas' | 'Stock' | 'Mensual' | 'Pedidos' | 'Nutrición' | 'Clientes'
type IreksSortKey = 'ref' | 'name' | 'sel'

interface LoadedIreksData {
  items: IngredientIreksRead[]
  total: number
  catalogs: IngredientIreksListPayload['catalogs']
}

const EMPTY_DATA: LoadedIreksData = {
  items: [],
  total: 0,
  catalogs: {
    distribuidores: [],
    fabricantes: [],
    familias: [],
    subfamilias: [],
    envases: [],
  },
}

const TABS: IreksTab[] = ['Datos', 'Tarifa', 'Entradas', 'Salidas', 'Stock', 'Mensual', 'Pedidos', 'Nutrición', 'Clientes']

function formatText(value: string | number | boolean | null | undefined) {
  if (value === null || value === undefined) {
    return '-'
  }
  if (typeof value === 'boolean') {
    return value ? 'Si' : 'No'
  }
  const text = String(value).trim()
  return text || '-'
}

function formatNumber(value: number | null | undefined) {
  const safeValue = Number.isFinite(Number(value)) ? Number(value) : 0
  return new Intl.NumberFormat('es-ES', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(safeValue)
}

function buildLookup(options: Array<{ id: string; name: string }>) {
  return new Map(options.map((item) => [item.id, item.name]))
}

function buildUniqueCatalogOptions(
  rows: IngredientIreksRead[],
  key: 'fabricante_id' | 'articulo_familia_id' | 'articulo_subfamilia_id',
  lookup: Map<string, string>,
) {
  const seen = new Set<string>()

  return rows.reduce<Array<{ id: string; name: string }>>((options, row) => {
    const id = row[key]
    if (!id || seen.has(id)) {
      return options
    }

    seen.add(id)
    options.push({ id, name: lookup.get(id) || id })
    return options
  }, [])
}

function ReadonlyField({
  label,
  value,
  kind = 'text',
  className = '',
}: {
  label: string
  value: string | number | boolean | null | undefined
  kind?: 'text' | 'number'
  className?: string
}) {
  const displayValue =
    kind === 'number' ? formatNumber(typeof value === 'number' ? value : Number(value)) : formatText(value)

  return (
    <label className={`ireks-field ${className}`.trim()}>
      <span>{label}</span>
      <input className="input" value={displayValue} readOnly />
    </label>
  )
}

function TabButton({
  tab,
  active,
  onClick,
}: {
  tab: IreksTab
  active: boolean
  onClick: (tab: IreksTab) => void
}) {
  return (
    <button type="button" className={`ireks-tab ${active ? 'ireks-tab-active' : ''}`} onClick={() => onClick(tab)}>
      {tab}
    </button>
  )
}

function ActionButton({
  children,
  className = '',
  disabled = true,
  onClick,
}: {
  children: string
  className?: string
  disabled?: boolean
  onClick?: () => void
}) {
  return (
    <button type="button" className={`action-btn ireks-action-btn ${className}`.trim()} disabled={disabled} onClick={onClick}>
      {children}
    </button>
  )
}

async function loadAllIreksIngredients(search: string): Promise<LoadedIreksData> {
  const items: IngredientIreksRead[] = []
  let offset = 0
  let catalogs: LoadedIreksData['catalogs'] = EMPTY_DATA.catalogs

  while (true) {
    const payload = await listIreksIngredients(search, PAGE_SIZE, offset)
    catalogs = payload.catalogs ?? catalogs
    items.push(...payload.items)

    const fetched = payload.items.length
    if (!fetched || items.length >= payload.total) {
      break
    }
    offset += fetched
  }

  return { items, total: items.length, catalogs }
}

export function IreksProductsPage() {
  const [search, setSearch] = useState('')
  const [selectedCandidateId, setSelectedCandidateId] = useState<number | null>(null)
  const [checkedCandidateId, setCheckedCandidateId] = useState<number | null>(null)
  const [refreshTick, setRefreshTick] = useState(0)
  const [activeTab, setActiveTab] = useState<IreksTab>('Datos')
  const [sortKey, setSortKey] = useState<IreksSortKey>('ref')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc')
  const [selectedFabricanteId, setSelectedFabricanteId] = useState('')
  const [selectedFamiliaId, setSelectedFamiliaId] = useState('')
  const [selectedSubfamiliaId, setSelectedSubfamiliaId] = useState('')

  const query = useAsyncResource<LoadedIreksData>(() => loadAllIreksIngredients(search), EMPTY_DATA, [search, refreshTick])
  const rows = query.data.items
  const catalogs = query.data.catalogs

  const filteredRows = useMemo(() => {
    return rows.filter((row) => {
      if (selectedFabricanteId && row.fabricante_id !== selectedFabricanteId) {
        return false
      }
      if (selectedFamiliaId && row.articulo_familia_id !== selectedFamiliaId) {
        return false
      }
      if (selectedSubfamiliaId && row.articulo_subfamilia_id !== selectedSubfamiliaId) {
        return false
      }
      return true
    })
  }, [rows, selectedFabricanteId, selectedFamiliaId, selectedSubfamiliaId])

  const fabricanteLookup = useMemo(() => buildLookup(catalogs.fabricantes), [catalogs.fabricantes])
  const familiaLookup = useMemo(() => buildLookup(catalogs.familias), [catalogs.familias])
  const subfamiliaLookup = useMemo(() => buildLookup(catalogs.subfamilias), [catalogs.subfamilias])
  const distribuidorLookup = useMemo(() => buildLookup(catalogs.distribuidores), [catalogs.distribuidores])
  const envaseLookup = useMemo(() => buildLookup(catalogs.envases), [catalogs.envases])

  const fabricanteOptions = useMemo(() => buildUniqueCatalogOptions(rows, 'fabricante_id', fabricanteLookup), [rows, fabricanteLookup])
  const familyBaseRows = useMemo(
    () => rows.filter((row) => !selectedFabricanteId || row.fabricante_id === selectedFabricanteId),
    [rows, selectedFabricanteId],
  )
  const familiaOptions = useMemo(
    () => buildUniqueCatalogOptions(familyBaseRows, 'articulo_familia_id', familiaLookup),
    [familyBaseRows, familiaLookup],
  )
  const subfamilyBaseRows = useMemo(
    () =>
      rows.filter(
        (row) =>
          (!selectedFabricanteId || row.fabricante_id === selectedFabricanteId) &&
          (!selectedFamiliaId || row.articulo_familia_id === selectedFamiliaId),
      ),
    [rows, selectedFabricanteId, selectedFamiliaId],
  )
  const subfamiliaOptions = useMemo(
    () => buildUniqueCatalogOptions(subfamilyBaseRows, 'articulo_subfamilia_id', subfamiliaLookup),
    [subfamilyBaseRows, subfamiliaLookup],
  )

  const sortedRows = useMemo(() => {
    const sorted = [...filteredRows]

    sorted.sort((left, right) => {
      let comparison = 0

      if (sortKey === 'ref') {
        comparison = (left.articulo_referencia_corta || left.articulo_referencia || left.articulo_id).localeCompare(
          right.articulo_referencia_corta || right.articulo_referencia || right.articulo_id,
          'es',
          { sensitivity: 'base', numeric: true },
        )
      } else if (sortKey === 'name') {
        comparison = (left.articulo_descripcion || '').localeCompare(right.articulo_descripcion || '', 'es', {
          sensitivity: 'base',
          numeric: true,
        })
      } else {
        const leftSelected = checkedCandidateId !== null && left.id === checkedCandidateId
        const rightSelected = checkedCandidateId !== null && right.id === checkedCandidateId
        comparison = Number(leftSelected) - Number(rightSelected)
      }

      if (comparison === 0) {
        comparison =
          (left.articulo_referencia_corta || left.articulo_referencia || left.articulo_id).localeCompare(
            right.articulo_referencia_corta || right.articulo_referencia || right.articulo_id,
            'es',
            { sensitivity: 'base', numeric: true },
          )
      }

      return sortDirection === 'asc' ? comparison : -comparison
    })

    return sorted
  }, [filteredRows, checkedCandidateId, sortDirection, sortKey])

  const selectedRowId = useMemo(() => {
    if (!sortedRows.length) {
      return null
    }
    if (selectedCandidateId !== null && sortedRows.some((row) => row.id === selectedCandidateId)) {
      return selectedCandidateId
    }
    return sortedRows[0].id ?? null
  }, [selectedCandidateId, sortedRows])

  const sortAriaValue = (key: IreksSortKey) => {
    if (sortKey !== key) {
      return 'none'
    }
    return sortDirection === 'asc' ? 'ascending' : 'descending'
  }

  const updateSort = (nextKey: IreksSortKey) => {
    if (sortKey === nextKey) {
      setSortDirection((currentDirection) => (currentDirection === 'asc' ? 'desc' : 'asc'))
      return
    }

    setSortKey(nextKey)
    setSortDirection('asc')
  }

  const detailQuery = useAsyncResource(
    () => {
      if (selectedRowId === null) {
        return Promise.resolve(null as IngredientIreksRead | null)
      }
      return getIreksIngredientDetail(selectedRowId)
    },
    null as IngredientIreksRead | null,
    [selectedRowId],
  )

  const formatCatalog = (value: string, lookup: Map<string, string>) => lookup.get(value) || 'Pendiente de catálogo'

  const dataTab = detailQuery.data ? (
    <div className="ireks-products-data-grid">
      <ReadonlyField label="Fabricante" value={formatCatalog(detailQuery.data.fabricante_id, fabricanteLookup)} />
      <ReadonlyField label="Familia" value={formatCatalog(detailQuery.data.articulo_familia_id, familiaLookup)} />
      <ReadonlyField label="Subfamilia" value={formatCatalog(detailQuery.data.articulo_subfamilia_id, subfamiliaLookup)} />
      <ReadonlyField label="Presentación" value={formatCatalog(detailQuery.data.articulo_envase_id, envaseLookup)} />
      <ReadonlyField label="Contenido" value={detailQuery.data.articulo_envase_cantidad} kind="number" />
      <ReadonlyField label="Unidad contenido" value={detailQuery.data.articulo_contenido_unidad} />
      <ReadonlyField label="Peso unidad" value={detailQuery.data.articulo_envase_peso} kind="number" />
      <ReadonlyField label="Unidad peso" value={detailQuery.data.articulo_envase_unidad_medida} />
      <ReadonlyField label="Total presentación" value={detailQuery.data.articulo_envase_peso_total} kind="number" />
      <ReadonlyField label="Pallet" value={detailQuery.data.transporte_pallet_tipo} />
      <ReadonlyField label="Presentaciones/capa" value={detailQuery.data.transporte_cajas_por_capa} kind="number" />
      <ReadonlyField label="Capas" value={detailQuery.data.transporte_capas_por_pallet} kind="number" />
      <ReadonlyField label="Presentaciones/pallet" value={detailQuery.data.transporte_cajas_por_pallet} kind="number" />
      <ReadonlyField label="Uds/pallet" value={detailQuery.data.transporte_unidades_por_pallet} kind="number" />
      <ReadonlyField label="Total pallet" value={detailQuery.data.transporte_kg_por_pallet} kind="number" />
      <ReadonlyField label="Obs." value={detailQuery.data.transporte_observaciones} />
    </div>
  ) : (
    <div className="ireks-products-tab-empty">Selecciona un producto para ver los datos.</div>
  )

  const clearFilters = () => {
    setSearch('')
    setSelectedFabricanteId('')
    setSelectedFamiliaId('')
    setSelectedSubfamiliaId('')
    setSelectedCandidateId(null)
  }

  return (
    <section className="page-grid ireks-products-page">
      <div className="ireks-products-workspace">
        <section className="panel-section ireks-products-list-panel">
          <AppSectionHeader
            title="Productos IREKS"
            rightSlot={<span className="surface-chip">{filteredRows.length} visibles</span>}
            className="ireks-products-page__header"
          />

          <div className="ireks-products-action-ribbon" aria-label="Acciones de productos IREKS">
            <AppButton variant="primary" size="sm" disabled icon={<Plus size={16} strokeWidth={2.5} />}>
              Nuevo
            </AppButton>
            <AppButton variant="danger" size="sm" disabled icon={<Trash2 size={16} strokeWidth={2.5} />}>
              Eliminar
            </AppButton>
            <AppButton variant="ghost" size="sm" disabled icon={<List size={16} strokeWidth={2.5} />}>
              Listados
            </AppButton>
          </div>

          <div className="ireks-products-filters">
            <label className="ireks-filter">
              <span>Fabricante</span>
              <select
                className="select"
                value={selectedFabricanteId}
                onChange={(event) => {
                  const nextValue = event.target.value
                  setSelectedFabricanteId(nextValue)
                  setSelectedFamiliaId('')
                  setSelectedSubfamiliaId('')
                }}
              >
                <option value="">Todos</option>
                {fabricanteOptions.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="ireks-filter">
              <span>Familia</span>
              <select
                className="select"
                value={selectedFamiliaId}
                onChange={(event) => {
                  const nextValue = event.target.value
                  setSelectedFamiliaId(nextValue)
                  setSelectedSubfamiliaId('')
                }}
              >
                <option value="">Todos</option>
                {familiaOptions.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="ireks-filter">
              <span>Subfamilia</span>
              <select
                className="select"
                value={selectedSubfamiliaId}
                onChange={(event) => setSelectedSubfamiliaId(event.target.value)}
              >
                <option value="">Todos</option>
                {subfamiliaOptions.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.name}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="toolbar ingredients-search-toolbar">
            <input
              className="input"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value)
                setSelectedCandidateId(null)
              }}
              placeholder="Buscar producto por referencia o nombre"
            />
            <AppButton
              variant="danger"
              size="sm"
              onClick={clearFilters}
              disabled={!search && !selectedFabricanteId && !selectedFamiliaId && !selectedSubfamiliaId}
              icon={<X size={16} strokeWidth={2.4} />}
            >
              Limpiar
            </AppButton>
          </div>

          <QueryState
            loading={query.loading}
            error={query.error}
            empty={!filteredRows.length}
            emptyMessage="No hay productos IREKS para los filtros actuales."
          />

          <div className="ireks-products-list-scroll">
            {!!filteredRows.length && (
              <AppDataTable
                rows={sortedRows}
                getRowKey={(row, index) => row.id ?? row.articulo_id ?? index}
                wrapClassName="ireks-products-table-wrap"
                tableClassName="ireks-products-table"
                rowClassName={(row) => {
                  const rowId = row.id ?? null
                  return rowId !== null && rowId === selectedRowId ? 'row-selected' : undefined
                }}
                onRowClick={(row) => {
                  if (row.id !== null) {
                    setSelectedCandidateId(row.id)
                  }
                }}
                columns={[
                  {
                    key: 'ref',
                    header: (
                      <button type="button" className="ireks-sort-button" onClick={() => updateSort('ref')}>
                        <span>Ref.</span>
                        {sortKey === 'ref' && <span className="ireks-sort-indicator">{sortDirection === 'asc' ? '▲' : '▼'}</span>}
                      </button>
                    ),
                    render: (row) => row.articulo_referencia_corta || row.articulo_referencia || row.articulo_id,
                    headerCellProps: { 'aria-sort': sortAriaValue('ref') },
                  },
                  {
                    key: 'name',
                    header: (
                      <button type="button" className="ireks-sort-button" onClick={() => updateSort('name')}>
                        <span>Nombre</span>
                        {sortKey === 'name' && <span className="ireks-sort-indicator">{sortDirection === 'asc' ? '▲' : '▼'}</span>}
                      </button>
                    ),
                    render: (row) => row.articulo_descripcion || '-',
                    headerCellProps: { 'aria-sort': sortAriaValue('name') },
                  },
                  {
                    key: 'sel',
                    header: (
                      <button
                        type="button"
                        className="ireks-sort-button ireks-sort-button-center"
                        onClick={() => updateSort('sel')}
                      >
                        <span>Sel.</span>
                        {sortKey === 'sel' && <span className="ireks-sort-indicator">{sortDirection === 'asc' ? '▲' : '▼'}</span>}
                      </button>
                    ),
                    cellClassName: 'ireks-products-sel-cell',
                    render: (row) => {
                      const rowId = row.id ?? null
                      const isChecked = rowId !== null && rowId === checkedCandidateId
                      return (
                        <input
                          type="checkbox"
                          checked={isChecked}
                          aria-label={`Seleccionar ${row.articulo_descripcion || row.articulo_referencia || row.articulo_id}`}
                          onClick={(event) => event.stopPropagation()}
                          onChange={() => {
                            if (rowId === null) {
                              return
                            }
                            setCheckedCandidateId((currentId) => (currentId === rowId ? null : rowId))
                          }}
                        />
                      )
                    },
                    headerCellProps: { 'aria-sort': sortAriaValue('sel') },
                  },
                ]}
              />
            )}
          </div>
        </section>

        <div className="ireks-products-right-stack">
          <section className="panel-section ireks-products-detail-panel">
            <div className="ireks-products-detail-toolbar">
              <ActionButton className="ireks-action-btn-success">Nuevo</ActionButton>
              <ActionButton className="ireks-action-btn-danger">Eliminar</ActionButton>
              <ActionButton className="ireks-action-btn-outline">ID</ActionButton>
              <ActionButton className="ireks-action-btn-outline">Importar Excel/CSV</ActionButton>
              <ActionButton className="ireks-action-btn-primary">Listados</ActionButton>
              <ActionButton
                className="ireks-action-btn-outline"
                disabled={false}
                onClick={() => {
                  setRefreshTick((prev) => prev + 1)
                }}
              >
                Refrescar
              </ActionButton>
            </div>

            <div className="section-heading section-heading-compact">
              <div>
                <h3>Detalle del producto</h3>
                <p>Ficha read-only del producto IREKS seleccionado.</p>
              </div>
            </div>

            <div className="ireks-products-detail-scroll">
              <QueryState
                loading={detailQuery.loading}
                error={detailQuery.error}
                empty={!detailQuery.data}
                emptyMessage="Selecciona un producto para ver el detalle read-only."
              />

              {!!detailQuery.data && (
                <div className="ireks-products-detail-grid">
                  <ReadonlyField
                    label="Ref."
                    value={detailQuery.data.articulo_referencia || detailQuery.data.articulo_id}
                    className="ireks-field--compact ireks-field--ref"
                  />
                  <ReadonlyField
                    label="Ref. corta"
                    value={detailQuery.data.articulo_referencia_corta}
                    className="ireks-field--compact ireks-field--ref-corta"
                  />
                  <ReadonlyField
                    label="Descripción"
                    value={detailQuery.data.articulo_descripcion}
                    className="ireks-field--description"
                  />
                  <ReadonlyField label="Distribuidor" value={formatCatalog(detailQuery.data.distribuidor_id, distribuidorLookup)} />
                  <ReadonlyField
                    label="Referencia"
                    value={detailQuery.data.articulo_referencia || detailQuery.data.articulo_id}
                    className="ireks-field--compact ireks-field--distributor-reference"
                  />
                  <ReadonlyField label="Descripción comercial" value={detailQuery.data.articulo_descripcion} />
                  <div className="ireks-products-status-row">
                    <span className="surface-chip">{detailQuery.data.articulo_status_activo ? 'Status activo' : 'Status inactivo'}</span>
                  </div>
                  <div className="ireks-products-status-row">
                    <span className="surface-chip">{detailQuery.data.articulo_status_en_lista ? 'Status en lista' : 'Fuera de lista'}</span>
                  </div>
                  <div className="ireks-products-status-row">
                    <span className="surface-chip">{formatText(detailQuery.data.categoria)}</span>
                  </div>
                </div>
              )}
            </div>
          </section>

          <section className="panel-section ireks-products-tabs-panel">
            <div className="section-heading">
              <div>
                <h3>Información del producto</h3>
                <p>Tabs read-only del producto seleccionado.</p>
              </div>
            </div>

            <div className="ireks-tabs">
              {TABS.map((tab) => (
                <TabButton key={tab} tab={tab} active={activeTab === tab} onClick={setActiveTab} />
              ))}
            </div>

            <div className="ireks-products-tab-body">
              {activeTab === 'Datos' ? dataTab : <div className="ireks-products-tab-empty">{tabPlaceholder(activeTab)}</div>}
            </div>
          </section>
        </div>
      </div>
    </section>
  )
}

function tabPlaceholder(tab: IreksTab) {
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
      return 'Datos del producto'
  }
}


