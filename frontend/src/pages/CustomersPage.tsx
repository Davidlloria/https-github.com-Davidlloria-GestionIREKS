import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import {
  createCustomer,
  deleteCustomer,
  generateCustomerListing,
  getCustomerAddressCatalogs,
  getCustomerDetail,
  listCustomers,
  updateCustomer,
  type CustomerSavePayload,
} from '../api/customers'
import { listContacts } from '../api/contacts'
import { BinaryToggleSelect } from '../components/BinaryToggleSelect'
import { QueryState } from '../components/QueryState'
import { useAsyncResource } from '../features/useAsyncResource'
import type {
  AddressOption,
  ContactListItem,
  CustomerAddressCatalogsPayload,
  CustomerDetail,
  CustomerListItem,
  CustomerListingResponse,
  PaginatedList,
} from '../types/api'

const PAGE_SIZE = 25

type CustomerTab = 'contacts' | 'sales' | 'recipes' | 'agenda'
type CustomerSortKey = 'code' | 'name' | 'island'
type CustomerEditorMode = 'create' | null
type CustomerDeleteTarget = {
  customerId: string
  customerLabel: string
  customerCode: string | number | null
}

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
  cliente_actividad: string
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

const CUSTOMER_ACTIVITIES = ['PANADERIA', 'PASTELERIA', 'HELADERIA', 'CAFETERIA', 'RESTAURANTE', 'HOTEL']
const CUSTOMER_ACTIVITY_TONES: Record<string, string> = {
  PANADERIA: 'tone-panaderia',
  PASTELERIA: 'tone-pasteleria',
  HELADERIA: 'tone-heladeria',
  CAFETERIA: 'tone-cafeteria',
  RESTAURANTE: 'tone-restaurante',
  HOTEL: 'tone-hotel',
}
const CUSTOMER_ACTIVITY_ICONS: Record<string, string> = {
  PANADERIA: '🥖',
  PASTELERIA: '🧁',
  HELADERIA: '🍦',
  CAFETERIA: '☕',
  RESTAURANTE: '🍽',
  HOTEL: '🏨',
}

const TABS: Array<{ key: CustomerTab; label: string }> = [
  { key: 'contacts', label: 'Contactos' },
  { key: 'sales', label: 'Ventas' },
  { key: 'recipes', label: 'Recetas' },
  { key: 'agenda', label: 'Agenda' },
]

const LISTING_PRESETS = [
  {
    label: 'Clientes activos de Tenerife',
    prompt: 'Clientes activos de Tenerife con contactos principales',
    tone: 'green',
  },
  {
    label: 'Clientes con actividad panadería',
    prompt: 'Clientes con actividad panadería y ventas del último mes',
    tone: 'amber',
  },
  {
    label: 'Clientes con contactos y ventas',
    prompt: 'Clientes con contactos, ventas y recetas relacionadas',
    tone: 'blue',
  },
] as const

const LISTING_TIPS = [
  {
    title: 'Sé específico',
    text: 'Indica filtros, condiciones y valores concretos para obtener mejores resultados.',
    tone: 'blue',
  },
  {
    title: 'Elige columnas clave',
    text: 'Selecciona los campos que realmente necesitas ver en el listado.',
    tone: 'violet',
  },
  {
    title: 'Usa rangos de fechas',
    text: 'Especifica periodos para analizar datos relevantes en el tiempo.',
    tone: 'green',
  },
] as const

function escapeCsvValue(value: string) {
  return `"${value.replace(/"/g, '""')}"`
}

function rowsToCsv(headers: string[], rows: Array<Array<string | number | boolean | null>>) {
  const lines = [headers.map((header) => escapeCsvValue(String(header))).join(',')]
  rows.forEach((row) => {
    lines.push(row.map((cell) => escapeCsvValue(cell === null || cell === undefined ? '-' : String(cell))).join(','))
  })
  return lines.join('\r\n')
}

function customerLabel(customer: { cliente_id: string; cliente_nombre_comercial: string; cliente_nombre_fiscal: string }) {
  return customer.cliente_nombre_comercial || customer.cliente_nombre_fiscal || customer.cliente_id
}

function customerActivityText(customer: { cliente_actividad?: string; cliente_grupo?: string }) {
  return customer.cliente_actividad || customer.cliente_grupo || ''
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

function normalizeActivityKey(value: string) {
  return value
    .trim()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toUpperCase()
}

function splitActivityValues(value: string) {
  return value
    .split(/[\n,;]+/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function customerActivityToneClass(activity: string) {
  return CUSTOMER_ACTIVITY_TONES[normalizeActivityKey(activity)] || 'tone-default'
}

function customerActivityIcon(activity: string) {
  const token = splitActivityValues(activity).find((item) => {
    const normalized = normalizeActivityKey(item)
    return CUSTOMER_ACTIVITIES.some((candidate) => normalizeActivityKey(candidate) === normalized)
  })
  if (token) {
    const matched = CUSTOMER_ACTIVITIES.find((candidate) => normalizeActivityKey(candidate) === normalizeActivityKey(token))
    if (matched) {
      return CUSTOMER_ACTIVITY_ICONS[matched]
    }
  }
  const normalizedActivity = normalizeActivityKey(activity)
  const matchedActivity = CUSTOMER_ACTIVITIES.find((candidate) => normalizeActivityKey(candidate) === normalizedActivity)
  return matchedActivity ? CUSTOMER_ACTIVITY_ICONS[matchedActivity] : '•'
}

function customerActivitySelection(value: string) {
  const tokens = splitActivityValues(value)
  const normalizedTokens = new Set(tokens.map((token) => normalizeActivityKey(token)))

  return CUSTOMER_ACTIVITIES.filter((activity) => normalizedTokens.has(normalizeActivityKey(activity)))
}

function customerActivityValue(value: string) {
  return customerActivitySelection(value).join(', ')
}

function ListingIcon({
  tone,
  className,
}: {
  tone: (typeof LISTING_PRESETS)[number]['tone'] | (typeof LISTING_TIPS)[number]['tone'] | 'chatgpt' | 'close' | 'preview' | 'check' | 'info'
  className?: string
}) {
  const common = { className, 'aria-hidden': true, viewBox: '0 0 24 24', fill: 'none' as const }

  switch (tone) {
    case 'green':
      return (
        <svg {...common}>
          <path d="M16 11.5c0 3.2-2.4 5.8-5.4 5.8S5.2 14.7 5.2 11.5 7.6 5.7 10.6 5.7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
          <path d="M14.2 7.2c.7-1.5 2-2.5 3.5-2.5 2.2 0 4 1.9 4 4.2 0 4.1-5.7 7.6-8.2 9-1 .6-2.3.6-3.4 0-1.6-.8-4.6-2.7-4.6-5.9 0-1.7 1.1-3 2.8-3.6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
          <circle cx="8.3" cy="8.5" r="1.5" stroke="currentColor" strokeWidth="1.8" />
          <circle cx="16.6" cy="17" r="1.5" stroke="currentColor" strokeWidth="1.8" />
        </svg>
      )
    case 'amber':
      return (
        <svg {...common}>
          <path d="M7.5 8.5c0-1.9 1.5-3.5 3.4-3.5 1.2 0 2.3.6 3 1.5.5-1.5 1.8-2.6 3.4-2.6 2 0 3.7 1.6 3.7 3.6 0 1.1-.5 2.1-1.2 2.7L12 20.1 5 11.8c-1-.9-1.5-2-1.5-3.3 0-2 1.5-3.6 3.4-3.6.9 0 1.8.3 2.5 1.1.6.7.9 1.5.1 2.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      )
    case 'blue':
      return (
        <svg {...common}>
          <path d="M5 16.5c1.9-3.4 4.4-5.2 7-5.2 1.8 0 3.2.8 4.1 2.1" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
          <circle cx="8.1" cy="8.3" r="2.4" stroke="currentColor" strokeWidth="1.8" />
          <path d="M14.5 17.4V13m3.2 4.4V11m3.2 6.4v-8.2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
      )
    case 'violet':
      return (
        <svg {...common}>
          <rect x="4.5" y="5" width="15" height="14" rx="3.2" stroke="currentColor" strokeWidth="1.8" />
          <path d="M9 5v14M15 5v14" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
      )
    case 'check':
      return (
        <svg {...common}>
          <path d="M20 6 9 17l-5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      )
    case 'info':
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="8.2" stroke="currentColor" strokeWidth="1.8" />
          <path d="M12 10.5v5M12 7.8h.01" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
      )
    case 'preview':
      return (
        <svg {...common}>
          <path d="M4.5 7.5h15M4.5 12h15M4.5 16.5h15" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
          <path d="M8 4.5v15" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
      )
    case 'chatgpt':
      return (
        <svg {...common}>
          <path d="M12 4.5c1.5 0 2.9.8 3.7 2l1.1-.3c1.6-.4 3.2.5 3.7 2.1.4 1.4-.2 2.9-1.4 3.7l.1 1.2c.2 1.7-.9 3.2-2.6 3.5-1.2.2-2.4-.2-3.2-1l-1 .5c-1.4.8-3.2.7-4.5-.4-1.1-.9-1.6-2.3-1.4-3.6l-.9-.7c-1.4-1.1-1.8-3-1-4.6.7-1.4 2.1-2.2 3.7-2.1l.6-1c.8-1.3 2.2-2 3.8-2Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
          <path d="M8.7 8.5 12 6.6l3.3 1.9v3.8L12 14.2l-3.3-1.9V8.5Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
        </svg>
      )
    case 'close':
      return (
        <svg {...common}>
          <path d="M6 6l12 12M18 6 6 18" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
      )
    default:
      return (
        <svg {...common}>
          <path d="M12 4.5c1.5 0 2.9.8 3.7 2l1.1-.3c1.6-.4 3.2.5 3.7 2.1.4 1.4-.2 2.9-1.4 3.7l.1 1.2c.2 1.7-.9 3.2-2.6 3.5-1.2.2-2.4-.2-3.2-1l-1 .5c-1.4.8-3.2.7-4.5-.4-1.1-.9-1.6-2.3-1.4-3.6l-.9-.7c-1.4-1.1-1.8-3-1-4.6.7-1.4 2.1-2.2 3.7-2.1l.6-1c.8-1.3 2.2-2 3.8-2Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
          <path d="M8.7 8.5 12 6.6l3.3 1.9v3.8L12 14.2l-3.3-1.9V8.5Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
        </svg>
      )
  }
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
    cliente_actividad: '',
    cliente_prospeccion: false,
    distribuidor_id: '',
    activo: true,
  }
}

function draftFromDetail(detail: CustomerDetail): CustomerDraft {
  const customerActivity = customerActivityText(detail)
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
    cliente_actividad: customerActivity,
    cliente_prospeccion: Boolean(detail.cliente_prospeccion),
    distribuidor_id: detail.distribuidor_id || '',
    activo: Boolean(detail.activo),
  }
}

function draftToPayload(draft: CustomerDraft): CustomerSavePayload {
  const customerActivity = customerActivityValue(draft.cliente_actividad)
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
    cliente_actividad: customerActivity,
    cliente_grupo: customerActivity,
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

function PostalCodeField({
  value,
  onChange,
  options,
}: {
  value: string
  onChange: (value: string) => void
  options: AddressOption[]
}) {
  return (
    <label className="customers-field-postal">
      <span>C.P.</span>
      <select
        className="select customers-field"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">Selecciona C.P.</option>
        {options.map((option) => {
          const optionValue = option.code || option.label
          return (
            <option key={option.id} value={optionValue}>
              {optionValue}
            </option>
          )
        })}
      </select>
    </label>
  )
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
  const [syncedDraft, setSyncedDraft] = useState<CustomerDraft>(emptyCustomerDraft())
  const [refreshTick, setRefreshTick] = useState(0)
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<CustomerDeleteTarget | null>(null)
  const [deleteError, setDeleteError] = useState('')
  const [deleting, setDeleting] = useState(false)
  const [listingTarget, setListingTarget] = useState('')
  const [listingError, setListingError] = useState('')
  const [listingResult, setListingResult] = useState<CustomerListingResponse | null>(null)
  const [listingModalOpen, setListingModalOpen] = useState(false)
  const [listingSubmitting, setListingSubmitting] = useState(false)
  const autosaveTimerRef = useRef<number | null>(null)
  const listingsPrintWindowRef = useRef<Window | null>(null)
  const invalidSignatureRef = useRef('')

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

  const islandNameById = useMemo(() => buildAddressLookup(customerCatalogs.islas), [customerCatalogs.islas])
  const islandInitialsById = useMemo(
    () => new Map(customerCatalogs.islas.map((option) => [option.id, option.code || option.label])),
    [customerCatalogs.islas],
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
  const isCreating = editorMode === 'create'
  const selectedAddressProvinceId = draft.cliente_direccion_provincia_id
  const selectedAddressIslandId = draft.cliente_direccion_isla_id
  const selectedAddressMunicipalityId = draft.cliente_direccion_municipio_id
  const selectedAddressLocalityId = draft.cliente_direccion_localidad_id

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

  useEffect(() => {
    if (isCreating || !selectedDetail) {
      return
    }

    const nextDraft = draftFromDetail(selectedDetail)
    setDraft(nextDraft)
    setSyncedDraft(nextDraft)
    setFormError('')
    invalidSignatureRef.current = ''
  }, [isCreating, selectedDetail, selectedCustomerId])

  useEffect(() => {
    if (isCreating || !selectedDetail || !selectedCustomerId) {
      return
    }

    if (autosaveTimerRef.current !== null) {
      window.clearTimeout(autosaveTimerRef.current)
      autosaveTimerRef.current = null
    }

    const nextPayload = draftToPayload(draft)
    const baselinePayload = draftToPayload(syncedDraft)
    const nextSignature = JSON.stringify(nextPayload)
    const baselineSignature = JSON.stringify(baselinePayload)

    if (nextSignature === baselineSignature) {
      invalidSignatureRef.current = ''
      setFormError('')
      return
    }

    if (!nextPayload.cliente_nombre_comercial) {
      if (invalidSignatureRef.current !== nextSignature) {
        invalidSignatureRef.current = nextSignature
        setFormError('El nombre comercial es obligatorio.')
      }
      return
    }

    invalidSignatureRef.current = ''
    autosaveTimerRef.current = window.setTimeout(() => {
      setSaving(true)
      setFormError('')
      updateCustomer(selectedCustomerId, nextPayload)
        .then((saved) => {
          const nextDraft = draftFromDetail(saved)
          setDraft(nextDraft)
          setSyncedDraft(nextDraft)
          setRefreshTick((current) => current + 1)
        })
        .catch((error) => {
          setFormError(getErrorMessage(error))
        })
        .finally(() => {
          setSaving(false)
        })
    }, 650)

    return () => {
      if (autosaveTimerRef.current !== null) {
        window.clearTimeout(autosaveTimerRef.current)
        autosaveTimerRef.current = null
      }
    }
  }, [draft, isCreating, selectedDetail, selectedCustomerId, syncedDraft])

  const setDraftField = <K extends keyof CustomerDraft>(key: K, value: CustomerDraft[K]) => {
    setDraft((current) => ({ ...current, [key]: value }))
  }

  const openCreateForm = () => {
    setEditorMode('create')
    setFormError('')
    const nextDraft = emptyCustomerDraft()
    setDraft(nextDraft)
    setSyncedDraft(nextDraft)
    setSelectedCandidateId('')
  }

  const closeEditor = () => {
    setEditorMode(null)
    setFormError('')
    setSaving(false)
    invalidSignatureRef.current = ''
    const nextDraft = selectedDetail ? draftFromDetail(selectedDetail) : emptyCustomerDraft()
    setDraft(nextDraft)
    setSyncedDraft(nextDraft)
  }

  const openDeleteConfirm = () => {
    if (!selectedCustomerId) {
      return
    }

    const selectedCustomer = customerRows.find((row) => row.cliente_id === selectedCustomerId) || null
    const targetLabel = selectedDetail ? customerLabel(selectedDetail) : selectedCustomer ? customerLabel(selectedCustomer) : selectedCustomerId
    const customerCode = selectedDetail?.cliente_codigo ?? selectedCustomer?.cliente_codigo ?? null

    setDeleteTarget({
      customerId: selectedCustomerId,
      customerLabel: targetLabel,
      customerCode,
    })
    setDeleteError('')
  }

  const closeDeleteConfirm = () => {
    if (deleting) {
      return
    }
    setDeleteTarget(null)
    setDeleteError('')
  }

  const openListingsModal = () => {
    setListingError('')
    setListingResult(null)
    setListingModalOpen(true)
  }

  const closeListingsModal = () => {
    if (listingSubmitting) {
      return
    }
    setListingModalOpen(false)
    setListingError('')
  }

  const downloadListingFile = (filename: string, content: string, mimeType: string) => {
    if (typeof window === 'undefined') {
      return
    }
    const blob = new Blob([content], { type: mimeType })
    const url = window.URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = filename
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    window.URL.revokeObjectURL(url)
  }

  const handleListingCsvExport = () => {
    if (!listingResult?.headers.length || !listingResult.rows.length) {
      return
    }
    const csv = rowsToCsv(listingResult.headers, listingResult.rows)
    downloadListingFile('listado-clientes.csv', csv, 'text/csv;charset=utf-8')
  }

  const handleListingExcelExport = () => {
    if (!listingResult?.headers.length || !listingResult.rows.length) {
      return
    }
    const csv = rowsToCsv(listingResult.headers, listingResult.rows)
    downloadListingFile('listado-clientes.xls', csv, 'application/vnd.ms-excel;charset=utf-8')
  }

  const handleListingPdfExport = () => {
    if (!listingResult?.headers.length || !listingResult.rows.length || typeof window === 'undefined') {
      return
    }

    const tableRows = listingResult.rows
      .map((row) => `<tr>${row.map((cell) => `<td>${cell === null || cell === undefined || cell === '' ? '-' : String(cell)}</td>`).join('')}</tr>`)
      .join('')
    const headers = listingResult.headers.map((header) => `<th>${header}</th>`).join('')
    const html = `
      <html>
        <head>
          <title>${listingResult.title || 'Listado de clientes'}</title>
          <style>
            body { font-family: Arial, sans-serif; margin: 24px; color: #1f2937; }
            h1 { font-size: 20px; margin: 0 0 8px; }
            p { margin: 0 0 16px; color: #64748b; }
            table { width: 100%; border-collapse: collapse; font-size: 12px; }
            th, td { border: 1px solid #dbe4f0; padding: 8px 10px; text-align: left; vertical-align: top; }
            th { background: #eef4ff; color: #1d4ed8; }
          </style>
        </head>
        <body>
          <h1>${listingResult.title || 'Listado de clientes'}</h1>
          <p>${listingResult.source || 'interprete local'}</p>
          <table>
            <thead><tr>${headers}</tr></thead>
            <tbody>${tableRows}</tbody>
          </table>
        </body>
      </html>
    `

    const printWindow = window.open('', '_blank', 'noopener,noreferrer,width=1200,height=800')
    if (!printWindow) {
      return
    }
    listingsPrintWindowRef.current = printWindow
    printWindow.document.open()
    printWindow.document.write(html)
    printWindow.document.close()
    printWindow.focus()
    setTimeout(() => {
      printWindow.print()
    }, 250)
  }

  const handleListingPrint = () => {
    if (!listingResult?.headers.length || !listingResult.rows.length || typeof window === 'undefined') {
      return
    }
    handleListingPdfExport()
  }

  const handleListingSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    const prompt = listingTarget.trim()
    if (!prompt) {
      setListingError('Escribe primero qué listado necesitas.')
      return
    }

    setListingSubmitting(true)
    setListingError('')

    try {
      // La integración real con ChatGPT se conectará en el siguiente paso.
      setListingModalOpen(false)
      setListingTarget('')
    } catch (error) {
      setListingError(getErrorMessage(error))
    } finally {
      setListingSubmitting(false)
    }
  }

  const handleListingSubmitV2 = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    const prompt = listingTarget.trim()
    if (!prompt) {
      setListingError('Escribe primero qué listado necesitas.')
      return
    }

    setListingSubmitting(true)
    setListingError('')

    try {
      const result = await generateCustomerListing(prompt)
      setListingResult(result)
    } catch (error) {
      setListingError(getErrorMessage(error))
    } finally {
      setListingSubmitting(false)
    }
  }

  void handleListingSubmit

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) {
      return
    }

    setDeleting(true)
    setDeleteError('')
    setFormError('')
    try {
      await deleteCustomer(deleteTarget.customerId)
      setDeleteTarget(null)
      setEditorMode(null)
      const nextDraft = emptyCustomerDraft()
      setDraft(nextDraft)
      setSyncedDraft(nextDraft)
      setSelectedCandidateId('')
      setRefreshTick((current) => current + 1)
    } catch (error) {
      setDeleteError(getErrorMessage(error))
    } finally {
      setDeleting(false)
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
      const saved = await createCustomer(payload)
      setEditorMode(null)
      const nextDraft = draftFromDetail(saved)
      setDraft(nextDraft)
      setSyncedDraft(nextDraft)
      setSelectedCandidateId(saved.cliente_id)
      setRefreshTick((current) => current + 1)
    } catch (error) {
      setFormError(getErrorMessage(error))
    } finally {
      setSaving(false)
    }
  }

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

          <div className="customers-list-actions">
            <button type="button" className="customers-action-btn customers-action-btn-primary" disabled={isCreating} onClick={openCreateForm}>
              <span className="customers-action-btn-icon" aria-hidden="true">
                +
              </span>
              <span>Nuevo</span>
            </button>
            <button type="button" className="customers-action-btn customers-action-btn-danger" disabled={isCreating || !selectedCustomerId} onClick={openDeleteConfirm}>
              <span className="customers-action-btn-icon" aria-hidden="true">
                🗑
              </span>
              <span>Eliminar</span>
            </button>
            <button type="button" className="customers-action-btn customers-action-btn-ghost" onClick={openListingsModal}>
              <span className="customers-action-btn-icon" aria-hidden="true">
                📄
              </span>
              <span>Listados</span>
            </button>
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
            {customersQuery.loading && (
              <div className="customers-loading-toast" role="status" aria-live="polite" aria-label="Cargando clientes">
                <span className="customers-loading-spinner" aria-hidden="true" />
                <div className="customers-loading-copy">
                  <strong>Cargando clientes</strong>
                  <span>Actualizando listado...</span>
                </div>
                <div className="customers-loading-bar" aria-hidden="true">
                  <span />
                </div>
              </div>
            )}

            {!customersQuery.loading && customersQuery.error && (
              <div className="state state-error" role="alert">
                Error: {customersQuery.error}
              </div>
            )}

            {!customersQuery.loading && !customersQuery.error && !sortedCustomerRows.length && (
              <div className="state state-empty" role="status">
                No hay clientes para los filtros actuales.
              </div>
            )}

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
                          if (!isCreating) {
                            setSelectedCandidateId(customer.cliente_id)
                          }
                        }}
                        disabled={isCreating}
                      >
                        <span className="customers-list-cell">{customer.cliente_codigo}</span>
                        <span className="customers-list-cell customers-list-cell-name">
                          <span className="customers-list-cell-icon" aria-hidden="true">
                            {customerActivityIcon(customerActivityText(customer) || customer.cliente_tipo || customer.cliente_nombre_comercial)}
                          </span>
                          <span>{customerLabel(customer)}</span>
                        </span>
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

        <section className={`customers-detail-panel ${isCreating ? 'is-create-flow' : ''}`} hidden={isCreating}>
          <div className="customers-detail-body customers-detail-main">
            <div className="customers-detail-grid customers-detail-top">
              <section className="customers-detail-card">
                <div className="customers-section-head">
                  <div>
                    <h3>{isCreating ? 'Nuevo cliente' : 'Detalle de cliente'}</h3>
                  </div>
                  {!!selectedDetail && !isCreating && (
                    <span
                      className={`surface-chip customers-status-chip ${selectedDetail.activo ? 'is-active' : 'is-inactive'}`}
                    >
                      {saving ? 'Guardando...' : statusLabel(selectedDetail.activo)}
                    </span>
                  )}
                  {isCreating && <span className="surface-chip">Alta activa</span>}
                </div>

                {formError && (
                  <div className="state" role="alert">
                    {formError}
                  </div>
                )}

                {isCreating || selectedDetail ? (
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

                    <div className="customers-field-divider" aria-hidden="true" />

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
                      <PostalCodeField value={draft.cliente_direccion_cp} onChange={(nextValue) => setDraftField('cliente_direccion_cp', nextValue)} options={filteredPostalCodes} />
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

                            <div className="customers-field-divider" aria-hidden="true" />

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
                              <PostalCodeField value={draft.cliente_direccion_cp} onChange={(nextValue) => setDraftField('cliente_direccion_cp', nextValue)} options={filteredPostalCodes} />
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

                            {isCreating && (
                              <div className="customers-detail-actions">
                                <button type="submit" className="customers-action-btn customers-action-btn-primary" disabled={saving}>
                                  Guardar
                                </button>
                                <button type="button" className="customers-action-btn customers-action-btn-outline" disabled={saving} onClick={closeEditor}>
                                  Cancelar
                                </button>
                              </div>
                            )}
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
                    <h3>Clasificación del cliente</h3>
                    <span className="customers-type-subhead">Actividad</span>
                  </div>
                </div>

                {isCreating || selectedDetail ? (
                  <>
                    <div className="customers-type-grid">
                      {CUSTOMER_ACTIVITIES.map((activity) => {
                        const isActive = customerActivitySelection(draft.cliente_actividad).includes(activity)
                        return (
                          <button
                            key={activity}
                            type="button"
                            className={`customer-type-pill ${customerActivityToneClass(activity)} ${isActive ? 'active' : ''}`}
                            aria-pressed={isActive}
                            disabled={saving}
                            onClick={() => {
                              const nextSelection = customerActivitySelection(draft.cliente_actividad)
                              const nextSet = new Set(nextSelection)
                              if (nextSet.has(activity)) {
                                nextSet.delete(activity)
                              } else {
                                nextSet.add(activity)
                              }
                              setDraftField(
                                'cliente_actividad',
                                CUSTOMER_ACTIVITIES.filter((item) => nextSet.has(item)).join(', '),
                              )
                            }}
                          >
                            <span className="customer-type-pill-icon" aria-hidden="true">
                              {customerActivityIcon(activity)}
                            </span>
                            <span className="customer-type-pill-label">{activity}</span>
                            {isActive && <span className="customer-type-pill-check">✓</span>}
                          </button>
                        )
                      })}
                    </div>

                    <div className="customers-type-divider" aria-hidden="true" />

                    <div className="customers-type-fields">
                      <div className="customers-binary-row">
                        <span>Tipo</span>
                        <BinaryToggleSelect
                          value={draft.cliente_tipo.toUpperCase() === 'DIRECTO'}
                          onChange={(nextValue) => setDraftField('cliente_tipo', nextValue ? 'DIRECTO' : 'INDIRECTO')}
                          trueLabel="DIREC."
                          falseLabel="INDIR."
                          disabled={saving}
                          ariaLabel="Tipo de cliente"
                        />
                      </div>
                    </div>

                    <div className="customers-type-divider" aria-hidden="true" />

                    <div className="customers-binary-row">
                      <span>Estado</span>
                      <BinaryToggleSelect
                        value={draft.activo}
                        onChange={(nextValue) => setDraftField('activo', nextValue)}
                        trueLabel="ACTI."
                        falseLabel="INACT."
                        disabled={saving}
                        ariaLabel="Estado del cliente"
                        className="binary-toggle-select--customer-status"
                      />
                    </div>

                    <div className="customers-type-divider" aria-hidden="true" />

                    <div className="customers-binary-row customers-prospect-row">
                      <span>Prospección</span>
                      <BinaryToggleSelect
                        value={draft.cliente_prospeccion}
                        onChange={(nextValue) => setDraftField('cliente_prospeccion', nextValue)}
                        trueLabel="SI"
                        falseLabel="NO"
                        disabled={saving}
                        ariaLabel="Prospección"
                        className="binary-toggle-select--customer-prospect"
                      />
                    </div>
                  </>
                ) : (
                  <>
                    {selectedDetail ? (
                      <>
                        <div className="customers-type-grid">
                          {CUSTOMER_ACTIVITIES.map((activity) => {
                            const isActive = customerActivitySelection(draft.cliente_actividad).includes(activity)
                            return (
                              <button
                                key={activity}
                                type="button"
                                className={`customer-type-pill ${customerActivityToneClass(activity)} ${isActive ? 'active' : ''}`}
                                aria-pressed={isActive}
                                disabled
                              >
                                <span className="customer-type-pill-icon" aria-hidden="true">
                                  {customerActivityIcon(activity)}
                                </span>
                                <span className="customer-type-pill-label">{activity}</span>
                                {isActive && <span className="customer-type-pill-check">✓</span>}
                              </button>
                            )
                          })}
                        </div>

                        <div className="customers-type-fields">
                          <label>
                            <span>Actividad</span>
                            <input className="input customers-field" readOnly value={valueOrDash(draft.cliente_actividad)} />
                          </label>
                          <label>
                            <span>Tipo</span>
                            <input className="input customers-field" readOnly value={valueOrDash(draft.cliente_tipo)} />
                          </label>
                        </div>

                        <div className="customers-status-row">
                          <span className={`customers-status-pill ${draft.activo ? 'is-active' : 'is-inactive'}`}>
                            {draft.activo ? 'ACTIVO' : 'INACTIVO'}
                          </span>
                          <span className={`customers-status-pill ${draft.activo ? 'is-inactive' : 'is-active'}`}>
                            {draft.activo ? 'INACTIVO' : 'ACTIVO'}
                          </span>
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

      {listingModalOpen && (
        <div className="customers-modal-overlay" role="presentation">
          <div
            className="customers-modal customers-modal-listings"
            role="dialog"
            aria-modal="true"
            aria-labelledby="customers-listings-modal-title"
          >
            <div className="customers-modal-head customers-listings-head">
              <div className="customers-listings-head-copy">
                <h3 id="customers-listings-modal-title">Listados asistidos</h3>
                <p>Describe el listado que necesitas y generaremos la consulta automáticamente.</p>
              </div>
              <div className="customers-listings-head-actions">
                <span className="surface-chip customers-status-chip customers-listings-chatgpt-chip is-active">
                  <ListingIcon tone="chatgpt" className="customers-listings-chatgpt-icon" />
                  ChatGPT
                </span>
                <button
                  type="button"
                  className="customers-listings-close"
                  aria-label="Cerrar"
                  onClick={closeListingsModal}
                  disabled={listingSubmitting}
                >
                  <ListingIcon tone="close" className="customers-listings-close-icon" />
                </button>
              </div>
            </div>

            <form className="customers-modal-body customers-listings-body customers-listings-layout" onSubmit={handleListingSubmitV2}>
              <label className="customers-listings-field">
                <span className="customers-listings-section-label">Solicitud</span>
                <textarea
                  className="input customers-listings-textarea"
                  value={listingTarget}
                  onChange={(event) => setListingTarget(event.target.value)}
                  placeholder="Escribe el listado que quieres generar..."
                  rows={2}
                />
              </label>

              <div className="customers-listings-ribbon">
                <div className="customers-listings-ribbon-head">
                  <ListingIcon tone="preview" className="customers-listings-help-head-icon" />
                  <span>Exportar listado</span>
                </div>
                <div className="customers-listings-export-actions customers-listings-export-actions-ribbon">
                  <button type="button" className="customers-listings-export-btn" onClick={handleListingPrint} disabled={!listingResult?.rows.length}>
                    Imprimir
                  </button>
                  <button type="button" className="customers-listings-export-btn" onClick={handleListingPdfExport} disabled={!listingResult?.rows.length}>
                    PDF
                  </button>
                  <button type="button" className="customers-listings-export-btn" onClick={handleListingExcelExport} disabled={!listingResult?.rows.length}>
                    Excel
                  </button>
                  <button type="button" className="customers-listings-export-btn" onClick={handleListingCsvExport} disabled={!listingResult?.rows.length}>
                    CSV
                  </button>
                </div>
              </div>

              <div className="customers-listings-help-note customers-listings-ribbon-note">
                <ListingIcon tone="info" className="customers-listings-help-note-icon" />
                <span>Puedes usar datos de clientes, contactos, ventas, recetas y más.</span>
              </div>

              <div className="customers-listings-result">
                <div className="customers-listings-result-head">
                  <div>
                    <strong>{listingResult?.title || 'Listado de clientes'}</strong>
                    <span>{listingResult?.source || 'Vista previa del listado'}</span>
                  </div>
                  <span className={`surface-chip customers-status-chip ${listingResult ? 'is-active' : 'is-inactive'}`}>
                    {listingResult ? (
                      <>
                        <ListingIcon tone="check" className="customers-listings-status-icon" />
                        Listo
                      </>
                    ) : (
                      <>
                        <ListingIcon tone="info" className="customers-listings-status-icon" />
                        Pendiente
                      </>
                    )}
                  </span>
                </div>

                {listingResult?.rows.length ? (
                  <div className="customers-listings-table-wrap">
                    <table className="customers-listings-table">
                      <thead>
                        <tr>
                          {listingResult.headers.map((header) => (
                            <th key={header}>{header}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {listingResult.rows.slice(0, 5).map((row, rowIndex) => (
                          <tr key={rowIndex}>
                            {row.map((cell, cellIndex) => (
                              <td key={`${rowIndex}-${cellIndex}`}>{cell === null || cell === undefined || cell === '' ? '-' : String(cell)}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="customers-listings-result-empty">
                    <ListingIcon tone="preview" className="customers-listings-help-note-icon" />
                    <p className="customers-listings-result-message">Aquí aparecerá el listado generado. Escribe una solicitud y pulsa Generar listado.</p>
                  </div>
                )}

                <div className="customers-listings-result-footer">
                  <span>
                    {listingResult?.rows.length
                      ? `Mostrando ${Math.min(5, listingResult.rows.length)} de +${listingResult.rows.length} resultados`
                      : 'Todavía no se ha generado ningún listado'}
                  </span>
                  <span>Los resultados completos se descargarán al generar el listado.</span>
                </div>
              </div>

              {listingError && (
                <div className="state" role="alert">
                  {listingError}
                </div>
              )}

              <div className="customers-listings-footer-actions">
                <div className="customers-detail-actions customers-modal-actions customers-listings-actions">
                  <button type="submit" className="customers-action-btn customers-action-btn-primary" disabled={listingSubmitting}>
                    {listingSubmitting ? 'Preparando...' : 'Generar listado'}
                  </button>
                  <button type="button" className="customers-action-btn customers-action-btn-outline" disabled={listingSubmitting} onClick={closeListingsModal}>
                    Cancelar
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {deleteTarget && (
        <div className="customers-modal-overlay" role="presentation">
          <div
            className="customers-modal customers-modal-confirm"
            role="dialog"
            aria-modal="true"
            aria-labelledby="customers-delete-modal-title"
          >
            <div className="customers-modal-head">
              <div>
                <h3 id="customers-delete-modal-title">Eliminar cliente</h3>
                <p>Confirma si quieres borrar este registro de la base de datos.</p>
              </div>
              <span className="surface-chip customers-status-chip is-inactive">Confirmación</span>
            </div>

            <div className="customers-delete-summary">
              <div>
                <span className="customers-delete-summary-label">Registro seleccionado</span>
                <strong>{deleteTarget.customerLabel}</strong>
              </div>
              <div className="customers-delete-summary-grid">
                <span className="customers-delete-summary-label">Código</span>
                <span>{deleteTarget.customerCode ?? '-'}</span>
              </div>
            </div>

            {deleteError && (
              <div className="state" role="alert">
                {deleteError}
              </div>
            )}

            <div className="customers-detail-actions customers-modal-actions customers-delete-actions">
              <button type="button" className="customers-action-btn customers-action-btn-danger" disabled={deleting} onClick={handleDeleteConfirm}>
                {deleting ? 'Eliminando...' : 'Eliminar'}
              </button>
              <button type="button" className="customers-action-btn customers-action-btn-outline" disabled={deleting} onClick={closeDeleteConfirm}>
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}

      {isCreating && (
        <div className="customers-modal-overlay" role="presentation">
          <div
            className="customers-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="customers-create-modal-title"
          >
            <div className="customers-modal-head">
              <div>
                <h3 id="customers-create-modal-title">Nuevo cliente</h3>
                <p>Introduce los datos del cliente y guarda para crear el registro en la base de datos.</p>
              </div>
              <span className="surface-chip">Alta activa</span>
            </div>

            <form className="customers-modal-body" onSubmit={handleSubmit}>
              <div className="customers-detail-grid customers-detail-top">
                <section className="customers-detail-card">
                  <div className="customers-section-head">
                    <div>
                      <h3>Detalle de cliente</h3>
                    </div>
                    <span className="surface-chip customers-status-chip is-active">Activo</span>
                  </div>

                  {formError && (
                    <div className="state" role="alert">
                      {formError}
                    </div>
                  )}

                  <div className="customers-field-grid">
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

                    <div className="customers-field-divider" aria-hidden="true" />

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
                      <PostalCodeField value={draft.cliente_direccion_cp} onChange={(nextValue) => setDraftField('cliente_direccion_cp', nextValue)} options={filteredPostalCodes} />
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

                    <div className="customers-detail-actions customers-modal-actions">
                      <button type="submit" className="customers-action-btn customers-action-btn-primary" disabled={saving}>
                        Guardar
                      </button>
                      <button type="button" className="customers-action-btn customers-action-btn-outline" disabled={saving} onClick={closeEditor}>
                        Cancelar
                      </button>
                    </div>
                  </div>
                </section>

                <aside className="customers-type-panel">
                  <div className="customers-section-head">
                    <div>
                      <h3>Clasificación del cliente</h3>
                      <span className="customers-type-subhead">Actividad</span>
                    </div>
                  </div>

                  <div className="customers-type-grid">
                    {CUSTOMER_ACTIVITIES.map((activity) => {
                      const isActive = customerActivitySelection(draft.cliente_actividad).includes(activity)
                      return (
                        <button
                          key={activity}
                          type="button"
                          className={`customer-type-pill ${customerActivityToneClass(activity)} ${isActive ? 'active' : ''}`}
                          aria-pressed={isActive}
                          disabled={saving}
                          onClick={() => {
                            const nextSelection = customerActivitySelection(draft.cliente_actividad)
                            const nextSet = new Set(nextSelection)
                            if (nextSet.has(activity)) {
                              nextSet.delete(activity)
                            } else {
                              nextSet.add(activity)
                            }
                            setDraftField(
                              'cliente_actividad',
                              CUSTOMER_ACTIVITIES.filter((item) => nextSet.has(item)).join(', '),
                            )
                          }}
                        >
                          <span className="customer-type-pill-icon" aria-hidden="true">
                            {customerActivityIcon(activity)}
                          </span>
                          <span className="customer-type-pill-label">{activity}</span>
                          {isActive && <span className="customer-type-pill-check">✓</span>}
                        </button>
                      )
                    })}
                  </div>

                  <div className="customers-type-divider" aria-hidden="true" />

                  <div className="customers-type-fields">
                    <div className="customers-binary-row">
                      <span>Tipo</span>
                      <BinaryToggleSelect
                        value={draft.cliente_tipo.toUpperCase() === 'DIRECTO'}
                        onChange={(nextValue) => setDraftField('cliente_tipo', nextValue ? 'DIRECTO' : 'INDIRECTO')}
                        trueLabel="DIREC."
                        falseLabel="INDIR."
                        disabled={saving}
                        ariaLabel="Tipo de cliente"
                      />
                    </div>
                  </div>

                  <div className="customers-type-divider" aria-hidden="true" />

                  <div className="customers-binary-row">
                    <span>Estado</span>
                    <BinaryToggleSelect
                      value={draft.activo}
                      onChange={(nextValue) => setDraftField('activo', nextValue)}
                      trueLabel="ACTI."
                      falseLabel="INACT."
                      disabled={saving}
                      ariaLabel="Estado del cliente"
                      className="binary-toggle-select--customer-status"
                    />
                  </div>

                  <div className="customers-type-divider" aria-hidden="true" />

                  <div className="customers-binary-row customers-prospect-row">
                    <span>Prospección</span>
                    <BinaryToggleSelect
                      value={draft.cliente_prospeccion}
                      onChange={(nextValue) => setDraftField('cliente_prospeccion', nextValue)}
                      trueLabel="SI"
                      falseLabel="NO"
                      disabled={saving}
                      ariaLabel="Prospección"
                      className="binary-toggle-select--customer-prospect"
                    />
                  </div>
                </aside>
              </div>
            </form>
          </div>
        </div>
      )}
    </section>
  )
}
