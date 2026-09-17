import { Outlet } from "react-router-dom"

import { AppSidebar } from "@/components/AppSidebar"

// The persistent shell every route now renders inside (App.tsx), replacing
// each page's own <AppHeader/> call from before Direction A.
export function Layout() {
  return (
    <div className="flex min-h-screen flex-col bg-background md:flex-row">
      <AppSidebar />
      <main className="min-w-0 flex-1">
        <Outlet />
      </main>
    </div>
  )
}
