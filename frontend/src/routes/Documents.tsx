import { useEffect, useMemo, useState } from "react"
import { useParams } from "react-router-dom"
import { toast } from "sonner"

import { DocumentUploadDialog } from "@/components/DocumentUploadDialog"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { BACKEND_ORIGIN, listDocuments, type ProjectDocument } from "@/lib/api"

// Unifying the workspace frontend: the real document register, in React,
// wired to the same GET .../documents endpoint the static project.html
// page has always used - not a mockup, not a second source of truth. Upload
// now lives here as well, closing the former static-page dependency.

function folderOf(doc: ProjectDocument): string {
  const trimmed = doc.relative_path.replace(/\/[^/]*$/, "")
  return trimmed || "(root)"
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const units = ["KB", "MB", "GB"]
  let value = bytes / 1024
  let unitIndex = 0
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024
    unitIndex += 1
  }
  return `${value.toFixed(1)} ${units[unitIndex]}`
}

export function Documents() {
  const { projectId } = useParams<{ projectId: string }>()
  const [documents, setDocuments] = useState<ProjectDocument[] | null>(null)
  const [search, setSearch] = useState("")
  const [folder, setFolder] = useState("all")
  const [type, setType] = useState("all")
  const [uploadOpen, setUploadOpen] = useState(false)

  async function reload() {
    if (!projectId) return
    try {
      setDocuments(await listDocuments(projectId))
    } catch {
      toast.error("Could not load documents.")
    }
  }

  useEffect(() => {
    reload()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId])

  const folders = useMemo(
    () => Array.from(new Set((documents ?? []).map(folderOf))).sort(),
    [documents]
  )
  const types = useMemo(
    () => Array.from(new Set((documents ?? []).map((d) => d.extension.replace(/^\./, "").toUpperCase()))).sort(),
    [documents]
  )

  const filtered = (documents ?? []).filter((doc) => {
    if (search && !doc.original_filename.toLowerCase().includes(search.toLowerCase())) return false
    if (folder !== "all" && folderOf(doc) !== folder) return false
    if (type !== "all" && doc.extension.replace(/^\./, "").toUpperCase() !== type) return false
    return true
  })

  if (!documents || !projectId) {
    return <div className="mx-auto max-w-4xl px-6 pt-8 pb-20 text-sm text-muted-foreground">Loading documents…</div>
  }

  return (
    <div className="mx-auto max-w-4xl px-6 pt-8 pb-20 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-semibold text-foreground">Documents</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {documents.length} document{documents.length === 1 ? "" : "s"} in this deal's evidence room.
          </p>
        </div>
        <Button onClick={() => setUploadOpen(true)}>Upload documents</Button>
      </div>

      <Card className="p-4">
        <div className="flex flex-wrap gap-3">
          <Input
            placeholder="Search filename"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            className="max-w-xs"
          />
          <select
            value={folder}
            onChange={(event) => setFolder(event.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="all">All folders</option>
            {folders.map((f) => (
              <option key={f} value={f}>{f}</option>
            ))}
          </select>
          <select
            value={type}
            onChange={(event) => setType(event.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="all">All types</option>
            {types.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
      </Card>

      <Card className="overflow-hidden p-0">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs text-muted-foreground">
              <th className="px-4 py-2 font-medium">Name</th>
              <th className="px-4 py-2 font-medium">Folder</th>
              <th className="px-4 py-2 font-medium">Type</th>
              <th className="px-4 py-2 font-medium">Size</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((doc) => (
              <tr key={doc.id} className="border-b border-border last:border-0 hover:bg-accent/5">
                <td className="px-4 py-2">
                  <a
                    href={`${BACKEND_ORIGIN}/api/projects/${encodeURIComponent(projectId ?? "")}/documents/${encodeURIComponent(doc.id)}/download?inline=1`}
                    target="_blank"
                    rel="noreferrer"
                    className="text-foreground hover:text-accent hover:underline"
                  >
                    {doc.original_filename}
                  </a>
                </td>
                <td className="px-4 py-2 text-muted-foreground">{folderOf(doc)}</td>
                <td className="px-4 py-2 text-muted-foreground">{doc.extension.replace(/^\./, "").toUpperCase()}</td>
                <td className="px-4 py-2 text-muted-foreground">{formatBytes(doc.size_bytes)}</td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-muted-foreground">
                  No documents match these filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </Card>

      <DocumentUploadDialog
        projectId={projectId}
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        onUploaded={reload}
      />
    </div>
  )
}
