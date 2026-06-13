import { useMemo, useState } from 'react'
import { getIreksIngredientDetail, listIreksIngredients } from '../api/ingredients'
import { QueryState } from '../components/QueryState'
import { useAsyncResource } from '../features/useAsyncResource'
import type { IngredientIreksListPayload, IngredientIreksRead } from '../types/api'

const PAGE_SIZE = 100

type IreksTab = 'Datos' | 'Tarifa' | 'Entradas' | 'Salidas' | 'Stock' | 'Mensual' | 'Pedidos' | 'Nutrición' | 'Clientes'

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

function ReadonlyField({
  label,
  value,
  kind = 'text',
}: {
  label: string
  value: string | number | boolean | null | undefined
  kind?: 'text' | 'number'
}) {
  const displayValue =
    kind === 'number' ? formatNumber(typeof value === 'number' ? value : Number(value)) : formatText(value)

  return (
    <label className="ireks-field">
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
  const [refreshTick, setRefreshTick] = useState(0)
  const [activeTab, setActiveTab] = useState<IreksTab>('Datos')

  const query = useAsyncResource<LoadedIreksData>(() => loadAllIreksIngredients(search), EMPTY_DATA, [search, refreshTick])
  const rows = query.data.items

  const selectedRowId = useMemo(() => {
    if (!rows.length) {
      return null
    }
    if (selectedCandidateId !== null && rows.some((row) => row.id === selectedCandidateId)) {
      return selectedCandidateId
    }
    return rows[0].id ?? null
  }, [rows, selectedCandidateId])

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

  const catalogs = query.data.catalogs
  const fabricanteLookup = useMemo(() => buildLookup(catalogs.fabricantes), [catalogs.fabricantes])
  const familiaLookup = useMemo(() => buildLookup(catalogs.familias), [catalogs.familias])
  const subfamiliaLookup = useMemo(() => buildLookup(catalogs.subfamilias), [catalogs.subfamilias])
  const distribuidorLookup = useMemo(() => buildLookup(catalogs.distribuidores), [catalogs.distribuidores])
  const envaseLookup = useMemo(() => buildLookup(catalogs.envases), [catalogs.envases])

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

  return (
    <section className="page-grid ireks-products-page">
      <div className="ireks-products-workspace">
        <section className="panel-section ireks-products-list-panel">
          <div className="section-heading">
            <div>
              <h3>Productos IREKS</h3>
              <p>Catálogo read-only de productos IREKS.</p>
            </div>
            <span className="surface-chip">{query.data.total} visibles</span>
          </div>

          <div className="ireks-products-filters">
            <label className="ireks-filter">
              <span>Fabricante</span>
              <select className="select" disabled defaultValue="">
                <option value="">Todos</option>
              </select>
            </label>
            <label className="ireks-filter">
              <span>Familia</span>
              <select className="select" disabled defaultValue="">
                <option value="">Todos</option>
              </select>
            </label>
            <label className="ireks-filter">
              <span>Subfamilia</span>
              <select className="select" disabled defaultValue="">
                <option value="">Todos</option>
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
          </div>

          <QueryState loading={query.loading} error={query.error} empty={!rows.length} emptyMessage="No hay productos IREKS para los filtros actuales." />

          <div className="ireks-products-list-scroll">
            {!!rows.length && (
              <div className="table-wrap ireks-products-table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Ref.</th>
                      <th>Nombre</th>
                      <th>Sel.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row, index) => {
                      const rowId = row.id ?? null
                      const isSelected = rowId !== null && rowId === selectedRowId
                      return (
                        <tr
                          key={rowId ?? row.articulo_id ?? index}
                          className={isSelected ? 'row-selected' : ''}
                          onClick={() => {
                            if (rowId !== null) {
                              setSelectedCandidateId(rowId)
                            }
                          }}
                        >
                          <td>{row.articulo_referencia_corta || row.articulo_referencia || row.articulo_id}</td>
                          <td>{row.articulo_descripcion || '-'}</td>
                          <td>{row.articulo_status_en_lista ? 'Si' : 'No'}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </section>

        <div className="ireks-products-right-stack">
          <section className="panel-section ireks-products-detail-panel">
            <div className="ireks-products-detail-toolbar">
              <button type="button" className="action-btn" disabled>
                Nuevo
              </button>
              <button type="button" className="action-btn" disabled>
                Eliminar
              </button>
              <button type="button" className="action-btn" disabled>
                ID
              </button>
              <button type="button" className="action-btn" disabled>
                Importar Excel/CSV
              </button>
              <button type="button" className="action-btn" disabled>
                Listados
              </button>
              <button
                type="button"
                className="action-btn"
                onClick={() => {
                  setRefreshTick((prev) => prev + 1)
                }}
              >
                Refrescar
              </button>
            </div>

            <div className="section-heading section-heading-compact">
              <div>
                <h3>Detalle del producto</h3>
                <p>Ficha read-only del producto IREKS seleccionado.</p>
              </div>
            </div>

            <QueryState
              loading={detailQuery.loading}
              error={detailQuery.error}
              empty={!detailQuery.data}
              emptyMessage="Selecciona un producto para ver el detalle read-only."
            />

            {!!detailQuery.data && (
              <div className="ireks-products-detail-grid">
                <ReadonlyField label="Ref." value={detailQuery.data.articulo_referencia || detailQuery.data.articulo_id} />
                <ReadonlyField label="Ref. corta" value={detailQuery.data.articulo_referencia_corta} />
                <ReadonlyField label="Descripción" value={detailQuery.data.articulo_descripcion} />
                <ReadonlyField label="Distribuidor" value={formatCatalog(detailQuery.data.distribuidor_id, distribuidorLookup)} />
                <ReadonlyField label="Referencia" value={detailQuery.data.articulo_referencia || detailQuery.data.articulo_id} />
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

            <div className="ireks-products-tab-body">{activeTab === 'Datos' ? dataTab : <div className="ireks-products-tab-empty">{tabPlaceholder(activeTab)}</div>}</div>
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
