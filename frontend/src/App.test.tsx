import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import App from './App'

const salesSummary = {
  source: 'ireks',
  year: 2024,
  month: 1,
  acumulado: false,
  total: 1,
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
  ],
  total: 1,
  limit: 25,
  offset: 0,
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
  getIngredientDetail: vi.fn(async () => ({
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
  })),
  listIngredients: vi.fn(async () => ingredientList),
}))

describe('App shell smoke', () => {
  it('renders the app shell and the main tabs', async () => {
    render(<App />)

    await screen.findByText('Ventas anual')

    expect(screen.getByRole('tab', { name: 'Ventas' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Recetas' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Cursos' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Clientes' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Ingredientes' })).toBeInTheDocument()
  })

  it('switches the visible page when the user clicks the tabs', async () => {
    render(<App />)

    await screen.findByText('Ventas anual')

    fireEvent.click(screen.getByRole('tab', { name: 'Recetas' }))
    expect(await screen.findByPlaceholderText('Buscar receta por nombre, codigo o proceso')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('tab', { name: 'Cursos' }))
    expect(await screen.findByPlaceholderText('Buscar curso por nombre o codigo')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('tab', { name: 'Clientes' }))
    expect(await screen.findByPlaceholderText('Buscar cliente por nombre, email o CIF')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('tab', { name: 'Ingredientes' }))
    expect(await screen.findByPlaceholderText('Buscar ingrediente por nombre, codigo o referencia')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('tab', { name: 'Ventas' }))
    expect(await screen.findByText('Ventas anual')).toBeInTheDocument()
  })
})
