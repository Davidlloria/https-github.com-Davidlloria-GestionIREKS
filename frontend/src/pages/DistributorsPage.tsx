import { useCallback, useMemo, useState } from 'react'
import { getDistributorDetail, listDistributors } from '../api/distributors'
import { QueryState } from '../components/QueryState'
import { useAsyncResource } from '../features/useAsyncResource'
import type { DistributorListItem } from '../types/api'

const PAGE_SIZE = 50

function distributorLabel(row: DistributorListItem) {
  return row.distribuidor_nombre_comercial || row.distribuidor_razon_social || row.distribuidor_id
}

function valueOrDash(value: string | number | null | undefined) {
  if (value === null || value === undefined) {
    return '-'
  }

  const text = String(value).trim()
  return text || '-'
}

export function DistributorsPage() {
  const [search, setSearch] = useState('')
  const [pageIndex, setPageIndex] = useState(0)
  const [selectedCandidateId, setSelectedCandidateId] = useState('')

  const offset = pageIndex * PAGE_SIZE
  const distributorsQuery = useAsyncResource(
    () => listDistributors(search, PAGE_SIZE, offset),
    { items: [], total: 0, limit: PAGE_SIZE, offset: 0 },
    [search, offset],
  )
  const rows = distributorsQuery.data.items

  const selectedDistributorId = useMemo(() => {
    if (!rows.length) {
      return ''
    }

    if (selectedCandidateId && rows.some((row) => row.distribuidor_id === selectedCandidateId)) {
      return selectedCandidateId
    }

    return rows[0].distribuidor_id
  }, [rows, selectedCandidateId])

  const loadSelectedDetail = useCallback(() => {
    if (!selectedDistributorId) {
      return Promise.resolve(null)
    }

    return getDistributorDetail(selectedDistributorId)
  }, [selectedDistributorId])

  const detailQuery = useAsyncResource(loadSelectedDetail, null, [loadSelectedDetail, selectedDistributorId])
  const detailDistributor = detailQuery.data

  const hasPreviousPage = pageIndex > 0
  const hasNextPage = offset + rows.length < distributorsQuery.data.total
  const currentPage = pageIndex + 1
  const totalPages = Math.max(1, Math.ceil(distributorsQuery.data.total / PAGE_SIZE))

  return (
    <section className="distributors-saas-page">
      <div className="distributors-saas-workspace">
        <aside className="distributors-list-panel">
          <div className="distributors-list-head">
            <div className="distributors-list-head-copy">
              <p className="distributors-list-kicker">Distribuidores</p>
              <h2>Distribuidores</h2>
              <p>Listado read-only</p>
            </div>
            <span className="surface-chip">{rows.length} visibles</span>
          </div>

          <div className="distributors-list-filters">
            <input
              className="input distributors-search"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value)
                setPageIndex(0)
                setSelectedCandidateId('')
              }}
              placeholder="Buscar por codigo, nombre, razon social, CIF o contacto"
            />
          </div>

          <div className="distributors-list-meta">
            <span className="surface-chip">
              Pagina {currentPage} de {totalPages}
            </span>
            <div className="distributors-pager-actions" aria-label="Paginacion de distribuidores">
              <button
                type="button"
                className="distributors-pager-btn"
                disabled={!hasPreviousPage}
                onClick={() => setPageIndex((prev) => Math.max(0, prev - 1))}
              >
                Anterior
              </button>
              <button
                type="button"
                className="distributors-pager-btn"
                disabled={!hasNextPage}
                onClick={() => setPageIndex((prev) => prev + 1)}
              >
                Siguiente
              </button>
            </div>
          </div>

          <div className="distributors-list-scroll">
            <QueryState
              loading={distributorsQuery.loading}
              error={distributorsQuery.error}
              empty={!rows.length}
              emptyMessage="No hay distribuidores para los filtros actuales."
            />

            {!!rows.length && (
              <div className="distributors-list-grid">
                <div className="distributors-list-header">
                  <div className="distributors-list-cell">Cod.</div>
                  <div className="distributors-list-cell">Nombre</div>
                  <div className="distributors-list-cell">CIF</div>
                  <div className="distributors-list-cell">Telefono</div>
                  <div className="distributors-list-cell">Contacto</div>
                </div>

                <div className="distributors-list-body">
                  {rows.map((row) => {
                    const isSelected = row.distribuidor_id === selectedDistributorId

                    return (
                      <button
                        key={row.distribuidor_id}
                        type="button"
                        className={`distributors-list-row ${isSelected ? 'is-selected' : ''}`}
                        onClick={() => setSelectedCandidateId(row.distribuidor_id)}
                      >
                        <span className="distributors-list-cell">{valueOrDash(row.distribuidor_codigo)}</span>
                        <span className="distributors-list-cell distributors-list-cell-name">{distributorLabel(row)}</span>
                        <span className="distributors-list-cell">{valueOrDash(row.distribuidor_cif)}</span>
                        <span className="distributors-list-cell">{valueOrDash(row.distribuidor_telefono)}</span>
                        <span className="distributors-list-cell">{valueOrDash(row.distribuidor_contacto)}</span>
                      </button>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        </aside>

        <section className="distributors-detail-panel">
          <div className="distributors-detail-card">
            <div className="distributors-section-head">
              <div>
                <p className="distributors-detail-kicker">Modulo read-only</p>
                <h3>Detalle de distribuidor</h3>
                <p>Ficha compacta sin mutaciones.</p>
              </div>
              {!!detailDistributor && <span className="surface-chip">Cod. {valueOrDash(detailDistributor.distribuidor_codigo)}</span>}
            </div>

            {!selectedDistributorId && <div className="state">Selecciona un distribuidor para ver el detalle.</div>}

            {!!selectedDistributorId && (
              <QueryState
                loading={detailQuery.loading}
                error={detailQuery.error}
                empty={!detailQuery.data}
                emptyMessage="No se encontro detalle para el distribuidor seleccionado."
              />
            )}

            {!!detailDistributor && (
              <div className="distributors-field-grid">
                <div className="distributors-field-row distributors-field-row-top">
                  <label className="distributors-field-code">
                    <span>Cod.</span>
                    <input className="input distributors-field" readOnly value={valueOrDash(detailDistributor.distribuidor_codigo)} />
                  </label>
                  <label className="distributors-field-name">
                    <span>Nombre comercial</span>
                    <input className="input distributors-field" readOnly value={valueOrDash(detailDistributor.distribuidor_nombre_comercial)} />
                  </label>
                  <label className="distributors-field-cif">
                    <span>CIF</span>
                    <input className="input distributors-field" readOnly value={valueOrDash(detailDistributor.distribuidor_cif)} />
                  </label>
                </div>

                <div className="distributors-field-row distributors-field-row-mid">
                  <label className="distributors-field-social">
                    <span>Razon social</span>
                    <input className="input distributors-field" readOnly value={valueOrDash(detailDistributor.distribuidor_razon_social)} />
                  </label>
                  <label className="distributors-field-phone">
                    <span>Telefono</span>
                    <input className="input distributors-field" readOnly value={valueOrDash(detailDistributor.distribuidor_telefono)} />
                  </label>
                  <label className="distributors-field-contact">
                    <span>Contacto</span>
                    <input className="input distributors-field" readOnly value={valueOrDash(detailDistributor.distribuidor_contacto)} />
                  </label>
                </div>
              </div>
            )}
          </div>
        </section>
      </div>
    </section>
  )
}
