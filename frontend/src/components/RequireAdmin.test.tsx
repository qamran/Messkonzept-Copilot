import { useUser } from '@clerk/react'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { RequireAdmin } from './RequireAdmin'

vi.mock('@clerk/react', () => ({ useUser: vi.fn() }))

type UserState = ReturnType<typeof useUser>

function mockUser(state: { isLoaded: boolean; isSignedIn?: boolean; role?: string }) {
  const user = state.isSignedIn ? { publicMetadata: state.role ? { role: state.role } : {} } : null
  vi.mocked(useUser).mockReturnValue({
    isLoaded: state.isLoaded,
    isSignedIn: state.isSignedIn ?? false,
    user,
  } as unknown as UserState)
}

function renderAdminRoute() {
  return render(
    <MemoryRouter initialEntries={['/admin']}>
      <Routes>
        <Route
          path="/admin"
          element={
            <RequireAdmin>
              <p>admin area</p>
            </RequireAdmin>
          }
        />
        <Route path="/sign-in/*" element={<p>sign-in page</p>} />
      </Routes>
    </MemoryRouter>,
  )
}

afterEach(() => vi.mocked(useUser).mockReset())

describe('RequireAdmin', () => {
  it('shows nothing and does not redirect while Clerk is loading', () => {
    mockUser({ isLoaded: false })
    renderAdminRoute()
    expect(screen.queryByText('admin area')).not.toBeInTheDocument()
    expect(screen.queryByText('sign-in page')).not.toBeInTheDocument()
  })

  it('redirects a signed-out user to the sign-in page', () => {
    mockUser({ isLoaded: true, isSignedIn: false })
    renderAdminRoute()
    expect(screen.getByText('sign-in page')).toBeInTheDocument()
    expect(screen.queryByText('admin area')).not.toBeInTheDocument()
  })

  it('blocks a signed-in user without the admin role', () => {
    mockUser({ isLoaded: true, isSignedIn: true })
    renderAdminRoute()
    expect(screen.getByRole('heading', { name: 'Admin role required' })).toBeInTheDocument()
    expect(screen.queryByText('admin area')).not.toBeInTheDocument()
  })

  it('blocks a signed-in user with another role', () => {
    mockUser({ isLoaded: true, isSignedIn: true, role: 'member' })
    renderAdminRoute()
    expect(screen.queryByText('admin area')).not.toBeInTheDocument()
  })

  it('renders the page for an admin', () => {
    mockUser({ isLoaded: true, isSignedIn: true, role: 'admin' })
    renderAdminRoute()
    expect(screen.getByText('admin area')).toBeInTheDocument()
  })
})
