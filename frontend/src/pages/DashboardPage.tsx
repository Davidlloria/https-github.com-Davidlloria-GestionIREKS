import { useMemo } from 'react'
import { getCustomerAddressCatalogs, listCustomers } from '../api/customers'
import { useAsyncResource } from '../features/useAsyncResource'
import type { ViewKey } from '../components/SidebarNav'
import type { CustomerAddressCatalogsPayload, CustomerListItem } from '../types/api'

interface DashboardPageProps {
  onChangeView: (view: ViewKey) => void
}

const quickActions: Array<{ view: ViewKey; label: string; tone: string }> = [
  { view: 'customers', label: 'Clientes', tone: 'blue' },
  { view: 'contacts', label: 'Contactos', tone: 'purple' },
  { view: 'orders', label: 'Pedidos', tone: 'orange' },
  { view: 'sales', label: 'Ventas', tone: 'green' },
  { view: 'warehouse', label: 'Almacén', tone: 'emerald' },
  { view: 'recipes', label: 'Recetas', tone: 'violet' },
  { view: 'ingredients', label: 'Ingredientes', tone: 'leaf' },
  { view: 'courses', label: 'Cursos', tone: 'amber' },
  { view: 'settings', label: 'Configuración', tone: 'slate' },
]

const DASHBOARD_CUSTOMERS_PAGE_SIZE = 250

async function listAllCustomers() {
  const firstPage = await listCustomers('', DASHBOARD_CUSTOMERS_PAGE_SIZE, 0)
  const items = [...firstPage.items]
  let offset = items.length

  while (offset < firstPage.total) {
    const page = await listCustomers('', DASHBOARD_CUSTOMERS_PAGE_SIZE, offset)
    if (!page.items.length) {
      break
    }
    items.push(...page.items)
    offset += page.items.length
    if (page.items.length < DASHBOARD_CUSTOMERS_PAGE_SIZE) {
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

function normalizeKey(value: string | null | undefined) {
  return value?.trim() ?? ''
}

function deriveIslandCode(label: string) {
  const cleanLabel = label.trim()
  if (!cleanLabel) {
    return '--'
  }

  const normalized = cleanLabel.toLowerCase()
  if (normalized.includes('fuerteventura')) {
    return 'FV'
  }
  if (normalized.includes('gran canaria')) {
    return 'GC'
  }
  if (normalized.includes('lanzarote')) {
    return 'LZ'
  }
  if (normalized.includes('la palma')) {
    return 'LP'
  }
  if (normalized.includes('la gomera')) {
    return 'LG'
  }
  if (normalized.includes('tenerife')) {
    return 'TF'
  }

  const words = cleanLabel.split(/[\s-]+/).filter(Boolean)
  if (words.length === 1) {
    return words[0].slice(0, 2).toUpperCase()
  }

  return words.map((word) => word[0]).join('').slice(0, 2).toUpperCase()
}

function normalizeIslandCode(code: string | null | undefined, label: string) {
  const normalizedCode = (code ?? '').trim().toUpperCase()
  const normalizedLabel = label.trim().toLowerCase()

  if (normalizedLabel.includes('fuerteventura') || normalizedCode === 'FUERTEVENTURA') {
    return 'FV'
  }
  if (normalizedLabel.includes('gran canaria') || normalizedCode === 'GRAN CANARIA') {
    return 'GC'
  }
  if (normalizedLabel.includes('lanzarote') || normalizedCode === 'LANZAROTE') {
    return 'LZ'
  }
  if (normalizedLabel.includes('la palma') || normalizedCode === 'LA PALMA') {
    return 'LP'
  }
  if (normalizedLabel.includes('la gomera') || normalizedCode === 'LA GOMERA') {
    return 'LG'
  }
  if (normalizedLabel.includes('tenerife') || normalizedCode === 'TENERIFE') {
    return 'TF'
  }

  return normalizedCode || deriveIslandCode(label)
}

function islandBadgeStyle(code: string) {
  switch (code) {
    case 'FV':
      return {
        background: 'linear-gradient(180deg, #fb7185 0%, #e11d48 100%)',
        color: '#ffffff',
      }
    case 'TF':
      return {
        background: 'linear-gradient(180deg, #4f84ff 0%, #316fee 100%)',
        color: '#ffffff',
      }
    case 'GC':
      return {
        background: 'linear-gradient(180deg, #6ad180 0%, #3dc16a 100%)',
        color: '#ffffff',
      }
    case 'LZ':
      return {
        background: 'linear-gradient(180deg, #ffb02c 0%, #f59e0b 100%)',
        color: '#ffffff',
      }
    case 'LP':
      return {
        background: 'linear-gradient(180deg, #7d70ff 0%, #6366f1 100%)',
        color: '#ffffff',
      }
    case 'LG':
      return {
        background: 'linear-gradient(180deg, #28c6d9 0%, #18b7cc 100%)',
        color: '#ffffff',
      }
    default:
      return {
        background: 'linear-gradient(180deg, #94a3b8 0%, #64748b 100%)',
        color: '#ffffff',
      }
  }
}

function formatNumber(value: number) {
  return new Intl.NumberFormat('es-ES').format(value)
}

function percentage(value: number, total: number) {
  if (!total) {
    return 0
  }
  return (value / total) * 100
}

function formatPercent(value: number) {
  return `${value.toFixed(1).replace('.', ',')}%`
}

function DashboardIcon({ tone }: { tone: string }) {
  const common = {
    'aria-hidden': true,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: '1.8',
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
  }

  switch (tone) {
    case 'orange':
      return (
        <svg {...common}>
          <path d="M4 19V5" />
          <path d="M4 19h16" />
          <path d="M7 15l4-5 3 3 4-6" />
        </svg>
      )
    case 'purple':
      return (
        <svg {...common}>
          <circle cx="9" cy="8" r="3" />
          <path d="M4 19v-1a5 5 0 0 1 5-5h0a5 5 0 0 1 5 5v1" />
          <path d="M15 7h5" />
          <path d="M17.5 4.5v5" />
        </svg>
      )
    case 'emerald':
      return (
        <svg {...common}>
          <path d="M12 3l7 4v10l-7 4-7-4V7z" />
          <path d="M12 7v10" />
          <path d="M9 10h6" />
        </svg>
      )
    case 'violet':
      return (
        <svg {...common}>
          <path d="M7 4h10v16H7z" />
          <path d="M9 8h6M9 12h6M9 16h4" />
        </svg>
      )
    case 'leaf':
      return (
        <svg {...common}>
          <path d="M20 4c-7 1-12 6-12 12a8 8 0 0 0 8 4c0-6 4-11 4-16z" />
          <path d="M9 15c2-1 4-3 6-6" />
        </svg>
      )
    case 'amber':
      return (
        <svg {...common}>
          <path d="M4 8l8-4 8 4-8 4-8-4z" />
          <path d="M7 10v4c0 1.7 2.2 3 5 3s5-1.3 5-3v-4" />
        </svg>
      )
    case 'slate':
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="3.2" />
          <path d="M19 12a7 7 0 0 0-.08-1l1.76-1.36-1.9-3.29-2.12.72a7 7 0 0 0-1.73-1l-.32-2.19h-3.8l-.32 2.2a7 7 0 0 0-1.73 1l-2.12-.73-1.9 3.29L5.08 11A7 7 0 0 0 5 12c0 .34.03.67.08 1l-1.76 1.36 1.9 3.29 2.12-.72a7 7 0 0 0 1.73 1l.32 2.19h3.8l.32-2.2a7 7 0 0 0 1.73-1l2.12.73 1.9-3.29L18.92 13c.05-.33.08-.66.08-1Z" />
        </svg>
      )
    case 'green':
      return (
        <svg {...common}>
          <path d="M4 19V5" />
          <path d="M4 19h16" />
          <path d="M7 15v-5" />
          <path d="M11 15V9" />
          <path d="M15 15v-7" />
        </svg>
      )
    case 'blue':
    default:
      return (
        <svg {...common}>
          <path d="M12 4v16" />
          <path d="M4 12h16" />
          <path d="M7 15V9" />
          <path d="M17 15V6" />
        </svg>
      )
  }
}

function DashboardClientsIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M16.5 11a3.5 3.5 0 1 0-3.5-3.5 3.5 3.5 0 0 0 3.5 3.5Z" />
      <path d="M8 12a4 4 0 1 0-4-4 4 4 0 0 0 4 4Z" />
      <path d="M3 20v-1.5A4.5 4.5 0 0 1 7.5 14h1A4.5 4.5 0 0 1 13 18.5V20" />
      <path d="M12.5 20v-1.1A4.2 4.2 0 0 1 16.7 14h.6a4.7 4.7 0 0 1 4.7 4.7V20" />
    </svg>
  )
}

function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="dashboard-empty-state">
      <strong>{title}</strong>
      <p>{description}</p>
    </div>
  )
}

function DashboardClientKpi() {
  const customersQuery = useAsyncResource(
    () => listAllCustomers(),
    { items: [], total: 0, limit: DASHBOARD_CUSTOMERS_PAGE_SIZE, offset: 0 },
    [],
  )
  const catalogsQuery = useAsyncResource(
    () => getCustomerAddressCatalogs(),
    { provincias: [], islas: [], municipios: [], codigos_postales: [], localidades: [] } as CustomerAddressCatalogsPayload,
    [],
  )

  const summary = useMemo(() => {
    const customers = customersQuery.data.items
    const countsByIslandId = new Map<string, number>()

    customers.forEach((customer: CustomerListItem) => {
      const islandId = normalizeKey(customer.cliente_direccion_isla_id)
      if (!islandId) {
        return
      }
      countsByIslandId.set(islandId, (countsByIslandId.get(islandId) || 0) + 1)
    })

    const islands = catalogsQuery.data.islas
      .map((island) => {
        const count = countsByIslandId.get(island.id) || 0
        const code = normalizeIslandCode(island.code, island.label)
        return {
          id: island.id,
          code,
          label: island.label,
          count,
        }
      })
      .filter((island) => island.count > 0)
      .sort((left, right) => {
        if (right.count !== left.count) {
          return right.count - left.count
        }
        return left.code.localeCompare(right.code, 'es', { sensitivity: 'base', numeric: true })
      })

    const total = customers.length
    const islandsWithCustomers = islands.filter((island) => island.count > 0).length
    const loading = customersQuery.loading || catalogsQuery.loading
    const error = customersQuery.error || catalogsQuery.error

    return { total, islands, islandsWithCustomers, loading, error }
  }, [catalogsQuery.data.islas, catalogsQuery.error, catalogsQuery.loading, customersQuery.data.items, customersQuery.error, customersQuery.loading])

  const hasData = !summary.loading && !summary.error
  const activeIslands = summary.islandsWithCustomers
  const totalIslands = catalogsQuery.data.islas.length
  const islandCoverage = totalIslands ? (activeIslands / totalIslands) * 100 : 0

  return (
    <article className="dashboard-panel dashboard-client-panel">
      <div className="dashboard-client-panel-top">
        <div className="dashboard-client-icon">
          <DashboardClientsIcon />
        </div>
        <div className="dashboard-client-heading">
          <h2>Clientes</h2>
          <p>Clientes y contactos combinados</p>
        </div>
        <div className="dashboard-client-mini-icon" aria-hidden="true">
          <DashboardClientsIcon />
        </div>
      </div>

      <div className="dashboard-client-panel-body">
        <div className="dashboard-client-panel-main">
          <strong>{hasData ? formatNumber(summary.total) : 'Pendiente'}</strong>
          <span>Clientes totales</span>

          <div className="dashboard-client-summary-pill" aria-label="Resumen de islas activas">
            <span className="dashboard-client-summary-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 19V5" />
                <path d="M4 19h16" />
                <path d="M7 15l4-4 3 3 5-5" />
              </svg>
            </span>
            <span className="dashboard-client-summary-copy">
              <strong>{formatPercent(islandCoverage)}</strong>
              <span>{activeIslands} de {totalIslands || 0} islas con clientes</span>
            </span>
          </div>
        </div>

        <div className="dashboard-client-divider" aria-hidden="true" />

        <div className="dashboard-client-panel-right">
          <div className="dashboard-client-panel-right-title">
            <span className="dashboard-client-location-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 21s6-5.5 6-11a6 6 0 0 0-12 0c0 5.5 6 11 6 11z" />
                <circle cx="12" cy="10" r="2.2" />
              </svg>
            </span>
            <strong>Por isla</strong>
          </div>

          <div className="dashboard-client-islands">
            {hasData &&
              summary.islands.map((island) => (
                <div key={island.id} className="dashboard-client-island-row">
                  <span className={`dashboard-client-island-code dashboard-client-island-code-${island.code}`} style={islandBadgeStyle(island.code)}>{island.code}</span>
                  <span className="dashboard-client-island-label">{island.label}</span>
                  <span className="dashboard-client-island-count">
                    {formatNumber(island.count)} <small>({formatPercent(percentage(island.count, summary.total))})</small>
                  </span>
                </div>
              ))}
          </div>
        </div>
      </div>

    </article>
  )
}

export function DashboardPage({ onChangeView }: DashboardPageProps) {
  return (
    <section className="dashboard-page">
      <header className="dashboard-header">
        <div className="dashboard-header-copy">
          <h1>Dashboard</h1>
          <span className="dashboard-header-pill">Datos pendientes de conexión</span>
        </div>

        <button type="button" className="dashboard-period-select" disabled>
          <span className="dashboard-period-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <rect x="4" y="5" width="16" height="15" rx="2.5" />
              <path d="M8 3v4M16 3v4M4 10h16" />
            </svg>
          </span>
          <span>Año actual (2025)</span>
          <span className="dashboard-period-chevron" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="m6 9 6 6 6-6" />
            </svg>
          </span>
        </button>
      </header>

      <DashboardClientKpi />

      <section className="dashboard-main-grid">
        <article className="dashboard-panel dashboard-chart-panel">
          <div className="dashboard-panel-head">
            <h3>Ventas por año</h3>
            <button type="button" className="dashboard-panel-select" disabled>
              Mensual
            </button>
          </div>
          <EmptyState title="Ventas pendientes de conexión" description="Se mostrará al conectar los datos reales." />
        </article>

        <article className="dashboard-panel dashboard-table-panel">
          <div className="dashboard-panel-head">
            <h3>Pedidos pendientes</h3>
          </div>
          <EmptyState title="Sin datos reales conectados" description="Pendiente de conexión a pedidos." />
          <a href="#" className="dashboard-panel-link" onClick={(event) => event.preventDefault()}>
            Ver todos los pedidos pendientes
          </a>
        </article>

        <article className="dashboard-panel dashboard-table-panel">
          <div className="dashboard-panel-head">
            <h3>Stock bajo mínimo</h3>
          </div>
          <EmptyState title="Sin datos reales conectados" description="Pendiente de conexión a inventario." />
          <a href="#" className="dashboard-panel-link" onClick={(event) => event.preventDefault()}>
            Ver inventario completo
          </a>
        </article>
      </section>

      <section className="dashboard-lower-grid">
        <article className="dashboard-panel dashboard-list-panel">
          <div className="dashboard-panel-head">
            <h3>Clientes recientes</h3>
          </div>
          <EmptyState title="Pendiente de conectar clientes reales" description="Cuando se active la fuente de datos se mostrará el historial real." />
          <a href="#" className="dashboard-panel-link" onClick={(event) => event.preventDefault()}>
            Ver todos los clientes
          </a>
        </article>

        <article className="dashboard-panel dashboard-list-panel">
          <div className="dashboard-panel-head">
            <h3>Contactos recientes</h3>
          </div>
          <EmptyState title="Pendiente de conectar contactos reales" description="Cuando se active la fuente de datos se mostrará el historial real." />
          <a href="#" className="dashboard-panel-link" onClick={(event) => event.preventDefault()}>
            Ver todos los contactos
          </a>
        </article>

        <article className="dashboard-panel dashboard-list-panel">
          <div className="dashboard-panel-head">
            <h3>Últimos pedidos</h3>
          </div>
          <EmptyState title="Pendiente de conectar pedidos reales" description="Cuando se active la fuente de datos se mostrará el historial real." />
          <a href="#" className="dashboard-panel-link" onClick={(event) => event.preventDefault()}>
            Ver todos los pedidos
          </a>
        </article>

        <article className="dashboard-panel dashboard-quick-panel">
          <div className="dashboard-panel-head">
            <h3>Accesos rápidos</h3>
          </div>
          <div className="dashboard-quick-actions">
            {quickActions.map((action) => (
              <button
                key={action.view}
                type="button"
                className={`dashboard-quick-action tone-${action.tone}`}
                onClick={() => onChangeView(action.view)}
              >
                <span className="dashboard-quick-icon">
                  <DashboardIcon tone={action.tone} />
                </span>
                <span>{action.label}</span>
              </button>
            ))}
          </div>
        </article>
      </section>
    </section>
  )
}
