# Repository instructions for coding agents

## Mission

Build the collaborative AI-native professional workspace defined in
`docs/product/`. The current implementation focuses on deal, diligence and
advisory work. Extend the working system; do not reinterpret it as a collection
of disconnected AI demos or reports.

## Required reading

Before planning or changing product behavior, read completely:

1. `docs/product/README.md`
2. `docs/product/01-product-definition.md`
3. `docs/product/02-experience-and-information-architecture.md`
4. `docs/product/03-mandates-and-intelligence.md`
5. `docs/product/04-build-and-delivery-rules.md`
6. `docs/product/05-current-product-map.md`
7. `docs/product/06-truth-register.md`
8. `docs/workspace-shift/docs/10-decisions.md`
9. The relevant current section of `docs/workspace-shift/STATUS.md`
10. The selected task specification and every document it directly requires.

For domain, permission, architecture or roadmap work, also read the relevant
document under `docs/workspace-shift/docs/`. Claude Code must additionally obey
`CLAUDE.md`; its design guidance supplements rather than replaces this file.

## Authority and truth

- Latest explicit founder instruction outranks accepted decisions; accepted
  decisions outrank product context; product context outranks task examples and
  historical milestone plans.
- Code is evidence of what exists, not permission to redefine the intended
  product.
- Re-verify status claims against the checkout before relying on them.
- Preserve distinctions between established direction, implemented fact,
  working hypothesis, open decision and deferred work.
- Surface conflicts and ask for a founder decision. Never silently choose the
  more convenient interpretation.

## Working rules

- Inspect `git status` before editing. Existing changes belong to the user or
  another agent; do not overwrite, reset, clean or fold them into your task.
- Work on one bounded, reviewable workflow at a time. State preserved behavior,
  exclusions, data changes, paid calls and deployment effects.
- Reuse tested domain modules and APIs. Do not create a second runtime,
  findings silo, authorization path or parser without explicit need.
- React + TypeScript is the permanent customer-facing frontend. Do not add a
  new static application page or expose a user-facing link back to a migrated
  static workflow.
- Deterministic software owns access, versions, state, audit and limits. AI
  handles comprehension and synthesis. Humans approve consequential outcomes.
- Pin exact source/submission versions. Preserve historical outputs and
  decisions; later evidence may mark them stale but must not rewrite them.
- Never use real deal records as writable test fixtures. Every real project is
  read-only unless the founder explicitly authorizes a disposable copy.
- Never commit secrets, credentials, deal documents, raw provider traces,
  database dumps or private company information.
- Never make a paid model call, transmit documents, deploy, migrate real data or
  push to a remote without explicit task-specific authorization.

## Required completion evidence

For code changes:

1. Run the narrow tests first, then the relevant broader suite.
2. Run type checking and linting applicable to changed code.
3. For UI changes, build the React app, verify the real browser journey and run
   `scripts/build-frontend-into-static.sh` so port 8765 receives the change.
4. Record commands, results, limitations and environment blockers honestly.
5. Update `docs/workspace-shift/STATUS.md` when the change materially alters
   implemented product state.
6. Commit the bounded change separately with a reversible message.

Do not claim live browser verification when only source inspection or mocked
requests were used. Do not claim the full suite passes if dependencies or local
PostgreSQL prevented it from running.
