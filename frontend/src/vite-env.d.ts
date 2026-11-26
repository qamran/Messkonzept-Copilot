/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string
  readonly VITE_CLERK_PUBLISHABLE_KEY: string
  /** Commit this build was made from; set by CD only (decision 46). */
  readonly VITE_COMMIT?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
