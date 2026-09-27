import { useEffect, useMemo, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import {
  confirmAssertion,
  disputeAssertion,
  listAssertionLedgerEntries,
  listDocuments,
  listTasksWithWorkProducts,
  type AssertionLedgerEntry,
  type ProjectDocument,
  type TaskWithWorkProducts,
} from "@/lib/api"

// Task 17.10 (D15, founder-directed): a real, visible surface for
// assertion_ledger.py - promoted, human-confirmed assertions from
// Integrity Review, with their own supersession/dispute history and
// staleness lineage, kept deliberately distinct from the reconciliation/
// human/AI findings register (Findings.tsx) rather than merged into it.
// An assertion is a claim a human confirmed once; a finding is an open
// matter under review - collapsing them would flatten a real distinction
// docs/03-domain-model.md itself draws (locator-valid vs. quoted-value-
// checked vs. calculation-reproduced vs. human-confirmed are different
// verification states, never one green check).

const MODALITY_LABELS: Record<string, string> = {
  firm: "Firm", hedged: "Hedged", speculative: "Speculative",
}

function EntryCard({
  entry,
  projectId,
  workProductTitle,
  documentNames,
  onChanged,
}: {
  entry: AssertionLedgerEntry
  projectId: string
  workProductTitle: string
  documentNames: string[]
  onChanged: () => void
}) {
  const [disputing, setDisputing] = useState(false)
  const [reason, setReason] = useState("")
  const [busy, setBusy] = useState(false)

  async function submitDispute() {
    if (!reason.trim()) {
      toast.error("A reason is required to dispute an assertion.")
      return
    }
    setBusy(true)
    try {
      await disputeAssertion(projectId, entry.entry_key, reason.trim())
      toast.success("Assertion disputed.")
      setDisputing(false)
      setReason("")
      onChanged()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not dispute this assertion.")
    } finally {
      setBusy(false)
    }
  }

  async function submitConfirm() {
    setBusy(true)
    try {
      await confirmAssertion(projectId, entry.entry_key)
      toast.success("Assertion confirmed.")
      onChanged()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not confirm this assertion.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="space-y-2 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="min-w-0 flex-1 text-sm text-foreground">{entry.assertion_text}</p>
        <span
          className={`shrink-0 rounded-full border px-2 py-0.5 text-xs font-semibold ${
            entry.verification_status === "confirmed"
              ? "border-emerald-900 bg-emerald-950/60 text-emerald-300"
              : "border-red-900 bg-red-950/60 text-red-300"
          }`}
        >
          {entry.verification_status === "confirmed" ? "Confirmed" : "Disputed"}
        </span>
      </div>
      <p className="text-xs text-muted-foreground">
        From {workProductTitle || "a work product"} · Modality: {MODALITY_LABELS[entry.modality] ?? entry.modality}
        {documentNames.length > 0 && ` · Evidence: ${documentNames.join(", ")}`}
      </p>
      {entry.verification_status === "disputed" && entry.dispute_reason && (
        <p className="rounded-md border border-red-900 bg-red-950/30 px-3 py-2 text-xs text-red-300">
          Disputed by {entry.disputed_by ?? "someone"}: {entry.dispute_reason}
        </p>
      )}
      {entry.published_finding_id && (
        <p className="text-xs text-muted-foreground">
          <Link to={`/projects/${projectId}/findings`} className="underline">View the published finding</Link>
        </p>
      )}
      <div className="flex items-center gap-2">
        {entry.verification_status === "confirmed" ? (
          disputing ? (
            <div className="flex w-full items-start gap-2">
              <Textarea
                value={reason}
                placeholder="Why is this assertion no longer supported?"
                rows={2}
                onChange={(event) => setReason(event.target.value)}
                className="text-xs"
              />
              <Button size="sm" variant="secondary" disabled={busy} onClick={submitDispute}>Submit</Button>
              <Button size="sm" variant="secondary" disabled={busy} onClick={() => setDisputing(false)}>Cancel</Button>
            </div>
          ) : (
            <Button size="sm" variant="secondary" onClick={() => setDisputing(true)}>Dispute</Button>
          )
        ) : (
          <Button size="sm" disabled={busy} onClick={submitConfirm}>{busy ? "Confirming…" : "Re-confirm"}</Button>
        )}
      </div>
    </Card>
  )
}

export function Assertions() {
  const { projectId } = useParams<{ projectId: string }>()
  const [entries, setEntries] = useState<AssertionLedgerEntry[] | null>(null)
  const [tasks, setTasks] = useState<TaskWithWorkProducts[]>([])
  const [documents, setDocuments] = useState<ProjectDocument[]>([])

  function reload() {
    if (!projectId) return
    listAssertionLedgerEntries(projectId).then(setEntries).catch(() => toast.error("Could not load the assertion ledger."))
  }

  useEffect(() => {
    if (!projectId) return
    reload()
    listTasksWithWorkProducts(projectId).then(setTasks).catch(() => undefined)
    listDocuments(projectId).then(setDocuments).catch(() => undefined)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId])

  const workProductTitles = useMemo(() => {
    const map: Record<string, string> = {}
    for (const task of tasks) {
      for (const wp of task.work_products) map[wp.id] = wp.title
    }
    return map
  }, [tasks])

  const documentNamesById = useMemo(() => {
    const map: Record<string, string> = {}
    for (const doc of documents) map[doc.id] = doc.original_filename
    return map
  }, [documents])

  if (!entries) {
    return <div className="mx-auto max-w-4xl px-6 pt-8 pb-20 text-sm text-muted-foreground">Loading…</div>
  }

  return (
    <div className="mx-auto max-w-4xl px-6 pt-8 pb-20 space-y-4">
      <div>
        <h1 className="font-heading text-2xl font-semibold text-foreground">Assertions</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Claims confirmed through Integrity Review, kept distinct from open findings.{" "}
          <Link to={`/projects/${projectId}/findings`} className="underline">Back to findings</Link>
        </p>
      </div>

      {entries.length === 0 ? (
        <Card className="p-6 text-sm text-muted-foreground">
          No assertion has been promoted for this deal yet. An assertion is created when an Integrity Review
          candidate is accepted - not created directly from this screen.
        </Card>
      ) : (
        entries.map((entry) => (
          <EntryCard
            key={entry.id}
            entry={entry}
            projectId={projectId!}
            workProductTitle={workProductTitles[entry.target_work_product_id] ?? ""}
            documentNames={entry.source_document_ids.map((id) => documentNamesById[id]).filter((n): n is string => Boolean(n))}
            onChanged={reload}
          />
        ))
      )}
    </div>
  )
}
