import { useEffect, useMemo, useState } from "react"
import { useParams } from "react-router-dom"
import { toast } from "sonner"

import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { getWorkspaceBundle, listWorkspaces, type Finding, type Workspace, type WorkspaceBundle } from "@/lib/api"

// Unifying the workspace frontend: the real findings register, in React,
// wired to the same GET .../workspaces/<id> bundle the static workspace.html
// page has always used. A project can have several workspaces (one per
// completed reconciliation run, or per Integrity Review) - the picker
// below is a genuine, not-yet-solved product question the static page
// answers by making the caller navigate from a specific reconciliation;
// here it's an explicit dropdown instead, defaulting to the most recent.
//
// Disclosed scope boundary, inherited from the backend (server.py's
// `_get_workspace_analysis`, unchanged by this task): the full findings
// bundle only exists for a cross-format-analysis-backed workspace. An
// Integrity-Review-backed workspace (`integrity_review_id` set instead)
// 400s on that same endpoint - this screen shows a plain explanatory
// message for those rather than a broken fetch, and does not attempt to
// extend that backend boundary itself.

const SEVERITY_LABELS: Record<string, string> = {
  critical: "Critical", high: "High", medium: "Medium", low: "Low", informational: "Info",
}
const SEVERITY_ORDER = ["critical", "high", "medium", "low", "informational"]

function SeverityBadge({ severity }: { severity: string | null }) {
  const key = (severity ?? "").toLowerCase()
  const label = SEVERITY_LABELS[key] ?? severity ?? "Unspecified"
  const styles: Record<string, string> = {
    critical: "bg-red-950/60 text-red-300 border-red-900",
    high: "bg-orange-950/60 text-orange-300 border-orange-900",
    medium: "bg-yellow-950/60 text-yellow-300 border-yellow-900",
    low: "bg-blue-950/60 text-blue-300 border-blue-900",
    informational: "bg-surface-2 text-muted-foreground border-border",
  }
  return (
    <span className={`inline-block w-20 rounded-full border px-2 py-0.5 text-center text-xs font-semibold ${styles[key] ?? styles.informational}`}>
      {label}
    </span>
  )
}

export function Findings() {
  const { projectId } = useParams<{ projectId: string }>()
  const [workspaces, setWorkspacesList] = useState<Workspace[] | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [bundle, setBundle] = useState<WorkspaceBundle | null>(null)
  const [bundleError, setBundleError] = useState<string | null>(null)
  const [search, setSearch] = useState("")
  const [severityFilter, setSeverityFilter] = useState("all")

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
    if (!projectId || !selectedId) return
    setBundle(null)
    setBundleError(null)
    getWorkspaceBundle(projectId, selectedId)
      .then(setBundle)
      .catch((err) => setBundleError(err instanceof Error ? err.message : "Could not load findings."))
  }, [projectId, selectedId])

  const filtered: Finding[] = useMemo(() => {
    if (!bundle) return []
    return bundle.findings.filter((f) => {
      if (severityFilter !== "all" && (f.effective_severity ?? "").toLowerCase() !== severityFilter) return false
      if (search && !f.title.toLowerCase().includes(search.toLowerCase())) return false
      return true
    })
  }, [bundle, search, severityFilter])

  if (!workspaces) {
    return <div className="mx-auto max-w-4xl px-6 pt-8 pb-20 text-sm text-muted-foreground">Loading findings…</div>
  }

  if (workspaces.length === 0) {
    return (
      <div className="mx-auto max-w-4xl px-6 pt-8 pb-20">
        <h1 className="font-heading text-2xl font-semibold text-foreground">Findings</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          No reconciliation or integrity review has been run on this deal yet.
        </p>
      </div>
    )
  }

  const selected = workspaces.find((w) => w.id === selectedId) ?? null

  return (
    <div className="mx-auto max-w-4xl px-6 pt-8 pb-20 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-heading text-2xl font-semibold text-foreground">Findings</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {bundle ? `${bundle.summary.total_findings} finding${bundle.summary.total_findings === 1 ? "" : "s"}` : " "}
          </p>
        </div>
        {workspaces.length > 1 && (
          <select
            value={selectedId ?? ""}
            onChange={(event) => setSelectedId(event.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            {workspaces.map((w) => (
              <option key={w.id} value={w.id}>
                {w.cross_format_analysis_id ? "Reconciliation" : "Integrity review"} — {new Date(w.created_at).toLocaleDateString()}
              </option>
            ))}
          </select>
        )}
      </div>

      {selected && !selected.cross_format_analysis_id ? (
        <Card className="p-6 text-sm text-muted-foreground">
          This workspace is backed by an Integrity Review, not a cross-format reconciliation - this screen doesn't
          yet render that kind of workspace's findings (a real backend boundary, not a bug: server.py's own
          workspace-bundle endpoint only serves reconciliation-backed workspaces today).
        </Card>
      ) : bundleError ? (
        <Card className="p-6 text-sm text-muted-foreground">{bundleError}</Card>
      ) : !bundle ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : (
        <>
          <div className="flex flex-wrap gap-4">
            {SEVERITY_ORDER.filter((s) => bundle.summary.by_severity[s]).map((s) => (
              <div key={s}>
                <div className="font-heading text-xl font-bold text-foreground">{bundle.summary.by_severity[s]}</div>
                <div className="text-xs tracking-wide text-muted-foreground uppercase">{SEVERITY_LABELS[s]}</div>
              </div>
            ))}
            <div>
              <div className="font-heading text-xl font-bold text-foreground">{bundle.summary.total_findings}</div>
              <div className="text-xs tracking-wide text-muted-foreground uppercase">Total</div>
            </div>
          </div>

          <Card className="p-4">
            <div className="flex flex-wrap gap-3">
              <Input
                placeholder="Search title"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                className="max-w-xs"
              />
              <select
                value={severityFilter}
                onChange={(event) => setSeverityFilter(event.target.value)}
                className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
              >
                <option value="all">All severities</option>
                {SEVERITY_ORDER.map((s) => (
                  <option key={s} value={s}>{SEVERITY_LABELS[s]}</option>
                ))}
              </select>
            </div>
          </Card>

          <Card className="divide-y divide-border p-0">
            {filtered.map((finding) => (
              <div key={finding.id} className="flex items-center gap-3 px-4 py-3 text-sm">
                <SeverityBadge severity={finding.effective_severity} />
                <span className="min-w-0 flex-1 truncate text-foreground">{finding.title}</span>
                <span className="text-xs text-muted-foreground">{finding.review_status || "unreviewed"}</span>
              </div>
            ))}
            {filtered.length === 0 && (
              <p className="px-4 py-6 text-center text-sm text-muted-foreground">No findings match these filters.</p>
            )}
          </Card>
        </>
      )}
    </div>
  )
}
