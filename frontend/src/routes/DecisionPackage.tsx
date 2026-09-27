import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import {
  approveDeliverable,
  getDeliverable,
  getSession,
  listDealMemberships,
  listDeliverables,
  listWorkspaces,
  type Deliverable,
  type StalenessFlag,
  type Workspace,
} from "@/lib/api"

// Deep page (not a sixth primary tab, per docs/product/02's own target
// route inventory - "Decision Package" is listed as a deep page, like
// Mandate Detail or Document Detail). Deliberately not built here: any
// "create a decision package" action - the real backend has no create
// route at all (decision_package.produce_draft is a mandate capability,
// wired up once the unified Mandates composer, Phase C, exists).

const STATUS_LABELS: Record<string, string> = { draft: "Draft", approved: "Approved", superseded: "Superseded" }

const SECTIONS: Array<{ key: keyof Deliverable; label: string }> = [
  { key: "executive_summary", label: "Executive summary" },
  { key: "recommendation", label: "Recommendation" },
  { key: "key_evidence_and_findings", label: "Key evidence and findings" },
  { key: "outstanding_and_unresolved_matters", label: "Outstanding and unresolved matters" },
  { key: "risks_and_limitations", label: "Risks and limitations" },
]

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    draft: "bg-surface-2 text-muted-foreground border-border",
    approved: "bg-emerald-950/60 text-emerald-300 border-emerald-900",
    superseded: "bg-surface-2 text-muted-foreground border-border line-through",
  }
  return (
    <span className={`inline-block rounded-full border px-2 py-0.5 text-xs font-semibold ${styles[status] ?? styles.draft}`}>
      {STATUS_LABELS[status] ?? status}
    </span>
  )
}

function DeliverableCard({
  deliverable,
  canApprove,
  onApproved,
}: {
  deliverable: Deliverable
  canApprove: boolean
  onApproved: () => void
}) {
  const [staleness, setStaleness] = useState<StalenessFlag | null | undefined>(undefined)
  const [approving, setApproving] = useState(false)
  const { projectId } = useParams<{ projectId: string }>()

  useEffect(() => {
    // Staleness only comes back from the single-item route, not the list.
    if (!projectId) return
    getDeliverable(projectId, deliverable.workspace_id, deliverable.id)
      .then((full) => setStaleness(full.staleness))
      .catch(() => setStaleness(null))
  }, [projectId, deliverable.workspace_id, deliverable.id])

  async function approve() {
    if (!projectId) return
    setApproving(true)
    try {
      await approveDeliverable(projectId, deliverable.workspace_id, deliverable.id)
      toast.success("Decision package approved.")
      onApproved()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not approve this decision package.")
    } finally {
      setApproving(false)
    }
  }

  return (
    <Card className="space-y-3 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="font-heading text-lg font-semibold text-foreground">
            {deliverable.title || `Decision package · version ${deliverable.version_number}`}
          </h3>
          <p className="text-xs text-muted-foreground">
            Version {deliverable.version_number} · {new Date(deliverable.created_at).toLocaleString()}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={deliverable.status} />
          {deliverable.status === "draft" && canApprove && (
            <Button size="sm" disabled={approving} onClick={approve}>
              {approving ? "Approving…" : "Approve"}
            </Button>
          )}
        </div>
      </div>

      {staleness && (
        <div className="rounded-md border border-amber-900 bg-amber-950/40 px-3 py-2 text-xs text-amber-300">
          Potentially stale: {staleness.reason}
        </div>
      )}

      <div className="grid gap-3">
        {SECTIONS.map(({ key, label }) => {
          const value = deliverable[key]
          if (!value || typeof value !== "string") return null
          return (
            <div key={key}>
              <h4 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">{label}</h4>
              <p className="mt-1 whitespace-pre-wrap text-sm text-foreground">{value}</p>
            </div>
          )
        })}
      </div>

      <p className="text-xs text-muted-foreground">
        {deliverable.source_finding_ids.length} finding{deliverable.source_finding_ids.length === 1 ? "" : "s"},{" "}
        {deliverable.source_request_ids.length} request{deliverable.source_request_ids.length === 1 ? "" : "s"} cited.
        {deliverable.approved_by && ` Approved by ${deliverable.approved_by} on ${new Date(deliverable.approved_at!).toLocaleString()}.`}
      </p>
    </Card>
  )
}

export function DecisionPackage() {
  const { projectId } = useParams<{ projectId: string }>()
  const [workspacesList, setWorkspacesList] = useState<Workspace[] | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [deliverables, setDeliverablesList] = useState<Deliverable[] | null>(null)
  const [canApprove, setCanApprove] = useState(false)

  useEffect(() => {
    if (!projectId) return
    listWorkspaces(projectId)
      .then((list) => {
        const sorted = [...list].sort((a, b) => b.created_at.localeCompare(a.created_at))
        setWorkspacesList(sorted)
        setSelectedId(sorted[0]?.id ?? null)
      })
      .catch(() => toast.error("Could not load this deal's workspaces."))
  }, [projectId])

  useEffect(() => {
    if (!projectId) return
    Promise.all([getSession(), listDealMemberships(projectId)])
      .then(([session, memberships]) => {
        const mine = memberships.find((m) => m.user_id === session.user.id && !m.revoked_at)
        setCanApprove(mine?.role === "deal_lead")
      })
      .catch(() => setCanApprove(false))
  }, [projectId])

  function reload() {
    if (!projectId || !selectedId) return
    listDeliverables(projectId, selectedId).then(setDeliverablesList).catch(() => toast.error("Could not load decision packages."))
  }

  useEffect(reload, [projectId, selectedId])

  if (!workspacesList) {
    return <div className="mx-auto max-w-4xl px-6 pt-8 pb-20 text-sm text-muted-foreground">Loading…</div>
  }

  const selected = workspacesList.find((w) => w.id === selectedId) ?? null

  return (
    <div className="mx-auto max-w-4xl px-6 pt-8 pb-20 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-heading text-2xl font-semibold text-foreground">Decision package</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Drafted, reviewable positions for this deal.{" "}
            <Link to={`/projects/${projectId}/findings`} className="underline">Back to findings</Link>
          </p>
        </div>
        {workspacesList.length > 1 && (
          <select
            value={selectedId ?? ""}
            onChange={(event) => setSelectedId(event.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            {workspacesList.map((w) => (
              <option key={w.id} value={w.id}>
                {w.cross_format_analysis_id ? "Reconciliation" : "Integrity review"} — {new Date(w.created_at).toLocaleDateString()}
              </option>
            ))}
          </select>
        )}
      </div>

      {!selected ? (
        <Card className="p-6 text-sm text-muted-foreground">
          No reconciliation or integrity review has been run on this deal yet, so there is no workspace to draft a
          decision package from.
        </Card>
      ) : !deliverables ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : deliverables.length === 0 ? (
        <Card className="p-6 text-sm text-muted-foreground">
          No decision package has been drafted for this workspace yet. A decision package is produced by running a
          "decision-package" mandate against this deal's reviewed findings - not created directly from this screen.
        </Card>
      ) : (
        deliverables
          .slice()
          .sort((a, b) => b.version_number - a.version_number)
          .map((deliverable) => (
            <DeliverableCard key={deliverable.id} deliverable={deliverable} canApprove={canApprove} onApproved={reload} />
          ))
      )}
    </div>
  )
}
