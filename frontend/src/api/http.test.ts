import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiDelete, apiGet, apiPost } from './http'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('http client', () => {
  it('returns parsed JSON for successful requests', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ ok: true }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await apiGet<{ ok: boolean }>('/status')

    expect(result).toEqual({ ok: true })
    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/status',
      expect.objectContaining({
        headers: { Accept: 'application/json' },
      }),
    )
  })

  it('throws the response text for non-ok requests', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('No permitido', { status: 403 })))

    await expect(apiGet('/blocked')).rejects.toThrow('No permitido')
  })

  it('sends non-json delete requests without parsing a body', async () => {
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    await apiDelete('/items/1')

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/items/1',
      expect.objectContaining({
        method: 'DELETE',
        headers: { Accept: 'application/json' },
      }),
    )
  })

  it('stringifies JSON bodies for post requests', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ id: 1 }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await apiPost<{ id: number }>('/items', { name: 'A' })

    expect(result).toEqual({ id: 1 })
    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/items',
      expect.objectContaining({
        method: 'POST',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'A' }),
      }),
    )
  })
})
