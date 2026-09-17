import { useEffect, useState } from "react"

import { useSidebar } from "@/components/ui/sidebar"
import { type DevIdentity, type Session, getSession, listDevIdentities, switchIdentity } from "@/lib/api"

// Extracted from the old AppHeader's IdentityNav (Task 11.3b) when that
// header was replaced by the sidebar shell - same behavior, moved and
// restyled for the sidebar footer. Hidden while the sidebar is collapsed
// (a <select> doesn't collapse to a meaningful icon-only state) rather
// than half-rendering it - expanding the sidebar is one click away.
export function IdentityFooter() {
  const { open } = useSidebar()
  const [session, setSession] = useState<Session | null>(null)
  const [identities, setIdentities] = useState<DevIdentity[] | null>(null)
  const [switching, setSwitching] = useState(false)

  useEffect(() => {
    getSession()
      .then(setSession)
      .catch(() => setSession(null))
    // Absent (404) outside dev - see docs/06-security-and-collaboration.md.
    // Treated the same as "not available", not an error to surface.
    listDevIdentities()
      .then(setIdentities)
      .catch(() => setIdentities(null))
  }, [])

  async function handleSwitch(userId: string) {
    if (!userId || userId === session?.user.id) return
    setSwitching(true)
    try {
      const next = await switchIdentity(userId)
      setSession(next)
      // Every screen's data is scoped to the caller's identity server-side
      // (Task 11.3b) - a full reload is the simplest way to make every
      // already-loaded list (starting with the project list) re-fetch
      // under the new identity, without building a shared auth store.
      window.location.reload()
    } finally {
      setSwitching(false)
    }
  }

  if (!session || !open) return null
  const orgName = session.organizations[0]?.organization.name

  return (
    <div className="flex flex-col gap-1.5 border-t border-sidebar-border px-2.5 pt-3 pb-1 text-xs">
      {orgName ? <span className="truncate text-sidebar-foreground/60">{orgName}</span> : null}
      {identities && identities.length > 0 ? (
        <select
          aria-label="Switch dev identity"
          className="h-8 rounded-md border border-sidebar-border bg-sidebar-accent px-2 text-sm text-sidebar-foreground disabled:opacity-50"
          value={session.user.id}
          disabled={switching}
          onChange={(event) => handleSwitch(event.target.value)}
        >
          {identities.map((identity) => (
            <option key={identity.user.id} value={identity.user.id}>
              {identity.user.display_name}
            </option>
          ))}
        </select>
      ) : (
        <span className="truncate text-sidebar-foreground">{session.user.display_name}</span>
      )}
    </div>
  )
}
