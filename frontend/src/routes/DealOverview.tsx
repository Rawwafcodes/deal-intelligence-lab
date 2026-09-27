import { useEffect, useState } from "react"
import { BellIcon, FileUpIcon, ListTodoIcon, PencilIcon } from "lucide-react"
import { Link, useParams } from "react-router-dom"
import { toast } from "sonner"

import { BriefEditorDialog } from "@/components/BriefEditorDialog"
import { DealPeopleCard } from "@/components/DealPeopleCard"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import {
  getDealOverview,
  updateRequest,
  type DealOverview as DealOverviewData, type RestrictedDealOverview, type WorkspaceRequest,
} from "@/lib/api"

// Task 13.3: this is the "MD drill-down" landing page for a single deal -
// a real-data summary with links to the React-native deal surfaces. Brief
// editing is intentionally local to this page; documents and human work
// have their own deep-linkable routes under the same DealShell.

const TASK_STATUS_LABELS: Record<string, string> = {
  open: "Open", in_progress: "In progress", submitted: "Submitted",
  returned: "Returned for revision", approved: "Approved", cancelled: "Cancelled",
}

const MANDATE_STATUS_LABELS: Record<string, string> = {
  draft: "Draft", planning: "Planning", awaiting_approval: "Awaiting approval",
  active: "Active", under_review: "Under review", completed: "Completed",
  cancelled: "Cancelled", failed: "Failed",
}

const SEVERITY_LABELS: Record<string, string> = {
  critical: "Critical", high: "High", medium: "Medium", low: "Low",
  informational: "Informational", unspecified: "Unspecified",
}
const SEVERITY_ORDER = ["critical", "high", "medium", "low", "informational", "unspecified"]

function formatDate(isoString: string) {
  return new Date(isoString).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })
}

function StatusPill({ label }: { label: string }) {
  return (
    <span className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">{label}</span>
  )
}

function CountRow({ counts, labels }: { counts: Record<string, number>; labels: Record<string, string> }) {
  const entries = Object.entries(counts)
  if (entries.length === 0) return <p className="text-sm text-muted-foreground">None yet.</p>
  return (
    <div className="flex flex-wrap gap-2">
      {entries.map(([status, count]) => (
        <span key={status} className="rounded-full border border-border px-2.5 py-1 text-xs text-foreground">
          {labels[status] ?? status}: <span className="font-semibold">{count}</span>
        </span>
      ))}
    </div>
  )
}

function RequestResponseRow({
  projectId, request, onResponded,
}: { projectId: string; request: WorkspaceRequest; onResponded: () => void }) {
  const [response, setResponse] = useState(request.management_response)
  const [busy, setBusy] = useState(false)

  async function submit() {
    setBusy(true)
    try {
      await updateRequest(projectId, request.workspace_id, request.id, { management_response: response })
      toast.success("Response sent.")
      onResponded()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not send the response.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <li className="rounded-md border border-border p-3">
      <p className="text-sm font-medium text-foreground">{request.question}</p>
      <p className="mt-1 text-xs text-muted-foreground">
        {request.management_response.trim() ? "You already responded - you can update your response below." : "Awaiting your response."}
      </p>
      <Textarea
        className="mt-2"
        value={response}
        onChange={(event) => setResponse(event.target.value)}
        placeholder="Your response"
        aria-label={`Response to: ${request.question}`}
        rows={3}
      />
      <Button size="sm" className="mt-2" disabled={busy || !response.trim()} onClick={submit}>
        {request.management_response.trim() ? "Update response" : "Send response"}
      </Button>
    </li>
  )
}

function RestrictedDealOverviewView({
  overview, projectId, onReload,
}: { overview: RestrictedDealOverview; projectId: string; onReload: () => void }) {
  const { project, brief, approved_deliverables, approved_decision_packages, requests } = overview
  return (
    <div className="mx-auto max-w-3xl px-6 pt-8 pb-20 space-y-6">
      <div>
        <h1 className="font-heading text-2xl font-semibold text-foreground">{project.name}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {project.description || "No description"} · Created {formatDate(project.created_at)}
        </p>
        <p className="mt-3 text-sm text-muted-foreground">
          You have restricted access to this deal - approved deliverables and the deal brief only.
        </p>
      </div>

      <Card className="p-6">
        <h2 className="font-heading text-lg font-semibold text-foreground">Deal brief</h2>
        {brief ? (
          <div className="mt-2 space-y-1 text-sm">
            <p className="text-muted-foreground">Version {String(brief.version_number)} · {formatDate(String(brief.created_at))}</p>
            {brief.objective ? <p className="text-foreground">{String(brief.objective)}</p> : null}
          </div>
        ) : (
          <p className="mt-2 text-sm text-muted-foreground">No approved brief recorded for this deal yet.</p>
        )}
      </Card>

      <Card className="p-6">
        <h2 className="font-heading text-lg font-semibold text-foreground">Approved deliverables</h2>
        {approved_deliverables.length === 0 ? (
          <p className="mt-2 text-sm text-muted-foreground">Nothing has been approved for sharing yet.</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {approved_deliverables.map((deliverable, index) => (
              <li key={index} className="flex items-center justify-between gap-3 text-sm">
                <div>
                  <span className="text-foreground">{deliverable.work_product.title}</span>
                  <span className="ml-2 text-xs text-muted-foreground">for "{deliverable.task_title}"</span>
                </div>
                {deliverable.approved_at && (
                  <span className="text-xs text-muted-foreground">{formatDate(deliverable.approved_at)}</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="p-6">
        <h2 className="font-heading text-lg font-semibold text-foreground">Decision package</h2>
        {approved_decision_packages.length === 0 ? (
          <p className="mt-2 text-sm text-muted-foreground">No decision package is currently approved for sharing.</p>
        ) : (
          <div className="mt-3 space-y-5">
            {approved_decision_packages.map((pkg) => (
              <article key={pkg.id} className="space-y-3">
                <p className="text-xs text-muted-foreground">
                  Version {pkg.version_number}
                  {pkg.approved_at ? ` · approved ${formatDate(pkg.approved_at)}` : ""}
                </p>
                {pkg.sources_changed_since_approval && (
                  <p role="status" className="rounded-md border border-amber-900 bg-amber-950/40 px-3 py-2 text-xs text-amber-300">
                    Some source documents have changed since this package was approved. The deal team is reviewing
                    whether the position needs updating.
                  </p>
                )}
                {[
                  ["Executive summary", pkg.executive_summary],
                  ["Recommendation", pkg.recommendation],
                ].map(([label, text]) =>
                  text ? (
                    <div key={label}>
                      <h3 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">{label}</h3>
                      <p className="mt-1 whitespace-pre-wrap text-sm text-foreground">{text}</p>
                    </div>
                  ) : null
                )}
                <details className="text-sm">
                  <summary className="cursor-pointer text-xs text-muted-foreground underline">
                    Evidence, open matters and risks
                  </summary>
                  <div className="mt-3 space-y-3">
                    {[
                      ["Key evidence and findings", pkg.key_evidence_and_findings],
                      ["Outstanding and unresolved matters", pkg.outstanding_and_unresolved_matters],
                      ["Risks and limitations", pkg.risks_and_limitations],
                    ].map(([label, text]) =>
                      text ? (
                        <div key={label}>
                          <h3 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">{label}</h3>
                          <p className="mt-1 whitespace-pre-wrap text-sm text-foreground">{text}</p>
                        </div>
                      ) : null
                    )}
                  </div>
                </details>
              </article>
            ))}
          </div>
        )}
      </Card>

      <Card className="p-6">
        <h2 className="font-heading text-lg font-semibold text-foreground">Information requests</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Requests the deal team has sent you - respond directly below.
        </p>
        {requests.length === 0 ? (
          <p className="mt-2 text-sm text-muted-foreground">No requests are waiting on you right now.</p>
        ) : (
          <ul className="mt-3 space-y-3">
            {requests.map((request) => (
              <RequestResponseRow key={request.id} projectId={projectId} request={request} onResponded={onReload} />
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}

export function DealOverview() {
  const { projectId } = useParams<{ projectId: string }>()
  const [overview, setOverview] = useState<DealOverviewData | RestrictedDealOverview | null>(null)
  const [briefEditorOpen, setBriefEditorOpen] = useState(false)

  async function reload() {
    if (!projectId) return
    try {
      setOverview(await getDealOverview(projectId))
    } catch {
      toast.error("Could not load the deal overview.")
    }
  }

  useEffect(() => {
    reload()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId])

  if (!overview || !projectId) {
    return <div className="mx-auto max-w-3xl px-6 pt-8 pb-20 text-sm text-muted-foreground">Loading…</div>
  }

  if (overview.restricted) {
    return <RestrictedDealOverviewView overview={overview} projectId={projectId} onReload={reload} />
  }

  const { project, brief, workstreams, tasks, mandates, reconciliations, documents } = overview
  const severityEntries = SEVERITY_ORDER.filter((s) => reconciliations.findings.by_severity[s]).map((s) => [
    s, reconciliations.findings.by_severity[s],
  ] as const)

  return (
    <div className="mx-auto max-w-3xl px-6 pt-8 pb-20 space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-semibold text-foreground">{project.name}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {project.description || "No description"} · Created {formatDate(project.created_at)}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" render={<Link to={`/projects/${projectId}/documents`} />}>
            <FileUpIcon /> Documents
          </Button>
          <Button variant="secondary" render={<Link to={`/projects/${projectId}/work`} />}>
            <ListTodoIcon /> Manage work
          </Button>
          <Button variant="secondary" render={<Link to={`/projects/${projectId}/triggers`} />}>
            <BellIcon /> Monitoring
          </Button>
          <Button onClick={() => setBriefEditorOpen(true)}><PencilIcon /> Edit brief</Button>
        </div>
      </div>

      <Card className="p-6">
        <div className="flex items-center justify-between gap-3">
          <h2 className="font-heading text-lg font-semibold text-foreground">Deal brief</h2>
          <Button size="sm" variant="ghost" onClick={() => setBriefEditorOpen(true)}>Edit</Button>
        </div>
        {brief ? (
          <div className="mt-2 space-y-1 text-sm">
            <p className="text-muted-foreground">Version {String(brief.version_number)} · {formatDate(String(brief.created_at))}</p>
            {brief.objective ? <p className="text-foreground">{String(brief.objective)}</p> : null}
          </div>
        ) : (
          <p className="mt-2 text-sm text-muted-foreground">No approved brief recorded for this deal yet.</p>
        )}
      </Card>

      <Card className="p-6">
        <div className="flex items-center justify-between gap-3">
          <h2 className="font-heading text-lg font-semibold text-foreground">Tasks</h2>
          <Button size="sm" variant="ghost" render={<Link to={`/projects/${projectId}/work`} />}>Manage</Button>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">Real counts across every task on this deal.</p>
        <div className="mt-3">
          <CountRow counts={tasks.counts} labels={TASK_STATUS_LABELS} />
        </div>
        {tasks.needs_attention.length > 0 && (
          <div className="mt-4 border-t border-border pt-4">
            <p className="mb-2 text-sm font-medium text-foreground">Needs attention</p>
            <ul className="space-y-2">
              {tasks.needs_attention.map((task) => (
                <li key={task.id} className="flex items-center justify-between gap-3 text-sm">
                  <span className="text-foreground">{task.title}</span>
                  <div className="flex items-center gap-2">
                    {task.assigned_user && (
                      <span className="text-xs text-muted-foreground">{task.assigned_user.display_name}</span>
                    )}
                    <StatusPill label={TASK_STATUS_LABELS[task.status] ?? task.status} />
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </Card>

      <Card className="p-6">
        <h2 className="font-heading text-lg font-semibold text-foreground">Mandates</h2>
        <div className="mt-3">
          <CountRow counts={mandates.counts} labels={MANDATE_STATUS_LABELS} />
        </div>
        {mandates.recent.length > 0 && (
          <ul className="mt-4 space-y-2 border-t border-border pt-4">
            {mandates.recent.map((mandate) => (
              <li key={mandate.id}>
                <Link
                  to={`/projects/${projectId}/mandates/${mandate.id}`}
                  className="flex items-center justify-between gap-3 text-sm hover:underline"
                >
                  <span className="text-foreground">{mandate.objective}</span>
                  <StatusPill label={MANDATE_STATUS_LABELS[mandate.status] ?? mandate.status} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="p-6">
        <h2 className="font-heading text-lg font-semibold text-foreground">Reconciliations &amp; findings</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {reconciliations.count} reconciliation{reconciliations.count === 1 ? "" : "s"} ·{" "}
          {reconciliations.findings.total} finding{reconciliations.findings.total === 1 ? "" : "s"} total
        </p>
        {severityEntries.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {severityEntries.map(([severity, count]) => (
              <span key={severity} className="rounded-full border border-border px-2.5 py-1 text-xs text-foreground">
                {SEVERITY_LABELS[severity] ?? severity}: <span className="font-semibold">{count}</span>
                {reconciliations.findings.open_by_severity[severity] ? (
                  <span className="text-muted-foreground"> ({reconciliations.findings.open_by_severity[severity]} open)</span>
                ) : null}
              </span>
            ))}
          </div>
        )}
      </Card>

      <Card className="p-6">
        <h2 className="font-heading text-lg font-semibold text-foreground">Workstreams &amp; documents</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          {workstreams.length} workstream{workstreams.length === 1 ? "" : "s"} · {documents.count} document
          {documents.count === 1 ? "" : "s"}
        </p>
      </Card>

      <DealPeopleCard projectId={projectId} />

      <BriefEditorDialog
        projectId={projectId}
        open={briefEditorOpen}
        onOpenChange={setBriefEditorOpen}
        onSaved={reload}
      />
    </div>
  )
}
