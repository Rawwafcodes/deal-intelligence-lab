import { useEffect, useRef, useState } from "react"
import { useParams } from "react-router-dom"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import {
  approvePlan,
  cancelRun,
  decideIntegrityCandidate,
  getCurrentBriefVersion,
  getIntegrityReview,
  getMandate,
  listDocuments,
  listMandateTemplates,
  listTasksWithWorkProducts,
  listWorkstreams,
  NON_TERMINAL_RUN_STATUSES,
  proposePlan,
  proposePlanWithAi,
  rejectPlan,
  resumeRun,
  startRun,
  type CurrentBriefVersion,
  type IntegrityCandidateDecisionPayload,
  type IntegrityReview,
  type Mandate,
  type MandateTemplate,
  type PlanProposalOutcome,
  type ProjectDocument,
  type TaskWithWorkProducts,
  type WorkstreamSummary,
} from "@/lib/api"

// Mirrors mandates.py's own _CAPABILITIES_NEEDING_DOCUMENT_SELECTION: the
// set of capabilities whose stage input is a source document selection,
// not something derivable purely from the mandate's objective (see
// mandates.py's _default_input_for_stage). Task 12.5 added a second
// template built on this same capability (`reconciliation-with-review`),
// which is exactly why this is keyed by capability, not by a single
// hardcoded template key - a human picking either template from the
// manual dropdown below needs the same document checklist.
const CAPABILITIES_NEEDING_DOCUMENT_SELECTION = new Set(["reconciliation.cross_format"])

// Task 14.2: integrity.review_work_product needs a genuinely different
// selection UI (target/peer submission + version, not a flat document
// checklist) - kept as its own set/branch rather than folded into the
// one above, since its stage input shape is not "a list of document ids"
// at all.
const INTEGRITY_REVIEW_CAPABILITY = "integrity.review_work_product"

const STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  planning: "Planning",
  awaiting_approval: "Awaiting approval",
  active: "Active",
  under_review: "Under review",
  completed: "Completed",
  cancelled: "Cancelled",
  failed: "Failed",
}

// Task 12.2: a run now spends real time in these statuses while the
// durable worker (a background thread independent of this page) actually
// processes it - this page polls while any run is in one of them, rather
// than assuming the run is already finished once startRun()/resumeRun()
// resolve.
const RUN_STATUS_LABELS: Record<string, string> = {
  queued: "Queued",
  running: "Running",
  succeeded: "Succeeded",
  failed: "Failed",
  interrupted: "Interrupted",
  outcome_unknown: "Outcome unknown - needs review",
  cancel_requested: "Cancelling…",
  cancelled: "Cancelled",
  waiting_for_input: "Waiting for input",
}

function StageRow({ stage }: { stage: Mandate["plans"][number]["stages"][number] }) {
  const isCheckpoint = stage.kind === "human_checkpoint"
  return (
    <li className="flex items-center justify-between gap-3 rounded-md border border-border px-3 py-2 text-sm">
      <span className="font-medium text-foreground">{stage.id}</span>
      <span className="text-muted-foreground">
        {isCheckpoint ? "Human checkpoint" : stage.capability}
      </span>
    </li>
  )
}

const CANDIDATE_DECISION_LABELS: Record<string, string> = {
  pending: "Pending review",
  accepted: "Accepted — published",
  rejected: "Rejected",
  duplicate: "Marked as duplicate",
  unresolved: "Left unresolved",
}

// Task 14.2: the human checkpoint made real - a candidate only ever
// becomes a shared finding through the explicit "Accept" action below
// (server.py's own candidate-decision route), never automatically when
// the capability stage above finishes.
function IntegrityReviewPanel({ projectId, reviewId }: { projectId: string; reviewId: string }) {
  const [review, setReview] = useState<IntegrityReview | null>(null)
  const [busyCandidateId, setBusyCandidateId] = useState<string | null>(null)
  const [notesByCandidate, setNotesByCandidate] = useState<Record<string, string>>({})
  const [duplicateTargetByCandidate, setDuplicateTargetByCandidate] = useState<Record<string, string>>({})

  async function load() {
    try {
      setReview(await getIntegrityReview(projectId, reviewId))
    } catch {
      toast.error("Could not load the integrity review.")
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reviewId])

  async function decide(candidateId: string, decision: IntegrityCandidateDecisionPayload["decision"]) {
    const payload: IntegrityCandidateDecisionPayload = {
      decision,
      decision_notes: notesByCandidate[candidateId]?.trim() || undefined,
    }
    if (decision === "duplicate") {
      const duplicateOf = duplicateTargetByCandidate[candidateId]?.trim()
      if (!duplicateOf) {
        toast.error("Enter the id of the existing finding this candidate duplicates.")
        return
      }
      payload.duplicate_of_finding_id = duplicateOf
    }
    setBusyCandidateId(candidateId)
    try {
      await decideIntegrityCandidate(projectId, reviewId, candidateId, payload)
      await load()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not record that decision.")
    } finally {
      setBusyCandidateId(null)
    }
  }

  if (!review) {
    return <p className="mt-1 text-xs text-muted-foreground">Loading integrity review candidates…</p>
  }

  return (
    <div className="mt-3 space-y-3 border-t border-border pt-3">
      <p className="text-xs text-muted-foreground">
        {review.candidates.length} candidate{review.candidates.length === 1 ? "" : "s"} from real model {review.model}
        {review.published_findings.length > 0 &&
          ` · ${review.published_findings.length} published to the shared findings register`}
      </p>
      {review.candidates.length === 0 && (
        <p className="text-xs text-muted-foreground">No candidates were proposed.</p>
      )}
      {review.candidates.map((candidate) => (
        <div key={candidate.id} className="rounded-md border border-border p-3 text-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-medium text-foreground">{candidate.title || "(untitled candidate)"}</span>
            <span className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">
              {CANDIDATE_DECISION_LABELS[candidate.decision] ?? candidate.decision}
            </span>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {candidate.classification || "unclassified"} · {candidate.severity || "no severity"} ·{" "}
            {candidate.deterministic_or_judgment || "unspecified"}
          </p>
          <div className="mt-2 space-y-1 text-xs text-foreground">
            <p><span className="font-medium">Assertion:</span> {candidate.assertion}</p>
            <p><span className="font-medium">Conflicting/missing evidence:</span> {candidate.conflicting_or_missing_evidence}</p>
            <p className="text-muted-foreground"><span className="font-medium">Why it matters:</span> {candidate.why_it_matters}</p>
            <p className="text-muted-foreground"><span className="font-medium">Uncertainty:</span> {candidate.uncertainty}</p>
            <p className="text-muted-foreground"><span className="font-medium">Recommended resolution:</span> {candidate.recommended_resolution}</p>
          </div>

          {candidate.decision === "pending" ? (
            <div className="mt-3 space-y-2">
              <Textarea
                placeholder="Decision notes (optional)"
                rows={1}
                value={notesByCandidate[candidate.id] ?? ""}
                onChange={(event) =>
                  setNotesByCandidate((prev) => ({ ...prev, [candidate.id]: event.target.value }))
                }
              />
              <div className="flex flex-wrap items-center gap-2">
                <Button size="sm" disabled={busyCandidateId === candidate.id} onClick={() => decide(candidate.id, "accepted")}>
                  Accept
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={busyCandidateId === candidate.id}
                  onClick={() => decide(candidate.id, "rejected")}
                >
                  Reject
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={busyCandidateId === candidate.id}
                  onClick={() => decide(candidate.id, "unresolved")}
                >
                  Leave unresolved
                </Button>
                <Input
                  placeholder="Existing finding id"
                  className="h-7 w-36 text-xs"
                  value={duplicateTargetByCandidate[candidate.id] ?? ""}
                  onChange={(event) =>
                    setDuplicateTargetByCandidate((prev) => ({ ...prev, [candidate.id]: event.target.value }))
                  }
                />
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={busyCandidateId === candidate.id}
                  onClick={() => decide(candidate.id, "duplicate")}
                >
                  Mark duplicate
                </Button>
              </div>
            </div>
          ) : (
            <p className="mt-2 text-xs text-muted-foreground">
              {CANDIDATE_DECISION_LABELS[candidate.decision] ?? candidate.decision}
              {candidate.decision_notes && ` — ${candidate.decision_notes}`}
            </p>
          )}
        </div>
      ))}
    </div>
  )
}

export function MandateDetail() {
  const { projectId, mandateId } = useParams<{ projectId: string; mandateId: string }>()
  const [mandate, setMandate] = useState<Mandate | null>(null)
  const [templates, setTemplates] = useState<MandateTemplate[]>([])
  const [selectedTemplate, setSelectedTemplate] = useState("")
  const [decision, setDecision] = useState("")
  const [budgetLimit, setBudgetLimit] = useState("")
  const [busy, setBusy] = useState(false)
  const [documents, setDocuments] = useState<ProjectDocument[]>([])
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<Set<string>>(new Set())
  const [aiOutcome, setAiOutcome] = useState<PlanProposalOutcome | null>(null)
  const [aiFeedback, setAiFeedback] = useState("")
  const [tasksWithWorkProducts, setTasksWithWorkProducts] = useState<TaskWithWorkProducts[]>([])
  const [workstreams, setWorkstreams] = useState<WorkstreamSummary[]>([])
  const [currentBrief, setCurrentBrief] = useState<CurrentBriefVersion | null>(null)
  const [targetWorkProductId, setTargetWorkProductId] = useState("")
  const [selectedPeerIds, setSelectedPeerIds] = useState<Set<string>>(new Set())
  const [includeBrief, setIncludeBrief] = useState(false)
  const [selectedWorkstreamId, setSelectedWorkstreamId] = useState("")
  const [reviewScope, setReviewScope] = useState("")
  const reloadingRef = useRef(false)

  async function reload() {
    if (!projectId || !mandateId || reloadingRef.current) return
    reloadingRef.current = true
    try {
      const [loaded, templateList, documentList, taskList, workstreamList, brief] = await Promise.all([
        getMandate(projectId, mandateId),
        listMandateTemplates(),
        listDocuments(projectId),
        listTasksWithWorkProducts(projectId),
        listWorkstreams(projectId),
        getCurrentBriefVersion(projectId),
      ])
      setMandate(loaded)
      setTemplates(templateList)
      setDocuments(documentList)
      setTasksWithWorkProducts(taskList)
      setWorkstreams(workstreamList)
      setCurrentBrief(brief)
      if (!selectedTemplate && templateList.length > 0) setSelectedTemplate(templateList[0].key)
    } catch {
      toast.error("Could not load this mandate.")
    } finally {
      reloadingRef.current = false
    }
  }

  function toggleDocument(documentId: string) {
    setSelectedDocumentIds((prev) => {
      const next = new Set(prev)
      if (next.has(documentId)) next.delete(documentId)
      else next.add(documentId)
      return next
    })
  }

  function togglePeer(workProductId: string) {
    setSelectedPeerIds((prev) => {
      const next = new Set(prev)
      if (next.has(workProductId)) next.delete(workProductId)
      else next.add(workProductId)
      return next
    })
  }

  useEffect(() => {
    reload()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, mandateId])

  // Task 12.2: the durable worker finishes a run on its own background
  // thread, independent of this page - poll while any run is still being
  // processed (queued/running/cancel_requested) so the UI catches up
  // without a manual refresh, instead of assuming startRun()/resumeRun()
  // already reflect the final outcome.
  const hasActiveRun = mandate?.runs.some((run) => NON_TERMINAL_RUN_STATUSES.includes(run.status)) ?? false
  useEffect(() => {
    if (!hasActiveRun) return
    const interval = window.setInterval(reload, 750)
    return () => window.clearInterval(interval)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasActiveRun])

  async function withBusy(action: () => Promise<void>) {
    setBusy(true)
    try {
      await action()
      await reload()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Something went wrong.")
    } finally {
      setBusy(false)
    }
  }

  // Task 12.4: unlike withBusy's other actions, a "not confident enough"
  // result from the planner is a normal, expected outcome (docs/04:
  // "Display unavailable work as unsupported") - not an error to toast and
  // discard. It's kept in state and shown inline, with a way to add
  // guidance and try again, rather than the human getting nothing back.
  async function handleProposeWithAi(feedback?: string) {
    if (!projectId || !mandateId) return
    setBusy(true)
    try {
      const outcome = await proposePlanWithAi(projectId, mandateId, feedback)
      setAiOutcome(outcome.status === "unsupported" ? outcome : null)
      if (outcome.status === "proposed") setAiFeedback("")
      await reload()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "The planner could not be reached.")
    } finally {
      setBusy(false)
    }
  }

  if (!mandate || !projectId || !mandateId) {
    return <div className="mx-auto max-w-3xl px-6 pt-8 pb-20 text-sm text-muted-foreground">Loading…</div>
  }

  const proposedPlan = mandate.plans.find((p) => p.status === "proposed")
  const approvedPlan = mandate.plans.find((p) => p.id === mandate.current_plan_id)
  const latestRun = mandate.runs[mandate.runs.length - 1]
  const awaitingHumanAttempt = latestRun?.attempts.find((a) => a.status === "awaiting_human")

  const selectedTemplateObject = templates.find((t) => t.key === selectedTemplate)
  const isReconciliation = Boolean(
    selectedTemplateObject?.stages.some(
      (stage) => stage.capability && CAPABILITIES_NEEDING_DOCUMENT_SELECTION.has(stage.capability)
    )
  )
  const pdfDocuments = documents.filter((d) => d.extension === ".pdf")
  const excelDocuments = documents.filter((d) => d.extension === ".xlsx" || d.extension === ".xls")
  const selectedPdfCount = pdfDocuments.filter((d) => selectedDocumentIds.has(d.id)).length
  const selectedExcelCount = excelDocuments.filter((d) => selectedDocumentIds.has(d.id)).length
  const reconciliationSelectionValid = selectedPdfCount >= 1 && selectedExcelCount >= 1

  const isIntegrityReview = Boolean(
    selectedTemplateObject?.stages.some((stage) => stage.capability === INTEGRITY_REVIEW_CAPABILITY)
  )
  // v1 scope boundary (integrity_review.py's own docstring): the target
  // submission and any peer submissions must be PDF; source documents
  // may be PDF or Excel, exactly like reconciliation's own picker above.
  const allWorkProducts = tasksWithWorkProducts.flatMap((t) =>
    t.work_products.map((wp) => ({ ...wp, taskTitle: t.title }))
  )
  const pdfWorkProducts = allWorkProducts.filter((wp) => wp.extension === ".pdf")
  const peerCandidates = pdfWorkProducts.filter((wp) => wp.id !== targetWorkProductId)
  const integrityReviewSelectionValid = Boolean(targetWorkProductId) && selectedDocumentIds.size >= 1

  const canProposePlan = isReconciliation
    ? reconciliationSelectionValid
    : isIntegrityReview
      ? integrityReviewSelectionValid
      : Boolean(selectedTemplate)

  function buildIntegrityReviewStageInput() {
    const targetWorkProduct = allWorkProducts.find((wp) => wp.id === targetWorkProductId)
    if (!targetWorkProduct?.current_version_id) return null
    const documentRefs = Array.from(selectedDocumentIds).flatMap((documentId) => {
      const doc = documents.find((d) => d.id === documentId)
      return doc?.current_version_id ? [{ document_id: documentId, version_id: doc.current_version_id }] : []
    })
    const peerRefs = Array.from(selectedPeerIds).flatMap((workProductId) => {
      const peer = allWorkProducts.find((wp) => wp.id === workProductId)
      return peer?.current_version_id
        ? [{ work_product_id: workProductId, version_id: peer.current_version_id }]
        : []
    })
    return {
      target: { work_product_id: targetWorkProduct.id, version_id: targetWorkProduct.current_version_id },
      documents: documentRefs,
      ...(peerRefs.length > 0 ? { peers: peerRefs } : {}),
      ...(includeBrief && currentBrief ? { brief_version_id: currentBrief.id } : {}),
      ...(selectedWorkstreamId ? { workstream_id: selectedWorkstreamId } : {}),
      ...(reviewScope.trim() ? { review_scope: reviewScope.trim() } : {}),
    }
  }

  function resetIntegrityReviewSelection() {
    setSelectedDocumentIds(new Set())
    setTargetWorkProductId("")
    setSelectedPeerIds(new Set())
    setIncludeBrief(false)
    setSelectedWorkstreamId("")
    setReviewScope("")
  }

  return (
    <>
      <div className="mx-auto max-w-3xl px-6 pt-8 pb-20 space-y-6">
        <div>
          <h1 className="font-heading text-2xl font-semibold text-foreground">{mandate.objective}</h1>
          <span className="mt-2 inline-block rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">
            {STATUS_LABELS[mandate.status] ?? mandate.status}
          </span>
        </div>

        {mandate.status === "draft" && (
          <Card className="p-6">
            <h2 className="font-heading text-lg font-semibold text-foreground">Propose a plan with AI</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              A real model reads this mandate&rsquo;s objective, deal brief, and the project&rsquo;s real
              documents (filenames only, never file content) and proposes which capability to use and -
              for reconciliation - which documents look like the right pair. Every claim it makes is
              independently re-checked before anything is proposed for your approval; if it isn&rsquo;t
              confident, it says so instead of guessing.
            </p>
            <div className="mt-4">
              <Button disabled={busy} onClick={() => handleProposeWithAi()}>
                Propose with AI
              </Button>
            </div>
            {aiOutcome && aiOutcome.status === "unsupported" && (
              <div className="mt-4 space-y-3 rounded-md border border-destructive/40 bg-destructive/5 p-4">
                <p className="text-sm font-medium text-foreground">
                  The planner could not confidently propose a plan.
                </p>
                <p className="text-sm text-muted-foreground">{aiOutcome.reason}</p>
                {aiOutcome.reasoning && (
                  <p className="text-xs text-muted-foreground">{aiOutcome.reasoning}</p>
                )}
                <Textarea
                  placeholder="Add guidance for the planner and try again (optional)"
                  value={aiFeedback}
                  onChange={(event) => setAiFeedback(event.target.value)}
                  rows={2}
                />
                <Button
                  variant="secondary"
                  disabled={busy}
                  onClick={() => handleProposeWithAi(aiFeedback.trim() || undefined)}
                >
                  Try again
                </Button>
              </div>
            )}
          </Card>
        )}

        {mandate.status === "draft" && (
          <Card className="p-6">
            <h2 className="font-heading text-lg font-semibold text-foreground">Propose manually</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {isReconciliation
                ? "A real, paid Claude call reconciling the documents you select below against each other - not a fixture."
                : isIntegrityReview
                  ? "A real, paid Claude call reviewing the submission you select below against the evidence and any peer submissions you also select - exact versions, never “whatever is current.”"
                  : "A deterministic fixture planner only, for now - no AI call. Pick a template."}
            </p>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <select
                aria-label="Template"
                className="h-9 rounded-md border border-border bg-background px-2 text-sm text-foreground"
                value={selectedTemplate}
                onChange={(event) => setSelectedTemplate(event.target.value)}
              >
                {templates.map((template) => (
                  <option key={template.key} value={template.key}>
                    {template.name}
                  </option>
                ))}
              </select>
              {!isReconciliation && !isIntegrityReview && (
                <Button
                  disabled={busy || !canProposePlan}
                  onClick={() => withBusy(() => proposePlan(projectId, mandateId, selectedTemplate).then(() => {}))}
                >
                  Propose plan
                </Button>
              )}
            </div>

            {isIntegrityReview && (
              <div className="mt-4 space-y-4">
                <div>
                  <p className="mb-2 text-sm font-medium text-foreground">
                    Submission under review (must be a PDF)
                  </p>
                  <select
                    aria-label="Submission under review"
                    className="h-9 w-full rounded-md border border-border bg-background px-2 text-sm text-foreground"
                    value={targetWorkProductId}
                    onChange={(event) => setTargetWorkProductId(event.target.value)}
                  >
                    <option value="">Select a submission…</option>
                    {pdfWorkProducts.map((wp) => (
                      <option key={wp.id} value={wp.id}>
                        {wp.taskTitle} — {wp.title} (v{wp.version_number})
                      </option>
                    ))}
                  </select>
                  {pdfWorkProducts.length === 0 && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      No PDF work-product submissions exist yet in this project.
                    </p>
                  )}
                </div>

                <div>
                  <p className="mb-2 text-sm font-medium text-foreground">Source evidence (select at least one)</p>
                  {documents.length === 0 ? (
                    <p className="text-sm text-muted-foreground">This project has no documents yet.</p>
                  ) : (
                    <ul className="space-y-1">
                      {[...pdfDocuments, ...excelDocuments].map((doc) => (
                        <li key={doc.id}>
                          <label className="flex items-center gap-2 text-sm text-foreground">
                            <input
                              type="checkbox"
                              checked={selectedDocumentIds.has(doc.id)}
                              onChange={() => toggleDocument(doc.id)}
                            />
                            {doc.original_filename} (v{doc.version_number})
                          </label>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <div>
                  <p className="mb-2 text-sm font-medium text-foreground">Peer submissions (optional, PDF only)</p>
                  {peerCandidates.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No other PDF submissions to compare against.</p>
                  ) : (
                    <ul className="space-y-1">
                      {peerCandidates.map((wp) => (
                        <li key={wp.id}>
                          <label className="flex items-center gap-2 text-sm text-foreground">
                            <input
                              type="checkbox"
                              checked={selectedPeerIds.has(wp.id)}
                              onChange={() => togglePeer(wp.id)}
                            />
                            {wp.taskTitle} — {wp.title} (v{wp.version_number})
                          </label>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <div className="flex flex-wrap items-center gap-4">
                  <label className="flex items-center gap-2 text-sm text-foreground">
                    <input
                      type="checkbox"
                      checked={includeBrief}
                      disabled={!currentBrief}
                      onChange={(event) => setIncludeBrief(event.target.checked)}
                    />
                    Pin the current deal brief{currentBrief ? ` (v${currentBrief.version_number})` : " (none saved)"}
                  </label>
                  <select
                    aria-label="Workstream"
                    className="h-9 rounded-md border border-border bg-background px-2 text-sm text-foreground"
                    value={selectedWorkstreamId}
                    onChange={(event) => setSelectedWorkstreamId(event.target.value)}
                  >
                    <option value="">No workstream</option>
                    {workstreams.map((ws) => (
                      <option key={ws.id} value={ws.id}>
                        {ws.name}
                      </option>
                    ))}
                  </select>
                </div>

                <Textarea
                  placeholder="Review scope or objective for the reviewer to give the model (optional)"
                  value={reviewScope}
                  onChange={(event) => setReviewScope(event.target.value)}
                  rows={2}
                />

                <Button
                  disabled={busy || !canProposePlan}
                  onClick={() => {
                    const stageInput = buildIntegrityReviewStageInput()
                    if (!stageInput) {
                      toast.error("Select a valid submission under review.")
                      return
                    }
                    withBusy(() =>
                      proposePlan(projectId, mandateId, selectedTemplate, { review: stageInput }).then(() =>
                        resetIntegrityReviewSelection()
                      )
                    )
                  }}
                >
                  Propose plan
                </Button>
              </div>
            )}

            {isReconciliation && (
              <div className="mt-4 space-y-4">
                {documents.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    This project has no documents yet - upload PDFs and an Excel workbook on the project page first.
                  </p>
                ) : (
                  <>
                    <div>
                      <p className="mb-2 text-sm font-medium text-foreground">PDFs (select at least one)</p>
                      <ul className="space-y-1">
                        {pdfDocuments.map((doc) => (
                          <li key={doc.id}>
                            <label className="flex items-center gap-2 text-sm text-foreground">
                              <input
                                type="checkbox"
                                checked={selectedDocumentIds.has(doc.id)}
                                onChange={() => toggleDocument(doc.id)}
                              />
                              {doc.original_filename}
                            </label>
                          </li>
                        ))}
                        {pdfDocuments.length === 0 && (
                          <li className="text-sm text-muted-foreground">No PDFs in this project.</li>
                        )}
                      </ul>
                    </div>
                    <div>
                      <p className="mb-2 text-sm font-medium text-foreground">Excel workbooks (select at least one)</p>
                      <ul className="space-y-1">
                        {excelDocuments.map((doc) => (
                          <li key={doc.id}>
                            <label className="flex items-center gap-2 text-sm text-foreground">
                              <input
                                type="checkbox"
                                checked={selectedDocumentIds.has(doc.id)}
                                onChange={() => toggleDocument(doc.id)}
                              />
                              {doc.original_filename}
                            </label>
                          </li>
                        ))}
                        {excelDocuments.length === 0 && (
                          <li className="text-sm text-muted-foreground">No Excel workbooks in this project.</li>
                        )}
                      </ul>
                    </div>
                  </>
                )}
                <Button
                  disabled={busy || !canProposePlan}
                  onClick={() =>
                    withBusy(() =>
                      proposePlan(projectId, mandateId, selectedTemplate, {
                        reconcile: { document_ids: Array.from(selectedDocumentIds) },
                      }).then(() => setSelectedDocumentIds(new Set()))
                    )
                  }
                >
                  Propose plan
                </Button>
              </div>
            )}
          </Card>
        )}

        {proposedPlan && (
          <Card className="p-6">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="font-heading text-lg font-semibold text-foreground">
                Proposed plan (revision {proposedPlan.revision_number})
              </h2>
              <span className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">
                {proposedPlan.proposed_by === "llm" ? "Proposed by AI" : "Proposed manually"}
              </span>
            </div>
            {proposedPlan.planner_reasoning && (
              <p className="mt-2 text-sm text-muted-foreground">{proposedPlan.planner_reasoning}</p>
            )}
            <ul className="mt-3 space-y-2">
              {proposedPlan.stages.map((stage) => (
                <StageRow key={stage.id} stage={stage} />
              ))}
            </ul>
            <div className="mt-4 flex gap-3">
              <Button
                disabled={busy}
                onClick={() => withBusy(() => approvePlan(projectId, mandateId, proposedPlan.id).then(() => {}))}
              >
                Approve plan
              </Button>
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() => withBusy(() => rejectPlan(projectId, mandateId, proposedPlan.id).then(() => {}))}
              >
                Reject plan
              </Button>
            </div>

            {proposedPlan.proposed_by === "llm" && (
              <div className="mt-4 space-y-2 border-t border-border pt-4">
                <label htmlFor="ai-replan-feedback" className="text-sm font-medium text-foreground">
                  Request a change from the planner
                </label>
                <Textarea
                  id="ai-replan-feedback"
                  placeholder="e.g. Use the Q3 workbook instead of Q2."
                  value={aiFeedback}
                  onChange={(event) => setAiFeedback(event.target.value)}
                  rows={2}
                />
                <Button
                  variant="secondary"
                  disabled={busy || !aiFeedback.trim()}
                  onClick={() => handleProposeWithAi(aiFeedback.trim())}
                >
                  Ask planner to revise
                </Button>
                <p className="text-xs text-muted-foreground">
                  Creates a new plan revision for your approval - this one is kept, marked superseded, not
                  overwritten.
                </p>
              </div>
            )}
          </Card>
        )}

        {approvedPlan && mandate.status === "active" && !latestRun && (
          <Card className="p-6">
            <h2 className="font-heading text-lg font-semibold text-foreground">
              Approved plan (revision {approvedPlan.revision_number})
            </h2>
            <ul className="mt-3 space-y-2">
              {approvedPlan.stages.map((stage) => (
                <StageRow key={stage.id} stage={stage} />
              ))}
            </ul>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2">
                <label htmlFor="budget-limit" className="text-sm text-muted-foreground">
                  Budget limit (optional)
                </label>
                <Input
                  id="budget-limit"
                  type="number"
                  min="0"
                  step="any"
                  className="h-9 w-28"
                  value={budgetLimit}
                  onChange={(event) => setBudgetLimit(event.target.value)}
                  placeholder="Unlimited"
                />
              </div>
              <Button
                disabled={busy}
                onClick={() =>
                  withBusy(() =>
                    startRun(projectId, mandateId, budgetLimit.trim() ? Number(budgetLimit) : undefined).then(
                      () => {}
                    )
                  )
                }
              >
                Start run
              </Button>
            </div>
          </Card>
        )}

        {mandate.runs.length > 0 && (
          <Card className="p-6">
            <h2 className="font-heading text-lg font-semibold text-foreground">Runs</h2>
            <ul className="mt-3 space-y-4">
              {mandate.runs.map((run) => {
                const stageCount = mandate.plans.find((p) => p.id === run.plan_revision_id)?.stages.length
                const isNonTerminal = NON_TERMINAL_RUN_STATUSES.includes(run.status)
                return (
                  <li key={run.id} className="rounded-md border border-border p-4">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-foreground">Run {run.id.slice(0, 8)}</span>
                      <span className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">
                        {RUN_STATUS_LABELS[run.status] ?? run.status}
                      </span>
                    </div>
                    <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                      {stageCount !== undefined && (
                        <span>
                          Stage {Math.min(run.current_stage_index + 1, stageCount)} of {stageCount}
                        </span>
                      )}
                      {run.budget_limit != null && (
                        <span>
                          Budget used: {run.budget_consumed} / {run.budget_limit}
                        </span>
                      )}
                    </div>
                    <ul className="mt-3 space-y-2">
                      {run.attempts.map((attempt) => (
                        <li key={attempt.id} className="text-sm">
                          <div className="flex items-center justify-between">
                            <span className="font-medium text-foreground">{attempt.stage_id}</span>
                            <span className="text-muted-foreground">{attempt.status}</span>
                          </div>
                          {attempt.output && typeof attempt.output.integrity_review_id === "string" ? (
                            <IntegrityReviewPanel projectId={projectId} reviewId={attempt.output.integrity_review_id} />
                          ) : (
                            attempt.output && (
                              <pre className="mt-1 overflow-x-auto rounded bg-muted p-2 text-xs text-muted-foreground">
                                {JSON.stringify(attempt.output, null, 2)}
                              </pre>
                            )
                          )}
                          {attempt.error && <p className="mt-1 text-xs text-destructive">{attempt.error}</p>}
                        </li>
                      ))}
                    </ul>

                    {run.id === latestRun?.id && awaitingHumanAttempt && (
                      <div className="mt-4 space-y-2 border-t border-border pt-4">
                        <label htmlFor="decision" className="text-sm font-medium text-foreground">
                          Human decision for &ldquo;{awaitingHumanAttempt.stage_id}&rdquo;
                        </label>
                        <Textarea
                          id="decision"
                          value={decision}
                          onChange={(event) => setDecision(event.target.value)}
                          rows={2}
                        />
                        <div className="flex gap-3">
                          <Button
                            disabled={busy || !decision.trim()}
                            onClick={() =>
                              withBusy(() =>
                                resumeRun(projectId, mandateId, run.id, awaitingHumanAttempt.stage_id, decision).then(
                                  () => setDecision("")
                                )
                              )
                            }
                          >
                            Resume
                          </Button>
                          <Button
                            variant="secondary"
                            disabled={busy}
                            onClick={() => withBusy(() => cancelRun(projectId, mandateId, run.id).then(() => {}))}
                          >
                            Cancel run
                          </Button>
                        </div>
                      </div>
                    )}

                    {run.id === latestRun?.id && isNonTerminal && !awaitingHumanAttempt && (
                      <div className="mt-4 border-t border-border pt-4">
                        <Button
                          variant="secondary"
                          disabled={busy}
                          onClick={() => withBusy(() => cancelRun(projectId, mandateId, run.id).then(() => {}))}
                        >
                          Cancel run
                        </Button>
                      </div>
                    )}
                  </li>
                )
              })}
            </ul>
          </Card>
        )}
      </div>
    </>
  )
}
