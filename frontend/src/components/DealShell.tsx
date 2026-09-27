import { useEffect, useState } from "react"
import { Link, NavLink, Outlet, useLocation, useParams } from "react-router-dom"

import { getDealOverview } from "@/lib/api"

// Unifying the workspace frontend: a single, in-app tab strip for every
// deal-scoped destination (Overview / Documents / Findings / Mandates /
// Activity), matching the 6-tab shape of the "Mandate Workspace Prototype"
// design artifact this whole effort was built against. Replaces the
// AppSidebar's former hard links out to the static project.html page for
// documents and findings - those destinations are now real routes in this
// app, not a jump to a different codebase. "Deals" (the artifact's 6th tab,
// the top-level project list) stays on the existing left AppSidebar's
// "Projects" link rather than being duplicated here - one destination,
// one place to find it. "Validation" is a deliberate, disclosed exception
// (not one of the artifact's 6 tabs; still an external link to
// validation.html) - migrating it is a separate, larger task, not
// attempted here.
const TABS = [
  { to: "", label: "Overview", end: true },
  { to: "documents", label: "Documents" },
  { to: "findings", label: "Findings" },
  { to: "mandates", label: "Mandates" },
  { to: "activity", label: "Activity" },
]

export function DealShell() {
  const { projectId } = useParams<{ projectId: string }>()
  const location = useLocation()
  const overviewChildActive = location.pathname.endsWith("/work")
  // Task 17.8 (nav-clarity pass): docs/product/02's own requirement that
  // "Documents, Findings and Activity must make the selected deal
  // obvious" was not true before this - every deal-scoped page's own
  // header just said "Documents"/"Findings"/etc, never which deal.
  // Fetched once here, at the shell every deal-scoped route already
  // renders inside, rather than duplicating a fetch in each of those
  // five page components.
  const [dealName, setDealName] = useState<string | null>(null)

  useEffect(() => {
    if (!projectId) return
    setDealName(null)
    getDealOverview(projectId).then((overview) => setDealName(overview.project.name)).catch(() => undefined)
  }, [projectId])

  return (
    <div className="flex min-h-full flex-col">
      <div className="border-b border-border">
        <div className="flex items-center gap-2 px-6 pt-3 text-xs text-muted-foreground">
          <Link to="/deals" className="hover:underline">Deals</Link>
          <span aria-hidden="true">/</span>
          <span className="truncate font-medium text-foreground">{dealName ?? "…"}</span>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-6 pt-2" aria-label="Deal sections">
          {TABS.map((tab) => (
            <NavLink
              key={tab.label}
              to={`/projects/${projectId}${tab.to ? `/${tab.to}` : ""}`}
              end={tab.end}
              className={({ isActive }) =>
                `whitespace-nowrap rounded-t-md px-3 py-2 text-sm font-medium transition-colors ${
                  isActive || (tab.label === "Overview" && overviewChildActive)
                    ? "border-b-2 border-accent text-foreground"
                    : "border-b-2 border-transparent text-muted-foreground hover:text-foreground"
                }`
              }
            >
              {tab.label}
            </NavLink>
          ))}
        </nav>
      </div>
      <div className="flex-1">
        <Outlet />
      </div>
    </div>
  )
}
