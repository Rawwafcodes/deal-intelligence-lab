# Change history
## 1.2.0 — 2026-09-27
Adopted the post-M17 roadmap (M18 Product and Intelligence Validation,
M19 Secure Online Foundation, M20 Commercial Pilot Readiness, M21 Live
Design-Partner Pilot, M22 Repeatability and Early Scale) as documentation
and planning only, following M17's confirmed completion and push to
`origin/main` (`70f03ca`). New `docs/13-post-m17-roadmap.md`; `10-
decisions.md` D17; `08-roadmap.md` M18-M22 pointer entries. M16's
outstanding validation gates are incorporated into M18 Track B, not
marked complete; provider/hosting selection remains deferred to M19. No
code, schema, deployment or paid-call authorization changed.

## 1.1.0 — 2026-09-17
Adopted the externally-supplied `workspace-integrity-integration` v1.0.0
package as a documentation/roadmap integration (preserved in full at
`integrations/workspace-integrity-integration-v1.0.0/`; see
`docs/10-decisions.md`'s I01-I08). Extended M14.2 and M15 with a bounded
Work-product Integrity Review capability family inside the existing
Mandate/findings hierarchy, and added a new, evidence-gated M16 for a
reusable evidence-assertion ledger and deterministic/semantic
cross-source review. No code, schema, or paid-call authorization changed;
M13.2 remains the next implementation task; M1-13.1 completion evidence
is unchanged and un-rewritten.

## 1.0.1 — 2026-09-15
Separated the Organization tenant entity from the product term Workspace and the
Milestone 9 legacy table. Added an early SQLite/WAL contention decision and a gate
requiring existing reconciliation to pass through the mandate runtime before expansion.

## 1.0.0 — 2026-09-15
Established the collaborative workspace and Mandates direction as the planning baseline.
Preserved the M1–9 engine, separated desired product from reported implementation,
moved collaboration and durable jobs into local development, and deferred hosting.
