import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import {
  decideReassessmentItem,
  getReassessment,
  listDocuments,
  listReassessments,
  type ProjectDocument,
  type Reassessment,
  type ReassessmentItem,
} from "@/lib/api"

// Deep page, project-scoped (the real backend route
// /api/projects/:id/reassessments has no workspace filter exposed, so
// this lists every targeted reassessment for the deal directly - no
// workspace picker, unlike DecisionPackage.tsx/Readiness.tsx).

function ItemCard({
  projectId,
  reassessmentId,
  item,
  onDecided,
}: {
  projectId: string
  reassessmentId: string
  item: ReassessmentItem
  onDecided: () => void
}) {
  const [notes, setNotes] = useState(item.decision_notes)
  const [saving, setSaving] = useState(false)

  async function acknowledge() {
    setSaving(true)
    try {
      await decideReassessmentItem(projectId, reassessmentId, item.id, notes)
      toast.success("Reassessment item acknowledged.")
      onDecided()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not record this decision.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-2 border-b border-border px-4 py-3 text-sm last:border-b-0">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="min-w-0 flex-1 font-medium text-foreground">{item.finding_title}</p>
        <span
          className={`inline-block rounded-full border px-2 py-0.5 text-xs font-semibold ${
            item.decision === "acknowledged"
              ? "border-emerald-900 bg-emerald-950/60 text-emerald-300"
              : "border-amber-900 bg-amber-950/40 text-amber-300"
          }`}
        >
          {item.decision === "acknowledged" ? "Acknowledged" : "Pending"}
        </span>
      </div>
      <p className="text-xs text-muted-foreground">{item.explanation}</p>
      {item.evidence_of_change && (
        <p className="text-xs text-muted-foreground">Evidence of change: {item.evidence_of_change}</p>
      )}
      {item.decision === "pending" ? (
        <div className="flex items-start gap-2">
          <Textarea
            value={notes}
            placeholder="Decision notes (optional)…"
            rows={2}
            onChange={(event) => setNotes(event.target.value)}
            className="text-xs"
          />
          <Button size="sm" disabled={saving} onClick={acknowledge}>{saving ? "Saving…" : "Acknowledge"}</Button>
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">
          Acknowledged by {item.decided_by ?? "someone"} on {item.decided_at ? new Date(item.decided_at).toLocaleString() : ""}
          {item.decision_notes && ` — ${item.decision_notes}`}
        </p>
      )}
    </div>
  )
}

function ReassessmentCard({
  projectId,
  reassessment,
  documents,
}: {
  projectId: string
  reassessment: Reassessment
  documents: ProjectDocument[]
}) {
  const [detail, setDetail] = useState<(Reassessment & { items: ReassessmentItem[]; workspace_staleness: unknown }) | null>(null)

  function reload() {
    getReassessment(projectId, reassessment.id).then(setDetail).catch(() => toast.error("Could not load this reassessment."))
  }

  useEffect(reload, [projectId, reassessment.id])

  const doc = documents.find((d) => d.id === reassessment.document_id)

  return (
    <Card className="space-y-3 p-4">
      <div>
        <h3 className="font-heading text-lg font-semibold text-foreground">
          {doc ? doc.original_filename : "Document"} changed
        </h3>
        <p className="text-xs text-muted-foreground">{new Date(reassessment.created_at).toLocaleString()}</p>
      </div>
      <div>
        <h4 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">What changed</h4>
        <p className="mt-1 whitespace-pre-wrap text-sm text-foreground">{reassessment.what_changed}</p>
      </div>
      <div>
        <h4 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Executive summary</h4>
        <p className="mt-1 whitespace-pre-wrap text-sm text-foreground">{reassessment.executive_summary}</p>
      </div>
      {!detail ? (
        <p className="text-xs text-muted-foreground">Loading items…</p>
      ) : (
        <Card className="divide-y divide-border p-0">
          {detail.items.map((item) => (
            <ItemCard key={item.id} projectId={projectId} reassessmentId={reassessment.id} item={item} onDecided={reload} />
          ))}
          {detail.items.length === 0 && (
            <p className="px-4 py-4 text-center text-xs text-muted-foreground">No items were proposed.</p>
          )}
        </Card>
      )}
    </Card>
  )
}

export function Reassessments() {
  const { projectId } = useParams<{ projectId: string }>()
  const [reassessments, setReassessments] = useState<Reassessment[] | null>(null)
  const [documents, setDocuments] = useState<ProjectDocument[]>([])

  useEffect(() => {
    if (!projectId) return
    listReassessments(projectId).then(setReassessments).catch(() => toast.error("Could not load reassessments."))
    listDocuments(projectId).then(setDocuments).catch(() => undefined)
  }, [projectId])

  if (!reassessments) {
    return <div className="mx-auto max-w-4xl px-6 pt-8 pb-20 text-sm text-muted-foreground">Loading…</div>
  }

  return (
    <div className="mx-auto max-w-4xl px-6 pt-8 pb-20 space-y-4">
      <div>
        <h1 className="font-heading text-2xl font-semibold text-foreground">Reassessments</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          <Link to={`/projects/${projectId}/findings`} className="underline">Back to findings</Link>
        </p>
      </div>

      {reassessments.length === 0 ? (
        <Card className="p-6 text-sm text-muted-foreground">
          No targeted reassessment has been run for this deal yet. A reassessment is produced by running a
          "reassessment" mandate when a source document changes - not created directly from this screen.
        </Card>
      ) : (
        reassessments
          .slice()
          .sort((a, b) => b.created_at.localeCompare(a.created_at))
          .map((r) => <ReassessmentCard key={r.id} projectId={projectId!} reassessment={r} documents={documents} />)
      )}
    </div>
  )
}
