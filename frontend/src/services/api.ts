export const API_URL = window.location.port === '5173' ? 'http://127.0.0.1:8000/api' : '/api'

export interface ApiFailure { error?: { code?: string; message?: string; details?: string }; detail?: string }

export async function api<T = unknown>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init)
  if (!response.ok) {
    const data = await response.json().catch(() => ({} as ApiFailure)) as ApiFailure
    throw new Error(data.error?.message || data.detail || `Falha HTTP ${response.status}`)
  }
  return response.json()
}

export const jsonRequest = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: body === undefined ? undefined : JSON.stringify(body),
})
