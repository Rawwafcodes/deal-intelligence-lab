#!/usr/bin/env python3
"""Task 11.3a: one-time transport of the real data from the old SQLite
database (data/deal_lab.db) into the new local Postgres database. Read-only
against the SQLite file - it is never written to, and stays on disk
afterward as a permanent historical reference (its own `.bak-*` sibling from
Task 11.2 stays too).

Generic by design: for each table, the column list is read straight off the
SQLite source via `PRAGMA table_info`, so this never needs hand-maintained
column lists that could drift from the real schema. Every one of the 11
schema-owning modules' `init_*_db()` functions is called first (identical to
server.py's own startup sequence) so every destination table already exists
in Postgres before any row is copied.

Usage:
    venv/bin/python migrate_sqlite_to_postgres.py [--sqlite-db PATH]

Verifies row counts match per table and spot-checks Task 11.2's own
migrated finding-snapshot content (the highest-value, most recently-changed
data) before reporting success.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import answer_keys
import cross_analyses
import cross_format_analyses
import documents
import evaluations
import inspections
import store
import validation_cases
import validation_runs
import workspaces
import xlsx_inspections

DEFAULT_SQLITE_DB = Path(__file__).parent / "data" / "deal_lab.db"

# Server startup order (server.py:main()) - no real FK constraints exist in
# either database, but this keeps the migration's own log output legible
# and matches how the app itself creates these tables.
TABLES_IN_ORDER = [
    "projects",
    "documents",
    "inspections",
    "xlsx_inspections",
    "cross_analyses",
    "cross_format_analyses",
    "validation_cases",
    "answer_key_versions",
    "validation_runs",
    "evaluations",
    "workspaces",
    "workspace_findings",
    "workspace_requests",
    "workspace_memos",
    "workspace_audit_log",
]


def init_all_postgres_tables() -> None:
    store.init_db()
    documents.init_documents_db()
    inspections.init_inspections_db()
    xlsx_inspections.init_xlsx_inspections_db()
    cross_analyses.init_cross_analyses_db()
    cross_format_analyses.init_cross_format_analyses_db()
    validation_cases.init_validation_cases_db()
    answer_keys.init_answer_keys_db()
    validation_runs.init_validation_runs_db()
    evaluations.init_evaluations_db()
    workspaces.init_workspaces_db()


def _sqlite_columns(sqlite_conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in sqlite_conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _pg_count(pg_conn, table: str) -> int:
    row = pg_conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
    assert row is not None  # COUNT(*) always returns exactly one row
    return row["n"]


def copy_table(sqlite_conn: sqlite3.Connection, pg_conn, table: str) -> tuple[int, int]:
    """Returns (source_row_count, rows_inserted)."""
    columns = _sqlite_columns(sqlite_conn, table)
    if not columns:
        return 0, 0  # table doesn't exist in the source (nothing to copy)

    column_list = ", ".join(columns)
    rows = sqlite_conn.execute(f"SELECT {column_list} FROM {table}").fetchall()

    placeholders = ", ".join(["%s"] * len(columns))
    insert_sql = f"INSERT INTO {table} ({column_list}) VALUES ({placeholders})"
    for row in rows:
        pg_conn.execute(insert_sql, tuple(row))
    return len(rows), len(rows)


def verify_counts(sqlite_conn: sqlite3.Connection, pg_conn) -> list[tuple[str, int, int]]:
    """Returns [(table, sqlite_count, postgres_count), ...]."""
    results = []
    for table in TABLES_IN_ORDER:
        columns = _sqlite_columns(sqlite_conn, table)
        sqlite_count = (
            sqlite_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] if columns else 0
        )
        pg_count = _pg_count(pg_conn, table)
        results.append((table, sqlite_count, pg_count))
    return results


def spot_check_finding_snapshots(sqlite_conn: sqlite3.Connection, pg_conn) -> list[str]:
    """Content equality check on the Task 11.2 finding-snapshot columns,
    the highest-value and most recently-written data in the real database.
    Returns a list of problems found (empty means clean)."""
    problems = []
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_rows = sqlite_conn.execute(
        "SELECT id, workspace_id, ai_snapshot_json, ai_content_hash FROM workspace_findings "
        "WHERE ai_snapshot_json IS NOT NULL"
    ).fetchall()
    for row in sqlite_rows:
        pg_row = pg_conn.execute(
            "SELECT ai_snapshot_json, ai_content_hash FROM workspace_findings WHERE workspace_id = %s AND id = %s",
            (row["workspace_id"], row["id"]),
        ).fetchone()
        if pg_row is None:
            problems.append(f"finding {row['id']} missing entirely in Postgres")
            continue
        if pg_row["ai_snapshot_json"] != row["ai_snapshot_json"]:
            problems.append(f"finding {row['id']}: ai_snapshot_json mismatch")
        if pg_row["ai_content_hash"] != row["ai_content_hash"]:
            problems.append(f"finding {row['id']}: ai_content_hash mismatch")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sqlite-db", type=Path, default=DEFAULT_SQLITE_DB, help="Path to the source SQLite file.")
    args = parser.parse_args(argv)

    if not args.sqlite_db.exists():
        print(f"No SQLite database at {args.sqlite_db}; nothing to migrate.")
        return 1

    print(f"Source (read-only): {args.sqlite_db}")
    print(f"Destination: Postgres schema '{store.SCHEMA}' at {store.PG_HOST}:{store.PG_PORT}/{store.PG_DBNAME}")

    init_all_postgres_tables()

    sqlite_conn = sqlite3.connect(f"file:{args.sqlite_db}?mode=ro", uri=True)
    pg_conn = store.get_connection()
    try:
        print("\nCopying tables:")
        for table in TABLES_IN_ORDER:
            existing_pg_count = _pg_count(pg_conn, table)
            if existing_pg_count > 0:
                print(f"  {table}: skipped - Postgres already has {existing_pg_count} row(s) (not re-copying)")
                continue
            source_count, inserted = copy_table(sqlite_conn, pg_conn, table)
            print(f"  {table}: copied {inserted} row(s) (source had {source_count})")
        pg_conn.commit()

        print("\nVerifying row counts:")
        all_match = True
        for table, sqlite_count, pg_count in verify_counts(sqlite_conn, pg_conn):
            status = "OK" if sqlite_count == pg_count else "MISMATCH"
            if sqlite_count != pg_count:
                all_match = False
            print(f"  {table}: sqlite={sqlite_count} postgres={pg_count} [{status}]")

        print("\nSpot-checking finding-snapshot content (Task 11.2 data):")
        problems = spot_check_finding_snapshots(sqlite_conn, pg_conn)
        if problems:
            for p in problems:
                print(f"  PROBLEM: {p}")
        else:
            print("  All migrated finding snapshots match byte-for-byte between SQLite and Postgres.")

        print("\nVERIFY:", "PASS" if all_match and not problems else "FAIL")
        return 0 if all_match and not problems else 1
    finally:
        sqlite_conn.close()
        pg_conn.close()


if __name__ == "__main__":
    sys.exit(main())
