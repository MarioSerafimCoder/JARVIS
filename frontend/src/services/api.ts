export const API_URL = 'http://127.0.0.1:8000/api'

export async function api<T = unknown>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init)
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(data.detail || `Falha HTTP ${response.status}`)
  }
  return response.json()
}

export const jsonRequest = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: body === undefined ? undefined : JSON.stringify(body),
})

