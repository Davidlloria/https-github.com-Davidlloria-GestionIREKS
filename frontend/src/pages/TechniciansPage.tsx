import { useCallback, useMemo, useState } from 'react'
import { getTechnicianDetail, listTechnicians } from '../api/technicians'
import { QueryState } from '../components/QueryState'
import { useAsyncResource } from '../features/useAsyncResource'
import type { TechnicianListItem } from '../types/api'

const PAGE_SIZE = 50

function fullName(row: TechnicianListItem) {
  return `${row.nombre || ''} ${row.apellidos || ''}`.trim()
}

function valueOrDash(value: string | number | null | undefined) {
  if (value === null || value === undefined) {
    return '-'
  }

  const text = String(value).trim()
  return text || '-'
}

export function TechniciansPage() {
  const [search, setSearch] = useState('')
  const [pageIndex, setPageIndex] = useState(0)
  const [selectedCandidateId, setSelectedCandidateId] = useState('')

  const offset = pageIndex * PAGE_SIZE
  const techniciansQuery = useAsyncResource(
    () => listTechnicians(search, PAGE_SIZE, offset),
    { items: [], total: 0, limit: PAGE_SIZE, offset: 0 },
    [search, offset],
  )
  const rows = techniciansQuery.data.items

  const selectedTechnicianId = useMemo(() => {
    if (!rows.length) {
      return ''
    }

    if (selectedCandidateId && rows.some((row) => row.tecnico_id === selectedCandidateId)) {
      return selectedCandidateId
    }

    return rows[0].tecnico_id
  }, [rows, selectedCandidateId])

  const loadSelectedDetail = useCallback(() => {
    if (!selectedTechnicianId) {
      return Promise.resolve(null)
    }

    return getTechnicianDetail(selectedTechnicianId)
  }, [selectedTechnicianId])

  const detailQuery = useAsyncResource(loadSelectedDetail, null, [loadSelectedDetail, selectedTechnicianId])
  const detailTechnician = detailQuery.data

  const hasPreviousPage = pageIndex > 0
  const hasNextPage = offset + rows.length < techniciansQuery.data.total
  const currentPage = pageIndex + 1
  const totalPages = Math.max(1, Math.ceil(techniciansQuery.data.total / PAGE_SIZE))

  return (
    <section className="technicians-saas-page">
      <div className="technicians-saas-workspace">
        <aside className="technicians-list-panel">
          <div className="technicians-list-head">
            <div className="technicians-list-head-copy">
              <p className="technicians-list-kicker">Tecnicos</p>
              <h2>Tecnicos</h2>
              <p>Listado read-only</p>
            </div>
            <span className="surface-chip">{rows.length} visibles</span>
          </div>

          <div className="technicians-list-filters">
            <input
              className="input technicians-search"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value)
                setPageIndex(0)
                setSelectedCandidateId('')
              }}
              placeholder="Buscar por nombre, apellido, movil, interno o email"
            />
          </div>

          <div className="technicians-list-meta">
            <span className="surface-chip">
              Pagina {currentPage} de {totalPages}
            </span>
            <div className="technicians-pager-actions" aria-label="Paginacion de tecnicos">
              <button
                type="button"
                className="technicians-pager-btn"
                disabled={!hasPreviousPage}
                onClick={() => setPageIndex((prev) => Math.max(0, prev - 1))}
              >
                Anterior
              </button>
              <button
                type="button"
                className="technicians-pager-btn"
                disabled={!hasNextPage}
                onClick={() => setPageIndex((prev) => prev + 1)}
              >
                Siguiente
              </button>
            </div>
          </div>

          <div className="technicians-list-scroll">
            <QueryState
              loading={techniciansQuery.loading}
              error={techniciansQuery.error}
              empty={!rows.length}
              emptyMessage="No hay tecnicos para los filtros actuales."
            />

            {!!rows.length && (
              <div className="technicians-list-grid">
                <div className="technicians-list-header">
                  <div className="technicians-list-cell">Cod.</div>
                  <div className="technicians-list-cell">Nombre</div>
                  <div className="technicians-list-cell">Movil</div>
                  <div className="technicians-list-cell">Interno</div>
                  <div className="technicians-list-cell">Email</div>
                </div>

                <div className="technicians-list-body">
                  {rows.map((row) => {
                    const isSelected = row.tecnico_id === selectedTechnicianId

                    return (
                      <button
                        key={row.tecnico_id}
                        type="button"
                        className={`technicians-list-row ${isSelected ? 'is-selected' : ''}`}
                        onClick={() => setSelectedCandidateId(row.tecnico_id)}
                      >
                        <span className="technicians-list-cell">{valueOrDash(row.tecnico_codigo)}</span>
                        <span className="technicians-list-cell technicians-list-cell-name">{fullName(row) || '(sin nombre)'}</span>
                        <span className="technicians-list-cell">{valueOrDash(row.movil)}</span>
                        <span className="technicians-list-cell">{valueOrDash(row.interno)}</span>
                        <span className="technicians-list-cell">{valueOrDash(row.email)}</span>
                      </button>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        </aside>

        <section className="technicians-detail-panel">
          <div className="technicians-detail-card">
            <div className="technicians-section-head">
              <div>
                <p className="technicians-detail-kicker">Modulo read-only</p>
                <h3>Detalle de tecnico</h3>
                <p>Ficha compacta sin mutaciones.</p>
              </div>
              {!!detailTechnician && <span className="surface-chip">Cod. {valueOrDash(detailTechnician.tecnico_codigo)}</span>}
            </div>

            {!selectedTechnicianId && <div className="state">Selecciona un tecnico para ver el detalle.</div>}

            {!!selectedTechnicianId && (
              <QueryState
                loading={detailQuery.loading}
                error={detailQuery.error}
                empty={!detailQuery.data}
                emptyMessage="No se encontro detalle para el tecnico seleccionado."
              />
            )}

            {!!detailTechnician && (
              <div className="technicians-field-grid">
                <div className="technicians-field-row technicians-field-row-top">
                  <label className="technicians-field-code">
                    <span>Cod.</span>
                    <input className="input technicians-field" readOnly value={valueOrDash(detailTechnician.tecnico_codigo)} />
                  </label>
                  <label className="technicians-field-name">
                    <span>Nombre completo</span>
                    <input className="input technicians-field" readOnly value={fullName(detailTechnician) || '-'} />
                  </label>
                  <label className="technicians-field-mobile">
                    <span>Movil</span>
                    <input className="input technicians-field" readOnly value={valueOrDash(detailTechnician.movil)} />
                  </label>
                </div>

                <div className="technicians-field-row technicians-field-row-mid">
                  <label className="technicians-field-internal">
                    <span>Interno</span>
                    <input className="input technicians-field" readOnly value={valueOrDash(detailTechnician.interno)} />
                  </label>
                  <label className="technicians-field-email">
                    <span>Email</span>
                    <input className="input technicians-field" readOnly value={valueOrDash(detailTechnician.email)} />
                  </label>
                  <label className="technicians-field-created">
                    <span>Creado</span>
                    <input className="input technicians-field" readOnly value={valueOrDash(detailTechnician.created_at)} />
                  </label>
                </div>

                <div className="technicians-field-row technicians-field-row-bottom">
                  <label className="technicians-field-updated">
                    <span>Actualizado</span>
                    <input className="input technicians-field" readOnly value={valueOrDash(detailTechnician.updated_at)} />
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
