import { afterEach, describe, expect, it, vi } from 'vitest'
import { getIngredientDetail, listIngredients } from './ingredients'

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
})
