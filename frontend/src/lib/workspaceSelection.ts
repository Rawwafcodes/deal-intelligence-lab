import { useState } from "react"
import { useSearchParams } from "react-router-dom"

import type { Workspace } from "@/lib/api"

// Task 18.1 follow-up: which findings workspace a deal page shows. The
// choice travels in `?workspace=<id>` so moving between Findings,
// Readiness and Decision package keeps the same workspace instead of each
// page silently falling back to the newest one.

export function workspaceLabel(workspace: Workspace, withTime = false): string {
  const name = workspace.label || (workspace.cross_format_analysis_id ? "Reconciliation" : "Integrity review")
  const created = new Date(workspace.created_at)
  return `${name} — ${withTime ? created.toLocaleString() : created.toLocaleDateString()}`
}

export function initialWorkspaceId(sorted: Workspace[], requestedId: string | null): string | null {
  return sorted.find((w) => w.id === requestedId)?.id ?? sorted[0]?.id ?? null
}

export function useWorkspaceSelection() {
  const [searchParams, setSearchParams] = useSearchParams()
  // Read once on mount: the URL seeds the initial choice, the page owns it after.
  const [requestedId] = useState(() => searchParams.get("workspace"))

  function remember(workspaceId: string) {
    setSearchParams(
      (params) => {
        params.set("workspace", workspaceId)
        return params
      },
      { replace: true }
    )
  }

  return { requestedId, remember }
}

export function withWorkspace(path: string, workspaceId: string | null): string {
  return workspaceId ? `${path}?workspace=${encodeURIComponent(workspaceId)}` : path
}
