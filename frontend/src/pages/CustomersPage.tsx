import { useMemo, useState, type FormEvent } from 'react'
import {
  createCustomer,
  deleteCustomer,
  getCustomerAddressCatalogs,
  getCustomerDetail,
  listCustomers,
  updateCustomer,
  type CustomerSavePayload,
} from '../api/customers'
import { listContacts } from '../api/contacts'
import { QueryState } from '../components/QueryState'
import { useAsyncResource } from '../features/useAsyncResource'
import type { AddressOption, ContactListItem, CustomerAddressCatalogsPayload, CustomerDetail, CustomerListItem, PaginatedList } from '../types/api'

const PAGE_SIZE = 25

type CustomerTab = 'contacts' | 'sales' | 'recipes' | 'agenda'
type CustomerSortKey = 'code' | 'name' | 'island'
type CustomerEditorMode = 'create' | 'edit' | null

interface CustomerDraft {
  cliente_codigo: string
  cliente_nombre_comercial: string
  cliente_nombre_fiscal: string
  cliente_nombre_interno: string
  cliente_abreviatura: string
  cliente_cif: string
  cliente_telefono: string
  cliente_email: string
  cliente_direccion: string
  cliente_direccion_cp: string
  cliente_direccion_localidad_id: string
  cliente_direccion_municipio_id: string
  cliente_direccion_provincia_id: string
  cliente_direccion_isla_id: string
  cliente_tipo: string
  cliente_grupo: string
  cliente_prospeccion: boolean
  distribuidor_id: string
  activo: boolean
}

const EMPTY_CATALOGS: CustomerAddressCatalogsPayload = {
  provincias: [],
  islas: [],
  municipios: [],
  codigos_postales: [],
  localidades: [],
}

const EMPTY_LIST: PaginatedList<CustomerListItem> = {
  items: [],
  total: 0,
  limit: PAGE_SIZE,
  offset: 0,
}

const CUSTOMER_TYPES = ['PANADERIA', 'PASTELERIA', 'HELADERIA', 'CAFETERIA', 'RESTAURANTE', 'HOTEL']

const TABS: Array<{ key: CustomerTab; label: string }> = [
  { key: 'contacts', label: 'Contactos' },
  { key: 'sales', label: 'Ventas' },
  { key: 'recipes', label: 'Recetas' },
  { key: 'agenda', label: 'Agenda' },
]

function customerLabel(customer: { cliente_id: string; cliente_nombre_comercial: string; cliente_nombre_fiscal: string }) {
  return customer.cliente_nombre_comercial || customer.cliente_nombre_fiscal || customer.cliente_id
}

function contactLabel(contact: Pick<ContactListItem, 'nombre' | 'apellidos' | 'contacto_id'>) {
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
  return value?.trim() ?? ''
}

function resolveAddressLabel(value: string | null | undefined, lookup: Map<string, string>) {
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

function emptyCustomerDraft(): CustomerDraft {
  return {
    cliente_codigo: '',
    cliente_nombre_comercial: '',
    cliente_nombre_fiscal: '',
    cliente_nombre_interno: '',
    cliente_abreviatura: '',
    cliente_cif: '',
    cliente_telefono: '',
    cliente_email: '',
    cliente_direccion: '',
    cliente_direccion_cp: '',
    cliente_direccion_localidad_id: '',
    cliente_direccion_municipio_id: '',
    cliente_direccion_provincia_id: '',
    cliente_direccion_isla_id: '',
    cliente_tipo: '',
    cliente_grupo: '',
    cliente_prospeccion: false,
    distribuidor_id: '',
    activo: true,
  }
}

function draftFromDetail(detail: CustomerDetail): CustomerDraft {
  return {
    cliente_codigo: detail.cliente_codigo ? String(detail.cliente_codigo) : '',
    cliente_nombre_comercial: detail.cliente_nombre_comercial || '',
    cliente_nombre_fiscal: detail.cliente_nombre_fiscal || '',
    cliente_nombre_interno: detail.cliente_nombre_interno || '',
    cliente_abreviatura: detail.cliente_abreviatura || '',
    cliente_cif: detail.cliente_cif || '',
    cliente_telefono: detail.cliente_telefono || '',
    cliente_email: detail.cliente_email || '',
    cliente_direccion: detail.cliente_direccion || '',
    cliente_direccion_cp: detail.cliente_direccion_cp || '',
    cliente_direccion_localidad_id: detail.cliente_direccion_localidad_id || '',
    cliente_direccion_municipio_id: detail.cliente_direccion_municipio_id || '',
    cliente_direccion_provincia_id: detail.cliente_direccion_provincia_id || '',
    cliente_direccion_isla_id: detail.cliente_direccion_isla_id || '',
    cliente_tipo: detail.cliente_tipo || '',
    cliente_grupo: detail.cliente_grupo || '',
    cliente_prospeccion: Boolean(detail.cliente_prospeccion),
    distribuidor_id: detail.distribuidor_id || '',
    activo: Boolean(detail.activo),
  }
}

function draftToPayload(draft: CustomerDraft): CustomerSavePayload {
  return {
    cliente_codigo: draft.cliente_codigo.trim() ? Number(draft.cliente_codigo) : undefined,
    cliente_nombre_comercial: draft.cliente_nombre_comercial.trim(),
    cliente_nombre_fiscal: draft.cliente_nombre_fiscal.trim(),
    cliente_nombre_interno: draft.cliente_nombre_interno.trim(),
    cliente_abreviatura: draft.cliente_abreviatura.trim(),
    cliente_cif: draft.cliente_cif.trim(),
    cliente_telefono: draft.cliente_telefono.trim(),
    cliente_email: draft.cliente_email.trim(),
    cliente_direccion: draft.cliente_direccion.trim(),
    cliente_direccion_cp: draft.cliente_direccion_cp.trim(),
    cliente_direccion_localidad_id: draft.cliente_direccion_localidad_id.trim(),
    cliente_direccion_municipio_id: draft.cliente_direccion_municipio_id.trim(),
    cliente_direccion_provincia_id: draft.cliente_direccion_provincia_id.trim(),
    cliente_direccion_isla_id: draft.cliente_direccion_isla_id.trim(),
    cliente_tipo: draft.cliente_tipo.trim(),
    cliente_grupo: draft.cliente_grupo.trim(),
    cliente_prospeccion: draft.cliente_prospeccion,
    distribuidor_id: draft.distribuidor_id.trim(),
    activo: draft.activo,
  }
}

function buildAddressLookup(options: AddressOption[]) {
  return new Map(options.map((option) => [option.id, option.label]))
}

function filterAddressOptions(options: AddressOption[], parentId: string) {
  if (!parentId) {
    return options
  }
  return options.filter((option) => normalizeLookupKey(option.parent_id) === parentId)
}

function listAllCustomers(search: string) {
  return listCustomers(search, PAGE_SIZE, 0).then(async (firstPage) => {
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
  })
}

function getErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'Error de red'
}

export function CustomersPage() {
  const [search, setSearch] = useState('')
  const [islandFilter, setIslandFilter] = useState('')
  const [selectedCandidateId, setSelectedCandidateId] = useState('')
  const [activeTab, setActiveTab] = useState<CustomerTab>('contacts')
  const [sortKey, setSortKey] = useState<CustomerSortKey>('code')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc')
  const [editorMode, setEditorMode] = useState<CustomerEditorMode>(null)
  const [draft, setDraft] = useState<CustomerDraft>(emptyCustomerDraft())
  const [refreshTick, setRefreshTick] = useState(0)
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)

  const catalogsQuery = useAsyncResource(
    () => getCustomerAddressCatalogs(),
    EMPTY_CATALOGS,
    [refreshTick],
  )
  const customersQuery = useAsyncResource(
    () => listAllCustomers(search),
    EMPTY_LIST,
    [search, refreshTick],
  )
  const customerRows = customersQuery.data.items
  const customerCatalogs = catalogsQuery.data

  const provinceNameById = useMemo(() => buildAddressLookup(customerCatalogs.provincias), [customerCatalogs.provincias])
  const islandNameById = useMemo(() => buildAddressLookup(customerCatalogs.islas), [customerCatalogs.islas])
  const islandInitialsById = useMemo(
    () => new Map(customerCatalogs.islas.map((option) => [option.id, option.code || option.label])),
    [customerCatalogs.islas],
  )
  const municipalityNameById = useMemo(() => buildAddressLookup(customerCatalogs.municipios), [customerCatalogs.municipios])
  const localityNameById = useMemo(() => buildAddressLookup(customerCatalogs.localidades), [customerCatalogs.localidades])

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
          islandInitialsById.get(normalizeLookupKey(left.cliente_direccion_isla_id)) || '-',
          islandInitialsById.get(normalizeLookupKey(right.cliente_direccion_isla_id)) || '-',
        )
      }

      if (comparison === 0) {
        comparison = compareText(customerLabel(left), customerLabel(right))
      }

      return sortDirection === 'asc' ? comparison : -comparison
    })
    return rows
  }, [visibleCustomerRows, sortDirection, sortKey, islandInitialsById])

  const selectedCustomerId = useMemo(() => {
    if (!sortedCustomerRows.length) {
      return ''
    }
    if (editorMode === 'create' && !selectedCandidateId) {
      return ''
    }
    if (selectedCandidateId && sortedCustomerRows.some((row) => row.cliente_id === selectedCandidateId)) {
      return selectedCandidateId
    }
    return sortedCustomerRows[0].cliente_id
  }, [sortedCustomerRows, selectedCandidateId, editorMode])

  const detailQuery = useAsyncResource(
    () => (selectedCustomerId ? getCustomerDetail(selectedCustomerId) : Promise.resolve(null as CustomerDetail | null)),
    null as CustomerDetail | null,
    [selectedCustomerId, refreshTick],
  )

  const contactsQuery = useAsyncResource<PaginatedList<ContactListItem>>(
    () =>
      selectedCustomerId
        ? listContacts('', selectedCustomerId, PAGE_SIZE, 0)
        : Promise.resolve({ items: [], total: 0, limit: PAGE_SIZE, offset: 0 }),
    { items: [], total: 0, limit: PAGE_SIZE, offset: 0 },
    [selectedCustomerId, refreshTick],
  )

  const sortAriaValue = sortDirection === 'asc' ? 'ascending' : 'descending'
  const selectedDetail = detailQuery.data
  const hasEditor = editorMode !== null
  const firstCustomerId = sortedCustomerRows[0]?.cliente_id || ''
  const selectedAddressProvinceId = hasEditor ? draft.cliente_direccion_provincia_id : selectedDetail?.cliente_direccion_provincia_id || ''
  const selectedAddressIslandId = hasEditor ? draft.cliente_direccion_isla_id : selectedDetail?.cliente_direccion_isla_id || ''
  const selectedAddressMunicipalityId = hasEditor ? draft.cliente_direccion_municipio_id : selectedDetail?.cliente_direccion_municipio_id || ''
  const selectedAddressLocalityId = hasEditor ? draft.cliente_direccion_localidad_id : selectedDetail?.cliente_direccion_localidad_id || ''

  const filteredIslands = useMemo(
    () => filterAddressOptions(customerCatalogs.islas, selectedAddressProvinceId),
    [customerCatalogs.islas, selectedAddressProvinceId],
  )
  const filteredMunicipalities = useMemo(
    () => filterAddressOptions(customerCatalogs.municipios, selectedAddressIslandId),
    [customerCatalogs.municipios, selectedAddressIslandId],
  )
  const filteredLocalities = useMemo(
    () => filterAddressOptions(customerCatalogs.localidades, selectedAddressMunicipalityId),
    [customerCatalogs.localidades, selectedAddressMunicipalityId],
  )
  const filteredPostalCodes = useMemo(
    () => filterAddressOptions(customerCatalogs.codigos_postales, selectedAddressMunicipalityId),
    [customerCatalogs.codigos_postales, selectedAddressMunicipalityId],
  )

  const setDraftField = <K extends keyof CustomerDraft>(key: K, value: CustomerDraft[K]) => {
    setDraft((current) => ({ ...current, [key]: value }))
  }

  const openCreateForm = () => {
    setEditorMode('create')
    setFormError('')
    setDraft(emptyCustomerDraft())
    setSelectedCandidateId('')
  }

  const openEditForm = () => {
    if (!selectedDetail) {
      return
    }
    setEditorMode('edit')
    setFormError('')
    setDraft(draftFromDetail(selectedDetail))
  }

  const closeEditor = () => {
    setEditorMode(null)
    setFormError('')
    setSaving(false)
    setDraft(emptyCustomerDraft())
    if (!selectedCandidateId && firstCustomerId) {
      setSelectedCandidateId(firstCustomerId)
    }
  }

  const refreshData = () => {
    setRefreshTick((current) => current + 1)
  }

  const handleDelete = async () => {
    if (!selectedCustomerId) {
      return
    }
    const confirmed = window.confirm('Eliminar cliente')
    if (!confirmed) {
      return
    }

    setSaving(true)
    setFormError('')
    try {
      await deleteCustomer(selectedCustomerId)
      setEditorMode(null)
      setDraft(emptyCustomerDraft())
      setSelectedCandidateId('')
      setRefreshTick((current) => current + 1)
    } catch (error) {
      setFormError(getErrorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const payload = draftToPayload(draft)

    if (!payload.cliente_nombre_comercial) {
      setFormError('El nombre comercial es obligatorio.')
      return
    }

    setSaving(true)
    setFormError('')
    try {
      const saved =
        editorMode === 'create'
          ? await createCustomer(payload)
          : await updateCustomer(selectedCustomerId, payload)
      setEditorMode(null)
      setDraft(emptyCustomerDraft())
      setSelectedCandidateId(saved.cliente_id)
      setRefreshTick((current) => current + 1)
    } catch (error) {
      setFormError(getErrorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  const canEdit = Boolean(selectedDetail) && !hasEditor
  const canDelete = Boolean(selectedCustomerId) && !hasEditor
  const canCreate = !hasEditor

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
                    const islandAbbrev = islandInitialsById.get(normalizeLookupKey(customer.cliente_direccion_isla_id)) || '-'
                    const isSelected = customer.cliente_id === selectedCustomerId

                    return (
                      <button
                        key={customer.cliente_id}
                        type="button"
                        className={`customers-list-row ${isSelected ? 'is-selected' : ''}`}
                        onClick={() => {
                          if (!hasEditor) {
                            setSelectedCandidateId(customer.cliente_id)
                          }
                        }}
                        disabled={hasEditor}
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
            <button type="button" className="customers-action-btn customers-action-btn-primary" disabled={!canCreate} onClick={openCreateForm}>
              + Nuevo
            </button>
            <button type="button" className="customers-action-btn customers-action-btn-outline" disabled={!canEdit} onClick={openEditForm}>
              Editar
            </button>
            <button type="button" className="customers-action-btn customers-action-btn-danger" disabled={!canDelete} onClick={handleDelete}>
              Eliminar
            </button>
            <button type="button" className="customers-action-btn customers-action-btn-ghost" disabled={saving} onClick={refreshData}>
              Refrescar
            </button>
            {hasEditor && (
              <button type="button" className="customers-action-btn customers-action-btn-ghost" onClick={closeEditor}>
                Cancelar
              </button>
            )}
          </div>

          <div className="customers-detail-body customers-detail-main">
            <div className="customers-detail-grid customers-detail-top">
              <section className="customers-detail-card">
                <div className="customers-section-head">
                  <div>
                    <h3>{hasEditor ? (editorMode === 'create' ? 'Nuevo cliente' : 'Editar cliente') : 'Detalle de cliente'}</h3>
                    <p>{hasEditor ? 'Formulario de edicion con persistencia real.' : 'Ficha de consulta con acciones CRUD.'}</p>
                  </div>
                  {!!selectedDetail && !hasEditor && <span className="surface-chip">{statusLabel(selectedDetail.activo)}</span>}
                  {!!hasEditor && <span className="surface-chip">Edicion activa</span>}
                </div>

                {formError && (
                  <div className="state" role="alert">
                    {formError}
                  </div>
                )}

                {hasEditor ? (
                  <form className="customers-field-grid" onSubmit={handleSubmit}>
                    <div className="customers-field-row customers-field-row-top">
                      <label className="customers-field-code">
                        <span>Cod.</span>
                        <input className="input customers-field" readOnly value={draft.cliente_codigo || 'Auto'} />
                      </label>
                      <label className="customers-field-commercial">
                        <span>Nombre comercial</span>
                        <input
                          className="input customers-field"
                          value={draft.cliente_nombre_comercial}
                          onChange={(event) => setDraftField('cliente_nombre_comercial', event.target.value)}
                          placeholder="Nombre comercial"
                          autoComplete="organization"
                        />
                      </label>
                      <label className="customers-field-tax">
                        <span>C.I.F.</span>
                        <input
                          className="input customers-field"
                          value={draft.cliente_cif}
                          onChange={(event) => setDraftField('cliente_cif', event.target.value)}
                          placeholder="CIF"
                          autoComplete="off"
                        />
                      </label>
                    </div>

                    <div className="customers-field-row customers-field-row-mid">
                      <label className="customers-field-phone">
                        <span>Telefono</span>
                        <input
                          className="input customers-field"
                          value={draft.cliente_telefono}
                          onChange={(event) => setDraftField('cliente_telefono', event.target.value)}
                          placeholder="Telefono"
                          autoComplete="tel"
                        />
                      </label>
                      <label className="customers-field-fiscal">
                        <span>Nombre fiscal</span>
                        <input
                          className="input customers-field"
                          value={draft.cliente_nombre_fiscal}
                          onChange={(event) => setDraftField('cliente_nombre_fiscal', event.target.value)}
                          placeholder="Nombre fiscal"
                          autoComplete="organization"
                        />
                      </label>
                    </div>

                    <div className="customers-field-row customers-field-row-mid">
                      <label className="customers-field-commercial">
                        <span>Nombre interno</span>
                        <input
                          className="input customers-field"
                          value={draft.cliente_nombre_interno}
                          onChange={(event) => setDraftField('cliente_nombre_interno', event.target.value)}
                          placeholder="Nombre interno"
                        />
                      </label>
                      <label className="customers-field-fiscal">
                        <span>Abreviatura</span>
                        <input
                          className="input customers-field"
                          value={draft.cliente_abreviatura}
                          onChange={(event) => setDraftField('cliente_abreviatura', event.target.value)}
                          placeholder="Abreviatura"
                        />
                      </label>
                    </div>

                    <div className="customers-field-row customers-field-row-location">
                      <label>
                        <span>Provincia</span>
                        <select
                          className="select customers-field"
                          value={selectedAddressProvinceId}
                          onChange={(event) => {
                            const provinceId = event.target.value
                            setDraft((current) => ({
                              ...current,
                              cliente_direccion_provincia_id: provinceId,
                              cliente_direccion_isla_id: '',
                              cliente_direccion_municipio_id: '',
                              cliente_direccion_localidad_id: '',
                            }))
                          }}
                        >
                          <option value="">Selecciona provincia</option>
                          {customerCatalogs.provincias.map((option) => (
                            <option key={option.id} value={option.id}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        <span>Isla</span>
                        <select
                          className="select customers-field"
                          value={selectedAddressIslandId}
                          onChange={(event) => {
                            const islandId = event.target.value
                            setDraft((current) => ({
                              ...current,
                              cliente_direccion_isla_id: islandId,
                              cliente_direccion_municipio_id: '',
                              cliente_direccion_localidad_id: '',
                            }))
                          }}
                        >
                          <option value="">Selecciona isla</option>
                          {filteredIslands.map((option) => (
                            <option key={option.id} value={option.id}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        <span>Municipio</span>
                        <select
                          className="select customers-field"
                          value={selectedAddressMunicipalityId}
                          onChange={(event) => {
                            const municipalityId = event.target.value
                            setDraft((current) => ({
                              ...current,
                              cliente_direccion_municipio_id: municipalityId,
                              cliente_direccion_localidad_id: '',
                            }))
                          }}
                        >
                          <option value="">Selecciona municipio</option>
                          {filteredMunicipalities.map((option) => (
                            <option key={option.id} value={option.id}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>

                    <div className="customers-field-row customers-field-row-location customers-field-row-location-compact">
                      <label className="customers-field-locality">
                        <span>Localidad</span>
                        <select
                          className="select customers-field"
                          value={selectedAddressLocalityId}
                          onChange={(event) => setDraftField('cliente_direccion_localidad_id', event.target.value)}
                        >
                          <option value="">Selecciona localidad</option>
                          {filteredLocalities.map((option) => (
                            <option key={option.id} value={option.id}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="customers-field-postal">
                        <span>C.P.</span>
                        <input
                          className="input customers-field"
                          value={draft.cliente_direccion_cp}
                          onChange={(event) => setDraftField('cliente_direccion_cp', event.target.value)}
                          placeholder="C.P."
                          list="customer-postal-codes"
                        />
                        <datalist id="customer-postal-codes">
                          {filteredPostalCodes.map((option) => (
                            <option key={option.id} value={option.code || option.label} />
                          ))}
                        </datalist>
                      </label>
                    </div>

                    <div className="customers-field-row customers-field-row-street">
                      <label>
                        <span>Calle</span>
                        <input
                          className="input customers-field"
                          value={draft.cliente_direccion}
                          onChange={(event) => setDraftField('cliente_direccion', event.target.value)}
                          placeholder="Calle"
                          autoComplete="street-address"
                        />
                      </label>
                    </div>

                    <div className="customers-field-row customers-field-row-location">
                      <label>
                        <span>Tipo</span>
                        <input
                          className="input customers-field"
                          value={draft.cliente_tipo}
                          onChange={(event) => setDraftField('cliente_tipo', event.target.value)}
                          placeholder="Tipo de cliente"
                          list="customer-types"
                        />
                        <datalist id="customer-types">
                          {CUSTOMER_TYPES.map((type) => (
                            <option key={type} value={type} />
                          ))}
                        </datalist>
                      </label>
                      <label>
                        <span>Grupo</span>
                        <input
                          className="input customers-field"
                          value={draft.cliente_grupo}
                          onChange={(event) => setDraftField('cliente_grupo', event.target.value)}
                          placeholder="Grupo"
                        />
                      </label>
                      <label>
                        <span>Distribuidor</span>
                        <input
                          className="input customers-field"
                          value={draft.distribuidor_id}
                          onChange={(event) => setDraftField('distribuidor_id', event.target.value)}
                          placeholder="ID distribuidor"
                        />
                      </label>
                    </div>

                    <div className="customers-field-row customers-field-row-location">
                      <label className="customers-prospect-row">
                        <span>Activo</span>
                        <input
                          type="checkbox"
                          checked={draft.activo}
                          onChange={(event) => setDraftField('activo', event.target.checked)}
                        />
                      </label>
                      <label className="customers-prospect-row">
                        <span>Prospeccion</span>
                        <input
                          type="checkbox"
                          checked={draft.cliente_prospeccion}
                          onChange={(event) => setDraftField('cliente_prospeccion', event.target.checked)}
                        />
                      </label>
                      <div className="customers-prospect-row">
                        <span>Estado de edicion</span>
                        <span className={`customers-status-pill ${draft.activo ? 'is-active' : 'is-inactive'}`}>
                          {draft.activo ? 'ACTIVO' : 'INACTIVO'}
                        </span>
                      </div>
                    </div>

                    <div className="customers-detail-actions">
                      <button type="submit" className="customers-action-btn customers-action-btn-primary" disabled={saving}>
                        Guardar
                      </button>
                      <button type="button" className="customers-action-btn customers-action-btn-outline" disabled={saving} onClick={closeEditor}>
                        Cancelar
                      </button>
                    </div>
                  </form>
                ) : (
                  <>
                    {!selectedCustomerId && <div className="state">Selecciona un cliente para ver el detalle.</div>}

                    {!!selectedCustomerId && (
                      <>
                        <QueryState
                          loading={detailQuery.loading}
                          error={detailQuery.error}
                          empty={!selectedDetail}
                          emptyMessage="No se encontro detalle para el cliente seleccionado."
                        />

                        {!!selectedDetail && (
                          <div className="customers-field-grid">
                            <div className="customers-field-row customers-field-row-top">
                              <label className="customers-field-code">
                                <span>Cod.</span>
                                <input className="input customers-field" readOnly value={valueOrDash(selectedDetail.cliente_codigo)} />
                              </label>
                              <label className="customers-field-commercial">
                                <span>Nombre comercial</span>
                                <input className="input customers-field" readOnly value={valueOrDash(selectedDetail.cliente_nombre_comercial)} />
                              </label>
                              <label className="customers-field-tax">
                                <span>C.I.F.</span>
                                <input className="input customers-field" readOnly value={valueOrDash(selectedDetail.cliente_cif)} />
                              </label>
                            </div>

                            <div className="customers-field-row customers-field-row-mid">
                              <label className="customers-field-phone">
                                <span>Telefono</span>
                                <input className="input customers-field" readOnly value={valueOrDash(selectedDetail.cliente_telefono)} />
                              </label>
                              <label className="customers-field-fiscal">
                                <span>Nombre fiscal</span>
                                <input className="input customers-field" readOnly value={valueOrDash(selectedDetail.cliente_nombre_fiscal)} />
                              </label>
                            </div>

                            <div className="customers-field-row customers-field-row-mid">
                              <label className="customers-field-commercial">
                                <span>Nombre interno</span>
                                <input className="input customers-field" readOnly value={valueOrDash(selectedDetail.cliente_nombre_interno)} />
                              </label>
                              <label className="customers-field-fiscal">
                                <span>Abreviatura</span>
                                <input className="input customers-field" readOnly value={valueOrDash(selectedDetail.cliente_abreviatura)} />
                              </label>
                            </div>

                            <div className="customers-field-row customers-field-row-location">
                              <label>
                                <span>Provincia</span>
                                <input
                                  className="input customers-field"
                                  readOnly
                                  value={resolveAddressLabel(selectedDetail.cliente_direccion_provincia_id, provinceNameById)}
                                />
                              </label>
                              <label>
                                <span>Isla</span>
                                <input
                                  className="input customers-field"
                                  readOnly
                                  value={resolveAddressLabel(selectedDetail.cliente_direccion_isla_id, islandNameById)}
                                />
                              </label>
                              <label>
                                <span>Municipio</span>
                                <input
                                  className="input customers-field"
                                  readOnly
                                  value={resolveAddressLabel(selectedDetail.cliente_direccion_municipio_id, municipalityNameById)}
                                />
                              </label>
                            </div>

                            <div className="customers-field-row customers-field-row-location customers-field-row-location-compact">
                              <label className="customers-field-locality">
                                <span>Localidad</span>
                                <input
                                  className="input customers-field"
                                  readOnly
                                  value={resolveAddressLabel(selectedDetail.cliente_direccion_localidad_id, localityNameById)}
                                />
                              </label>
                              <label className="customers-field-postal">
                                <span>C.P.</span>
                                <input className="input customers-field" readOnly value={valueOrDash(selectedDetail.cliente_direccion_cp)} />
                              </label>
                            </div>

                            <div className="customers-field-row customers-field-row-street">
                              <label>
                                <span>Calle</span>
                                <input className="input customers-field" readOnly value={valueOrDash(selectedDetail.cliente_direccion)} />
                              </label>
                            </div>
                          </div>
                        )}
                      </>
                    )}
                  </>
                )}
              </section>

              <aside className="customers-type-panel">
                <div className="customers-section-head">
                  <div>
                    <h3>Tipo de cliente</h3>
                    <p>{hasEditor ? 'Resumen del borrador en curso.' : 'Seleccion read-only con estado limpio.'}</p>
                  </div>
                </div>

                {hasEditor ? (
                  <>
                    <div className="customers-type-grid">
                      {CUSTOMER_TYPES.map((type) => {
                        const isActive = draft.cliente_tipo.toUpperCase() === type
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
                        <input className="input customers-field" readOnly value={valueOrDash(draft.cliente_tipo)} />
                      </label>
                      <label>
                        <span>Abrev. pedido</span>
                        <input className="input customers-field" readOnly value={valueOrDash(draft.cliente_abreviatura)} />
                      </label>
                    </div>

                    <div className="customers-status-row">
                      <span className={`customers-status-pill ${draft.activo ? 'is-active' : 'is-inactive'}`}>{draft.activo ? 'ACTIVO' : 'INACTIVO'}</span>
                      <span className={`customers-status-pill ${draft.activo ? 'is-inactive' : 'is-active'}`}>{draft.activo ? 'INACTIVO' : 'ACTIVO'}</span>
                    </div>

                    <div className="customers-prospect-row">
                      <span>Prospeccion</span>
                      <div className="customers-radio-readonly">
                        <span className={draft.cliente_prospeccion ? 'selected' : ''}>Si</span>
                        <span className={!draft.cliente_prospeccion ? 'selected' : ''}>No</span>
                      </div>
                    </div>
                  </>
                ) : (
                  <>
                    {selectedDetail ? (
                      <>
                        <div className="customers-type-grid">
                          {CUSTOMER_TYPES.map((type) => {
                            const isActive = selectedDetail.cliente_tipo.toUpperCase() === type
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
                            <input className="input customers-field" readOnly value={valueOrDash(selectedDetail.cliente_tipo)} />
                          </label>
                          <label>
                            <span>Abrev. pedido</span>
                            <input className="input customers-field" readOnly value={valueOrDash(selectedDetail.cliente_abreviatura)} />
                          </label>
                        </div>

                        <div className="customers-status-row">
                          <span className={`customers-status-pill ${selectedDetail.activo ? 'is-active' : 'is-inactive'}`}>
                            {selectedDetail.activo ? 'ACTIVO' : 'INACTIVO'}
                          </span>
                          <span className={`customers-status-pill ${selectedDetail.activo ? 'is-inactive' : 'is-active'}`}>
                            {selectedDetail.activo ? 'INACTIVO' : 'ACTIVO'}
                          </span>
                        </div>

                        <div className="customers-prospect-row">
                          <span>Prospeccion</span>
                          <div className="customers-radio-readonly">
                            <span className={selectedDetail.cliente_prospeccion ? 'selected' : ''}>Si</span>
                            <span className={!selectedDetail.cliente_prospeccion ? 'selected' : ''}>No</span>
                          </div>
                        </div>
                      </>
                    ) : (
                      <div className="state customers-empty-panel">Sin datos de cliente para mostrar.</div>
                    )}
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
