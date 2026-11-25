import { Route, Routes } from 'react-router'

import { AppShell } from '@/components/AppShell'
import { RequireAdmin } from '@/components/RequireAdmin'
import { AdminPage } from '@/pages/AdminPage'
import { HomePage } from '@/pages/HomePage'
import { SignInPage } from '@/pages/SignInPage'

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/sign-in/*" element={<SignInPage />} />
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
