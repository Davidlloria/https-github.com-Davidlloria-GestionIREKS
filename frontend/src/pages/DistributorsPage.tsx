import { useCallback, useMemo, useState } from 'react'
import { getDistributorDetail, listDistributors } from '../api/distributors'
import { QueryState } from '../components/QueryState'
import { StatCard } from '../components/StatCard'
import { useAsyncResource } from '../features/useAsyncResource'
import type { DistributorListItem } from '../types/api'

const PAGE_SIZE = 50

function distributorLabel(row: DistributorListItem) {
  return row.distribuidor_nombre_comercial || row.distribuidor_razon_social || row.distribuidor_id
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

  const totals = useMemo(() => {
    const withContact = rows.filter((row) => !!row.distribuidor_contacto).length
    const withPhone = rows.filter((row) => !!row.distribuidor_telefono).length
    return {
      total: distributorsQuery.data.total,
      withContact,
      withPhone,
    }
  }, [rows, distributorsQuery.data.total])

  const hasPreviousPage = pageIndex > 0
  const hasNextPage = offset + rows.length < distributorsQuery.data.total
  const currentPage = pageIndex + 1
  const totalPages = Math.max(1, Math.ceil(distributorsQuery.data.total / PAGE_SIZE))

  return (
    <section className="page-grid">
      <header className="module-header">
        <div className="module-header-copy">
          <p className="module-kicker">Modulo read-only</p>
          <h2>Distribuidores</h2>
          <p className="module-description">
            Consulta de distribuidores con detalle lateral para revisar codigo, razon social y contacto sin editar datos.
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
            <p>Busca por codigo, nombre, razon social, CIF o contacto y navega por pagina.</p>
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
            placeholder="Buscar por codigo, nombre, razon social, CIF o contacto"
          />
        </div>
      </section>

      <div className="cards">
        <StatCard label="Total distribuidores" value={totals.total} />
        <StatCard label="Con telefono" value={totals.withPhone} />
        <StatCard label="Con contacto" value={totals.withContact} />
        <StatCard label="Pagina" value={currentPage} />
      </div>

      <QueryState
        loading={distributorsQuery.loading}
        error={distributorsQuery.error}
        empty={!rows.length}
        emptyMessage="No hay distribuidores para los filtros actuales."
      />

      {!!rows.length && (
        <div className="orders-workspace">
          <section className="orders-list-panel">
            <div className="panel-section">
              <div className="section-heading">
                <div>
                  <h3>Listado de distribuidores</h3>
                  <p>Selecciona una fila para abrir el detalle lateral.</p>
                </div>
                <span className="surface-chip">Mostrando {rows.length} de {distributorsQuery.data.total}</span>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Codigo</th>
                      <th>Nombre</th>
                      <th>CIF</th>
                      <th>Telefono</th>
                      <th>Contacto</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => (
                      <tr
                        key={row.distribuidor_id}
                        className={row.distribuidor_id === selectedDistributorId ? 'row-selected' : ''}
                        onClick={() => setSelectedCandidateId(row.distribuidor_id)}
                      >
                        <td>{row.distribuidor_codigo || '-'}</td>
                        <td>{distributorLabel(row)}</td>
                        <td>{row.distribuidor_cif || '-'}</td>
                        <td>{row.distribuidor_telefono || '-'}</td>
                        <td>{row.distribuidor_contacto || '-'}</td>
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
                <h3>Detalle de distribuidor</h3>
                <p>Datos principales del registro seleccionado.</p>
              </div>
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

            {!!detailQuery.data && (
              <dl className="detail-list">
                <div>
                  <dt>Nombre comercial</dt>
                  <dd>{detailQuery.data.distribuidor_nombre_comercial || '-'}</dd>
                </div>
                <div>
                  <dt>Razon social</dt>
                  <dd>{detailQuery.data.distribuidor_razon_social || '-'}</dd>
                </div>
                <div>
                  <dt>Distribuidor ID</dt>
                  <dd>{detailQuery.data.distribuidor_id}</dd>
                </div>
                <div>
                  <dt>Codigo</dt>
                  <dd>{detailQuery.data.distribuidor_codigo}</dd>
                </div>
                <div>
                  <dt>CIF</dt>
                  <dd>{detailQuery.data.distribuidor_cif || '-'}</dd>
                </div>
                <div>
                  <dt>Telefono</dt>
                  <dd>{detailQuery.data.distribuidor_telefono || '-'}</dd>
                </div>
                <div>
                  <dt>Contacto</dt>
                  <dd>{detailQuery.data.distribuidor_contacto || '-'}</dd>
                </div>
              </dl>
            )}
          </aside>
        </div>
      )}
    </section>
  )
}
