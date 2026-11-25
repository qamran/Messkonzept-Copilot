import { useEffect, useState } from 'react'

import { apiFetch } from '@/lib/api'

/** Admin area placeholder; proves the backend's `require_admin` accepts the token. */
export function AdminPage() {
  const [result, setResult] = useState('Checking…')

  useEffect(() => {
    let active = true
    apiFetch('/api/admin/ping')
      .then((response) => {
        if (active) setResult(response.ok ? 'Backend admin check passed' : `Backend answered ${response.status}`)
      })
      .catch((error: unknown) => {
        if (active) setResult(error instanceof Error ? error.message : String(error))
      })
    return () => {
      active = false
    }
  }, [])

  return (
    <section className="space-y-2">
      <h1 className="font-heading text-2xl font-semibold">Admin</h1>
      <p className="text-muted-foreground">{result}</p>
    </section>
  )
}
