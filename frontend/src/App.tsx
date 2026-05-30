import { useMemo, useState } from 'react'
import { AppErrorBoundary } from './components/AppErrorBoundary'
import { ContactsPage } from './pages/ContactsPage'
import { CustomersPage } from './pages/CustomersPage'
import { IngredientsPage } from './pages/IngredientsPage'
import { OrdersPage } from './pages/OrdersPage'
import { SettingsPage } from './pages/SettingsPage'
import { WarehousePage } from './pages/WarehousePage'

type ViewKey = 'customers' | 'contacts' | 'ingredients' | 'orders' | 'warehouse' | 'settings'

const VIEWS: Array<{ key: ViewKey; label: string }> = [
  { key: 'customers', label: 'Clientes' },
  { key: 'contacts', label: 'Contactos' },
  { key: 'ingredients', label: 'Ingredientes' },
  { key: 'orders', label: 'Pedidos' },
  { key: 'warehouse', label: 'Almacen' },
  { key: 'settings', label: 'Configuracion' },
]

function App() {
  const [activeView, setActiveView] = useState<ViewKey>('customers')

  const viewTitle = useMemo(() => {
    if (activeView === 'contacts') {
      return 'Consulta de contactos'
    }
    if (activeView === 'ingredients') {
      return 'Consulta de ingredientes'
    }
    if (activeView === 'orders') {
      return 'Consulta de pedidos'
    }
    if (activeView === 'warehouse') {
      return 'Consulta de almacen'
    }
    if (activeView === 'settings') {
      return 'Configuracion y mantenimiento'
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
          {activeView === 'contacts' && <ContactsPage />}
          {activeView === 'ingredients' && <IngredientsPage />}
          {activeView === 'orders' && <OrdersPage />}
          {activeView === 'warehouse' && <WarehousePage />}
          {activeView === 'settings' && <SettingsPage />}
        </AppErrorBoundary>
      </section>
    </main>
  )
}

export default App
