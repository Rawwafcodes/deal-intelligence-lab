import { lazy } from 'react'

// Task 19.4 (M19): the hosted (Clerk) root, split into its own chunk so the
// Clerk SDK is only downloaded by hosted builds.
export const HostedRoot = lazy(() => import('./hostedRoot'))
