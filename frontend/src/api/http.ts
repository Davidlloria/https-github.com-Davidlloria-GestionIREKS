const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

function buildUrl(path: string, params?: Record<string, string | number | undefined>) {
  const query = new URLSearchParams()
  Object.entries(params ?? {}).forEach(([key, value]) => {
    if (value === undefined || value === '') {
      return
    }
    query.set(key, String(value))
  })
  const qs = query.toString()
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  const prefix = API_BASE_URL.endsWith('/') ? API_BASE_URL.slice(0, -1) : API_BASE_URL
  return `${prefix}${normalizedPath}${qs ? `?${qs}` : ''}`
}

async function fetchJson<T>(input: string, init?: RequestInit, expectJson = true): Promise<T> {
  const response = await fetch(input, init)
  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `Error HTTP ${response.status}`)
  }
  if (!expectJson) {
    return undefined as T
  }
  return (await response.json()) as T
}

export async function apiGet<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
  return fetchJson<T>(buildUrl(path, params), {
    headers: { Accept: 'application/json' },
  })
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return fetchJson<T>(buildUrl(path), {
    method: 'POST',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

export async function apiPostForm<T>(path: string, body: FormData): Promise<T> {
  return fetchJson<T>(buildUrl(path), {
    method: 'POST',
    headers: { Accept: 'application/json' },
    body,
  })
}

export async function apiPatch<T>(path: string, body?: unknown): Promise<T> {
  return fetchJson<T>(buildUrl(path), {
    method: 'PATCH',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

export async function apiPut<T>(path: string, body?: unknown): Promise<T> {
  return fetchJson<T>(buildUrl(path), {
    method: 'PUT',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

export async function apiDelete(path: string): Promise<void> {
  await fetchJson<void>(buildUrl(path), {
    method: 'DELETE',
    headers: { Accept: 'application/json' },
  }, false)
}
