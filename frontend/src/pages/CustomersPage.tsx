import { useMemo, useState } from 'react'
import { listContacts } from '../api/contacts'
import { getCustomerDetail, listCustomers } from '../api/customers'
import { QueryState } from '../components/QueryState'
import { useAsyncResource } from '../features/useAsyncResource'
import type { ContactListItem, CustomerDetail } from '../types/api'

const PAGE_SIZE = 25

type CustomerTab = 'contacts' | 'sales' | 'recipes' | 'agenda'

const TABS: Array<{ key: CustomerTab; label: string }> = [
  { key: 'contacts', label: 'Contactos' },
  { key: 'sales', label: 'Ventas' },
  { key: 'recipes', label: 'Recetas' },
  { key: 'agenda', label: 'Agenda' },
]

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

function locationValueOrDash(value: string | null | undefined) {
  if (!value) {
    return '-'
  }

  const text = value.trim()
  if (!text) {
    return '-'
  }

  if (/^\d+$/.test(text)) {
    return '-'
  }

  if (/^[A-Z]{1,4}\d+$/i.test(text)) {
    return '-'
  }

  if (/^[0-9a-f-]{8,}$/i.test(text)) {
    return '-'
  }

  return text
}

function statusLabel(active?: boolean) {
  if (active === true) {
    return 'Activo'
  }
  if (active === false) {
    return 'Inactivo'
  }
  return '-'
}

export function CustomersPage() {
  const [search, setSearch] = useState('')
  const [islandFilter, setIslandFilter] = useState('')
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

  const islandOptions = useMemo(() => {
    const values = new Set<string>()
    customerRows.forEach((customer) => {
      const island = customer.cliente_direccion_isla?.trim()
      if (island) {
        values.add(island)
      }
    })
    return Array.from(values).sort((a, b) => a.localeCompare(b, 'es'))
  }, [customerRows])

  const visibleCustomerRows = useMemo(() => {
    if (!islandFilter) {
      return customerRows
    }
    return customerRows.filter((customer) => customer.cliente_direccion_isla?.trim() === islandFilter)
  }, [customerRows, islandFilter])

  const selectedCustomerId = useMemo(() => {
    if (!visibleCustomerRows.length) {
      return ''
    }
    if (selectedCandidateId && visibleCustomerRows.some((row) => row.cliente_id === selectedCandidateId)) {
      return selectedCandidateId
    }
    return visibleCustomerRows[0].cliente_id
  }, [visibleCustomerRows, selectedCandidateId])

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
    <section className="customers-saas-page">
      <div className="customers-saas-workspace">
        <aside className="customers-list-panel">
          <div className="customers-list-head">
            <div className="customers-list-head-copy">
              <p className="customers-list-kicker">Clientes</p>
              <h2>Listado</h2>
            </div>
            <span className="surface-chip">{visibleCustomerRows.length} visibles</span>
          </div>

          <div className="customers-list-filters">
            <select
              className="select customers-island-select"
              value={islandFilter}
              onChange={(event) => {
                setIslandFilter(event.target.value)
                setPageIndex(0)
                setSelectedCandidateId('')
              }}
            >
              <option value="">Todas las islas</option>
              {islandOptions.map((island) => (
                <option key={island} value={island}>
                  {island}
                </option>
              ))}
            </select>

            <div className="customers-search-row">
              <input
                className="input customers-search"
                value={search}
                onChange={(event) => {
                  setSearch(event.target.value)
                  setPageIndex(0)
                  setSelectedCandidateId('')
                }}
                placeholder="Buscar cliente..."
              />
              <button
                type="button"
                className="customers-clear"
                aria-label="Limpiar busqueda"
                disabled={!search && !islandFilter}
                onClick={() => {
                  setSearch('')
                  setIslandFilter('')
                  setPageIndex(0)
                  setSelectedCandidateId('')
                }}
              >
                ×
              </button>
            </div>
          </div>

          <div className="customers-list-scroll">
            <QueryState
              loading={customersQuery.loading}
              error={customersQuery.error}
              empty={!visibleCustomerRows.length}
              emptyMessage="No hay clientes para los filtros actuales."
            />

            {!!visibleCustomerRows.length && (
              <div className="table-wrap customers-list-table">
                <table>
                  <thead>
                    <tr>
                      <th>COD.</th>
                      <th>NOMBRE</th>
                      <th>ISLA</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleCustomerRows.map((customer) => {
                      const island = customer.cliente_direccion_isla?.trim() || '-'
                      const isSelected = customer.cliente_id === selectedCustomerId

                      return (
                        <tr
                          key={customer.cliente_id}
                          className={isSelected ? 'is-selected' : ''}
                          onClick={() => setSelectedCandidateId(customer.cliente_id)}
                        >
                          <td>{customer.cliente_codigo}</td>
                          <td>{customerLabel(customer)}</td>
                          <td>{island}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="customers-list-pager">
            <button
              type="button"
              className="customers-pager-btn"
              disabled={!hasPreviousPage}
              onClick={() => setPageIndex((prev) => Math.max(0, prev - 1))}
            >
              Anterior
            </button>
            <span className="customers-pager-state">
              Pagina {currentPage} de {totalPages}
            </span>
            <button type="button" className="customers-pager-btn" disabled={!hasNextPage} onClick={() => setPageIndex((prev) => prev + 1)}>
              Siguiente
            </button>
          </div>
        </aside>

        <section className="customers-detail-panel">
          <div className="customers-detail-actions">
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
              ID
            </button>
            <button type="button" className="customers-action-btn customers-action-btn-ghost" disabled>
              Importar Excel/CSV
            </button>
            <button type="button" className="customers-action-btn customers-action-btn-ghost" disabled>
              Listados
            </button>
            <button type="button" className="customers-action-btn customers-action-btn-ghost" disabled>
              Refrescar
            </button>
          </div>

          <div className="customers-detail-body">
            <div className="customers-detail-grid">
              <section className="customers-detail-card">
                <div className="customers-section-head">
                  <div>
                    <h3>Detalle de cliente</h3>
                    <p>Ficha de consulta sin mutaciones.</p>
                  </div>
                  {!!detailQuery.data && <span className="surface-chip">{statusLabel(detailQuery.data.activo)}</span>}
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
                      <div className="customers-field-grid">
                        <div className="customers-field-row customers-field-row-top">
                          <label className="customers-field-code">
                            <span>Cod.</span>
                            <input className="input customers-field" readOnly value={valueOrDash(detailQuery.data.cliente_codigo)} />
                          </label>
                          <label className="customers-field-commercial">
                            <span>Nombre Comercial</span>
                            <input className="input customers-field" readOnly value={valueOrDash(detailQuery.data.cliente_nombre_comercial)} />
                          </label>
                          <label className="customers-field-tax">
                            <span>C.I.F.</span>
                            <input className="input customers-field" readOnly value={valueOrDash(detailQuery.data.cliente_cif)} />
                          </label>
                        </div>

                        <div className="customers-field-row customers-field-row-mid">
                          <label className="customers-field-phone">
                            <span>Telef.</span>
                            <input className="input customers-field" readOnly value={valueOrDash(detailQuery.data.cliente_telefono)} />
                          </label>
                          <label className="customers-field-fiscal">
                            <span>Nombre Fiscal</span>
                            <input className="input customers-field" readOnly value={valueOrDash(detailQuery.data.cliente_nombre_fiscal)} />
                          </label>
                        </div>

                        <div className="customers-field-row customers-field-row-location">
                          <label>
                            <span>Provincia</span>
                            <input
                              className="input customers-field"
                              readOnly
                              value={locationValueOrDash(detailQuery.data.cliente_direccion_provincia_id)}
                            />
                          </label>
                          <label>
                            <span>Isla</span>
                            <input
                              className="input customers-field"
                              readOnly
                              value={locationValueOrDash(detailQuery.data.cliente_direccion_isla)}
                            />
                          </label>
                          <label>
                            <span>Municipio</span>
                            <input
                              className="input customers-field"
                              readOnly
                              value={locationValueOrDash(detailQuery.data.cliente_direccion_municipio_id)}
                            />
                          </label>
                        </div>

                        <div className="customers-field-row customers-field-row-location customers-field-row-location-compact">
                          <label className="customers-field-locality">
                            <span>Localidad</span>
                            <input
                              className="input customers-field"
                              readOnly
                              value={locationValueOrDash(detailQuery.data.cliente_direccion_localidad_id)}
                            />
                          </label>
                          <label className="customers-field-postal">
                            <span>C.P.</span>
                            <input className="input customers-field" readOnly value={valueOrDash(detailQuery.data.cliente_direccion_cp)} />
                          </label>
                        </div>

                        <div className="customers-field-row customers-field-row-street">
                          <label>
                            <span>Calle</span>
                            <input className="input customers-field" readOnly value={valueOrDash(detailQuery.data.cliente_direccion)} />
                          </label>
                        </div>
                      </div>
                    )}
                  </>
                )}
              </section>

              <aside className="customers-type-panel">
                <div className="customers-section-head">
                  <div>
                    <h3>Tipo de cliente</h3>
                    <p>Seleccion read-only con estado limpio.</p>
                  </div>
                </div>

                {!!detailQuery.data && (
                  <>
                    <div className="customers-type-grid">
                      {['PANADERIA', 'PASTELERIA', 'HELADERIA', 'CAFETERIA', 'RESTAURANTE', 'HOTEL'].map((type) => {
                        const isActive = detailQuery.data?.cliente_tipo?.toUpperCase() === type
                        return (
                          <button
                            key={type}
                            type="button"
                            className={`customer-type-pill ${isActive ? 'active' : ''}`}
                            aria-pressed={isActive}
                            disabled
                          >
                            <span className="customer-type-pill-label">{type}</span>
                            {isActive && <span className="customer-type-pill-check">✓</span>}
                          </button>
                        )
                      })}
                    </div>

                    <div className="customers-type-fields">
                      <label>
                        <span>Tipo</span>
                        <input className="input customers-field" readOnly value={valueOrDash(detailQuery.data.cliente_tipo)} />
                      </label>
                      <label>
                        <span>Abrev. pedido</span>
                        <input className="input customers-field" readOnly value={valueOrDash(detailQuery.data.cliente_abreviatura)} />
                      </label>
                    </div>

                    <div className="customers-status-row">
                      <span className={`customers-status-pill ${detailQuery.data.activo ? 'is-active' : 'is-inactive'}`}>
                        ACTIVO
                      </span>
                      <span className={`customers-status-pill ${detailQuery.data.activo ? 'is-inactive' : 'is-active'}`}>
                        INACTIVO
                      </span>
                    </div>

                    <div className="customers-prospect-row">
                      <span>Prospeccion</span>
                      <div className="customers-radio-readonly">
                        <span className={detailQuery.data.cliente_prospeccion ? 'selected' : ''}>Si</span>
                        <span className={!detailQuery.data.cliente_prospeccion ? 'selected' : ''}>No</span>
                      </div>
                    </div>
                  </>
                )}
              </aside>
            </div>

            <section className="customers-tabs-panel">
              <div className="customers-tabs" role="tablist" aria-label="Secciones de cliente">
                {TABS.map((tab) => (
                  <button
                    key={tab.key}
                    type="button"
                    role="tab"
                    aria-selected={activeTab === tab.key}
                    className={`customers-tab ${activeTab === tab.key ? 'active' : ''}`}
                    onClick={() => setActiveTab(tab.key)}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              <div className="customers-tabs-content">
                {activeTab === 'contacts' && (
                  <div className="customers-tab-scroll">
                    <div className="customers-tab-head">
                      <div>
                        <h3>Contactos</h3>
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
                      <div className="table-wrap customers-contacts-table">
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

                {activeTab === 'sales' && <div className="state customers-empty-panel">Sin datos asociados a ventas.</div>}
                {activeTab === 'recipes' && <div className="state customers-empty-panel">Sin datos asociados a recetas.</div>}
                {activeTab === 'agenda' && <div className="state customers-empty-panel">Sin datos asociados a agenda.</div>}
              </div>
            </section>
          </div>
        </section>
      </div>
    </section>
  )
}
