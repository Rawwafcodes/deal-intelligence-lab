import { StrictMode, Suspense } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { CLERK_PUBLISHABLE_KEY } from '@/lib/auth'
import { HostedRoot } from './hostedLoader'

// Task 19.4 (M19): hosted builds sign in through Clerk; the SDK is loaded
// only then, so local builds are unchanged.

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {CLERK_PUBLISHABLE_KEY ? (
      <Suspense fallback={null}>
        <HostedRoot publishableKey={CLERK_PUBLISHABLE_KEY}>
          <App />
        </HostedRoot>
      </Suspense>
    ) : (
      <App />
    )}
  </StrictMode>,
)
