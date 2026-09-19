import type { ActivityEvent } from "@/lib/api"

// Shared by Overview and Activity (Activity is its own tab now, per the
// design prototype's 6-tab shape) - pulled out of DealOverview.tsx rather
// than exported from it, so neither route file mixes component exports
// with plain functions (oxlint's own "only-export-components" rule).

export function formatDateTime(isoString: string) {
  return new Date(isoString).toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  })
}

export function activitySummary(event: ActivityEvent): string {
  const actor = event.actor ? event.actor.display_name : "Someone"
  switch (event.kind) {
    case "comment":
      return `${actor} commented on "${event.task_title}"`
    case "submission":
      return `${actor} submitted "${event.work_product_title}" (v${event.version_number}) for "${event.task_title}"`
    case "review_decision":
      return event.decision === "approved"
        ? `${actor} approved "${event.work_product_title}" for "${event.task_title}"`
        : `${actor} returned "${event.work_product_title}" for revision on "${event.task_title}"`
    default:
      return actor
  }
}
