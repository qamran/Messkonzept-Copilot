import { useAuth } from '@clerk/react'
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/lib/api'

import { HomePage } from './HomePage'

vi.mock('@clerk/react', () => ({ useAuth: vi.fn() }))
vi.mock('@/lib/api', () => ({ apiFetch: vi.fn() }))

type AuthState = ReturnType<typeof useAuth>

function mockAuth(isLoaded: boolean, isSignedIn: boolean) {
  vi.mocked(useAuth).mockReturnValue({ isLoaded, isSignedIn } as unknown as AuthState)
}

afterEach(() => vi.resetAllMocks())

describe('HomePage', () => {
  it('asks a signed-out user to sign in and calls no protected route', () => {
    mockAuth(true, false)
    render(<HomePage />)
    expect(screen.getByText(/You are signed out/)).toBeInTheDocument()
    expect(apiFetch).not.toHaveBeenCalled()
  })

  it('shows what the backend says about a signed-in user', async () => {
    mockAuth(true, true)
    vi.mocked(apiFetch).mockResolvedValue(
      Response.json({ id: 'user_1', role: 'admin', is_admin: true }),
    )
    render(<HomePage />)
    expect(await screen.findByText('user_1')).toBeInTheDocument()
    expect(screen.getByText('admin')).toBeInTheDocument()
    expect(apiFetch).toHaveBeenCalledWith('/api/me')
  })

  it('shows the backend status when the call fails', async () => {
    mockAuth(true, true)
    vi.mocked(apiFetch).mockResolvedValue(new Response('', { status: 401 }))
    render(<HomePage />)
    expect(await screen.findByText(/Backend answered 401/)).toBeInTheDocument()
  })
})
