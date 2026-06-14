import { useMemo, useState } from 'react'
import { listContacts } from '../api/contacts'
import { getCustomerAddressCatalogs, getCustomerDetail, listCustomers } from '../api/customers'
import { QueryState } from '../components/QueryState'
import { useAsyncResource } from '../features/useAsyncResource'
import type { ContactListItem, CustomerAddressCatalogsPayload, CustomerDetail } from '../types/api'

const PAGE_SIZE = 25

type CustomerTab = 'contacts' | 'sales' | 'recipes' | 'agenda'
type CustomerSortKey = 'code' | 'name' | 'island'

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

function normalizeLookupKey(value: string | null | undefined) {
  const text = value?.trim() ?? ''
  return text
}

function resolveAddressLabel(value: string | null | undefined, lookup: Map<string, string>) {
  const key = normalizeLookupKey(value)
  if (!key) {
    return '-'
  }
  return lookup.get(key) || '-'
}

function islandInitials(value: string | null | undefined, lookup: Map<string, string>) {
  const key = normalizeLookupKey(value)
  if (!key) {
    return '-'
  }

  return lookup.get(key) || '-'
}

function compareText(a: string, b: string) {
  return a.localeCompare(b, 'es', { sensitivity: 'base', numeric: true })
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

async function listAllCustomers(search: string) {
  const firstPage = await listCustomers(search, PAGE_SIZE, 0)
  const items = [...firstPage.items]
  let offset = items.length

  while (offset < firstPage.total) {
    const page = await listCustomers(search, PAGE_SIZE, offset)
    if (!page.items.length) {
      break
    }
    items.push(...page.items)
    offset += page.items.length
    if (page.items.length < PAGE_SIZE) {
      break
    }
  }

  return {
    ...firstPage,
    items,
    limit: items.length,
    offset: 0,
  }
}

export function CustomersPage() {
  const [search, setSearch] = useState('')
  const [islandFilter, setIslandFilter] = useState('')
  const [selectedCandidateId, setSelectedCandidateId] = useState('')
  const [activeTab, setActiveTab] = useState<CustomerTab>('contacts')
  const [sortKey, setSortKey] = useState<CustomerSortKey>('code')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc')

  const catalogsQuery = useAsyncResource(
    () => getCustomerAddressCatalogs(),
    { provincias: [], islas: [], municipios: [], codigos_postales: [], localidades: [] } as CustomerAddressCatalogsPayload,
    [],
  )
  const customersQuery = useAsyncResource(
    () => listAllCustomers(search),
    { items: [], total: 0, limit: PAGE_SIZE, offset: 0 },
    [search],
  )
  const customerRows = customersQuery.data.items
  const customerCatalogs = catalogsQuery.data

  const provinceNameById = useMemo(
    () => new Map(customerCatalogs.provincias.map((option) => [option.id, option.label])),
    [customerCatalogs.provincias],
  )
  const islandNameById = useMemo(
    () => new Map(customerCatalogs.islas.map((option) => [option.id, option.label])),
    [customerCatalogs.islas],
  )
  const islandInitialsById = useMemo(
    () => new Map(customerCatalogs.islas.map((option) => [option.id, option.code || option.label])),
    [customerCatalogs.islas],
  )
  const municipalityNameById = useMemo(
    () => new Map(customerCatalogs.municipios.map((option) => [option.id, option.label])),
    [customerCatalogs.municipios],
  )
  const localityNameById = useMemo(
    () => new Map(customerCatalogs.localidades.map((option) => [option.id, option.label])),
    [customerCatalogs.localidades],
  )

  const visibleCustomerRows = useMemo(() => {
    if (!islandFilter) {
      return customerRows
    }
    return customerRows.filter((customer) => normalizeLookupKey(customer.cliente_direccion_isla_id) === islandFilter)
  }, [customerRows, islandFilter])

  const sortedCustomerRows = useMemo(() => {
    const rows = [...visibleCustomerRows]
    rows.sort((left, right) => {
      let comparison: number
      if (sortKey === 'code') {
        comparison = (left.cliente_codigo || 0) - (right.cliente_codigo || 0)
      } else if (sortKey === 'name') {
        comparison = compareText(customerLabel(left), customerLabel(right))
      } else {
        comparison = compareText(
          islandInitials(left.cliente_direccion_isla_id, islandInitialsById),
          islandInitials(right.cliente_direccion_isla_id, islandInitialsById),
        )
      }

      if (comparison === 0) {
        comparison = compareText(customerLabel(left), customerLabel(right))
      }

      return sortDirection === 'asc' ? comparison : -comparison
    })
    return rows
  }, [visibleCustomerRows, sortDirection, sortKey, islandInitialsById])

  const sortAriaValue = sortDirection === 'asc' ? 'ascending' : 'descending'

  const selectedCustomerId = useMemo(() => {
    if (!sortedCustomerRows.length) {
      return ''
    }
    if (selectedCandidateId && sortedCustomerRows.some((row) => row.cliente_id === selectedCandidateId)) {
      return selectedCandidateId
    }
    return sortedCustomerRows[0].cliente_id
  }, [sortedCustomerRows, selectedCandidateId])

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

  return (
    <section className="customers-saas-page">
      <div className="customers-saas-workspace">
        <aside className="customers-list-panel">
          <div className="customers-list-head">
            <div className="customers-list-head-copy">
              <h2>Clientes</h2>
            </div>
            <span className="surface-chip">{sortedCustomerRows.length} visibles</span>
          </div>

          <div className="customers-list-filters">
            <select
              className="select customers-island-select"
              value={islandFilter}
              onChange={(event) => {
                setIslandFilter(event.target.value)
                setSelectedCandidateId('')
              }}
            >
              <option value="">Todas las islas</option>
              {customerCatalogs.islas.map((island) => (
                <option key={island.id} value={island.id}>
                  {island.label}
                </option>
              ))}
            </select>

            <div className="customers-search-row">
              <input
                className="input customers-search"
                value={search}
                onChange={(event) => {
                  setSearch(event.target.value)
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
                  setSelectedCandidateId('')
                }}
              >
                <span aria-hidden="true" className="customers-clear-icon">
                  ↺
                </span>
              </button>
            </div>
          </div>

          <div className="customers-list-scroll">
            <QueryState
              loading={customersQuery.loading}
              error={customersQuery.error}
              empty={!sortedCustomerRows.length}
              emptyMessage="No hay clientes para los filtros actuales."
            />

            {!!sortedCustomerRows.length && (
              <div className="customers-list-grid">
                <div className="customers-list-header">
                  <button
                    type="button"
                    className="customers-list-header-cell"
                    onClick={() => {
                      if (sortKey === 'code') {
                        setSortDirection((current) => (current === 'asc' ? 'desc' : 'asc'))
                      } else {
                        setSortKey('code')
                        setSortDirection('asc')
                      }
                    }}
                    aria-sort={sortKey === 'code' ? sortAriaValue : 'none'}
                  >
                    <span>COD.</span>
                    {sortKey === 'code' && <span className="customers-sort-indicator">{sortDirection === 'asc' ? '▲' : '▼'}</span>}
                  </button>
                  <button
                    type="button"
                    className="customers-list-header-cell"
                    onClick={() => {
                      if (sortKey === 'name') {
                        setSortDirection((current) => (current === 'asc' ? 'desc' : 'asc'))
                      } else {
                        setSortKey('name')
                        setSortDirection('asc')
                      }
                    }}
                    aria-sort={sortKey === 'name' ? sortAriaValue : 'none'}
                  >
                    <span>NOMBRE</span>
                    {sortKey === 'name' && <span className="customers-sort-indicator">{sortDirection === 'asc' ? '▲' : '▼'}</span>}
                  </button>
                  <button
                    type="button"
                    className="customers-list-header-cell"
                    onClick={() => {
                      if (sortKey === 'island') {
                        setSortDirection((current) => (current === 'asc' ? 'desc' : 'asc'))
                      } else {
                        setSortKey('island')
                        setSortDirection('asc')
                      }
                    }}
                    aria-sort={sortKey === 'island' ? sortAriaValue : 'none'}
                  >
                    <span>ISLA</span>
                    {sortKey === 'island' && <span className="customers-sort-indicator">{sortDirection === 'asc' ? '▲' : '▼'}</span>}
                  </button>
                </div>

                <div className="customers-list-body">
                  {sortedCustomerRows.map((customer) => {
                    const islandLabel = resolveAddressLabel(customer.cliente_direccion_isla_id, islandNameById)
                    const islandAbbrev = islandInitials(customer.cliente_direccion_isla_id, islandInitialsById)
                    const isSelected = customer.cliente_id === selectedCustomerId

                    return (
                      <button
                        key={customer.cliente_id}
                        type="button"
                        className={`customers-list-row ${isSelected ? 'is-selected' : ''}`}
                        onClick={() => setSelectedCandidateId(customer.cliente_id)}
                        >
                        <span className="customers-list-cell">{customer.cliente_codigo}</span>
                        <span className="customers-list-cell customers-list-cell-name">{customerLabel(customer)}</span>
                        <span className="customers-list-cell customers-list-cell-island" title={islandLabel}>
                          {islandAbbrev}
                        </span>
                      </button>
                    )
                  })}
                </div>
              </div>
            )}
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

          <div className="customers-detail-body customers-detail-main">
            <div className="customers-detail-grid customers-detail-top">
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
                              value={resolveAddressLabel(detailQuery.data.cliente_direccion_provincia_id, provinceNameById)}
                            />
                          </label>
                          <label>
                            <span>Isla</span>
                            <input
                              className="input customers-field"
                              readOnly
                              value={resolveAddressLabel(detailQuery.data.cliente_direccion_isla_id, islandNameById)}
                            />
                          </label>
                          <label>
                            <span>Municipio</span>
                            <input
                              className="input customers-field"
                              readOnly
                              value={resolveAddressLabel(detailQuery.data.cliente_direccion_municipio_id, municipalityNameById)}
                            />
                          </label>
                        </div>

                        <div className="customers-field-row customers-field-row-location customers-field-row-location-compact">
                          <label className="customers-field-locality">
                            <span>Localidad</span>
                            <input
                              className="input customers-field"
                              readOnly
                              value={resolveAddressLabel(detailQuery.data.cliente_direccion_localidad_id, localityNameById)}
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

              <div className="customers-tabs-content customers-tabs-body">
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

                {activeTab === 'sales' && <div className="state customers-empty-panel customers-tab-empty">Sin datos asociados a ventas.</div>}
                {activeTab === 'recipes' && <div className="state customers-empty-panel customers-tab-empty">Sin datos asociados a recetas.</div>}
                {activeTab === 'agenda' && <div className="state customers-empty-panel customers-tab-empty">Sin datos asociados a agenda.</div>}
              </div>
            </section>
          </div>
        </section>
      </div>
    </section>
  )
}

