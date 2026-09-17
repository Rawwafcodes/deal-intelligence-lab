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
