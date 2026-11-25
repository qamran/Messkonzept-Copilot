import { useEffect, useState } from 'react'

import { apiFetch } from '@/lib/api'

/**
 * Warns when the API runs another commit than the one this frontend was built from.
 *
 * CD builds the production frontend with `VITE_COMMIT` (decision 46). Local and preview builds
 * have none and skip the check: previews call the production API and would always differ.
 * A failed request shows nothing; the page must keep working.
 */
export function VersionWarning({
  builtCommit = import.meta.env.VITE_COMMIT ?? '',
}: {
  builtCommit?: string
}) {
  const [apiCommit, setApiCommit] = useState<string | null>(null)

  useEffect(() => {
    if (!builtCommit) return
    let active = true
    apiFetch('/api/version')
      .then(async (response) => {
        if (!response.ok) return
        const body: unknown = await response.json()
        const commit = (body as { commit?: unknown } | null)?.commit
        if (active && typeof commit === 'string') setApiCommit(commit)
      })
      .catch(() => {
        // Unreachable API or bad JSON: no warning, the page keeps working.
      })
    return () => {
      active = false
    }
  }, [builtCommit])

  if (!builtCommit || apiCommit === null || apiCommit === builtCommit) return null
  return (
    <div role="alert" className="border-b border-amber-300 bg-amber-50 px-4 py-2 text-sm text-amber-900">
      API version differs from this page (page {builtCommit.slice(0, 7)}, API{' '}
      {apiCommit.slice(0, 7)}). Reload the page; if this stays, a deploy is in progress or was
      rolled back.
    </div>
  )
}
