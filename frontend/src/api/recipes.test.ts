import { afterEach, describe, expect, it, vi } from 'vitest'
import { getRecipeDetail, listRecipeItems, listRecipes } from './recipes'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('recipes api client', () => {
  it('lists recipes with search and paging query params', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ items: [], total: 0 }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await listRecipes('pan', 25, 50)

    expect(result).toEqual({ items: [], total: 0 })
    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/recipes?q=pan&limit=25&offset=50',
      expect.any(Object),
    )
  })

  it('fetches recipe detail and items from recipe-specific endpoints', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 7, nombre: 'Receta 7' }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [{ id: 1 }] }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(getRecipeDetail(7)).resolves.toEqual({ id: 7, nombre: 'Receta 7' })
    await expect(listRecipeItems(7)).resolves.toEqual({ items: [{ id: 1 }] })

    expect(fetchMock).toHaveBeenNthCalledWith(1, 'http://127.0.0.1:8000/recipes/7', expect.any(Object))
    expect(fetchMock).toHaveBeenNthCalledWith(2, 'http://127.0.0.1:8000/recipes/7/items', expect.any(Object))
  })
})
