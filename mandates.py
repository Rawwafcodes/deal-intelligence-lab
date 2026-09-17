"""Mandate engine (roadmap M12.1-M12.2): docs/04-mandate-engine.md's
Mandate / Template / Plan / Run / Attempt contracts, a deterministic
"fixture" planner, one fixture-only capability, and a durable local
worker - proving the runtime's plumbing end to end without touching any
real analytical capability or calling any AI provider.

Task 12.2 replaced 12.1's synchronous, in-request `execute_run`/
`resume_run` with a real durable worker (see `Worker` below):
`execute_run` now only persists a "queued" Run and returns immediately -
by the time it returns, the run exists independently of the HTTP request
that created it. The `Worker`'s poll loop (a background thread, started
from `server.py:main()`, independent of any request) is what actually
walks a plan's stages, so closing the browser or the request connection
mid-run has no effect on whether the run finishes. `Worker.recover()`
handles the "the process itself died mid-run" case (see its own
docstring): a clean between-stages interruption is safely resumed: one
where a capability call was genuinely in flight when the process died is
reported as `outcome_unknown` rather than guessed at or silently
retried (docs/04: "unknown provider outcome is not automatically
retried"). Cancellation is now cooperative and checked before each stage
(`_run_stages`'s own per-stage check), not only available while parked at
a human checkpoint. Each Run also carries a minimal, enforced budget
ledger (`budget_limit`/`budget_consumed`, checked before every capability
call) - real and enforced, even though `fixture.echo`'s own declared
`unit_cost` has no real-money meaning.

Task 12.4 added real LLM planning (`propose_plan_llm`, below): a real model
(`mandate_planning.propose_candidate_plan`) proposes a candidate template
and, for a template that needs one, a source document selection - from the
mandate's objective, the project's real document inventory, and its brief,
never from file content. That proposal is untrusted exactly like any other
model output (docs/04): every document id is independently re-verified to
exist and belong to this project before being trusted, and the proposal is
handed to the *exact same* `propose_plan`/`validate_plan_stages` path a
human's manual selection already goes through - there is no separate,
laxer validation path for a model-proposed plan. A proposal the model
itself was not confident about, or one this function's own independent
checks reject, comes back as `LlmPlanProposalResult(status="unsupported")`
with a reason - no `PlanRevision` row is created for it. `approve_plan`
is completely unchanged: a model-proposed plan is exactly as "proposed,
not approved" as a human-proposed one, and only a human calling
`approve_plan` moves a mandate to `active`.

Task 12.5 (reuse proof) added no new capability and no new executor - the
roadmap's own instruction is "configure a second flow from existing
capabilities using the same runtime/UI", not build a second analytical
capability. `reconciliation-with-review` (below) is a second *template*
combining two already-registered/already-proven building blocks in a new
way: the real `reconciliation.cross_format` capability (12.3) and the
`human_checkpoint` stage kind (12.1, previously only exercised by the
fixture templates) - a mandate using it is not marked complete until a
human has reviewed the findings the reconciliation stage just produced.
Nothing in `_run_stages`, `_default_input_for_stage`, or
`propose_plan_llm` needed to change for this: a new stage-kind
*combination* on an existing capability is exactly the "new combinations
of existing capabilities should normally require configuration only"
line from AGENTS.md, proven true rather than just claimed.

Explicitly deferred to later, separately-authorized tasks (see
docs/workspace-shift/docs/08-roadmap.md's M12 breakdown and
docs/workspace-shift/tasks/12.2-durable-worker.md's own Exclusions):
- A `draft_from_reviewed_findings` capability (examples/reconciliation-
  template.json's own `draft`/`approve` stages) - still does not exist;
  `reconciliation-with-review` stops at `review`, on purpose.

Two logical registries live here, both **in-memory, code-level** (like a
plugin registry, not user data - see docs/04-mandate-engine.md's
"Register each capability with: name/version; input schema; ..."):
Capabilities (what an executor can actually do) and Templates (a reusable
stage blueprint a mandate's plan can be proposed from). Mandates, plans,
runs and attempts are the persisted, per-project data.
"""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

import cross_format_analyses
import cross_format_analysis
import deal_briefs
import documents
import evaluations
import integrity_review
import integrity_reviews
import mandate_planning
import store
import work_products
import workspaces
import workstreams

MANDATE_STATUSES = {
    "draft", "planning", "awaiting_approval", "active", "under_review",
    "completed", "cancelled", "failed",
}
PLAN_STATUSES = {"proposed", "approved", "rejected", "superseded"}
RUN_STATUSES = {
    "queued", "running", "succeeded", "failed", "interrupted",
    "outcome_unknown", "cancel_requested", "cancelled", "waiting_for_input",
}
# "running" (Task 12.2): an attempt in flight - recorded *before* its
# capability is called (docs/04: "Record attempts before provider calls"),
# so a crash mid-call leaves a real, inspectable trace rather than nothing.
ATTEMPT_STATUSES = {"succeeded", "failed", "awaiting_human", "running"}
STAGE_KINDS = {"capability", "human_checkpoint"}


class MandateValidationError(Exception):
    pass


class PlanValidationError(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# -- capability registry (code, not data) ----------------------------------


@dataclass
class CapabilityDescriptor:
    name: str
    version: str
    side_effect_class: str  # e.g. "read_only" - docs/04's "side-effect class"
    permission_check: Callable[[str], bool]
    executor: Callable[[str, dict], dict]
    # Task 12.2's minimal budget ledger: a flat cost per call, charged
    # against a Run's own budget_limit before the executor is invoked (see
    # _run_stages). fixture.echo's own value below is nominal - it has no
    # real-money meaning - but the check that enforces it against a Run's
    # budget is real, not a stub.
    unit_cost: float = 0.0
    # Task 14.1: formalizes docs/04's capability-boundary contract
    # verbatim - "Register each capability with: name/version; input
    # schema; output schema; allowed formats..." - as real, enforced
    # fields rather than the ad hoc, capability-name-keyed checks that
    # used to live scattered across _default_input_for_stage and each
    # executor. A minimal, hand-rolled JSON-Schema-shaped dict (object/
    # required/properties/type/items/minItems only) - see
    # _validate_against_schema below; not a general JSON Schema engine,
    # since this app's own schemas never need more than that.
    input_schema: dict = field(default_factory=dict)
    output_schema: dict = field(default_factory=dict)
    # None for a capability with no source documents at all (fixture.echo).
    allowed_source_formats: tuple[str, ...] | None = None


_CAPABILITIES: dict[str, CapabilityDescriptor] = {}


def register_capability(descriptor: CapabilityDescriptor) -> None:
    _CAPABILITIES[descriptor.name] = descriptor


def get_capability(name: str) -> CapabilityDescriptor | None:
    return _CAPABILITIES.get(name)


def _validate_field(value: Any, schema: dict, context: str) -> None:
    expected = schema.get("type")
    if expected == "string":
        if not isinstance(value, str):
            raise PlanValidationError(f"{context}: expected a string")
    elif expected == "array":
        if not isinstance(value, list):
            raise PlanValidationError(f"{context}: expected an array")
        min_items = schema.get("minItems")
        if min_items is not None and len(value) < min_items:
            raise PlanValidationError(f"{context}: expected at least {min_items} item(s)")
        item_schema = schema.get("items")
        if item_schema is not None:
            for i, item in enumerate(value):
                _validate_field(item, item_schema, f"{context}[{i}]")
    elif expected == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise PlanValidationError(f"{context}: expected a number")
    elif expected == "boolean":
        if not isinstance(value, bool):
            raise PlanValidationError(f"{context}: expected a boolean")
    elif expected == "object":
        _validate_against_schema(value, schema, context)
    # No "type" at all (e.g. pinned_versions' free-form value shape) is
    # deliberately unchecked beyond the object/array/string/number/boolean
    # cases above - this validator only pins what this app's own two
    # capabilities actually need, not a general schema language.


def _validate_against_schema(value: Any, schema: dict, context: str) -> None:
    """Task 14.1: the one place every capability's declared input_schema/
    output_schema is actually enforced, not merely documented - see
    CapabilityDescriptor's own docstring comment above. Raises
    PlanValidationError (propose-time) the same way validate_plan_stages
    already does, so an out-of-contract stage input is rejected before a
    run is ever created; called again at execution time in _run_stages
    against output_schema, so an executor whose real return value drifts
    from its own declared contract fails loudly (attempt/run marked
    failed) rather than propagating a malformed shape downstream."""
    if not schema or schema.get("type") != "object":
        return
    if not isinstance(value, dict):
        raise PlanValidationError(f"{context}: expected an object, got {type(value).__name__}")
    for key in schema.get("required", []):
        if key not in value:
            raise PlanValidationError(f"{context}: missing required field {key!r}")
    for key, subschema in schema.get("properties", {}).items():
        if key in value:
            _validate_field(value[key], subschema, f"{context}.{key}")


def _fixture_echo_executor(project_id: str, stage_input: dict) -> dict:
    return {"echoed": str(stage_input.get("message", "")), "processed_at": _now()}


register_capability(
    CapabilityDescriptor(
        name="fixture.echo",
        version="1",
        side_effect_class="read_only",
        permission_check=lambda project_id: True,
        executor=_fixture_echo_executor,
        unit_cost=1.0,
        input_schema={
            "type": "object", "required": ["message"],
            "properties": {"message": {"type": "string"}},
        },
        output_schema={
            "type": "object", "required": ["echoed", "processed_at"],
            "properties": {"echoed": {"type": "string"}, "processed_at": {"type": "string"}},
        },
        allowed_source_formats=None,
    )
)


class ReconciliationInputError(Exception):
    """A stage's own input was invalid for this capability - distinct from
    PlanValidationError (which is about the plan's shape) since this is
    raised at execution time, from data that could only be known once the
    plan actually runs (a document deleted after approval, a version pinned
    at propose-time no longer being current)."""


def _reconciliation_executor(project_id: str, stage_input: dict) -> dict:
    """Task 12.3's real capability adapter: calls the exact same two
    functions the pre-existing, non-mandate reconciliation route
    (server.py's _handle_reconciliation) already calls - cross_format_
    analysis.run_cross_format_analysis (a real, paid Anthropic call) then
    cross_format_analyses.create_cross_format_analysis - so this is a thin
    adapter around tested modules, not a second implementation of
    reconciliation (AGENTS.md: "Reuse tested analytical modules through
    narrow adapters"). workspaces.get_or_create_workspace is the same
    idempotent call the existing static page's "Open deal workspace" link
    already makes - Gate A's "shared findings, no parallel mandate-only
    finding silo" (docs/04) holds because this is literally the same
    finding-materialization path, not a copy of it.

    Enforces the plan's pinned document versions (see _default_input_for_
    stage) at the one point that matters - immediately before the paid
    call - rather than trusting that nothing changed between approval and
    execution: docs/03's "Run / Attempt / InputManifest... pinned sources"
    is checked, not just recorded.
    """
    document_ids = stage_input.get("document_ids") or []
    pinned_versions: dict[str, str] = stage_input.get("pinned_versions") or {}

    selected = []
    for document_id in document_ids:
        document = documents.get_document(project_id, document_id)
        if document is None:
            raise ReconciliationInputError(f"document not found: {document_id!r} (deleted since the plan was approved?)")
        pinned = pinned_versions.get(document_id)
        if pinned is not None and document.current_version_id != pinned:
            raise ReconciliationInputError(
                f"{document.original_filename!r} has a newer version than this plan pinned "
                f"(pinned {pinned}, current {document.current_version_id}) - re-propose the plan "
                "to reconcile against the current version"
            )
        selected.append(document)

    validation_error = cross_format_analysis.validate_selection(selected)
    if validation_error is not None:
        error_type, error_message = validation_error
        raise ReconciliationInputError(f"{error_type}: {error_message}")

    outcome = cross_format_analysis.run_cross_format_analysis(selected)

    pdf_docs = [d for d in selected if d.extension == ".pdf"]
    excel_docs = [d for d in selected if d.extension in (".xlsx", ".xls")]

    record = cross_format_analyses.create_cross_format_analysis(
        project_id=project_id,
        pdf_document_ids=[d.id for d in pdf_docs],
        pdf_document_filenames=[d.original_filename for d in pdf_docs],
        pdf_document_checksums=[d.sha256 for d in pdf_docs],
        excel_document_ids=[d.id for d in excel_docs],
        excel_document_filenames=[d.original_filename for d in excel_docs],
        excel_document_checksums=[d.sha256 for d in excel_docs],
        status="success" if outcome.success else "error",
        transmitted=outcome.transmitted,
        analysis_seconds=outcome.analysis_seconds,
        model=outcome.model,
        mandate_version=cross_format_analysis.MANDATE_VERSION,
        stop_reason=outcome.stop_reason,
        input_tokens=outcome.usage["input_tokens"] if outcome.usage else None,
        output_tokens=outcome.usage["output_tokens"] if outcome.usage else None,
        code_execution_requests=outcome.usage.get("code_execution_requests") if outcome.usage else None,
        error_type=outcome.error_type,
        error_message=outcome.error_message,
        segments=[s.to_dict() for s in outcome.segments] if outcome.segments else None,
        tool_trace=outcome.tool_trace,
        excel_cleanup=[c.to_dict() for c in outcome.excel_cleanup] if outcome.excel_cleanup else None,
        excel_verification=[v.to_dict() for v in outcome.excel_verification] if outcome.excel_verification else None,
    )

    if not outcome.success:
        # The audit record above is persisted regardless (same as the
        # existing non-mandate route) - the failure is real and should
        # fail this attempt/run/mandate, but the record of what was
        # attempted, and why it failed, is not lost.
        raise RuntimeError(f"reconciliation failed (see cross_format_analysis {record.id}): {outcome.error_message}")

    workspace, workspace_created = workspaces.get_or_create_workspace(project_id, record)
    finding_count = len(evaluations.extract_findings(record.segments))

    return {
        "cross_format_analysis_id": record.id,
        "workspace_id": workspace.id,
        "workspace_created": workspace_created,
        "finding_count": finding_count,
        "model": record.model,
        "input_tokens": record.input_tokens,
        "output_tokens": record.output_tokens,
    }


register_capability(
    CapabilityDescriptor(
        name="reconciliation.cross_format",
        version="1",
        side_effect_class="external_paid_call",
        permission_check=lambda project_id: True,
        executor=_reconciliation_executor,
        # Nominal, like fixture.echo's own unit_cost - a real dollar-cost
        # model (from actual token usage) is 12.4/AI-integration territory,
        # not this task's job. The budget-ledger mechanism itself (Task
        # 12.2) is real and enforced against this number regardless.
        unit_cost=1.0,
        # Task 14.1: pins the exact contract this capability has always
        # informally had - see docs/workspace-shift/docs/
        # 12-reconciliation-capability-contract.md for the full formal
        # spec (evidence semantics, outputs, limitations) this schema is
        # drawn from. pinned_versions has no declared "type" deliberately -
        # its values are plain document_id -> version_id strings, already
        # enforced by _default_input_for_stage's own document lookups
        # rather than this generic validator.
        input_schema={
            "type": "object", "required": ["document_ids"],
            "properties": {
                "document_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                "pinned_versions": {"type": "object"},
            },
        },
        output_schema={
            "type": "object",
            "required": [
                "cross_format_analysis_id", "workspace_id", "workspace_created",
                "finding_count", "model",
            ],
            "properties": {
                "cross_format_analysis_id": {"type": "string"},
                "workspace_id": {"type": "string"},
                "workspace_created": {"type": "boolean"},
                "finding_count": {"type": "number"},
                "model": {"type": "string"},
            },
        },
        allowed_source_formats=(".pdf", ".xlsx", ".xls"),
    )
)


class IntegrityReviewInputError(Exception):
    """Task 14.2's analogue of ReconciliationInputError - raised at
    execution time when a plan's pinned target/source/peer version was
    deleted since approval. Unlike reconciliation, there is no "current
    version drifted" case to check here: this capability pins an exact,
    human-chosen SubmissionVersion/DocumentVersion (never "whatever is
    current"), and a version row, once created, is never replaced or
    deleted independently of its parent Document/WorkProduct - so the
    only drift possible is the parent itself having been deleted."""


def _lookup_target_or_peer(
    project_id: str, ref: Any
) -> tuple[work_products.WorkProduct, work_products.SubmissionVersion] | None:
    """Resolves a `{work_product_id, version_id}` reference against the
    real, current project state - used for both the target submission and
    any peer submissions, which share the exact same shape. Returns None
    on any failure (unknown/forged id, cross-project id, deleted parent)
    rather than raising, so propose-time and execution-time callers can
    each wrap the failure in whatever exception fits their own moment."""
    if not isinstance(ref, dict):
        return None
    work_product = work_products.get_work_product(project_id, str(ref.get("work_product_id", "")))
    if work_product is None:
        return None
    version = work_products.get_version(work_product.id, str(ref.get("version_id", "")))
    if version is None:
        return None
    return work_product, version


def _lookup_source(project_id: str, ref: Any) -> tuple[documents.Document, documents.DocumentVersion] | None:
    if not isinstance(ref, dict):
        return None
    document = documents.get_document(project_id, str(ref.get("document_id", "")))
    if document is None:
        return None
    version = documents.get_version(document.id, str(ref.get("version_id", "")))
    if version is None:
        return None
    return document, version


def _build_integrity_review_context(project_id: str, stage_input: dict, error_cls: type[Exception]) -> str:
    """Assembles the plain-text review context sent to the model - pinned
    brief fields and the workstream name, if selected, plus the
    reviewer's own stated scope. Raises `error_cls` if a pinned
    brief_version_id/workstream_id no longer resolves (deleted since
    approval) - the same "re-verify every identifier independently"
    discipline as every other lookup in this capability."""
    parts = []
    brief_version_id = stage_input.get("brief_version_id")
    if brief_version_id:
        brief = deal_briefs.get_version(project_id, brief_version_id)
        if brief is None:
            raise error_cls(f"brief version not found: {brief_version_id!r} (deleted since the plan was approved?)")
        brief_lines = [
            f"{field.capitalize()}: {getattr(brief, field)}"
            for field in deal_briefs.BRIEF_FIELDS
            if getattr(brief, field)
        ]
        if brief_lines:
            parts.append("Deal brief:\n" + "\n".join(brief_lines))
    workstream_id = stage_input.get("workstream_id")
    if workstream_id:
        workstream = workstreams.get_workstream(project_id, workstream_id)
        if workstream is None:
            raise error_cls(f"workstream not found: {workstream_id!r} (deleted since the plan was approved?)")
        parts.append(f"Workstream: {workstream.name}")
    review_scope = str(stage_input.get("review_scope", "") or "")
    if review_scope.strip():
        parts.append(f"Reviewer's stated scope: {review_scope.strip()}")
    return "\n\n".join(parts)


def _integrity_review_executor(project_id: str, stage_input: dict) -> dict:
    """Task 14.2's real capability adapter: independently re-resolves
    every identifier in the plan's pinned input against the real, current
    project state (never trusts the plan's own copy of a filename or
    title), builds the exact Selection objects integrity_review.py's pure
    adapter needs, persists the audit record and every candidate exactly
    as produced (never auto-published - see integrity_reviews.py's own
    module docstring), and materializes an (initially empty) shared
    workspace ready to receive published findings once a human accepts a
    candidate."""
    target_ref = stage_input["target"]
    resolved_target = _lookup_target_or_peer(project_id, target_ref)
    if resolved_target is None:
        raise IntegrityReviewInputError(
            f"target submission version not found: {target_ref!r} (deleted since the plan was approved?)"
        )
    target_work_product, target_version = resolved_target
    target = integrity_review.TargetSelection(work_product=target_work_product, version=target_version)

    sources = []
    for doc_ref in stage_input.get("documents", []):
        resolved_source = _lookup_source(project_id, doc_ref)
        if resolved_source is None:
            raise IntegrityReviewInputError(
                f"source document version not found: {doc_ref!r} (deleted since the plan was approved?)"
            )
        document, doc_version = resolved_source
        sources.append(integrity_review.SourceSelection(document=document, version=doc_version))

    peers = []
    for peer_ref in stage_input.get("peers", []):
        resolved_peer = _lookup_target_or_peer(project_id, peer_ref)
        if resolved_peer is None:
            raise IntegrityReviewInputError(
                f"peer submission version not found: {peer_ref!r} (deleted since the plan was approved?)"
            )
        peer_work_product, peer_version = resolved_peer
        peers.append(integrity_review.PeerSelection(work_product=peer_work_product, version=peer_version))

    validation_error = integrity_review.validate_selection(target, sources, peers)
    if validation_error is not None:
        error_type, error_message = validation_error
        raise IntegrityReviewInputError(f"{error_type}: {error_message}")

    review_context = _build_integrity_review_context(project_id, stage_input, IntegrityReviewInputError)
    outcome = integrity_review.run_integrity_review(target, sources, peers, review_context)

    record = integrity_reviews.create_integrity_review(
        project_id=project_id,
        # Task 14.2 lineage fix (found live, during this task's own real
        # paid proof run - see STATUS.md): _run_stages injects these three
        # reserved keys into a local copy of the stage input at execution
        # time only (never at propose time, since no Run/Attempt exists
        # yet then) - satisfies the spec's own "Published findings
        # identify: Originating mandate/run/attempt" requirement.
        mandate_id=stage_input.get("_mandate_id"), run_id=stage_input.get("_run_id"),
        attempt_id=stage_input.get("_attempt_id"),
        target_work_product_id=target_work_product.id, target_version_id=target_version.id,
        source_document_ids=[s.document.id for s in sources], source_version_ids=[s.version.id for s in sources],
        peer_work_product_ids=[p.work_product.id for p in peers], peer_version_ids=[p.version.id for p in peers],
        brief_version_id=stage_input.get("brief_version_id"), workstream_id=stage_input.get("workstream_id"),
        review_scope=str(stage_input.get("review_scope", "") or ""),
        status="success" if outcome.success else "error", transmitted=outcome.transmitted,
        analysis_seconds=outcome.analysis_seconds, model=outcome.model,
        review_template_version=integrity_review.REVIEW_TEMPLATE_VERSION, stop_reason=outcome.stop_reason,
        input_tokens=outcome.usage["input_tokens"] if outcome.usage else None,
        output_tokens=outcome.usage["output_tokens"] if outcome.usage else None,
        code_execution_requests=outcome.usage.get("code_execution_requests") if outcome.usage else None,
        error_type=outcome.error_type, error_message=outcome.error_message,
        materials_reviewed_text=outcome.materials_reviewed_text, tool_trace=outcome.tool_trace,
        excel_cleanup=[c.to_dict() for c in outcome.excel_cleanup] if outcome.excel_cleanup else None,
        excel_verification=[v.to_dict() for v in outcome.excel_verification] if outcome.excel_verification else None,
    )

    if not outcome.success:
        # Audit record persisted above regardless (same as reconciliation's
        # own pattern) - the failure is real and should fail this
        # attempt/run/mandate, but the record of what was attempted, and
        # why it failed, is not lost.
        raise RuntimeError(f"integrity review failed (see integrity_review {record.id}): {outcome.error_message}")

    candidate_dicts = [c.to_dict() for c in (outcome.candidates or [])]
    candidates = integrity_reviews.create_candidates(record.id, candidate_dicts)
    workspace, workspace_created = workspaces.get_or_create_workspace_for_integrity_review(project_id, record.id)

    return {
        "integrity_review_id": record.id,
        "workspace_id": workspace.id,
        "workspace_created": workspace_created,
        "candidate_count": len(candidates),
        "model": record.model,
    }


_INTEGRITY_REVIEW_REF_SCHEMA = {
    "type": "object", "required": ["work_product_id", "version_id"],
    "properties": {"work_product_id": {"type": "string"}, "version_id": {"type": "string"}},
}
_INTEGRITY_REVIEW_DOCUMENT_REF_SCHEMA = {
    "type": "object", "required": ["document_id", "version_id"],
    "properties": {"document_id": {"type": "string"}, "version_id": {"type": "string"}},
}

register_capability(
    CapabilityDescriptor(
        name="integrity.review_work_product",
        version="1",
        side_effect_class="external_paid_call",
        permission_check=lambda project_id: True,
        executor=_integrity_review_executor,
        unit_cost=1.0,
        # Task 14.2: unlike reconciliation.cross_format's flat
        # document_ids list, this capability pins an exact *version* per
        # reference (docs/workspace-shift/integrations/
        # workspace-integrity-integration-v1.0.0/05-task-14.2-integrity-
        # review.md: "The UI must make exact version selection visible") -
        # a human picks specific SubmissionVersion/DocumentVersion ids,
        # never "whatever is current," so there is no server-side
        # "pin to current" step the way reconciliation's own
        # _default_input_for_stage performs.
        input_schema={
            "type": "object", "required": ["target", "documents"],
            "properties": {
                "target": _INTEGRITY_REVIEW_REF_SCHEMA,
                "documents": {"type": "array", "items": _INTEGRITY_REVIEW_DOCUMENT_REF_SCHEMA, "minItems": 1},
                "peers": {"type": "array", "items": _INTEGRITY_REVIEW_REF_SCHEMA},
                "brief_version_id": {"type": "string"},
                "workstream_id": {"type": "string"},
                "review_scope": {"type": "string"},
            },
        },
        output_schema={
            "type": "object",
            "required": ["integrity_review_id", "workspace_id", "workspace_created", "candidate_count", "model"],
            "properties": {
                "integrity_review_id": {"type": "string"},
                "workspace_id": {"type": "string"},
                "workspace_created": {"type": "boolean"},
                "candidate_count": {"type": "number"},
                "model": {"type": "string"},
            },
        },
        # The target submission and any peer submissions must be PDF
        # (this capability's own v1 scope boundary); source documents may
        # be PDF or Excel, exactly like reconciliation - see
        # integrity_review.py's own module docstring for why this single
        # flat tuple undersells the real, per-role restriction actually
        # enforced by integrity_review.validate_selection.
        allowed_source_formats=(".pdf", ".xlsx", ".xls"),
    )
)


# -- template registry (code, not data) -------------------------------------


@dataclass
class Template:
    key: str
    version: int
    name: str
    description: str
    stages: list[dict]  # blueprint: id, capability|kind, depends_on, outputs

    def to_dict(self) -> dict:
        return {
            "key": self.key, "version": self.version, "name": self.name,
            "description": self.description, "stages": self.stages,
        }


_TEMPLATES: dict[str, Template] = {}


def register_template(template: Template) -> None:
    _TEMPLATES[template.key] = template


def list_templates() -> list[Template]:
    return list(_TEMPLATES.values())


def get_template(key: str) -> Template | None:
    return _TEMPLATES.get(key)


register_template(
    Template(
        key="fixture-echo",
        version=1,
        name="Fixture echo (single stage)",
        description=(
            "One capability stage that echoes the mandate's objective back. "
            "Proves the runtime end to end; registers no real analytical capability."
        ),
        stages=[
            {"id": "echo", "kind": "capability", "capability": "fixture.echo", "depends_on": [], "outputs": ["echoed_message"]},
        ],
    )
)

register_template(
    Template(
        key="fixture-echo-with-review",
        version=1,
        name="Fixture echo with human review",
        description=(
            "Adds a human checkpoint after the echo stage - proves the "
            "'sequential steps and human waits' runtime shape from "
            "docs/04-mandate-engine.md, including resuming a run after a "
            "human decision."
        ),
        stages=[
            {"id": "echo", "kind": "capability", "capability": "fixture.echo", "depends_on": [], "outputs": ["echoed_message"]},
            {"id": "review", "kind": "human_checkpoint", "depends_on": ["echo"], "outputs": ["review_decision"]},
        ],
    )
)

register_template(
    Template(
        key="reconciliation",
        version=1,
        name="Cross-format reconciliation (PDF + Excel)",
        description=(
            "Task 12.3/Gate A: reconciles a selected group of original PDFs "
            "against Excel workbooks via the same real, paid Anthropic call "
            "the existing static reconciliation page uses - a real "
            "analytical capability, not a fixture. Requires document_ids "
            "(at least one PDF, one Excel) supplied at propose time; see "
            "propose_plan's stage_inputs parameter."
        ),
        stages=[
            {
                "id": "reconcile", "kind": "capability", "capability": "reconciliation.cross_format",
                "depends_on": [], "outputs": ["cross_format_analysis_id", "workspace_id"],
            },
        ],
    )
)

register_template(
    Template(
        key="reconciliation-with-review",
        version=1,
        name="Cross-format reconciliation with human review",
        description=(
            "Task 12.5 (reuse proof): the exact same reconciliation.cross_format "
            "capability as the plain 'reconciliation' template - no new capability, "
            "no new executor - followed by a human_checkpoint so the mandate is "
            "not marked complete until a reviewer has actually looked at the "
            "findings the run just produced and recorded a decision. This is the "
            "'reconcile -> review' portion of examples/reconciliation-template.json's "
            "own illustrative pipeline, made real; 'draft' and 'approve' stay "
            "aspirational since draft_from_reviewed_findings does not exist as a "
            "capability yet (a separate, unauthorized future task). Prefer the "
            "plain 'reconciliation' template when the objective has no explicit "
            "need for an in-mandate review gate beyond the shared workspace's own "
            "review tools; prefer this one when it does."
        ),
        stages=[
            {
                "id": "reconcile", "kind": "capability", "capability": "reconciliation.cross_format",
                "depends_on": [], "outputs": ["cross_format_analysis_id", "workspace_id"],
            },
            {"id": "review", "kind": "human_checkpoint", "depends_on": ["reconcile"], "outputs": ["review_decision"]},
        ],
    )
)

register_template(
    Template(
        key="integrity-review",
        version=1,
        name="Work-product Integrity Review",
        description=(
            "Task 14.2: reviews one immutable analyst SubmissionVersion "
            "against selected source-evidence DocumentVersions and, "
            "optionally, peer SubmissionVersions, proposing candidate "
            "integrity challenges - never authorized here as a "
            "reconciliation-style automatic finding. The human_checkpoint "
            "stage marks the mandate reviewed only once a human has "
            "worked through the candidates via the dedicated candidate-"
            "decision endpoints (accept/reject/edit/link-duplicate/leave-"
            "unresolved); accepted candidates publish into the same "
            "shared workspace findings register reconciliation already "
            "uses, with origin 'integrity' and full version/mandate "
            "lineage. Proposed manually only (stage_inputs, exact version "
            "ids) - never by the LLM planner; see mandates.py's own "
            "_TEMPLATES_EXCLUDED_FROM_LLM_PLANNING for why."
        ),
        stages=[
            {
                "id": "review", "kind": "capability", "capability": "integrity.review_work_product",
                "depends_on": [], "outputs": ["integrity_review_id", "workspace_id"],
            },
            {"id": "checkpoint", "kind": "human_checkpoint", "depends_on": ["review"], "outputs": ["review_decision"]},
        ],
    )
)


# Capabilities whose stage input is a source document selection, not
# something derivable purely from the mandate's objective - Task 12.4's
# planner (propose_plan_llm) needs to know which capabilities these are so
# it knows when a model-proposed plan must name document_ids at all, and
# which stage id to attach them to. Keyed by capability name rather than
# template key, matching _default_input_for_stage's own dispatch below.
# integrity.review_work_product is deliberately absent - see
# _TEMPLATES_EXCLUDED_FROM_LLM_PLANNING below, not this set.
_CAPABILITIES_NEEDING_DOCUMENT_SELECTION = {"reconciliation.cross_format"}

# Task 14.2: templates never offered to the LLM planner at all - the
# M14.2 spec's own "The planner may propose this pipeline, but it may
# not authorize new sources, expand access, or skip the human
# publication checkpoint" and "exact version selection visible" are a
# human-UI job (a specific SubmissionVersion/DocumentVersion/peer
# selection, not "whatever document the model thinks looks relevant"),
# not something reconciliation's own document_ids-only planner support
# generalizes to safely. A model that somehow still proposed this
# template would simply see its own plan rejected as unsupported (empty
# stage_inputs fails this capability's own input_schema) rather than
# anything unsafe - this set only avoids offering a template the planner
# cannot use well in the first place.
_TEMPLATES_EXCLUDED_FROM_LLM_PLANNING = {"integrity-review"}


def _document_selection_stage(template: Template) -> dict | None:
    """The one stage in `template` (if any) whose capability needs an
    explicit document selection - see _CAPABILITIES_NEEDING_DOCUMENT_SELECTION.
    Every registered template today has at most one such stage; this
    returns the first, which is exactly all any caller today needs."""
    for stage in template.stages:
        if stage.get("capability") in _CAPABILITIES_NEEDING_DOCUMENT_SELECTION:
            return stage
    return None


def _default_input_for_stage(stage: dict, mandate: "Mandate", stage_inputs: dict[str, dict] | None) -> dict:
    """Fills a capability stage's input. For fixture.echo, purely derived
    from the mandate (a placeholder standing in for what a real planner
    would derive from selected sources/context - trivial, since that
    capability takes one field). For the real reconciliation capability,
    there is still no *code-level* derivation of a source selection - a
    human supplies document_ids explicitly via `stage_inputs` (manual
    proposal), or Task 12.4's `propose_plan_llm` derives them from a real
    model call and passes them through this exact same `stage_inputs`
    parameter, so this function - and the validation/pinning it does below -
    is identical either way; a model-proposed selection gets no separate,
    laxer path. This function pins each document id to its *current*
    DocumentVersion at propose time (docs/03's "Run / Attempt /
    InputManifest... pinned sources") - enforced later, at execution, by
    _reconciliation_executor."""
    capability = stage.get("capability")
    if capability == "fixture.echo":
        return {"message": mandate.objective}

    if capability == "reconciliation.cross_format":
        provided = (stage_inputs or {}).get(stage["id"]) or {}
        descriptor = get_capability(capability)
        assert descriptor is not None  # validate_plan_stages already confirmed this is registered
        # Task 14.1: the capability's own declared input_schema is what
        # enforces "a non-empty document_ids list of strings" now - not a
        # hand-written check specific to this one capability's name.
        _validate_against_schema(
            provided, descriptor.input_schema, f"stage {stage['id']!r} ({capability}) input"
        )
        document_ids = provided["document_ids"]
        pinned_versions: dict[str, str] = {}
        for document_id in document_ids:
            document = documents.get_document(mandate.project_id, document_id)
            if document is None:
                raise PlanValidationError(f"document not found: {document_id!r}")
            if document.current_version_id is not None:
                pinned_versions[document_id] = document.current_version_id
        return {"document_ids": document_ids, "pinned_versions": pinned_versions}

    if capability == "integrity.review_work_product":
        provided = (stage_inputs or {}).get(stage["id"]) or {}
        descriptor = get_capability(capability)
        assert descriptor is not None
        # Task 14.2: unlike reconciliation, there is no "pin to current
        # version" step here at all - the human already named an exact
        # SubmissionVersion/DocumentVersion in `provided` (the M14.2
        # spec's own "exact version selection visible" requirement), so
        # this function's only job is to verify every referenced id is
        # real, in this project, before the plan is ever approved -
        # never to silently substitute or derive one.
        _validate_against_schema(
            provided, descriptor.input_schema, f"stage {stage['id']!r} ({capability}) input"
        )
        if _lookup_target_or_peer(mandate.project_id, provided["target"]) is None:
            raise PlanValidationError(f"target submission version not found: {provided['target']!r}")
        for doc_ref in provided["documents"]:
            if _lookup_source(mandate.project_id, doc_ref) is None:
                raise PlanValidationError(f"source document version not found: {doc_ref!r}")
        for peer_ref in provided.get("peers", []):
            if _lookup_target_or_peer(mandate.project_id, peer_ref) is None:
                raise PlanValidationError(f"peer submission version not found: {peer_ref!r}")
        # Re-verifies brief_version_id/workstream_id too, so an approved
        # plan can never reference a context record that never existed -
        # the error is raised here (PlanValidationError), not deferred.
        _build_integrity_review_context(mandate.project_id, provided, PlanValidationError)
        return {
            "target": provided["target"],
            "documents": provided["documents"],
            "peers": provided.get("peers", []),
            "brief_version_id": provided.get("brief_version_id"),
            "workstream_id": provided.get("workstream_id"),
            "review_scope": str(provided.get("review_scope", "") or ""),
        }

    return {}


def validate_plan_stages(stages: list[dict]) -> None:
    """Model-proposed plans are untrusted (docs/04) - this same validator
    runs for the deterministic fixture planner too, so the mechanism is
    proven before 12.4 ever needs to trust it with real model output.
    Enforces: stable, unique stage ids; a known stage kind; a registered
    capability for capability stages; and dependencies that only ever
    reference an earlier stage in the list - the "sequential steps, no
    DAG editor" runtime shape from docs/04, checked structurally rather
    than merely asserted in a comment."""
    seen_ids: set[str] = set()
    for stage in stages:
        stage_id = stage.get("id")
        if not stage_id or not isinstance(stage_id, str) or stage_id in seen_ids:
            raise PlanValidationError(f"duplicate or missing stage id: {stage_id!r}")

        kind = stage.get("kind", "capability")
        if kind not in STAGE_KINDS:
            raise PlanValidationError(f"invalid stage kind: {kind!r}")

        if kind == "capability":
            capability = stage.get("capability")
            if not capability or get_capability(capability) is None:
                raise PlanValidationError(f"unregistered capability: {capability!r}")

        for dep in stage.get("depends_on", []):
            if dep not in seen_ids:
                raise PlanValidationError(
                    f"stage {stage_id!r} depends on unknown or non-earlier stage {dep!r}"
                )

        seen_ids.add(stage_id)


# -- persisted dataclasses ---------------------------------------------------


@dataclass
class Mandate:
    id: str
    project_id: str
    objective: str
    status: str
    current_plan_id: str | None
    created_at: str
    updated_at: str
    created_by: str | None

    def to_dict(self) -> dict:
        return {
            "id": self.id, "project_id": self.project_id, "objective": self.objective,
            "status": self.status, "current_plan_id": self.current_plan_id,
            "created_at": self.created_at, "updated_at": self.updated_at,
            "created_by": self.created_by,
        }


@dataclass
class PlanRevision:
    id: str
    mandate_id: str
    revision_number: int
    status: str
    template_key: str | None
    stages: list[dict]
    created_at: str
    approved_at: str | None
    approved_by: str | None
    # Task 12.4: which planner produced this revision, and (for "llm") the
    # model's own stated rationale - shown to the human approver so
    # "reviewed outputs" (docs/04) means something for a model-proposed
    # plan, not just a fixture/human one. Additive; every plan before this
    # task defaults to "human" (see init_mandates_db's migration below).
    proposed_by: str = "human"
    planner_reasoning: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id, "mandate_id": self.mandate_id, "revision_number": self.revision_number,
            "status": self.status, "template_key": self.template_key, "stages": self.stages,
            "created_at": self.created_at, "approved_at": self.approved_at, "approved_by": self.approved_by,
            "proposed_by": self.proposed_by, "planner_reasoning": self.planner_reasoning,
        }


@dataclass
class Run:
    id: str
    mandate_id: str
    plan_revision_id: str
    status: str
    queued_at: str | None  # Task 12.2: set when execute_run/resume_run persist and hand off to the Worker
    started_at: str | None  # set when the Worker actually begins executing (may be well after queued_at)
    finished_at: str | None
    current_stage_index: int  # Task 12.2: next stage to (re)run - what Worker.recover() resumes from
    budget_limit: float | None  # Task 12.2: None means unlimited
    budget_consumed: float

    def to_dict(self) -> dict:
        return {
            "id": self.id, "mandate_id": self.mandate_id, "plan_revision_id": self.plan_revision_id,
            "status": self.status, "queued_at": self.queued_at, "started_at": self.started_at,
            "finished_at": self.finished_at, "current_stage_index": self.current_stage_index,
            "budget_limit": self.budget_limit, "budget_consumed": self.budget_consumed,
        }


@dataclass
class Attempt:
    id: str
    run_id: str
    stage_id: str
    capability: str | None
    status: str
    started_at: str
    finished_at: str | None
    output: dict | None
    error: str | None

    def to_dict(self) -> dict:
        return {
            "id": self.id, "run_id": self.run_id, "stage_id": self.stage_id,
            "capability": self.capability, "status": self.status,
            "started_at": self.started_at, "finished_at": self.finished_at,
            "output": self.output, "error": self.error,
        }


# -- schema -------------------------------------------------------------


def init_mandates_db() -> None:
    conn = store.get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mandates (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                objective TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                current_plan_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_by TEXT
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mandates_project ON mandates(project_id)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS plan_revisions (
                id TEXT PRIMARY KEY,
                mandate_id TEXT NOT NULL,
                revision_number INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'proposed',
                template_key TEXT,
                stages_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                approved_at TEXT,
                approved_by TEXT,
                proposed_by TEXT NOT NULL DEFAULT 'human',
                planner_reasoning TEXT
            )
            """
        )
        # Task 12.4, additive migration for a database created under Task
        # 12.1/12.3 (this codebase's real Postgres install already has real
        # plan_revisions rows from those tasks' own live verification) - the
        # CREATE TABLE above already includes these columns for a fresh
        # install, so these are no-ops there.
        conn.execute("ALTER TABLE plan_revisions ADD COLUMN IF NOT EXISTS proposed_by TEXT NOT NULL DEFAULT 'human'")
        conn.execute("ALTER TABLE plan_revisions ADD COLUMN IF NOT EXISTS planner_reasoning TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_plan_revisions_mandate ON plan_revisions(mandate_id)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mandate_runs (
                id TEXT PRIMARY KEY,
                mandate_id TEXT NOT NULL,
                plan_revision_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                queued_at TEXT,
                started_at TEXT,
                finished_at TEXT,
                current_stage_index INTEGER NOT NULL DEFAULT 0,
                budget_limit REAL,
                budget_consumed REAL NOT NULL DEFAULT 0
            )
            """
        )
        # Task 12.2, additive migration for a database created under Task
        # 12.1 (this codebase's real Postgres install already has two real
        # runs from 12.1's own live verification) - CREATE TABLE above
        # already includes these columns for a fresh install, so these are
        # no-ops there; ADD COLUMN IF NOT EXISTS is the idempotent,
        # native-Postgres equivalent of the PRAGMA-guarded ALTERs earlier
        # tasks (e.g. workspaces.py) used under SQLite.
        conn.execute("ALTER TABLE mandate_runs ADD COLUMN IF NOT EXISTS queued_at TEXT")
        conn.execute("ALTER TABLE mandate_runs ADD COLUMN IF NOT EXISTS current_stage_index INTEGER NOT NULL DEFAULT 0")
        conn.execute("ALTER TABLE mandate_runs ADD COLUMN IF NOT EXISTS budget_limit REAL")
        conn.execute("ALTER TABLE mandate_runs ADD COLUMN IF NOT EXISTS budget_consumed REAL NOT NULL DEFAULT 0")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mandate_runs_mandate ON mandate_runs(mandate_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mandate_runs_status ON mandate_runs(status)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mandate_attempts (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                stage_id TEXT NOT NULL,
                capability TEXT,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                output_json TEXT,
                error TEXT
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mandate_attempts_run ON mandate_attempts(run_id)")
        conn.commit()
    finally:
        conn.close()


# -- mandates -----------------------------------------------------------


def _row_to_mandate(row) -> Mandate:
    return Mandate(
        row["id"], row["project_id"], row["objective"], row["status"],
        row["current_plan_id"], row["created_at"], row["updated_at"], row["created_by"],
    )


def create_mandate(project_id: str, objective: str, created_by: str | None) -> Mandate:
    objective = objective.strip()
    if not objective:
        raise MandateValidationError("objective is required")
    now = _now()
    mandate = Mandate(
        id=uuid.uuid4().hex, project_id=project_id, objective=objective, status="draft",
        current_plan_id=None, created_at=now, updated_at=now, created_by=created_by,
    )
    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO mandates (id, project_id, objective, status, current_plan_id, created_at, updated_at, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (mandate.id, mandate.project_id, mandate.objective, mandate.status, mandate.current_plan_id,
             mandate.created_at, mandate.updated_at, mandate.created_by),
        )
        conn.commit()
    finally:
        conn.close()
    return mandate


def list_mandates(project_id: str) -> list[Mandate]:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM mandates WHERE project_id = %s ORDER BY created_at DESC", (project_id,)
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_mandate(r) for r in rows]


def get_mandate(project_id: str, mandate_id: str) -> Mandate | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM mandates WHERE project_id = %s AND id = %s", (project_id, mandate_id)
        ).fetchone()
    finally:
        conn.close()
    return _row_to_mandate(row) if row else None


def _set_mandate(mandate_id: str, **fields: Any) -> None:
    fields["updated_at"] = _now()
    set_clause = ", ".join(f"{k} = %s" for k in fields)
    conn = store.get_connection()
    try:
        conn.execute(f"UPDATE mandates SET {set_clause} WHERE id = %s", (*fields.values(), mandate_id))
        conn.commit()
    finally:
        conn.close()


# -- plans ----------------------------------------------------------------


def _row_to_plan(row) -> PlanRevision:
    return PlanRevision(
        row["id"], row["mandate_id"], row["revision_number"], row["status"], row["template_key"],
        json.loads(row["stages_json"]), row["created_at"], row["approved_at"], row["approved_by"],
        proposed_by=row["proposed_by"], planner_reasoning=row["planner_reasoning"],
    )


def get_plan(mandate_id: str, plan_id: str) -> PlanRevision | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM plan_revisions WHERE mandate_id = %s AND id = %s", (mandate_id, plan_id)
        ).fetchone()
    finally:
        conn.close()
    return _row_to_plan(row) if row else None


def list_plans(mandate_id: str) -> list[PlanRevision]:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM plan_revisions WHERE mandate_id = %s ORDER BY revision_number ASC", (mandate_id,)
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_plan(r) for r in rows]


def propose_plan(
    project_id: str, mandate_id: str, template_key: str, stage_inputs: dict[str, dict] | None = None,
    proposed_by: str = "human", planner_reasoning: str | None = None,
) -> PlanRevision:
    """Instantiates one of the built-in templates and runs the untrusted-plan
    validator every plan - fixture, manually-selected, or (Task 12.4) an
    LLM's own candidate - must pass before a `PlanRevision` is persisted.

    `stage_inputs` (optional): explicit input for a stage whose capability
    can't derive its own input purely from the mandate (today:
    reconciliation.cross_format's document_ids - see
    _default_input_for_stage). Ignored by any stage that doesn't need it.
    Supplied either by a human directly (the manual proposal flow) or by
    `propose_plan_llm` after independently re-verifying a model's candidate
    selection - this function itself never distinguishes the two, which is
    exactly the point: there is one validation path, not two.

    `proposed_by`/`planner_reasoning` (Task 12.4): recorded on the
    resulting `PlanRevision` purely for the human approver's own
    transparency (docs/04: plans are "reviewed outputs", not a black box) -
    neither field affects validation, execution, or the approval gate in
    any way; `approve_plan` doesn't even look at them."""
    mandate = get_mandate(project_id, mandate_id)
    if mandate is None:
        raise ValueError("mandate not found")
    if mandate.status not in ("draft", "awaiting_approval"):
        raise MandateValidationError(f"cannot propose a plan while mandate status is {mandate.status!r}")

    template = get_template(template_key)
    if template is None:
        raise PlanValidationError(f"unknown template: {template_key!r}")

    stages = []
    for blueprint_stage in template.stages:
        stage = dict(blueprint_stage)
        if stage.get("kind", "capability") == "capability":
            stage["input"] = _default_input_for_stage(stage, mandate, stage_inputs)
        stages.append(stage)
    validate_plan_stages(stages)

    existing = list_plans(mandate_id)
    revision_number = (existing[-1].revision_number + 1) if existing else 1
    # A newly proposed revision supersedes whatever the prior current one
    # was - mirrors D06/docs/03-domain-model.md's "editing creates a draft
    # successor" shape used elsewhere in this app (e.g. answer_keys.py).
    for prior in existing:
        if prior.status == "proposed":
            _set_plan(prior.id, status="superseded")

    now = _now()
    plan = PlanRevision(
        id=uuid.uuid4().hex, mandate_id=mandate_id, revision_number=revision_number, status="proposed",
        template_key=template_key, stages=stages, created_at=now, approved_at=None, approved_by=None,
        proposed_by=proposed_by, planner_reasoning=planner_reasoning,
    )
    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO plan_revisions
                (id, mandate_id, revision_number, status, template_key, stages_json, created_at,
                 proposed_by, planner_reasoning)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (plan.id, plan.mandate_id, plan.revision_number, plan.status, plan.template_key,
             json.dumps(plan.stages), plan.created_at, plan.proposed_by, plan.planner_reasoning),
        )
        conn.commit()
    finally:
        conn.close()
    _set_mandate(mandate_id, status="awaiting_approval")
    return plan


def _set_plan(plan_id: str, **fields: Any) -> None:
    set_clause = ", ".join(f"{k} = %s" for k in fields)
    conn = store.get_connection()
    try:
        conn.execute(f"UPDATE plan_revisions SET {set_clause} WHERE id = %s", (*fields.values(), plan_id))
        conn.commit()
    finally:
        conn.close()


# -- LLM planning (Task 12.4) --------------------------------------------


@dataclass
class LlmPlanProposalResult:
    """The outcome of asking a real model to propose a plan.
    `status == "proposed"`: `plan` is a real, persisted `PlanRevision` -
    exactly as untrusted-until-approved as any manually-proposed one (see
    propose_plan_llm's own docstring). `status == "unsupported"`: the model
    itself declined to guess, or this function's own independent checks
    rejected its candidate - no `PlanRevision` was created; `reason`
    explains why, `reasoning` (when present) is the model's own stated
    rationale regardless. `status == "error"`: the planning call itself
    failed (missing key, rate limit, a malformed reply, ...) - distinct
    from "unsupported", which is a considered planning judgment, not a
    failure."""

    status: str
    plan: PlanRevision | None = None
    reasoning: str | None = None
    reason: str | None = None
    model: str | None = None
    usage: dict | None = None

    def to_dict(self) -> dict:
        out: dict[str, Any] = {
            "status": self.status, "plan": self.plan.to_dict() if self.plan else None,
            "reasoning": self.reasoning, "reason": self.reason, "model": self.model, "usage": self.usage,
        }
        if self.status == "error":
            # jsonOrThrow-style clients (frontend/src/lib/api.ts) surface
            # body.error as the thrown message - see server.py's
            # _handle_propose_plan_llm, which sends this dict verbatim.
            out["error"] = self.reason
        return out


def propose_plan_llm(project_id: str, mandate_id: str, feedback: str | None = None) -> LlmPlanProposalResult:
    """Task 12.4: LLM planning over the registered capabilities - the human
    no longer has to hand-pick a template or (for reconciliation) a source
    document pair; a real model proposes both from the mandate's objective,
    the project's real document inventory, and its brief (docs/04: "Start
    with authorized brief and document manifest").

    The model's reply (`mandate_planning.propose_candidate_plan`) is
    untrusted in exactly the sense docs/04's Plan contract describes -
    "Model-proposed plans are untrusted. Validate schemas, capability
    names, source access, dependencies, limits and approval rules." -
    which this function enforces at two layers:

    1. Independently, here, before anything else: every document id the
       model named is re-looked-up with `documents.get_document(project_id,
       ...)` - the same project-scoped lookup every other part of this app
       uses - so a hallucinated id, or a real id belonging to a *different*
       project, resolves to None and rejects the whole candidate (never
       silently dropped and the rest kept - a partial, silently-edited
       selection is exactly the kind of "best-guess plan silently
       submitted" this task must not produce). The resolved documents are
       then run through `cross_format_analysis.validate_selection` (the
       same structural PDF/Excel-mix check the real capability's own
       executor uses) *before* any PlanRevision is created - not deferred
       to execution time.
    2. Then, unconditionally, by handing the (now independently verified)
       template key and stage_inputs to the *exact same* `propose_plan` a
       human's manual proposal already goes through - `validate_plan_stages`
       runs again there, unchanged, on this input like any other.

    A candidate that fails either layer - the model's own status was
    "unsupported", it named an unregistered template, it named a document
    outside this project, or its selection doesn't form a valid PDF/Excel
    pair - comes back as `LlmPlanProposalResult(status="unsupported")`
    with a specific `reason`. No `PlanRevision` is created in that case:
    displaying unavailable work as unsupported (docs/04) means exactly
    that - nothing gets silently submitted for a human to rubber-stamp.

    This function only ever creates a "proposed" plan revision - the same
    state a manual proposal starts in. It never calls `approve_plan`,
    never touches a run, and never resolves a human_checkpoint attempt: the
    model cannot mark its own human checkpoints approved, because nothing
    in this function's call graph can reach that gate at all.

    `feedback` (optional): free text from a human who reviewed a prior
    proposal and wants a different one (docs/04: "AI can request
    adaptation... Record a new plan revision"). Passed straight through to
    the model as context; a second call with feedback is otherwise
    identical to the first, including going through `propose_plan` again -
    which means it creates a brand new `PlanRevision` (a new
    `revision_number`) and marks whatever was previously `proposed`
    `superseded`, exactly like any other re-proposal. The prior revision
    row itself is never mutated - docs/03's revision-counter pattern,
    unchanged for this new caller."""
    mandate = get_mandate(project_id, mandate_id)
    if mandate is None:
        raise ValueError("mandate not found")
    if mandate.status not in ("draft", "awaiting_approval"):
        raise MandateValidationError(f"cannot propose a plan while mandate status is {mandate.status!r}")

    doc_summaries = [
        mandate_planning.DocumentSummary(id=d.id, original_filename=d.original_filename, extension=d.extension)
        for d in documents.list_documents(project_id)
    ]
    template_summaries = [
        mandate_planning.TemplateSummary(
            key=t.key, name=t.name, description=t.description,
            needs_documents=_document_selection_stage(t) is not None,
        )
        for t in list_templates()
        if t.key not in _TEMPLATES_EXCLUDED_FROM_LLM_PLANNING
    ]
    brief = deal_briefs.get_current_version(project_id)

    outcome = mandate_planning.propose_candidate_plan(
        objective=mandate.objective, documents=doc_summaries, templates=template_summaries,
        brief=brief.to_dict() if brief else None, feedback=feedback,
    )

    if outcome.status == "error":
        return LlmPlanProposalResult(status="error", reason=outcome.error_message, model=outcome.model)

    if outcome.status == "unsupported":
        return LlmPlanProposalResult(
            status="unsupported", reasoning=outcome.reasoning,
            reason=outcome.unsupported_reason or "the planner did not explain why", model=outcome.model,
            usage=outcome.usage,
        )

    # status == "proposed": still just a candidate - independently verify
    # every claim before trusting any of it (see this function's own
    # docstring, layer 1).
    template = get_template(outcome.template_key) if outcome.template_key else None
    if template is None or template.key in _TEMPLATES_EXCLUDED_FROM_LLM_PLANNING:
        return LlmPlanProposalResult(
            status="unsupported", reasoning=outcome.reasoning,
            reason=f"the planner proposed an unregistered template: {outcome.template_key!r}",
            model=outcome.model, usage=outcome.usage,
        )

    stage_inputs: dict[str, dict] | None = None
    document_stage = _document_selection_stage(template)
    if document_stage is not None:
        resolved = []
        for document_id in outcome.document_ids:
            document = documents.get_document(project_id, document_id)
            if document is None:
                # Exactly the "hallucinated or cross-project id" case this
                # task requires be rejected, not trusted -
                # documents.get_document is itself project_id-scoped, so a
                # real id from a different project resolves to None here
                # too, not just a made-up one.
                return LlmPlanProposalResult(
                    status="unsupported", reasoning=outcome.reasoning,
                    reason=(
                        f"the planner referenced a document that does not exist in this project: "
                        f"{document_id!r}"
                    ),
                    model=outcome.model, usage=outcome.usage,
                )
            resolved.append(document)

        validation_error = cross_format_analysis.validate_selection(resolved)
        if validation_error is not None:
            error_type, error_message = validation_error
            return LlmPlanProposalResult(
                status="unsupported", reasoning=outcome.reasoning,
                reason=f"{error_type}: {error_message}", model=outcome.model, usage=outcome.usage,
            )
        stage_inputs = {document_stage["id"]: {"document_ids": [d.id for d in resolved]}}

    try:
        plan = propose_plan(
            project_id, mandate_id, template.key, stage_inputs=stage_inputs,
            proposed_by="llm", planner_reasoning=outcome.reasoning,
        )
    except (PlanValidationError, MandateValidationError) as exc:
        # The exact same untrusted-plan validator 12.1 built rejected this
        # candidate (e.g. validate_plan_stages catching something layer 1
        # above didn't) - reported as unsupported, not a raw exception, so
        # this function never lets a model's bad output surface as a
        # server error to the human.
        return LlmPlanProposalResult(
            status="unsupported", reasoning=outcome.reasoning, reason=str(exc),
            model=outcome.model, usage=outcome.usage,
        )

    return LlmPlanProposalResult(
        status="proposed", plan=plan, reasoning=outcome.reasoning, model=outcome.model, usage=outcome.usage,
    )


def approve_plan(project_id: str, mandate_id: str, plan_id: str, approved_by: str | None) -> PlanRevision:
    mandate = get_mandate(project_id, mandate_id)
    if mandate is None:
        raise ValueError("mandate not found")
    plan = get_plan(mandate_id, plan_id)
    if plan is None:
        raise ValueError("plan not found")
    if plan.status != "proposed":
        raise MandateValidationError(f"cannot approve a plan with status {plan.status!r}")

    _set_plan(plan_id, status="approved", approved_at=_now(), approved_by=approved_by)
    _set_mandate(mandate_id, status="active", current_plan_id=plan_id)
    updated = get_plan(mandate_id, plan_id)
    assert updated is not None
    return updated


def reject_plan(project_id: str, mandate_id: str, plan_id: str) -> PlanRevision:
    mandate = get_mandate(project_id, mandate_id)
    if mandate is None:
        raise ValueError("mandate not found")
    plan = get_plan(mandate_id, plan_id)
    if plan is None:
        raise ValueError("plan not found")
    if plan.status != "proposed":
        raise MandateValidationError(f"cannot reject a plan with status {plan.status!r}")

    _set_plan(plan_id, status="rejected")
    _set_mandate(mandate_id, status="draft")
    updated = get_plan(mandate_id, plan_id)
    assert updated is not None
    return updated


# -- runs and attempts --------------------------------------------------


def _row_to_run(row) -> Run:
    return Run(
        row["id"], row["mandate_id"], row["plan_revision_id"], row["status"],
        row["queued_at"], row["started_at"], row["finished_at"],
        row["current_stage_index"], row["budget_limit"], row["budget_consumed"],
    )


def _get_mandate_by_id(mandate_id: str) -> Mandate | None:
    """Unlike get_mandate(), not project-scoped - only used by the Worker,
    which processes runs by id across the whole app and already trusts the
    persisted Run -> Mandate linkage (this is background job processing,
    not a new user-facing route, so it adds no new authorization surface)."""
    conn = store.get_connection()
    try:
        row = conn.execute("SELECT * FROM mandates WHERE id = %s", (mandate_id,)).fetchone()
    finally:
        conn.close()
    return _row_to_mandate(row) if row else None


def _list_runs_by_status(status: str) -> list[Run]:
    """Unlike list_runs(), scans across every mandate/project - the
    Worker's poll loop serves the whole app, not one project at a time."""
    conn = store.get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM mandate_runs WHERE status = %s ORDER BY queued_at ASC NULLS FIRST", (status,)
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_run(r) for r in rows]


def _row_to_attempt(row) -> Attempt:
    return Attempt(
        row["id"], row["run_id"], row["stage_id"], row["capability"], row["status"],
        row["started_at"], row["finished_at"],
        json.loads(row["output_json"]) if row["output_json"] else None, row["error"],
    )


def get_run(mandate_id: str, run_id: str) -> Run | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM mandate_runs WHERE mandate_id = %s AND id = %s", (mandate_id, run_id)
        ).fetchone()
    finally:
        conn.close()
    return _row_to_run(row) if row else None


def list_runs(mandate_id: str) -> list[Run]:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM mandate_runs WHERE mandate_id = %s ORDER BY started_at ASC", (mandate_id,)
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_run(r) for r in rows]


def list_attempts(run_id: str) -> list[Attempt]:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM mandate_attempts WHERE run_id = %s ORDER BY started_at ASC", (run_id,)
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_attempt(r) for r in rows]


def _set_run(run_id: str, **fields: Any) -> None:
    set_clause = ", ".join(f"{k} = %s" for k in fields)
    conn = store.get_connection()
    try:
        conn.execute(f"UPDATE mandate_runs SET {set_clause} WHERE id = %s", (*fields.values(), run_id))
        conn.commit()
    finally:
        conn.close()


def _record_attempt(run_id: str, stage_id: str, capability: str | None, status: str,
                     output: dict | None, error: str | None) -> str:
    """Returns the new attempt's id. Task 12.2: "running" and
    "awaiting_human" are both genuinely unfinished at insertion time
    (finished_at stays None) - docs/04's "Record attempts before provider
    calls" means a capability attempt is now recorded as "running" *before*
    its executor is called, then finalized via _update_attempt once the
    call returns (or the process finds it still "running" at startup - see
    Worker.recover())."""
    now = _now()
    attempt_id = uuid.uuid4().hex
    finished_at = None if status in ("running", "awaiting_human") else now
    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO mandate_attempts (id, run_id, stage_id, capability, status, started_at, finished_at, output_json, error)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (attempt_id, run_id, stage_id, capability, status, now, finished_at,
             json.dumps(output) if output is not None else None, error),
        )
        conn.commit()
    finally:
        conn.close()
    return attempt_id


def _get_attempt(run_id: str, stage_id: str) -> Attempt | None:
    matches = [a for a in list_attempts(run_id) if a.stage_id == stage_id]
    return matches[-1] if matches else None


def _update_attempt(attempt_id: str, status: str, output: dict | None, error: str | None = None) -> None:
    conn = store.get_connection()
    try:
        conn.execute(
            "UPDATE mandate_attempts SET status = %s, finished_at = %s, output_json = %s, error = %s WHERE id = %s",
            (status, _now(), json.dumps(output) if output is not None else None, error, attempt_id),
        )
        conn.commit()
    finally:
        conn.close()


def execute_run(project_id: str, mandate_id: str, budget_limit: float | None = None) -> Run:
    """Task 12.2: persists and acknowledges a "queued" Run, then returns
    immediately - no capability executes here or anywhere in this call
    stack. The Run already exists, independently of this request, by the
    time this function returns; the Worker's background poll loop (started
    from server.py:main(), not from here) is what actually executes it.
    Closing the browser or losing the HTTP connection right after this
    returns has no effect on whether the run runs."""
    mandate = get_mandate(project_id, mandate_id)
    if mandate is None:
        raise ValueError("mandate not found")
    if mandate.status != "active" or mandate.current_plan_id is None:
        raise MandateValidationError("mandate must have an approved, active plan before it can run")
    plan = get_plan(mandate_id, mandate.current_plan_id)
    assert plan is not None

    run = Run(
        id=uuid.uuid4().hex, mandate_id=mandate_id, plan_revision_id=plan.id,
        status="queued", queued_at=_now(), started_at=None, finished_at=None,
        current_stage_index=0, budget_limit=budget_limit, budget_consumed=0.0,
    )
    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO mandate_runs
                (id, mandate_id, plan_revision_id, status, queued_at, current_stage_index, budget_limit, budget_consumed)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (run.id, run.mandate_id, run.plan_revision_id, run.status, run.queued_at,
             run.current_stage_index, run.budget_limit, run.budget_consumed),
        )
        conn.commit()
    finally:
        conn.close()
    return run


def _run_stages(project_id: str, mandate: Mandate, plan: PlanRevision, run_id: str, start_index: int) -> None:
    """Walks plan.stages[start_index:], one at a time. Called only from
    the Worker (_execute, below) - never from an HTTP request thread.
    Re-fetches the Run's own row at the top of every iteration rather than
    trusting an in-memory copy, specifically so a cancellation requested
    concurrently (cancel_run, running on a request thread, mid-loop here)
    is noticed before the *next* stage starts (Task 12.2: "cancellation
    actually stops future stages of an in-flight run" - it does not, and
    cannot, interrupt a stage already in progress)."""
    for idx in range(start_index, len(plan.stages)):
        current = get_run(mandate.id, run_id)
        assert current is not None
        if current.status == "cancel_requested":
            _set_run(run_id, status="cancelled", finished_at=_now())
            _set_mandate(mandate.id, status="cancelled")
            return

        stage = plan.stages[idx]
        _set_run(run_id, current_stage_index=idx)
        kind = stage.get("kind", "capability")

        if kind == "human_checkpoint":
            _record_attempt(run_id, stage["id"], capability=None, status="awaiting_human", output=None, error=None)
            _set_run(run_id, status="waiting_for_input")
            # docs/04-mandate-engine.md: "Active mandates can be waiting_
            # for_input or paused" - that's a Run-level condition here,
            # not a separate Mandate status. The mandate stays "active"
            # throughout; only the Run reflects the pause.
            return

        capability_name = stage.get("capability")
        descriptor = get_capability(capability_name) if capability_name else None
        if descriptor is None:
            _record_attempt(run_id, stage["id"], capability=capability_name, status="failed",
                             output=None, error="capability not registered")
            _set_run(run_id, status="failed", finished_at=_now())
            _set_mandate(mandate.id, status="failed")
            return

        if not descriptor.permission_check(project_id):
            _record_attempt(run_id, stage["id"], capability=capability_name, status="failed",
                             output=None, error="permission denied for capability")
            _set_run(run_id, status="failed", finished_at=_now())
            _set_mandate(mandate.id, status="failed")
            return

        # Budget ledger (Task 12.2): checked before the call, not after -
        # docs/04: "Budgets check before calls and between stages." Real
        # and enforced, even though fixture.echo's unit_cost is nominal.
        projected_cost = current.budget_consumed + descriptor.unit_cost
        if current.budget_limit is not None and projected_cost > current.budget_limit:
            _record_attempt(
                run_id, stage["id"], capability=capability_name, status="failed", output=None,
                error=(
                    f"budget exceeded: stage would consume {projected_cost:g}, "
                    f"run limit is {current.budget_limit:g}"
                ),
            )
            _set_run(run_id, status="failed", finished_at=_now())
            _set_mandate(mandate.id, status="failed")
            return

        # Recorded as "running" *before* the call (docs/04: "Record
        # attempts before provider calls") - see Worker.recover() for why:
        # this is what lets a later restart tell "died before this stage
        # ever started" apart from "died while this exact call was live".
        attempt_id = _record_attempt(run_id, stage["id"], capability=capability_name,
                                      status="running", output=None, error=None)
        try:
            # Task 14.2: a local copy only - never written back into the
            # plan's own stored stages_json. Reserved, underscore-prefixed
            # keys carrying the mandate/run/attempt context an executor
            # may need for its own audit record's lineage (see
            # _integrity_review_executor) - harmless for every existing
            # executor, which reads only the specific keys it already
            # expects and ignores the rest; not part of any capability's
            # own declared input_schema, and never checked by it.
            stage_input_with_context = dict(stage.get("input", {}))
            stage_input_with_context["_mandate_id"] = mandate.id
            stage_input_with_context["_run_id"] = run_id
            stage_input_with_context["_attempt_id"] = attempt_id
            output = descriptor.executor(project_id, stage_input_with_context)
            # Task 14.1: the executor's real return value must match its
            # own declared output_schema - a capability whose output
            # drifts from its own pinned contract fails loudly here,
            # exactly like any other executor exception, rather than
            # propagating a malformed shape into a persisted Attempt.
            _validate_against_schema(
                output, descriptor.output_schema, f"stage {stage['id']!r} ({capability_name}) output"
            )
        except Exception as exc:  # the executor is untrusted third-party-shaped code
            _update_attempt(attempt_id, status="failed", output=None, error=str(exc))
            _set_run(run_id, status="failed", finished_at=_now())
            _set_mandate(mandate.id, status="failed")
            return

        _update_attempt(attempt_id, status="succeeded", output=output, error=None)
        _set_run(run_id, budget_consumed=projected_cost)

    _set_run(run_id, status="succeeded", finished_at=_now(), current_stage_index=len(plan.stages))
    _set_mandate(mandate.id, status="completed")


def _execute(run: Run) -> None:
    """Worker entry point for one run: resolves its mandate/plan, marks it
    "running" (setting started_at only the first time), and walks its
    stages from wherever it left off (current_stage_index - 0 for a fresh
    run, just past a checkpoint for a resumed one, or wherever
    Worker.recover() left it for an interrupted one)."""
    mandate = _get_mandate_by_id(run.mandate_id)
    if mandate is None:
        _set_run(run.id, status="failed", finished_at=_now())
        return
    plan = get_plan(run.mandate_id, run.plan_revision_id)
    if plan is None:
        _set_run(run.id, status="failed", finished_at=_now())
        _set_mandate(mandate.id, status="failed")
        return

    fields: dict[str, Any] = {"status": "running"}
    if run.started_at is None:
        fields["started_at"] = _now()
    _set_run(run.id, **fields)
    _run_stages(mandate.project_id, mandate, plan, run.id, start_index=run.current_stage_index)


def resume_run(project_id: str, mandate_id: str, run_id: str, stage_id: str, decision: str) -> Run:
    """Records the human's decision - durably, before this returns - then
    hands the run back to the Worker to continue past the checkpoint (see
    _execute/Worker) rather than continuing inline. Even if this very
    request is what gets interrupted right after, the decision itself is
    already safe, and the Worker will pick the run back up on its own."""
    mandate = get_mandate(project_id, mandate_id)
    run = get_run(mandate_id, run_id)
    if mandate is None or run is None:
        raise ValueError("mandate or run not found")
    if run.status != "waiting_for_input":
        raise MandateValidationError("run is not waiting for human input")
    attempt = _get_attempt(run_id, stage_id)
    if attempt is None or attempt.status != "awaiting_human":
        raise MandateValidationError("stage is not awaiting human input")

    _update_attempt(attempt.id, status="succeeded", output={"decision": decision}, error=None)

    plan = get_plan(mandate_id, run.plan_revision_id)
    assert plan is not None
    resume_index = next(i for i, s in enumerate(plan.stages) if s["id"] == stage_id) + 1
    _set_run(run_id, status="queued", current_stage_index=resume_index)
    updated = get_run(mandate_id, run_id)
    assert updated is not None
    return updated


def cancel_run(project_id: str, mandate_id: str, run_id: str) -> Run:
    """Task 12.2: cancellation now works for a "queued" or "running" run,
    not only one already parked at a human checkpoint (all 12.1 could do).
    For those two, this only *requests* cancellation - the actual stop
    happens cooperatively, either from _run_stages' own per-stage check
    (if a Worker is already mid-run on it) or from the Worker's own
    cancel_requested scan (if it is still sitting "queued", never
    dispatched) - see Worker.poll_once(). A "waiting_for_input" run has
    nothing in flight to stop, so it is cancelled immediately, as before."""
    mandate = get_mandate(project_id, mandate_id)
    run = get_run(mandate_id, run_id)
    if mandate is None or run is None:
        raise ValueError("mandate or run not found")

    if run.status == "waiting_for_input":
        # Found during this task's own live browser verification: the
        # checkpoint's attempt was left "awaiting_human" forever once its
        # run was cancelled - not a status resume_run itself ever checks
        # again, but the frontend's "is a decision still needed here?"
        # check keys off exactly this attempt status, so the decision
        # form and Resume/Cancel controls kept rendering on an already-
        # cancelled run. Finalizing it here closes that gap.
        pending = next((a for a in list_attempts(run_id) if a.status == "awaiting_human"), None)
        if pending is not None:
            _update_attempt(pending.id, status="failed", output=None, error="run cancelled")
        _set_run(run_id, status="cancelled", finished_at=_now())
        _set_mandate(mandate_id, status="cancelled")
    elif run.status in ("queued", "running"):
        _set_run(run_id, status="cancel_requested")
    else:
        raise MandateValidationError(f"cannot cancel a run with status {run.status!r}")

    updated = get_run(mandate_id, run_id)
    assert updated is not None
    return updated


# -- durable local worker (Task 12.2) ----------------------------------


class Worker:
    """The durable local worker. A Run is persisted and acknowledged by
    execute_run()/resume_run() *before* this ever sees it - acknowledging
    a run never depends on this object existing, let alone being healthy.
    This is what actually executes it, on its own background thread,
    independent of any HTTP request.

    Single-process, single-worker by construction (this app runs one
    local server process at a time - see docs/07-architecture.md) - there
    is deliberately no cross-process locking (e.g. `SELECT ... FOR UPDATE
    SKIP LOCKED`) because there is never more than one worker to contend
    with. The one known, disclosed race this leaves: a cancel_run call
    landing in the exact instant between poll_once() reading a run as
    "queued" and _execute() writing it to "running" can be silently
    overwritten back to "running" - a repeat cancel immediately afterward
    always succeeds, since _run_stages' own per-stage check will then see
    the run genuinely "running" and honor it before the next stage."""

    def __init__(self, poll_interval: float = 0.5):
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self.recover()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, name="mandate-worker", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout)

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.poll_once()
            except Exception:
                # A bug surfaced while processing one run must not kill
                # the whole worker thread - poll_once() already isolates
                # each individual run from the others (see there); this is
                # only a last-resort backstop around the scan itself.
                pass
            self._stop_event.wait(self.poll_interval)

    def recover(self) -> None:
        """Startup recovery (roadmap M12.2, verbatim: "the worker can be
        interrupted (e.g. server restart) and recovers or reports
        outcome_unknown rather than silently losing state"). Called once,
        before the poll loop starts. Any Run still "running" at this point
        was, by construction, left there by a *prior* process's worker -
        this one has not started its loop yet - so that state is
        definitionally stale; exactly one of two things happened to it:

        1. The prior process died while a capability call was genuinely in
           flight (its own attempt row is still "running"). Whether that
           capability's side effect actually completed is unknowable from
           here (docs/04: "Internal idempotency does not imply
           provider-side deduplication... At interruption, unknown
           provider outcome is not automatically retried") - so this is
           reported as outcome_unknown, not guessed at, and the mandate
           moves to under_review for a human to look at, not silently
           back to active or completed.
        2. The prior process died cleanly between stages (or before
           starting any stage at all) - every attempt already recorded is
           a real, finished fact, so it is safe to requeue and let the
           ordinary poll loop finish it from current_stage_index, exactly
           as it would for any other queued run.
        """
        for run in _list_runs_by_status("running"):
            attempts = list_attempts(run.id)
            last = attempts[-1] if attempts else None
            if last is not None and last.status == "running":
                _update_attempt(
                    last.id, status="failed", output=None,
                    error="interrupted: outcome unknown (worker process restarted mid-attempt)",
                )
                _set_run(run.id, status="outcome_unknown", finished_at=_now())
                mandate = _get_mandate_by_id(run.mandate_id)
                if mandate is not None:
                    _set_mandate(mandate.id, status="under_review")
            else:
                _set_run(run.id, status="queued")

    def poll_once(self) -> None:
        """One scan-and-process pass over every project's runs. A public
        method in its own right (not folded into _loop) specifically so
        tests can force one deterministic step without sleeping or racing
        a background thread."""
        for run in _list_runs_by_status("cancel_requested"):
            try:
                self._finalize_cancel(run)
            except Exception:
                continue
        for run in _list_runs_by_status("queued"):
            try:
                _execute(run)
            except Exception:
                _set_run(run.id, status="failed", finished_at=_now())
                mandate = _get_mandate_by_id(run.mandate_id)
                if mandate is not None:
                    _set_mandate(mandate.id, status="failed")

    @staticmethod
    def _finalize_cancel(run: Run) -> None:
        # Only ever reached for a run that was "queued" (never dispatched)
        # or left mid-cancel by a crash before this scan could run. One
        # that is actually "running" right now is cancelled by
        # _run_stages' own per-stage check instead (see cancel_run) -
        # never by this scan - so there is no risk of two places finishing
        # the same in-flight run at once.
        _set_run(run.id, status="cancelled", finished_at=_now())
        _set_mandate(run.mandate_id, status="cancelled")
