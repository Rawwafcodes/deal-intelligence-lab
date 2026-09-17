"""Organizations, users, deal memberships and dev-only sessions
(Task 11.3b - see docs/workspace-shift/tasks/11.3b-organization-auth.md).

Deliberately additive: no existing table (`projects` included) is altered.
`project_organizations` is a new side table mapping a project (Deal) to the
Organization it belongs to, joined on `project_id` - so `store.py`'s
`Project` dataclass, its `to_dict()` shape, and every existing test that
asserts against it stay untouched.

Identity here is dev-only by construction (docs/06-security-and-
collaboration.md): no password, no real auth provider. A session is an
opaque, server-generated token in an HttpOnly cookie, resolved against the
`sessions` table - never a client-supplied user id or header.

Backward compatibility for the existing static pages (which have no login
UI and never will - see docs/10-decisions.md D13): a request with no valid
session is transparently attached to one bootstrap "default" identity
(`get_default_user_id`) rather than rejected. That default identity is
auto-granted membership on every pre-existing project (the one-time legacy
backfill in `_seed_defaults`), so the app keeps working exactly as before
for anyone who never explicitly switches identity. Explicitly switching to
a different seeded identity (the new dev-only `/api/dev/session` endpoint)
is what actually exercises differentiated, server-enforced access.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import store

SESSION_TTL = timedelta(days=30)

# Seeded once, only when the organizations table is empty (see
# _seed_defaults) - never re-run against a database that already has real
# organizations, so this never overwrites anything a founder later creates.
_DEFAULT_ORG_NAME = "Local Organization"
_DEFAULT_IDENTITY_EMAIL = "lead@local.dev"


@dataclass
class Organization:
    id: str
    name: str
    created_at: str

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "created_at": self.created_at}


@dataclass
class User:
    id: str
    email: str
    display_name: str
    created_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "display_name": self.display_name,
            "created_at": self.created_at,
        }


@dataclass
class OrganizationMembership:
    id: str
    organization_id: str
    user_id: str
    role: str
    created_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "user_id": self.user_id,
            "role": self.role,
            "created_at": self.created_at,
        }


@dataclass
class DealMembership:
    id: str
    project_id: str
    user_id: str
    role: str
    created_at: str
    revoked_at: str | None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "user_id": self.user_id,
            "role": self.role,
            "created_at": self.created_at,
            "revoked_at": self.revoked_at,
        }


@dataclass
class Session:
    token: str
    user_id: str
    created_at: str
    expires_at: str


DEAL_ROLES = ("analyst", "reviewer", "deal_lead")
ORG_ROLES = ("admin", "member")


def init_identity_db() -> None:
    conn = store.get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS organizations (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS organization_memberships (
                id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE (organization_id, user_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS project_organizations (
                project_id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS deal_memberships (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TEXT NOT NULL,
                revoked_at TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_deal_memberships_project ON deal_memberships(project_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_deal_memberships_user ON deal_memberships(user_id)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()
    _seed_defaults()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seed_defaults() -> None:
    """Idempotent, additive bootstrap: creates one default Organization and
    three dev identities (analyst/reviewer/deal_lead) the first time this
    runs against a database with none yet, and backfills every
    pre-existing project (real data included) into that org with the
    deal_lead identity as its member - so nothing that worked before this
    task stops working. Never touches `projects` itself or any other
    table's existing rows; only ever inserts into the new tables above,
    and only for rows that don't already have an entry."""
    existing_default = _find_user_by_email(_DEFAULT_IDENTITY_EMAIL)
    if existing_default is not None:
        memberships = list_organization_memberships_for_user(existing_default.id)
        default_org_id = memberships[0].organization_id if memberships else create_organization(_DEFAULT_ORG_NAME).id
        _backfill_legacy_projects(default_org_id=default_org_id, default_user_id=existing_default.id)
        return

    org = create_organization(_DEFAULT_ORG_NAME)
    lead = create_user(_DEFAULT_IDENTITY_EMAIL, "Sam Okafor (Deal Lead)")
    analyst = create_user("analyst@local.dev", "Alex Rivera (Analyst)")
    reviewer = create_user("reviewer@local.dev", "Jordan Lee (Reviewer)")
    add_organization_membership(org.id, lead.id, "admin")
    add_organization_membership(org.id, analyst.id, "member")
    add_organization_membership(org.id, reviewer.id, "member")
    _backfill_legacy_projects(default_org_id=org.id, default_user_id=lead.id)


def _find_user_by_email(email: str) -> User | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT id, email, display_name, created_at FROM users WHERE email = %s", (email,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return User(row["id"], row["email"], row["display_name"], row["created_at"])


def _backfill_legacy_projects(default_org_id: str, default_user_id: str) -> None:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            """
            SELECT p.id FROM projects p
            LEFT JOIN project_organizations po ON po.project_id = p.id
            WHERE po.project_id IS NULL
            """
        ).fetchall()
    finally:
        conn.close()
    for row in rows:
        assign_project_organization(row["id"], default_org_id)
        add_deal_membership(row["id"], default_user_id, "deal_lead")


def get_default_user_id() -> str:
    user = _find_user_by_email(_DEFAULT_IDENTITY_EMAIL)
    if user is None:
        # _seed_defaults() always creates this identity before any request
        # can be served (called from init_identity_db(), itself called from
        # main() before the HTTP server starts) - reaching here would mean
        # init never ran.
        raise RuntimeError("identity.init_identity_db() has not run")
    return user.id


# -- organizations --------------------------------------------------------


def create_organization(name: str) -> Organization:
    org = Organization(id=uuid.uuid4().hex, name=name.strip(), created_at=_now())
    conn = store.get_connection()
    try:
        conn.execute(
            "INSERT INTO organizations (id, name, created_at) VALUES (%s, %s, %s)",
            (org.id, org.name, org.created_at),
        )
        conn.commit()
    finally:
        conn.close()
    return org


def list_organizations() -> list[Organization]:
    conn = store.get_connection()
    try:
        rows = conn.execute("SELECT id, name, created_at FROM organizations ORDER BY created_at").fetchall()
    finally:
        conn.close()
    return [Organization(r["id"], r["name"], r["created_at"]) for r in rows]


def get_organization(organization_id: str) -> Organization | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT id, name, created_at FROM organizations WHERE id = %s", (organization_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return Organization(row["id"], row["name"], row["created_at"])


# -- users -----------------------------------------------------------------


def create_user(email: str, display_name: str) -> User:
    user = User(id=uuid.uuid4().hex, email=email.strip(), display_name=display_name.strip(), created_at=_now())
    conn = store.get_connection()
    try:
        conn.execute(
            "INSERT INTO users (id, email, display_name, created_at) VALUES (%s, %s, %s, %s)",
            (user.id, user.email, user.display_name, user.created_at),
        )
        conn.commit()
    finally:
        conn.close()
    return user


def get_user(user_id: str) -> User | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT id, email, display_name, created_at FROM users WHERE id = %s", (user_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return User(row["id"], row["email"], row["display_name"], row["created_at"])


def list_users() -> list[User]:
    conn = store.get_connection()
    try:
        rows = conn.execute("SELECT id, email, display_name, created_at FROM users ORDER BY created_at").fetchall()
    finally:
        conn.close()
    return [User(r["id"], r["email"], r["display_name"], r["created_at"]) for r in rows]


# -- organization memberships ----------------------------------------------


def add_organization_membership(organization_id: str, user_id: str, role: str) -> OrganizationMembership:
    if role not in ORG_ROLES:
        raise ValueError(f"invalid organization role: {role!r}")
    membership = OrganizationMembership(
        id=uuid.uuid4().hex, organization_id=organization_id, user_id=user_id, role=role, created_at=_now()
    )
    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO organization_memberships (id, organization_id, user_id, role, created_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (organization_id, user_id) DO UPDATE SET role = EXCLUDED.role
            """,
            (membership.id, organization_id, user_id, role, membership.created_at),
        )
        conn.commit()
    finally:
        conn.close()
    return membership


def list_organization_memberships_for_user(user_id: str) -> list[OrganizationMembership]:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, organization_id, user_id, role, created_at
            FROM organization_memberships WHERE user_id = %s ORDER BY created_at
            """,
            (user_id,),
        ).fetchall()
    finally:
        conn.close()
    return [OrganizationMembership(r["id"], r["organization_id"], r["user_id"], r["role"], r["created_at"]) for r in rows]


# -- project <-> organization -----------------------------------------------


def assign_project_organization(project_id: str, organization_id: str) -> None:
    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO project_organizations (project_id, organization_id, created_at)
            VALUES (%s, %s, %s)
            ON CONFLICT (project_id) DO UPDATE SET organization_id = EXCLUDED.organization_id
            """,
            (project_id, organization_id, _now()),
        )
        conn.commit()
    finally:
        conn.close()


def get_project_organization_id(project_id: str) -> str | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT organization_id FROM project_organizations WHERE project_id = %s", (project_id,)
        ).fetchone()
    finally:
        conn.close()
    return row["organization_id"] if row else None


# -- deal memberships --------------------------------------------------------


def add_deal_membership(project_id: str, user_id: str, role: str) -> DealMembership:
    """Grants (or re-activates, updating the role) deal access. Never
    deletes a prior row - a previously revoked-then-regranted user keeps
    their full history, per D06 (revocation preserves history)."""
    if role not in DEAL_ROLES:
        raise ValueError(f"invalid deal role: {role!r}")
    conn = store.get_connection()
    try:
        existing = conn.execute(
            """
            SELECT id FROM deal_memberships
            WHERE project_id = %s AND user_id = %s AND revoked_at IS NULL
            """,
            (project_id, user_id),
        ).fetchone()
        if existing:
            conn.execute("UPDATE deal_memberships SET role = %s WHERE id = %s", (role, existing["id"]))
            conn.commit()
            membership_id = existing["id"]
            created_at = _now()
        else:
            membership_id = uuid.uuid4().hex
            created_at = _now()
            conn.execute(
                """
                INSERT INTO deal_memberships (id, project_id, user_id, role, created_at, revoked_at)
                VALUES (%s, %s, %s, %s, %s, NULL)
                """,
                (membership_id, project_id, user_id, role, created_at),
            )
            conn.commit()
    finally:
        conn.close()
    return DealMembership(membership_id, project_id, user_id, role, created_at, None)


def revoke_deal_membership(project_id: str, user_id: str) -> bool:
    """Sets revoked_at on the active membership row, if any. Returns
    whether a row was actually revoked."""
    conn = store.get_connection()
    try:
        row = conn.execute(
            """
            UPDATE deal_memberships SET revoked_at = %s
            WHERE project_id = %s AND user_id = %s AND revoked_at IS NULL
            RETURNING id
            """,
            (_now(), project_id, user_id),
        ).fetchone()
        conn.commit()
    finally:
        conn.close()
    return row is not None


def has_deal_access(project_id: str, user_id: str) -> bool:
    conn = store.get_connection()
    try:
        row = conn.execute(
            """
            SELECT 1 FROM deal_memberships
            WHERE project_id = %s AND user_id = %s AND revoked_at IS NULL
            """,
            (project_id, user_id),
        ).fetchone()
    finally:
        conn.close()
    if row is not None:
        return True
    if user_id == get_default_user_id() and get_project_organization_id(project_id) is None:
        # Orphan project: it exists in `projects` but was never routed
        # through this feature's org/membership assignment - either it
        # predates this task, or (the common case in this codebase's own
        # test suite) it was created directly via store.create_project(),
        # bypassing the POST /api/projects handler that normally assigns
        # one. Lazily adopt it into the default identity's organization,
        # the same outcome the one-time startup backfill gives every
        # project that already existed when this feature was added - so
        # nothing that worked before this task starts 404ing. Only the
        # default identity gains access from this; a different seeded
        # user still correctly has none. Only triggered when the caller
        # being checked IS the default identity - checking some other
        # user's access to an orphan project must never have the side
        # effect of silently adopting it.
        assign_project_organization(project_id, _default_organization_id())
        add_deal_membership(project_id, user_id, "deal_lead")
        return True
    return False


def _default_organization_id() -> str:
    memberships = list_organization_memberships_for_user(get_default_user_id())
    if memberships:
        return memberships[0].organization_id
    return create_organization(_DEFAULT_ORG_NAME).id


def list_accessible_project_ids(user_id: str) -> set[str]:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            "SELECT project_id FROM deal_memberships WHERE user_id = %s AND revoked_at IS NULL",
            (user_id,),
        ).fetchall()
        accessible = {r["project_id"] for r in rows}
        if user_id == get_default_user_id():
            # See has_deal_access()'s "orphan project" comment: include
            # not-yet-adopted projects in the default identity's own list
            # view too, without needing a prior per-project GET to trigger
            # the lazy adoption first.
            orphan_rows = conn.execute(
                """
                SELECT p.id FROM projects p
                LEFT JOIN project_organizations po ON po.project_id = p.id
                WHERE po.project_id IS NULL
                """
            ).fetchall()
            accessible |= {r["id"] for r in orphan_rows}
    finally:
        conn.close()
    return accessible


def list_deal_memberships_for_project(project_id: str) -> list[DealMembership]:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, project_id, user_id, role, created_at, revoked_at
            FROM deal_memberships WHERE project_id = %s ORDER BY created_at
            """,
            (project_id,),
        ).fetchall()
    finally:
        conn.close()
    return [
        DealMembership(r["id"], r["project_id"], r["user_id"], r["role"], r["created_at"], r["revoked_at"])
        for r in rows
    ]


# -- sessions ----------------------------------------------------------------


def create_session(user_id: str) -> Session:
    now = datetime.now(timezone.utc)
    session = Session(
        token=uuid.uuid4().hex,
        user_id=user_id,
        created_at=now.isoformat(),
        expires_at=(now + SESSION_TTL).isoformat(),
    )
    conn = store.get_connection()
    try:
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (%s, %s, %s, %s)",
            (session.token, session.user_id, session.created_at, session.expires_at),
        )
        conn.commit()
    finally:
        conn.close()
    return session


def get_session(token: str) -> Session | None:
    """Returns the session only if it exists and hasn't expired. An
    expired row is left in place (harmless, and cheap to prune later) -
    the caller just treats it as no session, same as a missing token."""
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT token, user_id, created_at, expires_at FROM sessions WHERE token = %s", (token,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    expires_at = datetime.fromisoformat(row["expires_at"])
    if expires_at < datetime.now(timezone.utc):
        return None
    return Session(row["token"], row["user_id"], row["created_at"], row["expires_at"])


def delete_session(token: str) -> None:
    conn = store.get_connection()
    try:
        conn.execute("DELETE FROM sessions WHERE token = %s", (token,))
        conn.commit()
    finally:
        conn.close()
