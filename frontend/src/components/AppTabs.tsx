type AppViewKey =
  | 'sales'
  | 'recipes'
  | 'courses'
  | 'customers'
  | 'contacts'
  | 'ingredients'
  | 'orders'
  | 'warehouse'
  | 'settings'

export interface AppTabOption {
  key: AppViewKey
  label: string
}

interface AppTabsProps {
  activeView: AppViewKey
  onChange: (view: AppViewKey) => void
  views: AppTabOption[]
}

export function AppTabs({ activeView, onChange, views }: AppTabsProps) {
  return (
    <div className="tabs" role="tablist" aria-label="Navegacion principal">
      {views.map((view) => (
        <button
          key={view.key}
          type="button"
          role="tab"
          aria-selected={activeView === view.key}
          className={`tab-btn ${activeView === view.key ? 'active' : ''}`}
          onClick={() => onChange(view.key)}
        >
          {view.label}
        </button>
      ))}
    </div>
  )
}
