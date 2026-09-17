import { BrowserRouter, Route, Routes } from "react-router-dom"

import { Layout } from "@/components/Layout"
import { Toaster } from "@/components/ui/sonner"
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
          <Route path="/projects/:projectId/mandates" element={<MandateList />} />
          <Route path="/projects/:projectId/mandates/:mandateId" element={<MandateDetail />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
