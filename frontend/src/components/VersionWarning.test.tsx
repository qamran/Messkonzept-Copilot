import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { VersionWarning } from './VersionWarning'

vi.mock('@clerk/react', () => ({ getToken: async () => null }))

const BUILT = 'a'.repeat(40)
const OTHER = 'b'.repeat(40)

function stubApi(response: Promise<Response>) {
  const fetchMock = vi.fn(() => response)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function versionResponse(commit: string): Promise<Response> {
  return Promise.resolve(
    new Response(JSON.stringify({ version: '0.1.0', commit }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('VersionWarning (MKC-10.2, decision 46)', () => {
  it('warns when the API runs another commit', async () => {
    const fetchMock = stubApi(versionResponse(OTHER))
    render(<VersionWarning builtCommit={BUILT} />)

    expect(await screen.findByRole('alert')).toHaveTextContent(/API version differs/i)
    expect(fetchMock).toHaveBeenCalledWith('http://api.test/api/version', expect.anything())
  })

  it('shows nothing when the commits match', async () => {
    const fetchMock = stubApi(versionResponse(BUILT))
    render(<VersionWarning builtCommit={BUILT} />)

    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('does not check without a build commit (local and preview builds)', async () => {
    const fetchMock = stubApi(versionResponse(OTHER))
    render(<VersionWarning builtCommit="" />)

    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(fetchMock).not.toHaveBeenCalled()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows nothing when the API cannot be reached', async () => {
    const fetchMock = stubApi(Promise.reject(new TypeError('Failed to fetch')))
    render(<VersionWarning builtCommit={BUILT} />)

    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows nothing when the API answers with an error or odd JSON', async () => {
    const fetchMock = stubApi(Promise.resolve(new Response('{"commit": 1}', { status: 200 })))
    render(<VersionWarning builtCommit={BUILT} />)

    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
