import { afterEach, describe, expect, it, vi } from 'vitest'
import { getContactDetail, listContactCompanies, listContacts } from './contacts'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('contacts api client', () => {
  it('lists contacts with company filter and paging query params', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ items: [], total: 0 }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await listContacts('', 'C-1', 15, 30)

    expect(result).toEqual({ items: [], total: 0 })
    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/contacts?cliente_id=C-1&limit=15&offset=30',
      expect.any(Object),
    )
  })

  it('fetches contact detail and companies from the expected endpoints', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ contacto_id: 'CT-1' }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([{ cliente_id: 'C-1', nombre: 'Cliente Uno' }]), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(getContactDetail('CT-1')).resolves.toEqual({ contacto_id: 'CT-1' })
    await expect(listContactCompanies()).resolves.toEqual([{ cliente_id: 'C-1', nombre: 'Cliente Uno' }])

    expect(fetchMock).toHaveBeenNthCalledWith(1, 'http://127.0.0.1:8000/contacts/CT-1', expect.any(Object))
    expect(fetchMock).toHaveBeenNthCalledWith(2, 'http://127.0.0.1:8000/contacts/companies', expect.any(Object))
  })
})
