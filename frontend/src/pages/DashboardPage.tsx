import type { ViewKey } from '../components/SidebarNav'

interface DashboardPageProps {
  onChangeView: (view: ViewKey) => void
}

const kpiCards = [
  {
    title: 'Ventas año actual',
    value: 'Pendiente',
    detail: 'Pendiente de datos reales',
    tone: 'green',
  },
  {
    title: 'Pedidos pendientes',
    value: 'Pendiente',
    detail: 'Pendiente de datos reales',
    tone: 'orange',
  },
  {
    title: 'Clientes',
    value: '—',
    detail: 'Pendiente de datos reales',
    tone: 'blue',
  },
  {
    title: 'Contactos',
    value: '—',
    detail: 'Pendiente de datos reales',
    tone: 'purple',
  },
  {
    title: 'Stock total',
    value: 'Pendiente',
    detail: 'Pendiente de datos reales',
    tone: 'emerald',
  },
] as const

const quickActions: Array<{ view: ViewKey; label: string; tone: string }> = [
  { view: 'customers', label: 'Clientes', tone: 'blue' },
  { view: 'contacts', label: 'Contactos', tone: 'purple' },
  { view: 'orders', label: 'Pedidos', tone: 'orange' },
  { view: 'sales', label: 'Ventas', tone: 'green' },
  { view: 'warehouse', label: 'Almacén', tone: 'emerald' },
  { view: 'recipes', label: 'Recetas', tone: 'violet' },
  { view: 'ingredients', label: 'Ingredientes', tone: 'leaf' },
  { view: 'courses', label: 'Cursos', tone: 'amber' },
]

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

function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="dashboard-empty-state">
      <strong>{title}</strong>
      <p>{description}</p>
    </div>
  )
}

export function DashboardPage({ onChangeView }: DashboardPageProps) {
  return (
    <section className="dashboard-page">
      <header className="dashboard-header">
        <div className="dashboard-header-copy">
          <p className="dashboard-kicker">Inicio</p>
          <h1>Dashboard</h1>
          <p>Resumen general de actividad</p>
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

      <p className="dashboard-note">Dashboard visual pendiente de conexión a datos reales</p>

      <section className="dashboard-kpi-grid" aria-label="Indicadores principales">
        {kpiCards.map((card) => (
          <article key={card.title} className={`dashboard-kpi-card tone-${card.tone}`}>
            <div className="dashboard-kpi-icon">
              <DashboardIcon tone={card.tone} />
            </div>
            <div className="dashboard-kpi-copy">
              <h2>{card.title}</h2>
              <strong>{card.value}</strong>
              <p>{card.detail}</p>
            </div>
          </article>
        ))}
      </section>

      <section className="dashboard-main-grid">
        <article className="dashboard-panel dashboard-chart-panel">
          <div className="dashboard-panel-head">
            <h3>Ventas por año</h3>
            <button type="button" className="dashboard-panel-select" disabled>
              Mensual
            </button>
          </div>
          <EmptyState
            title="Ventas pendientes de conexión"
            description="Se mostrará al conectar los datos reales."
          />
        </article>

        <article className="dashboard-panel dashboard-table-panel">
          <div className="dashboard-panel-head">
            <h3>Pedidos pendientes</h3>
          </div>
          <EmptyState
            title="Sin datos reales conectados"
            description="Pendiente de conexión a pedidos."
          />
          <a href="#" className="dashboard-panel-link" onClick={(event) => event.preventDefault()}>
            Ver todos los pedidos pendientes
          </a>
        </article>

        <article className="dashboard-panel dashboard-table-panel">
          <div className="dashboard-panel-head">
            <h3>Stock bajo mínimo</h3>
          </div>
          <EmptyState
            title="Sin datos reales conectados"
            description="Pendiente de conexión a inventario."
          />
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
          <EmptyState
            title="Pendiente de conectar clientes reales"
            description="Cuando se active la fuente de datos se mostrará el historial real."
          />
          <a href="#" className="dashboard-panel-link" onClick={(event) => event.preventDefault()}>
            Ver todos los clientes
          </a>
        </article>

        <article className="dashboard-panel dashboard-list-panel">
          <div className="dashboard-panel-head">
            <h3>Contactos recientes</h3>
          </div>
          <EmptyState
            title="Pendiente de conectar contactos reales"
            description="Cuando se active la fuente de datos se mostrará el historial real."
          />
          <a href="#" className="dashboard-panel-link" onClick={(event) => event.preventDefault()}>
            Ver todos los contactos
          </a>
        </article>

        <article className="dashboard-panel dashboard-list-panel">
          <div className="dashboard-panel-head">
            <h3>Últimos pedidos</h3>
          </div>
          <EmptyState
            title="Pendiente de conectar pedidos reales"
            description="Cuando se active la fuente de datos se mostrará el historial real."
          />
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
