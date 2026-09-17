import { createContext, useContext, useEffect, useState } from "react"
import { Link, type LinkProps } from "react-router-dom"
import { Menu, X } from "lucide-react"

import { cn } from "@/lib/utils"

// Grounded in https://21st.dev/@manuarora700/components/sidebar (Task
// "Direction A" exploration) but reimplemented rather than installed
// verbatim: the reference is Next.js (next/link, next/image) and uses
// framer-motion for a hover-triggered expand with no keyboard path at
// all - both wrong for this project (Vite + react-router, and
// CLAUDE.md's "avoid decorative motion" plus a real accessibility
// requirement that hover isn't the only way to operate a control). This
// version is click-toggled (works identically for mouse, keyboard, and
// touch), uses a plain CSS width transition instead of a new animation
// dependency, and is styled entirely from the --sidebar-* tokens already
// defined in index.css.

interface SidebarContextValue {
  open: boolean
  setOpen: (open: boolean) => void
}

const SidebarContext = createContext<SidebarContextValue | undefined>(undefined)

const STORAGE_KEY = "dl-sidebar-open"

export function useSidebar() {
  const context = useContext(SidebarContext)
  if (!context) throw new Error("useSidebar must be used within <Sidebar>")
  return context
}

export function Sidebar({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(() => {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY)
      return stored === null ? true : stored === "1"
    } catch {
      return true
    }
  })

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, open ? "1" : "0")
    } catch {
      // per-viewer convenience only - fine to no-op if storage is unavailable
    }
  }, [open])

  return <SidebarContext.Provider value={{ open, setOpen }}>{children}</SidebarContext.Provider>
}

export function SidebarToggle({ className }: { className?: string }) {
  const { open, setOpen } = useSidebar()
  return (
    <button
      type="button"
      aria-label={open ? "Collapse sidebar" : "Expand sidebar"}
      aria-expanded={open}
      onClick={() => setOpen(!open)}
      className={cn(
        "flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-sidebar-foreground/70 transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring",
        className,
      )}
    >
      <Menu className="h-4 w-4" aria-hidden="true" />
    </button>
  )
}

export function SidebarBody({ children, className }: { children: React.ReactNode; className?: string }) {
  const { open } = useSidebar()
  return (
    <>
      <div
        className={cn(
          "hidden shrink-0 flex-col border-r border-sidebar-border bg-sidebar transition-[width] duration-150 ease-out md:flex",
          open ? "w-60" : "w-14",
          className,
        )}
      >
        {children}
      </div>
      <MobileSidebar className={className}>{children}</MobileSidebar>
    </>
  )
}

function MobileSidebar({ children, className }: { children: React.ReactNode; className?: string }) {
  const { open, setOpen } = useSidebar()
  return (
    <div className="border-b border-sidebar-border bg-sidebar md:hidden">
      <div className="flex h-12 items-center justify-between px-4">
        <span className="font-heading text-sm font-semibold text-sidebar-foreground">Deal Intelligence Lab</span>
        <button
          type="button"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          onClick={() => setOpen(!open)}
          className="flex h-8 w-8 items-center justify-center rounded-md text-sidebar-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring"
        >
          {open ? <X className="h-5 w-5" aria-hidden="true" /> : <Menu className="h-5 w-5" aria-hidden="true" />}
        </button>
      </div>
      {open ? <div className={cn("flex flex-col gap-1 p-3", className)}>{children}</div> : null}
    </div>
  )
}

export function SidebarLink({
  to,
  icon,
  label,
  active,
  external,
}: {
  to: string
  icon: React.ReactNode
  label: string
  active?: boolean
  external?: boolean
} & Partial<Pick<LinkProps, "target">>) {
  const { open } = useSidebar()
  const className = cn(
    "flex items-center gap-3 rounded-md px-2.5 py-2 text-sm text-sidebar-foreground/80 transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring",
    active && "bg-sidebar-accent text-sidebar-foreground",
  )
  const content = (
    <>
      <span className="flex h-5 w-5 shrink-0 items-center justify-center" aria-hidden="true">
        {icon}
      </span>
      {open ? <span className="truncate">{label}</span> : null}
    </>
  )
  // A collapsed link (icon-only) still needs an accessible name - supplied
  // via aria-label rather than visually-hidden text, since the label text
  // isn't in the DOM at all when collapsed (see the `open ?` above).
  const ariaLabel = open ? undefined : label
  if (external) {
    return (
      <a href={to} className={className} aria-label={ariaLabel}>
        {content}
      </a>
    )
  }
  return (
    <Link to={to} className={className} aria-label={ariaLabel}>
      {content}
    </Link>
  )
}
