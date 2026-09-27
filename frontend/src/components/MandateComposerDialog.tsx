import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
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
import { createMandate, listMandateTemplates, type MandateTemplate } from "@/lib/api"
import { isPipelineTemplate, isReviewTemplate } from "@/lib/mandateTemplates"

type Structure = "flexible" | "review" | "pipeline" | "monitoring"

interface MandateComposerDialogProps {
  projectId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

const STRUCTURE_COPY: Record<Structure, { label: string; hint: string }> = {
  flexible: { label: "Flexible", hint: "AI proposes the method - you review the plan before anything runs." },
  review: { label: "Review", hint: "Check a work product, model or conclusion against evidence." },
  pipeline: { label: "Pipeline", hint: "Run a known professional workflow from the registered templates." },
  monitoring: { label: "Monitoring", hint: "React to a future document or state change - configured as a trigger." },
}

export function MandateComposerDialog({ projectId, open, onOpenChange }: MandateComposerDialogProps) {
  const navigate = useNavigate()
  const [step, setStep] = useState<"objective" | "structure" | "pipeline-pick">("objective")
  const [objective, setObjective] = useState("")
  const [formError, setFormError] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [templates, setTemplates] = useState<MandateTemplate[]>([])

  useEffect(() => {
    if (!open) return
    setStep("objective")
    setObjective("")
    setFormError("")
    listMandateTemplates().then(setTemplates).catch(() => setTemplates([]))
  }, [open])

  const reviewTemplate = templates.find((t) => isReviewTemplate(t.key))
  const pipelineTemplates = templates.filter((t) => isPipelineTemplate(t.key))

  function continueToStructure(event: React.FormEvent) {
    event.preventDefault()
    if (!objective.trim()) {
      setFormError("An objective is required.")
      return
    }
    setFormError("")
    setStep("structure")
  }

  async function commission(structure: Structure, templateKey?: string) {
    if (structure === "monitoring") {
      onOpenChange(false)
      navigate(`/projects/${projectId}/triggers`)
      return
    }
    setSubmitting(true)
    try {
      const mandate = await createMandate(projectId, objective.trim())
      onOpenChange(false)
      const params = new URLSearchParams({ structure })
      if (templateKey) params.set("template", templateKey)
      navigate(`/projects/${projectId}/mandates/${mandate.id}?${params.toString()}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not create the mandate.")
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
        {step === "objective" && (
          <form onSubmit={continueToStructure}>
            <DialogHeader>
              <DialogTitle>What do you need accomplished?</DialogTitle>
              <DialogDescription className="sr-only">Describe the professional objective for this mandate.</DialogDescription>
            </DialogHeader>
            <div className="py-2">
              <Textarea
                value={objective}
                onChange={(event) => setObjective(event.target.value)}
                placeholder="e.g. Reconcile the term sheet against the financial model"
                autoFocus
                required
                rows={4}
              />
              {formError ? <p className="mt-2 text-sm text-destructive">{formError}</p> : null}
            </div>
            <DialogFooter>
              <Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button>
              <Button type="submit">Continue</Button>
            </DialogFooter>
          </form>
        )}

        {step === "structure" && (
          <>
            <DialogHeader>
              <DialogTitle>Starting structure</DialogTitle>
              <DialogDescription>
                Four ways of configuring the same mandate - not four separate products.
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-3 py-2">
              <Card
                className="cursor-pointer p-4 transition-colors hover:border-primary"
                onClick={() => commission("flexible")}
              >
                <div className="font-heading font-semibold text-foreground">{STRUCTURE_COPY.flexible.label}</div>
                <p className="mt-1 text-sm text-muted-foreground">{STRUCTURE_COPY.flexible.hint}</p>
              </Card>

              {reviewTemplate && (
                <Card
                  className="cursor-pointer p-4 transition-colors hover:border-primary"
                  onClick={() => commission("review", reviewTemplate.key)}
                >
                  <div className="font-heading font-semibold text-foreground">{STRUCTURE_COPY.review.label}</div>
                  <p className="mt-1 text-sm text-muted-foreground">{reviewTemplate.description}</p>
                </Card>
              )}

              <Card
                className="cursor-pointer p-4 transition-colors hover:border-primary"
                onClick={() => setStep("pipeline-pick")}
              >
                <div className="font-heading font-semibold text-foreground">{STRUCTURE_COPY.pipeline.label}</div>
                <p className="mt-1 text-sm text-muted-foreground">{STRUCTURE_COPY.pipeline.hint}</p>
              </Card>

              <Card
                className="cursor-pointer p-4 transition-colors hover:border-primary"
                onClick={() => commission("monitoring")}
              >
                <div className="font-heading font-semibold text-foreground">{STRUCTURE_COPY.monitoring.label}</div>
                <p className="mt-1 text-sm text-muted-foreground">{STRUCTURE_COPY.monitoring.hint}</p>
              </Card>
            </div>
            <DialogFooter>
              <Button type="button" variant="secondary" onClick={() => setStep("objective")}>Back</Button>
            </DialogFooter>
          </>
        )}

        {step === "pipeline-pick" && (
          <>
            <DialogHeader>
              <DialogTitle>Choose a pipeline</DialogTitle>
              <DialogDescription>Every real, registered professional template.</DialogDescription>
            </DialogHeader>
            <div className="grid gap-3 py-2">
              {pipelineTemplates.map((template) => (
                <Card
                  key={template.key}
                  className="cursor-pointer p-4 transition-colors hover:border-primary"
                  onClick={() => commission("pipeline", template.key)}
                >
                  <div className="font-heading font-semibold text-foreground">{template.name}</div>
                  <p className="mt-1 text-sm text-muted-foreground">{template.description}</p>
                </Card>
              ))}
            </div>
            <DialogFooter>
              <Button type="button" variant="secondary" disabled={submitting} onClick={() => setStep("structure")}>Back</Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
