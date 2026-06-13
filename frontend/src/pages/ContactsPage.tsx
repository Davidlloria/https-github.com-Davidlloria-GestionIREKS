import { useCallback, useMemo, useState } from 'react'
import { getContactDetail, listContactCompanies, listContacts } from '../api/contacts'
import { QueryState } from '../components/QueryState'
import { useAsyncResource } from '../features/useAsyncResource'
import type { ContactListItem } from '../types/api'

const PAGE_SIZE = 50

function fullName(row: ContactListItem) {
  return `${row.nombre || ''} ${row.apellidos || ''}`.trim()
}

function valueOrDash(value: string | number | null | undefined) {
  if (value === null || value === undefined) {
    return '-'
  }

  const text = String(value).trim()
  return text || '-'
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

  const hasPreviousPage = pageIndex > 0
  const hasNextPage = offset + contactRows.length < contactsQuery.data.total
  const currentPage = pageIndex + 1
  const totalPages = Math.max(1, Math.ceil(contactsQuery.data.total / PAGE_SIZE))
  const detailContact = detailQuery.data
  const fullDetailName = detailContact ? fullName(detailContact) : '-'

  return (
    <section className="contacts-saas-page">
      <div className="contacts-saas-workspace">
        <aside className="contacts-list-panel">
          <div className="contacts-list-head">
            <div className="contacts-list-head-copy">
              <p className="contacts-list-kicker">Contactos</p>
              <h2>Contactos</h2>
              <p>Listado read-only</p>
            </div>
            <span className="surface-chip">{contactRows.length} visibles</span>
          </div>

          <div className="contacts-list-filters">
            <input
              className="input contacts-search"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value)
                setPageIndex(0)
                setSelectedCandidateId('')
              }}
              placeholder="Buscar por nombre, apellido, cargo, email o empresa"
            />
            <select
              className="select contacts-company-select"
              value={companyFilter}
              onChange={(event) => {
                setCompanyFilter(event.target.value)
                setPageIndex(0)
                setSelectedCandidateId('')
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

          <div className="contacts-list-meta">
            <span className="surface-chip">
              Pagina {currentPage} de {totalPages}
            </span>
            <div className="contacts-pager-actions" aria-label="Paginacion de contactos">
              <button
                type="button"
                className="contacts-pager-btn"
                disabled={!hasPreviousPage}
                onClick={() => setPageIndex((prev) => Math.max(0, prev - 1))}
              >
                Anterior
              </button>
              <button
                type="button"
                className="contacts-pager-btn"
                disabled={!hasNextPage}
                onClick={() => setPageIndex((prev) => prev + 1)}
              >
                Siguiente
              </button>
            </div>
          </div>

          <div className="contacts-list-scroll">
            <QueryState
              loading={contactsQuery.loading}
              error={contactsQuery.error}
              empty={!contactRows.length}
              emptyMessage="No hay contactos para los filtros actuales."
            />

            {!!contactRows.length && (
              <div className="contacts-list-grid">
                <div className="contacts-list-header">
                  <div className="contacts-list-cell">NOMBRE</div>
                  <div className="contacts-list-cell">EMPRESA</div>
                  <div className="contacts-list-cell">CARGO</div>
                  <div className="contacts-list-cell">TELEFONO / EMAIL</div>
                </div>

                <div className="contacts-list-body">
                  {contactRows.map((row) => {
                    const isSelected = row.contacto_id === selectedContactId

                    return (
                      <button
                        key={row.contacto_id}
                        type="button"
                        className={`contacts-list-row ${isSelected ? 'is-selected' : ''}`}
                        onClick={() => setSelectedCandidateId(row.contacto_id)}
                      >
                        <span className="contacts-list-cell contacts-list-cell-name">{fullName(row) || '(sin nombre)'}</span>
                        <span className="contacts-list-cell">{valueOrDash(row.cliente_nombre)}</span>
                        <span className="contacts-list-cell">{valueOrDash(row.cargo)}</span>
                        <span className="contacts-list-cell">{valueOrDash(row.telefono || row.email)}</span>
                      </button>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        </aside>

        <section className="contacts-detail-panel">
          <div className="contacts-detail-actions">
            <button type="button" className="customers-action-btn customers-action-btn-primary" disabled>
              + Nuevo
            </button>
            <button type="button" className="customers-action-btn customers-action-btn-outline" disabled>
              Editar
            </button>
            <button type="button" className="customers-action-btn customers-action-btn-danger" disabled>
              Eliminar
            </button>
            <button type="button" className="customers-action-btn customers-action-btn-ghost" disabled>
              Refrescar
            </button>
          </div>

          <div className="contacts-detail-body">
            <section className="contacts-detail-card">
              <div className="contacts-section-head">
                <div>
                  <p className="contacts-detail-kicker">Modulo read-only</p>
                  <h3>Detalle de contacto</h3>
                  <p>Ficha compacta sin mutaciones.</p>
                </div>
                {!!detailContact && <span className="surface-chip">Cod. {valueOrDash(detailContact.contacto_codigo)}</span>}
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

                  {!!detailContact && (
                    <div className="contacts-field-grid">
                      <div className="contacts-field-row contacts-field-row-top">
                        <label className="contacts-field-code">
                          <span>Cod.</span>
                          <input className="input contacts-field" readOnly value={valueOrDash(detailContact.contacto_codigo)} />
                        </label>
                        <label className="contacts-field-name">
                          <span>Nombre</span>
                          <input className="input contacts-field" readOnly value={fullDetailName} />
                        </label>
                        <label className="contacts-field-company">
                          <span>Empresa</span>
                          <input className="input contacts-field" readOnly value={valueOrDash(detailContact.cliente_nombre)} />
                        </label>
                      </div>

                      <div className="contacts-field-row contacts-field-row-mid">
                        <label className="contacts-field-role">
                          <span>Cargo</span>
                          <input className="input contacts-field" readOnly value={valueOrDash(detailContact.cargo)} />
                        </label>
                        <label className="contacts-field-email">
                          <span>Email</span>
                          <input className="input contacts-field" readOnly value={valueOrDash(detailContact.email)} />
                        </label>
                        <label className="contacts-field-phone">
                          <span>Telefono</span>
                          <input className="input contacts-field" readOnly value={valueOrDash(detailContact.telefono)} />
                        </label>
                      </div>

                      <div className="contacts-field-row contacts-field-row-bottom">
                        <label className="contacts-field-nif">
                          <span>NIF</span>
                          <input className="input contacts-field" readOnly value={valueOrDash(detailContact.nif)} />
                        </label>
                        <label className="contacts-field-created">
                          <span>Creado</span>
                          <input className="input contacts-field" readOnly value={valueOrDash(detailContact.created_at)} />
                        </label>
                        <label className="contacts-field-updated">
                          <span>Actualizado</span>
                          <input className="input contacts-field" readOnly value={valueOrDash(detailContact.updated_at)} />
                        </label>
                      </div>
                    </div>
                  )}
                </>
              )}
            </section>
          </div>
        </section>
      </div>
    </section>
  )
}
