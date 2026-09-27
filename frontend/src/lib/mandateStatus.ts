// Mirrors mandates.py's MANDATE_STATUSES exactly - shared by every
// screen that renders a mandate status label (MandateList, MandateDetail,
// and Overview's cross-deal Mandates summary), so the wording never
// drifts between them.
export const MANDATE_STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  planning: "Planning",
  awaiting_approval: "Awaiting approval",
  active: "Active",
  under_review: "Under review",
  completed: "Completed",
  cancelled: "Cancelled",
  failed: "Failed",
}
