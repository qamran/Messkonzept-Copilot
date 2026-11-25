import { getToken } from '@clerk/react'

// Characters that URL parsing rewrites or drops: "\" (read as "/"), control characters
// such as tab and newline (removed), and DEL. Any of them could move the request to another host.
// eslint-disable-next-line no-control-regex
const UNSAFE_PATH = /[\\\u0000-\u001f\u007f]/

/** The backend base URL from `VITE_API_URL`; must be an absolute http(s) URL. */
function apiBase(): URL {
  const raw = import.meta.env.VITE_API_URL ?? ''
  let base: URL
  try {
    base = new URL(raw)
  } catch {
    throw new Error(`VITE_API_URL must be an absolute URL, got "${raw}"`)
  }
  if (base.protocol !== 'http:' && base.protocol !== 'https:') {
    throw new Error(`VITE_API_URL must use http or https, got "${raw}"`)
  }
  return base
}

/**
 * Fetch from the backend API with the Clerk session token attached.
 *
 * `path` must start with a single `/` (e.g. `/api/me`) and is appended to `VITE_API_URL`.
 * The final URL must stay on the API origin, so the token never goes to another host.
 * When the user is signed out, the request goes out without an Authorization header.
 */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  if (!path.startsWith('/') || path.startsWith('//') || UNSAFE_PATH.test(path)) {
    throw new Error(`apiFetch needs a plain path starting with "/", got ${JSON.stringify(path)}`)
  }
  const base = apiBase()
  const url = new URL(base.href.replace(/\/+$/, '') + path)
  if (url.origin !== base.origin) {
    throw new Error(`apiFetch refused a URL outside ${base.origin}`)
  }

  const headers = new Headers(init.headers)
  const token = await getToken()
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  return fetch(url.href, { ...init, headers })
}
