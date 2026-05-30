import { useCallback, useMemo, useState } from 'react'
import { getContactDetail, listContactCompanies, listContacts } from '../api/contacts'
import { QueryState } from '../components/QueryState'
import { StatCard } from '../components/StatCard'
import { useAsyncResource } from '../features/useAsyncResource'
import type { ContactDetail, ContactListItem } from '../types/api'

export function ContactsPage() {
  const [search, setSearch] = useState('')
  const [companyFilter, setCompanyFilter] = useState('')
  const [selectedCandidateId, setSelectedCandidateId] = useState('')

  const contactsQuery = useAsyncResource(() => listContacts(search), [], [search])
  const companiesQuery = useAsyncResource(() => listContactCompanies(), [], [])

  const filteredContacts = useMemo(() => {
    if (!companyFilter) {
      return contactsQuery.data
    }
    return contactsQuery.data.filter((row) => row.cliente_id === companyFilter)
  }, [companyFilter, contactsQuery.data])

  const selectedContactId = useMemo(() => {
    if (!filteredContacts.length) {
      return ''
    }
    if (selectedCandidateId && filteredContacts.some((row) => row.contacto_id === selectedCandidateId)) {
      return selectedCandidateId
    }
    return filteredContacts[0].contacto_id
  }, [filteredContacts, selectedCandidateId])

  const loadSelectedDetail = useCallback(() => {
    if (!selectedContactId) {
      return Promise.resolve(null as ContactDetail | null)
    }
    return getContactDetail(selectedContactId)
  }, [selectedContactId])

  const detailQuery = useAsyncResource(loadSelectedDetail, null as ContactDetail | null, [loadSelectedDetail, selectedContactId])

  const totals = useMemo(() => {
    const withEmail = filteredContacts.filter((row) => !!row.email).length
    const withPhone = filteredContacts.filter((row) => !!row.telefono).length
    const uniqueCompanies = new Set(filteredContacts.map((row) => row.cliente_id).filter(Boolean)).size
    return {
      total: filteredContacts.length,
      withEmail,
      withPhone,
      uniqueCompanies,
    }
  }, [filteredContacts])

  const fullName = (row: ContactListItem) => `${row.nombre || ''} ${row.apellidos || ''}`.trim()

  return (
    <section className="page-grid">
      <div className="toolbar">
        <input
          className="input"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Buscar por nombre, apellido, cargo, email o empresa"
        />
        <select
          className="select"
          value={companyFilter}
          onChange={(event) => setCompanyFilter(event.target.value)}
        >
          <option value="">Todas las empresas</option>
          {companiesQuery.data.map((company) => (
            <option key={company.cliente_id} value={company.cliente_id}>
              {company.nombre}
            </option>
          ))}
        </select>
      </div>

      <div className="cards">
        <StatCard label="Total contactos" value={totals.total} />
        <StatCard label="Con email" value={totals.withEmail} />
        <StatCard label="Con telefono" value={totals.withPhone} />
        <StatCard label="Empresas con contactos" value={totals.uniqueCompanies} />
      </div>

      <QueryState
        loading={contactsQuery.loading}
        error={contactsQuery.error}
        empty={!filteredContacts.length}
        emptyMessage="No hay contactos para los filtros actuales."
      />

      {!!filteredContacts.length && (
        <div className="split-panel">
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
                {filteredContacts.map((row) => (
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

          <aside className="detail-panel">
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
