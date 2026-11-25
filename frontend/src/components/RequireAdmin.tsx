import { useUser } from '@clerk/react'
import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'

import { isAdmin } from '@/lib/roles'

/**
 * Route guard for admin pages. It only shapes the UI: the backend checks the token
 * and the role on every admin request (`require_admin`).
 */
export function RequireAdmin({ children }: { children: ReactNode }) {
  const { isLoaded, isSignedIn, user } = useUser()
  const location = useLocation()

  if (!isLoaded) {
    return null
  }
  if (!isSignedIn) {
    return <Navigate to="/sign-in" replace state={{ from: location.pathname }} />
  }
  if (!isAdmin(user?.publicMetadata)) {
    return (
      <section className="space-y-2">
        <h1 className="font-heading text-2xl font-semibold">Admin role required</h1>
        <p className="text-muted-foreground">
          You are signed in, but this page is for admins only.
        </p>
      </section>
    )
  }
  return <>{children}</>
}
