import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { toast } from "sonner"

import { Card } from "@/components/ui/card"
import { listReadinessAssessments, listWorkspaces, type ReadinessAssessment, type Workspace } from "@/lib/api"

// Deep page, not a primary tab - readiness isn't in the canonical target
// route inventory (docs/product/02) as its own numbered destination, but
// the founder's own 2026-09-27 directive asked for it explicitly; placed
// consistently with DecisionPackage.tsx (same workspace-picker pattern,
// linked from Findings).
//
// No percentage, health meter, or traffic light is invented here: the
// real backend (readiness.py) gives exactly one boolean `ready` plus six
// named, explicit checklist items, each with its own met/unmet state and
// detail text - that is exactly what renders below, nothing synthesized
// on top. See readiness.py's own module docstring for why this checklist
// is deliberately narrow ("ready to sign off," not "diligence complete").

function ItemRow({ item }: { item: { key: string; label: string; met: boolean; detail: string } }) {
  return (
    <div className="flex items-start gap-3 px-4 py-3 text-sm">
      <span
        className={`mt-0.5 inline-block h-2 w-2 shrink-0 rounded-full ${item.met ? "bg-emerald-500" : "bg-amber-500"}`}
        aria-hidden
      />
      <div className="min-w-0 flex-1">
        <p className={item.met ? "text-foreground" : "text-foreground font-medium"}>{item.label}</p>
        {item.detail && <p className="mt-0.5 text-xs text-muted-foreground">{item.detail}</p>}
      </div>
      <span className="text-xs text-muted-foreground">{item.met ? "Met" : "Unmet"}</span>
    </div>
  )
}

function AssessmentCard({ assessment, projectId }: { assessment: ReadinessAssessment; projectId: string }) {
  const unmet = assessment.items.filter((i) => !i.met)
  return (
    <Card className="space-y-3 p-0">
      <div className="flex flex-wrap items-start justify-between gap-2 border-b border-border px-4 py-3">
        <div>
          <span
            className={`inline-block rounded-full border px-2 py-0.5 text-xs font-semibold ${
              assessment.ready
                ? "border-emerald-900 bg-emerald-950/60 text-emerald-300"
                : "border-amber-900 bg-amber-950/40 text-amber-300"
            }`}
          >
            {assessment.ready ? "Ready to sign off" : "Not yet ready"}
          </span>
          <p className="mt-1 text-xs text-muted-foreground">{new Date(assessment.created_at).toLocaleString()}</p>
        </div>
      </div>
      <p className="px-4 text-xs text-muted-foreground">{assessment.scope_description}</p>
      <div className="divide-y divide-border">
        {assessment.items.map((item) => <ItemRow key={item.key} item={item} />)}
      </div>
      {unmet.length > 0 && (
        <p className="border-t border-border px-4 py-3 text-xs text-muted-foreground">
          To close the remaining {unmet.length} item{unmet.length === 1 ? "" : "s"}, see{" "}
          <Link to={`/projects/${projectId}/findings`} className="underline">Findings</Link> (findings and requests
          live there) or the deal's information requests.
        </p>
      )}
    </Card>
  )
}

export function Readiness() {
  const { projectId } = useParams<{ projectId: string }>()
  const [workspacesList, setWorkspacesList] = useState<Workspace[] | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [assessments, setAssessments] = useState<ReadinessAssessment[] | null>(null)

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
    listReadinessAssessments(projectId, selectedId).then(setAssessments).catch(() => toast.error("Could not load readiness assessments."))
  }, [projectId, selectedId])

  if (!workspacesList) {
    return <div className="mx-auto max-w-4xl px-6 pt-8 pb-20 text-sm text-muted-foreground">Loading…</div>
  }

  const selected = workspacesList.find((w) => w.id === selectedId) ?? null

  return (
    <div className="mx-auto max-w-4xl px-6 pt-8 pb-20 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-heading text-2xl font-semibold text-foreground">Readiness</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            <Link to={`/projects/${projectId}/findings`} className="underline">Back to findings</Link>
          </p>
        </div>
        {workspacesList.length > 1 && (
          <select
            aria-label="Findings workspace"
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
          No reconciliation or integrity review has been run on this deal yet, so there is no workspace to assess.
        </Card>
      ) : !assessments ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : assessments.length === 0 ? (
        <Card className="p-6 text-sm text-muted-foreground">
          No readiness assessment has been run for this workspace yet. Running one is a "readiness" mandate against
          this deal - not created directly from this screen.
        </Card>
      ) : (
        assessments
          .slice()
          .sort((a, b) => b.created_at.localeCompare(a.created_at))
          .map((assessment) => <AssessmentCard key={assessment.id} assessment={assessment} projectId={projectId!} />)
      )}
    </div>
  )
}
