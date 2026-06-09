import { useMemo, useState } from 'react'
import { getIngredientDetail, listIngredients } from '../api/ingredients'
import { QueryState } from '../components/QueryState'
import { StatCard } from '../components/StatCard'
import { useAsyncResource } from '../features/useAsyncResource'
import type { IngredientDetail, IngredientListItem, IngredientListResponse } from '../types/api'

const PAGE_SIZE = 25

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

export function IngredientsPage() {
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

  const selectedIngredientId = useMemo(() => {
    if (!ingredientRows.length) {
      return ''
    }
    if (selectedCandidateId && ingredientRows.some((row) => row.id === selectedCandidateId)) {
      return selectedCandidateId
    }
    return ingredientRows[0].id
  }, [ingredientRows, selectedCandidateId])

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

  const totals = useMemo(() => {
    const activeCount = ingredientRows.filter((row) => row.activo).length
    const stdCount = ingredientRows.filter((row) => row.source === 'std').length
    const pricedCount = ingredientRows.filter((row) => Number.isFinite(row.precio) && row.precio > 0).length
    return {
      total: ingredientsQuery.data.total,
      activeCount,
      stdCount,
      pricedCount,
    }
  }, [ingredientRows, ingredientsQuery.data.total])

  const hasPreviousPage = pageIndex > 0
  const hasNextPage = offset + ingredientRows.length < ingredientsQuery.data.total
  const currentPage = pageIndex + 1
  const totalPages = Math.max(1, Math.ceil(ingredientsQuery.data.total / PAGE_SIZE))

  return (
    <section className="page-grid">
      <div className="toolbar">
        <input
          className="input"
          value={search}
          onChange={(event) => {
            setSearch(event.target.value)
            setPageIndex(0)
          }}
          placeholder="Buscar ingrediente por nombre, codigo o referencia"
        />
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
        <span className="state">
          Pagina {currentPage} de {totalPages}
        </span>
      </div>

      <div className="cards">
        <StatCard label="Total ingredientes" value={totals.total} />
        <StatCard label="Activos" value={totals.activeCount} />
        <StatCard label="STD" value={totals.stdCount} />
        <StatCard label="Con precio" value={totals.pricedCount} />
      </div>

      <QueryState
        loading={ingredientsQuery.loading}
        error={ingredientsQuery.error}
        empty={!ingredientRows.length}
        emptyMessage="No hay ingredientes para los filtros actuales."
      />

      {!!ingredientRows.length && (
        <div className="split-panel">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Codigo</th>
                  <th>Nombre</th>
                  <th>Origen</th>
                  <th>Activo</th>
                </tr>
              </thead>
              <tbody>
                {ingredientRows.map((row) => (
                  <tr
                    key={row.id}
                    className={row.id === selectedIngredientId ? 'row-selected' : ''}
                    onClick={() => setSelectedCandidateId(row.id)}
                  >
                    <td>{row.id}</td>
                    <td>{row.codigo || '-'}</td>
                    <td>{row.nombre || '-'}</td>
                    <td>{formatText(row.source)}</td>
                    <td>{row.activo ? 'Si' : 'No'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <aside className="detail-panel">
            <QueryState
              loading={detailQuery.loading}
              error={detailQuery.error}
              empty={!detailQuery.data}
              emptyMessage="Selecciona un ingrediente para ver el detalle."
            />

            {!!detailQuery.data && (
              <>
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
                    <dd>{formatText(detailQuery.data.source)}</dd>
                  </div>
                  <div>
                    <dt>Fabricante / proveedor</dt>
                    <dd>{formatText(detailQuery.data.fabricante_id || detailQuery.data.proveedor_id)}</dd>
                  </div>
                  <div>
                    <dt>Familia / subfamilia</dt>
                    <dd>
                      {formatText(detailQuery.data.familia_id || detailQuery.data.subfamilia_id)}
                    </dd>
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
              </>
            )}
          </aside>
        </div>
      )}
    </section>
  )
}
