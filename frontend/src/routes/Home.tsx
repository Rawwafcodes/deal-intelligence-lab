import { useGSAP } from "@gsap/react"
import gsap from "gsap"
import { FolderOpen } from "lucide-react"
import { useRef, useState } from "react"
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
import { createProject, getWorkspaceOverview, listProjects, type Project, type WorkspaceOverviewTask } from "@/lib/api"

const TASK_STATUS_LABELS: Record<string, string> = {
  submitted: "Submitted", returned: "Returned for revision",
}

function formatDate(isoString: string) {
  return new Date(isoString).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}

export function Home() {
  const [projects, setProjects] = useState<Project[] | null>(null)
  const [myAttention, setMyAttention] = useState<WorkspaceOverviewTask[] | null>(null)
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
    // Task 13.3: a "simple overview shell" (docs/08-roadmap.md's own
    // allowance) - failing quietly here just means the attention section
    // stays hidden, since the project list above is the page's own
    // primary content and shouldn't be blocked by this.
    try {
      const overview = await getWorkspaceOverview()
      setMyAttention(overview.my_attention)
    } catch {
      setMyAttention([])
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

  return (
    <>
      <div className="mx-auto max-w-3xl px-6 pt-8 pb-20">
        <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="font-heading text-2xl font-semibold text-foreground">Projects</h1>
            <p className="text-sm text-muted-foreground">
              Your M&amp;A transaction projects, stored locally on this computer.
            </p>
          </div>
          <Button onClick={openDialog}>+ New project</Button>
        </div>

        {myAttention && myAttention.length > 0 && (
          <Card className="mb-6 p-6">
            <h2 className="font-heading text-lg font-semibold text-foreground">My attention</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Tasks assigned to you that need a review or a revision, across every deal.
            </p>
            <ul className="mt-3 space-y-2">
              {myAttention.map((task) => (
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

        <Card className="p-6" ref={listRef}>
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
              <p className="text-sm">No projects yet.</p>
              <Button onClick={openDialog}>+ New project</Button>
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
        </Card>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <form onSubmit={handleSubmit}>
            <DialogHeader>
              <DialogTitle>New project</DialogTitle>
              <DialogDescription className="sr-only">
                Create a new M&amp;A deal project.
              </DialogDescription>
            </DialogHeader>

            <div className="grid gap-4 py-2">
              <div className="grid gap-1.5">
                <Label htmlFor="name">Project name</Label>
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
                {submitting ? "Creating…" : "Create project"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  )
}
