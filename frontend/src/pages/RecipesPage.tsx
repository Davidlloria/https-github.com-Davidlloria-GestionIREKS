import { useCallback, useMemo, useState } from 'react'
import { getRecipeDetail, listRecipeItems, listRecipes } from '../api/recipes'
import { QueryState } from '../components/QueryState'
import { useAsyncResource } from '../features/useAsyncResource'
import type { RecipeDetail, RecipeItem, RecipeListItem } from '../types/api'

interface RecipeDetailPayload {
  detail: RecipeDetail | null
  items: RecipeItem[]
}

const EMPTY_DETAIL: RecipeDetailPayload = {
  detail: null,
  items: [],
}

const PAGE_SIZE = 25

function valueOrDash(value: string | number | null | undefined) {
  if (value === null || value === undefined) {
    return '-'
  }

  const text = String(value).trim()
  return text || '-'
}

function boolLabel(value: boolean | null | undefined) {
  return value ? 'Si' : 'No'
}

function formatGrams(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '-'
  }

  return Number(value).toFixed(2)
}

function recipeLabel(recipe: RecipeListItem) {
  return recipe.nombre || recipe.codigo_receta || '-'
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
    if (selectedCandidateId !== null && recipeRows.some((row) => row.id === selectedCandidateId)) {
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
  const detailRecipe = detailQuery.data.detail

  const hasPreviousPage = pageIndex > 0
  const hasNextPage = offset + recipeRows.length < recipesQuery.data.total
  const currentPage = pageIndex + 1
  const totalPages = Math.max(1, Math.ceil(recipesQuery.data.total / PAGE_SIZE))

  return (
    <section className="recipes-saas-page">
      <div className="recipes-saas-workspace">
        <aside className="recipes-list-panel">
          <div className="recipes-list-head">
            <div className="recipes-list-head-copy">
              <p className="recipes-list-kicker">Recetas</p>
              <h2>Recetas</h2>
              <p>Listado read-only</p>
            </div>
            <span className="surface-chip">{recipesQuery.loading ? 'Cargando...' : `${recipeRows.length} visibles`}</span>
          </div>

          <div className="recipes-list-filters">
            <input
              className="input recipes-search"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value)
                setPageIndex(0)
                setSelectedCandidateId(null)
              }}
              placeholder="Buscar receta por nombre, codigo o proceso"
            />
          </div>

          <div className="recipes-list-meta">
            <span className="surface-chip">
              Pagina {currentPage} de {totalPages}
            </span>
            <div className="recipes-pager-actions" aria-label="Paginacion de recetas">
              <button
                type="button"
                className="recipes-pager-btn"
                disabled={!hasPreviousPage}
                onClick={() => setPageIndex((prev) => Math.max(0, prev - 1))}
              >
                Anterior
              </button>
              <button
                type="button"
                className="recipes-pager-btn"
                disabled={!hasNextPage}
                onClick={() => setPageIndex((prev) => prev + 1)}
              >
                Siguiente
              </button>
            </div>
          </div>

          <div className="recipes-list-scroll">
            <QueryState
              loading={recipesQuery.loading}
              error={recipesQuery.error}
              empty={!recipeRows.length}
              emptyMessage="No hay recetas para los filtros actuales."
            />

            {!recipesQuery.loading && !recipesQuery.error && !!recipeRows.length && (
              <div className="recipes-list-grid">
                <div className="recipes-list-header">
                  <div className="recipes-list-cell recipes-list-cell-code">Codigo</div>
                  <div className="recipes-list-cell recipes-list-cell-name">Nombre</div>
                  <div className="recipes-list-cell recipes-list-cell-process">Proceso</div>
                </div>

                <div className="recipes-list-body">
                  {recipeRows.map((recipe) => {
                    const isSelected = recipe.id === selectedRecipeId

                    return (
                      <button
                        key={recipe.id ?? recipe.codigo_receta}
                        type="button"
                        className={`recipes-list-row ${isSelected ? 'is-selected' : ''}`}
                        onClick={() => setSelectedCandidateId(recipe.id)}
                      >
                        <span className="recipes-list-cell recipes-list-cell-code">{recipe.codigo_receta || '-'}</span>
                        <span className="recipes-list-cell recipes-list-cell-name">{recipeLabel(recipe)}</span>
                        <span className="recipes-list-cell recipes-list-cell-process">{valueOrDash(recipe.proceso)}</span>
                      </button>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        </aside>

        <section className="recipes-detail-panel">
          <section className="recipes-detail-card">
            <div className="recipes-section-head">
              <div>
                <p className="recipes-detail-kicker">Modulo read-only</p>
                <h3>Detalle de receta</h3>
                <p>Ficha compacta sin mutaciones ni IDs tecnicos destacados.</p>
              </div>
            </div>

            {!selectedRecipeId && <div className="state">Selecciona una receta para ver el detalle.</div>}

            {!!selectedRecipeId && (
              <QueryState
                loading={detailQuery.loading}
                error={detailQuery.error}
                empty={!detailRecipe}
                emptyMessage="No se encontro detalle para la receta seleccionada."
              />
            )}

            {!detailQuery.loading && !detailQuery.error && !!detailRecipe && (
              <div className="recipes-detail-grid">
                <label className="recipes-field recipes-field-wide">
                  <span>Nombre</span>
                  <input className="input recipes-field-input" readOnly value={valueOrDash(detailRecipe.nombre)} />
                </label>

                <label className="recipes-field">
                  <span>Codigo</span>
                  <input className="input recipes-field-input" readOnly value={valueOrDash(detailRecipe.codigo_receta)} />
                </label>

                <label className="recipes-field">
                  <span>Proceso</span>
                  <input className="input recipes-field-input" readOnly value={valueOrDash(detailRecipe.proceso)} />
                </label>

                <label className="recipes-field">
                  <span>Estado</span>
                  <input className="input recipes-field-input" readOnly value={valueOrDash(detailRecipe.estado)} />
                </label>

                <label className="recipes-field">
                  <span>Version</span>
                  <input className="input recipes-field-input" readOnly value={valueOrDash(detailRecipe.version)} />
                </label>

                <label className="recipes-field">
                  <span>Base</span>
                  <input className="input recipes-field-input" readOnly value={boolLabel(detailRecipe.es_base)} />
                </label>

                <label className="recipes-field">
                  <span>Masa final (g)</span>
                  <input className="input recipes-field-input" readOnly value={formatGrams(detailRecipe.masa_final_deseada_g)} />
                </label>

                <label className="recipes-field">
                  <span>Peso pieza (g)</span>
                  <input className="input recipes-field-input" readOnly value={formatGrams(detailRecipe.peso_pieza_g)} />
                </label>

                <label className="recipes-field">
                  <span>No. piezas</span>
                  <input className="input recipes-field-input" readOnly value={valueOrDash(detailRecipe.numero_piezas)} />
                </label>

                <label className="recipes-field recipes-field-wide">
                  <span>Cliente</span>
                  <input className="input recipes-field-input" readOnly value="-" />
                </label>
              </div>
            )}
          </section>

          <section className="recipes-items-panel">
            <div className="recipes-section-head recipes-section-head-compact">
              <div>
                <h3>Lineas de receta</h3>
                <p>Composicion read-only de la formula seleccionada.</p>
              </div>
              <span className="surface-chip">
                {detailQuery.loading || detailQuery.error ? '0 lineas' : `${detailQuery.data.items.length} lineas`}
              </span>
            </div>

            {!selectedRecipeId && <div className="state">Selecciona una receta para ver las lineas.</div>}

            {!!selectedRecipeId && !detailQuery.loading && !detailQuery.error && !detailQuery.data.items.length && (
              <div className="state">Sin lineas registradas.</div>
            )}

            {!detailQuery.loading && !detailQuery.error && !!detailQuery.data.items.length && (
              <div className="recipes-items-scroll">
                <div className="recipes-items-table-wrap">
                  <table className="recipes-items-table">
                    <thead>
                      <tr>
                        <th>Orden</th>
                        <th>Ingrediente</th>
                        <th>Codigo ingrediente</th>
                        <th>Cantidad base (g)</th>
                        <th>Cantidad calculada (g)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detailQuery.data.items.map((item) => (
                        <tr key={item.id ?? `${item.orden}-${item.codigo_ingrediente}`}>
                          <td>{valueOrDash(item.orden)}</td>
                          <td>{valueOrDash(item.nombre_mostrado)}</td>
                          <td>{valueOrDash(item.codigo_ingrediente)}</td>
                          <td>{formatGrams(item.cantidad_base_g)}</td>
                          <td>{formatGrams(item.cantidad_calculada_g)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </section>
        </section>
      </div>
    </section>
  )
}
