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

function formatActive(value: boolean | null | undefined) {
  return value ? 'Activo' : 'Inactivo'
}

function formatListFlag(value: boolean | null | undefined) {
  return value ? 'En lista' : 'Fuera de lista'
}

export function IreksProductsPage() {
  const [search, setSearch] = useState('')
  const [pageIndex, setPageIndex] = useState(0)
  const [selectedCandidateId, setSelectedCandidateId] = useState<number | null>(null)
  const [refreshTick, setRefreshTick] = useState(0)

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

  const hasPreviousPage = pageIndex > 0
  const hasNextPage = offset + rows.length < query.data.total
  const currentPage = pageIndex + 1
  const totalPages = Math.max(1, Math.ceil(query.data.total / PAGE_SIZE))

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
              <h3>Productos IREKS</h3>
              <p>Busca, recorre paginas y abre el detalle del producto seleccionado.</p>
            </div>
            <div className="toolbar pager-toolbar">
              <span className="surface-chip">Pagina {currentPage} de {totalPages}</span>
            </div>
          </div>

          <div className="toolbar ingredients-action-toolbar">
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
              Importar
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

          <div className="toolbar ingredients-search-toolbar">
            <input
              className="input"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value)
                setPageIndex(0)
              }}
              placeholder="Buscar producto IREKS por nombre, referencia o codigo"
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
            emptyMessage={
              query.data.total > 0
                ? 'No hay productos IREKS en la pagina actual. Prueba con otra busqueda o pagina.'
                : 'No hay productos IREKS para los filtros actuales.'
            }
          />

          {!!rows.length && (
            <div className="table-wrap ingredients-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Referencia</th>
                    <th>Descripcion</th>
                    <th>Fabricante</th>
                    <th>Familia</th>
                    <th>Activo</th>
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
                        <td>{formatText(row.fabricante_id)}</td>
                        <td>{formatText(row.articulo_familia_id)}</td>
                        <td>{formatActive(row.articulo_status_activo)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <aside className="panel-section ingredients-detail-panel">
          <div className="section-heading section-heading-compact">
            <div>
              <h3>Detalle de producto IREKS</h3>
              <p>Ficha read-only sin tabs adicionales.</p>
            </div>
          </div>

          <QueryState
            loading={detailQuery.loading}
            error={detailQuery.error}
            empty={!detailQuery.data}
            emptyMessage="Selecciona un producto para ver el detalle read-only."
          />

          {!!detailQuery.data && (
            <dl className="detail-list ingredients-detail-list">
              <div>
                <dt>Referencia</dt>
                <dd>{formatText(detailQuery.data.articulo_referencia || detailQuery.data.articulo_id)}</dd>
              </div>
              <div>
                <dt>Referencia corta</dt>
                <dd>{formatText(detailQuery.data.articulo_referencia_corta)}</dd>
              </div>
              <div>
                <dt>Descripcion</dt>
                <dd>{formatText(detailQuery.data.articulo_descripcion)}</dd>
              </div>
              <div>
                <dt>Fabricante</dt>
                <dd>{formatText(detailQuery.data.fabricante_id)}</dd>
              </div>
              <div>
                <dt>Distribuidor</dt>
                <dd>{formatText(detailQuery.data.distribuidor_id)}</dd>
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
                <dt>Categoria</dt>
                <dd>{formatText(detailQuery.data.categoria)}</dd>
              </div>
              <div>
                <dt>Estado</dt>
                <dd>{formatActive(detailQuery.data.articulo_status_activo)}</dd>
              </div>
              <div>
                <dt>En lista</dt>
                <dd>{formatListFlag(detailQuery.data.articulo_status_en_lista)}</dd>
              </div>
              <div>
                <dt>Envase</dt>
                <dd>{formatText(detailQuery.data.articulo_envase_id)}</dd>
              </div>
              <div>
                <dt>Unidad contenido</dt>
                <dd>{formatText(detailQuery.data.articulo_contenido_unidad)}</dd>
              </div>
              <div>
                <dt>Peso total</dt>
                <dd>{formatNumber(detailQuery.data.articulo_envase_peso_total)}</dd>
              </div>
              <div>
                <dt>Unidad medida</dt>
                <dd>{formatText(detailQuery.data.articulo_envase_unidad_medida)}</dd>
              </div>
            </dl>
          )}
        </aside>
      </div>
    </section>
  )
}
