import { useCallback, useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { toast } from "sonner"

import { Card } from "@/components/ui/card"
import {
  documentVersionHref,
  getDocument,
  getDocumentUsage,
  listDocumentVersions,
  uploadDocumentVersion,
  type DocumentDependent,
  type DocumentUsage,
  type DocumentVersionRecord,
  type ProjectDocument,
} from "@/lib/api"
import { labelFor } from "@/lib/findingDisplay"
import { withWorkspace } from "@/lib/workspaceSelection"

// Surface #13 (Document Detail) - founder decision 2026-09-27 to build it
// in M18: one document's content, its full version history, and its
// citation backlinks (which findings cite it, at which version and
// location, and what depends on it and is now potentially stale). Read-
// only apart from uploading a new version; deletion stays off this page.

const PREVIEWABLE_IMAGES = new Set([".png", ".jpg", ".jpeg", ".gif", ".webp"])

const DEPENDENT_LABELS: Record<string, string> = {
  workspace: "Findings workspace",
  deliverable_version: "Decision package",
  assertion_ledger_entry: "Assertion",
  mandate_run: "Mandate run",
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const kb = bytes / 1024
  return kb < 1024 ? `${kb.toFixed(1)} KB` : `${(kb / 1024).toFixed(1)} MB`
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString()
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card className="p-0">
      <h2 className="border-b border-border px-4 py-3 text-sm font-semibold text-foreground">{title}</h2>
      {children}
    </Card>
  )
}

function DependentRow({ dependent }: { dependent: DocumentDependent }) {
  const kind = DEPENDENT_LABELS[dependent.dependent_type] ?? dependent.dependent_type
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 px-4 py-2 text-sm">
      <span className="min-w-0 flex-1 text-foreground">
        {kind}
        {dependent.label ? `: ${dependent.label}` : ""}
      </span>
      <span className="text-xs text-muted-foreground">
        {dependent.version_number ? `uses v${dependent.version_number}` : ""}
      </span>
      {dependent.potentially_stale && (
        <span className="rounded-full border border-amber-900 bg-amber-950/40 px-2 py-0.5 text-xs text-amber-300">
          Potentially stale
        </span>
      )}
    </li>
  )
}

export function DocumentDetail() {
  const { projectId, documentId } = useParams<{ projectId: string; documentId: string }>()
  const [document, setDocument] = useState<ProjectDocument | null>(null)
  const [versions, setVersions] = useState<DocumentVersionRecord[]>([])
  const [usage, setUsage] = useState<DocumentUsage | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)

  const reload = useCallback(() => {
    if (!projectId || !documentId) return
    Promise.all([
      getDocument(projectId, documentId),
      listDocumentVersions(projectId, documentId),
      getDocumentUsage(projectId, documentId),
    ])
      .then(([doc, versionList, usageInfo]) => {
        setDocument(doc)
        setVersions([...versionList].sort((a, b) => b.version_number - a.version_number))
        setUsage(usageInfo)
      })
      .catch((error) => setLoadError(error instanceof Error ? error.message : "Could not load this document."))
  }, [projectId, documentId])

  useEffect(reload, [reload])

  async function uploadNewVersion(file: File | undefined) {
    if (!projectId || !documentId || !file || !document) return
    setUploading(true)
    try {
      const result = await uploadDocumentVersion(projectId, documentId, file)
      toast.success(
        `Now version ${result.document?.version_number ?? document.version_number + 1}. ` +
          "Anything based on the previous version is flagged for reassessment."
      )
      reload()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not upload the new version.")
    } finally {
      setUploading(false)
    }
  }

  if (loadError) {
    return (
      <div className="mx-auto max-w-4xl px-6 pt-8 pb-20">
        <Card className="p-6 text-sm text-muted-foreground">{loadError}</Card>
      </div>
    )
  }
  if (!document || !projectId) {
    return <div className="mx-auto max-w-4xl px-6 pt-8 pb-20 text-sm text-muted-foreground">Loading…</div>
  }

  const current = versions.find((v) => v.id === document.current_version_id) ?? versions[0]
  const currentHref = current ? documentVersionHref(projectId, document.id, current.id) : null
  const folder = document.relative_path.replace(/\/[^/]*$/, "") || "(root)"

  return (
    <div className="mx-auto max-w-4xl space-y-4 px-6 pt-8 pb-20">
      <div>
        <Link to={`/projects/${projectId}/documents`} className="text-sm text-muted-foreground underline">
          Back to documents
        </Link>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h1 className="font-heading text-2xl font-semibold break-words text-foreground">{document.original_filename}</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {folder} · {document.extension.replace(/^\./, "").toUpperCase()} · {formatBytes(document.size_bytes)} ·
              version {document.version_number} · uploaded {formatDate(document.uploaded_at)}
            </p>
          </div>
          <div className="flex items-center gap-3">
            {currentHref && (
              <a href={currentHref} target="_blank" rel="noreferrer" className="text-sm underline">
                Open file
              </a>
            )}
            <label className={`cursor-pointer text-sm underline ${uploading ? "pointer-events-none opacity-50" : ""}`}>
              {uploading ? "Uploading…" : "Upload new version"}
              <input
                type="file"
                className="sr-only"
                aria-label={`Upload a new version of ${document.original_filename}`}
                disabled={uploading}
                onChange={(event) => {
                  uploadNewVersion(event.target.files?.[0])
                  event.target.value = ""
                }}
              />
            </label>
          </div>
        </div>
      </div>

      <Section title="Content">
        {currentHref && document.extension === ".pdf" ? (
          <iframe
            title={`${document.original_filename}, version ${current?.version_number}`}
            src={currentHref}
            className="h-[70vh] w-full rounded-b-lg border-0 bg-white"
          />
        ) : currentHref && PREVIEWABLE_IMAGES.has(document.extension) ? (
          <img src={currentHref} alt={document.original_filename} className="max-h-[70vh] w-full object-contain p-4" />
        ) : (
          <p className="px-4 py-6 text-sm text-muted-foreground">
            No in-app preview for {document.extension.replace(/^\./, "").toUpperCase()} files.{" "}
            {currentHref && (
              <a href={currentHref} target="_blank" rel="noreferrer" className="underline">
                Open the current version
              </a>
            )}
            .
          </p>
        )}
      </Section>

      <Section title={`Versions (${versions.length})`}>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs text-muted-foreground">
              <th className="px-4 py-2 font-medium">Version</th>
              <th className="px-4 py-2 font-medium">Uploaded</th>
              <th className="px-4 py-2 font-medium">Size</th>
              <th className="px-4 py-2 font-medium">SHA-256</th>
              <th className="px-4 py-2 font-medium"><span className="sr-only">Open</span></th>
            </tr>
          </thead>
          <tbody>
            {versions.map((version) => (
              <tr key={version.id} className="border-b border-border last:border-0">
                <td className="px-4 py-2 text-foreground">
                  v{version.version_number}
                  {version.id === document.current_version_id && (
                    <span className="ml-2 rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">current</span>
                  )}
                </td>
                <td className="px-4 py-2 text-muted-foreground">{formatDate(version.uploaded_at)}</td>
                <td className="px-4 py-2 text-muted-foreground">{formatBytes(version.size_bytes)}</td>
                <td className="px-4 py-2 font-mono text-xs text-muted-foreground" title={version.sha256}>
                  {version.sha256.slice(0, 12)}
                </td>
                <td className="px-4 py-2 text-right">
                  <a
                    href={documentVersionHref(projectId, document.id, version.id)}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs underline"
                    aria-label={`Open version ${version.version_number}`}
                  >
                    Open
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <Section title="Cited by findings">
        {!usage || usage.citing_findings.length === 0 ? (
          <p className="px-4 py-6 text-sm text-muted-foreground">No finding cites this document yet.</p>
        ) : (
          <ul className="divide-y divide-border">
            {usage.citing_findings.map((finding) => {
              const where = [
                ...finding.pages.map((page) => `p. ${page}`),
                ...finding.cells,
              ].join(", ")
              return (
                <li key={`${finding.workspace_id}-${finding.finding_id}`} className="px-4 py-3 text-sm">
                  <Link
                    to={`${withWorkspace(`/projects/${projectId}/findings`, finding.workspace_id)}&finding=${encodeURIComponent(finding.finding_id)}`}
                    className="text-foreground underline"
                  >
                    {finding.title}
                  </Link>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {labelFor(finding.effective_severity)} · {labelFor(finding.review_status || "unreviewed")} ·{" "}
                    {finding.workspace_label}
                    {finding.version_number ? ` · cites v${finding.version_number}` : ""}
                    {where ? ` · ${where}` : ""}
                  </p>
                </li>
              )
            })}
          </ul>
        )}
      </Section>

      <Section title="Depends on this document">
        {!usage || usage.dependents.length === 0 ? (
          <p className="px-4 py-6 text-sm text-muted-foreground">Nothing recorded as depending on this document.</p>
        ) : (
          <ul className="divide-y divide-border">
            {usage.dependents.map((dependent) => (
              <DependentRow key={`${dependent.dependent_type}-${dependent.dependent_id}`} dependent={dependent} />
            ))}
          </ul>
        )}
      </Section>
    </div>
  )
}
