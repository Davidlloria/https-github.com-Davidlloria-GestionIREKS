import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  getIreksIngredientDetail,
  getIngredientDetail,
  getStdIngredient,
  listIreksIngredients,
  listIngredients,
  listStdIngredientPrices,
  listStdIngredients,
} from './ingredients'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('ingredients api client', () => {
  it('lists ingredients with search and paging query params', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ items: [], total: 0 }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await listIngredients('harina', 15, 30)

    expect(result).toEqual({ items: [], total: 0 })
    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/ingredients?q=harina&limit=15&offset=30',
      expect.any(Object),
    )
  })

  it('fetches ingredient detail from the expected endpoint', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ id: 'ireks:1' }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(getIngredientDetail('ireks:1')).resolves.toEqual({ id: 'ireks:1' })

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/ingredients/ireks:1',
      expect.any(Object),
    )
  })

  it('lists IREKS ingredients with search and paging query params', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ items: [], total: 0, catalogs: {} }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await listIreksIngredients('harina', 15, 30)

    expect(result).toEqual({ items: [], total: 0, catalogs: {} })
    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/ingredients/ireks?q=harina&limit=15&offset=30',
      expect.any(Object),
    )
  })

  it('fetches IREKS ingredient detail from the expected endpoint', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ id: 1 }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(getIreksIngredientDetail(1)).resolves.toEqual({ id: 1 })

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/ingredients/ireks/1',
      expect.any(Object),
    )
  })

  it('lists standard ingredients with search paging and activity filter', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ items: [], total: 0, limit: 25, offset: 0 }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await listStdIngredients('harina', 25, 50, 'active')

    expect(result).toEqual({ items: [], total: 0, limit: 25, offset: 0 })
    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/ingredients/std?q=harina&limit=25&offset=50&activity_filter=active',
      expect.any(Object),
    )
  })

  it('fetches standard ingredient detail from the expected endpoint', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ articulo_id: '100100E' }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(getStdIngredient('100100E')).resolves.toEqual({ articulo_id: '100100E' })

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/ingredients/std/100100E',
      expect.any(Object),
    )
  })

  it('lists standard ingredient prices from the expected endpoint', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify([]), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(listStdIngredientPrices('100100E')).resolves.toEqual([])

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/ingredients/std/100100E/prices',
      expect.any(Object),
    )
  })
})
