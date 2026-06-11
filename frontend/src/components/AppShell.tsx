import { type ReactNode } from 'react'
import { SidebarNav, type SidebarNavItem, type ViewKey } from './SidebarNav'

interface AppShellProps {
  activeView: ViewKey
  onChangeView: (view: ViewKey) => void
  currentTitle: string
  currentSubtitle: string
  currentBadge: string
  navItems: SidebarNavItem[]
  children: ReactNode
}

export function AppShell({
  activeView,
  onChangeView,
  currentTitle,
  currentSubtitle,
  currentBadge,
  navItems,
  children,
}: AppShellProps) {
  const isCustomers = activeView === 'customers'

  return (
    <div className={`app-shell ${isCustomers ? 'app-shell-customers' : ''}`}>
      <header className={`app-header ${isCustomers ? 'app-header-customers' : ''}`}>
        <div className="app-brand app-brand-compact">
          <div className="app-brand-row">
            <p className="app-brand-kicker">Gestion IREKS</p>
            <span className="app-brand-title-chip">{currentBadge}</span>
          </div>
          {!isCustomers && (
            <>
              <h1>{currentTitle}</h1>
              <p className="app-brand-subtitle">{currentSubtitle}</p>
            </>
          )}
        </div>
      </header>

      <div className={`app-nav-shell ${isCustomers ? 'app-nav-shell-customers' : ''}`}>
        <SidebarNav activeView={activeView} onChange={onChangeView} items={navItems} />
      </div>

      <main className="app-content">{children}</main>
    </div>
  )
}
