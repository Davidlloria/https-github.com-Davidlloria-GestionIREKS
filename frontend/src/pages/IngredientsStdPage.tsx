import { useMemo, useState } from 'react'

import { getStdIngredient, listStdIngredientPrices, listStdIngredients } from '../api/ingredients'
import { QueryState } from '../components/QueryState'
import { StatCard } from '../components/StatCard'
import { useAsyncResource } from '../features/useAsyncResource'
import type { IngredientStdListResponse } from '../api/ingredients'
import type { IngredientStdRead, MateriaPrimaPrecioRead } from '../types/ingredients'

const PAGE_SIZE = 25

type StdTab = 'Articulo' | 'Proveedores'
type StdFilter = 'all' | 'active' | 'inactive'

const EMPTY_LIST: IngredientStdListResponse = {
  items: [],
  total: 0,
  limit: PAGE_SIZE,
  offset: 0,
}

function formatNumber(value: number | null | undefined) {
  const safeValue = Number.isFinite(Number(value)) ? Number(value) : 0
  return new Intl.NumberFormat('es-ES', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(safeValue)
}

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

function formatPrice(value: number | null | undefined) {
  const safeValue = Number.isFinite(Number(value)) ? Number(value) : 0
  return safeValue > 0 ? formatNumber(safeValue) : '-'
}

const TABS: StdTab[] = ['Articulo', 'Proveedores']

export function IngredientsStdPage() {
  const [search, setSearch] = useState('')
  const [pageIndex, setPageIndex] = useState(0)
  const [activeFilter, setActiveFilter] = useState<StdFilter>('all')
  const [selectedCandidateId, setSelectedCandidateId] = useState('')
  const [activeTab, setActiveTab] = useState<StdTab>('Articulo')

  const offset = pageIndex * PAGE_SIZE
  const listQuery = useAsyncResource<IngredientStdListResponse>(
    () => listStdIngredients(search, PAGE_SIZE, offset, activeFilter),
    EMPTY_LIST,
    [search, offset, activeFilter],
  )

  const rows = listQuery.data.items
  const selectedArticuloId = useMemo(() => {
    if (!rows.length) {
      return ''
    }
    if (selectedCandidateId && rows.some((row) => row.articulo_id === selectedCandidateId)) {
      return selectedCandidateId
    }
    return rows[0].articulo_id
  }, [rows, selectedCandidateId])

  const detailQuery = useAsyncResource<IngredientStdRead | null>(
    () => {
      if (!selectedArticuloId) {
        return Promise.resolve(null)
      }
      return getStdIngredient(selectedArticuloId)
    },
    null,
    [selectedArticuloId],
  )

  const pricesQuery = useAsyncResource<MateriaPrimaPrecioRead[]>(
    () => {
      if (!selectedArticuloId) {
        return Promise.resolve([])
      }
      return listStdIngredientPrices(selectedArticuloId)
    },
    [],
    [selectedArticuloId],
  )

  const visibleRows = rows
  const hasPreviousPage = pageIndex > 0
  const hasNextPage = offset + rows.length < listQuery.data.total
  const currentPage = pageIndex + 1
  const totalPages = Math.max(1, Math.ceil(listQuery.data.total / PAGE_SIZE))

  const providerSummary = useMemo(() => {
    const summary = new Map<
      string,
      { provider: string; count: number; active: number; priceTotal: number; priceCount: number }
    >()

    for (const row of visibleRows) {
      const providerKey = row.distribuidor_id || row.proveedor_id || row.distribuidor_nombre || 'sin-proveedor'
      const providerName = row.distribuidor_nombre || row.proveedor_id || 'Sin proveedor'
      const current = summary.get(providerKey) ?? {
        provider: providerName,
        count: 0,
        active: 0,
        priceTotal: 0,
        priceCount: 0,
      }
      current.count += 1
      current.active += row.activo ? 1 : 0
      if (Number.isFinite(row.pvp_formato) && row.pvp_formato > 0) {
        current.priceTotal += row.pvp_formato
        current.priceCount += 1
      }
      summary.set(providerKey, current)
    }

    return Array.from(summary.values()).sort((a, b) => b.count - a.count || a.provider.localeCompare(b.provider))
  }, [visibleRows])

  const articleTab = (
    <div className="ingredients-std-workspace">
      <section className="panel-section ingredients-std-list-panel">
        <div className="section-heading">
          <div>
            <h3>Listado de materias primas</h3>
            <p>Vista read-only propia, separada de Productos IREKS.</p>
          </div>
          <span className="surface-chip">
            {visibleRows.length} visibles de {listQuery.data.total}
          </span>
        </div>

        <div className="ingredients-std-filters">
          <label className="ingredients-std-filter">
            <span>Estado</span>
            <select
              className="select"
              value={activeFilter}
              onChange={(event) => {
                setActiveFilter(event.target.value as StdFilter)
                setPageIndex(0)
                setSelectedCandidateId('')
              }}
            >
              <option value="all">Todos</option>
              <option value="active">Activas</option>
              <option value="inactive">Inactivas</option>
            </select>
          </label>

          <label className="ingredients-std-search">
            <span>Buscar</span>
            <input
              className="input"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value)
                setPageIndex(0)
                setSelectedCandidateId('')
              }}
              placeholder="Buscar materia prima por nombre, codigo o referencia"
            />
          </label>
        </div>

        <div className="toolbar pager-toolbar">
          <span className="surface-chip">
            Página {currentPage} de {totalPages}
          </span>
          <button
            type="button"
            className="action-btn"
            disabled={!hasPreviousPage}
            onClick={() => setPageIndex((prev) => Math.max(0, prev - 1))}
          >
            Anterior
          </button>
          <button
            type="button"
            className="action-btn"
            disabled={!hasNextPage}
            onClick={() => setPageIndex((prev) => prev + 1)}
          >
            Siguiente
          </button>
        </div>

        <QueryState
          loading={listQuery.loading}
          error={listQuery.error}
          empty={!visibleRows.length}
          emptyMessage="No hay materias primas para los filtros actuales."
        />

        {!!visibleRows.length && (
          <div className="table-wrap ingredients-std-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Activo</th>
                  <th>Referencia</th>
                  <th>Nombre</th>
                  <th>Proveedor</th>
                  <th>Categoria</th>
                  <th>Formato</th>
                  <th>Cantidad</th>
                  <th>PVP formato</th>
                  <th>PVP unidad</th>
                </tr>
              </thead>
              <tbody>
                {visibleRows.map((row) => (
                  <tr
                    key={row.articulo_id}
                    className={row.articulo_id === selectedArticuloId ? 'row-selected' : ''}
                    onClick={() => setSelectedCandidateId(row.articulo_id)}
                  >
                    <td>{row.activo ? 'Si' : 'No'}</td>
                    <td>{row.articulo_referencia_distribuidor || row.articulo_id || '-'}</td>
                    <td>{row.articulo_descripcion || '-'}</td>
                    <td>{row.distribuidor_nombre || row.proveedor_id || '-'}</td>
                    <td>{row.categoria || '-'}</td>
                    <td>{row.formato || '-'}</td>
                    <td>{`${formatNumber(row.formato_cantidad)} ${row.formato_unidad || ''}`.trim()}</td>
                    <td>{formatPrice(row.pvp_formato)}</td>
                    <td>{formatPrice(row.pvp_unidad_medida)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <aside className="panel-section ingredients-std-detail-panel">
        <div className="section-heading section-heading-compact">
          <div>
            <h3>Detalle de materia prima</h3>
            <p>Ficha read-only de la materia prima seleccionada.</p>
          </div>
        </div>

        <QueryState
          loading={detailQuery.loading}
          error={detailQuery.error}
          empty={!detailQuery.data}
          emptyMessage="Selecciona un registro para ver el detalle read-only."
        />

        {!!detailQuery.data && (
          <>
            <dl className="detail-list ingredients-std-detail-list">
              <div>
                <dt>Referencia</dt>
                <dd>{formatText(detailQuery.data.articulo_referencia_distribuidor || detailQuery.data.articulo_id)}</dd>
              </div>
              <div>
                <dt>Proveedor</dt>
                <dd>{formatText(detailQuery.data.distribuidor_nombre || detailQuery.data.proveedor_id)}</dd>
              </div>
              <div>
                <dt>Descripcion</dt>
                <dd>{formatText(detailQuery.data.articulo_descripcion)}</dd>
              </div>
              <div>
                <dt>Categoria</dt>
                <dd>{formatText(detailQuery.data.categoria)}</dd>
              </div>
              <div>
                <dt>Grupo</dt>
                <dd>{formatText(detailQuery.data.articulo_grupo_id)}</dd>
              </div>
              <div>
                <dt>Familia</dt>
                <dd>{formatText(detailQuery.data.articulo_familia_id)}</dd>
              </div>
              <div>
                <dt>Subfamilia</dt>
                <dd>{formatText(detailQuery.data.articulo_subfamilia_id)}</dd>
              </div>
              <div>
                <dt>Formato</dt>
                <dd>{formatText(detailQuery.data.formato)}</dd>
              </div>
              <div>
                <dt>Cantidad</dt>
                <dd>{formatText(detailQuery.data.formato_cantidad)}</dd>
              </div>
              <div>
                <dt>Unidad</dt>
                <dd>{formatText(detailQuery.data.formato_unidad)}</dd>
              </div>
              <div>
                <dt>PVP formato</dt>
                <dd>{formatPrice(detailQuery.data.pvp_formato)}</dd>
              </div>
              <div>
                <dt>PVP unidad</dt>
                <dd>{formatPrice(detailQuery.data.pvp_unidad_medida)}</dd>
              </div>
              <div>
                <dt>Estado</dt>
                <dd>{detailQuery.data.activo ? 'Activo' : 'Inactivo'}</dd>
              </div>
            </dl>

            <div className="ingredients-std-prices-panel">
              <div className="section-heading section-heading-compact">
                <div>
                  <h3>Historial de precios</h3>
                  <p>Lectura propia del endpoint read-only de materias primas.</p>
                </div>
              </div>

              <QueryState
                loading={pricesQuery.loading}
                error={pricesQuery.error}
                empty={!pricesQuery.data.length}
                emptyMessage="No hay historial de precios para esta materia prima."
              />

              {!!pricesQuery.data.length && (
                <div className="table-wrap ingredients-std-prices-table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Fecha</th>
                        <th>Costo neto</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pricesQuery.data.map((row) => (
                        <tr key={`${row.articulo_id}-${row.fecha_precio}`}>
                          <td>{row.fecha_precio}</td>
                          <td>{formatNumber(row.costo_neto)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </>
        )}
      </aside>
    </div>
  )

  const providersTab = (
    <div className="panel-section ingredients-std-providers-panel">
      <div className="section-heading">
        <div>
          <h3>Proveedores</h3>
          <p>Resumen read-only de los proveedores visibles en la página actual.</p>
        </div>
        <span className="surface-chip">{providerSummary.length} proveedores</span>
      </div>

      <QueryState
        loading={listQuery.loading}
        error={listQuery.error}
        empty={!providerSummary.length}
        emptyMessage="No hay proveedores visibles para el filtro actual."
      />

      {!!providerSummary.length && (
        <div className="table-wrap ingredients-std-providers-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Proveedor</th>
                <th>Referencias</th>
                <th>Activas</th>
                <th>PVP medio</th>
              </tr>
            </thead>
            <tbody>
              {providerSummary.map((row) => (
                <tr key={row.provider}>
                  <td>{row.provider}</td>
                  <td>{row.count}</td>
                  <td>{row.active}</td>
                  <td>{row.priceCount ? formatNumber(row.priceTotal / row.priceCount) : '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )

  return (
    <section className="page-grid ingredients-std-page">
      <header className="module-header">
        <div className="module-header-copy">
          <p className="module-kicker">Modulo read-only</p>
          <h2>Materias primas</h2>
          <p className="module-description">Catalogo read-only propio de materias primas, separado de Productos IREKS.</p>
        </div>
        <div className="module-header-meta">
          <span className="surface-chip">Vista sin mutaciones</span>
        </div>
      </header>

      <div className="cards">
        <StatCard label="Total" value={visibleRows.length} />
        <StatCard label="Activas" value={visibleRows.filter((row) => row.activo).length} />
        <StatCard label="Con precio" value={visibleRows.filter((row) => Number.isFinite(row.pvp_formato) && row.pvp_formato > 0).length} />
        <StatCard label="Proveedores" value={providerSummary.length} />
      </div>

      <section className="panel-section ingredients-std-tabs-panel">
        <div className="section-heading">
          <div>
            <h3>Contenido</h3>
            <p>La navegación interna se mantiene read-only y no expone mutaciones.</p>
          </div>
        </div>

        <div className="ingredients-std-tabs" role="tablist" aria-label="Secciones de materias primas">
          {TABS.map((tab) => (
            <button
              key={tab}
              type="button"
              role="tab"
              aria-selected={activeTab === tab}
              className={`ingredients-std-tab ${activeTab === tab ? 'active' : ''}`}
              onClick={() => setActiveTab(tab)}
            >
              {tab}
            </button>
          ))}
        </div>

        <div className="ingredients-std-tab-body">
          {activeTab === 'Articulo' ? articleTab : providersTab}
        </div>
      </section>
    </section>
  )
}
