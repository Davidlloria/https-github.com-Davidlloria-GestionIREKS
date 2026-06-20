import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  createCustomer,
  deleteCustomer,
  getCustomerAddressCatalogs,
  getCustomerDetail,
  listCustomers,
  updateCustomer,
} from './customers'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('customers api client', () => {
  it('lists customers with search and paging query params', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ items: [], total: 0 }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await listCustomers('cliente', 10, 20)

    expect(result).toEqual({ items: [], total: 0 })
    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/customers?q=cliente&limit=10&offset=20',
      expect.any(Object),
    )
  })

  it('fetches customer detail from the expected endpoint', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ cliente_id: 'C-1' }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(getCustomerDetail('C-1')).resolves.toEqual({ cliente_id: 'C-1' })

    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:8000/customers/C-1', expect.any(Object))
  })

  it('fetches customer address catalogs from the expected endpoint', async () => {
    const fetchMock = vi.fn(
      async () => new Response(JSON.stringify({ provincias: [], islas: [], municipios: [], codigos_postales: [], localidades: [] }), { status: 200 }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(getCustomerAddressCatalogs()).resolves.toEqual({
      provincias: [],
      islas: [],
      municipios: [],
      codigos_postales: [],
      localidades: [],
    })

    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:8000/customers/address-catalogs', expect.any(Object))
  })

  it('creates a customer with the expected payload', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ cliente_id: 'C-2' }), { status: 201 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(
      createCustomer({
        cliente_nombre_comercial: 'Cliente Nuevo',
        cliente_nombre_fiscal: 'Cliente Nuevo SL',
        cliente_cif: 'B999',
        cliente_telefono: '928000001',
        cliente_email: 'nuevo@example.com',
        cliente_tipo: 'CAFETERIA',
        cliente_actividad: 'PANADERIA',
        cliente_prospeccion: true,
        activo: true,
      }),
    ).resolves.toEqual({ cliente_id: 'C-2' })

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/customers',
      expect.objectContaining({
        method: 'POST',
      }),
    )
  })

  it('updates a customer with the expected payload', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ cliente_id: 'C-1' }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(
      updateCustomer('C-1', {
        cliente_nombre_comercial: 'Cliente Uno Editado',
        cliente_actividad: 'PANADERIA',
      }),
    ).resolves.toEqual({ cliente_id: 'C-1' })

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/customers/C-1',
      expect.objectContaining({
        method: 'PATCH',
      }),
    )
  })

  it('deletes a customer from the expected endpoint', async () => {
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(deleteCustomer('C-1')).resolves.toBeUndefined()

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/customers/C-1',
      expect.objectContaining({
        method: 'DELETE',
      }),
    )
  })
})
