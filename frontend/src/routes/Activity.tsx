import { useEffect, useState } from "react"
import { useParams } from "react-router-dom"
import { toast } from "sonner"

import { Card } from "@/components/ui/card"
import { activitySummary, formatDateTime } from "@/lib/activity"
import { getDealOverview, type ActivityEvent } from "@/lib/api"

// Unifying the workspace frontend: Activity as its own tab, matching the
// design prototype's 6-tab shape - previously this feed only existed as
// a card at the bottom of Overview. Reuses DealOverview's own
// `activitySummary`/`formatDateTime` formatting rather than duplicating
// it, and its same data source (GET .../overview) - there is no separate
// activity-only endpoint yet, so this fetches the same overview payload
// Overview does and only renders the `activity` slice of it.

export function Activity() {
  const { projectId } = useParams<{ projectId: string }>()
  const [activity, setActivity] = useState<ActivityEvent[] | null>(null)

  useEffect(() => {
    if (!projectId) return
    getDealOverview(projectId)
      .then((overview) => setActivity(overview.restricted ? [] : overview.activity))
      .catch(() => toast.error("Could not load activity."))
  }, [projectId])

  if (!activity) {
    return <div className="mx-auto max-w-3xl px-6 pt-8 pb-20 text-sm text-muted-foreground">Loading activity…</div>
  }

  return (
    <div className="mx-auto max-w-3xl px-6 pt-8 pb-20 space-y-4">
      <div>
        <h1 className="font-heading text-2xl font-semibold text-foreground">Activity</h1>
        <p className="mt-1 text-sm text-muted-foreground">This deal's real audit trail, most recent first.</p>
      </div>

      <Card className="p-6">
        {activity.length === 0 ? (
          <p className="text-sm text-muted-foreground">No activity recorded yet.</p>
        ) : (
          <ul className="space-y-3">
            {activity.map((event, index) => (
              <li key={index} className="border-b border-border pb-3 text-sm last:border-0 last:pb-0">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="text-foreground">{activitySummary(event)}</span>
                  <span className="shrink-0 text-xs text-muted-foreground">{formatDateTime(event.at)}</span>
                </div>
                {event.summary && <p className="mt-0.5 text-xs text-muted-foreground">{event.summary}</p>}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
