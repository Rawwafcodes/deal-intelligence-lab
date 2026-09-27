import { createContext, type ReactNode, useContext } from "react"

import { Card } from "@/components/ui/card"
import type { DealCapabilities } from "@/lib/api"

// M17 authorization closeout: a server-provided capability set consumed
// by shared frontend guards, never a second, frontend-only permission
// model that could drift from authz.py (the closeout directive's own
// explicit requirement). DealShell.tsx is the one place that fetches
// the deal overview (already doing so for the deal-name breadcrumb) and
// provides the role/capabilities it carries; every deal-scoped page
// reads from this context instead of re-deriving anything. `null`
// capabilities means "not loaded yet", not "denied" - callers must not
// treat the two the same, or a real capability would flash false before
// its first real fetch resolves.
interface DealAccessValue {
  role: string | null
  capabilities: DealCapabilities | null
}

const DealAccessContext = createContext<DealAccessValue>({ role: null, capabilities: null })

export function DealAccessProvider({ value, children }: { value: DealAccessValue; children: ReactNode }) {
  return <DealAccessContext.Provider value={value}>{children}</DealAccessContext.Provider>
}

export function useDealAccess(): DealAccessValue {
  return useContext(DealAccessContext)
}

export function useCapability(capability: string): boolean {
  const { capabilities } = useDealAccess()
  return capabilities?.[capability] ?? false
}

// Frontend guards are usability aids only (the backend independently
// re-checks every one of these on its own matching route) - but a
// denied destination should still say so clearly rather than silently
// rendering nothing or a generic fetch-error toast. Renders `children`
// only once capabilities have actually loaded and the capability is
// present - the guarded page's own component never mounts otherwise,
// so its own data fetch never fires (no sensitive content is ever
// requested before this decision is made).
export function RequireCapability({ capability, children }: { capability: string; children: ReactNode }) {
  const { capabilities } = useDealAccess()
  if (capabilities === null) return null
  if (!capabilities[capability]) {
    return (
      <div className="mx-auto max-w-2xl px-6 pt-8 pb-20">
        <Card className="p-6 text-center">
          <h1 className="font-heading text-lg font-semibold text-foreground">Not available for your role</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Your role on this deal doesn't include access to this section.
          </p>
        </Card>
      </div>
    )
  }
  return <>{children}</>
}
