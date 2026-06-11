import { useMemo, useState } from 'react'
import { listContacts } from '../api/contacts'
import { getCustomerDetail, listCustomers } from '../api/customers'
import { QueryState } from '../components/QueryState'
import { StatCard } from '../components/StatCard'
import { useAsyncResource } from '../features/useAsyncResource'
import type { ContactListItem, CustomerDetail } from '../types/api'

const PAGE_SIZE = 25

function customerLabel(customer: { cliente_id: string; cliente_nombre_comercial: string; cliente_nombre_fiscal: string }) {
  return customer.cliente_nombre_comercial || customer.cliente_nombre_fiscal || customer.cliente_id
}

function contactLabel(contact: ContactListItem) {
  return `${contact.nombre || ''} ${contact.apellidos || ''}`.trim() || contact.contacto_id
}

export function CustomersPage() {
  const [search, setSearch] = useState('')
  const [pageIndex, setPageIndex] = useState(0)
  const [selectedCandidateId, setSelectedCandidateId] = useState('')

  const offset = pageIndex * PAGE_SIZE
  const customersQuery = useAsyncResource(
    () => listCustomers(search, PAGE_SIZE, offset),
    { items: [], total: 0, limit: PAGE_SIZE, offset: 0 },
    [search, offset],
  )
  const customerRows = customersQuery.data.items

  const selectedCustomerId = useMemo(() => {
    if (!customerRows.length) {
      return ''
    }
    if (selectedCandidateId && customerRows.some((row) => row.cliente_id === selectedCandidateId)) {
      return selectedCandidateId
    }
    return customerRows[0].cliente_id
  }, [customerRows, selectedCandidateId])

  const detailQuery = useAsyncResource(
    () => (selectedCustomerId ? getCustomerDetail(selectedCustomerId) : Promise.resolve(null as CustomerDetail | null)),
    null as CustomerDetail | null,
    [selectedCustomerId],
  )

  const contactsQuery = useAsyncResource(
    () =>
      selectedCustomerId
        ? listContacts('', selectedCustomerId, PAGE_SIZE, 0)
        : Promise.resolve({ items: [], total: 0, limit: PAGE_SIZE, offset: 0 }),
    { items: [], total: 0, limit: PAGE_SIZE, offset: 0 },
    [selectedCustomerId],
  )

  const hasPreviousPage = pageIndex > 0
  const hasNextPage = offset + customerRows.length < customersQuery.data.total
  const currentPage = pageIndex + 1
  const totalPages = Math.max(1, Math.ceil(customersQuery.data.total / PAGE_SIZE))
  const summary = useMemo(() => {
    const activeCount = customerRows.filter((row) => row.activo).length
    const withEmailCount = customerRows.filter((row) => !!row.cliente_email).length
    const withPhoneCount = customerRows.filter((row) => !!row.cliente_telefono).length
    return {
      total: customersQuery.data.total,
      activeCount,
      withEmailCount,
      withPhoneCount,
    }
  }, [customerRows, customersQuery.data.total])

  return (
    <section className="page-grid">
      <header className="module-header">
        <div className="module-header-copy">
          <p className="module-kicker">Modulo read-only</p>
          <h2>Clientes</h2>
          <p className="module-description">
            Consulta de clientes con detalle lateral y contactos asociados para revisar informacion comercial sin editar datos.
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
            <p>Busca por texto y navega por pagina para revisar el cliente seleccionado.</p>
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
            placeholder="Buscar cliente por nombre, email o CIF"
          />
        </div>
      </section>

      <div className="cards">
        <StatCard label="Total clientes" value={summary.total} />
        <StatCard label="Activos en pagina" value={summary.activeCount} />
        <StatCard label="Con email en pagina" value={summary.withEmailCount} />
        <StatCard label="Con telefono en pagina" value={summary.withPhoneCount} />
      </div>

      <QueryState
        loading={customersQuery.loading}
        error={customersQuery.error}
        empty={!customerRows.length}
        emptyMessage="No hay clientes para los filtros actuales."
      />

      {!!customerRows.length && (
        <div className="orders-workspace">
          <section className="orders-list-panel">
            <div className="panel-section">
              <div className="section-heading">
                <div>
                  <h3>Listado de clientes</h3>
                  <p>Selecciona una fila para cargar el detalle y los contactos asociados.</p>
                </div>
                <span className="surface-chip">Mostrando {customerRows.length} de {customersQuery.data.total}</span>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Codigo</th>
                      <th>Nombre comercial</th>
                      <th>Nombre fiscal</th>
                      <th>Email</th>
                      <th>Telefono</th>
                      <th>Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {customerRows.map((customer) => (
                      <tr
                        key={customer.cliente_id}
                        className={customer.cliente_id === selectedCustomerId ? 'row-selected' : ''}
                        onClick={() => setSelectedCandidateId(customer.cliente_id)}
                      >
                        <td>{customer.cliente_codigo}</td>
                        <td>{customerLabel(customer)}</td>
                        <td>{customer.cliente_nombre_fiscal || '-'}</td>
                        <td>{customer.cliente_email || '-'}</td>
                        <td>{customer.cliente_telefono || '-'}</td>
                        <td>
                          <span className={`pill ${customer.activo ? 'ok' : 'off'}`}>{customer.activo ? 'Activo' : 'Inactivo'}</span>
                        </td>
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
                <h3>Detalle de cliente</h3>
                <p>Datos comerciales y contactos asociados al cliente activo.</p>
              </div>
            </div>
            {!selectedCustomerId && <div className="state">Selecciona un cliente para ver el detalle.</div>}

            {!!selectedCustomerId && (
              <>
                <QueryState
                  loading={detailQuery.loading}
                  error={detailQuery.error}
                  empty={!detailQuery.data}
                  emptyMessage="No se encontro detalle para el cliente seleccionado."
                />

                {!!detailQuery.data && (
                  <>
                    <dl className="detail-list">
                      <div>
                        <dt>Cliente ID</dt>
                        <dd>{detailQuery.data.cliente_id}</dd>
                      </div>
                      <div>
                        <dt>Nombre comercial</dt>
                        <dd>{detailQuery.data.cliente_nombre_comercial || '-'}</dd>
                      </div>
                      <div>
                        <dt>Nombre fiscal</dt>
                        <dd>{detailQuery.data.cliente_nombre_fiscal || '-'}</dd>
                      </div>
                      <div>
                        <dt>CIF</dt>
                        <dd>{detailQuery.data.cliente_cif || '-'}</dd>
                      </div>
                      <div>
                        <dt>Grupo</dt>
                        <dd>{detailQuery.data.cliente_grupo || '-'}</dd>
                      </div>
                      <div>
                        <dt>Tipo</dt>
                        <dd>{detailQuery.data.cliente_tipo || '-'}</dd>
                      </div>
                      <div>
                        <dt>Email</dt>
                        <dd>{detailQuery.data.cliente_email || '-'}</dd>
                      </div>
                      <div>
                        <dt>Telefono</dt>
                        <dd>{detailQuery.data.cliente_telefono || '-'}</dd>
                      </div>
                      <div>
                        <dt>Direccion</dt>
                        <dd>{detailQuery.data.cliente_direccion || '-'}</dd>
                      </div>
                      <div>
                        <dt>Codigo postal</dt>
                        <dd>{detailQuery.data.cliente_direccion_cp || '-'}</dd>
                      </div>
                      <div>
                        <dt>Activo</dt>
                        <dd>{detailQuery.data.activo ? 'Si' : 'No'}</dd>
                      </div>
                    </dl>

                    <div className="related-block">
                      <div className="section-heading section-heading-compact">
                        <div>
                          <h3>Contactos asociados</h3>
                          <p>Listado read-only de contactos relacionados con este cliente.</p>
                        </div>
                        <span className="surface-chip">{contactsQuery.data.items.length} contactos</span>
                      </div>
                      <QueryState
                        loading={contactsQuery.loading}
                        error={contactsQuery.error}
                        empty={!contactsQuery.data.items.length}
                        emptyMessage="No hay contactos asociados."
                      />

                      {!!contactsQuery.data.items.length && (
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
                              {contactsQuery.data.items.map((contact) => (
                                <tr key={contact.contacto_id}>
                                  <td>{contactLabel(contact)}</td>
                                  <td>{contact.cliente_nombre || '-'}</td>
                                  <td>{contact.cargo || '-'}</td>
                                  <td>{contact.email || '-'}</td>
                                  <td>{contact.telefono || '-'}</td>
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
