import { type ReactNode } from 'react'
import { SidebarNav, type SidebarNavItem, type ViewKey } from './SidebarNav'

interface AppShellProps {
  activeView: ViewKey
  onChangeView: (view: ViewKey) => void
  currentTitle: string
  currentSubtitle: string
  navItems: SidebarNavItem[]
  children: ReactNode
}

function ModuleIcon({ view }: { view: ViewKey }) {
  const commonProps = {
    'aria-hidden': true,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: '1.8',
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
  }

  switch (view) {
    case 'customers':
      return (
        <svg {...commonProps}>
          <path d="M4 18.5V17a4 4 0 0 1 4-4h2" />
          <circle cx="9" cy="8" r="3" />
          <path d="M14 9h6" />
          <path d="M17 6v6" />
        </svg>
      )
    case 'contacts':
      return (
        <svg {...commonProps}>
          <rect x="5" y="4" width="14" height="16" rx="2.5" />
          <path d="M8 8h8" />
          <path d="M8 12h8" />
          <path d="M8 16h5" />
        </svg>
      )
    case 'technicians':
      return (
        <svg {...commonProps}>
          <path d="M14.5 6.5a4 4 0 0 0-5.8 4.4L4 15.6l4.4.5.5 4.4 4.7-4.7a4 4 0 0 0 5.3-5.3l-2.1 2.1-2.8-.5-.5-2.8 2.1-2.1Z" />
        </svg>
      )
    case 'distributors':
      return (
        <svg {...commonProps}>
          <path d="M3 7h11v8H3z" />
          <path d="M14 10h4l3 3v2h-7z" />
          <circle cx="7" cy="17" r="1.5" />
          <circle cx="17" cy="17" r="1.5" />
        </svg>
      )
    case 'courses':
      return (
        <svg {...commonProps}>
          <path d="M4 9l8-4 8 4-8 4-8-4Z" />
          <path d="M7 11v4c0 1.7 2.2 3 5 3s5-1.3 5-3v-4" />
        </svg>
      )
    case 'recipes':
      return (
        <svg {...commonProps}>
          <path d="M7 4h10v16H7z" />
          <path d="M9 8h6M9 12h6M9 16h4" />
        </svg>
      )
    case 'ingredients':
      return (
        <svg {...commonProps}>
          <path d="M12 3c2.8 2.2 5 5.2 5 8.6A5 5 0 0 1 12 17a5 5 0 0 1-5-5.4C7 8.2 9.2 5.2 12 3Z" />
          <path d="M9 14c1.2-1 2.4-1.8 3-3.5" />
        </svg>
      )
    case 'warehouse':
      return (
        <svg {...commonProps}>
          <path d="M4 10.5 12 5l8 5.5" />
          <path d="M6 10v8h12v-8" />
          <path d="M9 18v-5h6v5" />
        </svg>
      )
    case 'orders':
      return (
        <svg {...commonProps}>
          <rect x="5" y="4" width="14" height="16" rx="2" />
          <path d="M8 8h8M8 12h8M8 16h5" />
        </svg>
      )
    case 'sales':
      return (
        <svg {...commonProps}>
          <path d="M5 19V5" />
          <path d="M5 19h14" />
          <path d="M8 14l3-3 3 2 5-6" />
          <path d="M17 7h2v2" />
        </svg>
      )
    default:
      return (
        <svg {...commonProps}>
          <circle cx="12" cy="12" r="7" />
          <path d="M12 8v4l3 2" />
        </svg>
      )
  }
}

export function AppShell({
  activeView,
  onChangeView,
  currentTitle,
  currentSubtitle,
  navItems,
  children,
}: AppShellProps) {
  const isCustomers = activeView === 'customers'

  return (
    <div className={`app-shell ${isCustomers ? 'app-shell-customers' : ''}`}>
      {isCustomers ? (
        <>
          <header className="app-topbar">
            <div className="app-topbar-brand">
              <span className="app-topbar-brand-name">GESTIÓN IREKS</span>
              <span className="app-topbar-section">Clientes</span>
            </div>

            <nav className="app-topbar-nav" aria-label="Navegacion principal">
              {navItems.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  aria-label={item.label}
                  className={`app-topbar-nav-item ${activeView === item.key ? 'app-topbar-nav-item-active' : ''}`}
                  aria-current={activeView === item.key ? 'page' : undefined}
                  onClick={() => onChangeView(item.key)}
                >
                  <span className="app-topbar-nav-icon">
                    <ModuleIcon view={item.key} />
                  </span>
                  <span className="app-topbar-nav-label">{item.label}</span>
                </button>
              ))}
            </nav>
          </header>

          <main className="app-content">
            <section className="view-panel view-panel-customers">{children}</section>
          </main>
        </>
      ) : (
        <>
          <header className={`app-header ${isCustomers ? 'app-header-customers' : ''}`}>
            <div className="app-brand app-brand-compact">
              <div className="app-brand-row">
                <p className="app-brand-kicker">Gestion IREKS</p>
              </div>
              <h1>{currentTitle}</h1>
              <p className="app-brand-subtitle">{currentSubtitle}</p>
            </div>
          </header>

          <div className={`app-nav-shell ${isCustomers ? 'app-nav-shell-customers' : ''}`}>
            <SidebarNav activeView={activeView} onChange={onChangeView} items={navItems} />
          </div>

          <div className={`app-stage ${isCustomers ? 'app-stage-customers' : ''}`}>
            <main className="app-content">{children}</main>
          </div>
        </>
      )}
    </div>
  )
}
