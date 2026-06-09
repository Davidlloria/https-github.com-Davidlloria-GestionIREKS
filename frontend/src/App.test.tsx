import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
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

vi.mock('./api/sales', () => ({
  getSalesAnnualSummary: vi.fn(async () => salesSummary),
  listSalesAnnualClients: vi.fn(async () => ({ items: [{ id: '1', name: 'Cliente 1', code: 'C1' }] })),
  listSalesAnnualYears: vi.fn(async () => ({ items: [{ year: 2024, label: '2024' }] })),
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
  listRecipes: vi.fn(async () => ({
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
  })),
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
  listCourses: vi.fn(async () => ({
    items: [{ curso_id: 'CUR-1', curso_nombre: 'Curso 1', curso_fecha: '2026-01-01' }],
    total: 1,
    limit: 25,
    offset: 0,
  })),
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
  listIngredients: vi.fn(async () => ({
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
  })),
}))

describe('App shell', () => {
  beforeEach(() => {
    render(<App />)
  })

  it('renders the app and switches between the four read-only views', async () => {
    await screen.findByText('Ventas anual')

    expect(screen.getByRole('tab', { name: 'Ventas' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Recetas' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Cursos' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Ingredientes' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('tab', { name: 'Recetas' }))
    await waitFor(() => {
      expect(screen.getByPlaceholderText('Buscar receta por nombre, codigo o proceso')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('tab', { name: 'Cursos' }))
    await waitFor(() => {
      expect(screen.getByPlaceholderText('Buscar curso por nombre o codigo')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('tab', { name: 'Ingredientes' }))
    await waitFor(() => {
      expect(screen.getByPlaceholderText('Buscar ingrediente por nombre, codigo o referencia')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('tab', { name: 'Ventas' }))
    await waitFor(() => {
      expect(screen.getByText('Ventas anual')).toBeInTheDocument()
    })
  })
})
