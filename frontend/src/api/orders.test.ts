import { afterEach, describe, expect, it, vi } from 'vitest'
import { getOrderDetail, listOrderItems, listOrderPending, listOrders } from './orders'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('orders api client', () => {
  it('lists orders with filters and paging query params', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ items: [], total: 0 }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await listOrders({ year: '2026', monthFrom: 1, monthTo: 12, almacenId: 'ALM-1', limit: 20, offset: 40 })

    expect(result).toEqual({ items: [], total: 0 })
    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/orders?year=2026&month_from=1&month_to=12&almacen_id=ALM-1&limit=20&offset=40',
      expect.any(Object),
    )
  })

  it('fetches order detail, items and pending rows from the expected endpoints', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ pedido_id: 'P-1' }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [{ item_id: 'I-1' }], total: 1 }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [{ pendiente_id: 'PE-1' }], total: 1 }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(getOrderDetail('P-1')).resolves.toEqual({ pedido_id: 'P-1' })
    await expect(listOrderItems('P-1', 10, 20)).resolves.toEqual({ items: [{ item_id: 'I-1' }], total: 1 })
    await expect(listOrderPending('P-1', 5, 15)).resolves.toEqual({ items: [{ pendiente_id: 'PE-1' }], total: 1 })

    expect(fetchMock).toHaveBeenNthCalledWith(1, 'http://127.0.0.1:8000/orders/P-1', expect.any(Object))
    expect(fetchMock).toHaveBeenNthCalledWith(2, 'http://127.0.0.1:8000/orders/P-1/items?limit=10&offset=20', expect.any(Object))
    expect(fetchMock).toHaveBeenNthCalledWith(3, 'http://127.0.0.1:8000/orders/P-1/pending?limit=5&offset=15', expect.any(Object))
  })
})
