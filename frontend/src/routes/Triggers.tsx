import { useEffect, useState } from "react"
import { useParams } from "react-router-dom"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import {
  createTrigger,
  disableTrigger,
  getSession,
  getTrigger,
  listDealMemberships,
  listDocuments,
  listTriggers,
  listWorkspaces,
  TRIGGER_EVENT_TEMPLATE_COMPATIBILITY,
  type ProjectDocument,
  type Trigger,
  type TriggerFiring,
  type Workspace,
} from "@/lib/api"

// First-ever React (or any) frontend for triggers.py (M15.3) - there is
// no static-page precedent to migrate from, just a fully backend-tested
// module with no UI at all until this task. See triggers.py's own
// module docstring for exactly why v1 supports only these two event
// types and why approval_policy only ever offers "manual" - not gaps in
// this screen, real v1 scope boundaries on the backend itself.

const EVENT_TYPE_LABELS: Record<string, string> = {
  document_version_changed: "A document gets a new version",
  decision_package_prepared: "A decision package is drafted",
}

function TriggerRow({
  trigger,
  canManage,
  projectId,
  onChanged,
}: {
  trigger: Trigger
  canManage: boolean
  projectId: string
  onChanged: () => void
}) {
  const [expanded, setExpanded] = useState(false)
  const [firings, setFirings] = useState<TriggerFiring[] | null>(null)
  const [disabling, setDisabling] = useState(false)

  function toggleExpanded() {
    setExpanded((current) => !current)
    if (!firings) {
      getTrigger(projectId, trigger.id).then((full) => setFirings(full.firings)).catch(() => toast.error("Could not load firings."))
    }
  }

  async function disable() {
    setDisabling(true)
    try {
      await disableTrigger(projectId, trigger.id)
      toast.success("Trigger disabled.")
      onChanged()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not disable this trigger.")
    } finally {
      setDisabling(false)
    }
  }

  return (
    <div className="border-b border-border last:border-b-0">
      <div className="flex flex-wrap items-start justify-between gap-3 px-4 py-3 text-sm">
        <div className="min-w-0 flex-1">
          <button type="button" onClick={toggleExpanded} className="text-left font-medium text-foreground underline-offset-2 hover:underline">
            {trigger.name}
          </button>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Watches: {EVENT_TYPE_LABELS[trigger.event_type] ?? trigger.event_type} · Fires: {trigger.template_key}
            {trigger.budget_limit != null && ` · Budget limit: ${trigger.budget_limit}`}
          </p>
          {trigger.reason && <p className="mt-0.5 text-xs text-muted-foreground">{trigger.reason}</p>}
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`inline-block rounded-full border px-2 py-0.5 text-xs font-semibold ${
              trigger.status === "active"
                ? "border-emerald-900 bg-emerald-950/60 text-emerald-300"
                : "border-border bg-surface-2 text-muted-foreground"
            }`}
          >
            {trigger.status === "active" ? "Active" : "Disabled"}
          </span>
          {canManage && trigger.status === "active" && (
            <Button size="sm" variant="secondary" disabled={disabling} onClick={disable}>
              {disabling ? "Disabling…" : "Disable"}
            </Button>
          )}
        </div>
      </div>
      {expanded && (
        <div className="border-t border-border bg-surface-2/40 px-4 py-2">
          {!firings ? (
            <p className="py-2 text-xs text-muted-foreground">Loading firings…</p>
          ) : firings.length === 0 ? (
            <p className="py-2 text-xs text-muted-foreground">Never fired yet - always visible when it does, success or failure.</p>
          ) : (
            <div className="space-y-2 py-2">
              {firings.map((firing) => (
                <div key={firing.id} className="text-xs text-muted-foreground">
                  <span className={firing.status === "error" ? "text-red-400" : "text-emerald-400"}>
                    {firing.status === "error" ? "Failed" : "Proposed a mandate"}
                  </span>{" "}
                  at {new Date(firing.fired_at).toLocaleString()}
                  {firing.mandate_id && ` · mandate ${firing.mandate_id.slice(0, 8)}…`}
                  {firing.error_message && ` · ${firing.error_message}`}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function CreateTriggerDialog({
  projectId,
  documents,
  workspaces,
  open,
  onOpenChange,
  onCreated,
}: {
  projectId: string
  documents: ProjectDocument[]
  workspaces: Workspace[]
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: () => void
}) {
  const eventTypes = Object.keys(TRIGGER_EVENT_TEMPLATE_COMPATIBILITY)
  const [name, setName] = useState("")
  const [eventType, setEventType] = useState(eventTypes[0])
  const compatibleTemplates = TRIGGER_EVENT_TEMPLATE_COMPATIBILITY[eventType] ?? []
  const [templateKey, setTemplateKey] = useState(compatibleTemplates[0] ?? "")
  const [scopeId, setScopeId] = useState("")
  const [budgetLimit, setBudgetLimit] = useState("")
  const [reason, setReason] = useState("")
  const [saving, setSaving] = useState(false)

  function changeEventType(next: string) {
    setEventType(next)
    setTemplateKey(TRIGGER_EVENT_TEMPLATE_COMPATIBILITY[next]?.[0] ?? "")
    setScopeId("")
  }

  async function submit() {
    if (!name.trim() || !scopeId) {
      toast.error("A name and a scope are required.")
      return
    }
    setSaving(true)
    try {
      await createTrigger(projectId, {
        name: name.trim(),
        event_type: eventType,
        template_key: templateKey,
        scope_document_id: eventType === "document_version_changed" ? scopeId : null,
        scope_workspace_id: eventType === "decision_package_prepared" ? scopeId : null,
        budget_limit: budgetLimit ? Number(budgetLimit) : null,
        reason: reason.trim(),
      })
      toast.success("Trigger created.")
      setName(""); setReason(""); setBudgetLimit(""); setScopeId("")
      onOpenChange(false)
      onCreated()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not create this trigger.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>New monitoring trigger</DialogTitle>
          <DialogDescription>
            A standing, opt-in watch. Firing always creates a normal, visible mandate that still needs your explicit
            approval before it runs - never a hidden or automatic action.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-1">
          <label className="grid gap-1.5 text-sm font-medium text-foreground">
            Name
            <Input value={name} placeholder="e.g. Watch the IM for revisions" onChange={(event) => setName(event.target.value)} />
          </label>

          <label className="grid gap-1.5 text-sm font-medium text-foreground">
            Watch for
            <select
              value={eventType}
              onChange={(event) => changeEventType(event.target.value)}
              className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
            >
              {eventTypes.map((type) => (
                <option key={type} value={type}>{EVENT_TYPE_LABELS[type] ?? type}</option>
              ))}
            </select>
          </label>

          <label className="grid gap-1.5 text-sm font-medium text-foreground">
            Then propose
            <select
              value={templateKey}
              onChange={(event) => setTemplateKey(event.target.value)}
              className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
            >
              {compatibleTemplates.map((key) => (
                <option key={key} value={key}>{key}</option>
              ))}
            </select>
          </label>

          {eventType === "document_version_changed" ? (
            <label className="grid gap-1.5 text-sm font-medium text-foreground">
              Which document
              <select
                value={scopeId}
                onChange={(event) => setScopeId(event.target.value)}
                className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
              >
                <option value="">Select a document…</option>
                {documents.map((doc) => (
                  <option key={doc.id} value={doc.id}>{doc.original_filename}</option>
                ))}
              </select>
            </label>
          ) : (
            <label className="grid gap-1.5 text-sm font-medium text-foreground">
              Which workspace
              <select
                value={scopeId}
                onChange={(event) => setScopeId(event.target.value)}
                className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
              >
                <option value="">Select a workspace…</option>
                {workspaces.map((ws) => (
                  <option key={ws.id} value={ws.id}>
                    {ws.cross_format_analysis_id ? "Reconciliation" : "Integrity review"} — {new Date(ws.created_at).toLocaleDateString()}
                  </option>
                ))}
              </select>
            </label>
          )}

          <label className="grid gap-1.5 text-sm font-medium text-foreground">
            Budget limit (optional, in internal units)
            <Input
              type="number"
              value={budgetLimit}
              placeholder="e.g. 5"
              onChange={(event) => setBudgetLimit(event.target.value)}
            />
          </label>

          <label className="grid gap-1.5 text-sm font-medium text-foreground">
            Reason
            <Textarea
              value={reason}
              placeholder="Why does this watch exist?"
              rows={2}
              onChange={(event) => setReason(event.target.value)}
            />
          </label>
        </div>

        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button disabled={saving} onClick={submit}>{saving ? "Creating…" : "Create trigger"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function Triggers() {
  const { projectId } = useParams<{ projectId: string }>()
  const [triggers, setTriggers] = useState<Trigger[] | null>(null)
  const [documents, setDocuments] = useState<ProjectDocument[]>([])
  const [workspacesList, setWorkspacesList] = useState<Workspace[]>([])
  const [canManage, setCanManage] = useState(false)
  const [dialogOpen, setDialogOpen] = useState(false)

  function reload() {
    if (!projectId) return
    listTriggers(projectId).then(setTriggers).catch(() => toast.error("Could not load monitoring triggers."))
  }

  useEffect(() => {
    if (!projectId) return
    reload()
    listDocuments(projectId).then(setDocuments).catch(() => undefined)
    listWorkspaces(projectId).then(setWorkspacesList).catch(() => undefined)
    Promise.all([getSession(), listDealMemberships(projectId)])
      .then(([session, memberships]) => {
        const mine = memberships.find((m) => m.user_id === session.user.id && !m.revoked_at)
        setCanManage(mine?.role === "reviewer" || mine?.role === "deal_lead")
      })
      .catch(() => setCanManage(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId])

  if (!triggers) {
    return <div className="mx-auto max-w-4xl px-6 pt-8 pb-20 text-sm text-muted-foreground">Loading…</div>
  }

  return (
    <div className="mx-auto max-w-4xl px-6 pt-8 pb-20 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-heading text-2xl font-semibold text-foreground">Monitoring</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Opt-in watches for future changes. Every firing creates a normal, visible, budgeted mandate that still
            needs human approval - never hidden background inference.
          </p>
        </div>
        {canManage && <Button onClick={() => setDialogOpen(true)}>New trigger</Button>}
      </div>

      <Card className="p-0">
        {triggers.length === 0 ? (
          <p className="px-4 py-6 text-center text-sm text-muted-foreground">No monitoring triggers configured for this deal yet.</p>
        ) : (
          triggers.map((trigger) => (
            <TriggerRow key={trigger.id} trigger={trigger} canManage={canManage} projectId={projectId!} onChanged={reload} />
          ))
        )}
      </Card>

      {projectId && (
        <CreateTriggerDialog
          projectId={projectId}
          documents={documents}
          workspaces={workspacesList}
          open={dialogOpen}
          onOpenChange={setDialogOpen}
          onCreated={reload}
        />
      )}
    </div>
  )
}
