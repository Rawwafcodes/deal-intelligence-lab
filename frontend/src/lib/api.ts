// The static pages (project.html, validation.html, ...) are served only by
// the Python backend, never by Vite's dev server - vite.config.ts proxies
// exactly `/api`, nothing else (see its own comment, and AppHeader's former
// docstring before Direction A). A plain relative link to one of those pages
// resolves against the Vite origin (5173) in dev, which has no such route,
// and just blanks the page. In dev, point explicitly at the known backend
// dev port; once/if this scaffold is ever built and served *by* that same
// backend process (not the case today - see docs/10-decisions.md O01/O02),
// window.location.origin is already correct with no cross-origin link needed.
export const BACKEND_ORIGIN = import.meta.env.DEV ? "http://127.0.0.1:8765" : window.location.origin

export interface Project {
  id: string
  name: string
  description: string
  created_at: string
}

export interface ProjectDocument {
  id: string
  project_id: string
  original_filename: string
  relative_path: string
  extension: string
  size_bytes: number
  sha256: string
  uploaded_at: string
  version_number: number
  current_version_id: string | null
}

export async function listDocuments(projectId: string): Promise<ProjectDocument[]> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/documents`)
  return jsonOrThrow(res, "Could not load documents.")
}

// Unifying the workspace frontend: a Workspace is created once per
// completed cross-format reconciliation run (or, separately, per M14.2
// Integrity Review - see `integrity_review_id` below) - a project can
// have several. `workspaces.py`'s own GET .../workspaces/<id> bundle
// (findings + summary) is reconciliation-only today (server.py's
// `_get_workspace_analysis` 400s for an integrity-review-backed
// workspace) - `cross_format_analysis_id` tells the caller which kind
// it is before fetching, rather than discovering it from a failed request.
export interface Workspace {
  id: string
  project_id: string
  cross_format_analysis_id: string | null
  integrity_review_id: string | null
  created_at: string
  updated_at: string
}

export async function listWorkspaces(projectId: string): Promise<Workspace[]> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/workspaces`)
  return jsonOrThrow(res, "Could not load workspaces.")
}

// Matches workspaces.py's `_merged_finding` dict shape exactly (that
// function has no fixed dataclass on the backend - findings are plain
// dicts merging an immutable AI/integrity/human content snapshot with
// mutable workflow-state fields).
export interface Finding {
  id: string
  workspace_id: string
  origin: "ai" | "integrity" | "human"
  title: string
  classification: string
  severity: string
  effective_severity: string | null
  explanation: string
  pdf_evidence: string
  workbook_evidence: string
  commercial_relevance: string
  uncertainty: string
  recommended_action: string
  raw_text: string
  pdf_citations: PdfCitation[]
  excel_citations: ExcelCitation[]
  evidence_notes: string
  evidence_document_ids: string[]
  review_status: string
  adjusted_severity: string | null
  resolution_status: string
  assigned_owner: string
  management_response: string
  reviewer_notes: string
  due_date_text: string
  is_duplicate: boolean
  duplicate_of: string | null
  duplicate_marked_by: string | null
  duplicate_marked_at: string | null
  duplicate_finding_ids: string[]
  created_at: string
  updated_at: string
  revision: number
}

export interface FindingsSummary {
  total_findings: number
  by_severity: Record<string, number>
}

export interface WorkspaceBundle {
  workspace: Workspace
  analysis: Record<string, unknown>
  findings: Finding[]
  summary: FindingsSummary
  staleness: { reason: string } | null
}

export async function getWorkspaceBundle(projectId: string, workspaceId: string): Promise<WorkspaceBundle> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/workspaces/${encodeURIComponent(workspaceId)}`
  )
  return jsonOrThrow(res, "Could not load this workspace's findings.")
}

export interface IdentityUser {
  id: string
  email: string
  display_name: string
  created_at: string
}

export interface OrganizationMembership {
  organization: { id: string; name: string; created_at: string }
  role: string
}

export interface Session {
  user: IdentityUser
  organizations: OrganizationMembership[]
}

export interface DevIdentity {
  user: IdentityUser
  organizations: OrganizationMembership[]
}

export async function getSession(): Promise<Session> {
  const res = await fetch("/api/session")
  if (!res.ok) throw new Error("Could not load the current session.")
  return res.json()
}

export async function listDevIdentities(): Promise<DevIdentity[]> {
  const res = await fetch("/api/dev/identities")
  if (!res.ok) throw new Error("Dev identity switching is not available.")
  return res.json()
}

export async function switchIdentity(userId: string): Promise<Session> {
  const res = await fetch("/api/dev/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || "Could not switch identity.")
  }
  return res.json()
}

export async function listProjects(): Promise<Project[]> {
  const res = await fetch("/api/projects")
  if (!res.ok) throw new Error("Could not load projects.")
  return res.json()
}

export async function createProject(name: string, description: string): Promise<Project> {
  const res = await fetch("/api/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || "Something went wrong creating the project.")
  }
  return res.json()
}

// Task 12.1: mandate/template/plan/run/attempt contracts, proven with a
// deterministic fixture planner and one fixture-only capability - see
// mandates.py's own module docstring for exactly what this does and does
// not cover yet (no real analytical capability, no AI call, no durable
// async worker).
export interface MandateTemplate {
  key: string
  version: number
  name: string
  description: string
  stages: MandateStage[]
}

export interface MandateStage {
  id: string
  kind?: "capability" | "human_checkpoint"
  capability?: string
  depends_on: string[]
  outputs?: string[]
  input?: Record<string, unknown>
}

export interface MandatePlan {
  id: string
  mandate_id: string
  revision_number: number
  status: "proposed" | "approved" | "rejected" | "superseded"
  template_key: string | null
  stages: MandateStage[]
  created_at: string
  approved_at: string | null
  approved_by: string | null
  // Task 12.4: which planner produced this revision, and (for "llm") its
  // own stated rationale - shown to the human approver, never used to skip
  // or shortcut the approval gate itself.
  proposed_by: "human" | "llm"
  planner_reasoning: string | null
}

// Task 12.4: the outcome of asking a real model to propose a plan.
// "proposed" - `plan` is a real PlanRevision, exactly as unapproved as a
// manually-proposed one. "unsupported" - the model itself wasn't confident,
// or this app's own independent checks rejected its candidate (a
// hallucinated/cross-project document id, an invalid PDF/Excel mix, an
// unregistered template) - no plan was created; `reason` says why.
export interface PlanProposalOutcome {
  status: "proposed" | "unsupported"
  plan: MandatePlan | null
  reasoning: string | null
  reason: string | null
}

export interface MandateAttempt {
  id: string
  run_id: string
  stage_id: string
  capability: string | null
  status: "succeeded" | "failed" | "awaiting_human" | "running"
  started_at: string
  finished_at: string | null
  output: Record<string, unknown> | null
  error: string | null
}

// Task 12.2: a run is now "queued" and "cancel_requested" too (durable
// local worker), and "outcome_unknown" is reachable if the worker process
// was interrupted mid-attempt and could not confirm what happened - see
// mandates.py's Worker.recover(). A run in any of these non-terminal
// statuses ("queued", "running", "cancel_requested") is still being
// processed by the worker in the background - see MandateDetail.tsx's polling.
export type MandateRunStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "interrupted"
  | "outcome_unknown"
  | "cancel_requested"
  | "cancelled"
  | "waiting_for_input"

export interface MandateRun {
  id: string
  mandate_id: string
  plan_revision_id: string
  status: MandateRunStatus
  queued_at: string | null
  started_at: string | null
  finished_at: string | null
  current_stage_index: number
  budget_limit: number | null
  budget_consumed: number
  attempts: MandateAttempt[]
}

export const NON_TERMINAL_RUN_STATUSES: readonly MandateRunStatus[] = ["queued", "running", "cancel_requested"]

export interface Mandate {
  id: string
  project_id: string
  objective: string
  status: string
  current_plan_id: string | null
  created_at: string
  updated_at: string
  created_by: string | null
  plans: MandatePlan[]
  runs: MandateRun[]
}

async function jsonOrThrow<T>(res: Response, fallback: string): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || fallback)
  }
  return res.json()
}

export async function listMandateTemplates(): Promise<MandateTemplate[]> {
  const res = await fetch("/api/mandate-templates")
  return jsonOrThrow(res, "Could not load mandate templates.")
}

export async function listMandates(projectId: string): Promise<Mandate[]> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/mandates`)
  return jsonOrThrow(res, "Could not load mandates.")
}

export async function getMandate(projectId: string, mandateId: string): Promise<Mandate> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/mandates/${encodeURIComponent(mandateId)}`)
  return jsonOrThrow(res, "Could not load the mandate.")
}

export async function createMandate(projectId: string, objective: string): Promise<Mandate> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/mandates`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ objective }),
  })
  return jsonOrThrow(res, "Could not create the mandate.")
}

export async function proposePlan(
  projectId: string, mandateId: string, templateKey: string, stageInputs?: Record<string, Record<string, unknown>>
): Promise<MandatePlan> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/mandates/${encodeURIComponent(mandateId)}/plan`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ template_key: templateKey, stage_inputs: stageInputs }),
    }
  )
  return jsonOrThrow(res, "Could not propose a plan.")
}

// Task 12.4: asks a real model to propose which template/capability to use
// and (for a capability that needs one) which real documents to select -
// instead of a human hand-picking both. `feedback`: an optional requested
// change to a prior proposal (docs/04: "AI can request adaptation") -
// always produces a brand new plan revision, never edits the old one.
// Status is 200 for "unsupported" (an honest planning judgment, not an
// error) and 201 for a created plan; jsonOrThrow only throws on a real
// provider-error response (502), where the server always includes `error`.
export async function proposePlanWithAi(
  projectId: string, mandateId: string, feedback?: string
): Promise<PlanProposalOutcome> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/mandates/${encodeURIComponent(mandateId)}/plan/propose-ai`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(feedback ? { feedback } : {}),
    }
  )
  return jsonOrThrow(res, "The planner could not propose a plan.")
}

export async function approvePlan(projectId: string, mandateId: string, planId: string): Promise<MandatePlan> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/mandates/${encodeURIComponent(mandateId)}/plan/approve`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ plan_id: planId }) }
  )
  return jsonOrThrow(res, "Could not approve the plan.")
}

export async function rejectPlan(projectId: string, mandateId: string, planId: string): Promise<MandatePlan> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/mandates/${encodeURIComponent(mandateId)}/plan/reject`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ plan_id: planId }) }
  )
  return jsonOrThrow(res, "Could not reject the plan.")
}

export async function startRun(projectId: string, mandateId: string, budgetLimit?: number): Promise<MandateRun> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/mandates/${encodeURIComponent(mandateId)}/runs`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(budgetLimit != null ? { budget_limit: budgetLimit } : {}),
    }
  )
  return jsonOrThrow(res, "Could not start a run.")
}

export async function getRun(projectId: string, mandateId: string, runId: string): Promise<MandateRun> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/mandates/${encodeURIComponent(mandateId)}/runs/${encodeURIComponent(runId)}`
  )
  return jsonOrThrow(res, "Could not load the run.")
}

export async function resumeRun(
  projectId: string, mandateId: string, runId: string, stageId: string, decision: string
): Promise<MandateRun> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/mandates/${encodeURIComponent(mandateId)}/runs/${encodeURIComponent(runId)}/resume`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ stage_id: stageId, decision }) }
  )
  return jsonOrThrow(res, "Could not resume the run.")
}

export async function cancelRun(projectId: string, mandateId: string, runId: string): Promise<MandateRun> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/mandates/${encodeURIComponent(mandateId)}/runs/${encodeURIComponent(runId)}/cancel`,
    { method: "POST" }
  )
  return jsonOrThrow(res, "Could not cancel the run.")
}

// Task 14.2: Work-product Integrity Review's own selection data (target/
// peer submissions and their real, immutable versions; workstreams; the
// current brief) - the exact "make exact version selection visible"
// inputs the mandate composer needs for this one capability.

export interface WorkProductVersionSummary {
  id: string
  version_number: number
  uploaded_at: string
}

export interface WorkProductSummary {
  id: string
  task_id: string
  title: string
  extension: string
  version_number: number
  current_version_id: string | null
  versions: WorkProductVersionSummary[]
}

export interface TaskWithWorkProducts {
  id: string
  title: string
  work_products: WorkProductSummary[]
}

export async function listTasksWithWorkProducts(projectId: string): Promise<TaskWithWorkProducts[]> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/tasks`)
  return jsonOrThrow(res, "Could not load tasks.")
}

export interface WorkstreamSummary {
  id: string
  name: string
}

export async function listWorkstreams(projectId: string): Promise<WorkstreamSummary[]> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/workstreams`)
  return jsonOrThrow(res, "Could not load workstreams.")
}

export interface CurrentBriefVersion {
  id: string
  version_number: number
  objective: string
}

export async function getCurrentBriefVersion(projectId: string): Promise<CurrentBriefVersion | null> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/brief`)
  return jsonOrThrow(res, "Could not load the deal brief.")
}

// Task 14.2: Integrity Review candidates - never a shared finding until
// an explicit human decision (see integrity_reviews.py's own module
// docstring); this is the one and only path that publishes one.

// Task 16.6: matches cross_format_analysis.py's PdfCitation.to_dict()/
// ExcelCitation.to_dict() exactly - this data has always come back from
// the API (IntegrityReviewCandidate.to_dict() includes it), but no
// frontend type or rendering existed for it until this task.
export interface PdfCitation {
  cited_text: string
  document_id: string | null
  document_title: string | null
  start_page: number
  end_page: number
}

export interface ExcelCitation {
  workbook_label: string
  document_id: string | null
  document_filename: string | null
  sheet: string
  ref: string
  kind: "value" | "formula" | "label"
  exists: boolean | null
}

export interface IntegrityCandidate {
  id: string
  integrity_review_id: string
  candidate_index: number
  title: string
  classification: string
  severity: string
  assertion: string
  conflicting_or_missing_evidence: string
  why_it_matters: string
  uncertainty: string
  recommended_resolution: string
  deterministic_or_judgment: string
  raw_text: string
  pdf_citations: PdfCitation[]
  excel_citations: ExcelCitation[]
  decision: "pending" | "accepted" | "rejected" | "duplicate" | "unresolved"
  decision_notes: string
  decided_by: string | null
  decided_at: string | null
  duplicate_of_finding_id: string | null
  published_finding_id: string | null
  edits: Record<string, string> | null
}

export interface PublishedIntegrityFinding {
  id: string
  origin: string
  title: string
  classification: string
  severity: string | null
  effective_severity: string | null
  assertion: string
  conflicting_or_missing_evidence: string
  recommended_resolution: string
  lineage: Record<string, unknown>
}

export interface IntegrityReview {
  id: string
  project_id: string
  target_work_product_id: string
  target_version_id: string
  source_document_ids: string[]
  // Task 16.6: were already returned by the API (IntegrityReview.to_dict())
  // but never typed here, since nothing previously needed to resolve a
  // citation's document_id back to the exact version actually reviewed.
  source_version_ids: string[]
  peer_work_product_ids: string[]
  peer_version_ids: string[]
  brief_version_id: string | null
  workstream_id: string | null
  review_scope: string
  status: "success" | "error"
  model: string
  error_message: string | null
  materials_reviewed_text: string | null
  candidates: IntegrityCandidate[]
  workspace_id: string | null
  published_findings: PublishedIntegrityFinding[]
}

export async function getIntegrityReview(projectId: string, reviewId: string): Promise<IntegrityReview> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/integrity-reviews/${encodeURIComponent(reviewId)}`
  )
  return jsonOrThrow(res, "Could not load the integrity review.")
}

// Task 16.6 (M16.6 "Inline assistance decision" - attach challenges to
// immutable submission spans first, before considering a live editor):
// resolves one candidate's PDF citation back to a real download URL,
// pinned to the EXACT version actually reviewed (never "whatever is
// current now" - the version that changed the underlying content is
// exactly what Task 15.1's staleness mechanism already tracks
// separately) with a `#page=N` fragment so a reviewer's own PDF viewer
// opens directly on the cited page. Pure function, no fetch - easy to
// unit-test and to reuse from anywhere a citation might be rendered.
export function buildPdfCitationHref(
  projectId: string, review: IntegrityReview, citation: PdfCitation
): string | null {
  if (!citation.document_id) return null
  const page = citation.start_page
  const encodedProject = encodeURIComponent(projectId)

  if (citation.document_id === review.target_work_product_id) {
    return (
      `/api/projects/${encodedProject}/work-products/${encodeURIComponent(review.target_work_product_id)}` +
      `/versions/${encodeURIComponent(review.target_version_id)}/download?inline=1#page=${page}`
    )
  }

  const peerIndex = review.peer_work_product_ids.indexOf(citation.document_id)
  if (peerIndex !== -1 && review.peer_version_ids[peerIndex]) {
    return (
      `/api/projects/${encodedProject}/work-products/${encodeURIComponent(citation.document_id)}` +
      `/versions/${encodeURIComponent(review.peer_version_ids[peerIndex])}/download?inline=1#page=${page}`
    )
  }

  const sourceIndex = review.source_document_ids.indexOf(citation.document_id)
  if (sourceIndex !== -1 && review.source_version_ids[sourceIndex]) {
    return (
      `/api/projects/${encodedProject}/documents/${encodeURIComponent(citation.document_id)}` +
      `/versions/${encodeURIComponent(review.source_version_ids[sourceIndex])}/download?inline=1#page=${page}`
    )
  }

  // Unrecognized document_id (shouldn't happen for a real review, but a
  // stale/edited record is possible) - fall back to the plain,
  // current-version document download rather than producing a broken link.
  return `/api/projects/${encodedProject}/documents/${encodeURIComponent(citation.document_id)}/download?inline=1#page=${page}`
}

export interface IntegrityCandidateDecisionPayload {
  decision: "accepted" | "rejected" | "duplicate" | "unresolved"
  decision_notes?: string
  edits?: Partial<Record<"title" | "classification" | "severity" | "why_it_matters", string>>
  duplicate_of_finding_id?: string
}

export async function decideIntegrityCandidate(
  projectId: string, reviewId: string, candidateId: string, payload: IntegrityCandidateDecisionPayload
): Promise<IntegrityCandidate> {
  const res = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/integrity-reviews/${encodeURIComponent(reviewId)}` +
      `/candidates/${encodeURIComponent(candidateId)}/decision`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }
  )
  return jsonOrThrow(res, "Could not record that decision.")
}

// Task 13.3: Workspace/Deal Overview - every number here is a real count
// of real records (docs/05-experience.md: "Counts derive from real
// records with visible filters. No invented percent-health metrics.").

export interface TaskSummary {
  id: string
  project_id: string
  title: string
  description: string
  workstream_id: string | null
  assigned_to: string | null
  assigned_user: IdentityUser | null
  workstream: { id: string; name: string } | null
  created_by: string | null
  status: string
  created_at: string
  updated_at: string
  comments: unknown[]
  work_products: unknown[]
}

export interface ActivityEvent {
  kind: "comment" | "submission" | "review_decision"
  at: string
  task_id: string
  task_title: string
  work_product_title?: string
  version_number?: number
  decision?: "approved" | "returned"
  actor: IdentityUser | null
  summary: string | null
}

export interface FindingsSummary {
  total: number
  by_severity: Record<string, number>
  open_by_severity: Record<string, number>
}

export interface DealOverview {
  project: Project
  restricted?: false
  brief: Record<string, unknown> | null
  workstreams: unknown[]
  tasks: { counts: Record<string, number>; needs_attention: TaskSummary[] }
  mandates: { counts: Record<string, number>; recent: Mandate[] }
  reconciliations: { count: number; findings: FindingsSummary }
  documents: { count: number }
  activity: ActivityEvent[]
}

// Task 13.4 / docs/05-experience.md: "External executive view exposes
// approved shared materials only by default" - a deliberately much
// smaller payload for the external_executive deal role, with no tasks,
// comments, mandates, activity feed, or reconciliation/finding detail.
export interface ApprovedDeliverable {
  task_title: string
  work_product: { id: string; title: string; version_number: number } & Record<string, unknown>
  approved_at: string | null
}

export interface RestrictedDealOverview {
  project: Project
  restricted: true
  brief: Record<string, unknown> | null
  approved_deliverables: ApprovedDeliverable[]
}

export async function getDealOverview(projectId: string): Promise<DealOverview | RestrictedDealOverview> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/overview`)
  return jsonOrThrow(res, "Could not load the deal overview.")
}

export interface WorkspaceOverviewEngagement {
  project: Project
  task_counts: Record<string, number>
  mandate_counts: Record<string, number>
}

export interface WorkspaceOverviewTask extends TaskSummary {
  project: Project
}

export interface WorkspaceOverview {
  my_attention: WorkspaceOverviewTask[]
  engagements: WorkspaceOverviewEngagement[]
}

export async function getWorkspaceOverview(): Promise<WorkspaceOverview> {
  const res = await fetch("/api/overview")
  return jsonOrThrow(res, "Could not load the workspace overview.")
}
