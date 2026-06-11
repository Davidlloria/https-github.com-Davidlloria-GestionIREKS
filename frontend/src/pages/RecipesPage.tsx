import { useCallback, useMemo, useState } from 'react'
import { getRecipeDetail, listRecipeItems, listRecipes } from '../api/recipes'
import { QueryState } from '../components/QueryState'
import { StatCard } from '../components/StatCard'
import { useAsyncResource } from '../features/useAsyncResource'
import type { RecipeDetail, RecipeItem } from '../types/api'

interface RecipeDetailPayload {
  detail: RecipeDetail | null
  items: RecipeItem[]
}

const EMPTY_DETAIL: RecipeDetailPayload = {
  detail: null,
  items: [],
}

const PAGE_SIZE = 25

function safeNumber(value: unknown) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : 0
}

export function RecipesPage() {
  const [search, setSearch] = useState('')
  const [pageIndex, setPageIndex] = useState(0)
  const [selectedCandidateId, setSelectedCandidateId] = useState<number | null>(null)

  const offset = pageIndex * PAGE_SIZE
  const recipesQuery = useAsyncResource(
    () => listRecipes(search, PAGE_SIZE, offset),
    { items: [], total: 0, limit: PAGE_SIZE, offset: 0 },
    [search, offset],
  )
  const recipeRows = recipesQuery.data.items

  const selectedRecipeId = useMemo(() => {
    if (!recipeRows.length) {
      return null
    }
    if (selectedCandidateId && recipeRows.some((row) => row.id === selectedCandidateId)) {
      return selectedCandidateId
    }
    return recipeRows[0].id
  }, [recipeRows, selectedCandidateId])

  const loadSelectedRecipe = useCallback(() => {
    if (!selectedRecipeId) {
      return Promise.resolve(EMPTY_DETAIL)
    }
    return Promise.all([getRecipeDetail(selectedRecipeId), listRecipeItems(selectedRecipeId)]).then(
      ([detail, items]) => ({ detail, items: items.items }),
    )
  }, [selectedRecipeId])

  const detailQuery = useAsyncResource(loadSelectedRecipe, EMPTY_DETAIL, [loadSelectedRecipe, selectedRecipeId])

  const totals = useMemo(() => {
    const baseCount = recipeRows.filter((row) => row.es_base).length
    const publishedCount = recipeRows.filter((row) => (row.estado || '').toLowerCase() === 'publicada').length
    const withProcess = recipeRows.filter((row) => !!row.proceso).length
    return {
      total: recipesQuery.data.total,
      baseCount,
      publishedCount,
      withProcess,
    }
  }, [recipeRows, recipesQuery.data.total])

  const hasPreviousPage = pageIndex > 0
  const hasNextPage = offset + recipeRows.length < recipesQuery.data.total
  const currentPage = pageIndex + 1
  const totalPages = Math.max(1, Math.ceil(recipesQuery.data.total / PAGE_SIZE))

  return (
    <section className="page-grid">
      <header className="module-header">
        <div className="module-header-copy">
          <p className="module-kicker">Modulo read-only</p>
          <h2>Recetas</h2>
          <p className="module-description">
            Consulta de recetas con detalle lateral, cabecera separada y composicion de lineas para revisar la formula sin editar.
          </p>
        </div>
        <div className="module-header-meta">
          <span className="surface-chip">Pagina {currentPage} de {totalPages}</span>
          <span className="surface-chip">Vista sin mutaciones</span>
        </div>
      </header>

      <section className="panel-section">
        <div className="section-heading">
          <div>
            <h3>Filtros</h3>
            <p>Busca por nombre, codigo o proceso y usa la paginacion antes de abrir detalle.</p>
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
            placeholder="Buscar receta por nombre, codigo o proceso"
          />
        </div>
      </section>

      <div className="cards">
        <StatCard label="Total recetas" value={totals.total} />
        <StatCard label="Bases" value={totals.baseCount} />
        <StatCard label="Publicadas" value={totals.publishedCount} />
        <StatCard label="Con proceso" value={totals.withProcess} />
      </div>

      <QueryState
        loading={recipesQuery.loading}
        error={recipesQuery.error}
        empty={!recipeRows.length}
        emptyMessage="No hay recetas para los filtros actuales."
      />

      {!!recipeRows.length && (
        <div className="orders-workspace">
          <section className="orders-list-panel">
            <div className="panel-section">
              <div className="section-heading">
                <div>
                  <h3>Listado de recetas</h3>
                  <p>Selecciona una fila para cargar la cabecera y las lineas en el panel lateral.</p>
                </div>
                <span className="surface-chip">Mostrando {recipeRows.length} de {recipesQuery.data.total}</span>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Codigo</th>
                      <th>Nombre</th>
                      <th>Version</th>
                      <th>Estado</th>
                      <th>Base</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recipeRows.map((recipe) => (
                      <tr
                        key={recipe.id ?? recipe.codigo_receta}
                        className={recipe.id === selectedRecipeId ? 'row-selected' : ''}
                        onClick={() => setSelectedCandidateId(recipe.id)}
                      >
                        <td>{recipe.codigo_receta || recipe.id}</td>
                        <td>{recipe.nombre || '-'}</td>
                        <td>{recipe.version || '-'}</td>
                        <td>{recipe.estado || '-'}</td>
                        <td>{recipe.es_base ? 'Si' : 'No'}</td>
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
                <h3>Detalle de receta</h3>
                <p>Cabecera de receta y composicion separadas en secciones claras.</p>
              </div>
            </div>
            {!selectedRecipeId && <div className="state">Selecciona una receta para ver el detalle.</div>}
            {!!selectedRecipeId && (
              <>
                <QueryState
                  loading={detailQuery.loading}
                  error={detailQuery.error}
                  empty={!detailQuery.data.detail}
                  emptyMessage="No se encontro detalle para la receta seleccionada."
                />

                {!!detailQuery.data.detail && (
                  <>
                    <dl className="detail-list">
                      <div>
                        <dt>Receta ID</dt>
                        <dd>{detailQuery.data.detail.id ?? '-'}</dd>
                      </div>
                      <div>
                        <dt>Nombre</dt>
                        <dd>{detailQuery.data.detail.nombre || '-'}</dd>
                      </div>
                      <div>
                        <dt>Codigo</dt>
                        <dd>{detailQuery.data.detail.codigo_receta || '-'}</dd>
                      </div>
                      <div>
                        <dt>Cliente</dt>
                        <dd>{detailQuery.data.detail.cliente_id || '-'}</dd>
                      </div>
                      <div>
                        <dt>Proceso</dt>
                        <dd>{detailQuery.data.detail.proceso || '-'}</dd>
                      </div>
                      <div>
                        <dt>Estado</dt>
                        <dd>{detailQuery.data.detail.estado || '-'}</dd>
                      </div>
                    </dl>

                    <div className="related-block">
                      <div className="section-heading section-heading-compact">
                        <div>
                          <h3>Cabecera de receta</h3>
                          <p>Resumen de datos principales de la receta activa.</p>
                        </div>
                      </div>
                    </div>

                    <div className="related-block">
                      <div className="section-heading section-heading-compact">
                        <div>
                          <h3>Lineas de receta</h3>
                          <p>Composicion read-only de la formula seleccionada.</p>
                        </div>
                      </div>
                      {!detailQuery.data.items.length && <div className="state">Sin lineas.</div>}
                      {!!detailQuery.data.items.length && (
                        <div className="table-wrap">
                          <table>
                            <thead>
                              <tr>
                                <th>Orden</th>
                                <th>Ingrediente</th>
                                <th>Codigo</th>
                                <th>Cantidad base</th>
                                <th>Cantidad calc.</th>
                              </tr>
                            </thead>
                            <tbody>
                              {detailQuery.data.items.map((item) => (
                                <tr key={item.id ?? `${item.orden}-${item.codigo_ingrediente}`}>
                                  <td>{item.orden}</td>
                                  <td>{item.nombre_mostrado || '-'}</td>
                                  <td>{item.codigo_ingrediente || '-'}</td>
                                  <td>{safeNumber(item.cantidad_base_g).toFixed(2)}</td>
                                  <td>{safeNumber(item.cantidad_calculada_g).toFixed(2)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  </>
                )}
              </>
            )}
          </aside>
        </div>
      )}
    </section>
  )
}
