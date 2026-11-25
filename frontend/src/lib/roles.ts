/** The admin role, set as public metadata `{"role": "admin"}` in the Clerk dashboard. */
export const ADMIN_ROLE = 'admin'

/** Same rule as the backend (`mkc.api.auth`): admin only if `role` is exactly "admin". */
export function isAdmin(publicMetadata: Record<string, unknown> | undefined): boolean {
  return publicMetadata?.role === ADMIN_ROLE
}
