import { BrowserRouter, Route, Routes } from "react-router-dom"

import { DealShell } from "@/components/DealShell"
import { Layout } from "@/components/Layout"
import { Toaster } from "@/components/ui/sonner"
import { Activity } from "@/routes/Activity"
import { DealOverview } from "@/routes/DealOverview"
import { Documents } from "@/routes/Documents"
import { Findings } from "@/routes/Findings"
import { Home } from "@/routes/Home"
import { MandateDetail } from "@/routes/MandateDetail"
import { MandateList } from "@/routes/MandateList"

function App() {
  return (
    <BrowserRouter>
      <Toaster />
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Home />} />
          <Route path="/projects/:projectId" element={<DealShell />}>
            <Route index element={<DealOverview />} />
            <Route path="documents" element={<Documents />} />
            <Route path="findings" element={<Findings />} />
            <Route path="mandates" element={<MandateList />} />
            <Route path="mandates/:mandateId" element={<MandateDetail />} />
            <Route path="activity" element={<Activity />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
