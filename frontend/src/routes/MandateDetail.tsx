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
  getMandate,
  listDocuments,
  listMandateTemplates,
  NON_TERMINAL_RUN_STATUSES,
  proposePlan,
  proposePlanWithAi,
  rejectPlan,
  resumeRun,
  startRun,
  type Mandate,
  type MandateTemplate,
  type PlanProposalOutcome,
  type ProjectDocument,
} from "@/lib/api"

// Task 12.3: the only template today whose one capability stage can't
// derive its own input purely from the mandate's objective (see
// mandates.py's _default_input_for_stage) - it needs an explicit source
// selection, which nothing here has a planner to propose yet (12.4 is
// still LLM planning, out of scope). This is that selection's one hardcoded
// hook; a real multi-capability composer would generalize it, but with
// exactly one capability needing explicit input, that generalization has
// nothing yet to prove itself against.
const RECONCILIATION_TEMPLATE_KEY = "reconciliation"

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
  const reloadingRef = useRef(false)

  async function reload() {
    if (!projectId || !mandateId || reloadingRef.current) return
    reloadingRef.current = true
    try {
      const [loaded, templateList, documentList] = await Promise.all([
        getMandate(projectId, mandateId),
        listMandateTemplates(),
        listDocuments(projectId),
      ])
      setMandate(loaded)
      setTemplates(templateList)
      setDocuments(documentList)
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

  const isReconciliation = selectedTemplate === RECONCILIATION_TEMPLATE_KEY
  const pdfDocuments = documents.filter((d) => d.extension === ".pdf")
  const excelDocuments = documents.filter((d) => d.extension === ".xlsx" || d.extension === ".xls")
  const selectedPdfCount = pdfDocuments.filter((d) => selectedDocumentIds.has(d.id)).length
  const selectedExcelCount = excelDocuments.filter((d) => selectedDocumentIds.has(d.id)).length
  const reconciliationSelectionValid = selectedPdfCount >= 1 && selectedExcelCount >= 1
  const canProposePlan = isReconciliation ? reconciliationSelectionValid : Boolean(selectedTemplate)

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
              {!isReconciliation && (
                <Button
                  disabled={busy || !canProposePlan}
                  onClick={() => withBusy(() => proposePlan(projectId, mandateId, selectedTemplate).then(() => {}))}
                >
                  Propose plan
                </Button>
              )}
            </div>

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
                          {attempt.output && (
                            <pre className="mt-1 overflow-x-auto rounded bg-muted p-2 text-xs text-muted-foreground">
                              {JSON.stringify(attempt.output, null, 2)}
                            </pre>
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
