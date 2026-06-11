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
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-brand">
          <p className="app-brand-kicker">Gestion IREKS</p>
          <h1>{currentTitle}</h1>
          <p className="app-brand-subtitle">{currentSubtitle}</p>
        </div>
        <div className="app-header-badge" aria-hidden="true">
          <span className="surface-chip">{currentBadge}</span>
        </div>
      </header>

      <div className="app-body">
        <aside className="app-sidebar">
          <div className="app-sidebar-title">{"Módulos"}</div>
          <SidebarNav activeView={activeView} onChange={onChangeView} items={navItems} />
        </aside>

        <main className="app-content">{children}</main>
      </div>
    </div>
  )
}
