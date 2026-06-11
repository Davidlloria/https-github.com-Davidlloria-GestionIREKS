import { afterEach, describe, expect, it, vi } from 'vitest'
import { getTechnicianDetail, listTechnicians } from './technicians'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('technicians api client', () => {
  it('lists technicians with query params', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ items: [], total: 0 }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await listTechnicians('Ana', 12, 24)

    expect(result).toEqual({ items: [], total: 0 })
    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/technicians?q=Ana&limit=12&offset=24',
      expect.any(Object),
    )
  })

  it('fetches technician detail from the expected endpoint', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ tecnico_id: 'TECH-1' }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(getTechnicianDetail('TECH-1')).resolves.toEqual({ tecnico_id: 'TECH-1' })

    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:8000/technicians/TECH-1', expect.any(Object))
  })
})
