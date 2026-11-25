# MKC-7 plan: frontend skeleton with Clerk

**Ticket:** MKC-7 (#7). **Branch:** `mkc-7-frontend-skeleton`.

**Goal:** a React app with login and an admin role, deployable to Vercel previews, and a backend that verifies Clerk tokens.

## Sub-issues

| Key | What |
|---|---|
| MKC-7.1 | Backend: `mkc.api.auth` with `require_user` and `require_admin`; `GET /api/me`; CORS allow-list for local dev |
| MKC-7.2 | Frontend scaffold: Vite + React + TypeScript + Tailwind + shadcn/ui, ESLint, vitest; CI frontend job live; `npm audit` in the dependency scan |
| MKC-7.3 | `apiFetch` and the `RequireAdmin` guard, with pages for the three states |
| MKC-7.4 | Clerk instance decision in ADR 002 and the design doc; local check of the three states |

## User decisions (25.11.2026)

- **Clerk development instance for every environment, permanently** (local, Vercel previews, Vercel production). No production instance, so Clerk needs no owned domain.
  - Why: Clerk production keys don't work on `*.vercel.app`; the only way around it (Vercel's Preview Deployment Suffix) needs Vercel Pro; the user has no Pro plan.
  - Accepted limits: the "Development" banner, at most 100 users, a relaxed security posture ("not suitable for production workloads" in Clerk's docs), shared Google OAuth credentials.
- **Sign-in:** email and Google. The user's own Google account is the admin.
- **Admin role:** public metadata `{"role": "admin"}`, set only in the Clerk dashboard. The session token carries it as a custom claim `"role": "{{user.public_metadata.role}}"`.

## Checked before starting (25.11.2026)

- Clerk docs: production keys can't be used with a host's preview domain such as `*.vercel.app`; a production instance needs an owned domain.
- Clerk docs: the default session token has no metadata; a custom claim is needed.
- The instance's JWKS (`<issuer>/.well-known/jwks.json`) serves one RS256 key.
- `@clerk/clerk-react` is deprecated in favour of `@clerk/react` (Core 3).
- `typescript-eslint` 8.74 supports TypeScript `<6.1`; the Vite template pins TypeScript `~5.9.3`, which fits.

## Design choices

- **Backend verifies with public keys only.** PyJWT checks the RS256 signature against the instance's JWKS, plus `exp`, `nbf`, `iss` and, when present, `azp` against an allow-list. No Clerk secret key is needed or stored.
- **Settings:** `MKC_CLERK_ISSUER` (empty = auth not configured, so protected routes answer 503), `MKC_CLERK_AUTHORIZED_PARTIES` and `MKC_CORS_ORIGINS` (both default to the local Vite dev server).
- **Testable key lookup:** the verifier takes a key resolver. Tests generate an RSA key pair at runtime and sign their own tokens; no key file is committed and no test touches the network.
- **Admin rule in one place per side:** backend `role == "admin"` from the token; frontend `user.publicMetadata.role === "admin"`. The frontend guard is only for the UI; the backend enforces.
- **`apiFetch(path, init)`** gets the token from Clerk's `getToken()`, which works outside React, so callers don't pass tokens. It refuses absolute URLs, so the token never goes to another host.
- **Frontend packages:** `@clerk/react`, `react-router`, Vite, Tailwind 4, shadcn/ui (only the components we use), vitest with Testing Library and jsdom.

## Order

1. MKC-7.1: red tests for the token checks (missing, expired, wrong issuer, wrong key, `none`/HS256, wrong `azp`, non-admin 403, admin 200), then `mkc.api.auth`.
2. MKC-7.2: scaffold in its own commit; CI frontend job runs lint, typecheck and test.
3. MKC-7.3: red vitest tests for `apiFetch` and `RequireAdmin`, then the code.
4. MKC-7.4: docs; local run of the three states with the real Clerk instance.

## Done when

- Backend and frontend tests are green in CI.
- Signed-out, signed-in non-admin and signed-in admin work locally against the backend's `/api/me`.
- ADR 002 and the design doc record the Clerk decision.
