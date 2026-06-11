import { useCallback, useMemo, useState } from 'react'
import { getContactDetail, listContactCompanies, listContacts } from '../api/contacts'
import { QueryState } from '../components/QueryState'
import { StatCard } from '../components/StatCard'
import { useAsyncResource } from '../features/useAsyncResource'
import type { ContactListItem } from '../types/api'

const PAGE_SIZE = 50

function fullName(row: ContactListItem) {
  return `${row.nombre || ''} ${row.apellidos || ''}`.trim()
}

export function ContactsPage() {
  const [search, setSearch] = useState('')
  const [companyFilter, setCompanyFilter] = useState('')
  const [pageIndex, setPageIndex] = useState(0)
  const [selectedCandidateId, setSelectedCandidateId] = useState('')

  const offset = pageIndex * PAGE_SIZE
  const contactsQuery = useAsyncResource(
    () => listContacts(search, companyFilter, PAGE_SIZE, offset),
    { items: [], total: 0, limit: PAGE_SIZE, offset: 0 },
    [search, companyFilter, offset],
  )
  const companiesQuery = useAsyncResource(() => listContactCompanies(), [], [])
  const contactRows = contactsQuery.data.items

  const selectedContactId = useMemo(() => {
    if (!contactRows.length) {
      return ''
    }
    if (selectedCandidateId && contactRows.some((row) => row.contacto_id === selectedCandidateId)) {
      return selectedCandidateId
    }
    return contactRows[0].contacto_id
  }, [contactRows, selectedCandidateId])

  const loadSelectedDetail = useCallback(() => {
    if (!selectedContactId) {
      return Promise.resolve(null)
    }
    return getContactDetail(selectedContactId)
  }, [selectedContactId])

  const detailQuery = useAsyncResource(loadSelectedDetail, null, [loadSelectedDetail, selectedContactId])

  const totals = useMemo(() => {
    const withEmail = contactRows.filter((row) => !!row.email).length
    const withPhone = contactRows.filter((row) => !!row.telefono).length
    const uniqueCompanies = new Set(contactRows.map((row) => row.cliente_id).filter(Boolean)).size
    return {
      total: contactsQuery.data.total,
      withEmail,
      withPhone,
      uniqueCompanies,
    }
  }, [contactRows, contactsQuery.data.total])

  const hasPreviousPage = pageIndex > 0
  const hasNextPage = offset + contactRows.length < contactsQuery.data.total
  const currentPage = pageIndex + 1
  const totalPages = Math.max(1, Math.ceil(contactsQuery.data.total / PAGE_SIZE))

  return (
    <section className="page-grid">
      <header className="module-header">
        <div className="module-header-copy">
          <p className="module-kicker">Modulo read-only</p>
          <h2>Contactos</h2>
          <p className="module-description">
            Consulta de contactos con filtros por empresa y detalle lateral para revisar datos de contacto y trazabilidad.
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
            <p>Usa el texto libre y el filtro de empresa para acotar el listado.</p>
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
            placeholder="Buscar por nombre, apellido, cargo, email o empresa"
          />
          <select
            className="select"
            value={companyFilter}
            onChange={(event) => {
              setCompanyFilter(event.target.value)
              setPageIndex(0)
            }}
          >
            <option value="">Todas las empresas</option>
            {companiesQuery.data.map((company) => (
              <option key={company.cliente_id} value={company.cliente_id}>
                {company.nombre}
              </option>
            ))}
          </select>
        </div>
      </section>

      <div className="cards">
        <StatCard label="Total contactos" value={totals.total} />
        <StatCard label="Con email" value={totals.withEmail} />
        <StatCard label="Con telefono" value={totals.withPhone} />
        <StatCard label="Empresas con contactos" value={totals.uniqueCompanies} />
      </div>

      <QueryState
        loading={contactsQuery.loading}
        error={contactsQuery.error}
        empty={!contactRows.length}
        emptyMessage="No hay contactos para los filtros actuales."
      />

      {!!contactRows.length && (
        <div className="orders-workspace">
          <section className="orders-list-panel">
            <div className="panel-section">
              <div className="section-heading">
                <div>
                  <h3>Listado de contactos</h3>
                  <p>Selecciona una fila para revisar el detalle lateral del contacto activo.</p>
                </div>
                <span className="surface-chip">Mostrando {contactRows.length} de {contactsQuery.data.total}</span>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Nombre</th>
                      <th>Empresa</th>
                      <th>Cargo</th>
                      <th>Email</th>
                      <th>Telefono</th>
                    </tr>
                  </thead>
                  <tbody>
                    {contactRows.map((row) => (
                      <tr
                        key={row.contacto_id}
                        className={row.contacto_id === selectedContactId ? 'row-selected' : ''}
                        onClick={() => setSelectedCandidateId(row.contacto_id)}
                      >
                        <td>{fullName(row) || '(sin nombre)'}</td>
                        <td>{row.cliente_nombre || '-'}</td>
                        <td>{row.cargo || '-'}</td>
                        <td>{row.email || '-'}</td>
                        <td>{row.telefono || '-'}</td>
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
                <h3>Detalle de contacto</h3>
                <p>Datos de identidad, empresa y trazabilidad del registro seleccionado.</p>
              </div>
            </div>
            {!selectedContactId && <div className="state">Selecciona un contacto para ver el detalle.</div>}
            {!!selectedContactId && (
              <>
                <QueryState
                  loading={detailQuery.loading}
                  error={detailQuery.error}
                  empty={!detailQuery.data}
                  emptyMessage="No se encontro detalle para el contacto seleccionado."
                />

                {!!detailQuery.data && (
                  <dl className="detail-list">
                    <div>
                      <dt>Nombre completo</dt>
                      <dd>{`${detailQuery.data.nombre || ''} ${detailQuery.data.apellidos || ''}`.trim() || '-'}</dd>
                    </div>
                    <div>
                      <dt>Empresa</dt>
                      <dd>{detailQuery.data.cliente_nombre || '-'}</dd>
                    </div>
                    <div>
                      <dt>Cliente ID</dt>
                      <dd>{detailQuery.data.cliente_id || '-'}</dd>
                    </div>
                    <div>
                      <dt>Cargo</dt>
                      <dd>{detailQuery.data.cargo || '-'}</dd>
                    </div>
                    <div>
                      <dt>NIF</dt>
                      <dd>{detailQuery.data.nif || '-'}</dd>
                    </div>
                    <div>
                      <dt>Email</dt>
                      <dd>{detailQuery.data.email || '-'}</dd>
                    </div>
                    <div>
                      <dt>Telefono</dt>
                      <dd>{detailQuery.data.telefono || '-'}</dd>
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
              </>
            )}
          </aside>
        </div>
      )}
    </section>
  )
}
