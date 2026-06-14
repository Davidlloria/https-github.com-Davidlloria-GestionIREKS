import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  getSalesAnnualSummary,
  listSalesAnnualClients,
  listSalesAnnualFamilies,
  listSalesAnnualManufacturers,
  listSalesAnnualSubfamilies,
  listSalesAnnualYears,
} from './sales'

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

  it('lists igsa annual years on the expected endpoint', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ items: [{ year: 2024 }] }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await listSalesAnnualYears('igsa')

    expect(result).toEqual({ items: [{ year: 2024 }] })
    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/sales/annual-summary/igsa/years',
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

  it('builds annual summary query params for the extended read-only filters', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ total: 1, items: [] }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await getSalesAnnualSummary({
      source: 'igsa',
      year: 2025,
      month: 6,
      acumulado: true,
      productoTexto: 'BAM',
      fabricanteId: 'FAB-1',
      familiaId: 'FAM-1',
      subfamiliaId: 'SUB-1',
    })

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/sales/annual-summary/igsa?year=2025&month=6&acumulado=true&producto_texto=BAM&fabricante_id=FAB-1&familia_id=FAM-1&subfamilia_id=SUB-1',
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

  it('lists annual manufacturers on the expected endpoint', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ items: [{ id: '1' }] }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await listSalesAnnualManufacturers()

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/sales/annual-summary/filters/manufacturers',
      expect.any(Object),
    )
  })

  it('lists annual families on the expected endpoint', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ items: [{ id: '1' }] }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await listSalesAnnualFamilies('igsa', 'FAB-1')

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/sales/annual-summary/igsa/filters/families?fabricante_id=FAB-1',
      expect.any(Object),
    )
  })

  it('lists annual subfamilies on the expected endpoint', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ items: [{ id: '1' }] }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await listSalesAnnualSubfamilies('igsa', 'FAM-1')

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/sales/annual-summary/igsa/filters/subfamilies?familia_id=FAM-1',
      expect.any(Object),
    )
  })
})
