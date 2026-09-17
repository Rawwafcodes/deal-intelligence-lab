# Instructions for implementing agents

## Mission
Build the collaborative workspace described here by extending the existing lab.
Read README.md, STATUS.md, docs/00-direction-change.md, docs/02-existing-baseline.md,
docs/04-mandate-engine.md and the selected task completely before acting.
Read other specs referenced by that task.

## Authorization and evidence
- Task 000 is the current starting task. It authorizes inspection and documentation,
  not feature implementation, deployment, data mutation, paid API calls or pushing.
- Locate the actual application repository with the user. This spec folder is not it.
- Read the host repository's AGENTS.md/CLAUDE.md. Report substantive conflicts.
- Treat milestone reports as historical claims until verified against code.
- Never claim tests pass without running them and recording command, revision and scope.
- Preserve concurrent edits and untracked frontend work. Do not reset or clean them.
- Never use real deal records as writable acceptance fixtures. Use isolated synthetic
  data or an explicitly authorized copy. Universal Logic is read-only by default.
- No secrets, deal documents, client names, raw provider traces or production DBs in Git.
- Never access validation answer keys through AI tools, planning context, search or logs.
- Do not make paid calls or send documents externally without task-specific authorization.

## Architecture discipline
- One mandate concept, composer, executor and output experience.
- Templates describe professional methods; models adapt plans; code enforces boundaries.
- Reuse tested analytical modules through narrow adapters. Separate provider adapters
  are legitimate; a separate workflow engine and page per template are not.
- Do not implement a universal graph builder, plugin marketplace or broad framework first.
- New capabilities may require code and tests. New combinations of existing capabilities
  should normally require configuration only.
- Persist stable UUIDs and immutable finding snapshots. Hashes are integrity checks,
  not primary finding identity. Never reinterpret historical reviews on read.
- Keep observation history distinct from human issue resolution and approvals.
- Inputs are pinned versions; selecting a whole workspace never bypasses permissions.
- AI plans cannot introduce arbitrary code execution on the app host, new providers,
  network destinations, access grants, spending authority or approval powers.
- Model identifiers and provider features must be verified at integration time.
- Browser closure must not terminate a job. Durable local execution precedes multi-stage AI.
- Collaboration is a local foundation, not a staging add-on.
- Use Organization for the new persisted tenant boundary. Workspace is the product/UX
  term; `LegacyAnalysisWorkspace` denotes Milestone 9's preserved per-analysis record.
- Pass Gate A with the existing reconciliation capability before registering a second
  analytical capability or expanding the runtime abstraction.

## Workflow
Inspect → propose bounded changes → implement only the authorized task → test →
browser verify if UI changed → report limitations → update STATUS and CHANGELOG.
Stop when the task's acceptance criteria are met; do not advance automatically.

Each completion report includes: revision/dirty state, files changed, migrations,
tests and results, browser evidence, AI usage if authorized, remaining limitations,
rollback procedure and next recommended task.
