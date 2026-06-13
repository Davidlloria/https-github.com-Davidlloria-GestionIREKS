import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import App from './App'

const salesSummary = {
  source: 'ireks',
  year: 2024,
  month: 1,
  acumulado: false,
  total: 2,
  items: [
    {
      articulo_id: 'A-1',
      codigo: 'A-1',
      nombre: 'Venta 1',
      kilos_prev: 1,
      kilos_curr: 2,
      ventas_prev: 3,
      ventas_curr: 4,
      delta_kg: 1,
      delta_ventas: 1,
    },
  ],
}

const recipeList = {
  items: [
    {
      id: 1,
      codigo_receta: 'R-1',
      nombre: 'Receta 1',
      version: '1',
      estado: 'Publicada',
      es_base: true,
      proceso: 'Proceso 1',
    },
  ],
  total: 1,
  limit: 25,
  offset: 0,
}

const courseList = {
  items: [{ curso_id: 'CUR-1', curso_nombre: 'Curso 1', curso_fecha: '2026-01-01' }],
  total: 1,
  limit: 25,
  offset: 0,
}

const ingredientList = {
  items: [
    {
      id: 'ireks:1',
      codigo: 'ING-1',
      nombre: 'Ingrediente 1',
      fabricante_id: '',
      proveedor_id: 'PROV-1',
      familia_id: 'FAM-1',
      subfamilia_id: 'SUB-1',
      unidad: 'kg',
      activo: true,
      precio: 0,
      source: 'ireks',
    },
    {
      id: 'std:1',
      codigo: 'STD-1',
      nombre: 'Materia prima 1',
      fabricante_id: '',
      proveedor_id: 'PROV-2',
      familia_id: 'FAM-2',
      subfamilia_id: 'SUB-2',
      unidad: 'kg',
      activo: true,
      precio: 2.5,
      source: 'std',
    },
  ],
  total: 2,
  limit: 25,
  offset: 0,
}

const ireksIngredientList = {
  items: [
    {
      id: 1,
      almacen_id: 'ALM-1',
      fabricante_id: 'FAB-1',
      distribuidor_id: 'DIST-1',
      articulo_id: 'ART-1',
      articulo_referencia: 'IR-001',
      articulo_referencia_corta: 'IR-1',
      articulo_descripcion: 'Producto IREKS 1',
      articulo_envase_id: 'ENV-1',
      articulo_contenido_unidad: 'kg',
      articulo_envase_cantidad: 1,
      articulo_envase_peso: 1,
      articulo_envase_unidad_medida: 'kg',
      articulo_envase_peso_total: 1,
      transporte_pallet_tipo: '',
      transporte_cajas_por_capa: 0,
      transporte_capas_por_pallet: 0,
      transporte_cajas_por_pallet: 0,
      transporte_unidades_por_pallet: 0,
      transporte_kg_por_pallet: 0,
      transporte_observaciones: '',
      articulo_familia_id: 'FAM-1',
      articulo_grupo_id: 'GRP-1',
      articulo_subfamilia_id: 'SUB-1',
      categoria: 'PAN',
      articulo_status_activo: true,
      articulo_status_en_lista: true,
    },
    {
      id: 2,
      almacen_id: 'ALM-1',
      fabricante_id: 'FAB-2',
      distribuidor_id: 'DIST-2',
      articulo_id: 'ART-2',
      articulo_referencia: 'IR-002',
      articulo_referencia_corta: 'IR-2',
      articulo_descripcion: 'Producto IREKS 2',
      articulo_envase_id: 'ENV-2',
      articulo_contenido_unidad: 'kg',
      articulo_envase_cantidad: 2,
      articulo_envase_peso: 2,
      articulo_envase_unidad_medida: 'kg',
      articulo_envase_peso_total: 2,
      transporte_pallet_tipo: '',
      transporte_cajas_por_capa: 0,
      transporte_capas_por_pallet: 0,
      transporte_cajas_por_pallet: 0,
      transporte_unidades_por_pallet: 0,
      transporte_kg_por_pallet: 0,
      transporte_observaciones: '',
      articulo_familia_id: 'FAM-2',
      articulo_grupo_id: 'GRP-2',
      articulo_subfamilia_id: 'SUB-2',
      categoria: 'MIX',
      articulo_status_activo: true,
      articulo_status_en_lista: false,
    },
  ],
  total: 2,
  limit: 25,
  offset: 0,
  catalogs: {
    distribuidores: [],
    fabricantes: [],
    familias: [],
    subfamilias: [],
    envases: [],
  },
}

const warehouseStock = {
  items: [
    { almacen_id: 'ALM-1', articulo_id: 'ART-1', cantidad_total: 12.5 },
    { almacen_id: 'ALM-1', articulo_id: 'ART-2', cantidad_total: 3 },
  ],
  total: 2,
  limit: 12,
  offset: 0,
}

const warehouseMovements = {
  items: [
    {
      id: 1,
      almacen_id: 'ALM-1',
      articulo_id: 'ART-1',
      pedido_numero: 'P-1',
      pedido_albaran_numero: 'A-1',
      cantidad: 4,
      articulo_lote: 'L-1',
      fecha_pedido: '2026-01-01',
      albaran_item_id: 'AI-1',
    },
  ],
  total: 1,
  limit: 12,
  offset: 0,
}

const warehouseHistory = {
  items: [
    {
      inventario_id: 'INV-1',
      almacen_id: 'ALM-1',
      fecha: '2026-01-02',
      contador: 'Contador 1',
      aprobador: 'Aprobador 1',
      estado: 'Cerrado',
      lineas: 1,
      ajustes: 1,
    },
  ],
  total: 1,
  limit: 12,
  offset: 0,
}

const orderList = {
  items: [
    {
      pedido_id: 'P-1',
      almacen_id: 'ALM-1',
      almacen_nombre: 'Almacen 1',
      pedido_fecha: '2026-01-03',
      pedido_numero: 'PED-1',
      pedido_albaran_numero: 'ALB-1',
      pedido_factura_numero: 'FAC-1',
      pedido_ref: 'REF-1',
      pedido_estado: 'N',
      semana: 1,
      total_kg: 25.5,
    },
  ],
  total: 1,
  limit: 25,
  offset: 0,
}

const orderDetail = {
  pedido_id: 'P-1',
  almacen_id: 'ALM-1',
  pedido_fecha: '2026-01-03',
  pedido_numero: 'PED-1',
  pedido_albaran_numero: 'ALB-1',
  pedido_factura_numero: 'FAC-1',
  pedido_ref: 'REF-1',
  pedido_estado: 'N',
}

const orderItems = {
  items: [
    {
      item_id: 'I-1',
      pedido_id: 'P-1',
      pedido_numero: 'PED-1',
      pedido_albaran_numero: 'ALB-1',
      pedido_item_fecha: '2026-01-03',
      articulo_id: 'ART-1',
      articulo_cantidad: 5,
    },
  ],
  total: 1,
  limit: 25,
  offset: 0,
}

const orderPending = {
  items: [
    {
      pendiente_id: 'PE-1',
      pedido_id: 'P-1',
      albaran_id: 'ALB-1',
      articulo_id: 'ART-1',
      cantidad_pedida: 5,
      cantidad_recibida: 3,
      cantidad_pendiente: 2,
      estado: 'Pendiente',
      fecha_registro: '2026-01-03',
    },
  ],
  total: 1,
  limit: 25,
  offset: 0,
}

const technicianList = {
  items: [
    {
      tecnico_id: 'TECH-1',
      tecnico_codigo: 10,
      nombre: 'Ana',
      apellidos: 'Lopez',
      movil: '600000010',
      interno: '101',
      email: 'ana@example.com',
    },
  ],
  total: 1,
  limit: 25,
  offset: 0,
}

const technicianDetail = {
  ...technicianList.items[0],
  created_at: null,
  updated_at: null,
}

const distributorList = {
  items: [
    {
      distribuidor_id: 'DIST-1',
      distribuidor_codigo: 10,
      distribuidor_razon_social: 'Distribuciones Norte SL',
      distribuidor_nombre_comercial: 'Norte',
      distribuidor_cif: 'B123',
      distribuidor_telefono: '928000011',
      distribuidor_contacto: 'Ana',
    },
  ],
  total: 1,
  limit: 25,
  offset: 0,
}

const distributorDetail = {
  ...distributorList.items[0],
}

const customerList = {
  items: [
    {
      cliente_id: 'C-1',
      cliente_codigo: 101,
      cliente_nombre_comercial: 'Cliente Uno',
      cliente_nombre_fiscal: 'Cliente Uno SL',
      cliente_cif: 'B123',
      cliente_grupo: 'Grupo A',
      cliente_tipo: 'Distribuidor',
      cliente_email: 'cliente1@example.com',
      cliente_telefono: '928000000',
      cliente_prospeccion: false,
      activo: true,
    },
  ],
  total: 1,
  limit: 25,
  offset: 0,
}

const customerDetail = {
  ...customerList.items[0],
  cliente_nombre_interno: 'Interno Uno',
  cliente_abreviatura: 'C1',
  cliente_direccion: 'Calle 1',
  cliente_direccion_cp: '35001',
  cliente_direccion_localidad_id: 'L1',
  cliente_direccion_municipio_id: 'M1',
  cliente_direccion_provincia_id: 'P1',
  cliente_direccion_isla_id: 'I1',
  distribuidor_id: 'D1',
}

const customerContacts = {
  items: [
    {
      contacto_id: 'CT-1',
      contacto_codigo: 1,
      cliente_id: 'C-1',
      cliente_nombre: 'Cliente Uno',
      nombre: 'Ana',
      apellidos: 'Lara',
      cargo: 'Ventas',
      nif: '123',
      telefono: '600000000',
      email: 'ana@example.com',
    },
  ],
  total: 1,
  limit: 25,
  offset: 0,
}

vi.mock('./api/sales', () => ({
  getSalesAnnualSummary: vi.fn(async () => salesSummary),
  listSalesAnnualClients: vi.fn(async () => ({ items: [{ id: '1', name: 'Cliente 1', code: 'C1' }] })),
  listSalesAnnualYears: vi.fn(async () => ({ items: [{ year: 2024, label: '2024' }] })),
}))

vi.mock('./api/customers', () => ({
  getCustomerDetail: vi.fn(async () => customerDetail),
  listCustomers: vi.fn(async () => customerList),
}))

vi.mock('./api/contacts', () => ({
  getContactDetail: vi.fn(async () => ({
    contacto_id: 'CT-1',
    contacto_codigo: 1,
    cliente_id: 'C-1',
    cliente_nombre: 'Cliente Uno',
    nombre: 'Ana',
    apellidos: 'Lara',
    cargo: 'Ventas',
    nif: '123',
    telefono: '600000000',
    email: 'ana@example.com',
    created_at: null,
    updated_at: null,
  })),
  listContactCompanies: vi.fn(async () => [{ cliente_id: 'C-1', nombre: 'Cliente Uno' }]),
  listContacts: vi.fn(async () => customerContacts),
}))

vi.mock('./api/recipes', () => ({
  getRecipeDetail: vi.fn(async () => ({
    id: 1,
    nombre: 'Receta 1',
    codigo_receta: 'R-1',
    cliente_id: 'C-1',
    proceso: 'Proceso 1',
    estado: 'Publicada',
  })),
  listRecipeItems: vi.fn(async () => ({
    items: [
      {
        id: 1,
        orden: 1,
        nombre_mostrado: 'Harina',
        codigo_ingrediente: 'H-1',
        cantidad_base_g: 1,
        cantidad_calculada_g: 1,
      },
    ],
  })),
  listRecipes: vi.fn(async () => recipeList),
}))

vi.mock('./api/courses', () => ({
  getCourseDetail: vi.fn(async () => ({
    curso_id: 'CUR-1',
    curso_nombre: 'Curso 1',
    curso_fecha: '2026-01-01',
  })),
  listCourseAttendees: vi.fn(async () => ({
    items: [{ id: 1, nombre: 'Asistente 1', empresa: 'Empresa 1', confirmado: true }],
  })),
  listCourses: vi.fn(async () => courseList),
}))

vi.mock('./api/ingredients', () => ({
  getIreksIngredientDetail: vi.fn(async (rowId: number) => {
    if (rowId === 2) {
      return {
        id: 2,
        almacen_id: 'ALM-1',
        fabricante_id: 'FAB-2',
        distribuidor_id: 'DIST-2',
        articulo_id: 'ART-2',
        articulo_referencia: 'IR-002',
        articulo_referencia_corta: 'IR-2',
        articulo_descripcion: 'Producto IREKS 2',
        articulo_envase_id: 'ENV-2',
        articulo_contenido_unidad: 'kg',
        articulo_envase_cantidad: 2,
        articulo_envase_peso: 2,
        articulo_envase_unidad_medida: 'kg',
        articulo_envase_peso_total: 2,
        transporte_pallet_tipo: '',
        transporte_cajas_por_capa: 0,
        transporte_capas_por_pallet: 0,
        transporte_cajas_por_pallet: 0,
        transporte_unidades_por_pallet: 0,
        transporte_kg_por_pallet: 0,
        transporte_observaciones: '',
        articulo_familia_id: 'FAM-2',
        articulo_grupo_id: 'GRP-2',
        articulo_subfamilia_id: 'SUB-2',
        categoria: 'MIX',
        articulo_status_activo: true,
        articulo_status_en_lista: false,
      }
    }

    return {
      id: 1,
      almacen_id: 'ALM-1',
      fabricante_id: 'FAB-1',
      distribuidor_id: 'DIST-1',
      articulo_id: 'ART-1',
      articulo_referencia: 'IR-001',
      articulo_referencia_corta: 'IR-1',
      articulo_descripcion: 'Producto IREKS 1',
      articulo_envase_id: 'ENV-1',
      articulo_contenido_unidad: 'kg',
      articulo_envase_cantidad: 1,
      articulo_envase_peso: 1,
      articulo_envase_unidad_medida: 'kg',
      articulo_envase_peso_total: 1,
      transporte_pallet_tipo: '',
      transporte_cajas_por_capa: 0,
      transporte_capas_por_pallet: 0,
      transporte_cajas_por_pallet: 0,
      transporte_unidades_por_pallet: 0,
      transporte_kg_por_pallet: 0,
      transporte_observaciones: '',
      articulo_familia_id: 'FAM-1',
      articulo_grupo_id: 'GRP-1',
      articulo_subfamilia_id: 'SUB-1',
      categoria: 'PAN',
      articulo_status_activo: true,
      articulo_status_en_lista: true,
    }
  }),
  listIreksIngredients: vi.fn(async () => ireksIngredientList),
  getIngredientDetail: vi.fn(async (ingredientId: string) => {
    if (ingredientId === 'std:1') {
      return {
        id: 'std:1',
        codigo: 'STD-1',
        nombre: 'Materia prima 1',
        fabricante_id: '',
        proveedor_id: 'PROV-2',
        familia_id: 'FAM-2',
        subfamilia_id: 'SUB-2',
        unidad: 'kg',
        activo: true,
        precio: 2.5,
        source: 'std',
      }
    }

    return {
      id: 'ireks:1',
      codigo: 'ING-1',
      nombre: 'Ingrediente 1',
      fabricante_id: '',
      proveedor_id: 'PROV-1',
      familia_id: 'FAM-1',
      subfamilia_id: 'SUB-1',
      unidad: 'kg',
      activo: true,
      precio: 0,
      source: 'ireks',
    }
  }),
  listIngredients: vi.fn(async () => ingredientList),
}))

vi.mock('./api/warehouse', () => ({
  getInventoryDetail: vi.fn(async () => [
    {
      id: 1,
      inventario_id: 'INV-1',
      almacen_id: 'ALM-1',
      articulo_id: 'ART-1',
      articulo_lote: 'L-1',
      articulo_caducidad: '2026-12-31',
      teorico_uds: 10,
      conteo_uds: 9,
      diferencia_uds: -1,
      kg_ajuste: -2.5,
    },
  ]),
  listInventoryHistory: vi.fn(async () => warehouseHistory),
  listMovements: vi.fn(async () => warehouseMovements),
  listStock: vi.fn(async () => warehouseStock),
}))

vi.mock('./api/orders', () => ({
  getOrderDetail: vi.fn(async () => orderDetail),
  listOrderItems: vi.fn(async () => orderItems),
  listOrderPending: vi.fn(async () => orderPending),
  listOrders: vi.fn(async () => orderList),
}))

vi.mock('./api/technicians', () => ({
  getTechnicianDetail: vi.fn(async () => technicianDetail),
  listTechnicians: vi.fn(async () => technicianList),
}))

vi.mock('./api/distributors', () => ({
  getDistributorDetail: vi.fn(async () => distributorDetail),
  listDistributors: vi.fn(async () => distributorList),
}))

describe('App shell smoke', () => {
  it('renders the app shell and the main modules', async () => {
    render(<App />)
    const getNav = () => within(screen.getByRole('navigation', { name: 'Navegacion principal' }))

    expect(screen.getByText('GESTIÓN IREKS')).toBeInTheDocument()
    await screen.findByRole('heading', { name: 'Dashboard' })

    expect(getNav().getByRole('button', { name: 'Inicio' })).toBeInTheDocument()
    expect(getNav().getByRole('button', { name: 'Ventas' })).toBeInTheDocument()
    expect(getNav().getByRole('button', { name: 'Recetas' })).toBeInTheDocument()
    expect(getNav().getByRole('button', { name: 'Cursos' })).toBeInTheDocument()
    expect(getNav().getByRole('button', { name: 'Clientes' })).toBeInTheDocument()
    expect(getNav().getByRole('button', { name: 'Contactos' })).toBeInTheDocument()
    expect(getNav().getByRole('button', { name: 'Pedidos' })).toBeInTheDocument()
    expect(getNav().getByRole('button', { name: 'Tecnicos' })).toBeInTheDocument()
    expect(getNav().getByRole('button', { name: 'Distribuidores' })).toBeInTheDocument()
    expect(getNav().getByRole('button', { name: 'Productos IREKS' })).toBeInTheDocument()
    expect(getNav().getByRole('button', { name: 'Materias primas' })).toBeInTheDocument()
    expect(getNav().getByRole('button', { name: 'Almacen' })).toBeInTheDocument()
  })

  it('switches the visible page when the user clicks the sidebar items', async () => {
    render(<App />)
    const getNav = () => within(screen.getByRole('navigation', { name: 'Navegacion principal' }))

    await screen.findByRole('heading', { name: 'Dashboard' })

    fireEvent.click(getNav().getByRole('button', { name: 'Recetas' }))
    expect(await screen.findByPlaceholderText('Buscar receta por nombre, codigo o proceso')).toBeInTheDocument()

    fireEvent.click(getNav().getByRole('button', { name: 'Cursos' }))
    expect(await screen.findByPlaceholderText('Buscar curso por nombre o codigo')).toBeInTheDocument()

    fireEvent.click(getNav().getByRole('button', { name: 'Clientes' }))
    expect(await screen.findByPlaceholderText('Buscar cliente...')).toBeInTheDocument()

    fireEvent.click(getNav().getByRole('button', { name: 'Contactos' }))
    expect(await screen.findByRole('heading', { name: 'Contactos' })).toBeInTheDocument()

    fireEvent.click(getNav().getByRole('button', { name: 'Inicio' }))
    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()

    fireEvent.click(getNav().getByRole('button', { name: 'Pedidos' }))
    expect(await screen.findByPlaceholderText('Ano (ej: 2026)')).toBeInTheDocument()

    fireEvent.click(getNav().getByRole('button', { name: 'Tecnicos' }))
    expect(await screen.findByPlaceholderText('Buscar por nombre, apellido, movil, interno o email')).toBeInTheDocument()

    fireEvent.click(getNav().getByRole('button', { name: 'Distribuidores' }))
    expect(await screen.findByPlaceholderText('Buscar por codigo, nombre, razon social, CIF o contacto')).toBeInTheDocument()

    fireEvent.click(getNav().getByRole('button', { name: 'Productos IREKS' }))
    expect(await screen.findByRole('heading', { name: 'Productos IREKS', level: 3 })).toBeInTheDocument()
    expect(await screen.findByPlaceholderText('Buscar producto por referencia o nombre')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Anterior' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Siguiente' })).not.toBeInTheDocument()
    expect(screen.queryByText(/Pagina/i)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Refrescar' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Datos' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Tarifa' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Detalle del producto' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Información del producto' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Tarifa' }))
    expect(await screen.findByText('Tarifa pendiente de migración read-only')).toBeInTheDocument()

    fireEvent.click(getNav().getByRole('button', { name: 'Materias primas' }))
    expect(await screen.findByPlaceholderText('Buscar materia prima por nombre, codigo o referencia')).toBeInTheDocument()

    fireEvent.click(getNav().getByRole('button', { name: 'Almacen' }))
    expect(await screen.findByRole('heading', { name: 'Almacén', level: 2 })).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Stock actual' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Últimos movimientos' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Histórico de inventarios' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Detalle de inventario' })).toBeInTheDocument()

    fireEvent.click(getNav().getByRole('button', { name: 'Ventas' }))
    expect(await screen.findByRole('heading', { name: 'Ventas' })).toBeInTheDocument()
  })
})
