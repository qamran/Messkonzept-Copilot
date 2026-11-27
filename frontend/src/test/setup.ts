import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// MKC-36: unmount after each test. Vitest runs without globals, so Testing Library's
// automatic cleanup is off, and a second render in one file would see the first one.
afterEach(() => cleanup())
