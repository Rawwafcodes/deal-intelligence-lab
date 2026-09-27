import { useState } from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import {
  FINDING_SEVERITIES,
  FindingConflictError,
  RESOLUTION_STATUSES,
  REVIEW_STATUSES,
  updateFindingWorkflow,
  type Finding,
  type FindingWorkflowUpdate,
} from "@/lib/api"
import { labelFor, type PinnedVersions } from "@/lib/findingDisplay"

// Surface #15 (Finding Detail): an inline expansion inside Findings, not a
// separate route. Shows the finding's immutable content and its evidence,
// with citation links pinned to the exact document version that was
// analysed (never "whatever is current now"), plus the human review fields
// for roles holding manage_findings. Saves carry the finding's revision;
// a 409 shows what the other person saved rather than overwriting it.

function versionHref(projectId: string, documentId: string, pinned: PinnedVersions, page?: number): string {
  const project = encodeURIComponent(projectId)
  const document = encodeURIComponent(documentId)
  const fragment = page ? `#page=${page}` : ""
  const versionId = pinned[documentId]
  return versionId
    ? `/api/projects/${project}/documents/${document}/versions/${encodeURIComponent(versionId)}/download?inline=1${fragment}`
    : `/api/projects/${project}/documents/${document}/download?inline=1${fragment}`
}

const SELECT_CLASS = "rounded-md border border-border bg-background px-2 py-1.5 text-sm text-foreground disabled:opacity-50"

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">{title}</h3>
      <div className="mt-1 text-sm text-foreground">{children}</div>
    </div>
  )
}

function Evidence({ finding, projectId, pinned }: { finding: Finding; projectId: string; pinned: PinnedVersions }) {
  const hasCitations = finding.pdf_citations.length > 0 || finding.excel_citations.length > 0
  const fallback = [finding.pdf_evidence, finding.workbook_evidence, finding.evidence_notes].filter((t) => t?.trim())
  if (!hasCitations && fallback.length === 0) {
    return <p className="text-sm text-muted-foreground">No evidence locators recorded for this finding.</p>
  }
  return (
    <ul className="space-y-2">
      {finding.pdf_citations.map((citation, index) => {
        const pageLabel = citation.end_page > citation.start_page + 1
          ? `pp. ${citation.start_page}–${citation.end_page - 1}`
          : `p. ${citation.start_page}`
        return (
          <li key={`pdf-${index}`} className="rounded-md border border-border px-3 py-2">
            <div className="text-xs text-muted-foreground">
              {citation.document_id ? (
                <a
                  className="underline"
                  href={versionHref(projectId, citation.document_id, pinned, citation.start_page)}
                  target="_blank"
                  rel="noreferrer"
                >
                  {citation.document_title ?? "Document"} · {pageLabel}
                </a>
              ) : (
                <span>{citation.document_title ?? "Document"} · {pageLabel}</span>
              )}
            </div>
            <p className="mt-1 line-clamp-4 text-xs whitespace-pre-line text-foreground">{citation.cited_text}</p>
          </li>
        )
      })}
      {finding.excel_citations.map((citation, index) => {
        const label = `${citation.document_filename ?? citation.workbook_label} · ${citation.sheet}!${citation.ref} (${citation.kind})`
        return (
          <li key={`xl-${index}`} className="rounded-md border border-border px-3 py-2 text-xs">
            {citation.document_id ? (
              <a className="underline" href={versionHref(projectId, citation.document_id, pinned)} target="_blank" rel="noreferrer">
                {label}
              </a>
            ) : (
              <span>{label}</span>
            )}
            {citation.exists === false && <span className="ml-2 text-destructive">cell not found in workbook</span>}
          </li>
        )
      })}
      {!hasCitations && fallback.map((text, index) => (
        <li key={`text-${index}`} className="rounded-md border border-border px-3 py-2 text-xs whitespace-pre-line">{text}</li>
      ))}
    </ul>
  )
}

function ReviewPanel({
  finding, projectId, canManage, onSaved,
}: { finding: Finding; projectId: string; canManage: boolean; onSaved: (finding: Finding) => void }) {
  const [draft, setDraft] = useState<Required<FindingWorkflowUpdate>>({
    review_status: finding.review_status || "unreviewed",
    adjusted_severity: finding.adjusted_severity,
    resolution_status: finding.resolution_status || "open",
    assigned_owner: finding.assigned_owner,
    reviewer_notes: finding.reviewer_notes,
  })
  const [saving, setSaving] = useState(false)
  const [conflict, setConflict] = useState<Finding | null>(null)

  const dirty =
    draft.review_status !== (finding.review_status || "unreviewed") ||
    draft.adjusted_severity !== finding.adjusted_severity ||
    draft.resolution_status !== (finding.resolution_status || "open") ||
    draft.assigned_owner !== finding.assigned_owner ||
    draft.reviewer_notes !== finding.reviewer_notes

  async function save() {
    setSaving(true)
    try {
      const saved = await updateFindingWorkflow(projectId, finding.workspace_id, finding.id, draft, finding.revision)
      setConflict(null)
      onSaved(saved)
      toast.success("Finding review saved.")
    } catch (error) {
      if (error instanceof FindingConflictError) setConflict(error.current)
      else toast.error(error instanceof Error ? error.message : "Could not save this finding.")
    } finally {
      setSaving(false)
    }
  }

  function loadLatest() {
    if (!conflict) return
    const latest = { ...finding, ...conflict }
    setDraft({
      review_status: latest.review_status || "unreviewed",
      adjusted_severity: latest.adjusted_severity,
      resolution_status: latest.resolution_status || "open",
      assigned_owner: latest.assigned_owner,
      reviewer_notes: latest.reviewer_notes,
    })
    setConflict(null)
    onSaved(latest)
  }

  if (!canManage) {
    return (
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-4">
        <dt className="text-muted-foreground">Review</dt><dd>{labelFor(finding.review_status || "unreviewed")}</dd>
        <dt className="text-muted-foreground">Resolution</dt><dd>{labelFor(finding.resolution_status || "open")}</dd>
      </dl>
    )
  }

  return (
    <div className="space-y-3">
      {conflict && (
        <div role="alert" className="rounded-md border border-amber-900 bg-amber-950/40 px-3 py-2 text-sm text-amber-300">
          <p className="font-medium">Someone else saved this finding while you were editing. Your changes were not saved.</p>
          <p className="mt-1 text-xs">
            Their version: review {labelFor(conflict.review_status || "unreviewed")} · severity{" "}
            {labelFor(conflict.adjusted_severity ?? conflict.severity)} · resolution {labelFor(conflict.resolution_status || "open")}
            {conflict.reviewer_notes ? ` · notes: "${conflict.reviewer_notes}"` : ""}
          </p>
          <Button size="sm" variant="secondary" className="mt-2" onClick={loadLatest}>Load their version</Button>
        </div>
      )}
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="grid gap-1 text-xs font-medium text-muted-foreground">
          Review decision
          <select
            className={SELECT_CLASS}
            value={draft.review_status}
            onChange={(e) => setDraft({ ...draft, review_status: e.target.value })}
          >
            {REVIEW_STATUSES.map((s) => <option key={s} value={s}>{labelFor(s)}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-xs font-medium text-muted-foreground">
          Adjusted severity
          <select
            className={SELECT_CLASS}
            value={draft.adjusted_severity ?? ""}
            onChange={(e) => setDraft({ ...draft, adjusted_severity: e.target.value || null })}
          >
            <option value="">As assessed ({labelFor(finding.severity)})</option>
            {FINDING_SEVERITIES.map((s) => <option key={s} value={s}>{labelFor(s)}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-xs font-medium text-muted-foreground">
          Resolution
          <select
            className={SELECT_CLASS}
            value={draft.resolution_status}
            onChange={(e) => setDraft({ ...draft, resolution_status: e.target.value })}
          >
            {RESOLUTION_STATUSES.map((s) => <option key={s} value={s}>{labelFor(s)}</option>)}
          </select>
        </label>
      </div>
      <label className="grid gap-1 text-xs font-medium text-muted-foreground">
        Owner
        <Input
          value={draft.assigned_owner}
          placeholder="Who owns resolving this?"
          onChange={(e) => setDraft({ ...draft, assigned_owner: e.target.value })}
        />
      </label>
      <label className="grid gap-1 text-xs font-medium text-muted-foreground">
        Reviewer notes
        <Textarea
          value={draft.reviewer_notes}
          rows={2}
          placeholder="Why you reached this decision"
          onChange={(e) => setDraft({ ...draft, reviewer_notes: e.target.value })}
        />
      </label>
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-muted-foreground">Revision {finding.revision}</span>
        <Button size="sm" disabled={saving || !dirty} onClick={save}>{saving ? "Saving…" : "Save review"}</Button>
      </div>
    </div>
  )
}

export function FindingDetail({
  finding, projectId, pinned, canManage, onSaved,
}: {
  finding: Finding
  projectId: string
  pinned: PinnedVersions
  canManage: boolean
  onSaved: (finding: Finding) => void
}) {
  const originLabel = finding.origin === "ai" ? "AI reconciliation" : finding.origin === "integrity" ? "Integrity review" : "Added by a reviewer"
  return (
    <div className="space-y-4 border-t border-border bg-surface-2/40 px-4 py-4">
      <p className="text-xs text-muted-foreground">
        {originLabel}{finding.classification ? ` · ${finding.classification}` : ""}
        {finding.adjusted_severity ? ` · assessed ${labelFor(finding.severity)}, adjusted to ${labelFor(finding.adjusted_severity)}` : ""}
      </p>
      {finding.explanation && <Section title="Explanation">{finding.explanation}</Section>}
      <Section title="Evidence"><Evidence finding={finding} projectId={projectId} pinned={pinned} /></Section>
      {finding.commercial_relevance && <Section title="Commercial relevance">{finding.commercial_relevance}</Section>}
      {finding.uncertainty && <Section title="Uncertainty">{finding.uncertainty}</Section>}
      {finding.recommended_action && <Section title="Recommended action">{finding.recommended_action}</Section>}
      {finding.management_response && <Section title="Management response">{finding.management_response}</Section>}
      <Section title="Review">
        <ReviewPanel key={finding.revision} finding={finding} projectId={projectId} canManage={canManage} onSaved={onSaved} />
      </Section>
    </div>
  )
}
