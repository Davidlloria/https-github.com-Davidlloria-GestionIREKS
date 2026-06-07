import { useState } from 'react'
import { AppErrorBoundary } from './components/AppErrorBoundary'
import { ContactsPage } from './pages/ContactsPage'
import { CustomersPage } from './pages/CustomersPage'
import { IngredientsPage } from './pages/IngredientsPage'
import { OrdersPage } from './pages/OrdersPage'
import { SettingsPage } from './pages/SettingsPage'
import { WarehousePage } from './pages/WarehousePage'

type ViewKey = 'customers' | 'contacts' | 'ingredients' | 'orders' | 'warehouse' | 'settings'

type ViewMeta = {
  label: string
  title: string
  subtitle: string
  note: string
}

const VIEWS: Array<{ key: ViewKey; label: string }> = [
  { key: 'customers', label: 'Clientes' },
  { key: 'contacts', label: 'Contactos' },
  { key: 'ingredients', label: 'Ingredientes' },
  { key: 'orders', label: 'Pedidos' },
  { key: 'warehouse', label: 'Almacen' },
  { key: 'settings', label: 'Configuracion' },
]

const VIEW_META: Record<ViewKey, ViewMeta> = {
  customers: {
    label: 'Clientes',
    title: 'Consulta de clientes',
    subtitle: 'Ficha, relaciones y estados visibles en una lectura rapida.',
    note: 'Vista base',
  },
  contacts: {
    label: 'Contactos',
    title: 'Consulta de contactos',
    subtitle: 'Listado con detalle lateral para localizar y revisar sin perder contexto.',
    note: 'Relacionados',
  },
  ingredients: {
    label: 'Ingredientes',
    title: 'Consulta de ingredientes',
    subtitle: 'Vista densa, ahora con jerarquia mas clara entre filtros, resumen y detalle.',
    note: 'Catalogo',
  },
  orders: {
    label: 'Pedidos',
    title: 'Consulta de pedidos',
    subtitle: 'Prioriza lectura del listado, detalle y estados sin saturar la cabecera.',
    note: 'Operacion',
  },
  warehouse: {
    label: 'Almacen',
    title: 'Consulta de almacen',
    subtitle: 'Mas aire entre tarjetas, tablas y acciones para bajar friccion visual.',
    note: 'Stock',
  },
  settings: {
    label: 'Configuracion',
    title: 'Configuracion y mantenimiento',
    subtitle: 'Herramientas de soporte con un encuadre mas limpio y predecible.',
    note: 'Soporte',
  },
}

function App() {
  const [activeView, setActiveView] = useState<ViewKey>('customers')
  const currentView = VIEW_META[activeView]

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="topbar-copy">
          <p className="eyebrow">Gestion IREKS</p>
          <h1>{currentView.title}</h1>
          <p className="view-subtitle">{currentView.subtitle}</p>
        </div>
        <div className="topbar-badges" aria-hidden="true">
          <span className="surface-chip">{currentView.label}</span>
          <span className="surface-chip surface-chip-muted">{currentView.note}</span>
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
