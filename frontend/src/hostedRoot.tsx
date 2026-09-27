import type { ReactNode } from 'react'
import { ClerkProvider } from '@clerk/react'

import { AuthGate } from '@/components/AuthGate'

// Task 19.4 (M19): loaded only for hosted builds (see main.tsx), so the
// Clerk SDK never ships in the local bundle's main chunk.
export default function HostedRoot({ publishableKey, children }: { publishableKey: string; children: ReactNode }) {
  return (
    <ClerkProvider publishableKey={publishableKey}>
      <AuthGate>{children}</AuthGate>
    </ClerkProvider>
  )
}
