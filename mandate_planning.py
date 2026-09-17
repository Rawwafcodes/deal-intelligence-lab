"""Task 12.4: the LLM planning call itself.

Docs/04-mandate-engine.md's Plan contract: "Model-proposed plans are
untrusted. Validate schemas, capability names, source access, dependencies,
limits and approval rules. Display unavailable work as unsupported. Planner
proposes; server authorizes; executor invokes registered capability."

This module is deliberately the *only* thing in the planning path that talks
to Anthropic, and it is a pure function of its inputs: given a mandate's
objective, the project's real document inventory (id/filename/extension
only - never file bytes, never document content), the currently registered
templates, an optional deal brief, and optional human feedback on a prior
proposal, it asks a real model to propose one candidate plan and returns a
structured, still-untrusted `PlanProposalOutcome`. It never touches the
database, never creates a Mandate/PlanRevision, and never decides whether a
proposal is *actually* valid - `mandates.propose_plan_llm` does all of that
independently, re-verifying every document id against the real database and
running the exact same `validate_plan_stages`/`propose_plan` path a manual,
human-proposed plan already goes through (see that function's own
docstring). This mirrors this codebase's own established convention (see
`cross_format_analysis.run_cross_format_analysis`, `ai_client.
test_connection`): the module that makes the paid call is a thin, mockable
boundary, and every non-network concern (schema/authorization/dependency
checks) lives outside it.

Uses Anthropic's structured JSON output (`output_config.format`, confirmed
present in the installed SDK - anthropic 1.5.0 ships `JSONOutputFormatParam`/
`OutputConfigParam` - by direct inspection, not assumed from memory, the
same "inspect the SDK directly" discipline `cross_format_analysis.py`'s own
docstring describes) rather than asking for JSON in prose and parsing markdown,
since this call needs no citations (citations are documented as the one
structured-output incompatibility; a planning call, with no document content
sent at all, has none). This guarantees the reply's *shape* matches
PLAN_PROPOSAL_SCHEMA; it does not and cannot guarantee the reply's *content*
is true - a schema-conformant reply can still name a hallucinated document
id or a made-up template key, which is exactly why every value is
independently re-checked by `mandates.propose_plan_llm`, never trusted
because the shape was valid.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anthropic
from dotenv import load_dotenv

from anthropic_errors import is_insufficient_credit_error

load_dotenv(Path(__file__).parent / ".env.local")

# The founder authorized claude-sonnet-5 as this module's own fallback
# default - a one-off exception to this app's otherwise universal
# claude-opus-5 default (ai_client.py, pdf_inspection.py, cross_format_
# analysis.py, xlsx_inspection.py all default to opus-5), since planning
# sends only text (objective, brief, filenames - never document bytes) and
# is a small classification-shaped task, not the heavier per-file reasoning
# those other modules do. Like every one of those other modules, this
# fallback is silently overridden whenever ANTHROPIC_MODEL is set in the
# environment - this app's one existing deployment does set it (to
# claude-opus-5, in .env.local), so this fallback in practice only takes
# effect in a deployment that unsets ANTHROPIC_MODEL. Discovered live,
# after this task's own authorized planning call: that call actually ran
# on claude-opus-5, not the sonnet-5 intended, because of this exact
# override - disclosed in the task file, not silently corrected after the
# fact. A dedicated planning-only override (e.g. ANTHROPIC_PLANNING_MODEL)
# would restore the cost distinction, but the founder's explicit choice,
# once this was found, was to keep one global model knob rather than add
# a second one.
DEFAULT_MODEL = "claude-sonnet-5"

PLANNING_MAX_TOKENS = 4096

PLAN_PROPOSAL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "status": {
            "type": "string",
            "enum": ["proposed", "unsupported"],
            "description": (
                "'proposed' only when you are confident in both the template/capability "
                "and (if it needs one) the source document selection. 'unsupported' "
                "whenever you are not confident - an ambiguous document pairing, no "
                "matching documents, or an objective that doesn't match any registered "
                "capability - rather than guessing."
            ),
        },
        "template_key": {
            "type": ["string", "null"],
            "description": "Required (non-null) when status is 'proposed': one of the template keys listed above, verbatim.",
        },
        "document_ids": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Document ids (verbatim from the list above, never invented) to select, "
                "only when the chosen template's capability needs a source selection. "
                "Empty array otherwise, or when status is 'unsupported'."
            ),
        },
        "reasoning": {
            "type": "string",
            "description": "Brief explanation of the chosen template and selection, or of why no confident plan could be made.",
        },
        "unsupported_reason": {
            "type": ["string", "null"],
            "description": "Required (non-null) when status is 'unsupported': a short, specific, human-readable reason.",
        },
    },
    "required": ["status", "template_key", "document_ids", "reasoning", "unsupported_reason"],
}

_ERROR_MESSAGES = {
    "missing_api_key": "No API key is configured. Set ANTHROPIC_API_KEY (or add it to .env.local) and try again.",
    "invalid_api_key": "The configured API key was rejected. Check ANTHROPIC_API_KEY and try again.",
    "insufficient_credit": "The Anthropic account has insufficient credit for this request.",
    "rate_limit": "Rate limit reached. Wait a moment and try again.",
    "network_error": "Could not reach the Anthropic API. Check your internet connection and try again.",
    "model_unavailable": "The configured model is not available. Check ANTHROPIC_MODEL and try again.",
    "invalid_reply": "The planner's reply did not match the expected shape.",
    "unexpected_error": "The planning call failed unexpectedly.",
}


@dataclass
class DocumentSummary:
    """Everything the planner is allowed to see about a document: never its
    bytes or extracted content, only the same inventory metadata the
    existing manual document checklist (MandateDetail.tsx) already shows a
    human - docs/04's "Metadata-only selection can miss evidence" applies
    here by construction, not by omission."""

    id: str
    original_filename: str
    extension: str


@dataclass
class TemplateSummary:
    key: str
    name: str
    description: str
    needs_documents: bool


@dataclass
class PlanProposalOutcome:
    """`status`: "proposed" (a candidate plan - still untrusted, still to be
    independently re-verified by mandates.propose_plan_llm), "unsupported"
    (the model itself declined to guess), or "error" (the call itself
    failed - missing key, rate limit, a reply that didn't match the schema,
    etc. - distinct from "unsupported", which is an honest planning
    judgment, not a failure)."""

    status: str
    template_key: str | None = None
    document_ids: list[str] = field(default_factory=list)
    reasoning: str | None = None
    unsupported_reason: str | None = None
    model: str | None = None
    usage: dict | None = None
    stop_reason: str | None = None
    error_type: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "template_key": self.template_key,
            "document_ids": self.document_ids,
            "reasoning": self.reasoning,
            "unsupported_reason": self.unsupported_reason,
            "model": self.model,
            "usage": self.usage,
            "stop_reason": self.stop_reason,
            "error_type": self.error_type,
            "error_message": self.error_message,
        }


def _build_prompt(
    objective: str,
    documents: list[DocumentSummary],
    templates: list[TemplateSummary],
    brief: dict | None,
    feedback: str | None,
) -> str:
    template_lines = []
    for template in templates:
        note = " (needs a source document selection)" if template.needs_documents else ""
        template_lines.append(f"- key: {template.key!r} | name: {template.name} | {template.description}{note}")

    if documents:
        document_lines = [f"- id: {d.id!r} | filename: {d.original_filename} | type: {d.extension}" for d in documents]
    else:
        document_lines = ["(this project has no documents uploaded yet)"]

    brief_section = "No deal brief has been recorded for this project yet."
    if brief:
        brief_lines = [f"{field}: {brief.get(field, '')}" for field in
                       ("parties", "objective", "perspective", "scope", "periods", "uncertainties")
                       if brief.get(field)]
        if brief_lines:
            brief_section = "\n".join(brief_lines)

    feedback_section = ""
    if feedback:
        feedback_section = (
            "\n\nA human reviewed a previous proposal from you and asked for this change - "
            f"take it into account:\n{feedback}\n"
        )

    return f"""You are proposing a plan for an M&A due-diligence mandate. Pick the single
best-fitting registered template/capability for the objective below, and -
only if that template's capability needs one - a source document selection.
Never invent a template key or a document id that isn't listed below
verbatim. The "fixture-*" templates are internal runtime test scaffolding
only - never propose them for a genuine deal objective; if nothing else
fits, that means no real capability matches yet, so answer 'unsupported'.

If you are not confident - the objective doesn't clearly match a registered
capability, or (for a template needing documents) there is no clear,
unambiguous pairing of the right documents - answer 'unsupported' with a
specific reason, rather than guessing. A wrong guess that gets approved and
run is worse than asking a human to select sources manually.

Mandate objective:
{objective}

Deal brief:
{brief_section}

Registered templates:
{chr(10).join(template_lines)}

Project documents:
{chr(10).join(document_lines)}{feedback_section}

Respond with exactly one JSON object matching the required schema."""


def propose_candidate_plan(
    objective: str,
    documents: list[DocumentSummary],
    templates: list[TemplateSummary],
    brief: dict | None = None,
    feedback: str | None = None,
) -> PlanProposalOutcome:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    configured_model = os.environ.get("ANTHROPIC_MODEL", "").strip() or DEFAULT_MODEL

    if not api_key:
        return PlanProposalOutcome(
            status="error", model=configured_model,
            error_type="missing_api_key", error_message=_ERROR_MESSAGES["missing_api_key"],
        )

    client = anthropic.Anthropic(api_key=api_key)
    prompt = _build_prompt(objective, documents, templates, brief, feedback)

    try:
        response = client.messages.create(
            model=configured_model,
            max_tokens=PLANNING_MAX_TOKENS,
            output_config={
                "effort": "low",
                "format": {"type": "json_schema", "schema": PLAN_PROPOSAL_SCHEMA},
            },
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.AuthenticationError:
        return PlanProposalOutcome(
            status="error", model=configured_model,
            error_type="invalid_api_key", error_message=_ERROR_MESSAGES["invalid_api_key"],
        )
    except anthropic.NotFoundError:
        return PlanProposalOutcome(
            status="error", model=configured_model,
            error_type="model_unavailable", error_message=_ERROR_MESSAGES["model_unavailable"],
        )
    except anthropic.RateLimitError:
        return PlanProposalOutcome(
            status="error", model=configured_model,
            error_type="rate_limit", error_message=_ERROR_MESSAGES["rate_limit"],
        )
    except anthropic.APIStatusError as exc:
        if is_insufficient_credit_error(exc):
            return PlanProposalOutcome(
                status="error", model=configured_model,
                error_type="insufficient_credit", error_message=_ERROR_MESSAGES["insufficient_credit"],
            )
        return PlanProposalOutcome(
            status="error", model=configured_model,
            error_type="unexpected_error", error_message=f"API error ({exc.status_code}): {exc.message}",
        )
    except anthropic.APIConnectionError:
        return PlanProposalOutcome(
            status="error", model=configured_model,
            error_type="network_error", error_message=_ERROR_MESSAGES["network_error"],
        )
    except Exception as exc:  # pragma: no cover - defensive catch-all
        return PlanProposalOutcome(
            status="error", model=configured_model,
            error_type="unexpected_error", error_message=f"{_ERROR_MESSAGES['unexpected_error']} ({exc})",
        )

    usage = {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens}
    reply_text = "".join(block.text for block in response.content if block.type == "text").strip()

    if response.stop_reason == "max_tokens" or not reply_text:
        return PlanProposalOutcome(
            status="error", model=response.model, usage=usage, stop_reason=response.stop_reason,
            error_type="invalid_reply", error_message=_ERROR_MESSAGES["invalid_reply"],
        )

    try:
        parsed = json.loads(reply_text)
    except json.JSONDecodeError:
        return PlanProposalOutcome(
            status="error", model=response.model, usage=usage, stop_reason=response.stop_reason,
            error_type="invalid_reply", error_message=_ERROR_MESSAGES["invalid_reply"],
        )

    status = parsed.get("status")
    if status not in ("proposed", "unsupported"):
        # Schema validation on the provider side should make this
        # unreachable, but this function trusts nothing about the reply's
        # *content* - only structured JSON parsing succeeding, never a
        # provider-side guarantee, gets treated as fact.
        return PlanProposalOutcome(
            status="error", model=response.model, usage=usage, stop_reason=response.stop_reason,
            error_type="invalid_reply", error_message=_ERROR_MESSAGES["invalid_reply"],
        )

    document_ids = parsed.get("document_ids")
    if not isinstance(document_ids, list) or not all(isinstance(d, str) for d in document_ids):
        document_ids = []

    return PlanProposalOutcome(
        status=status,
        template_key=parsed.get("template_key"),
        document_ids=document_ids,
        reasoning=parsed.get("reasoning"),
        unsupported_reason=parsed.get("unsupported_reason"),
        model=response.model,
        usage=usage,
        stop_reason=response.stop_reason,
    )
