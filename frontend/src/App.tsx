import { BrowserRouter, Route, Routes } from "react-router-dom"

import { DealShell } from "@/components/DealShell"
import { Layout } from "@/components/Layout"
import { Toaster } from "@/components/ui/sonner"
import { Activity } from "@/routes/Activity"
import { Assertions } from "@/routes/Assertions"
import { DealOverview } from "@/routes/DealOverview"
import { Deals } from "@/routes/Deals"
import { DecisionPackage } from "@/routes/DecisionPackage"
import { Documents } from "@/routes/Documents"
import { Findings } from "@/routes/Findings"
import { Home } from "@/routes/Home"
import { MandateDetail } from "@/routes/MandateDetail"
import { MandateList } from "@/routes/MandateList"
import { MandatesHome } from "@/routes/MandatesHome"
import { Readiness } from "@/routes/Readiness"
import { Reassessments } from "@/routes/Reassessments"
import { Triggers } from "@/routes/Triggers"
import { Work } from "@/routes/Work"
import { RequireCapability } from "@/lib/dealAccess"

function App() {
  return (
    <BrowserRouter>
      <Toaster />
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Home />} />
          <Route path="/deals" element={<Deals />} />
          <Route path="/mandates" element={<MandatesHome />} />
          <Route path="/projects/:projectId" element={<DealShell />}>
            <Route index element={<DealOverview />} />
            <Route
              path="documents"
              element={<RequireCapability capability="view_internal_documents"><Documents /></RequireCapability>}
            />
            <Route
              path="findings"
              element={<RequireCapability capability="view_findings"><Findings /></RequireCapability>}
            />
            <Route
              path="decision-package"
              element={<RequireCapability capability="view_decision_packages"><DecisionPackage /></RequireCapability>}
            />
            <Route
              path="readiness"
              element={<RequireCapability capability="view_readiness"><Readiness /></RequireCapability>}
            />
            <Route
              path="reassessments"
              element={<RequireCapability capability="view_reassessments"><Reassessments /></RequireCapability>}
            />
            <Route
              path="assertions"
              element={<RequireCapability capability="view_assertions"><Assertions /></RequireCapability>}
            />
            <Route
              path="triggers"
              element={<RequireCapability capability="view_triggers"><Triggers /></RequireCapability>}
            />
            <Route
              path="mandates"
              element={<RequireCapability capability="view_mandates"><MandateList /></RequireCapability>}
            />
            <Route
              path="mandates/:mandateId"
              element={<RequireCapability capability="view_mandates"><MandateDetail /></RequireCapability>}
            />
            <Route
              path="work"
              element={<RequireCapability capability="view_work_products"><Work /></RequireCapability>}
            />
            <Route
              path="activity"
              element={<RequireCapability capability="view_internal_activity"><Activity /></RequireCapability>}
            />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
