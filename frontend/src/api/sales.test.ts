import { afterEach, describe, expect, it, vi } from 'vitest'
import { getSalesAnnualSummary, listSalesAnnualClients, listSalesAnnualYears } from './sales'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('sales api client', () => {
  it('lists annual years on the expected endpoint', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ items: [{ year: 2024 }] }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await listSalesAnnualYears()

    expect(result).toEqual({ items: [{ year: 2024 }] })
    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/sales/annual-summary/years',
      expect.objectContaining({
        headers: { Accept: 'application/json' },
      }),
    )
  })

  it('builds annual summary query params', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ total: 1, items: [] }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await getSalesAnnualSummary(2024, 'C-1')

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/sales/annual-summary?year=2024&cliente_id=C-1',
      expect.any(Object),
    )
  })

  it('omits empty client filters from the query string', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ total: 1, items: [] }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await getSalesAnnualSummary(2024)

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/sales/annual-summary?year=2024',
      expect.any(Object),
    )
  })

  it('lists annual clients on the expected endpoint', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ items: [{ id: '1' }] }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await listSalesAnnualClients()

    expect(result).toEqual({ items: [{ id: '1' }] })
    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/sales/annual-summary/filters/clients',
      expect.any(Object),
    )
  })
})
