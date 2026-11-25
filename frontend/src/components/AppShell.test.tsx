import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'

import { AppShell } from './AppShell'

vi.mock('@clerk/react', () => ({
  Show: ({ when, children }: { when: string; children: React.ReactNode }) =>
    when === 'signed-out' ? children : null,
  SignInButton: ({ children }: { children: React.ReactNode }) => children,
  UserButton: () => null,
}))

describe('AppShell', () => {
  it('shows the app name, the page content and a sign-in button when signed out', () => {
    render(
      <MemoryRouter>
        <AppShell>
          <p>page content</p>
        </AppShell>
      </MemoryRouter>,
    )

    expect(screen.getByRole('link', { name: 'Messkonzept-Copilot' })).toBeInTheDocument()
    expect(screen.getByText('page content')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument()
  })
})
