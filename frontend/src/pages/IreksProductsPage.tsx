import { useMemo, useState } from 'react'
import { getIreksIngredientDetail, listIreksIngredients } from '../api/ingredients'
import { QueryState } from '../components/QueryState'
import { useAsyncResource } from '../features/useAsyncResource'
import type { IngredientIreksListPayload, IngredientIreksRead } from '../types/api'

const PAGE_SIZE = 25

const EMPTY_LIST: IngredientIreksListPayload = {
  items: [],
  total: 0,
  limit: PAGE_SIZE,
  offset: 0,
  catalogs: {
    distribuidores: [],
    fabricantes: [],
    familias: [],
    subfamilias: [],
    envases: [],
  },
}

const TABS = ['Datos', 'Tarifa', 'Entradas', 'Salidas', 'Stock', 'Mensual', 'Pedidos', 'Nutrición', 'Clientes'] as const
type IreksTab = (typeof TABS)[number]

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

function CatalogSelect({ label, disabled = true }: { label: string; disabled?: boolean }) {
  return (
    <label className="ireks-filter">
      <span>{label}</span>
      <select className="select" disabled={disabled} defaultValue="">
        <option value="">Todos</option>
      </select>
    </label>
  )
}

function ReadonlyField({
  label,
  value,
  format = 'text',
}: {
  label: string
  value: string | number | boolean | null | undefined
  format?: 'text' | 'number'
}) {
  const displayValue = format === 'number' ? formatNumber(typeof value === 'number' ? value : Number(value)) : formatText(value)
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
  disabled = false,
  onClick,
}: {
  tab: IreksTab
  active: boolean
  disabled?: boolean
  onClick: (tab: IreksTab) => void
}) {
  return (
    <button
      type="button"
      className={`ireks-tab ${active ? 'ireks-tab-active' : ''}`}
      disabled={disabled}
      onClick={() => onClick(tab)}
    >
      {tab}
    </button>
  )
}

export function IreksProductsPage() {
  const [search, setSearch] = useState('')
  const [pageIndex, setPageIndex] = useState(0)
  const [selectedCandidateId, setSelectedCandidateId] = useState<number | null>(null)
  const [refreshTick, setRefreshTick] = useState(0)
  const [activeTab, setActiveTab] = useState<IreksTab>('Datos')

  const offset = pageIndex * PAGE_SIZE
  const query = useAsyncResource<IngredientIreksListPayload>(
    () => listIreksIngredients(search, PAGE_SIZE, offset),
    EMPTY_LIST,
    [search, offset, refreshTick],
  )
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

  const selectedRow = rows.find((row) => row.id === selectedRowId) ?? null
  const hasPreviousPage = pageIndex > 0
  const hasNextPage = offset + rows.length < query.data.total
  const currentPage = pageIndex + 1
  const totalPages = Math.max(1, Math.ceil(query.data.total / PAGE_SIZE))
  const emptyMessage =
    query.data.total > 0 && !rows.length
      ? 'No hay productos IREKS en la pagina actual. Prueba con otra busqueda o pagina.'
      : 'No hay productos IREKS para los filtros actuales.'

  return (
    <section className="page-grid ingredients-page ingredients-page-ireks">
      <header className="module-header">
        <div className="module-header-copy">
          <p className="module-kicker">Modulo read-only</p>
          <h2>Productos IREKS</h2>
          <p className="module-description">Catalogo read-only de productos IREKS</p>
        </div>
        <div className="module-header-meta">
          <span className="surface-chip">Vista sin mutaciones</span>
        </div>
      </header>

      <div className="ingredients-workspace">
        <section className="panel-section ingredients-list-panel">
          <div className="section-heading">
            <div>
              <h3>Listado de productos</h3>
              <p>Filtros y busqueda sobre el catalogo de productos IREKS.</p>
            </div>
            <span className="surface-chip">Pagina {currentPage} de {totalPages}</span>
          </div>

          <div className="ingredients-filters">
            <CatalogSelect label="Fabricante" />
            <CatalogSelect label="Familia" />
            <CatalogSelect label="Subfamilia" />
          </div>

          <div className="toolbar ingredients-search-toolbar">
            <input
              className="input"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value)
                setPageIndex(0)
              }}
              placeholder="Buscar producto por referencia o nombre"
            />
            <div className="toolbar pager-toolbar">
              <button
                type="button"
                className="action-btn"
                disabled={!hasPreviousPage}
                onClick={() => setPageIndex((prev) => Math.max(0, prev - 1))}
              >
                Anterior
              </button>
              <button type="button" className="action-btn" disabled={!hasNextPage} onClick={() => setPageIndex((prev) => prev + 1)}>
                Siguiente
              </button>
            </div>
          </div>

          <QueryState
            loading={query.loading}
            error={query.error}
            empty={!rows.length}
            emptyMessage={emptyMessage}
          />

          {!!rows.length && (
            <div className="table-wrap ingredients-table-wrap">
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
        </section>

        <aside className="panel-section ingredients-detail-panel">
          <div className="ingredients-detail-toolbar">
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
            <>
              <div className="ireks-detail-grid">
                <ReadonlyField label="Ref." value={detailQuery.data.articulo_referencia || detailQuery.data.articulo_id} />
                <ReadonlyField label="Ref. corta" value={detailQuery.data.articulo_referencia_corta} />
                <ReadonlyField label="Descripción" value={detailQuery.data.articulo_descripcion} />
                <ReadonlyField label="Distribuidor" value={detailQuery.data.distribuidor_id} />
                <ReadonlyField label="Referencia" value={detailQuery.data.articulo_referencia || detailQuery.data.articulo_id} />
                <ReadonlyField label="Descripción comercial" value={detailQuery.data.articulo_descripcion} />
              </div>

              <div className="ireks-status-row">
                <div className="ireks-status-pill-row">
                  <span className="surface-chip">{detailQuery.data.articulo_status_activo ? 'Status activo' : 'Status inactivo'}</span>
                  <span className="surface-chip">{detailQuery.data.articulo_status_en_lista ? 'Status en lista' : 'Fuera de lista'}</span>
                  <span className="surface-chip">{formatText(detailQuery.data.categoria)}</span>
                </div>
              </div>

              <div className="ireks-tabs">
                {TABS.map((tab) => (
                  <TabButton
                    key={tab}
                    tab={tab}
                    active={activeTab === tab}
                    disabled={tab !== 'Datos'}
                    onClick={(nextTab) => setActiveTab(nextTab)}
                  />
                ))}
              </div>

              {activeTab === 'Datos' ? (
                <div className="ireks-data-grid">
                  <ReadonlyField label="Fabricante" value={detailQuery.data.fabricante_id} />
                  <ReadonlyField label="Familia" value={detailQuery.data.articulo_familia_id} />
                  <ReadonlyField label="Subfamilia" value={detailQuery.data.articulo_subfamilia_id} />
                  <ReadonlyField label="Presentación" value={detailQuery.data.articulo_envase_id} />
                  <ReadonlyField label="Contenido" value={detailQuery.data.articulo_envase_cantidad} format="number" />
                  <ReadonlyField label="Unidad contenido" value={detailQuery.data.articulo_contenido_unidad} />
                  <ReadonlyField label="Peso unidad" value={detailQuery.data.articulo_envase_peso} format="number" />
                  <ReadonlyField label="Unidad peso" value={detailQuery.data.articulo_envase_unidad_medida} />
                  <ReadonlyField label="Total presentación" value={detailQuery.data.articulo_envase_peso_total} format="number" />
                  <ReadonlyField label="Pallet" value={detailQuery.data.transporte_pallet_tipo} />
                  <ReadonlyField label="Presentaciones/capa" value={detailQuery.data.transporte_cajas_por_capa} format="number" />
                  <ReadonlyField label="Capas" value={detailQuery.data.transporte_capas_por_pallet} format="number" />
                  <ReadonlyField label="Presentaciones/pallet" value={detailQuery.data.transporte_cajas_por_pallet} format="number" />
                  <ReadonlyField label="Uds/pallet" value={detailQuery.data.transporte_unidades_por_pallet} format="number" />
                  <ReadonlyField label="Total pallet" value={detailQuery.data.transporte_kg_por_pallet} format="number" />
                  <ReadonlyField label="Obs." value={detailQuery.data.transporte_observaciones} />
                </div>
              ) : (
                <div className="ireks-tab-placeholder">Pendiente de migración específica</div>
              )}

              <div className="ireks-detail-footer">
                <ReadonlyField label="Estado selección" value={selectedRow?.articulo_status_en_lista ? 'Seleccionado' : 'No disponible'} />
                <ReadonlyField label="Peso total" value={detailQuery.data.articulo_envase_peso_total} format="number" />
              </div>
            </>
          )}
        </aside>
      </div>
    </section>
  )
}
