import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
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
import { Textarea } from "@/components/ui/textarea"
import { createMandate, listMandates, type Mandate } from "@/lib/api"

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

export function MandateList() {
  const { projectId } = useParams<{ projectId: string }>()
  const [mandates, setMandates] = useState<Mandate[] | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [objective, setObjective] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState("")

  async function reload() {
    if (!projectId) return
    try {
      setMandates(await listMandates(projectId))
    } catch {
      toast.error("Could not load mandates.")
      setMandates([])
    }
  }

  useEffect(() => {
    reload()
  }, [projectId])

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (!projectId) return
    const trimmed = objective.trim()
    if (!trimmed) {
      setFormError("An objective is required.")
      return
    }
    setSubmitting(true)
    try {
      await createMandate(projectId, trimmed)
      setDialogOpen(false)
      setObjective("")
      setFormError("")
      toast.success("Mandate created.")
      await reload()
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Something went wrong.")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <div className="mx-auto max-w-3xl px-6 pt-8 pb-20">
        <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="font-heading text-2xl font-semibold text-foreground">Mandates</h1>
            <p className="text-sm text-muted-foreground">
              What do you need accomplished? Commission a mandate, then propose and approve a plan
              before it runs.
            </p>
          </div>
          <Button onClick={() => setDialogOpen(true)}>+ New mandate</Button>
        </div>

        <Card className="p-6">
          {mandates === null ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : mandates.length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-6 text-center text-muted-foreground">
              <p className="text-sm">No mandates yet for this project.</p>
              <Button onClick={() => setDialogOpen(true)}>+ New mandate</Button>
            </div>
          ) : (
            <ul className="space-y-3">
              {mandates.map((mandate) => (
                <li key={mandate.id}>
                  <Link to={`/projects/${projectId}/mandates/${mandate.id}`}>
                    <Card className="p-4 transition-all duration-200 hover:-translate-y-0.5 hover:border-primary">
                      <div className="flex items-start justify-between gap-3">
                        <div className="font-heading text-base font-semibold text-foreground">
                          {mandate.objective}
                        </div>
                        <span className="whitespace-nowrap rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">
                          {STATUS_LABELS[mandate.status] ?? mandate.status}
                        </span>
                      </div>
                    </Card>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <form onSubmit={handleSubmit}>
            <DialogHeader>
              <DialogTitle>New mandate</DialogTitle>
              <DialogDescription className="sr-only">
                Describe what you need accomplished for this deal.
              </DialogDescription>
            </DialogHeader>

            <div className="grid gap-4 py-2">
              <div className="grid gap-1.5">
                <label htmlFor="objective" className="text-sm font-medium text-foreground">
                  What do you need accomplished?
                </label>
                <Textarea
                  id="objective"
                  value={objective}
                  onChange={(event) => setObjective(event.target.value)}
                  autoFocus
                  required
                  rows={3}
                />
              </div>
              {formError ? <p className="text-sm text-destructive">{formError}</p> : null}
            </div>

            <DialogFooter>
              <Button type="button" variant="secondary" onClick={() => setDialogOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={submitting}>
                {submitting ? "Creating…" : "Create mandate"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  )
}
