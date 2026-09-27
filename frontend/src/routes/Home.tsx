import { useGSAP } from "@gsap/react"
import gsap from "gsap"
import { FolderOpen } from "lucide-react"
import { useMemo, useRef, useState } from "react"
import { useEffect } from "react"
import { Link } from "react-router-dom"
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
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import {
  createProject,
  getWorkspaceOverview,
  listProjects,
  type MaterialChangeEvent,
  type Project,
  type WorkspaceOverview,
  type WorkspaceOverviewTask,
} from "@/lib/api"
import { MANDATE_STATUS_LABELS } from "@/lib/mandateStatus"

const TASK_STATUS_LABELS: Record<string, string> = {
  submitted: "Submitted", returned: "Returned for revision",
}

// Which of mandates.py's real MANDATE_STATUSES count as "still needs
// attention" for the Mandates summary's own headline count - the same
// distinction MandateList.tsx's own status labels already draw, applied
// across every accessible deal instead of one.
const MANDATE_ACTIVE_STATUSES = ["draft", "planning", "awaiting_approval", "active", "under_review"]

function formatDate(isoString: string) {
  return new Date(isoString).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}

function formatDateTime(isoString: string) {
  return new Date(isoString).toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  })
}

function materialChangeSummary(event: MaterialChangeEvent): string {
  switch (event.kind) {
    case "comment":
      return `${event.actor?.display_name ?? "Someone"} commented on "${event.task_title}"`
    case "submission":
      return `${event.actor?.display_name ?? "Someone"} submitted "${event.work_product_title}" v${event.version_number} for "${event.task_title}"`
    case "review_decision":
      return `${event.actor?.display_name ?? "Someone"} ${event.decision === "approved" ? "approved" : "returned"} "${event.work_product_title}"`
    case "stale_workspace":
      return `A workspace may be stale: ${event.reason}`
    default:
      return "Update"
  }
}

// Mandates summary card - real counts aggregated from engagements[].
// mandate_counts (already returned by /api/overview, no extra fetch).
// No invented category: every key that shows up here is a real
// mandates.py MANDATE_STATUSES value.
function MandatesSummaryCard({ overview }: { overview: WorkspaceOverview }) {
  const counts = useMemo(() => {
    const totals: Record<string, number> = {}
    for (const engagement of overview.engagements) {
      for (const [status, count] of Object.entries(engagement.mandate_counts)) {
        totals[status] = (totals[status] ?? 0) + count
      }
    }
    return totals
  }, [overview])

  const activeTotal = MANDATE_ACTIVE_STATUSES.reduce((sum, status) => sum + (counts[status] ?? 0), 0)
  const present = Object.keys(counts).filter((status) => counts[status] > 0)

  return (
    <Card className="p-6">
      <h2 className="font-heading text-lg font-semibold text-foreground">Mandates</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        {activeTotal > 0
          ? `${activeTotal} active across every deal you can see.`
          : "No mandate is currently active."}
      </p>
      {present.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-4">
          {present.map((status) => (
            <div key={status}>
              <div className="font-heading text-xl font-bold text-foreground">{counts[status]}</div>
              <div className="text-xs tracking-wide text-muted-foreground uppercase">
                {MANDATE_STATUS_LABELS[status] ?? status}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

function MaterialChangesCard({ events }: { events: MaterialChangeEvent[] }) {
  return (
    <Card className="p-0">
      <div className="border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold text-foreground">Material changes</h2>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Submissions, review decisions, comments and staleness across every deal you can see.
        </p>
      </div>
      {events.length === 0 ? (
        <p className="px-4 py-6 text-center text-sm text-muted-foreground">No material changes recently.</p>
      ) : (
        <div className="divide-y divide-border">
          {events.map((event, index) => (
            <Link
              key={index}
              to={
                event.kind === "stale_workspace"
                  ? `/projects/${event.project.id}/findings`
                  : `/projects/${event.project.id}/work`
              }
              className="flex items-center justify-between gap-3 px-4 py-3 text-sm hover:bg-surface-2/40"
            >
              <span className="min-w-0 flex-1 truncate text-foreground">
                {materialChangeSummary(event)} <span className="text-muted-foreground">· {event.project.name}</span>
              </span>
              <span className="shrink-0 text-xs text-muted-foreground">{formatDateTime(event.at)}</span>
            </Link>
          ))}
        </div>
      )}
    </Card>
  )
}

export function Home() {
  const [projects, setProjects] = useState<Project[] | null>(null)
  const [overview, setOverview] = useState<WorkspaceOverview | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [formError, setFormError] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const listRef = useRef<HTMLDivElement>(null)

  async function reload() {
    try {
      setProjects(await listProjects())
    } catch {
      toast.error("Could not load projects.")
      setProjects([])
    }
    try {
      setOverview(await getWorkspaceOverview())
    } catch {
      setOverview({ my_attention: [], engagements: [], material_changes: [] })
    }
  }

  useEffect(() => {
    reload()
  }, [])

  useGSAP(
    () => {
      if (!projects || projects.length === 0) return
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return
      gsap.from(".project-card", {
        opacity: 0,
        y: 8,
        duration: 0.36,
        ease: "power2.out",
        stagger: 0.045,
      })
    },
    { dependencies: [projects], scope: listRef },
  )

  function openDialog() {
    setName("")
    setDescription("")
    setFormError("")
    setDialogOpen(true)
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    const trimmedName = name.trim()
    if (!trimmedName) {
      setFormError("Project name is required.")
      return
    }

    setSubmitting(true)
    try {
      await createProject(trimmedName, description.trim())
      setDialogOpen(false)
      toast.success("Project created.")
      await reload()
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Something went wrong.")
    } finally {
      setSubmitting(false)
    }
  }

  // Quick actions' own disclosed simplification (see 17.6's task file):
  // jump to the most recently created accessible deal rather than
  // presenting a deal picker - fine at this product's current scale.
  const mostRecentProjectId = useMemo(() => {
    if (!projects || projects.length === 0) return null
    return [...projects].sort((a, b) => b.created_at.localeCompare(a.created_at))[0].id
  }, [projects])

  return (
    <>
      <div className="mx-auto max-w-3xl px-6 pt-8 pb-20 space-y-6">
        <div>
          <h1 className="font-heading text-2xl font-semibold text-foreground">Overview</h1>
          <p className="text-sm text-muted-foreground">What requires attention, and what could affect a decision.</p>
        </div>

        {overview && overview.my_attention.length > 0 && (
          <Card className="p-6">
            <h2 className="font-heading text-lg font-semibold text-foreground">My attention</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Tasks assigned to you that need a review or a revision, across every deal.
            </p>
            <ul className="mt-3 space-y-2">
              {overview.my_attention.map((task: WorkspaceOverviewTask) => (
                <li key={task.id}>
                  <Link
                    to={`/projects/${task.project.id}`}
                    className="flex items-center justify-between gap-3 rounded-md border border-border px-3 py-2 text-sm hover:border-primary"
                  >
                    <span className="text-foreground">
                      {task.title} <span className="text-muted-foreground">· {task.project.name}</span>
                    </span>
                    <span className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">
                      {TASK_STATUS_LABELS[task.status] ?? task.status}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </Card>
        )}

        {overview && <MandatesSummaryCard overview={overview} />}

        <Card className="p-6">
          <div className="flex items-center justify-between gap-3">
            <h2 className="font-heading text-lg font-semibold text-foreground">Active engagements</h2>
            <Button onClick={openDialog}>+ New deal</Button>
          </div>
          <div className="mt-3" ref={listRef}>
            {projects === null ? (
              <div className="space-y-3">
                <Skeleton className="h-16 w-full" />
                <Skeleton className="h-16 w-full" />
                <Skeleton className="h-16 w-full" />
              </div>
            ) : projects.length === 0 ? (
              <div className="flex flex-col items-center gap-3 py-6 text-center text-muted-foreground">
                <div className="rounded-full bg-muted p-3">
                  <FolderOpen className="size-5" />
                </div>
                <p className="text-sm">No deals yet.</p>
                <Button onClick={openDialog}>+ New deal</Button>
              </div>
            ) : (
              <ul className="space-y-3">
                {projects.map((project) => (
                  <li key={project.id} className="project-card">
                    <Card className="p-4 shadow-(--shadow-elevation-1) transition-all duration-200 hover:-translate-y-0.5 hover:border-primary hover:shadow-(--shadow-elevation-2)">
                      <Link to={`/projects/${project.id}`}>
                        <div className="font-heading text-base font-semibold text-foreground">
                          {project.name}
                        </div>
                        <div className="truncate text-sm text-muted-foreground">
                          {project.description || "No description"}
                        </div>
                        <div className="mt-1.5 text-xs text-muted-foreground">
                          Created {formatDate(project.created_at)}
                        </div>
                      </Link>
                      <Link
                        to={`/projects/${project.id}/mandates`}
                        className="mt-2 inline-block text-xs text-accent hover:underline"
                      >
                        Mandates →
                      </Link>
                    </Card>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Card>

        <Card className="p-6">
          <h2 className="font-heading text-lg font-semibold text-foreground">Quick actions</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button onClick={openDialog}>Create a deal</Button>
            <Button
              variant="secondary"
              disabled={!mostRecentProjectId}
              render={mostRecentProjectId ? <Link to={`/projects/${mostRecentProjectId}/mandates`} /> : undefined}
            >
              Create a mandate
            </Button>
            <Button
              variant="secondary"
              disabled={!mostRecentProjectId}
              render={mostRecentProjectId ? <Link to={`/projects/${mostRecentProjectId}/documents`} /> : undefined}
            >
              Upload evidence
            </Button>
          </div>
        </Card>

        <MaterialChangesCard events={overview?.material_changes ?? []} />
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <form onSubmit={handleSubmit}>
            <DialogHeader>
              <DialogTitle>New deal</DialogTitle>
              <DialogDescription className="sr-only">
                Create a new M&amp;A deal engagement.
              </DialogDescription>
            </DialogHeader>

            <div className="grid gap-4 py-2">
              <div className="grid gap-1.5">
                <Label htmlFor="name">Deal name</Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  maxLength={200}
                  autoFocus
                  required
                />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  maxLength={5000}
                />
              </div>
              {formError ? <p className="text-sm text-destructive">{formError}</p> : null}
            </div>

            <DialogFooter>
              <Button type="button" variant="secondary" onClick={() => setDialogOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={submitting}>
                {submitting ? "Creating…" : "Create deal"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  )
}
