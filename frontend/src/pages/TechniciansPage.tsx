import { useCallback, useMemo, useState } from 'react'
import { getTechnicianDetail, listTechnicians } from '../api/technicians'
import { QueryState } from '../components/QueryState'
import { StatCard } from '../components/StatCard'
import { useAsyncResource } from '../features/useAsyncResource'
import type { TechnicianListItem } from '../types/api'

const PAGE_SIZE = 50

function fullName(row: TechnicianListItem) {
  return `${row.nombre || ''} ${row.apellidos || ''}`.trim()
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

  const totals = useMemo(() => {
    const withEmail = rows.filter((row) => !!row.email).length
    const withMobile = rows.filter((row) => !!row.movil).length
    return {
      total: techniciansQuery.data.total,
      withEmail,
      withMobile,
    }
  }, [rows, techniciansQuery.data.total])

  const hasPreviousPage = pageIndex > 0
  const hasNextPage = offset + rows.length < techniciansQuery.data.total
  const currentPage = pageIndex + 1
  const totalPages = Math.max(1, Math.ceil(techniciansQuery.data.total / PAGE_SIZE))

  return (
    <section className="page-grid">
      <header className="module-header">
        <div className="module-header-copy">
          <p className="module-kicker">Modulo read-only</p>
          <h2>Tecnicos</h2>
          <p className="module-description">
            Consulta de tecnicos con detalle lateral, pensada para revisar codigo, contacto y trazabilidad sin editar datos.
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
            <p>Busca por nombre, apellido, movil, interno o email y navega por pagina.</p>
          </div>
          <div className="toolbar pager-toolbar">
            <button type="button" className="action-btn" disabled={!hasPreviousPage} onClick={() => setPageIndex((prev) => Math.max(0, prev - 1))}>
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
            placeholder="Buscar por nombre, apellido, movil, interno o email"
          />
        </div>
      </section>

      <div className="cards">
        <StatCard label="Total tecnicos" value={totals.total} />
        <StatCard label="Con email" value={totals.withEmail} />
        <StatCard label="Con movil" value={totals.withMobile} />
        <StatCard label="Pagina" value={currentPage} />
      </div>

      <QueryState
        loading={techniciansQuery.loading}
        error={techniciansQuery.error}
        empty={!rows.length}
        emptyMessage="No hay tecnicos para los filtros actuales."
      />

      {!!rows.length && (
        <div className="orders-workspace">
          <section className="orders-list-panel">
            <div className="panel-section">
              <div className="section-heading">
                <div>
                  <h3>Listado de tecnicos</h3>
                  <p>Selecciona una fila para cargar el detalle lateral.</p>
                </div>
                <span className="surface-chip">Mostrando {rows.length} de {techniciansQuery.data.total}</span>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Codigo</th>
                      <th>Nombre</th>
                      <th>Movil</th>
                      <th>Interno</th>
                      <th>Email</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => (
                      <tr
                        key={row.tecnico_id}
                        className={row.tecnico_id === selectedTechnicianId ? 'row-selected' : ''}
                        onClick={() => setSelectedCandidateId(row.tecnico_id)}
                      >
                        <td>{row.tecnico_codigo || '-'}</td>
                        <td>{fullName(row) || '(sin nombre)'}</td>
                        <td>{row.movil || '-'}</td>
                        <td>{row.interno || '-'}</td>
                        <td>{row.email || '-'}</td>
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
                <h3>Detalle de tecnico</h3>
                <p>Datos de contacto y trazabilidad del registro seleccionado.</p>
              </div>
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

            {!!detailQuery.data && (
              <dl className="detail-list">
                <div>
                  <dt>Nombre completo</dt>
                  <dd>{fullName(detailQuery.data) || '-'}</dd>
                </div>
                <div>
                  <dt>Tecnico ID</dt>
                  <dd>{detailQuery.data.tecnico_id}</dd>
                </div>
                <div>
                  <dt>Codigo</dt>
                  <dd>{detailQuery.data.tecnico_codigo}</dd>
                </div>
                <div>
                  <dt>Movil</dt>
                  <dd>{detailQuery.data.movil || '-'}</dd>
                </div>
                <div>
                  <dt>Interno</dt>
                  <dd>{detailQuery.data.interno || '-'}</dd>
                </div>
                <div>
                  <dt>Email</dt>
                  <dd>{detailQuery.data.email || '-'}</dd>
                </div>
                <div>
                  <dt>Creado</dt>
                  <dd>{detailQuery.data.created_at || '-'}</dd>
                </div>
                <div>
                  <dt>Actualizado</dt>
                  <dd>{detailQuery.data.updated_at || '-'}</dd>
                </div>
              </dl>
            )}
          </aside>
        </div>
      )}
    </section>
  )
}
