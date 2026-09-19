import { useState } from "react"
import { UploadIcon } from "lucide-react"
import { toast } from "sonner"

import { Button, buttonVariants } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { uploadDocuments, type UploadResult } from "@/lib/api"

interface DocumentUploadDialogProps {
  projectId: string
  open: boolean
  onOpenChange: (open: boolean) => void
  onUploaded: () => void
}

export function DocumentUploadDialog({ projectId, open, onOpenChange, onUploaded }: DocumentUploadDialogProps) {
  const [files, setFiles] = useState<File[]>([])
  const [results, setResults] = useState<UploadResult[]>([])
  const [uploading, setUploading] = useState(false)

  async function upload() {
    if (files.length === 0) return
    setUploading(true)
    setResults([])
    try {
      const response = await uploadDocuments(projectId, files)
      setResults(response.results)
      const uploaded = response.results.filter((result) => result.status === "success").length
      const skipped = response.results.length - uploaded
      toast.success(`${uploaded} document${uploaded === 1 ? "" : "s"} uploaded${skipped ? `; ${skipped} skipped` : ""}.`)
      setFiles([])
      onUploaded()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not upload documents.")
    } finally {
      setUploading(false)
    }
  }

  function close(nextOpen: boolean) {
    onOpenChange(nextOpen)
    if (!nextOpen) {
      setFiles([])
      setResults([])
    }
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Upload documents</DialogTitle>
          <DialogDescription>
            Original files are stored unchanged. Choose individual files or preserve a folder structure.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-3">
          <div className="rounded-lg border border-dashed border-border p-5 text-center">
            <UploadIcon className="mx-auto mb-2 size-5 text-muted-foreground" aria-hidden="true" />
            <div className="flex flex-wrap justify-center gap-2">
              <label className={buttonVariants({ variant: "secondary" })} htmlFor="document-files">Choose files</label>
              <input
                id="document-files"
                className="sr-only"
                type="file"
                multiple
                onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
              />
              <label className={buttonVariants({ variant: "secondary" })} htmlFor="document-folder">Choose folder</label>
              <input
                id="document-folder"
                className="sr-only"
                type="file"
                multiple
                // React's type does not expose the Chromium directory attribute.
                {...({ webkitdirectory: "" } as React.InputHTMLAttributes<HTMLInputElement>)}
                onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
              />
            </div>
            <p className="mt-3 text-xs text-muted-foreground">
              PDF, DOCX, XLSX, XLS, PPTX, TXT and common image formats. Up to 200 files per upload.
            </p>
          </div>

          {files.length > 0 ? (
            <div className="rounded-md bg-muted/50 px-3 py-2 text-sm text-foreground">
              {files.length} file{files.length === 1 ? "" : "s"} selected
            </div>
          ) : null}

          {results.length > 0 ? (
            <ul className="max-h-40 space-y-1 overflow-y-auto text-xs">
              {results.map((result, index) => (
                <li key={`${result.filename}-${index}`} className="flex justify-between gap-3">
                  <span className="truncate text-foreground">{result.relative_path || result.filename}</span>
                  <span className="shrink-0 text-muted-foreground">{result.status.replaceAll("_", " ")}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>

        <DialogFooter>
          <Button variant="secondary" onClick={() => close(false)}>Close</Button>
          <Button disabled={files.length === 0 || uploading} onClick={upload}>
            {uploading ? "Uploading…" : `Upload${files.length ? ` ${files.length}` : ""}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
