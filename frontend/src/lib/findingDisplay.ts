// Shared display helpers for findings (Findings list + FindingDetail).

// Document id -> the exact version id the analysis read, built from the
// workspace's own analysis record (pdf_/excel_document_ids zipped with
// the matching *_version_ids).
export type PinnedVersions = Record<string, string>

export function pinnedVersionsFromAnalysis(analysis: Record<string, unknown> | null): PinnedVersions {
  const pinned: PinnedVersions = {}
  if (!analysis) return pinned
  for (const kind of ["pdf", "excel"]) {
    const ids = analysis[`${kind}_document_ids`]
    const versions = analysis[`${kind}_document_version_ids`]
    if (!Array.isArray(ids) || !Array.isArray(versions)) continue
    ids.forEach((id, index) => {
      if (typeof id === "string" && typeof versions[index] === "string") pinned[id] = versions[index]
    })
  }
  return pinned
}

const LABELS: Record<string, string> = {
  unreviewed: "Unreviewed", accepted: "Accepted", partially_accepted: "Partially accepted",
  rejected: "Rejected", unverifiable: "Unverifiable",
  critical: "Critical", high: "High", medium: "Medium", low: "Low", informational: "Info",
  open: "Open", awaiting_information: "Awaiting information", management_responded: "Management responded",
  resolved: "Resolved", accepted_risk: "Accepted risk",
}
export const labelFor = (value: string | null | undefined) => (value ? LABELS[value] ?? value : "—")
