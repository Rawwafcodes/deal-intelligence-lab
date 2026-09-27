import { BrowserRouter, Route, Routes } from "react-router-dom"

import { DealShell } from "@/components/DealShell"
import { Layout } from "@/components/Layout"
import { Toaster } from "@/components/ui/sonner"
import { Activity } from "@/routes/Activity"
import { DealOverview } from "@/routes/DealOverview"
import { Deals } from "@/routes/Deals"
import { DecisionPackage } from "@/routes/DecisionPackage"
import { Documents } from "@/routes/Documents"
import { Findings } from "@/routes/Findings"
import { Home } from "@/routes/Home"
import { MandateDetail } from "@/routes/MandateDetail"
import { MandateList } from "@/routes/MandateList"
import { Readiness } from "@/routes/Readiness"
import { Reassessments } from "@/routes/Reassessments"
import { Triggers } from "@/routes/Triggers"
import { Work } from "@/routes/Work"

function App() {
  return (
    <BrowserRouter>
      <Toaster />
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Home />} />
          <Route path="/deals" element={<Deals />} />
          <Route path="/projects/:projectId" element={<DealShell />}>
            <Route index element={<DealOverview />} />
            <Route path="documents" element={<Documents />} />
            <Route path="findings" element={<Findings />} />
            <Route path="decision-package" element={<DecisionPackage />} />
            <Route path="readiness" element={<Readiness />} />
            <Route path="reassessments" element={<Reassessments />} />
            <Route path="triggers" element={<Triggers />} />
            <Route path="mandates" element={<MandateList />} />
            <Route path="mandates/:mandateId" element={<MandateDetail />} />
            <Route path="work" element={<Work />} />
            <Route path="activity" element={<Activity />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
