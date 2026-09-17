import { FileStack, FolderKanban, ShieldCheck } from "lucide-react"
import { Link, useLocation, useParams } from "react-router-dom"

import { IdentityFooter } from "@/components/IdentityFooter"
import { Sidebar, SidebarBody, SidebarLink, SidebarToggle } from "@/components/ui/sidebar"
import { BACKEND_ORIGIN } from "@/lib/api"

// The persistent navigation shell ("Direction A" from the frontend design
// exploration). Project-scoped links only cover destinations that have a
// real, stable per-project URL today: the static project hub
// (documents/brief/workstreams/cross-format-analyses list) and Validation
// both do; reconciliation/inspection/cross-analysis pages require picking
// a specific analysis first (see static/project.js), so they stay reachable
// only from the project hub itself, not invented as sidebar links that
// would have nowhere real to point without an analysis id.
export function AppSidebar() {
  const { projectId, mandateId } = useParams<{ projectId?: string; mandateId?: string }>()
  const location = useLocation()

  return (
    <Sidebar>
      <SidebarBody className="justify-between overflow-y-auto">
        <div className="flex flex-1 flex-col gap-1">
          <div className="mb-2 flex items-center justify-between gap-2 px-1 py-1">
            <Link
              to="/"
              className="truncate font-heading text-sm font-semibold text-sidebar-foreground hover:text-sidebar-primary"
            >
              Deal Intelligence Lab
            </Link>
            <SidebarToggle className="hidden md:flex" />
          </div>

          <SidebarLink
            to="/"
            icon={<FolderKanban className="h-4 w-4" />}
            label="Projects"
            active={location.pathname === "/"}
          />

          {projectId ? (
            <>
              <div
                className="mt-3 mb-1 px-2.5 text-xs font-medium tracking-wide text-sidebar-foreground/50 uppercase"
                aria-hidden="true"
              >
                This deal
              </div>
              <SidebarLink
                to={`${BACKEND_ORIGIN}/project.html?id=${encodeURIComponent(projectId)}`}
                external
                icon={<FileStack className="h-4 w-4" />}
                label="Overview & documents"
              />
              <SidebarLink
                to={`/projects/${projectId}/mandates`}
                icon={<FolderKanban className="h-4 w-4" />}
                label="Mandates"
                active={location.pathname.startsWith(`/projects/${projectId}/mandates`) || Boolean(mandateId)}
              />
              <SidebarLink
                to={`${BACKEND_ORIGIN}/validation.html?project=${encodeURIComponent(projectId)}`}
                external
                icon={<ShieldCheck className="h-4 w-4" />}
                label="Validation"
              />
            </>
          ) : null}
        </div>

        <IdentityFooter />
      </SidebarBody>
    </Sidebar>
  )
}
