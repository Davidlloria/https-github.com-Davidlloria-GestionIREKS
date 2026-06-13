import type { ViewKey } from '../components/SidebarNav'

interface DashboardPageProps {
  onChangeView: (view: ViewKey) => void
}

const kpiCards = [
  {
    title: 'Ventas año actual',
    value: '245.780 €',
    detail: '+18,6% vs año anterior',
    tone: 'green',
  },
  {
    title: 'Pedidos pendientes',
    value: '36',
    detail: '12 con retraso',
    tone: 'orange',
  },
  {
    title: 'Clientes',
    value: '1.284',
    detail: '+5,3% vs año anterior',
    tone: 'blue',
  },
  {
    title: 'Contactos',
    value: '2.430',
    detail: '+7,8% vs año anterior',
    tone: 'purple',
  },
  {
    title: 'Stock total',
    value: '1.985',
    detail: 'referencias activas',
    tone: 'emerald',
  },
] as const

const yearChart = [
  { month: 'Ene', current: 52, previous: 34 },
  { month: 'Feb', current: 63, previous: 50 },
  { month: 'Mar', current: 71, previous: 53 },
  { month: 'Abr', current: 70, previous: 45 },
  { month: 'May', current: 46, previous: 31 },
  { month: 'Jun', current: 38, previous: 26 },
  { month: 'Jul', current: 36, previous: 24 },
  { month: 'Ago', current: 30, previous: 21 },
  { month: 'Sep', current: 24, previous: 19 },
  { month: 'Oct', current: 18, previous: 16 },
  { month: 'Nov', current: 16, previous: 13 },
  { month: 'Dic', current: 12, previous: 10 },
]

const pendingOrders = [
  { pedido: 'PED-2025-0421', cliente: 'Panadería La Unión', fecha: '20/05/2025', estado: 'Retrasado', importe: '1.250,00 €' },
  { pedido: 'PED-2025-0418', cliente: 'Hornos del Norte', fecha: '19/05/2025', estado: 'Pendiente', importe: '980,50 €' },
  { pedido: 'PED-2025-0415', cliente: 'Pastelería Dulce Sabor', fecha: '18/05/2025', estado: 'Pendiente', importe: '765,00 €' },
  { pedido: 'PED-2025-0412', cliente: 'Pan y Más, S.L.', fecha: '17/05/2025', estado: 'Pendiente', importe: '540,00 €' },
  { pedido: 'PED-2025-0410', cliente: 'Bollería Artesana', fecha: '16/05/2025', estado: 'Pendiente', importe: '1.120,00 €' },
]

const stockAlerts = [
  { ingrediente: 'Harina de Trigo 25kg', almacen: 'Central', actual: '45 kg', minimo: '100 kg' },
  { ingrediente: 'Levadura Prensada 500g', almacen: 'Central', actual: '12 ud', minimo: '50 ud' },
  { ingrediente: 'Mejorante Panificación 5kg', almacen: 'Central', actual: '8 ud', minimo: '20 ud' },
  { ingrediente: 'Cobertura Chocolate 10kg', almacen: 'Secundario', actual: '6 kg', minimo: '15 kg' },
  { ingrediente: 'Azúcar Perlado 5kg', almacen: 'Central', actual: '3 kg', minimo: '10 kg' },
]

const recentCustomers = [
  { name: 'Panadería San Blas', date: '20/05/2025', tone: 'P' },
  { name: 'Horno Artesano', date: '19/05/2025', tone: 'H' },
  { name: 'Dulces Tradición, S.L.', date: '18/05/2025', tone: 'D' },
  { name: 'Molino del Sur', date: '16/05/2025', tone: 'M' },
  { name: 'Bakers Premium', date: '15/05/2025', tone: 'B' },
]

const recentContacts = [
  { name: 'María López', company: 'Panadería La Unión', date: '20/05/2025' },
  { name: 'Carlos Martín', company: 'Hornos del Norte', date: '19/05/2025' },
  { name: 'Laura Gómez', company: 'Pastelería Dulce Sabor', date: '18/05/2025' },
  { name: 'Javier Ruiz', company: 'Pan y Más, S.L.', date: '17/05/2025' },
  { name: 'Ana Torres', company: 'Bollería Artesana', date: '16/05/2025' },
]

const recentOrders = [
  { order: 'PED-2025-0420', customer: 'Panadería San Blas', date: '20/05/2025', amount: '980,00 €' },
  { order: 'PED-2025-0419', customer: 'Horno Artesano', date: '19/05/2025', amount: '670,00 €' },
  { order: 'PED-2025-0417', customer: 'Dulces Tradición, S.L.', date: '18/05/2025', amount: '1.340,00 €' },
  { order: 'PED-2025-0414', customer: 'Molino del Sur', date: '16/05/2025', amount: '430,00 €' },
  { order: 'PED-2025-0411', customer: 'Bakers Premium', date: '16/05/2025', amount: '890,00 €' },
]

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

function MiniStatePill({ label }: { label: string }) {
  return <span className="dashboard-state-pill">{label}</span>
}

function SimpleChart() {
  return (
    <div className="dashboard-chart" aria-label="Ventas por año">
      <div className="dashboard-chart-legend">
        <span><i className="chart-key chart-key-soft" />2024</span>
        <span><i className="chart-key chart-key-strong" />2025</span>
      </div>
      <div className="dashboard-chart-bars">
        {yearChart.map((entry) => (
          <div key={entry.month} className="dashboard-chart-column">
            <div className="dashboard-chart-bars-group">
              <div className="dashboard-chart-bar dashboard-chart-bar-soft" style={{ height: `${entry.previous}%` }} />
              <div className="dashboard-chart-bar dashboard-chart-bar-strong" style={{ height: `${entry.current}%` }} />
            </div>
            <span className="dashboard-chart-label">{entry.month}</span>
          </div>
        ))}
      </div>
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
          <SimpleChart />
        </article>

        <article className="dashboard-panel dashboard-table-panel">
          <div className="dashboard-panel-head">
            <h3>Pedidos pendientes</h3>
          </div>
          <div className="dashboard-table-wrap">
            <table className="dashboard-table">
              <thead>
                <tr>
                  <th>Pedido</th>
                  <th>Cliente</th>
                  <th>Fecha</th>
                  <th>Estado</th>
                  <th>Importe</th>
                </tr>
              </thead>
              <tbody>
                {pendingOrders.map((row) => (
                  <tr key={row.pedido}>
                    <td>{row.pedido}</td>
                    <td>{row.cliente}</td>
                    <td>{row.fecha}</td>
                    <td><MiniStatePill label={row.estado} /></td>
                    <td>{row.importe}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <a href="#" className="dashboard-panel-link" onClick={(event) => event.preventDefault()}>
            Ver todos los pedidos pendientes
          </a>
        </article>

        <article className="dashboard-panel dashboard-table-panel">
          <div className="dashboard-panel-head">
            <h3>Stock bajo mínimo</h3>
          </div>
          <div className="dashboard-table-wrap">
            <table className="dashboard-table">
              <thead>
                <tr>
                  <th>Ingrediente</th>
                  <th>Almacén</th>
                  <th>Stock actual</th>
                  <th>Mínimo</th>
                </tr>
              </thead>
              <tbody>
                {stockAlerts.map((row) => (
                  <tr key={row.ingrediente}>
                    <td>{row.ingrediente}</td>
                    <td>{row.almacen}</td>
                    <td className="dashboard-strong-cell">{row.actual}</td>
                    <td>{row.minimo}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
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
          <div className="dashboard-list">
            {recentCustomers.map((row) => (
              <div key={row.name} className="dashboard-list-item">
                <span className="dashboard-list-avatar">{row.tone}</span>
                <span className="dashboard-list-name">{row.name}</span>
                <span className="dashboard-list-date">{row.date}</span>
              </div>
            ))}
          </div>
          <a href="#" className="dashboard-panel-link" onClick={(event) => event.preventDefault()}>
            Ver todos los clientes
          </a>
        </article>

        <article className="dashboard-panel dashboard-list-panel">
          <div className="dashboard-panel-head">
            <h3>Contactos recientes</h3>
          </div>
          <div className="dashboard-list">
            {recentContacts.map((row) => (
              <div key={row.name} className="dashboard-list-item dashboard-list-item-three">
                <span className="dashboard-list-name">{row.name}</span>
                <span className="dashboard-list-company">{row.company}</span>
                <span className="dashboard-list-date">{row.date}</span>
              </div>
            ))}
          </div>
          <a href="#" className="dashboard-panel-link" onClick={(event) => event.preventDefault()}>
            Ver todos los contactos
          </a>
        </article>

        <article className="dashboard-panel dashboard-list-panel">
          <div className="dashboard-panel-head">
            <h3>Últimos pedidos</h3>
          </div>
          <div className="dashboard-list">
            {recentOrders.map((row) => (
              <div key={row.order} className="dashboard-list-item dashboard-list-item-three dashboard-list-item-order">
                <span className="dashboard-list-name">{row.order}</span>
                <span className="dashboard-list-company">{row.customer}</span>
                <span className="dashboard-list-date">{row.date}</span>
                <span className="dashboard-list-amount">{row.amount}</span>
              </div>
            ))}
          </div>
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
