"""Opt-in trigger configuration (roadmap M15.3: docs/workspace-shift/
integrations/workspace-integrity-integration-v1.0.0/
06-m15-change-awareness.md's own "15.3 Trigger policy" section). A
freestanding, leaf module (only `store` imported) - the actual firing
orchestration (creating a real Mandate and proposing a real Plan when an
event matches an active trigger) lives in `mandates.py`, not here, so
that `mandates.py` can import this module without a cycle (`mandates.py`
already imports `documents.py`/`workspaces.py`/`deliverables.py`; this
module must never import `mandates.py` back).

A Trigger is a durable, human-authored configuration, never inferred or
auto-created: "Authorized users may configure opt-in triggers." Firing
one always creates a normal, visible Mandate with its own real
PlanRevision/Run/Attempt lineage - never a hidden action, and never one
that runs unapproved (every plan a trigger proposes still needs an
explicit `approve_plan`/`execute_run` call from a human, exactly like a
manually-proposed one - `approval_policy` is recorded on the trigger for
future extension but this v1 only ever operates in `"manual"` mode, see
this module's own `APPROVAL_POLICIES`).

v1 scope (disclosed): two event types only, both chosen because they
already have a real, existing hook point and a workspace_id the fired
template can use directly without any new inference - `readiness` and
`reassessment` both take exactly `{"workspace_id": ...}`:

- `document_version_changed` - a document this app already tracks
  dependencies for (Task 15.1) received a new version. Compatible
  templates: `readiness`, `reassessment`.
- `decision_package_prepared` - a new DeliverableVersion (Task 14.3) was
  drafted, awaiting approval. Compatible template: `readiness` only (a
  freshly drafted decision package has no version comparison to make).

The roadmap's other three example triggers (a submission entering
`submitted`, returned work resubmitted, a reviewer requesting
cross-workstream review) are not supported in this version: none of them
has a single, unambiguous `workspace_id` a template could consume
without new inference logic, and "request cross-workstream review" has
no existing action in this app to hook at all - each is a distinct,
larger, unauthorized future task, not an oversight.

Every firing attempt - whether a real Mandate/Plan was created or the
attempt itself failed - is durably recorded (`TriggerFiring`), never
silently dropped. This app has no separate background scheduler that
could itself go down and miss events (firing is synchronous with the
real event that causes it, inside the same request); "downtime/failure
visibility" here means exactly this: every attempt's outcome is always
visible via `list_firings`, success or failure alike.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import store

TRIGGER_STATUSES = {"active", "disabled"}
APPROVAL_POLICIES = {"manual"}
FIRING_STATUSES = {"proposed", "error"}

# Which mandate templates make sense for each event type - both compatible
# templates take exactly {"workspace_id": ...} as their entire stage input,
# which is exactly what this v1's two event types can each derive on their
# own (see this module's own docstring for why no other roadmap-listed
# event type is supported yet).
EVENT_TEMPLATE_COMPATIBILITY: dict[str, set[str]] = {
    "document_version_changed": {"readiness", "reassessment"},
    "decision_package_prepared": {"readiness"},
}
TRIGGER_EVENT_TYPES = set(EVENT_TEMPLATE_COMPATIBILITY.keys())


class TriggerValidationError(Exception):
    pass


@dataclass
class Trigger:
    id: str
    project_id: str
    name: str
    event_type: str
    template_key: str
    scope_document_id: str | None
    scope_workspace_id: str | None
    owner_user_id: str
    budget_limit: float | None
    reason: str
    approval_policy: str
    status: str
    created_at: str
    created_by: str | None
    disabled_at: str | None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "name": self.name,
            "event_type": self.event_type,
            "template_key": self.template_key,
            "scope_document_id": self.scope_document_id,
            "scope_workspace_id": self.scope_workspace_id,
            "owner_user_id": self.owner_user_id,
            "budget_limit": self.budget_limit,
            "reason": self.reason,
            "approval_policy": self.approval_policy,
            "status": self.status,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "disabled_at": self.disabled_at,
        }


@dataclass
class TriggerFiring:
    id: str
    trigger_id: str
    project_id: str
    workspace_id: str
    event_detail: dict[str, Any]
    mandate_id: str | None
    plan_id: str | None
    status: str
    error_message: str | None
    fired_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "trigger_id": self.trigger_id,
            "project_id": self.project_id,
            "workspace_id": self.workspace_id,
            "event_detail": self.event_detail,
            "mandate_id": self.mandate_id,
            "plan_id": self.plan_id,
            "status": self.status,
            "error_message": self.error_message,
            "fired_at": self.fired_at,
        }


def init_triggers_db() -> None:
    conn = store.get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS triggers (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                name TEXT NOT NULL,
                event_type TEXT NOT NULL,
                template_key TEXT NOT NULL,
                scope_document_id TEXT,
                scope_workspace_id TEXT,
                owner_user_id TEXT NOT NULL,
                budget_limit REAL,
                reason TEXT NOT NULL DEFAULT '',
                approval_policy TEXT NOT NULL DEFAULT 'manual',
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                created_by TEXT,
                disabled_at TEXT
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_triggers_project ON triggers(project_id)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_triggers_project_event ON triggers(project_id, event_type, status)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trigger_firings (
                id TEXT PRIMARY KEY,
                trigger_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                event_detail_json TEXT NOT NULL DEFAULT '{}',
                mandate_id TEXT,
                plan_id TEXT,
                status TEXT NOT NULL,
                error_message TEXT,
                fired_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_trigger_firings_trigger ON trigger_firings(trigger_id)")
        conn.commit()
    finally:
        conn.close()


def _row_to_trigger(row) -> Trigger:
    return Trigger(
        id=row["id"], project_id=row["project_id"], name=row["name"], event_type=row["event_type"],
        template_key=row["template_key"], scope_document_id=row["scope_document_id"],
        scope_workspace_id=row["scope_workspace_id"], owner_user_id=row["owner_user_id"],
        budget_limit=row["budget_limit"], reason=row["reason"], approval_policy=row["approval_policy"],
        status=row["status"], created_at=row["created_at"], created_by=row["created_by"],
        disabled_at=row["disabled_at"],
    )


def create_trigger(
    *,
    project_id: str,
    name: str,
    event_type: str,
    template_key: str,
    owner_user_id: str,
    scope_document_id: str | None = None,
    scope_workspace_id: str | None = None,
    budget_limit: float | None = None,
    reason: str = "",
    approval_policy: str = "manual",
    created_by: str | None = None,
) -> Trigger:
    name = name.strip()
    if not name:
        raise TriggerValidationError("name is required")
    if event_type not in TRIGGER_EVENT_TYPES:
        raise TriggerValidationError(f"event_type must be one of {sorted(TRIGGER_EVENT_TYPES)}")
    if template_key not in EVENT_TEMPLATE_COMPATIBILITY[event_type]:
        raise TriggerValidationError(
            f"template {template_key!r} is not compatible with event {event_type!r} - "
            f"compatible templates: {sorted(EVENT_TEMPLATE_COMPATIBILITY[event_type])}"
        )
    if approval_policy not in APPROVAL_POLICIES:
        raise TriggerValidationError(f"approval_policy must be one of {sorted(APPROVAL_POLICIES)}")
    if not owner_user_id:
        raise TriggerValidationError("owner_user_id is required")

    now = datetime.now(timezone.utc).isoformat()
    trigger = Trigger(
        id=uuid.uuid4().hex, project_id=project_id, name=name, event_type=event_type, template_key=template_key,
        scope_document_id=scope_document_id, scope_workspace_id=scope_workspace_id, owner_user_id=owner_user_id,
        budget_limit=budget_limit, reason=reason.strip(), approval_policy=approval_policy, status="active",
        created_at=now, created_by=created_by, disabled_at=None,
    )
    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO triggers (
                id, project_id, name, event_type, template_key, scope_document_id, scope_workspace_id,
                owner_user_id, budget_limit, reason, approval_policy, status, created_at, created_by, disabled_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                trigger.id, trigger.project_id, trigger.name, trigger.event_type, trigger.template_key,
                trigger.scope_document_id, trigger.scope_workspace_id, trigger.owner_user_id, trigger.budget_limit,
                trigger.reason, trigger.approval_policy, trigger.status, trigger.created_at, trigger.created_by,
                trigger.disabled_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return trigger


def get_trigger(project_id: str, trigger_id: str) -> Trigger | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM triggers WHERE project_id = %s AND id = %s", (project_id, trigger_id)
        ).fetchone()
    finally:
        conn.close()
    return _row_to_trigger(row) if row else None


def list_triggers(project_id: str) -> list[Trigger]:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM triggers WHERE project_id = %s ORDER BY created_at", (project_id,)
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_trigger(r) for r in rows]


def disable_trigger(project_id: str, trigger_id: str) -> Trigger:
    existing = get_trigger(project_id, trigger_id)
    if existing is None:
        raise TriggerValidationError("trigger not found")
    now = datetime.now(timezone.utc).isoformat()
    conn = store.get_connection()
    try:
        conn.execute(
            "UPDATE triggers SET status = 'disabled', disabled_at = %s WHERE id = %s", (now, existing.id),
        )
        conn.commit()
    finally:
        conn.close()
    updated = get_trigger(project_id, trigger_id)
    assert updated is not None
    return updated


def match_active_triggers(
    project_id: str, event_type: str, *, document_id: str | None = None, workspace_id: str | None = None,
) -> list[Trigger]:
    """Every active trigger in this project for this event type whose own
    scope (if any) matches the real event - an unscoped trigger
    (`scope_document_id`/`scope_workspace_id` both `None`) matches every
    occurrence of its event type in the project; a scoped one matches
    only the exact document or workspace it names."""
    conn = store.get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM triggers WHERE project_id = %s AND event_type = %s AND status = 'active'",
            (project_id, event_type),
        ).fetchall()
    finally:
        conn.close()
    matches = []
    for row in rows:
        trigger = _row_to_trigger(row)
        if trigger.scope_document_id is not None and trigger.scope_document_id != document_id:
            continue
        if trigger.scope_workspace_id is not None and trigger.scope_workspace_id != workspace_id:
            continue
        matches.append(trigger)
    return matches


def _row_to_firing(row) -> TriggerFiring:
    return TriggerFiring(
        id=row["id"], trigger_id=row["trigger_id"], project_id=row["project_id"], workspace_id=row["workspace_id"],
        event_detail=json.loads(row["event_detail_json"]), mandate_id=row["mandate_id"], plan_id=row["plan_id"],
        status=row["status"], error_message=row["error_message"], fired_at=row["fired_at"],
    )


def record_firing(
    *,
    trigger_id: str,
    project_id: str,
    workspace_id: str,
    event_detail: dict[str, Any],
    mandate_id: str | None,
    plan_id: str | None,
    status: str,
    error_message: str | None,
) -> TriggerFiring:
    if status not in FIRING_STATUSES:
        raise TriggerValidationError(f"status must be one of {sorted(FIRING_STATUSES)}")
    firing = TriggerFiring(
        id=uuid.uuid4().hex, trigger_id=trigger_id, project_id=project_id, workspace_id=workspace_id,
        event_detail=event_detail, mandate_id=mandate_id, plan_id=plan_id, status=status,
        error_message=error_message, fired_at=datetime.now(timezone.utc).isoformat(),
    )
    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO trigger_firings (
                id, trigger_id, project_id, workspace_id, event_detail_json, mandate_id, plan_id, status,
                error_message, fired_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                firing.id, firing.trigger_id, firing.project_id, firing.workspace_id,
                json.dumps(firing.event_detail), firing.mandate_id, firing.plan_id, firing.status,
                firing.error_message, firing.fired_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return firing


def list_firings(trigger_id: str) -> list[TriggerFiring]:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM trigger_firings WHERE trigger_id = %s ORDER BY fired_at", (trigger_id,)
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_firing(r) for r in rows]
