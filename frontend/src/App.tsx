import { useState } from 'react'
import { AppErrorBoundary } from './components/AppErrorBoundary'
import { AppShell } from './components/AppShell'
import { CoursesPage } from './pages/CoursesPage'
import { CustomersPage } from './pages/CustomersPage'
import { IngredientsPage } from './pages/IngredientsPage'
import { RecipesPage } from './pages/RecipesPage'
import { SalesPage } from './pages/SalesPage'
import { WarehousePage } from './pages/WarehousePage'

type ViewKey = 'sales' | 'recipes' | 'courses' | 'customers' | 'ingredients' | 'warehouse'

type ViewMeta = {
  label: string
  title: string
  subtitle: string
}

const VIEWS: Array<{ key: ViewKey; label: string; description: string }> = [
  { key: 'sales', label: 'Ventas', description: 'Ventas anual y comparativas' },
  { key: 'recipes', label: 'Recetas', description: 'Listado y detalle read-only' },
  { key: 'courses', label: 'Cursos', description: 'Cursos y asistentes' },
  { key: 'customers', label: 'Clientes', description: 'Ficha y relaciones' },
  { key: 'ingredients', label: 'Ingredientes', description: 'Catálogo e inspección' },
  { key: 'warehouse', label: 'Almacén', description: 'Stock, movimientos e inventario' },
]

const VIEW_META: Record<ViewKey, ViewMeta> = {
  sales: {
    label: 'Ventas',
    title: 'Comparacion anual de ventas',
    subtitle: 'Prototipo minimo para consumir la API read-only de ventas desde React.',
  },
  recipes: {
    label: 'Recetas',
    title: 'Consulta de recetas',
    subtitle: 'Vista read-only minima para explorar lista, detalle y lineas de receta.',
  },
  courses: {
    label: 'Cursos',
    title: 'Consulta de cursos',
    subtitle: 'Vista read-only minima para explorar listado, detalle y asistentes.',
  },
  customers: {
    label: 'Clientes',
    title: 'Consulta de clientes',
    subtitle: 'Ficha, relaciones y estados visibles en una lectura rapida.',
  },
  ingredients: {
    label: 'Ingredientes',
    title: 'Consulta de ingredientes',
    subtitle: 'Vista read-only minima para explorar listado y detalle de ingredientes.',
  },
  warehouse: {
    label: 'Almac\u00e9n',
    title: 'Consulta de almac\u00e9n',
    subtitle: 'Vista read-only de stock, movimientos e inventarios historicos.',
  },
}

function App() {
  const [activeView, setActiveView] = useState<ViewKey>('sales')
  const currentView = VIEW_META[activeView]

  return (
    <AppShell
      activeView={activeView}
      onChangeView={setActiveView}
      currentTitle={currentView.title}
      currentSubtitle={currentView.subtitle}
      currentBadge={currentView.label}
      navItems={VIEWS}
    >
      <section className="view-panel">
        <AppErrorBoundary>
          {activeView === 'sales' && <SalesPage />}
          {activeView === 'recipes' && <RecipesPage />}
          {activeView === 'courses' && <CoursesPage />}
          {activeView === 'customers' && <CustomersPage />}
          {activeView === 'ingredients' && <IngredientsPage />}
          {activeView === 'warehouse' && <WarehousePage />}
        </AppErrorBoundary>
      </section>
    </AppShell>
  )
}

export default App
