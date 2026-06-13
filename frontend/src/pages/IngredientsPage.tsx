import { useMemo, useState } from 'react'
import { getIngredientDetail, listIngredients } from '../api/ingredients'
import { QueryState } from '../components/QueryState'
import { StatCard } from '../components/StatCard'
import { useAsyncResource } from '../features/useAsyncResource'
import type { IngredientDetail, IngredientListItem, IngredientListResponse } from '../types/api'

const PAGE_SIZE = 25

type IngredientsMode = 'ireks' | 'std'

interface IngredientsPageProps {
  mode: IngredientsMode
}

const EMPTY_LIST: IngredientListResponse = {
  items: [] as IngredientListItem[],
  total: 0,
  limit: PAGE_SIZE,
  offset: 0,
}

function formatNumber(value: number) {
  return new Intl.NumberFormat('es-ES', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number.isFinite(value) ? value : 0)
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

function formatSource(source: string) {
  if (source === 'ireks') {
    return 'IREKS'
  }
  if (source === 'std') {
    return 'Materia prima'
  }
  return formatText(source)
}

const MODE_COPY: Record<
  IngredientsMode,
  {
    title: string
    subtitle: string
    searchPlaceholder: string
    listTitle: string
    listDescription: string
    detailTitle: string
    detailDescription: string
    emptyMessage: string
  }
> = {
  ireks: {
    title: 'Productos IREKS',
    subtitle: 'Catalogo read-only de productos IREKS, separado de materias primas.',
    searchPlaceholder: 'Buscar producto IREKS por nombre, codigo o referencia',
    listTitle: 'Listado de productos IREKS',
    listDescription: 'Selecciona una fila para cargar el detalle del producto activo.',
    detailTitle: 'Detalle de producto IREKS',
    detailDescription: 'Campos principales del producto seleccionado.',
    emptyMessage: 'No hay productos IREKS para los filtros actuales.',
  },
  std: {
    title: 'Materias primas',
    subtitle: 'Catalogo read-only de materias primas y articulos genericos.',
    searchPlaceholder: 'Buscar materia prima por nombre, codigo o referencia',
    listTitle: 'Listado de materias primas',
    listDescription: 'Selecciona una fila para cargar el detalle de la materia prima activa.',
    detailTitle: 'Detalle de materia prima',
    detailDescription: 'Campos principales de la materia prima seleccionada.',
    emptyMessage: 'No hay materias primas para los filtros actuales.',
  },
}

export function IngredientsPage({ mode }: IngredientsPageProps) {
  const modeCopy = MODE_COPY[mode]
  const isIreksMode = mode === 'ireks'
  const [search, setSearch] = useState('')
  const [pageIndex, setPageIndex] = useState(0)
  const [selectedCandidateId, setSelectedCandidateId] = useState('')

  const offset = pageIndex * PAGE_SIZE
  const ingredientsQuery = useAsyncResource<IngredientListResponse>(
    () => listIngredients(search, PAGE_SIZE, offset),
    EMPTY_LIST,
    [search, offset],
  )
  const ingredientRows: IngredientListItem[] = ingredientsQuery.data.items
  const visibleRows = useMemo(
    () => ingredientRows.filter((row) => row.source === mode),
    [ingredientRows, mode],
  )

  const selectedIngredientId = useMemo(() => {
    if (!visibleRows.length) {
      return ''
    }
    if (selectedCandidateId && visibleRows.some((row) => row.id === selectedCandidateId)) {
      return selectedCandidateId
    }
    return visibleRows[0].id
  }, [selectedCandidateId, visibleRows])

  const detailQuery = useAsyncResource(
    () => {
      if (!selectedIngredientId) {
        return Promise.resolve(null as IngredientDetail | null)
      }
      return getIngredientDetail(selectedIngredientId)
    },
    null as IngredientDetail | null,
    [selectedIngredientId],
  )

  const hasPreviousPage = pageIndex > 0
  const hasNextPage = offset + ingredientRows.length < ingredientsQuery.data.total
  const currentPage = pageIndex + 1
  const totalPages = Math.max(1, Math.ceil(ingredientsQuery.data.total / PAGE_SIZE))
  const emptyMessage =
    isIreksMode && ingredientsQuery.data.total > 0 && ingredientRows.length > 0 && !visibleRows.length
      ? 'La pagina actual no contiene productos IREKS. Cambia de pagina o ajusta la busqueda.'
      : modeCopy.emptyMessage

  const listPanel = (
    <section className="panel-section ingredients-list-panel">
      <div className="section-heading">
        <div>
          <h3>{modeCopy.listTitle}</h3>
          <p>{modeCopy.listDescription}</p>
        </div>
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

      <div className="toolbar ingredients-search-toolbar">
        <input
          className="input"
          value={search}
          onChange={(event) => {
            setSearch(event.target.value)
            setPageIndex(0)
          }}
          placeholder={modeCopy.searchPlaceholder}
        />
        <span className="surface-chip">Pagina {currentPage} de {totalPages}</span>
      </div>

      <div className="table-wrap ingredients-table-wrap">
        <table>
          <thead>
            <tr>
              <th>Codigo</th>
              <th>Nombre</th>
              <th>Origen</th>
              <th>Estado</th>
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row) => (
              <tr
                key={row.id}
                className={row.id === selectedIngredientId ? 'row-selected' : ''}
                onClick={() => setSelectedCandidateId(row.id)}
              >
                <td>{row.codigo || '-'}</td>
                <td>{row.nombre || '-'}</td>
                <td>{formatSource(row.source)}</td>
                <td>{row.activo ? 'Activo' : 'Inactivo'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )

  const detailPanel = (
    <aside className="panel-section ingredients-detail-panel">
      <div className="section-heading section-heading-compact">
        <div>
          <h3>{modeCopy.detailTitle}</h3>
          <p>{modeCopy.detailDescription}</p>
        </div>
      </div>

      <QueryState
        loading={detailQuery.loading}
        error={detailQuery.error}
        empty={!detailQuery.data}
        emptyMessage="Selecciona un registro para ver el detalle read-only."
      />

      {!!detailQuery.data && (
        <dl className="detail-list ingredients-detail-list">
          <div>
            <dt>Codigo</dt>
            <dd>{formatText(detailQuery.data.codigo)}</dd>
          </div>
          <div>
            <dt>Nombre</dt>
            <dd>{formatText(detailQuery.data.nombre)}</dd>
          </div>
          <div>
            <dt>Origen</dt>
            <dd>{formatSource(detailQuery.data.source)}</dd>
          </div>
          <div>
            <dt>Fabricante / proveedor</dt>
            <dd>{formatText(detailQuery.data.fabricante_id || detailQuery.data.proveedor_id)}</dd>
          </div>
          <div>
            <dt>Familia / subfamilia</dt>
            <dd>{formatText(detailQuery.data.familia_id || detailQuery.data.subfamilia_id)}</dd>
          </div>
          <div>
            <dt>Unidad</dt>
            <dd>{formatText(detailQuery.data.unidad)}</dd>
          </div>
          <div>
            <dt>Estado</dt>
            <dd>{detailQuery.data.activo ? 'Activo' : 'Inactivo'}</dd>
          </div>
          <div>
            <dt>Precio</dt>
            <dd>{detailQuery.data.precio > 0 ? formatNumber(detailQuery.data.precio) : '-'}</dd>
          </div>
        </dl>
      )}
    </aside>
  )

  if (isIreksMode) {
    return (
      <section className="page-grid ingredients-page ingredients-page-ireks">
        <header className="module-header">
          <div className="module-header-copy">
            <p className="module-kicker">Modulo read-only</p>
            <h2>{modeCopy.title}</h2>
            <p className="module-description">{modeCopy.subtitle}</p>
          </div>
          <div className="module-header-meta">
            <span className="surface-chip">Vista sin mutaciones</span>
          </div>
        </header>

        <QueryState
          loading={ingredientsQuery.loading}
          error={ingredientsQuery.error}
          empty={!visibleRows.length}
          emptyMessage={emptyMessage}
        />

        {!!visibleRows.length && (
          <div className="ingredients-workspace">
            {listPanel}
            {detailPanel}
          </div>
        )}
      </section>
    )
  }

  return (
    <section className="page-grid">
      <header className="module-header">
        <div className="module-header-copy">
          <p className="module-kicker">Modulo read-only</p>
          <h2>{modeCopy.title}</h2>
          <p className="module-description">{modeCopy.subtitle}</p>
        </div>
        <div className="module-header-meta">
          <span className="surface-chip">Vista sin mutaciones</span>
        </div>
      </header>

      <section className="panel-section">
        <div className="section-heading">
          <div>
            <h3>Filtros</h3>
            <p>Busca por nombre, codigo o referencia y navega por pagina antes de abrir el detalle.</p>
          </div>
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

        <div className="toolbar">
          <input
            className="input"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value)
              setPageIndex(0)
            }}
            placeholder={modeCopy.searchPlaceholder}
          />
        </div>
      </section>

      <div className="cards">
        <StatCard label="Total" value={visibleRows.length} />
        <StatCard label="Activos" value={visibleRows.filter((row) => row.activo).length} />
        <StatCard label="Con precio" value={visibleRows.filter((row) => Number.isFinite(row.precio) && row.precio > 0).length} />
        <StatCard
          label="Sin precio"
          value={visibleRows.length - visibleRows.filter((row) => Number.isFinite(row.precio) && row.precio > 0).length}
        />
      </div>

      <QueryState
        loading={ingredientsQuery.loading}
        error={ingredientsQuery.error}
        empty={!visibleRows.length}
        emptyMessage={emptyMessage}
      />

      {!!visibleRows.length && (
        <div className="orders-workspace">
          <section className="orders-list-panel">
            <div className="panel-section">
              <div className="section-heading">
                <div>
                  <h3>{modeCopy.listTitle}</h3>
                  <p>{modeCopy.listDescription}</p>
                </div>
                <span className="surface-chip">Mostrando {visibleRows.length} de {ingredientsQuery.data.total}</span>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Codigo</th>
                      <th>Nombre</th>
                      <th>Origen</th>
                      <th>Precio</th>
                      <th>Activo</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleRows.map((row) => (
                      <tr
                        key={row.id}
                        className={row.id === selectedIngredientId ? 'row-selected' : ''}
                        onClick={() => setSelectedCandidateId(row.id)}
                      >
                        <td>{row.id}</td>
                        <td>{row.codigo || '-'}</td>
                        <td>{row.nombre || '-'}</td>
                        <td>{formatSource(row.source)}</td>
                        <td>{Number.isFinite(row.precio) && row.precio > 0 ? formatNumber(row.precio) : '-'}</td>
                        <td>{row.activo ? 'Si' : 'No'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </section>

          <aside className="detail-panel detail-panel-orders">
            <div className="section-heading section-heading-compact">
              <div>
                <h3>{modeCopy.detailTitle}</h3>
                <p>{modeCopy.detailDescription}</p>
              </div>
            </div>
            <QueryState
              loading={detailQuery.loading}
              error={detailQuery.error}
              empty={!detailQuery.data}
              emptyMessage="Selecciona un ingrediente para ver el detalle."
            />

            {!!detailQuery.data && (
              <dl className="detail-list">
                <div>
                  <dt>ID</dt>
                  <dd>{formatText(detailQuery.data.id)}</dd>
                </div>
                <div>
                  <dt>Codigo</dt>
                  <dd>{formatText(detailQuery.data.codigo)}</dd>
                </div>
                <div>
                  <dt>Nombre</dt>
                  <dd>{formatText(detailQuery.data.nombre)}</dd>
                </div>
                <div>
                  <dt>Origen</dt>
                  <dd>{formatSource(detailQuery.data.source)}</dd>
                </div>
                <div>
                  <dt>Codigo / referencia</dt>
                  <dd>{formatText(detailQuery.data.codigo || detailQuery.data.id)}</dd>
                </div>
                <div>
                  <dt>Fabricante / proveedor</dt>
                  <dd>{formatText(detailQuery.data.fabricante_id || detailQuery.data.proveedor_id)}</dd>
                </div>
                <div>
                  <dt>Familia / subfamilia</dt>
                  <dd>{formatText(detailQuery.data.familia_id || detailQuery.data.subfamilia_id)}</dd>
                </div>
                <div>
                  <dt>Unidad</dt>
                  <dd>{formatText(detailQuery.data.unidad)}</dd>
                </div>
                <div>
                  <dt>Activo</dt>
                  <dd>{detailQuery.data.activo ? 'Si' : 'No'}</dd>
                </div>
                <div>
                  <dt>Precio</dt>
                  <dd>{detailQuery.data.precio > 0 ? formatNumber(detailQuery.data.precio) : '-'}</dd>
                </div>
              </dl>
            )}
          </aside>
        </div>
      )}
    </section>
  )
}
