import { useMemo, useState } from 'react'
import { AppErrorBoundary } from './components/AppErrorBoundary'
import { CustomersPage } from './pages/CustomersPage'
import { IngredientsPage } from './pages/IngredientsPage'
import { WarehousePage } from './pages/WarehousePage'

type ViewKey = 'customers' | 'ingredients' | 'warehouse'

const VIEWS: Array<{ key: ViewKey; label: string }> = [
  { key: 'customers', label: 'Clientes' },
  { key: 'ingredients', label: 'Ingredientes' },
  { key: 'warehouse', label: 'Almacen' },
]

function App() {
  const [activeView, setActiveView] = useState<ViewKey>('customers')

  const viewTitle = useMemo(() => {
    if (activeView === 'ingredients') {
      return 'Consulta de ingredientes'
    }
    if (activeView === 'warehouse') {
      return 'Consulta de almacen'
    }
    return 'Consulta de clientes'
  }, [activeView])

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Gestion IREKS</p>
          <h1>{viewTitle}</h1>
        </div>
        <div className="tabs" role="tablist" aria-label="Navegacion principal">
          {VIEWS.map((view) => (
            <button
              key={view.key}
              type="button"
              role="tab"
              aria-selected={activeView === view.key}
              className={`tab-btn ${activeView === view.key ? 'active' : ''}`}
              onClick={() => setActiveView(view.key)}
            >
              {view.label}
            </button>
          ))}
        </div>
      </header>

      <section className="view-panel">
        <AppErrorBoundary>
          {activeView === 'customers' && <CustomersPage />}
          {activeView === 'ingredients' && <IngredientsPage />}
          {activeView === 'warehouse' && <WarehousePage />}
        </AppErrorBoundary>
      </section>
    </main>
  )
}

export default App
