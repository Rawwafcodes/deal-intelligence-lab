import { useState } from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
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
  createRequest,
  REQUEST_PRIORITIES,
  type Finding,
  type RequestPriority,
} from "@/lib/api"

interface RequestDialogProps {
  projectId: string
  workspaceId: string
  findings: Finding[]
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: () => void
}

export function RequestDialog({ projectId, workspaceId, findings, open, onOpenChange, onCreated }: RequestDialogProps) {
  const [question, setQuestion] = useState("")
  const [priority, setPriority] = useState<RequestPriority>("medium")
  const [assignedRecipient, setAssignedRecipient] = useState("")
  const [relatedFindingIds, setRelatedFindingIds] = useState<string[]>([])
  const [saving, setSaving] = useState(false)

  function reset() {
    setQuestion("")
    setPriority("medium")
    setAssignedRecipient("")
    setRelatedFindingIds([])
  }

  function toggleFinding(id: string) {
    setRelatedFindingIds((current) =>
      current.includes(id) ? current.filter((f) => f !== id) : [...current, id]
    )
  }

  async function submit() {
    if (!question.trim()) {
      toast.error("A question is required.")
      return
    }
    setSaving(true)
    try {
      await createRequest(projectId, workspaceId, {
        question: question.trim(),
        priority,
        assigned_recipient: assignedRecipient.trim(),
        related_finding_ids: relatedFindingIds,
      })
      toast.success("Request created.")
      reset()
      onOpenChange(false)
      onCreated()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not create the request.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>New information request</DialogTitle>
          <DialogDescription>
            Ask management or another workstream for something this deal needs to resolve.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-1">
          <label className="grid gap-1.5 text-sm font-medium text-foreground">
            Question
            <Textarea
              value={question}
              placeholder="What do you need to know or receive?"
              rows={3}
              onChange={(event) => setQuestion(event.target.value)}
            />
          </label>

          <div className="grid grid-cols-2 gap-4">
            <label className="grid gap-1.5 text-sm font-medium text-foreground">
              Priority
              <select
                value={priority}
                onChange={(event) => setPriority(event.target.value as RequestPriority)}
                className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
              >
                {REQUEST_PRIORITIES.map((p) => (
                  <option key={p} value={p}>{p[0].toUpperCase() + p.slice(1)}</option>
                ))}
              </select>
            </label>
            <label className="grid gap-1.5 text-sm font-medium text-foreground">
              Assigned recipient
              <Input
                value={assignedRecipient}
                placeholder="Who should answer this?"
                onChange={(event) => setAssignedRecipient(event.target.value)}
              />
            </label>
          </div>

          {findings.length > 0 && (
            <div className="grid gap-1.5 text-sm font-medium text-foreground">
              Related findings (optional)
              <div className="max-h-40 overflow-y-auto rounded-md border border-border">
                {findings.map((finding) => (
                  <label key={finding.id} className="flex items-center gap-2 border-b border-border px-3 py-2 text-sm font-normal last:border-b-0">
                    <input
                      type="checkbox"
                      checked={relatedFindingIds.includes(finding.id)}
                      onChange={() => toggleFinding(finding.id)}
                    />
                    <span className="min-w-0 flex-1 truncate">{finding.title}</span>
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button disabled={saving} onClick={submit}>{saving ? "Creating…" : "Create request"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
