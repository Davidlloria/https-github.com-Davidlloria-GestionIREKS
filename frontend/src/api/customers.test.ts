import { afterEach, describe, expect, it, vi } from 'vitest'
import { getCustomerDetail, listCustomers } from './customers'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('customers api client', () => {
  it('lists customers with search and paging query params', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ items: [], total: 0 }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await listCustomers('cliente', 10, 20)

    expect(result).toEqual({ items: [], total: 0 })
    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/customers?q=cliente&limit=10&offset=20',
      expect.any(Object),
    )
  })

  it('fetches customer detail from the expected endpoint', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ cliente_id: 'C-1' }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(getCustomerDetail('C-1')).resolves.toEqual({ cliente_id: 'C-1' })

    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:8000/customers/C-1', expect.any(Object))
  })
})
