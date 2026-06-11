export type ViewKey = 'sales' | 'recipes' | 'courses' | 'customers' | 'contacts' | 'orders' | 'ingredients' | 'warehouse'

export interface SidebarNavItem {
  key: ViewKey
  label: string
  description: string
}

interface SidebarNavProps {
  activeView: ViewKey
  onChange: (view: ViewKey) => void
  items: SidebarNavItem[]
}

export function SidebarNav({ activeView, onChange, items }: SidebarNavProps) {
  return (
    <nav className="sidebar-nav" aria-label="Navegacion principal">
      {items.map((item) => (
        <button
          key={item.key}
          type="button"
          aria-label={item.label}
          className={`sidebar-item ${activeView === item.key ? 'active' : ''}`}
          aria-current={activeView === item.key ? 'page' : undefined}
          onClick={() => onChange(item.key)}
        >
          <span className="sidebar-item-label">{item.label}</span>
          <span className="sidebar-item-description">{item.description}</span>
        </button>
      ))}
    </nav>
  )
}
