import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import test from "node:test"

function source(relativePath) {
  return readFileSync(new URL(`../../${relativePath}`, import.meta.url), "utf8")
}

test("deal overview has no user-facing escape to the legacy project page", () => {
  const overview = source("frontend/src/routes/DealOverview.tsx")

  assert.doesNotMatch(overview, /project\.html/)
  assert.doesNotMatch(overview, /legacy page/i)
  assert.match(overview, /BriefEditorDialog/)
  assert.match(overview, /\/documents/)
  assert.match(overview, /\/work/)
})

test("React owns document upload and the human-work route", () => {
  const documents = source("frontend/src/routes/Documents.tsx")
  const app = source("frontend/src/App.tsx")
  const work = source("frontend/src/routes/Work.tsx")

  assert.match(documents, /DocumentUploadDialog/)
  assert.match(app, /path="work" element=\{<Work \/>\}/)
  assert.match(work, /Workstreams &amp; tasks/)
  assert.match(work, /submitWorkProduct/)
  assert.match(work, /reviewWorkProduct/)
})
