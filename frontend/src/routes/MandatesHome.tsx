import { useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { toast } from "sonner"

import { Card } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { listAllMandates, type OrgWideMandate } from "@/lib/api"
import { MANDATE_STATUS_LABELS } from "@/lib/mandateStatus"

// Organization-wide Mandates (docs/product/02: "Mandates" is a peer
// primary destination operating across the user's authorized work, not
// only inside one deal - MandateList.tsx stays the deal-scoped detail
// view/creation surface; this page is the cross-deal register). Reuses
// the existing per-project mandate data via server.py's new
// _org_wide_mandates composition (Task 17.8) - no new domain logic, no
// duplicate mandate model.

function formatDate(isoString: string) {
  return new Date(isoString).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })
}

export function MandatesHome() {
  const [mandates, setMandates] = useState<OrgWideMandate[] | null>(null)
  const [statusFilter, setStatusFilter] = useState("all")

  useEffect(() => {
    listAllMandates().then(setMandates).catch(() => {
      toast.error("Could not load mandates.")
      setMandates([])
    })
  }, [])

  const presentStatuses = useMemo(() => {
    if (!mandates) return []
    return [...new Set(mandates.map((m) => m.status))]
  }, [mandates])

  const filtered = useMemo(() => {
    if (!mandates) return []
    if (statusFilter === "all") return mandates
    return mandates.filter((m) => m.status === statusFilter)
  }, [mandates, statusFilter])

  return (
    <div className="mx-auto max-w-3xl px-6 pt-8 pb-20 space-y-4">
      <div>
        <h1 className="font-heading text-2xl font-semibold text-foreground">Mandates</h1>
        <p className="text-sm text-muted-foreground">Every mandate across every deal you can see.</p>
      </div>

      {presentStatuses.length > 1 && (
        <select
          aria-label="Filter by status"
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value)}
          className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
        >
          <option value="all">All statuses</option>
          {presentStatuses.map((status) => (
            <option key={status} value={status}>{MANDATE_STATUS_LABELS[status] ?? status}</option>
          ))}
        </select>
      )}

      {mandates === null ? (
        <div className="space-y-3">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      ) : filtered.length === 0 ? (
        <Card className="p-6 text-center text-sm text-muted-foreground">
          {mandates.length === 0 ? "No mandates yet. Open a deal to commission one." : "No mandates match this filter."}
        </Card>
      ) : (
        <ul className="space-y-3">
          {filtered.map((mandate) => (
            <li key={mandate.id}>
              <Link to={`/projects/${mandate.project.id}/mandates/${mandate.id}`}>
                <Card className="p-4 transition-all duration-200 hover:-translate-y-0.5 hover:border-primary">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="font-heading text-base font-semibold text-foreground">{mandate.objective}</div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        {mandate.project.name} · Updated {formatDate(mandate.updated_at)}
                      </div>
                    </div>
                    <span className="shrink-0 whitespace-nowrap rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">
                      {MANDATE_STATUS_LABELS[mandate.status] ?? mandate.status}
                    </span>
                  </div>
                </Card>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
