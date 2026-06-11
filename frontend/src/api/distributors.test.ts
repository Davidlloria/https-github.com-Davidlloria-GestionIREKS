import { afterEach, describe, expect, it, vi } from 'vitest'
import { getDistributorDetail, listDistributors } from './distributors'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('distributors api client', () => {
  it('lists distributors with query params', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ items: [], total: 0 }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await listDistributors('Norte', 12, 24)

    expect(result).toEqual({ items: [], total: 0 })
    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/distributors?q=Norte&limit=12&offset=24',
      expect.any(Object),
    )
  })

  it('fetches distributor detail from the expected endpoint', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ distribuidor_id: 'DIST-1' }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(getDistributorDetail('DIST-1')).resolves.toEqual({ distribuidor_id: 'DIST-1' })

    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:8000/distributors/DIST-1', expect.any(Object))
  })
})
