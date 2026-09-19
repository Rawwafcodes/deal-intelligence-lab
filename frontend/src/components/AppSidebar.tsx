import { FolderKanban, ShieldCheck } from "lucide-react"
import { Link, useLocation, useParams } from "react-router-dom"

import { IdentityFooter } from "@/components/IdentityFooter"
import { Sidebar, SidebarBody, SidebarLink, SidebarToggle } from "@/components/ui/sidebar"
import { BACKEND_ORIGIN } from "@/lib/api"

// The persistent navigation shell for app-level destinations only.
// Deal-scoped navigation (Overview/Documents/Findings/Mandates/Activity)
// now lives entirely in DealShell's own in-app tab strip, matching the
// design prototype this whole effort was built against - this sidebar no
// longer hard-links out to the static project.html page for those
// (formerly "Overview & documents"/"Mandates" here). Validation is a
// disclosed, deliberate exception: it isn't one of the prototype's tabs,
// and migrating it to React is a separate, larger task not attempted here.
export function AppSidebar() {
  const { projectId } = useParams<{ projectId?: string }>()
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
