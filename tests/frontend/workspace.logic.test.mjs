// Regression coverage for the adjusted_severity fix (Task 11.1, item 2):
// static/workspace.js's save-button handler used to inline
// `{ ...values, adjusted_severity: values.adjusted_severity || null }`
// directly in a click listener, with no test. buildFindingUpdatePayload is
// now a standalone pure function at the top of static/workspace.js (no DOM
// dependency), imported here directly via Node's built-in test runner - no
// jsdom, no bundler, no new dependency. Deliberately narrow: this proves
// the one fixed bug stays fixed, not a general DOM-testing framework.

import test from "node:test";
import assert from "node:assert/strict";

import { buildFindingUpdatePayload } from "../../static/workspace.js";

test("buildFindingUpdatePayload converts an empty adjusted_severity to null", () => {
  const result = buildFindingUpdatePayload({ adjusted_severity: "" });
  assert.equal(result.adjusted_severity, null);
});

test("buildFindingUpdatePayload leaves a set adjusted_severity unchanged", () => {
  const result = buildFindingUpdatePayload({ adjusted_severity: "high" });
  assert.equal(result.adjusted_severity, "high");
});

test("buildFindingUpdatePayload passes other fields through untouched", () => {
  const input = {
    review_status: "accepted",
    assigned_owner: "J. Rivera",
    due_date_text: "2026-10-01",
    management_response: "Pending",
    reviewer_notes: "Looks fine",
    adjusted_severity: "",
  };
  const result = buildFindingUpdatePayload(input);
  assert.equal(result.review_status, "accepted");
  assert.equal(result.assigned_owner, "J. Rivera");
  assert.equal(result.due_date_text, "2026-10-01");
  assert.equal(result.management_response, "Pending");
  assert.equal(result.reviewer_notes, "Looks fine");
  assert.equal(result.adjusted_severity, null);
});
