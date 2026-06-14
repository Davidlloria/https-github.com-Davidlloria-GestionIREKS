import { useState } from 'react'
import { AppErrorBoundary } from './components/AppErrorBoundary'
import { AppShell } from './components/AppShell'
import type { ViewKey } from './components/SidebarNav'
import { DashboardPage } from './pages/DashboardPage'
import { ContactsPage } from './pages/ContactsPage'
import { CoursesPage } from './pages/CoursesPage'
import { CustomersPage } from './pages/CustomersPage'
import { DistributorsPage } from './pages/DistributorsPage'
import { ConfigurationPage } from './pages/ConfigurationPage'
import { IreksProductsPage } from './pages/IreksProductsPage'
import { IngredientsPage } from './pages/IngredientsPage'
import { OrdersPage } from './pages/OrdersPage'
import { RecipesPage } from './pages/RecipesPage'
import { SalesPage } from './pages/SalesPage'
import { TechniciansPage } from './pages/TechniciansPage'
import { WarehousePage } from './pages/WarehousePage'

type ViewMeta = {
  label: string
  title: string
  subtitle: string
}

const VIEWS: Array<{ key: ViewKey; label: string; description: string }> = [
  { key: 'dashboard', label: 'Inicio', description: 'Resumen general' },
  { key: 'customers', label: 'Clientes', description: 'Ficha y relaciones' },
  { key: 'contacts', label: 'Contactos', description: 'Consulta read-only' },
  { key: 'technicians', label: 'Tecnicos', description: 'Consulta read-only' },
  { key: 'distributors', label: 'Distribuidores', description: 'Consulta read-only' },
  { key: 'courses', label: 'Cursos', description: 'Cursos y asistentes' },
  { key: 'recipes', label: 'Recetas', description: 'Listado y detalle read-only' },
  { key: 'ingredientsIreks', label: 'Productos IREKS', description: 'Catalogo read-only de productos IREKS' },
  { key: 'ingredientsStd', label: 'Materias primas', description: 'Catalogo read-only de materias primas' },
  { key: 'warehouse', label: 'Almacen', description: 'Stock, movimientos e inventario' },
  { key: 'orders', label: 'Pedidos', description: 'Consulta read-only' },
  { key: 'sales', label: 'Ventas', description: 'Ventas anual y comparativas' },
]

const VIEW_META: Record<ViewKey, ViewMeta> = {
  dashboard: {
    label: 'Inicio',
    title: 'Dashboard',
    subtitle: 'Resumen general de actividad',
  },
  settings: {
    label: 'Configuración',
    title: 'Configuración',
    subtitle: 'Acceso controlado y read-only desde Dashboard.',
  },
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
  ingredients: {
    label: 'Productos IREKS',
    title: 'Productos IREKS',
    subtitle: 'Vista read-only minima para explorar listado y detalle de productos IREKS.',
  },
  courses: {
    label: 'Cursos',
    title: 'Consulta de cursos',
    subtitle: 'Vista read-only minima para explorar listado, detalle y asistentes.',
  },
  customers: {
    label: 'Clientes',
    title: 'Clientes',
    subtitle: 'Consulta read-only de clientes con detalle compacto y relaciones.',
  },
  contacts: {
    label: 'Contactos',
    title: 'Consulta de contactos',
    subtitle: 'Vista read-only minima para explorar listado y detalle de contactos.',
  },
  orders: {
    label: 'Pedidos',
    title: 'Consulta de pedidos',
    subtitle: 'Vista read-only minima para explorar listado, detalle, lineas y pendientes.',
  },
  technicians: {
    label: 'Tecnicos',
    title: 'Consulta de tecnicos',
    subtitle: 'Vista read-only minima para explorar listado y detalle de tecnicos.',
  },
  distributors: {
    label: 'Distribuidores',
    title: 'Consulta de distribuidores',
    subtitle: 'Vista read-only minima para explorar listado y detalle de distribuidores.',
  },
  ingredientsIreks: {
    label: 'Productos IREKS',
    title: 'Productos IREKS',
    subtitle: 'Vista read-only minima para explorar listado y detalle de productos IREKS.',
  },
  ingredientsStd: {
    label: 'Materias primas',
    title: 'Materias primas',
    subtitle: 'Vista read-only minima para explorar listado y detalle de materias primas.',
  },
  warehouse: {
    label: 'Almacen',
    title: 'Consulta de almacen',
    subtitle: 'Vista read-only de stock, movimientos e inventarios historicos.',
  },
}

function App() {
  const [activeView, setActiveView] = useState<ViewKey>('dashboard')
  const currentView = VIEW_META[activeView]

  return (
    <AppShell
      activeView={activeView}
      onChangeView={setActiveView}
      currentTitle={currentView.title}
      currentSubtitle={currentView.subtitle}
      navItems={VIEWS}
    >
      <section className="view-panel">
        <AppErrorBoundary>
          {activeView === 'dashboard' && <DashboardPage onChangeView={setActiveView} />}
          {activeView === 'sales' && <SalesPage />}
          {activeView === 'recipes' && <RecipesPage />}
          {activeView === 'courses' && <CoursesPage />}
          {activeView === 'customers' && <CustomersPage />}
          {activeView === 'contacts' && <ContactsPage />}
          {activeView === 'settings' && <ConfigurationPage onBack={() => setActiveView('dashboard')} />}
          {activeView === 'orders' && <OrdersPage />}
          {activeView === 'technicians' && <TechniciansPage />}
          {activeView === 'distributors' && <DistributorsPage />}
          {(activeView === 'ingredients' || activeView === 'ingredientsIreks') && <IreksProductsPage />}
          {activeView === 'ingredientsStd' && <IngredientsPage mode="std" />}
          {activeView === 'warehouse' && <WarehousePage />}
        </AppErrorBoundary>
      </section>
    </AppShell>
  )
}

export default App
