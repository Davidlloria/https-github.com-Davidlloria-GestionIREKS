import { afterEach, describe, expect, it, vi } from 'vitest'
import { getCourseDetail, listCourseAttendees, listCourses } from './courses'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('courses api client', () => {
  it('lists courses with search and paging query params', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ items: [], total: 0 }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await listCourses('curso', 10, 20)

    expect(result).toEqual({ items: [], total: 0 })
    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/courses?q=curso&limit=10&offset=20',
      expect.any(Object),
    )
  })

  it('fetches detail and attendees from course-specific endpoints', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ curso_id: 'CUR-1' }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [{ id: 1 }] }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(getCourseDetail('CUR-1')).resolves.toEqual({ curso_id: 'CUR-1' })
    await expect(listCourseAttendees('CUR-1')).resolves.toEqual({ items: [{ id: 1 }] })

    expect(fetchMock).toHaveBeenNthCalledWith(1, 'http://127.0.0.1:8000/courses/CUR-1', expect.any(Object))
    expect(fetchMock).toHaveBeenNthCalledWith(2, 'http://127.0.0.1:8000/courses/CUR-1/attendees', expect.any(Object))
  })
})
