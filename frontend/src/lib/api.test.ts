import { getToken } from '@clerk/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from './api'

vi.mock('@clerk/react', () => ({ getToken: vi.fn() }))

const fetchMock = vi.fn<typeof fetch>()

beforeEach(() => {
  fetchMock.mockResolvedValue(new Response('{}'))
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.mocked(getToken).mockReset()
})

function sentRequest(): { url: string; headers: Headers; init: RequestInit } {
  const [url, init] = fetchMock.mock.calls[0]
  return { url: String(url), headers: new Headers(init?.headers), init: init ?? {} }
}

describe('apiFetch', () => {
  it('sets the Authorization header with the Clerk token', async () => {
    vi.mocked(getToken).mockResolvedValue('tok_123')

    await apiFetch('/api/me')

    expect(sentRequest().headers.get('Authorization')).toBe('Bearer tok_123')
  })

  it('sends no Authorization header when signed out', async () => {
    vi.mocked(getToken).mockResolvedValue(null)

    await apiFetch('/api/version')

    expect(sentRequest().headers.has('Authorization')).toBe(false)
  })

  it('prefixes VITE_API_URL', async () => {
    vi.mocked(getToken).mockResolvedValue(null)

    await apiFetch('/api/me')

    expect(sentRequest().url).toBe('http://api.test/api/me')
  })

  it('keeps the caller headers and options', async () => {
    vi.mocked(getToken).mockResolvedValue('tok_123')

    await apiFetch('/api/runs', {
      method: 'POST',
      body: '{"a":1}',
      headers: { 'Content-Type': 'application/json' },
    })

    const { headers, init } = sentRequest()
    expect(headers.get('Content-Type')).toBe('application/json')
    expect(headers.get('Authorization')).toBe('Bearer tok_123')
    expect(init.method).toBe('POST')
    expect(init.body).toBe('{"a":1}')
  })

  it('rejects absolute URLs, so the token never goes to another host', async () => {
    vi.mocked(getToken).mockResolvedValue('tok_123')

    await expect(apiFetch('https://evil.example/x')).rejects.toThrow(/path/)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  // PR #91 review: URL parsing treats "\" as "/" and drops tabs and newlines.
  it.each([
    ['backslash', '/\\evil.example/x'],
    ['tab', '/\t/evil.example/x'],
    ['newline', '/\n/evil.example/x'],
    ['protocol-relative', '//evil.example/x'],
  ])('rejects a path that could leave the API host (%s)', async (_name, path) => {
    vi.mocked(getToken).mockResolvedValue('tok_123')

    await expect(apiFetch(path)).rejects.toThrow()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it.each([
    ['empty', ''],
    ['relative', '/api'],
  ])('refuses to run when VITE_API_URL is %s', async (_name, value) => {
    vi.stubEnv('VITE_API_URL', value)
    vi.mocked(getToken).mockResolvedValue('tok_123')

    try {
      await expect(apiFetch('/api/me')).rejects.toThrow(/VITE_API_URL/)
      expect(fetchMock).not.toHaveBeenCalled()
    } finally {
      vi.unstubAllEnvs()
    }
  })

  it('keeps a base path in VITE_API_URL', async () => {
    vi.stubEnv('VITE_API_URL', 'http://api.test/base/')
    vi.mocked(getToken).mockResolvedValue(null)

    try {
      await apiFetch('/api/me')
      expect(sentRequest().url).toBe('http://api.test/base/api/me')
    } finally {
      vi.unstubAllEnvs()
    }
  })
})
