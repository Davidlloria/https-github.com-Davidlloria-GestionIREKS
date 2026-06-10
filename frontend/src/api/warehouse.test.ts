import { afterEach, describe, expect, it, vi } from 'vitest'
import { getInventoryDetail, listInventoryHistory, listMovements, listStock } from './warehouse'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('warehouse api client', () => {
  it('lists stock with query params', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ items: [], total: 0 }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await listStock('ALM-1', 12, 24)

    expect(result).toEqual({ items: [], total: 0 })
    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/warehouse/stock?almacen_id=ALM-1&limit=12&offset=24',
      expect.any(Object),
    )
  })

  it('lists movements with query params', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ items: [], total: 0 }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await listMovements('ALM-1', 8, 16)

    expect(result).toEqual({ items: [], total: 0 })
    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/warehouse/movements?almacen_id=ALM-1&limit=8&offset=16',
      expect.any(Object),
    )
  })

  it('lists inventory history with query params', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ items: [], total: 0 }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await listInventoryHistory('ALM-1', 5, 10)

    expect(result).toEqual({ items: [], total: 0 })
    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/warehouse/inventory/history?almacen_id=ALM-1&limit=5&offset=10',
      expect.any(Object),
    )
  })

  it('fetches inventory detail from the expected endpoint', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify([{ inventario_id: 'INV-1' }]), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(getInventoryDetail('INV-1')).resolves.toEqual([{ inventario_id: 'INV-1' }])

    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:8000/warehouse/inventory/INV-1', expect.any(Object))
  })
})
