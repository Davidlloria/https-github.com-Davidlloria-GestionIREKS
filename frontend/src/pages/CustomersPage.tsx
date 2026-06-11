import { useMemo, useState } from 'react'
import { listContacts } from '../api/contacts'
import { getCustomerDetail, listCustomers } from '../api/customers'
import { QueryState } from '../components/QueryState'
import { useAsyncResource } from '../features/useAsyncResource'
import type { ContactListItem, CustomerDetail } from '../types/api'

const PAGE_SIZE = 25

type CustomerTab = 'contacts' | 'sales' | 'recipes' | 'agenda'

function customerLabel(customer: { cliente_id: string; cliente_nombre_comercial: string; cliente_nombre_fiscal: string }) {
  return customer.cliente_nombre_comercial || customer.cliente_nombre_fiscal || customer.cliente_id
}

function contactLabel(contact: ContactListItem) {
  return `${contact.nombre || ''} ${contact.apellidos || ''}`.trim() || contact.contacto_id
}

function valueOrDash(value: string | number | boolean | null | undefined) {
  if (value === null || value === undefined) {
    return '-'
  }
  if (typeof value === 'boolean') {
    return value ? 'Si' : 'No'
  }
  const text = String(value).trim()
  return text || '-'
}

const TABS: Array<{ key: CustomerTab; label: string }> = [
  { key: 'contacts', label: 'Contactos' },
  { key: 'sales', label: 'Ventas' },
  { key: 'recipes', label: 'Recetas' },
  { key: 'agenda', label: 'Agenda' },
]

export function CustomersPage() {
  const [search, setSearch] = useState('')
  const [pageIndex, setPageIndex] = useState(0)
  const [selectedCandidateId, setSelectedCandidateId] = useState('')
  const [activeTab, setActiveTab] = useState<CustomerTab>('contacts')

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

  return (
    <section className="page-grid customers-layout">
      <header className="customers-page-title">
        <div>
          <p className="module-kicker">Modulo read-only</p>
          <h2>Clientes</h2>
          <p className="module-description">Consulta compacta de clientes con detalle, tipo y relaciones asociadas.</p>
        </div>
      </header>

      <div className="customers-shell">
        <aside className="customers-list-pane">
          <div className="customers-filter-card">
            <select className="select customers-island-select" disabled value="">
              <option value="">Todas las islas</option>
            </select>
            <div className="customers-search-row">
              <input
                className="input customers-search"
                value={search}
                onChange={(event) => {
                  setSearch(event.target.value)
                  setPageIndex(0)
                }}
                placeholder="Buscar cliente..."
              />
              <button type="button" className="customers-clear" disabled aria-label="Limpiar búsqueda">
                ✕
              </button>
            </div>
          </div>

          <div className="customers-list-meta">
            <span className="customers-count">Cod.</span>
            <span className="customers-count">Nombre</span>
            <span className="customers-count">Tipo</span>
          </div>

          <div className="customers-list-scroll">
            <QueryState
              loading={customersQuery.loading}
              error={customersQuery.error}
              empty={!customerRows.length}
              emptyMessage="No hay clientes para los filtros actuales."
            />

            {!!customerRows.length && (
              <div className="table-wrap customers-list-table">
                <table>
                  <thead>
                    <tr>
                      <th>Cod.</th>
                      <th>Nombre</th>
                      <th>Tipo</th>
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
                        <td>{customer.cliente_tipo || '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="customers-pager">
            <button type="button" className="action-btn" disabled={!hasPreviousPage} onClick={() => setPageIndex((prev) => Math.max(0, prev - 1))}>
              Anterior
            </button>
            <span className="state customers-page-state">
              Pagina {currentPage} de {totalPages}
            </span>
            <button type="button" className="action-btn" disabled={!hasNextPage} onClick={() => setPageIndex((prev) => prev + 1)}>
              Siguiente
            </button>
          </div>
        </aside>

        <section className="customers-detail-pane">
          <div className="customers-toolbar">
            <button type="button" className="customers-toolbar-btn customers-toolbar-btn-green" disabled>
              Nuevo
            </button>
            <button type="button" className="customers-toolbar-btn customers-toolbar-btn-orange" disabled>
              Editar
            </button>
            <button type="button" className="customers-toolbar-btn customers-toolbar-btn-red" disabled>
              Eliminar
            </button>
            <button type="button" className="customers-toolbar-btn" disabled>
              ID
            </button>
            <button type="button" className="customers-toolbar-btn customers-toolbar-btn-wide" disabled>
              Importar Excel/CSV
            </button>
            <button type="button" className="customers-toolbar-btn customers-toolbar-btn-blue" disabled>
              Listados
            </button>
            <button type="button" className="customers-toolbar-btn" disabled>
              Refrescar
            </button>
          </div>

          <div className="customers-detail-grid">
            <section className="customers-form-card">
              <div className="customers-section-head">
                <h3>Detalle de cliente</h3>
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
                    <div className="customers-form-grid">
                      <label>
                        <span>Cod.</span>
                        <input className="input customers-field" readOnly value={valueOrDash(detailQuery.data.cliente_codigo)} />
                      </label>
                      <label className="customers-wide-field">
                        <span>Nombre Comercial</span>
                        <input className="input customers-field" readOnly value={valueOrDash(detailQuery.data.cliente_nombre_comercial)} />
                      </label>
                      <label>
                        <span>Telef.</span>
                        <input className="input customers-field" readOnly value={valueOrDash(detailQuery.data.cliente_telefono)} />
                      </label>
                      <label>
                        <span>C.I.F.</span>
                        <input className="input customers-field" readOnly value={valueOrDash(detailQuery.data.cliente_cif)} />
                      </label>
                      <label className="customers-wide-field">
                        <span>Nombre Fiscal</span>
                        <input className="input customers-field" readOnly value={valueOrDash(detailQuery.data.cliente_nombre_fiscal)} />
                      </label>
                      <label>
                        <span>Provincia</span>
                        <input className="input customers-field" readOnly value={valueOrDash(detailQuery.data.cliente_direccion_provincia_id)} />
                      </label>
                      <label>
                        <span>Isla</span>
                        <input className="input customers-field" readOnly value={valueOrDash(detailQuery.data.cliente_direccion_isla_id)} />
                      </label>
                      <label>
                        <span>Municipio</span>
                        <input className="input customers-field" readOnly value={valueOrDash(detailQuery.data.cliente_direccion_municipio_id)} />
                      </label>
                      <label className="customers-wide-field">
                        <span>Calle</span>
                        <input className="input customers-field" readOnly value={valueOrDash(detailQuery.data.cliente_direccion)} />
                      </label>
                      <label>
                        <span>C.P.</span>
                        <input className="input customers-field" readOnly value={valueOrDash(detailQuery.data.cliente_direccion_cp)} />
                      </label>
                      <label>
                        <span>Localidad</span>
                        <input className="input customers-field" readOnly value={valueOrDash(detailQuery.data.cliente_direccion_localidad_id)} />
                      </label>
                    </div>
                  )}
                </>
              )}
            </section>

            <aside className="customers-type-card">
              <div className="customers-section-head">
                <h3>Tipo de cliente</h3>
              </div>

              {!!detailQuery.data && (
                <div className="customers-type-grid">
                  {['PANADERIA', 'PASTELERIA', 'HELADERIA', 'CAFETERIA', 'RESTAURANTE', 'HOTEL'].map((type) => (
                    <button
                      key={type}
                      type="button"
                      className={`customer-type-pill ${detailQuery.data?.cliente_tipo?.toUpperCase() === type ? 'active' : ''}`}
                      disabled
                    >
                      {type}
                    </button>
                  ))}
                </div>
              )}

                  <div className="customers-type-fields">
                <label>
                  <span>Tipo</span>
                  <input className="input customers-field" readOnly value={detailQuery.data ? valueOrDash(detailQuery.data.cliente_tipo) : ''} />
                </label>
                <label>
                  <span>Abrev. pedido</span>
                  <input className="input customers-field" readOnly value={detailQuery.data ? valueOrDash(detailQuery.data.cliente_abreviatura) : ''} />
                </label>
              </div>

              <div className="customers-status-row">
                <span className={`customers-status ${detailQuery.data?.activo ? 'active' : ''}`}>ACTIVO</span>
                <span className={`customers-status ${detailQuery.data?.activo ? '' : 'inactive'}`}>INACTIVO</span>
              </div>

              <div className="customers-prospect-row">
                <span>Prospección</span>
                <div className="customers-radio-readonly">
                  <span className={detailQuery.data?.cliente_prospeccion ? 'selected' : ''}>Si</span>
                  <span className={!detailQuery.data?.cliente_prospeccion ? 'selected' : ''}>No</span>
                </div>
              </div>
            </aside>
          </div>

          <div className="customers-tabs">
            {TABS.map((tab) => (
              <button
                key={tab.key}
                type="button"
                className={`customers-tab ${activeTab === tab.key ? 'active' : ''}`}
                onClick={() => setActiveTab(tab.key)}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="customers-tab-panel">
            {activeTab === 'contacts' && (
              <div className="customers-tab-scroll">
                <div className="customers-tab-head">
                  <div>
                    <h3>Contactos</h3>
                    <p>Listado read-only de contactos relacionados con el cliente seleccionado.</p>
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
            )}

            {activeTab === 'sales' && <div className="state customers-empty-panel">Vista read-only reservada para ventas asociadas.</div>}
            {activeTab === 'recipes' && <div className="state customers-empty-panel">Vista read-only reservada para recetas asociadas.</div>}
            {activeTab === 'agenda' && <div className="state customers-empty-panel">Vista read-only reservada para agenda asociada.</div>}
          </div>
        </section>
      </div>
    </section>
  )
}
