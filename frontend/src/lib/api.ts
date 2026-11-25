import { getToken } from '@clerk/react'

/**
 * Fetch from the backend API with the Clerk session token attached.
 *
 * `path` must start with `/` (e.g. `/api/me`); it is resolved against `VITE_API_URL`.
 * Absolute URLs are refused so the token is never sent to another host.
 * When the user is signed out, the request goes out without an Authorization header.
 */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  if (!path.startsWith('/') || path.startsWith('//')) {
    throw new Error(`apiFetch needs a path starting with "/", got "${path}"`)
  }
  const headers = new Headers(init.headers)
  const token = await getToken()
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  const base = (import.meta.env.VITE_API_URL ?? '').replace(/\/+$/, '')
  return fetch(`${base}${path}`, { ...init, headers })
}
