import { useEffect, useState } from "react"
import { ChevronDownIcon, ChevronRightIcon, PlusIcon } from "lucide-react"
import { useParams } from "react-router-dom"
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
import { Textarea } from "@/components/ui/textarea"
import {
  addTaskComment,
  addWorkProductVersion,
  assignTask,
  createTask,
  createWorkstream,
  listDetailedWorkstreams,
  listDevIdentities,
  listTasks,
  reviewWorkProduct,
  submitWorkProduct,
  updateTaskStatus,
  workProductDownloadUrl,
  type DevIdentity,
  type TaskDetail,
  type WorkProductSummary,
  type Workstream,
} from "@/lib/api"

const STATUS_LABELS: Record<string, string> = {
  open: "Open",
  in_progress: "In progress",
  submitted: "Submitted",
  returned: "Returned for revision",
  approved: "Approved",
  cancelled: "Cancelled",
}

interface NewTaskDialogProps {
  projectId: string
  workstreams: Workstream[]
  identities: DevIdentity[]
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: () => void
}

function NewTaskDialog({ projectId, workstreams, identities, open, onOpenChange, onCreated }: NewTaskDialogProps) {
  const [title, setTitle] = useState("")
  const [description, setDescription] = useState("")
  const [workstreamId, setWorkstreamId] = useState("")
  const [assignedTo, setAssignedTo] = useState("")
  const [saving, setSaving] = useState(false)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setSaving(true)
    try {
      await createTask(projectId, {
        title,
        description,
        workstream_id: workstreamId || null,
        assigned_to: assignedTo || null,
      })
      setTitle("")
      setDescription("")
      setWorkstreamId("")
      setAssignedTo("")
      onOpenChange(false)
      onCreated()
      toast.success("Task created.")
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not create the task.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={submit}>
          <DialogHeader>
            <DialogTitle>New task</DialogTitle>
            <DialogDescription>Assign a human work item inside this deal.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <label className="grid gap-1.5 text-sm font-medium">Title
              <Input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={200} required />
            </label>
            <label className="grid gap-1.5 text-sm font-medium">Description
              <Textarea value={description} onChange={(event) => setDescription(event.target.value)} rows={3} maxLength={4000} />
            </label>
            <label className="grid gap-1.5 text-sm font-medium">Workstream
              <select className="h-9 rounded-md border border-border bg-background px-2 text-sm" value={workstreamId} onChange={(event) => setWorkstreamId(event.target.value)}>
                <option value="">No workstream</option>
                {workstreams.map((workstream) => <option key={workstream.id} value={workstream.id}>{workstream.name}</option>)}
              </select>
            </label>
            <label className="grid gap-1.5 text-sm font-medium">Assignee
              <select className="h-9 rounded-md border border-border bg-background px-2 text-sm" value={assignedTo} onChange={(event) => setAssignedTo(event.target.value)}>
                <option value="">Unassigned</option>
                {identities.map((identity) => <option key={identity.user.id} value={identity.user.id}>{identity.user.display_name}</option>)}
              </select>
            </label>
          </div>
          <DialogFooter>
            <Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={saving}>{saving ? "Creating…" : "Create task"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

interface TaskCardProps {
  projectId: string
  task: TaskDetail
  identities: DevIdentity[]
  onChanged: () => void
}

interface WorkProductItemProps {
  projectId: string
  task: TaskDetail
  workProduct: WorkProductSummary
  busy: boolean
  mutate: (action: () => Promise<unknown>, success?: string) => Promise<boolean>
}

function WorkProductItem({ projectId, task, workProduct, busy, mutate }: WorkProductItemProps) {
  const [rationale, setRationale] = useState("")
  const currentVersionId = workProduct.current_version_id

  return (
    <li className="rounded-md border border-border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-medium text-foreground">{workProduct.title}</p>
          <p className="text-xs text-muted-foreground">
            Version {workProduct.version_number}{workProduct.current_version_approved ? " · Approved" : ""}
          </p>
        </div>
        {currentVersionId ? (
          <Button
            size="sm"
            variant="ghost"
            render={<a href={workProductDownloadUrl(projectId, workProduct.id, currentVersionId)} />}
          >
            Download
          </Button>
        ) : null}
      </div>

      <form
        className="mt-3 flex flex-wrap items-center gap-2"
        onSubmit={async (event) => {
          event.preventDefault()
          const form = new FormData(event.currentTarget)
          const file = form.get("file")
          if (!(file instanceof File) || file.size === 0) return
          const succeeded = await mutate(
            () => addWorkProductVersion(projectId, workProduct.id, file),
            "New work-product version submitted.",
          )
          if (succeeded) event.currentTarget.reset()
        }}
      >
        <input className="min-w-0 flex-1 text-xs" type="file" name="file" aria-label={`New version of ${workProduct.title}`} required />
        <Button size="sm" type="submit" variant="secondary" disabled={busy}>Add version</Button>
      </form>

      {task.status === "submitted" ? (
        <div className="mt-3 grid gap-2 border-t border-border pt-3">
          <Textarea
            value={rationale}
            onChange={(event) => setRationale(event.target.value)}
            placeholder="Review rationale (required when returning)"
            aria-label={`Review rationale for ${workProduct.title}`}
            rows={2}
          />
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              disabled={busy}
              onClick={() => mutate(
                () => reviewWorkProduct(projectId, workProduct.id, "approved", rationale),
                "Work product approved.",
              )}
            >
              Approve
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={busy || !rationale.trim()}
              onClick={() => mutate(
                () => reviewWorkProduct(projectId, workProduct.id, "returned", rationale),
                "Work product returned for revision.",
              )}
            >
              Return for revision
            </Button>
          </div>
        </div>
      ) : null}
    </li>
  )
}

function TaskCard({ projectId, task, identities, onChanged }: TaskCardProps) {
  const [expanded, setExpanded] = useState(false)
  const [comment, setComment] = useState("")
  const [busy, setBusy] = useState(false)

  async function mutate(action: () => Promise<unknown>, success?: string): Promise<boolean> {
    setBusy(true)
    try {
      await action()
      if (success) toast.success(success)
      onChanged()
      return true
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not update the task.")
      return false
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="overflow-hidden p-0">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-4 p-4 text-left hover:bg-muted/40"
        aria-expanded={expanded}
        onClick={() => setExpanded((value) => !value)}
      >
        <span className="flex min-w-0 items-center gap-2">
          {expanded ? <ChevronDownIcon className="size-4 shrink-0" /> : <ChevronRightIcon className="size-4 shrink-0" />}
          <span className="truncate font-medium text-foreground">{task.title}</span>
        </span>
        <span className="shrink-0 rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">
          {STATUS_LABELS[task.status] ?? task.status}
        </span>
      </button>

      {expanded ? (
        <div className="grid gap-4 border-t border-border p-4">
          {task.description ? <p className="text-sm text-muted-foreground">{task.description}</p> : null}
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="grid gap-1 text-xs font-medium text-muted-foreground">Status
              <select
                className="h-9 rounded-md border border-border bg-background px-2 text-sm text-foreground"
                value={task.status}
                disabled={busy || ["submitted", "returned", "approved"].includes(task.status)}
                onChange={(event) => mutate(() => updateTaskStatus(projectId, task.id, event.target.value))}
              >
                <option value="open">Open</option>
                <option value="in_progress">In progress</option>
                <option value="cancelled">Cancelled</option>
                {["submitted", "returned", "approved"].includes(task.status) ? (
                  <option value={task.status}>{STATUS_LABELS[task.status]}</option>
                ) : null}
              </select>
            </label>
            <label className="grid gap-1 text-xs font-medium text-muted-foreground">Assignee
              <select
                className="h-9 rounded-md border border-border bg-background px-2 text-sm text-foreground"
                value={task.assigned_to ?? ""}
                disabled={busy}
                onChange={(event) => mutate(() => assignTask(projectId, task.id, event.target.value || null))}
              >
                <option value="">Unassigned</option>
                {identities.map((identity) => <option key={identity.user.id} value={identity.user.id}>{identity.user.display_name}</option>)}
              </select>
            </label>
          </div>

          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">Conversation</p>
            {task.comments.length === 0 ? (
              <p className="text-sm text-muted-foreground">No comments yet.</p>
            ) : (
              <ul className="space-y-2">
                {task.comments.map((item) => (
                  <li key={item.id} className="rounded-md bg-muted/40 px-3 py-2 text-sm">
                    <p className="text-xs text-muted-foreground">{item.author?.display_name ?? "Unknown identity"}</p>
                    <p className="mt-1 text-foreground">{item.body}</p>
                  </li>
                ))}
              </ul>
            )}
            <form
              className="mt-3 flex gap-2"
              onSubmit={(event) => {
                event.preventDefault()
                const body = comment.trim()
                if (!body) return
                mutate(() => addTaskComment(projectId, task.id, body), "Comment added.").then((succeeded) => {
                  if (succeeded) setComment("")
                })
              }}
            >
              <Input aria-label={`Comment on ${task.title}`} value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Add a comment" maxLength={4000} />
              <Button type="submit" variant="secondary" disabled={busy || !comment.trim()}>Add</Button>
            </form>
          </div>

          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">Work products</p>
            {task.work_products.length > 0 ? (
              <ul className="space-y-2">
                {task.work_products.map((workProduct) => (
                  <WorkProductItem
                    key={workProduct.id}
                    projectId={projectId}
                    task={task}
                    workProduct={workProduct}
                    busy={busy}
                    mutate={mutate}
                  />
                ))}
              </ul>
            ) : <p className="text-sm text-muted-foreground">No work products submitted.</p>}
            <form
              className="mt-3 grid gap-2 rounded-md bg-muted/30 p-3 sm:grid-cols-[1fr_1fr_auto]"
              onSubmit={async (event) => {
                event.preventDefault()
                const form = new FormData(event.currentTarget)
                const file = form.get("file")
                const title = String(form.get("title") ?? "").trim()
                if (!(file instanceof File) || file.size === 0 || !title) return
                const succeeded = await mutate(
                  () => submitWorkProduct(projectId, task.id, title, file),
                  "Work product submitted for review.",
                )
                if (succeeded) event.currentTarget.reset()
              }}
            >
              <Input name="title" placeholder="Work-product title" aria-label={`Work-product title for ${task.title}`} required />
              <input className="min-w-0 text-xs" type="file" name="file" aria-label={`Submit a work product for ${task.title}`} required />
              <Button size="sm" type="submit" variant="secondary" disabled={busy}>Submit</Button>
            </form>
          </div>

          {task.workstream ? <p className="text-xs text-muted-foreground">Workstream: {task.workstream.name}</p> : null}
        </div>
      ) : null}
    </Card>
  )
}

export function Work() {
  const { projectId } = useParams<{ projectId: string }>()
  const [tasks, setTasks] = useState<TaskDetail[] | null>(null)
  const [workstreams, setWorkstreams] = useState<Workstream[]>([])
  const [identities, setIdentities] = useState<DevIdentity[]>([])
  const [taskDialogOpen, setTaskDialogOpen] = useState(false)
  const [workstreamName, setWorkstreamName] = useState("")
  const [workstreamDescription, setWorkstreamDescription] = useState("")
  const [savingWorkstream, setSavingWorkstream] = useState(false)

  async function reload() {
    if (!projectId) return
    try {
      const [nextTasks, nextWorkstreams, nextIdentities] = await Promise.all([
        listTasks(projectId),
        listDetailedWorkstreams(projectId),
        listDevIdentities(),
      ])
      setTasks(nextTasks)
      setWorkstreams(nextWorkstreams)
      setIdentities(nextIdentities)
    } catch {
      toast.error("Could not load deal work.")
    }
  }

  useEffect(() => {
    reload()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId])

  async function addWorkstream(event: React.FormEvent) {
    event.preventDefault()
    if (!projectId) return
    setSavingWorkstream(true)
    try {
      await createWorkstream(projectId, workstreamName, workstreamDescription)
      setWorkstreamName("")
      setWorkstreamDescription("")
      toast.success("Workstream created.")
      await reload()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not create the workstream.")
    } finally {
      setSavingWorkstream(false)
    }
  }

  if (!projectId || tasks === null) {
    return <div className="mx-auto max-w-5xl px-6 pt-8 pb-20 text-sm text-muted-foreground">Loading work…</div>
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 px-6 pt-8 pb-20">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-semibold text-foreground">Workstreams &amp; tasks</h1>
          <p className="mt-1 text-sm text-muted-foreground">Coordinate human work without leaving the deal workspace.</p>
        </div>
        <Button onClick={() => setTaskDialogOpen(true)}><PlusIcon /> New task</Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <section aria-labelledby="tasks-heading" className="space-y-3">
          <h2 id="tasks-heading" className="font-heading text-lg font-semibold">Tasks</h2>
          {tasks.length === 0 ? (
            <Card className="p-8 text-center text-sm text-muted-foreground">No tasks yet.</Card>
          ) : tasks.map((task) => (
            <TaskCard key={task.id} projectId={projectId} task={task} identities={identities} onChanged={reload} />
          ))}
        </section>

        <aside className="space-y-3" aria-labelledby="workstreams-heading">
          <h2 id="workstreams-heading" className="font-heading text-lg font-semibold">Workstreams</h2>
          <Card className="p-4">
            {workstreams.length === 0 ? (
              <p className="text-sm text-muted-foreground">No workstreams yet.</p>
            ) : (
              <ul className="space-y-3">
                {workstreams.map((workstream) => (
                  <li key={workstream.id}>
                    <p className="text-sm font-medium text-foreground">{workstream.name}</p>
                    {workstream.description ? <p className="text-xs text-muted-foreground">{workstream.description}</p> : null}
                    <p className="mt-1 text-xs text-muted-foreground">{workstream.assignments.length} assigned</p>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card className="p-4">
            <form className="grid gap-3" onSubmit={addWorkstream}>
              <p className="text-sm font-medium text-foreground">Add workstream</p>
              <Input value={workstreamName} onChange={(event) => setWorkstreamName(event.target.value)} placeholder="e.g. Financial diligence" maxLength={200} required />
              <Textarea value={workstreamDescription} onChange={(event) => setWorkstreamDescription(event.target.value)} placeholder="Description" rows={2} maxLength={2000} />
              <Button type="submit" variant="secondary" disabled={savingWorkstream}>{savingWorkstream ? "Adding…" : "Add workstream"}</Button>
            </form>
          </Card>
        </aside>
      </div>

      <NewTaskDialog
        projectId={projectId}
        workstreams={workstreams}
        identities={identities}
        open={taskDialogOpen}
        onOpenChange={setTaskDialogOpen}
        onCreated={reload}
      />
    </div>
  )
}
