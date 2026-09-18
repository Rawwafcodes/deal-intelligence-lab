"""Tests for mandates.py (roadmap M12.1-M12.3): the Mandate/Template/Plan/
Run/Attempt contracts, the fixture planner, the durable local Worker, and
(Task 12.3) the real reconciliation.cross_format capability adapter.

Task 12.2 changed execute_run()/resume_run() from synchronous (finished by
the time they return) to queue-and-hand-off (a Worker finishes them). Most
tests below call self.worker.poll_once() - one deterministic, synchronous
scan-and-process pass, with no sleep and no background thread - right
after queuing/resuming/cancelling a run, then assert on the resulting
persisted state. This proves the same lifecycle 12.1 proved, through the
new asynchronous contract, without flakiness. A dedicated WorkerThreadTests
class below separately proves the actual background-thread behavior
(execute_run returning before a real poll loop finishes the run) that
poll_once()-based determinism can't by itself demonstrate.

ReconciliationCapabilityTests (bottom of file) proves Task 12.3's adapter
wiring - not cross_format_analysis.py's own internal correctness, which
tests/test_cross_format_analysis.py and tests/test_reconcile_endpoint.py
already cover. Exactly like those files' own convention, no real network
call happens here: `cross_format_analysis.run_cross_format_analysis` itself
is replaced with a canned CrossFormatAnalysisOutcome, so these tests are
free to run in CI and prove the mandate-runtime side of the wiring (pinned
versions, the shared cross_format_analyses/workspaces/findings records,
run/attempt lifecycle, budget enforcement) with zero cost and zero
flakiness. The one real, paid call this task makes at all happens exactly
once, live, outside the automated suite - see the task file.
"""

import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import cross_format_analyses
import deal_briefs
import documents
import mandate_planning
import mandates
import store
import version_dependencies
import workspaces
from cross_format_analysis import AnalysisSegment, CrossFormatAnalysisOutcome, Part, PdfCitation


class MandateLifecycleTests(unittest.TestCase):
    def setUp(self):
        self._schema = f"test_{uuid.uuid4().hex}"
        self._original_schema = store.SCHEMA
        store.ensure_schema(self._schema)
        store.SCHEMA = self._schema
        store.init_db()
        version_dependencies.init_version_dependencies_db()
        mandates.init_mandates_db()
        self.project = store.create_project("Acme Merger", "")
        self.worker = mandates.Worker()

    def tearDown(self):
        store.SCHEMA = self._original_schema
        store.drop_schema(self._schema)

    # -- capability/template registries ----------------------------------

    def test_fixture_capability_is_registered(self):
        descriptor = mandates.get_capability("fixture.echo")
        self.assertIsNotNone(descriptor)
        self.assertEqual(descriptor.side_effect_class, "read_only")
        self.assertTrue(descriptor.permission_check(self.project.id))

    def test_both_builtin_templates_are_registered(self):
        # Not an exact-set assertion: the registry is a process-global,
        # code-level registry that other tests in this same process may
        # (deliberately) add throwaway templates/capabilities to - it is
        # meant to be extensible, not a fixed, closed list.
        keys = {t.key for t in mandates.list_templates()}
        self.assertTrue({"fixture-echo", "fixture-echo-with-review"} <= keys)

    # -- mandate creation ---------------------------------------------------

    def test_create_mandate_starts_in_draft(self):
        mandate = mandates.create_mandate(self.project.id, "Assess the Acme deal", created_by="u1")
        self.assertEqual(mandate.status, "draft")
        self.assertIsNone(mandate.current_plan_id)

    def test_blank_objective_is_rejected(self):
        with self.assertRaises(mandates.MandateValidationError):
            mandates.create_mandate(self.project.id, "   ", created_by="u1")

    def test_mandates_are_isolated_per_project(self):
        other = store.create_project("Other Deal", "")
        mandates.create_mandate(self.project.id, "Acme's mandate", created_by="u1")
        self.assertEqual(mandates.list_mandates(other.id), [])

    # -- plan validation ------------------------------------------------

    def test_validate_plan_stages_rejects_unregistered_capability(self):
        with self.assertRaises(mandates.PlanValidationError):
            mandates.validate_plan_stages([{"id": "s1", "capability": "not.real", "depends_on": []}])

    def test_validate_plan_stages_rejects_forward_dependency(self):
        with self.assertRaises(mandates.PlanValidationError):
            mandates.validate_plan_stages([
                {"id": "s1", "capability": "fixture.echo", "depends_on": ["s2"]},
                {"id": "s2", "capability": "fixture.echo", "depends_on": []},
            ])

    def test_validate_plan_stages_rejects_duplicate_ids(self):
        with self.assertRaises(mandates.PlanValidationError):
            mandates.validate_plan_stages([
                {"id": "s1", "capability": "fixture.echo", "depends_on": []},
                {"id": "s1", "capability": "fixture.echo", "depends_on": []},
            ])

    def test_propose_plan_rejects_unknown_template(self):
        mandate = mandates.create_mandate(self.project.id, "Assess the deal", created_by="u1")
        with self.assertRaises(mandates.PlanValidationError):
            mandates.propose_plan(self.project.id, mandate.id, "not-a-real-template")

    # -- propose / approve / reject --------------------------------------

    def test_propose_plan_moves_mandate_to_awaiting_approval(self):
        mandate = mandates.create_mandate(self.project.id, "Assess the deal", created_by="u1")
        plan = mandates.propose_plan(self.project.id, mandate.id, "fixture-echo")
        self.assertEqual(plan.status, "proposed")
        self.assertEqual(plan.revision_number, 1)
        # The mandate's own objective flows into the fixture stage's input.
        self.assertEqual(plan.stages[0]["input"]["message"], "Assess the deal")

        refreshed = mandates.get_mandate(self.project.id, mandate.id)
        self.assertEqual(refreshed.status, "awaiting_approval")

    def test_reproposing_supersedes_the_prior_proposed_plan(self):
        mandate = mandates.create_mandate(self.project.id, "Assess the deal", created_by="u1")
        first = mandates.propose_plan(self.project.id, mandate.id, "fixture-echo")
        second = mandates.propose_plan(self.project.id, mandate.id, "fixture-echo")
        self.assertEqual(second.revision_number, 2)
        first_reloaded = mandates.get_plan(mandate.id, first.id)
        self.assertEqual(first_reloaded.status, "superseded")

    def test_approve_plan_activates_the_mandate(self):
        mandate = mandates.create_mandate(self.project.id, "Assess the deal", created_by="u1")
        plan = mandates.propose_plan(self.project.id, mandate.id, "fixture-echo")
        approved = mandates.approve_plan(self.project.id, mandate.id, plan.id, approved_by="lead")
        self.assertEqual(approved.status, "approved")
        self.assertIsNotNone(approved.approved_at)

        refreshed = mandates.get_mandate(self.project.id, mandate.id)
        self.assertEqual(refreshed.status, "active")
        self.assertEqual(refreshed.current_plan_id, plan.id)

    def test_cannot_approve_an_already_approved_plan(self):
        mandate = mandates.create_mandate(self.project.id, "Assess the deal", created_by="u1")
        plan = mandates.propose_plan(self.project.id, mandate.id, "fixture-echo")
        mandates.approve_plan(self.project.id, mandate.id, plan.id, approved_by="lead")
        with self.assertRaises(mandates.MandateValidationError):
            mandates.approve_plan(self.project.id, mandate.id, plan.id, approved_by="lead")

    def test_reject_plan_returns_mandate_to_draft(self):
        mandate = mandates.create_mandate(self.project.id, "Assess the deal", created_by="u1")
        plan = mandates.propose_plan(self.project.id, mandate.id, "fixture-echo")
        rejected = mandates.reject_plan(self.project.id, mandate.id, plan.id)
        self.assertEqual(rejected.status, "rejected")
        self.assertEqual(mandates.get_mandate(self.project.id, mandate.id).status, "draft")

    # -- execution: single-stage template --------------------------------

    def test_execute_run_without_an_active_plan_is_rejected(self):
        mandate = mandates.create_mandate(self.project.id, "Assess the deal", created_by="u1")
        with self.assertRaises(mandates.MandateValidationError):
            mandates.execute_run(self.project.id, mandate.id)

    def test_execute_run_persists_as_queued_before_any_capability_runs(self):
        # Task 12.2's core contract: the run is a real, persisted fact -
        # acknowledged - before this function returns, and before any
        # capability has executed. No worker has touched it yet.
        mandate = mandates.create_mandate(self.project.id, "Assess the deal", created_by="u1")
        plan = mandates.propose_plan(self.project.id, mandate.id, "fixture-echo")
        mandates.approve_plan(self.project.id, mandate.id, plan.id, approved_by="lead")

        run = mandates.execute_run(self.project.id, mandate.id)
        self.assertEqual(run.status, "queued")
        self.assertIsNone(run.started_at)
        self.assertIsNotNone(run.queued_at)
        self.assertEqual(mandates.list_attempts(run.id), [])
        # It's a real row, independently readable - not just the return value.
        self.assertEqual(mandates.get_run(mandate.id, run.id).status, "queued")

    def test_execute_run_single_stage_succeeds_end_to_end(self):
        mandate = mandates.create_mandate(self.project.id, "Assess the Acme deal", created_by="u1")
        plan = mandates.propose_plan(self.project.id, mandate.id, "fixture-echo")
        mandates.approve_plan(self.project.id, mandate.id, plan.id, approved_by="lead")

        run = mandates.execute_run(self.project.id, mandate.id)
        self.worker.poll_once()
        run = mandates.get_run(mandate.id, run.id)
        self.assertEqual(run.status, "succeeded")
        self.assertIsNotNone(run.started_at)
        self.assertIsNotNone(run.finished_at)
        self.assertEqual(run.current_stage_index, 1)

        attempts = mandates.list_attempts(run.id)
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0].status, "succeeded")
        self.assertEqual(attempts[0].output["echoed"], "Assess the Acme deal")

        self.assertEqual(mandates.get_mandate(self.project.id, mandate.id).status, "completed")

    # -- execution: human checkpoint + resume ----------------------------

    def test_execute_run_stops_at_human_checkpoint(self):
        mandate = mandates.create_mandate(self.project.id, "Assess the deal", created_by="u1")
        plan = mandates.propose_plan(self.project.id, mandate.id, "fixture-echo-with-review")
        mandates.approve_plan(self.project.id, mandate.id, plan.id, approved_by="lead")

        run = mandates.execute_run(self.project.id, mandate.id)
        self.worker.poll_once()
        run = mandates.get_run(mandate.id, run.id)
        self.assertEqual(run.status, "waiting_for_input")
        # docs/04: "Active mandates can be waiting_for_input" - the pause
        # is a Run-level condition; the mandate itself stays "active".
        self.assertEqual(mandates.get_mandate(self.project.id, mandate.id).status, "active")

        attempts = mandates.list_attempts(run.id)
        self.assertEqual([a.status for a in attempts], ["succeeded", "awaiting_human"])

    def test_resume_run_continues_and_completes(self):
        mandate = mandates.create_mandate(self.project.id, "Assess the deal", created_by="u1")
        plan = mandates.propose_plan(self.project.id, mandate.id, "fixture-echo-with-review")
        mandates.approve_plan(self.project.id, mandate.id, plan.id, approved_by="lead")
        run = mandates.execute_run(self.project.id, mandate.id)
        self.worker.poll_once()

        resumed = mandates.resume_run(self.project.id, mandate.id, run.id, "review", decision="looks fine")
        self.assertEqual(resumed.status, "queued")  # handed back to the worker, not finished inline
        self.worker.poll_once()
        resumed = mandates.get_run(mandate.id, run.id)
        self.assertEqual(resumed.status, "succeeded")
        self.assertEqual(mandates.get_mandate(self.project.id, mandate.id).status, "completed")

        attempts = {a.stage_id: a for a in mandates.list_attempts(run.id)}
        self.assertEqual(attempts["review"].status, "succeeded")
        self.assertEqual(attempts["review"].output["decision"], "looks fine")

    def test_resume_run_when_not_waiting_is_rejected(self):
        mandate = mandates.create_mandate(self.project.id, "Assess the deal", created_by="u1")
        plan = mandates.propose_plan(self.project.id, mandate.id, "fixture-echo")
        mandates.approve_plan(self.project.id, mandate.id, plan.id, approved_by="lead")
        run = mandates.execute_run(self.project.id, mandate.id)
        self.worker.poll_once()  # already succeeded, no checkpoint
        with self.assertRaises(mandates.MandateValidationError):
            mandates.resume_run(self.project.id, mandate.id, run.id, "echo", decision="n/a")

    # -- cancellation -----------------------------------------------------

    def test_cancel_run_while_waiting_for_input(self):
        mandate = mandates.create_mandate(self.project.id, "Assess the deal", created_by="u1")
        plan = mandates.propose_plan(self.project.id, mandate.id, "fixture-echo-with-review")
        mandates.approve_plan(self.project.id, mandate.id, plan.id, approved_by="lead")
        run = mandates.execute_run(self.project.id, mandate.id)
        self.worker.poll_once()

        cancelled = mandates.cancel_run(self.project.id, mandate.id, run.id)
        self.assertEqual(cancelled.status, "cancelled")
        self.assertEqual(mandates.get_mandate(self.project.id, mandate.id).status, "cancelled")

        # Found during this task's own live browser verification: the
        # checkpoint's attempt must not be left "awaiting_human" forever -
        # a caller (e.g. the frontend) checking "is a decision still
        # needed?" off the attempt's own status must see it resolved too.
        review_attempt = next(a for a in mandates.list_attempts(run.id) if a.stage_id == "review")
        self.assertEqual(review_attempt.status, "failed")
        self.assertEqual(review_attempt.error, "run cancelled")

    def test_cancel_run_when_not_waiting_is_rejected(self):
        mandate = mandates.create_mandate(self.project.id, "Assess the deal", created_by="u1")
        plan = mandates.propose_plan(self.project.id, mandate.id, "fixture-echo")
        mandates.approve_plan(self.project.id, mandate.id, plan.id, approved_by="lead")
        run = mandates.execute_run(self.project.id, mandate.id)
        self.worker.poll_once()  # already succeeded
        with self.assertRaises(mandates.MandateValidationError):
            mandates.cancel_run(self.project.id, mandate.id, run.id)

    def test_cancel_run_while_queued_is_never_dispatched(self):
        # Task 12.2's actual improvement over 12.1: cancelling before the
        # worker ever picks the run up at all - not just while parked at a
        # checkpoint. Cancel first, poll second: the stage must never run.
        mandate = mandates.create_mandate(self.project.id, "Assess the deal", created_by="u1")
        plan = mandates.propose_plan(self.project.id, mandate.id, "fixture-echo")
        mandates.approve_plan(self.project.id, mandate.id, plan.id, approved_by="lead")
        run = mandates.execute_run(self.project.id, mandate.id)
        self.assertEqual(run.status, "queued")

        requested = mandates.cancel_run(self.project.id, mandate.id, run.id)
        self.assertEqual(requested.status, "cancel_requested")

        self.worker.poll_once()
        final = mandates.get_run(mandate.id, run.id)
        self.assertEqual(final.status, "cancelled")
        self.assertEqual(mandates.get_mandate(self.project.id, mandate.id).status, "cancelled")
        self.assertEqual(mandates.list_attempts(run.id), [])  # the echo stage never ran

    def test_cancel_run_mid_flight_stops_the_next_stage(self):
        # Proves "cancellation actually stops future stages of an
        # in-flight run" for a run the worker is *actively* executing
        # (not merely sitting queued) - deterministically, with no sleep
        # or second thread: the first stage's own executor calls
        # cancel_run on itself, simulating "someone clicked Cancel while
        # this stage was running". _run_stages must then never start the
        # second stage.
        calls: list[str] = []

        def cancel_from_within(project_id, stage_input):
            mandates.cancel_run(self.project.id, mandate.id, stage_input["run_id"])
            calls.append("first")
            return {"ok": True}

        def should_not_run(project_id, stage_input):
            calls.append("second")  # must never happen
            return {"ok": True}

        mandates.register_capability(
            mandates.CapabilityDescriptor(
                name="fixture.cancel_from_within", version="1", side_effect_class="read_only",
                permission_check=lambda project_id: True, executor=cancel_from_within,
            )
        )
        mandates.register_capability(
            mandates.CapabilityDescriptor(
                name="fixture.should_not_run", version="1", side_effect_class="read_only",
                permission_check=lambda project_id: True, executor=should_not_run,
            )
        )
        mandates.register_template(
            mandates.Template(
                key="fixture-cancel-midflight", version=1, name="Cancel midflight", description="test-only",
                stages=[
                    {"id": "s1", "kind": "capability", "capability": "fixture.cancel_from_within", "depends_on": []},
                    {"id": "s2", "kind": "capability", "capability": "fixture.should_not_run", "depends_on": ["s1"]},
                ],
            )
        )
        self.addCleanup(mandates._CAPABILITIES.pop, "fixture.cancel_from_within", None)
        self.addCleanup(mandates._CAPABILITIES.pop, "fixture.should_not_run", None)
        self.addCleanup(mandates._TEMPLATES.pop, "fixture-cancel-midflight", None)

        mandate = mandates.create_mandate(self.project.id, "Assess the deal", created_by="u1")
        plan = mandates.propose_plan(self.project.id, mandate.id, "fixture-cancel-midflight")
        mandates.approve_plan(self.project.id, mandate.id, plan.id, approved_by="lead")
        run = mandates.execute_run(self.project.id, mandate.id)

        # _default_input_for_stage doesn't know this capability, so its
        # input is normally {} - inject the run id it needs to call
        # cancel_run on itself. (Test-only wiring; not a runtime feature.)
        conn = store.get_connection()
        try:
            import json as _json
            row = conn.execute("SELECT stages_json FROM plan_revisions WHERE id = %s", (plan.id,)).fetchone()
            stages = _json.loads(row["stages_json"])
            stages[0]["input"] = {"run_id": run.id}
            conn.execute("UPDATE plan_revisions SET stages_json = %s WHERE id = %s", (_json.dumps(stages), plan.id))
            conn.commit()
        finally:
            conn.close()

        self.worker.poll_once()

        self.assertEqual(calls, ["first"])  # second stage never executed
        final = mandates.get_run(mandate.id, run.id)
        self.assertEqual(final.status, "cancelled")
        self.assertEqual(mandates.get_mandate(self.project.id, mandate.id).status, "cancelled")
        attempts = mandates.list_attempts(run.id)
        self.assertEqual([a.stage_id for a in attempts], ["s1"])
        self.assertEqual(attempts[0].status, "succeeded")

    # -- capability failure handling -------------------------------------

    def test_a_failing_capability_fails_the_run_and_mandate(self):
        def boom(project_id, stage_input):
            raise RuntimeError("simulated capability failure")

        mandates.register_capability(
            mandates.CapabilityDescriptor(
                name="fixture.boom", version="1", side_effect_class="read_only",
                permission_check=lambda project_id: True, executor=boom,
            )
        )
        mandates.register_template(
            mandates.Template(
                key="fixture-boom", version=1, name="Boom", description="fails deliberately",
                stages=[{"id": "s1", "kind": "capability", "capability": "fixture.boom", "depends_on": []}],
            )
        )
        self.addCleanup(mandates._CAPABILITIES.pop, "fixture.boom", None)
        self.addCleanup(mandates._TEMPLATES.pop, "fixture-boom", None)

        mandate = mandates.create_mandate(self.project.id, "Assess the deal", created_by="u1")
        plan = mandates.propose_plan(self.project.id, mandate.id, "fixture-boom")
        mandates.approve_plan(self.project.id, mandate.id, plan.id, approved_by="lead")

        run = mandates.execute_run(self.project.id, mandate.id)
        self.worker.poll_once()
        run = mandates.get_run(mandate.id, run.id)
        self.assertEqual(run.status, "failed")
        self.assertEqual(mandates.get_mandate(self.project.id, mandate.id).status, "failed")
        attempts = mandates.list_attempts(run.id)
        self.assertEqual(attempts[0].status, "failed")
        self.assertIn("simulated capability failure", attempts[0].error)

    def test_output_that_violates_its_own_declared_schema_fails_the_run(self):
        """Task 14.1: a capability's real return value is checked against
        its own declared output_schema - a capability whose output drifts
        from its own contract fails loudly (like any other executor
        exception), rather than silently persisting a malformed Attempt."""
        def under_promises(project_id, stage_input):
            return {"wrong_field": "not what the schema requires"}

        mandates.register_capability(
            mandates.CapabilityDescriptor(
                name="fixture.under_promises", version="1", side_effect_class="read_only",
                permission_check=lambda project_id: True, executor=under_promises,
                output_schema={"type": "object", "required": ["echoed"], "properties": {"echoed": {"type": "string"}}},
            )
        )
        mandates.register_template(
            mandates.Template(
                key="fixture-under-promises", version=1, name="Under-promises", description="test-only",
                stages=[{"id": "s1", "kind": "capability", "capability": "fixture.under_promises", "depends_on": []}],
            )
        )
        self.addCleanup(mandates._CAPABILITIES.pop, "fixture.under_promises", None)
        self.addCleanup(mandates._TEMPLATES.pop, "fixture-under-promises", None)

        mandate = mandates.create_mandate(self.project.id, "Assess the deal", created_by="u1")
        plan = mandates.propose_plan(self.project.id, mandate.id, "fixture-under-promises")
        mandates.approve_plan(self.project.id, mandate.id, plan.id, approved_by="lead")

        run = mandates.execute_run(self.project.id, mandate.id)
        self.worker.poll_once()
        run = mandates.get_run(mandate.id, run.id)
        self.assertEqual(run.status, "failed")
        attempts = mandates.list_attempts(run.id)
        self.assertEqual(attempts[0].status, "failed")
        self.assertIn("missing required field", attempts[0].error)

    # -- budget ledger (Task 12.2) ----------------------------------------

    def test_budget_exceeded_blocks_the_call_before_it_happens(self):
        called = []

        def tracked_echo(project_id, stage_input):
            called.append(True)
            return mandates._fixture_echo_executor(project_id, stage_input)

        mandates.register_capability(
            mandates.CapabilityDescriptor(
                name="fixture.tracked_echo", version="1", side_effect_class="read_only",
                permission_check=lambda project_id: True, executor=tracked_echo, unit_cost=1.0,
            )
        )
        mandates.register_template(
            mandates.Template(
                key="fixture-tracked-echo", version=1, name="Tracked echo", description="test-only",
                stages=[{"id": "s1", "kind": "capability", "capability": "fixture.tracked_echo", "depends_on": []}],
            )
        )
        self.addCleanup(mandates._CAPABILITIES.pop, "fixture.tracked_echo", None)
        self.addCleanup(mandates._TEMPLATES.pop, "fixture-tracked-echo", None)

        mandate = mandates.create_mandate(self.project.id, "Assess the deal", created_by="u1")
        plan = mandates.propose_plan(self.project.id, mandate.id, "fixture-tracked-echo")
        mandates.approve_plan(self.project.id, mandate.id, plan.id, approved_by="lead")

        run = mandates.execute_run(self.project.id, mandate.id, budget_limit=0.5)  # less than the 1.0 unit cost
        self.worker.poll_once()

        self.assertEqual(called, [])  # the capability was never actually invoked
        run = mandates.get_run(mandate.id, run.id)
        self.assertEqual(run.status, "failed")
        self.assertEqual(run.budget_consumed, 0.0)
        attempts = mandates.list_attempts(run.id)
        self.assertEqual(attempts[0].status, "failed")
        self.assertIn("budget exceeded", attempts[0].error)

    def test_budget_sufficient_allows_the_call_and_tracks_consumption(self):
        mandate = mandates.create_mandate(self.project.id, "Assess the deal", created_by="u1")
        plan = mandates.propose_plan(self.project.id, mandate.id, "fixture-echo")
        mandates.approve_plan(self.project.id, mandate.id, plan.id, approved_by="lead")

        run = mandates.execute_run(self.project.id, mandate.id, budget_limit=5.0)
        self.worker.poll_once()
        run = mandates.get_run(mandate.id, run.id)
        self.assertEqual(run.status, "succeeded")
        self.assertEqual(run.budget_consumed, 1.0)  # fixture.echo's own nominal unit_cost

    def test_budget_checked_between_stages_not_just_up_front(self):
        # A budget that covers the first stage but not the second: the
        # first stage's own success is preserved (not rolled back), the
        # second is blocked before it runs.
        mandate = mandates.create_mandate(self.project.id, "Assess the deal", created_by="u1")
        plan = mandates.propose_plan(self.project.id, mandate.id, "fixture-echo-with-review")
        mandates.approve_plan(self.project.id, mandate.id, plan.id, approved_by="lead")
        run = mandates.execute_run(self.project.id, mandate.id, budget_limit=1.0)
        self.worker.poll_once()
        run = mandates.get_run(mandate.id, run.id)
        # The human_checkpoint stage has no capability/cost, so this run
        # simply pauses as usual - budget only ever gates capability stages.
        self.assertEqual(run.status, "waiting_for_input")
        self.assertEqual(run.budget_consumed, 1.0)


class WorkerRecoveryTests(unittest.TestCase):
    """Simulates a crashed prior process by hand-crafting the exact
    persisted state a real crash would leave behind, then proving
    Worker.recover() (called once, at startup, before the poll loop
    starts - see Worker.start()) turns it into either a safely resumed run
    or an explicit outcome_unknown - never silence."""

    def setUp(self):
        self._schema = f"test_{uuid.uuid4().hex}"
        self._original_schema = store.SCHEMA
        store.ensure_schema(self._schema)
        store.SCHEMA = self._schema
        store.init_db()
        version_dependencies.init_version_dependencies_db()
        mandates.init_mandates_db()
        self.project = store.create_project("Acme Merger", "")
        self.worker = mandates.Worker()

    def tearDown(self):
        store.SCHEMA = self._original_schema
        store.drop_schema(self._schema)

    def _prepare_approved_two_stage_mandate(self):
        mandate = mandates.create_mandate(self.project.id, "Assess the deal", created_by="u1")
        plan = mandates.propose_plan(self.project.id, mandate.id, "fixture-echo-with-review")
        mandates.approve_plan(self.project.id, mandate.id, plan.id, approved_by="lead")
        return mandate, plan

    def test_recover_requeues_a_run_interrupted_cleanly_between_stages(self):
        mandate, plan = self._prepare_approved_two_stage_mandate()
        run = mandates.execute_run(self.project.id, mandate.id)
        # Hand-craft "the prior process died right after starting to
        # execute this run, before finishing any stage" - a Run marked
        # "running" with zero attempts recorded is unambiguous: nothing
        # was ever in flight.
        mandates._set_run(run.id, status="running", started_at=mandates._now())

        self.worker.recover()
        recovered = mandates.get_run(mandate.id, run.id)
        self.assertEqual(recovered.status, "queued")  # safe to requeue

        self.worker.poll_once()
        finished = mandates.get_run(mandate.id, run.id)
        self.assertEqual(finished.status, "waiting_for_input")  # resumed and ran to its natural pause

    def test_recover_reports_outcome_unknown_for_a_genuinely_in_flight_attempt(self):
        mandate, plan = self._prepare_approved_two_stage_mandate()
        run = mandates.execute_run(self.project.id, mandate.id)
        # Hand-craft "the prior process died while the echo capability's
        # own executor call was live" - the exact state _run_stages leaves
        # behind between _record_attempt(status="running") and the
        # matching _update_attempt call (see _run_stages' own comments).
        mandates._set_run(run.id, status="running", started_at=mandates._now())
        mandates._record_attempt(run.id, "echo", capability="fixture.echo", status="running", output=None, error=None)

        self.worker.recover()
        recovered = mandates.get_run(mandate.id, run.id)
        self.assertEqual(recovered.status, "outcome_unknown")
        self.assertIsNotNone(recovered.finished_at)
        self.assertEqual(mandates.get_mandate(self.project.id, mandate.id).status, "under_review")

        attempts = mandates.list_attempts(run.id)
        self.assertEqual(attempts[0].status, "failed")
        self.assertIn("outcome unknown", attempts[0].error)

        # Not automatically retried (docs/04) - poll_once must leave it
        # alone; a human has to look at it (the Mandate is "under_review").
        self.worker.poll_once()
        self.assertEqual(mandates.get_run(mandate.id, run.id).status, "outcome_unknown")

    def test_recover_leaves_a_waiting_for_input_run_untouched(self):
        mandate, plan = self._prepare_approved_two_stage_mandate()
        run = mandates.execute_run(self.project.id, mandate.id)
        self.worker.poll_once()
        paused = mandates.get_run(mandate.id, run.id)
        self.assertEqual(paused.status, "waiting_for_input")

        self.worker.recover()  # a genuine restart would call this at startup
        still_paused = mandates.get_run(mandate.id, run.id)
        self.assertEqual(still_paused.status, "waiting_for_input")
        self.assertEqual(mandates.get_mandate(self.project.id, mandate.id).status, "active")

    def test_recover_finalizes_a_stale_cancel_requested_run(self):
        mandate, plan = self._prepare_approved_two_stage_mandate()
        run = mandates.execute_run(self.project.id, mandate.id)
        # A cancel requested against a queued run that the prior process
        # died before ever finalizing.
        mandates._set_run(run.id, status="cancel_requested")

        self.worker.poll_once()
        final = mandates.get_run(mandate.id, run.id)
        self.assertEqual(final.status, "cancelled")
        self.assertEqual(mandates.get_mandate(self.project.id, mandate.id).status, "cancelled")


class WorkerThreadTests(unittest.TestCase):
    """The one thing poll_once()-based determinism can't itself prove: that
    a *real* background thread, started independently of any request,
    genuinely finishes a run on its own after execute_run() has already
    returned - real durability, not just a synchronous call in disguise."""

    def setUp(self):
        self._schema = f"test_{uuid.uuid4().hex}"
        self._original_schema = store.SCHEMA
        store.ensure_schema(self._schema)
        store.SCHEMA = self._schema
        store.init_db()
        version_dependencies.init_version_dependencies_db()
        mandates.init_mandates_db()
        self.project = store.create_project("Acme Merger", "")
        self.worker = mandates.Worker(poll_interval=0.02)
        self.worker.start()

    def tearDown(self):
        self.worker.stop()
        store.SCHEMA = self._original_schema
        store.drop_schema(self._schema)

    def _wait_for_terminal_status(self, mandate_id, run_id, timeout=2.0):
        deadline = time.monotonic() + timeout
        terminal = {"succeeded", "failed", "cancelled", "outcome_unknown", "waiting_for_input"}
        run = mandates.get_run(mandate_id, run_id)
        while run.status not in terminal and time.monotonic() < deadline:
            time.sleep(0.01)
            run = mandates.get_run(mandate_id, run_id)
        if run.status not in terminal:
            self.fail(f"run did not reach a terminal status within {timeout}s (last: {run.status!r})")
        return run

    def test_background_thread_finishes_a_run_after_execute_run_returns(self):
        mandate = mandates.create_mandate(self.project.id, "Assess the Acme deal", created_by="u1")
        plan = mandates.propose_plan(self.project.id, mandate.id, "fixture-echo")
        mandates.approve_plan(self.project.id, mandate.id, plan.id, approved_by="lead")

        run = mandates.execute_run(self.project.id, mandate.id)
        self.assertEqual(run.status, "queued")  # nothing has run yet, by construction

        finished = self._wait_for_terminal_status(mandate.id, run.id)
        self.assertEqual(finished.status, "succeeded")
        self.assertEqual(mandates.get_mandate(self.project.id, mandate.id).status, "completed")

    def test_background_thread_finishes_a_resumed_run(self):
        mandate = mandates.create_mandate(self.project.id, "Assess the deal", created_by="u1")
        plan = mandates.propose_plan(self.project.id, mandate.id, "fixture-echo-with-review")
        mandates.approve_plan(self.project.id, mandate.id, plan.id, approved_by="lead")
        run = mandates.execute_run(self.project.id, mandate.id)
        self._wait_for_terminal_status(mandate.id, run.id)  # reaches waiting_for_input

        mandates.resume_run(self.project.id, mandate.id, run.id, "review", decision="approved live")
        finished = self._wait_for_terminal_status(mandate.id, run.id)
        self.assertEqual(finished.status, "succeeded")


PDF_BYTES = b"%PDF-1.4\n%Confidential information memorandum, harmless test bytes\n%%EOF"
XLSX_BYTES = b"PK\x03\x04fake-xlsx-bytes-for-reconciliation-capability-tests"

FINDINGS_TEXT = (
    "## Reconciliation Findings\n"
    "- **Title:** Term-sheet price gap\n"
    "**Classification:** cross-source conflict\n"
    "**Severity:** critical\n"
    "**Explanation:** the price differs across sources.\n"
    "**PDF evidence:** "
)
FINDINGS_TEXT_TAIL = (
    "\n**Workbook evidence:** the model says $10m.\n"
    "**Commercial or financial relevance:** determines the offer price.\n"
    "**Uncertainty:** fully supported by citations\n"
    "**Recommended action:** ask the seller to reconcile.\n\n"
)


def _fake_outcome(success=True, segments=None, error_message=None):
    return CrossFormatAnalysisOutcome(
        success=success,
        transmitted=True,
        analysis_seconds=4.2,
        model="claude-opus-5",
        stop_reason="end_turn" if success else None,
        usage={"input_tokens": 4000, "output_tokens": 900} if success else None,
        segments=segments,
        error_type=None if success else "provider_error",
        error_message=error_message,
    )


class ReconciliationCapabilityTests(unittest.TestCase):
    """Task 12.3: the real reconciliation.cross_format capability, adapted
    from the exact same two functions server.py's pre-existing, non-mandate
    reconciliation route already calls - see mandates._reconciliation_executor's
    own docstring. No real network call anywhere in this class (see the
    module docstring)."""

    def setUp(self):
        self._schema = f"test_{uuid.uuid4().hex}"
        self._original_schema = store.SCHEMA
        self._tmpdir = tempfile.TemporaryDirectory()
        self._original_data_dir = documents.DATA_DIR
        documents.DATA_DIR = Path(self._tmpdir.name) / "DealLabData"
        store.ensure_schema(self._schema)
        store.SCHEMA = self._schema
        store.init_db()
        documents.init_documents_db()
        cross_format_analyses.init_cross_format_analyses_db()
        workspaces.init_workspaces_db()
        version_dependencies.init_version_dependencies_db()
        mandates.init_mandates_db()
        self.project = store.create_project("Reconciliation Capability Tests", "")
        self.pdf_doc = documents.save_uploaded_file(self.project.id, "im.pdf", "", PDF_BYTES).document
        self.xlsx_doc = documents.save_uploaded_file(self.project.id, "model.xlsx", "", XLSX_BYTES).document
        self.worker = mandates.Worker()

    def tearDown(self):
        store.SCHEMA = self._original_schema
        store.drop_schema(self._schema)
        documents.DATA_DIR = self._original_data_dir
        self._tmpdir.cleanup()

    def _propose_and_approve(self, document_ids=None):
        mandate = mandates.create_mandate(self.project.id, "Reconcile Q3 financials", created_by="u1")
        plan = mandates.propose_plan(
            self.project.id, mandate.id, "reconciliation",
            stage_inputs={"reconcile": {"document_ids": document_ids or [self.pdf_doc.id, self.xlsx_doc.id]}},
        )
        mandates.approve_plan(self.project.id, mandate.id, plan.id, approved_by="lead")
        return mandate, plan

    # -- registration ------------------------------------------------------

    def test_capability_and_template_are_registered(self):
        descriptor = mandates.get_capability("reconciliation.cross_format")
        self.assertIsNotNone(descriptor)
        self.assertEqual(descriptor.side_effect_class, "external_paid_call")
        template = mandates.get_template("reconciliation")
        self.assertIsNotNone(template)
        self.assertEqual(template.stages[0]["capability"], "reconciliation.cross_format")

    # -- plan proposal / pinned manifest ------------------------------------

    def test_propose_plan_without_document_ids_is_rejected(self):
        mandate = mandates.create_mandate(self.project.id, "Reconcile Q3 financials", created_by="u1")
        with self.assertRaises(mandates.PlanValidationError):
            mandates.propose_plan(self.project.id, mandate.id, "reconciliation")

    def test_propose_plan_rejects_an_empty_document_ids_list(self):
        """Task 14.1: enforced by the capability's own declared
        input_schema (minItems: 1) now, not a hand-written truthiness
        check specific to this one capability."""
        mandate = mandates.create_mandate(self.project.id, "Reconcile Q3 financials", created_by="u1")
        with self.assertRaises(mandates.PlanValidationError):
            mandates.propose_plan(
                self.project.id, mandate.id, "reconciliation", stage_inputs={"reconcile": {"document_ids": []}},
            )

    def test_propose_plan_rejects_a_non_string_document_id(self):
        mandate = mandates.create_mandate(self.project.id, "Reconcile Q3 financials", created_by="u1")
        with self.assertRaises(mandates.PlanValidationError):
            mandates.propose_plan(
                self.project.id, mandate.id, "reconciliation", stage_inputs={"reconcile": {"document_ids": [123]}},
            )

    def test_propose_plan_rejects_a_deleted_or_unknown_document(self):
        mandate = mandates.create_mandate(self.project.id, "Reconcile Q3 financials", created_by="u1")
        with self.assertRaises(mandates.PlanValidationError):
            mandates.propose_plan(
                self.project.id, mandate.id, "reconciliation",
                stage_inputs={"reconcile": {"document_ids": ["does-not-exist"]}},
            )

    def test_propose_plan_pins_current_document_versions(self):
        mandate = mandates.create_mandate(self.project.id, "Reconcile Q3 financials", created_by="u1")
        plan = mandates.propose_plan(
            self.project.id, mandate.id, "reconciliation",
            stage_inputs={"reconcile": {"document_ids": [self.pdf_doc.id, self.xlsx_doc.id]}},
        )
        stage = plan.stages[0]
        self.assertEqual(sorted(stage["input"]["document_ids"]), sorted([self.pdf_doc.id, self.xlsx_doc.id]))
        self.assertEqual(stage["input"]["pinned_versions"][self.pdf_doc.id], self.pdf_doc.current_version_id)
        self.assertEqual(stage["input"]["pinned_versions"][self.xlsx_doc.id], self.xlsx_doc.current_version_id)

    # -- execution: success, shared findings --------------------------------

    def test_execute_run_produces_real_shared_records_and_findings(self):
        mandate, plan = self._propose_and_approve()
        fake_outcome = _fake_outcome(segments=[
            AnalysisSegment(
                parts=[Part(type="text", text=FINDINGS_TEXT)],
                pdf_citations=[PdfCitation(cited_text="Revenue is $12m", document_id=self.pdf_doc.id,
                                            document_title="im.pdf", start_page=1, end_page=1)],
            ),
            AnalysisSegment(parts=[Part(type="text", text=FINDINGS_TEXT_TAIL)]),
        ])

        with patch("mandates.cross_format_analysis.run_cross_format_analysis", return_value=fake_outcome) as mock_run:
            run = mandates.execute_run(self.project.id, mandate.id)
            self.worker.poll_once()
            mock_run.assert_called_once()
            # The real adapter, not a re-derivation - the exact Document
            # objects it was handed.
            called_docs = mock_run.call_args.args[0]
            self.assertEqual({d.id for d in called_docs}, {self.pdf_doc.id, self.xlsx_doc.id})

        run = mandates.get_run(mandate.id, run.id)
        self.assertEqual(run.status, "succeeded")
        self.assertEqual(mandates.get_mandate(self.project.id, mandate.id).status, "completed")

        attempts = mandates.list_attempts(run.id)
        self.assertEqual(attempts[0].status, "succeeded")
        output = attempts[0].output
        self.assertTrue(output["workspace_created"])
        self.assertEqual(output["finding_count"], 1)

        # Not a mandate-only silo (docs/04: "no parallel mandate-only
        # finding silo") - the exact same records the pre-existing,
        # non-mandate reconciliation route and the static workspace page
        # already read and write.
        record = cross_format_analyses.get_cross_format_analysis(self.project.id, output["cross_format_analysis_id"])
        self.assertIsNotNone(record)
        self.assertEqual(record.status, "success")
        self.assertEqual(sorted(record.pdf_document_ids + record.excel_document_ids),
                          sorted([self.pdf_doc.id, self.xlsx_doc.id]))

        workspace = workspaces.get_workspace(self.project.id, output["workspace_id"])
        self.assertIsNotNone(workspace)
        findings = workspaces.list_findings(workspace, record)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["title"], "Term-sheet price gap")
        self.assertEqual(findings[0]["severity"], "critical")

    def test_reproposing_after_success_creates_a_second_real_run(self):
        # Idempotent workspace creation: running reconciliation again against
        # the same analysis-less mandate creates a *new* analysis (each run
        # is its own immutable record) but get_or_create_workspace is keyed
        # per-analysis, so this just proves two runs don't corrupt each
        # other - not exhaustive, just a sanity check on the adapter reusing
        # shared, keyed-by-analysis-id state correctly.
        mandate, plan = self._propose_and_approve()
        with patch("mandates.cross_format_analysis.run_cross_format_analysis", return_value=_fake_outcome(segments=None)):
            run = mandates.execute_run(self.project.id, mandate.id)
            self.worker.poll_once()
        output = mandates.list_attempts(run.id)[0].output
        self.assertEqual(output["finding_count"], 0)
        self.assertTrue(output["workspace_created"])

    # -- execution: failure handling ----------------------------------------

    def test_a_failed_outcome_still_persists_the_audit_record_but_fails_the_run(self):
        mandate, plan = self._propose_and_approve()
        with patch(
            "mandates.cross_format_analysis.run_cross_format_analysis",
            return_value=_fake_outcome(success=False, error_message="the model returned an error"),
        ):
            run = mandates.execute_run(self.project.id, mandate.id)
            self.worker.poll_once()

        run = mandates.get_run(mandate.id, run.id)
        self.assertEqual(run.status, "failed")
        self.assertEqual(mandates.get_mandate(self.project.id, mandate.id).status, "failed")
        attempts = mandates.list_attempts(run.id)
        self.assertEqual(attempts[0].status, "failed")
        self.assertIn("the model returned an error", attempts[0].error)

        # The audit trail survives the failure - same as the pre-existing
        # non-mandate route's own behavior (it always records the attempt,
        # success or not).
        conn = store.get_connection()
        try:
            rows = conn.execute(
                "SELECT status FROM cross_format_analyses WHERE project_id = %s", (self.project.id,)
            ).fetchall()
        finally:
            conn.close()
        self.assertEqual([r["status"] for r in rows], ["error"])

    def test_pinned_version_drift_fails_the_attempt_without_calling_the_provider(self):
        mandate, plan = self._propose_and_approve()
        # Simulates "someone replaced this document after the plan was
        # approved" - docs/03's "pinned sources" is enforced, not just
        # recorded.
        documents.add_version(self.project.id, self.pdf_doc.id, PDF_BYTES + b"\nchanged")

        with patch("mandates.cross_format_analysis.run_cross_format_analysis") as mock_run:
            run = mandates.execute_run(self.project.id, mandate.id)
            self.worker.poll_once()
            mock_run.assert_not_called()

        run = mandates.get_run(mandate.id, run.id)
        self.assertEqual(run.status, "failed")
        attempts = mandates.list_attempts(run.id)
        self.assertIn("newer version", attempts[0].error)

    # -- budget ledger (Task 12.2, exercised against a real capability) -----

    def test_budget_exceeded_blocks_the_paid_call(self):
        mandate, plan = self._propose_and_approve()
        run = mandates.execute_run(self.project.id, mandate.id, budget_limit=0.5)  # unit_cost is 1.0
        with patch("mandates.cross_format_analysis.run_cross_format_analysis") as mock_run:
            self.worker.poll_once()
            mock_run.assert_not_called()

        run = mandates.get_run(mandate.id, run.id)
        self.assertEqual(run.status, "failed")
        attempts = mandates.list_attempts(run.id)
        self.assertIn("budget exceeded", attempts[0].error)


class CapabilityContractTests(unittest.TestCase):
    """Task 14.1: formalizes docs/04-mandate-engine.md's capability-
    boundary contract - 'Register each capability with: name/version;
    input schema; output schema; allowed formats...' - as real, checked
    fields on CapabilityDescriptor rather than prose alone. No database
    needed: every assertion here is against the module-level capability
    registry and the pure _validate_against_schema helper."""

    def test_every_registered_capability_declares_input_and_output_schemas(self):
        for name in ("fixture.echo", "reconciliation.cross_format"):
            descriptor = mandates.get_capability(name)
            self.assertIsNotNone(descriptor)
            assert descriptor is not None
            self.assertEqual(descriptor.input_schema.get("type"), "object")
            self.assertEqual(descriptor.output_schema.get("type"), "object")

    def test_reconciliation_declares_its_allowed_source_formats(self):
        descriptor = mandates.get_capability("reconciliation.cross_format")
        assert descriptor is not None
        self.assertEqual(descriptor.allowed_source_formats, (".pdf", ".xlsx", ".xls"))

    def test_fixture_echo_has_no_source_formats(self):
        descriptor = mandates.get_capability("fixture.echo")
        assert descriptor is not None
        self.assertIsNone(descriptor.allowed_source_formats)

    def test_schema_validator_accepts_a_conforming_reconciliation_input(self):
        descriptor = mandates.get_capability("reconciliation.cross_format")
        assert descriptor is not None
        mandates._validate_against_schema(
            {"document_ids": ["doc-1"], "pinned_versions": {"doc-1": "v1"}}, descriptor.input_schema, "test",
        )  # must not raise

    def test_schema_validator_rejects_missing_required_field(self):
        descriptor = mandates.get_capability("reconciliation.cross_format")
        assert descriptor is not None
        with self.assertRaises(mandates.PlanValidationError):
            mandates._validate_against_schema({}, descriptor.input_schema, "test")

    def test_schema_validator_rejects_empty_document_ids_list(self):
        descriptor = mandates.get_capability("reconciliation.cross_format")
        assert descriptor is not None
        with self.assertRaises(mandates.PlanValidationError):
            mandates._validate_against_schema({"document_ids": []}, descriptor.input_schema, "test")

    def test_schema_validator_rejects_a_non_string_document_id(self):
        descriptor = mandates.get_capability("reconciliation.cross_format")
        assert descriptor is not None
        with self.assertRaises(mandates.PlanValidationError):
            mandates._validate_against_schema({"document_ids": [123]}, descriptor.input_schema, "test")

    def test_schema_validator_accepts_a_conforming_reconciliation_output(self):
        descriptor = mandates.get_capability("reconciliation.cross_format")
        assert descriptor is not None
        mandates._validate_against_schema(
            {
                "cross_format_analysis_id": "a1", "workspace_id": "w1", "workspace_created": True,
                "finding_count": 3, "model": "claude-opus-5",
            },
            descriptor.output_schema, "test",
        )  # must not raise

    def test_schema_validator_rejects_output_missing_a_required_field(self):
        descriptor = mandates.get_capability("reconciliation.cross_format")
        assert descriptor is not None
        with self.assertRaises(mandates.PlanValidationError):
            mandates._validate_against_schema({"cross_format_analysis_id": "a1"}, descriptor.output_schema, "test")

    def test_fixture_echo_executor_output_matches_its_own_declared_schema(self):
        """A self-consistency check that the pattern also holds for the
        one other registered capability, not only reconciliation."""
        descriptor = mandates.get_capability("fixture.echo")
        assert descriptor is not None
        output = descriptor.executor("proj-1", {"message": "hi"})
        mandates._validate_against_schema(output, descriptor.output_schema, "test")  # must not raise


class ReconciliationWithReviewTests(unittest.TestCase):
    """Task 12.5 (reuse proof): the `reconciliation-with-review` template
    combines two already-registered/already-proven building blocks - the
    real `reconciliation.cross_format` capability (12.3) and the
    `human_checkpoint` stage kind (12.1) - in a new way, with zero new
    executor code. These tests exist to prove the *combination* works
    (the checkpoint genuinely pauses after real reconciliation output
    exists, and resuming genuinely completes the mandate), not to
    re-prove either building block's own correctness a second time - that
    coverage already lives in ReconciliationCapabilityTests (the
    capability) and MandateLifecycleTests/WorkerRecoveryTests (checkpoint
    pause/resume/recovery, generically). Same no-real-network-call
    convention: `cross_format_analysis.run_cross_format_analysis` is
    mocked throughout."""

    def setUp(self):
        self._schema = f"test_{uuid.uuid4().hex}"
        self._original_schema = store.SCHEMA
        self._tmpdir = tempfile.TemporaryDirectory()
        self._original_data_dir = documents.DATA_DIR
        documents.DATA_DIR = Path(self._tmpdir.name) / "DealLabData"
        store.ensure_schema(self._schema)
        store.SCHEMA = self._schema
        store.init_db()
        documents.init_documents_db()
        cross_format_analyses.init_cross_format_analyses_db()
        workspaces.init_workspaces_db()
        version_dependencies.init_version_dependencies_db()
        mandates.init_mandates_db()
        self.project = store.create_project("Reconciliation With Review Tests", "")
        self.pdf_doc = documents.save_uploaded_file(self.project.id, "im.pdf", "", PDF_BYTES).document
        self.xlsx_doc = documents.save_uploaded_file(self.project.id, "model.xlsx", "", XLSX_BYTES).document
        self.worker = mandates.Worker()

    def tearDown(self):
        store.SCHEMA = self._original_schema
        store.drop_schema(self._schema)
        documents.DATA_DIR = self._original_data_dir
        self._tmpdir.cleanup()

    def _propose_and_approve(self):
        mandate = mandates.create_mandate(self.project.id, "Reconcile Q3 financials, then review", created_by="u1")
        plan = mandates.propose_plan(
            self.project.id, mandate.id, "reconciliation-with-review",
            stage_inputs={"reconcile": {"document_ids": [self.pdf_doc.id, self.xlsx_doc.id]}},
        )
        mandates.approve_plan(self.project.id, mandate.id, plan.id, approved_by="lead")
        return mandate, plan

    def test_template_and_document_selection_reuse_the_existing_mechanisms(self):
        template = mandates.get_template("reconciliation-with-review")
        self.assertIsNotNone(template)
        self.assertEqual(
            [s["id"] for s in template.stages], ["reconcile", "review"],
        )
        self.assertEqual(template.stages[1]["kind"], "human_checkpoint")
        self.assertEqual(template.stages[1]["depends_on"], ["reconcile"])
        # No document_ids -> still rejected exactly like the plain
        # "reconciliation" template - _default_input_for_stage doesn't
        # care which template a reconcile stage belongs to.
        mandate = mandates.create_mandate(self.project.id, "Reconcile something", created_by="u1")
        with self.assertRaises(mandates.PlanValidationError):
            mandates.propose_plan(self.project.id, mandate.id, "reconciliation-with-review")

    def test_run_pauses_after_real_reconciliation_output_then_resumes_to_completion(self):
        mandate, plan = self._propose_and_approve()
        fake_outcome = _fake_outcome(segments=[
            AnalysisSegment(
                parts=[Part(type="text", text=FINDINGS_TEXT)],
                pdf_citations=[PdfCitation(cited_text="Revenue is $12m", document_id=self.pdf_doc.id,
                                            document_title="im.pdf", start_page=1, end_page=1)],
            ),
            AnalysisSegment(parts=[Part(type="text", text=FINDINGS_TEXT_TAIL)]),
        ])

        with patch("mandates.cross_format_analysis.run_cross_format_analysis", return_value=fake_outcome):
            run = mandates.execute_run(self.project.id, mandate.id)
            self.worker.poll_once()

        # Paused at the checkpoint - not completed - but the real
        # reconciliation output already exists, exactly as if the plain
        # "reconciliation" template had been used: the review stage
        # reviews something real, not a placeholder.
        run = mandates.get_run(mandate.id, run.id)
        self.assertEqual(run.status, "waiting_for_input")
        self.assertEqual(mandates.get_mandate(self.project.id, mandate.id).status, "active")

        attempts = mandates.list_attempts(run.id)
        reconcile_attempt = next(a for a in attempts if a.stage_id == "reconcile")
        self.assertEqual(reconcile_attempt.status, "succeeded")
        self.assertTrue(reconcile_attempt.output["workspace_created"])
        review_attempt = next(a for a in attempts if a.stage_id == "review")
        self.assertEqual(review_attempt.status, "awaiting_human")

        workspace = workspaces.get_workspace(self.project.id, reconcile_attempt.output["workspace_id"])
        self.assertIsNotNone(workspace)
        record = cross_format_analyses.get_cross_format_analysis(
            self.project.id, reconcile_attempt.output["cross_format_analysis_id"]
        )
        findings = workspaces.list_findings(workspace, record)
        self.assertEqual(len(findings), 1)  # real findings exist before any human has reviewed them

        mandates.resume_run(self.project.id, mandate.id, run.id, "review", decision="Reviewed - escalate the critical item.")
        self.worker.poll_once()

        run = mandates.get_run(mandate.id, run.id)
        self.assertEqual(run.status, "succeeded")
        self.assertEqual(mandates.get_mandate(self.project.id, mandate.id).status, "completed")
        review_attempt = next(a for a in mandates.list_attempts(run.id) if a.stage_id == "review")
        self.assertEqual(review_attempt.output, {"decision": "Reviewed - escalate the critical item."})

    def test_cancelling_while_paused_at_review_does_not_lose_the_real_findings(self):
        # Task 12.2's own cancel-while-waiting fix (mandates.cancel_run),
        # exercised here against a real capability's output for the first
        # time - the findings/workspace already produced by "reconcile"
        # are not affected by cancelling the mandate at the checkpoint.
        mandate, plan = self._propose_and_approve()
        with patch("mandates.cross_format_analysis.run_cross_format_analysis", return_value=_fake_outcome(segments=None)):
            run = mandates.execute_run(self.project.id, mandate.id)
            self.worker.poll_once()

        workspace_id = mandates.list_attempts(run.id)[0].output["workspace_id"]
        mandates.cancel_run(self.project.id, mandate.id, run.id)

        run = mandates.get_run(mandate.id, run.id)
        self.assertEqual(run.status, "cancelled")
        self.assertIsNotNone(workspaces.get_workspace(self.project.id, workspace_id))

    def test_llm_planner_can_select_the_review_template(self):
        # Task 12.4's planner reasons generically over list_templates() -
        # this is the first test proving that generalization actually
        # extends to a template registered after 12.4 was built, with no
        # planner code change.
        mandate = mandates.create_mandate(self.project.id, "Reconcile the term sheet, with a review step", created_by="u1")
        outcome = mandate_planning.PlanProposalOutcome(
            status="proposed", template_key="reconciliation-with-review",
            document_ids=[self.pdf_doc.id, self.xlsx_doc.id],
            reasoning="Objective explicitly asks for a review step after reconciling.",
        )
        with patch("mandates.mandate_planning.propose_candidate_plan", return_value=outcome) as mock_call:
            result = mandates.propose_plan_llm(self.project.id, mandate.id)

        self.assertEqual(result.status, "proposed")
        self.assertEqual(result.plan.template_key, "reconciliation-with-review")
        self.assertEqual([s["id"] for s in result.plan.stages], ["reconcile", "review"])
        template_keys_seen = {t.key: t.needs_documents for t in mock_call.call_args.kwargs["templates"]}
        self.assertTrue(template_keys_seen["reconciliation-with-review"])


class LlmPlanningTests(unittest.TestCase):
    """Task 12.4: mandates.propose_plan_llm's own independent
    re-verification of a model's candidate plan - document existence,
    project scoping, the PDF/Excel structural check, and the untrusted-plan
    validator - proven against a real project/document set. The planning
    call itself (mandate_planning.propose_candidate_plan) is mocked here,
    exactly like tests/test_mandate_planning.py mocks the Anthropic client
    one layer further down: no real network call anywhere in this class."""

    def setUp(self):
        self._schema = f"test_{uuid.uuid4().hex}"
        self._original_schema = store.SCHEMA
        self._tmpdir = tempfile.TemporaryDirectory()
        self._original_data_dir = documents.DATA_DIR
        documents.DATA_DIR = Path(self._tmpdir.name) / "DealLabData"
        store.ensure_schema(self._schema)
        store.SCHEMA = self._schema
        store.init_db()
        documents.init_documents_db()
        deal_briefs.init_deal_briefs_db()
        version_dependencies.init_version_dependencies_db()
        mandates.init_mandates_db()
        self.project = store.create_project("LLM Planning Tests", "")
        self.other_project = store.create_project("A Different Deal", "")
        self.pdf_doc = documents.save_uploaded_file(self.project.id, "term_sheet.pdf", "", PDF_BYTES).document
        self.xlsx_doc = documents.save_uploaded_file(self.project.id, "model.xlsx", "", XLSX_BYTES).document
        self.foreign_doc = documents.save_uploaded_file(self.other_project.id, "other.pdf", "", PDF_BYTES).document

    def tearDown(self):
        store.SCHEMA = self._original_schema
        store.drop_schema(self._schema)
        documents.DATA_DIR = self._original_data_dir
        self._tmpdir.cleanup()

    def _fake_llm_outcome(self, **overrides):
        defaults = dict(
            status="proposed", template_key="reconciliation",
            document_ids=[self.pdf_doc.id, self.xlsx_doc.id],
            reasoning="Clear PDF/Excel pair for the term sheet.",
            unsupported_reason=None, model="claude-sonnet-5",
            usage={"input_tokens": 900, "output_tokens": 120},
        )
        defaults.update(overrides)
        return mandate_planning.PlanProposalOutcome(**defaults)

    # -- happy path: a confident, valid candidate becomes a real plan ----

    def test_confident_proposal_creates_a_real_plan_revision(self):
        mandate = mandates.create_mandate(self.project.id, "Reconcile the term sheet against the model", created_by="u1")
        with patch("mandates.mandate_planning.propose_candidate_plan", return_value=self._fake_llm_outcome()) as mock_call:
            result = mandates.propose_plan_llm(self.project.id, mandate.id)

        self.assertEqual(result.status, "proposed")
        self.assertIsNotNone(result.plan)
        self.assertEqual(result.plan.template_key, "reconciliation")
        self.assertEqual(result.plan.proposed_by, "llm")
        self.assertEqual(result.plan.planner_reasoning, "Clear PDF/Excel pair for the term sheet.")
        self.assertEqual(
            sorted(result.plan.stages[0]["input"]["document_ids"]),
            sorted([self.pdf_doc.id, self.xlsx_doc.id]),
        )
        # Pinned exactly like a manual proposal (Task 12.3's own mechanism,
        # untouched - see _default_input_for_stage).
        self.assertEqual(
            result.plan.stages[0]["input"]["pinned_versions"][self.pdf_doc.id], self.pdf_doc.current_version_id
        )

        # The human approval gate is completely unaffected - this only ever
        # reaches "proposed", never "active".
        self.assertEqual(mandates.get_mandate(self.project.id, mandate.id).status, "awaiting_approval")

        # The model saw only metadata - never file bytes/content - and the
        # objective/brief/templates it was actually handed.
        call_kwargs = mock_call.call_args.kwargs
        self.assertEqual(call_kwargs["objective"], mandate.objective)
        self.assertIsNone(call_kwargs["brief"])  # no brief exists yet for this project
        doc_ids_seen = {d.id for d in call_kwargs["documents"]}
        self.assertEqual(doc_ids_seen, {self.pdf_doc.id, self.xlsx_doc.id})
        template_keys_seen = {t.key: t.needs_documents for t in call_kwargs["templates"]}
        self.assertTrue(template_keys_seen["reconciliation"])
        self.assertFalse(template_keys_seen["fixture-echo"])

    def test_brief_is_passed_to_the_planner_when_one_exists(self):
        deal_briefs.create_version(
            self.project.id,
            {"parties": "Buyer Co and Target Co", "objective": "Assess valuation", "perspective": "",
             "scope": "", "periods": "", "uncertainties": ""},
            created_by="u1",
        )
        mandate = mandates.create_mandate(self.project.id, "Reconcile the term sheet", created_by="u1")
        with patch("mandates.mandate_planning.propose_candidate_plan", return_value=self._fake_llm_outcome()) as mock_call:
            mandates.propose_plan_llm(self.project.id, mandate.id)
        brief_seen = mock_call.call_args.kwargs["brief"]
        self.assertIsNotNone(brief_seen)
        self.assertEqual(brief_seen["parties"], "Buyer Co and Target Co")

    def test_feedback_is_passed_through_to_the_planner(self):
        mandate = mandates.create_mandate(self.project.id, "Reconcile the term sheet", created_by="u1")
        with patch("mandates.mandate_planning.propose_candidate_plan", return_value=self._fake_llm_outcome()) as mock_call:
            mandates.propose_plan_llm(self.project.id, mandate.id, feedback="Use model.xlsx, not an older workbook.")
        self.assertEqual(mock_call.call_args.kwargs["feedback"], "Use model.xlsx, not an older workbook.")

    # -- the model's own honest "unsupported" is trusted as-is -----------

    def test_model_reported_unsupported_creates_no_plan(self):
        mandate = mandates.create_mandate(self.project.id, "Reconcile something", created_by="u1")
        outcome = self._fake_llm_outcome(
            status="unsupported", template_key=None, document_ids=[],
            unsupported_reason="ambiguous document pairing",
        )
        with patch("mandates.mandate_planning.propose_candidate_plan", return_value=outcome):
            result = mandates.propose_plan_llm(self.project.id, mandate.id)

        self.assertEqual(result.status, "unsupported")
        self.assertEqual(result.reason, "ambiguous document pairing")
        self.assertIsNone(result.plan)
        self.assertEqual(mandates.list_plans(mandate.id), [])
        self.assertEqual(mandates.get_mandate(self.project.id, mandate.id).status, "draft")

    def test_planning_call_error_is_passed_through(self):
        mandate = mandates.create_mandate(self.project.id, "Reconcile something", created_by="u1")
        outcome = mandate_planning.PlanProposalOutcome(
            status="error", error_type="rate_limit", error_message="Rate limit reached.",
        )
        with patch("mandates.mandate_planning.propose_candidate_plan", return_value=outcome):
            result = mandates.propose_plan_llm(self.project.id, mandate.id)
        self.assertEqual(result.status, "error")
        self.assertEqual(result.reason, "Rate limit reached.")
        self.assertEqual(mandates.list_plans(mandate.id), [])

    # -- untrusted output: every independent check must actually reject --

    def test_unregistered_template_is_rejected_as_unsupported(self):
        mandate = mandates.create_mandate(self.project.id, "Reconcile something", created_by="u1")
        outcome = self._fake_llm_outcome(template_key="not-a-real-template", document_ids=[])
        with patch("mandates.mandate_planning.propose_candidate_plan", return_value=outcome):
            result = mandates.propose_plan_llm(self.project.id, mandate.id)
        self.assertEqual(result.status, "unsupported")
        self.assertIn("unregistered template", result.reason)
        self.assertEqual(mandates.list_plans(mandate.id), [])

    def test_hallucinated_document_id_is_rejected_not_dropped(self):
        mandate = mandates.create_mandate(self.project.id, "Reconcile something", created_by="u1")
        outcome = self._fake_llm_outcome(document_ids=[self.pdf_doc.id, "does-not-exist"])
        with patch("mandates.mandate_planning.propose_candidate_plan", return_value=outcome):
            result = mandates.propose_plan_llm(self.project.id, mandate.id)
        self.assertEqual(result.status, "unsupported")
        self.assertIn("does-not-exist", result.reason)
        self.assertEqual(mandates.list_plans(mandate.id), [])

    def test_cross_project_document_id_is_rejected(self):
        # foreign_doc is real, but belongs to self.other_project - a
        # hallucination isn't the only way an id can be illegitimate here;
        # documents.get_document is itself project-scoped, so this rejects
        # exactly the same way a made-up id does.
        mandate = mandates.create_mandate(self.project.id, "Reconcile something", created_by="u1")
        outcome = self._fake_llm_outcome(document_ids=[self.pdf_doc.id, self.foreign_doc.id])
        with patch("mandates.mandate_planning.propose_candidate_plan", return_value=outcome):
            result = mandates.propose_plan_llm(self.project.id, mandate.id)
        self.assertEqual(result.status, "unsupported")
        self.assertIn(self.foreign_doc.id, result.reason)
        self.assertEqual(mandates.list_plans(mandate.id), [])

    def test_invalid_pdf_excel_mix_is_rejected(self):
        # Only a PDF, no Excel - cross_format_analysis.validate_selection's
        # own structural check, run before any plan is created, not
        # deferred to execution time.
        mandate = mandates.create_mandate(self.project.id, "Reconcile something", created_by="u1")
        outcome = self._fake_llm_outcome(document_ids=[self.pdf_doc.id])
        with patch("mandates.mandate_planning.propose_candidate_plan", return_value=outcome):
            result = mandates.propose_plan_llm(self.project.id, mandate.id)
        self.assertEqual(result.status, "unsupported")
        self.assertIn("missing_excel", result.reason)
        self.assertEqual(mandates.list_plans(mandate.id), [])

    def test_empty_document_selection_for_a_template_needing_one_is_rejected(self):
        mandate = mandates.create_mandate(self.project.id, "Reconcile something", created_by="u1")
        outcome = self._fake_llm_outcome(document_ids=[])
        with patch("mandates.mandate_planning.propose_candidate_plan", return_value=outcome):
            result = mandates.propose_plan_llm(self.project.id, mandate.id)
        self.assertEqual(result.status, "unsupported")
        self.assertEqual(mandates.list_plans(mandate.id), [])

    def test_a_template_needing_no_documents_ignores_document_ids(self):
        mandate = mandates.create_mandate(self.project.id, "Just echo the objective", created_by="u1")
        outcome = self._fake_llm_outcome(template_key="fixture-echo", document_ids=["irrelevant"])
        with patch("mandates.mandate_planning.propose_candidate_plan", return_value=outcome):
            result = mandates.propose_plan_llm(self.project.id, mandate.id)
        self.assertEqual(result.status, "proposed")
        self.assertEqual(result.plan.stages[0]["input"], {"message": mandate.objective})

    # -- replanning: a new revision, never a mutation of the old one -----

    def test_reproposing_supersedes_the_prior_proposed_plan_with_a_new_revision(self):
        mandate = mandates.create_mandate(self.project.id, "Reconcile the term sheet", created_by="u1")
        with patch("mandates.mandate_planning.propose_candidate_plan", return_value=self._fake_llm_outcome()):
            first = mandates.propose_plan_llm(self.project.id, mandate.id)

        with patch("mandates.mandate_planning.propose_candidate_plan", return_value=self._fake_llm_outcome()):
            second = mandates.propose_plan_llm(self.project.id, mandate.id, feedback="Actually, double-check the pair.")

        self.assertEqual(second.plan.revision_number, first.plan.revision_number + 1)
        plans = {p.id: p for p in mandates.list_plans(mandate.id)}
        self.assertEqual(plans[first.plan.id].status, "superseded")
        self.assertEqual(plans[second.plan.id].status, "proposed")
        # The first revision's own row is untouched, not rewritten -
        # docs/03's revision-counter pattern: only its status changed.
        self.assertEqual(plans[first.plan.id].stages, first.plan.stages)

    # -- the model can never approve its own plan or checkpoints ---------

    def test_llm_proposal_never_auto_approves(self):
        mandate = mandates.create_mandate(self.project.id, "Reconcile the term sheet", created_by="u1")
        with patch("mandates.mandate_planning.propose_candidate_plan", return_value=self._fake_llm_outcome()):
            result = mandates.propose_plan_llm(self.project.id, mandate.id)
        self.assertEqual(result.plan.status, "proposed")
        self.assertEqual(mandates.get_mandate(self.project.id, mandate.id).status, "awaiting_approval")
        with self.assertRaises(mandates.MandateValidationError):
            mandates.execute_run(self.project.id, mandate.id)  # not active - never approved

    # -- mandate-level guards, inherited from propose_plan unchanged -----

    def test_mandate_not_found(self):
        with self.assertRaises(ValueError):
            mandates.propose_plan_llm(self.project.id, "not-a-real-mandate")

    def test_cannot_propose_once_active(self):
        mandate = mandates.create_mandate(self.project.id, "Reconcile the term sheet", created_by="u1")
        with patch("mandates.mandate_planning.propose_candidate_plan", return_value=self._fake_llm_outcome()):
            result = mandates.propose_plan_llm(self.project.id, mandate.id)
        mandates.approve_plan(self.project.id, mandate.id, result.plan.id, approved_by="lead")
        with patch("mandates.mandate_planning.propose_candidate_plan", return_value=self._fake_llm_outcome()):
            with self.assertRaises(mandates.MandateValidationError):
                mandates.propose_plan_llm(self.project.id, mandate.id)


if __name__ == "__main__":
    unittest.main()
