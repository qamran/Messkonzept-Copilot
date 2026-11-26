import { Show, SignInButton, UserButton } from '@clerk/react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import { Button } from '@/components/ui/button'
import { VersionWarning } from '@/components/VersionWarning'

/** Page frame: app name, navigation and the Clerk sign-in or user button. */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-svh bg-background text-foreground">
      <VersionWarning />
      <header className="border-b">
        <div className="mx-auto flex max-w-4xl items-center justify-between gap-4 px-4 py-3">
          <Link to="/" className="font-heading text-lg font-semibold">
            Messkonzept-Copilot
          </Link>
          <nav className="flex items-center gap-3 text-sm">
            <Link to="/admin" className="text-muted-foreground hover:text-foreground">
              Admin
            </Link>
            <Show when="signed-out">
              <SignInButton mode="modal">
                <Button size="sm">Sign in</Button>
              </SignInButton>
            </Show>
            <Show when="signed-in">
              <UserButton />
            </Show>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-4xl px-4 py-8">{children}</main>
    </div>
  )
}
