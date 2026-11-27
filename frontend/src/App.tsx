import { Route, Routes } from 'react-router'

import { AppShell } from '@/components/AppShell'
import { RequireAdmin } from '@/components/RequireAdmin'
import { AdminPage } from '@/pages/AdminPage'
import { AdvisorPage } from '@/pages/AdvisorPage'
import { HomePage } from '@/pages/HomePage'
import { SignInPage } from '@/pages/SignInPage'

// MKC-36: the two catalogue operators until lane A serves an operator list.
const ADVISOR_OPERATORS = [
  { id: 'stromnetz-berlin', label: 'Stromnetz Berlin' },
  { id: 'sachsennetze', label: 'SachsenNetze' },
]

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/sign-in/*" element={<SignInPage />} />
        <Route path="/advisor" element={<AdvisorPage operators={ADVISOR_OPERATORS} />} />
        <Route
          path="/admin"
          element={
            <RequireAdmin>
              <AdminPage />
            </RequireAdmin>
          }
        />
      </Routes>
    </AppShell>
  )
}
