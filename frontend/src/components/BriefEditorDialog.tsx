import { useEffect, useState } from "react"
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
  getCurrentBriefVersion,
  saveBriefVersion,
  type BriefFields,
} from "@/lib/api"

const EMPTY_BRIEF: BriefFields = {
  parties: "",
  objective: "",
  perspective: "",
  scope: "",
  periods: "",
  uncertainties: "",
}

const FIELD_CONFIG: Array<{
  key: keyof BriefFields
  label: string
  hint: string
  multiline?: boolean
}> = [
  { key: "parties", label: "Parties", hint: "Buyer, seller, target, sponsor or project vehicle" },
  { key: "objective", label: "Objective", hint: "The decision or outcome this engagement must support", multiline: true },
  { key: "perspective", label: "Perspective", hint: "Buyer, seller, lender, investor or another perspective" },
  { key: "scope", label: "Scope", hint: "What is included and excluded", multiline: true },
  { key: "periods", label: "Relevant periods", hint: "Financial periods, forecast window or transaction dates" },
  { key: "uncertainties", label: "Known uncertainties", hint: "Unconfirmed relationships, assumptions or evidence gaps", multiline: true },
]

interface BriefEditorDialogProps {
  projectId: string
  open: boolean
  onOpenChange: (open: boolean) => void
  onSaved: () => void
}

export function BriefEditorDialog({ projectId, open, onOpenChange, onSaved }: BriefEditorDialogProps) {
  const [fields, setFields] = useState<BriefFields>(EMPTY_BRIEF)
  const [version, setVersion] = useState<number | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!open) return
    getCurrentBriefVersion(projectId)
      .then((current) => {
        setVersion(current?.version_number ?? null)
        setFields(current ? {
          parties: current.parties,
          objective: current.objective,
          perspective: current.perspective,
          scope: current.scope,
          periods: current.periods,
          uncertainties: current.uncertainties,
        } : EMPTY_BRIEF)
      })
      .catch(() => toast.error("Could not load the deal brief."))
  }, [open, projectId])

  async function save() {
    setSaving(true)
    try {
      const saved = await saveBriefVersion(projectId, fields)
      toast.success(`Deal brief saved as version ${saved.version_number}.`)
      onOpenChange(false)
      onSaved()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not save the deal brief.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{version ? `Edit deal brief · version ${version}` : "Create deal brief"}</DialogTitle>
          <DialogDescription>
            Saving creates a new immutable version. The brief guides interpretation; it is not treated as evidence.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-1">
          {FIELD_CONFIG.map((field) => (
            <label key={field.key} className="grid gap-1.5 text-sm font-medium text-foreground">
              {field.label}
              {field.multiline ? (
                <Textarea
                  value={fields[field.key]}
                  placeholder={field.hint}
                  rows={3}
                  onChange={(event) => setFields((current) => ({ ...current, [field.key]: event.target.value }))}
                />
              ) : (
                <Input
                  value={fields[field.key]}
                  placeholder={field.hint}
                  onChange={(event) => setFields((current) => ({ ...current, [field.key]: event.target.value }))}
                />
              )}
            </label>
          ))}
        </div>

        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button disabled={saving} onClick={save}>{saving ? "Saving…" : "Save new version"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
