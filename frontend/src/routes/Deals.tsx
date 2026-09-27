import { useEffect, useMemo, useState } from "react"
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
  getSession,
  getWorkspaceOverview,
  listDealMemberships,
  type MaterialChangeEvent,
  type WorkspaceOverviewEngagement,
} from "@/lib/api"
import { MANDATE_STATUS_LABELS } from "@/lib/mandateStatus"

function formatDate(isoString: string) {
  return new Date(isoString).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })
}

const ROLE_LABELS: Record<string, string> = {
  deal_lead: "Deal lead", reviewer: "Reviewer", analyst: "Analyst", external_executive: "External executive",
}

// "Current phase or workflow state where supported" (docs/product/02):
// store.Project has no real phase/stage field at all - showing one
// would be invented. Real task/mandate exposure counts (already
// returned by /api/overview) stand in honestly instead.
function ExposureCounts({ engagement }: { engagement: WorkspaceOverviewEngagement }) {
  const needsAttention = (engagement.task_counts.submitted ?? 0) + (engagement.task_counts.returned ?? 0)
  const mandateEntries = Object.entries(engagement.mandate_counts).filter(([, count]) => count > 0)
  return (
    <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
      {needsAttention > 0 && <span>{needsAttention} task{needsAttention === 1 ? "" : "s"} needing attention</span>}
      {mandateEntries.map(([status, count]) => (
        <span key={status}>{count} {(MANDATE_STATUS_LABELS[status] ?? status).toLowerCase()} mandate{count === 1 ? "" : "s"}</span>
      ))}
      {needsAttention === 0 && mandateEntries.length === 0 && <span>No open exposure</span>}
    </div>
  )
}

export function Deals() {
  const [engagements, setEngagements] = useState<WorkspaceOverviewEngagement[] | null>(null)
  const [latestChangeByProject, setLatestChangeByProject] = useState<Record<string, MaterialChangeEvent>>({})
  const [rolesByProject, setRolesByProject] = useState<Record<string, string>>({})
  const [search, setSearch] = useState("")
  const [dialogOpen, setDialogOpen] = useState(false)
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [formError, setFormError] = useState("")
  const [submitting, setSubmitting] = useState(false)

  async function reload() {
    try {
      const overview = await getWorkspaceOverview()
      setEngagements(overview.engagements)

      const latest: Record<string, MaterialChangeEvent> = {}
      for (const event of overview.material_changes) {
        if (!latest[event.project.id] || event.at > latest[event.project.id].at) latest[event.project.id] = event
      }
      setLatestChangeByProject(latest)

      const session = await getSession()
      const roleEntries = await Promise.all(
        overview.engagements.map(async (engagement) => {
          const memberships = await listDealMemberships(engagement.project.id).catch(() => [])
          const mine = memberships.find((m) => m.user_id === session.user.id && !m.revoked_at)
          return [engagement.project.id, mine?.role ?? ""] as const
        })
      )
      setRolesByProject(Object.fromEntries(roleEntries))
    } catch {
      toast.error("Could not load deals.")
      setEngagements([])
    }
  }

  useEffect(() => {
    reload()
  }, [])

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
      setFormError("Deal name is required.")
      return
    }
    setSubmitting(true)
    try {
      await createProject(trimmedName, description.trim())
      setDialogOpen(false)
      toast.success("Deal created.")
      await reload()
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Something went wrong.")
    } finally {
      setSubmitting(false)
    }
  }

  const filtered = useMemo(() => {
    if (!engagements) return []
    const query = search.trim().toLowerCase()
    if (!query) return engagements
    return engagements.filter(
      (e) => e.project.name.toLowerCase().includes(query) || e.project.description.toLowerCase().includes(query)
    )
  }, [engagements, search])

  return (
    <>
      <div className="mx-auto max-w-3xl px-6 pt-8 pb-20 space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="font-heading text-2xl font-semibold text-foreground">Deals</h1>
            <p className="text-sm text-muted-foreground">Every engagement you have access to.</p>
          </div>
          <Button onClick={openDialog}>+ New deal</Button>
        </div>

        <Input
          placeholder="Search deals by name or description…"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          className="max-w-sm"
        />

        {engagements === null ? (
          <div className="space-y-3">
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        ) : filtered.length === 0 ? (
          <Card className="p-6 text-center text-sm text-muted-foreground">
            {engagements.length === 0 ? "No deals yet." : "No deals match this search."}
          </Card>
        ) : (
          <ul className="space-y-3">
            {filtered.map((engagement) => {
              const latest = latestChangeByProject[engagement.project.id]
              const role = rolesByProject[engagement.project.id]
              return (
                <li key={engagement.project.id}>
                  <Card className="p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <Link to={`/projects/${engagement.project.id}`} className="min-w-0 flex-1">
                        <div className="font-heading text-base font-semibold text-foreground">
                          {engagement.project.name}
                        </div>
                        <div className="truncate text-sm text-muted-foreground">
                          {engagement.project.description || "No description"}
                        </div>
                        <div className="mt-1 text-xs text-muted-foreground">
                          Created {formatDate(engagement.project.created_at)}
                        </div>
                      </Link>
                      {role && (
                        <span className="shrink-0 rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">
                          {ROLE_LABELS[role] ?? role}
                        </span>
                      )}
                    </div>
                    <div className="mt-2">
                      <ExposureCounts engagement={engagement} />
                    </div>
                    {latest && (
                      <p className="mt-2 text-xs text-muted-foreground">
                        Latest activity: {new Date(latest.at).toLocaleDateString()}
                      </p>
                    )}
                  </Card>
                </li>
              )
            })}
          </ul>
        )}
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <form onSubmit={handleSubmit}>
            <DialogHeader>
              <DialogTitle>New deal</DialogTitle>
              <DialogDescription className="sr-only">Create a new M&amp;A deal engagement.</DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-2">
              <div className="grid gap-1.5">
                <Label htmlFor="deal-name">Deal name</Label>
                <Input id="deal-name" value={name} onChange={(event) => setName(event.target.value)} maxLength={200} autoFocus required />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="deal-description">Description</Label>
                <Textarea id="deal-description" value={description} onChange={(event) => setDescription(event.target.value)} maxLength={5000} />
              </div>
              {formError ? <p className="text-sm text-destructive">{formError}</p> : null}
            </div>
            <DialogFooter>
              <Button type="button" variant="secondary" onClick={() => setDialogOpen(false)}>Cancel</Button>
              <Button type="submit" disabled={submitting}>{submitting ? "Creating…" : "Create deal"}</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  )
}
