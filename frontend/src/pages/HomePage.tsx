import { useAuth } from '@clerk/react'
import { useEffect, useState } from 'react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { apiFetch } from '@/lib/api'

type Me = { id: string; role: string | null; is_admin: boolean }
type MeState = { status: 'loading' } | { status: 'ok'; me: Me } | { status: 'error'; message: string }

/** Start page: shows the login state as the backend sees it (`GET /api/me`). */
export function HomePage() {
  const { isLoaded, isSignedIn } = useAuth()

  return (
    <section className="space-y-6">
      <h1 className="font-heading text-2xl font-semibold">Messkonzept-Copilot</h1>
      {!isLoaded ? null : isSignedIn ? (
        <BackendIdentity />
      ) : (
        <p className="text-muted-foreground">You are signed out. Sign in to continue.</p>
      )}
    </section>
  )
}

function BackendIdentity() {
  const [state, setState] = useState<MeState>({ status: 'loading' })

  useEffect(() => {
    let active = true
    apiFetch('/api/me')
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`Backend answered ${response.status}`)
        }
        const me = (await response.json()) as Me
        if (active) setState({ status: 'ok', me })
      })
      .catch((error: unknown) => {
        const message = error instanceof Error ? error.message : String(error)
        if (active) setState({ status: 'error', message })
      })
    return () => {
      active = false
    }
  }, [])

  return (
    <Card>
      <CardHeader>
        <CardTitle>Signed in: what the backend sees</CardTitle>
      </CardHeader>
      <CardContent>
        {state.status === 'loading' && <p className="text-muted-foreground">Checking…</p>}
        {state.status === 'error' && <p className="text-destructive">{state.message}</p>}
        {state.status === 'ok' && (
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
            <dt className="text-muted-foreground">User ID</dt>
            <dd>{state.me.id}</dd>
            <dt className="text-muted-foreground">Role</dt>
            <dd>{state.me.role ?? 'none'}</dd>
            <dt className="text-muted-foreground">Admin</dt>
            <dd>{state.me.is_admin ? 'yes' : 'no'}</dd>
          </dl>
        )}
      </CardContent>
    </Card>
  )
}
