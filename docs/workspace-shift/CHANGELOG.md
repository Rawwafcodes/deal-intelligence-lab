# Change history
## 1.3.0 — 2026-09-27
Extended the post-M17 roadmap through M23 (Repeatable Commercial and
Customer-Administration Experience), M24 (Enterprise Identity, Audit,
Compliance and Isolated Deployment) and M25 (Scalable Operational
Capabilities), and reconciled every canonical surface in `docs/product/
02-experience-and-information-architecture.md`'s 25-surface target
inventory against the actual implementation (new `docs/product/
07-surface-reconciliation.md`; `10-decisions.md` D18). 13 of 25 surfaces
are complete, 2 are correctly static-only, 1 is partial (Document
Detail), and 9 are genuinely absent - each assigned to M19, M20 or M23.
Disclosed, not resolved, a real conflict: four shipped destinations
(Readiness, Reassessments, Triggers, Assertions) outside the canonical
25. The canonical table itself was not edited. No code, schema,
deployment or paid-call authorization changed.

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
